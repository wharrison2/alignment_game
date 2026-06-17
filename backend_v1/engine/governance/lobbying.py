"""Lobbying (§10c, DECIDED v1): per-policy stance for/against/abstain, binary,
no cost, re-set each turn. Weight = market cap. Rivals lobby by race position.

Regulatory capture falls out: lobbying power and the thing-to-be-regulated are
the same quantity.
"""


def resolve_rival_stances(lab, labs, policy_defs):
    """Leaders lobby against regulation, trailers for it, modulated by
    recklessness (a reckless trailer still dislikes rules)."""
    ranked = sorted(labs, key=lambda l: l.market_cap, reverse=True)
    position = ranked.index(lab) / max(1, len(ranked) - 1)   # 0 = leader
    stances = {}
    for p in policy_defs:
        lean_for = position - 0.35 - 0.4 * lab.disposition.recklessness
        if p.id == "open_weights_restriction" and lab.disposition.open_weights_ideology:
            stances[p.id] = -1
            continue
        stances[p.id] = 1 if lean_for > 0.1 else (-1 if lean_for < -0.1 else 0)
    return stances


def lobby_term(labs, policy_id, lobby_weight):
    total_cap = sum(l.market_cap for l in labs) or 1.0
    s = sum(l.lobby_stances.get(policy_id, 0) * l.market_cap for l in labs)
    return lobby_weight * s / total_cap
