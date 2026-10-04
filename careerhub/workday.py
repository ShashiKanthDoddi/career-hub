"""workday: fills the "My Experience" page of Workday applications (work history and education) from the
history she saved in Profile. Workday asks for each job and degree in its own block, opened with an Add button.
Selectors use Workday's data-automation-id names with a label fallback. Never raises: a section it can't work
with is left for her to fill in Chrome."""
import re
from .bridge import log
from .history import get_history
from .textutil import pick

SECTIONS = (("work", "workExperienceSection", "workExperience"), ("education", "educationSection", "education"))
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]


async def _entry_ids(section, prefix):
    ids = await section.evaluate("s => [...s.querySelectorAll('[data-automation-id]')].map(e => e.getAttribute('data-automation-id'))")
    found = sorted({i for i in ids if re.fullmatch(rf"{prefix}-\d+", i)}, key=lambda i: int(i.split("-")[1]))
    return found


async def _box(entry, ids, label_re):
    """The input / textarea inside one entry: by automation id first, then by its label."""
    for i in ids:
        loc = entry.locator(f'[data-automation-id="{i}"]').first
        if await loc.count():
            return loc
    loc = entry.get_by_label(re.compile(label_re, re.I)).first
    return loc if await loc.count() else None


async def _type(box, text):
    await box.click()
    await box.fill("")
    await box.press_sequentially(str(text), delay=25)


async def _date(entry, field_id, label_re, year, month=""):
    """Workday's month / year boxes (month is skipped for education, which only asks for a year)."""
    wrap = entry.locator(f'[data-automation-id="{field_id}"]').first
    if not await wrap.count():
        return False
    y = wrap.locator('[data-automation-id="dateSectionYear-input"]').first
    m = wrap.locator('[data-automation-id="dateSectionMonth-input"]').first
    if month and await m.count():
        await _type(m, month)
    if year and await y.count():
        await _type(y, year)
    return True


async def _pick_option(page, entry, opener, answer):
    """Dropdowns / search lists whose choices appear as [role=option]."""
    await opener.click()
    await page.wait_for_timeout(700)
    opts = page.locator('[role="option"]:visible')
    texts = [t.strip() for t in await opts.all_inner_texts()]
    choice = pick(answer, [t for t in texts if t])
    if not choice:
        await page.keyboard.press("Escape")
        return None
    await opts.nth(texts.index(choice)).click()
    return choice


async def _fill_work(page, entry, w):
    title = await _box(entry, ["jobTitle"], r"job title|title")
    company = await _box(entry, ["company", "companyName"], r"company|employer")
    if not title or not company:
        return False
    await _type(title, w["title"])
    await _type(company, w["company"])
    loc = await _box(entry, ["location"], r"^location|city")
    if loc and w["location"]:
        await _type(loc, w["location"])
    sy, _, sm = w["start"].partition("-")
    ey, _, em = w["end"].partition("-")
    await _date(entry, "formField-startDate", "from", sy, sm)
    cur = await _box(entry, ["currentlyWorkHere"], r"currently work here")
    if w["current"] or not ey:
        if cur:
            await cur.check(force=True)
    else:
        if cur and await cur.is_checked():
            await cur.uncheck(force=True)
        await _date(entry, "formField-endDate", "to", ey, em)
    desc = await _box(entry, ["description", "roleDescription"], r"role description|description")
    if desc and w["description"]:
        await desc.fill(w["description"])
    return True


async def _fill_edu(page, entry, e):
    school = await _box(entry, ["school", "schoolName"], r"school|university")
    if not school:
        return False
    await _type(school, e["school"])
    deg = entry.locator('[data-automation-id="degree"]').first
    if e["degree"] and await deg.count():
        await _pick_option(page, entry, deg, e["degree"])
    fos = await _box(entry, ["fieldOfStudy"], r"field of study")
    if fos and e["field"]:
        await fos.click()
        await fos.fill(e["field"])
        await fos.press("Enter")
        await page.wait_for_timeout(1000)
        opts = page.locator('[role="option"]:visible')
        texts = [t.strip() for t in await opts.all_inner_texts()]
        choice = pick(e["field"], [t for t in texts if t])
        if choice:
            await opts.nth(texts.index(choice)).click()
        else:
            await page.keyboard.press("Escape")
    gpa = await _box(entry, ["gradeAverage", "gpa"], r"overall result|gpa|grade")
    if gpa and e["grade"]:
        await _type(gpa, e["grade"])
    await _date(entry, "formField-firstYearAttended", "from", e["start"])
    await _date(entry, "formField-lastYearAttended", "to", e["end"])
    return True


async def fill_history(page, db):
    """Returns [(label, value, source)] for what was added. Does nothing off Workday's My Experience page."""
    out = []
    hist = get_history()
    for kind, section_id, prefix in SECTIONS:
        items = hist.get(kind) or []
        try:
            section = page.locator(f'[data-automation-id="{section_id}"]').first
            if not items or not await section.count():
                continue
            ids = await _entry_ids(section, prefix)
            first = ids and await section.locator(f'[data-automation-id="{ids[0]}"] input').first.input_value()
            if ids and first:
                log(f"   ℹ Workday already shows {kind.replace('work', 'work experience')} entries; leaving them as they are.")
                continue
            for n, item in enumerate(items):
                if n >= len(ids):
                    add = section.locator('[data-automation-id="add-button"], button:has-text("Add")').first
                    before = len(ids)
                    await add.click()
                    for _ in range(20):
                        await page.wait_for_timeout(250)
                        ids = await _entry_ids(section, prefix)
                        if len(ids) > before:
                            break
                    else:
                        log(f"   ⚠ Couldn't add another {kind} entry on this page.")
                        break
                entry = section.locator(f'[data-automation-id="{ids[n]}"]').first
                ok = await (_fill_work(page, entry, item) if kind == "work" else _fill_edu(page, entry, item))
                if ok:
                    label = f"{item['title']}, {item['company']}" if kind == "work" else f"{item['degree']}, {item['school']}"
                    out.append((("Work history: " if kind == "work" else "Education: ") + label.strip(", "), "added", "your profile"))
        except Exception as ex:
            log(f"   ⚠ Couldn't fill the {kind} section: {str(ex).splitlines()[0][:90]}")
    return out
