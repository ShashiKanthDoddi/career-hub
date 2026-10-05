"""ai module of Career Hub. See MAP.md for what lives where."""
import datetime
import html
from .bridge import UI, log
from .config import COVER_DIR
from .resume import resume_text
from .state import CURRENT_JOB, PW
from .textutil import slug


NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODELS = ["deepseek-ai/deepseek-v3.2", "moonshotai/kimi-k2.5", "meta/llama-3.3-70b-instruct"]   # tried in turn, model names change


async def nvidia_complete(db, prompt, max_tokens=900):
    """NVIDIA's free hosted models (build.nvidia.com, free key). Her own model name first, then the fallbacks."""
    own = str(db.settings.get("nvidia_model") or "").strip()
    err = "no model answered"
    req = await PW["p"].request.new_context()
    try:
        for model in ([own] if own else []) + [m for m in NVIDIA_MODELS if m != own]:
            r = await req.post(NVIDIA_URL, timeout=120000,
                               headers={"Authorization": f"Bearer {db.nvidia_key}", "content-type": "application/json"},
                               data={"model": model, "max_tokens": max_tokens, "temperature": 0.6,
                                     "messages": [{"role": "user", "content": prompt}]})
            if r.status in (401, 403):
                raise RuntimeError("NVIDIA did not accept the key. Check it in Settings, AI helper.")
            if r.status == 429:
                raise RuntimeError("NVIDIA's free limit was reached for now. Wait a minute and try again.")
            if not r.ok:
                err = f"{model}: error {r.status}"
                continue
            d = await r.json()
            text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            if text.strip():
                return text.strip()
        raise RuntimeError(err)
    finally:
        await req.dispose()


async def ai_complete(db, prompt, max_tokens=900):
    if db.ai_nvidia:
        return await nvidia_complete(db, prompt, max_tokens)
    if not db.ai_paid:
        return await free_complete(prompt)
    model = str(db.settings.get("ai_model") or "claude-sonnet-5-5")
    req = await PW["p"].request.new_context()
    try:
        r = await req.post("https://api.anthropic.com/v1/messages", timeout=90000,
                           headers={"x-api-key": db.ai_key, "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"},
                           data={"model": model, "max_tokens": max_tokens,
                                 "messages": [{"role": "user", "content": prompt}]})
        d = await r.json()
    finally:
        await req.dispose()
    if not r.ok:
        raise RuntimeError((d.get("error") or {}).get("message") or f"error {r.status}")
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()


FREE_AI_URL = "https://text.pollinations.ai/"


async def free_complete(prompt):
    """A free AI that needs no key (Pollinations). Send it only public facts, never her resume or contact details."""
    req = await PW["p"].request.new_context()
    try:
        r = await req.post(FREE_AI_URL, timeout=60000, headers={"content-type": "application/json"},
                           data={"model": "openai-fast", "messages": [{"role": "user", "content": prompt}]})
        text = await r.text()
    finally:
        await req.dispose()
    if not r.ok:
        raise RuntimeError(f"free AI error {r.status}")
    return "\n".join(l for l in text.strip().splitlines() if "pollinations" not in l.lower()).strip()


def ai_context(db):
    return (f"COMPANY: {CURRENT_JOB.get('company') or 'unknown'}\nROLE: {CURRENT_JOB.get('title') or 'unknown'}\n\n"
            f"JOB POSTING (excerpt):\n{(CURRENT_JOB.get('desc') or '')[:6000]}\n\n"
            f"CANDIDATE RESUME:\n{resume_text(db)[:8000]}\n")


async def ai_answer(db, question):
    prompt = ("You are helping a marketing professional answer a question in a job application.\n"
              "Write the answer in first person, warm and specific. Use ONLY facts from the resume; never invent "
              "numbers, employers or skills. If the question is about this company, connect the candidate's "
              "experience to the job posting. Keep it under 120 words unless the question clearly asks for more. "
              "Output only the answer text, no preamble.\n\n" + ai_context(db) + f"\nQUESTION: {question}")
    return await ai_complete(db, prompt)


async def ai_prep(db, company, title, kind="interview"):
    """Short interview prep for one job: likely questions, talking points from her resume, questions to ask."""
    prompt = (f"You are a friendly coach helping a marketing professional get ready for a {kind} at {company or 'a company'}"
              f" for the role {title or 'a marketing role'}.\nUse ONLY facts from the resume; never invent numbers, employers or skills.\n"
              "Reply in plain text with exactly three short sections, each starting with its heading on its own line:\n"
              "Likely questions\nTalking points from your resume\nQuestions to ask them\n"
              "Give 4 bullet lines (starting with '- ') under each heading. No other text.\n\n"
              f"CANDIDATE RESUME:\n{resume_text(db)[:8000]}\n")
    return await ai_complete(db, prompt, 700)


async def ai_tailor(db, resume, job):
    """Suggestions to fit one resume to one job posting. Only facts already in the resume; she edits her file herself."""
    prompt = ("You are helping a marketing professional tailor her resume to one job. Use ONLY facts from the resume; "
              "never invent numbers, employers, tools or skills. Reply in plain text with exactly three sections, each "
              "starting with its heading on its own line:\nA summary for the top\nLines to rewrite\nWords from the job to use, if true for you\n"
              "Under the first heading give 1 line starting with '- ' (a 2-3 sentence summary). Under the second give 4 lines "
              "starting with '- ', each one an improved version of a real resume line that fits this job better. Under the "
              "third give up to 8 lines starting with '- '. No other text.\n\n"
              f"JOB POSTING:\n{(job or '')[:6000]}\n\nRESUME:\n{(resume or '')[:8000]}\n")
    return await ai_complete(db, prompt, 900)


async def text_to_pdf(text, path):
    browser = await PW["p"].chromium.launch()
    try:
        pg = await browser.new_page()
        body = html.escape(text).replace("\n", "<br>")
        await pg.set_content("<html><body style='font-family:Helvetica,Arial,sans-serif;font-size:11.5pt;"
                             f"line-height:1.55;color:#111'>{body}</body></html>")
        await pg.pdf(path=str(path), format="A4",
                     margin={"top": "25mm", "bottom": "25mm", "left": "22mm", "right": "22mm"})
    finally:
        await browser.close()


async def ai_cover_letter_flow(db):
    """Drafts a cover letter for this job, lets you edit it, saves it as a PDF. Returns the PDF path or None."""
    company = CURRENT_JOB.get("company") or "the company"
    note = "✨ Writing a cover letter for this job…"
    log(note)
    try:
        draft = await ai_complete(db, (
            "Write a one-page cover letter (250-320 words) for this marketing job application. First person, "
            "confident and specific, no clichés. Use ONLY facts from the resume; never invent numbers or employers. "
            "Connect 2-3 of the candidate's strongest relevant results to what the job posting asks for. "
            "Start with 'Dear Hiring Team,' and end with 'Best regards,' and the candidate's name from the resume. "
            "Output only the letter.\n\n" + ai_context(db)), max_tokens=1200)
    except Exception as e:
        await UI.ask(title="AI cover letter failed", message=str(e)[:300], choices=[("OK", "ok", "primary")])
        return None
    v = await UI.ask(title=f"Cover letter for {company}", message="✨ AI draft. Read it, edit anything that isn't "
                     "true or doesn't sound like you, then save. It becomes a PDF and is uploaded.",
                     text=True, value=draft, choices=[("Don't use it", "__cancel__", "ghost")], kind="text")
    if not v or v == "__cancel__":
        return None
    COVER_DIR.mkdir(exist_ok=True)
    path = COVER_DIR / f"CoverLetter_{slug(company)}_{datetime.date.today().isoformat()}.pdf"
    await text_to_pdf(v, path)
    log(f"   ✓ Cover letter saved: cover_letters/{path.name}")
    return str(path)
