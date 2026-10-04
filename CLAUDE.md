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

## Security rules

- **Releases are signed.** `make_release.py` signs `release.json` with the private key in `~/.careerhub_release_key` (only on the helper's computer, never in the repo; back it up: if it is lost, her app refuses all updates until a release signed by the old key ships a new `PUBLIC_KEY`). The app checks the signature against `PUBLIC_KEY` in `careerhub/sigcheck.py`; the zip fallback needs the signed `release.json` too.
- `tools/make_key.py` makes a signing key (and a new one when rotating; see its header).
- **Update source must be GitHub over https** (`updater.source_base`). Other addresses are refused. `pinned_base` asks api.github.com for the branch's newest commit and reads every file from that commit (branch addresses are cached by GitHub for ~5 min); it falls back to the branch address if the API fails.
- **`api_*` functions only answer the app's own window** (`main.guarded`: page and frame must be under `ui/`). Don't add `--allow-file-access-from-files` or load web pages in the app window.

## Release (automatic update to her laptop)

0. **Update the documentation once per day** (saves tokens): the first release of a day updates `MAP.md` (new/changed
   modules), `CLAUDE.md` (rules, known limits), and the user guide when something she sees or sets has changed, covering
   every change since the last docs update (see `Docs updated:` at the top of `MAP.md`, then set it to today and the version).
   Later releases the same day skip this step (their changes go into the next day's docs update), unless the change is
   important (a new setting or page she uses, a changed rule or security behaviour, an `--urgent` release): then update now.
   The guide's source is `docs/Career_Hub_Guide.docx`: edit that (also the version in its page header), then run
   `python tools/make_guide.py` to write `Career_Hub_Guide.pdf` for her (uses Word or LibreOffice). Never edit the PDF by hand.
1. Bump `APP_VERSION` in `careerhub/config.py`.
2. Add an entry at the top of `CHANGELOG` in `careerhub/changelog.py` (title, `new`, `fixed`).
3. `python3 tools/make_release.py` (hashes use LF line ends, like GitHub serves, so CRLF files on Windows still verify) (add `--urgent` for important fixes). It runs the self-test and writes `release.json`.
4. Commit and push to the GitHub repo set in `careerhub/config.py` (`UPDATE_SOURCE = "owner/repo"`).
5. Her app checks on start and every hour, shows "What's new", installs on "Update now", and restarts.
   If the new version crashes on start, `career_hub.py` restores the previous files automatically.

## Debugging her problems

- **Suggest a feature** (and Report a problem, when the `github_token` setting is set) creates a GitHub issue in the private `ISSUES_SOURCE` repo (config.py), with the log, screenshots and her pictures on its `issue-files` branch. The token (fine-grained, that repo only, Issues + Contents write) is set in her Settings; without it reports go by email and ideas are refused. Settings, Your reports and ideas, lists them with Open / Done / Won't do (`my_issues`, last 50, same token).
- She sends **Report a problem**: a zip with `activity_log.txt`, `info.txt`, and screenshots of both windows.
- Field answered wrongly? Find the label in the log. Then decide: is the label read wrongly (`page_js.py`), or is
  the wording missing (`answers.py` FIELD_ALIASES)? Then add a selftest case.
- Run the app locally with a throwaway data folder: `CAREERHUB_DATA=/tmp/chdata python3 career_hub.py`.

## Not done yet / known limits

- Mail is read on start and hourly (`main.mail_loop`). A manual Check email shows scanned / read counts (`mail_progress` event from `imap_fetch`, sent thread-safely via `loop.call_soon_threadsafe`); bodies are fetched 25 at a time. Interview dates are read by regex (`meetings.py`): other time zones are not converted; a reschedule moves the calendar entry and a cancel removes it (matched by company).
- Up to three job inboxes are read (settings `gmail_address`, `_2`, `_3`, each with its own app password); the first must work, extra ones are skipped with a log line if they fail.
- Company and title of job-board mails like LinkedIn "Your application to X at Y" come from the subject (`job_from_subject`); other subject wordings still fall back to the sender (e.g. "LinkedIn").
- Mail from job boards (`BOARD_SENDERS` in `gmail.py`: Naukri, AmbitionBox, LinkedIn…) is judged by subject only; digests never become interview cards.
- Gmail labels (`X-GM-LABELS`, read from All Mail) decide the mail type via `label_kind` in `gmail.py`: names containing interview/assessment/reject/offer; "Job boards" is skipped. The whole label path counts (Rejected/Naukri), and one 180-day re-scan (`label_scan` in app state) re-sorts older mail. The company comes from the sender name only if it looks like a company; otherwise from the mail domain (`company_from_sender`). Job-board senders without a strong subject are dropped, not shown as Update.
- A new version is downloaded in the background as soon as it is found (`prefetch_update`); "Update now" installs the cached files.
- My jobs stages "Waiting for reply" (Interview whose date, from the email or the calendar entry, has passed; no date = stays Interview) and "No response" (Applied 30+ days, `NO_REPLY_DAYS`) are derived in `overview._timed_stage`, not stored. A hand-set stage holds until the derived stage changes.
- Cards from emails with no tracker row are made in `overview.py` (key `mail:<company>`); a stage she set by hand holds only until the auto stage changes.
- Captchas are never solved: if one is empty, the app asks her to type it in Chrome before it clicks Submit.
- Calendar pop-up date boxes are set by script (jQuery datepicker if present, else dd/mm/yyyy); other picker libraries are untested.
- Interview emails: time zones in `meetings.py` ZONES (CST left out as ambiguous). Reschedule / cancel match by company name only.
- Workday work history and education (2.6) come from Profile, Work and education (`history.py`, `workday.py`), but the selectors were only tested on a mock page, not a live Workday. Resume reading is a draft she must check.
- Windows is untested on real hardware. LinkedIn/Indeed/Naukri: pasted links work with a daily limit (default 10 per site),
  pacing and rest-on-robot-check (`careerhub/jobsites.py`), alert-email links feed Find jobs; none of it is tested on a real login.
- Location filter (`location_ok`): "remote" matches only plain "Remote", "anywhere" or remote with India; remote tied to another country is dropped. Jobs with no location are kept.
- Web search for companies: DuckDuckGo and Bing block automatic requests, so `discover()` relies on `DEFAULT_BOARDS`
  (`careerhub/finder.py`, live-checked in 2.4; re-check now and then, boards come and go). Companies on their own hiring system
  (Nykaa, Swiggy, Zomato, Freshworks) can't be read: she can only add companies on the five supported systems.
- Look (2.7): stat cards on Home are separate tiles coloured by `--c`; the jobs filter row uses `.row.fbar` so selects stay narrow. Themes: Clean white (default), Sand, Emerald, Slate, Mint. A saved theme that no longer exists falls back to Clean white. Letters (3.0): `data-font` (Classic, Friendly, Elegant, Bold, Handwritten) and Calm mode (`data-motion`), saved in state `font` / `calm`.
- "Continue with Google" on LinkedIn may still be refused by Google even with automation flags hidden (`launch.py`); she should sign in with her LinkedIn email and password.
- Logins persist because `launch.py` re-saves session cookies (`.job_browser_cookies.json`, `.app_window_cookies.json` in her data folder, plain text) every minute; a login made in the last minute before closing may be lost.
- The app window opens maximised (`main.open_app_window`: `--start-maximized`, then forced through Chrome's DevTools protocol because Chrome may restore a saved smaller size). She can still resize it.
- "Show every opening at these companies" (`all_openings` in `finder.search_jobs`) skips the role, city, age and minimum-match filters and the web search; it only works for companies on the five supported systems.
- Rejection wording is regex-based (`MAIL_TYPES` in `gmail.py`); a polite rejection with none of the listed phrases is still shown as an update.
- Mail sorting (2.8.2, `process_mail`): Gmail Promotions/Social are skipped at scan time (job alerts and ATS mail kept); newsletters (`is_bulk`: List-Unsubscribe, bulk header, marketing sender) are judged by subject only; the full text is read only for mail tied to her applications (tracked company, ATS, reply thread); other job-like mail needs 2 points for interview/test. Types are scored (`type_scores`: subject 3, text 1 each, quoted replies and `NOT_INVITE` phrases ignored); an offer or rejection wins when found. "Not a job email" (`api_not_job`) adds the sender to `mail_blocked` (data, schema 6); there is no unblock in the app yet. One re-sort pass (`label_scan` 6) re-checks old interview/received cards; cards too old to re-read are kept.
- Speed (2.8): the data file is saved compact (no indent) and `Store.version` counts saves; `jobs_overview` is cached on (version, hour), so anything that changes data must call `save_data()`. Profile/Settings forms are drawn only when opened (`FORMS_STALE`); My jobs tables (`api_tables`) are fetched only for the Accounts and Found tabs; Find jobs draws 60 rows at a time.
- Duplicate warning (`api_found` `dup`) matches company and title exactly after `norm()`; a re-worded title is not caught. Interview prep tips (`api_prep`) need the Claude key and use only her resume, not the job text.
- Never use `confirm()`, `alert()` or `prompt()` in `ui/`: Playwright closes browser dialogs at once (she saw Clear flash and do nothing). Use `askYes` / `notice` (`questions.js`).
- Chrome alerts (3.0): `UI.ask(..., chrome=page)` raises the job window (`bridge.raise_window`: minimise + restore through CDP) and calls `notify`; untested on real Windows, where the pop-up is a PowerShell tray balloon. Unanswered asks ring again after 4 and 8 minutes.
- Interview reminders (`main.remind_loop`, `planner.due_reminders`): one pop-up an hour before, or at 08:00 for an entry with no time; marked `reminded` on the event. A reschedule clears it.
- Company brief (`research.py`, Next up on Home) sends only the company name and Wikipedia text to the free Pollinations AI (`ai.free_complete`, no key); never send her resume or contact details there.
- Find jobs shows only the newest search (`last_found` in state) until she clicks the link to earlier results; `diag.missing` lists company names no supported hiring system was found for.
- Home's 7-day summary and the "offer waiting" line count job cards (same as the stat boxes), not raw emails, so an offer email that matched no job only shows in Needs you.
- Passwords, the Gmail app password and the API key are stored in plain text in the data file (her choice).
