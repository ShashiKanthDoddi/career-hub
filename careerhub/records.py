"""records module of Career Hub. See MAP.md for what lives where."""
from pathlib import Path
from urllib.parse import urlparse
import datetime
import re
from .store import data, save_data
from .textutil import norm, norm_link


def known_companies():
    return {(r.get("Company") or "").strip() for r in tracker_rows() if (r.get("Company") or "").strip()}


def answer_mentions_other_company(ans, company):
    a = (ans or "").lower()
    me = (company or "").lower().strip()
    for c in known_companies():
        c2 = c.lower()
        if len(c2) >= 3 and c2 != me and c2 not in ("linkedin job", "job") and re.search(rf"\b{re.escape(c2)}\b", a):
            return True
    return False


def already_applied_same_job(company, title, link):
    if not company or not title or len(title) < 6 or title.lower() == "job":
        return None
    for r in tracker_rows():
        if (norm(r.get("Company")) == norm(company) and norm(r.get("Job title")) == norm(title)
                and norm_link(r.get("Link")) != norm_link(link) and (r.get("Status") or "").startswith("Submitted")):
            return r.get("Date", "")
    return None


ACCOUNT_COLS = ["Date", "Company", "Website", "Email", "Password", "What happened"]


def account_rows():
    return list(data()["accounts"])


def saved_password(host):
    """Latest password used successfully on this website (from the accounts list)."""
    for r in reversed(account_rows()):
        if (r.get("Website") or "").lower() == host and (r.get("Password") or "").strip():
            return r["Password"].strip()
    return None


def log_account(company, host, email_addr, pw, action):
    data()["accounts"].append({"Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Company": company,
                               "Website": host, "Email": email_addr, "Password": pw, "What happened": action})
    save_data()


def save_default_password(pw):
    data()["profile"]["settings"]["job_site_password"] = pw
    save_data()


TRACKER_COLS = ["Date", "Company", "Job title", "Status", "Link", "Summary file"]


def tracker_rows():
    return list(data()["applications"])


def tracker_add(company, title, status, link, summary):
    data()["applications"].append({"Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "Company": company,
                                   "Job title": title, "Status": status, "Link": link,
                                   "Summary file": Path(summary).name if summary else ""})
    save_data()


def already_applied(link):
    for r in tracker_rows():
        if norm_link(r.get("Link")) == norm_link(link) and (r.get("Status") or "").startswith("Submitted"):
            return r.get("Date", "")
    return None


def guess_company(url, page_title=""):
    u = urlparse(url)
    host = u.netloc.lower().split(":")[0]
    parts = [x for x in u.path.split("/") if x]
    if "linkedin.com" in host:
        bits = [b.strip() for b in page_title.split("|")]
        return bits[1] if len(bits) >= 3 else "LinkedIn job"
    if "myworkdayjobs" in host or "workday" in host or "bamboohr" in host:
        return host.split(".")[0].replace("-", " ").title()
    if any(h in host for h in ("greenhouse.io", "lever.co", "ashbyhq.com", "smartrecruiters.com", "workable.com")):
        return parts[0].replace("-", " ").title() if parts else host
    skip = {"www", "careers", "career", "jobs", "job", "apply", "com", "co", "in", "io", "org", "net", "uk"}
    labels = [l for l in host.split(".") if l not in skip]
    return labels[0].replace("-", " ").title() if labels else host


def read_jobs_file():
    seen, links = set(), []
    for l in data()["saved_links"]:
        if l.startswith("http") and norm_link(l) not in seen:
            seen.add(norm_link(l))
            links.append(l)
    return links


def seen_links():
    s_ = {norm_link(r.get("Link")) for r in tracker_rows()}
    s_ |= {norm_link(r.get("Link")) for r in data()["found_jobs"]}
    s_ |= {norm_link(l) for l in read_jobs_file()}
    return s_


def save_found(jobs):
    for j in jobs:
        data()["found_jobs"].append({"Date found": datetime.datetime.now().strftime("%Y-%m-%d"), "Match %": j["score"],
                                     "Company": j["company"], "Job title": j["title"], "Location": j["location"],
                                     "Posted (days ago)": "" if j["age"] is None else j["age"], "Link": j["link"]})
    save_data()


def add_to_jobs_file(links):
    have = {norm_link(l) for l in data()["saved_links"]}
    for l in links:
        if norm_link(l) not in have:
            data()["saved_links"].append(l)
            have.add(norm_link(l))
    save_data()
