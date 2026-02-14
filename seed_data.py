from models import Base, Motion
from database import engine, SessionLocal

# This is a starter set — you'll expand this with the full MODAPTS library
MODAPTS_MOTIONS = [
    # MOVE motions
    {"code": "M1", "category": "move", "description": "Move object, very short distance",
     "body_region": "fingers", "mod_value": 1},
    {"code": "M2", "category": "move", "description": "Move object, short distance",
     "body_region": "hand", "mod_value": 2},
    {"code": "M3", "category": "move", "description": "Move object, medium distance",
     "body_region": "arm", "mod_value": 3},
    {"code": "M4", "category": "move", "description": "Move object, long distance",
     "body_region": "arm", "mod_value": 4},
    {"code": "M5", "category": "move", "description": "Move object, very long distance",
     "body_region": "full_arm", "mod_value": 5},

    # GET/GRASP motions
    {"code": "G0", "category": "get", "description": "Get object, contact grasp",
     "body_region": "fingers", "mod_value": 0},
    {"code": "G1", "category": "get", "description": "Get object, simple grasp",
     "body_region": "fingers", "mod_value": 1},
    {"code": "G3", "category": "get", "description": "Get object, complex grasp",
     "body_region": "hand", "mod_value": 3},

    # PUT motions
    {"code": "P0", "category": "put", "description": "Put object, loose placement",
     "body_region": "fingers", "mod_value": 0},
    {"code": "P2", "category": "put", "description": "Put object, approximate location",
     "body_region": "hand", "mod_value": 2},
    {"code": "P5", "category": "put", "description": "Put object, tight tolerance",
     "body_region": "hand", "mod_value": 5},

    # WALK
    {"code": "W5", "category": "walk", "description": "Walk 1 pace (step)",
     "body_region": "leg", "mod_value": 5},

    # BEND/SIT/STAND
    {"code": "B17", "category": "bend", "description": "Bend and arise",
     "body_region": "body", "mod_value": 17},
    {"code": "S30", "category": "sit", "description": "Sit down",
     "body_region": "body", "mod_value": 30},
    {"code": "ST30", "category": "stand", "description": "Stand up from sitting",
     "body_region": "body", "mod_value": 30},

    # EYE ACTIONS
    {"code": "E2", "category": "eye_action", "description": "Eye focus/shift",
     "body_region": "eyes", "mod_value": 2},
]

def seed_database():
    """Manual seed function (for local use)"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear existing data
    db.query(Motion).delete()

    # Insert motion codes
    for motion_data in MODAPTS_MOTIONS:
        motion = Motion(
            code=motion_data["code"],
            category=motion_data["category"],
            description=motion_data["description"],
            body_region=motion_data["body_region"],
            mod_value=motion_data["mod_value"],
            time_seconds=motion_data["mod_value"] * 0.129
        )
        db.add(motion)

    db.commit()
    print(f"✅ Seeded {len(MODAPTS_MOTIONS)} motion codes")
    db.close()

if __name__ == "__main__":
    seed_database()

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Clear existing data
    db.query(Motion).delete()

    # Insert motion codes
    for motion_data in MODAPTS_MOTIONS:
        motion = Motion(
            code=motion_data["code"],
            category=motion_data["category"],
            description=motion_data["description"],
            body_region=motion_data["body_region"],
            mod_value=motion_data["mod_value"],
            time_seconds=motion_data["mod_value"] * 0.129
        )
        db.add(motion)

    db.commit()
    print(f"✅ Seeded {len(MODAPTS_MOTIONS)} motion codes")
    db.close()

if __name__ == "__main__":
    seed_database()