from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from contextlib import asynccontextmanager
import models
from database import get_db, engine
from pydantic import BaseModel

# Create tables
models.Base.metadata.create_all(bind=engine)
# Auto-seed function
def seed_if_empty():
    """Seed the database if it's empty (for first deploy)"""
    from database import SessionLocal
    
    db = SessionLocal()
    
    # Check if already seeded
    motion_count = db.query(models.Motion).count()
    if motion_count > 0:
        print(f"✅ Database already has {motion_count} motions - skipping seed")
        db.close()
        return
    
    # Import seed data
    from seed_data import MODAPTS_MOTIONS
    
    print("🌱 Seeding database with motion codes...")
    
    for motion_data in MODAPTS_MOTIONS:
        motion = models.Motion(
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: runs when app starts
    seed_if_empty()
    yield
    # Shutdown: runs when app stops (put cleanup code here if needed)

app = FastAPI(
    title="OpenPTS API",
    description="Open Predetermined Time Standards - REST API for industrial time study calculations",
    version="0.1.0",
    lifespan=lifespan
)

#Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response/Request models
class MotionInput(BaseModel):
    code: str
    quantity: int = 1

class CreateStudyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    motions: List[MotionInput]

class MotionResponse(BaseModel):
    id: int
    code: str
    category: str
    description: str
    body_region: str
    mod_value: float
    time_seconds: float

    class Config:
        from_attributes = True

class StudyResult(BaseModel):
    study_id: int
    name: str
    total_motions: int
    total_mods: float
    base_time_seconds: float
    allowances_pct: float
    standard_time_seconds: float
    units_per_hour: int


@app.get("/")
def read_root():
    return {
        "message":"Welcome to OpenPTS API",
        "docs_url":"/docs",
        "version":"0.1.0"
    }


@app.get("/api/v1/motions", response_model=List[MotionResponse])
def get_all_motions(db: Session = Depends(get_db)):
    """
   Get all available motion codes
    """
    motions = db.query(models.Motion).all()
    return motions

@app.get("/api/v1/motions/{code}", response_model=MotionResponse)
def get_motion_by_code(code: str, db: Session = Depends(get_db)):
    """
    Get details for a specific motion code (e.g. M3, G1, P2)
    """
    motion = db.query(models.Motion).filter(models.Motion.code == code.upper()).first()
    if not motion:
        raise HTTPException(status_code=404, detail=f"Motion code '{code}' not found")
    return motion

