"""overview module of Career Hub. See MAP.md for what lives where."""
import datetime

from .gmail import TYPE_LABELS, job_from_subject
from .records import tracker_rows
from .store import STORE, data


STAGE_ORDER = ["Offer", "Interview", "Assessment", "Waiting", "Rejected", "Applied", "NoResponse", "Draft", "Skipped", "Error"]


_MEMO = {}


def jobs_overview():
    """Cached until the data is saved again (or the hour changes, since stages depend on dates)."""
    key = (STORE.version, datetime.datetime.now().strftime("%Y-%m-%d %H"))   # interview times pass during the day
    if _MEMO.get("key") != key:
        _MEMO["key"], _MEMO["val"] = key, _build_overview()
    return _MEMO["val"]


def _build_overview():
    rows = tracker_rows()
    notes = data()["notes"]
    updates = data()["email_updates"]
    by_link, by_company = {}, {}
    for u in updates:
        sub_company, sub_title = job_from_subject(u.get("subject"))
        if sub_company:                                  # older mail was stored under "LinkedIn": fix on the fly
            u["company"], u["title"] = sub_company, u.get("title") or sub_title
        if u.get("link"):
            by_link.setdefault(u["link"], []).append(u)
        elif (u.get("company") or "").strip() and u["type"] in MAIL_STAGE:
            by_company.setdefault(u["company"].strip().lower(), []).append(u)
    jobs, seen = [], set()
    for r in reversed(rows):
        link = r.get("Link", "")
        key = link or f"{r.get('Company')}|{r.get('Job title')}|{r.get('Date')}"
        if key in seen:
            continue
        seen.add(key)
        status = r.get("Status", "")
        stage = ("Applied" if status.startswith("Submitted") else "Draft" if status.startswith("Not submitted")
                 else "Skipped" if status.startswith("Skipped") else "Error" if status.startswith("Error") else status)
        ups = by_link.get(link, [])
        if not ups and stage in ("Applied", "Draft"):    # an email that matched no link still belongs to the newest job at that company
            ups = by_company.pop((r.get("Company") or "").strip().lower(), [])
        ups = sorted(ups, key=lambda u: u["date"], reverse=True)
        for u in ups:
            if u["type"] in ("offer", "interview", "assessment", "rejection"):
                stage = TYPE_LABELS[u["type"]].replace("Rejected", "Rejected")
                break
        jobs.append(_job(key, r.get("Date", ""), r.get("Company", ""), r.get("Job title", ""), status, link, stage, ups, notes))
    # Emails about a company that is not in the tracker (applied by hand, or on her phone) still get a card
    for ups in by_company.values():
        ups.sort(key=lambda u: u["date"], reverse=True)
        stage = next((TYPE_LABELS[u["type"]] for u in ups if u["type"] in ("offer", "interview", "assessment", "rejection")), "Applied")
        jobs.append(_job("mail:" + ups[0]["company"].strip().lower(), ups[-1]["date"][:10], ups[0]["company"].strip(),
                         ups[0].get("title", ""), "Submitted (from email)", "", stage, ups, notes))
    jobs.sort(key=lambda j: j["date"], reverse=True)
    return jobs, updates


MAIL_STAGE = ("received", "interview", "assessment", "offer", "rejection")


NO_REPLY_DAYS = 30


def _passed(date, time=""):
    """True when a 'YYYY-MM-DD' (and optional 'HH:MM') is in the past."""
    try:
        d = datetime.date.fromisoformat((date or "")[:10])
    except ValueError:
        return False
    if d != datetime.date.today():
        return d < datetime.date.today()
    try:
        return datetime.datetime.strptime(time, "%H:%M").time() < datetime.datetime.now().time()
    except ValueError:
        return False                                      # today, no time known: still counts as happening


def _timed_stage(key, date, stage, ups):
    """Interview whose date has passed -> Waiting. Applied for 30+ days with no reply -> No response."""
    if stage == "Interview":
        when = [(e["date"], e.get("time", "")) for e in data()["events"] if e.get("ref") == key and e.get("date")]
        when += [((u.get("meeting") or {}).get("date"), (u.get("meeting") or {}).get("time", ""))
                 for u in ups if u["type"] == "interview" and (u.get("meeting") or {}).get("date")]
        if when and _passed(*max(when)):
            return "Waiting"
    elif stage == "Applied" and date:
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(date[:10])).days
        except ValueError:
            return stage
        if age >= NO_REPLY_DAYS:
            return "NoResponse"
    return stage


def _job(key, date, company, title, status, link, stage, ups, notes):
    """One card. A stage she set by hand wins only until the emails say something new."""
    stage = _timed_stage(key, date, stage, ups)
    n = notes.get(key, {})
    chosen = n.get("stage") if n.get("stage") and n.get("auto", stage) == stage else ""
    return {"key": key, "date": date, "company": company, "title": title, "status": status, "link": link,
            "stage": chosen or stage, "auto_stage": stage, "notes": n.get("notes", ""),
            "latest": ups[0] if ups else None, "updates": len(ups)}
