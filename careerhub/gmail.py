"""gmail module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
import asyncio
import datetime
import email.utils
import html
import imaplib
import re
from .bridge import log, notify
from .jobsites import ALERT_SENDERS, alert_jobs
from .records import save_found, seen_links, tracker_rows
from .state import MAIL
from .store import app_state, data, load_profile, save_app_state, save_data
from .textutil import norm, norm_link, truthy


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


MAIL_TYPES = [
    ("offer", r"pleased to (extend|offer)|offer letter|job offer|formal offer|offer of employment|we.d like to offer you"),
    ("rejection", r"unfortunately|regret to inform|not (be )?(moving|move|proceed|proceeding) forward|decided to "
                  r"(move forward|proceed|pursue|go ahead) with other|other candidates|will not be (progressing|proceeding|"
                  r"moving)|not been selected|were not selected|position has (now )?been filled|no longer (under "
                  r"consideration|being considered)|not (a|the right) (fit|match)|we won.t be (moving|progressing)"),
    ("interview", r"\binterview|schedule (a|an|your) (call|chat|conversation|meeting)|phone screen|next round|your "
                  r"availability|calendly\.com|meet with (you|our)|speak with you|invite you to"),
    ("assessment", r"\bassessment|\bassignment|case study|take.?home|online test|hackerrank|testgorilla|task for you"),
    ("received", r"thank you for (applying|your application|your interest)|application (has been |was )?(received|"
                 r"submitted)|we('ve| have) received your application|received your application"),
]


MAIL_SKIP = re.compile(r"verify your (email|account)|confirm your email|activate your account|reset your password|"
                       r"password reset|verification code|one.time (code|password)|job alert|jobs you may be interested|"
                       r"recommended jobs|new jobs for you|jobs matching", re.I)


JOB_WORDS = re.compile(r"applica|applied|interview|position|candida|opportunit|offer|assessment|recruit|hiring|role\b|"
                       r"next steps|talent", re.I)


ATS_SENDERS = ("myworkday", "greenhouse", "lever.co", "ashbyhq", "smartrecruiters", "workable", "icims", "taleo",
               "successfactors", "bamboohr", "jobvite", "recruitee")


TYPE_LABELS = {"offer": "Offer", "rejection": "Rejected", "interview": "Interview", "assessment": "Assessment",
               "received": "Application received", "other": "Update"}


def mail_settings(db=None):
    st = (db.settings if db else (load_profile().get("settings") or {}))
    fields = (load_profile().get("fields") or {}) if db is None else db.fields
    addr = str(st.get("gmail_address") or "").strip() or str(fields.get("e ?mail") or "").strip()
    return {"addr": addr, "pw": str(st.get("gmail_app_password") or "").replace(" ", "").strip(),
            "auto": truthy(st.get("gmail_auto") if st.get("gmail_auto") is not None else "Yes"),
            "helper": str(st.get("helper_email") or "").strip()}


def classify_mail(subject, body):
    text = f"{subject}\n{body[:6000]}"
    if MAIL_SKIP.search(subject):
        return None
    for t, pat in MAIL_TYPES:
        if re.search(pat, text, re.I):
            return t
    return "other"


def dec(h):
    try:
        return str(email.header.make_header(email.header.decode_header(h or "")))
    except Exception:
        return h or ""


def mail_body(msg):
    plain, htm = "", ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            txt = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain" and not plain:
            plain = txt
        elif ctype == "text/html" and not htm:
            htm = re.sub(r"(?is)<(script|style).*?</\1>", " ", txt)
            htm = html.unescape(re.sub(r"<[^>]+>", " ", htm))
    return re.sub(r"\s+", " ", plain or htm).strip()


def company_from_sender(name, addr):
    n = re.sub(r"(?i)\b(recruiting|recruitment|careers?|talent( acquisition)?|hiring( team)?|team|hr|jobs|people|"
               r"no.?reply|notifications?|via \w+|workday)\b", " ", name or "")
    n = re.sub(r"[^\w&.' -]", " ", n).strip(" -.")
    if len(n) >= 2:
        return re.sub(r"\s+", " ", n).strip()
    dom = (addr or "").split("@")[-1].lower()
    parts = [p for p in dom.split(".") if p not in ("com", "co", "in", "io", "net", "org", "mail", "email", "jobs")]
    if parts and not any(a in dom for a in ATS_SENDERS) and parts[-1] not in ("gmail", "outlook", "yahoo"):
        return parts[-1].title()
    return ""


def match_application(text, from_addr, rows):
    t = (text or "").lower()
    tn = norm(text or "")
    best = None
    for r in rows:
        c = (r.get("Company") or "").strip().lower()
        if len(c) < 3 or c in ("job", "linkedin job"):
            continue
        if re.search(rf"\b{re.escape(c)}\b", t) or c.replace(" ", "") in (from_addr or "").lower():
            title = norm(r.get("Job title"))
            score = 3 if (title and len(title) > 5 and title in tn) else 1
            if best is None or score > best[0]:
                best = (score, r)
    return best[1] if best else None


def process_mail(items, rows, known_ids):
    """items: [(gmail_id, raw_bytes)]. Returns new update records."""
    out = []
    for gid, raw in items:
        if gid in known_ids:
            continue
        msg = email.message_from_bytes(raw)
        subject = dec(msg.get("Subject"))
        from_name, from_addr = email.utils.parseaddr(dec(msg.get("From")))
        if any(a in from_addr.lower() for a in ALERT_SENDERS) and re.search(r"(?i)alert|jobs? for you|new jobs|recommended|recommendation", subject):
            continue                                    # job-alert emails are handled by alert_links()
        body = mail_body(msg)
        kind = classify_mail(subject, body)
        if kind is None:
            continue
        app = match_application(f"{from_name} {subject} {body[:4000]}", from_addr, rows)
        if kind == "other" and not app:
            continue
        if not app and not (JOB_WORDS.search(subject) or any(a in from_addr.lower() for a in ATS_SENDERS)):
            continue
        try:
            when = email.utils.parsedate_to_datetime(msg.get("Date")).astimezone().isoformat(timespec="minutes")
        except Exception:
            when = datetime.datetime.now().isoformat(timespec="minutes")
        out.append({"id": gid, "date": when, "from": from_name or from_addr, "subject": subject[:200], "type": kind,
                    "company": (app or {}).get("Company") or company_from_sender(from_name, from_addr),
                    "title": (app or {}).get("Job title", ""), "link": (app or {}).get("Link", ""),
                    "snippet": body[:300], "done": kind in ("received", "rejection", "other")})
    return out


def alert_links(items):
    """Job links from LinkedIn / Indeed / Naukri alert emails: [(link, title, site)]."""
    out = []
    for _gid, raw in items:
        msg = email.message_from_bytes(raw)
        _n, from_addr = email.utils.parseaddr(dec(msg.get("From")))
        site = next((s for s in ("linkedin", "indeed", "naukri") if s in from_addr.lower()), None)
        if not site:
            continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    htm = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", "replace")
                except Exception:
                    continue
                out += [(l, t, site.title()) for l, t in alert_jobs(htm)]
    return out


def imap_fetch(addr, pw, since, known_ids, company_names, limit=400):
    """Reads (never changes) the job inbox. Returns [(gmail_id, raw_bytes)] for likely job emails."""
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    try:
        M.login(addr, pw)
        M.select("INBOX", readonly=True)
        typ, data = M.search(None, "SINCE", f"{since.day:02d}-{MONTHS[since.month - 1]}-{since.year}")
        ids = (data[0] or b"").split()[-limit:]
        wanted = []
        names = [c.lower() for c in company_names if len(c) >= 3]
        for i in range(0, len(ids), 100):
            typ, resp = M.fetch(b",".join(ids[i:i + 100]), "(X-GM-MSGID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            for part in resp:
                if not isinstance(part, tuple):
                    continue
                meta = part[0].decode(errors="replace")
                m = re.search(r"X-GM-MSGID (\d+)", meta)
                gid = format(int(m.group(1)), "x") if m else meta.split()[0]
                if gid in known_ids:
                    continue
                hdr = email.message_from_bytes(part[1])
                head = f"{dec(hdr.get('From'))} {dec(hdr.get('Subject'))}".lower()
                if (any(a in head for a in ALERT_SENDERS) or JOB_WORDS.search(head) or any(a in head for a in ATS_SENDERS)
                        or any(re.search(rf"\b{re.escape(c)}\b", head) for c in names)):
                    wanted.append((meta.split()[0].encode(), gid))
        out = []
        for seq, gid in wanted:
            typ, resp = M.fetch(seq, "(BODY.PEEK[])")
            for part in resp:
                if isinstance(part, tuple):
                    out.append((gid, part[1]))
                    break
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def gmail_link(addr, gid):
    return f"https://mail.google.com/mail/?authuser={quote(addr)}#all/{gid}"


def friendly_mail_error(msg):
    m = msg.lower()
    if "application-specific password" in m:
        return ("Gmail needs an app password here, not your normal password. Create one at "
                "myaccount.google.com/apppasswords (turn on 2-Step Verification first), then paste the 16 letters.")
    if "authenticationfailed" in m or "invalid credentials" in m:
        return "Gmail refused the login. Check the address and the 16-letter app password."
    if "imap" in m and "disabled" in m:
        return "IMAP is switched off for this Gmail. Turn it on in Gmail settings, Forwarding and POP/IMAP."
    return msg[:200]


def mail_failed(hint):
    log(f"⚠  Email check failed: {hint}")
    save_app_state(last_mail_error=hint)
    return {"ok": False, "error": hint}


async def check_mail(manual=False):
    if MAIL["busy"]:
        return {"ok": False, "error": "Already checking."}
    MAIL["busy"] = True
    try:
        ms = mail_settings()
        if not ms["addr"] or not ms["pw"]:
            return {"ok": False, "error": "Add the job Gmail address and its app password in Settings → Job email."}
        if len(ms["pw"]) != 16:
            return mail_failed("That isn't a Gmail app password: those are exactly 16 letters. Create one at "
                               "myaccount.google.com/apppasswords (it needs 2-Step Verification on).")
        st = app_state()
        updates = data()["email_updates"]
        known = {u["id"] for u in updates}
        try:
            last = datetime.datetime.fromisoformat(st.get("last_mail_check", "")) - datetime.timedelta(days=2)
        except Exception:
            last = datetime.datetime.now() - datetime.timedelta(days=60)
        rows = list(reversed(tracker_rows()))
        log("📬 Checking the job inbox for updates…")
        items = await asyncio.to_thread(imap_fetch, ms["addr"], ms["pw"], last.date(), known,
                                        [r.get("Company", "") for r in rows])
        new = process_mail(items, rows, known)
        have, found = seen_links(), []
        for link, title, site in alert_links(items):
            if norm_link(link) not in have:
                have.add(norm_link(link))
                found.append({"score": "", "company": f"{site} alert", "title": title, "location": "", "age": None,
                              "link": link})
        if found:
            save_found(found)
            log(f"   🔎 {len(found)} new job link(s) from job-alert emails (see Find jobs).")
        for u in new:
            u["gmail"] = gmail_link(ms["addr"], u["id"])
        if new:
            updates += new
            updates.sort(key=lambda u: u["date"], reverse=True)
            save_data()
        save_app_state(last_mail_check=datetime.datetime.now().isoformat(timespec="seconds"), last_mail_error="")
        counts = {}
        for u in new:
            counts[u["type"]] = counts.get(u["type"], 0) + 1
        summary = ", ".join(f"{n} {TYPE_LABELS[t].lower()}" for t, n in counts.items()) or "no new job emails"
        log(f"   📬 {summary}.")
        if any(u["type"] in ("interview", "assessment", "offer") for u in new):
            notify("New interview / assessment email!")
        return {"ok": True, "new": len(new), "summary": summary}
    except imaplib.IMAP4.error as e:
        return mail_failed(friendly_mail_error(str(e)))
    except Exception as e:
        return mail_failed(str(e)[:200])
    finally:
        MAIL["busy"] = False
