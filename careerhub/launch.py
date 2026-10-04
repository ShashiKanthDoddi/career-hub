"""launch: starts Chrome (or Playwright's bundled Chromium) for the app window and the job browser."""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from .bridge import log

# Keep Chrome's sandbox on (no "--no-sandbox" warning bar). Linux test machines run as root, where it can't start.
SANDBOX = os.name == "nt" or sys.platform == "darwin"


KEEP_DAYS = 90


def _cookie_file(user_dir):
    return Path(str(user_dir) + "_cookies.json")


async def _restore_cookies(ctx, user_dir):
    """Chrome drops 'session' cookies when it closes, which logs her out of LinkedIn etc. Put them back."""
    try:
        saved = json.loads(_cookie_file(user_dir).read_text(encoding="utf-8"))
        if saved:
            await ctx.add_cookies(saved)
    except Exception:
        pass


async def _save_cookies_loop(ctx, user_dir):
    """Every minute, save the cookies with an expiry date so a login lasts across restarts."""
    while True:
        await asyncio.sleep(60)
        try:
            keep = []
            for c in await ctx.cookies():
                if c.get("expires", -1) in (-1, None):
                    c["expires"] = time.time() + KEEP_DAYS * 86400
                keep.append(c)
            _cookie_file(user_dir).write_text(json.dumps(keep), encoding="utf-8")
        except Exception:
            return  # window closed


async def launch_chrome(p, user_dir, **opts):
    ctx = await _launch(p, user_dir, **opts)
    await _restore_cookies(ctx, user_dir)
    asyncio.get_running_loop().create_task(_save_cookies_loop(ctx, user_dir))
    return ctx


async def _launch(p, user_dir, **opts):
    opts.setdefault("headless", False)
    opts.setdefault("no_viewport", True)
    opts["chromium_sandbox"] = SANDBOX
    # Google refuses sign-in ("This browser or app may not be secure") in a browser flagged as automated.
    opts["ignore_default_args"] = list(opts.get("ignore_default_args", [])) + ["--enable-automation"]
    opts["args"] = list(opts.get("args", [])) + ["--disable-blink-features=AutomationControlled",
                                                       "--test-type"]  # --test-type hides the "unsupported flag" bar
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
