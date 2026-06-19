"use strict";
// ── core: shared state, constants, helpers, network, and the render bus ──────
// Everything here is imported by the view modules. The mutable game state lives
// in `let` exports (live bindings): only this module REASSIGNS them (in apply/
// freshPending/resetFeed); view modules read them and mutate their CONTENTS.

// ── DOM / formatting helpers ─────────────────────────────────────────────────
export const $ = id => document.getElementById(id);
export const fmt$ = v => "$" + Math.round(v).toLocaleString() + "M";

// ── Network ──────────────────────────────────────────────────────────────────
export async function api(path, body){
  const response = await fetch(path, body===undefined ? {} :
    {method:"POST", headers:{"Content-Type":"application/json"},
     body:JSON.stringify(body)});
  return response.json();
}

// ── Constants ────────────────────────────────────────────────────────────────
export const COLORS = {player:"#4fb3ff", rival1:"#ff6868", rival2:"#ffb347",
                       rival3:"#9a7bff", rival4:"#6fd087", rival5:"#ff8ad0"};

export const PREVENTIVE_MODES = ["penalize_reward_hacking","inoculation"];

export const PT_MODE_HINT = {
  capability:"fast elicitation, minimal alignment shaping — raises jump risk",
  balanced:"steady elicitation + alignment shaping",
  safety:"slow elicitation, heavy corrective effort (gated late — patching trap)",
  penalize_reward_hacking:"preventive: lowers emergence slope + jump (bypasses concealment)",
  inoculation:"preventive: strongest jump/emergence suppression",
};

export const ENF_COLOR = {low:"dim", medium:"warn", high:"bad"};

// ── Mutable game state (live-binding exports) ────────────────────────────────
export let OBS = null, NAMES = {}, HIST = [], FEED = [], TRUTH = {turns:[]};
export let pending = freshPending();

export function freshPending(){
  // lobby: {pid:{stance,spend}}  litigation: {pid:{side,tier,spend}}  defect: {pid:true}
  return {start_projects:[], post_train:null, commission_run:null,
          release:false, lobby:{}, litigation:{}, defect:{}, sign_safe_harbor:false};
}

export function resetFeed(){ FEED = []; }

// ── Render bus — main.js registers the master render()/post-mortem hooks here,
// so view-module handlers can trigger a re-render without importing main. ──────
export let render = () => {};
export function setRender(fn){ render = fn; }
let onGameOver = () => {};
export function setOnGameOver(fn){ onGameOver = fn; }

// ── Core state application ────────────────────────────────────────────────────
// Receives a server payload, updates globals, and triggers a full render.
export async function apply(payload){
  if(payload.errors){ $("errors").textContent = payload.errors.join("\n"); return; }
  $("errors").textContent = "";
  OBS = payload.observation; NAMES = payload.lab_names; HIST = payload.caps_history;
  pending = freshPending();
  collectFeed();
  TRUTH = await api("/api/truth");   // debug god-view, served separately from OBS
  render();
  if(OBS.game_over) onGameOver();
}

// Prepends all new per-turn feed items (findings, tips, news, events) to FEED.
function collectFeed(){
  const turn = OBS.turn;

  OBS.new_findings.forEach(finding => FEED.unshift(
    {turn, cls:"finding", text:`[${finding.evidence}] ${finding.text}`}));

  OBS.tips.forEach(tip => FEED.unshift(
    {turn, cls:"tip", text:`tip (${tip.reliability}): ${tip.text}`}));

  OBS.policy_news.forEach(newsItem => FEED.unshift(
    {turn, cls:"news", text:newsItem}));

  OBS.public_events.forEach(event => FEED.unshift(
    {turn, cls:"event", text:`EVENT [${event.category}] ${event.text}`}));

  if(FEED.length>400) FEED.length = 400;
}

// ── AI-assist budget/time preview helpers ────────────────────────────────────
// Mirrors engine _effective_fraction / duration speedup so the player SEES
// assist shrink budget + time before committing.
export function effFraction(base, assist){
  const assistParams = OBS.legal_moves.assist;
  return base * (1 - assistParams.max_reduction * (assist||0) * assistParams.potency);
}
export function effYears(base, assist){
  const assistParams = OBS.legal_moves.assist;
  return base / (1 + assistParams.speedup * (assist||0) * assistParams.speed_potency);
}

// Returns remaining work-budget after all queued project costs.
export function budgetLeft(){
  let usedBudget = 0;
  const allProjects = OBS.legal_moves.capability_projects_available
                      .concat(OBS.legal_moves.safety_projects_available);

  pending.start_projects.forEach(queued => {
    const project = allProjects.find(x => x.project_id === queued.project_id);
    if(project) usedBudget += effFraction(project.budget_fraction, queued.ai_assist);
  });

  if(pending.post_train) usedBudget += 0.30;
  return OBS.work_budget_free - usedBudget;
}
