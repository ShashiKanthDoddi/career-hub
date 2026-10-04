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
from .finder import run_find
from .gmail import check_mail, mail_settings
from . import history, planner
from .overview import jobs_overview
from .profile_form import profile_values
from .records import add_to_jobs_file, read_jobs_file
from .reports import send_report
from .resume import resume_info
from .state import TASKS
from .store import ProfileError, app_state, data, export_csv, folder_files, save_app_state, save_data, table_of
from .textutil import norm, norm_link
from .updater import check_for_update, install_latest, install_zip
from .ai import ai_answer
from .state import APP
from .config import UPDATE_SOURCE
from .records import tracker_rows



def start_task(coro):
    t = asyncio.get_running_loop().create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)


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
            "theme": st.get("theme", "clean"), "changelog": CHANGELOG,
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
        return {"ok": False, "error": "Couldn't read your resume. Drop it into Profile → Files, "
                                      "pick it as Resume, and Save profile."}
    return {"ok": True, **prof}


async def api_start_find(roles_text, companies_text, auto):
    if UI.busy:
        return {"ok": False, "error": "Already working. Wait for it to finish or press Stop."}
    roles = [norm(x) for x in (roles_text or "").split(",") if x.strip()]
    tokens = [t.strip() for t in (companies_text or "").split(",") if t.strip()]
    if auto:
        tokens.append("auto")
    if not tokens:
        return {"ok": False, "error": "Add a company name, or switch on “Search the web for companies hiring”."}
    if not roles:
        try:
            has_resume = resume_info(Answers()) is not None
        except ProfileError:
            has_resume = False
        if not has_resume:
            return {"ok": False, "error": "I need a job title to look for. Add one above, or add your resume in Profile → Files."}
    start_task(run_find(roles, tokens))
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


async def api_home():
    jobs, updates = jobs_overview()
    now = datetime.datetime.now()
    week_ago = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    applied = [j for j in jobs if j["status"].startswith("Submitted")]
    stages = {}
    for j in applied:
        stages[j["stage"]] = stages.get(j["stage"], 0) + 1
    replied = sum(1 for j in applied if j["stage"] in ("Interview", "Assessment", "Offer", "Rejected"))
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
    return {"weekly": weekly, "stages": stages, "stats": {"applied": len(applied), "week": sum(1 for j in applied if j["date"][:10] >= week_ago),
                      "interviews": stages.get("Interview", 0) + stages.get("Assessment", 0),
                      "offers": stages.get("Offer", 0), "rejected": stages.get("Rejected", 0),
                      "waiting": stages.get("Applied", 0),
                      "reply_rate": round(100 * replied / len(applied)) if applied else 0,
                      "drafts": sum(1 for j in jobs if j["stage"] == "Draft")},
            "attention": [u for u in updates if not u.get("done")][:10],
            "feed": updates[:15], "mail_ready": bool(ms["addr"] and ms["pw"]), "mail_due": due,
            "mail_error": st.get("last_mail_error", ""),
            "last_mail_check": st.get("last_mail_check", ""), "list_count": len(read_jobs_file()),
            "events": planner.list_events(), "todos": data()["todos"], "cheer": cheer_due()}


async def api_add_event(title, date, time="", company="", note=""):
    return planner.add_event(title, date, time, company, note)


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
        return {"ok": False, "error": "I couldn't find work or education sections in the resume. You can type them in below."}
    return {"ok": True, **h}


async def api_jobs():
    jobs, updates = jobs_overview()
    return {"jobs": jobs, "updates": updates}


async def api_set_note(key, stage, notes):
    auto = next((j["auto_stage"] for j in jobs_overview()[0] if j["key"] == key), "")
    data()["notes"][key] = {"stage": stage or "", "notes": notes or "", "auto": auto}   # her choice holds until a newer email changes the auto stage
    if stage in ("Applied", "Draft"):                  # moved back before any interview: its calendar entry goes too
        planner.drop_job_event(key)
    save_data()
    return True


async def api_dismiss(uid):
    for u in data()["email_updates"]:
        if u["id"] == uid:
            u["done"] = True
    save_data()
    return True


async def api_check_mail(manual=False):
    r = await check_mail(manual=manual)
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


async def api_report(note):
    try:
        return await send_report(note)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_check_update(manual=False):
    r = await check_for_update()
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


async def api_ai_draft(question):
    try:
        return {"ok": True, "text": await ai_answer(Answers(), question)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def api_found():
    """Found jobs she hasn't applied to or dismissed (newest first), for the Find jobs page."""
    applied = {norm_link(r.get("Link")) for r in tracker_rows()}
    out, seen = [], set()
    for j in reversed(data()["found_jobs"]):
        k = norm_link(j.get("Link"))
        if k in applied or k in seen or j.get("Dismissed"):
            continue
        seen.add(k)
        out.append({"score": j.get("Match %"), "title": j.get("Job title"), "company": j.get("Company"),
                    "location": j.get("Location"), "age": j.get("Posted (days ago)") if j.get("Posted (days ago)") != "" else None,
                    "link": j.get("Link"), "date": j.get("Date found")})
    return out[:150]


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


async def api_seen_version():
    save_app_state(last_seen_version=APP_VERSION)
    return True


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
