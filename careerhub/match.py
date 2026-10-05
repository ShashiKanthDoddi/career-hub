"""match module of Career Hub: how well a job fits her. See MAP.md.
The score is built from parts that are only counted when the information is there: the job title against her roles,
the job's required skills and words against her resume, years asked for against her years, the level in the title,
and the city. With too little information (for example only a title from an alert email) there is NO score: None."""
import re
from .resume import MKT_SKILLS
from .textutil import has_phrase, norm

WEIGHTS = {"skills": 40, "role": 25, "experience": 15, "level": 10, "location": 10}
LEVELS = [(0, r"intern|apprentice|trainee|fresher|graduate"), (1, r"junior|jr|associate|entry|assistant"),
          (3, r"senior|sr"), (4, r"lead|principal|staff|manager|head"), (5, r"director|vp|vice president|chief")]
STOP = set("""a about above across after again all also an and any are as at be been being both but by can could do does done during each
either for from had has have having he her here his how i if in into is it its just may me more most must my no nor not of off on only
or other our out over own per same she should so some such than that the their them then there these they this those through to too
under until up use used using very was we were what when where which while who whom why will with within without would you your
experience experienced work working team teams role roles job jobs position company candidate candidates ability able strong good great
excellent knowledge skills skill years year plus required requirements preferred qualification qualifications responsibilities
responsibility including include includes etc well new key high level based related relevant like need needs looking join part full time
opportunity opportunities environment business people help ensure support provide providing across end day days every make making
across degree bachelor bachelors master masters equivalent least minimum etc apply benefits equal employer""".split())
REQ_HEAD = re.compile(r"(?im)^\W*(requirements?|qualifications?|what you.?ll need|must have|skills|who you are|you have|what we.?re looking for)\b")


def title_level(title):
    t = f" {norm(title)} "
    for lv, pat in LEVELS:
        if re.search(rf" (?:{pat}) ", t):
            return lv
    if re.search(r" (?:ii|2) ", t):
        return 2
    return None


def role_fit(title, roles):
    """0 to 1: does the title contain one of her roles? None when she has no roles."""
    t = norm(title)
    if not roles or not t:
        return None
    toks, best = set(t.split()), 0.0
    for r in roles:
        r = norm(r)
        if not r:
            continue
        if has_phrase(r, t):
            best = max(best, 1.0 if t == r else 0.9)
            continue
        rt = set(r.split()) - {"and", "of", "the"}
        if rt:
            best = max(best, 0.7 * len(rt & toks) / len(rt))
        if "marketing" in toks and "marketing" in r:
            best = max(best, 0.5)
    return best


def job_terms(desc):
    """{term: weight}: the curated skills named in the job text, plus its other meaningful words (words in the
    requirements section count double)."""
    text = desc or ""
    req = []
    lines = text.splitlines()
    on = False
    for l in lines:
        if REQ_HEAD.match(l):
            on = True
            continue
        if on and re.match(r"^\W*[A-Z][A-Za-z /&']{3,40}:?\s*$", l.strip()) and not REQ_HEAD.match(l):
            on = False
        if on:
            req.append(l)
    reqn = norm(" ".join(req).lower())
    n = norm(text.lower())
    terms = {}
    for s in MKT_SKILLS:
        if has_phrase(s, n):
            terms[norm(s)] = 3 + (2 if has_phrase(s, reqn) else 0)
    counts = {}
    for w in n.split():
        if len(w) >= 3 and w not in STOP and not w.isdigit():
            counts[w] = counts.get(w, 0) + 1
    covered = " ".join(terms)
    for w, c in sorted(counts.items(), key=lambda kv: -kv[1])[:40]:
        if w in covered:
            continue
        terms[w] = (1 + (1 if w in reqn.split() else 0)) * (1.5 if c >= 3 else 1)
    return terms


def years_asked(desc):
    m = re.findall(r"(\d{1,2})\s*\+?\s*(?:(?:-|to|–)\s*\d{1,2}\s*)?\+?\s*(?:years|yrs)", (desc or "").lower())
    vals = [int(x) for x in m if 0 < int(x) < 30]
    return min(vals) if vals else None


def score_job(title, desc, location, prof, wanted=None, location_ok=None):
    """{'score': 0-100 or None, 'parts': {name: 0-1}, 'missing': [terms the job asks for that her resume lacks]}.
    prof: {'roles', 'skills', 'years', 'text' (her resume, normalised)}."""
    parts, missing = {}, []
    r = role_fit(title, prof.get("roles"))
    if r is not None:
        parts["role"] = r
    rtext = prof.get("text") or ""
    if desc and len(desc) > 200 and rtext:
        terms = job_terms(desc)
        if len(terms) >= 4:
            tot = sum(terms.values())
            have = sum(w for k, w in terms.items() if has_phrase(k, rtext))
            parts["skills"] = have / tot
            missing = [k for k, w in sorted(terms.items(), key=lambda kv: -kv[1]) if not has_phrase(k, rtext)][:8]
    years = prof.get("years")
    ask = years_asked(desc)
    if years is not None and ask is not None:
        parts["experience"] = 1.0 if years >= ask else max(0.0, 1 - 0.25 * (ask - years))
    lv = title_level(title)
    if years is not None and lv is not None:
        want = 0 if years < 1 else 1 if years < 3 else 2 if years < 6 else 3 if years < 9 else 4 if years < 14 else 5
        parts["level"] = max(0.0, 1 - 0.3 * abs(lv - want))
    if location_ok is not None and location and wanted:
        parts["location"] = 1.0 if location_ok(location, wanted) else 0.0
    if "skills" not in parts:                         # the job text was not read (or not enough of it): no number at all
        return {"score": None, "parts": parts, "missing": []}
    w = sum(WEIGHTS[k] for k in parts)
    return {"score": round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()) / w), "parts": parts, "missing": missing}
