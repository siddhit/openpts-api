from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import models
from database import get_db, engine
from pydantic import BaseModel

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="OpenPTS API",
    description="Open Predetermined Time Standards - REST API for industrial time study calculations",
    version="0.1.0"
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

@app.post("/api/v1/studies", response_model=StudyResult)
def create_study(request: CreateStudyRequest, db: Session = Depends(get_db)):
    """Create a new time study with a sequence of motions"""

    # Create study
    study = models.Study(name=request.name, description=request.description)
    db.add(study)
    db.flush()  # Get the study ID

    total_mods = 0
    motion_count = 0

    # Add motions
    for idx, motion_input in enumerate(request.motions):
        # Look up motion
        motion = db.query(models.Motion).filter(
            models.Motion.code == motion_input.code.upper()
        ).first()

        if not motion:
            raise HTTPException(status_code=400, detail=f"Invalid motion code: {motion_input.code}")

        # Add to study
        study_motion = models.StudyMotion(
            study_id=study.id,
            motion_code=motion.code,
            sequence_order=idx,
            quantity=motion_input.quantity
        )
        db.add(study_motion)

        total_mods += motion.mod_value * motion_input.quantity
        motion_count += motion_input.quantity

    db.commit()

    # Calculate times
    base_time_seconds = total_mods * 0.129
    allowances_pct = 12.0  # 12% is a standard allowance (5% personal, 4% fatigue, 3% delay)
    standard_time_seconds = base_time_seconds * (1 + allowances_pct / 100)
    units_per_hour = int(3600 / standard_time_seconds) if standard_time_seconds > 0 else 0

    return StudyResult(
        study_id=study.id,
        name=study.name,
        total_motions=motion_count,
        total_mods=total_mods,
        base_time_seconds=round(base_time_seconds, 3),
        allowances_pct=allowances_pct,
        standard_time_seconds=round(standard_time_seconds, 3),
        units_per_hour=units_per_hour
    )

@app.get("/api/v1/studies/{study_id}", response_model=StudyResult)
def get_study(study_id: int, db: Session = Depends(get_db)):
    """Get results for a specific study"""
    study = db.query(models.Study).filter(models.Study.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    # Recalculate
    total_mods = 0
    motion_count = 0
    for sm in study.study_motions:
        motion = db.query(models.Motion).filter(models.Motion.code == sm.motion_code).first()
        if motion:
            total_mods += motion.mod_value * sm.quantity
            motion_count += sm.quantity

    base_time_seconds = total_mods * 0.129
    allowances_pct = 12.0
    standard_time_seconds = base_time_seconds * (1 + allowances_pct / 100)
    units_per_hour = int(3600 / standard_time_seconds) if standard_time_seconds > 0 else 0

    return StudyResult(
        study_id=study.id,
        name=study.name,
        total_motions=motion_count,
        total_mods=total_mods,
        base_time_seconds=round(base_time_seconds, 3),
        allowances_pct=allowances_pct,
        standard_time_seconds=round(standard_time_seconds, 3),
        units_per_hour=units_per_hour
    )