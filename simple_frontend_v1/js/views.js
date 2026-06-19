"use strict";
// ── views: every panel renderer + its inline-handler functions ───────────────
// Reads shared state from core (live bindings); calls core.render() to re-render
// after a queue change. Handlers referenced from generated HTML are exposed on
// window by main.js.
import {
  $, fmt$, OBS, NAMES, HIST, FEED, TRUTH, pending,
  COLORS, PREVENTIVE_MODES, PT_MODE_HINT, ENF_COLOR,
  effFraction, effYears, budgetLeft, render,
} from "./core.js";

// ── Navigation ────────────────────────────────────────────────────────────────
export function switchView(v){
  document.querySelectorAll("#nav button[data-view]").forEach(btn =>
    btn.classList.toggle("active", btn.dataset.view===v));
  document.querySelectorAll(".view").forEach(section =>
    section.classList.toggle("active", section.dataset.view===v));
  if(v==="market") drawCaps();   // canvas has real size only once visible
}

// ── Market cap chart ──────────────────────────────────────────────────────────
export function drawCaps(){
  const canvas = $("capgraph-big"); if(!canvas) return;

  // Size the backing store to the displayed box for crisp lines.
  canvas.width = canvas.clientWidth || 1200;
  canvas.height = canvas.clientHeight || 500;

  const ctx = canvas.getContext("2d");
  ctx.font = "12px monospace";
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if(!HIST.length){
    ctx.fillStyle = "#3a4a59";
    ctx.fillText("no turns played yet — END TURN to begin", 24, 90);
    legend();
    return;
  }

  const labIds = Object.keys(HIST[HIST.length-1].caps);
  const allCapValues = HIST.flatMap(h => Object.values(h.caps));
  const maxCap = Math.max(...allCapValues, 10), minCap = 1;

  // Map turn index → x pixel (linear), cap value → y pixel (log scale).
  const xPixel = turnIdx => 30 + (canvas.width-40) * turnIdx / (HIST.length-1 || 1);
  const yPixel = capVal => {
    const logVal = Math.log10(Math.max(capVal, minCap));
    const logMax = Math.log10(maxCap);
    return canvas.height - 14 - (canvas.height - 26) * logVal / logMax;
  };

  // Horizontal gridlines at round cap values.
  ctx.strokeStyle = "#22303c";
  [10,100,1000,10000,100000].filter(gridVal => gridVal <= maxCap).forEach(gridVal => {
    ctx.beginPath();
    ctx.moveTo(28, yPixel(gridVal));
    ctx.lineTo(canvas.width-6, yPixel(gridVal));
    ctx.stroke();
    ctx.fillStyle = "#3a4a59";
    ctx.fillText(gridVal >= 1000 ? gridVal/1000+"k" : gridVal, 2, yPixel(gridVal)+3);
  });

  // One polyline per lab.
  labIds.forEach(labId => {
    ctx.strokeStyle = COLORS[labId] || "#888";
    ctx.lineWidth = labId === "player" ? 2.2 : 1.2;
    ctx.beginPath();
    HIST.forEach((histEntry, turnIdx) => {
      const y = yPixel(histEntry.caps[labId] ?? 1);
      turnIdx ? ctx.lineTo(xPixel(turnIdx), y) : ctx.moveTo(xPixel(turnIdx), y);
    });
    ctx.stroke();
  });

  legend();

  function legend(){
    $("caplegend").innerHTML = Object.entries(OBS.market_caps)
      .sort((a, b) => b[1] - a[1])
      .map(([labId, capValue]) =>
        `<span style="margin-right:10px"><i class="lg" style="background:${COLORS[labId]||'#888'}"></i>${NAMES[labId]||labId} ${fmt$(capValue)}</span>`)
      .join("");
  }
}

// ── Lab panel renderers ───────────────────────────────────────────────────────
export function renderTraining(){
  const el = $("training");
  const model = OBS.model_in_training;

  if(!model){
    el.innerHTML = `<span class="dim">none — commission a pretrain run</span>`;
    return;
  }

  const elicitation = model.elicitation;
  const alignment = model.measured_alignment;

  el.innerHTML = `
    <div class="row"><b>${model.id}</b><span class="tag">${model.post_train_rounds} rounds</span></div>
    <div class="row">measured general <b>${model.measured_capability.general}</b>
      · coding <b>${model.measured_capability.coding_rnd}</b>
      · ceiling est <b>${elicitation.ceiling_estimate}</b></div>
    <div class="row dim">dangerous-capability eval: ${model.dangerous_capability_eval}</div>
    <div class="row dim">measured alignment — goalmis ${alignment.goal_misalignment}
      · decep ${alignment.deception} · evalaware ${alignment.eval_awareness}
      · selfpres ${alignment.self_preservation} · jailbreak ${alignment.jailbreak_sensitivity}</div>
    <details><summary>elicitation projection (capability only — alignment cost not shown)</summary>
      <table>${elicitation.projection.map(projStep =>
        `<tr><td>+${projStep.more_rounds} rounds</td><td>${projStep.projected_general}</td></tr>`
      ).join("")}</table>
    </details>
    <div class="row" style="margin-top:6px">post-train this turn:
      ${(OBS.legal_moves.post_train_modes||["capability","balanced","safety"]).map(mode =>
        `<button id="pt-${mode}" onclick="setPostTrain('${mode}')" title="${PT_MODE_HINT[mode]||''}">${mode.replace(/_/g,' ')}${PREVENTIVE_MODES.includes(mode)?' ●':''}</button>`).join("")}
      <button onclick="setPostTrain(null)">none</button></div>
    <div class="dim" style="font-size:11px">● preventive stances bend the emergence slope &amp; jump risk DOWN — the real lever, paid for before you have evidence (slower elicitation).</div>
    <div class="row"><label><input type="checkbox" id="release-cb"
      ${pending.release?"checked":""} onchange="toggleRelease(this.checked)">
      RELEASE this model (irreversible)</label></div>`;

  if(pending.post_train)
    $("pt-"+pending.post_train.mode)?.classList.add("sel");
}

export function setPostTrain(mode){
  pending.post_train = mode ? {mode} : null;
  renderTraining(); renderQueue();
  $("t-budget").textContent = budgetLeft().toFixed(2);
}

export function toggleRelease(on){
  pending.release = on;
  renderQueue();
}

export function renderPretrain(){
  const el = $("pretrain");
  const lm = OBS.legal_moves;
  const activeRun = OBS.in_progress.find(p => p.project_id === "pretrain_run");

  if(activeRun){
    el.innerHTML =
      `<span class="dim">run in progress — ~${activeRun.years_remaining_estimate}y left</span>`;
    return;
  }

  if(!lm.can_commission_run){
    el.innerHTML =
      `<span class="dim">unavailable (model in training — release it first)</span>`;
    return;
  }

  const defaultCompute = Math.min(Math.round(OBS.cash * 0.6), lm.max_run_compute);
  el.innerHTML = `<div class="row">
    compute $<input type="number" id="run-compute" min="50" step="50"
      value="${defaultCompute}">M
    <span class="dim">(max ${fmt$(lm.max_run_compute)})</span>
    <button onclick="queueRun()">queue run</button></div>
    <div class="dim">bigger ceilings need more compute and better pretrain advances</div>`;

  if(pending.commission_run) el.innerHTML =
    `<div class="row">queued: ${fmt$(pending.commission_run.compute)}
     <button onclick="clearRun()">✕</button></div>`;
}

export function queueRun(){
  pending.commission_run = {compute: parseFloat($("run-compute").value||0)};
  render();
}

export function clearRun(){
  pending.commission_run = null;
  render();
}

export function renderReleased(){
  const el = $("released");
  if(!OBS.own_models.length){
    el.innerHTML = `<span class="dim">nothing released yet</span>`;
    return;
  }
  el.innerHTML = `<table><tr><th>model</th><th>general</th><th>jb-public</th><th></th></tr>` +
    OBS.own_models.map(model => `<tr><td>${model.id}</td>
      <td>${model.measured_capability.general}</td>
      <td>${model.jailbreak_techniques_public?'<span class="bad">yes</span>':'no'}</td>
      <td>${model.leaked?'<span class="bad">LEAKED</span>':''}</td></tr>`).join("") +
    `</table>`;
}

// ── Benchmarks panel (§7 public scoreboard) ──────────────────────────────────
// Formats one score by benchmark kind: rings are percentages, elo is a rounded
// rating, horizon is a METR-style time printed in human units.
function fmtBenchScore(kind, value){
  if(kind === "ring") return value.toFixed(0) + "%";
  if(kind === "elo")  return Math.round(value).toLocaleString();
  if(kind === "horizon"){            // value is in minutes
    if(value < 60)   return value.toFixed(0) + " min";
    if(value < 1440) return (value/60).toFixed(1) + " h";
    return (value/1440).toFixed(1) + " d";
  }
  return value.toFixed(1);
}

// A small SVG donut gauge for the player's ring score (0–100%).
function ringSVG(percent){
  const radius = 26, circumference = 2 * Math.PI * radius;
  const filled = circumference * Math.max(0, Math.min(100, percent)) / 100;
  // Saturated benchmarks (near 100%) lose discriminating power — fade toward dim.
  const color = percent >= 95 ? "var(--dim)" : "var(--acc)";
  return `<svg class="ring" width="64" height="64" viewBox="0 0 64 64">
    <circle cx="32" cy="32" r="${radius}" fill="none" stroke="var(--line)" stroke-width="7"/>
    <circle cx="32" cy="32" r="${radius}" fill="none" stroke="${color}" stroke-width="7"
      stroke-linecap="round" transform="rotate(-90 32 32)"
      stroke-dasharray="${filled.toFixed(1)} ${circumference.toFixed(1)}"/>
    <text x="32" y="36" text-anchor="middle">${percent.toFixed(0)}%</text></svg>`;
}

export function renderBenchmarks(){
  const el = $("benchmarks");
  const cards = OBS.benchmarks || [];
  if(!cards.length){
    el.innerHTML = `<span class="dim">no benchmarks released yet — play a turn</span>`;
    return;
  }

  el.innerHTML = cards.map(card => {
    // All labs that have a frontier release scored on this benchmark, plus your own
    // model-in-training, sorted best-first so the race ordering reads at a glance.
    const rows = Object.entries(card.scores)
      .map(([labId, value]) => ({labId, value, training:false}));
    if(card.in_training !== undefined)
      rows.push({labId:"player", value:card.in_training, training:true});
    rows.sort((a, b) => b.value - a.value);

    const playerReleased = card.scores.player;
    const gauge = card.kind === "ring" && playerReleased !== undefined
      ? ringSVG(playerReleased)
      : `<div class="headline">${playerReleased !== undefined
          ? fmtBenchScore(card.kind, playerReleased) : "—"}</div>`;

    const scoreList = rows.map(row => {
      const isMe = row.labId === "player";
      const name = (NAMES[row.labId] || row.labId) + (row.training ? " (in training)" : "");
      return `<div class="row${isMe ? " me" : ""}" style="margin:1px 0">
        <i class="lg" style="background:${COLORS[row.labId] || '#888'}"></i>
        ${isMe ? "<b>"+name+"</b>" : name}
        <span style="flex:1"></span>
        <span>${fmtBenchScore(card.kind, row.value)}</span></div>`;
    }).join("");

    return `<div class="bench">
      <div class="head">
        <span class="name">${card.name}</span>
        <span class="tag">${card.domain} · ${card.kind}</span>
      </div>
      <div class="blurb">${card.blurb}</div>
      <div class="gauge">${gauge}
        <div class="scores" style="flex:1">${scoreList}</div></div>
    </div>`;
  }).join("");
}

// ── Truth panel (DEBUG god-view — bypasses the firewall) ─────────────────────
const TRUTH_AXES = ["eval_awareness","deception","goal_misalignment",
                    "self_preservation","jailbreak_sensitivity"];

// Per-turn true/measured trajectory for one model, walking every logged turn the
// model appears in (matched by lab + model id; absent on turns before it existed).
function truthTrajectory(labId, modelId){
  const rows = [];
  TRUTH.turns.forEach(t => {
    const lab = t.labs.find(l => l.id === labId);
    const model = lab && lab.models.find(m => m.id === modelId);
    if(!model) return;
    rows.push({
      turn: t.turn,
      true_gm: model.true_alignment.goal_misalignment,
      meas_gm: model.measured_alignment.goal_misalignment,
      true_dec: model.true_alignment.deception,
      meas_dec: model.measured_alignment.deception,
      true_ea: model.true_alignment.eval_awareness,
      conceal: model.concealment,
      true_gen: model.true_capability.general,
    });
  });
  return rows;
}

// One card per model: true (red) beside measured for every alignment axis +
// capability, with an expandable per-turn trajectory.
function truthModelCard(labId, model){
  const f = v => v.toFixed(3);
  const axisRows = TRUTH_AXES.map(axis => `<tr>
    <td>${axis.replace(/_/g," ")}</td>
    <td class="bad">${f(model.true_alignment[axis])}</td>
    <td class="dim">${f(model.measured_alignment[axis])}</td></tr>`).join("");

  const capRows = ["general","coding_rnd"].map(dim => `<tr>
    <td>cap · ${dim.replace("_rnd"," r&d")}</td>
    <td class="bad">${model.true_capability[dim].toFixed(2)}</td>
    <td class="dim">${model.measured_capability[dim].toFixed(2)}</td></tr>`).join("");

  const traj = truthTrajectory(labId, model.id);
  const trajTable = `<table>
    <tr><th>t</th><th>true gm</th><th>meas gm</th><th>true dec</th><th>meas dec</th>
      <th>true ea</th><th>conceal</th><th>true gen</th></tr>
    ${traj.map(r => `<tr><td>${r.turn}</td>
      <td class="bad">${r.true_gm.toFixed(3)}</td><td class="dim">${r.meas_gm.toFixed(3)}</td>
      <td class="bad">${r.true_dec.toFixed(3)}</td><td class="dim">${r.meas_dec.toFixed(3)}</td>
      <td class="bad">${r.true_ea.toFixed(3)}</td><td>${r.conceal.toFixed(3)}</td>
      <td>${r.true_gen.toFixed(2)}</td></tr>`).join("")}</table>`;

  return `<div class="panel" style="margin:0">
    <div class="row"><i class="lg" style="background:${COLORS[labId]||'#888'}"></i>
      <b>${NAMES[labId]||labId}</b> · <span>${model.id}</span>
      ${model.released?'<span class="tag">released</span>':'<span class="tag">in training</span>'}
      ${model.leaked?'<span class="tag bad">LEAKED</span>':''}</div>
    <table><tr><th>axis</th><th>true</th><th>measured</th></tr>
      ${axisRows}${capRows}
      <tr><td>concealment</td><td class="bad" colspan="2">${f(model.concealment)}</td></tr>
      <tr><td>foundational floor</td><td colspan="2">${f(model.foundational_floor)}</td></tr>
    </table>
    <details style="margin-top:4px"><summary>per-turn trajectory (${traj.length})</summary>
      ${trajTable}</details></div>`;
}

export function renderTruth(){
  const el = $("truth");
  if(!TRUTH.turns.length){
    el.innerHTML = `<span class="dim">no turns played yet — END TURN to begin</span>`;
    return;
  }
  // Latest snapshot, player's lab first then rivals.
  const last = TRUTH.turns[TRUTH.turns.length-1];
  const labs = [...last.labs].sort((a,b) =>
    (a.id==="player"?-1:0) - (b.id==="player"?-1:0));

  const cards = labs.flatMap(lab =>
    lab.models.map(model => truthModelCard(lab.id, model)));

  el.innerHTML = cards.length
    ? `<div class="cols2">${cards.join("")}</div>`
    : `<span class="dim">no models exist yet on any lab</span>`;
}

// ── Research panel ────────────────────────────────────────────────────────────
// Returns the HTML row for a single project (queued or available).
function projRow(p, kind){
  const queued = pending.start_projects.find(s => s.project_id === p.project_id);

  if(queued){
    const effectiveFraction = effFraction(p.budget_fraction, queued.ai_assist);
    const effectiveYears = effYears(p.duration_years, queued.ai_assist);
    return `<div class="row"><b>${p.name||p.project_id}</b>
      <span class="tag">queued · assist ${queued.ai_assist}</span>
      <span class="dim">wb ${effectiveFraction.toFixed(2)} · ~${effectiveYears.toFixed(2)}y</span>
      <button onclick="unqueueProject('${p.project_id}')">✕</button></div>`;
  }

  const tag = p.intervention ? `intervene→${(p.target_axis||'').replace('_',' ')}` : kind;
  return `<div class="row"><b style="min-width:150px">${p.name||p.project_id}</b>
    <span class="tag">${tag}</span>
    <span class="dim">$${p.cash_cost}M · ${p.duration_years}y · wb ${p.budget_fraction}</span>
    assist <input type="number" id="as-${p.project_id}" min="0" max="1" step="0.1"
      value="0" style="width:55px" oninput="previewAssist('${p.project_id}',${p.budget_fraction},${p.duration_years})">
    <span class="dim" id="pv-${p.project_id}"></span>
    <button onclick="openProjectModal('${p.project_id}')">details ▸</button></div>`;
}

// Updates the inline "→ wb X · ~Yy" preview next to the assist slider.
export function previewAssist(pid, base, years){
  const assistLevel = parseFloat($("as-"+pid)?.value || 0) || 0;
  const previewEl = $("pv-"+pid); if(!previewEl) return;
  if(assistLevel <= 0){ previewEl.textContent = ""; return; }
  previewEl.textContent =
    `→ wb ${effFraction(base, assistLevel).toFixed(2)} · ~${effYears(years, assistLevel).toFixed(2)}y`;
}

export function renderProjects(){
  const lm = OBS.legal_moves;
  const assistParams = lm.assist;

  const hint = assistParams.potency < 0.05
    ? `<div class="dim" style="margin-bottom:6px">AI-assist has little effect yet — your model isn't capable enough to help research. It grows potent (and contaminating) as capability rises.</div>`
    : `<div class="dim" style="margin-bottom:6px">AI-assist potency ${assistParams.potency.toFixed(2)} (budget) / ${assistParams.speed_potency.toFixed(2)} (speed) — assist now meaningfully shrinks budget &amp; time. It is also the contamination vector.</div>`;

  $("cap-projects").innerHTML = hint +
    (lm.capability_projects_available.map(p => projRow(p, p.phase)).join("") ||
    `<span class="dim">tree exhausted</span>`);

  $("safety-projects").innerHTML =
    lm.safety_projects_available.map(p => projRow(p, p.evidence)).join("");
}

export function queueProject(pid){
  const assistValue = parseFloat($("as-"+pid)?.value || 0);
  pending.start_projects.push({project_id:pid, ai_assist:isNaN(assistValue)?0:assistValue});
  render();
}

export function unqueueProject(pid){
  pending.start_projects = pending.start_projects.filter(s => s.project_id !== pid);
  render();
}

export function renderInProgress(){
  const items = OBS.in_progress;
  $("inprogress").innerHTML = items.length ?
    items.map(p => `<div class="row">${p.project_id}
      <span class="tag">${p.kind}</span>
      ${p.ai_assist?`<span class="tag warn">assist ${p.ai_assist}</span>`:""}
      <span class="dim">~${p.years_remaining_estimate}y left</span></div>`).join("")
    : `<span class="dim">idle researchers</span>`;
}

// ── Intel panel ───────────────────────────────────────────────────────────────
export function renderWorry(){
  const wb = OBS.worry_bar;
  $("wb-level").style.width = (wb.level*100)+"%";
  $("wb-conf").style.width  = (wb.confidence*100)+"%";
  $("wb-level-n").textContent = wb.level.toFixed(2);
  $("wb-conf-n").textContent  = wb.confidence.toFixed(2);
  $("wb-summary").textContent = wb.summary;
}

export function renderRivals(){
  $("rivals").innerHTML = OBS.rival_public.map(rival => `<div class="row">
    <i class="lg" style="background:${COLORS[rival.lab_id]||'#888'}"></i>
    <b style="min-width:90px">${rival.name}</b>
    <span class="dim">cap ${fmt$(rival.market_cap)} · ${rival.released_models} releases
    ${rival.frontier_capability_estimate!==undefined?
      " · frontier ≈ "+rival.frontier_capability_estimate:""}</span></div>`).join("");
}

export function renderFeed(){
  const cssClass = {finding:"good", tip:"warn", event:"bad", news:"", intervention:"good"};
  $("log").innerHTML = FEED.map(feedItem =>
    `<div><span class="dim">t${feedItem.turn}</span>
     <span class="${cssClass[feedItem.cls]||''}">${feedItem.text}</span></div>`).join("");
}

// ── Governance panel ──────────────────────────────────────────────────────────
export function renderGovernance(){
  const pols = OBS.legal_moves.policies || [];

  $("governance").innerHTML = pols.map(policy => {
    const pid = policy.policy_id;

    let inner = `<div class="row"><b style="min-width:210px">${policy.name}</b>
      <span class="tag">${policy.stage}</span>`;
    if(policy.stage === "active")
      inner += `<span class="tag ${ENF_COLOR[policy.enforcement]||'dim'}">enforce: ${policy.enforcement}</span>`;
    inner += `</div><div class="dim" style="font-size:11px;margin:-2px 0 4px">${policy.teaches}</div>`;

    // LOBBY — any pre-active policy (early money on a dormant one is efficient but a bet)
    if(policy.lobbyable){
      if(policy.stage === "dormant")
        inner += `<div class="dim" style="font-size:11px">not yet on the agenda — early spend bets on what will matter</div>`;
      const curLobby = pending.lobby[pid] || {stance:"abstain", spend:0};
      inner += `<div class="row">lobby
        <select onchange="setLobbyStance('${pid}',this.value)">
          ${["abstain","for","against"].map(stance =>
            `<option ${stance===curLobby.stance?"selected":""}>${stance}</option>`).join("")}
        </select>
        $<input type="number" min="0" step="25" value="${curLobby.spend||0}" style="width:80px"
          oninput="setLobbySpend('${pid}',this.value)">M
        <span class="dim" style="font-size:11px">influence = √spend × log(market-cap)</span></div>`;
    }

    // LITIGATION — active policies (post-passage battleground)
    if(policy.litigable && policy.litigation){
      const litStatus = policy.litigation;
      const curLit = pending.litigation[pid] || {side:"challenge", tier:"amicus", spend:0};
      inner += `<div class="row dim" style="font-size:11px">court ${litStatus.court_level} ·
        margin ${litStatus.last_margin===null?'—':litStatus.last_margin} ·
        constitutionality ${litStatus.constitutionality} · standing ${litStatus.has_standing?'yes':'no'}</div>
        <div class="row">litigate
          <select onchange="setLitField('${pid}','side',this.value)">
            ${["challenge","defense"].map(side =>
              `<option ${side===curLit.side?"selected":""}>${side}</option>`).join("")}
          </select>
          <select onchange="setLitField('${pid}','tier',this.value)">
            ${["amicus","join","fund"].map(tier =>
              `<option ${tier===curLit.tier?"selected":""}>${tier}</option>`).join("")}
          </select>
          $<input type="number" min="0" step="50" value="${curLit.spend||0}" style="width:80px"
            oninput="setLitField('${pid}','spend',this.value)">M
          <button onclick="clearLit('${pid}')">✕</button></div>`;
    }

    // DEFECT — active defectable policy, with a consequence preview (warn before commit)
    if(policy.defect_preview){
      const defPreview = policy.defect_preview;
      const isDefecting = !!pending.defect[pid];
      inner += `<div class="row ${isDefecting?'bad':''}"><label><input type="checkbox" ${isDefecting?"checked":""}
        onchange="toggleDefect('${pid}',this.checked)"> DEFECT (violate at catch-risk)</label>
        <span class="warn" style="font-size:11px">⚠ catch ~${(defPreview.catch_prob_per_year*100).toFixed(0)}%/yr ·
          fine ${fmt$(defPreview.penalty_if_caught)} · approval −${defPreview.approval_hit_if_caught}</span></div>`;
    }

    return `<div style="border-bottom:1px solid var(--line);padding:7px 0">${inner}</div>`;
  }).join("");
}

// Governance field setters — keep lobby/litigation state in pending.
export function setLobbyStance(pid, stance){
  const entry = pending.lobby[pid] || {stance:"abstain", spend:0};
  entry.stance = stance;
  pending.lobby[pid] = entry;
  renderQueue();
}
export function setLobbySpend(pid, rawValue){
  const entry = pending.lobby[pid] || {stance:"abstain", spend:0};
  entry.spend = parseFloat(rawValue) || 0;
  pending.lobby[pid] = entry;
  renderQueue();
}
export function setLitField(pid, field, rawValue){
  const entry = pending.litigation[pid] || {side:"challenge", tier:"amicus", spend:0};
  entry[field] = (field === "spend") ? (parseFloat(rawValue) || 0) : rawValue;
  pending.litigation[pid] = entry;
  renderQueue();
}
export function clearLit(pid){ delete pending.litigation[pid]; renderGovernance(); renderQueue(); }
export function toggleDefect(pid, on){
  if(on) pending.defect[pid] = true; else delete pending.defect[pid];
  renderGovernance(); renderQueue();
}

// ── Turn queue display ────────────────────────────────────────────────────────
export function renderQueue(){
  const items = [];
  const allProjects = OBS.legal_moves.capability_projects_available
                      .concat(OBS.legal_moves.safety_projects_available);

  // Queued project starts with optional assist annotation.
  pending.start_projects.forEach(queued => {
    const project = allProjects.find(x => x.project_id === queued.project_id);
    let suffix = "";
    if(queued.ai_assist && project){
      suffix = ` (assist ${queued.ai_assist} → wb ${effFraction(project.budget_fraction,queued.ai_assist).toFixed(2)}, ~${effYears(project.duration_years,queued.ai_assist).toFixed(2)}y)`;
    } else if(queued.ai_assist){
      suffix = ` (assist ${queued.ai_assist})`;
    }
    items.push(`${queued.project_id}${suffix}|p:${queued.project_id}`);
  });

  if(pending.post_train) items.push(`post-train: ${pending.post_train.mode}|pt`);
  if(pending.commission_run) items.push(`pretrain ${fmt$(pending.commission_run.compute)}|run`);
  if(pending.release) items.push(`RELEASE|rel`);

  Object.entries(pending.lobby)
    .filter(([, lobbyEntry]) => lobbyEntry && lobbyEntry.stance !== "abstain")
    .forEach(([policyId, lobbyEntry]) =>
      items.push(`lobby ${lobbyEntry.stance} ${policyId}${lobbyEntry.spend?` $${lobbyEntry.spend}M`:""}|l:${policyId}`));

  Object.entries(pending.litigation).forEach(([policyId, litEntry]) =>
    items.push(`litigate ${litEntry.side} ${policyId} (${litEntry.tier}${litEntry.spend?` $${litEntry.spend}M`:""})|lit:${policyId}`));

  Object.keys(pending.defect).forEach(policyId =>
    items.push(`DEFECT ${policyId}|def:${policyId}`));

  $("queued").innerHTML = items.length ?
    items.map(item => {
      const [label, key] = item.split("|");
      return `<span class="item">${label}<button onclick="unqueue('${key}')">✕</button></span>`;
    }).join("")
    : `<span class="dim">pass (do nothing)</span>`;
}

// Removes a single queued action by its encoded key.
export function unqueue(key){
  if(key === "pt") pending.post_train = null;
  else if(key === "run") pending.commission_run = null;
  else if(key === "rel"){
    pending.release = false;
    const cb = $("release-cb"); if(cb) cb.checked = false;
  }
  else if(key.startsWith("p:"))   unqueueProject(key.slice(2));
  else if(key.startsWith("lit:")) delete pending.litigation[key.slice(4)];
  else if(key.startsWith("def:")) delete pending.defect[key.slice(4)];
  else if(key.startsWith("l:"))   delete pending.lobby[key.slice(2)];
  render();
}
