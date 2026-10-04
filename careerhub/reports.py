"""reports module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
import urllib.request
import re
import asyncio
import datetime
import email.utils
import json
import platform
import shutil
import smtplib
import subprocess
import sys
import webbrowser
import zipfile
from .bridge import LOG, UI, log, os_open
from .config import APP_NAME, APP_VERSION, DRAFT_DIR, OWNER, REPORT_DIR, UPDATE_SOURCE
from .gmail import mail_settings
from .records import tracker_rows
from .state import JOB
from .store import load_profile
from .textutil import mask


async def make_report(note):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder = REPORT_DIR / f"report_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    if LOG["file"] and LOG["file"].exists():
        shutil.copy2(LOG["file"], folder / "activity_log.txt")
    try:
        if UI.page:
            await UI.page.screenshot(path=str(folder / "app_window.png"))
    except Exception:
        pass
    try:
        if JOB["ctx"] and JOB["ctx"].pages:
            await JOB["ctx"].pages[-1].screenshot(path=str(folder / "job_window.png"))
    except Exception:
        pass
    if DRAFT_DIR.exists():
        sums = sorted(DRAFT_DIR.glob("*.html"))
        if sums:
            shutil.copy2(sums[-1], folder / sums[-1].name)
    try:
        st = load_profile().get("settings") or {}
    except Exception:
        st = {}
    safe = {k: (mask(v) if any(w in k for w in ("password", "key")) else v) for k, v in st.items()}
    info = [f"{APP_NAME} {APP_VERSION}", f"Computer: {platform.platform()}", f"Python: {platform.python_version()}",
            f"Time: {stamp}", "", "What happened (from the user):", note or "(no description)", "",
            "Settings (secrets hidden):", json.dumps(safe, indent=2, ensure_ascii=False), "",
            "Last 5 applications:"] + [" | ".join([r.get("Date", ""), r.get("Company", ""), r.get("Job title", ""),
                                                   r.get("Status", ""), r.get("Link", "")]) for r in tracker_rows()[-5:]]
    (folder / "info.txt").write_text("\n".join(info), encoding="utf-8")
    zpath = REPORT_DIR / f"problem_report_{stamp}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.iterdir():
            z.write(f, f.name)
    shutil.rmtree(folder, ignore_errors=True)
    return zpath


def smtp_send(addr, pw, to, subject, body, attachment):
    msg = email.message.EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = addr, to, subject
    msg.set_content(body)
    msg.add_attachment(attachment.read_bytes(), maintype="application", subtype="zip", filename=attachment.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(addr, pw)
        s.send_message(msg)


def issue_repo():
    m = re.match(r"(?:https://github\.com/)?([\w.-]+/[\w.-]+?)(?:@.*|\.git)?/?$", str(UPDATE_SOURCE or "").strip())
    return m.group(1) if m else ""


def github_issue(repo, token, title, body, label):
    """Create an issue on GitHub. Returns its web link."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues", method="POST",
        data=json.dumps({"title": title[:200], "body": body[:60000], "labels": [label]}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "CareerHub"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("html_url", "")


async def file_issue(kind, title, body, open_page=True):
    """kind: 'bug' or 'enhancement'. With a GitHub token in Settings the issue is created directly;
    without one, GitHub's new-issue page opens with everything filled in."""
    repo = issue_repo()
    if not repo:
        return {"ok": False, "error": "No GitHub repository is set up."}
    token = str((load_profile().get("settings") or {}).get("github_token") or "").strip()
    if token:
        try:
            url = await asyncio.to_thread(github_issue, repo, token, title, body, kind)
            log(f"📨 GitHub issue created ({kind}): {url}")
            return {"ok": True, "created": True, "url": url}
        except Exception as e:
            log(f"⚠  Couldn't create the GitHub issue ({str(e)[:120]}).")
    if not open_page:
        return {"ok": True, "created": False}
    webbrowser.open(f"https://github.com/{repo}/issues/new?labels={kind}&title={quote(title[:200])}&body={quote(body[:3000])}")
    return {"ok": True, "created": False}


async def send_suggestion(text):
    text = str(text or "").strip()
    if not text:
        return {"ok": False, "error": "Please write your idea first."}
    title = text.splitlines()[0][:70]
    return await file_issue("enhancement", f"Suggestion: {title}",
                            f"{text}\n\n---\nFrom {OWNER} · {APP_NAME} {APP_VERSION}")


async def send_report(note):
    zpath = await make_report(note)
    ms = mail_settings()
    tail = ""
    if LOG["file"] and LOG["file"].exists():
        tail = "\n".join(LOG["file"].read_text(encoding="utf-8").splitlines()[-60:])
    subject = f"Career Hub problem report from {OWNER} ({APP_VERSION})"
    body = f"{note or '(no description)'}\n\n--- last activity ---\n{tail}"
    first = (note or "Problem report").strip().splitlines()[0][:70]
    r = await file_issue("bug", f"Bug: {first}", f"{note or '(no description)'}\n\n{APP_NAME} {APP_VERSION} · "
                         f"{platform.platform()}\n\n<details><summary>Last activity</summary>\n\n```\n{tail[-2500:]}\n```\n</details>", open_page=False)
    if r.get("created"):
        return {**r, "sent": False, "issue": True, "path": str(zpath)}
    if ms["addr"] and ms["pw"] and ms["helper"]:
        try:
            await asyncio.to_thread(smtp_send, ms["addr"], ms["pw"], ms["helper"], subject, body, zpath)
            log(f"📨 Problem report sent to {ms['helper']}.")
            return {"ok": True, "sent": True, "to": ms["helper"]}
        except Exception as e:
            log(f"⚠  Couldn't email the report ({str(e)[:120]}). Saved it instead.")
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(zpath)])
    else:
        os_open(zpath.parent)
    if ms["helper"]:
        webbrowser.open("https://mail.google.com/mail/?view=cm&fs=1&to=" + quote(ms["helper"]) + "&su=" +
                        quote(subject) + "&body=" + quote(body[:1800]))
    return {"ok": True, "sent": False, "path": str(zpath), "helper": ms["helper"]}
