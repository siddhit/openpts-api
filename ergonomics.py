"""
ergonomics.py — MODAPTS ergonomic risk scoring for OpenPTS.

Computes a Repetitive Strain Index (RSI) for any MODAPTS motion sequence
using body-region strain weights inspired by NIOSH lifting guidelines and
RULA/REBA literature. The RSI is not a clinical instrument — it is an
engineering signal for comparing task variants and flagging high-load elements.

Reference body-region risk ordering:
  Trunk flexion > Full-arm extension > Upper arm > Wrist/hand > Leg > Fingers > Eyes
"""

from typing import List, Dict, Any

# ── Strain weights by body_region ───────────────────────────────────────────────
# Higher = more musculoskeletal injury risk per MOD unit.
# Calibrated against RULA upper limb scores and NIOSH trunk-load guidelines.
STRAIN_WEIGHTS: Dict[str, float] = {
    "body":     3.5,   # Trunk flexion — #1 WMSD risk factor (L4/L5 disc loading)
    "full_arm": 2.5,   # Full arm extension — rotator cuff impingement risk
    "arm":      2.0,   # Upper-arm dominant — elbow/shoulder fatigue
    "hand":     1.5,   # Grip and wrist — carpal tunnel, tendonitis
    "leg":      1.2,   # Walking — low per-step, cumulative compression
    "fingers":  1.0,   # Precision motion, low mass
    "eyes":     0.5,   # Visual fatigue only — no musculoskeletal load
}

# RSI normalisation: this raw score maps to 10/10 (worst possible task).
# Calibrated so a continuous B17 sequence fills the scale.
RSI_MAX_REFERENCE = 150.0

# WMSD anatomical targets by body region (for reporting)
WMSD_TARGETS: Dict[str, str] = {
    "body":     "Lumbar spine (L4/L5 disc)",
    "full_arm": "Rotator cuff / shoulder complex",
    "arm":      "Elbow (lateral epicondyle)",
    "hand":     "Wrist / carpal tunnel",
    "leg":      "Knees, lower back",
    "fingers":  "Finger flexor tendons",
    "eyes":     "Visual fatigue",
}

# Human-readable risk notes per motion code
RISK_NOTES: Dict[str, str] = {
    "B17":  "Floor-level trunk flexion — high lumbar WMSD risk",
    "S30":  "Full sit-down — sustained hip and knee load",
    "ST30": "Full stand-up — hip and knee strain",
    "M5":   "Full-arm extension under load — shoulder impingement risk",
    "M4":   "Long arm motion — shoulder and elbow fatigue",
    "M3":   "Medium arm move — acceptable at low frequency",
    "G3":   "Complex grasp — sustained grip force required",
    "P5":   "Tight-tolerance placement — prolonged fine motor control",
    "W5":   "Loaded walking — cumulative fatigue multiplier applies",
    "E2":   "Eye focus/shift — visual fatigue at high frequency",
}


def _element_rsi_score(raw: float) -> float:
    """Normalise a raw RSI value to 0–10."""
    return round(min(10.0, (raw / RSI_MAX_REFERENCE) * 10), 1)


def _risk_level(score: float) -> str:
    if score >= 8.0:
        return "CRITICAL"
    if score >= 5.0:
        return "HIGH"
    if score >= 2.5:
        return "MODERATE"
    return "LOW"


def _overall_risk_category(total_rsi: float) -> str:
    if total_rsi >= 7.5:
        return "VERY HIGH"
    if total_rsi >= 5.0:
        return "HIGH"
    if total_rsi >= 2.5:
        return "MODERATE"
    return "LOW"


def score_sequence(motion_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute ergonomic risk for a MODAPTS sequence.

    Args:
        motion_elements: list of dicts, each with:
            code, category, body_region, mod_value (float), quantity (int)

    Returns:
        ergonomic_risk dict ready to embed in SequenceAnalysisResponse.
    """
    element_scores = []
    raw_scores = []

    for elem in motion_elements:
        region = elem["body_region"]
        weight = STRAIN_WEIGHTS.get(region, 1.0)
        raw = elem["mod_value"] * elem["quantity"] * weight
        score = _element_rsi_score(raw)
        raw_scores.append(raw)

        element_scores.append({
            "code":       elem["code"],
            "quantity":   elem["quantity"],
            "element_rsi": score,
            "risk_level": _risk_level(score),
            "note":       RISK_NOTES.get(elem["code"], f"{region} motion"),
        })

    total_raw = sum(raw_scores)
    total_rsi = _element_rsi_score(total_raw)

    # Primary risk factors = elements above MODERATE threshold
    primary_factors = []
    for elem, raw in zip(motion_elements, raw_scores):
        score = _element_rsi_score(raw)
        if score >= 2.5:
            region = elem["body_region"]
            primary_factors.append({
                "code":        elem["code"],
                "risk":        RISK_NOTES.get(elem["code"], f"{region} loading"),
                "body_region": region,
                "wmsd_target": WMSD_TARGETS.get(region, "Musculoskeletal system"),
                "severity":    _risk_level(score),
            })
    # Highest risk first
    primary_factors.sort(key=lambda x: -next(
        _element_rsi_score(r) for e, r in zip(motion_elements, raw_scores)
        if e["code"] == x["code"]
    ))

    recommendations = _generate_recommendations(motion_elements, element_scores)

    return {
        "repetitive_strain_index": total_rsi,
        "risk_category":           _overall_risk_category(total_rsi),
        "risk_scale":              "0–10 (low → very high)",
        "element_scores":          element_scores,
        "primary_risk_factors":    primary_factors,
        "recommendations":         recommendations,
    }


def _generate_recommendations(
    motion_elements: List[Dict[str, Any]],
    element_scores: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    recs = []
    priority = 1
    codes = {e["code"] for e in motion_elements}
    score_map = {s["code"]: s["element_rsi"] for s in element_scores}

    # B17 — highest priority: floor-level trunk flexion
    if "B17" in codes:
        recs.append({
            "priority": priority,
            "action":   "Eliminate B17 with mechanical assist",
            "detail":   (
                "Raise the source pallet or bin to waist height using a scissors lift, "
                "pneumatic tilter, or adjustable-height cart. Eliminates floor-level trunk "
                "flexion entirely. Expected to be the single highest-impact intervention."
            ),
            "expected_rsi_reduction": round(score_map.get("B17", 5.0) * 0.90, 1),
        })
        priority += 1
        recs.append({
            "priority": priority,
            "action":   "If B17 cannot be eliminated: require knee-bend technique",
            "detail":   (
                "Retrain the task as S30 (kneel) + M5 (lift) rather than B17 (back-bend). "
                "Knee-bend lifts distribute load through the legs, significantly reducing "
                "L4/L5 disc compression."
            ),
            "expected_rsi_reduction": round(score_map.get("B17", 5.0) * 0.40, 1),
        })
        priority += 1

    # Loaded walking — 4+ paces
    walk_qty = sum(e["quantity"] for e in motion_elements if e["code"] == "W5")
    if walk_qty >= 4:
        recs.append({
            "priority": priority,
            "action":   "Replace loaded walking with roller conveyor or pallet jack",
            "detail":   (
                f"{walk_qty} loaded walk paces ({walk_qty * 0.645:.2f}s) add cumulative "
                "compression to knees and lower back. A roller conveyor or pallet jack "
                "reduces this to a single P2 push motion."
            ),
            "expected_rsi_reduction": round(score_map.get("W5", 1.5) * 0.70, 1),
        })
        priority += 1

    # M5 — full-arm extension under load
    if "M5" in codes:
        recs.append({
            "priority": priority,
            "action":   "Split M5 lift into two stages via intermediate shelf",
            "detail":   (
                "Floor-to-chest (M5) can be split into floor-to-waist (M3) + "
                "waist-to-chest (M2) using a mid-height shelf. Reduces peak shoulder "
                "moment arm and rotator cuff load."
            ),
            "expected_rsi_reduction": round(score_map.get("M5", 2.5) * 0.50, 1),
        })
        priority += 1

    # P5 — tight tolerance placement
    if "P5" in codes:
        recs.append({
            "priority": priority,
            "action":   "Use locating fixture to reduce P5 to P2",
            "detail":   (
                "Tight-tolerance placement (P5, 5 MODs) demands prolonged fine-motor control. "
                "A well-designed locating fixture or chamfered entry guides the part, "
                "reducing placement to P2 (2 MODs) and cutting sustained grip time."
            ),
            "expected_rsi_reduction": round(score_map.get("P5", 2.0) * 0.60, 1),
        })
        priority += 1

    # G3 — complex grasp at high frequency
    if "G3" in codes and score_map.get("G3", 0) >= 2.5:
        recs.append({
            "priority": priority,
            "action":   "Redesign part presentation to allow G1 simple grasp",
            "detail":   (
                "G3 (complex grasp, 3 MODs) indicates the part is difficult to pick due to "
                "orientation, surface, or crowding. A part-presentation tray or parts feeder "
                "oriented for one-handed pickup reduces this to G1 (1 MOD)."
            ),
            "expected_rsi_reduction": round(score_map.get("G3", 1.0) * 0.50, 1),
        })
        priority += 1

    if not recs:
        recs.append({
            "priority": 1,
            "action":   "Maintain current method — ergonomic risk is acceptable",
            "detail":   (
                "No high-risk motion elements detected. Continue monitoring for "
                "cumulative repetition effects at high production volumes."
            ),
            "expected_rsi_reduction": 0.0,
        })

    return recs
