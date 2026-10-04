/* ===== Profile: work history and education (used on Workday-style forms) ===== */
let HIST = {work: [], education: []};
const WORK_F = [["title", "Job title"], ["company", "Company"], ["location", "City"], ["start", "From (month and year, e.g. 2023-06)"],
                ["end", "To (leave empty if you still work here)"]];
const EDU_F = [["degree", "Degree (e.g. B.Tech, MBA)"], ["field", "Field of study"], ["school", "School or university"],
               ["start", "Start year"], ["end", "End year"], ["grade", "Grade (e.g. 8.5/10)"]];
const asHist = h => ({work: (h && h.work) || [], education: (h && h.education) || []});
async function loadHistory(){ HIST = asHist(await api_history()); renderHistory(); }
function renderHistory(){
  const box = (kind, list, fields) => list.map((e, i) => `<div class="panel" style="background:var(--surface-2);margin-bottom:10px" data-kind="${kind}" data-i="${i}">
    <div class="formgrid">${fields.map(([k, l]) => `<label class="field"><span class="small muted">${esc(l)}</span><input type="text" data-k="${k}" value="${esc(e[k] || "")}"></label>`).join("")}</div>
    ${kind === "work" ? `<label class="small muted">What you did (one point per line)</label><textarea data-k="description" rows="3">${esc(e.description || "")}</textarea>
      <label class="switch small" style="margin-top:8px"><input type="checkbox" data-k="current" ${e.current ? "checked" : ""}> I still work here</label>` : ""}
    <div style="text-align:right"><button class="btn sm ghost" data-del="${kind}:${i}">${icon("x")} Remove</button></div></div>`).join("");
  $("#histWork").innerHTML = box("work", HIST.work, WORK_F) || `<div class="muted small" style="margin-bottom:8px">No jobs added yet.</div>`;
  $("#histEdu").innerHTML = box("education", HIST.education, EDU_F) || `<div class="muted small" style="margin-bottom:8px">No education added yet.</div>`;
  $$("#sec-history [data-del]").forEach(b => b.onclick = () => { collectHistory(); const [k, i] = b.dataset.del.split(":"); HIST[k].splice(+i, 1); renderHistory(); });
}
function collectHistory(){
  $$("#sec-history [data-kind]").forEach(card => { const e = HIST[card.dataset.kind][+card.dataset.i];
    card.querySelectorAll("[data-k]").forEach(el => { e[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; }); });
}
$("#histAddWork").onclick = () => { collectHistory(); HIST.work.push({title: "", company: "", location: "", start: "", end: "", current: false, description: ""}); renderHistory(); };
$("#histAddEdu").onclick = () => { collectHistory(); HIST.education.push({school: "", degree: "", field: "", start: "", end: "", grade: ""}); renderHistory(); };
$("#histRead").onclick = async () => {
  collectHistory();
  if ((HIST.work.length || HIST.education.length) && !confirm("Replace what is below with what the resume says?")) return;
  const b = $("#histRead"); b.disabled = true; const r = await api_read_history(); b.disabled = false;
  if (!r.ok) return toast(r.error, true);
  HIST = {work: r.work, education: r.education}; renderHistory(); $("#histState").textContent = "Check each box, then save"; toast("Read from your resume. Please check it."); };
$("#histSave").onclick = async () => { collectHistory(); HIST = asHist(await api_save_history(HIST)); renderHistory(); $("#histState").textContent = "Saved"; toast("Work and education saved"); };
