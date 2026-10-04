"""meetings: finds the date and time of an interview inside an email. Returns ISO date + 'HH:MM' (time may be empty)."""
import datetime
import re

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
DAYS = {d: i for i, d in enumerate("mon tue wed thu fri sat sun".split())}
MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DAY = r"(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
ORD = r"(?:st|nd|rd|th)?"
DATE_RES = [
    (re.compile(rf"\b(\d{{1,2}}){ORD}\s+(?:of\s+)?{MON}\.?,?(?:\s+(\d{{4}}))?\b", re.I), "dm"),      # 12 Oct 2026, 12th October
    (re.compile(rf"\b{MON}\.?\s+(\d{{1,2}}){ORD}(?:,?\s+(\d{{4}}))?\b", re.I), "md"),               # October 12, 2026
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),                                              # 2026-10-12
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b"), "dmy"),                                    # 12/10/2026 (day first)
    (re.compile(r"\b(tomorrow)\b", re.I), "rel"),
    (re.compile(rf"\b(?:this|next|on)\s+{DAY}\b", re.I), "wd"),
]
TIME_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?m\b\.?|\b([01]?\d|2[0-3]):([0-5]\d)\b", re.I)


def _ymd(y, m, d):
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def _candidates(text, sent):
    """[(position, date)] for every date written in the text, on or after the day the email was sent."""
    out = []
    for rx, kind in DATE_RES:
        for m in rx.finditer(text):
            g = m.groups()
            d = None
            if kind == "dm":
                d = _ymd(int(g[2]) if g[2] else sent.year, MONTHS[g[1][:3].lower()], int(g[0]))
            elif kind == "md":
                d = _ymd(int(g[2]) if g[2] else sent.year, MONTHS[g[0][:3].lower()], int(g[1]))
            elif kind == "iso":
                d = _ymd(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "dmy":
                d = _ymd(int(g[2]), int(g[1]), int(g[0]))
            elif kind == "rel":
                d = sent + datetime.timedelta(days=1)
            elif kind == "wd":
                ahead = (DAYS[g[0][:3].lower()] - sent.weekday()) % 7
                d = sent + datetime.timedelta(days=ahead or 7)
            if d and kind in ("dm", "md") and not (g[2] if kind == "dm" else g[2]) and d < sent:
                d = _ymd(d.year + 1, d.month, d.day)              # "12 January" written in December means next year
            if d and sent <= d <= sent + datetime.timedelta(days=120):
                out.append((m.start(), d))
    return sorted(out)


def _time_near(text, pos):
    window = text[max(0, pos - 60): pos + 140]
    m = TIME_RE.search(window) or TIME_RE.search(text)
    if not m:
        return ""
    if m.group(3):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= h <= 12:
            return ""
        h = h % 12 + (12 if m.group(3).lower() == "p" else 0)
    else:
        h, mi = int(m.group(4)), int(m.group(5))
    return f"{h:02d}:{mi:02d}"


def find_meeting(text, sent):
    """text: subject + email body. sent: datetime.date the email was sent. Returns {'date','time'} or None."""
    found = _candidates(re.sub(r"\s+", " ", text or ""), sent)
    if not found:
        return None
    pos, d = found[0]
    return {"date": d.isoformat(), "time": _time_near(re.sub(r"\s+", " ", text), pos)}
