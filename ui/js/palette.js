/* ===== activity, report, palette ===== */
let LOGTEXT = "";
function addLog(t){ LOGTEXT += t + "\n"; const el = $("#log"); if (el){ el.textContent = LOGTEXT; el.parentElement.scrollTop = el.parentElement.scrollHeight; } }
function openActivity(){
  $("#layer").innerHTML = `<div class="scrim" id="scrim"></div><aside class="drawer" aria-label="Activity"><div class="dh"><div class="grow"><h2>Activity</h2><div class="muted small">Everything the app is doing, step by step</div></div>
    <button class="btn sm" id="copyLog">Copy</button><button class="btn sm" data-open2="logs">Logs</button><button class="btn sm ghost" id="closeDrawer">${icon("x")}</button></div>
    <div class="db"><pre id="log"></pre></div></aside>`;
  $("#log").textContent = LOGTEXT || "Nothing yet."; $("#log").parentElement.scrollTop = 1e9;
  const close = () => $("#layer").innerHTML = ""; $("#scrim").onclick = close; $("#closeDrawer").onclick = close;
  $("[data-open2]").onclick = () => api_open("logs");
  $("#copyLog").onclick = async () => { try { await navigator.clipboard.writeText(LOGTEXT); } catch(e){ const ta = document.createElement("textarea"); ta.value = LOGTEXT; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); } toast("Activity copied"); };
}
$("#activityBtn").onclick = openActivity;
/* Pictures for a report or idea: pick files or paste a screenshot (Ctrl+V anywhere in the box). Up to 5, each under 5 MB. */
let PICS = [];
const picsHtml = () => `<div class="row" style="margin-top:10px"><label class="btn" style="cursor:pointer">Add a picture<input type="file" id="picIn" accept="image/*" multiple hidden></label><span class="muted">or press Ctrl+V to paste a screenshot</span></div><div class="row" id="picList" style="margin-top:8px;gap:8px"></div>`;
function picsInit(){
  PICS = [];
  const draw = () => { $("#picList").innerHTML = PICS.map((p, i) => `<span style="position:relative"><img src="data:image/png;base64,${p.data}" style="height:56px;border-radius:8px;border:1px solid var(--line,#ddd)"><button class="btn ghost" data-rm="${i}" title="Remove" style="position:absolute;top:-8px;right:-8px;padding:0 6px;min-height:0">×</button></span>`).join("");
    $("#picList").querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { PICS.splice(+b.dataset.rm, 1); draw(); }); };
  const add = files => [...files].filter(f => f.type.startsWith("image/")).forEach(f => {
    if (PICS.length >= 5) return toast("Up to 5 pictures", true);
    if (f.size > 5e6) return toast("That picture is too big (over 5 MB)", true);
    const r = new FileReader(); r.onload = () => { PICS.push({ name: f.name || "screenshot.png", data: String(r.result).split(",")[1] }); draw(); }; r.readAsDataURL(f); });
  $("#picIn").onchange = e => { add(e.target.files); e.target.value = ""; };
  const onPaste = e => { if (!$("#picList")) return document.removeEventListener("paste", onPaste);
    const fs = [...(e.clipboardData?.files || [])]; if (fs.length) { e.preventDefault(); add(fs); } };
  document.addEventListener("paste", onPaste);
}
function openReport(){
  $("#layer").innerHTML = `<div class="modal"><div class="sheet" style="--k:var(--rose)"><div class="sh"><div class="kind">Report a problem</div><h2>What went wrong?</h2>
    <p class="msg">A short note helps, like "Swiggy job stopped on the second page". The activity log and screenshots are attached, and you can add your own pictures. Passwords never are.</p></div>
    <div class="sb"><textarea id="reportText" rows="4" placeholder="Describe what happened (optional)"></textarea>${picsHtml()}
    <div class="row" style="margin-top:14px"><button class="btn primary" id="reportSend">Send report</button><button class="btn ghost" id="reportCancel">Cancel</button></div></div></div></div>`;
  setTimeout(() => $("#reportText").focus(), 30); picsInit();
  $("#reportCancel").onclick = () => $("#layer").innerHTML = "";
  $("#reportSend").onclick = async () => { const b = $("#reportSend"); b.disabled = true; b.textContent = "Sending"; const r = await api_report($("#reportText").value, PICS); $("#layer").innerHTML = ""; reportResult(r); };
}
function reportResult(r){
  if (!r.ok) return toast("Couldn't make the report: " + r.error, true);
  if (r.created) return toast("Thanks, your report was sent to GitHub");
  const why = r.why ? ` Not sent to GitHub: ${r.why}.` : "";
  if (r.sent) return toast("Report sent to " + r.to + "." + why);
  toast((r.helper ? "Report saved. Attach the highlighted zip to the Gmail draft that opened." : "Report saved in the Reports folder. Send that zip to your helper.") + why);
}
$("#reportBtn").onclick = openReport; $("#reportBtn2").onclick = openReport;
function openSuggest(){
  $("#layer").innerHTML = `<div class="modal"><div class="sheet" style="--k:var(--rose)"><div class="sh"><div class="kind">Suggest a feature</div><h2>What would help you?</h2>
    <p class="msg">Describe what you wish the app could do. It goes straight to the person who looks after it.</p></div>
    <div class="sb"><textarea id="suggestText" rows="4" placeholder="For example: remind me to follow up after a week"></textarea>${picsHtml()}
    <div class="row" style="margin-top:14px"><button class="btn primary" id="suggestSend">Send idea</button><button class="btn ghost" id="suggestCancel">Cancel</button></div></div></div></div>`;
  setTimeout(() => $("#suggestText").focus(), 30); picsInit();
  $("#suggestCancel").onclick = () => $("#layer").innerHTML = "";
  $("#suggestSend").onclick = async () => { const t = $("#suggestText").value.trim(); if (!t) return toast("Please write your idea first", true);
    const b = $("#suggestSend"); b.disabled = true; b.textContent = "Sending"; const r = await api_suggest(t, PICS); $("#layer").innerHTML = "";
    if (!r.ok) return toast("Couldn't send the idea: " + r.error, true);
    toast("Thanks, your idea was sent"); };
}
$("#suggestBtn").onclick = openSuggest; $("#suggestBtn2").onclick = openSuggest;

const ACTIONS = [
  ["Go to Home", () => go("home"), "1"], ["Apply to a job", () => { go("apply"); setTimeout(() => $("#links").focus(), 50); }, "2"],
  ["Find new jobs", () => go("find"), "3"], ["Open My jobs", () => go("jobs"), "4"], ["Edit Profile", () => go("profile"), "5"], ["Open Settings", () => go("settings"), "6"],
  ["Check email now", () => { go("home"); $("#checkMailBtn").click(); }], ["Apply to all saved jobs", () => startApply(SAVED)],
  ["Theme: Sand", () => setTheme("sand")], ["Theme: Emerald", () => setTheme("emerald")], ["Theme: Slate", () => setTheme("slate")], ["Theme: Clean white", () => setTheme("clean")], ["Theme: Mint", () => setTheme("mint")], ["Check for updates", () => checkUpdates(true)],
  ["Show activity", openActivity], ["Report a problem", openReport], ["Suggest a feature", openSuggest],["What's new", showNews], ["Add a resume or file", () => { go("profile"); setTimeout(() => $("#addFile").click(), 80); }]];
function openPalette(){
  $("#layer").innerHTML = `<div class="palette" id="pal"><div class="box"><input type="text" id="palIn" placeholder="Type a command, e.g. dark, email, apply"><div class="list" id="palList"></div></div></div>`;
  let sel = 0; const list = () => ACTIONS.filter(a => a[0].toLowerCase().includes($("#palIn").value.toLowerCase()));
  const draw = () => { const l = list(); sel = Math.min(sel, Math.max(0, l.length - 1));
    $("#palList").innerHTML = l.map((a, i) => `<div class="pi ${i === sel ? "on" : ""}" data-i="${i}">${icon("sparkle")}<span>${esc(a[0])}</span>${a[2] ? `<small>${a[2]}</small>` : ""}</div>`).join("") || `<div class="muted small" style="padding:12px">No match</div>`;
    $$("#palList .pi").forEach(el => el.onclick = () => run(l[+el.dataset.i])); };
  const run = a => { $("#layer").innerHTML = ""; a && a[1](); };
  $("#pal").onclick = e => { if (e.target.id === "pal") $("#layer").innerHTML = ""; };
  $("#palIn").oninput = () => { sel = 0; draw(); };
  $("#palIn").onkeydown = e => { const l = list(); if (e.key === "ArrowDown"){ sel = (sel + 1) % l.length; draw(); e.preventDefault(); }
    else if (e.key === "ArrowUp"){ sel = (sel - 1 + l.length) % l.length; draw(); e.preventDefault(); } else if (e.key === "Enter") run(l[sel]); };
  draw(); $("#palIn").focus();
}
$("#paletteBtn").onclick = openPalette;
document.addEventListener("keydown", e => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k"){ e.preventDefault(); openPalette(); return; }
  if (e.key === "Escape"){ if (ASK) return; $("#layer").innerHTML = ""; return; }
  if (ASK && !typing && /^[1-9]$/.test(e.key)){ const o = ASK.options[+e.key - 1]; if (o !== undefined) reply(o); return; }
  if (!typing && !ASK && !$("#layer").innerHTML && /^[1-6]$/.test(e.key)) go(PAGES[+e.key - 1]);
});

$("#moreBtn").onclick = () => { const box = $("#moreBox"); box.hidden = !box.hidden; $("#moreBtn").setAttribute("aria-expanded", String(!box.hidden)); };

async function loadFeedback(){
  const box = $("#feedbackList"); box.textContent = "Loading…";
  const r = await api_my_issues();
  if (!r.ok) { box.textContent = r.error; return; }
  if (!r.items || !r.items.length) { box.textContent = "Nothing sent yet."; return; }
  const tone = {Done: "color:var(--ok,#2e7d32)", "Won't do": "color:var(--muted)"};
  box.innerHTML = r.items.map(i => `<div class="item"><div class="body"><b>${esc(i.title)}</b><span>${i.kind === "bug" ? "Problem" : "Idea"} · ${when(i.date)}${i.comments ? ` · ${i.comments} repl${i.comments === 1 ? "y" : "ies"}` : ""}${i.labels.length ? " · " + esc(i.labels.join(", ")) : ""}</span></div>
    <div class="side-acts"><span class="tag" style="${tone[i.status] || ""}">${i.status}</span><a class="btn sm ghost" href="${esc(i.url)}">View</a></div></div>`).join("");
}
$("#feedbackRefresh").onclick = loadFeedback;
