"use strict";
// ── warnings: the §7c per-item "explain it, then carry it out" modal ─────────
// Clicking a research item opens a modal that explains what it does, shows the
// diegetic mechanism-teaching warning(s) for the risk it carries (from the
// backend warning catalog in legal_moves.warnings), and offers to carry it out.
// Education arrives exactly at the moment of choosing (design §7c).
import { $, OBS } from "./core.js";
import { queueProject } from "./views.js";

// One warning's layered HTML: line (always) -> why (expandable) -> paper link.
function warningHTML(catalog, id, emphasised){
  const w = catalog[id];
  if(!w) return "";
  const paper = w.paper
    ? `<div style="margin-top:4px"><a href="${w.paper.url}" target="_blank"
         rel="noopener" class="acc">${w.paper.title} ↗</a></div>`
    : "";
  return `<div class="warn-item${emphasised ? " warn-emph" : ""}">
    <div class="warn-line">⚠ your researchers warn — ${w.line}</div>
    <details><summary>why this happens</summary>
      <div class="dim" style="margin-top:4px">${w.why}</div>${paper}</details></div>`;
}

// Which catalog warnings apply to a given project, and whether to emphasise the
// assist warning (assist already cranked high on its row).
function projectWarnings(project, isSafety){
  const W = OBS.legal_moves.warnings;
  const out = [];
  const assistVal = parseFloat($("as-" + project.project_id)?.value || 0) || 0;
  out.push({ id: W.assist, emphasised: assistVal >= W.assist_emphasis_threshold });
  if(isSafety && project.intervention &&
     W.disposition_axes.includes(project.target_axis))
    out.push({ id: W.intervention_disposition, emphasised: false });
  return out;
}

function findProject(pid){
  const lm = OBS.legal_moves;
  const cap = lm.capability_projects_available.find(p => p.project_id === pid);
  if(cap) return { project: cap, isSafety: false };
  const safe = lm.safety_projects_available.find(p => p.project_id === pid);
  if(safe) return { project: safe, isSafety: true };
  return null;
}

// Opens the modal for one research item.
export function openProjectModal(pid){
  const found = findProject(pid);
  if(!found){ queueProject(pid); return; }   // fallback: never block the action
  const { project, isSafety } = found;
  const W = OBS.legal_moves.warnings;

  // §8b: the value-neutral "what it does" comes FIRST (teaches the concept + the
  // genuine benefit), then the risk layers after.
  const desc = isSafety
    ? `${project.blurb || ""}<div class="dim" style="margin-top:4px">evidence:
        ${project.evidence} · spoofability ${project.spoofability}${
        project.intervention ? ` · intervenes on ${(project.target_axis||"").replace(/_/g," ")}` : ""}</div>`
    : `${project.what_it_does || ""}`;

  // Risk layer AFTER: the node's own risk framing (capability items), then the
  // generic §7c catalog warning(s) for the knobs this choice opens.
  const nodeRisk = (!isSafety && project.risk_blurb)
    ? `<div class="warn-item"><div class="warn-line">⚠ your researchers warn — ${project.risk_blurb}</div></div>`
    : "";
  const warns = nodeRisk + projectWarnings(project, isSafety)
    .map(w => warningHTML(W.catalog, w.id, w.emphasised)).join("");

  $("modal-body").innerHTML = `
    <h3 style="text-transform:none;color:var(--txt);font-size:15px">${project.name || pid}</h3>
    <div class="dim" style="margin-bottom:8px">$${project.cash_cost}M ·
      ${project.duration_years}y · work-budget ${project.budget_fraction}</div>
    <div style="margin-bottom:10px">${desc}</div>
    ${warns}
    <div class="row" style="margin-top:14px">
      <button class="primary" onclick="carryOutProject('${pid}')">carry it out ▸</button>
      <button onclick="closeItemModal()">cancel</button>
    </div>`;
  $("itemmodal").classList.add("show");
}

// "Carry it out" — performs the same queue action as before (reads the row's
// assist value), then closes the modal.
export function carryOutProject(pid){
  queueProject(pid);
  closeItemModal();
}

export function closeItemModal(){ $("itemmodal").classList.remove("show"); }
