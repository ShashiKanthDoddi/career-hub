#!/usr/bin/env python3
"""Harshitha's Career Hub: the start file. Keep it small and stable.

It installs any missing Python parts, starts the app (careerhub/ + ui/), restarts it after an update,
and puts the previous version back if a freshly installed update crashes on start.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CAREERHUB_DATA") or BASE / "Harshitha's Data")
PENDING = DATA / ".update" / "pending.json"
RESTART = 42
REQUIRED = {"playwright": "playwright", "yaml": "pyyaml", "pypdf": "pypdf"}   # import name: pip name


def ensure_packages():
    missing = [pip for mod, pip in REQUIRED.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    print("Installing helper parts:", ", ".join(missing))
    cmd = [sys.executable, "-m", "pip", "install", "--user", *missing]
    if subprocess.call(cmd) != 0:
        subprocess.call(cmd + ["--break-system-packages"])


def roll_back(error_text):
    info = json.loads(PENDING.read_text(encoding="utf-8"))
    src = Path(info["backup"])
    for rel in info.get("files", []):
        if (src / rel).exists():
            (BASE / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, BASE / rel)
    info["error"] = error_text[-4000:]
    (PENDING.parent / "rolled_back.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    PENDING.unlink()


def restart():
    if os.environ.get("CAREERHUB_LAUNCHER"):          # the launcher loops on this exit code
        sys.exit(RESTART)
    subprocess.Popen([sys.executable, str(Path(__file__).resolve())])
    sys.exit(0)


def main():
    ensure_packages()
    sys.path.insert(0, str(BASE))
    try:
        from careerhub.main import run
        code = run()
    except KeyboardInterrupt:
        return
    except Exception:
        err = traceback.format_exc()
        print(err)
        if PENDING.exists():
            print("The new version didn't start. Going back to the previous version…")
            roll_back(err)
            restart()
        sys.exit(1)
    if code == RESTART:
        restart()


if __name__ == "__main__":
    main()
