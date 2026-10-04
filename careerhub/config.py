"""config module of Career Hub. See MAP.md for what lives where."""
import os
from pathlib import Path


APP_NAME = "Harshitha's Career Hub"


OWNER = "Harshitha"


APP_VERSION = "2.8.0"


BASE = Path(__file__).resolve().parent.parent      # the "Career Hub" folder


DATA = Path(os.environ.get("CAREERHUB_DATA") or BASE / "Harshitha's Data")   # env var = tests use a temp folder


DATA_FILE = DATA / "career_data.json"


FILES_DIR = DATA / "Files"


COVER_DIR = FILES_DIR / "Cover letters"


DRAFT_DIR = DATA / "Summaries"


LOG_DIR = DATA / "Logs"


BACKUP_DIR = DATA / "Backups"


REPORT_DIR = DATA / "Reports"


EXPORT_DIR = DATA / "Exports"


BROWSER_DIR = DATA / ".job_browser"


APP_WINDOW_DIR = DATA / ".app_window"


SKIP = "__SKIP__"


CLICKABLE = "a, button, input[type=submit], [role=button], [role=link]"


APPLY_WORDS = ["apply manually", "easy apply", "apply now", "apply for this job", "apply to this job",
               "apply for this position", "apply online", "start application", "start your application",
               "i m interested", "apply"]


APPLY_IDS = ["applyManually", "adventureButton"]                    # Workday


SIGNUP_WORDS = ["create account", "create an account", "create my account", "sign up", "register",
                "continue", "next", "submit"]


SIGNUP_IDS = ["createAccountSubmitButton"]


SIGNIN_WORDS = ["sign in", "log in", "login", "continue", "next", "submit"]


SIGNIN_IDS = ["signInSubmitButton"]


SSO_SITES = ("linkedin.com", "google.com", "indeed.com", "apple.com", "microsoftonline.com",
             "live.com", "facebook.com", "naukri.com")     # you log in to these yourself


NEXT_WORDS = ["save and continue", "continue", "next", "review", "proceed"]


NEXT_AUTOMATION_IDS = ["bottom-navigation-next-button", "pageFooterNextButton"]  # Workday


# ---- automatic updates (see careerhub/updater.py and tools/make_release.py) ----
# GitHub repository the app updates from, as "owner/repo" or "owner/repo@branch".
# The helper sets this once; it can also be changed in Settings -> Updates.
UPDATE_SOURCE = "ShashiKanthDoddi/career-hub"
# Private repository where problem reports and ideas become issues (needs github_token in Settings).
ISSUES_SOURCE = "ShashiKanthDoddi/career-hub-reports"
RESTART_CODE = 42          # main() returns this to ask the launcher to restart the app
