# OpenPTS

> Open Predetermined Time Standards — video-to-MODAPTS motion analysis with a REST API

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Live demo + docs:** https://openpts-api-w79z.vercel.app  
**Swagger UI:** https://openpts-api-w79z.vercel.app/docs

---

## What is OpenPTS?

OpenPTS is an open-source framework that converts video of a manual task into a structured MODAPTS annotation: motion codes, standard times, body-region breakdown, and an ergonomic Repetitive Strain Index.

**Pipeline:**

```
Video → MediaPipe Pose (33 landmarks) → Sliding-window classifier → MODAPTS codes → /sequence/analyze → Standard time + RSI
```

The demo runs MediaPipe entirely in the browser — no upload required. The REST API handles time-study calculations and ergonomic scoring for any MODAPTS sequence.

---

## What is MODAPTS?

MODAPTS (MODular Arrangement of Predetermined Time Standards) is a work measurement system used in manufacturing and logistics for over 50 years. Every observable human motion is assigned a code and a time value in **MODs** (1 MOD = 0.129 s).

| Family | Codes | Body region |
|--------|-------|-------------|
| Move | M1 – M5 | Fingers → full arm |
| Get / grasp | G0, G1, G3 | Fingers / hand |
| Put / place | P0, P2, P5 | Fingers / hand |
| Walk | W5 (per step) | Leg |
| Bend & arise | B17 | Full body |
| Sit / stand | S30, ST30 | Full body |
| Eye action | E2 | Eyes |

MODAPTS® is a registered trademark of the International MODAPTS Association. OpenPTS is an independent open-source implementation and is not affiliated with or endorsed by the IMA. For official training and certification visit [modapts.org](https://modapts.org).

---

## REST API

Base URL: `https://openpts-api-w79z.vercel.app`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/motions` | Full motion library (filterable by `body_region`, `category`) |
| `GET` | `/api/v1/motions/{code}` | Single code detail |
| `POST` | `/api/v1/sequence/analyze` | **Primary endpoint** — standard time, units/hour, ergonomic risk profile |
| `POST` | `/api/v1/classify` | Classify a MediaPipe pose-keypoint sequence into a MODAPTS code |

Full interactive docs at `/docs`.

### GET /api/v1/motions/{code}

```bash
curl https://openpts-api-w79z.vercel.app/api/v1/motions/B17
```

```json
{
  "code": "B17",
  "category": "bend",
  "body_region": "body",
  "mod_value": 17,
  "time_seconds": 2.193
}
```

### POST /api/v1/sequence/analyze

```bash
curl -X POST https://openpts-api-w79z.vercel.app/api/v1/sequence/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Delivery unload — van to ground",
    "allowances_pct": 15,
    "motions": [
      {"code": "B17", "quantity": 3},
      {"code": "W5",  "quantity": 4},
      {"code": "G3",  "quantity": 2},
      {"code": "M5",  "quantity": 2},
      {"code": "P2",  "quantity": 3}
    ]
  }'
```

```json
{
  "total_mods": 88,
  "base_time_seconds": 11.352,
  "standard_time_seconds": 13.055,
  "units_per_hour": 275,
  "breakdown_by_body_region": {
    "body":     {"total_mods": 51, "pct_of_task": 57.9},
    "leg":      {"total_mods": 20, "pct_of_task": 22.7},
    "hand":     {"total_mods": 10, "pct_of_task": 11.4},
    "full_arm": {"total_mods": 10, "pct_of_task": 11.4}
  },
  "ergonomic_risk": {
    "repetitive_strain_index": 8.9,
    "risk_category": "VERY HIGH",
    "recommendations": [...]
  }
}
```

### POST /api/v1/classify

Submit a sequence of MediaPipe 33-point pose frames; receive a predicted MODAPTS code with confidence score and classification reasoning.

```bash
curl -X POST https://openpts-api-w79z.vercel.app/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "landmark_format": "mediapipe_33",
    "fps": 30,
    "active_side": "bilateral",
    "frames": [ /* 20–90 frames */ ]
  }'
```

```json
{
  "predicted_code": "B17",
  "confidence": 0.97,
  "mod_value": 17,
  "body_region": "body",
  "classification_reasoning": "Trunk bend detected via gap_dominant: shoulder/hip gap ranged 49.0% of frame height...",
  "downstream_suggestion": {
    "likely_next_code": "G3",
    "reason": "Wrists at low position after arise — complex grasp expected next"
  }
}
```

---

## Video Analysis Pipeline

### Server-side (Python — any video)

```bash
# Install dependencies
pip install mediapipe opencv-python

# Analyze with auto-segmentation (works for any video)
python mediapipe_extract.py my_task.mp4 --auto --output demo/annotations.json

# Analyze with a custom task definition
python mediapipe_extract.py my_task.mp4 --task my_task.json --output demo/annotations.json
```

`--auto` uses a sliding-window mode detector: each frame is labelled as bend / walk / arm using a 1-second window of pose context, then consecutive same-mode frames are grouped into segments. This handles continuous manual labour tasks where the worker never comes to a complete stop between motions.

**Task JSON format** (`--task`):
```json
[
  {"code": "B17", "qty": 1, "label": "Bend to floor",  "cat": "bend", "region": "body",     "mv": 17, "mods": 17},
  {"code": "G3",  "qty": 1, "label": "Grasp box",      "cat": "get",  "region": "hand",     "mv": 3,  "mods": 3},
  {"code": "M5",  "qty": 1, "label": "Lift to chest",  "cat": "move", "region": "full_arm", "mv": 5,  "mods": 5},
  {"code": "P2",  "qty": 1, "label": "Place on table", "cat": "put",  "region": "hand",     "mv": 2,  "mods": 2}
]
```

### Browser-side (JavaScript — no server needed)

Drop a video on the demo page. `@mediapipe/tasks-vision` runs pose detection in-browser at 10 fps, the JS classifier applies the same sliding-window mode logic, and results are shown live during playback.

---

## Ergonomic Risk Index (RSI)

Each motion code carries a strain weight based on the body region involved:

| Region | Weight | Example codes |
|--------|--------|---------------|
| Full body | 3.5 | B17, S30, ST30 |
| Full arm | 2.5 | M5, W5 |
| Arm | 2.0 | M4, M3 |
| Hand / wrist | 1.5 | M2, G3, P2 |
| Leg | 1.2 | W5 (deprecated — use Full arm row above) |
| Fingers | 1.0 | G0, G1, M1 |
| Eyes | 0.5 | E2 |

RSI = min(10, Σ(MODs × qty × weight) / 150 × 10)

- 0–3: Low risk
- 3–6: Moderate
- 6–10: High / Very High

RSI is an engineering signal inspired by RULA/REBA/NIOSH literature. It is not a clinical instrument.

---

## Local Development

```bash
git clone https://github.com/siddhit/openpts-api.git
cd openpts-api

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Start the API
uvicorn main:app --reload
# → http://localhost:8000/docs

# Run the demo locally (in a second terminal)
cd demo && python3 -m http.server 8080
# → http://localhost:8080
```

The database auto-seeds with motion codes on first startup.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI (Python 3.11+) |
| Database | SQLite (local) |
| ORM | SQLAlchemy |
| Pose estimation | MediaPipe Tasks Vision 0.10+ |
| CV processing | OpenCV |
| Deployment | Vercel (serverless) |
| Demo frontend | Vanilla JS + Tailwind CSS |
| API docs | Swagger UI / OpenAPI 3.0 |

---

## Use Cases

- **Line balancing** — calculate cycle times for assembly stations
- **Capacity planning** — estimate labour requirements before tooling is built
- **Ergonomic assessment** — identify high-strain motions for WMSD prevention
- **Digital twins** — feed standard times into simulation models
- **ERP integration** — auto-calculate labour standards for Bills of Materials
- **Lean manufacturing** — quantify non-value-added motions
- **Robot learning** — label demonstration video for imitation-learning pipelines via `/classify`

---

## References

- [About MODAPTS® — Eisbrenner Productivity Group](https://www.eisbrennerpg.com/about-modapts/)
- [MODAPTS: The Simple Language for Analyzing Work — SixSigma.us](https://www.6sigma.us/work-measurement/modapts-modular-arrangement-of-predetermined-time-standards/)
- [Incorporating motion analysis technology into MODAPTS — Applied Ergonomics, 2016](https://www.sciencedirect.com/science/article/abs/pii/S0169814116300142)
- [Integrating MODAPTS and AI for Work Measurement — INFORMS, 2025](https://pubsonline.informs.org/do/10.1287/LYTX.2025.04.10/full/)
- [MODAPTS movement codes — ResearchGate](https://www.researchgate.net/figure/MODAPTS-movement-codes_fig2_353073640)
- [Applying MODAPTS Standards — IISE (PDF)](https://www.iise.org/uploadedfiles/IIE/Community/Technical_Societies_and_Divisions/SWS/sws1102.pdf)
- [Ergonomics Analysis Using MODAPTS — Wiley AI Magazine](https://onlinelibrary.wiley.com/doi/full/10.1609/aimag.v26i3.1824)

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Author

**Sid Sanghavi**  
Licensed MODAPTS Practitioner · M.S. Industrial & Systems Engineering, Virginia Tech · Former Senior Assembly Systems Engineer, Ford Motor Company

[siddh.it](https://siddh.it) · [LinkedIn](https://linkedin.com/in/SiddhitSanghavi) · [GitHub](https://github.com/siddhit) · siddhits@gmail.com

---

**Version:** 0.2.0 · Active development

**Roadmap:**
- [x] Core MODAPTS motion library (17 codes, 7 families)
- [x] Time-study calculations with configurable allowances
- [x] Swagger / OpenAPI 3.0 interactive docs
- [x] Public deployment (Vercel)
- [x] Ergonomic risk scoring (RSI 0–10 with WMSD recommendations)
- [x] Pose-sequence classifier (geometric rules + visibility filtering)
- [x] Server-side video analysis pipeline (MediaPipe + auto-segmentation)
- [x] Browser-side MediaPipe analysis (no upload — runs in-browser)
- [x] Interactive demo site with skeleton overlay and live MODAPTS feed
- [ ] Complete motion library (30+ codes)
- [ ] PDF / Excel report export
- [ ] Supervised CV classifier (labeled training data required)
- [ ] MTM and MOST standards
