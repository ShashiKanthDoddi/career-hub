"""launch: starts Chrome (or Playwright's bundled Chromium) for the app window and the job browser."""
import os
import subprocess
import sys
from .bridge import log

# Keep Chrome's sandbox on (no "--no-sandbox" warning bar). Linux test machines run as root, where it can't start.
SANDBOX = os.name == "nt" or sys.platform == "darwin"


async def launch_chrome(p, user_dir, **opts):
    opts.setdefault("headless", False)
    opts.setdefault("no_viewport", True)
    opts["chromium_sandbox"] = SANDBOX
    try:
        return await p.chromium.launch_persistent_context(str(user_dir), channel="chrome", **opts)
    except Exception:
        pass
    try:
        return await p.chromium.launch_persistent_context(str(user_dir), **opts)
    except Exception as e:
        if "Executable doesn't exist" not in str(e):
            raise
        log("ℹ  Downloading the built-in browser (one time, about 150 MB)…")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        return await p.chromium.launch_persistent_context(str(user_dir), **opts)
