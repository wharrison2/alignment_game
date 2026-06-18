"""Appeals + the court hierarchy (§10c). Margin of victory drives everything:
a knife-edge ruling is ripe for reversal; a blowout is near-unappealable.

  • P(appeal succeeds) ∝ (−original_margin) — close rulings get appealed.
  • P(gov appeals a loss) ∝ WTR — struck-while-WTR-decayed just dies; struck-while-
    WTR-high → the government appeals. Challenge TIMING matters.
  • Court hierarchy trial → circuit → SCOTUS. SCOTUS gated TWICE: a low P(cert) AND
    a higher win bar once heard (COURT_WIN_BAR in litigation resolution).
  • Stay pending appeal: fast freeze of the status quo while litigation continues.
  • Precedent updates constitutionality ∝ court level (SCOTUS near-permanent).
"""


def appeal_strength(margin, consts):
    """How ripe a ruling is for reversal: ∝ how CLOSE it was (small |margin|)."""
    return consts.APPEAL_MARGIN_K / (1.0 + abs(margin))


def maybe_appeal(sb, st, case, outcome, margin) -> bool:
    """The losing side may appeal a DECISIVE ruling (struck / fail). Escalates the
    court level (cert-gated at SCOTUS) and may freeze the status quo with a stay.
    Returns True if an appeal was taken (case stays open at a higher court)."""
    consts, world, rng = sb.consts, sb.world, sb.rng
    if case.court_level == "scotus":
        return False                      # terminal — SCOTUS settles it
    if outcome == "struck":
        loser = "defense"                 # the policy's side lost; gov may appeal ∝ WTR
        p = min(0.95, consts.GOV_APPEAL_WTR_K * world.wtr + appeal_strength(margin, consts))
    elif outcome == "fail":
        loser = "challenge"               # challengers lost a close one
        p = appeal_strength(margin, consts)
    else:
        return False                      # interlocutory outcomes aren't full appeals
    if not rng.roll(min(0.95, p)):
        return False

    nxt = "circuit" if case.court_level == "trial" else "scotus"
    if nxt == "scotus" and not rng.roll(consts.SCOTUS_CERT_P):
        return False                      # cert denied — the lower ruling stands

    case.court_level = nxt
    case.status = "appealed"
    case.appeal_by = loser
    # stay pending appeal: arrives fast, freezes the current state while it proceeds
    if rng.roll(min(0.9, consts.STAY_GRANT_MARGIN_K * appeal_strength(margin, consts) * 4.0)):
        case.stay_active = True
        # a stay on a struck policy freezes it BACK to active while the appeal runs
        if outcome == "struck" and st.stage == "struck":
            st.stage = "active"
    return True


def apply_precedent(st, case, outcome, consts):
    """On final (un-appealed) resolution, precedent updates constitutionality ∝
    court level: a SCOTUS-upheld policy is nearly unchallengeable; a struck TYPE is
    nearly un-passable (handled as the policy staying struck)."""
    mult = consts.COURT_PRECEDENT_MULT[case.court_level]
    if outcome == "fail":                 # upheld — entrench further by court weight
        st.constitutionality = min(1.0, st.constitutionality
                                   + consts.LIT_ENTRENCH_GAIN * mult)
    case.stay_active = False
