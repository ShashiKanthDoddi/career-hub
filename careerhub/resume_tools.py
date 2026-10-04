"""resume_tools: the Resume page. A plain-words ATS check, keyword match against one job, skills to build for her
target roles (with free courses), and her resume versions. Pure functions on text, so selftest can check them."""
import re
from .resume import MKT_SKILLS
from .textutil import has_phrase, norm, split_list

# ---- ATS check ----

ACTION_VERBS = ("led", "managed", "grew", "launched", "built", "created", "drove", "increased", "reduced", "planned",
                "ran", "owned", "delivered", "developed", "improved", "optimised", "optimized", "executed", "designed",
                "achieved", "scaled", "generated", "spearheaded", "established", "coordinated", "analysed", "analyzed",
                "boosted", "cut", "secured", "negotiated", "introduced", "headed", "partnered", "wrote", "produced")
SECTION_RE = {"experience": r"(?im)^\s*(work |professional )?(experience|employment|work history|career history)\b",
              "education": r"(?im)^\s*(education|academic|qualifications?)\b",
              "skills": r"(?im)^\s*(key |core |technical )?(skills|competencies|tools|expertise)\b",
              "summary": r"(?im)^\s*(professional )?(summary|profile|about me|objective|career objective)\b"}


def ats_check(text):
    """{'score': 0-100, 'words': n, 'checks': [{'ok', 'title', 'tip', 'weight'}]}: what application systems need to read
    a resume well. Each check has a plain-words tip for when it fails."""
    text = text or ""
    words = len(re.findall(r"[A-Za-z]{2,}", text))
    lines = [l.strip(" •·-–*\t") for l in text.splitlines() if l.strip()]
    t = norm(text.lower())          # lower first: norm splits camelCase, and "HubSpot" must stay one word
    numbers = sum(1 for l in lines if re.search(r"\d+\s*(%|x\b|k\b|lakh|crore|cr\b|mn\b|million|users|leads|followers)|[₹$]\s*\d|\d+%", l, re.I))
    verbs = sum(1 for l in lines if l.split(" ", 1)[0].lower().rstrip(",.:") in ACTION_VERBS)
    skills = [s for s in MKT_SKILLS if has_phrase(s, t)]
    years = set(re.findall(r"\b(?:19|20)\d\d\b", text))
    checks = [
        (words >= 150, 25, "Readable by job sites",
         "Very little text came out of this file. It may be a picture or a scan, which application systems can't read. "
         "Save it again as PDF from Word or Google Docs."),
        (bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)), 6, "Email address", "Add your email address at the top."),
        (bool(re.search(r"(\+?\d[\d ()-]{8,}\d)", text)), 6, "Phone number", "Add your phone number at the top."),
        (bool(re.search(r"linkedin\.com/", text, re.I)), 4, "LinkedIn link", "Add your LinkedIn profile link at the top."),
        (bool(re.search(SECTION_RE["experience"], text)), 8, "Work experience heading",
         "Use a clear heading like \"Work experience\" so systems find your jobs."),
        (bool(re.search(SECTION_RE["education"], text)), 5, "Education heading", "Add a heading called \"Education\"."),
        (bool(re.search(SECTION_RE["skills"], text)), 6, "Skills heading",
         "Add a \"Skills\" section listing your tools and skills (for example Google Ads, GA4, HubSpot)."),
        (bool(re.search(SECTION_RE["summary"], text)), 4, "Short summary at the top",
         "Add 2 or 3 lines at the top that say who you are and what you're great at."),
        (300 <= words <= 1100, 8, "Length",
         "It is quite short: add results and tools for each job." if words < 300 else "It is long: aim for 1 to 2 pages."),
        (numbers >= 5, 10, "Numbers in your results",
         f"Only {numbers} line{'s' if numbers != 1 else ''} with numbers. Add results like \"grew leads by 40%\" or \"managed a ₹20 lakh budget\"."),
        (verbs >= 6, 6, "Action words",
         "Start bullet points with action words like Led, Grew, Launched, Managed."),
        (len(skills) >= 8, 8, "Marketing keywords",
         f"Only {len(skills)} marketing keywords found. Name the tools and channels you used (SEO, Meta Ads, GA4, CRM…)."),
        (len(years) >= 2, 4, "Dates for each job", "Add start and end dates (month and year) to every job."),
    ]
    score = sum(w for ok, w, _, _ in checks if ok)
    return {"score": round(100 * score / sum(w for _, w, _, _ in checks)), "words": words, "skills": skills,
            "checks": [{"ok": ok, "title": title, "tip": "" if ok else tip, "weight": w} for ok, w, title, tip in checks]}


# ---- skills to build for her target roles (#13) ----

COURSES = {
    "google_ads": ("Google Ads certifications (free)", "https://skillshop.withgoogle.com/"),
    "analytics": ("Google Analytics certification (free)", "https://skillshop.withgoogle.com/"),
    "meta": ("Meta Blueprint courses (free)", "https://www.facebook.com/business/learn"),
    "seo": ("SEO training, HubSpot Academy (free)", "https://academy.hubspot.com/courses/seo-training"),
    "semrush": ("Semrush Academy (free)", "https://www.semrush.com/academy/"),
    "content": ("Content marketing, HubSpot Academy (free)", "https://academy.hubspot.com/courses/content-marketing"),
    "social": ("Social media marketing, HubSpot Academy (free)", "https://academy.hubspot.com/courses/social-media"),
    "email": ("Email marketing, HubSpot Academy (free)", "https://academy.hubspot.com/courses/email-marketing"),
    "hubspot": ("HubSpot Academy courses (free)", "https://academy.hubspot.com/"),
}


def _coursera(q):
    return (f"{q.title()} courses on Coursera", "https://www.coursera.org/search?query=" + q.replace(" ", "%20"))


# role -> [(skill name, phrases that count as having it, course key or search words)]
ROLE_SKILLS = {
    "performance marketing": [("Google Ads", ["google ads", "sem", "ppc", "adwords"], "google_ads"),
                              ("Meta Ads", ["meta ads", "facebook ads", "instagram ads"], "meta"),
                              ("Google Analytics / GA4", ["google analytics", "ga4"], "analytics"),
                              ("A/B testing", ["a b testing", "ab testing", "split testing"], "a b testing"),
                              ("Conversion rate (CRO)", ["conversion rate", "cro"], "conversion rate optimization"),
                              ("Google Tag Manager", ["google tag manager", "gtm"], "analytics"),
                              ("Excel / Sheets", ["excel", "google sheets", "spreadsheets"], "excel"),
                              ("ROAS and budgets", ["roas", "cac", "cpa", "budget"], "digital marketing analytics")],
    "digital marketing": [("SEO", ["seo", "search engine optimization"], "seo"),
                          ("Google Ads", ["google ads", "sem", "ppc"], "google_ads"),
                          ("Meta Ads", ["meta ads", "facebook ads", "instagram ads"], "meta"),
                          ("Google Analytics / GA4", ["google analytics", "ga4"], "analytics"),
                          ("Email marketing", ["email marketing", "newsletter"], "email"),
                          ("Social media", ["social media"], "social"),
                          ("Content marketing", ["content marketing", "content strategy"], "content"),
                          ("Marketing automation", ["marketing automation", "hubspot", "marketo"], "hubspot")],
    "content marketing": [("Content strategy", ["content strategy", "content calendar"], "content"),
                          ("SEO writing", ["seo"], "seo"),
                          ("Copywriting", ["copywriting", "copy"], "copywriting"),
                          ("WordPress / CMS", ["wordpress", "cms", "webflow"], "wordpress"),
                          ("Video content", ["video marketing", "video", "reels", "youtube"], "video marketing"),
                          ("Google Analytics / GA4", ["google analytics", "ga4"], "analytics"),
                          ("Canva / design basics", ["canva", "figma", "photoshop"], "canva")],
    "social media": [("Social media strategy", ["social media"], "social"),
                     ("Meta Ads", ["meta ads", "facebook ads", "instagram ads"], "meta"),
                     ("Influencer marketing", ["influencer marketing", "influencer"], "influencer marketing"),
                     ("Community building", ["community"], "community management"),
                     ("Short video (Reels)", ["reels", "video marketing", "short form video"], "video marketing"),
                     ("Canva / design basics", ["canva", "figma", "photoshop"], "canva"),
                     ("Social analytics", ["analytics", "insights", "engagement rate"], "social media analytics")],
    "brand": [("Brand strategy", ["brand strategy", "brand management", "branding"], "brand management"),
              ("Positioning", ["positioning"], "brand positioning"),
              ("Market research", ["market research", "consumer insights"], "market research"),
              ("Media planning", ["media planning", "media buying"], "media planning"),
              ("ATL and BTL", ["atl", "btl", "integrated marketing"], "integrated marketing communications"),
              ("Go-to-market", ["go to market", "gtm", "product launch"], "go to market strategy"),
              ("PR and communications", ["public relations", "communications", "pr"], "public relations")],
    "product marketing": [("Go-to-market", ["go to market", "gtm", "product launch"], "go to market strategy"),
                          ("Positioning and messaging", ["positioning", "messaging"], "product positioning"),
                          ("Market and competitor research", ["market research", "competitive", "competitor"], "market research"),
                          ("Sales enablement", ["sales enablement", "sales collateral", "pitch deck"], "sales enablement"),
                          ("Customer insights", ["consumer insights", "customer insights", "user research"], "customer research"),
                          ("B2B / SaaS", ["b2b", "saas"], "b2b marketing")],
    "growth marketing": [("A/B testing", ["a b testing", "ab testing", "experiments"], "a b testing"),
                         ("Funnels and CRO", ["conversion rate", "cro", "funnel"], "conversion rate optimization"),
                         ("User acquisition", ["user acquisition", "app marketing", "aso"], "user acquisition"),
                         ("Retention and lifecycle", ["retention", "lifecycle", "loyalty"], "customer retention"),
                         ("SQL / data", ["sql", "looker", "tableau", "power bi"], "sql for marketers"),
                         ("Marketing automation", ["marketing automation", "moengage", "clevertap", "webengage", "hubspot"], "hubspot")],
    "email marketing": [("Email marketing", ["email marketing", "newsletter"], "email"),
                        ("CRM", ["crm", "salesforce", "hubspot"], "hubspot"),
                        ("Automation and journeys", ["marketing automation", "journeys", "workflows", "moengage", "clevertap"], "hubspot"),
                        ("Segmentation", ["segmentation", "segments"], "customer segmentation"),
                        ("Retention and lifecycle", ["retention", "lifecycle"], "customer retention"),
                        ("A/B testing", ["a b testing", "ab testing"], "a b testing")],
    "seo": [("Technical SEO", ["technical seo", "site audit", "core web vitals"], "seo"),
            ("Keyword research", ["keyword research", "semrush", "ahrefs"], "semrush"),
            ("Google Search Console", ["search console"], "google search console"),
            ("Link building", ["link building", "backlinks"], "link building"),
            ("Content for SEO", ["content strategy", "content marketing", "blog"], "content"),
            ("WordPress / CMS", ["wordpress", "cms"], "wordpress"),
            ("Google Analytics / GA4", ["google analytics", "ga4"], "analytics")],
}
ROLE_KEYS = {"performance": "performance marketing", "paid": "performance marketing", "digital": "digital marketing",
             "content": "content marketing", "copywriter": "content marketing", "writer": "content marketing",
             "social": "social media", "influencer": "social media", "brand": "brand", "product marketing": "product marketing",
             "growth": "growth marketing", "email": "email marketing", "crm": "email marketing", "lifecycle": "email marketing",
             "seo": "seo"}


def target_roles(roles_text, resume_roles):
    """Role keys for the skills section: from her Find jobs titles first, else what her resume says."""
    out = []
    for r in split_list(roles_text) + list(resume_roles or []):
        n = norm(r)
        key = next((v for k, v in ROLE_KEYS.items() if k in n), None)
        if key and key not in out:
            out.append(key)
    return out[:3] or ["digital marketing"]


def _course_for(word):
    for items in ROLE_SKILLS.values():
        for _, phrases, course in items:
            if word in [norm(p) for p in phrases]:
                return COURSES.get(course) or _coursera(course)
    return _coursera(word)


def job_skills(missing):
    """[{'skill', 'course', 'url'}]: a free course for each word the job asks for that her resume lacks."""
    return [{"skill": w, "course": c, "url": u} for w in missing for c, u in [_course_for(w)]]


def job_roles(job):
    """Role keys (as in ROLE_SKILLS) named at the top of a job text, at most two; [] if none is recognised."""
    n = norm((job or "")[:600].lower())
    out = []
    for k, v in ROLE_KEYS.items():
        if has_phrase(norm(k), n) and v not in out:
            out.append(v)
    return out[:2]


def skill_gaps(text, roles):
    """[{'role', 'have': [skill], 'missing': [{'skill', 'course', 'url'}]}] for each target role."""
    t = norm((text or "").lower())
    out = []
    for role in roles:
        have, missing = [], []
        for name, phrases, course in ROLE_SKILLS.get(role, []):
            if any(has_phrase(norm(p), t) for p in phrases):
                have.append(name)
            else:
                c_name, url = COURSES.get(course) or _coursera(course)
                missing.append({"skill": name, "course": c_name, "url": url})
        out.append({"role": role, "have": have, "missing": missing})
    return out


# ---- match against one job ----

def _vocab():
    words = set(MKT_SKILLS)
    for items in ROLE_SKILLS.values():
        for _, phrases, _ in items:
            words.update(norm(p) for p in phrases if len(p) > 2)
    return sorted(words, key=len, reverse=True)


VOCAB = _vocab()


def keyword_match(resume, job):
    """Keywords the job asks for: which are in the resume and which are missing. {'score', 'have', 'missing'}."""
    r, j = norm((resume or "").lower()), norm((job or "").lower())
    asked = []
    for w in VOCAB:
        if has_phrase(w, j) and not any(w in a for a in asked):     # "google ads" already covers "ads"
            asked.append(w)
    have = [w for w in asked if has_phrase(w, r)]
    missing = [w for w in asked if w not in have]
    return {"score": round(100 * len(have) / len(asked)) if asked else 0, "have": have, "missing": missing,
            "asked": len(asked)}


def html_to_text(htm):
    htm = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", htm or "")
    htm = re.sub(r"(?i)<br\s*/?>|</(p|li|div|h\d)>", "\n", htm)
    txt = re.sub(r"<[^>]+>", " ", htm)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", txt)).strip()
