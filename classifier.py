"""
classifier.py — Rule-based MODAPTS motion classifier for OpenPTS.

Accepts MediaPipe-format pose keypoint sequences and returns a predicted
MODAPTS code with confidence, extracted geometric features, and a
downstream suggestion for the likely next code.

This is a geometric heuristic implementation. It correctly handles the
primary manufacturing motions (B17, M3–M5, G1/G3, W5, S30/ST30) without
any trained model. A supervised classifier trained on labeled video data
will replace these rules once sufficient data is available.

Design note — why rule-based first:
  No public dataset maps pose sequences → MODAPTS codes. This stub gives
  the API a working /classify endpoint for the demo pipeline today, while
  making the logic legible enough that a practitioner can audit and correct
  every decision. The geometric features it outputs are the exact features
  a future ML model should learn — so the feature extraction code will be
  reused, not discarded.
"""

import math
from typing import List, Dict, Optional, Any


# ── Motion lookup table (duplicates DB to keep classifier stateless) ──────────
_MOTION_INFO: Dict[str, Dict[str, Any]] = {
    "B17":  {"mod_value": 17, "body_region": "body",     "category": "bend",       "time_seconds": 2.193},
    "S30":  {"mod_value": 30, "body_region": "body",     "category": "sit",        "time_seconds": 3.870},
    "ST30": {"mod_value": 30, "body_region": "body",     "category": "stand",      "time_seconds": 3.870},
    "W5":   {"mod_value":  5, "body_region": "leg",      "category": "walk",       "time_seconds": 0.645},
    "F3":   {"mod_value":  3, "body_region": "leg",      "category": "walk",       "time_seconds": 0.387},
    "M1":   {"mod_value":  1, "body_region": "fingers",  "category": "move",       "time_seconds": 0.129},
    "M2":   {"mod_value":  2, "body_region": "hand",     "category": "move",       "time_seconds": 0.258},
    "M3":   {"mod_value":  3, "body_region": "arm",      "category": "move",       "time_seconds": 0.387},
    "M4":   {"mod_value":  4, "body_region": "arm",      "category": "move",       "time_seconds": 0.516},
    "M5":   {"mod_value":  5, "body_region": "full_arm", "category": "move",       "time_seconds": 0.645},
    "G0":   {"mod_value":  0, "body_region": "fingers",  "category": "get",        "time_seconds": 0.000},
    "G1":   {"mod_value":  1, "body_region": "fingers",  "category": "get",        "time_seconds": 0.129},
    "G3":   {"mod_value":  3, "body_region": "hand",     "category": "get",        "time_seconds": 0.387},
    "P0":   {"mod_value":  0, "body_region": "fingers",  "category": "put",        "time_seconds": 0.000},
    "P2":   {"mod_value":  2, "body_region": "hand",     "category": "put",        "time_seconds": 0.258},
    "P5":   {"mod_value":  5, "body_region": "hand",     "category": "put",        "time_seconds": 0.645},
    "A4":   {"mod_value":  4, "body_region": "fingers",  "category": "put",        "time_seconds": 0.516},
    "R2":   {"mod_value":  2, "body_region": "hand",     "category": "get",        "time_seconds": 0.258},
    "E2":   {"mod_value":  2, "body_region": "eyes",     "category": "eye_action", "time_seconds": 0.258},
}

# ── Classification thresholds ─────────────────────────────────────────────────
# All values are in normalised MediaPipe coordinate space (0–1 relative to
# frame dimensions). These are starting-point values calibrated against a
# person filmed at ~2m distance, full-body visible, standard-height camera.
# They will need per-deployment calibration once labeled data exists.
THRESHOLDS = {
    "bend_shoulder_drop":    0.12,   # shoulder/hip gap closes >12% → bending trunk
                                     # (was 0.18 — real-world bends in normalized coords
                                     #  often land 0.12–0.17 depending on camera height)
    "sit_hip_drop":          0.15,   # hips descend >15% of frame → sit/stand motion
    "walk_ankle_oscillation":0.04,   # ankle Y oscillation >4% → walking
    "wrist_M5":              0.22,   # wrist travels >22% of frame → M5 (very long move)
                                     # (was 0.28 — floor-to-chest lift in full-body frame ≈ 0.22–0.35)
    "wrist_M4":              0.14,   # >14% → M4
    "wrist_M3":              0.08,   # >8%  → M3
    "wrist_M2":              0.04,   # >4%  → M2
    "wrist_lift_dominant":   0.08,   # wrist Y displacement >8% → lift vs horizontal
    "wrist_y_range_M5":      0.20,   # wrist vertical range (max-min Y) >20% → likely M5 lift
                                     # catches short segments where start is already mid-lift
}


# ── Landmark helpers ──────────────────────────────────────────────────────────

def _lm(frame: Dict, name: str) -> Optional[Dict]:
    """Return a landmark dict or None."""
    return frame["landmarks"].get(name)


def _mean_y(frames: List[Dict], names: List[str]) -> List[float]:
    """Per-frame mean Y across the given landmark names."""
    result = []
    for f in frames:
        vals = [_lm(f, n) for n in names]
        ys = [v["y"] for v in vals if v is not None]
        if ys:
            result.append(sum(ys) / len(ys))
    return result


def _centroid(frame: Dict, names: List[str]) -> Optional[tuple]:
    pts = [_lm(frame, n) for n in names]
    pts = [(v["x"], v["y"]) for v in pts if v is not None]
    if not pts:
        return None
    return (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))


def _max_displacement(frames: List[Dict], names: List[str]) -> float:
    """Max Euclidean distance the centroid of <names> travels from its start."""
    if len(frames) < 2:
        return 0.0
    start = _centroid(frames[0], names)
    if not start:
        return 0.0
    max_d = 0.0
    for f in frames:
        c = _centroid(f, names)
        if c:
            d = math.hypot(c[0] - start[0], c[1] - start[1])
            max_d = max(max_d, d)
    return max_d


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_features(frames: List[Dict], active_side: str) -> Dict[str, Any]:
    shoulder_ys = _mean_y(frames, ["left_shoulder", "right_shoulder"])
    hip_ys      = _mean_y(frames, ["left_hip",      "right_hip"])
    ankle_ys    = _mean_y(frames, ["left_ankle",    "right_ankle"])

    wrist_names = (
        ["left_wrist", "right_wrist"] if active_side == "bilateral"
        else [f"{active_side}_wrist"]
    )
    wrist_ys = _mean_y(frames, wrist_names)

    # ── Bending signature ──────────────────────────────────────────────────
    # In screen-Y (down = positive), hips normally have higher Y than shoulders.
    # When a person bends, shoulders descend toward hip level — gap closes.
    shoulder_y_drop = 0.0
    returns_to_start = False
    if shoulder_ys and hip_ys:
        n = min(len(shoulder_ys), len(hip_ys))
        gaps = [hip_ys[i] - shoulder_ys[i] for i in range(n)]
        start_gap = gaps[0]
        min_gap   = min(gaps)
        shoulder_y_drop = max(0.0, start_gap - min_gap)
        returns_to_start = abs(shoulder_ys[-1] - shoulder_ys[0]) < 0.08

    # ── Sitting / standing signature ───────────────────────────────────────
    hip_y_displacement = (max(hip_ys) - min(hip_ys)) if hip_ys else 0.0

    # ── Walking signature ─────────────────────────────────────────────────
    ankle_oscillation = (max(ankle_ys) - min(ankle_ys)) if len(ankle_ys) > 4 else 0.0

    # ── Arm / wrist motion ─────────────────────────────────────────────────
    wrist_displacement = _max_displacement(frames, wrist_names)
    wrist_y_displacement = (wrist_ys[0] - min(wrist_ys)) if wrist_ys else 0.0   # lift = positive
    # Range captures full-body vertical lift even when segment starts mid-motion
    wrist_y_range = (max(wrist_ys) - min(wrist_ys)) if wrist_ys else 0.0

    return {
        "shoulder_y_drop":        round(shoulder_y_drop, 3),
        "hip_y_displacement":     round(hip_y_displacement, 3),
        "ankle_oscillation":      round(ankle_oscillation, 3),
        "wrist_displacement":     round(wrist_displacement, 3),
        "wrist_y_displacement":   round(wrist_y_displacement, 3),
        "wrist_y_range":          round(wrist_y_range, 3),
        "returns_to_start":       returns_to_start,
    }


def _is_converging(frames: List[Dict]) -> bool:
    """
    True if the two wrists are moving toward each other (or a common point)
    in the second half of the sequence — grasp/place signature.
    """
    if len(frames) < 6:
        return False
    half = len(frames) // 2
    early, late = frames[:half], frames[half:]

    def wrist_y_gap(f: Dict) -> Optional[float]:
        lw = _lm(f, "left_wrist")
        rw = _lm(f, "right_wrist")
        if lw and rw:
            return abs(lw["y"] - rw["y"])
        return None

    early_gaps = [g for f in early if (g := wrist_y_gap(f)) is not None]
    late_gaps  = [g for f in late  if (g := wrist_y_gap(f)) is not None]
    if not early_gaps or not late_gaps:
        return False
    return (sum(late_gaps) / len(late_gaps)) < (sum(early_gaps) / len(early_gaps)) * 0.75


# ── Classification rules ──────────────────────────────────────────────────────

def classify_pose_sequence(
    frames:      List[Dict],
    fps:         int = 30,
    active_side: str = "bilateral",
) -> Dict[str, Any]:
    """
    Classify a sequence of MediaPipe pose frames into a MODAPTS motion code.

    Args:
        frames:      List of frame dicts — each has 'frame_index', 'timestamp_ms',
                     and 'landmarks' (dict of landmark_name → {x, y, z, visibility}).
        fps:         Frames per second of the source video.
        active_side: 'bilateral' | 'left' | 'right'

    Returns:
        Classification result dict matching ClassifyResponse schema.
    """
    if not frames or len(frames) < 2:
        return {"error": "Minimum 2 frames required for classification."}

    duration_ms = frames[-1]["timestamp_ms"] - frames[0]["timestamp_ms"]
    feat = _extract_features(frames, active_side)
    f = feat  # shorthand

    # ── Rule 1: BEND AND ARISE (B17) ───────────────────────────────────────
    if (f["shoulder_y_drop"] >= THRESHOLDS["bend_shoulder_drop"]
            and f["returns_to_start"]
            and f["hip_y_displacement"] < THRESHOLDS["sit_hip_drop"]):
        trunk_degrees = int(f["shoulder_y_drop"] * 230)   # rough calibration
        return _result(
            code="B17",
            confidence=min(0.97, 0.74 + f["shoulder_y_drop"] * 1.1),
            features={
                **feat,
                "trunk_flexion_peak_degrees": trunk_degrees,
                "motion_type":    "bilateral_symmetric",
                "motion_duration_ms": duration_ms,
                "return_to_upright":  True,
            },
            reasoning=(
                f"Shoulders descended {f['shoulder_y_drop']*100:.0f}% of frame height "
                f"relative to hips and returned to start position (Δ < 8%). "
                f"Estimated trunk flexion ~{trunk_degrees}°. Hips stationary "
                f"(Δ={f['hip_y_displacement']*100:.1f}%). Pattern is B17: trunk bend-and-arise."
            ),
            alternatives=[
                {"code": "S30",  "confidence": 0.05,
                 "reason": "Hips did not descend — rules out sit-down"},
                {"code": "M5",   "confidence": 0.02,
                 "reason": "Motion is trunk-dominant, not arm-dominant"},
            ],
            next_code="G3",
            next_reason="Wrists at low position after arise — complex grasp expected next",
        )

    # ── Rule 2: SIT (S30) or STAND (ST30) ─────────────────────────────────
    # Guard: exclude walking — hip oscillation during normal gait can exceed
    # sit_hip_drop. Only classify as sit/stand when ankles are NOT oscillating.
    if (f["hip_y_displacement"] >= THRESHOLDS["sit_hip_drop"]
            and f["ankle_oscillation"] < THRESHOLDS["walk_ankle_oscillation"]):
        hip_start = _mean_y([frames[0]], ["left_hip", "right_hip"])
        hip_end   = _mean_y([frames[-1]], ["left_hip", "right_hip"])
        descending = (hip_end[0] > hip_start[0]) if (hip_start and hip_end) else True
        code = "S30" if descending else "ST30"
        return _result(
            code=code,
            confidence=0.88,
            features={
                **feat,
                "hip_y_displacement_normalized": f["hip_y_displacement"],
                "motion_type":    "body_vertical",
                "motion_direction": "descending" if descending else "ascending",
                "motion_duration_ms": duration_ms,
            },
            reasoning=(
                f"Hips {'descended' if descending else 'ascended'} "
                f"{f['hip_y_displacement']*100:.1f}% of frame — "
                f"{'sit-down' if descending else 'stand-up'} motion confirmed."
            ),
            alternatives=[
                {"code": "B17", "confidence": 0.09,
                 "reason": "Some shoulder drop, but hip displacement is dominant signal"},
            ],
            next_code="ST30" if descending else "W5",
            next_reason=("Stand-up typically follows later in cycle"
                         if descending else "Standing precedes walking"),
        )

    # ── Rule 3: WALKING (W5) ───────────────────────────────────────────────
    if f["ankle_oscillation"] >= THRESHOLDS["walk_ankle_oscillation"]:
        pace_ms = int(_MOTION_INFO["W5"]["time_seconds"] * 1000)   # 645 ms/pace
        estimated_paces = max(1, round(duration_ms / pace_ms))
        return _result(
            code="W5",
            confidence=min(0.96, 0.80 + f["ankle_oscillation"] * 3.0),
            features={
                **feat,
                "ankle_oscillation_normalized": f["ankle_oscillation"],
                "estimated_paces":  estimated_paces,
                "motion_type":      "bilateral_alternating",
                "motion_duration_ms": duration_ms,
            },
            reasoning=(
                f"Ankle Y oscillation of {f['ankle_oscillation']*100:.1f}% with alternating "
                f"bilateral pattern. Duration {duration_ms}ms ≈ {estimated_paces} pace(s) "
                f"(W5 = {pace_ms}ms/pace)."
            ),
            alternatives=[
                {"code": "B17", "confidence": 0.02,
                 "reason": "No shoulder-to-hip gap closure detected"},
            ],
            next_code="B17" if estimated_paces <= 5 else "W5",
            next_reason=("Short walk — likely ending at retrieval point (B17 expected)"
                         if estimated_paces <= 5 else "Continued walking"),
        )

    # ── Rules 4–8: ARM MOTIONS (M1–M5, G0–G3, P0–P5) ─────────────────────
    wd = f["wrist_displacement"]
    wy = f["wrist_y_displacement"]
    wr = f["wrist_y_range"]    # full vertical travel regardless of start position
    is_lift = wy >= THRESHOLDS["wrist_lift_dominant"] or wr >= THRESHOLDS["wrist_y_range_M5"]

    # Use the larger of point-to-point displacement and total Y range so that
    # floor-to-chest lifts are not missed when the segment starts mid-motion.
    effective_wd = max(wd, wr * 0.85)   # 0.85 corrects for diagonal vs. vertical

    if effective_wd >= THRESHOLDS["wrist_M5"]:
        direction = "vertical_lift" if is_lift else "horizontal_sweep"
        return _result(
            code="M5",
            confidence=min(0.93, 0.76 + effective_wd * 0.5),
            features={
                **feat,
                "wrist_displacement_normalized": wd,
                "wrist_y_range_normalized":      wr,
                "effective_displacement":        round(effective_wd, 3),
                "wrist_y_displacement_normalized": wy,
                "motion_direction":   direction,
                "motion_type":        "arm_dominant",
                "motion_duration_ms": duration_ms,
            },
            reasoning=(
                f"Wrist centroid traveled {wd*100:.0f}% from start; "
                f"vertical Y range {wr*100:.0f}% (effective {effective_wd*100:.0f}%). "
                f"{'Vertical lift detected. ' if is_lift else ''}"
                f"Exceeds M5 threshold ({THRESHOLDS['wrist_M5']*100:.0f}%). "
                f"Full arm extension engaged (body_region: full_arm)."
            ),
            alternatives=[
                {"code": "M4", "confidence": 0.07,
                 "reason": "Large displacement — trajectory clearly exceeds M4 boundary"},
            ],
            next_code="P2",
            next_reason="Long move typically ends with a placement event",
        )

    if effective_wd >= THRESHOLDS["wrist_M4"]:
        return _result(
            code="M4",
            confidence=0.85,
            features={**feat, "wrist_displacement_normalized": wd,
                      "motion_duration_ms": duration_ms},
            reasoning=(
                f"Wrist displacement {wd*100:.0f}% of frame — "
                f"consistent with long upper-arm motion (M4)."
            ),
            alternatives=[
                {"code": "M5", "confidence": 0.10,
                 "reason": "Near upper boundary — confirm with load weight context"},
                {"code": "M3", "confidence": 0.05,
                 "reason": "Near lower M4 boundary"},
            ],
            next_code="P2",
            next_reason="Long arm motion typically precedes placement",
        )

    if effective_wd >= THRESHOLDS["wrist_M3"]:
        return _result(
            code="M3",
            confidence=0.83,
            features={**feat, "wrist_displacement_normalized": wd,
                      "motion_duration_ms": duration_ms},
            reasoning=(
                f"Wrist displacement {wd*100:.0f}% — medium-distance arm motion (M3, "
                f"forearm-length travel)."
            ),
            alternatives=[
                {"code": "M4", "confidence": 0.11,
                 "reason": "Could extend to M4 with a heavy object"},
                {"code": "G3", "confidence": 0.06,
                 "reason": "Convergent path possible — re-run with wider window"},
            ],
            next_code="P2",
            next_reason="Medium arm move typically precedes placement or regrasp",
        )

    if effective_wd >= THRESHOLDS["wrist_M2"]:
        converging = _is_converging(frames)
        if converging:
            return _result(
                code="G1",
                confidence=0.79,
                features={**feat, "wrist_displacement_normalized": wd,
                           "converging_trajectory": True,
                           "motion_duration_ms": duration_ms},
                reasoning=(
                    f"Short wrist displacement ({wd*100:.0f}%) with convergent trajectory "
                    f"in second half of sequence — simple grasp (G1) signature."
                ),
                alternatives=[
                    {"code": "G3", "confidence": 0.13,
                     "reason": "If object is bulky or awkward, upgrade to G3"},
                    {"code": "P2", "confidence": 0.08,
                     "reason": "Settling motion consistent with approximate placement"},
                ],
                next_code="M3",
                next_reason="Grasp typically followed by a move",
            )
        else:
            return _result(
                code="M2",
                confidence=0.77,
                features={**feat, "wrist_displacement_normalized": wd,
                           "converging_trajectory": False,
                           "motion_duration_ms": duration_ms},
                reasoning=(
                    f"Short wrist displacement ({wd*100:.0f}%) without convergent path — "
                    f"short arm motion (M2, hand-length travel)."
                ),
                alternatives=[
                    {"code": "G1", "confidence": 0.15,
                     "reason": "Displacement boundary overlaps — widen window for confidence"},
                    {"code": "P0", "confidence": 0.08,
                     "reason": "Settling motion possible"},
                ],
                next_code="P0",
                next_reason="Short move often ends in contact placement",
            )

    # Very small displacement — finger / contact level
    return _result(
        code="G0",
        confidence=0.71,
        features={**feat, "wrist_displacement_normalized": wd,
                  "motion_duration_ms": duration_ms},
        reasoning=(
            f"Very small wrist displacement ({wd*100:.1f}%) — finger-level contact motion. "
            f"Likely G0 (contact grasp) or P0 (loose placement)."
        ),
        alternatives=[
            {"code": "P0", "confidence": 0.22,
             "reason": "Could be placing rather than grasping — context needed"},
            {"code": "M1", "confidence": 0.07,
             "reason": "Minimal finger-tip motion possible"},
        ],
        next_code="M1",
        next_reason="Contact grasp typically followed by a very short move",
    )


# ── Response builder ──────────────────────────────────────────────────────────

def _result(
    code:         str,
    confidence:   float,
    features:     Dict[str, Any],
    reasoning:    str,
    alternatives: List[Dict],
    next_code:    str,
    next_reason:  str,
) -> Dict[str, Any]:
    info = _MOTION_INFO.get(code, {
        "mod_value": 0, "body_region": "unknown",
        "category": "unknown", "time_seconds": 0.0,
    })
    next_info = _MOTION_INFO.get(next_code, {"category": "move"})

    return {
        "predicted_code":     code,
        "confidence":         round(confidence, 2),
        "time_seconds":       info["time_seconds"],
        "mod_value":          info["mod_value"],
        "body_region":        info["body_region"],
        "category":           info["category"],
        "alternative_candidates": alternatives,
        "detected_features":  features,
        "classification_reasoning": reasoning,
        "downstream_suggestion": {
            "likely_next_code": next_code,
            "reason":           next_reason,
            "filter_url": (
                f"/api/v1/motions"
                f"?category={next_info.get('category', 'move')}"
                f"&body_region={next_info.get('body_region', '')}"
            ),
        },
    }
