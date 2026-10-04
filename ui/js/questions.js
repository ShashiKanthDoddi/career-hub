/* ===== questions from the app ===== */
const KIND = {text:["New question","var(--violet)"], select:["New question","var(--violet)"], file:["Upload","var(--violet)"],
  help:["Your turn in Chrome","var(--amber)"], page:["Check this page","var(--teal)"], submit:["Ready to send","var(--green)"], info:["Note","var(--violet)"]};
function showAsk(q){
  if (q.questions && q.questions.length) return showForm(q);
  ASK = q; const [kind, color] = KIND[q.kind] || KIND.info;
  const table = q.table.length ? `<div class="minitable"><table>${q.table.map(r => `<tr class="${String(r[1]).includes("⚠") ? "warn" : ""}"><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join("")}</table></div>` : "";
  const opts = q.options.map((o, i) => `<button class="opt" data-i="${i}">${i < 9 ? `<kbd>${i + 1}</kbd>` : ""}<span>${esc(o)}</span></button>`).join("");
  const text = q.text ? `<textarea id="askText" rows="${(q.value || "").length > 300 ? 12 : 4}" placeholder="${esc(q.placeholder || "")}">${esc(q.value || "")}</textarea>
     <div class="row" style="margin-top:10px"><span class="kbdhint grow"><kbd>Enter</kbd> to save, <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line</span><button class="btn primary" id="askSave">Save answer</button></div>` : "";
  const choices = q.choices.map((c, i) => `<button class="btn ${c[2] === "primary" ? "primary" : c[2] === "danger" ? "danger" : ""}" data-c="${i}">${esc(c[0]).replace(/\s*→$/, "")}</button>`).join("");
  $("#layer").innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="sheet" style="--k:${color}">
     <div class="sh"><div class="kind">${kind}</div><h2>${esc(q.title)}</h2>${q.message ? `<p class="msg">${esc(q.message)}</p>` : ""}</div>
     <div class="sb">${table}${opts ? `<div style="margin-top:6px">${opts}</div>` : ""}${text}<div class="row" style="margin-top:14px">${choices}</div></div></div></div>`;
  $$("#layer .opt").forEach(b => b.onclick = () => reply(q.options[+b.dataset.i]));
  $$("#layer [data-c]").forEach(b => b.onclick = () => reply(q.choices[+b.dataset.c][1]));
  const t = $("#askText");
  if (t){ setTimeout(() => { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }, 30);
    $("#askSave").onclick = () => { const v = t.value.trim(); if (v) reply(v); };
    t.onkeydown = e => { if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); $("#askSave").click(); } }; }
  else setTimeout(() => ($("#layer .opt") || $("#layer .btn.primary"))?.focus(), 30);
}
function reply(v){ if (!ASK) return; const id = ASK.id; ASK = null; $("#layer").innerHTML = "";
  if (id === -1){ window._notice && window._notice(); return; } api_answer(id, v); }
function notice(title, msg){ return new Promise(res => { window._notice = res; showAsk({id:-1, title, message:msg, options:[], choices:[["OK","ok","primary"]], text:false, table:[], kind:"info"}); }); }

/* ===== all new questions on a page, on one card (kind "form") ===== */
function formField(x){
  const id = `fq${x.qid}`, req = x.required ? ` <span style="color:var(--rose)">*</span>` : "";
  let input;
  if (x.kind === "choice" || x.kind === "file"){
    const opts = x.options.map(o => `<option>${esc(o)}</option>`).join("");
    input = `<select id="${id}"><option value="">${x.kind === "file" ? "Choose a file" : "Choose"}</option>${opts}</select>`;
  } else if (x.kind === "textarea"){
    input = `<textarea id="${id}" rows="3">${esc(x.value || "")}</textarea>`;
  } else input = `<input type="text" id="${id}" value="${esc(x.value || "")}" placeholder="${x.kind === "date" ? "e.g. 15/11/2026 or Immediately" : ""}">`;
  return `<div class="field qf" data-q="${x.qid}"><label for="${id}">${esc(x.label)}${req}</label>${input}
    ${x.note ? `<div class="hint">${esc(x.note)}</div>` : ""}
    <div class="row" style="margin-top:6px;gap:8px">${x.ai ? `<button class="btn sm ghost" data-ai="${x.qid}">${icon("sparkle")}Draft with AI</button>` : ""}
    <label class="switch small muted"><input type="checkbox" class="never"> Never ask this</label></div></div>`;
}
function showForm(q){
  ASK = q;
  const files = q.questions.some(x => x.kind === "file") ? `<p class="hint">New file? Add it in Profile, Your files, then come back.</p>` : "";
  $("#layer").innerHTML = `<div class="modal" role="dialog" aria-modal="true"><div class="sheet" style="--k:var(--violet);width:min(720px,100%)">
     <div class="sh"><div class="kind">New questions</div><h2>${esc(q.title)}</h2><p class="msg">${esc(q.message || "")}</p></div>
     <div class="sb"><div style="display:grid;gap:16px">${q.questions.map(formField).join("")}</div>${files}
     <div class="row" style="margin-top:18px"><button class="btn primary" id="formSave">Fill these in</button><button class="btn ghost" id="formSkip">Skip all</button>
     <span class="kbdhint grow" style="text-align:right"><kbd>Ctrl</kbd>+<kbd>Enter</kbd> to fill</span></div></div></div></div>`;
  const collect = () => { const out = {}; $$("#layer .qf").forEach(el => { const i = el.dataset.q;
    out[i] = {value: (el.querySelector("select, textarea, input[type=text]") || {}).value || "", never: el.querySelector(".never").checked}; }); return out; };
  $("#formSave").onclick = () => reply(collect());
  $("#formSkip").onclick = () => reply("__skip__");
  $$("#layer [data-ai]").forEach(b => b.onclick = async () => { const i = b.dataset.ai, x = q.questions.find(y => String(y.qid) === i);
    b.disabled = true; b.lastChild.textContent = "Writing…"; const r = await api_ai_draft(x.label); b.disabled = false; b.lastChild.textContent = "Draft with AI";
    if (r.ok){ const el = $(`#fq${i}`); el.value = r.text; } else toast(r.error, true); });
  $("#layer .sheet").onkeydown = e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)){ e.preventDefault(); $("#formSave").click(); } };
  setTimeout(() => $("#layer .qf select, #layer .qf textarea, #layer .qf input[type=text]")?.focus(), 30);
}
