"""
IN-KluSo Signal Confidence Model
Version: 1.0.0
Author: Juan Camilo Echeverri / IN-KluSo Editorial Lab
Status: CANONICAL — all signal scoring runs against this model

=============================================================
MATHEMATICAL FOUNDATION
=============================================================

Signal Confidence Index (SCI):

    SCI = (S × w_s) + (L × w_l) + (M × w_m) + (T × w_t)

    Where:
        S  = Source Score       (0.0 – 1.0)
        L  = Lens Coverage Score (0.0 – 1.0)
        M  = Mechanism Clarity Score (normalized 0.0 – 1.0)
        T  = Territory Specificity Score (0.0 – 1.0)

    Global weights:
        w_s = 0.35  (source quality is load-bearing)
        w_l = 0.30  (three-lens coverage)
        w_m = 0.25  (causal chain clarity)
        w_t = 0.10  (territory tracability)

-------------------------------------------------------------
SOURCE SCORE (S)

    For n sources across tiers A, B, C:

        S = clip( Σ(count_tier × weight_tier × decay(i)) / threshold, 0, 1 )

    Tier weights (w_tier):
        Tier A (Primary):            1.00
        Tier B (Reputable Secondary): 0.60
        Tier C (Commentary/Color):    0.15

    Decay: each additional source of same tier adds 60% of previous
        decay(i) = 0.6^(i-1)   for i = 1,2,3,...

    Threshold normalization = 1.0 (one Tier A alone = score 1.0)

    Hard rule: if count_A == 0 and count_B < 2 → SCI capped at 0.55 (LOW ceiling)

-------------------------------------------------------------
LENS COVERAGE SCORE (L)

    Three lenses, division-specific weights:

        L = (E × w_E[div]) + (Sys × w_Sys[div]) + (B × w_B[div])

    Division weight matrices:
        Division    Epistemology  Systems  Behavioral
        ─────────   ────────────  ───────  ──────────
        CORE            0.40       0.40      0.20
        THRIVE          0.33       0.33      0.34
        AXIS            0.20       0.40      0.40
        FLOW            0.20       0.40      0.40
        GROUND          0.40       0.20      0.40

    Each lens scored 0.0–1.0:
        0.0 = not addressed
        0.5 = present but incomplete
        1.0 = fully addressed with evidence

-------------------------------------------------------------
MECHANISM CLARITY SCORE (M)

    Scored 1–5, normalized to 0.0–1.0 via (score - 1) / 4

    1 = No causal chain identified
    2 = Causal direction stated but not evidenced
    3 = Partial chain, gaps acknowledged
    4 = Full chain with partial evidence
    5 = Full chain, mechanism named, evidence complete

-------------------------------------------------------------
TERRITORY SPECIFICITY SCORE (T)

    T = sum of criteria met / 4

    Criteria:
        1. City/neighborhood named (not just "urban areas")
        2. Time window specified (month + year minimum)
        3. Actor or institution identified (vendor, city dept, company)
        4. Observable behavior documented (not inferred from pattern alone)

-------------------------------------------------------------
CONFIDENCE TIER OUTPUT

    SCI ≥ 0.80  →  HIGH       (publishable, fully verifiable)
    0.55 ≤ SCI < 0.80  →  MODERATE   (publishable, uncertainty disclosed)
    0.30 ≤ SCI < 0.55  →  LOW        (not publishable; flag for follow-up)
    SCI < 0.30  →  MINIMAL    (noise; archive only)

=============================================================
"""

from dataclasses import dataclass, field
from typing import Literal
import math

# ── Type aliases ────────────────────────────────────────────
Division = Literal["CORE", "THRIVE", "AXIS", "FLOW", "GROUND"]
ConfidenceTier = Literal["HIGH", "MODERATE", "LOW", "MINIMAL"]

# ── Constants ────────────────────────────────────────────────
GLOBAL_WEIGHTS = {
    "source":      0.35,
    "lens":        0.30,
    "mechanism":   0.25,
    "territory":   0.10,
}

TIER_WEIGHTS = {
    "A": 1.00,
    "B": 0.60,
    "C": 0.15,
}

LENS_WEIGHTS: dict[Division, dict[str, float]] = {
    "CORE":   {"epistemology": 0.40, "systems": 0.40, "behavioral": 0.20},
    "THRIVE": {"epistemology": 0.33, "systems": 0.33, "behavioral": 0.34},
    "AXIS":   {"epistemology": 0.20, "systems": 0.40, "behavioral": 0.40},
    "FLOW":   {"epistemology": 0.20, "systems": 0.40, "behavioral": 0.40},
    "GROUND": {"epistemology": 0.40, "systems": 0.20, "behavioral": 0.40},
}

# ── Input data structures ────────────────────────────────────

@dataclass
class SourceBundle:
    """Evidence sources for a signal."""
    tier_a: int = 0   # Primary sources (institutional, filings, primary docs)
    tier_b: int = 0   # Reputable secondary (major publications w/ primary citation)
    tier_c: int = 0   # Commentary (color only, never load-bearing)

@dataclass
class LensScores:
    """Three-lens analysis coverage, each 0.0–1.0."""
    epistemology: float = 0.0   # Knowability: sources, temporal markers, verifiability
    systems:      float = 0.0   # Incentives: capital, institutional, perverse outcomes
    behavioral:   float = 0.0   # Optimization: what people actually do vs. claim

@dataclass
class TerritorySpec:
    """Territory specificity criteria."""
    city_named:          bool = False   # City or neighborhood explicitly named
    time_window_set:     bool = False   # Month + year minimum
    actor_identified:    bool = False   # Vendor, institution, or company named
    behavior_documented: bool = False   # Observable behavior, not inferred pattern

@dataclass
class SignalInput:
    """Complete input for a signal confidence calculation."""
    signal_id:   str
    title:       str
    division:    Division
    sources:     SourceBundle
    lenses:      LensScores
    mechanism:   int          # 1–5 raw score
    territory:   TerritorySpec
    tags:        list[str] = field(default_factory=list)
    cluster:     str = ""

# ── Scoring functions ────────────────────────────────────────

def _source_score(sources: SourceBundle) -> tuple[float, bool]:
    """
    Compute source score S with decay for repeated same-tier sources.
    Returns (score, hard_cap_triggered).

    Hard cap: if no Tier A and fewer than 2 Tier B → cap SCI at 0.55
    """
    def tier_contribution(count: int, weight: float) -> float:
        total = 0.0
        for i in range(1, count + 1):
            total += weight * (0.6 ** (i - 1))
        return total

    raw = (
        tier_contribution(sources.tier_a, TIER_WEIGHTS["A"]) +
        tier_contribution(sources.tier_b, TIER_WEIGHTS["B"]) +
        tier_contribution(sources.tier_c, TIER_WEIGHTS["C"])
    )

    score = min(raw, 1.0)
    hard_cap = (sources.tier_a == 0 and sources.tier_b < 2)
    return score, hard_cap


def _lens_score(division: Division, lenses: LensScores) -> float:
    """Compute weighted lens coverage score L."""
    weights = LENS_WEIGHTS[division]
    return (
        lenses.epistemology * weights["epistemology"] +
        lenses.systems      * weights["systems"] +
        lenses.behavioral   * weights["behavioral"]
    )


def _mechanism_score(raw: int) -> float:
    """Normalize mechanism clarity 1–5 → 0.0–1.0."""
    raw = max(1, min(5, raw))
    return (raw - 1) / 4


def _territory_score(t: TerritorySpec) -> float:
    """Fraction of territory criteria met."""
    criteria = [t.city_named, t.time_window_set, t.actor_identified, t.behavior_documented]
    return sum(criteria) / len(criteria)


def _confidence_tier(sci: float) -> ConfidenceTier:
    if sci >= 0.80:   return "HIGH"
    if sci >= 0.55:   return "MODERATE"
    if sci >= 0.30:   return "LOW"
    return "MINIMAL"

# ── Main scoring engine ──────────────────────────────────────

@dataclass
class SignalResult:
    signal_id:     str
    title:         str
    division:      Division
    S:             float   # Source score
    L:             float   # Lens score
    M:             float   # Mechanism score
    T:             float   # Territory score
    SCI:           float   # Final Signal Confidence Index
    tier:          ConfidenceTier
    hard_cap:      bool    # True if source hard cap was applied
    publishable:   bool
    notes:         list[str]

    def report(self) -> str:
        lines = [
            f"\n{'═'*56}",
            f"  SIGNAL: {self.signal_id}",
            f"  {self.title}",
            f"{'─'*56}",
            f"  Division       : {self.division}",
            f"  Source Score   : {self.S:.3f}  (w=0.35 → {self.S*0.35:.3f})",
            f"  Lens Score     : {self.L:.3f}  (w=0.30 → {self.L*0.30:.3f})",
            f"  Mechanism Score: {self.M:.3f}  (w=0.25 → {self.M*0.25:.3f})",
            f"  Territory Score: {self.T:.3f}  (w=0.10 → {self.T*0.10:.3f})",
            f"{'─'*56}",
            f"  SCI            : {self.SCI:.4f}",
            f"  Tier           : {self.tier}",
            f"  Hard Cap       : {'YES — capped at 0.55' if self.hard_cap else 'No'}",
            f"  Publishable    : {'✓ YES' if self.publishable else '✗ NO — needs more evidence'}",
        ]
        if self.notes:
            lines.append(f"{'─'*56}")
            for n in self.notes:
                lines.append(f"  ⚠  {n}")
        lines.append(f"{'═'*56}\n")
        return "\n".join(lines)


def score_signal(inp: SignalInput) -> SignalResult:
    """Run full SCI calculation for a signal candidate."""
    notes = []

    S, hard_cap = _source_score(inp.sources)
    L = _lens_score(inp.division, inp.lenses)
    M = _mechanism_score(inp.mechanism)
    T = _territory_score(inp.territory)

    w = GLOBAL_WEIGHTS
    raw_sci = (S * w["source"]) + (L * w["lens"]) + (M * w["mechanism"]) + (T * w["territory"])

    # Apply hard cap
    if hard_cap:
        raw_sci = min(raw_sci, 0.55)
        notes.append("No Tier A source + <2 Tier B → SCI capped at 0.55 (MODERATE ceiling)")

    # Lens completeness warnings
    lw = LENS_WEIGHTS[inp.division]
    for lens, score in [("epistemology", inp.lenses.epistemology),
                         ("systems",      inp.lenses.systems),
                         ("behavioral",   inp.lenses.behavioral)]:
        if score == 0.0 and lw[lens] >= 0.33:
            notes.append(f"{lens.capitalize()} lens = 0 but has high weight ({lw[lens]}) in {inp.division}")

    # Mechanism warning
    if inp.mechanism <= 2:
        notes.append(f"Mechanism clarity = {inp.mechanism}/5 — causal chain not evidenced")

    tier = _confidence_tier(raw_sci)
    publishable = tier in ("HIGH", "MODERATE")

    return SignalResult(
        signal_id=inp.signal_id,
        title=inp.title,
        division=inp.division,
        S=S, L=L, M=M, T=T,
        SCI=raw_sci,
        tier=tier,
        hard_cap=hard_cap,
        publishable=publishable,
        notes=notes,
    )


# ── Cluster readiness check ──────────────────────────────────

def cluster_status(signals: list[SignalResult], cluster_name: str) -> str:
    """
    Doctrine 2026: Cluster requires ≥10 signals, ≥3 months coverage.
    This checks current signal count and publishable rate.
    """
    total     = len(signals)
    pub       = [s for s in signals if s.publishable]
    high      = [s for s in signals if s.tier == "HIGH"]
    moderate  = [s for s in signals if s.tier == "MODERATE"]

    lines = [
        f"\n{'═'*56}",
        f"  CLUSTER: {cluster_name}",
        f"{'─'*56}",
        f"  Total signals    : {total}",
        f"  Publishable      : {len(pub)} / {total}",
        f"  HIGH tier        : {len(high)}",
        f"  MODERATE tier    : {len(moderate)}",
        f"  Doctrine minimum : 10 signals",
        f"  Progress         : {'▓' * total}{'░' * max(0, 10-total)} {total}/10",
        f"  Status           : {'ACTIVE — meets minimum' if total >= 10 else f'BUILDING — {10-total} more needed'}",
        f"{'═'*56}\n",
    ]
    return "\n".join(lines)


# ── Demo run ─────────────────────────────────────────────────

if __name__ == "__main__":

    # Signal NWA-GROUND-001: The New Booth in Bella Vista
    nwa_001 = SignalInput(
        signal_id = "NWA-GROUND-001",
        title     = "The New Booth in Bella Vista",
        division  = "GROUND",
        cluster   = "Farmers Market Disruption / US",
        sources   = SourceBundle(tier_a=0, tier_b=2, tier_c=1),
        lenses    = LensScores(
            epistemology = 0.70,   # Vendor count documented, time window set
            systems      = 0.50,   # Fee structure mentioned, incentive partial
            behavioral   = 0.90,   # Therapy-to-legitimacy behavior fully documented
        ),
        mechanism  = 3,            # Partial chain: social-infrastructure shift noted, not fully evidenced
        territory  = TerritorySpec(
            city_named          = True,   # Bella Vista, NWA
            time_window_set     = True,   # 2023–2025
            actor_identified    = True,   # Vendors described (therapists, life coaches)
            behavior_documented = True,   # Booth as office documented
        ),
        tags = [
            "farmers-market", "social-infrastructure", "behavioral-shift",
            "NWA", "GROUND", "vendor-economics", "legitimacy-signal"
        ],
    )

    result = score_signal(nwa_001)
    print(result.report())

    # Cluster status
    print(cluster_status([result], "Farmers Market Disruption / US"))

    print("Model version: IN-KluSo Signal Confidence Model v1.0.0")
    print("Next: Add signals NWA-GROUND-002 through NWA-GROUND-010 to reach doctrine minimum.\n")
