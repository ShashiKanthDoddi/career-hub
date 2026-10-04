/* ===== home: calendar of interviews + to-do list ===== */
let CAL = {y: new Date().getFullYear(), m: new Date().getMonth(), sel: ""};
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hhmm = t => { if (!t) return ""; const [h, m] = t.split(":").map(Number); return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`; };
const dayName = s => new Date(s + "T00:00").toLocaleDateString([], {weekday: "short", day: "numeric", month: "short"});

function renderPlanner(H){
  const evs = H.events || [], today = iso(new Date()), by = {};
  evs.forEach(e => (by[e.date] = by[e.date] || []).push(e));
  const first = new Date(CAL.y, CAL.m, 1), lead = (first.getDay() + 6) % 7, days = new Date(CAL.y, CAL.m + 1, 0).getDate();
  $("#calTitle").textContent = first.toLocaleDateString([], {month: "long", year: "numeric"});
  let cells = ["Mo","Tu","We","Th","Fr","Sa","Su"].map(d => `<div class="dow">${d}</div>`).join("") + "<i></i>".repeat(lead);
  for (let d = 1; d <= days; d++){
    const k = `${CAL.y}-${String(CAL.m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`, n = (by[k] || []).length;
    cells += `<button type="button" class="day ${k === today ? "today" : ""} ${k === CAL.sel ? "sel" : ""} ${n ? "has" : ""}" data-d="${k}"
      title="${n ? esc(by[k].map(e => e.title + (e.company ? ", " + e.company : "")).join("\n")) : ""}">${d}${n ? `<u>${n}</u>` : ""}</button>`;
  }
  $("#calGrid").innerHTML = cells;
  $$("#calGrid .day").forEach(b => b.onclick = () => { CAL.sel = CAL.sel === b.dataset.d ? "" : b.dataset.d; renderPlanner(H); });
  const shown = CAL.sel ? evs.filter(e => e.date === CAL.sel) : evs.filter(e => e.date >= today).slice(0, 5);
  const next = evs.find(e => e.date >= today);
  $("#calNext").textContent = next ? `Next: ${dayName(next.date)}${next.time ? ", " + hhmm(next.time) : ""}` : "";
  $("#calList").innerHTML = shown.length ? `<div class="muted small cal-h">${CAL.sel ? dayName(CAL.sel) : "Coming up"}</div>` + shown.map(e => `<div class="item">
      <div class="body"><b>${esc(e.title)}${e.company ? ", " + esc(e.company) : ""}</b><span>${esc(dayName(e.date))}${e.time ? " at " + hhmm(e.time) : ""}${e.mail_id ? " · from your email" : ""}</span></div>
      <button class="btn sm ghost" data-evdel="${esc(e.id)}" title="Remove">${icon("x")}</button></div>`).join("")
    : `<div class="muted small cal-h">${CAL.sel ? "Nothing on " + dayName(CAL.sel) + "." : "No interviews scheduled. Use Add interview when one is booked."}</div>`;
  $$("#calList [data-evdel]").forEach(b => b.onclick = async () => { await api_delete_event(b.dataset.evdel); H.events = H.events.filter(e => e.id !== b.dataset.evdel); renderPlanner(H); });

  const todos = H.todos || [];
  $("#todoClear").hidden = !todos.some(t => t.done);
  $("#todoList").innerHTML = todos.length ? todos.map(t => `<div class="item todo ${t.done ? "done" : ""}">
      <input type="checkbox" data-tid="${esc(t.id)}" ${t.done ? "checked" : ""}><div class="body"><b>${esc(t.text)}</b></div>
      <button class="btn sm ghost" data-tdel="${esc(t.id)}" title="Delete">${icon("x")}</button></div>`).join("")
    : emptyHTML("check", "Nothing to do", "Add reminders like “Update LinkedIn” or “Prepare for Friday’s interview”.");
  $$("#todoList [data-tid]").forEach(c => c.onchange = async () => { await api_set_todo(c.dataset.tid, c.checked); todos.find(t => t.id === c.dataset.tid).done = c.checked; renderPlanner(H); });
  $$("#todoList [data-tdel]").forEach(b => b.onclick = async () => { await api_delete_todo(b.dataset.tdel); H.todos = todos.filter(t => t.id !== b.dataset.tdel); renderPlanner(H); });
  $$("#attention [data-cal]").forEach(b => b.onclick = () => { const [c, t] = b.dataset.cal.split("|"); openEventForm(c, t); });
}
function openEventForm(company, title){
  $("#calForm").hidden = false;
  $("#evCompany").value = company || ""; $("#evTitle").value = title ? "Interview, " + title : "Interview";
  $("#evDate").value = CAL.sel || iso(new Date()); $("#evTime").value = "";
  $("#calForm").scrollIntoView({behavior: "smooth", block: "nearest"}); $("#evDate").focus();
}
$("#calAdd").onclick = () => openEventForm("", "");
$("#evCancel").onclick = () => { $("#calForm").hidden = true; };
$("#calForm").onsubmit = async e => { e.preventDefault();
  if (!$("#evDate").value) return toast("Pick a date", true);
  const r = await api_add_event($("#evTitle").value || "Interview", $("#evDate").value, $("#evTime").value, $("#evCompany").value, "");
  if (!r) return toast("Could not save that. Check the date.", true);
  $("#calForm").hidden = true; const [y, m] = r.date.split("-").map(Number); CAL.y = y; CAL.m = m - 1;
  HOME.events.push(r); HOME.events.sort((a, b) => (a.date + (a.time || "99")).localeCompare(b.date + (b.time || "99"))); renderPlanner(HOME); };
$("#calPrev").onclick = () => { CAL.m--; if (CAL.m < 0) { CAL.m = 11; CAL.y--; } renderPlanner(HOME); };
$("#calFwd").onclick = () => { CAL.m++; if (CAL.m > 11) { CAL.m = 0; CAL.y++; } renderPlanner(HOME); };
$("#calToday").onclick = () => { const n = new Date(); CAL = {y: n.getFullYear(), m: n.getMonth(), sel: ""}; renderPlanner(HOME); };
$("#todoForm").onsubmit = async e => { e.preventDefault(); const v = $("#todoText").value.trim(); if (!v) return;
  $("#todoText").value = ""; const t = await api_add_todo(v); if (t){ HOME.todos.push(t); renderPlanner(HOME); } };
$("#todoClear").onclick = async () => { await api_clear_done_todos(); HOME.todos = HOME.todos.filter(t => !t.done); renderPlanner(HOME); };

/* A kind word after a run of rejection emails (more than 6, then every 5 more) */
function showCheer(n){
  if (document.getElementById("cheerBox")) return;
  const box = document.createElement("div"); box.id = "cheerBox"; box.className = "modal"; box.style.zIndex = 80;
  box.innerHTML = `<div class="sheet" style="--k:var(--hi)"><div class="sh"><div class="kind" style="color:var(--hi-ink)">A note for you</div>
    <h2>I know you can do it</h2></div><p>Don't give up.</p>
    <div class="row" style="margin-top:14px"><button class="btn primary" id="cheerOk">Thank you</button></div></div>`;
  document.body.appendChild(box);
  box.querySelector("#cheerOk").onclick = async () => { box.remove(); await api_cheer_seen(n); };
}
