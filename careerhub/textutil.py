"""textutil module of Career Hub. See MAP.md for what lives where."""
import datetime
import difflib
import html
import re


def split_words(s):
    """'mobilePhone.countryCode' -> 'mobile Phone country Code' (field names used as labels)."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(s or ""))
    return re.sub(r"[._]+", " ", s)


def norm(s, split=True):
    s = split_words(s) if split else str(s or "")
    s = re.sub(r"\b(required|select one|optional)\b", " ", s.lower())
    s = re.sub(r"[^a-z0-9+]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def truthy(v):
    return norm(str(v)) in {"yes", "y", "true", "1", "agree", "i agree", "checked", "x"}


def pretty_label(s):
    """What the user sees for a field: 'standardFields.locationPreference.answer' -> 'Location preference'."""
    t = re.sub(r"\s+", " ", split_words(s)).strip(" *:")
    t = re.sub(r"(?i)^(standard fields|custom fields|fields|question)\s+|\s+(answer|value)$", "", t)
    return (t[:1].upper() + t[1:].lower()) if t and (t.islower() or " " not in t or t != t.title()) else t


def phone_code(s):
    m = re.search(r"\+\s?(\d{1,4}(?:-\d{1,4})?)", str(s or ""))
    return m.group(1) if m else None


def adapt_value(f, value):
    """Numbers-only fields ('Available to join (in days)', number inputs) get just the number."""
    label = norm(f.get("label", ""))
    v = str(value)
    if f.get("itype") == "number" or re.search(r"\bin (days|months|years)\b|\b(no|number) of\b|\(?(days|years)\)?$", label):
        m = re.search(r"\d+(?:\.\d+)?", v)
        if m:
            return m.group(0)
    return v


def pick(ans, options):
    """Match a saved answer to one of the options on screen."""
    a = norm(ans)
    if not a or not options:
        return None
    normed = [norm(o) for o in options]
    for o, n in zip(options, normed):
        if n == a:
            return o
    code = phone_code(ans)                        # 'India (+91)' <-> '+91'
    if code:
        for o in options:
            if phone_code(o) == code:
                return o
    for o, n in zip(options, normed):
        if re.search(rf"\b{re.escape(a)}\b", n) or (n and re.search(rf"\b{re.escape(n)}\b", a)):
            return o
    m = difflib.get_close_matches(a, normed, n=1, cutoff=0.75)
    return options[normed.index(m[0])] if m else None


def to_iso_date(s):
    v = str(s or "").strip().lower()
    today = datetime.date.today()
    if v in ("today", "now", "immediately", "immediate", "asap", "right away"):
        return today.isoformat()
    m = re.match(r"in (\d+) (day|week|month)s?", v)
    if m:
        n = int(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2)]
        return (today + datetime.timedelta(days=n)).isoformat()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.datetime.strptime(str(s).strip().replace(",", ""), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def clean_label(l):
    return re.sub(r"\s+", " ", re.sub(r"\*|\brequired\b|\bselect one\b", "", l or "", flags=re.I)).strip(" -:")


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")[:40] or "job"


def strong(pw):
    return bool(len(pw) >= 8 and re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw)
                and re.search(r"\d", pw) and re.search(r"[^A-Za-z0-9]", pw))


def norm_link(u):
    return (u or "").split("#")[0].rstrip("/").lower()


def has_phrase(phrase, text_norm):
    return re.search(rf"\b{re.escape(norm(phrase))}\b", text_norm) is not None


def split_list(v):
    return [x.strip().lower() for x in str(v or "").split(",") if x.strip()]


def days_ago(value):
    """Turns the different 'posted' formats into a number of days (or None)."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):                       # Lever: milliseconds
            return (datetime.datetime.now() - datetime.datetime.fromtimestamp(value / 1000)).days
        v = str(value).lower()
        if "today" in v or "just" in v:
            return 0
        if "yesterday" in v:
            return 1
        m = re.search(r"(\d+)\+?\s*day", v)
        if m:
            return int(m.group(1)) + (1 if "+" in v else 0)
        return (datetime.datetime.now() - datetime.datetime.fromisoformat(str(value)[:19])).days
    except Exception:
        return None


def strip_tags(s):
    return re.sub(r"<[^>]+>", " ", html.unescape(s or ""))


def mask(v):
    return (str(v)[:2] + "•••") if v else ""
