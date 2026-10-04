"""jobsites module of Career Hub: LinkedIn / Indeed / Naukri safety rules and job-alert links. See MAP.md."""
from urllib.parse import parse_qs, urlparse
import asyncio
import datetime
import random
import re
from .bridge import check_stop, log
from .records import tracker_rows
from .store import data, save_data

SITES = {"linkedin.com": "LinkedIn", "indeed.com": "Indeed", "naukri.com": "Naukri"}
DEFAULT_DAILY_LIMIT = 10
PACE_SECONDS = (25, 70)            # random wait between two jobs on these sites
CHALLENGE_RE = re.compile(r"captcha|are you a (robot|human)|verify you.re (a )?human|unusual (activity|traffic)|"
                          r"security (check|verification)|confirm you.re not a robot|temporarily (restricted|blocked)|"
                          r"account (has been )?restricted|access denied|too many requests|checking your browser", re.I)
ALERT_SENDERS = ("linkedin.com", "indeed.com", "naukri.com", "naukrimail", "indeedemail")


def site_of(url):
    host = urlparse(url or "").netloc.lower()
    return next((name for dom, name in SITES.items() if host == dom or host.endswith("." + dom)), None)


def daily_limit():
    try:
        return max(1, int(data()["profile"]["settings"].get("jobsite_daily_limit") or DEFAULT_DAILY_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_LIMIT


def done_today(site):
    """Applications on this site today (submitted or started), counted from the tracker."""
    today = datetime.date.today().isoformat()
    return sum(1 for r in tracker_rows() if (r.get("Date") or "").startswith(today) and site_of(r.get("Link")) == site
               and not (r.get("Status") or "").startswith(("Skipped", "Error")))


def cooling_off(site):
    """True when a check from this site stopped us earlier today."""
    return data()["state"].get("jobsite_pause", {}).get(site) == datetime.date.today().isoformat()


def start_cooling_off(site):
    st = data()["state"]
    st.setdefault("jobsite_pause", {})[site] = datetime.date.today().isoformat()
    save_data()


def allowed(site):
    """(ok, reason). Reason is plain words for the activity log."""
    if cooling_off(site):
        return False, f"{site} showed a security check earlier today, so the app is resting from it until tomorrow."
    n, cap = done_today(site), daily_limit()
    if n >= cap:
        return False, f"Daily limit reached for {site} ({n} of {cap}). This keeps the account safe. Try again tomorrow."
    return True, ""


async def pace(site):
    """Human-speed pause before the next job on the same site. Stop button works during the wait."""
    secs = random.randint(*PACE_SECONDS)
    log(f"⏳ Waiting {secs} seconds before the next {site} job (keeps the account safe).")
    for _ in range(secs):
        check_stop()
        await asyncio.sleep(1)


async def challenged(page):
    """True when the page shows a robot check or a 'we noticed unusual activity' wall."""
    try:
        text = (await page.title()) + " " + (await page.inner_text("body", timeout=3000))[:1500]
    except Exception:
        return False
    return bool(CHALLENGE_RE.search(text))


# ---- job links inside "job alert" emails ----

def clean_job_link(url):
    """Short, tracking-free job link, or None when the link isn't a single job."""
    u = urlparse(url)
    host, path, q = u.netloc.lower(), u.path, parse_qs(u.query)
    if host.endswith("linkedin.com"):
        m = re.search(r"/jobs/view/(?:[^/?]*-)?(\d{6,})", path)
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}" if m else None
    if host.endswith("indeed.com"):
        jk = (q.get("jk") or q.get("vjk") or [""])[0]
        return f"https://{host}/viewjob?jk={jk}" if jk and re.fullmatch(r"[0-9a-f]{8,}", jk) else None
    if host.endswith("naukri.com"):
        return f"https://www.naukri.com{path}" if "job-listings" in path else None
    return None


def alert_jobs(htm):
    """[(link, title)] from the HTML of a job-alert email."""
    out, seen = [], set()
    for href, inner in re.findall(r'(?is)<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', htm or ""):
        link = clean_job_link(re.sub(r"&amp;", "&", href))
        title = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", inner)).strip()
        if link and link not in seen and 4 <= len(title) <= 120 and not re.search(r"(?i)^(view|apply|see)\b", title):
            seen.add(link)
            out.append((link, title))
    return out
