"""planner: interviews on the Home calendar and the to-do list. Stored in career_data.json under 'events' and 'todos'."""
import datetime
import uuid
from .store import data, save_data


def _date(s):
    try:
        return datetime.date.fromisoformat(str(s or "").strip()).isoformat()
    except ValueError:
        return ""


def _time(s):
    try:
        return datetime.datetime.strptime(str(s or "").strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        return ""


def list_events():
    return sorted(data()["events"], key=lambda e: (e["date"], e.get("time") or "99:99"))


def add_event(title, date, time="", company="", note="", mail_id="", ref=""):
    d = _date(date)
    if not d or not str(title or "").strip():
        return None
    if mail_id and any(e.get("mail_id") == mail_id for e in data()["events"]):
        return None                                    # this email is already on the calendar
    ev = {"id": uuid.uuid4().hex[:8], "title": str(title).strip()[:120], "company": str(company or "").strip()[:80],
          "date": d, "time": _time(time), "note": str(note or "").strip()[:300], "mail_id": mail_id, "ref": ref}
    data()["events"].append(ev)
    save_data()
    return ev


def delete_event(eid):
    data()["events"] = [e for e in data()["events"] if e["id"] != eid]
    save_data()


def add_todo(text):
    text = str(text or "").strip()[:200]
    if not text:
        return None
    t = {"id": uuid.uuid4().hex[:8], "text": text, "done": False}
    data()["todos"].append(t)
    save_data()
    return t


def set_todo(tid, done):
    for t in data()["todos"]:
        if t["id"] == tid:
            t["done"] = bool(done)
    save_data()


def delete_todo(tid):
    data()["todos"] = [t for t in data()["todos"] if t["id"] != tid]
    save_data()


def clear_done_todos():
    data()["todos"] = [t for t in data()["todos"] if not t["done"]]
    save_data()


def events_from_mail(updates):
    """Puts interviews found in emails on the calendar (each email once). A reschedule email moves that company's
    earlier email entry; a cancellation removes it. Returns how many calendar entries changed."""
    from .meetings import find_change, find_meeting
    changed = 0
    for u in sorted(updates, key=lambda x: x.get("date", "")):          # oldest first, so the newest email wins
        if u.get("type") != "interview" or u.get("cal_done"):
            continue
        u["cal_done"] = True
        try:
            sent = datetime.datetime.fromisoformat(u["date"]).date()
        except (KeyError, ValueError):
            continue
        text = f"{u.get('subject', '')} {u.get('snippet', '')}"
        change = u["change"] if "change" in u else find_change(text)
        m = u.get("meeting")
        if m is None and "meeting" not in u:                  # emails saved before 2.5 only kept the subject and first lines
            m = find_meeting(text, sent)
        company = (u.get("company") or "").strip().lower()
        old = next((e for e in reversed(data()["events"]) if company and e.get("mail_id")
                    and (e.get("company") or "").strip().lower() == company), None)
        if change == "cancel" and old:
            data()["events"].remove(old)
            changed += 1
        elif m and change == "reschedule" and old:
            old.update(date=m["date"], time=m.get("time", ""), mail_id=u["id"])
            changed += 1
        elif m and add_event("Interview" + (f", {u['title']}" if u.get("title") else ""), m["date"], m.get("time", ""),
                             u.get("company", ""), "", u["id"]):
            changed += 1
    return changed



def set_job_event(key, stage, company, title, date, time=""):
    """A card moved to Interview / Test on My jobs: one calendar entry per job (moving it again replaces the date)."""
    drop_job_event(key)
    label = "Test" if stage == "Assessment" else "Interview"
    return add_event(f"{label}, {title}" if title else label, date, time, company, "", ref=key)


def drop_job_event(key):
    data()["events"] = [e for e in data()["events"] if e.get("ref") != key]
    save_data()
