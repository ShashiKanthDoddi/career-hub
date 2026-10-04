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
        n = notes.get(key, {})
        jobs.append({"key": key, "date": r.get("Date", ""), "company": r.get("Company", ""),
                     "title": r.get("Job title", ""), "status": status, "link": link,
                     "stage": n.get("stage") or stage, "auto_stage": stage, "notes": n.get("notes", ""),
                     "latest": ups[0] if ups else None, "updates": len(ups)})
    return jobs, updates
