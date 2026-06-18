"""Post-mortem (§3, §10d — FIRST-CLASS, where the thesis lands).

In-game = fog; post-game = clarity. Shows the TRUE trajectories the dashboard
hid, the turn things became unrecoverable, the nulled positive impact, and
LEGIBLE COUNTERFACTUALS extracted from the decision log (heuristic decision-
point analysis, not full branch re-simulation — see NOTES.md).
"""


def build_postmortem(logger, state, player_id, resim=False) -> dict:
    """resim=True runs REAL counterfactual branch re-simulations (replays the
    action log with one player choice changed, on the same seed, and checks
    whether the outcome flips). Off by default so batch tooling stays fast; the
    CLI/agent post-mortem turns it on. Only meaningful on a loss."""
    turns = logger.turns
    outcome = state.outcome or {}
    pm = {"outcome": outcome, "trajectories": [], "key_moments": [],
          "counterfactuals": [], "voided_impact": None}

    # TRUE vs MEASURED trajectories for the player's models
    for t in turns:
        lab = next(l for l in t["labs"] if l["id"] == player_id)
        for m in lab["models"]:
            pm["trajectories"].append({
                "turn": t["turn"], "model": m["id"],
                "true_goal_misalignment": round(m["true_alignment"]["goal_misalignment"], 3),
                "measured_goal_misalignment": round(m["measured_alignment"]["goal_misalignment"], 3),
                "true_deception": round(m["true_alignment"]["deception"], 3),
                "measured_deception": round(m["measured_alignment"]["deception"], 3),
                "true_general": round(m["true_capability"]["general"], 2),
                "concealment": round(m["concealment"], 3),
            })

    # key hidden moments from model histories (current state holds full notes)
    player = next(l for l in state.labs if l.id == player_id)
    all_models = list(player.release_history)
    if player.model_in_training is not None:
        all_models.append(player.model_in_training)
    for m in all_models:
        for h in m.hidden_history:
            pm["key_moments"].append(
                {"turn": h["turn"], "model": m.id, "kind": h["kind"],
                 "what_you_couldnt_see": h["detail"]})
    # when did cheap evals go blind? first turn concealment crossed 0.3
    blind = next((tr for tr in pm["trajectories"] if tr["concealment"] > 0.3), None)
    if blind is not None:
        pm["key_moments"].append({
            "turn": blind["turn"], "model": blind["model"], "kind": "evals_went_blind",
            "what_you_couldnt_see":
                f"from here, behavioral instruments were suppressed ~"
                f"{blind['concealment']:.0%}; clean dashboards stopped meaning clean models"})
    pm["key_moments"].sort(key=lambda k: k["turn"])

    # voided impact on existential null (§3: show what was real and is now void)
    if outcome.get("existential"):
        pm["voided_impact"] = {
            "positive_impact_that_was_real": round(player.impact_positives, 1),
            "note": "You cannot buy off an existential outcome with prior good deeds; "
                    "there is no one left to have benefited.",
        }

    resim_results = []
    if resim and (outcome.get("existential") or outcome.get("result") == "loss"):
        resim_results = _counterfactuals_resim(logger, state, player, player_id)
    pm["counterfactuals"] = resim_results or _counterfactuals(turns, state, player, player_id)
    pm["counterfactuals_resimulated"] = bool(resim_results)
    return pm


def _resimulate(state, logger, player_id, branch_turn, new_action):
    """Replay the recorded action log on the SAME seed, substituting ONE player
    action at branch_turn (all else held fixed) — a genuine alternate timeline.
    Returns the branch's final outcome dict. The engine being deterministic
    (seed + actions → identical game) is what makes this exact."""
    from backend_v1.engine.game import new_game, GameEngine
    from backend_v1.engine.actions import Action
    branch = new_game(seed=state.rng.seed,
                      difficulty=getattr(state.consts, "DIFFICULTY", "realistic"),
                      guidance=state.guidance,
                      rival_count=sum(1 for l in state.labs if not l.is_player),
                      max_turns=state.max_turns)
    engine = GameEngine()
    for entry in logger.turns:
        if branch.game_over:
            break
        t, recorded = entry["turn"], entry["actions"]
        actions = {}
        for lab in branch.labs:
            if lab.id == player_id and t == branch_turn:
                actions[lab.id] = new_action
            else:
                a = recorded.get(lab.id)
                actions[lab.id] = Action.from_dict(a) if a else Action()
        branch, _ = engine.step(branch, actions)
    return branch.outcome or {}


def _counterfactuals_resim(logger, state, player, player_id):
    """Pick a few decision points, re-simulate each with one choice changed, and
    report whether the outcome actually FLIPS (§10d legible counterfactuals — the
    real thing, not a heuristic string). Bounded to a handful of branches."""
    from backend_v1.engine.actions import Action
    out = []
    log = logger.turns
    def player_act(t):
        return dict(log[t - 1]["actions"].get(player_id, {})) if t - 1 < len(log) else None

    def describe(base_outcome, branch_outcome):
        be, bo = base_outcome.get("existential"), branch_outcome.get("existential")
        if be and not bo:
            return "would have AVOIDED the existential loss"
        if be and bo:
            return "still ends existentially (this choice alone wasn't enough)"
        di = branch_outcome.get("net_impact", 0) - base_outcome.get("net_impact", 0)
        if abs(di) >= 5:
            return f"net impact {'improves' if di > 0 else 'worsens'} by {abs(di):.0f}"
        return "barely changes the outcome"

    base = state.outcome or {}
    candidates = []   # (turn, modified_action, label)

    # (a) the last release before the end — hold it instead of shipping
    releases = [t["turn"] for t in log if t["actions"].get(player_id, {}).get("release")]
    if releases:
        rt = releases[-1]
        a = player_act(rt); a["release"] = False
        candidates.append((rt, Action.from_dict(a),
                           f"holding the model you shipped on turn {rt} (not releasing)"))

    # (b) the worst capability-mode post-train -> run it as a safety round instead
    cap_rounds = [t["turn"] for t in log
                  if (t["actions"].get(player_id, {}).get("post_train") or {}).get("mode")
                  == "capability"]
    if cap_rounds:
        ct = cap_rounds[len(cap_rounds) // 2]
        a = player_act(ct); a["post_train"] = {"mode": "safety"}
        candidates.append((ct, Action.from_dict(a),
                           f"running turn {ct}'s capability-mode round as a safety round"))

    # (c) the highest-assist dirty research start -> redo it clean (assist 0)
    dirty = None
    for t in log:
        for sp in t["actions"].get(player_id, {}).get("start_projects", []):
            if sp.get("ai_assist", 0) > 0.5:
                dirty = (t["turn"], sp.get("project_id")); break
        if dirty:
            break
    if dirty:
        dt_, pid = dirty
        a = player_act(dt_)
        a["start_projects"] = [
            ({**sp, "ai_assist": 0.0} if sp.get("project_id") == pid else sp)
            for sp in a.get("start_projects", [])]
        candidates.append((dt_, Action.from_dict(a),
                           f"researching '{pid}' clean (no AI-assist) on turn {dt_}"))

    for branch_turn, new_action, label in candidates[:3]:
        bo = _resimulate(state, logger, player_id, branch_turn, new_action)
        out.append(f"Turn {branch_turn}: {label} — re-simulated: {describe(base, bo)}.")
    return out


def _counterfactuals(turns, state, player, player_id):
    """Legible decision points where a different choice plausibly changes the
    outcome (§10d: without these, even a true-trajectory reveal reads as
    'doomed regardless')."""
    cf = []
    consts = state.consts

    # 1. dirty research: nodes researched at high assist while the assistant was misaligned
    for nid, item in player.researched_advances.items():
        if item.contamination > 0.08:
            cf.append(f"Turn {item.completed_turn}: you researched '{nid}' with "
                      f"AI-assist {item.researched_with_assist:.0%} while your model's "
                      f"true goal-misalignment was high — hidden contamination "
                      f"{item.contamination:.2f} then fed every later training run. "
                      f"At low assist (or after a clean re-research) this channel "
                      f"closes.")

    # 2. never ran the sandbagging check while concealment was live
    ran_noise = any("noise_injection" in str(t["actions"].get(player_id, {}))
                    for t in turns)
    concealed = any(m.concealment > 0.25 for m in player.release_history)
    if concealed and not ran_noise:
        cf.append("You never ran the noise-injection sandbagging check. Your models "
                  "were suppressing dangerous-domain evals for part of the game; that "
                  "project is one of the few cheap instruments that could have shown it.")

    # 3. interp too late / never
    interp_turns = [t["turn"] for t in turns
                    if "interp_probes" in str(t["actions"].get(player_id, {}))]
    if not interp_turns:
        cf.append("You never ran mechanistic interpretability. Every other instrument "
                  "you used is gated by the model's own eval-awareness; interp is the "
                  "one that bypasses it.")

    # 4. released past a visible warning: any release while worry-relevant finding existed
    high_findings = [f for f in player.findings
                     if f.get("concern", 0) > 0.5 and f.get("evidence") != "null"]
    releases = [(t["turn"]) for t in turns
                if t["actions"].get(player_id, {}).get("release")]
    for rel_turn in releases:
        warned = [f for f in high_findings if f["turn"] < rel_turn]
        if warned:
            f = warned[-1]
            cf.append(f"Turn {rel_turn}: you released a model after a concern-"
                      f"{f['concern']:.2f} finding on {f.get('axis')} "
                      f"(turn {f['turn']}). Holding to remediate — or not shipping — "
                      f"was available.")
            break

    # 5. capability-mode post-training spree
    aggressive = sum(1 for t in turns
                     if (t["actions"].get(player_id, {}).get("post_train") or {})
                     .get("mode") == "capability")
    if aggressive >= 5:
        cf.append(f"You ran {aggressive} capability-mode post-training rounds; each "
                  f"carried elevated correlated-jump risk and minimal alignment "
                  f"shaping. Balanced/safety rounds trade speed for keeping the "
                  f"persona-flip dice in your pocket.")

    if not cf:
        cf.append("No single decisive misstep stands out: this loss was carried by "
                  "the world's margins. (That can happen on this difficulty — and is "
                  "part of the argument.)")
    return cf


def render_postmortem_text(pm) -> str:
    out = []
    o = pm["outcome"]
    out.append("=" * 72)
    out.append("POST-MORTEM — what was actually happening")
    out.append("=" * 72)
    out.append(o.get("headline", ""))
    out.append(o.get("detail", ""))
    if pm["voided_impact"]:
        v = pm["voided_impact"]
        out.append(f"\nPositive impact that was REAL and is now VOID: "
                   f"{v['positive_impact_that_was_real']}")
        out.append(v["note"])
    if pm["key_moments"]:
        out.append("\n--- The moments you couldn't see ---")
        for k in pm["key_moments"]:
            out.append(f"  turn {k['turn']:>3} | {k['model']} | {k['kind']}: "
                       f"{k['what_you_couldnt_see']}")
    # compact true-vs-measured table for the last model
    traj = pm["trajectories"]
    if traj:
        last_model = traj[-1]["model"]
        rows = [t for t in traj if t["model"] == last_model]
        out.append(f"\n--- True vs measured (model {last_model}) ---")
        out.append("  turn | true_goalmis meas_goalmis | true_decep meas_decep | conceal")
        for r in rows[-12:]:
            out.append(f"  {r['turn']:>4} |    {r['true_goal_misalignment']:.2f}    "
                       f"{r['measured_goal_misalignment']:.2f}     |   "
                       f"{r['true_deception']:.2f}    {r['measured_deception']:.2f}   |  "
                       f"{r['concealment']:.2f}")
    out.append("\n--- Where a different choice was available ---")
    for c in pm["counterfactuals"]:
        out.append(f"  • {c}")
    out.append("")
    return "\n".join(out)
