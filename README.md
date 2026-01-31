# ShowSpec CAD Bench

FreeCAD + Woodworking Workbench server for automated cut list generation and BOM calculation.

## Purpose

This service takes parametric inputs (component type, dimensions) and returns precise material cut lists, costs, and shop drawings. It powers the "backing" system in ShowSpec where every design element must be traceable to raw materials.

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
│  Templates (S3):                                                            │
│  - wall_straight.FCStd        - counter_straight.FCStd                     │
│  - wall_curved.FCStd          - counter_curved.FCStd                       │
│  - circular_platform.FCStd    - seg_lightbox.FCStd                         │
│  - tower_square.FCStd         - custom uploads                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **FreeCAD 0.21+** - 3D parametric CAD engine (LGPL)
- **Woodworking Workbench** - Cut list generation (MIT) - github.com/dprojects/Woodworking
- **Python 3.11+** - API and FreeCAD scripting
- **FastAPI** - REST API framework
- **Docker** - Containerization
- **AWS ECS/Fargate** - Hosting

## License

This server wrapper is proprietary (ShowSpec).
FreeCAD is LGPL (used as-is, not modified/distributed).
Woodworking Workbench is MIT.
