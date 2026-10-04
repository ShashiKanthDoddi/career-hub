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
  const r = await api_start_find(ROLES.join(", "), COMPS.join(", "), $("#autoSearch").checked, $("#allOpenings").checked);
  if (!r.ok) toast(r.error, true); else { $("#foundPanel").hidden = true; toast("Searching"); }
};
$("#dailyFind").onchange = e => { api_set_daily(e.target.checked); toast(e.target.checked ? "This search will repeat daily" : "Daily search off"); };
function diagText(d){
  if (!d || d.fetched === undefined) return "";
  const parts = [["seen","already seen or applied"],["title","not your kind of role"],["city","in other cities"],["old","too old"],["match","below your minimum match"]]
    .filter(([k]) => d[k]).map(([k, t]) => `${d[k]} ${t}`);
  return `Last search: checked ${d.sites} career site${d.sites === 1 ? "" : "s"} and ${d.fetched} job${d.fetched === 1 ? "" : "s"}` +
    (parts.length ? `. Skipped ${parts.join(", ")}.` : ".") + (d.sites === 0 ? " Add company names or careers-page links above to find more." : "");
}
async function loadFound(diag){ showFound(await api_found(), diag); }
function showFound(jobs, diag){
  FOUND = jobs; OFF.clear(); jobs.forEach((j, i) => { if (j.dup) OFF.add(i); }); $("#foundPanel").hidden = false;   // jobs she already applied to start unticked
  $("#foundTitle").textContent = jobs.length ? `${jobs.length} job${jobs.length > 1 ? "s" : ""} that fit you` : "No matching jobs yet";
  $("#findDiag").textContent = diagText(diag || STATE.find_diag);
  $("#foundFilters").hidden = !jobs.length; drawFound();
  if (PAGE !== "find" && diag && jobs.length){ setCount("#navFound", jobs.length); toast(`${jobs.length} job${jobs.length > 1 ? "s" : ""} that fit you`); }
}
const OFF = new Set();                          // jobs she unticked: kept when the filters change
function foundView(){
  const q = $("#fQ").value.trim().toLowerCase(), age = +$("#fAge").value, min = +$("#fMin").value, sort = $("#fSort").value;
  const rows = FOUND.map((j, i) => [j, i]).filter(([j]) => (!q || `${j.title} ${j.company} ${j.location || ""}`.toLowerCase().includes(q)) &&
    (!age || j.age == null || +j.age < age + (age === 1 ? 1 : 0)) && (!min || j.score >= min));
  if (sort === "new") rows.sort((a, b) => (a[0].age ?? 999) - (b[0].age ?? 999));
  else if (sort === "co") rows.sort((a, b) => a[0].company.localeCompare(b[0].company));
  return rows;
}
let FOUND_SHOWN = 60;                            // long lists are drawn 60 at a time so the page stays quick
function drawFound(more){
  if (more !== true) FOUND_SHOWN = 60;
  const jobs = FOUND, all = foundView(), rows = all.slice(0, FOUND_SHOWN);
  $("#foundList").innerHTML = rows.length ? rows.map(([j, i]) => `<label class="result"><input type="checkbox" class="fj" data-i="${i}"${OFF.has(i) ? "" : " checked"}>
      <div class="ring" style="--p:${j.score}">${j.score}</div>
      <div><b>${esc(j.title)}</b><span>${esc(j.company)}${j.location ? `, ${esc(j.location)}` : ""}${j.age != null ? `. Posted ${+j.age === 0 ? "today" : j.age + " days ago"}` : ""}</span>${j.dup ? `<span class="dupwarn">You already applied to this job on ${esc(j.dup.slice(0, 10))}, through another link</span>` : ""}</div>
      <span class="row" style="gap:4px"><a class="btn sm ghost" href="${esc(j.link)}" target="_blank" onclick="event.stopPropagation()" title="Open">${icon("ext")}</a>
      <button class="btn sm ghost" data-dis="${i}" title="Not interested">${icon("x")}</button></span></label>`).join("") +
      (all.length > rows.length ? `<button class="btn sm feed-more" id="foundMore">Show more (${all.length - rows.length} left)</button>` : "")
    : jobs.length ? emptyHTML("search", "No jobs match these filters", "Clear a filter above to see more.")
    : emptyHTML("search", "Nothing here yet", "Add companies or careers-page links, keep web search on, and press Find jobs. A lower minimum match in Settings shows more.");
  $("#bulk").hidden = !jobs.length; updateBulk();
  $("#foundMore") && ($("#foundMore").onclick = () => { FOUND_SHOWN += 60; drawFound(true); });
  $$(".fj").forEach(c => c.onchange = () => { c.checked ? OFF.delete(+c.dataset.i) : OFF.add(+c.dataset.i); updateBulk(); });
  $$("#foundList [data-dis]").forEach(b => b.onclick = async e => { e.preventDefault(); e.stopPropagation();
    await api_dismiss_found(FOUND[+b.dataset.dis].link); loadFound(); });
}
$("#fQ").oninput = debounce(() => drawFound()); $("#fAge").onchange = $("#fMin").onchange = $("#fSort").onchange = () => drawFound();
function picked(){ return foundView().filter(([, i]) => !OFF.has(i)).map(([j]) => j.link); }     // every shown-by-filter job, also those not drawn yet
function updateBulk(){ const n = picked().length; $("#bulkText").textContent = `${n} selected`; }
function selectShown(on){ foundView().forEach(([, i]) => on ? OFF.delete(i) : OFF.add(i)); $$(".fj").forEach(c => c.checked = on); updateBulk(); }
$("#selAll").onclick = () => selectShown(true); $("#selNone").onclick = () => selectShown(false);
$("#applyFoundBtn").onclick = () => { const l = picked(); if (!l.length) return toast("Select at least one job", true); startApply(l); };
$("#saveFoundBtn").onclick = async () => { const l = picked(); if (!l.length) return toast("Select at least one job", true);
  const r = await api_add_to_list(l); toast(`${r.added} saved for later`); loadState(); };
