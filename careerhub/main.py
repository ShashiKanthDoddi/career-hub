"""main: opens the app window (ui/index.html), connects every api_* function, runs the hourly update check.
run() returns RESTART_CODE when an update was installed, so the launcher starts the new version."""
import asyncio
import datetime
from playwright.async_api import async_playwright
from . import api
from .bridge import LOG, UI, log
from .config import APP_NAME, APP_VERSION, APP_WINDOW_DIR, BASE, LOG_DIR, RESTART_CODE
from .gmail import mail_settings
from .launch import launch_chrome
from .state import APP, JOB, PW, TASKS
from .store import backup_data, data
from .updater import confirm_started

UI_INDEX = BASE / "ui" / "index.html"
UI_PREFIX = (BASE / "ui").as_uri().rstrip("/") + "/"


def guarded(fn):
    """Only our own window (file:// ui/) may call the api_* functions, never a web page that ends up in it."""
    async def call(source, *args):
        urls = [str(getattr(source.get(k), "url", "") or "") for k in ("page", "frame")]
        if not all(u.startswith(UI_PREFIX) for u in urls):
            log(f"⚠  Blocked a call to {fn.__name__} from outside the app window.")
            raise PermissionError("not allowed")
        return await fn(*args)
    return call


async def open_app_window(p):
    ctx = await launch_chrome(p, APP_WINDOW_DIR, args=[f"--app={UI_INDEX.as_uri()}", "--start-maximized",
                                                        "--enable-lcd-text", "--high-dpi-support=1"])
    try:  # Chrome may restore a saved smaller size for app windows: force maximised
        page = ctx.pages[0] if ctx.pages else await ctx.wait_for_event("page")
        cdp = await ctx.new_cdp_session(page)
        win = await cdp.send("Browser.getWindowForTarget")
        await cdp.send("Browser.setWindowBounds", {"windowId": win["windowId"], "bounds": {"windowState": "maximized"}})
    except Exception:
        pass
    return ctx


async def update_loop():
    await asyncio.sleep(8)                     # let the window settle, then check now and every hour
    while True:
        try:
            await api.api_check_update(False)
        except Exception as e:
            log(f"⚠  Update check failed: {e}")
        await asyncio.sleep(3600)


async def mail_loop():
    """Reads the job Gmail when the app starts and then every hour (unless switched off in Settings)."""
    await asyncio.sleep(12)
    while True:
        try:
            ms = mail_settings()
            if ms["auto"] and ms["addr"] and ms["pw"]:
                await api.api_check_mail(False)
        except Exception as e:
            log(f"⚠  Automatic email check failed: {e}")
        await asyncio.sleep(3600)


async def after_load(rolled_back):
    await asyncio.sleep(2)                     # the page's scripts are ready by then
    if rolled_back:
        await UI.emit({"type": "rolled_back", "from": rolled_back.get("from"), "to": rolled_back.get("to")})


async def main():
    data()                                     # creates / upgrades Harshitha's Data on first run
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG["file"] = LOG_DIR / f"{datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}.txt"
    log(f"{APP_NAME} {APP_VERSION} started")
    try:
        backup_data()
    except Exception as e:
        log(f"⚠  Backup skipped: {e}")
    print("=" * 60 + f"\n  {APP_NAME} is running.\n  Keep this window open (it minimises itself).\n"
          "  Close the app window to quit.\n" + "=" * 60)
    async with async_playwright() as p:
        PW["p"] = p
        app = await open_app_window(p)
        for name in dir(api):
            if name.startswith("api_"):
                await app.expose_binding(name, guarded(getattr(api, name)))
        page = app.pages[0] if app.pages else await app.new_page()
        await page.goto(UI_INDEX.as_uri())
        UI.page = page
        for coro in (after_load(confirm_started()), update_loop(), mail_loop()):
            t = asyncio.get_running_loop().create_task(coro)
            TASKS.add(t)
            t.add_done_callback(TASKS.discard)

        closed = asyncio.Event()
        page.on("close", lambda *_: closed.set())
        app.on("close", lambda *_: closed.set())
        await closed.wait()

        UI.page, UI.stop = None, True
        UI.cancel_all()
        for t in list(TASKS):
            t.cancel()
        for c in (JOB["ctx"], app):
            try:
                if c:
                    await c.close()
            except Exception:
                pass
    if APP["restart"]:
        print("Restarting into the new version…")
        return RESTART_CODE
    print(f"{APP_NAME} closed. You can close this window.")
    return 0


def run():
    return asyncio.run(main())
