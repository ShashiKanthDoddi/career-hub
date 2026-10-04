"""bridge module of Career Hub. See MAP.md for what lives where."""
import asyncio
import os
import re
import subprocess
import sys


class StopRun(Exception):
    pass


class Bridge:
    """Connects the engine to the app window: logs, status, questions."""

    def __init__(self):
        self.page = None
        self.pending = {}
        self.n = 0
        self.stop = False
        self.busy = False

    async def emit(self, ev):
        if self.page is None:
            return
        try:
            await self.page.evaluate("ev => window.onPy && window.onPy(ev)", ev)
        except Exception:
            pass

    async def ask(self, title, message="", options=None, choices=None, text=False, placeholder="",
                  table=None, kind="info", value="", questions=None, chrome=None):
        """Shows a question card. options = list of answers (buttons); choices = [(label, value, style)].
        chrome = the job page when she has to do something there first: that window comes to the front, with a sound."""
        if self.stop:
            raise StopRun()
        self.n += 1
        qid = self.n
        fut = asyncio.get_running_loop().create_future()
        self.pending[qid] = fut
        if chrome is None:
            try:
                focused = await self.page.evaluate("document.hasFocus()")
                await self.page.bring_to_front()
                if not focused:
                    notify(title)
            except Exception:
                pass
        await self.emit({"type": "ask", "value": value, "questions": questions or [], "id": qid, "title": title, "message": message,
                         "options": options or [], "choices": [list(c) for c in (choices or [])],
                         "text": text, "placeholder": placeholder, "table": table or [], "kind": kind,
                         "chrome": chrome is not None})
        if chrome is not None:
            notify(title, "Look at the Chrome window, then answer in Career Hub.")
            await raise_window(chrome)
        try:
            for _ in range(2):                         # still no answer after 4 and 8 minutes: ring again
                done, _p = await asyncio.wait({fut}, timeout=240)
                if done:
                    break
                notify(title, "Career Hub is still waiting for you.")
            v = await fut
        finally:
            self.pending.pop(qid, None)
            await self.emit({"type": "ask_done", "id": qid})
        if self.stop:
            raise StopRun()
        return v

    def answer(self, qid, value):
        fut = self.pending.get(int(qid))
        if fut and not fut.done():
            fut.set_result(value)

    def cancel_all(self):
        for fut in list(self.pending.values()):
            if not fut.done():
                fut.set_result(None)

    def status(self, **kw):
        self._send({"type": "status", **kw})

    def _send(self, ev):
        try:
            asyncio.get_running_loop().create_task(self.emit(ev))
        except RuntimeError:
            pass


UI = Bridge()


LOG = {"file": None}


def _plain(s, n):
    """Letters, digits and simple punctuation only: the text goes into an AppleScript / PowerShell string."""
    return re.sub(r"[^\w\s.,:;!?()+@/-]", "", str(s or ""))[:n].strip()


def notify(title, body=""):
    """A system notification with a sound when the app needs her (Mac: Notification Centre; Windows: tray pop-up)."""
    t, b = _plain(title, 100), _plain(body, 180)
    try:
        if sys.platform == "darwin":
            sub = f' subtitle "{b}"' if b else ""
            subprocess.Popen(["osascript", "-e", f'display notification "{t}" with title "Career Hub"{sub} sound name "Glass"'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            ps = ("Add-Type -AssemblyName System.Windows.Forms;$n=New-Object System.Windows.Forms.NotifyIcon;"
                  "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
                  f"$n.ShowBalloonTip(10000,'Career Hub','{(t + '. ' + b) if b else t}',[System.Windows.Forms.ToolTipIcon]::Info);"
                  "Start-Sleep -Seconds 11;$n.Dispose()")
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    except Exception:
        pass


async def raise_window(page):
    """Puts the window of this page on top of other apps. bring_to_front() alone only picks the tab, so the window is
    minimised and restored, which makes the system bring it forward."""
    try:
        await page.bring_to_front()
        if await page.evaluate("document.hasFocus()"):
            return
        cdp = await page.context.new_cdp_session(page)
        try:
            win = (await cdp.send("Browser.getWindowForTarget"))["windowId"]
            state = (await cdp.send("Browser.getWindowBounds", {"windowId": win}))["bounds"].get("windowState", "normal")
            back = "normal" if state in ("minimized", "fullscreen") else state
            await cdp.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": "minimized"}})
            await asyncio.sleep(0.15)
            await cdp.send("Browser.setWindowBounds", {"windowId": win, "bounds": {"windowState": back}})
        finally:
            await cdp.detach()
        await page.bring_to_front()
    except Exception:
        pass


def os_open(path, editor=False):
    path = str(path)
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "TextEdit", path] if editor else ["open", path])
    elif os.name == "nt":
        if editor:
            subprocess.Popen(["notepad", path])
        else:
            os.startfile(path)
    else:
        subprocess.run(["xdg-open", path])


def log(*args, **kwargs):
    text = " ".join(str(a) for a in args).replace("\r", "").rstrip()
    if kwargs.get("end") == "\r":          # progress lines
        UI.status(detail=text.strip())
        return
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode())
    if LOG["file"] is not None and text.strip() and kwargs.get("file", True):
        try:
            with LOG["file"].open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception:
            pass
    if text.strip():
        UI._send({"type": "log", "text": text, "key": kwargs.get("key", "")})   # same key: replaces the line above (live counts)


def check_stop():
    if UI.stop:
        raise StopRun()


async def ainput(prompt=""):           # only used if something still asks in Terminal
    return await asyncio.to_thread(input, prompt)
