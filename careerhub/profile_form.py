"""profile_form module of Career Hub. See MAP.md for what lives where."""
from .store import load_profile


# (section, label, where, key, type)   where: fields | settings | files
PROFILE_FORM = [
    ("About you", "First name", "fields", "first name|given name", "text"),
    ("About you", "Last name", "fields", "last name|surname|family name", "text"),
    ("About you", "Full name", "fields", "full name|legal name|^name$|your name", "text"),
    ("About you", "Email (also used for job-site accounts)", "fields", "e ?mail", "text"),
    ("About you", "Phone number", "fields", "phone|mobile|contact number", "text"),
    ("About you", "Country phone code", "fields", "country phone code|phone code|country code", "text"),
    ("About you", "Gender", "fields", "gender", "choice:Female|Male|Non-binary|Prefer not to say"),
    ("About you", "Date of birth (e.g. 15/08/1998)", "fields", 'date of birth|birth ?date|^dob$', "text"),
    ("About you", "Current location (city you live in now)", "fields", 'current location|current city|present location|currently (based|located)|^location$|city of residence|where are you (based|located)', "text"),
    ("Address", "Street address", "fields", "address line 1|street|^address", "text"),
    ("Address", "City", "fields", "city|town", "text"),
    ("Address", "State", "fields", "state|province|region", "text"),
    ("Address", "PIN / ZIP code", "fields", "postal|zip|pin ?code", "text"),
    ("Address", "Country", "fields", "country", "text"),
    ("Online presence", "LinkedIn profile link", "fields", "linked ?in", "text"),
    ("Online presence", "Portfolio / work samples link", "fields", "portfolio|work samples|writing samples|case stud", "text"),
    ("Online presence", "Behance / Dribbble", "fields", "behance|dribbble", "text"),
    ("Online presence", "Instagram", "fields", "instagram", "text"),
    ("Online presence", "Website / blog", "fields", "blog|personal website|^website", "text"),
    ("Education", "Highest qualification (e.g. MBA, B.Com)", "fields", 'course|degree|qualification|education level|highest education', "text"),
    ("Education", "Specialisation (e.g. Marketing)", "fields", 'branch|speciali[sz]ation|major|stream|field of study|discipline', "text"),
    ("Education", "College / university", "fields", 'university|college|institute|institution|school name', "text"),
    ("Education", "Course start date", "fields", 'start of course|course start|education start', "text"),
    ("Education", "Course end / graduation date", "fields", 'end of course|course end|graduation (date|year)|year of (passing|graduation)|passing year|passed out', "text"),
    ("Experience", "Currently employed?", "fields", 'currently working here|currently employed|currently work(ing)? (here|there)|i currently work', "yesno"),
    ("Experience", "Joined current company on", "fields", 'date of joining|joining date|start date (at|in) (current|this|your current)|employment start', "text"),
    ("Experience", "Key skills", "fields", 'skills|key skills|core skills|skill set', "text"),
    ("Experience", "Current company", "fields", "current (company|employer)|most recent (company|employer)", "text"),
    ("Experience", "Current job title", "fields", "current (job )?(title|role|designation|position)", "text"),
    ("Experience", "Total experience (years)", "fields", "total (work |professional )?experience|total years", "text"),
    ("Experience", "Notice period", "fields", "notice period", "text"),
    ("Experience", "Tools you use", "fields", "tools|software|platforms", "text"),
    ("Experience", "Marketing channels", "fields", "channels", "text"),
    ("Experience", "Languages", "fields", "languages", "text"),
    ("Experience", "Current salary (leave empty to answer per job)", "fields", "current (ctc|salary|compensation)", "text"),
    ("Experience", "Expected salary (leave empty to answer per job)", "fields",
     "expected (ctc|salary|compensation)|salary expectation|desired salary", "text"),
    ("Common questions", "Legally allowed to work in the job's country?", "fields",
     "legally authori[sz]ed|authori[sz]ed to work|eligible to work|work authori[sz]ation|right to work", "yesno"),
    ("Common questions", "Need visa sponsorship?", "fields", "sponsor|visa", "yesno"),
    ("Common questions", "Willing to relocate?", "fields", "relocat", "yesno"),
    ("Common questions", "Willing to travel?", "fields", "travel", "yesno"),
    ("Common questions", "OK with office / hybrid work?", "fields",
     "hybrid|on ?site|work from office|in office|in person", "yesno"),
    ("Common questions", "Worked at the company before?", "fields",
     "previously (worked|been employed)|former employee|ever (worked|been employed)", "yesno"),
    ("Common questions", "\"How did you hear about us?\"", "fields", "how did you hear|^source$", "text"),
    ("Files", "Resume", "files", "resume|cv|upload|attach|select files|file", "file"),
    ("Files", "Cover letter (optional)", "files", "cover", "file"),
    ("Files", "Second resume (optional)", "settings", "resume_2_file", "file"),
    ("Files", "…use it for job titles containing", "settings", "resume_2_keywords", "text"),
    ("Files", "Third resume (optional)", "settings", "resume_3_file", "file"),
    ("Files", "…use it for job titles containing", "settings", "resume_3_keywords", "text"),
    ("Job-site accounts", "Password for new job-site accounts", "settings", "job_site_password", "secret"),
    ("Applying", "Pause after every page so I can check it", "settings", "pause_after_each_page", "switch"),
    ("Applying", "Most applications per day on LinkedIn, Indeed or Naukri (keeps accounts safe)", "settings",
     "jobsite_daily_limit", "range"),
    ("Finding jobs", "Cities (comma separated, add Remote if you like)", "settings", "job_locations", "text"),
    ("Finding jobs", "Skip job titles containing", "settings", "exclude_words", "text"),
    ("Finding jobs", "Minimum match %", "settings", "minimum_match", "range"),
    ("Finding jobs", "Ignore jobs older than (days)", "settings", "max_job_age_days", "range"),
    ("Job email (Gmail)", "Job Gmail address", "settings", "gmail_address", "text"),
    ("Job email (Gmail)", "Gmail app password", "settings", "gmail_app_password", "secret"),
    ("Job email (Gmail)", "Second Gmail address (optional)", "settings", "gmail_address_2", "text"),
    ("Job email (Gmail)", "Second Gmail app password", "settings", "gmail_app_password_2", "secret"),
    ("Job email (Gmail)", "Third Gmail address (optional)", "settings", "gmail_address_3", "text"),
    ("Job email (Gmail)", "Third Gmail app password", "settings", "gmail_app_password_3", "secret"),
    ("Job email (Gmail)", "Check this inbox automatically", "settings", "gmail_auto", "switch"),
    ("Help", "Send problem reports to (email)", "settings", "helper_email", "text"),
    ("AI helper (optional)", "Claude API key (from console.anthropic.com)", "settings", "claude_api_key", "secret"),
    ("AI helper (optional)", "Write a tailored cover letter for every job", "settings", "ai_cover_letters", "switch"),
]


FORM_HINTS = {
    "gmail_app_password": "Not the normal Gmail password: a 16-letter app password. The guide shows how to make one.",
    "gmail_address_2": "Optional: Career Hub reads this inbox too. It needs its own 16-letter app password.",
    "helper_email": "Problem reports go here, e.g. the person who set this up for you.",
    "claude_api_key": "Optional. Enables ✨ AI drafts and cover letters.",
    "resume|cv|upload|attach|select files|file": "Not in the list? Drop the file into the box above, then pick it here.",
}


def profile_values():
    prof = load_profile()
    out = []
    for section, label, where, key, typ in PROFILE_FORM:
        v = (prof.get(where) or {}).get(key, "")
        if isinstance(v, bool):
            v = "Yes" if v else "No"
        tab = "settings" if (where == "settings" and section != "Files") else "profile"
        opts = typ.split(":", 1)[1].split("|") if typ.startswith("choice:") else []
        out.append({"section": section, "label": label, "where": where, "key": key, "type": typ.split(":")[0], "options": opts,
                    "value": "" if v is None else str(v), "hint": FORM_HINTS.get(key, ""), "tab": tab})
    return out
