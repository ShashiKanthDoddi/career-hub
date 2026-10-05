/* ===== Reach out: find hiring emails, write mails, show / save as Gmail drafts / send ===== */
let REACH = {history:[], mail_ok:false}, RFOUND = [], RMAILS = [], RSTOP = false, RBUSY = false;
const okMail = e => /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/.test((e || "").trim());
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function loadReach(){
  const r = await api_reach_page(), keep = $("#rcResume").value; REACH = r;
  $("#rcResume").innerHTML = r.resumes.map(v => `<option value="${esc(v.file)}">${esc(v.label)}: ${esc(v.file)}</option>`).join("") || `<option value="">No resume yet</option>`;
  if (keep) $("#rcResume").value = keep;
  $("#rcLimit").textContent = `Sent today: ${r.sent_today} of ${r.limit}`;
  $("#roChannel").innerHTML = r.channels.map(c => `<option>${esc(c)}</option>`).join(""); if (!$("#roDate").value) $("#roDate").value = new Date().toISOString().slice(0, 10); drawOther();
  $("#rcMailWarn").hidden = r.mail_ok; drawTiles(); if (r.mail_ok && r.history.length && !RSUM) checkReplies();
  $("#rpTone").innerHTML = r.tones.map(t => `<option>${esc(t)}</option>`).join(""); $("#rpLength").innerHTML = r.lengths.map(t => `<option>${esc(t)}</option>`).join("");
  const p = r.prefs; $("#rpTone").value = p.tone; $("#rpLength").value = p.length; $("#rpRole").value = p.role; $("#rpSubject").value = p.subject;
  $("#rpInclude").value = p.include; $("#rpAvoid").value = p.avoid; $("#rpOptOut").checked = !!p.opt_out;
  $("#rcHistory").innerHTML = r.history.length ? `<div class="tablewrap"><table><tr><th>Date</th><th>Company</th><th>Email</th><th>What happened</th><th>Reply</th></tr>${r.history.map(h =>
    `<tr><td>${esc(when(h.date))}</td><td>${esc(h.company)}</td><td>${esc(h.email)}</td><td>${h.how === "sent" ? "Sent" : "Gmail draft"}</td><td data-em="${esc(h.email)}"></td></tr>`).join("")}</table></div>`
    : `<p class="muted small">Nothing yet. Mails you send or save from here are listed, so no company is written to twice.</p>`;
}
function rcBusy(on){ RBUSY = on; ["#rcFind", "#rcGmail", "#rcWrite", "#rcSend", "#rcDraft"].forEach(s => $(s).disabled = on); $("#rcStop").hidden = !on; }

$("#rcFind").onclick = async () => {
  const items = [...new Set(($("#rcInput").value || "").split(/[\s,;]+/).filter(Boolean))];
  if (!items.length) return toast("Paste a website or an email address first.", true);
  if (!REACH.resumes.length) return toast("Add your resume first (Resume page, Your files).", true);
  RFOUND = []; RSTOP = false; rcBusy(true); $("#rcMails").hidden = true;
  const have = new Set(REACH.history.map(h => h.email));
  for (let i = 0; i < items.length && !RSTOP; i++){
    $("#rcProg").textContent = `Looking at ${i + 1} of ${items.length}…`; $("#rcFound").hidden = false;
    const r = await api_reach_find(items[i]);
    const row = r.ok ? {company:r.company, site:r.site, text:r.text, emails:r.emails, email:r.emails[0] || "", on:true, note:r.emails.length ? "" : "No email on this site (it may only have a contact form).", links:r.links || []}
                     : {company:items[i], site:items[i], text:"", emails:[], email:"", on:false, note:r.error};
    if (row.email && have.has(row.email.toLowerCase())){ row.on = false; row.note = "Already mailed before."; }
    RFOUND.push(row); drawFound();
  }
  $("#rcProg").textContent = ""; rcBusy(false);
};
function drawFound(){
  $("#rcFoundList").innerHTML = RFOUND.map((r, i) => `<div class="linkchip" style="margin-bottom:6px;flex-wrap:wrap">
    <input type="checkbox" data-on="${i}"${r.on ? " checked" : ""}><input type="text" data-co="${i}" value="${esc(r.company)}" style="width:170px">
    ${r.emails.length > 1 ? `<select data-pick="${i}">${r.emails.map(e => `<option${e === r.email ? " selected" : ""}>${esc(e)}</option>`).join("")}</select>`
      : `<input type="text" data-em="${i}" value="${esc(r.email)}" placeholder="email address" style="width:240px">`}
    <span class="muted small">${esc(r.note)}</span>${(r.links || []).map(l => ` <a href="${esc(l)}" target="_blank">${esc(l.replace(/^https?:\/\/(www\.)?/, "").slice(0, 40))}</a>`).join("")}${r.email ? "" : `<span class="muted small"> Find an address there and type it in, or untick.</span>`}</div>`).join("");
  $$("#rcFoundList [data-on]").forEach(b => b.onchange = () => RFOUND[+b.dataset.on].on = b.checked);
  $$("#rcFoundList [data-co]").forEach(b => b.oninput = () => RFOUND[+b.dataset.co].company = b.value);
  $$("#rcFoundList [data-em]").forEach(b => b.oninput = () => RFOUND[+b.dataset.em].email = b.value.trim());
  $$("#rcFoundList [data-pick]").forEach(b => b.onchange = () => RFOUND[+b.dataset.pick].email = b.value);
}

$("#rcWrite").onclick = async () => {
  const how = ($("input[name=rcHow]:checked") || {}).value || "review";
  const rows = RFOUND.filter(r => r.on && okMail(r.email));
  if (!rows.length) return toast("Tick at least one company with an email address.", true);
  RSTOP = false; rcBusy(true); RMAILS = [];
  for (let i = 0; i < rows.length && !RSTOP; i++){
    $("#rcProg").textContent = `Writing mail ${i + 1} of ${rows.length}…`;
    const w = await api_reach_write(rows[i].company, rows[i].text);
    if (!w.ok){ toast(w.error, true); continue; }
    RMAILS.push({text:rows[i].text, company:rows[i].company, site:rows[i].site, email:rows[i].email, subject:w.subject, body:w.body, on:true, status:""});
    drawMails(); $("#rcMails").hidden = false;
  }
  $("#rcProg").textContent = ""; rcBusy(false);
  if (RSTOP || !RMAILS.length) return;
  if (how === "draft") return sendAll("draft");
  if (how === "send"){
    if (await askYes("Send these mails now?", `${RMAILS.length} mail(s) will be sent from ${REACH.address} with your resume attached, a short pause between each. You will not see them first.`, "Send now")) return sendAll("send");
  }
  toast("Read them below, change anything, then send.");
};
function drawMails(){
  $("#rcMailList").innerHTML = RMAILS.map((m, i) => `<div class="panel" style="margin-bottom:10px;padding:12px">
    <div class="row"><input type="checkbox" data-mon="${i}"${m.on ? " checked" : ""}><b class="grow">${esc(m.company)} <span class="muted small">to ${esc(m.email)}</span></b>
    <button class="btn sm ghost" data-mre="${i}">Write again</button><span class="tag" id="mst${i}">${esc(m.status)}</span></div>
    <input type="text" data-msub="${i}" value="${esc(m.subject)}" style="margin:8px 0"><textarea data-mbody="${i}" rows="8">${esc(m.body)}</textarea></div>`).join("");
  $$("#rcMailList [data-mre]").forEach(b => b.onclick = async () => { const i = +b.dataset.mre, m = RMAILS[i]; if (m.status) return;
    b.disabled = true; b.textContent = "Writing…"; const w = await api_reach_write(m.company, m.text || "");
    if (w.ok){ m.body = w.body; m.subject = w.subject; drawMails(); } else { toast(w.error, true); b.disabled = false; b.textContent = "Write again"; } });
  $$("#rcMailList [data-mon]").forEach(b => b.onchange = () => RMAILS[+b.dataset.mon].on = b.checked);
  $$("#rcMailList [data-msub]").forEach(b => b.oninput = () => RMAILS[+b.dataset.msub].subject = b.value);
  $$("#rcMailList [data-mbody]").forEach(b => b.oninput = () => RMAILS[+b.dataset.mbody].body = b.value);
}
$("#rcSend").onclick = async () => {
  const n = RMAILS.filter(m => m.on && !m.status).length; if (!n) return toast("Nothing ticked to send.", true);
  if (await askYes("Send now?", `${n} mail(s) will be sent from ${REACH.address} with your resume attached.`, "Send")) sendAll("send");
};
$("#rcDraft").onclick = () => sendAll("draft");
$("#rcStop").onclick = () => { RSTOP = true; $("#rcSendProg").textContent = "Stopping after this one…"; };

async function sendAll(how){
  const todo = RMAILS.map((m, i) => i).filter(i => RMAILS[i].on && !RMAILS[i].status);
  RSTOP = false; rcBusy(true); let done = 0;
  for (const i of todo){
    if (RSTOP) break;
    const m = RMAILS[i]; $("#rcSendProg").textContent = `${how === "send" ? "Sending" : "Saving"} ${done + 1} of ${todo.length}…`;
    const r = await api_reach_send(m, how, $("#rcResume").value);
    m.status = r.ok ? (how === "send" ? "Sent ✓" : "Draft saved ✓") : r.skipped ? "Already mailed" : "Not sent: " + r.error;
    const el = $("#mst" + i); if (el) el.textContent = m.status;
    if (r.ok) done++;
    if (r.limit || /app password/i.test(r.error || "")){ toast(r.error, true); break; }
    if (how === "send" && r.ok && i !== todo[todo.length - 1] && !RSTOP){ for (let s = 25 + Math.random() * 20; s > 0 && !RSTOP; s--){ $("#rcSendProg").textContent = `Short pause before the next one (${Math.ceil(s)}s)…`; await sleep(1000); } }
  }
  rcBusy(false); $("#rcSendProg").textContent = done ? `${how === "send" ? "Sent" : "Saved"} ${done}.` : "";
  if (done) toast(how === "send" ? `Sent ${done} mail(s).` : `${done} draft(s) are in your Gmail Drafts.`);
  loadReach();
}

$("#rcGmail").onclick = async () => {
  rcBusy(true); $("#rcFound").hidden = false; $("#rcProg").textContent = "Reading your Gmail…";
  const r = await api_reach_contacts(); $("#rcProg").textContent = ""; rcBusy(false);
  if (!r.ok) return toast(r.error, true);
  const have = new Set(RFOUND.map(x => x.email.toLowerCase()));
  const rows = r.items.filter(c => !have.has(c.email)).slice(0, 80);
  if (!rows.length) return toast("No new contacts found in your Gmail.");
  rows.forEach(c => RFOUND.push({company:c.company, site:c.email.split("@")[1], text:"", emails:[c.email], email:c.email, on:false, links:[],
    note: c.done ? "Already mailed from here." : c.kind === "wrote" ? `You wrote to them before (${c.date}).` : `Wrote to you: ${c.subject}`}));
  drawFound(); toast(`Added ${rows.length} from your Gmail. Tick the ones you want.`);
};

const savePrefs = () => api_reach_prefs({tone:$("#rpTone").value, length:$("#rpLength").value, role:$("#rpRole").value, subject:$("#rpSubject").value,
  include:$("#rpInclude").value, avoid:$("#rpAvoid").value, opt_out:$("#rpOptOut").checked});
const savePrefsSoon = debounce(savePrefs, 500);
["#rpTone", "#rpLength", "#rpRole", "#rpSubject", "#rpInclude", "#rpAvoid", "#rpOptOut"].forEach(s => { $(s).onchange = savePrefsSoon; $(s).oninput = savePrefsSoon; });
$("#rpSample").onclick = async () => {
  $("#rpSample").disabled = true; $("#rpSampleNote").textContent = "Writing…"; await savePrefs();
  const w = await api_reach_write("Acme Marketing", "A digital marketing agency that helps brands with social media, content and email campaigns.");
  $("#rpSample").disabled = false; $("#rpSampleNote").textContent = "A made-up company, only so you can hear the tone.";
  if (!w.ok) return toast(w.error, true);
  $("#rpSampleText").hidden = false; $("#rpSampleText").value = "Subject: " + w.subject.replace("your company", "Acme Marketing") + "\n\n" + w.body;
};

let RSUM = null;
function drawTiles(){
  const h = REACH.history || [], sent = h.filter(x => x.how === "sent").length, drafts = h.length - sent, rep = RSUM ? RSUM.replies.length : null;
  const tile = (n, l, k) => `<div class="stagebox k-${k}"><div class="n">${n}</div><div class="l">${l}</div></div>`;
  $("#rcTiles").innerHTML = tile(sent, "Mails sent", "applied") + tile(drafts, "Saved as drafts", "saved") + tile(rep ?? "–", "Replies", "offer")
    + tile(rep === null || !sent ? "–" : Math.round(100 * rep / sent) + "%", "Reply rate", "heard") + tile(RSUM ? RSUM.others.length : "–", "Others wrote to you", "int") + tile((REACH.other || []).length, "Other ways", "saved");
}
const rcList = (rows, empty) => rows.length ? rows.map(x => `<div style="padding:5px 0;border-bottom:1px solid var(--line)"><b>${esc(x.company)}</b> <span class="muted">${esc(x.email)}</span><br>
  <span class="muted small">${esc(when(x.date))} · ${esc(x.subject)}</span></div>`).join("") : empty;
async function checkReplies(){
  $("#rcCheck").disabled = true; $("#rcCheck").textContent = "Checking…";
  const r = await api_reach_summary(); $("#rcCheck").disabled = false; $("#rcCheck").textContent = "Check for replies";
  if (!r.ok) return toast(r.error, true);
  RSUM = r; drawTiles();
  $("#rcReplies").innerHTML = rcList(r.replies, "No replies yet. Most come within a week or two.");
  $("#rcOthers").innerHTML = rcList(r.others, "Nobody new in the last 60 days.");
  const rep = new Set(r.replies.map(x => x.email));
  $$("#rcHistory [data-em]").forEach(td => td.textContent = rep.has(td.dataset.em) || r.replies.some(x => x.email.split("@")[1] === td.dataset.em.split("@")[1] && !/gmail|yahoo|outlook|hotmail/.test(x.email)) ? "Replied ✓" : "");
}
$("#rcCheck").onclick = checkReplies;

function drawOther(){
  const o = REACH.other || [];
  $("#roList").innerHTML = o.length ? o.map(x => `<div class="row" style="padding:6px 0;border-bottom:1px solid var(--line)"><span class="tag">${esc(x.channel)}</span>
    <div class="grow"><b>${esc(x.who || "Someone")}</b> <span class="muted small">${esc(when(x.date))}</span><br><span class="muted small">${esc(x.note)}</span></div>
    <button class="tag x" data-rod="${esc(x.id)}" title="Remove">×</button></div>`).join("") : `<p class="muted small">Nothing written down yet.</p>`;
  $$("#roList [data-rod]").forEach(b => b.onclick = async () => { const r = await api_reach_other_delete(b.dataset.rod); REACH.other = r.other; drawOther(); drawTiles(); });
}
$("#roAdd").onclick = async () => {
  const r = await api_reach_other_add($("#roChannel").value, $("#roWho").value, $("#roNote").value, $("#roDate").value);
  if (!r.ok) return toast(r.error, true);
  REACH.other = r.other; $("#roWho").value = ""; $("#roNote").value = ""; drawOther(); drawTiles(); toast("Added.");
};
