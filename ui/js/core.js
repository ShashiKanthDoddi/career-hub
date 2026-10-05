/* ===== basics ===== */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icon = (n, st="") => `<svg class="i" style="${st}"><use href="#i-${n}"/></svg>`;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
let STATE = {}, HOME = null, JOBS = {jobs:[], updates:[]}, TABLES = {}, ASK = null, RUN = null, FOUND = [], PAGE = "home";
async function ready(){ while (!window.api_state) await new Promise(r => setTimeout(r, 40)); }
function toast(t, bad){ const el = document.createElement("div"); el.className = "toast" + (bad ? " bad" : "");
  el.innerHTML = (bad ? icon("x") : icon("check")) + `<span>${esc(t)}</span>`; $("#toasts").appendChild(el);
  setTimeout(() => { el.style.transition = "opacity .3s"; el.style.opacity = 0; setTimeout(() => el.remove(), 300); }, 2800); }
function when(d){ if (!d) return ""; const t = new Date(d), days = Math.floor((Date.now() - t) / 864e5);
  return days <= 0 ? "Today" : days === 1 ? "Yesterday" : days < 7 ? `${days} days ago` : t.toLocaleDateString(undefined, {day:"numeric", month:"short"}); }
const debounce = (fn, ms = 160) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
function site(u){ const h = (u.match(/^https?:\/\/([^/]+)/i)||[])[1] || ""; const l = h.toLowerCase();
  if (l.includes("myworkdayjobs")) return ["Workday", h.split(".")[0]]; if (l.includes("greenhouse")) return ["Greenhouse", (u.split("/")[3]||"")];
  if (l.includes("lever.co")) return ["Lever", (u.split("/")[3]||"")]; if (l.includes("ashbyhq")) return ["Ashby", (u.split("/")[3]||"")];
  if (l.includes("linkedin")) return ["LinkedIn", "Easy Apply"]; if (l.includes("smartrecruiters")) return ["SmartRecruiters", (u.split("/")[3]||"")];
  if (l.includes("naukri")) return ["Naukri", ""]; return ["Website", h.replace(/^www\./, "")]; }
function links(t){ return [...new Set((t || "").split(/\s+/).filter(l => /^https?:\/\//i.test(l)))]; }
function countUp(el, to){ if (reduce || !to){ el.textContent = to; return; } const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / 700); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); }; requestAnimationFrame(step); }

/* a soft ripple where a button is clicked (styles.css .btn.rip); none in calm mode */
document.addEventListener("pointerdown", e => { const b = e.target.closest?.(".btn"); if (!b || reduce || STATE.calm) return;
  const r = b.getBoundingClientRect(); b.style.setProperty("--rx", (e.clientX - r.left) + "px"); b.style.setProperty("--ry", (e.clientY - r.top) + "px");
  b.classList.remove("rip"); void b.offsetWidth; b.classList.add("rip"); clearTimeout(b._rip); b._rip = setTimeout(() => b.classList.remove("rip"), 650); });

/* ===== navigation ===== */
const PAGES = ["home","apply","find","jobs","resume","profile","settings"];
function go(p, opts={}){
  if (!PAGES.includes(p)) return; PAGE = p;
  $$(".nav[data-go]").forEach(b => b.classList.toggle("on", b.dataset.go === p));
  PAGES.forEach(x => { const el = $("#p-" + x); el.hidden = x !== p; if (x === p){ el.classList.remove("fade-in"); void el.offsetWidth; el.classList.add("fade-in"); } });
  $("#main").scrollTop = 0;
  if ((STATE.new_pages || []).includes(p)){ STATE.new_pages = STATE.new_pages.filter(x => x !== p); api_page_seen(p); drawNewTag(p); }
  if ((p === "profile" || p === "settings") && FORMS_STALE) drawForms();
  if (p === "home") loadHome();
  if (p === "jobs") loadJobs(opts.filter || "all");     // from the sidebar: never keep an old stage filter (it looked like an empty board)
  if (p === "find"){ $("#navFound").hidden = true; if (!RESUME) loadResume(); loadFound(); }
  if (p === "settings") loadFeedback();
  if (p === "resume") loadResumePage();
  if (p === "profile"){ loadAnswers(); loadHistory(); }
}
$$(".nav[data-go]").forEach(b => b.onclick = () => go(b.dataset.go));
function drawNewTag(p){                        // "new" in the left pane: a page got a new feature or improvement (not for bug fixes)
  const b = $(`.nav[data-go="${p}"]`); if (!b) return;
  let t = b.querySelector(".newtag"), on = (STATE.new_pages || []).includes(p) && PAGE !== p;
  if (on && !t){ t = document.createElement("span"); t.className = "count newtag"; t.textContent = "new"; b.querySelector("span").after(t); }
  if (!on && t) t.remove();
}
$$("[data-open]").forEach(b => b.onclick = () => api_open(b.dataset.open));

/* ===== state ===== */
async function loadState(){
  STATE = await api_state();
  applyTheme(STATE.theme);
  $("#verSide").textContent = "Version " + STATE.version; $("#verTag").textContent = "You have version " + STATE.version;
  setSaved(links(STATE.jobs_text));
  $("#pauseToggle").checked = !/^no/i.test(val("pause_after_each_page") || "Yes");
  $("#dailyFind").checked = STATE.daily; setFindMode(STATE.find_auto !== false ? "auto" : "mine");
  if (!COMPS.length && STATE.find_companies) STATE.find_companies.split(",").map(s => s.trim()).filter(Boolean).forEach(c => addTag("comp", c));
  if (STATE.find_roles && !ROLES.length) STATE.find_roles.split(",").map(s => s.trim()).filter(Boolean).forEach(r => addTag("role", r));
  FORMS_STALE = true; if (PAGE === "profile" || PAGE === "settings") drawForms();   // the big forms are only drawn when she opens them
  $$(".nav[data-go]").forEach(b => drawNewTag(b.dataset.go));
}
let FORMS_STALE = true;
function drawForms(){ renderForms(); renderThemes(); renderChangelog(); renderUpdateInfo(); FORMS_STALE = false; }
function val(key){ const f = STATE.profile.find(f => f.key === key); return f ? f.value : ""; }

/* ===== confetti (only after a sent application or an offer) ===== */
function confetti(){
  if (reduce || STATE.calm) return; const c = $("#confetti"), x = c.getContext("2d"); c.width = innerWidth; c.height = innerHeight;
  const colors = ["#FFD84D","#C0532B","#1A8F86","#D9506A","#2E8B4E"];
  const ps = Array.from({length:140}, () => ({x:innerWidth / 2, y:innerHeight * .35, vx:(Math.random() - .5) * 14, vy:-Math.random() * 12 - 4, r:Math.random() * 6 + 3, c:colors[Math.random() * 5 | 0], a:Math.random() * 6}));
  let f = 0; (function tick(){ x.clearRect(0, 0, c.width, c.height);
    ps.forEach(p => { p.vy += .35; p.x += p.vx; p.y += p.vy; p.a += .1; x.save(); x.translate(p.x, p.y); x.rotate(p.a); x.fillStyle = p.c; x.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2); x.restore(); });
    if (++f < 110) requestAnimationFrame(tick); else x.clearRect(0, 0, c.width, c.height); })();
}

/* Web links open in her normal browser, not inside this window */
document.addEventListener("click", e => { const a = e.target.closest && e.target.closest('a[href^="http"]');
  if (a){ e.preventDefault(); api_open_url(a.href); } });
