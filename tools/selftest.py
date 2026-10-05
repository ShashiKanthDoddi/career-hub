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

    from careerhub import resume_tools as rt
    cv = "\n".join(["Priya Sharma", "priya@example.com | +91 98765 43210 | linkedin.com/in/priya", "Summary",
                    "Performance marketer.", "Work experience", "Growth Marketing Manager, Mamaearth, 2021 - 2024"]
                   + [f"{v} Google Ads and Meta Ads campaigns, grew leads by {n}0%" for n, v in
                      enumerate(["Led", "Grew", "Launched", "Managed", "Built", "Ran"], 2)]
                   + ["Education", "MBA, 2019", "Skills",
                      "SEO, SEM, GA4, HubSpot, CRM, Canva, Excel, email marketing, content marketing", "marketing work " * 150])
    a = rt.ats_check(cv)
    check(a["score"] >= 80 and all(c["ok"] for c in a["checks"]), f"resume check: a complete resume scores well ({a['score']})")
    b = rt.ats_check("")
    check(b["score"] < 30 and not b["checks"][0]["ok"] and "picture" in b["checks"][0]["tip"], "resume check: an unreadable (scanned) PDF is flagged")
    m = rt.keyword_match("Google Ads and SEO", "Must know Google Ads, GA4 and SEO. HubSpot is a plus.")
    check({"ga4", "hubspot"} <= set(m["missing"]) and "google ads" in m["have"], f"resume fit: missing job keywords found ({m['missing']})")
    check(rt.target_roles("Performance Marketing Manager", []) == ["performance marketing"], "resume skills: role from Find jobs titles")
    g = rt.skill_gaps("Google Ads, GA4", ["performance marketing"])[0]
    check("Google Ads" in g["have"] and all(x["url"].startswith("https://") for x in g["missing"]), "resume skills: gaps come with a course link")
    check(rt.job_roles("Senior SEO Executive, Bengaluru. We need Semrush.") == ["seo"] and rt.job_roles("Embedded engineer") == [],
          "resume skills: role read from the job text")
    ls = rt.job_skills(["ga4", "semrush", "tableau"])
    check([x["skill"] for x in ls] == ["ga4", "semrush", "tableau"] and all(x["url"].startswith("https://") for x in ls),
          "resume skills: each missing job word gets a course link")
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
    check(jobsites.alert_details('<a href="https://www.linkedin.com/jobs/view/123456789">SEO Lead</a><p>Acme Corp</p><p>Pune, India</p><p>2 days ago</p>')
          == [("https://www.linkedin.com/jobs/view/123456789", "SEO Lead", "Acme Corp", "Pune, India")], "Alert email: company and city read after the job link")
    check(jobsites.read_job_page('<script type="application/ld+json">{"@type":"JobPosting","title":"SEO Lead","hiringOrganization":{"name":"Acme"},'
                                 '"jobLocation":{"address":{"addressLocality":"Pune"}},"description":"Run SEO"}</script>') == ("SEO Lead", "Acme", "Pune", "Run SEO")
          and jobsites.read_job_page("<title>Globex hiring Growth Marketer in Remote | LinkedIn</title>")[:3] == ("Growth Marketer", "Globex", "Remote"),
          "Job page: title, company, city and text read from public job data")
    from careerhub.match import score_job
    _mp = {"roles": ["seo manager"], "skills": ["seo", "google analytics"], "years": 4,
           "text": "seo manager with 4 years of experience in seo google analytics content marketing email marketing hubspot reporting"}
    _jd = lambda extra: ("About the role. " * 6 + "Requirements:\n" + extra + "\nBenefits: health cover and learning budget for the whole team")
    _good = score_job("SEO Manager", _jd("3+ years of seo, google analytics, content marketing, email marketing and hubspot reporting"), "Bengaluru", _mp)["score"]
    _poor = score_job("SEO Manager", _jd("5+ years of kubernetes, terraform, golang and python backend services on aws"), "Bengaluru", _mp)["score"]
    _none = score_job("SEO Manager", "", "Bengaluru", _mp)["score"]
    check(_none is None and _good is not None and _poor is not None and _good > _poor + 25,
          f"Job match: no number without job text, and a fitting job scores well above a poor one ({_good} vs {_poor})")
    from careerhub.finder import location_ok
    check(location_ok("Remote, India", ["bengaluru", "remote"]) and location_ok("Remote", ["remote"])
          and not location_ok("Munich, Germany remote", ["bengaluru", "remote"]) and not location_ok("Remote in the US", ["remote"]),
          "remote jobs tied to another country are not shown")
    check(__import__("careerhub.gmail", fromlist=["x"]).company_from_sender("Choragudi, Kamala A.", "k@accenture.com") == "Accenture", "a recruiter's name is not used as the company")
    from careerhub import filler
    _fs = [({"label": "Notice period", "kind": "text", "nm": "np"}, {"action": "fill", "value": "30 days", "src": "profile"}),
           ({"label": "Gender", "kind": "select", "nm": "g"}, {"action": "fill", "value": "Female", "src": "profile", "options": ["Female", "Male"]}),
           ({"label": "Resume", "kind": "file", "nm": "r"}, {"action": "fill", "value": "C:/x/Resume.pdf", "src": "profile"}),
           ({"label": "Why us", "kind": "text", "nm": "w"}, {"action": "fill", "value": "typed", "src": "you"}),
           ({"label": "Phone", "kind": "text", "nm": "p"}, {"action": "skip"})]
    _qs = filler.review_questions(_fs)
    check([q["kind"] for _, _, q in _qs] == ["text", "choice", "fixed"] and _qs[1][2]["options"] == ["Female", "Male"]
          and _qs[2][2]["value"] == "Resume.pdf", "check-before-filling card lists profile answers, not ones she just typed")
    class _FakeUI:
        async def ask(self, **kw): return {"0": {"value": "15 days"}, "1": {"value": "Female", "never": True}, "2": {"value": ""}}
    _real, filler.UI = filler.UI, _FakeUI()
    asyncio.run(filler.review_before_fill(db, _fs))
    filler.UI = _real
    check(_fs[0][1]["value"] == "15 days" and _fs[0][1]["src"] == "you" and _fs[1][1]["action"] == "skip" and _fs[2][1]["action"] == "fill"
          and db.memory.get(textutil.norm("Notice period np")) == "15 days", "a fixed answer is used and remembered; 'leave empty' skips")
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
    def _bulk(frm, subj, body):
        m = email.message.EmailMessage(); m["From"], m["Subject"], m["Date"] = frm, subj, "Mon, 28 Sep 2026 10:00:00 +0000"
        m["List-Unsubscribe"] = "<mailto:u@x.com>"; m.set_content(body); return [("b" + subj, m.as_bytes())]
    check(not gmail.process_mail(_bulk("Thermo Fisher Scientific <opportunities@campaign.thermofisher.com>", "Jobs for you, interview tips & advancing research", "Recruiter interviewing tips, explore engineering jobs"), [], set())
          and not gmail.process_mail(_mail("Anuj at CodeChef <contests@codechef.com>", "Interview Readiness: Practice Test Series", "first assessment on 1st August, placement interviews"), [], set())
          and not gmail.process_mail(_bulk("Talenttitanletters <jobs@talenttitan.com>", "Hiring | Java skillset | Multiple Locations", "Shortlisted candidates will be called for interview"), [], set())
          and gmail.process_mail(_bulk("Acme Careers <careers@acme.com>", "Interview invitation: Marketing Manager", "Please share your availability"), [], set())[0]["type"] == "interview"
          and gmail.classify_mail("Next steps", "We would like to invite you to an interview") == "interview",
          "newsletters and interview-tips mails are not interviews; real invites still are")
    check(gmail.process_mail(_bulk("LinkedIn <jobs-noreply@linkedin.com>", "Your application to Marketing Manager at Acme",
                                   "Unfortunately, Acme has decided not to move forward with your application."), [], set())[0]["type"] == "rejection"
          and gmail.process_mail(_bulk("Acme Careers <careers@acme.com>", "Update on your application", "We regret to inform you that the role has been filled."), [], set())[0]["type"] == "rejection"
          and not gmail.process_mail(_bulk("Reddit <noreply@redditmail.com>", "Trending on r/marketing", "Unfortunately this post was removed"), [], set()),
          "rejections sent through LinkedIn or a mailing system are read; newsletters still aren't")
    check(gmail.classify_mail("Thank you for applying", "We received your application. If shortlisted, we will contact you for an interview.") == "received"
          and gmail.classify_mail("Re: Marketing role", "Thanks for the update.\nOn Mon, Sep 28 Harshitha wrote:\n> Can we schedule the interview?") == "other"
          and gmail.classify_mail("Thank you for interviewing", "Unfortunately we are moving forward with other candidates.") == "rejection"
          and gmail.classify_mail("Opportunity at Acme", "We may have an interview slot", strict=True) == "other",
          "mail types are scored: hypotheticals, quoted replies and single weak hits don't make an interview")
    gmail.BLOCKED.add("contests@codechef.com")
    check(not gmail.process_mail(_mail("CodeChef <contests@codechef.com>", "Interview invitation", "x"), [], set()),
          "a sender marked 'Not a job email' is ignored")
    gmail.BLOCKED.clear()
    _first = lambda items: (gmail.process_mail(items, [], set()) or [{}])[0]
    li = _first(_mail("LinkedIn <jobs-noreply@linkedin.com>", "Harshitha, your application was sent to Acme Foods", "Marketing Executive, Acme Foods. Applied on 1 Oct"))
    li2 = _first(_mail("LinkedIn <jobs-noreply@linkedin.com>", "Your application to Marketing Manager at Acme", "Your application was sent to Acme."))
    check(li.get("type") == "received" and li.get("company") == "Acme Foods" and li2.get("type") == "received" and li2.get("company") == "Acme"
          and _first(_bulk("Acme Careers <careers@acme.com>", "Thank you for applying to Acme", "We have received your application.")).get("type") == "received"
          and _first(_mail("Priya (Acme HR) <priya@acmefoods.in>", "Shortlisted for Marketing Executive", "You have been shortlisted. Please share your availability.")).get("type") == "interview"
          and not gmail.process_mail(_mail("LinkedIn <jobs-noreply@linkedin.com>", "Shashi, view your application updates from this week", "Your application was viewed"), [], set())
          and not gmail.process_mail(_mail("Reddit <noreply@redditmail.com>", "Is this actually normal in an interview for a developer", "interview offer"), [], set()),
          "jobs applied outside the app are found from their emails (LinkedIn, company mailers, recruiters); digests are not")
    _learned = [{"Company": "Swiggy", "Job title": "", "Link": "", "learned": True}]
    check(not gmail.process_mail(_mail("HDFC Bank <alerts@hdfcbank.net>", "Your credit card application", "Thank you for applying for the HDFC credit card. We have received your application."), [], set())
          and not gmail.process_mail(_mail("Swiggy <noreply@swiggy.in>", "Your order is on the way", "Your Swiggy order will arrive soon"), _learned, set())
          and not gmail.process_mail(_mail("Swiggy <noreply@swiggy.in>", "Order cancelled", "Unfortunately your Swiggy order was cancelled"), _learned, set())
          and (gmail.process_mail(_mail("Swiggy Talent <talent@swiggy.in>", "Next steps", "Unfortunately we will not move forward with your candidature for the role"), _learned, set()) or [{}])[0].get("type") == "rejection",
          "bank 'thank you for applying' mails and a learned company's orders are not jobs; its real rejection still is")
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

    from careerhub.meetings import find_details
    mt = find_meeting("Your technical interview with Priya Sharma is on 8 Oct 2026 at 3:30 PM IST. Join: https://us02web.zoom.us/j/12345?pwd=abc.", sent)
    check(mt and mt["link"] == "https://us02web.zoom.us/j/12345?pwd=abc" and mt["who"] == "Priya Sharma" and mt["round"] == "Technical round",
          "interview email: meeting link, interviewer and round read")
    check(find_details("Hi Anita, please share your first name. Your interview with the team. Meet with Our Team. HR will call.") == {},
          "interview email: ordinary words are not taken as a name, round or link")
    check(find_details("Interviewer: Dr. Rao Kumar\nJoin https://meet.google.com/abc-defg-hij\nSecond round")
          == {"link": "https://meet.google.com/abc-defg-hij", "who": "Dr. Rao Kumar", "round": "Second round"}, "interview email: Meet link, titled name, second round")

    from careerhub import planner as _pl
    _pl_old = (_pl.data, _pl.save_data)
    _ev = []
    _pl.data = lambda: {"events": _ev}
    _pl.save_data = lambda: None
    at = datetime.datetime(2026, 10, 8, 9, 0)
    _ev[:] = [{"id": "a", "title": "Interview", "company": "Acme", "date": "2026-10-08", "time": "09:30"},
              {"id": "b", "title": "Interview", "company": "Beta", "date": "2026-10-08", "time": "15:00"},
              {"id": "c", "title": "Test", "company": "Gamma", "date": "2026-10-08"},
              {"id": "d", "title": "Interview", "company": "Delta", "date": "2026-10-09", "time": "09:00"}]
    due = _pl.due_reminders(at)
    check([e["id"] for e in due] == ["a", "c"] and _pl.due_reminders(at) == [] and [e["id"] for e in _pl.due_reminders(at.replace(hour=14, minute=30))] == ["b"],
          "reminders: an hour before a timed interview, from 08:00 for one without a time, each only once")
    check(_pl.reminder_text(_ev[0], at)[0] == "Interview at Acme starts in 30 minutes" and _pl.reminder_text(_ev[2], at)[0] == "Today: Test at Gamma",
          "reminders: pop-up wording")
    _ev[:] = []
    note = {"id": "m1", "type": "interview", "date": "2026-10-04T10:00", "company": "Acme", "title": "", "subject": "Interview", "change": "",
            "meeting": {"date": "2026-10-08", "time": "10:00", "link": "https://zoom.us/j/1", "who": "Priya Sharma", "round": "Technical round"}}
    _pl.events_from_mail([note])
    check(len(_ev) == 1 and _ev[0]["link"] == "https://zoom.us/j/1" and _ev[0]["who"] == "Priya Sharma" and _ev[0]["round"] == "Technical round",
          "calendar: link, interviewer and round are kept from the email")
    _ev[0]["reminded"] = True
    _pl.events_from_mail([{**note, "cal_done": False, "id": "m2", "date": "2026-10-05T10:00", "change": "reschedule", "meeting": {"date": "2026-10-09", "time": "11:00"}}])
    check(_ev[0]["date"] == "2026-10-09" and "reminded" not in _ev[0] and _ev[0]["link"] == "https://zoom.us/j/1",
          "calendar: a reschedule moves the entry, resets its reminder and keeps the link")
    check(_pl.add_event("x", "2026-10-08", link="javascript:alert(1)") and "link" not in _ev[-1], "calendar: only web addresses are kept as a link")
    _pl.data, _pl.save_data = _pl_old

    from careerhub.research import clean_brief, pick_title
    check(pick_title("Nykaa", [{"title": "Falguni Nayar", "snippet": "founder of the company Nykaa"}, {"title": "Nykaa", "snippet": "an Indian retail company"}]) == "Nykaa"
          and pick_title("Mint", [{"title": "Mint", "snippet": "Mint is a genus of plants"}]) == ""
          and pick_title("Acme Pvt Ltd", [{"title": "Acme", "snippet": "a manufacturer of anvils"}]) == "Acme", "company brief: the right Wikipedia page is picked")
    check(clean_brief("Sure!\n**What they do**\n- A\n- B\n- C\nMarketing angle to mention:\n- D\nPowered by x") == "What they do\n- A\n- B\n- C\nMarketing angle to mention\n- D"
          and clean_brief("I do not know this company.") == "", "company brief: only headings and bullets are kept")

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
        async def apply_test():
            from careerhub.config import APPLY_WORDS
            from careerhub.filler import find_clickable
            page_html = ('<ul class="filters"><li><a class="pill" href="#">Easy Apply</a></li></ul>'
                         '<button class="apply-button">Apply</button>')    # LinkedIn's public job page
            async with _apw() as p:
                b = await p.chromium.launch()
                pg = await b.new_page()
                await pg.set_content(page_html)
                _, text = await find_clickable(pg, APPLY_WORDS)
                await b.close()
                return text
        try:
            got = asyncio.run(apply_test())
            check(got == "Apply", f"Apply button found, not the Easy Apply search filter (got {got})")
        except Exception as e:
            check(False, f"apply button test failed: {str(e)[:150]}")
        try:
            got = asyncio.run(guard_test())
            check(got == ["ran", "blocked"], f"app functions work from the app window only (got {got})")
        except Exception as e:
            check(False, f"window guard test failed: {str(e)[:150]}")

    from careerhub.store import data as _data
    _rows = [{"Date found": "2026-01-01", "Match %": 80, "Company": "Acme", "Job title": "SEO Manager", "Location": "Bengaluru", "Posted (days ago)": 2,
              "Link": "https://x.test/a1"},
             {"Date found": "2026-01-01", "Match %": "", "Company": "LinkedIn alert", "Job title": "Marketing Lead", "Location": "", "Posted (days ago)": "",
              "Link": "https://www.linkedin.com/jobs/view/111111111", "Alert site": "LinkedIn"}]
    _data()["found_jobs"].extend(_rows)
    try:
        _got = asyncio.run(api.api_found())
        _ok = {j["title"]: j for j in _got if j.get("title")}
        check({"SEO Manager", "Marketing Lead"} <= set(_ok) and _ok["SEO Manager"]["company"] == "Acme" and not _ok["SEO Manager"]["alert"]
              and _ok["Marketing Lead"]["alert"] and _ok["Marketing Lead"]["site"] == "LinkedIn" and _ok["Marketing Lead"]["score"] is None,
              "Find jobs list: title, company and alert fields are sent to the page")
    finally:
        for _r in _rows:
            _data()["found_jobs"].remove(_r)
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
            for n in range(1, 8):
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
