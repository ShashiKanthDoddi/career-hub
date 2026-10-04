/* ===== resume: her resume on the left; summary tiles on top; Health / Fit / Skills / Files tabs on the right ===== */
let RS = null, RS_URL = "", RS_VIEW = "pdf", RS_TAB = "health", RS_FIT = null;
const scoreColor = n => n >= 80 ? "var(--green)" : n >= 60 ? "var(--amber)" : "var(--rose)";
const CAPS = new Set(["seo","sem","ppc","crm","ga4","cro","gtm","aso","b2b","b2c","d2c","sql","atl","btl","saas","fmcg","roas","cac","cpa","cms","pr"]);
/* "google ads" -> "Google Ads", "a b testing" -> "A/B testing", "seo" -> "SEO" */
const BRANDS = {hubspot:"HubSpot", semrush:"Semrush", ahrefs:"Ahrefs", wordpress:"WordPress", youtube:"YouTube", linkedin:"LinkedIn", moengage:"MoEngage",
  clevertap:"CleverTap", webengage:"WebEngage", mailchimp:"Mailchimp", shopify:"Shopify", salesforce:"Salesforce", marketo:"Marketo", tableau:"Tableau"};
const kwLabel = w => w === "a b testing" || w === "ab testing" ? "A/B testing" : BRANDS[w] ? BRANDS[w] : w.split(" ").map(x => CAPS.has(x) ? x.toUpperCase() : x[0].toUpperCase() + x.slice(1)).join(" ");
const sentence = w => w ? w[0].toUpperCase() + w.slice(1) : w;

async function loadResumePage(name){
  if (STATE.profile){ renderFileForm(); renderFiles(); }       // Your files lives on this page
  const r = await api_resume_page(name || (RS && RS.file) || "");
  if (!r || !r.ok || !Array.isArray(r.versions)){
    RS = null; $("#rsPick").hidden = $("#rsView").hidden = $("#rsPdf").hidden = $("#rsHint").hidden = true; $("#rsText").hidden = false;
    $("#rsText").innerHTML = emptyHTML("file", "No resume yet", esc((r && r.error) || "Drop your resume into the Files tab on the right."));
    $("#rsSum").innerHTML = ""; $("#rsAts").innerHTML = ""; $("#rsSkills").innerHTML = ""; setRsTab("files"); return;
  }
  if (!RS || RS.file !== r.file) RS_FIT = null;
  RS = r;
  $("#rsPick").innerHTML = r.versions.map(v => `<option value="${esc(v.file)}" ${v.file === r.file ? "selected" : ""}>${esc(v.label)}: ${esc(v.file)}</option>`).join("");
  $("#rsPick").hidden = r.versions.length < 2;
  $("#rsName").textContent = r.file;
  $("#rsText").innerHTML = r.text ? resumeHTML(r.text, (r.ats && r.ats.skills) || [])
    : emptyHTML("file", "No text could be read", "Job sites can't read this file either. Save it again as a PDF from Word or Google Docs.");
  $("#rsTailorBtn").title = r.ai ? "" : "Needs your Claude key in Settings, AI helper";
  renderSummary(); renderAts(r.ats); renderSkills(r.gaps); setRsTab(RS_TAB);
  await showResumeFile(r);
}

/* ---- left: the resume ---- */
async function showResumeFile(r){
  const v = r.versions.find(x => x.file === r.file), canPdf = !!(v && v.exists && v.pdf);
  if (RS_URL){ URL.revokeObjectURL(RS_URL); RS_URL = ""; }
  if (canPdf){ const f = await api_resume_pdf(r.file);       // shown from memory (a blob): the window never opens other files from disk
    if (f && f.ok && f.b64){ const bytes = Uint8Array.from(atob(f.b64), c => c.charCodeAt(0));
      RS_URL = URL.createObjectURL(new Blob([bytes], {type: "application/pdf"})); $("#rsPdf").src = RS_URL; } }
  $("#rsView").hidden = !RS_URL; setRsView(RS_URL ? RS_VIEW : "text");
}
function setRsView(v){ $("#rsPdf").hidden = v !== "pdf"; $("#rsText").hidden = v !== "text"; $("#rsHint").hidden = v !== "text" || !RS || !RS.text;
  $$("#rsView button").forEach(b => b.classList.toggle("on", b.dataset.v === v)); }
/* What job sites read, as a clean page: headings stand out, marketing keywords are highlighted */
function resumeHTML(text, skills){
  const words = [...skills].sort((a, b) => b.length - a.length).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "[\\s/&-]+"));
  const kw = words.length ? new RegExp(`\\b(${words.join("|")})\\b`, "gi") : null;
  const head = /^(professional |work |key |core |technical |career )?(summary|profile|about me|objective|experience|employment|work history|education|academic|qualifications?|skills|competencies|tools|expertise|certifications?|projects|achievements|awards|languages|interests)\s*:?$/i;
  return text.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
    if (head.test(l) || (l.length < 32 && l === l.toUpperCase() && /[A-Z]{3}/.test(l))) return `<h4>${esc(l)}</h4>`;
    const e = esc(l.replace(/^[•·▪◦●*-]\s*/, "")), bullet = /^[•·▪◦●*-]\s*/.test(l);
    return `<p${bullet ? ' class="b"' : ""}>${kw ? e.replace(kw, "<mark>$1</mark>") : e}</p>`;
  }).join("");
}
$$("#rsView button").forEach(b => b.onclick = () => { RS_VIEW = b.dataset.v; setRsView(RS_VIEW); });
$("#rsPick").onchange = e => loadResumePage(e.target.value);
$("#rsOpen").onclick = async () => { if (!RS || !await api_resume_open(RS.file)) toast("Couldn't open the file", true); };

/* ---- top: four tiles that open their tab ---- */
function renderSummary(){
  const a = RS.ats, gaps = RS.gaps || [], miss = gaps.reduce((n, g) => n + g.missing.length, 0), all = gaps.reduce((n, g) => n + g.missing.length + g.have.length, 0);
  const fixes = a ? a.checks.filter(c => !c.ok).length : 0;
  const tiles = [
    ["health", "Resume health", a ? a.score : "–", a ? (fixes ? `${fixes} thing${fixes > 1 ? "s" : ""} to fix` : "Looks great") : "PDF files only", a ? a.score : 0, a ? scoreColor(a.score) : "var(--muted)"],
    ["fit", "Fit to a job", RS_FIT ? RS_FIT.score : "–", RS_FIT ? `${RS_FIT.missing.length} word${RS_FIT.missing.length === 1 ? "" : "s"} missing` : "Paste a job to check", RS_FIT ? RS_FIT.score : 0, RS_FIT ? scoreColor(RS_FIT.score) : "var(--muted)"],
    ["skills", "Skills to build", miss, gaps.map(g => sentence(g.role)).join(", "), all ? 100 * (all - miss) / all : 0, "var(--violet)"],
    ["files", "Resume versions", RS.versions.length, RS.versions.length > 1 ? "for different roles" : "add one per kind of role", 100 * RS.versions.length / 3, "var(--teal)"]];
  $("#rsSum").innerHTML = tiles.map(([t, l, n, s, p, c]) => `<button class="stagebox rs-tile${t === RS_TAB ? " on" : ""}" data-t="${t}" style="--c:${c}">
    <div class="n">${esc(n)}</div><div class="l">${l}</div><div class="s">${esc(s)}</div><div class="bar"><i style="width:${Math.round(p)}%"></i></div></button>`).join("");
  $$("#rsSum .rs-tile").forEach(b => b.onclick = () => setRsTab(b.dataset.t));
}
function setRsTab(t){ RS_TAB = t;
  $$("#rsTabs button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  $$(".rs-tab").forEach(x => x.hidden = x.dataset.t !== t);
  $$("#rsSum .rs-tile").forEach(b => b.classList.toggle("on", b.dataset.t === t)); }
$$("#rsTabs button").forEach(b => b.onclick = () => setRsTab(b.dataset.t));

/* ---- Health ---- */
function renderAts(a){
  if (!a){ $("#rsAts").innerHTML = `<h2>Resume health</h2>` + emptyHTML("file", "I can only check PDF files", "Save your resume as a PDF from Word or Google Docs, then add it in the Files tab."); return; }
  const bad = a.checks.filter(c => !c.ok).sort((x, y) => y.weight - x.weight), good = a.checks.filter(c => c.ok);
  const word = a.score >= 80 ? "Strong resume" : a.score >= 60 ? "Good, with a few things to fix" : "Needs some work";
  $("#rsAts").innerHTML = `<div class="rs-hero"><div class="rs-ring" style="--p:${a.score};--c:${scoreColor(a.score)}"><b>${a.score}</b><small>of 100</small></div>
      <div><h2>${word}</h2><p class="muted small">How easily job sites can read it: ${a.words} words, ${a.skills.length} marketing keywords.</p>
      <div class="rs-dots" title="${good.length} of ${a.checks.length} checks passed">${a.checks.map(c => `<i class="${c.ok ? "ok" : ""}"></i>`).join("")}</div></div></div>
    ${bad.length ? `<h3>To fix, most important first</h3>${bad.map(c => `<div class="rs-item"><span class="rs-ic warn">!</span><div><b>${esc(c.title)}</b><span>${esc(c.tip)}</span></div></div>`).join("")}`
      : `<div class="rs-item"><span class="rs-ic">${icon("check")}</span><div><b>Everything I check looks good</b><span>Now fit it to each job in the next tab.</span></div></div>`}
    ${good.length ? `<h3 style="margin-top:18px">Already good</h3><div class="chips" style="margin-top:0">${good.map(c => `<span class="tag got">${icon("check")}${esc(c.title)}</span>`).join("")}</div>` : ""}`;
}

/* ---- Skills (from the roles she looks for) ---- */
function renderSkills(g){
  $("#rsSkills").innerHTML = `<h2>Skills to build</h2><p class="muted small">For the roles you look for (your Find jobs titles, or your resume). Already have one? Add it to your resume.</p>` +
    (g || []).map(r => { const all = r.have.length + r.missing.length, pct = all ? Math.round(100 * r.have.length / all) : 0;
      return `<div class="rs-role"><div class="row"><b class="grow">${esc(sentence(r.role))}</b><span class="muted small">${r.have.length} of ${all} on your resume</span></div>
        <div class="rs-meter"><i style="width:${pct}%"></i></div>
        ${r.have.length ? `<div class="chips">${r.have.map(h => `<span class="tag got">${icon("check")}${esc(h)}</span>`).join("")}</div>` : ""}
        ${r.missing.length ? r.missing.map(m => `<div class="rs-learn"><span class="grow">${esc(m.skill)}</span><a class="btn sm" href="${esc(m.url)}" target="_blank" title="${esc(m.course)}">${icon("ext")}Free course</a></div>`).join("")
          : `<p class="small" style="margin:10px 0 0">Your resume already shows every skill on my list for this role.</p>`}</div>`; }).join("");
}

/* ---- Fit to one job: keywords in / missing, and (with the Claude key) rewrite suggestions ---- */
function rsJob(){ const j = $("#rsJob").value.trim(); if (!j) toast("Paste a job link or the job text first", true); return j; }
async function busyBtn(b, label, fn){ const t = b.innerHTML; b.disabled = true; b.textContent = label; try { return await fn(); } finally { b.disabled = false; b.innerHTML = t; } }
$("#rsMatchBtn").onclick = async () => { const job = rsJob(); if (!job) return;
  const r = await busyBtn($("#rsMatchBtn"), "Checking…", () => api_resume_match(job, RS ? RS.file : ""));
  if (!r.ok) return toast(r.error, true);
  if (!r.asked){ $("#rsMatch").innerHTML = `<p class="muted small" style="margin-top:14px">I found no marketing keywords in that text. Paste the full job description.</p>`; return; }
  RS_FIT = r; renderSummary();
  $("#rsMatch").innerHTML = `<div class="rs-hero" style="margin-top:18px"><div class="rs-ring" style="--p:${r.score};--c:${scoreColor(r.score)}"><b>${r.score}</b><small>fit</small></div>
      <div><h2>${r.have.length} of ${r.asked} job words are on your resume</h2><p class="muted small">${r.score >= 70 ? "A good fit. Apply with confidence." : "Add the missing words that are true for you, then check again."}</p></div></div>
    ${r.missing.length ? `<h3>Missing from your resume</h3><div class="chips" style="margin-top:0">${r.missing.map(w => `<span class="tag miss">${esc(kwLabel(w))}</span>`).join("")}</div>` : ""}
    ${r.have.length ? `<h3 style="margin-top:14px">Already there</h3><div class="chips" style="margin-top:0">${r.have.map(w => `<span class="tag got">${icon("check")}${esc(kwLabel(w))}</span>`).join("")}</div>` : ""}`; };
$("#rsTailorBtn").onclick = async () => { const job = rsJob(); if (!job) return;
  const r = await busyBtn($("#rsTailorBtn"), "Thinking…", () => api_resume_tailor(job, RS ? RS.file : ""));
  if (!r.ok) return toast(r.error, true);
  $("#rsMatch").innerHTML = `<div class="prep" style="margin-top:16px"><h3>Suggestions for this job</h3><p class="muted small">Written from your resume only. Change anything that isn't true, then edit your resume file.</p>
    ${prepTipsHTML(r.text)}<button class="btn sm" id="rsCopy">Copy</button></div>`;
  $("#rsCopy").onclick = () => { const ta = document.createElement("textarea"); ta.value = r.text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove(); toast("Copied"); }; };
