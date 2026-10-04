"""updater: automatic updates from GitHub (checked at start, hourly, and from Settings).

A release = release.json + the files it lists, in a GitHub repo (made by tools/make_release.py).
Install: download every file, check its SHA-256 and that Python files compile, back up the current files
and data, copy the new files in, then restart. If the new version crashes on start, career_hub.py
(the bootstrap) restores the backup automatically. Her data folder is never replaced.
"""
import datetime
import hashlib
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath
from .bridge import log
from .config import APP_VERSION, BASE, DATA, UPDATE_SOURCE
from .state import PW, UPDATE
from .store import backup_data, data, save_app_state

UPDATE_DIR = DATA / ".update"
PENDING = UPDATE_DIR / "pending.json"            # written before restarting into a new version
ROLLED_BACK = UPDATE_DIR / "rolled_back.json"    # written by career_hub.py if the new version failed
ALLOWED = ("career_hub.py", "careerhub/", "ui/", "tools/", "CLAUDE.md", "MAP.md", "README.md",
           "Setup (Mac).command", "Open Career Hub (Mac).command", "Setup (Windows).bat", "Open Career Hub (Windows).bat")


def vt(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))) or (0,)


def source_base():
    """Raw-file base URL from 'owner/repo', 'owner/repo@branch', a github.com link or a raw URL."""
    s = str(data()["profile"]["settings"].get("update_source") or UPDATE_SOURCE or "").strip()
    if not s:
        return ""
    m = re.fullmatch(r"([\w.-]+/[\w.-]+)(?:@([\w./-]+))?", s)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2) or 'main'}/"
    m = re.match(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?(?:/tree/([\w./-]+))?/?$", s)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2) or 'main'}/"
    return s if s.endswith("/") else s + "/"


def safe_path(rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or not any(rel == a or rel.startswith(a) for a in ALLOWED):
        raise ValueError(f"not an app file: {rel}")
    return rel


async def _get(url):
    req = await PW["p"].request.new_context()
    try:
        r = await req.get(f"{url}?t={int(time.time())}", timeout=30000)    # skip GitHub's short cache
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status}")
        return await r.body()
    finally:
        await req.dispose()


async def check_for_update():
    base = source_base()
    save_app_state(last_update_check=datetime.datetime.now().isoformat(timespec="seconds"))
    if not base:
        return {"ok": False, "error": "No update source set yet. Your helper adds it in Settings, Updates."}
    try:
        manifest = json.loads(await _get(base + "release.json"))
    except Exception as e:
        return {"ok": False, "error": f"Couldn't reach the update source ({str(e)[:120]})."}
    newv = str(manifest.get("version", ""))
    if vt(newv) <= vt(APP_VERSION):
        return {"ok": True, "available": False, "version": APP_VERSION}
    UPDATE["manifest"] = manifest
    notes = [c for c in manifest.get("changelog", []) if vt(c.get("version")) > vt(APP_VERSION)]
    log(f"⬆️  Version {newv} is available.")
    return {"ok": True, "available": True, "version": newv, "notes": notes, "urgent": bool(manifest.get("urgent"))}


def install_files(files, newv):
    """files = {relative path: bytes}. Checks, backs up, replaces. Returns the backup folder."""
    for rel, blob in files.items():
        safe_path(rel)
        if rel.endswith(".py"):
            compile(blob.decode("utf-8"), rel, "exec")            # a broken file never gets installed
    if "careerhub/config.py" not in files and "career_hub.py" not in files:
        raise ValueError("this doesn't look like a Career Hub release")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    dest = backup_data(tag=f"before-update_{APP_VERSION}-to-{newv}_{stamp}")
    old = dest / "app"
    existed = []
    for rel in files:
        cur = BASE / rel
        if cur.exists():
            existed.append(rel)
            (old / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cur, old / rel)
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps({"from": APP_VERSION, "to": newv, "backup": str(old), "files": list(files),
                                   "existed": existed, "time": stamp}, indent=1), encoding="utf-8")
    for rel, blob in files.items():
        target = BASE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        if rel.endswith(".command"):
            target.chmod(0o755)
    log(f"⬆️  Installed version {newv}. Backup of the old version: Backups/{dest.name}")
    return dest


async def download_files(m):
    """Downloads and checks every file of release manifest m. Kept in memory so 'Update now' is instant."""
    cached = UPDATE.get("files")
    if cached and cached[0] == m["version"]:
        return cached[1]
    base, files = source_base(), {}
    for f in m.get("files", []):
        rel = safe_path(f["path"])
        blob = await _get(base + rel.replace(" ", "%20").replace("(", "%28").replace(")", "%29"))
        if hashlib.sha256(blob).hexdigest() != f["sha256"]:
            raise ValueError(f"{rel} didn't download correctly (checksum mismatch)")
        files[rel] = blob
    UPDATE["files"] = (m["version"], files)
    return files


async def prefetch_update():
    """Quietly downloads the new version in the background; a failure here is harmless (Update now retries)."""
    m = UPDATE.get("manifest")
    try:
        if m:
            await download_files(m)
            log(f"⬇️  Version {m['version']} is downloaded and ready to install.")
    except Exception as e:
        log(f"⚠  Background download of the update failed (will retry on Update now): {str(e)[:120]}")


async def install_latest():
    m = UPDATE.get("manifest")
    if not m:
        r = await check_for_update()
        if not r.get("available"):
            return {"ok": False, "error": r.get("error") or "You already have the latest version."}
        m = UPDATE["manifest"]
    try:
        files = await download_files(m)
        install_files(files, m["version"])
    except Exception as e:
        log(f"⚠  Update failed, nothing was changed: {e}")
        return {"ok": False, "error": f"Update failed, nothing was changed: {str(e)[:200]}"}
    return {"ok": True, "version": m["version"]}


def install_zip(blob):
    """Manual fallback: a zip of the Career Hub folder (or its contents)."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = [n for n in z.namelist() if not n.endswith("/")]
    prefix = ""
    if not any(n.startswith("careerhub/") for n in names):
        tops = {n.split("/")[0] for n in names}
        prefix = next((t + "/" for t in tops if any(n.startswith(t + "/careerhub/") for n in names)), "")
    files = {}
    for n in names:
        if n.startswith(prefix):
            rel = n[len(prefix):]
            if any(rel == a or rel.startswith(a) for a in ALLOWED) and "__pycache__" not in rel:
                files[rel] = z.read(n)
    cfg = files.get("careerhub/config.py", b"").decode("utf-8", "ignore")
    m = re.search(r'APP_VERSION = "([^"]+)"', cfg)
    if not m:
        raise ValueError("this zip isn't a Career Hub release")
    install_files(files, m.group(1))
    return m.group(1)


def confirm_started():
    """Called once the window has loaded: the new version works, so forget the pending update."""
    if PENDING.exists():
        info = json.loads(PENDING.read_text(encoding="utf-8"))
        PENDING.unlink()
        log(f"✓ Updated from {info.get('from')} to {info.get('to')}.")
    if ROLLED_BACK.exists():
        info = json.loads(ROLLED_BACK.read_text(encoding="utf-8"))
        ROLLED_BACK.unlink()
        log(f"⚠  Version {info.get('to')} failed to start, so the app went back to {info.get('from')}.")
        return info
    return None


def restore_backup(info, base=BASE):
    """Used by career_hub.py when a new version crashes on start."""
    src = Path(info["backup"])
    for rel in info.get("files", []):
        if (src / rel).exists():
            shutil.copy2(src / rel, base / rel)
