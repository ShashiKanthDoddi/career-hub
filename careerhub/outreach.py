"""outreach module of Career Hub (Reach out page). See MAP.md for what lives where.
Finds hiring emails on company websites, writes one personal mail each, then shows it, saves it as a Gmail draft or sends it.
The page calls one api_reach_* function per company, so progress, Stop and her edits all stay on the page."""
import datetime
import email.message
import email.utils
import html
import imaplib
import re
import smtplib
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from .ai import ai_complete
from .config import OWNER
from .gmail import mail_settings
from .resume import resume_profile, resume_text
from .resume_tools import html_to_text
from .state import PW
from .store import data, save_data

DAILY_LIMIT = 20                                   # mails per day from her Gmail; Gmail itself allows far more, this keeps the account safe
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
JUNK_MAIL = re.compile(r"(no-?reply|donotreply|do-not-reply|mailer-daemon|postmaster|abuse|privacy|unsubscribe|sentry|wixpress|"
                       r"example\.|@(?:sentry|domain|email|yourdomain)\.|\.(?:png|jpe?g|gif|svg|webp|css|js)$)", re.I)
PREFER = ("hr", "career", "careers", "job", "jobs", "hiring", "recruit", "recruitment", "talent", "people", "work", "join", "resume", "cv")
GENERAL = ("info", "contact", "hello", "hi", "enquiry", "enquiries", "team", "office", "admin", "mail", "support")
PAGE_HINTS = re.compile(r"contact|career|job|join|hiring|work-with|about|team|opening|vacanc", re.I)


def valid_email(e):
    return bool(re.fullmatch(EMAIL_RE.pattern, str(e or "").strip())) and not JUNK_MAIL.search(str(e))


def rank_emails(found, site_host=""):
    """Best address first: hiring words, then general inboxes, then personal ones. Addresses on the company's own site come before others."""
    host = re.sub(r"^www\.", "", (site_host or "").lower())
    out, seen = [], set()
    for e in found:
        e = e.strip().strip(".,;:)>]").lower()
        if e in seen or not valid_email(e):
            continue
        seen.add(e)
        local, dom = e.split("@", 1)
        base = re.split(r"[._+-]", local)[0]
        score = (0 if local in PREFER or base in PREFER else 1 if local in GENERAL or base in GENERAL else 2) * 2 \
            + (0 if host and (dom == host or dom.endswith("." + host) or host.endswith("." + dom)) else 1)
        out.append((score, len(out), e))
    return [e for _, _, e in sorted(out)]


def company_from(html, url):
    m = (re.search(r'(?is)<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html or "")
         or re.search(r"(?is)<title[^>]*>(.*?)</title>", html or ""))
    name = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    name = re.split(r"\s[|\-–—:·]\s", name)[0].strip()
    if not name or len(name) > 40:
        host = re.sub(r"^www\.", "", urlparse(url).netloc.lower())
        name = host.split(".")[0].replace("-", " ").title()
    return name


async def _get(req, url):
    try:
        r = await req.get(url, timeout=15000)
        return await r.text() if r.ok else ""
    except Exception:
        return ""


def decode_cf(htm):
    """Cloudflare's 'email protected' links keep the address as hex (data-cfemail / email-protection#...)."""
    out = []
    for h in re.findall(r"(?i)(?:data-cfemail=[\"']|email-protection#)([0-9a-f]{6,})", htm or ""):
        try:
            k = int(h[:2], 16)
            out.append("".join(chr(int(h[i:i + 2], 16) ^ k) for i in range(2, len(h) - 1, 2)))
        except ValueError:
            pass
    return out


def emails_in(htm):
    """Every address in a page: mailto links, plain text, 'name [at] site [dot] com', &#64; and Cloudflare-protected ones."""
    htm = html.unescape(htm or "")
    plain = html_to_text(htm)
    plain = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", plain, flags=re.I)
    plain = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", plain, flags=re.I)
    return re.findall(r"(?i)mailto:([^\"'?>\s]+)", htm) + decode_cf(htm) + EMAIL_RE.findall(plain)


def _links(home, url):
    host = urlparse(url).netloc
    out = []
    for href in re.findall(r"""(?i)href=["']([^"'#]+)["']""", home):
        if PAGE_HINTS.search(href) and not href.lower().startswith(("mailto:", "tel:", "javascript:")):
            full = urljoin(url, href)
            if urlparse(full).netloc == host and full not in out and full.rstrip("/") != url.rstrip("/"):
                out.append(full)
    return out[:3]


async def _browse(urls):
    """Opens pages in a real browser, so addresses that scripts put on the page appear. Slower, so only used when the quick read found nothing."""
    found, text = [], ""
    browser = await PW["p"].chromium.launch()
    try:
        pg = await browser.new_page()
        for u in urls:
            try:
                await pg.goto(u, timeout=20000, wait_until="domcontentloaded")
                try:
                    await pg.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                htm = await pg.content()
                found += emails_in(htm)
                text += "\n" + html_to_text(htm)
            except Exception:
                continue
    finally:
        await browser.close()
    return found, text


async def find_site(url):
    """Opens a company website (home, then its Contact / Careers / About pages) and returns what it found."""
    url = url if re.match(r"https?://", url, re.I) else "https://" + url
    req = await PW["p"].request.new_context(extra_http_headers={"User-Agent": "Mozilla/5.0 (CareerHub)"})
    try:
        home = await _get(req, url)
        if not home:
            return {"ok": False, "error": "Couldn't open this website."}
        todo = _links(home, url)
        pages = [home] + [await _get(req, u) for u in todo]
        found = [e for page in pages for e in emails_in(page)]
        text = "\n".join(html_to_text(p) for p in pages)
    finally:
        await req.dispose()
    host = urlparse(url).netloc
    emails = rank_emails(found, host)
    if not emails:                                     # second try: let the pages run their scripts
        more, text2 = await _browse([url] + todo)
        emails, text = rank_emails(more, host), text or text2
    hrefs = [urljoin(url, h) for h in re.findall(r"""(?i)href=["']([^"'#]+)["']""", home) if h.lower().startswith(("http", "/"))]
    useful = [h for h in hrefs if re.search(r"contact|career|jobs?\.|/jobs|join-us|work-with", h, re.I)]
    return {"ok": True, "company": company_from(home, url), "site": url, "emails": emails[:5], "text": text[:2500],
            "links": list(dict.fromkeys(useful))[:2]}


def _hdr(msg, name):
    from .gmail import dec
    return dec(msg.get(name))


def gmail_contacts(addr, pw, limit=400):
    """Addresses from her own Gmail: people who wrote to her (recruiters, agencies, companies) and people she wrote to before.
    Newsletters, job boards, hiring-system mail and no-reply senders are left out."""
    import email as _email
    import email.utils
    from .gmail import ATS_SENDERS, BOARD_SENDERS, BLOCKED, BULK_SENDERS, SOCIAL_SENDERS, company_from_sender
    own = {a.lower() for a, _ in mail_settings()["boxes"]} | {addr.lower()}
    out = {}

    def scan(folder, fields, kind):
        if M.select(f'"{folder}"', readonly=True)[0] != "OK":
            return
        n = int(M.search(None, "ALL")[1][0].split()[-1]) if M.search(None, "ALL")[1][0] else 0
        lo = max(1, n - limit + 1)
        if not n:
            return
        typ, rows = M.fetch(f"{lo}:{n}", f"(BODY.PEEK[HEADER.FIELDS ({fields})])")
        for r in rows if typ == "OK" else []:
            if not isinstance(r, tuple):
                continue
            msg = _email.message_from_bytes(r[1])
            if kind == "got" and (msg.get("List-Unsubscribe") or msg.get("List-Id")
                                  or re.search(r"bulk|list|junk", str(msg.get("Precedence") or ""), re.I)):
                continue
            pairs = email.utils.getaddresses([_hdr(msg, "From")] if kind == "got" else [_hdr(msg, "To"), _hdr(msg, "Cc")])
            for name, a in pairs:
                a = a.strip().lower()
                if not valid_email(a) or a in own or a in out or a in BLOCKED:
                    continue
                if any(k in a for k in ATS_SENDERS + tuple(BOARD_SENDERS)) or SOCIAL_SENDERS.search(a) or BULK_SENDERS.search(a):
                    continue
                d = msg.get("Date") or ""
                out[a] = {"email": a, "company": company_from_sender(name, a) or a.split("@")[1].split(".")[0].title(),
                          "kind": kind, "date": d[:16], "subject": _hdr(msg, "Subject")[:70]}

    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    try:
        M.login(addr, pw)
        scan("[Gmail]/Sent Mail", "TO CC DATE SUBJECT", "wrote")
        scan("INBOX", "FROM DATE SUBJECT LIST-UNSUBSCRIBE LIST-ID PRECEDENCE", "got")
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return list(out.values())


FREE_MAIL = ("gmail.com", "googlemail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com", "live.com", "rediffmail.com", "icloud.com", "proton.me")


def _when(msg):
    try:
        d = email.utils.parsedate_to_datetime(msg.get("Date"))
        return d.astimezone().replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return None


def reach_summary(addr, pw, sent, limit=500, days=60):
    """Who answered the mails sent from Reach out, and who else wrote to her. sent = history rows (email, company, date, how).
    A reply is a mail after the send date from the same address, or from the same company domain (not Gmail and the like)."""
    import email as _email
    from .gmail import ATS_SENDERS, BOARD_SENDERS, BLOCKED, BULK_SENDERS, SOCIAL_SENDERS, JOB_WORDS, company_from_sender
    own = {a.lower() for a, _ in mail_settings()["boxes"]} | {addr.lower()}
    by_addr = {}
    by_dom = {}
    for r in sent:
        e = str(r.get("email", "")).lower()
        if "@" not in e:
            continue
        try:
            when = datetime.datetime.fromisoformat(r.get("date", ""))
        except ValueError:
            when = datetime.datetime.min
        by_addr[e] = (r, when)
        d = e.split("@")[1]
        if d not in FREE_MAIL:
            by_dom[d] = (r, when)
    replies, others = {}, {}
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    M = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    try:
        M.login(addr, pw)
        if M.select("INBOX", readonly=True)[0] != "OK":
            return {"replies": [], "others": []}
        ids = M.search(None, "ALL")[1][0].split()
        if not ids:
            return {"replies": [], "others": []}
        lo, hi = max(1, int(ids[-1]) - limit + 1), int(ids[-1])
        typ, rows = M.fetch(f"{lo}:{hi}", "(BODY.PEEK[HEADER.FIELDS (FROM DATE SUBJECT LIST-UNSUBSCRIBE LIST-ID PRECEDENCE)])")
        for r in rows if typ == "OK" else []:
            if not isinstance(r, tuple):
                continue
            msg = _email.message_from_bytes(r[1])
            name, a = email.utils.parseaddr(_hdr(msg, "From"))
            a, when = a.strip().lower(), _when(msg)
            if not valid_email(a) or a in own or a in BLOCKED or when is None:
                continue
            hit = by_addr.get(a) or by_dom.get(a.split("@")[1])
            if hit:
                if when >= hit[1] and a not in replies:
                    replies[a] = {"email": a, "company": hit[0].get("company") or company_from_sender(name, a), "date": when.isoformat(timespec="minutes"),
                                  "subject": _hdr(msg, "Subject")[:80]}
                continue
            if when < cutoff or a in others or msg.get("List-Unsubscribe") or msg.get("List-Id") \
                    or re.search(r"bulk|list|junk", str(msg.get("Precedence") or ""), re.I):
                continue
            if any(k in a for k in ATS_SENDERS + tuple(BOARD_SENDERS)) or SOCIAL_SENDERS.search(a) or BULK_SENDERS.search(a):
                continue
            subj = _hdr(msg, "Subject")
            if JOB_WORDS.search(subj):
                others[a] = {"email": a, "company": company_from_sender(name, a) or a.split("@")[1].split(".")[0].title(),
                             "date": when.isoformat(timespec="minutes"), "subject": subj[:80]}
    finally:
        try:
            M.logout()
        except Exception:
            pass
    key = lambda x: x["date"]
    return {"replies": sorted(replies.values(), key=key, reverse=True), "others": sorted(others.values(), key=key, reverse=True)[:30]}


CHANNELS = ["WhatsApp", "LinkedIn", "Phone call", "Naukri", "Instagram", "Telegram", "Agency or consultant", "Other"]


def other_list():
    return data().setdefault("outreach_other", [])


def add_other(channel, who, note, date):
    rows = other_list()
    try:
        date = datetime.date.fromisoformat(str(date)[:10]).isoformat()
    except ValueError:
        date = datetime.date.today().isoformat()
    rows.append({"id": f"{int(time.time() * 1000)}", "channel": channel if channel in CHANNELS else "Other", "who": str(who or "").strip()[:80],
                 "note": str(note or "").strip()[:400], "date": date})
    save_data()


def delete_other(oid):
    rows = other_list()
    rows[:] = [r for r in rows if r.get("id") != str(oid)]
    save_data()


def history():
    return data().setdefault("outreach", [])


def sent_today():
    today = datetime.date.today().isoformat()
    return sum(1 for r in history() if r.get("how") == "sent" and str(r.get("date", ""))[:10] == today)


def already(addr):
    a = str(addr or "").strip().lower()
    return next((r for r in history() if str(r.get("email", "")).lower() == a), None)


DEFAULT_PREFS = {"tone": "Warm and friendly", "length": "Medium", "role": "", "include": "", "avoid": "", "subject": "", "opt_out": True}
TONES = ["Warm and friendly", "Professional and formal", "Short and direct", "Enthusiastic"]
LENGTHS = {"Short": "60 to 80 words", "Medium": "90 to 130 words", "Detailed": "150 to 190 words"}


def get_prefs():
    saved = (data().get("state") or {}).get("reach_prefs") or {}
    return {**DEFAULT_PREFS, **{k: saved[k] for k in DEFAULT_PREFS if k in saved}}


def subject_for(company="", prefs=None):
    custom = str((prefs or {}).get("subject") or "").strip()
    if custom:
        return custom.replace("{company}", company or "your company")[:150]
    role = str((prefs or {}).get("role") or "").strip()
    return f"Application for {role or 'Marketing / Content Opportunities'} \u2013 {OWNER}"[:150]


def template(db, company, text="", prefs=None):
    """A plain mail that works with no AI, from her resume."""
    try:
        prof = resume_profile(resume_text(db) or "")
    except Exception:
        prof = {"skills": [], "years": None}
    skills = ", ".join(s for s in prof.get("skills", [])[:6])
    yrs = prof.get("years")
    role = str((prefs or {}).get("role") or "").strip()
    exp = f" I have around {yrs} years of experience in marketing." if yrs else ""
    mine = f" My experience includes {skills}." if skills else ""
    who = f" at {company}" if company else ""
    kind = f" as a {role}" if role else ""
    return (f"Dear Hiring Team,\n\nI'm writing to express my interest in opportunities{who}{kind}.{exp}{mine}\n\n"
            f"I've attached my resume for your consideration. I'd be happy to discuss any suitable opportunities.\n\nRegards,\n{OWNER}")


FOOT = "\n\nIf this is not relevant for you, just let me know and I won't write again."


async def write_mail(db, company, site_text, prefs=None):
    prefs = {**DEFAULT_PREFS, **(prefs or get_prefs())}
    extra = ""
    if prefs["role"].strip():
        extra += f"She is looking for: {prefs['role'].strip()}. "
    if prefs["include"].strip():
        extra += f"Make sure the mail includes: {prefs['include'].strip()}. "
    if prefs["avoid"].strip():
        extra += f"Do NOT include or mention: {prefs['avoid'].strip()}. "
    prompt = (f"Write an email from a marketing professional named {OWNER} to the hiring team at {company}. "
              "She is introducing herself and her skills and asking whether they have, or will have, suitable openings; her resume is attached. "
              f"Tone: {prefs['tone']}. Length: {LENGTHS.get(prefs['length'], LENGTHS['Medium'])}. {extra}"
              "Start with 'Dear Hiring Team,'. Use ONLY facts from her resume; never invent numbers, employers or skills. "
              "Mention one specific thing about the company taken from the company text, and only if the text really says it. "
              f"End with 'Regards,' then '{OWNER}'. Output only the email body, no subject, no preamble.\n\n"
              f"COMPANY TEXT:\n{site_text[:1800]}\n\nHER RESUME:\n{resume_text(db)[:6000]}\n")
    try:
        body = (await ai_complete(db, prompt, 600)).strip()
        if len(body) < 60 or "dear" not in body.lower()[:30]:
            raise ValueError("odd answer")
    except Exception:
        body = template(db, company, site_text, prefs)
    return {"subject": subject_for(company, prefs), "body": body.rstrip() + (FOOT if prefs["opt_out"] else "")}


def build_message(addr, to, subject, body, resume: Path):
    msg = email.message.EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = f"{OWNER} <{addr}>", to, subject
    msg.set_content(body)
    if resume and resume.is_file():
        sub = "pdf" if resume.suffix.lower() == ".pdf" else "octet-stream"
        msg.add_attachment(resume.read_bytes(), maintype="application", subtype=sub, filename=resume.name)
    return msg


def _smtp(addr, pw, msg):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(addr, pw)
        s.send_message(msg)


def _draft(addr, pw, msg):
    m = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    try:
        m.login(addr, pw)
        typ, _ = m.append("[Gmail]/Drafts", "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        if typ != "OK":
            raise RuntimeError("Gmail did not accept the draft")
    finally:
        try:
            m.logout()
        except Exception:
            pass


def record(to, company, site, subject, how):
    history().append({"email": to.lower(), "company": company, "site": site, "subject": subject, "how": how,
                      "date": datetime.datetime.now().isoformat(timespec="seconds")})
    save_data()


def friendly(e):
    s = str(e)
    if "Application-specific" in s or "535" in s or "AUTHENTICATIONFAILED" in s.upper():
        return "Gmail did not accept the app password. Check it in Settings, Job email."
    return s[:160]
