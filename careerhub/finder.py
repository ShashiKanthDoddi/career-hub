"""finder module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
from urllib.parse import unquote
import asyncio
import datetime
import html
import re
from .answers import Answers
from .bridge import StopRun, UI, check_stop, log
from .records import save_found, seen_links
from .resume import resume_info
from .state import FIND_DIAG, PW
from .store import ProfileError, save_app_state
from .textutil import days_ago, has_phrase, norm, norm_link, split_list, strip_tags


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


STRONG_TITLE_WORDS = ["marketing", "brand", "growth", "seo", "sem", "content", "social media", "communications",
                      "public relations", "campaign", "crm", "influencer", "copywriter", "community",
                      "demand generation", "lead generation", "lifecycle", "user acquisition", "media planner"]


TECH_WORDS = ["engineer", "developer", "sde", "devops", "scientist", "architect", "accountant", "legal counsel"]


CITY_ALIASES = {"bengaluru": ["bangalore", "bengaluru"], "bangalore": ["bangalore", "bengaluru"],
                "gurugram": ["gurgaon", "gurugram"], "gurgaon": ["gurgaon", "gurugram"],
                "mumbai": ["mumbai", "bombay"], "delhi": ["delhi", "ncr"], "new delhi": ["delhi", "ncr"],
                "noida": ["noida", "ncr"], "chennai": ["chennai", "madras"],
                "remote": ["remote", "anywhere", "work from home", "wfh"]}


ATS_PATTERNS = [
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)"),
    ("greenhouse", r"(?:job-)?boards(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("workday", r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
]


BAD_SLUGS = {"embed", "v1", "jobs", "js", "api", "static", "assets", "wday", "cxs", "en-us", "search", "careers"}


def boards_in(text):
    """Finds hiring-system job boards mentioned in a URL or a web page."""
    text = unquote(html.unescape(text or ""))
    found = {}
    for ats, pat in ATS_PATTERNS:
        for m in re.finditer(pat, text):
            if ats == "workday":
                tenant, wd, site = m.groups()
                if site.lower() in BAD_SLUGS:
                    continue
                key = ("workday", tenant.lower(), wd.lower(), site)
            else:
                slug = m.group(1).strip(".")
                if slug.lower() in BAD_SLUGS:
                    continue
                key = (ats, slug)
            found[key] = True
    return list(found)


def board_label(b):
    name = b[1].replace("-", " ").replace("_", " ").title()
    return f"{name} ({b[0].title()})"


def seniority_excludes(years):
    if years is None:
        return ["intern", "internship", "vice president", "chief", "cmo"]
    if years < 2:
        return ["senior", "sr", "lead", "head", "director", "vice president", "vp", "chief", "principal"]
    if years <= 5:
        return ["intern", "internship", "trainee", "head", "director", "vice president", "vp", "chief", "principal"]
    if years <= 10:
        return ["intern", "internship", "trainee", "junior", "vice president", "chief"]
    return ["intern", "internship", "trainee", "junior", "associate"]


def location_ok(loc, wanted):
    if not wanted:
        return True
    l = (loc or "").lower().strip()
    if not l or l in ("india", "multiple locations", "various locations", "various"):
        return True
    return any(alias in l for w in wanted for alias in CITY_ALIASES.get(w, [w]))


def relevant_title(title, prof):
    t = norm(title)
    if any(has_phrase(w, t) for w in TECH_WORDS) and "marketing" not in t:
        return False
    return any(has_phrase(w, t) for w in STRONG_TITLE_WORDS + prof["roles"])


def match_score(title, desc, prof):
    t = norm(title)
    if any(has_phrase(r, t) for r in prof["roles"] if r != "marketing"):
        s = 55
    elif "marketing" in t:
        s = 40
    else:
        s = 25
    d = norm(desc)
    if d and prof["skills"]:
        s += min(45, 6 * sum(1 for k in prof["skills"] if has_phrase(k, d)))
    elif not d:
        s += 15
    return min(s, 100)


async def get_json(req, url, data=None):
    try:
        if data is None:
            r = await req.get(url, timeout=25000)
        else:
            r = await req.post(url, data=data, timeout=25000,
                               headers={"Content-Type": "application/json", "Accept": "application/json"})
        if r.ok:
            return await r.json()
    except Exception:
        pass
    return None


async def fetch_board(req, b, terms):
    """Returns a list of jobs: dict(company, title, location, link, desc, age)."""
    out, ats = [], b[0]
    company = b[1].replace("-", " ").replace("_", " ").title()
    if ats == "greenhouse":
        d = await get_json(req, f"https://boards-api.greenhouse.io/v1/boards/{b[1]}/jobs?content=true") or {}
        for j in d.get("jobs", []):
            out.append(dict(company=company, title=j.get("title", ""), location=(j.get("location") or {}).get("name", ""),
                            link=j.get("absolute_url", ""), desc=strip_tags(j.get("content")), age=days_ago(j.get("updated_at"))))
    elif ats == "lever":
        d = await get_json(req, f"https://api.lever.co/v0/postings/{b[1]}?mode=json") or []
        for j in d if isinstance(d, list) else []:
            cat = j.get("categories") or {}
            out.append(dict(company=company, title=j.get("text", ""), location=cat.get("location", ""),
                            link=j.get("hostedUrl", ""), desc=j.get("descriptionPlain", "") + " " +
                            " ".join(strip_tags(x.get("content")) for x in j.get("lists", []) if isinstance(x, dict)),
                            age=days_ago(j.get("createdAt"))))
    elif ats == "ashby":
        d = await get_json(req, f"https://api.ashbyhq.com/posting-api/job-board/{b[1]}") or {}
        for j in d.get("jobs", []):
            if j.get("isListed") is False:
                continue
            loc = j.get("location", "") + (" remote" if j.get("isRemote") else "")
            out.append(dict(company=company, title=j.get("title", ""), location=loc,
                            link=j.get("jobUrl") or j.get("applyUrl", ""), desc=j.get("descriptionPlain", ""),
                            age=days_ago(j.get("publishedAt"))))
    elif ats == "smartrecruiters":
        seen = set()
        for term in terms:
            d = await get_json(req, f"https://api.smartrecruiters.com/v1/companies/{b[1]}/postings"
                                    f"?q={quote(term)}&limit=100") or {}
            for j in d.get("content", []):
                if j.get("id") in seen:
                    continue
                seen.add(j.get("id"))
                l = j.get("location") or {}
                loc = ", ".join(x for x in [l.get("city", ""), l.get("country", "")] if x) + (" remote" if l.get("remote") else "")
                out.append(dict(company=company, title=j.get("name", ""), location=loc,
                                link=f"https://jobs.smartrecruiters.com/{b[1]}/{j.get('id')}", desc="",
                                age=days_ago(j.get("releasedDate"))))
    elif ats == "workday":
        _, tenant, wd, site = b
        host = f"https://{tenant}.{wd}.myworkdayjobs.com"
        seen = set()
        for term in terms:
            for offset in range(0, 100, 20):
                d = await get_json(req, f"{host}/wday/cxs/{tenant}/{site}/jobs",
                                   {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term})
                posts = (d or {}).get("jobPostings", [])
                for j in posts:
                    path = j.get("externalPath", "")
                    if not path or path in seen:
                        continue
                    seen.add(path)
                    out.append(dict(company=company, title=j.get("title", ""), location=j.get("locationsText", ""),
                                    link=f"{host}/en-US/{site}{path}", desc="", age=days_ago(j.get("postedOn"))))
                if len(posts) < 20:
                    break
    return out


async def web_search(req, query):
    """Free web search (DuckDuckGo, then Bing). Returns raw page text."""
    text = ""
    for url in (f"https://html.duckduckgo.com/html/?q={quote(query)}",
                f"https://www.bing.com/search?q={quote(query)}&count=30"):
        try:
            r = await req.get(url, headers={"User-Agent": UA}, timeout=20000)
            text += " " + await r.text()
        except Exception:
            pass
        await asyncio.sleep(1)
    return text


async def resolve_name(req, name):
    slugs = list(dict.fromkeys([re.sub(r"[^a-z0-9]", "", name.lower()),
                                re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")]))
    for s in slugs:
        if await get_json(req, f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs"):
            return [("greenhouse", s)]
        d = await get_json(req, f"https://api.lever.co/v0/postings/{s}?mode=json")
        if isinstance(d, list) and d:
            return [("lever", s)]
        if await get_json(req, f"https://api.ashbyhq.com/posting-api/job-board/{s}"):
            return [("ashby", s)]
    key = slugs[0][:5]
    found = boards_in(await web_search(req, f"{name} careers jobs apply"))
    return [b for b in found if key in re.sub(r"[^a-z0-9]", "", b[1].lower())]


async def resolve_url(req, p, url):
    found = boards_in(url)
    if found:
        return found
    try:
        r = await req.get(url, headers={"User-Agent": UA}, timeout=25000)
        found = boards_in(await r.text())
    except Exception:
        found = []
    if found:
        return found
    try:                                                     # page built with JavaScript: open it for real
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=45000)
        await page.wait_for_timeout(4000)
        bits = [page.url, await page.content()] + [f.url for f in page.frames]
        await browser.close()
        return boards_in(" ".join(bits))
    except Exception:
        return []


async def discover(req, prof, locations):
    cities = [c for c in locations if c != "remote"][:2] or ["India"]
    queries = []
    for role in prof["roles"][:2]:
        for site in ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com", "myworkdayjobs.com"):
            queries.append(f'site:{site} "{role}" {cities[0]}')
    if len(cities) > 1:
        queries += [f'site:myworkdayjobs.com "{prof["roles"][0]}" {cities[1]}',
                    f'site:boards.greenhouse.io "{prof["roles"][0]}" {cities[1]}']
    found = {}
    for i, q in enumerate(queries, 1):
        log(f"   searching the web ({i}/{len(queries)})...", end="\r")
        for b in boards_in(await web_search(req, q)):
            found[b] = True
    log(" " * 50, end="\r")
    return list(found)[:30]


async def search_jobs(p, db, roles, tokens):
    prof = resume_info(db)
    if prof is None:
        return []
    if roles:
        prof["roles"] = roles
    st = db.settings
    locations = split_list(st.get("job_locations"))
    excludes = split_list(st.get("exclude_words")) + seniority_excludes(prof["years"])
    min_score = int(st.get("minimum_match") or 50)
    max_age = int(st.get("max_job_age_days") or 30)

    jobs = []
    req = await p.request.new_context(extra_http_headers={"User-Agent": UA})
    try:
        boards = {}
        for tok in tokens or ["auto"]:
            check_stop()
            if tok.lower() == "auto":
                log("🔎 Searching the internet for companies hiring for your profile…")
                found = await discover(req, prof, locations)
                log(f"   Found {len(found)} company career site(s).")
            elif tok.lower().startswith("http") or ("." in tok and " " not in tok):
                url = tok if tok.lower().startswith("http") else "https://" + tok
                log(f"🔎 Reading {url} …")
                found = await resolve_url(req, p, url)
            else:
                log(f"🔎 Looking up {tok} …")
                found = await resolve_name(req, tok)
            if not found:
                log(f"   ⚠  Couldn't find a job list for '{tok}'. Try pasting their careers-page link instead.")
            for b in found:
                boards[b] = True
        for i, b in enumerate(boards, 1):
            check_stop()
            UI.status(detail=f"Checking {board_label(b)} ({i}/{len(boards)})")
            try:
                got = await fetch_board(req, b, prof["roles"])
            except Exception:
                got = []
            log(f"   {board_label(b)}: {len(got)} jobs")
            jobs += got
    finally:
        await req.dispose()

    seen = seen_links()
    matches, done = [], set()
    diag = {"sites": len(boards), "fetched": len(jobs), "seen": 0, "title": 0, "city": 0, "old": 0, "match": 0}
    for j in jobs:
        t = norm(j["title"])
        if not j["link"] or norm_link(j["link"]) in seen or norm_link(j["link"]) in done:
            diag["seen"] += 1
            continue
        if not relevant_title(j["title"], prof) or any(has_phrase(x, t) for x in excludes):
            diag["title"] += 1
            continue
        if not location_ok(j["location"], locations):
            diag["city"] += 1
            continue
        if j["age"] is not None and j["age"] > max_age:
            diag["old"] += 1
            continue
        j["score"] = match_score(j["title"], j["desc"], prof)
        if j["score"] >= min_score:
            matches.append(j)
            done.add(norm_link(j["link"]))
        else:
            diag["match"] += 1
    matches.sort(key=lambda j: (-j["score"], j["age"] if j["age"] is not None else 99))
    if matches:
        save_found(matches)
    FIND_DIAG.clear()
    FIND_DIAG.update(diag)
    save_app_state(find_diag=diag)
    log(f"✨ {len(matches)} new matching job(s). Checked {diag['sites']} career sites, {diag['fetched']} jobs; skipped "
        f"{diag['seen']} already seen, {diag['title']} other roles, {diag['city']} other cities, {diag['old']} too old, "
        f"{diag['match']} below your minimum match.")
    return matches


async def run_find(roles, tokens):
    UI.busy, UI.stop = True, False
    save_app_state(last_find=datetime.datetime.now().isoformat(timespec="seconds"),
                   find_roles=", ".join(roles), find_tokens=tokens)
    jobs = []
    await UI.emit({"type": "run_start", "what": "find", "total": 0})
    try:
        db = Answers()
        found = await search_jobs(PW["p"], db, roles, tokens)
        jobs = [{"score": j["score"], "title": j["title"], "company": j["company"], "location": j["location"],
                 "age": j["age"], "link": j["link"]} for j in found[:100]]
    except StopRun:
        log("⏹ Stopped.")
    except ProfileError as e:
        log(f"⚠  {e}")
    except Exception as e:
        log(f"⚠  Unexpected problem: {str(e).splitlines()[0][:200]}")
    finally:
        UI.busy, UI.stop = False, False
        await UI.emit({"type": "run_end", "what": "find", "jobs": jobs, "diag": dict(FIND_DIAG)})
