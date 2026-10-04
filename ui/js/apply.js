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
  $("#savedList").innerHTML = list.length ? list.map((u, i) => { const [s, who] = site(u);
    return `<div class="linkchip"><input type="checkbox" class="sj" data-i="${i}" checked><span class="site">${s}</span>
      <span class="u" title="${esc(u)}">${esc(who || u)}</span><a class="btn sm ghost" href="${esc(u)}" target="_blank" title="Open">${icon("ext")}</a>
      <button class="btn sm" data-go1="${i}">Apply</button><button class="tag x" data-rm="${i}" title="Remove">×</button></div>`; }).join("")
    : emptyHTML("link", "Your list is empty", "Paste job links above. Collect them during the week, then apply in one go.");
  $$("#savedList [data-rm]").forEach(b => b.onclick = async () => saveList(SAVED.filter((_, i) => i !== +b.dataset.rm)));
  $$("#savedList [data-go1]").forEach(b => b.onclick = () => startApply([SAVED[+b.dataset.go1]]));
  $$("#savedList .sj").forEach(c => c.onchange = updateApplyBtn);
  updateApplyBtn(); setCount("#navSaved", list.length); }
function pickedSaved(){ return $$("#savedList .sj:checked").map(c => SAVED[+c.dataset.i]); }
function updateApplyBtn(){ const n = pickedSaved().length; $("#applyListBtn").disabled = !n;
  $("#applyListBtn").textContent = n === SAVED.length && n > 1 ? `Apply to all ${n}` : n > 1 ? `Apply to ${n} selected` : "Apply to selected";
  $("#allSaved").checked = n === SAVED.length && n > 0; }
$("#allSaved").onchange = e => { $$("#savedList .sj").forEach(c => c.checked = e.target.checked); updateApplyBtn(); };
async function saveList(list){ await api_save_list(list.join("\n")); setSaved(list); }
$("#addLinksBtn").onclick = async () => { const l = links($("#links").value); if (!l.length) return toast("Paste a link that starts with http", true);
  const fresh = l.filter(u => !SAVED.includes(u)); await saveList([...SAVED, ...fresh]); $("#links").value = ""; renderLinkChips();
  toast(fresh.length ? `${fresh.length} added to your list` : "Already in your list"); };
$("#clearListBtn").onclick = async () => { if (SAVED.length && confirm("Remove every job from the list?")) { await saveList([]); toast("List cleared"); } };
$("#applyListBtn").onclick = () => startApply(pickedSaved());
$("#pauseToggle").onchange = async e => { await api_save_profile([{where:"settings", key:"pause_after_each_page", value:e.target.checked ? "Yes" : "No"}]);
  toast(e.target.checked ? "You'll check each page" : "It will go straight to the Submit page"); };
async function startApply(l){
  if (!l.length) return toast("Pick at least one job", true);
  if (STATE.needs_profile){ toast("Add your email in Profile first", true); return go("profile"); }
  const r = await api_start_apply(l); if (!r.ok) toast(r.error, true); else toast(`Starting ${l.length} job${l.length > 1 ? "s" : ""}`);
}
