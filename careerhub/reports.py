"""reports module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import quote
import re
import asyncio
import base64
import datetime
import email.utils
import json
import os
import platform
import shutil
import smtplib
import subprocess
import sys
import webbrowser
import zipfile
from .bridge import LOG, UI, log, os_open
from .config import APP_NAME, APP_VERSION, DRAFT_DIR, OWNER, REPORT_DIR, ISSUES_SOURCE
from .gmail import mail_settings
from .records import tracker_rows
from .state import JOB, PW
from .store import load_profile
from .textutil import mask


IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")
MAX_IMAGES, MAX_IMAGE_BYTES = 5, 5_000_000


def decode_images(images):
    """[{name, data (base64)}] from the window -> [(safe file name, bytes)]; at most 5, each under 5 MB."""
    out = []
    for i, im in enumerate((images or [])[:MAX_IMAGES], 1):
        try:
            raw = base64.b64decode(str(im.get("data") or ""))
        except Exception:
            continue
        ext = os.path.splitext(str(im.get("name") or ""))[1].lower()
        if raw and len(raw) <= MAX_IMAGE_BYTES:
            out.append((f"picture_{i}{ext if ext in IMG_EXT else '.png'}", raw))
    return out


async def make_report(note, pictures=()):
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
    for name, raw in pictures:
        (folder / name).write_bytes(raw)
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
    attach = {}                      # what goes on GitHub: the log and pictures, not info.txt
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.iterdir():
            z.write(f, f.name)
            if f.name == "activity_log.txt" or f.suffix.lower() in IMG_EXT:
                attach[f.name] = f.read_bytes()
    shutil.rmtree(folder, ignore_errors=True)
    return zpath, attach


def smtp_send(addr, pw, to, subject, body, attachment):
    msg = email.message.EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = addr, to, subject
    msg.set_content(body)
    msg.add_attachment(attachment.read_bytes(), maintype="application", subtype="zip", filename=attachment.name)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(addr, pw)
        s.send_message(msg)


def issue_repo():
    m = re.match(r"(?:https://github\.com/)?([\w.-]+/[\w.-]+?)(?:@.*|\.git)?/?$", str(ISSUES_SOURCE or "").strip())
    return m.group(1) if m else ""


class GhError(Exception):
    def __init__(self, code, text=""):
        super().__init__(f"HTTP {code} {text}".strip())
        self.code = code


FILES_BRANCH = "issue-files"


async def gh_call(method, url, token, payload=None):
    """One GitHub API call. Uses Playwright's request client (like the updater), because Python's own
    urllib often has no root certificates on a Mac (SSL: CERTIFICATE_VERIFY_FAILED)."""
    ctx = await PW["p"].request.new_context(extra_http_headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "CareerHub"})
    try:
        r = await ctx.fetch(url, method=method, timeout=60000, data=None if payload is None else json.dumps(payload),
                            headers={"Content-Type": "application/json"})
        if not r.ok:
            raise GhError(r.status, (await r.text())[:100])
        return await r.json()
    finally:
        await ctx.dispose()


async def github_issue(repo, token, title, body, label):
    """Create an issue on GitHub. Returns its web link."""
    r = await gh_call("POST", f"https://api.github.com/repos/{repo}/issues", token,
                      {"title": title[:200], "body": body[:60000], "labels": [label]})
    return r.get("html_url", "")


async def upload_files(repo, token, folder, files):
    """GitHub's API can't attach files to an issue, so they go on a side branch of the repo and the issue links them.
    Returns [(name, raw link, page link)]."""
    api = f"https://api.github.com/repos/{repo}"
    try:
        await gh_call("GET", f"{api}/git/ref/heads/{FILES_BRANCH}", token)
    except GhError as e:
        if e.code != 404:
            raise
        base = (await gh_call("GET", api, token)).get("default_branch", "main")
        sha = (await gh_call("GET", f"{api}/git/ref/heads/{base}", token))["object"]["sha"]
        await gh_call("POST", f"{api}/git/refs", token, {"ref": f"refs/heads/{FILES_BRANCH}", "sha": sha})
    out = []
    for name, raw in files.items():
        path = f"{folder}/{name}"
        await gh_call("PUT", f"{api}/contents/{path}", token, {"message": f"Files for {folder}", "branch": FILES_BRANCH,
                                                                "content": base64.b64encode(raw).decode("ascii")})
        out.append((name, f"https://raw.githubusercontent.com/{repo}/{FILES_BRANCH}/{path}",
                    f"https://github.com/{repo}/blob/{FILES_BRANCH}/{path}"))
    return out


def files_markdown(uploaded):
    lines = ["", "", "**Attached**"]
    for name, raw, page in uploaded:
        lines.append(f"![{name}]({raw})" if name.lower().endswith(IMG_EXT) else f"- [{name}]({page})")
    return "\n".join(lines)


async def file_issue(kind, title, body, open_page=True, files=None):
    """kind: 'bug' or 'enhancement'. With a GitHub token in Settings the issue is created in the private ISSUES_SOURCE repo;
    without one a report goes by email and an idea is refused (the repo is private, so no web page to open)."""
    repo = issue_repo()
    if not repo:
        return {"ok": False, "error": "No GitHub repository is set up."}
    token = str((load_profile().get("settings") or {}).get("github_token") or "").strip()
    why = "no GitHub token in Settings"
    if token:
        try:
            if files:
                try:
                    folder = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
                    body += files_markdown(await upload_files(repo, token, folder, files))
                except Exception as e:
                    log(f"⚠  Couldn't attach files to the GitHub issue ({str(e)[:120]}).")
                    body += "\n\n(Files could not be attached.)"
            url = await github_issue(repo, token, title, body, kind)
            log(f"📨 GitHub issue created ({kind}): {url}")
            return {"ok": True, "created": True, "url": url}
        except Exception as e:
            why = f"GitHub said no ({str(e)[:100]})"
            if isinstance(e, GhError):
                why = {401: "the token is wrong or has expired", 403: "the token is missing permission (Issues and Contents)",
                       404: "the token can't reach the reports repository"}.get(e.code, f"GitHub error {e.code}")
            log(f"⚠  Couldn't create the GitHub issue ({str(e)[:120]}).")
    if not token:
        log("⚠  No GitHub token in Settings, so nothing was sent to GitHub.")
    if not open_page:                                  # a report falls back to email
        return {"ok": True, "created": False, "why": why}
    return {"ok": False, "error": f"Couldn't send it: {why}. Please ask your helper." if token else
            "Sending ideas isn't set up on this computer yet (no GitHub token in Settings). Please ask your helper."}


async def send_suggestion(text, images=None):
    text = str(text or "").strip()
    if not text:
        return {"ok": False, "error": "Please write your idea first."}
    title = text.splitlines()[0][:70]
    return await file_issue("enhancement", f"Suggestion: {title}",
                            f"{text}\n\n---\nFrom {OWNER} · {APP_NAME} {APP_VERSION}", files=dict(decode_images(images)))


async def send_report(note, images=None):
    zpath, attach = await make_report(note, decode_images(images))
    ms = mail_settings()
    tail = ""
    if LOG["file"] and LOG["file"].exists():
        tail = "\n".join(LOG["file"].read_text(encoding="utf-8").splitlines()[-60:])
    subject = f"Career Hub problem report from {OWNER} ({APP_VERSION})"
    body = f"{note or '(no description)'}\n\n--- last activity ---\n{tail}"
    first = (note or "Problem report").strip().splitlines()[0][:70]
    r = await file_issue("bug", f"Bug: {first}", f"{note or '(no description)'}\n\n{APP_NAME} {APP_VERSION} · "
                         f"{platform.platform()}\n\n<details><summary>Last activity</summary>\n\n```\n{tail[-2500:]}\n```\n</details>", open_page=False, files=attach)
    if r.get("created"):
        return {**r, "sent": False, "issue": True, "path": str(zpath)}
    why = r.get("why", "")
    if ms["addr"] and ms["pw"] and ms["helper"]:
        try:
            await asyncio.to_thread(smtp_send, ms["addr"], ms["pw"], ms["helper"], subject, body, zpath)
            log(f"📨 Problem report sent to {ms['helper']}.")
            return {"ok": True, "sent": True, "to": ms["helper"], "why": why}
        except Exception as e:
            log(f"⚠  Couldn't email the report ({str(e)[:120]}). Saved it instead.")
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(zpath)])
    else:
        os_open(zpath.parent)
    if ms["helper"]:
        webbrowser.open("https://mail.google.com/mail/?view=cm&fs=1&to=" + quote(ms["helper"]) + "&su=" +
                        quote(subject) + "&body=" + quote(body[:1800]))
    return {"ok": True, "sent": False, "path": str(zpath), "helper": ms["helper"], "why": why}
