/* ===== find jobs ===== */
let RESUME = null, ROLES = [], COMPS = [];
function addTag(kind, v){ v = v.trim(); if (!v) return; const arr = kind === "role" ? ROLES : COMPS;
  if (!arr.some(x => x.toLowerCase() === v.toLowerCase())) arr.push(v); renderTags(); }
function renderTags(){
  for (const [kind, box, input] of [["role","#rolesBox","#roleInput"],["comp","#compBox","#compInput"]]){
    const arr = kind === "role" ? ROLES : COMPS; $$(box + " .tag").forEach(t => t.remove());
    arr.forEach((v, i) => { const t = document.createElement("span"); t.className = "tag"; t.innerHTML = `${esc(v)}<button class="x" title="Remove">×</button>`;
      t.querySelector("button").onclick = () => { arr.splice(i, 1); renderTags(); }; $(box).insertBefore(t, $(input)); });
  }
}
for (const [kind, input, box] of [["role","#roleInput","#rolesBox"],["comp","#compInput","#compBox"]]){
  $(input).onkeydown = e => { if ((e.key === "Enter" || e.key === ",") && e.target.value.trim()){ e.preventDefault(); e.target.value.split(",").forEach(v => addTag(kind, v)); e.target.value = ""; }
    else if (e.key === "Backspace" && !e.target.value){ (kind === "role" ? ROLES : COMPS).pop(); renderTags(); } };
  $(box).onclick = () => $(input).focus();
}
async function loadResume(){
  const r = await api_resume(); RESUME = r;
  if (!r.ok){ $("#skills").innerHTML = `<span class="muted">${esc(r.error)}</span>`; $("#expLine").textContent = ""; return; }
  $("#expLine").textContent = (r.years ? `${r.years} years of experience` : "Experience not found") + (r.locations?.length ? `, looking in ${r.locations.join(", ")}` : "");
  $("#skills").innerHTML = (r.skills || []).map(s => `<span class="tag">${esc(s)}</span>`).join("") || `<span class="muted">No marketing skills recognised yet.</span>`;
  if (!ROLES.length) (r.roles || []).forEach(x => addTag("role", x));
}
$("#findBtn").onclick = async () => {
  if ($("#compInput").value.trim()){ addTag("comp", $("#compInput").value); $("#compInput").value = ""; }
  const auto = $("#autoSearch").checked;
  const r = await api_start_find(ROLES.join(", "), auto ? "" : COMPS.join(", "), auto, !auto && $("#allOpenings").checked);
  if (!r.ok) toast(r.error, true); else { $("#foundPanel").hidden = true; toast("Searching"); }
};
/* One choice instead of three switches: search widely for her, or only the companies she lists */
function setFindMode(m){
  $("#autoSearch").checked = m === "auto"; $("#compField").hidden = m === "auto"; $("#allWrap").hidden = m === "auto";
  $$("#findMode button").forEach(b => b.classList.toggle("on", b.dataset.m === m));
  $("#findModeHint").textContent = m === "auto" ? "I look through the job pages of many companies for roles that fit your resume and cities." : "";
  $("#findModeHint").hidden = m !== "auto";
}
$$("#findMode button").forEach(b => b.onclick = () => setFindMode(b.dataset.m));
setFindMode("auto");
$("#dailyFind").onchange =e => { api_set_daily(e.target.checked); toast(e.target.checked ? "This search will repeat daily" : "Daily search off"); };
function diagText(d){
  if (!d || d.fetched === undefined) return "";
  const parts = [["seen","already seen or applied"],["title","not your kind of role"],["city","in other cities"],["old","too old"],["match","below your minimum match"]]
    .filter(([k]) => d[k]).map(([k, t]) => `${d[k]} ${t}`);
  const miss = (d.missing || []).length ? ` I couldn't read the job lists of ${d.missing.join(", ")}: they use their own hiring website. Paste their careers-page link instead, or choose "Find jobs for me".` : "";
  return `Last search: looked at ${d.sites} company job page${d.sites === 1 ? "" : "s"} with ${d.fetched} opening${d.fetched === 1 ? "" : "s"}` +
    (parts.length ? `. Left out ${parts.join(", ")}.` : ".") + miss + (d.sites === 0 && !miss ? " Choose \"Find jobs for me\" above to search more widely." : "");
}
let ONLY_LAST = false;                           // right after a search: show only what that search found
async function loadFound(diag){ showFound(await api_found(), diag); }
function showFound(jobs, diag){
  FOUND = jobs; OFF.clear(); jobs.forEach((j, i) => { if (j.dup || j.alert) OFF.add(i); }); $("#foundPanel").hidden = false;   // jobs she already applied to start unticked
  if (diag !== undefined) ONLY_LAST = !!(diag && diag.fetched !== undefined);       // a dismiss reloads without diag: keep the view
  $("#findDiag").textContent = diagText(diag || STATE.find_diag);
  fillAlerts(); $("#foundFilters").hidden = !jobs.length; drawFound();
  const fresh = jobs.filter(j => j.last).length;
  if (PAGE !== "find" && diag && fresh){ setCount("#navFound", fresh); toast(`${fresh} new job${fresh > 1 ? "s" : ""} that fit you`); }
}
const OFF = new Set();                          // jobs she unticked: kept when the filters change
function foundView(){
  const q = $("#fQ").value.trim().toLowerCase(), age = +$("#fAge").value, min = +$("#fMin").value, sort = $("#fSort").value;
  const rows = FOUND.map((j, i) => [j, i]).filter(([j]) => (!ONLY_LAST || j.last) && alertOk(j) && (!q ||`${j.title} ${j.company} ${j.location || ""}`.toLowerCase().includes(q)) &&
    (!age || j.age == null || +j.age < age + (age === 1 ? 1 : 0)) && (!min || j.score >= min));
  if (sort === "new") rows.sort((a, b) => (a[0].age ?? 999) - (b[0].age ?? 999));
  else if (sort === "co") rows.sort((a, b) => a[0].company.localeCompare(b[0].company));
  return rows;
}
let FOUND_SHOWN = 60;                            // long lists are drawn 60 at a time so the page stays quick
let ALERTS_OPEN = false, OFFROLE_OPEN = false, ALERT_SHOWN = 30;       // alert-email links sit in their own folded box under the real jobs
function jobBtns(j, i){
  return `<span class="row" style="gap:4px"><a class="btn sm ghost" href="${esc(j.link)}" target="_blank" onclick="event.stopPropagation()" title="Open">${icon("ext")}</a>
      <button class="btn sm ghost" data-dis="${i}" title="Not interested">${icon("x")}</button></span>`;
}
function jobCard(j, i){                          // an alert-email job as a small card: title, company, then match, site and buttons
  const co = / alert$/.test(j.company) ? "" : j.company, place = [co, j.location].filter(Boolean).join(", ");
  const tone = j.score >= 70 ? "hi" : j.score >= 50 ? "mid" : "lo";
  return `<label class="al-card"><input type="checkbox" class="fj" data-i="${i}"${OFF.has(i) ? "" : " checked"}>
      <div class="al-main"><b>${esc(j.title)}</b>${place ? `<span>${esc(place)}</span>` : ""}</div>
      <div class="al-foot"><span class="al-match ${tone}" title="From the job title only">${j.score}% match</span><em>${esc(j.site)}</em>${jobBtns(j, i)}</div></label>`;
}
function jobRow(j, i){
  return `<label class="result"><input type="checkbox" class="fj" data-i="${i}"${OFF.has(i) ? "" : " checked"}>
      <div class="ring" style="--p:${j.score}">${j.score}</div>
      <div><b>${esc(j.title)}</b><span>${esc(j.company)}${j.location ? `, ${esc(j.location)}` : ""}${j.age != null ? `. Posted ${+j.age === 0 ? "today" : j.age + " days ago"}` : ""}</span>${j.dup ? `<span class="dupwarn">You already applied to this job on ${esc(j.dup.slice(0, 10))}, through another link</span>` : ""}</div>${jobBtns(j, i)}</label>`;
}
function drawFound(more){
  if (more !== true){ FOUND_SHOWN = 60; ALERT_SHOWN = 30; }
  const jobs = FOUND, all = foundView(), rows = all.slice(0, FOUND_SHOWN);
  const lastN = FOUND.filter(j => j.last).length, earlier = FOUND.length - lastN, s = n => n > 1 ? "s" : "";
  $("#foundTitle").textContent = ONLY_LAST ? (lastN ? `${lastN} new job${s(lastN)} from this search` : "No new jobs from this search")
    : FOUND.length ? `${FOUND.length} job${s(FOUND.length)} that fit you` : "No matching jobs yet";
  const nAl = FOUND.filter(j => !alertOk(j)).length;
  if (nAl) $("#foundTitle").textContent += ` (${nAl} from alert emails hidden)`;
  $("#foundScope")?.remove();
  if (ONLY_LAST ? earlier : lastN && earlier) $("#findDiag").insertAdjacentHTML("beforeend", ` <a href="#" id="foundScope">${ONLY_LAST ? `Show ${earlier} job${s(earlier)} found before` : "Show only the last search"}</a>`);
  $("#foundScope") && ($("#foundScope").onclick = e => { e.preventDefault(); ONLY_LAST = !ONLY_LAST; drawFound(); });
  const real = all.filter(([j]) => !j.alert), al = all.filter(([j]) => j.alert), shown = real.slice(0, FOUND_SHOWN);
  const open = ALERTS_OPEN || (!real.length && al.length);
  const fit = al.filter(([j]) => !j.off).sort((a, b) => b[0].score - a[0].score), off = al.filter(([j]) => j.off);
  const alShown = fit.slice(0, ALERT_SHOWN), offShown = OFFROLE_OPEN ? off.slice(0, ALERT_SHOWN) : [];
  const grid = list => `<div class="al-grid">${list.map(([j, i]) => jobCard(j, i)).join("")}</div>`;
  let html = shown.map(([j, i]) => jobRow(j, i)).join("") +
    (real.length > shown.length ? `<button class="btn sm feed-more" id="foundMore">Show more (${real.length - shown.length} left)</button>` : "");
  if (al.length) html += `<div class="al-box"><button class="al-head" id="alToggle" aria-expanded="${open}"><b>From job alert emails</b>
      <span>${al.length} link${al.length > 1 ? "s" : ""} from ${[...new Set(al.map(([j]) => j.site))].join(", ")}. The match is from the job title only.</span>
      <span class="al-act">${open ? "Hide" : "Show"}</span></button>` +
    (open ? `<div class="al-body">${fit.length ? grid(alShown) : `<p class="small muted">None of these look like your kind of role.</p>`}` +
      (fit.length > alShown.length ? `<button class="btn sm feed-more" id="alMore">Show more (${fit.length - alShown.length} left)</button>` : "") +
      (off.length ? `<button class="btn sm ghost feed-more" id="offToggle">${OFFROLE_OPEN ? "Hide" : "Show"} ${off.length} job${off.length > 1 ? "s" : ""} that don't match your job titles</button>${OFFROLE_OPEN ? grid(offShown) : ""}` : "") + `</div>` : "") + `</div>`;
  $("#foundList").innerHTML = html ||
    (ONLY_LAST && !lastN ? emptyHTML("search", "No new jobs from this search", "The note above says why. Jobs found before are still saved.")
    : jobs.length ? emptyHTML("search", "No jobs match these filters", "Clear a filter above to see more.")
    : emptyHTML("search", "Nothing here yet", "Choose where to search above and press Find jobs. A lower minimum match in Settings shows more."));
  $("#alToggle") && ($("#alToggle").onclick = () => { ALERTS_OPEN = !open; drawFound(true); });
  $("#alMore") && ($("#alMore").onclick = () => { ALERT_SHOWN += 30; drawFound(true); });
  $("#offToggle") && ($("#offToggle").onclick = () => { OFFROLE_OPEN = !OFFROLE_OPEN; drawFound(true); });
  $("#bulk").hidden = !jobs.length; updateBulk();
  $("#foundMore") && ($("#foundMore").onclick = () => { FOUND_SHOWN += 60; drawFound(true); });
  $$(".fj").forEach(c => c.onchange = () => { c.checked ? OFF.delete(+c.dataset.i) : OFF.add(+c.dataset.i); updateBulk(); });
  $$("#foundList [data-dis]").forEach(b => b.onclick = async e => { e.preventDefault(); e.stopPropagation();
    await api_dismiss_found(FOUND[+b.dataset.dis].link); loadFound(); });
}
$("#fQ").oninput = debounce(() => drawFound()); $("#fAge").onchange = $("#fMin").onchange = $("#fSort").onchange = () => drawFound();
function alertOk(j){ const a = STATE.alert_show || ""; return !j.alert || !a || (a !== "none" && j.site === a); }
function fillAlerts(){                           // "Alert emails": all, one site (LinkedIn, Indeed...) or none
  const sites = [...new Set(["LinkedIn", "Indeed", "Naukri", ...FOUND.filter(j => j.alert).map(j => j.site)])], cnt = x => FOUND.filter(j => j.site === x).length, cur = STATE.alert_show || "";
  $("#fAlerts").hidden = !FOUND.some(j => j.alert);
  $("#fAlerts").innerHTML = `<option value="">Alert emails: all</option>` + sites.map(x => `<option value="${esc(x)}">Alert emails: ${esc(x)} only (${cnt(x)})</option>`).join("") + `<option value="none">Alert emails: hide all</option>`;
  $("#fAlerts").value = cur;
  if ($("#fAlerts").value !== cur){ $("#fAlerts").value = ""; STATE.alert_show = ""; }
}
$("#fAlerts").onchange = () => { STATE.alert_show = $("#fAlerts").value; api_set_alert_show(STATE.alert_show); drawFound(); };
function picked(){ return foundView().filter(([, i]) => !OFF.has(i)).map(([j]) => j.link); }     // every shown-by-filter job, also those not drawn yet
function updateBulk(){ const n = picked().length; $("#bulkText").textContent = `${n} selected`; }
function selectShown(on){ foundView().forEach(([, i]) => on ? OFF.delete(i) : OFF.add(i)); $$(".fj").forEach(c => c.checked = on); updateBulk(); }
$("#selAll").onclick = () => selectShown(true); $("#selNone").onclick = () => selectShown(false);
$("#applyFoundBtn").onclick = () => { const l = picked(); if (!l.length) return toast("Select at least one job", true); startApply(l); };
$("#saveFoundBtn").onclick = async () => { const l = picked(); if (!l.length) return toast("Select at least one job", true);
  const r = await api_add_to_list(l); toast(`${r.added} saved for later`); loadState(); };
