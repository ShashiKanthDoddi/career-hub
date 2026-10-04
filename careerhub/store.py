"""store module of Career Hub. See MAP.md for what lives where."""
from pathlib import Path
import csv
import datetime
import json
import re
import shutil
from .config import BACKUP_DIR, BASE, BROWSER_DIR, DATA, DATA_FILE, DRAFT_DIR, EXPORT_DIR, FILES_DIR, LOG_DIR, REPORT_DIR


SCHEMA = 3
NEW_IN_SCHEMA_3 = {'referred by|referral|referrer': ""}   # defaults added for existing data in v2.2


FIELD_ORDER = ['first name|given name', 'middle name', 'last name|surname|family name', 'preferred name|nickname', 'full name|legal name|^name$|your name', 'date of birth|birth ?date|^dob$', 'e ?mail', 'phone device type|device type', 'country phone code|phone code|country code', 'phone extension|^extension', 'phone|mobile|contact number', 'legally authori[sz]ed|authori[sz]ed to work|eligible to work|work authori[sz]ation|right to work', 'sponsor|visa', '18 years|age of 18|over 18', 'previously (worked|been employed)|former employee|ever (worked|been employed)', 'relocat', 'travel', 'hybrid|on ?site|work from office|in office|in person', 'how did you hear|^source$', 'address line 2|apartment|suite', 'address line 1|street|^address', 'location preference|preferred (work |job )?locations?|preferred cit(y|ies)|locations? of choice', 'current location|current city|present location|currently (based|located)|^location$|city of residence|where are you (based|located)', 'city|town', 'state|province|region', 'postal|zip|pin ?code', 'country', 'linked ?in', 'portfolio|work samples|writing samples|case stud', 'behance|dribbble', 'instagram', 'twitter', 'blog|personal website|^website', 'currently working here|currently employed|currently work(ing)? (here|there)|i currently work', 'date of joining|joining date|start date (at|in) (current|this|your current)|employment start', 'start of course|course start|education start', 'end of course|course end|graduation (date|year)|year of (passing|graduation)|passing year|passed out', 'course|degree|qualification|education level|highest education', 'branch|speciali[sz]ation|major|stream|field of study|discipline', 'university|college|institute|institution|school name', 'current (company|employer)|most recent (company|employer)', 'current (job )?(title|role|designation|position)', 'total (work |professional )?experience|total years', 'notice period', 'tools|software|platforms', 'channels', 'languages', 'skills|key skills|core skills|skill set', 'referred by|referral|referrer', 'current (ctc|salary|compensation)', 'expected (ctc|salary|compensation)|salary expectation|desired salary', 'gender', 'race|ethnicity|hispanic', 'veteran', 'disability', 'terms|privacy|consent|i agree|acknowledge|certify']


DEFAULT_PROFILE = {'settings': {'pause_after_each_page': 'Yes', 'job_site_password': '', 'job_locations': 'Bengaluru, Mumbai, Remote', 'exclude_words': 'sales, intern', 'minimum_match': 50, 'max_job_age_days': 30, 'resume_2_file': '', 'resume_2_keywords': '', 'resume_3_file': '', 'resume_3_keywords': '', 'claude_api_key': '', 'ai_cover_letters': 'No', 'gmail_address': '', 'gmail_app_password': '', 'gmail_auto': 'Yes', 'helper_email': '', 'jobsite_daily_limit': 10}, 'fields': {'middle name': '', 'preferred name|nickname': '', 'phone device type|device type': 'Mobile', 'country phone code|phone code|country code': 'India (+91)', 'phone extension|^extension': '', 'legally authori[sz]ed|authori[sz]ed to work|eligible to work|work authori[sz]ation|right to work': 'Yes', 'sponsor|visa': 'No', '18 years|age of 18|over 18': 'Yes', 'previously (worked|been employed)|former employee|ever (worked|been employed)': 'No', 'relocat': 'Yes', 'travel': 'Yes', 'hybrid|on ?site|work from office|in office|in person': 'Yes', 'how did you hear|^source$': 'LinkedIn', 'address line 2|apartment|suite': '', 'country': 'India', 'behance|dribbble': '', 'instagram': '', 'twitter': '', 'blog|personal website|^website': '', 'notice period': '30 days', 'tools|software|platforms': 'Google Analytics, Google Ads, Meta Ads Manager, HubSpot, SEMrush, Canva', 'channels': 'SEO, Paid Social, Google Ads, Email, Content', 'languages': 'English, Hindi', 'race|ethnicity|hispanic': 'Decline', 'veteran': 'not a protected veteran', 'disability': 'do not want to answer', 'terms|privacy|consent|i agree|acknowledge|certify': 'Yes', 'first name|given name': 'Harshitha', 'referred by|referral|referrer': ''}, 'files': {'cover': 'CoverLetter.pdf', 'resume|cv|upload|attach|select files|file': 'Resume.pdf'}}


LEGACY_FILES = ["profile.yaml", "answers_memory.json", "applications.csv", "accounts.csv", "found_jobs.csv",
                "jobs.txt", "email_updates.json", "job_notes.json", ".app_state.json"]


def empty_data():
    return {"schema": SCHEMA, "profile": json.loads(json.dumps(DEFAULT_PROFILE)), "answers": {}, "applications": [],
            "accounts": [], "found_jobs": [], "email_updates": [], "notes": {}, "saved_links": [], "state": {}}


def _read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _legacy_dir():
    for d in (BASE, BASE.parent / "job_autofill"):
        if (d / "profile.yaml").exists() or (d / "applications.csv").exists():
            return d
    return None


def migrate_legacy(src):
    """One-time move from the old many-files layout (v1.x) into the single data file. Nothing is lost:
    every old file is kept in Backups/old-files-before-2.0."""
    d = empty_data()
    keep = BACKUP_DIR / "old-files-before-2.0"
    keep.mkdir(parents=True, exist_ok=True)
    for name in LEGACY_FILES:
        if (src / name).exists():
            shutil.copy2(src / name, keep / name)
    if (src / "profile.yaml").exists():
        try:
            import yaml
            txt = (src / "profile.yaml").read_text(encoding="utf-8")
            txt = txt.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
            y = yaml.safe_load(txt) or {}
            for part in ("fields", "files"):
                if isinstance(y.get(part), dict):
                    d["profile"][part] = {k: ("Yes" if v is True else "No" if v is False else ("" if v is None else v))
                                          for k, v in y[part].items()}
            if isinstance(y.get("settings"), dict):
                d["profile"]["settings"].update({k: ("Yes" if v is True else "No" if v is False else v)
                                                 for k, v in y["settings"].items()})
        except Exception as e:
            print("profile.yaml could not be read:", e)
    for name, key in (("answers_memory.json", "answers"), ("email_updates.json", "email_updates"),
                      ("job_notes.json", "notes"), (".app_state.json", "state")):
        if (src / name).exists():
            try:
                d[key] = json.loads((src / name).read_text(encoding="utf-8"))
            except Exception:
                pass
    for name, key in (("applications.csv", "applications"), ("accounts.csv", "accounts"), ("found_jobs.csv", "found_jobs")):
        if (src / name).exists():
            try:
                d[key] = _read_csv(src / name)
            except Exception:
                pass
    if (src / "jobs.txt").exists():
        d["saved_links"] = [l.strip() for l in (src / "jobs.txt").read_text(encoding="utf-8").splitlines()
                            if l.strip().startswith("http")]
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and f.suffix.lower() in (".pdf", ".doc", ".docx") and not f.name.lower().startswith("job_autofill_guide"):
            if not (FILES_DIR / f.name).exists():
                shutil.copy2(f, FILES_DIR / f.name)
    for old, new in (("cover_letters", FILES_DIR / "Cover letters"), ("summaries", DRAFT_DIR), ("logs", LOG_DIR),
                     ("backups", keep / "old backups"), ("reports", REPORT_DIR)):
        if (src / old).is_dir() and not new.exists():
            shutil.copytree(src / old, new)
    if (src / ".browser_profile").is_dir() and not BROWSER_DIR.exists():
        try:
            (shutil.move if src == BASE else shutil.copytree)(str(src / ".browser_profile"), str(BROWSER_DIR))
        except Exception:
            pass
    if src == BASE:                                   # tidy the main folder: originals now live in the backup
        for name in LEGACY_FILES:
            try:
                (src / name).unlink()
            except FileNotFoundError:
                pass
        for old in ("cover_letters", "summaries", "logs", "backups", "reports"):
            shutil.rmtree(src / old, ignore_errors=True)
        for f in src.iterdir():
            if f.is_file() and f.suffix.lower() in (".pdf", ".doc", ".docx") and (FILES_DIR / f.name).exists() \
                    and not f.name.lower().startswith(("job_autofill_guide", "career_hub_guide")):
                f.unlink()
        for junk in (".app_window.html",):
            try:
                (src / junk).unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(src / ".app_window_profile", ignore_errors=True)
    print(f"Moved your data from the old version into '{DATA.name}'. Old files kept in Backups/{keep.name}.")
    return d


class Store:
    def __init__(self):
        self.d = None

    def load(self):
        if self.d is None:
            DATA.mkdir(exist_ok=True)
            if DATA_FILE.exists():
                self.d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            else:
                src = _legacy_dir()
                self.d = migrate_legacy(src) if src else empty_data()
                self.save()
            self.upgrade()
        return self.d

    def upgrade(self):
        """Adds anything newer versions need. Existing data is never removed or rewritten."""
        d, changed = self.d, False
        for k, v in empty_data().items():
            if k not in d:
                d[k], changed = v, True
        prof = d.setdefault("profile", {})
        for part in ("fields", "files", "settings"):
            if not isinstance(prof.get(part), dict):
                prof[part], changed = {}, True
        for k, v in DEFAULT_PROFILE["settings"].items():
            if k not in prof["settings"]:
                prof["settings"][k], changed = v, True
        if d.get("schema", 1) < SCHEMA:
            backup_data(tag=f"before-schema-{SCHEMA}")
            if d.get("schema", 1) < 3:                   # v2.2: new default fields, gender became a real choice
                for k, v in NEW_IN_SCHEMA_3.items():
                    prof["fields"].setdefault(k, v)
                if prof["fields"].get("gender") == "Decline":
                    prof["fields"].pop("gender")
            d["schema"], changed = SCHEMA, True
        if changed:
            self.save()

    def save(self):
        DATA.mkdir(exist_ok=True)
        tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
        tmp.write_text(json.dumps(self.d, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(DATA_FILE)


STORE = Store()


def data():
    return STORE.load()


def save_data():
    STORE.save()


def ordered_fields(fields):
    pos = {k: i for i, k in enumerate(FIELD_ORDER)}
    return sorted(fields.items(), key=lambda kv: pos.get(kv[0], len(pos)))


def resolve_path(p):
    """Accepts 'Resume.pdf' (in Harshitha's Data/Files), '~/Documents/x.pdf', or a dragged-in path."""
    p = str(p).strip().strip("'\"").replace("\\ ", " ")
    path = Path(p).expanduser()
    return path if path.is_absolute() else FILES_DIR / path


class ProfileError(Exception):
    pass


def load_profile():
    prof = data()["profile"]
    return {"fields": dict(ordered_fields(prof.get("fields", {}))), "files": dict(prof.get("files", {})),
            "settings": dict(prof.get("settings", {}))}


def folder_files():
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.name for p in FILES_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in (".pdf", ".doc", ".docx") and not p.name.startswith("."))


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    """Writes to a temporary file first, so a crash can never leave a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def backup_data(tag=None, keep=14):
    """Copies the data file into Backups/<date>/ (daily, kept 14 days). Never changes the original."""
    dest = BACKUP_DIR / (tag or datetime.date.today().isoformat())
    if dest.exists() and tag is None:
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        shutil.copy2(DATA_FILE, dest / DATA_FILE.name)
    daily = sorted(d for d in BACKUP_DIR.iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d.name))
    for d in daily[:-keep]:
        shutil.rmtree(d, ignore_errors=True)
    return dest


def app_state():
    return dict(data()["state"])


def save_app_state(**kw):
    data()["state"].update(kw)
    save_data()


def table_of(rows):
    if not rows:
        return []
    head = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in head:
                head.append(k)
    return [head] + [[str(r.get(h, "")) for h in head] for r in rows]


def export_csv(name, rows):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows(table_of(rows))
    return path
