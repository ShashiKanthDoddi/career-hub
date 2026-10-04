"""overview module of Career Hub. See MAP.md for what lives where."""
from .gmail import TYPE_LABELS
from .records import tracker_rows
from .store import data


STAGE_ORDER = ["Offer", "Interview", "Assessment", "Rejected", "Applied", "Draft", "Skipped", "Error"]


def jobs_overview():
    rows = tracker_rows()
    notes = data()["notes"]
    updates = data()["email_updates"]
    by_link = {}
    for u in updates:
        if u.get("link"):
            by_link.setdefault(u["link"], []).append(u)
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
        ups = sorted(by_link.get(link, []), key=lambda u: u["date"], reverse=True)
        for u in ups:
            if u["type"] in ("offer", "interview", "assessment", "rejection"):
                stage = TYPE_LABELS[u["type"]].replace("Rejected", "Rejected")
                break
        jobs.append(_job(key, r.get("Date", ""), r.get("Company", ""), r.get("Job title", ""), status, link, stage, ups, notes))
    # Emails about a company that is not in the tracker (applied by hand, or on her phone) still get a card
    known = {(j["company"] or "").strip().lower() for j in jobs}
    loose = {}
    for u in updates:
        c = (u.get("company") or "").strip()
        if not u.get("link") and c and c.lower() not in known and u["type"] in MAIL_STAGE:
            loose.setdefault(c.lower(), []).append(u)
    for ups in loose.values():
        ups.sort(key=lambda u: u["date"], reverse=True)
        stage = next((TYPE_LABELS[u["type"]] for u in ups if u["type"] in ("offer", "interview", "assessment", "rejection")), "Applied")
        jobs.append(_job("mail:" + ups[0]["company"].strip().lower(), ups[-1]["date"][:10], ups[0]["company"].strip(),
                         ups[0].get("title", ""), "Submitted (from email)", "", stage, ups, notes))
    jobs.sort(key=lambda j: j["date"], reverse=True)
    return jobs, updates


MAIL_STAGE = ("received", "interview", "assessment", "offer", "rejection")


def _job(key, date, company, title, status, link, stage, ups, notes):
    """One card. A stage she set by hand wins only until the emails say something new."""
    n = notes.get(key, {})
    chosen = n.get("stage") if n.get("stage") and n.get("auto", stage) == stage else ""
    return {"key": key, "date": date, "company": company, "title": title, "status": status, "link": link,
            "stage": chosen or stage, "auto_stage": stage, "notes": n.get("notes", ""),
            "latest": ups[0] if ups else None, "updates": len(ups)}
