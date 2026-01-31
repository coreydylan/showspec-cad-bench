# ShowSpec CAD Bench

FreeCAD + Woodworking Workbench server for automated cut list generation and BOM calculation.

**Endpoint:** `https://cad.showspec.cc`

## Purpose

This service takes parametric inputs (component type, dimensions) and returns precise material cut lists, costs, and shop drawings. It powers the "backing" system in ShowSpec where every design element must be traceable to raw materials.

## Quick Start

### Local Development

```bash
cd docker
docker-compose up --build

# Test the API
curl http://localhost:8000/health

# Calculate a wall panel
curl -X POST http://localhost:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "component_type": "wall_straight",
    "dimensions": {"width": 120, "height": 96, "depth": 0.75},
    "surfaces": {"front": "laminate", "back": "raw"}
  }'
```

### Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full deployment instructions.

```bash
./scripts/deploy.sh all
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with FreeCAD version |
| `/calculate` | POST | Calculate cut list from parametric inputs |
| `/import` | POST | Import .FCStd file and extract cut list |
| `/templates` | GET | List available parametric templates |
| `/docs` | GET | OpenAPI documentation |

## Example Response

```json
{
  "success": true,
  "component_type": "wall_straight",
  "dimensions": {"width": 120, "height": 96, "depth": 0.75},
  "parts": [
    {
      "label": "PlywoodCore",
      "length": 120.0,
      "width": 96.0,
      "thickness": 0.75,
      "material": "Plywood 3/4",
      "quantity": 1,
      "grain_direction": "length"
    },
    {
      "label": "FrontLaminate",
      "length": 120.0,
      "width": 96.0,
      "thickness": 0.05,
      "material": "Laminate",
      "quantity": 1,
      "grain_direction": "any"
    }
  ],
  "materials": [
    {"material": "Plywood 3/4", "total_quantity": 3, "unit": "sheet", "total_cost": 195.00}
  ],
  "labor": [
    {"operation": "Carpentry (Standard)", "hours": 1.6, "rate_per_hour": 75.00, "total_cost": 120.00}
  ],
  "material_cost": 280.00,
  "labor_cost": 144.75,
  "total_cost": 424.75
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ShowSpec CAD Bench                                  │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────┐   │
│  │   FastAPI       │     │         FreeCAD (Headless)                  │   │
│  │   REST API      │────▶│  + Woodworking Workbench                    │   │
│  │                 │     │  + Parametric Templates                      │   │
│  │  /calculate     │     │                                             │   │
│  │  /import        │     │  - Load template                            │   │
│  │  /templates     │     │  - Set parameters (W × H × D, radius, etc)  │   │
│  │  /health        │     │  - Run getDimensions                        │   │
│  └─────────────────┘     │  - Export cut list JSON                     │   │
│                          └─────────────────────────────────────────────┘   │
│                                                                             │
│  Templates:                                                                 │
│  - wall_straight.py          - counter_straight.py                         │
│  - wall_curved.py            - counter_curved.py                           │
│  - circular_platform.py      - seg_lightbox.py                             │
│  - tower_square.py           - custom uploads                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
showspec-cad-bench/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point
│   ├── models.py          # Pydantic models
│   ├── routers/           # API endpoints
│   └── services/          # Business logic
├── templates/             # Parametric template generators
├── materials/             # Material and labor rate definitions
├── docker/                # Docker configuration
├── infrastructure/        # Terraform for AWS
├── tests/                 # Test suite
└── scripts/               # Deployment scripts
```

## Tech Stack

- **FreeCAD 0.21+** - 3D parametric CAD engine (LGPL)
- **Woodworking Workbench** - Cut list generation (MIT) - github.com/dprojects/Woodworking
- **Python 3.11+** - API and FreeCAD scripting
- **FastAPI** - REST API framework
- **Docker** - Containerization
- **AWS ECS/Fargate** - Hosting
- **Terraform** - Infrastructure as Code

## License

This server wrapper is proprietary (ShowSpec).
FreeCAD is LGPL (used as-is, not modified/distributed).
Woodworking Workbench is MIT.
