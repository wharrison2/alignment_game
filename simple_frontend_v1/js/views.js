"use strict";
// ── views: every panel renderer + its inline-handler functions ───────────────
// Reads shared state from core (live bindings); calls core.render() to re-render
// after a queue change. Handlers referenced from generated HTML are exposed on
// window by main.js.
import {
  $, fmt$, OBS, NAMES, TICKERS, HIST, FEED, TRUTH, pending, esc,
  COLORS, ENF_COLOR,
  effFraction, effYears, budgetLeft, render, t,
} from "./core.js";
import {
  renderAvailableItems, renderInProgressItems, renderCompletedAdvances,
} from "./research.js";

// ── Navigation ────────────────────────────────────────────────────────────────
export function switchView(v){
  document.querySelectorAll("#nav button[data-view]").forEach(btn =>
    btn.classList.toggle("active", btn.dataset.view===v));
  document.querySelectorAll(".view").forEach(section =>
    section.classList.toggle("active", section.dataset.view===v));
  if(v==="market") drawCaps();   // <svg> has real pixel size only once visible
}

// ── Market cap chart ──────────────────────────────────────────────────────────
// An inline SVG line chart: one polyline per lab on a LINEAR market-cap y-axis,
// quarter dates along the bottom, and a "tab" ticker pinned at the right end of
// each line. Between the real quarter data points we draw a deterministic, purely
// VISUAL stock-like wiggle (see capWiggleSteps) — it never touches game state.

const SVG_NS = "http://www.w3.org/2000/svg";

// Layout margins (px) around the plotting area inside the SVG viewport.
const CAP_MARGIN_LEFT = 46;     // room for y-axis cap labels
const CAP_MARGIN_RIGHT = 84;    // room for the right-pinned tab tickers
const CAP_MARGIN_TOP = 12;
const CAP_MARGIN_BOTTOM = 24;   // room for the x-axis date labels

// The interim wiggle divides each quarter into this many sub-steps. The trough
// list (see capWiggleSteps) has one entry per step and sums to zero, so the
// endpoints of every quarter land EXACTLY on the real market-cap value.
const CAP_WIGGLE_STEPS_PER_QUARTER = 15;

// Per-step vertical "trough" magnitude in log space — controls how jagged the
// interim wiggle looks. Small so the visual stays near the real trend line.
const CAP_WIGGLE_TROUGH_SCALE = 0.012;

// Quarter dates start here (mirrors backend config START_YEAR / DT_YEARS: one
// turn is one quarter). The graph is display-only, so duplicating these is fine.
const CAP_START_YEAR = 2021;
const CAP_QUARTERS_PER_YEAR = 4;

// Tab-ticker geometry (px). The tab is triangle(point facing LEFT) + rectangle +
// right semicircle; sized to the text, enlarged slightly on hover via CSS scale.
const CAP_TAB_HEIGHT = 16;
const CAP_TAB_TRIANGLE_WIDTH = 7;
const CAP_TAB_TEXT_PADDING = 6;
const CAP_TAB_CHAR_WIDTH = 7.5;   // approx advance of the 11px monospace ticker

export function drawCaps(){
  const svg = $("capgraph-big"); if(!svg) return;

  // Size the SVG coordinate system to the displayed box so 1 unit == 1 px.
  const width = svg.clientWidth || 1200;
  const height = svg.clientHeight || 500;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  while(svg.firstChild) svg.removeChild(svg.firstChild);

  if(!HIST.length){
    appendSvgText(svg, CAP_MARGIN_LEFT, 90,
      t("caps.empty"), "cap-axis-text");
    renderCapLegend();
    return;
  }

  const labIds = Object.keys(HIST[HIST.length-1].caps);
  const allCapValues = HIST.flatMap(histEntry => Object.values(histEntry.caps));
  const maxCap = Math.max(...allCapValues, 10);

  const plotLeft = CAP_MARGIN_LEFT;
  const plotRight = width - CAP_MARGIN_RIGHT;
  const plotTop = CAP_MARGIN_TOP;
  const plotBottom = height - CAP_MARGIN_BOTTOM;

  // x maps turn index → px (linear, evenly spaced quarters); y maps cap → px on a
  // LINEAR scale (was log) so absolute lead/gap between labs reads truthfully.
  const lastTurnIdx = HIST.length - 1;
  const xForTurn = turnIdx => plotLeft +
    (plotRight - plotLeft) * turnIdx / (lastTurnIdx || 1);
  const yForCap = capValue => plotBottom -
    (plotBottom - plotTop) * capValue / maxCap;

  drawCapGridlines(svg, maxCap, plotLeft, plotRight, yForCap);
  drawCapDateAxis(svg, HIST, xForTurn, plotBottom);

  // Draw a line + right-edge tab ticker for every lab. Group elements so the
  // hover handlers can thicken the line AND enlarge the tab together.
  labIds.forEach(labId => {
    drawCapLabSeries(svg, labId, xForTurn, yForCap);
  });

  renderCapLegend();
}

// Append an SVG <text> with content set via textContent (XSS-safe even for the
// player-authored ticker — never built into innerHTML markup).
function appendSvgText(parent, x, y, text, className){
  const node = document.createElementNS(SVG_NS, "text");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  if(className) node.setAttribute("class", className);
  node.textContent = text;
  parent.appendChild(node);
  return node;
}

// Horizontal gridlines at a few round-ish cap values up to the max.
function drawCapGridlines(svg, maxCap, plotLeft, plotRight, yForCap){
  const candidateLevels = [10, 100, 250, 500, 1000, 2500, 5000, 10000,
                           25000, 50000, 100000, 250000, 500000, 1000000];
  const visibleLevels = candidateLevels.filter(level => level <= maxCap);
  visibleLevels.forEach(level => {
    const y = yForCap(level);
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", plotLeft);
    line.setAttribute("x2", plotRight);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("class", "cap-gridline");
    svg.appendChild(line);

    const label = level >= 1000 ? (level / 1000) + "k" : String(level);
    appendSvgText(svg, 4, y + 3, label, "cap-axis-text");
  });
}

// Quarter-date labels along the bottom. Derived from the turn index: one turn is
// one quarter starting at CAP_START_YEAR (mirrors backend START_YEAR/DT_YEARS).
// Thin the labels when turns are crowded so they don't overlap.
function drawCapDateAxis(svg, hist, xForTurn, plotBottom){
  const maxLabels = 10;
  const labelStride = Math.max(1, Math.ceil(hist.length / maxLabels));
  hist.forEach((histEntry, turnIdx) => {
    const isLastTurn = turnIdx === hist.length - 1;
    if(turnIdx % labelStride !== 0 && !isLastTurn) return;
    const label = quarterLabelForTurn(histEntry.turn);
    const node = appendSvgText(svg, xForTurn(turnIdx), plotBottom + 16,
      label, "cap-axis-text");
    node.setAttribute("text-anchor", "middle");
  });
}

// Turn index → "Q1 2021"-style label (4 quarters per year from CAP_START_YEAR).
function quarterLabelForTurn(turnIndex){
  const yearOffset = Math.floor(turnIndex / CAP_QUARTERS_PER_YEAR);
  const quarterOfYear = (turnIndex % CAP_QUARTERS_PER_YEAR) + 1;
  const year = CAP_START_YEAR + yearOffset;
  return "Q" + quarterOfYear + " " + year;
}

// Draw one lab's wiggling polyline plus its right-edge tab ticker, wired so
// hovering either element thickens the line and enlarges the tab.
function drawCapLabSeries(svg, labId, xForTurn, yForCap){
  const color = COLORS[labId] || "#888";
  const isPlayer = labId === "player";

  const points = capWigglePoints(labId, xForTurn, yForCap);
  const pointsAttr = points.map(p => p.x.toFixed(1) + "," + p.y.toFixed(1)).join(" ");

  const line = document.createElementNS(SVG_NS, "polyline");
  line.setAttribute("points", pointsAttr);
  line.setAttribute("stroke", color);
  line.setAttribute("class", "cap-line" + (isPlayer ? " cap-line-player" : ""));
  svg.appendChild(line);

  const lineEnd = points[points.length - 1];
  const tab = buildCapTab(labId, color, lineEnd.x, lineEnd.y);
  svg.appendChild(tab);

  // Hover on the line OR the tab thickens the line and grows the tab together.
  const setHover = isHovering => {
    line.classList.toggle("cap-hover", isHovering);
    tab.classList.toggle("cap-tab-hover", isHovering);
    tab.style.transform = isHovering ?
      `translate(${lineEnd.x}px,${lineEnd.y}px) scale(1.18) translate(${-lineEnd.x}px,${-lineEnd.y}px)` :
      "";
  };
  line.addEventListener("mouseenter", () => setHover(true));
  line.addEventListener("mouseleave", () => setHover(false));
  tab.addEventListener("mouseenter", () => setHover(true));
  tab.addEventListener("mouseleave", () => setHover(false));
}

// Build the wiggling point list for a lab: real quarter endpoints with the
// deterministic interim noise (capWiggleSteps) filling each quarter interval.
function capWigglePoints(labId, xForTurn, yForCap){
  const points = [];
  for(let quarterIdx = 0; quarterIdx < HIST.length - 1; quarterIdx++){
    const startCap = HIST[quarterIdx].caps[labId] ?? 1;
    const endCap = HIST[quarterIdx + 1].caps[labId] ?? 1;
    const turnIndex = HIST[quarterIdx].turn;
    const interimCaps = capWiggleSteps(labId, turnIndex, startCap, endCap);
    interimCaps.forEach((capValue, stepIdx) => {
      const stepFraction = stepIdx / CAP_WIGGLE_STEPS_PER_QUARTER;
      const x = xForTurn(quarterIdx) + stepFraction *
        (xForTurn(quarterIdx + 1) - xForTurn(quarterIdx));
      points.push({x, y: yForCap(capValue)});
    });
  }
  // The very last real quarter has no following point to wiggle toward, so pin it.
  const lastTurnIdx = HIST.length - 1;
  const lastCap = HIST[lastTurnIdx].caps[labId] ?? 1;
  points.push({x: xForTurn(lastTurnIdx), y: yForCap(lastCap)});
  return points;
}

// The interim noise, per the designer's method (FIX_ITEMS "Market cap graph"):
//   - split the quarter into N steps;
//   - build a zero-sum trough list (length N, summing to 0) and SHUFFLE it;
//   - displayed value at step i = exp( sum(troughs[0..i]) + i*ln(growth)/N ),
//     where growth = endCap/startCap. The cumulative trough term is mean-zero so
//     the endpoints stay EXACTLY on the real quarter values; the i*ln(growth)/N
//     term tilts the interior up toward endCap like a real stock chart.
// The wiggle is DISPLAY-ONLY and must never touch the seeded game RNG, so the
// shuffle is driven by a tiny self-contained PRNG seeded by (turn, lab) — same
// (lab, quarter) ⇒ same shuffle on every re-render/resize (no jitter), and the
// result is cached so we only shuffle once.
const _capWiggleCache = new Map();

function capWiggleSteps(labId, turnIndex, startCap, endCap){
  const cacheKey = labId + "@" + turnIndex;
  let troughs = _capWiggleCache.get(cacheKey);
  if(!troughs){
    troughs = buildShuffledTroughs(labId, turnIndex);
    _capWiggleCache.set(cacheKey, troughs);
  }

  const growthFactor = endCap / (startCap || 1);
  const logGrowthPerStep = Math.log(growthFactor) / CAP_WIGGLE_STEPS_PER_QUARTER;

  const caps = [];
  let cumulativeTrough = 0;
  for(let step = 0; step < CAP_WIGGLE_STEPS_PER_QUARTER; step++){
    cumulativeTrough += troughs[step];
    const logValue = cumulativeTrough + step * logGrowthPerStep;
    caps.push(startCap * Math.exp(logValue));
  }
  return caps;
}

// A symmetric, zero-sum trough list (…,-2,-1,0,1,2,… scaled), then shuffled by a
// deterministic per-(lab,quarter) PRNG so it never re-randomizes across renders.
function buildShuffledTroughs(labId, turnIndex){
  const stepCount = CAP_WIGGLE_STEPS_PER_QUARTER;
  const troughs = [];
  for(let step = 0; step < stepCount; step++){
    const centered = step - (stepCount - 1) / 2;   // symmetric → sums to zero
    troughs.push(centered * CAP_WIGGLE_TROUGH_SCALE);
  }

  // Deterministic seed from the turn index and a stable hash of the lab id; this
  // is the ONLY randomness here and it is wall-of-glass separate from the game RNG.
  const seed = (turnIndex + 1) * 1000003 + hashLabId(labId);
  const nextRandom = makeDisplayPrng(seed);

  // Fisher–Yates shuffle driven by the display PRNG.
  for(let i = troughs.length - 1; i > 0; i--){
    const j = Math.floor(nextRandom() * (i + 1));
    const swap = troughs[i];
    troughs[i] = troughs[j];
    troughs[j] = swap;
  }
  return troughs;
}

// Tiny self-contained PRNG (mulberry32) for DISPLAY noise only. NOT the seeded
// game RNG — this never influences game state, just the cosmetic wiggle.
function makeDisplayPrng(seed){
  let state = seed >>> 0;
  return function nextRandom(){
    state = (state + 0x6D2B79F5) >>> 0;
    let scrambled = state;
    scrambled = Math.imul(scrambled ^ (scrambled >>> 15), scrambled | 1);
    scrambled ^= scrambled + Math.imul(scrambled ^ (scrambled >>> 7), scrambled | 61);
    return ((scrambled ^ (scrambled >>> 14)) >>> 0) / 4294967296;
  };
}

// Stable small integer hash of a lab id, so the display PRNG seed is reproducible.
function hashLabId(labId){
  let hash = 0;
  for(let i = 0; i < labId.length; i++){
    hash = (hash * 31 + labId.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

// Build a tab-shaped ticker pinned at (lineEndX, lineEndY): an isosceles triangle
// whose POINT faces LEFT toward the line end, a rectangle in the middle holding
// the ticker text, and a semicircle capping the RIGHT edge. Drawn as one <path>;
// ticker text is set via textContent (XSS-safe) and forced sans-serif in CSS.
function buildCapTab(labId, color, lineEndX, lineEndY){
  const ticker = (TICKERS[labId] || labId).toUpperCase();
  const textWidth = Math.max(ticker.length * CAP_TAB_CHAR_WIDTH, CAP_TAB_CHAR_WIDTH);
  const rectWidth = textWidth + CAP_TAB_TEXT_PADDING * 2;
  const halfHeight = CAP_TAB_HEIGHT / 2;

  // Geometry, left → right, vertically centered on the line end:
  //   triangle tip at lineEndX (points left), triangle base CAP_TAB_TRIANGLE_WIDTH
  //   to the right, then the rectangle, then a semicircle of radius halfHeight.
  const triangleTipX = lineEndX;
  const rectLeftX = triangleTipX + CAP_TAB_TRIANGLE_WIDTH;
  const rectRightX = rectLeftX + rectWidth;
  const top = lineEndY - halfHeight;
  const bottom = lineEndY + halfHeight;

  const pathData = [
    `M ${triangleTipX} ${lineEndY}`,            // triangle tip (points at the line)
    `L ${rectLeftX} ${top}`,                    // up to rectangle top-left
    `L ${rectRightX} ${top}`,                   // across the rectangle top
    `A ${halfHeight} ${halfHeight} 0 0 1 ${rectRightX} ${bottom}`,  // right semicircle
    `L ${rectLeftX} ${bottom}`,                 // back across the rectangle bottom
    "Z",                                        // close to the triangle tip
  ].join(" ");

  const group = document.createElementNS(SVG_NS, "g");
  group.setAttribute("class", "cap-tab");

  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", pathData);
  path.setAttribute("fill", color);
  path.setAttribute("class", "cap-tab-shape");
  group.appendChild(path);

  const textX = rectLeftX + rectWidth / 2;
  const text = appendSvgText(group, textX, lineEndY + 4, ticker, "cap-tab-text");
  text.setAttribute("text-anchor", "middle");
  return group;
}

// Bottom legend: a swatch + ticker + name + current cap per lab. Player-authored
// names/tickers are untrusted, so escape both before they go into innerHTML.
function renderCapLegend(){
  $("caplegend").innerHTML = Object.entries(OBS.market_caps)
    .sort((a, b) => b[1] - a[1])
    .map(([labId, capValue]) => {
      const ticker = esc(TICKERS[labId] || labId);
      const name = esc(NAMES[labId] || labId);
      const swatch = `<i class="lg" style="background:${COLORS[labId]||'#888'}"></i>`;
      return `<span style="margin-right:10px">${swatch}<b>${ticker}</b> ${name} ${fmt$(capValue)}</span>`;
    })
    .join("");
}

// ── Lab panel renderers ───────────────────────────────────────────────────────
export function renderTraining(){
  const el = $("training");
  const model = OBS.model_in_training;

  if(!model){
    el.innerHTML = `<span class="dim">${t("training.empty")}</span>`;
    return;
  }

  const elicitation = model.elicitation;
  const alignment = model.measured_alignment;

  el.innerHTML = `
    <div class="row"><b>${model.id}</b><span class="tag">${t("training.rounds", {rounds: model.post_train_rounds})}</span></div>
    <div class="row">${t("training.measuredGeneral")} <b>${model.measured_capability.general}</b>
      · ${t("training.coding")} <b>${model.measured_capability.coding_rnd}</b>
      · ${t("training.ceilingEst")} <b>${elicitation.ceiling_estimate}</b></div>
    <div class="row dim">${t("training.dangerousEval", {value: model.dangerous_capability_eval})}</div>
    <div class="row dim">${t("training.measuredAlignment", {
      goalmis: alignment.goal_misalignment, decep: alignment.deception,
      evalaware: alignment.eval_awareness, selfpres: alignment.self_preservation,
      jailbreak: alignment.jailbreak_sensitivity})}</div>
    <details><summary>${t("training.projection.summary")}</summary>
      <table>${elicitation.projection.map(projStep =>
        `<tr><td>${t("training.projection.moreRounds", {rounds: projStep.more_rounds})}</td><td>${projStep.projected_general}</td></tr>`
      ).join("")}</table>
    </details>
    ${postTrainSafetyHTML()}
    <div class="row"><label><input type="checkbox" id="release-cb"
      ${pending.release?"checked":""} onchange="toggleRelease(this.checked)">
      ${t("training.release.label")}</label></div>`;
}

// The post-train round controls. The old per-round MODE dropdown is gone (Stage A
// removed the knob); a round is now defined by WHICH researched post-train safety
// advances you APPLY to it (legal_moves.applicable_post_train_safety → the
// post_train action's applied_safety list).
function postTrainSafetyHTML(){
  const applicable = OBS.legal_moves.applicable_post_train_safety || [];
  const queued = pending.post_train;          // null | {applied_safety:[ids]}
  const applied = (queued && queued.applied_safety) || [];

  const advanceRows = applicable.length
    ? applicable.map(advance => {
        const isApplied = applied.includes(advance.advance_id);
        return `<div class="row"><label title="${esc(advance.risk_blurb || "")}">
          <input type="checkbox" ${isApplied ? "checked" : ""}
            onchange="togglePostTrainSafety('${esc(advance.advance_id)}',this.checked)">
          ${esc(advance.name)}</label></div>`;
      }).join("")
    : `<div class="dim" style="font-size:11px">${t("postTrain.empty")}</div>`;

  const ptQueued = queued != null;
  return `<div class="row" style="margin-top:6px"><b>${t("postTrain.heading")}</b>
      <label style="margin-left:8px"><input type="checkbox" ${ptQueued ? "checked" : ""}
        onchange="togglePostTrain(this.checked)"> ${t("postTrain.runRound")}</label></div>
    <div class="dim" style="font-size:11px">${t("postTrain.explainer")}</div>
    ${ptQueued ? advanceRows : ""}`;
}

// Toggle whether a post-train round runs this turn. Starting one preserves any
// already-chosen advances; turning it off clears the queued post_train entirely.
export function togglePostTrain(on){
  pending.post_train = on ? {applied_safety: pending.post_train?.applied_safety || []} : null;
  renderTraining(); renderQueue();
  $("t-budget").textContent = budgetLeft().toFixed(2);
}

// Apply / un-apply one researched post-train safety advance to this round.
export function togglePostTrainSafety(advanceId, on){
  if(!pending.post_train) pending.post_train = {applied_safety: []};
  const applied = pending.post_train.applied_safety;
  if(on){ if(!applied.includes(advanceId)) applied.push(advanceId); }
  else  { pending.post_train.applied_safety = applied.filter(id => id !== advanceId); }
  renderQueue();
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
      `<span class="dim">${t("pretrain.inProgress", {years: activeRun.years_remaining_estimate})}</span>`;
    return;
  }

  if(!lm.can_commission_run){
    el.innerHTML =
      `<span class="dim">${t("pretrain.unavailable")}</span>`;
    return;
  }

  const defaultCompute = Math.min(Math.round(OBS.cash * 0.6), lm.max_run_compute);
  el.innerHTML = `<div class="row">
    ${t("pretrain.compute.pre")}<input type="number" id="run-compute" min="50" step="50"
      value="${defaultCompute}">M
    <span class="dim">${t("pretrain.compute.maxNote", {max: fmt$(lm.max_run_compute)})}</span>
    <button onclick="queueRun()">${t("pretrain.queueRun")}</button></div>
    <div class="dim">${t("pretrain.computeHint")}</div>
    ${pretrainSafetyHTML()}`;

  if(pending.commission_run){
    const applied = pending.commission_run.applied_safety || [];
    // applied ids come from the chosen advances — esc() before they enter innerHTML.
    const appliedNote = applied.length
      ? t("pretrain.queued.safetyNote", {list: esc(applied.join(", "))}) : "";
    el.innerHTML =
      `<div class="row">${t("pretrain.queued.prefix")}${fmt$(pending.commission_run.compute)}${appliedNote}
       <button onclick="clearRun()">✕</button></div>`;
  }
}

// Pretrain safety-advance pickers. Pretrain safety advances (data cleaning,
// aligned synthetic data) act on the foundational floor & base goal-mis; the
// player applies the ones they've researched at commission time
// (legal_moves.applicable_pretrain_safety → commission_run.applied_safety).
function pretrainSafetyHTML(){
  const applicable = OBS.legal_moves.applicable_pretrain_safety || [];
  if(!applicable.length)
    return `<div class="dim" style="font-size:11px;margin-top:4px">${t("pretrain.safety.empty")}</div>`;

  const applied = pending.commission_run?.applied_safety || [];
  const rows = applicable.map(advance => {
    const isApplied = applied.includes(advance.advance_id);
    return `<div class="row"><label title="${esc(advance.risk_blurb || "")}">
      <input type="checkbox" id="prts-${esc(advance.advance_id)}" ${isApplied ? "checked" : ""}>
      ${esc(advance.name)}</label></div>`;
  }).join("");
  return `<div class="dim" style="font-size:11px;margin-top:6px">${t("pretrain.safety.apply")}</div>${rows}`;
}

export function queueRun(){
  const applicable = OBS.legal_moves.applicable_pretrain_safety || [];
  // read each pretrain safety-advance checkbox built by pretrainSafetyHTML (id "prts-<id>")
  const chosenSafety = applicable
    .filter(advance => $("prts-" + advance.advance_id)?.checked)
    .map(advance => advance.advance_id);
  pending.commission_run = {
    compute: parseFloat($("run-compute").value || 0),
    applied_safety: chosenSafety,
  };
  render();
}

export function clearRun(){
  pending.commission_run = null;
  render();
}

export function renderReleased(){
  const el = $("released");
  if(!OBS.own_models.length){
    el.innerHTML = `<span class="dim">${t("released.empty")}</span>`;
    return;
  }
  el.innerHTML = `<table><tr><th>${t("released.col.model")}</th><th>${t("released.col.general")}</th><th>${t("released.col.jbPublic")}</th><th></th></tr>` +
    OBS.own_models.map(model => `<tr><td>${model.id}</td>
      <td>${model.measured_capability.general}</td>
      <td>${model.jailbreak_techniques_public?`<span class="bad">${t("released.yes")}</span>`:t("released.no")}</td>
      <td>${model.leaked?`<span class="bad">${t("released.leaked")}</span>`:''}</td></tr>`).join("") +
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
    el.innerHTML = `<span class="dim">${t("benchmarks.empty")}</span>`;
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
      // Lab name is player-authored/untrusted — escape before innerHTML.
      const labName = esc(NAMES[row.labId] || row.labId);
      const name = labName + (row.training ? t("caps.inTraining") : "");
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

  // Lab name is player-authored/untrusted — escape before innerHTML (even on the
  // debug Truth tab; the §2 firewall discipline applies here in full).
  return `<div class="panel" style="margin:0">
    <div class="row"><i class="lg" style="background:${COLORS[labId]||'#888'}"></i>
      <b>${esc(NAMES[labId]||labId)}</b> · <span>${esc(model.id)}</span>
      ${model.released?`<span class="tag">${t("truth.released")}</span>`:`<span class="tag">${t("truth.inTraining")}</span>`}
      ${model.leaked?`<span class="tag bad">${t("truth.leaked")}</span>`:''}</div>
    <table><tr><th>${t("truth.col.axis")}</th><th>${t("truth.col.true")}</th><th>${t("truth.col.measured")}</th></tr>
      ${axisRows}${capRows}
      <tr><td>${t("truth.concealment")}</td><td class="bad" colspan="2">${f(model.concealment)}</td></tr>
      <tr><td>${t("truth.foundationalFloor")}</td><td colspan="2">${f(model.foundational_floor)}</td></tr>
    </table>
    <details style="margin-top:4px"><summary>${t("truth.trajectory.summary", {count: traj.length})}</summary>
      ${trajTable}</details></div>`;
}

export function renderTruth(){
  const el = $("truth");
  if(!TRUTH.turns.length){
    el.innerHTML = `<span class="dim">${t("truth.empty")}</span>`;
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
    : `<span class="dim">${t("truth.noModels")}</span>`;
}

// ── Research panel ────────────────────────────────────────────────────────────
// The unified research-item state-machine cards live in research.js; the panels
// here just feed it the right list and grouping. Capability/safety/completed each
// get their own panel so the split reads at a glance.

// The "kind" tag shown on an available capability card (its training phase).
function capabilityKindTag(item){
  return item.phase;
}

// The "kind" tag shown on an available safety card. Safety items are a MIX of
// measurement/intervention PROJECTS and the §8b safety ADVANCES; both arrive in
// safety_projects_available + safety_advances_available, so the tag reflects which.
function safetyKindTag(item){
  if(item.intervention)
    return `intervene → ${(item.target_axis || "").replace(/_/g, " ")}`;
  if(item.phase)            // a safety ADVANCE carries a training phase
    return `advance · ${item.phase}`;
  return item.evidence || "safety";
}

// Updates the inline "→ wb X · ~Yy" preview next to a card's assist slider.
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
    ? `<div class="dim" style="margin-bottom:6px">${t("research.assistHint.weak")}</div>`
    : `<div class="dim" style="margin-bottom:6px">${t("research.assistHint.potent", {
        budget: assistParams.potency.toFixed(2),
        speed: assistParams.speed_potency.toFixed(2)})}</div>`;

  $("cap-projects").innerHTML = hint;
  // append the capability cards beneath the assist hint
  renderAvailableInto("cap-projects", lm.capability_projects_available,
    capabilityKindTag, t("research.capability.empty"), /*append=*/true);

  // Safety panel = measurement/intervention projects AND the §8b safety advances.
  const safetyItems = lm.safety_projects_available.concat(lm.safety_advances_available);
  renderAvailableItems("safety-projects", safetyItems, safetyKindTag, t("research.safety.empty"));

  renderCompletedAdvances("completed-advances", OBS.researched_advances,
    t("research.completed.empty"));
}

// Small adapter so the capability panel can keep its assist hint above the cards.
function renderAvailableInto(containerId, items, kindOf, emptyText, append){
  const container = $(containerId);
  if(!container) return;
  const hintHTML = append ? container.innerHTML : "";
  renderAvailableItems(containerId, items, kindOf, emptyText);
  if(append) container.innerHTML = hintHTML + container.innerHTML;
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
  renderInProgressItems("inprogress", OBS.in_progress, t("research.inProgress.empty"));
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
  // rival.name / rival.ticker are public lab identity but still strings that
  // (for the player's own lab) can be user-authored — escape before innerHTML.
  $("rivals").innerHTML = OBS.rival_public.map(rival => `<div class="row">
    <i class="lg" style="background:${COLORS[rival.lab_id]||'#888'}"></i>
    <span class="tag">${esc(rival.ticker || rival.lab_id)}</span>
    <b style="min-width:90px">${esc(rival.name)}</b>
    <span class="dim">${t("rivals.cap", {cap: fmt$(rival.market_cap), releases: rival.released_models})}
    ${rival.frontier_capability_estimate!==undefined?
      t("rivals.frontier", {value: rival.frontier_capability_estimate}):""}</span></div>`).join("");
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

    // Header: name | stage. The stage cell is a fixed-width grid column so the
    // lifecycle label (dormant/introduced/passed/signed/active) aligns vertically
    // across every policy item — scan the column to read the whole board's state.
    let stageCell = `<span class="tag stage-${policy.stage}">${policy.stage}</span>`;
    if(policy.stage === "active")
      stageCell += `<span class="tag ${ENF_COLOR[policy.enforcement]||'dim'}">${t("gov.enforce", {level: policy.enforcement})}</span>`;
    let inner = `<div class="policy-head">
      <span class="policy-name">${policy.name}</span>
      <span class="policy-stage">${stageCell}</span></div>
      <div class="policy-teaches">${policy.teaches}</div>`;

    // LOBBY — any pre-active policy (early money on a dormant one is efficient but a bet)
    if(policy.lobbyable){
      if(policy.stage === "dormant")
        inner += `<div class="dim" style="font-size:11px">${t("gov.dormantNote")}</div>`;
      const curLobby = pending.lobby[pid] || {stance:"abstain", spend:0};
      inner += `<div class="row">${t("gov.lobby.label")}
        <select onchange="setLobbyStance('${pid}',this.value)">
          ${["abstain","for","against"].map(stance =>
            `<option ${stance===curLobby.stance?"selected":""}>${stance}</option>`).join("")}
        </select>
        $<input type="number" min="0" step="25" value="${curLobby.spend||0}" style="width:80px"
          oninput="setLobbySpend('${pid}',this.value)">M
        <span class="dim" style="font-size:11px">${t("gov.lobby.influenceNote")}</span></div>`;
    }

    // LITIGATION — active policies (post-passage battleground)
    if(policy.litigable && policy.litigation){
      const litStatus = policy.litigation;
      const curLit = pending.litigation[pid] || {side:"challenge", tier:"amicus", spend:0};
      inner += `<div class="row dim" style="font-size:11px">${t("gov.lit.status", {
        court: litStatus.court_level,
        margin: litStatus.last_margin===null?'—':litStatus.last_margin,
        constitutionality: litStatus.constitutionality,
        standing: litStatus.has_standing?t("gov.lit.standingYes"):t("gov.lit.standingNo")})}</div>
        <div class="row">${t("gov.lit.label")}
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
        onchange="toggleDefect('${pid}',this.checked)"> ${t("gov.defect.label")}</label>
        <span class="warn" style="font-size:11px">${t("gov.defect.preview", {
          catch: (defPreview.catch_prob_per_year*100).toFixed(0),
          fine: fmt$(defPreview.penalty_if_caught),
          approval: defPreview.approval_hit_if_caught})}</span></div>`;
    }

    return `<div class="policy">${inner}</div>`;
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

  if(pending.post_train){
    const applied = pending.post_train.applied_safety || [];
    const label = applied.length
      ? t("queue.postTrain.withSafety", {count: applied.length})
      : t("queue.postTrain.bare");
    items.push(`${label}|pt`);
  }
  if(pending.commission_run){
    const applied = pending.commission_run.applied_safety || [];
    const safetyNote = applied.length ? ` +${applied.length} safety` : "";
    items.push(`pretrain ${fmt$(pending.commission_run.compute)}${safetyNote}|run`);
  }
  if(pending.release) items.push(`${t("queue.release")}|rel`);

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
    : `<span class="dim">${t("queue.pass")}</span>`;
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
