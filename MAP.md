# MAP: which file holds what

Read this first, then open only the file you need. Each Python module is small and focused.

## Start and launchers

| File | What it does |
| --- | --- |
| `career_hub.py` | Bootstrap: installs missing pip packages, runs `careerhub.main.run()`, restarts after updates (exit code 42), rolls back a crashing update. Keep it small and stable. |
| `Open Career Hub (Mac).command` / `(Windows).bat` | Launchers. Loop while the app exits with 42 (restart after update). The .bat must not use brackets inside IF blocks. |
| `Setup (Mac).command` / `(Windows).bat` | One-time install of Python packages and Chromium. |
| `tools/selftest.py` | Run before every release. Add a CASES line for every label a real site answered wrongly. |
| `tools/make_icon.py` | Draws the gold H icon in 7 pixel-aligned sizes and writes them into the `<link rel="icon">` tags of `ui/index.html`. |
| `tools/make_guide.py` | Turns `docs/Career_Hub_Guide.docx` (the guide's source, edit this) into `Career_Hub_Guide.pdf`. Needs Word or LibreOffice. Refuses if the docx header version differs from APP_VERSION. |
| `tools/make_release.py` | Writes `release.json` (version, changelog, SHA-256 of every file) for auto-updates. |

## Python package `careerhub/`

| Module | Lines | Purpose | Main names |
| --- | --- | --- | --- |
| `config.py` | 92 | Paths, app name/version, button words, UPDATE_SOURCE, RESTART_CODE. Bump APP_VERSION here. | `APP_NAME`, `OWNER`, `APP_VERSION`, `BASE` |
| `changelog.py` | 101 | CHANGELOG list shown in What's new and copied into release.json. Add an entry per release. | `CHANGELOG` |
| `state.py` | 23 | Shared runtime dicts (current job, browser handles, find diagnostics, update manifest, restart flag). | `CURRENT_JOB`, `RESUME_CACHE`, `MAIL`, `JOB` |
| `store.py` | 257 | The ONE data file (career_data.json): defaults, FIELD_ORDER, schema upgrades (Store.upgrade), migration from 1.x, backups, file paths. | `empty_data`, `migrate_legacy`, `Store`, `data`, `save_data`, `ordered_fields`, `resolve_path`, `ProfileError`, `load_profile`, `SCHEMA`, `NEW_IN_SCHEMA_3`, `FIELD_ORDER`, `DEFAULT_PROFILE` … |
| `bridge.py` | 136 | Python <-> window: UI.ask() cards, UI._send() events, log(), notify(), os_open(). | `StopRun`, `Bridge`, `notify`, `os_open`, `log`, `check_stop`, `ainput`, `UI`, `LOG` |
| `textutil.py` | 136 | Small pure helpers: norm (label normaliser, splits camelCase), pick (match answer to options), pretty_label, adapt_value, dates. | `split_words`, `norm`, `truthy`, `pretty_label`, `phone_code`, `adapt_value`, `pick`, `to_iso_date`, `clean_label` … |
| `records.py` | 127 | Applications, accounts/passwords, saved links, found jobs: read/write helpers on the data file. | `known_companies`, `answer_mentions_other_company`, `already_applied_same_job`, `account_rows`, `saved_password`, `log_account`, `save_default_password`, `tracker_rows`, `tracker_add`, `ACCOUNT_COLS`, `TRACKER_COLS` … |
| `page_js.py` | 179 | JavaScript run inside job pages: COLLECT_JS (field + label detection), BUTTONS_JS, TITLE_JS, ERRORS_JS, job-window badge. | `COLLECT_JS`, `BUTTONS_JS`, `TITLE_JS`, `ERRORS_JS` |
| `answers.py` | 89 | Answers.lookup(): finds an answer from memory/profile. FIELD_ALIASES (extra wordings per profile field) and COMPUTED answers. | `Answers`, `FIELD_ALIASES`, `COMPUTED` |
| `resume.py` | 92 | Reads the resume PDF; skills/titles/years; picks 2nd/3rd resume by job title. | `resume_for_job`, `resume_text`, `read_resume`, `resume_profile`, `resume_info`, `MKT_SKILLS`, `ROLE_PHRASES` |
| `ai.py` | 80 | Claude API calls: drafts for questions, tailored cover letters (PDF). | `ai_complete`, `ai_context`, `ai_answer`, `text_to_pdf`, `ai_cover_letter_flow` |
| `filler.py` | 343 | Fills one page: plan_field -> ask_batch (one card for all unknowns) -> fill_field. Next/Submit button detection. | `click_check`, `popup_options`, `plan_field`, `ask_batch`, `fill_field`, `scan`, `fill_page`, `find_buttons`, `settle`, `SUCCESS_RE` … |
| `auth.py` | 146 | Gets from job posting to the form: clicks Apply, signs in / creates accounts. | `get_password`, `auth_state`, `handle_auth`, `get_to_form` |
| `apply_run.py` | 310 | Runs a list of jobs: apply_one (page loop, summary, submit), run_apply, job browser. | `save_draft`, `open_browser`, `table_rows`, `apply_one`, `job_browser`, `run_apply` |
| `launch.py` | 26 | Starts Chrome/Chromium with the sandbox on; downloads the browser if missing. | `launch_chrome`, `SANDBOX` |
| `finder.py` | 363 | Find jobs: hiring-system APIs (Workday, Greenhouse, Lever, Ashby, SmartRecruiters), web discovery plus `DEFAULT_BOARDS` (verified built-in boards, used when search engines refuse us), title-only search without a resume, filters, scoring, diagnostics. | `boards_in`, `board_label`, `seniority_excludes`, `location_ok`, `relevant_title`, `match_score`, `get_json`, `fetch_board`, `web_search`, `UA`, `STRONG_TITLE_WORDS`, `TECH_WORDS`, `CITY_ALIASES` … |
| `jobsites.py` | 100 | LinkedIn / Indeed / Naukri safety: daily limit, pacing between jobs, robot-check detection, rest-for-the-day, job links from alert emails. | `site_of`, `allowed`, `pace`, `challenged`, `alert_jobs`, `clean_job_link` |
| `gmail.py` | 258 | Reads the job Gmail (IMAP, read-only), classifies replies, friendly errors. | `mail_settings`, `classify_mail`, `dec`, `mail_body`, `company_from_sender`, `match_application`, `process_mail`, `imap_fetch`, `gmail_link`, `MONTHS`, `MAIL_TYPES`, `MAIL_SKIP`, `JOB_WORDS` … |
| `reports.py` | 94 | Problem reports (zip of log + screenshots) emailed to the helper. | `make_report`, `smtp_send`, `send_report` |
| `planner.py` | 75 | Home calendar events and to-do list (data keys `events`, `todos`); events from interview emails and from cards moved to Interview/Test. | `add_event`, `set_job_event`, `events_from_mail`, `add_todo` |
| `meetings.py` | 85 | Reads an interview date and time out of an email (`find_meeting`). Add a selftest case for every wording it misses. | `find_meeting` |
| `history.py` | 190 | Work history and education: `parse_history` (resume text -> draft), saved under data key `history`. | `parse_history`, `get_history`, `save_history` |
| `workday.py` | 150 | Workday "My Experience" page: adds and fills one block per job and degree from `history`. Not yet tried on a live Workday. | `fill_history` |
| `overview.py` | 38 | Combines applications + emails into stages for Home and My jobs. | `jobs_overview`, `STAGE_ORDER` |
| `profile_form.py` | 95 | PROFILE_FORM: every box on Profile and Settings (section, label, where, key, type). | `profile_values`, `PROFILE_FORM`, `FORM_HINTS` |
| `updater.py` | 177 | Automatic updates from GitHub: check, download, verify SHA-256, install, rollback info. | `vt`, `source_base`, `safe_path`, `check_for_update`, `install_files`, `install_latest`, `install_zip`, `confirm_started`, `restore_backup`, `UPDATE_DIR`, `PENDING`, `ROLLED_BACK`, `ALLOWED` |
| `api.py` | 383 | Every api_* function the window calls (exposed automatically by main.py). | `start_task`, `api_state`, `api_save_profile`, `api_save_list`, `api_add_to_list`, `api_start_apply`, `api_resume`, `api_start_find`, `api_answers`, `THEMES` … |
| `main.py` | 86 | Opens the app window (ui/index.html), exposes api_*, hourly update check, returns restart code. | `open_app_window`, `update_loop`, `after_load`, `main`, `run`, `UI_INDEX` |

## Interface `ui/` (plain HTML/CSS/JS, loaded straight from disk)

| File | Lines | Purpose |
| --- | --- | --- |
| `ui/index.html` | 226 | All page markup (sidebar, Home, Apply, Find jobs, My jobs, Profile, Settings) + SVG icons. |
| `ui/styles.css` | 285 | Design tokens, 5 colour themes (data-theme / data-mode), components, layout. |
| `ui/js/core.js` | 65 | Web links open in the default browser (`api_open_url`). Helpers ($, esc, toast, when, site), navigation go(), loadState(). |
| `ui/js/home.js` | 51 | Home: greeting, funnel, Needs you, Inbox (shows Gmail errors). |
| `ui/js/planner.js` | 85 | Home calendar, to-do, the "when is it?" and the rejection-kindness pop-ups. | `renderPlanner`, `showCheer` |
| `ui/js/history.js` | 45 | Profile, Work and education: edit jobs and degrees, Read from my resume. | `loadHistory` |
| `ui/js/apply.js` | 38 | Apply: the one job list (add links, apply to one/selected/all). |
| `ui/js/run.js` | 27 | Run bar while applying/finding; end-of-run results. |
| `ui/js/questions.js` | 59 | Question cards from Python: single questions and the all-at-once form (showForm). |
| `ui/js/find.js` | 59 | Find jobs: resume tags, companies, results list, skip reasons, dismiss. |
| `ui/js/jobs.js` | 87 | My jobs board (drag and drop), list, emails, accounts, found, job drawer. |
| `ui/js/forms.js` | 137 | Profile and Settings forms, files, saved answers, themes, What's new, zip install. |
| `ui/js/palette.js` | 57 | Activity drawer, More menu in the sidebar, Report a problem, Quick actions (Ctrl/Cmd+K), keyboard shortcuts. |
| `ui/js/events.js` | 68 | window.onPy event handling, filled-fields pop-up, update modal, startup sequence. |

## Where common changes go

| I want to… | Edit |
| --- | --- |
| Make a profile answer match a new label wording | `careerhub/answers.py` FIELD_ALIASES (then add a case to `tools/selftest.py`) |
| Add a new profile/settings box | `careerhub/profile_form.py` PROFILE_FORM (+ default in `store.py` if needed) |
| The Updates button / update source | `ui/js/events.js` (`checkUpdates`), `careerhub/config.py` `UPDATE_SOURCE` (no Settings box any more) |
| Fix how a field's label is read on a site | `careerhub/page_js.py` COLLECT_JS (`labelOf`, `visualLabel`) |
| Dropdown pre-selected by the site, read-only calendar boxes, captcha before Submit | `careerhub/filler.py` (`plan_field`, `fill_field`, `empty_captcha`), `careerhub/apply_run.py`, `COLLECT_JS` `picker` flag |
| Change filling / asking behaviour | `careerhub/filler.py` (`plan_field`, `ask_batch`, `fill_field`) |
| Next / Submit button not found | `careerhub/config.py` NEXT_WORDS, `careerhub/filler.py` `find_buttons` |
| Login / sign-up problem | `careerhub/auth.py` |
| Workday work history / education not filled | `careerhub/workday.py` (automation ids), `careerhub/history.py` (resume reading) |
| Interview date not read from an email | `careerhub/meetings.py` (then add a case to `tools/selftest.py`) |
| Email sorted wrongly | `careerhub/gmail.py` MAIL_TYPES |
| Job search | `careerhub/finder.py` |
| Store new data | `careerhub/store.py` `Store.upgrade()` + bump SCHEMA |
| A page's look or behaviour | the matching `ui/js/<page>.js` and `ui/styles.css` |
| New button that calls Python | add `api_xxx` in `careerhub/api.py` (auto-exposed), call `api_xxx()` from JS |

## Data (never in the repo)

`Harshitha's Data/` next to the app: `career_data.json` (everything), `Files/`, `Summaries/`, `Logs/`, `Backups/`, `Reports/`, `Exports/`, `.update/`, browser profiles.
