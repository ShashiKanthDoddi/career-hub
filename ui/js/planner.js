/* ===== home: calendar of interviews + to-do list ===== */
let CAL = {y: new Date().getFullYear(), m: new Date().getMonth(), sel: ""};
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hhmm = t => { if (!t) return ""; const [h, m] = t.split(":").map(Number); return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`; };
const dayName = s => new Date(s + "T00:00").toLocaleDateString([], {weekday: "short", day: "numeric", month: "short"});

function renderPlanner(H){
  renderNextUp(H);
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
      <div class="body"><b>${esc(e.title)}${e.company ? ", " + esc(e.company) : ""}</b><span>${esc(dayName(e.date))}${e.time ? " at " + hhmm(e.time) : ""}${e.round ? " · " + esc(e.round) : ""}${e.who ? " · with " + esc(e.who) : ""}${e.mail_id ? " · from your email" : ""}</span></div>
      ${safeLink(e.link) ? `<a class="btn sm ghost" href="${esc(e.link)}" target="_blank" title="Join the call">${icon("ext")}</a>` : ""}
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
  $("#evDate").value = CAL.sel || iso(new Date()); $("#evTime").value = ""; $("#evLink").value = "";
  $("#calForm").scrollIntoView({behavior: "smooth", block: "nearest"}); $("#evDate").focus();
}
$("#calAdd").onclick = () => openEventForm("", "");
$("#evCancel").onclick = () => { $("#calForm").hidden = true; };
$("#calForm").onsubmit = async e => { e.preventDefault();
  if (!$("#evDate").value) return toast("Pick a date", true);
  const r = await api_add_event($("#evTitle").value || "Interview", $("#evDate").value, $("#evTime").value, $("#evCompany").value, "", $("#evLink").value);
  if (!r) return toast("Could not save that. Check the date.", true);
  $("#calForm").hidden = true; const [y, m] = r.date.split("-").map(Number); CAL.y = y; CAL.m = m - 1;
  HOME.events.push(r); HOME.events.sort((a, b) => (a.date + (a.time || "99")).localeCompare(b.date + (b.time || "99"))); renderPlanner(HOME); };
$("#calPrev").onclick = () => { CAL.m--; if (CAL.m < 0) { CAL.m = 11; CAL.y--; } renderPlanner(HOME); };
$("#calFwd").onclick = () => { CAL.m++; if (CAL.m > 11) { CAL.m = 0; CAL.y++; } renderPlanner(HOME); };
$("#calToday").onclick = () => { const n = new Date(); CAL = {y: n.getFullYear(), m: n.getMonth(), sel: ""}; renderPlanner(HOME); };
$("#todoForm").onsubmit = async e => { e.preventDefault(); const v = $("#todoText").value.trim(); if (!v) return;
  $("#todoText").value = ""; const t = await api_add_todo(v); if (t){ HOME.todos.push(t); renderPlanner(HOME); } };
$("#todoClear").onclick = async () => { await api_clear_done_todos(); HOME.todos = HOME.todos.filter(t => !t.done); renderPlanner(HOME); };

/* Next up: the closest interview, how long to go, the call link, and a short brief about the company */
let NU = {id: "", html: ""};
const safeLink = u => /^https?:\/\//i.test(u || "");
function nextEvent(evs){
  const now = Date.now();
  return evs.map(e => ({e, at: new Date(e.date + "T" + (e.time || "23:59")).getTime()}))
    .filter(x => x.at >= now - (x.e.time ? 30 * 60000 : 0)).sort((a, b) => a.at - b.at).map(x => x.e)[0];
}
function untilText(e){
  const mins = Math.round((new Date(e.date + "T" + (e.time || "23:59")) - new Date()) / 60000),
        days = Math.round((new Date(e.date + "T00:00") - new Date(iso(new Date()) + "T00:00")) / 864e5);
  if (days > 1) return {text: `In ${days} days`, soon: false};
  if (days === 1) return {text: "Tomorrow", soon: false};
  if (!e.time) return {text: "Today", soon: false};
  if (mins <= 0) return {text: "Happening now", soon: true};
  return mins < 60 ? {text: `In ${mins} minutes`, soon: true} : {text: `Today, in ${Math.round(mins / 60)} hours`, soon: false};
}
function renderNextUp(H){
  const box = $("#nextUp"), e = nextEvent(H.events || []);
  if (!e){ box.hidden = true; return; }
  const u = untilText(e), shown = NU.id === e.id && NU.html;
  const sub = [dayName(e.date) + (e.time ? " at " + hhmm(e.time) : ""), e.round, e.who ? "with " + e.who : ""].filter(Boolean).join(" · ");
  box.hidden = false; box.classList.toggle("soon", u.soon);
  box.innerHTML = `<div class="nu-top"><div><div class="nu-k">Next up · ${esc(u.text)}</div>
    <h2>${esc(e.title)}${e.company ? ", " + esc(e.company) : ""}</h2><div class="nu-sub">${esc(sub)}</div></div>
    <div class="nu-acts">${safeLink(e.link) ? `<a class="btn primary" href="${esc(e.link)}" target="_blank">${icon("ext")}Join call</a>` : ""}
    ${e.company ? `<button class="btn" id="nuBrief">${shown ? "Hide" : "About " + esc(e.company)}</button>` : ""}</div></div>
    ${shown ? `<div class="nu-brief">${NU.html}</div>` : ""}`;
  const b = $("#nuBrief"); if (!b) return;
  b.onclick = async () => {
    if (shown){ NU = {id: "", html: ""}; return renderNextUp(H); }
    b.disabled = true; b.textContent = "Looking it up…";
    const r = await api_company_brief(e.company);
    if (!r.ok){ b.disabled = false; b.textContent = "About " + e.company; return toast(r.error, true); }
    NU = {id: e.id, html: `${r.ai ? `<p style="margin:0 0 6px">${aiBadge(r.ai)}</p>` : ""}${prepTipsHTML(r.text)}<div class="nu-src">Source: ${esc(r.source)}</div>`}; renderNextUp(H);
  };
}
setInterval(() => { if (typeof HOME !== "undefined" && HOME && !$("#p-home").hidden) renderNextUp(HOME); }, 30000);

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
