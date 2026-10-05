"""filler: fills one page of an application. plan_field() decides, ask_batch() asks all unknowns at once,
fill_field() types/clicks. See MAP.md."""
import re
from pathlib import Path
from .ai import ai_cover_letter_flow
from .bridge import UI, log
from .config import NEXT_AUTOMATION_IDS, NEXT_WORDS, SKIP, CLICKABLE
from .page_js import BUTTONS_JS, COLLECT_JS, TITLE_JS
from .records import answer_mentions_other_company
from .resume import resume_for_job
from .workday import fill_history
from .state import CURRENT_JOB
from .store import folder_files, resolve_path
from .textutil import adapt_value, clean_label, norm, pick, pretty_label, to_iso_date, truthy


async def click_check(loc):
    try:
        await loc.check(force=True, timeout=3000)
    except Exception:
        await loc.evaluate("e => ((e.labels && e.labels[0]) || e).click()")


async def popup_options(page, fr, opener=None):
    """Options of a Workday-style dropdown or autocomplete list ([role=option]). Opens it first if given."""
    if opener is not None:
        await opener.click()
        await page.wait_for_timeout(700)
    opts = fr.locator('[role="option"]:visible')
    return opts, [t.strip() for t in await opts.all_inner_texts()]


async def plan_field(f, db, page):
    """Decide what to do with one field, without asking. Returns a dict with action fill / ask / have / skip / manual."""
    kind = f["kind"]
    if f.get("captcha"):
        return {"action": "manual", "why": "captcha"}
    if f["value"] and kind != "select":
        return {"action": "have"} if kind != "checkbox" else {"action": "skip"}
    ans, src = db.lookup(f)
    if f["value"]:                                   # a select already showing a value (often the site's default, e.g. Male)
        c = pick(ans, f["options"]) if ans not in (None, SKIP, "") else None
        if not c or norm(c) == norm(f["value"]):
            return {"action": "have"}
        return {"action": "fill", "value": c, "src": src, "options": f["options"]}
    if ans in (SKIP, ""):
        return {"action": "skip"}
    q = {"label": pretty_label(f["label"]) or "(this field has no label)", "required": bool(f.get("required")),
         "kind": "text", "options": [], "note": "", "value": ""}
    options = None
    if kind == "select":
        options = f["options"]
    elif kind == "radio":
        options = [o["label"] for o in f["options"]]
    elif kind == "checkbox":
        options = ["Yes", "No"]
    elif kind == "dropdown":
        try:
            _, texts = await popup_options(page, f["frame"], f["frame"].locator(f'[data-afid="{f["id"]}"]'))
            await page.keyboard.press("Escape")
            options = [t for t in texts if t]
        except Exception:
            options = []
    if options is not None:
        if ans is not None and kind != "checkbox":
            c = pick(ans, options)
            if c:
                return {"action": "fill", "value": c, "options": options,
                        "src": src if norm(c) == norm(ans) else f"best guess from “{ans}”"}
            q["note"] = f"Your saved answer “{ans}” isn't one of the options."
        elif ans is not None:
            return {"action": "fill", "value": ans, "src": src, "options": options}
        if f.get("weak") and not f.get("required"):
            return {"action": "skip"}
        q.update(kind="choice", options=options)
        return {"action": "ask", "q": q}
    if kind == "file":
        path, is_cover = ans, "cover" in norm(f["label"])
        if src == "profile" and not is_cover:
            path = resume_for_job(db) or path
        if is_cover and db.ai_on and truthy(db.settings.get("ai_cover_letters") or ""):
            made = await ai_cover_letter_flow(db)
            if made:
                return {"action": "fill", "value": made, "src": "AI cover letter"}
        if path and resolve_path(path).is_file():
            return {"action": "fill", "value": path, "src": src}
        if (src == "profile" or f.get("weak")) and not f.get("required"):
            return {"action": "skip"}
        q.update(kind="file", options=folder_files(), note=f"Couldn't find {Path(str(path)).name}." if path else "")
        return {"action": "ask", "q": q}
    # text, textarea, date, autocomplete
    if ans is not None and src.startswith("memory") and len(ans) >= 40 and (
            src == "memory~" or answer_mentions_other_company(ans, CURRENT_JOB["company"])):
        q.update(value=ans, note="You wrote this for a similar question before, maybe for another company. Check it fits.")
        q["kind"] = "textarea"
        return {"action": "ask", "q": q}
    if ans is None:
        if f.get("weak") and not f.get("required"):
            return {"action": "skip"}                      # only an example placeholder, not a real question
        if f.get("itype") == "date":
            q.update(kind="date", note="A date, e.g. 15/11/2026 or Immediately.")
        elif kind == "textarea":
            q["kind"] = "textarea"
        return {"action": "ask", "q": q}
    return {"action": "fill", "value": adapt_value(f, ans), "src": src}


async def ask_batch(db, asks):
    """One card with every unknown question on the page. Saves the answers. Returns {index: value}."""
    qs = []
    for i, (f, p) in enumerate(asks):
        qs.append({**p["q"], "qid": i, "ai": db.ai_on and p["q"]["kind"] in ("text", "textarea")})
    n = len(qs)
    res = await UI.ask(title=f"{n} new question{'s' if n > 1 else ''} on this page",
                       message="Answer what you can; anything left empty is skipped. Your answers are remembered.",
                       questions=qs, choices=[("Fill these in", "__form__", "primary"), ("Skip all", "__skip__", "ghost")],
                       kind="form")
    out = {}
    if not isinstance(res, dict):
        return out
    for i, (f, p) in enumerate(asks):
        r = res.get(str(i)) or {}
        v, never = str(r.get("value") or "").strip(), bool(r.get("never"))
        if never:
            db.remember(f["label"], SKIP, f.get("nm", ""))
        elif v:
            if p["q"]["kind"] != "file" or "cover" not in norm(f["label"]):
                db.remember(f["label"], v, f.get("nm", ""))
            out[i] = v
    return out


def review_questions(plans):
    """Questions for the check-before-filling card: every answer the app is about to type, except those she just typed."""
    items = []
    for f, p in plans:
        if p["action"] != "fill" or p.get("src") == "you":
            continue
        v, opts = str(p["value"]), p.get("options")
        q = {"label": pretty_label(f["label"]) or "(this field has no label)", "required": bool(f.get("required")),
             "options": [], "value": v, "note": "From " + str(p.get("src") or "your profile"), "review": True}
        if f["kind"] == "file":
            q.update(kind="fixed", value=Path(v).name)
        elif opts:
            q.update(kind="choice", options=list(opts))
        else:
            q["kind"] = "textarea" if f["kind"] == "textarea" or len(v) > 80 else "text"
        items.append((f, p, q))
    return items


async def review_before_fill(db, plans):
    """Shows the planned answers on one card; she can change any, or leave one empty. Changes are remembered."""
    items = review_questions(plans)
    if not items:
        return
    qs = [{**q, "qid": i} for i, (_, _, q) in enumerate(items)]
    n = len(qs)
    res = await UI.ask(title=f"Check {n} answer{'s' if n > 1 else ''} before I fill them in",
                       message="This is what I'm about to type on this page. Change anything that's wrong, or tick “Leave empty” "
                               "to skip one. Changes are remembered.",
                       questions=qs, choices=[("Looks good, fill these in", "__form__", "primary"),
                                              ("Don't fill, I'll do it", "__skip__", "ghost")], kind="form")
    for i, (f, p, q) in enumerate(items):
        if not isinstance(res, dict):
            p["action"] = "skip"
            continue
        r = res.get(str(i)) or {}
        v = str(r.get("value") or "").strip()
        if r.get("never") or (not v and q["kind"] != "fixed"):
            p["action"] = "skip"
        elif q["kind"] != "fixed" and v != q["value"]:
            db.remember(f["label"], v, f.get("nm", ""))
            p["value"], p["src"] = (v if q["kind"] == "choice" else adapt_value(f, v)), "you"


async def fill_field(f, value, src, page, db):
    """Types / clicks / uploads one answer. Returns (label, shown value, source) or None."""
    fr, kind = f["frame"], f["kind"]
    loc = fr.locator(f'[data-afid="{f["id"]}"]')
    ans = value
    try:
        if kind in ("text", "textarea"):
            if f.get("picker"):                                          # read-only calendar boxes: set by script
                iso = to_iso_date(ans)
                if not iso:
                    log(f"   ⚠ '{ans}' isn't a date I understand for '{f['label'][:40]}'")
                    return None
                await loc.evaluate("""(e, iso) => { const [y, m, d] = iso.split('-').map(Number), dt = new Date(y, m - 1, d);
                    const jq = window.jQuery;
                    if (jq && jq.fn.datepicker && jq(e).hasClass('hasDatepicker')) jq(e).datepicker('setDate', dt);
                    else { const p = n => String(n).padStart(2, '0'); e.value = `${p(d)}/${p(m)}/${y}`; }
                    e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); }""", iso)
            elif f.get("itype") == "date":
                iso = to_iso_date(ans)
                if not iso:
                    log(f"   ⚠ '{ans}' isn't a date I understand for '{f['label'][:40]}'")
                    return None
                await loc.fill(iso)
            elif (f.get("auto") or "").startswith("dateSection"):        # Workday month / day / year boxes
                await loc.click()
                await loc.press_sequentially(str(ans), delay=60)
            else:
                await loc.fill(str(ans))
            await loc.evaluate("e => e.blur()")
        elif kind == "select":
            await loc.select_option(label=ans)
        elif kind == "radio":
            labels = [o["label"] for o in f["options"]]
            if ans not in labels:
                ans = pick(ans, labels)
                if not ans:
                    return None
            await click_check(fr.locator(f'[data-afid="{f["options"][labels.index(ans)]["id"]}"]'))
        elif kind == "checkbox":
            if not truthy(ans):
                return None
            await click_check(loc)
            ans = "✔ checked"
        elif kind == "file":
            path = resolve_path(ans)
            if not path.is_file():
                log(f"   ⚠ File not found: {ans}")
                return None
            await loc.set_input_files(str(path))
            ans = path.name
        elif kind == "dropdown":
            opts, texts = await popup_options(page, fr, loc)
            choice = pick(ans, [t for t in texts if t])
            if not choice:
                await page.keyboard.press("Escape")
                return None
            await opts.nth(texts.index(choice)).click()
            ans = choice
        elif kind == "combo":
            await loc.click()
            await loc.fill(str(ans))
            if f.get("auto") == "searchBox":           # Workday multi-select search
                await loc.press("Enter")
            await page.wait_for_timeout(1200)
            opts, texts = await popup_options(page, fr)
            choice = pick(ans, [t for t in texts if t])
            if choice:
                await opts.nth(texts.index(choice)).click()
                ans = choice
    except Exception as e:
        log(f"   ⚠ Could not fill '{f['label'][:60]}': {str(e).splitlines()[0]}")
        return None
    return (pretty_label(f["label"]), ans, src or "you")


async def scan(page):
    fields = []
    for fr in page.frames:                               # covers Greenhouse/Lever iframes
        try:
            items = await fr.evaluate(COLLECT_JS)
        except Exception:
            continue
        for it in items:
            it["frame"] = fr
            fields.append(it)
    return fields


async def fill_page(page, db):
    """Fills the visible page. Unknown questions are asked together on one card. Returns [(label, value, source)]."""
    records, done, manual = {}, set(), []
    for r in await fill_history(page, db):            # Workday "My Experience": jobs and degrees from Profile
        records[r[0]] = r
    for _ in range(3):                # extra passes catch follow-up questions that appear after answers
        fields = [f for f in await scan(page) if (id(f["frame"]), f["id"]) not in done]
        if not fields:
            break
        plans, asks = [], []
        for f in fields:
            done.add((id(f["frame"]), f["id"]))
            p = await plan_field(f, db, page)
            plans.append((f, p))
            if p["action"] == "ask":
                asks.append((f, p))
            elif p["action"] == "manual":
                manual.append(pretty_label(f["label"]))
        if asks:
            answers = await ask_batch(db, asks)
            for i, (f, p) in enumerate(asks):
                if i in answers:
                    p.update(action="fill", value=adapt_value(f, answers[i]) if p["q"]["kind"] != "file" else answers[i],
                             src="you")
        if truthy(db.settings.get("review_before_fill", "Yes")):
            await review_before_fill(db, plans)
        new = False
        for f, p in plans:
            if p["action"] == "have":
                records[pretty_label(f["label"])] = (pretty_label(f["label"]), f["value"], "already filled")
            elif p["action"] == "fill":
                r = await fill_field(f, p["value"], p["src"], page, db)
                if r:
                    records[r[0]] = r
                    new = True
        if not new:
            break
        await page.wait_for_timeout(800)
    filled = [[r[0], str(r[1])] for r in records.values() if r[2] != "already filled"]
    if filled:
        UI._send({"type": "filled", "items": filled})
    if manual:
        log("   ✋ Type these yourself in Chrome: " + ", ".join(dict.fromkeys(manual)))
        UI._send({"type": "manual", "items": list(dict.fromkeys(manual))})
    return list(records.values())


async def find_buttons(page):
    nxt = sub = None
    for fr in page.frames:
        try:
            btns = await fr.evaluate(BUTTONS_JS)
        except Exception:
            continue
        for b in btns:
            t = norm(b["text"])
            loc = fr.locator(f'[data-afbtn="{b["id"]}"]')
            if t.startswith("submit") or t in ("apply", "apply now", "apply for this job", "send application", "finish", "complete application"):
                sub = sub or loc
            elif b["auto"] in NEXT_AUTOMATION_IDS or any(t == w or t.startswith(w + " ") for w in NEXT_WORDS):
                nxt = nxt or loc
    return nxt, sub


async def settle(page):
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    await page.wait_for_timeout(1500)


async def page_info(page):
    try:
        return await page.evaluate(TITLE_JS)
    except Exception:
        return {"title": "", "count": 0}


async def fingerprint(page):
    i = await page_info(page)
    return f"{page.url}|{i['title']}|{i['count']}"


async def empty_required(page):
    out = []
    for f in await scan(page):
        if f.get("required") and not f["value"]:
            l = clean_label(f["label"])
            if l and l not in out:
                out.append(l)
    return out


async def empty_captcha(page):
    """True when a captcha box on the page is still empty (she has to type it herself)."""
    return any(f.get("captcha") and not f["value"] for f in await scan(page))


SUCCESS_RE = re.compile(r"thank you for (applying|your application|your interest)|application (has been |was )?"
                        r"(received|submitted|sent)|successfully (applied|submitted)|we('ve| have) received your "
                        r"application|you('ve| have) applied|application complete", re.I)


async def page_text(page):
    out = ""
    for fr in page.frames:
        try:
            out += " " + await fr.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            pass
    return out.lower()


async def find_clickable(page, words, ids=(), exclude=r"\bwith\b|google|linkedin|apple|facebook|forgot|indeed|reset"):
    best = None
    for fr in page.frames:
        try:
            items = await fr.evaluate(BUTTONS_JS, CLICKABLE)
        except Exception:
            continue
        for b in items:
            loc = fr.locator(f'[data-afbtn="{b["id"]}"]')
            rank = None
            if b["auto"] in ids:
                rank = ids.index(b["auto"]) - len(ids)
            else:
                t = norm(b["text"])
                if b.get("filt") or not t or len(t) > 40 or re.search(exclude, t):
                    continue
                for i, w in enumerate(words):
                    if t == w or t.startswith(w + " "):
                        rank = i
                        break
            if rank is not None and (best is None or rank < best[0]):
                best = (rank, loc, b["text"])
    return (best[1], best[2]) if best else (None, None)


async def safe_click(loc):
    try:
        await loc.click(timeout=5000)
    except Exception:
        await loc.click(force=True, timeout=5000)        # Workday puts an invisible layer over buttons


async def looks_like_form(page):
    fields = [f for f in await scan(page) if f["kind"] != "checkbox"]
    return len(fields) >= 3
