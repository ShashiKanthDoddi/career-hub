# Harshitha's Career Hub

Desktop app (Python + Playwright + a local HTML window) that applies to marketing jobs for one person, Harshitha.
It fills application forms, finds matching jobs, and tracks replies from her job Gmail. The helper (her partner)
maintains it and ships fixes through automatic updates from GitHub.

## Save tokens: how to work here

1. **Read `MAP.md` first.** It says which file holds what. Open only the file(s) you need to change.
2. **Make small, targeted edits.** Never rewrite or reformat whole files. Don't re-read files you just edited.
3. **Don't regenerate docs or screenshots** unless asked. The PDF guide is not part of a normal fix.
4. **Verify with `python3 tools/selftest.py`** (about 10 seconds) instead of long manual test scripts.
5. **Keep replies short:** what changed, in which file, and the test result.

## Layout (details in MAP.md)

- `career_hub.py`: bootstrap (packages, start, restart, rollback). Keep it small and stable.
- `careerhub/`: Python package, one concern per module (filler, auth, finder, gmail, updater…).
- `ui/`: `index.html`, `styles.css`, `js/<page>.js`. Plain scripts sharing globals; no build step.
- `tools/`: `selftest.py`, `make_release.py`, `make_guide.py`.
- `docs/Career_Hub_Guide.docx`: source of the user guide (PDF is generated from it).
- `Harshitha's Data/`: her data. **Never commit it, never change its format destructively.**

## Rules

- **Her data is sacred.** All personal data lives in `Harshitha's Data/career_data.json`, accessed only through
  `careerhub/store.py`. New data = a new section or setting added in `Store.upgrade()` with a default.
  Never rename or remove existing keys. Bump `SCHEMA` for data changes; a backup is taken automatically.
- **Profile field keys are regex patterns** (e.g. `notice period`). Don't rename them: saved values hang off them.
  New wordings go in `FIELD_ALIASES` (`careerhub/answers.py`), plus a case in `tools/selftest.py`.
- **Labels are matched after `norm()`** (lowercase, punctuation to spaces, camelCase split).
- **Never click a site's final Submit without her choice.** The app always stops before Submit.
- **Windows launcher:** no brackets inside `IF ( … )` blocks (the file name contains brackets). Use `goto` labels.
- **UI text:** sentence case, plain words, no jargon. She is not technical.

## Release (automatic update to her laptop)

0. **Update the documentation first**: `MAP.md` (new/changed modules), `CLAUDE.md` (rules, known limits), and the
   user guide when something she sees or sets has changed. The guide's source is `docs/Career_Hub_Guide.docx`: edit that
   (also the version in its page header), then run `python tools/make_guide.py` to write `Career_Hub_Guide.pdf` for her
   (uses Word or LibreOffice). Never edit the PDF by hand. No release without this.
1. Bump `APP_VERSION` in `careerhub/config.py`.
2. Add an entry at the top of `CHANGELOG` in `careerhub/changelog.py` (title, `new`, `fixed`).
3. `python3 tools/make_release.py` (hashes use LF line ends, like GitHub serves, so CRLF files on Windows still verify) (add `--urgent` for important fixes). It runs the self-test and writes `release.json`.
4. Commit and push to the GitHub repo set in `careerhub/config.py` (`UPDATE_SOURCE = "owner/repo"`).
5. Her app checks on start and every hour, shows "What's new", installs on "Update now", and restarts.
   If the new version crashes on start, `career_hub.py` restores the previous files automatically.

## Debugging her problems

- She sends **Report a problem**: a zip with `activity_log.txt`, `info.txt`, and screenshots of both windows.
- Field answered wrongly? Find the label in the log. Then decide: is the label read wrongly (`page_js.py`), or is
  the wording missing (`answers.py` FIELD_ALIASES)? Then add a selftest case.
- Run the app locally with a throwaway data folder: `CAREERHUB_DATA=/tmp/chdata python3 career_hub.py`.

## Not done yet / known limits

- Mail is read on start and hourly (`main.mail_loop`). Interview dates are read by regex (`meetings.py`): other time zones are not converted and a reschedule email adds a second entry.
- Cards from emails with no tracker row are made in `overview.py` (key `mail:<company>`); a stage she set by hand holds only until the auto stage changes.
- Captchas are never solved: if one is empty, the app asks her to type it in Chrome before it clicks Submit.
- Calendar pop-up date boxes are set by script (jQuery datepicker if present, else dd/mm/yyyy); other picker libraries are untested.
- Interview emails: time zones in `meetings.py` ZONES (CST left out as ambiguous). Reschedule / cancel match by company name only.
- Workday work history and education (2.6) come from Profile, Work and education (`history.py`, `workday.py`), but the selectors were only tested on a mock page, not a live Workday. Resume reading is a draft she must check.
- Windows is untested on real hardware. LinkedIn/Indeed/Naukri: pasted links work with a daily limit (default 10 per site),
  pacing and rest-on-robot-check (`careerhub/jobsites.py`), alert-email links feed Find jobs; none of it is tested on a real login.
- Web search for companies: DuckDuckGo and Bing block automatic requests, so `discover()` relies on `DEFAULT_BOARDS`
  (`careerhub/finder.py`, live-checked in 2.4; re-check now and then, boards come and go). Companies on their own hiring system
  (Nykaa, Swiggy, Zomato, Freshworks) can't be read: she can only add companies on the five supported systems.
- Themes: Clean white (default), Sand, Emerald, Slate, Mint. A saved theme that no longer exists falls back to Clean white.
- Passwords, the Gmail app password and the API key are stored in plain text in the data file (her choice).
