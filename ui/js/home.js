/* ===== home ===== */
function greeting(){ const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; }
const NICKNAMES = ["Babe", "Bujjuku", "Bangaram", "Cutiepie", "Munchkin"];
/* A different pet name each hour: random-looking, but steady while she reloads within the hour. */
function nickname(){
  const d = new Date(), seed = d.getFullYear() * 1e6 + (d.getMonth() + 1) * 1e4 + d.getDate() * 100 + d.getHours();
  const x = Math.sin(seed) * 10000;
  return NICKNAMES[Math.floor((x - Math.floor(x)) * NICKNAMES.length)];
}
async function loadHome(){
  HOME = await api_home(); const s = HOME.stats, name = nickname();
  $("#hello").textContent = `${greeting()}, ${name}`;
  const heard = s.interviews + s.offers + s.rejected;
  const lines = [];
  const prep = HOME.attention.filter(u => u.type === "interview" || u.type === "assessment").length;
  if (HOME.attention.some(u => u.type === "offer")) lines.push("You have an offer waiting. Congratulations!");
  else if (prep) lines.push(`${prep} interview${prep > 1 ? "s" : ""} or test${prep > 1 ? "s" : ""} to get ready for.`);
  else if (s.week) lines.push(`${s.week} application${s.week > 1 ? "s" : ""} sent this week. Nice momentum.`);
  else lines.push(s.applied ? "A quiet week so far. Paste a link below to keep it moving." : "Let's send your first application today.");
  $("#helloSub").textContent = lines.join(" ");
  const max = Math.max(1, HOME.list_count, s.applied);
  const stages = [
    ["saved","Saved", HOME.list_count, "ready to apply", () => go("apply")],
    ["applied","Applied", s.applied, s.week ? `${s.week} this week` : "", () => go("jobs", {filter:"all"})],
    ["heard","Heard back", heard, s.applied ? `${s.reply_rate}% reply rate` : "", () => go("jobs", {filter:"replied"})],
    ["int","Interviews", s.interviews, s.interviews ? "including tests" : "", () => go("jobs", {filter:"Interview"})],
    ["offer","Offers", s.offers, s.offers ? "well done" : "", () => go("jobs", {filter:"Offer"})]];
  $("#funnel").innerHTML = stages.map(([k,l,n,sub]) => `<button class="stagebox k-${k} ${k==="offer" && n ? "win" : ""}" data-k="${k}">
     <div class="n" data-n="${n}">0</div><div class="l">${l}</div><div class="s">${esc(sub)}</div><div class="bar"><i></i></div></button>`).join("");
  $$("#funnel .stagebox").forEach((b,i) => { b.onclick = stages[i][4]; countUp(b.querySelector(".n"), stages[i][2]);
    requestAnimationFrame(() => b.querySelector(".bar i").style.width = (100 * stages[i][2] / max) + "%"); });
  $("#weekline").innerHTML = [s.waiting ? `<span><b>${s.waiting}</b> waiting to hear back</span>` : "",
    s.rejected ? `<span><b>${s.rejected}</b> not selected</span>` : "", s.drafts ? `<span><b>${s.drafts}</b> draft${s.drafts > 1 ? "s" : ""} to finish</span>` : ""].join("");
  renderWeekSum(HOME);
  $("#attnCount").textContent = HOME.attention.length ? `${HOME.attention.length} open` : "";
  $("#attention").innerHTML = HOME.attention.length ? HOME.attention.map(u => itemHTML(u, true)).join("")
    : emptyHTML("check", "You're all caught up", "Interview invites, tests and offers from your inbox land here.");
  $("#feed").innerHTML = HOME.feed.length ? HOME.feed.slice(0, 8).map(u => itemHTML(u, false)).join("")
    : emptyHTML("inbox", HOME.mail_ready ? "No job emails yet" : "Connect your job Gmail", HOME.mail_ready ? "Replies from companies will show up here." : `Settings, then Job email. <a href="#" onclick="go('settings');setTimeout(()=>$('#set-email')?.scrollIntoView({behavior:'smooth'}),80);return false">Open settings</a>`);
  const more = (HOME.mail_total || HOME.feed.length) - 8;
  if (more > 0) $("#feed").insertAdjacentHTML("beforeend", `<a href="#" class="feed-more" onclick="JVIEW='updates';go('jobs');return false">See all ${more + 8} emails</a>`);
  $("#mailInfo").textContent = HOME.mail_ready && HOME.last_mail_check ? "Checked " + when(HOME.last_mail_check).toLowerCase() + " at " + new Date(HOME.last_mail_check).toLocaleTimeString([], {hour:"numeric", minute:"2-digit"}) : "";
  if (HOME.mail_error) $("#mailInfo").innerHTML = `<span style="color:var(--rose)">${esc(HOME.mail_error)}</span> <a href="#" onclick="go('settings');setTimeout(()=>$('#set-email')?.scrollIntoView({behavior:'smooth'}),80);return false">Fix in Settings</a>`;
  $$("#attention [data-done]").forEach(b => b.onclick = async () => { const it = b.closest(".item"); it.classList.add("done-anim");
    await api_dismiss(b.dataset.done); setTimeout(loadHome, 330); });
  renderPlanner(HOME);
  if (HOME.cheer) showCheer(HOME.cheer);
  setCount("#navAttn", HOME.attention.length); setCount("#navSaved", HOME.list_count);
  return HOME;
}
function renderWeekSum(H){
  const m = H.summary, box = $("#weekSum"); box.hidden = !H.stats.applied && !m.replies; if (box.hidden) return;
  const diff = m.sent - m.sent_before, top = Math.max(1, ...H.weekly.map(w => w.count));
  const cell = (n, l, d = "") => `<div><div class="ws-n">${n}</div><div class="ws-l">${l}</div>${d ? `<div class="ws-d">${d}</div>` : ""}</div>`;
  box.innerHTML = `<div class="panel-head"><h2 class="grow">Your last 7 days</h2></div><div class="ws-top">
    ${cell(m.sent, "applications sent", diff ? `${diff > 0 ? "up" : "down"} ${Math.abs(diff)} from the week before` : "same as the week before")}
    ${cell(m.replies, m.replies === 1 ? "reply" : "replies")}${cell(m.interviews, m.interviews === 1 ? "interview or test" : "interviews or tests")}${m.offers ? cell(m.offers, "offer" + (m.offers > 1 ? "s" : "")) : ""}
    <div class="ws-bars" title="Applications sent per week, last 8 weeks">${H.weekly.map((w, i) => `<i class="${i === H.weekly.length - 1 ? "now" : ""}" style="height:${Math.max(6, 100 * w.count / top)}%" title="Week of ${esc(w.label)}: ${w.count}"></i>`).join("")}</div></div>
    ${m.follow_up ? `<div class="ws-note">${m.follow_up} application${m.follow_up > 1 ? "s have" : " has"} had no reply for a week or more. <a href="#" onclick="go('jobs',{filter:'Applied'});return false">See them</a>, and think about a short follow-up email.</div>` : ""}`;
}
const TYPE = {offer:["Offer","Offer"], rejection:["Not selected","Rejected"], interview:["Interview","Interview"], assessment:["Test","Assessment"], received:["Received","received"], other:["Update","other"]};
function itemHTML(u, attn){
  const [label, cls] = TYPE[u.type] || TYPE.other;
  return `<div class="item ${attn ? "new" : ""}"><span class="stage s-${cls}">${label}</span>
    <div class="body"><b>${esc(u.company || u.from)}${u.title ? `, ${esc(u.title)}` : ""}</b><span>${esc(u.subject)}</span><span>${when(u.date)}</span></div>
    <div class="side-acts"><a class="btn sm ghost" href="${esc(u.gmail || "#")}" target="_blank" title="Open in Gmail">${icon("ext")}</a>
    ${attn && (u.type === "interview" || u.type === "assessment") ? `<button class="btn sm ghost" data-cal="${esc(u.company || u.from)}|${esc(u.title || "")}" title="Put it on the calendar">${icon("cal")}</button>` : ""}
    ${attn ? `<button class="btn sm" data-done="${esc(u.id)}">Done</button>` : ""}</div></div>`;
}
function emptyHTML(ic, title, text){ return `<div class="empty">${icon(ic)}<b>${title}</b><div class="small">${text}</div></div>`; }
function setCount(sel, n){ const el = $(sel); el.textContent = n; el.hidden = !n; }
$("#checkMailBtn").onclick = async () => { const b = $("#checkMailBtn"); b.disabled = true; b.lastChild.textContent = "Checking";
  MAIL_SPIN_AT = Date.now(); $("#mailSpin span").textContent = "Starting…"; $("#mailSpin").hidden = false; $("#feed").hidden = true; await api_check_mail(true); };
let MAIL_SPIN_AT = 0;
function hideMailSpin(){ setTimeout(() => { $("#mailSpin").hidden = true; $("#feed").hidden = false; }, Math.max(0, 700 - (Date.now() - MAIL_SPIN_AT))); }
