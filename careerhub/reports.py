"""reports module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
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
from .config import APP_NAME, APP_VERSION, DRAFT_DIR, OWNER, REPORT_DIR
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


async def send_report(note):
    zpath = await make_report(note)
    ms = mail_settings()
    tail = ""
    if LOG["file"] and LOG["file"].exists():
        tail = "\n".join(LOG["file"].read_text(encoding="utf-8").splitlines()[-60:])
    subject = f"Career Hub problem report from {OWNER} ({APP_VERSION})"
    body = f"{note or '(no description)'}\n\n--- last activity ---\n{tail}"
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
