"""gmail module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
import asyncio
import datetime
import email.utils
import html
import imaplib
import re
from . import planner
from .bridge import UI, log, notify
from .jobsites import ALERT_SENDERS, alert_jobs
from .meetings import find_change, find_meeting
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
                  r"consideration|being considered)|not (a|the right) (fit|match)|we won.t be (moving|progressing)|"
                  r"decided not to|(move|moving|proceed|proceeding|go|going) (ahead|forward) with (other|another|different)|"
                  r"(continue|continuing) with (other|another)|not (been )?shortlisted|not successful|unsuccessful|"
                  r"unable to (offer|move|proceed|take)|regret|after careful (consideration|review)|"
                  r"pursue (other|another)|not (be )?selected"),
    ("interview", r"\binterview|schedule (a|an|your) (call|chat|conversation|meeting)|phone screen|next round|your "
                  r"availability|calendly\.com|meet with (you|our)|speak with you|invite you to"),
    ("assessment", r"\bassessment|\bassignment|case study|take.?home|online test|hackerrank|testgorilla|task for you"),
    ("received", r"thank you for (applying|your application|your interest)|application (has been |was )?(received|"
                 r"submitted)|we('ve| have) received your application|received your application"),
]


MAIL_SKIP = re.compile(r"verify your (email|account)|confirm your email|activate your account|reset your password|"
                       r"password reset|verification code|one.time (code|password)|job alert|jobs you may be interested|"
                       r"recommended jobs|new jobs for you|jobs matching", re.I)


NOT_INVITE = re.compile(r"interview(ing)? (tips?|questions?|readiness|prep\w*|practice|experiences?|guides?|skills|"
                        r"series|hacks|mistakes|secrets|coach\w*|ready)|(mock|practice|ai) interviews?|interview.ready|"
                        r"(practice|mock) (tests?|series|assessments?)|test series|jobs for you|explore (\w+ )*jobs|"
                        r"(if|should|once) (you are |you're |your (profile|application) is )?(shortlisted|selected|"
                        r"successful|a (good )?(fit|match))[^.\n]*|shortlisted (candidates|profiles)[^.\n]*", re.I)
QUOTED = re.compile(r"\n(On .{0,200}wrote:|-+ ?Original Message|From: .*\n(Sent|Date): )[\s\S]*", re.I)
BLOCKED = set()           # senders she marked "Not a job email" (filled by check_mail)


BULK_SENDERS = re.compile(r"campaign|newsletter|marketing|promo|contests?@|news@|mailer|digest|letters?\b|offers@|"
                          r"events?@|community@", re.I)


def is_bulk(msg, from_name, from_addr):
    """Newsletters and mass mails (unsubscribe link, bulk header or a marketing sender): judged by the subject only."""
    if any(a in from_addr.lower() for a in ATS_SENDERS):
        return False
    return bool(msg.get("List-Unsubscribe") or re.search(r"bulk|list|junk", str(msg.get("Precedence") or ""), re.I)
                or BULK_SENDERS.search(f"{from_addr} {from_name}"))


JOB_WORDS = re.compile(r"applica|applied|interview|position|candida|opportunit|offer|assessment|recruit|hiring|role\b|"
                       r"next steps|talent|update on|status of|regarding your|thank you for your|unfortunately|regret|shortlist|"
                       r"not selected|your interest|your candidacy|your profile", re.I)


BOARD_SENDERS = ALERT_SENDERS + ("ambitionbox", "glassdoor", "foundit", "monster", "shine.com", "instahyre", "cutshort",
                                 "iimjobs", "timesjobs", "hirist", "wellfound", "apna")


ATS_SENDERS = ("myworkday", "greenhouse", "lever.co", "ashbyhq", "smartrecruiters", "workable", "icims", "taleo",
               "successfactors", "bamboohr", "jobvite", "recruitee")


MAIL_LABELS = {}          # gmail id -> her Gmail labels (filled by imap_fetch)
LABEL_KINDS = [("interview", "interview"), ("assessment", "assessment"), ("reject", "rejection"), ("declin", "rejection"),
               ("not selected", "rejection"), ("unsuccessful", "rejection"), ("offer", "offer")]


def label_kind(labels):
    """Her own Gmail labels (e.g. Applied/Interviews, Rejected) decide the type; 'Job boards' mail is ignored."""
    names = [norm(l) for l in labels]                  # whole path, so Applied/Rejected and Rejected/Naukri both count
    for key, kind in LABEL_KINDS:
        if any(key in n for n in names):
            return kind
    if any("job board" in n for n in names):
        return "skip"
    return None


TYPE_LABELS = {"offer": "Offer", "rejection": "Rejected", "interview": "Interview", "assessment": "Assessment",
               "received": "Application received", "other": "Update"}


def mail_settings(db=None):
    st = (db.settings if db else (load_profile().get("settings") or {}))
    fields = (load_profile().get("fields") or {}) if db is None else db.fields
    addr = str(st.get("gmail_address") or "").strip() or str(fields.get("e ?mail") or "").strip()
    pw = str(st.get("gmail_app_password") or "").replace(" ", "").strip()
    boxes = [(addr, pw)]
    for n in ("2", "3"):                                # extra inboxes to read, each with its own app password
        a = str(st.get(f"gmail_address_{n}") or "").strip()
        p = str(st.get(f"gmail_app_password_{n}") or "").replace(" ", "").strip()
        if a and len(p) == 16:
            boxes.append((a, p))
    return {"addr": addr, "pw": pw, "boxes": boxes,
            "auto": truthy(st.get("gmail_auto") if st.get("gmail_auto") is not None else "Yes"),
            "helper": str(st.get("helper_email") or "").strip()}


def type_scores(subject, body):
    """Points per mail type: 3 for a match in the subject, 1 per match in the text (up to 3).
    Quoted earlier mails, interview tips and 'if shortlisted…' sentences don't count."""
    subj = NOT_INVITE.sub(" ", subject or "")
    text = NOT_INVITE.sub(" ", QUOTED.sub("", "\n".join(l for l in (body or "")[:8000].splitlines()
                                                       if not l.lstrip().startswith(">"))))
    scores = {}
    for t, pat in MAIL_TYPES:
        s = 3 * bool(re.search(pat, subj, re.I)) + min(3, len(re.findall(pat, text, re.I)))
        if s:
            scores[t] = s
    return scores


def classify_mail(subject, body, strict=False):
    """An offer or rejection wins when found (an outcome beats a polite subject); otherwise the best-scoring type
    (ties go to the earlier type in MAIL_TYPES). strict: an interview or test needs 2 points."""
    if MAIL_SKIP.search(subject or ""):
        return None
    sc = type_scores(subject, body)
    if strict:
        sc = {t: s for t, s in sc.items() if s >= 2 or t not in ("interview", "assessment")}
    for t in ("offer", "rejection"):
        if t in sc:
            return t
    best = max(sc.values(), default=0)
    return next((t for t, _p in MAIL_TYPES if sc.get(t) == best), "other") if best else "other"


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


COMPANY_WORDS = re.compile(r"(?i)(inc|ltd|llc|llp|pvt|corp|co|services|technologies|solutions|consulting|group|systems|labs|bank|"
                           r"software|global|india|limited)")


SUBJECT_JOB = re.compile(r"(?i)your application (?:to|for|was sent to|to the)\s+(.+?)\s+(?:at|with|@)\s+(.+?)\s*$")


def job_from_subject(subject):
    """LinkedIn-style 'Your application to <title> at <company>': (company, title), or ('', '')."""
    m = SUBJECT_JOB.search(subject or "")
    if not m:
        return "", ""
    return m.group(2).strip(" .-"), m.group(1).strip(" .-")


def company_from_sender(name, addr):
    n = re.sub(r"(?i)(recruiting|recruitment|careers?|talent( acquisition)?|hiring( team)?|team|hr|jobs|people|"
               r"no.?reply|notifications?|via \w+|workday)", " ", name or "")
    n = re.sub(r"[^\w&.' -]", " ", n).strip(" -.")
    n = re.sub(r"\s+", " ", n).strip()
    dom = (addr or "").split("@")[-1].lower()
    parts = [p for p in dom.split(".") if p not in ("com", "co", "in", "io", "net", "org", "mail", "email", "jobs")]
    slug = parts[-1] if parts and not any(a in dom for a in ATS_SENDERS) and parts[-1] not in ("gmail", "outlook", "yahoo", "hotmail") else ""
    if len(n) >= 2 and (not slug or COMPANY_WORDS.search(n) or slug in re.sub(r"\W", "", n.lower())):
        return n                                        # "Choragudi, Kamala A." is a person: use the mail domain instead
    return slug.title() if slug else (n if len(n) >= 2 else "")


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
        lk = label_kind(MAIL_LABELS.get(gid, []))
        if gid in known_ids and (lk in (None, "skip") or known_ids[gid] == lk):
            continue
        msg = email.message_from_bytes(raw)
        subject = dec(msg.get("Subject"))
        from_name, from_addr = email.utils.parseaddr(dec(msg.get("From")))
        if any(a in from_addr.lower() for a in ALERT_SENDERS) and re.search(r"(?i)alert|jobs? for you|new jobs|recommended|recommendation", subject):
            continue                                    # job-alert emails are handled by alert_links()
        if lk == "skip" or from_addr.lower() in BLOCKED or (from_name or "").lower() in BLOCKED:
            continue
        body = mail_body(msg)
        app = match_application(f"{from_name} {subject} {body[:4000]}", from_addr, rows)
        ats = any(a in from_addr.lower() for a in ATS_SENDERS)
        bulk = not ats and (any(a in from_addr.lower() for a in BOARD_SENDERS) or is_bulk(msg, from_name, from_addr))
        reply = not bulk and bool(msg.get("In-Reply-To")) and re.match(r"(?i)\s*(re|aw|sv)\s*:", subject or "")
        if lk:                                          # 1. her own Gmail label decides
            kind = lk
        elif bulk:                                      # 2. job-board digests and newsletters: the subject only
            kind = classify_mail(subject, "")
            if kind not in ("interview", "assessment", "offer", "rejection"):
                continue
        elif app or ats or reply:                       # 3. about her applications: read the whole mail
            kind = classify_mail(subject, body)
        elif JOB_WORDS.search(subject or ""):           # 4. job-like mail from someone not in her list: stricter
            kind = classify_mail(subject, body, strict=True)
        else:
            continue
        if kind is None or (kind == "other" and not app):
            continue
        try:
            when = email.utils.parsedate_to_datetime(msg.get("Date")).astimezone().isoformat(timespec="minutes")
        except Exception:
            when = datetime.datetime.now().isoformat(timespec="minutes")
        meeting = find_meeting(f"{subject} {body[:6000]}", datetime.datetime.fromisoformat(when).date()) if kind == "interview" else None
        sub_company, sub_title = job_from_subject(subject)
        out.append({"id": gid, "date": when, "from": from_name or from_addr, "from_addr": from_addr.lower(), "subject": subject[:200], "type": kind,
                    "company": (app or {}).get("Company") or sub_company or company_from_sender(from_name, from_addr),
                    "title": (app or {}).get("Job title", "") or sub_title, "link": (app or {}).get("Link", ""),
                    "snippet": body[:300], "done": kind in ("received", "rejection", "other"),
                    "meeting": meeting, "change": find_change(f"{subject} {body[:6000]}") if kind == "interview" else ""})
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


def imap_fetch(addr, pw, since, known_ids, company_names, limit=1500, progress=None, seen=None):
    """Reads (never changes) the job inbox. Returns [(gmail_id, raw_bytes)] for likely job emails.
    seen (a set) gets every mail id looked at, so check_mail knows which old cards were re-checked."""
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    try:
        M.login(addr, pw)
        if M.select('"[Gmail]/All Mail"', readonly=True)[0] != "OK":     # all mail: labelled mail moved out of the inbox too
            M.select("INBOX", readonly=True)
        day = f"{since.day:02d}-{MONTHS[since.month - 1]}-{since.year}"
        typ, data = M.search(None, "SINCE", day)
        ids = (data[0] or b"").split()[-limit:]
        try:                                            # Gmail's own Promotions / Social tabs: newsletters, not replies
            promo = set((M.search(None, "X-GM-RAW", '"category:promotions OR category:social"', "SINCE", day)[1][0]
                         or b"").split())
        except Exception:
            promo = set()
        wanted = []
        names = [c.lower() for c in company_names if len(c) >= 3]
        for i in range(0, len(ids), 100):
            if progress:
                progress("Scanning", min(i + 100, len(ids)), len(ids))
            typ, resp = M.fetch(b",".join(ids[i:i + 100]), "(X-GM-MSGID X-GM-LABELS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
            for k, part in enumerate(resp):
                if not isinstance(part, tuple):
                    continue
                meta = part[0].decode(errors="replace")
                if k + 1 < len(resp) and isinstance(resp[k + 1], bytes):
                    meta += " " + resp[k + 1].decode(errors="replace")      # Gmail may send the labels after the header text
                m = re.search(r"X-GM-MSGID (\d+)", meta)
                gid = format(int(m.group(1)), "x") if m else meta.split()[0]
                lm = re.search(r"X-GM-LABELS \((.*?)\)\s", meta + " ")
                labs = [a or b for a, b in re.findall(r'"([^"]*)"|([^\s"]+)', lm.group(1))] if lm else []
                if {"\\Sent", "\\Draft", "\\Spam", "\\Trash"} & set(labs):
                    continue
                MAIL_LABELS[gid] = [l for l in labs if not l.startswith("\\")]
                if seen is not None:
                    seen.add(gid)
                if gid in known_ids and label_kind(MAIL_LABELS[gid]) in (None, "skip", known_ids[gid]):
                    continue
                hdr = email.message_from_bytes(part[1])
                head = f"{dec(hdr.get('From'))} {dec(hdr.get('Subject'))}".lower()
                lk = label_kind(MAIL_LABELS[gid])
                if lk is None and (any(b in head for b in BLOCKED) or (meta.split()[0].encode() in promo and not any(
                        a in head for a in ALERT_SENDERS + ATS_SENDERS))):
                    continue                            # her blocked senders; promotions (job alerts and ATS mail still read)
                if (label_kind(MAIL_LABELS[gid]) not in (None, "skip") or any(a in head for a in ALERT_SENDERS) or JOB_WORDS.search(head) or any(a in head for a in ATS_SENDERS)
                        or any(re.search(rf"\b{re.escape(c)}\b", head) for c in names)):
                    wanted.append((meta.split()[0].encode(), gid))
        out, by_seq = [], {seq: gid for seq, gid in wanted}
        log(f"   📨 Reading {len(wanted)} likely job email(s)…")
        for i in range(0, len(wanted), 25):             # 25 at a time: one by one took minutes on a first run
            batch = [seq for seq, _g in wanted[i:i + 25]]
            if progress:
                progress("Reading", min(i + 25, len(wanted)), len(wanted))
            typ, resp = M.fetch(b",".join(batch), "(BODY.PEEK[])")
            for part in resp:
                if isinstance(part, tuple) and part[0].split()[0] in by_seq:
                    out.append((by_seq[part[0].split()[0]], part[1]))
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
        updates[:] = [u for u in updates                # drop "you applied for 5 jobs" digests from job boards
                      if not (any(b.split(".")[0] in (u.get("from") or "").lower() for b in BOARD_SENDERS)
                              and classify_mail(u.get("subject", ""), "") not in ("interview", "assessment", "offer"))]
        old_unmatched = {}
        if st.get("label_scan") != 6:                   # re-read unmatched, "received"/"update" and interview cards (6: new sorting)
            old_unmatched = {u["id"]: u for u in updates if not u.get("link")
                             or u.get("type") in ("received", "other", "interview", "assessment")}
            updates[:] = [u for u in updates if u["id"] not in old_unmatched]
        known = {u["id"]: u.get("type") for u in updates}
        BLOCKED.clear()
        BLOCKED.update(b.lower() for b in data().get("mail_blocked", []))
        try:
            last = datetime.datetime.fromisoformat(st.get("last_mail_check", "")) - datetime.timedelta(days=2)
        except Exception:
            last = datetime.datetime.now() - datetime.timedelta(days=60)
        if st.get("label_scan") != 6:                   # one wider pass so labelled mail from before label reading is sorted
            last = min(last, datetime.datetime.now() - datetime.timedelta(days=180))
        rows = list(reversed(tracker_rows()))
        log("📬 Checking the job inbox for updates…")
        names = [r.get("Company", "") for r in rows]
        have, found, new, reread = seen_links(), [], [], set()
        loop = asyncio.get_running_loop()

        def progress(what, done, total):                # runs in the reading thread: hand it to the window safely
            loop.call_soon_threadsafe(UI._send, {"type": "mail_progress", "what": what, "done": done, "total": total})
        for n, (addr, pw) in enumerate(ms["boxes"]):    # the first inbox must work; extra ones are skipped if they fail
            try:
                items = await asyncio.to_thread(imap_fetch, addr, pw, last.date(), known, names, 1500, progress, reread)
            except Exception as e:
                if n == 0:
                    raise
                log(f"⚠  Couldn't read the extra inbox {addr}: {friendly_mail_error(str(e))}")
                continue
            box_new = process_mail(items, rows, known)
            for u in box_new:
                u["gmail"] = gmail_link(addr, u["id"])
            new += box_new
            for link, title, site in alert_links(items):
                if norm_link(link) not in have:
                    have.add(norm_link(link))
                    found.append({"score": "", "company": f"{site} alert", "title": title, "location": "",
                                  "age": None, "link": link})
        for u in new:
            if u["id"] in old_unmatched:
                u["done"] = old_unmatched[u["id"]].get("done", u["done"])
        kept = [u for i, u in old_unmatched.items() if i not in reread]  # too old to re-read this time: keep the card
        replaced = {u["id"] for u in new}
        updates[:] = [u for u in updates if u["id"] not in replaced]   # a re-sorted mail replaces its old card
        if found:
            save_found(found)
            log(f"   🔎 {len(found)} new job link(s) from job-alert emails (see Find jobs).")
        if new or old_unmatched:
            updates += new + kept
            updates.sort(key=lambda u: u["date"], reverse=True)
        gone = set(old_unmatched) - {u["id"] for u in updates}            # re-sorted as not a job email: drop its calendar entry
        data()["events"][:] = [e for e in data()["events"] if e.get("mail_id") not in gone]
        booked = planner.events_from_mail(updates)
        if new or booked or old_unmatched:
            save_data()
        if booked:
            log(f"   📅 {booked} interview(s) from your emails added to the calendar.")
        save_app_state(last_mail_check=datetime.datetime.now().isoformat(timespec="seconds"), last_mail_error="",
                       label_scan=6)
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
