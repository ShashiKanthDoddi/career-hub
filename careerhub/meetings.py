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


# Offsets in minutes from UTC. Ambiguous ones (CST, which is also China and Cuba) are left out on purpose.
ZONES = {"ist": 330, "utc": 0, "gmt": 0, "bst": 60, "cet": 60, "cest": 120, "eet": 120, "est": -300, "edt": -240,
         "cdt": -300, "mst": -420, "mdt": -360, "pst": -480, "pdt": -420, "sgt": 480, "jst": 540, "gst": 240,
         "aest": 600, "aedt": 660, "india standard time": 330, "eastern": -300, "pacific": -480, "central european": 60}
ZONE_RE = re.compile(r"\b(?:(?:utc|gmt)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?|(india standard time|central european|eastern|pacific|ist|utc|gmt|bst|cest|cet|eet|est|edt|cdt|mst|mdt|pst|pdt|sgt|jst|gst|aest|aedt))\b", re.I)


def _zone_minutes(text, pos):
    """UTC offset (minutes) written next to the time, or None. US zones follow daylight saving for the given date by name only."""
    m = ZONE_RE.search(text[max(0, pos - 60): pos + 200])
    if not m:
        return None
    if m.group(2):
        return (1 if m.group(1) == "+" else -1) * (int(m.group(2)) * 60 + int(m.group(3) or 0))
    return ZONES.get(m.group(4).lower())


def _to_local(d, hhmm, zone_min):
    """Moves a date and time written in another zone to this computer's own time."""
    h, mi = int(hhmm[:2]), int(hhmm[3:])
    when = datetime.datetime(d.year, d.month, d.day, h, mi, tzinfo=datetime.timezone(datetime.timedelta(minutes=zone_min)))
    local = when.astimezone()
    return local.date(), local.strftime("%H:%M")


RANGE_END = re.compile(r"\s*(?:-|–|to|until)\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b", re.I)


def _time_near(text, pos):
    window = text[max(0, pos - 60): pos + 140]
    m = TIME_RE.search(window)
    if not m:
        window, m = text, TIME_RE.search(text)
    if not m:
        return ""
    if m.group(3):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= h <= 12:
            return ""
        h = h % 12 + (12 if m.group(3).lower() == "p" else 0)
    else:
        h, mi = int(m.group(4)), int(m.group(5))
        end = RANGE_END.match(window, m.end())              # "3:30 - 4:00pm": only the end says am / pm
        if end and 1 <= h <= 12:
            eh = int(end.group(1))
            pm = end.group(3).lower() == "p"
            if h % 12 > eh % 12:
                pm = not pm
            h = h % 12 + (12 if pm else 0)
    return f"{h:02d}:{mi:02d}"


def find_meeting(text, sent):
    """text: subject + email body. sent: datetime.date the email was sent. Returns {'date','time'} or None."""
    found = _candidates(re.sub(r"\s+", " ", text or ""), sent)
    if not found:
        return None
    flat = re.sub(r"\s+", " ", text)
    pos, d = found[0]
    t = _time_near(flat, pos)
    zone = _zone_minutes(flat, pos) if t else None
    if zone is not None:
        d, t = _to_local(d, t, zone)
    return {"date": d.isoformat(), "time": t}


CANCEL_RE = re.compile(r"\b(cancel(l)?ed|cancell?ation|no longer (going|able) to (hold|proceed)|called off)\b", re.I)
CHANGE_RE = re.compile(r"\b(re-?schedul\w*|new (date|time)|changed? (the )?(date|time)|updated? (the )?(date|time|invitation)|postponed|moved to|revised)\b", re.I)


def find_change(text):
    """'cancel', 'reschedule' or '' for an interview email."""
    if CANCEL_RE.search(text or ""):
        return "cancel"
    return "reschedule" if CHANGE_RE.search(text or "") else ""
