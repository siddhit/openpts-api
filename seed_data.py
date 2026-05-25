"""
seed_data.py — MODAPTS motion code library for OpenPTS.

Sources:
  - International MODAPTS Association (modapts.org)
  - Heyde & Fourie, "Modular Arrangement of Predetermined Time Standards" (ResearchGate)
  - IISE SWS division, "Applying MODAPTS Standards" (iise.org)
  - Eisbrenner Productivity Group, "About MODAPTS®"

1 MOD = 0.129 seconds (7.75 MODs/second).
"""

from models import Base, Motion
from database import engine, SessionLocal


MODAPTS_MOTIONS = [

    # ── MOVE (M) ────────────────────────────────────────────────────────────────
    # Object held and transported. Subscript = distance class (body part that moves).
    {"code": "M1", "category": "move",
     "description": "Move object — very short distance (finger length)",
     "body_region": "fingers", "mod_value": 1},

    {"code": "M2", "category": "move",
     "description": "Move object — short distance (hand length)",
     "body_region": "hand", "mod_value": 2},

    {"code": "M3", "category": "move",
     "description": "Move object — medium distance (forearm length)",
     "body_region": "arm", "mod_value": 3},

    {"code": "M4", "category": "move",
     "description": "Move object — long distance (upper-arm length)",
     "body_region": "arm", "mod_value": 4},

    {"code": "M5", "category": "move",
     "description": "Move object — very long distance (full arm extension)",
     "body_region": "full_arm", "mod_value": 5},

    # ── GET / GRASP (G) ─────────────────────────────────────────────────────────
    # Secure control of an object. Subscript reflects complexity of grasp.
    {"code": "G0", "category": "get",
     "description": "Get — contact grasp (no finger closure, object touches hand)",
     "body_region": "fingers", "mod_value": 0},

    {"code": "G1", "category": "get",
     "description": "Get — simple grasp (fingers close on easy-to-pick object)",
     "body_region": "fingers", "mod_value": 1},

    {"code": "G3", "category": "get",
     "description": "Get — complex grasp (object requires deliberate finger control: bulky, nested, or slippery)",
     "body_region": "hand", "mod_value": 3},

    # ── PUT / PLACE (P) ─────────────────────────────────────────────────────────
    # Release control of object at a target location. Subscript = precision required.
    {"code": "P0", "category": "put",
     "description": "Put — loose placement (drop or toss, no location control)",
     "body_region": "fingers", "mod_value": 0},

    {"code": "P2", "category": "put",
     "description": "Put — approximate placement (table surface, bin, pallet — ±25mm)",
     "body_region": "hand", "mod_value": 2},

    {"code": "P5", "category": "put",
     "description": "Put — tight-tolerance placement (fixture, hole, or mated part — ±2mm)",
     "body_region": "hand", "mod_value": 5},

    # ── REGRASP (R) ─────────────────────────────────────────────────────────────
    # Adjust finger position on an already-held object.
    {"code": "R2", "category": "get",
     "description": "Regrasp — adjust grip on held object (finger repositioning mid-carry)",
     "body_region": "hand", "mod_value": 2},

    # ── APPLY PRESSURE (A) ──────────────────────────────────────────────────────
    # Sustained force application — pressing a button, activating a lever, seating a part.
    {"code": "A4", "category": "put",
     "description": "Apply pressure — sustained force activation (button press, snap fit, lever)",
     "body_region": "fingers", "mod_value": 4},

    # ── WALK (W) ────────────────────────────────────────────────────────────────
    # One walking pace (single step). Multiply by number of paces.
    {"code": "W5", "category": "walk",
     "description": "Walk — one pace (step). Code once per step.",
     "body_region": "leg", "mod_value": 5},

    # ── FOOT (F) ────────────────────────────────────────────────────────────────
    # Foot pedal or foot-switch operation.
    {"code": "F3", "category": "walk",
     "description": "Foot motion — pedal or foot-switch operation",
     "body_region": "leg", "mod_value": 3},

    # ── BEND AND ARISE (B) ──────────────────────────────────────────────────────
    # Complete trunk flexion and return to upright. Includes the arise.
    {"code": "B17", "category": "bend",
     "description": "Bend and arise — trunk flexion to floor/low level and return to upright",
     "body_region": "body", "mod_value": 17},

    # ── SIT / STAND (S / ST) ────────────────────────────────────────────────────
    {"code": "S30", "category": "sit",
     "description": "Sit — lower body from standing to seated position",
     "body_region": "body", "mod_value": 30},

    {"code": "ST30", "category": "stand",
     "description": "Stand — rise from seated to standing position",
     "body_region": "body", "mod_value": 30},

    # ── EYE ACTION (E) ──────────────────────────────────────────────────────────
    # Deliberate eye movement to focus on a new target. Not blinking or incidental gaze.
    {"code": "E2", "category": "eye_action",
     "description": "Eye focus — deliberate shift of gaze to a new visual target",
     "body_region": "eyes", "mod_value": 2},
]


def seed_database():
    """Manual full-reseed (local development use only — clears existing data)."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(Motion).delete()
    for motion_data in MODAPTS_MOTIONS:
        db.add(Motion(
            code=motion_data["code"],
            category=motion_data["category"],
            description=motion_data["description"],
            body_region=motion_data["body_region"],
            mod_value=motion_data["mod_value"],
            time_seconds=motion_data["mod_value"] * 0.129,
        ))
    db.commit()
    print(f"✅ Seeded {len(MODAPTS_MOTIONS)} motion codes")
    db.close()


if __name__ == "__main__":
    seed_database()
