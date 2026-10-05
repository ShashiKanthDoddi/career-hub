"""research: a short brief about a company for interview prep. Wikipedia gives the facts; a free AI (no key) puts them
in plain words. Only the company name and public text leave the computer, never her resume. Briefs are kept 30 days in
the data file's state ('research')."""
import datetime
import re
from urllib.parse import urlencode
from .ai import free_complete
from .state import PW
from .store import data, save_data
from .textutil import norm

WIKI = "https://en.wikipedia.org/w/api.php"
KEEP_DAYS = 30
KEEP_BRIEFS = 40
SUFFIX = {"inc", "ltd", "limited", "pvt", "private", "llp", "llc", "corp", "corporation", "co", "technologies", "technology",
          "india", "solutions", "services", "the"}
BUSINESS = re.compile(r"\b(company|brand|firm|startup|start-up|platform|agency|corporation|business|e-commerce|retailer|"
                      r"manufacturer|conglomerate|multinational|subsidiary|provider|network|publisher|bank|chain)\b", re.I)


def pick_title(company, hits):
    """The Wikipedia title that is this company, or ''. Every main word of the name must be in the title, and the
    first lines must describe a business (so 'Mint' the plant or a person with the same name is not taken)."""
    words = [w for w in norm(company).split() if w not in SUFFIX]
    for h in hits:
        title = norm(h.get("title", ""))
        if words and all(w in title.split() for w in words) and BUSINESS.search(re.sub(r"<[^>]+>", " ", h.get("snippet") or h.get("extract", "")[:400])):
            return h["title"]
    return ""


def clean_brief(text):
    """Keeps only the three headings and their '- ' lines, so a chatty reply or an advert line is dropped."""
    heads = ("what they do", "marketing angle", "smart questions")
    out = []
    for l in (text or "").splitlines():
        l = l.strip().strip("*#").strip()
        if l.lower().startswith(heads):
            out.append(l.rstrip(":"))
        elif re.match(r"^[-•*]\s+\S", l) and out:
            out.append("- " + re.sub(r"^[-•*]\s+", "", l).replace("**", ""))
    return "\n".join(out) if sum(1 for l in out if l.startswith("- ")) >= 3 else ""


async def _wiki_facts(company):
    """(title, intro text) from Wikipedia, or ('', ''). One request: the search results come with their first lines."""
    req = await PW["p"].request.new_context(extra_http_headers={"User-Agent": "CareerHub/1.0 (personal job search app)"})
    try:
        r = await req.get(WIKI + "?" + urlencode({"action": "query", "generator": "search", "gsrsearch": company, "gsrlimit": 5, "prop": "extracts",
                                                  "exintro": 1, "explaintext": 1, "exlimit": "max", "format": "json"}), timeout=20000)
        pages = ((await r.json()).get("query") or {}).get("pages", {}) if r.ok else {}
        hits = sorted(pages.values(), key=lambda h: h.get("index", 99))
        title = pick_title(company, hits)
        text = next((h.get("extract", "") for h in hits if h["title"] == title), "")
        return (title, text[:1800]) if title and "may refer to" not in text[:200] else ("", "")
    finally:
        await req.dispose()


async def company_brief(company, refresh=False):
    """{'text', 'source', 'date'} for the Home card. Raises RuntimeError with a plain message when nothing is found."""
    company = str(company or "").strip()
    if not company:
        raise RuntimeError("No company name for this interview.")
    cache = data()["state"].setdefault("research", {})
    key = norm(company)
    hit = cache.get(key)
    if hit and not refresh and (datetime.date.today() - datetime.date.fromisoformat(hit["date"])).days < KEEP_DAYS:
        return hit
    title, facts = await _wiki_facts(company)
    prompt = (f"You are helping a marketing professional prepare for a job interview at {company}.\n"
              + (f"FACTS (from Wikipedia, {title}):\n{facts}\n\nUse ONLY these facts. " if facts else
                 "You have no source text. Use only what you are sure about and start any uncertain line with 'Not sure:'. ")
              + "Never invent numbers, names, campaigns or dates. Reply in plain text with exactly three headings, each on its own line, "
                "followed by 3 short lines starting with '- ':\nWhat they do\nMarketing angle to mention\nSmart questions to ask\nNo other text.")
    text = ""
    try:
        text = clean_brief(await free_complete(prompt))
    except Exception:
        pass
    by_ai = bool(text)
    if not text and facts:                                   # the AI failed: the plain facts are still useful
        text = "What they do\n- " + "\n- ".join(s.strip() for s in re.split(r"(?<=[.!?])\s+", facts)[:3] if s.strip())
    if not text:
        raise RuntimeError(f"Could not get anything about {company} right now. Try again later.")
    out = {"text": text, "source": f"Wikipedia: {title}" if facts else "AI general knowledge, check it on their website",
           "date": datetime.date.today().isoformat(), "ai": by_ai}
    cache[key] = out
    for old in sorted(cache, key=lambda k: cache[k]["date"])[:-KEEP_BRIEFS]:
        del cache[old]
    save_data()
    return out
