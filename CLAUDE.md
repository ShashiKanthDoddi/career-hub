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
- `tools/`: `selftest.py`, `make_release.py`.
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

1. Bump `APP_VERSION` in `careerhub/config.py`.
2. Add an entry at the top of `CHANGELOG` in `careerhub/changelog.py` (title, `new`, `fixed`).
3. `python3 tools/make_release.py` (add `--urgent` for important fixes). It runs the self-test and writes `release.json`.
4. Commit and push to the GitHub repo set in `careerhub/config.py` (`UPDATE_SOURCE = "owner/repo"`).
5. Her app checks on start and every hour, shows "What's new", installs on "Update now", and restarts.
   If the new version crashes on start, `career_hub.py` restores the previous files automatically.

## Debugging her problems

- She sends **Report a problem**: a zip with `activity_log.txt`, `info.txt`, and screenshots of both windows.
- Field answered wrongly? Find the label in the log. Then decide: is the label read wrongly (`page_js.py`), or is
  the wording missing (`answers.py` FIELD_ALIASES)? Then add a selftest case.
- Run the app locally with a throwaway data folder: `CAREERHUB_DATA=/tmp/chdata python3 career_hub.py`.

## Not done yet / known limits

- Workday work-history and education sections are not filled from the resume.
- Windows is untested on real hardware; LinkedIn automation risks account limits.
- Passwords, the Gmail app password and the API key are stored in plain text in the data file (her choice).
