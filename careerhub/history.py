"""history: work history and education. Read from the resume as a DRAFT she checks in Profile; the filler only ever
uses what she saved (data key 'history'). Resume layouts vary a lot, so every guess here is shown to her first."""
import re
from .store import data, save_data

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
PART = rf"(?:{MON}\.?\s*,?\s*\d{{4}}|\d{{1,2}}[/.]\d{{4}}|\d{{4}})"
RANGE = re.compile(rf"({PART})\s*(?:-|–|—|to|until)\s*({PART}|present|current|now|till date|ongoing)", re.I)
WORK_HEAD = {"EXPERIENCE", "WORKEXPERIENCE", "PROFESSIONALEXPERIENCE", "EMPLOYMENT", "EMPLOYMENTHISTORY", "WORKHISTORY",
             "INTERNSHIPS", "INTERNSHIPEXPERIENCE", "RELEVANTEXPERIENCE", "CAREERHISTORY"}
EDU_HEAD = {"EDUCATION", "EDUCATIONALQUALIFICATIONS", "ACADEMICS", "EDUCATIONANDTRAINING", "ACADEMICQUALIFICATIONS"}
DEGREE = re.compile(r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|b\.?\s?com|m\.?\s?com|b\.?\s?a\b|m\.?\s?a\b|"
                    r"bba|mba|pgdm|bca|mca|ph\.?d|bachelor|master|diploma|postgraduate|graduate|12th|10th|higher secondary|"
                    r"secondary|intermediate)", re.I)
SCHOOL = re.compile(r"university|college|institute|school|academy|iit|nit|iim|polytechnic|vidyalaya|campus", re.I)
BULLET = re.compile(r"^\s*[•●▪◦‣⁃*\-–·�?]\s*")


def _heading(line):
    """Section kind for a heading line ('work', 'edu', 'other') or ''. Handles SPACED CAPITALS, Title Case and 'Work Experience:'."""
    text = line.strip().rstrip(":")
    letters = re.sub(r"[^A-Za-z]", "", text)
    key = letters.upper()
    if len(letters) < 5 or len(text) > 50 or re.search(r"\d", text) or text.endswith("."):
        return ""
    words = len(re.findall(r"[A-Za-z]{2,}", text))
    if key in WORK_HEAD or (words <= 4 and any(w in key for w in ("EXPERIENCE", "EMPLOYMENT", "WORKHISTORY", "CAREERHISTORY"))):
        return "work"
    if key in EDU_HEAD or (words <= 4 and any(w in key for w in ("EDUCATION", "ACADEMIC", "QUALIFICATION"))):
        return "edu"
    return "other" if letters == key else ""


def _date(part):
    """'Oct 2024' / '10/2024' / '2024' -> ('2024', '10'); the month is '' when only a year is known."""
    p = part.strip().lower()
    m = re.match(rf"({MON})\.?\s*,?\s*(\d{{4}})", p)
    if m:
        return m.group(2), f"{MONTHS[m.group(1)[:3]]:02d}"
    m = re.match(r"(\d{1,2})[/.](\d{4})", p)
    if m:
        return m.group(2), f"{int(m.group(1)):02d}"
    m = re.match(r"(\d{4})", p)
    return (m.group(1), "") if m else ("", "")


def _sections(text):
    out, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        h = _heading(line)
        if h:
            cur = h
            out.setdefault(cur, [])
            continue
        if cur in ("work", "edu"):
            out[cur].append(line)
    return out


def _split_title_company(text):
    for sep in (r"\s*\|\s*", r"\s+at\s+", r"\s+@\s+", r"\s+[-–—]\s+", r"\s*,\s*"):
        parts = re.split(sep, text, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


def _parse_work(lines):
    jobs = []
    heads = [k for k, l in enumerate(lines) if RANGE.search(l) and not BULLET.match(l)]
    for n, k in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        m = RANGE.search(lines[k])
        rest = (lines[k][:m.start()] + " " + lines[k][m.end():]).strip(" |,-–—()")
        body = lines[k + 1:end]
        title, company = _split_title_company(rest) if rest else ("", "")
        if not rest:                                            # the title is on the line above the dates
            prev = [l for l in lines[max(0, k - 2):k] if not BULLET.match(l)]
            if prev:
                title, company = _split_title_company(prev[-1])
        elif not company or (rest.count(",") == 1 and not re.search(r"[|@]|\s[-–—]\s| at ", rest)):
            above = lines[k - 1] if k and (n == 0 or k - 1 > heads[n - 1]) else ""
            if above and not BULLET.match(above) and len(above) <= 60 and not above.rstrip().endswith("."):
                title, company = above.strip(), rest                # "Title" line, then "Company, City   dates"
                rest = ""
        if rest and not company:                                # title here, company on the next plain line
            nxt = next((l for l in body if not BULLET.match(l)), "")
            if nxt:
                company = nxt
                body = [l for l in body if l != nxt]
        loc = ""
        if "," in company:
            company, loc = [x.strip() for x in company.split(",", 1)]
        sy, sm = _date(m.group(1))
        cur = not re.search(r"\d", m.group(2))
        ey, em = ("", "") if cur else _date(m.group(2))
        desc = "\n".join(BULLET.sub("", l).strip() for l in body if BULLET.match(l)).strip()
        jobs.append({"title": title, "company": company, "location": loc, "start": (f"{sy}-{sm}" if sm else sy),
                     "end": (f"{ey}-{em}" if em else ey), "current": cur, "description": desc})
    return jobs


def _parse_edu(lines):
    anchors = [k for k, l in enumerate(lines) if DEGREE.search(l) and not BULLET.match(l)]
    if not anchors:
        return []
    anchors[0] = 0                                                  # a school line above the first degree belongs to it
    blocks = [lines[a:(anchors[i + 1] if i + 1 < len(anchors) else len(lines))] for i, a in enumerate(anchors)]
    school_lines = [[l for l in b if not BULLET.match(l) and SCHOOL.search(l) and not DEGREE.search(l)] for b in blocks]
    for i in range(len(blocks) - 1):                                # "ABC College" listed above the next degree line
        if len(school_lines[i]) > 1 and not school_lines[i + 1]:
            school_lines[i + 1] = [school_lines[i].pop()]
    entries = []
    for b, schools in zip(blocks, school_lines):
        e = {"school": "", "degree": "", "field": "", "start": "", "end": "", "grade": ""}
        for l in b:
            if DEGREE.search(l) and not BULLET.match(l):
                m = RANGE.search(l)
                t = (l[:m.start()] + l[m.end():]) if m else re.sub(r"\b(19|20)\d{2}\b", "", l)
                t = re.sub(r"\([^)]*\)", "", t).strip(" |,-–—")
                for sep in (r"\s*,\s*", r"\s+in\s+", r"\s+[-–—]\s+", r"\s*\|\s*"):
                    parts = re.split(sep, t, maxsplit=1)
                    if len(parts) == 2:
                        e["degree"], e["field"] = parts[0].strip(), parts[1].strip()
                        break
                else:
                    e["degree"] = t
                break
        if e["field"] and not schools:                              # "MBA, Marketing - XYZ University"
            for part in re.split(r"\s+[-–—|]\s+|\s*,\s*", e["field"]):
                if SCHOOL.search(part):
                    schools = [part]
                    e["field"] = re.sub(r"\s*[-–—|,]?\s*" + re.escape(part) + r"\s*$", "", e["field"]).strip(" -,")
                    break
        if schools:
            sch = re.sub(r"\([^)]*\)", "", schools[0]).strip()
            if "," in sch and len(sch.rsplit(",", 1)[1].strip()) <= 20:
                sch = sch.rsplit(",", 1)[0].strip()                # drop the trailing city
            e["school"] = sch
        for l in b:
            m = RANGE.search(l)
            if m:
                e["start"] = _date(m.group(1))[0]
                e["end"] = _date(m.group(2))[0] if re.search(r"\d{4}", m.group(2)) else ""
                break
        else:
            yrs = re.findall(r"\b(?:19|20)\d{2}\b", " ".join(b))
            e["end"] = yrs[-1] if yrs else ""
        g = re.search(r"(?:cgpa|gpa|grade|percentage|marks)\s*:?\s*([\d.]+\s*(?:/\s*\d+|%)?)", " ".join(b), re.I)
        e["grade"] = re.sub(r"\s+", "", g.group(1)) if g else ""
        entries.append(e)
    return entries


def parse_history(text):
    """Best-effort draft from resume text: {'work': [...], 'education': [...]}."""
    sec = _sections(text or "")
    work = _parse_work(sec.get("work", []))
    if not work:                                  # no clear heading: any line with a date range outside Education
        lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
        edu_lines = set(sec.get("edu", []))
        work = _parse_work([l for l in lines if l not in edu_lines])
    return {"work": work, "education": _parse_edu(sec.get("edu", []))}


def get_history():
    h = data().setdefault("history", {})
    h.setdefault("work", []), h.setdefault("education", [])
    return h


def save_history(h):
    work = [{k: (bool(w.get(k)) if k == "current" else str(w.get(k) or "").strip()) for k in
             ("title", "company", "location", "start", "end", "current", "description")} for w in h.get("work", [])]
    edu = [{k: str(e.get(k) or "").strip() for k in ("school", "degree", "field", "start", "end", "grade")}
           for e in h.get("education", [])]
    data()["history"] = {"work": [w for w in work if w["title"] or w["company"]],
                         "education": [e for e in edu if e["school"] or e["degree"]]}
    save_data()
