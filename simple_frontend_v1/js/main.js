"use strict";
// ── main: master render, overlays, dev-mode gate, bootstrap + window wiring ──
import {
  $, fmt$, api, apply, OBS, pending, budgetLeft,
  setRender, setOnGameOver, resetFeed, t,
} from "./core.js";
import {
  switchView, drawCaps, renderTraining, togglePostTrain, togglePostTrainSafety,
  toggleRelease, renderPretrain, queueRun, clearRun, renderReleased, renderBenchmarks,
  renderTruth, renderProjects, previewAssist, queueProject, unqueueProject,
  renderInProgress, renderWorry, renderRivals, renderFeed, renderGovernance,
  setLobbyStance, setLobbySpend, setLitField, clearLit, toggleDefect, openPolicyModal,
  renderQueue, unqueue,
} from "./views.js";
import {
  openProjectModal, carryOutProject, closeItemModal,
} from "./warnings.js";

// ── Master render — updates every panel ──────────────────────────────────────
function render(){
  if(!OBS) return;   // no game yet — nothing to render (guards pre-start renders)
  // Top bar chips
  $("t-turn").textContent = OBS.turn;
  $("t-year").textContent = OBS.year.toFixed(2);
  $("t-cash").textContent = fmt$(OBS.cash);
  $("t-rev").textContent  = fmt$(OBS.revenue_rate);
  $("t-inv").textContent  = fmt$(OBS.investment_rate);
  $("t-budget").textContent = budgetLeft().toFixed(2);
  $("t-appr").textContent = OBS.public_approval;
  $("t-chatter").textContent = OBS.regulatory_chatter;
  $("t-policies").textContent = OBS.active_policies.length ?
      t("topbar.policies.active", {list: OBS.active_policies.join(", ")}) :
      t("topbar.policies.none");

  drawCaps(); renderTraining(); renderPretrain(); renderReleased();
  renderBenchmarks();
  renderProjects(); renderInProgress(); renderWorry(); renderGovernance();
  renderRivals(); renderFeed(); renderQueue(); renderTruth();
  // No turns until a game has been started through the new-game modal (and never
  // once the game is over).
  $("endturn").disabled = !started || !!OBS.game_over;
}

// A game must be explicitly started via the new-game modal before any turn can be
// taken. Set true only when newGame() completes.
let started = false;

// ── Dev mode (god-view Truth tab) — OFF by default, opt-in per game ──────────
// The Truth tab bypasses the true/measured firewall; it's a debug instrument, so
// it stays hidden unless the player ticks "dev mode" when starting a game.
let DEV = false;
function setDevMode(on){
  DEV = on;
  document.querySelectorAll('[data-view="truth"]').forEach(el =>
    el.style.display = on ? "" : "none");
  if(!on) switchView("market");   // never leave the player stranded on a hidden tab
}

// ── Turn submission ───────────────────────────────────────────────────────────
async function endTurn(){
  if(!started) return;   // modal must be dismissed via "start" first
  pending.sign_safe_harbor = $("safeharbor").checked;
  $("endturn").disabled = true;
  const res = await api("/api/action", {action: pending});
  $("endturn").disabled = false;
  if(res.errors){ $("errors").textContent = res.errors.join("\n"); return; }
  apply(res);
}

// ── Overlays ──────────────────────────────────────────────────────────────────
function closeOverlay(){ $("overlay").classList.remove("show"); }

function showNewGame(opts){
  // On first load the modal is mandatory — no cancel, so a game can't be skipped.
  const initial = !!(opts && opts.initial);
  $("overlay-content").innerHTML = `
    <div class="panel" style="max-width:460px;margin:60px auto">
    <h3>${t("newgame.title")}</h3>
    <div class="row">${t("newgame.labName.label")}
      <input type="text" id="ng-name" maxlength="40" placeholder="${t("newgame.labName.placeholder")}"
        oninput="onLabNameInput()" style="flex:1"></div>
    <div class="row">${t("newgame.ticker.label")}
      <input type="text" id="ng-ticker" maxlength="6" placeholder="${t("newgame.ticker.placeholder")}"
        oninput="onTickerInput()" style="width:90px;text-transform:uppercase">
      <span class="dim" style="font-size:11px">${t("newgame.ticker.hint")}</span></div>
    <div class="row">${t("newgame.seed.label")} <input type="number" id="ng-seed" value="0"></div>
    <div class="row">${t("newgame.difficulty.label")} <select id="ng-diff">
      ${["easy","medium","realistic","impossible"].map(d=>
        `<option ${d==="realistic"?"selected":""}>${d}</option>`).join("")}</select></div>
    <div class="row">${t("newgame.guidance.label")} <select id="ng-guid">
      ${["hint_heavy","standard","sparse"].map(g=>
        `<option ${g==="standard"?"selected":""}>${g}</option>`).join("")}</select></div>
    <div class="row"><label><input type="checkbox" id="ng-dev" ${DEV?"checked":""}>
      ${t("newgame.dev.label")}</label></div>
    <div class="row" style="margin-top:10px">
      <button class="primary" onclick="newGame()">${t("newgame.start")}</button>
      ${initial ? "" : `<button onclick="closeOverlay()">${t("newgame.cancel")}</button>`}</div>
    </div>`;
  $("overlay").classList.add("show");
}

// ── New-game lab name → ticker auto-derive ───────────────────────────────────
// The ticker DEFAULTS to the first 3 letters of the name (uppercased) and tracks
// the name as the player types it — UNTIL they edit the ticker by hand, after
// which we stop auto-deriving (their explicit choice wins). The server re-derives
// and sanitizes regardless, so this is convenience, not a trust boundary.
let tickerManuallyEdited = false;

// First three alphanumeric characters of the name, uppercased (mirrors the
// backend's derive_ticker_from_name so the preview matches what the server stores).
function deriveTicker(name){
  const alphanumeric = (name.match(/[a-zA-Z0-9]/g) || []).slice(0, 3);
  return alphanumeric.join("").toUpperCase();
}

function onLabNameInput(){
  if(tickerManuallyEdited) return;   // player took over the ticker — leave it alone
  $("ng-ticker").value = deriveTicker($("ng-name").value);
}

function onTickerInput(){
  // Any keystroke in the ticker field is the player claiming it; stop auto-deriving.
  tickerManuallyEdited = true;
}

async function newGame(){
  resetFeed();
  tickerManuallyEdited = false;   // reset for the next new-game modal
  // Dev mode is OPTIONAL: an UNCHECKED box is the normal path. It only toggles the
  // god-view Truth tab; nothing about starting a game depends on it being on.
  const devChecked = $("ng-dev") ? $("ng-dev").checked : false;
  // Send the raw name/ticker; the server sanitizes (length-clamp, control-char
  // strip, empty→default) — client values are convenience only, never trusted.
  const fresh = await api("/api/new",
    {seed:parseInt($("ng-seed").value||0),
     difficulty:$("ng-diff").value, guidance:$("ng-guid").value,
     lab_name:$("ng-name").value, ticker:$("ng-ticker").value});
  // Only enter the started state once the server actually built a game. If the
  // request errored, leave the modal open so the player can retry.
  if(fresh && fresh.errors){
    $("errors").textContent = fresh.errors.join("\n");
    return;
  }
  started = true;            // enable turns now that a game has been started
  // apply() populates OBS BEFORE anything renders. setDevMode() can switchView →
  // drawCaps, which reads OBS, so it must run AFTER apply — otherwise the
  // dev-unchecked path renders against a null OBS, throws, and the modal never
  // closes (looked like "can't start without dev mode"). See UI_ISSUES issue 10.
  apply(fresh);
  setDevMode(devChecked);
  closeOverlay();
}

async function showPostmortem(){
  const pm = await api("/api/postmortem");
  const outcome = pm.outcome || {};
  const lastModel = pm.trajectories.length ?
      pm.trajectories[pm.trajectories.length-1].model : null;
  const trajectoryRows = pm.trajectories.filter(t => t.model === lastModel).slice(-14);

  $("overlay-content").innerHTML = `
    <div class="panel">
      <h3>${outcome.result || t("postmortem.defaultResult")} — ${t("postmortem.suffix")}</h3>
      <p style="font-size:15px">${outcome.headline||""}</p>
      <p class="dim">${outcome.detail||""}</p>
      ${pm.voided_impact?`<p class="bad">${t("postmortem.voidedImpact.prefix")}${pm.voided_impact.positive_impact_that_was_real}<br>
        <span class="dim">${pm.voided_impact.note}</span></p>`:""}
    </div>
    <div class="panel"><h3>${t("postmortem.keyMoments.title")}</h3>
      ${pm.key_moments.map(moment => `<div class="row"><span class="tag">t${moment.turn}</span>
        <b>${moment.model}</b> ${moment.kind}: <span class="dim">${moment.what_you_couldnt_see}</span></div>`)
        .join("") || `<span class="dim">${t("postmortem.keyMoments.empty")}</span>`}
    </div>
    ${trajectoryRows.length?`<div class="panel"><h3>${t("postmortem.truthTable.title", {model: lastModel})}</h3>
      <table><tr><th>${t("postmortem.truthTable.turn")}</th><th>${t("postmortem.truthTable.trueGoalmis")}</th><th>${t("postmortem.truthTable.measGoalmis")}</th>
        <th>${t("postmortem.truthTable.trueDecep")}</th><th>${t("postmortem.truthTable.measDecep")}</th><th>${t("postmortem.truthTable.conceal")}</th></tr>
      ${trajectoryRows.map(row => `<tr><td>${row.turn}</td>
        <td class="bad">${row.true_goal_misalignment}</td><td>${row.measured_goal_misalignment}</td>
        <td class="bad">${row.true_deception}</td><td>${row.measured_deception}</td>
        <td>${row.concealment}</td></tr>`).join("")}</table></div>`:""}
    <div class="panel"><h3>${t("postmortem.counterfactuals.title")}
      ${pm.counterfactuals_resimulated?`<span class="tag good">${t("postmortem.counterfactuals.resimulated")}</span>`:`<span class="tag">${t("postmortem.counterfactuals.heuristic")}</span>`}</h3>
      ${pm.counterfactuals.map(c=>`<div class="row">• ${c}</div>`).join("")}
    </div>
    <div class="row" style="margin:14px 0">
      <button class="primary" onclick="showNewGame()">${t("postmortem.newGame")}</button>
      <button onclick="closeOverlay()">${t("postmortem.inspectBoard")}</button>
    </div>`;
  $("overlay").classList.add("show");
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
// Load whatever the server session holds (so the board renders behind the modal),
// then force the new-game modal: the player must start a game before any turn.
async function init(){
  apply(await api("/api/state"));
  showNewGame({initial: true});
}

// Resize handler — redraws the SVG chart when the window changes size. The chart
// only has real pixel dimensions while the Market view is visible, so gate on the
// market section being active (an inline <svg> has no reliable offsetParent).
let _rz;
function marketViewVisible(){
  const section = document.querySelector('.view[data-view="market"]');
  return !!(section && section.classList.contains("active"));
}
addEventListener("resize", ()=>{ clearTimeout(_rz);
  _rz = setTimeout(()=>{ if(marketViewVisible()) drawCaps(); }, 120); });

// Wire the render bus + post-mortem hook, expose inline-handler targets on window.
setRender(render);
setOnGameOver(showPostmortem);
Object.assign(window, {
  switchView, showNewGame, endTurn, togglePostTrain, togglePostTrainSafety,
  toggleRelease, queueRun, clearRun, previewAssist, queueProject, unqueueProject,
  setLobbyStance, setLobbySpend, setLitField, clearLit, toggleDefect, unqueue,
  openPolicyModal,
  newGame, closeOverlay, openProjectModal, carryOutProject, closeItemModal,
  onLabNameInput, onTickerInput,
});

setDevMode(false);   // Truth tab hidden until a game is started with dev mode on
init();
