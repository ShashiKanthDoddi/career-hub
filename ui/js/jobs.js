/* ===== my jobs ===== */
let JVIEW = "board", JFILTER = "all", UPD_SHOWN = 25;
const COLS = ["Applied","Interview","Waiting","Assessment","Offer","Rejected","NoResponse","Draft"];
const COLNAME = {Applied:"Applied", Interview:"Interview", Waiting:"Waiting for reply", Assessment:"Test", Offer:"Offer", Rejected:"Not selected", NoResponse:"No response", Draft:"Draft"};
async function loadJobs(filter){
  if (filter){ JFILTER = filter; if (filter !== "all" && filter !== "replied") JVIEW = "board"; }
  JOBS = await api_jobs(); TABLES = await api_tables(); renderJobs();
}
$$("#jobsTabs button").forEach(b => b.onclick = () => { JVIEW = b.dataset.t; JFILTER = "all"; renderJobs(); });
$("#jobSearch").oninput = () => renderJobs();
$("#jobStage").onchange = e => { JFILTER = e.target.value; if (JFILTER !== "all" && JFILTER !== "replied") JVIEW = "board"; renderJobs(); };
const hasQ = o => { const q = $("#jobSearch").value.trim().toLowerCase(); return !q || Object.values(o).join(" ").toLowerCase().includes(q); };
$("#exportBtn").onclick = async () => { const m = {board:"applications", list:"applications", updates:"applications", accounts:"accounts", found:"found"};
  if (!await api_open(m[JVIEW])) toast("Nothing to export yet", true); };
function filtered(){ const q = $("#jobSearch").value.toLowerCase();
  return JOBS.jobs.filter(j => (!q || (j.company + " " + j.title).toLowerCase().includes(q)) &&
    (JFILTER === "all" || (JFILTER === "replied" ? ["Interview","Waiting","Assessment","Offer","Rejected"].includes(j.stage) : j.stage === JFILTER || (JFILTER === "Interview" && (j.stage === "Assessment" || j.stage === "Waiting"))))); }
function renderJobs(){
  $$("#jobsTabs button").forEach(b => b.classList.toggle("on", b.dataset.t === JVIEW));
  const v = $("#jobsView"); $("#jobStage").value = JFILTER; $("#jobStage").hidden = JVIEW !== "board" && JVIEW !== "list";
  if (JVIEW === "board"){
    const list = filtered(); const extra = ["Skipped","Error"].filter(s => list.some(j => j.stage === s));
    v.innerHTML = (JFILTER !== "all" ? `<div class="row" style="margin-bottom:10px"><span class="tag">Showing: ${esc(JFILTER === "replied" ? "heard back" : COLNAME[JFILTER] || JFILTER)}</span><button class="btn sm ghost" id="clearFilter">Show all</button></div>` : "") +
      `<div class="board">${[...COLS, ...extra].map(c => { const cards = list.filter(j => j.stage === c);
        return `<div class="col" data-col="${c}"><div class="col-head"><span class="stage s-${c}">${COLNAME[c] || c}</span><span class="c">${cards.length}</span></div>
          ${cards.map(j => `<div class="card" draggable="true" data-k="${esc(j.key)}"><b>${esc(j.company)}</b><span>${esc(j.title)}</span>
            <div class="foot">${esc(j.date.slice(0,10))}${j.latest ? `, ${esc((TYPE[j.latest.type] || TYPE.other)[0].toLowerCase())} email` : ""}${j.notes ? `<span class="note" title="${esc(j.notes)}">✎</span>` : ""}</div></div>`).join("")}
          ${!cards.length ? `<div class="muted small" style="padding:8px 4px">Drop here</div>` : ""}</div>`; }).join("")}</div>`;
    $("#clearFilter") && ($("#clearFilter").onclick = () => { JFILTER = "all"; renderJobs(); });
    if (!JOBS.jobs.length) v.innerHTML = `<div class="panel">${emptyHTML("board", "No applications yet", "Every job you apply to shows up here, and moves along as emails come in.")}</div>`;
    wireBoard();
  } else if (JVIEW === "list"){
    const list = filtered();
    v.innerHTML = list.length ? `<div class="tablewrap"><table><thead><tr><th>Date</th><th>Company</th><th>Job</th><th>Stage</th><th>Latest email</th></tr></thead><tbody>` +
      list.map(j => `<tr data-k="${esc(j.key)}" style="cursor:pointer"><td>${esc(j.date.slice(0,10))}</td><td><b>${esc(j.company)}</b></td><td>${esc(j.title)}</td>
        <td><span class="stage s-${j.stage}">${esc(COLNAME[j.stage] || j.stage)}</span></td><td class="muted">${j.latest ? esc(j.latest.subject) : ""}</td></tr>`).join("") + `</tbody></table></div>`
      : `<div class="panel">${emptyHTML("board", "Nothing here", "Try a different search.")}</div>`;
    $$("#jobsView tr[data-k]").forEach(tr => tr.onclick = () => openJob(tr.dataset.k));
  } else if (JVIEW === "updates"){
    const u = JOBS.updates.filter(hasQ);
    const shown = u.slice(0, UPD_SHOWN);
    v.innerHTML = u.length ? `<div class="panel">${shown.map(x => itemHTML(x, false)).join("")}${u.length > shown.length ? `<button class="btn sm feed-more" id="updMore">Show more (${u.length - shown.length} left)</button>` : ""}</div>` : `<div class="panel">${emptyHTML("inbox", "No job emails yet", "Connect your job Gmail in Settings.")}</div>`;
    $("#updMore") && ($("#updMore").onclick = () => { UPD_SHOWN += 25; renderJobs(); });
  } else {
    const rows = TABLES[JVIEW === "accounts" ? "accounts" : "found"] || [];
    if (rows.length < 2){ v.innerHTML = `<div class="panel">${emptyHTML(JVIEW === "accounts" ? "user" : "search", "Nothing here yet", JVIEW === "accounts" ? "Job-site logins appear here after the app signs you in." : "Jobs from Find jobs appear here.")}</div>`; return; }
    const q = $("#jobSearch").value.trim().toLowerCase(); const [head, ...all] = rows; const body = all.filter(r => !q || r.join(" ").toLowerCase().includes(q)); const pw = head.indexOf("Password");
    v.innerHTML = `<div class="tablewrap"><table><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>` +
      body.reverse().map(r => `<tr>${r.map((c, i) => i === pw ? `<td><button class="btn sm ghost reveal" data-p="${esc(c)}">Show</button></td>` :
        /^https?:\/\//.test(c) ? `<td><a href="${esc(c)}" target="_blank">Open</a></td>` : `<td>${esc(c)}</td>`).join("")}</tr>`).join("") + `</tbody></table></div>`;
    $$(".reveal").forEach(b => b.onclick = () => { b.outerHTML = `<code>${esc(b.dataset.p)}</code>`; });
  }
}
function wireBoard(){
  let dragKey = null;
  $$(".card").forEach(c => {
    c.ondragstart = e => { dragKey = c.dataset.k; c.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; };
    c.ondragend = () => c.classList.remove("drag");
    c.onclick = () => openJob(c.dataset.k);
  });
  $$(".col").forEach(col => {
    col.ondragover = e => { e.preventDefault(); col.classList.add("over"); };
    col.ondragleave = () => col.classList.remove("over");
    col.ondrop = async e => { e.preventDefault(); col.classList.remove("over"); const j = JOBS.jobs.find(x => x.key === dragKey); if (!j || j.stage === col.dataset.col) return;
      j.stage = col.dataset.col; renderJobs(); await api_set_note(j.key, j.stage, j.notes);
      if (j.stage === "Offer") confetti(); toast(`${j.company} moved to ${COLNAME[j.stage] || j.stage}`); await askWhen(j); };
  });
}
function openJob(key){
  const j = JOBS.jobs.find(x => x.key === key); if (!j) return;
  const ups = JOBS.updates.filter(u => u.link && u.link === j.link);
  $("#layer").innerHTML = `<div class="scrim" id="scrim"></div><aside class="drawer" role="dialog" aria-label="Job details">
    <div class="dh"><div class="grow"><h2 style="font-size:20px">${esc(j.company)}</h2><div class="muted">${esc(j.title)}</div></div><button class="btn sm ghost" id="closeDrawer">${icon("x")}</button></div>
    <div class="db">
      <h3>Stage</h3><div class="stagepick">${[...COLS, "Skipped"].map(s => `<button class="stage s-${s} ${s === j.stage ? "on" : ""}" data-s="${s}">${COLNAME[s] || s}</button>`).join("")}</div>
      <div class="row" style="margin:18px 0">${j.link ? `<a class="btn sm" href="${esc(j.link)}" target="_blank">${icon("ext")}Job page</a>` : ""}
        ${j.latest ? `<a class="btn sm" href="${esc(j.latest.gmail || "#")}" target="_blank">${icon("mail")}Latest email</a>` : ""}<span class="muted small grow" style="text-align:right">Applied ${esc(j.date.slice(0,10))}</span></div>
      <h3>Notes</h3><textarea id="jobNotes" rows="4" placeholder="Interview date, who you spoke to, salary discussed…">${esc(j.notes)}</textarea>
      <div class="muted small" id="noteState" style="margin-top:4px">Saves automatically</div>
      <h3 style="margin-top:20px">Emails</h3>
      ${ups.length ? `<div class="timeline">${ups.map(u => `<div class="t"><span class="stage s-${(TYPE[u.type] || TYPE.other)[1]}">${(TYPE[u.type] || TYPE.other)[0]}</span>
        <div style="margin-top:4px"><a href="${esc(u.gmail || "#")}" target="_blank">${esc(u.subject)}</a></div><div class="muted small">${when(u.date)}</div></div>`).join("")}</div>`
        : `<div class="muted small">No emails about this job yet.</div>`}
    </div></aside>`;
  const close = () => { $("#layer").innerHTML = ""; renderJobs(); };
  $("#scrim").onclick = close; $("#closeDrawer").onclick = close;
  $$(".stagepick button").forEach(b => b.onclick = async () => { j.stage = b.dataset.s; $$(".stagepick button").forEach(x => x.classList.toggle("on", x === b));
    await api_set_note(j.key, j.stage, $("#jobNotes").value); if (j.stage === "Offer") confetti(); toast(`Moved to ${COLNAME[j.stage] || j.stage}`); await askWhen(j); });
  let t; $("#jobNotes").oninput = e => { clearTimeout(t); $("#noteState").textContent = "Saving"; t = setTimeout(async () => { j.notes = e.target.value;
    await api_set_note(j.key, j.stage, j.notes); $("#noteState").textContent = "Saved"; }, 600); };
}

/* Moving a card to Interview or Test asks when it is, and puts it on the Home calendar */
function askWhen(j){
  if (j.stage !== "Interview" && j.stage !== "Assessment") return Promise.resolve();
  const what = j.stage === "Assessment" ? "test" : "interview";
  return new Promise(res => {
    const box = document.createElement("div"); box.className = "modal"; box.style.zIndex = 70;
    box.innerHTML = `<form class="sheet" style="--k:var(--hi)"><div class="sh"><div class="kind" style="color:var(--hi-ink)">Calendar</div>
      <h2>When is the ${what}?</h2><p class="muted">${esc(j.company)}${j.title ? ", " + esc(j.title) : ""}. It will show on the Home calendar.</p></div>
      <div class="row" style="gap:8px;margin:14px 0"><input type="date" id="wDate" required><input type="time" id="wTime"></div>
      <div class="row" style="gap:8px"><button class="btn primary" type="submit">Save to calendar</button><button class="btn ghost" type="button" id="wSkip">I don't know yet</button></div></form>`;
    document.body.appendChild(box);
    const d = box.querySelector("#wDate"); d.value = iso(new Date()); d.focus();
    const close = () => { box.remove(); res(); };
    box.querySelector("#wSkip").onclick = close;
    box.querySelector("form").onsubmit = async e => { e.preventDefault();
      await api_set_job_event(j.key, j.stage, j.company, j.title, d.value, box.querySelector("#wTime").value);
      toast(`Added to your calendar: ${dayName(d.value)}`); close(); if (typeof loadHome === "function") loadHome(); };
  });
}
