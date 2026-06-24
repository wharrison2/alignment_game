"""Player-facing AUTHORED content, centralized in one place (i18n-ready).

This is the backend half of the "all strings named and in one file" deliverable
(FIX_ITEMS.md). A translator should be able to find every player-facing string by
its name in a known location WITHOUT reading engine logic.

Scope of THIS file: the loose inline display strings that previously sat in engine
code — the default player lab name/ticker and the rival roster names. These are
AUTHORED CONTENT (they appear in the legend, panels, and attribution logs), not
hidden/firewalled state, so centralizing them changes nothing about behavior: the
VALUES are identical to what the engine used before, only their SOURCE moved here.

What is NOT duplicated into this file, and why:
  • The §7c warning catalog already lives as one named DATA table in
    backend_v1/engine/observation/warnings.py (CATALOG: id -> {line, why, paper}).
  • The capability/safety advance copy already lives as named dataclass rows
    (what_it_does / risk_blurb / name) in
    backend_v1/engine/research/capabilities/capabilities_research_item.py and
    backend_v1/engine/research/safety/safety_advance_item.py.
  Those catalogs ARE their own strings tables — each player-facing string is
  already a named field on a named row in a single file, discoverable by a
  translator. Copying them into a second table would be pointless indirection
  (and would risk the two copies drifting), which FIX_ITEMS / the task explicitly
  warns against. They are referenced in place; this module is the index pointing
  to them.

Determinism note: the rival names feed attribution logs, so their VALUES are kept
byte-identical to the previous inline list — same names, same order — and the
default lab name/ticker match game.py's prior literals. The golden master must not
move because of this refactor.
"""

# ── Default player-lab identity (was inline in engine/game.py) ────────────────
# Used when the player supplies no name/ticker (or supplies all-control input).
DEFAULT_PLAYER_LAB_NAME = "Your Lab"
DEFAULT_PLAYER_TICKER = "YOU"

# ── Rival roster (was inline in engine/game.py) ───────────────────────────────
# Public, legible lab identities for the AI rivals. Order is load-bearing for
# determinism: rival{i+1} draws name RIVAL_LAB_NAMES[i % len]. Keep names/order
# identical so attribution logs and the golden master are unchanged.
RIVAL_LAB_NAMES = ["Mistreal", "OpenBrain", "Anthropos", "DeepThink", "Cypher"]
