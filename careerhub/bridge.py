"""bridge module of Career Hub. See MAP.md for what lives where."""
import asyncio
import os
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
                  table=None, kind="info", value="", questions=None):
        """Shows a question card. options = list of answers (buttons); choices = [(label, value, style)]."""
        if self.stop:
            raise StopRun()
        self.n += 1
        qid = self.n
        fut = asyncio.get_running_loop().create_future()
        self.pending[qid] = fut
        try:
            focused = await self.page.evaluate("document.hasFocus()")
            await self.page.bring_to_front()
            if not focused:
                notify(title)
        except Exception:
            pass
        await self.emit({"type": "ask", "value": value, "questions": questions or [], "id": qid, "title": title, "message": message,
                         "options": options or [], "choices": [list(c) for c in (choices or [])],
                         "text": text, "placeholder": placeholder, "table": table or [], "kind": kind})
        try:
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


def notify(title):
    """Mac notification + sound (or a beep on Windows) when the app needs you."""
    try:
        if sys.platform == "darwin":
            t = title.replace('"', "'")[:100]
            subprocess.Popen(["osascript", "-e", f'display notification "{t}" with title "Career Hub" sound name "Glass"'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            import winsound
            winsound.MessageBeep()
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
    if LOG["file"] is not None and text.strip():
        try:
            with LOG["file"].open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception:
            pass
    if text.strip():
        UI._send({"type": "log", "text": text})


def check_stop():
    if UI.stop:
        raise StopRun()


async def ainput(prompt=""):           # only used if something still asks in Terminal
    return await asyncio.to_thread(input, prompt)
