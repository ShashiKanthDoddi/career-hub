"""apply_run module of Career Hub. See MAP.md for what lives where."""
import datetime
import html
import json
from .answers import Answers
from .auth import auth_state, get_to_form, handle_auth
from .jobsites import allowed, challenged, pace, site_of, start_cooling_off
from .launch import launch_chrome
from .bridge import StopRun, UI, check_stop, log
from .config import BROWSER_DIR, DRAFT_DIR
from .filler import SUCCESS_RE, empty_captcha, empty_required, fill_page, find_buttons, fingerprint, page_info, page_text, safe_click, settle
from .page_js import ERRORS_JS, JOB_BADGE_JS
from .records import already_applied, already_applied_same_job, guess_company, tracker_add
from .reports import send_report
from .state import CURRENT_JOB, JOB, PW, RESUME_CACHE
from .store import ProfileError, data, save_data
from .textutil import slug


def save_draft(draft, company, title):
    DRAFT_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    name = f"{stamp}_{slug(company)}"
    (DRAFT_DIR / f"{name}.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")

    sections = []
    for p in draft:
        rows = ""
        for r in p["fields"]:
            rows += (f"<tr><td>{html.escape(r['label'])}</td><td><b>{html.escape(str(r['value']))}</b></td>"
                     f"<td class=s>{html.escape(r['source'])}</td></tr>")
        sections.append(f"<h2>{html.escape(p['page'])}</h2>"
                        f"<table>{rows or '<tr><td>(nothing filled on this page)</td></tr>'}</table>")

    doc = f"""<!doctype html><meta charset=utf-8><title>Summary – {html.escape(company)}</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;max-width:900px;margin:30px auto;padding:0 16px;color:#1f2937}}
table{{border-collapse:collapse;width:100%;margin-bottom:20px}}td{{border-bottom:1px solid #e5e7eb;padding:7px;vertical-align:top}}
td:first-child{{width:45%;color:#4b5563}}.s{{color:#9ca3af;font-size:12px;width:100px}}h2{{margin-top:28px;font-size:18px}}
.note{{background:#fffbeb;border-left:4px solid #d97706;padding:10px 14px}}</style>
<h1>{html.escape(company)}</h1><p>{html.escape(title)}</p>
<p class=note>Check every answer below <b>and</b> glance over the pages in the other tab. Fields the tool didn't
recognise aren't listed here, so look for empty boxes before you submit.</p>{''.join(sections)}"""
    out = DRAFT_DIR / f"{name}.html"
    out.write_text(doc, encoding="utf-8")
    log(f"\n💾 Summary saved in the 'summaries' folder: {out.name}")
    return out


async def open_browser(p):
    return await launch_chrome(p, BROWSER_DIR, args=["--start-maximized"])


def table_rows(records):
    out = []
    for label, value, src in records:
        v = str(value)
        if "best guess" in str(src):
            v += f"   ⚠ {src}"
        out.append([label, v])
    return out


async def apply_one(ctx, link, db, n, total):
    for extra in ctx.pages[1:]:
        await extra.close()
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.bring_to_front()

    UI.status(job=n, total=total, company="", title="", detail="Opening the job…", link=link)
    log(f"\n━━━━━━━━  Job {n} of {total}  ━━━━━━━━\n{link}")
    try:
        await page.goto(link, timeout=60000)
    except Exception:
        log("⚠  The page was slow to load; carrying on.")
    try:
        page_title = (await page.title()).strip()
    except Exception:
        page_title = ""
    site = site_of(link)
    if site and await challenged(page):
        v = await UI.ask(title=f"{site} wants to check you're human",
                         message="Solve the check in the Chrome window yourself. If it keeps coming back, stop for today: "
                                 "pushing on can get the account restricted.",
                         choices=[("I solved it – continue", "go", "primary"), ("Stop for today", "stop", "danger")],
                         kind="help")
        if v == "stop" or await challenged(page):
            start_cooling_off(site)
            return "QUIT"
    company = guess_company(link, page_title)
    title = page_title.split("|")[0].strip()[:100] or "Job"
    CURRENT_JOB.update(company=company, title=title, desc=(await page_text(page))[:8000])
    UI.status(job=n, total=total, company=company, title=title, detail="Clicking Apply / signing in…", link=link)
    when = already_applied_same_job(company, title, link)
    if when:
        v = await UI.ask(title="Looks like you already applied", message=f"You submitted “{title}” at {company} on "
                         f"{when} (through a different link).", choices=[("Skip it", "skip", "primary"),
                                                                          ("Apply anyway", "go", "ghost")])
        if v != "go":
            return "Skipped (already applied)", company, title, ""

    if not await get_to_form(ctx, db, company):
        v = await UI.ask(title="I need your help in Chrome",
                         message="I couldn't reach the application form on my own.\n\nIn the Chrome window: log in or "
                                 "sign up (solve any \"I'm not a robot\" check) and click Apply until you see the "
                                 "first form with boxes to fill.",
                         choices=[("I'm on the form – continue", "go", "primary"), ("Skip this job", "skip", "ghost"),
                                  ("Stop everything", "quit", "danger")], kind="help")
        if v == "quit":
            return "QUIT"
        if v == "skip":
            return "Skipped", company, title, ""

    page = ctx.pages[-1]                          # Apply often opens a new tab
    await page.bring_to_front()
    draft, stuck = [], 0
    for step in range(1, 51):
        check_stop()
        await settle(page)
        page = ctx.pages[-1]
        _, npw = await auth_state(page)
        if npw:
            if not await handle_auth(ctx, db, company):
                await UI.ask(title="Please sign in", message="Finish signing in / signing up in the Chrome window.",
                             choices=[("Done – continue", "ok", "primary")], kind="help")
            page = ctx.pages[-1]
            await settle(page)
        pt = (await page_info(page))["title"] or f"Page {step}"
        UI.status(job=n, total=total, company=company, title=title, detail=f"Filling page {step}: {pt}", link=link)
        log(f"\n— Page {step}: {pt}")
        records = await fill_page(page, db)
        for r in records:
            log(f"   ✓ {r[0][:60]} → {r[1]}   ({r[2]})")
        draft.append({"page": pt, "url": page.url,
                      "fields": [{"label": a, "value": b, "source": c} for a, b, c in records]})

        nxt, sub = await find_buttons(page)
        if sub and not nxt:
            log("🛑 Reached the final Submit page.")
            break
        if db.pause or not nxt:
            if nxt:
                missing = await empty_required(page)
                warn = ("\n\n⚠ Still empty but required: " + ", ".join(missing[:8])) if missing else ""
                v = await UI.ask(title=f"Page {step} filled", message=f"“{pt}”\n\nCheck the page in Chrome. Anything "
                                 "you change there yourself is kept." + warn, table=table_rows(records),
                                 choices=[("Next page", "next", "primary"), ("Fill this page again", "again", "ghost"),
                                          ("Stop here & show summary", "done", "ghost")], kind="page")
            else:
                v = await UI.ask(title="No Next button found",
                                 message="Go to the next page in Chrome yourself, then come back here.",
                                 choices=[("I'm on the next page – fill it", "again", "primary"),
                                          ("Stop here & show summary", "done", "ghost")], kind="help")
            if v == "done":
                break
            if v == "again" or not nxt:
                draft.pop()
                continue

        before = await fingerprint(page)
        await safe_click(nxt)
        await settle(page)
        if await fingerprint(page) == before:
            errs = []
            for fr in page.frames:
                try:
                    errs += await fr.evaluate(ERRORS_JS)
                except Exception:
                    pass
            log("⚠  The page didn't move forward." + (" The website says: " + " | ".join(errs[:5]) if errs else ""))
            draft.pop()
            stuck += 1
            if stuck >= 2:
                await UI.ask(title="The page won't move forward",
                             message="The website wants something fixed first:\n\n• " + "\n• ".join(errs[:8] or
                                     ["(no message shown — look for red text or empty required boxes)"]) +
                                     "\n\nFix it in Chrome, then continue.",
                             choices=[("I fixed it – continue", "ok", "primary")], kind="help")
                stuck = 0
            continue
        stuck = 0

    summary = save_draft(draft, company, title)
    tab = await ctx.new_page()
    await tab.goto(summary.as_uri())
    await page.bring_to_front()
    rows = table_rows([(r["label"], r["value"], r["source"]) for p_ in draft for r in p_["fields"]])
    missing = await empty_required(page)
    if await empty_captcha(page):
        missing = ["Captcha (type it yourself in Chrome)"] + missing
    warn = ("\n\n⚠ These required boxes on this page are still empty: " + ", ".join(missing[:8])) if missing else ""
    UI.status(job=n, total=total, company=company, title=title, detail="Waiting for your decision", link=link)
    while True:
        v = await UI.ask(title="Ready to submit?",
                         message=f"{company} — {title}\n\nEverything the tool filled is listed below (and in a summary "
                                 "tab in Chrome). Glance over the form for any empty boxes before submitting." + warn,
                         table=rows,
                         choices=[("Submit it for me", "submit", "primary"), ("I submitted it myself", "mine", "ghost"),
                                  ("Don't submit (keep as draft)", "draft", "ghost")], kind="submit")
        if v == "submit":
            if await empty_captcha(page):                  # the site rejects an empty captcha, so she types it first
                await page.bring_to_front()
                await UI.ask(title="Type the captcha first",
                             message="This page has a captcha (the squiggly letters). Type it in Chrome, then come back here.",
                             choices=[("I typed it – submit now", "ok", "primary")], kind="help")
            _, sub = await find_buttons(page)
            if not sub:
                await UI.ask(title="Submit button not found", message="Please click Submit yourself in Chrome.",
                             choices=[("OK", "ok", "primary")], kind="help")
                continue
            await safe_click(sub)
            await settle(page)
            await page.wait_for_timeout(2500)
            texts = ""
            for pg in ctx.pages:
                if pg.url != summary.as_uri():
                    texts += " " + await page_text(pg)
            if SUCCESS_RE.search(texts):
                log("✅ Submitted, and the site confirmed it.")
                return "Submitted", company, title, summary
            errs = []
            for fr in page.frames:
                try:
                    errs += await fr.evaluate(ERRORS_JS)
                except Exception:
                    pass
            c = await UI.ask(title="Did it go through?",
                             message="I clicked Submit but didn't see a \"thank you\" message." +
                                     ("\n\nThe site shows: " + " | ".join(errs[:5]) if errs else "") +
                                     "\n\nLook at Chrome: was the application sent?",
                             choices=[("Yes, it's submitted", "yes", "primary"), ("No – I'll fix it and submit myself",
                                                                                   "fix", "ghost"),
                                      ("No – keep as draft", "no", "ghost")], kind="help")
            if c == "yes":
                return "Submitted", company, title, summary
            if c == "fix":
                await UI.ask(title="Over to you", message="Fix it in Chrome and click Submit there.",
                             choices=[("I submitted it", "ok", "primary")], kind="help")
                return "Submitted (by you)", company, title, summary
            return "Not submitted (draft)", company, title, summary
        if v == "mine":
            return "Submitted (by you)", company, title, summary
        return "Not submitted (draft)", company, title, summary


async def job_browser():
    ctx = JOB["ctx"]
    if ctx is not None:
        try:
            _ = ctx.pages
            if ctx.browser is None or ctx.browser.is_connected():
                return ctx
        except Exception:
            pass
    ctx = await open_browser(PW["p"])
    ctx.on("close", lambda *_: JOB.update(ctx=None))
    try:
        await ctx.add_init_script(JOB_BADGE_JS)
    except Exception:
        pass
    JOB["ctx"] = ctx
    return ctx


async def run_apply(links):
    UI.busy, UI.stop = True, False
    results, problems = [], []
    await UI.emit({"type": "run_start", "what": "apply", "total": len(links)})
    RESUME_CACHE["text"] = None
    try:
        db = Answers()
        todo = []
        for link in links:
            when = already_applied(link)
            if when:
                v = await UI.ask(title="Already applied", message=f"You applied to this job on {when}:\n{link}",
                                 choices=[("Skip it", "skip", "primary"), ("Apply again", "again", "ghost")])
                if v != "again":
                    continue
            todo.append(link)
        if not todo:
            log("Nothing to apply for.")
            return
        ctx = await job_browser()
        last_site = None
        for i, link in enumerate(todo, 1):
            check_stop()
            site = site_of(link)
            if site:
                ok, why = allowed(site)
                if not ok:
                    log(f"⏸ Skipped (left in your list): {link}\n   {why}")
                    continue
                if last_site == site:
                    await pace(site)
            try:
                res = await apply_one(ctx, link, db, i, len(todo))
            except StopRun:
                raise
            except Exception as e:
                msg = str(e).splitlines()[0][:150]
                log(f"⚠  Something went wrong with this job: {msg}")
                if "closed" in msg.lower():
                    log("   The job Chrome window was closed. Start again when ready.")
                    tracker_add(guess_company(link), "", "Error", link, "")
                    break
                problems.append(f"{link}: {msg}")
                res = ("Error", guess_company(link), "", "")
            if res == "QUIT":
                break
            status, company, title, summary = res
            last_site = site
            tracker_add(company, title, status, link, summary)
            if status.startswith("Submitted") and link in data()["saved_links"]:
                data()["saved_links"].remove(link)          # one list: sent jobs leave it
                save_data()
            results.append({"company": company, "title": title, "status": status})
            log(f"→ {company}: {status}")
    except StopRun:
        log("⏹ Stopped.")
    except ProfileError as e:
        log(f"⚠  {e}")
    except Exception as e:
        log(f"⚠  Unexpected problem: {str(e).splitlines()[0][:200]}")
        problems.append(str(e).splitlines()[0][:300])
    finally:
        UI.busy, UI.stop = False, False
        await UI.emit({"type": "run_end", "what": "apply", "results": results})
    if problems:
        try:
            v = await UI.ask(title="Something went wrong", message="Some jobs ran into a problem:\n\n• " +
                             "\n• ".join(problems[:5]) + "\n\nSend a problem report (activity log + screenshots) "
                             "so it can be fixed?", choices=[("Send a problem report", "send", "primary"),
                                                             ("Not now", "no", "ghost")], kind="help")
            if v == "send":
                r = await send_report("Automatic report after errors:\n" + "\n".join(problems))
                await UI.emit({"type": "report_done", **r})
        except Exception:
            pass
