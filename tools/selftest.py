#!/usr/bin/env python3
"""Quick check before every release: python3 tools/selftest.py   (exit code 0 = all good).

1. every Python file compiles      2. the package imports with a throwaway data folder
3. changelog matches APP_VERSION     4. field-matching cases from real sites still resolve
5. the UI files exist and the page loads in a hidden browser without JavaScript errors
Add a line to CASES whenever a real site's label was answered wrongly; it then stays fixed.
"""
import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["CAREERHUB_DATA"] = tempfile.mkdtemp(prefix="careerhub-test-")
sys.path.insert(0, str(ROOT))
FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


# (label as the site shows it, kind, expected answer) with the profile seeded below
CASES = [
    ("Experience *", "text", "3"),
    ("Available To Join (in days) *", "text", "30 days"),
    ("Current Location *", "text", "Hyderabad"),
    ("standardFields.locationPreference.answer", "text", "Hyderabad, Bengaluru"),
    ("mobilePhone.countryCode", "select", "India (+91)"),
    ("Company Name", "text", "Mamaearth"),
    ("Job Title", "text", "Growth Marketing Manager"),
    ("Referred By", "text", ""),
    ("By applying, you hereby accept the data processing terms under the Privacy Policy", "checkbox", "Yes"),
    ("Email Address*", "text", "jobs@example.com"),
    ("Notice Period", "text", "30 days"),
]


def main():
    print("1. compile")
    for p in sorted(list(ROOT.glob("careerhub/*.py")) + [ROOT / "career_hub.py"] + list(ROOT.glob("tools/*.py"))):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as e:
            check(False, f"{p.name}: {e}")
    check(True, "all Python files compile")

    print("2. import")
    from careerhub import api, answers, store, textutil
    from careerhub.changelog import CHANGELOG
    from careerhub.config import APP_VERSION
    d = store.data()
    check(d["schema"] == store.SCHEMA, f"data file created at schema {store.SCHEMA}")

    print("3. changelog")
    versions = [c["version"] for c in CHANGELOG]
    check(versions[0] == APP_VERSION, f"newest changelog entry is {APP_VERSION}")
    check(len(versions) == len(set(versions)), "no version listed twice")

    print("4. field matching")
    f = d["profile"]["fields"]
    f.update({"city|town": "Hyderabad", "total (work |professional )?experience|total years": "3",
              "current (company|employer)|most recent (company|employer)": "Mamaearth",
              "current (job )?(title|role|designation|position)": "Growth Marketing Manager", "e ?mail": "jobs@example.com"})
    d["profile"]["settings"]["job_locations"] = "Hyderabad, Bengaluru, Remote"
    db = answers.Answers()
    for label, kind, want in CASES:
        got = db.lookup({"label": label, "kind": kind})[0]
        check(got == want, f"{label[:50]!r} -> {got!r}" + ("" if got == want else f" (expected {want!r})"))
    check(textutil.pick("India (+91)", ["+93", "+91"]) == "+91", "phone code +91 matches 'India (+91)'")
    check(textutil.adapt_value({"label": "Available To Join (in days)"}, "30 days") == "30", "'in days' fields get a number")

    from careerhub import jobsites
    check(jobsites.site_of("https://in.indeed.com/viewjob?jk=abc") == "Indeed" and jobsites.site_of("https://x.com/linkedin.com") is None,
          "job sites recognised by host")
    check(jobsites.clean_job_link("https://www.linkedin.com/comm/jobs/view/3912345678/?trackingId=x") == "https://www.linkedin.com/jobs/view/3912345678",
          "LinkedIn alert link cleaned")
    check(jobsites.clean_job_link("https://in.indeed.com/rc/clk?jk=0123456789abcdef&fccid=1") == "https://in.indeed.com/viewjob?jk=0123456789abcdef",
          "Indeed alert link cleaned")
    check(jobsites.alert_jobs('<a href="https://www.naukri.com/job-listings-seo-manager-acme-123?src=m">SEO Manager</a>'
                              '<a href="https://www.naukri.com/jobs">More</a>') ==
          [("https://www.naukri.com/job-listings-seo-manager-acme-123", "SEO Manager")], "Naukri alert email: only real job links")
    from careerhub.finder import location_ok
    check(location_ok("Remote, India", ["bengaluru", "remote"]) and location_ok("Remote", ["remote"])
          and not location_ok("Munich, Germany remote", ["bengaluru", "remote"]) and not location_ok("Remote in the US", ["remote"]),
          "remote jobs tied to another country are not shown")
    check(__import__("careerhub.gmail", fromlist=["x"]).company_from_sender("Choragudi, Kamala A.", "k@accenture.com") == "Accenture", "a recruiter's name is not used as the company")
    import email.message
    from careerhub import gmail
    def _mail(frm, subj, body):
        m = email.message.EmailMessage(); m["From"], m["Subject"], m["Date"] = frm, subj, "Mon, 28 Sep 2026 10:00:00 +0000"
        m.set_content(body); return [("x" + subj, m.as_bytes())]
    check(not gmail.process_mail(_mail("Naukri <info@naukri.com>", "You applied for 5 jobs on 28 Sep", "Top interview questions, invite you to apply"), [], set())
          and not gmail.process_mail(_mail("AmbitionBox <no-reply@ambitionbox.com>", "Reviews of TNS India Foundation", "interview experiences"), [], set()),
          "job-board digest mails are not marked as interviews")
    check(gmail.process_mail(_mail("Naukri <info@naukri.com>", "Interview invitation from Acme", "hello"), [], set())[0]["type"] == "interview",
          "job-board mail with interview in the subject still counts")
    gmail.MAIL_LABELS["xRej"] = ["Applied", "Rejected"]; gmail.MAIL_LABELS["xJb"] = ["Job boards"]; gmail.MAIL_LABELS["xInt"] = ["Applied/Interviews"]
    check(gmail.process_mail([("xRej", _mail("Acme HR <hr@acme.com>", "Your application", "Thanks for your time")[0][1])], [], set())[0]["type"] == "rejection"
          and gmail.process_mail([("xInt", _mail("Acme HR <hr@acme.com>", "Next steps", "see you")[0][1])], [], set())[0]["type"] == "interview"
          and not gmail.process_mail([("xJb", _mail("Foo <a@foo.com>", "Application update", "applied")[0][1])], [], set()),
          "Gmail labels (Interviews, Rejected, Job boards) decide the type")
    check(all((gmail.process_mail(_mail("Acme HR <hr@acme.com>", sub, body), [], set()) or [{}])[0].get("type") == "rejection" for sub, body in
              [("Thank you for your interest in Acme", "We have decided not to take your application further."),
               ("Update on your application", "We are moving ahead with other candidates."),
               ("Your application at Acme", "You have not been shortlisted for this role.")]),
          "Rejection wordings without 'unfortunately' are still read as rejections")
    check(jobsites.CHALLENGE_RE.search("Let's do a quick security check") and not jobsites.CHALLENGE_RE.search("Marketing Manager"),
          "robot-check wording detected")
    check(jobsites.allowed("LinkedIn")[0], "daily limit allows the first application")

    import datetime
    from careerhub.meetings import find_meeting
    sent = datetime.date(2026, 10, 4)
    check(find_meeting("Your interview is on Thursday, 8 October 2026 at 3:30 PM IST", sent) == {"date": "2026-10-08", "time": "15:30"},
          "interview email: date and time read")
    check(find_meeting("Interview slot: Oct 12th, 10.30 am", sent) == {"date": "2026-10-12", "time": "10:30"}, "interview email: Oct 12th 10.30 am")
    from careerhub.meetings import find_change
    check(find_meeting("Thursday Oct 8 3:30 - 4:00pm IST", sent)["time"] == "15:30" if datetime.datetime.now().astimezone().utcoffset() == datetime.timedelta(hours=5, minutes=30)
          else True, "interview email: a range like 3:30 - 4:00pm takes pm from the end")
    check(find_meeting("Interview 8 Oct 2026 at 10:00 UTC", sent)["time"] == (datetime.datetime(2026, 10, 8, 10, 0, tzinfo=datetime.timezone.utc).astimezone().strftime("%H:%M")),
          "interview email: time in another zone is shown in local time")
    check(find_change("Rescheduled: your interview") == "reschedule" and find_change("Your interview was cancelled") == "cancel"
          and find_change("Interview invitation") == "", "interview email: reschedule / cancel wording")
    check(find_meeting("Please share your availability. You applied on 1 Oct 2026", sent) is None, "interview email without a date: nothing added")

    from careerhub.overview import _timed_stage
    day = lambda n: (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
    past_mtg = [{"type": "interview", "meeting": {"date": day(2), "time": "10:00"}}]
    next_mtg = [{"type": "interview", "meeting": {"date": day(-2), "time": "10:00"}}]
    check(_timed_stage("k", day(10), "Interview", past_mtg) == "Waiting" and _timed_stage("k", day(10), "Interview", next_mtg) == "Interview"
          and _timed_stage("k", day(10), "Interview", [{"type": "interview"}]) == "Interview",
          "My jobs: interview moves to Waiting for reply once its date has passed")
    check(_timed_stage("k", day(30), "Applied", []) == "NoResponse" and _timed_stage("k", day(29), "Applied", []) == "Applied"
          and _timed_stage("k", day(60), "Rejected", []) == "Rejected", "My jobs: applied 30+ days with no reply goes to No response")

    from careerhub import overview as _ov
    _ov.tracker_rows = lambda: [{"Company": "Acme", "Job title": "Manager", "Date": "2026-09-01", "Link": "https://a/1", "Status": "Submitted"}]
    _ov.data = lambda: {"notes": {}, "events": [], "email_updates": [
        {"id": "r1", "date": "2026-09-19T10:00", "company": "Acme", "title": "", "subject": "Update", "type": "rejection", "link": ""},
        {"id": "r2", "date": "2026-09-20T10:00", "company": "Zeta", "title": "", "subject": "Update", "type": "rejection", "link": ""}]}
    check(sorted((j["company"], j["stage"]) for j in _ov.jobs_overview()[0]) == [("Acme", "Rejected"), ("Zeta", "Rejected")],
          "My jobs: a rejection email that matched no link still shows (on the company's card, or its own)")
    first = _ov.jobs_overview()
    same = _ov.jobs_overview() is first
    _ov.STORE.version += 1                                # any save makes the next call recompute
    check(same and _ov.jobs_overview() is not first, "My jobs: overview is reused until the data is saved again")

    from careerhub.history import parse_history
    hh = parse_history("WORK EXPERIENCE\nSenior Manager\nAcme Corp, Bengaluru   Jan 2021 - Present\n- Led campaigns\n"
                       "Executive | Beta Ltd, Mumbai  06/2018 - 12/2020\n- Ran SEO\nEDUCATION\nMBA in Marketing\nXYZ University, Pune\n2016 - 2018\nPercentage: 78%")
    check([(w["title"], w["company"], w["start"], w["current"]) for w in hh["work"]] ==
          [("Senior Manager", "Acme Corp", "2021-01", True), ("Executive", "Beta Ltd", "2018-06", False)], "resume: jobs read in both layouts")
    check(hh["education"] and (hh["education"][0]["degree"], hh["education"][0]["school"], hh["education"][0]["end"]) == ("MBA", "XYZ University", "2018"),
          "resume: education read")

    from careerhub.answers import Answers
    from careerhub.textutil import to_iso_date

    class _A(Answers):
        def __init__(self, fields):
            self.fields, self.memory, self.files = fields, {}, {}
    a = _A({"total (work |professional )?experience|total years": "3.5",
            "date of joining|joining date|start date (at|in) (current|this|your current)|employment start": "June 2023"})
    check(a.lookup({"label": "Experience *", "kind": "text", "unit": "years"})[0] == "3"
          and a.lookup({"label": "Experience", "kind": "text", "unit": "months"})[0] == "6", "Experience boxes: years and months split")
    check(a.lookup({"label": "Date of joining (current company)", "kind": "text"})[0] == "June 2023"
          and a.lookup({"label": "Working since", "kind": "text"})[0] == "June 2023", "Joined current company: wordings found")
    check(to_iso_date("June 2023") == "2023-06-01" and to_iso_date("06/2023") == "2023-06-01", "month and year dates understood")

    print("4b. security")
    import base64
    import secrets
    from careerhub import sigcheck, updater
    seed = secrets.token_bytes(32)
    pub = sigcheck.public_key(seed).hex()
    man = {"version": "9.9.9", "files": [{"path": "careerhub/config.py", "sha256": "ab"}]}
    man["signature"] = base64.b64encode(sigcheck.sign(seed, sigcheck.canonical(man))).decode()
    check(sigcheck.manifest_ok(man, pub), "signed release: signature accepted")
    check(not sigcheck.manifest_ok({**man, "version": "9.9.8"}, pub) and not sigcheck.manifest_ok({k: v for k, v in man.items() if k != "signature"}, pub)
          and not sigcheck.manifest_ok(man), "release changed, unsigned, or signed by another key: refused")
    ok_src = []
    for src in ("owner/repo", "https://github.com/owner/repo", "https://raw.githubusercontent.com/owner/repo/main/"):
        updater.data = lambda s=src: {"profile": {"settings": {"update_source": s}}}
        ok_src.append(updater.source_base().startswith("https://raw.githubusercontent.com/owner/repo/"))
    bad_src = []
    for src in ("http://evil.example/x/", "https://evil.example/", "http://raw.githubusercontent.com/o/r/main/"):
        updater.data = lambda s=src: {"profile": {"settings": {"update_source": s}}}
        bad_src.append(updater.source_base() == "")
    check(all(ok_src) and all(bad_src), "update source: only GitHub over https is accepted")
    try:
        from playwright.async_api import async_playwright as _apw
    except ImportError:
        _apw = None
    if _apw:
        from careerhub.main import UI_INDEX, guarded

        async def guard_test():
            async def api_probe():
                return "ran"
            async with _apw() as p:
                b = await p.chromium.launch()
                ctx = await b.new_context()
                await ctx.expose_binding("api_probe", guarded(api_probe))
                res = []
                for url in (UI_INDEX.as_uri(), "data:text/html,<p>x</p>"):
                    pg = await ctx.new_page()
                    await pg.goto(url)
                    res.append(await pg.evaluate("window.api_probe().then(v => v, e => 'blocked')"))
                await b.close()
                return res
        try:
            got = asyncio.run(guard_test())
            check(got == ["ran", "blocked"], f"app functions work from the app window only (got {got})")
        except Exception as e:
            check(False, f"window guard test failed: {str(e)[:150]}")

    print("5. user interface")
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="((?:js/)?[\w./-]+\.(?:js|css))"', html)
    check(all((ROOT / "ui" / r).exists() for r in refs), f"{len(refs)} UI files referenced and present")
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  skip browser check (playwright not installed)")
        return
    stub = {n: None for n in dir(api) if n.startswith("api_")}

    async def load():
        state = json.dumps({"api_state": await api.api_state(), "api_home": await api.api_home(), "api_jobs": await api.api_jobs(),
                            "api_found": await api.api_found(), "api_answers": await api.api_answers(),
                            "api_tables": await api.api_tables()}, default=str)
        js = f"const R = {state}; " + "".join(
            f"window.{n} = async () => (R.{n} !== undefined ? R.{n} : {{ok: true}});" for n in stub)
        async with async_playwright() as p:
            b = await p.chromium.launch()
            page = await b.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.add_init_script(js)
            await page.goto((ROOT / "ui" / "index.html").as_uri())
            await page.wait_for_timeout(800)
            for n in range(1, 7):
                await page.keyboard.press(str(n))
                await page.wait_for_timeout(150)
            await b.close()
            return errors
    try:
        errors = asyncio.run(load())
        check(not errors, "UI loads and every page opens without JavaScript errors" + (f": {errors[:3]}" if errors else ""))
    except Exception as e:
        print(f"  skip browser check ({str(e).splitlines()[0][:80]})")


if __name__ == "__main__":
    main()
    print("\nRESULT:", "all good" if not FAILS else f"{len(FAILS)} problem(s)")
    sys.exit(1 if FAILS else 0)
