/* ===== running ===== */
function setRun(ev){
  RUN = Object.assign(RUN || {}, ev); $("#runbar").hidden = false;
  $("#statusDot").classList.add("busy");
  if (RUN.what === "find"){ $("#runTitle").textContent = "Looking for jobs that fit your resume"; $("#runSteps").innerHTML = ""; $("#statusText").textContent = "Finding jobs"; }
  else {
    const n = RUN.job || 1, t = RUN.total || 1;
    $("#runTitle").textContent = [RUN.company, RUN.title].filter(Boolean).join(", ") || `Job ${n} of ${t}`;
    $("#runSteps").innerHTML = Array.from({length:t}, (_, i) => `<i class="${i < n - 1 ? "done" : i === n - 1 ? "cur" : ""}"></i>`).join("");
    $("#statusText").textContent = `Applying, job ${n} of ${t}`;
  }
  $("#runDetail").textContent = RUN.detail || "";
}
function runEnd(ev){
  RUN = null; $("#runbar").hidden = true; $("#statusDot").classList.remove("busy"); $("#statusText").textContent = "Ready";
  if (ev.what === "apply"){
    const rs = ev.results || [];
    $("#lastRun").hidden = !rs.length;
    $("#lastTable").innerHTML = "<thead><tr><th>Company</th><th>Job</th><th>Result</th></tr></thead><tbody>" +
      rs.map(r => `<tr><td><b>${esc(r.company)}</b></td><td>${esc(r.title)}</td><td>${esc(r.status)}</td></tr>`).join("") + "</tbody>";
    const sent = rs.filter(r => r.status.startsWith("Submitted")).length;
    if (sent){ confetti(); toast(`${sent} application${sent > 1 ? "s" : ""} sent`); } else if (rs.length) toast("Run finished");
    loadState(); if (PAGE === "home") loadHome();
  } else loadFound(ev.diag || {});
}
$("#stopBtn").onclick = async () => { await api_stop(); toast("Stopping"); };
$("#runActivity").onclick = () => openActivity();
