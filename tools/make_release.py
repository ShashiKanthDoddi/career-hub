#!/usr/bin/env python3
"""Prepare a release for automatic updates:  python3 tools/make_release.py [--urgent] [--skip-tests]

Before running: bump APP_VERSION in careerhub/config.py and add the newest entry at the top of
careerhub/changelog.py. This script runs the self-test, then writes release.json (version, changelog,
and a SHA-256 fingerprint of every app file). Then commit and push everything to GitHub; her app picks it
up within an hour (or right away with Check for updates).
"""
import base64
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["career_hub.py", "careerhub/*.py", "ui/*.html", "ui/*.css", "ui/js/*.js", "tools/*.py", "CLAUDE.md", "MAP.md",
           "Setup (Mac).command", "Open Career Hub (Mac).command", "Setup (Windows).bat", "Open Career Hub (Windows).bat"]


def vt(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


TEXT = {".py", ".js", ".html", ".css", ".md", ".bat", ".command", ".json", ".txt"}


def git_bytes(p):
    """The bytes GitHub will serve. On Windows the working copy may use CRLF line ends while git stores LF,
    and the app checks the downloaded bytes against this hash."""
    b = p.read_bytes()
    return b.replace(b"\r\n", b"\n") if p.suffix.lower() in TEXT else b


def main():
    args = set(sys.argv[1:])
    version = re.search(r'APP_VERSION = "([^"]+)"', (ROOT / "careerhub/config.py").read_text(encoding="utf-8")).group(1)
    old = ROOT / "release.json"
    if old.exists():
        prev = json.loads(old.read_text(encoding="utf-8")).get("version", "0")
        if vt(version) <= vt(prev):
            sys.exit(f"APP_VERSION is {version}, but the last release was {prev}. Bump it in careerhub/config.py first.")
    if "--skip-tests" not in args:
        print("Running self-test…")
        if subprocess.call([sys.executable, str(ROOT / "tools/selftest.py")]) != 0:
            sys.exit("Self-test failed: fix it before releasing.")
    sys.path.insert(0, str(ROOT))
    from careerhub.changelog import CHANGELOG
    if CHANGELOG[0]["version"] != version:
        sys.exit(f"Add a changelog entry for {version} at the top of careerhub/changelog.py.")
    files = []
    for pattern in INCLUDE:
        for p in sorted(ROOT.glob(pattern)):
            if p.is_file() and "__pycache__" not in p.parts:
                files.append({"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(git_bytes(p)).hexdigest()})
    release = {"version": version, "date": datetime.date.today().isoformat(), "urgent": "--urgent" in args,
               "changelog": CHANGELOG[:8], "files": files}
    from careerhub import sigcheck
    keyfile = Path.home() / ".careerhub_release_key"
    if not keyfile.exists():
        sys.exit(f"Signing key not found: {keyfile}. Releases must be signed (the app refuses unsigned ones).")
    seed = bytes.fromhex(keyfile.read_text().strip())
    if sigcheck.public_key(seed).hex() != sigcheck.PUBLIC_KEY:
        sys.exit("The signing key doesn't match PUBLIC_KEY in careerhub/sigcheck.py.")
    release["signature"] = base64.b64encode(sigcheck.sign(seed, sigcheck.canonical(release))).decode("ascii")
    old.write_text(json.dumps(release, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nrelease.json written for version {version} ({len(files)} files).")
    print("Now publish it:\n  git add -A\n  git commit -m \"Release " + version + "\"\n  git push")


if __name__ == "__main__":
    main()
