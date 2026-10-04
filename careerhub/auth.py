"""auth module of Career Hub. See MAP.md for what lives where."""
from urllib.parse import urlparse
import re
from .bridge import UI, log
from .config import APPLY_IDS, APPLY_WORDS, SIGNIN_IDS, SIGNIN_WORDS, SIGNUP_IDS, SIGNUP_WORDS, SSO_SITES
from .filler import fill_page, find_clickable, looks_like_form, page_text, safe_click, settle
from .records import log_account, save_default_password, saved_password
from .textutil import strong


async def get_password(host, db):
    pw = saved_password(host) or db.site_password
    if pw:
        return pw
    msg = ("Job sites need an account. Choose ONE password the tool will use for new job-site accounts.\n\n"
           "8+ characters with a capital letter, a small letter, a number and a symbol (e.g. Mktg@2026!). "
           "It's saved in your profile and every account is listed in the Tracker.")
    while True:
        p = await UI.ask(title="Choose your job-site password", message=msg, text=True,
                         placeholder="e.g. Mktg@2026!", kind="text")
        p = (p or "").strip()
        if strong(p):
            break
        msg = "⚠ Most job sites won't accept that. Use 8+ characters with A, a, 1 and a symbol."
    save_default_password(p)
    db.site_password = p
    log("   ✓ Password saved in your profile.")
    return p


async def auth_state(page):
    """Returns (frame, number_of_visible_password_boxes)."""
    for fr in page.frames:
        try:
            n = await fr.locator('input[type="password"]:visible').count()
        except Exception:
            continue
        if n:
            return fr, n
    return None, 0


async def handle_auth(ctx, db, company):
    """Signs in or creates an account. Returns True when the login page is gone."""
    page = ctx.pages[-1]
    host = urlparse(page.url).netloc.lower()
    if any(s in host for s in SSO_SITES):
        log(f"\n🔑 {host} needs you to log in yourself (the tool doesn't type passwords for this site).")
        return False
    email = db.lookup({"label": "email", "kind": "text"})[0]
    if not email or "example.com" in email:
        log("\n⚠  Add your email address in Profile first.")
        return False

    asked_site_pw = False
    for _ in range(5):
        page = ctx.pages[-1]
        fr, n = await auth_state(page)
        if not n:
            return True
        signup = n >= 2
        log(f"\n🔑 {'Creating an account' if signup else 'Signing in'} on {host} with {email} ...")
        pw = await get_password(host, db)

        await fill_page(page, db)                               # email, name, "I agree" boxes, etc.
        try:
            await fr.locator('input[type="email"]:visible, input[data-automation-id="email"]:visible, '
                             'input[autocomplete="username"]:visible, input[name*="email" i]:visible, '
                             'input[id*="email" i]:visible').first.fill(email, timeout=3000)
        except Exception:
            pass
        boxes = fr.locator('input[type="password"]:visible')
        for i in range(min(await boxes.count(), 2)):
            await boxes.nth(i).fill(pw)

        btn, _t = await find_clickable(page, SIGNUP_WORDS if signup else SIGNIN_WORDS,
                                       SIGNUP_IDS if signup else SIGNIN_IDS)
        if not btn:
            return False
        await safe_click(btn)
        await settle(page)
        page = ctx.pages[-1]
        _, n2 = await auth_state(page)
        text = await page_text(page)

        if signup and re.search(r"already (exists|in use|registered|been registered|have an account)|account exists", text):
            log("   ℹ  You already have an account here. Signing in instead.")
            link, _t = await find_clickable(page, ["sign in", "log in", "already have an account"], ["signInLink"],
                                            exclude=r"\bwith\b|google|linkedin|apple|facebook")
            if link:
                await safe_click(link)
                await settle(page)
            continue
        if not n2:
            log("   ✓ Done.")
            log_account(company, host, email, pw, "Account created" if signup else "Signed in")
            if re.search(r"verif|confirm your email|check your (email|inbox)", text):
                await UI.ask(title="Check your email", message="The site sent you an email. Open your inbox, "
                             "click the verification link, then come back here.",
                             choices=[("I've verified it – continue", "ok", "primary")], kind="info")
            return True
        if re.search(r"verif|confirm your email|check your (email|inbox)|activation", text):
            log_account(company, host, email, pw, "Account created (email verification needed)")
            await UI.ask(title="Verify your email", message="Open your inbox and click the verification link "
                         "from this company, then come back here.",
                         choices=[("I've verified it – continue", "ok", "primary")], kind="info")
            await page.reload()
            await settle(page)
            continue
        if not signup and not asked_site_pw and re.search(
                r"incorrect|invalid|wrong|doesn.t match|not match|not recognized|failed|try again", text):
            log(f"   ⚠  That password didn't work on {host}.")
            pw = await UI.ask(title="Password didn't work", message=f"Your usual password didn't work on {host}. "
                              "Type the password you use on this site:", text=True, placeholder="Password",
                              choices=[("I'll log in myself", "__manual__", "ghost")], kind="text")
            pw = (pw or "").strip()
            if not pw or pw == "__manual__":
                return False
            log_account(company, host, email, pw, "Password entered by you")
            asked_site_pw = True
            continue
        return False                                            # CAPTCHA, code by SMS, unknown message
    return False


async def get_to_form(ctx, db, company):
    """Clicks Apply / Apply Manually and handles login until the first form is on screen."""
    clicks = 0
    for _ in range(10):
        page = ctx.pages[-1]
        await page.bring_to_front()
        await settle(page)
        _, n = await auth_state(page)
        if n:
            if not await handle_auth(ctx, db, company):
                return False
            continue
        if await looks_like_form(page):
            return True
        btn, text = await find_clickable(page, APPLY_WORDS, APPLY_IDS)
        if not btn or clicks >= 4:
            return False
        log(f"   → clicking \"{text[:40]}\"")
        await safe_click(btn)
        clicks += 1
    return False
