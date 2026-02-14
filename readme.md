# OpenPTS API

> Open Predetermined Time Standards — A modern REST API for industrial time study calculations

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Live API:** https://openpts-api-production.up.railway.app
**API Docs:** https://openpts-api-production.up.railway.app/docs

## What is OpenPTS?

OpenPTS is the first open-source REST API for predetermined time standards calculations used in manufacturing and industrial engineering. It implements MODAPTS-compatible motion codes to help engineers calculate standard work times for assembly and manufacturing tasks.

## Why This Exists

Predetermined time standards like MODAPTS have been used in manufacturing for decades, but they've remained locked in proprietary desktop software and Excel spreadsheets. OpenPTS brings these calculations into the modern API era, making it easy to integrate time standards into:

- Manufacturing Execution Systems (MES)
- Enterprise Resource Planning (ERP) platforms
- Digital twin simulations
- Custom production planning tools

## Features

✅ Complete library of MODAPTS motion codes
✅ Time study calculations with allowances
✅ Auto-generated interactive API documentation
✅ Open source and free to use
✅ RESTful JSON API

## Quick Start

### Get All Motion Codes
```bash
curl https://openpts-api-production.up.railway.app/api/v1/motions
```

### Get a Specific Motion
```bash
curl https://openpts-api-production.up.railway.app/api/v1/motions/M3
```

### Create a Time Study
```bash
curl -X POST https://openpts-api-production.up.railway.app/api/v1/studies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pick and Place Task",
    "motions": [
      {"code": "M3", "quantity": 1},
      {"code": "G1", "quantity": 1},
      {"code": "P2", "quantity": 1}
    ]
  }'
```

## API Documentation

Full interactive documentation available at: [https://openpts-api-production.up.railway.app/docs](https://openpts-api-production.up.railway.app/docs)

## Use Cases

- **Line Balancing**: Calculate cycle times for assembly stations
- **Capacity Planning**: Estimate labor requirements for new products
- **Ergonomic Assessment**: Identify high-frequency motions for injury risk
- **Digital Twins**: Feed standard times into simulation models
- **ERP Integration**: Auto-calculate labor standards for BOMs

## Disclaimer

MODAPTS® is a registered trademark of the International MODAPTS Association. This project is an independent, open-source implementation of predetermined time standards calculations and is not affiliated with, endorsed by, or supported by the International MODAPTS Association. For official MODAPTS training, certification, and commercial software, visit https://modapts.org

## Tech Stack

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL
- **Deployment**: Railway
- **Docs**: Auto-generated Swagger/OpenAPI

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Built by [Sid Sanghavi](https://siddh.it) with the help of Claude Cowork and Claude Code — Licensed MODAPTS Practitioner, former assembly systems engineer at Ford Motor Company.