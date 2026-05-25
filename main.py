"""
main.py — OpenPTS API v0.2.0

Open Predetermined Time Standards: REST API for MODAPTS-grounded time study
calculations, ergonomic risk scoring, and pose-sequence motion classification.

Endpoints:
  GET  /api/v1/motions                — full motion library, filterable
  GET  /api/v1/motions/{code}         — single motion code detail
  POST /api/v1/sequence/analyze       — full study: time + breakdown + ergonomic risk
  POST /api/v1/classify               — classify a pose keypoint sequence → MODAPTS code
"""

from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db, engine
from ergonomics import score_sequence
from classifier import classify_pose_sequence

# ── Database init ─────────────────────────────────────────────────────────────

models.Base.metadata.create_all(bind=engine)


def seed_if_empty():
    """
    On startup: seed any missing motion codes.
    Safe to call repeatedly — existing codes are never overwritten.
    """
    from database import SessionLocal
    from seed_data import MODAPTS_MOTIONS

    db = SessionLocal()
    existing_codes = {m.code for m in db.query(models.Motion).all()}
    new_motions = [m for m in MODAPTS_MOTIONS if m["code"] not in existing_codes]

    if not new_motions:
        print(f"✅ Database has {len(existing_codes)} motion codes — nothing to seed")
        db.close()
        return

    print(f"🌱 Adding {len(new_motions)} new motion code(s)...")
    for md in new_motions:
        db.add(models.Motion(
            code=md["code"],
            category=md["category"],
            description=md["description"],
            body_region=md["body_region"],
            mod_value=md["mod_value"],
            time_seconds=md["mod_value"] * 0.129,
        ))
    db.commit()
    print(f"✅ Now have {len(existing_codes) + len(new_motions)} motion codes")
    db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_if_empty()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenPTS API",
    description=(
        "Open Predetermined Time Standards — REST API for MODAPTS-based industrial "
        "time study calculations, ergonomic risk scoring (RSI), and pose-sequence "
        "motion classification for manufacturing robot learning pipelines."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class MotionResponse(BaseModel):
    id:           int
    code:         str
    category:     str
    description:  str
    body_region:  str
    mod_value:    float
    time_seconds: float

    class Config:
        from_attributes = True


class MotionInput(BaseModel):
    code:     str
    quantity: int = 1


class SequenceAnalyzeRequest(BaseModel):
    name:           str
    description:    Optional[str] = None
    allowances_pct: float = 15.0   # Standard automotive/manufacturing fatigue+delay
    motions:        List[MotionInput]


class SequenceElement(BaseModel):
    order:             int
    code:              str
    quantity:          int
    subtotal_mods:     float
    subtotal_seconds:  float
    category:          str
    body_region:       str


class RegionBreakdown(BaseModel):
    total_mods:   float
    pct_of_task:  float


class SequenceAnalysisResponse(BaseModel):
    name:                      str
    description:               Optional[str]
    total_mods:                float
    base_time_seconds:         float
    allowances_pct:            float
    standard_time_seconds:     float
    units_per_hour:            int
    sequence:                  List[SequenceElement]
    breakdown_by_body_region:  Dict[str, RegionBreakdown]
    breakdown_by_category:     Dict[str, RegionBreakdown]
    ergonomic_risk:            Dict[str, Any]


class Landmark(BaseModel):
    x:          float
    y:          float
    z:          float = 0.0
    visibility: float = 1.0


class PoseFrame(BaseModel):
    frame_index:  int
    timestamp_ms: int
    landmarks:    Dict[str, Landmark]


class ClassifyRequest(BaseModel):
    landmark_format: str  = "mediapipe_33"
    fps:             int  = 30
    active_side:     str  = "bilateral"   # bilateral | left | right
    context:         str  = "manufacturing_assembly"
    frames:          List[PoseFrame]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {
        "message": "Welcome to OpenPTS API",
        "version": "0.2.0",
        "docs_url": "/docs",
        "github":   "https://github.com/siddhit/openpts-api",
        "endpoints": {
            "motions":          "GET  /api/v1/motions[?body_region=arm&category=move]",
            "motion_by_code":   "GET  /api/v1/motions/{code}",
            "sequence_analyze": "POST /api/v1/sequence/analyze",
            "classify":         "POST /api/v1/classify",
        },
    }


@app.get("/api/v1/motions", response_model=List[MotionResponse])
def get_all_motions(
    body_region: Optional[str] = Query(
        None,
        description=(
            "Filter by body region. Partial match: 'arm' returns both 'arm' and 'full_arm'. "
            "Values: fingers, hand, arm, full_arm, leg, body, eyes."
        ),
    ),
    category: Optional[str] = Query(
        None,
        description=(
            "Filter by motion category. "
            "Values: move, get, put, walk, bend, sit, stand, eye_action."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Return all MODAPTS motion codes, with optional filtering.

    Typical CV pipeline use: call with `?body_region=arm` once the pose estimator
    has determined the arm is the dominant active segment, to narrow the candidate
    set before calling `/classify`.
    """
    query = db.query(models.Motion)
    if body_region:
        query = query.filter(models.Motion.body_region.contains(body_region.lower()))
    if category:
        query = query.filter(models.Motion.category == category.lower())
    return query.order_by(models.Motion.category, models.Motion.mod_value).all()


@app.get("/api/v1/motions/{code}", response_model=MotionResponse)
def get_motion_by_code(code: str, db: Session = Depends(get_db)):
    """
    Return details for a specific MODAPTS code (e.g. M3, G1, P2, B17).
    Codes are case-insensitive.
    """
    motion = db.query(models.Motion).filter(
        models.Motion.code == code.upper()
    ).first()
    if not motion:
        raise HTTPException(
            status_code=404,
            detail=f"Motion code '{code}' not found. GET /api/v1/motions to see all codes.",
        )
    return motion


@app.post("/api/v1/sequence/analyze", response_model=SequenceAnalysisResponse)
def analyze_sequence(
    request: SequenceAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze a complete MODAPTS motion sequence.

    Returns:
    - **Standard time** with configurable allowances (default 15%)
    - **Units per hour** (production rate)
    - **Per-element breakdown** with MODs, seconds, category, and body region
    - **Aggregate breakdowns** by body region and by category
    - **Ergonomic risk** — RSI score (0–10), risk category, per-element flags,
      primary WMSD risk factors, and prioritised engineering recommendations

    The `allowances_pct` field accepts any value; 15% is the standard automotive
    fatigue+personal+delay allowance. OSHA/NIOSH studies typically use 10–20%.
    """
    if not request.motions:
        raise HTTPException(status_code=400, detail="Motion list cannot be empty.")

    sequence_elements: List[SequenceElement] = []
    motion_data_for_ergonomics: List[Dict[str, Any]] = []
    total_mods = 0.0

    for order, item in enumerate(request.motions, start=1):
        code = item.code.upper()
        motion = db.query(models.Motion).filter(models.Motion.code == code).first()
        if not motion:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Motion code '{code}' not found. "
                    f"Call GET /api/v1/motions to see all available codes."
                ),
            )

        subtotal_mods    = motion.mod_value * item.quantity
        subtotal_seconds = round(subtotal_mods * 0.129, 4)
        total_mods      += subtotal_mods

        sequence_elements.append(SequenceElement(
            order            = order,
            code             = motion.code,
            quantity         = item.quantity,
            subtotal_mods    = subtotal_mods,
            subtotal_seconds = subtotal_seconds,
            category         = motion.category,
            body_region      = motion.body_region,
        ))
        motion_data_for_ergonomics.append({
            "code":        motion.code,
            "category":    motion.category,
            "body_region": motion.body_region,
            "mod_value":   motion.mod_value,
            "quantity":    item.quantity,
        })

    base_time     = round(total_mods * 0.129, 4)
    standard_time = round(base_time * (1 + request.allowances_pct / 100), 4)
    units_per_hour = int(3600 / standard_time) if standard_time > 0 else 0

    # Breakdowns
    region_totals:   Dict[str, float] = {}
    category_totals: Dict[str, float] = {}
    for el in sequence_elements:
        region_totals[el.body_region] = region_totals.get(el.body_region, 0.0) + el.subtotal_mods
        category_totals[el.category]  = category_totals.get(el.category,  0.0) + el.subtotal_mods

    breakdown_by_region = {
        region: RegionBreakdown(
            total_mods  = mods,
            pct_of_task = round(mods / total_mods * 100, 1) if total_mods else 0.0,
        )
        for region, mods in sorted(region_totals.items(), key=lambda x: -x[1])
    }
    breakdown_by_category = {
        cat: RegionBreakdown(
            total_mods  = mods,
            pct_of_task = round(mods / total_mods * 100, 1) if total_mods else 0.0,
        )
        for cat, mods in sorted(category_totals.items(), key=lambda x: -x[1])
    }

    ergonomic_risk = score_sequence(motion_data_for_ergonomics)

    return SequenceAnalysisResponse(
        name                     = request.name,
        description              = request.description,
        total_mods               = total_mods,
        base_time_seconds        = base_time,
        allowances_pct           = request.allowances_pct,
        standard_time_seconds    = standard_time,
        units_per_hour           = units_per_hour,
        sequence                 = sequence_elements,
        breakdown_by_body_region = breakdown_by_region,
        breakdown_by_category    = breakdown_by_category,
        ergonomic_risk           = ergonomic_risk,
    )


@app.post("/api/v1/classify")
def classify_motion(request: ClassifyRequest):
    """
    Classify a pose keypoint sequence into a MODAPTS motion code.

    **Input:** MediaPipe-format landmark data for a single motion segment
    (minimum 2 frames, recommended 20–90 frames at 30fps to cover one full motion element).

    **Output:** Predicted MODAPTS code, confidence (0–1), extracted geometric
    features, alternative candidates with ruled-out reasons, and a downstream
    suggestion for the likely next code in the sequence.

    **Current implementation:** Geometric rule-based heuristic classifier.
    Correctly handles B17, M3–M5, G1/G3, W5, S30/ST30, and contact motions
    without a trained model. A supervised classifier will replace these rules
    once labeled manufacturing video data is available.

    **Typical pipeline:** video → MediaPipe pose → segment by motion onset/offset
    → POST /api/v1/classify (one call per segment) → collect codes →
    POST /api/v1/sequence/analyze (one call per task cycle).
    """
    if len(request.frames) < 2:
        raise HTTPException(
            status_code=400,
            detail="Minimum 2 frames required for classification.",
        )

    # Convert Pydantic objects → plain dicts for the stateless classifier
    frames_raw = [
        {
            "frame_index":  f.frame_index,
            "timestamp_ms": f.timestamp_ms,
            "landmarks": {
                name: {"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility}
                for name, lm in f.landmarks.items()
            },
        }
        for f in request.frames
    ]

    result = classify_pose_sequence(
        frames      = frames_raw,
        fps         = request.fps,
        active_side = request.active_side,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result
