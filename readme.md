# OpenPTS API

> Open Predetermined Time Standards — A modern REST API for industrial time study calculations

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Live API:** https://your-app.onrender.com *(update with your Render URL)*
**API Docs:** https://your-app.onrender.com/docs *(update with your Render URL)*

## What is OpenPTS?

OpenPTS is the first open-source REST API for predetermined time standards calculations used in manufacturing and industrial engineering. It implements MODAPTS-compatible motion codes to help engineers calculate standard work times for assembly and manufacturing tasks.

## Why This Exists

Predetermined time standards like MODAPTS have been used in manufacturing for decades, but they've remained locked in proprietary desktop software and Excel spreadsheets. OpenPTS brings these calculations into the modern API era, making it easy to integrate time standards into:

- Manufacturing Execution Systems (MES)
- Enterprise Resource Planning (ERP) platforms
- Digital twin simulations
- Custom production planning tools
- AI-powered ergonomic assessment systems

## Features

✅ Complete library of MODAPTS motion codes
✅ Time study calculations with allowances
✅ Auto-generated interactive API documentation
✅ Open source and free to use
✅ RESTful JSON API

## Quick Start

### Get All Motion Codes
```bash
curl https://your-app.onrender.com/api/v1/motions
```

### Get a Specific Motion
```bash
curl https://your-app.onrender.com/api/v1/motions/M3
```

Returns:
```json
{
  "id": 3,
  "code": "M3",
  "category": "move",
  "description": "Move object, medium distance",
  "body_region": "arm",
  "mod_value": 3.0,
  "time_seconds": 0.387
}
```

### Create a Time Study
```bash
curl -X POST https://your-app.onrender.com/api/v1/studies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pick and Place Task",
    "description": "Simple assembly operation",
    "motions": [
      {"code": "M3", "quantity": 1},
      {"code": "G1", "quantity": 1},
      {"code": "P2", "quantity": 1}
    ]
  }'
```

Returns:
```json
{
  "study_id": 1,
  "name": "Pick and Place Task",
  "total_motions": 3,
  "total_mods": 6.0,
  "base_time_seconds": 0.774,
  "allowances_pct": 12.0,
  "standard_time_seconds": 0.867,
  "units_per_hour": 4152
}
```

## API Documentation

Full interactive documentation available at your deployed URL: `/docs`

The API follows OpenAPI 3.0 specification with Swagger UI for testing.

## Understanding MODAPTS

MODAPTS (MODular Arrangement of Predetermined Time Standards) is a work measurement system that assigns time values to basic human movements. Each movement is coded with a letter (representing the motion type) and number (representing the time in MODs).

**Key Concepts:**
- **1 MOD = 0.129 seconds** (7.75 MODs per second)
- Motion codes like `M3` (move medium distance), `G1` (simple grasp), `P2` (place approximately)
- Body-focused: codes represent which body part moves, not just object distance
- Ideal for ergonomic analysis since it tracks repetitive motions by body region

**Common Motion Categories:**
- **M** = Move (M1-M5)
- **G** = Get/Grasp (G0, G1, G3)
- **P** = Put/Place (P0, P2, P5)
- **W** = Walk (W5 per step)
- **B** = Bend (B17)
- **S/ST** = Sit/Stand (S30, ST30)
- **E** = Eye action (E2)

## Use Cases

- **Line Balancing**: Calculate cycle times for assembly stations to optimize production flow
- **Capacity Planning**: Estimate labor requirements for new products before manufacturing
- **Ergonomic Assessment**: Identify high-frequency or high-strain motions for injury prevention
- **Digital Twins**: Feed standard times into simulation models for virtual factory optimization
- **ERP Integration**: Auto-calculate labor standards for Bills of Materials (BOMs)
- **Lean Manufacturing**: Eliminate waste by quantifying non-value-added motions
- **Cost Estimation**: Build accurate labor cost models for quoting and budgeting

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Deployment**: Render.com
- **Docs**: Auto-generated Swagger/OpenAPI 3.0

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL (optional - SQLite used by default for local dev)

### Setup

```bash
# Clone the repository
git clone https://github.com/siddhit/openpts-api.git
cd openpts-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` to see the interactive API documentation.

The database will auto-seed with motion codes on first startup.

## Deployment

This API is designed to deploy easily on Render.com's free tier.

**Note:** Render's free tier spins down after 15 minutes of inactivity. The first request after spin down may take 30 seconds to wake the service. Subsequent requests are fast (<100ms).

See [DEPLOY_TO_RENDER.md](DEPLOY_TO_RENDER.md) for complete deployment instructions.

## Disclaimer

MODAPTS® is a registered trademark of the International MODAPTS Association. This project is an independent, open-source implementation of predetermined time standards calculations and is not affiliated with, endorsed by, or supported by the International MODAPTS Association.

For official MODAPTS training, certification, and commercial software, visit [https://modapts.org](https://modapts.org)

This tool is intended for educational, research, and open-source development purposes.

## References & Sources

This implementation is based on publicly documented MODAPTS principles and motion codes from academic literature and industrial engineering textbooks:

- [About MODAPTS® - Eisbrenner Productivity Group](https://www.eisbrennerpg.com/about-modapts/)
- [MODAPTS: The Simple Language for Analyzing Work - SixSigma.us](https://www.6sigma.us/work-measurement/modapts-modular-arrangement-of-predetermined-time-standards/)
- [Unlocking Improvement Opportunities with MODAPTS - iSixSigma](https://www.isixsigma.com/dictionary/modular-arrangements-of-predetermined-time-standards-modapts/)
- [MODAPTS Movement Codes - ResearchGate Scientific Diagram](https://www.researchgate.net/figure/MODAPTS-movement-codes_fig2_353073640)
- [The 21 Basic Actions in MODAPTS - ResearchGate](https://www.researchgate.net/figure/The-21-types-of-basic-actions-in-the-MODAPTS_tbl1_374694190)
- [Applying MODAPTS Standards - IISE (PDF)](https://www.iise.org/uploadedfiles/IIE/Community/Technical_Societies_and_Divisions/SWS/sws1102.pdf)
- [Ergonomics Analysis Using MODAPTS - Wiley AI Magazine](https://onlinelibrary.wiley.com/doi/full/10.1609/aimag.v26i3.1824)
- [Discover MODAPTS - Sugoya India](https://www.sugoyaindia.com/modapts/)

## Contributing

Contributions are welcome! Areas for improvement:

- Additional motion codes (expand beyond the initial 17 codes)
- Ergonomic risk assessment endpoint
- Export to PDF/Excel reports
- Video-based motion extraction (computer vision)
- Support for MTM and MOST standards
- Multi-language support

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Built by [Sid Sanghavi](https://siddh.it)

**Background:**
- Licensed MODAPTS Practitioner (via Ford Motor Company, 2015)
- M.S. Industrial & Systems Engineering, Virginia Tech
- 4+ years as Senior Assembly Systems Engineer at Ford
- Industrial engineering experience across automotive manufacturing, IoT, and AI-powered products

**Connect:**
- Portfolio: [https://siddh.it](https://siddh.it)
- LinkedIn: [linkedin.com/in/SiddhitSanghavi](https://linkedin.com/in/SiddhitSanghavi)
- GitHub: [@siddhit](https://github.com/siddhit)
- Email: siddhits@gmail.com

---

**Project Status:** Active development. Version 0.1.0 (Initial release)

**Roadmap:**
- [x] Core MODAPTS motion library
- [x] Time study calculations with allowances
- [x] Interactive API documentation
- [x] Public deployment
- [ ] Complete motion library (30+ codes)
- [ ] Ergonomic risk scoring
- [ ] PDF report generation
- [ ] Video motion extraction (AI/CV)
- [ ] MTM/MOST support
