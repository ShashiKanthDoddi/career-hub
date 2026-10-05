"""answers module of Career Hub. See MAP.md for what lives where."""
import difflib
import re
from .store import data, load_profile, ordered_fields, resolve_path, save_data
from .textutil import norm, truthy


class Answers:
    """Profile (fixed data) + remembered answers, both from the data file."""

    def __init__(self):
        prof = load_profile()
        self.fields = prof.get("fields") or {}
        self.files = prof.get("files") or {}
        settings = prof.get("settings") or {}
        self.settings = settings
        p = settings.get("pause_after_each_page", True)
        self.pause = p if isinstance(p, bool) else truthy(p)
        self.site_password = str(settings.get("job_site_password") or "").strip()
        self.memory = dict(data()["answers"])
        self.ai_key = str(settings.get("claude_api_key") or "").strip()
        mode = str(settings.get("ai_mode") or "").strip().lower()
        self.nvidia_key = str(settings.get("nvidia_api_key") or "").strip()
        self.ai_nvidia = mode.startswith("nvidia")
        self.ai_paid = mode.startswith("claude") or (not mode and bool(self.ai_key))   # a saved Claude key with no choice keeps Claude; otherwise free
        self.ai_on = bool(self.nvidia_key) if self.ai_nvidia else bool(self.ai_key) if self.ai_paid else True

    def _experience_part(self, unit):
        """Years or months out of her total experience ('3', '3.5', '3 years 6 months')."""
        total = ""
        for pat, val in self.fields.items():
            if pat.startswith("total (work"):
                total = str(val or "")
        if not re.search(r"\d", total):
            return None
        y = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?|y\b)", total, re.I)
        m = re.search(r"(\d+)\s*(?:months?|mos?)", total, re.I)
        if y or m:
            years = float(y.group(1)) if y else 0.0
            months = int(m.group(1)) if m else 0
        else:
            years, months = float(re.search(r"\d+(?:\.\d+)?", total).group(0)), 0
        whole = int(years)
        months += round((years - whole) * 12)
        whole += months // 12
        months %= 12
        return str(whole if unit == "years" else months)

    def remember(self, label, value, nm=""):
        k = norm(label + " " + nm) if nm else norm(label)
        self.memory[k] = value
        data()["answers"][k] = value
        save_data()

    def lookup(self, f):
        """Answer for a field from memory or profile, without asking. Returns (value, source) or (None, None)."""
        key = norm(f["label"])
        if f.get("unit") and re.search(r"experience|\bexp\b|tenure|how long|duration", key):
            part = self._experience_part(f["unit"])
            if part is not None:
                return part, "profile"
        old = norm(f["label"], split=False)               # answers saved before v2.2 used this form
        both = norm(f["label"] + " " + f.get("nm", "")) if f.get("nm") else key
        for k in (both, key, old):
            if k in self.memory:
                return self.memory[k], "memory"
        if f["kind"] == "file":
            for pat, path in self.files.items():
                if re.search(pat, key):
                    return (str(resolve_path(path)) if path else ""), "profile"
            return None, None
        texts = [both, key] if both != key else [key]     # label + field name ('mobile mobile phone country code'), then label
        for pat, val in ordered_fields(self.fields):
            if any(re.search(pat, k) or (pat in FIELD_ALIASES and re.search(FIELD_ALIASES[pat], k)) for k in texts):
                return ("" if val is None else str(val)), "profile"
            if pat in COMPUTED and re.search(pat, key):
                break
        for pat, fn in COMPUTED.items():                  # answers worked out from other settings
            if re.search(pat, key):
                v = fn(self)
                if v:
                    return v, "profile"
        m = difflib.get_close_matches(key, list(self.memory), n=1, cutoff=0.88)
        if m:
            return self.memory[m[0]], "memory~"            # similar (not identical) question
        return None, None


# Extra wordings for profile fields, so any site's label finds the right answer (matched on norm()'d labels).
FIELD_ALIASES = {
    "current (company|employer)|most recent (company|employer)": r"^company( name)?$|employer( name)?|organi[sz]ation( name)?|current organi[sz]ation",
    "current (job )?(title|role|designation|position)": r"^job title$|^designation$|^title$|current role|^role$|current position",
    "total (work |professional )?experience|total years": r"^experience$|years? of experience|work experience|experience in years|total exp|^exp\b|how many years",
    "date of joining|joining date|start date (at|in) (current|this|your current)|employment start":
        r"(current|present|latest|last) (company|employer|organi[sz]ation|job).*(join|start|since|from)|(join|start|since|from).*(current|present|latest|last) (company|employer|organi[sz]ation|job)|working (here |there )?since|employed since|since when (are|have) you|date joined|joined (on|in)|^start date$|^from( date)?$",
    "notice period": r"available to join|availability to join|days to join|joining (time|period)|how soon can you (join|start)|when can you (join|start)|earliest (joining|start)|notice",
    "country phone code|phone code|country code": r"dial(ing)? code|\bisd\b|calling code",
    "full name|legal name|^name$|your name": r"candidate name|applicant name",
    "how did you hear|^source$": r"source of (application|hire)|where did you (find|hear|see)",
    "phone|mobile|contact number": r"whats ?app",
}


def _pref_locations(db):
    from .textutil import split_list
    cities = [c for c in split_list(db.settings.get("job_locations")) if c != "remote"]
    return ", ".join(c.title() for c in cities)


def _current_location(db):
    v = ""
    for pat, val in db.fields.items():
        if pat.startswith("city|"):
            v = val
    return v


COMPUTED = {
    'location preference|preferred (work |job )?locations?|preferred cit(y|ies)|locations? of choice': _pref_locations,
    'current location|current city|present location|currently (based|located)|^location$|city of residence|where are you (based|located)': _current_location,
}
