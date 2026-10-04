/* ===== messages from the engine (Python calls window.onPy) ===== */
window.onPy = ev => {
  if (ev.type === "log") addLog(ev.text);
  else if (ev.type === "status") setRun(ev);
  else if (ev.type === "ask") showAsk(ev);
  else if (ev.type === "ask_done"){ if (ASK && ASK.id === ev.id){ ASK = null; $("#layer").innerHTML = ""; } }
  else if (ev.type === "run_start"){ RUN = null; setRun({what:ev.what, total:ev.total, detail:"Starting"}); }
  else if (ev.type === "run_end") runEnd(ev);
  else if (ev.type === "filled") filledToast(ev.items);
  else if (ev.type === "manual") toast("Type these yourself in Chrome: " + ev.items.join(", "));
  else if (ev.type === "mail_done"){ const b = $("#checkMailBtn"); b.disabled = false; b.lastChild.textContent = "Check email";
    if (ev.manual) ev.ok ? toast("Email checked: " + ev.summary) : toast(ev.error, true);   // automatic checks stay quiet
    loadHome(); if (PAGE === "jobs") loadJobs(); }
  else if (ev.type === "update_check") updateResult(ev);
  else if (ev.type === "rolled_back") notice("The update didn't start, so nothing changed",
    `Version ${ev.to} had a problem starting, so the app went back to ${ev.from}. Your data is fine. A report helps fix it: use Report a problem.`);
  else if (ev.type === "report_done") reportResult(ev);
};

/* what was filled on a page: a small list, bottom right, for a few seconds */
function filledToast(items){
  const box = document.createElement("div"); box.className = "filled";
  box.innerHTML = `<b>${icon("check")}Filled ${items.length} field${items.length > 1 ? "s" : ""}</b>` +
    items.slice(0, 8).map(([l, v]) => `<div><span>${esc(l)}</span><span>${esc(v)}</span></div>`).join("") +
    (items.length > 8 ? `<div class="muted">and ${items.length - 8} more</div>` : "");
  $("#filledBox").appendChild(box);
  setTimeout(() => { box.style.opacity = 0; setTimeout(() => box.remove(), 400); }, 4500);
}

/* ===== updates ===== */
async function checkUpdates(manual){
  const b = $("#checkUpdBtn"); if (b){ b.disabled = true; b.lastChild.textContent = "Checking"; }
  await api_check_update(!!manual);
  if (b){ b.disabled = false; b.lastChild.textContent = "Check for updates"; }
}
function updateResult(ev){
  STATE.last_update_check = new Date().toISOString(); renderUpdateInfo();
  if (!ev.ok){ if (ev.manual) toast(ev.error, true); return; }
  if (!ev.available){ if (ev.manual) toast(`You have the latest version (${ev.version})`); return; }
  const list = (ev.notes || []).map(v => `<div class="version cur" style="margin-bottom:10px"><b>Version ${esc(v.version)}: ${esc(v.title)}</b>
     <ul>${v.new.map(x => `<li>${esc(x)}</li>`).join("")}${(v.fixed || []).map(x => `<li class="fx">Fixed: ${esc(x)}</li>`).join("")}</ul></div>`).join("");
  $("#layer").innerHTML = `<div class="modal"><div class="sheet" style="--k:var(--hi)"><div class="sh"><div class="kind" style="color:var(--hi-ink)">Update available</div>
    <h2>Version ${esc(ev.version)} is ready</h2><p class="msg">Here's what's new. Updating takes a few seconds; the app restarts and your data stays exactly as it is.</p></div>
    <div class="sb">${list || "<p class='muted'>Fixes and improvements.</p>"}
    <div class="row" style="margin-top:16px"><button class="btn primary" id="updNow">Update now</button><button class="btn ghost" id="updLater">Later</button></div></div></div></div>`;
  $("#updLater").onclick = () => $("#layer").innerHTML = "";
  $("#updNow").onclick = async () => { const b = $("#updNow"); b.disabled = true; b.textContent = "Updating…";
    const r = await api_install_latest();
    if (r.ok){ b.textContent = "Restarting…"; setTimeout(() => api_restart(), 600); }
    else { b.disabled = false; b.textContent = "Update now"; toast(r.error, true); } };
}
function renderUpdateInfo(){
  const el = $("#updInfo"); if (!el) return;
  el.textContent = STATE.update_source ? (STATE.last_update_check ? "Last checked " + when(STATE.last_update_check).toLowerCase() + " at " +
    new Date(STATE.last_update_check).toLocaleTimeString([], {hour:"numeric", minute:"2-digit"}) : "Not checked yet")
    : "Updates come from GitHub once your helper adds the update source below.";
}

/* ===== start ===== */
(async () => {
  await ready(); await loadState();
  addLog("Welcome back. The app is ready.");
  if (STATE.first_run) api_seen_version(); else if (STATE.whats_new) showNews();
  if (STATE.needs_profile){ go("profile"); toast("Welcome! Start by adding your email and resume"); }
  else { const h = await loadHome(); if (h.mail_due){ addLog("Checking the job inbox (automatic)"); api_check_mail(false); } }
  setInterval(async () => { const h = await api_home(); if (h.mail_due) api_check_mail(false); }, 30 * 60 * 1000);
  if (!STATE.needs_profile && STATE.daily_due){ addLog("Checking for new jobs (daily search)"); api_start_find(STATE.find_roles, STATE.find_companies, STATE.find_auto); }
})();
