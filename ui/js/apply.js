/* ===== apply: one job list (saved_links). Add links, apply to one / selected / all. ===== */
let SAVED = [];
function chipHTML(u){ const [s, who] = site(u);
  return `<div class="linkchip"><span class="site">${s}</span><span class="u" title="${esc(u)}">${esc(who || u)}</span></div>`; }
function renderLinkChips(){ const l = links($("#links").value);
  $("#linkChips").innerHTML = l.map(chipHTML).join("");
  $("#addLinksBtn").textContent = l.length > 1 ? `Add ${l.length} to list` : "Add to list"; }
$("#links").oninput = renderLinkChips;
$("#links").onkeydown = e => { if (e.key === "Enter" && !e.shiftKey){ e.preventDefault(); $("#addLinksBtn").click(); } };
function setSaved(list){ SAVED = list;
  $("#listCount").textContent = list.length;
  const q = $("#savedQ").value.trim().toLowerCase(); $("#savedQ").hidden = list.length < 2;
  const rows = list.map((u, i) => [u, i]).filter(([u]) => !q || u.toLowerCase().includes(q) || site(u).join(" ").toLowerCase().includes(q));
  $("#savedList").innerHTML = rows.length ? rows.map(([u, i]) => { const [s, who] = site(u);
    return `<div class="linkchip"><input type="checkbox" class="sj" data-i="${i}" checked><span class="site">${s}</span>
      <span class="u" title="${esc(u)}">${esc(who || u)}</span><a class="btn sm ghost" href="${esc(u)}" target="_blank" title="Open">${icon("ext")}</a>
      <button class="btn sm" data-go1="${i}">Apply</button><button class="tag x" data-rm="${i}" title="Remove">×</button></div>`; }).join("")
    : list.length ? emptyHTML("link", "No links match", "Clear the filter to see your list.")
    : emptyHTML("link", "Your list is empty", "Paste job links above. Collect them during the week, then apply in one go.");
  $$("#savedList [data-rm]").forEach(b => b.onclick = async () => saveList(SAVED.filter((_, i) => i !== +b.dataset.rm)));
  $$("#savedList [data-go1]").forEach(b => b.onclick = () => startApply([SAVED[+b.dataset.go1]]));
  $$("#savedList .sj").forEach(c => c.onchange = updateApplyBtn);
  updateApplyBtn(); setCount("#navSaved", list.length); renderLimits(list); }
/* "LinkedIn: 7 of 10 left today" under the list, for sites in the list or used today */
async function renderLimits(list){
  let box = $("#siteLimits");
  if (!box){ box = document.createElement("div"); box.id = "siteLimits"; box.className = "muted small"; box.style.marginTop = "10px"; $("#savedList").after(box); }
  const r = await api_site_limits(); if (!Array.isArray(r)){ box.hidden = true; return; }
  const rows = r.filter(x => x.done || x.resting || list.some(u => u.toLowerCase().includes(x.site.toLowerCase() + ".")))
    .map(x => x.resting ? `${x.site}: resting until tomorrow (it showed a robot check today)` : `${x.site}: ${Math.max(0, x.cap - x.done)} of ${x.cap} left today`);
  box.hidden = !rows.length; box.textContent = rows.join("   ·   ");
  box.title = "A daily limit keeps your job-site accounts safe. Change it in Settings, Applying.";
}
$("#savedQ").oninput = () => setSaved(SAVED);
function pickedSaved(){ return $$("#savedList .sj:checked").map(c => SAVED[+c.dataset.i]); }
function updateApplyBtn(){ const n = pickedSaved().length; $("#applyListBtn").disabled = !n;
  $("#applyListBtn").textContent = n === SAVED.length && n > 1 ? `Apply to all ${n}` : n > 1 ? `Apply to ${n} selected` : "Apply to selected";
  $("#allSaved").checked = n === $$("#savedList .sj").length && n > 0; }
$("#allSaved").onchange = e => { $$("#savedList .sj").forEach(c => c.checked = e.target.checked); updateApplyBtn(); };
async function saveList(list){ await api_save_list(list.join("\n")); setSaved(list); }
$("#addLinksBtn").onclick = async () => { const l = links($("#links").value); if (!l.length) return toast("Paste a link that starts with http", true);
  const fresh = l.filter(u => !SAVED.includes(u)); await saveList([...SAVED, ...fresh]); $("#links").value = ""; renderLinkChips();
  toast(fresh.length ? `${fresh.length} added to your list` : "Already in your list"); };
$("#clearListBtn").onclick = async () => { if (SAVED.length && await askYes("Clear your job list?", `This removes all ${SAVED.length} job link${SAVED.length > 1 ? "s" : ""} from the list. Jobs you already applied to stay in My jobs.`, "Clear the list")) { await saveList([]); toast("List cleared"); } };
$("#applyListBtn").onclick = () => startApply(pickedSaved());
$("#pauseToggle").onchange = async e => { await api_save_profile([{where:"settings", key:"pause_after_each_page", value:e.target.checked ? "Yes" : "No"}]);
  toast(e.target.checked ? "You'll check each page" : "It will go straight to the Submit page"); };
async function startApply(l){
  if (!l.length) return toast("Pick at least one job", true);
  if (STATE.needs_profile){ toast("Add your email in Profile first", true); return go("profile"); }
  const r = await api_start_apply(l); if (!r.ok) toast(r.error, true); else toast(`Starting ${l.length} job${l.length > 1 ? "s" : ""}`);
}
