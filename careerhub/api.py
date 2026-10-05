"""api module of Career Hub. See MAP.md for what lives where."""
from pathlib import Path
import asyncio
import datetime
import imaplib
import re
import shutil
from .answers import Answers
from .apply_run import run_apply
from .bridge import UI, log, os_open
from .changelog import CHANGELOG
from .config import APP_NAME, APP_VERSION, BACKUP_DIR, DATA, DRAFT_DIR, FILES_DIR, LOG_DIR, OWNER, REPORT_DIR, SKIP
from .finder import location_ok, match_score, run_find, title_score
from .gmail import check_mail, mail_settings
from . import history, planner
from .overview import jobs_overview
from .profile_form import profile_values
from .records import add_to_jobs_file, read_jobs_file
from .reports import my_issues, send_report, send_suggestion
from .resume import resume_info
from .state import TASKS
from .textutil import split_list
from .store import ProfileError, app_state, data, load_profile, export_csv, folder_files, save_app_state, save_data, table_of
from .textutil import norm, norm_link
from .updater import check_for_update, install_latest, install_zip, prefetch_update
from .ai import ai_answer, ai_prep
from .research import company_brief
from .state import APP, MAIL
from .config import UPDATE_SOURCE
from .records import tracker_rows



def start_task(coro):
    t = asyncio.get_running_loop().create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)


def _vkey(v):
    return tuple(int(x) if x.isdigit() else 0 for x in str(v).split("."))


NEW_PAGES = None                                # decided once per launch


def _new_pages():
    """Pages that got a new feature or improvement (bug fixes don't count), shown with a "new" tag only on the
    first launch after an update; later launches show none. A page leaves the list when she opens it."""
    global NEW_PAGES
    if NEW_PAGES is None:
        seen = app_state().get("pages_version")
        NEW_PAGES = [] if seen is None else sorted({p for e in CHANGELOG if _vkey(e["version"]) > _vkey(seen)
                                                    for p in e.get("pages", [])}) if seen != APP_VERSION else []
        if seen != APP_VERSION:
            save_app_state(pages_version=APP_VERSION)
    return NEW_PAGES


async def api_page_seen(page):
    if page in _new_pages():
        NEW_PAGES.remove(page)
    return True


async def api_state():
    try:
        profile = profile_values()
        err = ""
    except ProfileError as e:
        profile, err = [], str(e)
    email = next((f["value"] for f in profile if f["key"] == "e ?mail"), "")
    st = app_state()
    due = False
    if st.get("daily") and st.get("find_tokens"):
        try:
            last = datetime.datetime.fromisoformat(st.get("last_find", "2000-01-01T00:00:00"))
            due = (datetime.datetime.now() - last).total_seconds() > 20 * 3600
        except Exception:
            due = True
    return {"version": APP_VERSION, "daily": bool(st.get("daily")), "daily_due": due,
            "find_roles": st.get("find_roles", ""), "find_companies": ", ".join(
                t for t in st.get("find_tokens", []) if t != "auto"), "find_auto": "auto" in st.get("find_tokens", ["auto"]),
            "profile": profile, "profile_error": err, "files": folder_files(),
            "jobs_text": "\n".join(read_jobs_file()), "app_name": APP_NAME, "owner": OWNER,
            "theme": st.get("theme", "clean"), "font": st.get("font", "classic"), "calm": bool(st.get("calm")), "alert_show": st.get("alert_show", ""), "new_pages": _new_pages(), "changelog": CHANGELOG,
            "whats_new": st.get("last_seen_version") not in (None, APP_VERSION),
            "first_run": st.get("last_seen_version") is None,
            "needs_profile": (not email) or "example.com" in email, "busy": UI.busy,
            "themes": THEMES, "update_source": str(data()["profile"]["settings"].get("update_source") or UPDATE_SOURCE),
            "last_update_check": st.get("last_update_check", ""), "find_diag": st.get("find_diag", {})}


async def api_save_profile(items):
    try:
        prof = data()["profile"]
        for it in items:
            where, key, value = it["where"], it["key"], str(it.get("value", "")).strip()
            if where == "settings":
                if key in ("minimum_match", "max_job_age_days", "jobsite_daily_limit") and value.isdigit():
                    prof["settings"][key] = int(value)
                else:
                    prof["settings"][key] = value
            elif value:
                prof[where][key] = value
            else:
                prof[where].pop(key, None)          # empty box = "ask me when a site needs it"
        save_data()
        from .state import RESUME_CACHE
        RESUME_CACHE["text"] = None                     # a different resume may have been picked
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


async def api_save_list(text):
    data()["saved_links"] = [l.strip() for l in text.split() if l.strip().lower().startswith("http")]
    save_data()
    return {"ok": True, "count": len(read_jobs_file())}


async def api_add_to_list(links):
    existing = {norm_link(l) for l in read_jobs_file()}
    new = [l for l in links if norm_link(l) not in existing]
    add_to_jobs_file(new)
    return {"ok": True, "added": len(new)}


async def api_start_apply(links):
    links = [l.strip().strip("'\"") for l in links if l.strip().lower().startswith("http")]
    links = list(dict.fromkeys(links))
    if UI.busy:
        return {"ok": False, "error": "Already working. Wait for it to finish or press Stop."}
    if not links:
        return {"ok": False, "error": "No job links found. Links start with http."}
    start_task(run_apply(links))
    return {"ok": True}


async def api_resume():
    try:
        db = Answers()
    except ProfileError as e:
        return {"ok": False, "error": str(e)}
    prof = resume_info(db)
    if prof is None:
        return {"ok": False, "error": "Couldn't read your resume. Drop it into Resume → Your files, "
                                      "pick it as Resume, and Save profile."}
    return {"ok": True, **prof}


async def api_start_find(roles_text, companies_text, auto, all_openings=False):
    if UI.busy:
        return {"ok": False, "error": "Already working. Wait for it to finish or press Stop."}
    roles = [norm(x) for x in (roles_text or "").split(",") if x.strip()]
    tokens = [t.strip() for t in (companies_text or "").split(",") if t.strip()]
    if auto and not all_openings:
        tokens.append("auto")
    if not tokens:
        return {"ok": False, "error": "Add a company name first, or choose “Find jobs for me”."}
    if not roles and not all_openings:
        try:
            has_resume = resume_info(Answers()) is not None
        except ProfileError:
            has_resume = False
        if not has_resume:
            return {"ok": False, "error": "I need a job title to look for. Add one above, or add your resume in Resume → Your files."}
    start_task(run_find(roles, tokens, bool(all_openings)))
    return {"ok": True}


async def api_answers():
    mem = data()["answers"]
    return [[k, "" if v == SKIP else v, v == SKIP] for k, v in sorted(mem.items())]


async def api_save_answers(rows):
    mem = {}
    for k, v, never in rows:
        if never:
            mem[k] = SKIP
        elif str(v).strip():
            mem[k] = str(v).strip()
    data()["answers"] = mem
    save_data()
    return {"ok": True, "count": len(mem)}


async def api_set_daily(flag):
    save_app_state(daily=bool(flag))
    return True


THEMES = ["clean", "sand", "emerald", "slate", "mint"]
FONTS = ["classic", "friendly", "elegant", "bold", "handwritten"]


async def api_home():
    jobs, updates = jobs_overview()
    now = datetime.datetime.now()
    week_ago = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    applied = [j for j in jobs if j["status"].startswith("Submitted")]
    stages = {}
    for j in applied:
        stages[j["stage"]] = stages.get(j["stage"], 0) + 1
    replied = sum(1 for j in applied if j["stage"] in ("Interview", "Waiting", "Assessment", "Offer", "Rejected"))
    st = app_state()
    ms = mail_settings()
    due = False
    if ms["auto"] and ms["addr"] and ms["pw"]:
        try:
            due = (now - datetime.datetime.fromisoformat(st.get("last_mail_check", "2000-01-01T00:00:00"))
                   ).total_seconds() > 3 * 3600
        except Exception:
            due = True
    weekly = []
    today = now.date()
    start = today - datetime.timedelta(days=today.weekday())
    for w in range(7, -1, -1):
        ws = start - datetime.timedelta(weeks=w)
        we = ws + datetime.timedelta(days=7)
        n = sum(1 for j in applied if ws.isoformat() <= j["date"][:10] < we.isoformat())
        weekly.append({"label": ws.strftime("%d %b"), "count": n})
    two_weeks_ago = (now - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
    # counted from the same job cards as the stat boxes above it (not from raw emails), so the numbers always agree
    recent = [j for j in applied if j.get("latest") and (j["latest"].get("date") or "")[:10] >= week_ago]
    summary = {"sent": sum(1 for j in applied if j["date"][:10] >= week_ago),
               "sent_before": sum(1 for j in applied if two_weeks_ago <= j["date"][:10] < week_ago),
               "replies": sum(1 for j in recent if j["latest"]["type"] in ("interview", "assessment", "offer", "rejection")),
               "interviews": sum(1 for j in recent if j["stage"] in ("Interview", "Waiting", "Assessment")),
               "offers": sum(1 for j in recent if j["stage"] == "Offer"),
               "follow_up": sum(1 for j in applied if j["stage"] == "Applied" and 0 < len(j["date"]) and
                                j["date"][:10] <= (today - datetime.timedelta(days=7)).isoformat())}   # applied 7+ days ago, no reply yet
    soon = []                                           # the Today strip: interviews today or tomorrow that haven't happened yet
    for e in planner.list_events():
        if e["date"] == today.isoformat() and not (e.get("time") and e["time"] < now.strftime("%H:%M")) or \
                e["date"] == (today + datetime.timedelta(days=1)).isoformat():
            soon.append({"day": "Today" if e["date"] == today.isoformat() else "Tomorrow", "time": e.get("time", ""),
                         "title": e["title"], "company": e.get("company", ""), "ref": e.get("ref", "")})
    today_strip = {"events": soon, "drafts": sum(1 for j in jobs if j["stage"] == "Draft"), "follow_up": summary["follow_up"]}
    return {"weekly": weekly, "summary": summary, "today": today_strip, "stages": stages, "stats": {"applied": len(applied), "week": sum(1 for j in applied if j["date"][:10] >= week_ago),
                      "interviews": stages.get("Interview", 0) + stages.get("Waiting", 0) + stages.get("Assessment", 0),
                      "offers": stages.get("Offer", 0), "rejected": stages.get("Rejected", 0),
                      "waiting": stages.get("Applied", 0) + stages.get("Waiting", 0),
                      "reply_rate": round(100 * replied / len(applied)) if applied else 0,
                      "drafts": sum(1 for j in jobs if j["stage"] == "Draft")},
            "attention": [u for u in updates if not u.get("done")][:10],
            "feed": updates[:15], "mail_total": len(updates), "mail_ready": bool(ms["addr"] and ms["pw"]), "mail_due": due,
            "mail_error": st.get("last_mail_error", ""),
            "last_mail_check": st.get("last_mail_check", ""), "list_count": len(read_jobs_file()),
            "events": planner.list_events(), "todos": data()["todos"], "cheer": cheer_due(),
            "mail_busy": MAIL["busy"], "mail_progress": MAIL.get("progress", "")}


async def api_add_event(title, date, time="", company="", note="", link=""):
    return planner.add_event(title, date, time, company, note, link=link)


async def api_delete_event(eid):
    planner.delete_event(eid)
    return True


async def api_set_job_event(key, stage, company, title, date, time=""):
    return planner.set_job_event(key, stage, company, title, date, time)


async def api_add_todo(text):
    return planner.add_todo(text)


async def api_set_todo(tid, done):
    planner.set_todo(tid, done)
    return True


async def api_delete_todo(tid):
    planner.delete_todo(tid)
    return True


async def api_clear_done_todos():
    planner.clear_done_todos()
    return True


def cheer_due():
    """True when more than 6 rejection emails are in, and again after every 5 more."""
    n = sum(1 for u in data()["email_updates"] if u.get("type") == "rejection")
    last = app_state().get("cheer_at", 0)
    return n if n > 6 and n >= (last + 5 if last else 7) else 0


async def api_cheer_seen(n):
    save_app_state(cheer_at=int(n))
    return True


async def api_history():
    return history.get_history()


async def api_save_history(h):
    history.save_history(h or {})
    return history.get_history()


async def api_read_history():
    """A draft from the resume for her to check. Nothing is saved until she presses Save."""
    from .resume import read_resume
    text = await asyncio.to_thread(read_resume, Answers())
    if not text:
        return {"ok": False, "error": "I can't find your resume. Add it under Your files first."}
    h = history.parse_history(text)
    if not h["work"] and not h["education"]:
        log("   Resume headings I saw: " + " | ".join(l.strip() for l in text.splitlines() if history._heading(l) or len(l.strip()) < 30)[:600])
    if not h["work"] and not h["education"]:
        return {"ok": False, "error": "I couldn't find work or education sections in the resume. You can type them in below."}
    return {"ok": True, **h}


async def api_jobs():
    jobs, updates = jobs_overview()
    return {"jobs": jobs, "updates": updates}


async def api_set_note(key, stage, notes):
    auto = next((j["auto_stage"] for j in jobs_overview()[0] if j["key"] == key), "")
    data()["notes"][key] = {"stage": stage or "", "notes": notes or "", "auto": auto}   # her choice holds until a newer email changes the auto stage
    if stage in ("Applied", "Draft", "NoResponse"):                  # moved back before any interview: its calendar entry goes too
        planner.drop_job_event(key)
    save_data()
    return True


async def api_dismiss(uid):
    for u in data()["email_updates"]:
        if u["id"] == uid:
            u["done"] = True
    save_data()
    return True


async def api_not_job(uid):
    """'Not a job email': hides the card, its calendar entry, and every later mail from that sender."""
    u = next((x for x in data()["email_updates"] if x["id"] == uid), None)
    if not u:
        return {"ok": False}
    who = (u.get("from_addr") or u.get("from") or "").strip().lower()
    if who and who not in data()["mail_blocked"]:
        data()["mail_blocked"].append(who)
    data()["email_updates"][:] = [x for x in data()["email_updates"] if (x.get("from_addr") or x.get("from") or "").strip().lower() != who]
    data()["events"][:] = [e for e in data()["events"] if e.get("mail_id") != uid]
    save_data()
    return {"ok": True, "who": u.get("from") or who}


async def api_check_mail(manual=False):
    r = await check_mail(manual=manual)
    if not r.get("busy"):                               # a check already running sends its own "done"
        await UI.emit({"type": "mail_done", "manual": bool(manual), **r})
    return r


async def api_test_mail():
    ms = mail_settings()
    if not ms["addr"] or not ms["pw"]:
        return {"ok": False, "error": "Fill in the Gmail address and app password, then Save profile first."}

    def _test():
        M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        M.login(ms["addr"], ms["pw"])
        M.select("INBOX", readonly=True)
        M.logout()
    try:
        await asyncio.to_thread(_test)
        return {"ok": True}
    except Exception as e:
        m = str(e)
        if "AUTHENTICATIONFAILED" in m.upper() or "credentials" in m.lower():
            m = "Gmail refused the login: check the address and the 16-letter app password."
        return {"ok": False, "error": m[:200]}


async def api_report(note, images=None):
    try:
        return await send_report(note, images)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_my_issues():
    try:
        return await my_issues()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_suggest(text, images=None):
    try:
        return await send_suggestion(text, images)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_check_update(manual=False):
    r = await check_for_update()
    if r.get("available"):
        asyncio.create_task(prefetch_update())
    if r.get("available") or manual:
        await UI.emit({"type": "update_check", "manual": bool(manual), **r})
    return r


async def api_install_latest():
    if UI.busy:
        return {"ok": False, "error": "Finish or stop the current run first."}
    return await install_latest()


async def api_install_zip(b64):
    import base64
    if UI.busy:
        return {"ok": False, "error": "Finish or stop the current run first."}
    try:
        return {"ok": True, "version": install_zip(base64.b64decode(b64))}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_restart():
    """Closes the window; main() then returns RESTART_CODE and the launcher starts the new version."""
    APP["restart"] = True
    try:
        await UI.page.context.close()
    except Exception:
        pass
    return True


# ---- Resume page ----

def _resume_versions(db):
    """[(info for the page, path)] for the main resume and the 2nd / 3rd ones from Settings."""
    from .store import resolve_path
    main = next((v for k, v in db.files.items() if "resume" in k and v), "")
    out, seen = [], set()
    for label, f, kw in [("Main resume", main, "")] + [(f"Resume {i}", db.settings.get(f"resume_{i}_file") or "",
                                                         db.settings.get(f"resume_{i}_keywords") or "") for i in (2, 3)]:
        f = str(f).strip()
        if f and Path(f).name not in seen:
            seen.add(Path(f).name)
            p = resolve_path(f)
            out.append(({"label": label, "file": Path(f).name, "keywords": str(kw), "exists": p.is_file(),
                         "pdf": p.suffix.lower() == ".pdf"}, p))
    return out


async def _resume_pick(name):
    """(versions, chosen info, its text) for the Resume page."""
    from .resume import pdf_text
    vs = _resume_versions(Answers())
    info, path = next(((i, p) for i, p in vs if i["file"] == name), vs[0] if vs else (None, None))
    text = await asyncio.to_thread(pdf_text, path) if info and info["exists"] and info["pdf"] else ""
    return [i for i, _ in vs], info, text


async def api_resume_page(name=""):
    """Everything the Resume page shows for one version: its text, the ATS check and skills to build."""
    from .resume import resume_profile
    from .resume_tools import ats_check, skill_gaps, target_roles
    try:
        versions, info, text = await _resume_pick(name)
        db = Answers()
    except ProfileError as e:
        return {"ok": False, "error": str(e), "versions": []}
    if not info:
        return {"ok": False, "versions": [], "error": "Add your resume first: drop it into Your files on this page."}
    roles = target_roles(app_state().get("find_roles", ""), resume_profile(text)["roles"] if text else [])
    return {"ok": True, "versions": versions, "file": info["file"], "text": text[:20000],
            "ats": ats_check(text) if info["exists"] and info["pdf"] else None,
            "gaps": skill_gaps(text, roles), "ai": db.ai_on}


async def api_resume_pdf(name=""):
    """The resume PDF itself (base64) for the preview. Only her resume versions, never any other file."""
    import base64
    try:
        vs = _resume_versions(Answers())
    except ProfileError:
        return {"ok": False}
    p = next((p for i, p in vs if i["file"] == name and i["exists"] and i["pdf"]), None)
    if p is None or p.stat().st_size > 15_000_000:
        return {"ok": False}
    return {"ok": True, "b64": base64.b64encode(p.read_bytes()).decode()}


async def api_resume_open(name=""):
    try:
        p = next((p for i, p in _resume_versions(Answers()) if i["file"] == name and i["exists"]), None)
    except ProfileError:
        p = None
    if p is None:
        return False
    os_open(p)
    return True


async def _job_text(job):
    """Job text she pasted, or the text of the job page when she pasted a link."""
    from .resume_tools import html_to_text
    from .state import PW
    job = str(job or "").strip()
    if not re.match(r"https?://\S+$", job):
        return job
    req = await PW["p"].request.new_context()
    try:
        r = await req.get(job, timeout=20000)
        text = html_to_text(await r.text()) if r.ok else ""
    except Exception:
        text = ""
    finally:
        await req.dispose()
    return text if len(text) > 300 else ""


async def api_resume_match(job, name=""):
    """How well one resume fits one job: keywords the job asks for that are in / missing from the resume."""
    from .resume_tools import job_roles, job_skills, keyword_match, skill_gaps
    text = await _job_text(job)
    if not text:
        return {"ok": False, "error": "I couldn't read that job page (it may need a login). Copy the job text and paste it here instead."}
    try:
        _, info, resume = await _resume_pick(name)
    except ProfileError as e:
        return {"ok": False, "error": str(e)}
    if not resume:
        return {"ok": False, "error": "I can't read this resume. Use a PDF saved from Word or Google Docs."}
    m = keyword_match(resume, text)
    return {"ok": True, **m, "job": text[:6000], "learn": job_skills(m["missing"]), "roles": skill_gaps(resume, job_roles(text))}


async def api_resume_tailor(job, name=""):
    """Rewrite suggestions from Claude for one job (needs the Claude key in Settings)."""
    from .ai import ai_tailor
    db = Answers()
    if not db.ai_on:
        return {"ok": False, "error": "Add your Claude key in Settings, AI helper, or choose another AI, to get rewrite suggestions."}
    text = await _job_text(job)
    if not text:
        return {"ok": False, "error": "I couldn't read that job page. Copy the job text and paste it here instead."}
    _, info, resume = await _resume_pick(name)
    try:
        return {"ok": True, "text": await ai_tailor(db, resume, text)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_prep(company, title, kind):
    """Interview prep tips for the job drawer. Needs the Claude key from Settings."""
    db = Answers()
    if not db.ai_on:
        return {"ok": False, "error": "Add your Claude key in Settings, AI helper, or choose another AI, to get prep tips."}
    try:
        return {"ok": True, "text": await ai_prep(db, company, title, kind)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_company_brief(company, refresh=False):
    """What the company does, a marketing angle and questions to ask (Home, Next up). Free: no key needed."""
    try:
        return {"ok": True, **await company_brief(company, bool(refresh))}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_ai_draft(question):
    try:
        return {"ok": True, "text": await ai_answer(Answers(), question)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_found():
    """Found jobs she hasn't applied to or dismissed (newest first), for the Find jobs page."""
    sent = [r for r in tracker_rows() if (r.get("Status") or "").startswith("Submitted")]
    applied = {norm_link(r.get("Link")) for r in tracker_rows()}
    same_job = {(norm(r.get("Company")), norm(r.get("Job title"))): r.get("Date", "") for r in sent}   # for the "already applied" warning
    out, seen = [], set()
    wanted = split_list((load_profile().get("settings") or {}).get("job_locations"))
    last = set(app_state().get("last_found", []))               # found by the newest search
    try:
        from .resume import resume_profile, resume_text
        rp = resume_profile(resume_text(Answers()))
    except Exception:
        rp = {"skills": [], "years": None}
    aprof = {"skills": rp.get("skills", []), "years": rp.get("years"), "roles": [norm(r) for r in split_list(app_state().get("find_roles", ""))] or ["marketing"]}
    for j in reversed(data()["found_jobs"]):
        k = norm_link(j.get("Link"))
        if k in applied or k in seen or j.get("Dismissed") or not location_ok(j.get("Location"), wanted):
            continue                                   # also hides jobs saved before the location filter existed
        seen.add(k)
        is_alert = bool(j.get("Alert site")) or str(j.get("Company") or "").endswith(" alert")
        ascore = title_score(j.get("Job title") or "", aprof, aprof.get("years")) if is_alert else None
        out.append({"score": ascore if is_alert else j.get("Match %"), "off": is_alert and match_score(j.get("Job title") or "", "", aprof) < 55, "title": j.get("Job title"), "company": j.get("Company"),   # off: below 55 = no role of hers in the title
                    "location": j.get("Location"), "age": j.get("Posted (days ago)") if j.get("Posted (days ago)") != "" else None,
                    "link": j.get("Link"), "date": j.get("Date found"), "last": k in last, "alert": bool(j.get("Alert site")) or str(j.get("Company") or "").endswith(" alert"),
                    "site": j.get("Alert site") or (str(j.get("Company") or "")[:-6] if str(j.get("Company") or "").endswith(" alert") else ""),
                    "dup": same_job.get((norm(j.get("Company")), norm(j.get("Job title")))) if len(norm(j.get("Job title"))) >= 6 else None})
    real = [x for x in out if not x["alert"]][:150]           # alert-email links must not push real finds off the list
    keep = {id(x) for x in real} | {id(x) for x in out if x["alert"]}
    return [x for x in out if id(x) in keep][:300]


async def api_site_limits():
    """LinkedIn / Indeed / Naukri: applications left today (or resting after a robot check), for the Apply page."""
    from .jobsites import SITES, cooling_off, daily_limit, done_today
    cap = daily_limit()
    return [{"site": s, "done": done_today(s), "cap": cap, "resting": cooling_off(s)} for s in SITES.values()]


async def api_dismiss_found(link):
    for j in data()["found_jobs"]:
        if norm_link(j.get("Link")) == norm_link(link):
            j["Dismissed"] = True
    save_data()
    return True


async def api_answer(qid, value):
    UI.answer(qid, value)
    return True


async def api_stop():
    UI.stop = True
    UI.cancel_all()
    return True


async def api_tables():
    return {"applications": table_of(data()["applications"]), "accounts": table_of(data()["accounts"]),
            "found": table_of(data()["found_jobs"])}


async def api_add_file(name, b64):
    import base64
    name = re.sub(r'[\\/:*?"<>|]+', "_", Path(name).name).strip() or "file.pdf"
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    (FILES_DIR / name).write_bytes(base64.b64decode(b64))
    log(f"📎 Added {name} to your files.")
    return {"ok": True, "name": name, "files": folder_files()}


async def api_files():
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(FILES_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix.lower() in (".pdf", ".doc", ".docx") and not p.name.startswith("."):
            st = p.stat()
            out.append({"name": p.name, "size": st.st_size,
                        "date": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d %b %Y")})
    return out


async def api_delete_file(name):
    src = FILES_DIR / Path(name).name
    if not src.is_file():
        return False
    dest = BACKUP_DIR / "removed-files"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest / f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{src.name}"))
    log(f"🗑  Removed {src.name} (a copy is kept in Backups/removed-files).")
    return True


async def api_set_theme(theme):
    save_app_state(theme=theme if theme in THEMES else "clean")
    return True


async def api_set_font(font):
    save_app_state(font=font if font in FONTS else "classic")
    return True


async def api_set_alert_show(choice):
    """Which alert-email jobs Find jobs lists: "" (all), "none", or one site name such as LinkedIn."""
    save_app_state(alert_show=str(choice or "")[:30])
    return True


async def api_set_calm(calm):
    save_app_state(calm=bool(calm))
    return True


async def api_seen_version():
    save_app_state(last_seen_version=APP_VERSION)
    return True


async def api_open_url(url):
    """Opens a web link in her normal browser, not inside the app window."""
    import webbrowser
    if not re.match(r"https?://", str(url or ""), re.I):
        return False
    return bool(webbrowser.open(str(url)))


async def api_open(name):
    rows = {"applications": "applications", "accounts": "accounts", "found": "found_jobs"}
    if name in rows:
        if not data()[rows[name]]:
            return False
        os_open(export_csv(name, data()[rows[name]]))
        return True
    allowed = {"folder": FILES_DIR, "data": DATA, "summaries": DRAFT_DIR, "logs": LOG_DIR, "backups": BACKUP_DIR,
               "reports": REPORT_DIR}
    target = allowed.get(name)
    if target is None:
        return False
    target.mkdir(parents=True, exist_ok=True)
    os_open(target)
    return True
