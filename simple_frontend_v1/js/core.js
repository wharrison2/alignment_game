"use strict";
// ── core: shared state, constants, helpers, network, and the render bus ──────
// Everything here is imported by the view modules. The mutable game state lives
// in `let` exports (live bindings): only this module REASSIGNS them (in apply/
// freshPending/resetFeed); view modules read them and mutate their CONTENTS.

// ── DOM / formatting helpers ─────────────────────────────────────────────────
export const $ = id => document.getElementById(id);
export const fmt$ = v => "$" + Math.round(v).toLocaleString() + "M";

// HTML-escape any value before it goes into an innerHTML template. The research
// content we render comes from the trusted backend catalog today, but a later
// stage adds user-entered lab name/ticker — escaping here keeps these templates
// from becoming an XSS sink when that lands. Use for any value, not just strings.
export function esc(value){
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Re-export the strings table + lookup helper so view modules can import them
// from core alongside the other shared helpers, matching the existing pattern.
export { STRINGS, t } from "./strings.js";
import { t } from "./strings.js";

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

export const ENF_COLOR = {low:"dim", medium:"warn", high:"bad"};

// ── Mutable game state (live-binding exports) ────────────────────────────────
export let OBS = null, NAMES = {}, TICKERS = {}, HIST = [], FEED = [], TRUTH = {turns:[]};
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
  TICKERS = payload.lab_tickers || {};
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
    {turn, cls:"tip", text:t("feed.tip", {reliability:tip.reliability, text:tip.text})}));

  OBS.policy_news.forEach(newsItem => FEED.unshift(
    {turn, cls:"news", text:newsItem}));

  OBS.public_events.forEach(event => FEED.unshift(
    {turn, cls:"event", text:t("feed.event", {category:event.category, text:event.text})}));

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

  if(pending.post_train){
    // a post-train round costs a base work-budget plus whatever each APPLIED safety
    // advance adds (mirrors rules.applied_post_train_round_budget on the backend).
    const lm = OBS.legal_moves;
    usedBudget += lm.post_train_round_budget || 0;
    const applied = pending.post_train.applied_safety || [];
    const applicable = lm.applicable_post_train_safety || [];
    applied.forEach(advanceId => {
      const advance = applicable.find(a => a.advance_id === advanceId);
      if(advance) usedBudget += advance.round_budget || 0;
    });
  }
  return OBS.work_budget_free - usedBudget;
}
