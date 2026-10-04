/* ===== profile & settings forms ===== */
const SETTINGS_SECTIONS = {"Job email (Gmail)":"set-email", "Job-site accounts":"set-accounts", "Applying":"set-applying", "Finding jobs":"set-finding", "AI helper (optional)":"set-ai"};
const SETTINGS_TITLES = {"Job email (Gmail)":"Job email", "Job-site accounts":"Job-site logins", "Applying":"Applying", "Finding jobs":"Finding jobs", "AI helper (optional)":"AI helper"};
const SETTINGS_INTRO = {"Job email (Gmail)":"Reads your job Gmail for replies from companies. It never sends from, deletes or changes your emails.",
  "Job-site accounts":"The password the app uses when it creates a new account on a job site. Use one that's only for job sites.",
  "Applying":"", "Finding jobs":"Used by Find jobs to decide what fits.", "AI helper (optional)":"With a Claude API key, the app can draft written answers and tailored cover letters. You always review them first."};
let DIRTY = {profile:false, settings:false};
const SWITCHES = ["pause_after_each_page", "ai_cover_letters", "gmail_auto"];
function fieldHTML(f, i){
  let input;
  if (f.type === "switch" || SWITCHES.includes(f.key))
    return `<div class="field ${f.label.length > 46 ? "wide" : ""}"><label>${esc(f.label)}</label><label class="switch" style="margin-top:6px"><input type="checkbox" data-i="${i}" ${/^no/i.test(f.value) ? "" : f.value || f.type === "switch" ? "checked" : ""}> <span class="muted small">${/^no/i.test(f.value) ? "Off" : "On"}</span></label>${f.hint ? `<div class="hint">${esc(f.hint)}</div>` : ""}</div>`;
  if (f.type === "choice") input = `<select data-i="${i}"><option value="">Ask me each time</option>${f.options.map(o => `<option ${f.value === o ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
  else if (f.type === "yesno") input = `<select data-i="${i}"><option value="">Ask me each time</option>${["Yes","No"].map(o => `<option ${f.value === o ? "selected" : ""}>${o}</option>`).join("")}</select>`;
  else if (f.type === "file"){ const files = [...new Set([...(STATE.files || []), f.value].filter(Boolean))];
    input = `<select data-i="${i}"><option value="">None</option>${files.map(o => `<option ${f.value === o ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`; }
  else { const t = f.type === "number" ? "number" : f.type === "secret" ? "password" : "text";
    input = `<input type="${t}" data-i="${i}" value="${esc(f.value)}" ${f.type === "secret" ? 'autocomplete="off" data-secret="1"' : ""}>`; }
  return `<div class="field ${f.label.length > 46 ? "wide" : ""}"><label>${esc(f.label)}</label>${input}${f.hint ? `<div class="hint">${esc(f.hint)}</div>` : ""}</div>`;
}
function renderForms(){
  $("#profileErr").hidden = !STATE.profile_error; $("#profileErr").textContent = STATE.profile_error || "";
  const groups = {}; STATE.profile.forEach((f, i) => (groups[f.section] = groups[f.section] || []).push([f, i]));
  let pHTML = "", sHTML = "", pNav = [], sNav = [["set-appearance","Appearance"]];
  for (const [sec, items] of Object.entries(groups)){
    if (sec === "Files"){ $("#fileForm").innerHTML = items.map(([f, i]) => fieldHTML(f, i)).join(""); continue; }
    if (sec === "Help"){ $("#helpFields").innerHTML = items.map(([f, i]) => fieldHTML(f, i)).join(""); continue; }
    if (sec === "Updates"){ $("#updateFields").innerHTML = items.map(([f, i]) => fieldHTML(f, i)).join(""); continue; }
    const id = SETTINGS_SECTIONS[sec];
    const block = `<div class="panel sec" id="${id || "sec-" + sec.replace(/\W+/g, "-").toLowerCase()}"><div class="panel-head"><h2 class="grow">${esc(SETTINGS_TITLES[sec] || sec)}</h2>
      ${sec === "Job email (Gmail)" ? `<button class="btn sm" id="testMailBtn">Test connection</button>` : ""}</div>
      ${SETTINGS_INTRO[sec] ? `<p class="muted small" style="margin-top:-6px">${SETTINGS_INTRO[sec]}</p>` : ""}
      <div class="formgrid">${items.map(([f, i]) => fieldHTML(f, i)).join("")}</div></div>`;
    if (id){ sHTML += block; sNav.push([id, SETTINGS_TITLES[sec]]); } else { pHTML += block; pNav.push(["sec-" + sec.replace(/\W+/g, "-").toLowerCase(), sec]); }
  }
  pNav.push(["sec-files","Your files"],["sec-answers","Saved answers"]); sNav.push(["set-help","Help"],["set-updates","Updates"],["set-news","What's new"]);
  $("#profileForm").innerHTML = pHTML; $("#settingsForm").innerHTML = sHTML;
  $("#profileNav").innerHTML = pNav.map(([id, t]) => `<a href="#${id}" data-sec="${id}">${esc(t)}</a>`).join("");
  $("#settingsNav").innerHTML = sNav.map(([id, t]) => `<a href="#${id}" data-sec="${id}">${esc(t)}</a>`).join("");
  $$(".secnav a").forEach(a => a.onclick = e => { e.preventDefault(); document.getElementById(a.dataset.sec)?.scrollIntoView({behavior: reduce ? "auto" : "smooth", block:"start"});
    $$(".secnav a").forEach(x => x.classList.toggle("on", x === a)); });
  $$("#p-profile [data-i]").forEach(el => el.oninput = el.onchange = () => markDirty("profile"));
  $$("#p-settings [data-i]").forEach(el => el.oninput = el.onchange = () => markDirty("settings"));
  $$('.switch input[data-i]').forEach(el => el.addEventListener("change", () => { const s = el.parentElement.querySelector("span"); if (s) s.textContent = el.checked ? "On" : "Off"; }));
  $$("[data-secret]").forEach(el => { el.onfocus = () => el.type = "text"; el.onblur = () => el.type = "password"; });
  $("#testMailBtn") && ($("#testMailBtn").onclick = async () => { if (DIRTY.settings) await saveForm("settings"); const r = await api_test_mail(); r.ok ? toast("Gmail connected") : toast(r.error, true); });
  renderFiles(); DIRTY = {profile:false, settings:false}; $("#saveBar").hidden = $("#saveBar2").hidden = true;
}
function markDirty(which){ DIRTY[which] = true; $(which === "profile" ? "#saveBar" : "#saveBar2").hidden = false; }
async function saveForm(which){
  const items = $$(`#p-${which} [data-i]`).map(el => { const f = STATE.profile[+el.dataset.i];
    return {where:f.where, key:f.key, value: el.type === "checkbox" ? (el.checked ? "Yes" : "No") : el.value.trim()}; });
  const r = await api_save_profile(items);
  if (r.ok){ toast("Changes saved"); await loadState(); RESUME = null; } else toast("Couldn't save: " + r.error, true);
}
$("#saveBtn").onclick = () => saveForm("profile"); $("#saveBtn2").onclick = () => saveForm("settings");
$("#discardBtn").onclick = $("#discardBtn2").onclick = () => { renderForms(); toast("Changes discarded"); };
function renderFiles(){
  const files = STATE.files || []; const used = {};
  STATE.profile.filter(f => f.type === "file" && f.value).forEach(f => (used[f.value] = used[f.value] || []).push(f.label.replace(/\s*\(optional\)/, "")));
  $("#fileList").innerHTML = files.map(n => `<div class="file">${icon("file")}<span class="grow">${esc(n)}</span>${used[n] ? `<span class="tag">${esc(used[n].join(", "))}</span>` : `<span class="muted small">not used yet</span>`}</div>`).join("");
}
async function addFile(f){
  const b64 = await new Promise(res => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(f); });
  const r = await api_add_file(f.name, b64);
  if (r.ok){ const dirty = DIRTY.profile, vals = $$("#p-profile [data-i]").map(el => [el.dataset.i, el.value]); STATE.files = r.files;
    $("#fileForm").innerHTML = STATE.profile.map((x, i) => [x, i]).filter(([x]) => x.section === "Files").map(([x, i]) => fieldHTML(x, i)).join("");
    vals.forEach(([i, v]) => { const el = $(`#p-profile [data-i="${i}"]`); if (el) el.value = v; });
    const resumeSel = $$("#fileForm select")[0]; if (resumeSel && !resumeSel.value && /\.pdf$/i.test(r.name)) { resumeSel.value = r.name; markDirty("profile"); }
    $$("#fileForm [data-i]").forEach(el => el.oninput = el.onchange = () => markDirty("profile")); if (dirty) markDirty("profile");
    renderFiles(); toast(`${r.name} added`); }
}
const drop = $("#drop");
drop.onclick = () => $("#addFile").click();
$("#addFile").onchange = e => { [...e.target.files].forEach(addFile); e.target.value = ""; };
drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); [...e.dataTransfer.files].forEach(addFile); };

/* saved answers */
let ANS = [];
async function loadAnswers(){ ANS = await api_answers(); renderAnswers(); }
function renderAnswers(){
  const q = $("#ansSearch").value.toLowerCase();
  const rows = ANS.map((a, i) => [a, i]).filter(([a]) => !q || (a[0] + " " + a[1]).toLowerCase().includes(q));
  $("#ansTable").innerHTML = ANS.length ? `<thead><tr><th>Question</th><th>Your answer</th><th>Ask me</th><th></th></tr></thead><tbody>` + rows.map(([a, i]) =>
    `<tr data-i="${i}"><td class="muted" style="width:40%">${esc(a[0])}</td><td><input type="text" value="${esc(a[1])}"></td>
     <td><label class="switch"><input type="checkbox" ${a[2] ? "" : "checked"}></label></td><td><button class="btn sm ghost" data-del="${i}" title="Delete">${icon("x")}</button></td></tr>`).join("") + "</tbody>"
    : `<tbody><tr><td>${emptyHTML("sparkle", "No saved answers yet", "They appear after your first application.")}</td></tr></tbody>`;
  $$("#ansTable [data-del]").forEach(b => b.onclick = async () => { ANS.splice(+b.dataset.del, 1); await saveAnswers(); });
  $$("#ansTable tr[data-i] input").forEach(el => el.onchange = () => { const tr = el.closest("tr"), a = ANS[+tr.dataset.i];
    a[1] = tr.querySelector("input[type=text]").value; a[2] = !tr.querySelector("input[type=checkbox]").checked; saveAnswers(); });
}
async function saveAnswers(){ await api_save_answers(ANS.map(a => [a[0], a[1], a[2]])); toast("Answer saved"); ANS = await api_answers(); renderAnswers(); }
$("#ansSearch").oninput = renderAnswers;

/* appearance & what's new */
// [sidebar, background, card, accent, mode] per theme; previews and data-mode come from here
const THEMES = {
  auto:["#3A2822","#F3E6DA","#FFF7F0","#C0532B","auto"], peach:["#3A2822","#F3E6DA","#FFF7F0","#C0532B","light"],
  mint:["#12403A","#DDEBE6","#F2FAF7","#0E8A70","light"], lavender:["#241A38","#ECE8F4","#F7F5FB","#6B4FD8","light"],
  midnight:["#120D1C","#15111F","#1E182C","#FFD84D","dark"], ocean:["#0A141C","#0E1A24","#142533","#4FC3D6","dark"],
  forest:["#1F3A2B","#E3EBE3","#F3F7F1","#2E7D55","light"], sand:["#23324A","#EFE7DA","#FAF6EE","#2F6D8A","light"],
  rose:["#4A1F35","#F4E6EB","#FCF5F8","#B03A6F","light"], slate:["#0F1114","#16181C","#1E2126","#F0A43A","dark"]};
const THEME_LABEL = {auto:"Match my computer", peach:"Peach", mint:"Mint", lavender:"Lavender", midnight:"Midnight", ocean:"Ocean", forest:"Forest", sand:"Sand", rose:"Rose", slate:"Slate"};
const darkQuery = matchMedia("(prefers-color-scheme: dark)");
function applyTheme(t){
  t = THEMES[t] ? t : "auto";
  const real = t === "auto" ? (darkQuery.matches ? "slate" : "peach") : t;
  document.documentElement.dataset.theme = real; document.documentElement.dataset.mode = THEMES[real][4];
}
darkQuery.addEventListener("change", () => applyTheme(STATE.theme));
function renderThemes(){
  const cur = THEMES[STATE.theme] ? STATE.theme : "auto";
  $("#themes").innerHTML = Object.keys(THEMES).map(t => { const [sb, bg, card, acc] = THEMES[t];
    const half = t === "auto" ? `background:linear-gradient(90deg,${bg} 50%,#16181C 50%)` : `background:${bg}`;
    return `<button class="themecard ${t === cur ? "on" : ""}" data-t="${t}"><div class="pv"><div class="a" style="background:${sb}"></div>
      <div class="b" style="${half}"><i style="background:${acc}"></i><i style="background:${card}"></i><i style="background:${card}"></i></div></div><b>${THEME_LABEL[t]}</b></button>`; }).join("");
  $$(".themecard").forEach(b => b.onclick = () => setTheme(b.dataset.t));
}
async function setTheme(t){ STATE.theme = t; applyTheme(t); renderThemes(); await api_set_theme(t); toast(`${THEME_LABEL[t]} theme`); }
function versionHTML(v, open){ return `<details class="version ${v.version === STATE.version ? "cur" : ""}" ${open ? "open" : ""}>
  <summary>Version ${esc(v.version)}<span>${esc(v.title)}${v.version === STATE.version ? ", the one you have" : ""}</span></summary>
  <ul>${v.new.map(x => `<li>${esc(x)}</li>`).join("")}${v.fixed.map(x => `<li class="fx">Fixed: ${esc(x)}</li>`).join("")}</ul></details>`; }
function renderChangelog(){ $("#changelog").innerHTML = STATE.changelog.map((v, i) => versionHTML(v, i === 0)).join(""); }
function showNews(){ const v = STATE.changelog[0];
  $("#layer").innerHTML = `<div class="modal"><div class="sheet" style="--k:var(--hi)"><div class="sh"><div class="kind" style="color:var(--hi-ink)">Updated to version ${esc(v.version)}</div><h2>${esc(v.title)}</h2></div>
    <div class="sb"><ul style="padding-left:18px;margin:0 0 6px;color:var(--ink-2)">${v.new.map(x => `<li style="margin:4px 0">${esc(x)}</li>`).join("")}${v.fixed.map(x => `<li class="muted" style="margin:4px 0">Fixed: ${esc(x)}</li>`).join("")}</ul>
    <div class="row" style="margin-top:16px"><button class="btn primary" id="newsOk">Got it</button><button class="btn ghost" id="newsAll">See every version</button></div></div></div></div>`;
  const done = () => { $("#layer").innerHTML = ""; api_seen_version(); $("#navNew").hidden = true; };
  $("#newsOk").onclick = done; $("#newsAll").onclick = () => { done(); go("settings"); setTimeout(() => $("#set-news").scrollIntoView({behavior:"smooth"}), 80); }; }
$("#checkUpdBtn").onclick = () => checkUpdates(true);
$("#zipBtn").onclick = () => $("#zipFile").click();
$("#zipFile").onchange = async e => { const file = e.target.files[0]; if (!file) return; e.target.value = "";
  const b64 = await new Promise(res => { const r = new FileReader(); r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(file); });
  const r = await api_install_zip(b64);
  if (r.ok){ await notice(`Version ${r.version} installed`, "The app will restart now. Your data wasn't touched, and a backup was saved."); api_restart(); }
  else toast(r.error, true); };
