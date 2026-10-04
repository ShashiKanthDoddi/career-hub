"""resume module of Career Hub. See MAP.md for what lives where."""
import re
from .bridge import log
from .config import BASE
from .state import CURRENT_JOB, RESUME_CACHE
from .store import resolve_path
from .textutil import has_phrase, norm, split_list


def resume_for_job(db):
    """Second / third resume when the job title matches their keywords."""
    title = norm(CURRENT_JOB.get("title", ""))
    for i in (2, 3):
        f = str(db.settings.get(f"resume_{i}_file") or "").strip()
        kws = split_list(db.settings.get(f"resume_{i}_keywords"))
        if f and kws and any(has_phrase(k, title) for k in kws) and resolve_path(f).is_file():
            return f
    return None


def resume_text(db):
    if RESUME_CACHE["text"] is None:
        RESUME_CACHE["text"] = read_resume(db) or ""
    return RESUME_CACHE["text"]


MKT_SKILLS = [
    "seo", "sem", "ppc", "google ads", "meta ads", "facebook ads", "instagram ads", "linkedin ads", "youtube ads",
    "performance marketing", "digital marketing", "content marketing", "content strategy", "social media",
    "brand management", "branding", "brand strategy", "campaign management", "email marketing", "crm",
    "hubspot", "salesforce", "marketo", "mailchimp", "moengage", "clevertap", "webengage", "google analytics",
    "ga4", "google tag manager", "semrush", "ahrefs", "canva", "copywriting", "influencer marketing",
    "affiliate marketing", "d2c", "ecommerce", "e commerce", "amazon", "flipkart", "b2b", "b2c", "saas",
    "product marketing", "growth marketing", "lead generation", "demand generation", "market research",
    "consumer insights", "public relations", "communications", "events", "media planning", "media buying",
    "atl", "btl", "trade marketing", "fmcg", "retail", "a b testing", "conversion rate", "cro",
    "marketing automation", "wordpress", "shopify", "retention", "loyalty", "community", "video marketing",
    "adobe", "photoshop", "figma", "excel", "tableau", "looker", "power bi", "sql", "go to market", "gtm",
    "positioning", "partnerships", "programmatic", "app marketing", "user acquisition", "aso", "lifecycle",
]


ROLE_PHRASES = [
    "performance marketing", "digital marketing", "product marketing", "brand marketing", "brand manager",
    "content marketing", "social media", "growth marketing", "email marketing", "influencer marketing",
    "trade marketing", "marketing communications", "public relations", "seo", "crm", "marketing manager",
    "marketing executive", "marketing specialist", "marketing associate", "content writer", "copywriter",
    "growth", "brand", "marketing",
]


def read_resume(db):
    path = None
    for pat, p in db.files.items():
        if "resume" in pat and p:
            path = resolve_path(p)
    path = path or BASE / "Resume.pdf"
    if not path.is_file():
        log(f"\n⚠  I can't find your resume ({path.name}). Drop it into Profile → Files.")
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        log("\n⚠  One part is missing. Double-click '1 - Setup (run once)' again, then retry.")
        return ""
    try:
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception as e:
        log(f"\n⚠  Couldn't read the resume PDF ({e}). Try saving it again as PDF from Word/Google Docs.")
        return ""


def resume_profile(text):
    t = norm(text)
    skills = [s for s in MKT_SKILLS if has_phrase(s, t)]
    roles = [r for r in ROLE_PHRASES if has_phrase(r, t)]
    roles = [r for r in roles if r not in ("growth", "brand", "marketing")][:3] or ["marketing"]
    yrs = [int(m) for m in re.findall(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", text.lower()) if 0 < int(m) < 40]
    return {"skills": skills, "roles": roles, "years": max(yrs) if yrs else None}


def resume_info(db):
    text = read_resume(db)
    if not text:
        return None
    prof = resume_profile(text)
    if not prof["years"]:                                 # resume shows dates, not "N years": use the profile
        exp = db.fields.get("total (work |professional )?experience|total years") or ""
        m = re.search(r"\d+", str(exp))
        prof["years"] = int(m.group(0)) if m else None
    prof["locations"] = split_list(db.settings.get("job_locations"))
    return prof
