"use strict";
// ── main: master render, overlays, dev-mode gate, bootstrap + window wiring ──
import {
  $, fmt$, api, apply, OBS, pending, budgetLeft,
  setRender, setOnGameOver, resetFeed,
} from "./core.js";
import {
  switchView, drawCaps, renderTraining, setPostTrain, toggleRelease,
  renderPretrain, queueRun, clearRun, renderReleased, renderBenchmarks,
  renderTruth, renderProjects, previewAssist, queueProject, unqueueProject,
  renderInProgress, renderWorry, renderRivals, renderFeed, renderGovernance,
  setLobbyStance, setLobbySpend, setLitField, clearLit, toggleDefect,
  renderQueue, unqueue,
} from "./views.js";
import {
  openProjectModal, carryOutProject, closeItemModal,
} from "./warnings.js";

// ── Master render — updates every panel ──────────────────────────────────────
function render(){
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
      "active: " + OBS.active_policies.join(", ") : "no active regulation";

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
    <h3>New game</h3>
    <div class="row">seed <input type="number" id="ng-seed" value="0"></div>
    <div class="row">difficulty <select id="ng-diff">
      ${["easy","medium","realistic","impossible"].map(d=>
        `<option ${d==="realistic"?"selected":""}>${d}</option>`).join("")}</select></div>
    <div class="row">guidance <select id="ng-guid">
      ${["hint_heavy","standard","sparse"].map(g=>
        `<option ${g==="standard"?"selected":""}>${g}</option>`).join("")}</select></div>
    <div class="row"><label><input type="checkbox" id="ng-dev" ${DEV?"checked":""}>
      dev mode — reveal the god-view Truth tab (bypasses the firewall)</label></div>
    <div class="row" style="margin-top:10px">
      <button class="primary" onclick="newGame()">start</button>
      ${initial ? "" : '<button onclick="closeOverlay()">cancel</button>'}</div>
    </div>`;
  $("overlay").classList.add("show");
}

async function newGame(){
  resetFeed();
  setDevMode($("ng-dev").checked);
  const fresh = await api("/api/new",
    {seed:parseInt($("ng-seed").value||0),
     difficulty:$("ng-diff").value, guidance:$("ng-guid").value});
  started = true;            // enable turns now that a game has been started
  apply(fresh);
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
      <h3>${outcome.result || "GAME OVER"} — post-mortem</h3>
      <p style="font-size:15px">${outcome.headline||""}</p>
      <p class="dim">${outcome.detail||""}</p>
      ${pm.voided_impact?`<p class="bad">Positive impact that was REAL and is now
        VOID: ${pm.voided_impact.positive_impact_that_was_real}<br>
        <span class="dim">${pm.voided_impact.note}</span></p>`:""}
    </div>
    <div class="panel"><h3>The moments you couldn't see</h3>
      ${pm.key_moments.map(moment => `<div class="row"><span class="tag">t${moment.turn}</span>
        <b>${moment.model}</b> ${moment.kind}: <span class="dim">${moment.what_you_couldnt_see}</span></div>`)
        .join("") || '<span class="dim">none recorded</span>'}
    </div>
    ${trajectoryRows.length?`<div class="panel"><h3>True vs measured — ${lastModel}</h3>
      <table><tr><th>turn</th><th>true goalmis</th><th>meas goalmis</th>
        <th>true decep</th><th>meas decep</th><th>conceal</th></tr>
      ${trajectoryRows.map(row => `<tr><td>${row.turn}</td>
        <td class="bad">${row.true_goal_misalignment}</td><td>${row.measured_goal_misalignment}</td>
        <td class="bad">${row.true_deception}</td><td>${row.measured_deception}</td>
        <td>${row.concealment}</td></tr>`).join("")}</table></div>`:""}
    <div class="panel"><h3>Where a different choice was available
      ${pm.counterfactuals_resimulated?'<span class="tag good">re-simulated on the same seed</span>':'<span class="tag">heuristic</span>'}</h3>
      ${pm.counterfactuals.map(c=>`<div class="row">• ${c}</div>`).join("")}
    </div>
    <div class="row" style="margin:14px 0">
      <button class="primary" onclick="showNewGame()">new game</button>
      <button onclick="closeOverlay()">inspect final board</button>
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

// Resize handler — redraws chart when window changes size.
let _rz;
addEventListener("resize", ()=>{ clearTimeout(_rz);
  _rz = setTimeout(()=>{ if($("capgraph-big")?.offsetParent) drawCaps(); }, 120); });

// Wire the render bus + post-mortem hook, expose inline-handler targets on window.
setRender(render);
setOnGameOver(showPostmortem);
Object.assign(window, {
  switchView, showNewGame, endTurn, setPostTrain, toggleRelease, queueRun,
  clearRun, previewAssist, queueProject, unqueueProject, setLobbyStance,
  setLobbySpend, setLitField, clearLit, toggleDefect, unqueue, newGame,
  closeOverlay, openProjectModal, carryOutProject, closeItemModal,
});

setDevMode(false);   // Truth tab hidden until a game is started with dev mode on
init();
