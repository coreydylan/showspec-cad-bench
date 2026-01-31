# Build Instructions

This document contains complete instructions for building out the ShowSpec CAD Bench service.

---

## Directory Structure to Create

```
showspec-cad-bench/
├── README.md                     # ✅ Already created
├── BUILD_INSTRUCTIONS.md         # ✅ This file
├── docker/
│   ├── Dockerfile                # FreeCAD + Woodworking WB + Python API
│   ├── docker-compose.yml        # Local development
│   └── entrypoint.sh             # Container startup script
├── api/
│   ├── __init__.py
│   ├── main.py                   # FastAPI application
│   ├── config.py                 # Environment configuration
│   ├── models.py                 # Pydantic request/response models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── calculate.py          # POST /calculate endpoint
│   │   ├── import_file.py        # POST /import endpoint
│   │   ├── templates.py          # GET /templates endpoint
│   │   └── health.py             # GET /health endpoint
│   └── services/
│       ├── __init__.py
│       ├── freecad_worker.py     # FreeCAD headless operations
│       ├── cut_list_generator.py # getDimensions + sheet2export wrapper
│       ├── template_loader.py    # Load .FCStd templates
│       └── cost_calculator.py    # Material + labor pricing
├── templates/
│   ├── README.md                 # How templates work
│   ├── wall_straight.py          # Parametric straight wall generator
│   ├── wall_curved.py            # Parametric curved wall generator
│   ├── counter_straight.py       # Parametric counter/desk
│   ├── counter_curved.py         # Parametric curved counter
│   ├── circular_platform.py      # Raised circular platform
│   ├── tower_square.py           # Square tower/column
│   └── seg_lightbox.py           # SEG fabric lightbox
├── materials/
│   ├── material_library.json     # Default material definitions + costs
│   └── labor_rates.json          # Labor operation rates
├── tests/
│   ├── __init__.py
│   ├── test_calculate.py
│   ├── test_import.py
│   └── test_templates.py
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf               # AWS infrastructure
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── ecr.tf                # Container registry
│   │   ├── ecs.tf                # ECS cluster + service
│   │   ├── alb.tf                # Application Load Balancer
│   │   └── s3.tf                 # Template storage
│   └── github-actions/
│       └── deploy.yml            # CI/CD pipeline
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Project metadata
└── .env.example                  # Environment variables template
```

---

## 1. Docker Setup

### Dockerfile

Create `docker/Dockerfile`:

```dockerfile
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    python3.11 \
    python3-pip \
    python3.11-venv \
    git \
    wget \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install FreeCAD
RUN add-apt-repository ppa:freecad-maintainers/freecad-stable \
    && apt-get update \
    && apt-get install -y freecad \
    && rm -rf /var/lib/apt/lists/*

# Install Woodworking Workbench
RUN git clone https://github.com/dprojects/Woodworking.git \
    /root/.local/share/FreeCAD/Mod/Woodworking

# Set up Python environment
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ ./api/
COPY templates/ ./templates/
COPY materials/ ./materials/

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### entrypoint.sh

```bash
#!/bin/bash
set -e

# Start virtual framebuffer for FreeCAD (even in headless mode it needs X)
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Execute command
exec "$@"
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  cad-bench:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - FREECAD_PATH=/usr/bin/freecad
      - TEMPLATE_DIR=/app/templates
      - MATERIAL_LIBRARY=/app/materials/material_library.json
      - LABOR_RATES=/app/materials/labor_rates.json
      - LOG_LEVEL=INFO
    volumes:
      - ../api:/app/api:ro
      - ../templates:/app/templates:ro
      - ../materials:/app/materials:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 2. API Implementation

### requirements.txt

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
httpx==0.26.0
boto3==1.34.0
```

### api/config.py

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    freecad_path: str = "/usr/bin/freecad"
    template_dir: str = "/app/templates"
    material_library: str = "/app/materials/material_library.json"
    labor_rates: str = "/app/materials/labor_rates.json"
    log_level: str = "INFO"

    # AWS (for S3 template storage in production)
    aws_region: str = "us-west-2"
    s3_template_bucket: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### api/models.py

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

class ComponentType(str, Enum):
    WALL_STRAIGHT = "wall_straight"
    WALL_CURVED = "wall_curved"
    COUNTER_STRAIGHT = "counter_straight"
    COUNTER_CURVED = "counter_curved"
    CIRCULAR_PLATFORM = "circular_platform"
    TOWER_SQUARE = "tower_square"
    SEG_LIGHTBOX = "seg_lightbox"
    CUSTOM = "custom"

class SurfaceTreatment(str, Enum):
    LAMINATE = "laminate"
    PAINT = "paint"
    FABRIC_SEG = "fabric_seg"
    FABRIC_WRAPPED = "fabric_wrapped"
    VINYL = "vinyl"
    RAW = "raw"

class Dimensions(BaseModel):
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")
    depth: float = Field(..., description="Depth/thickness in inches")
    radius: Optional[float] = Field(None, description="Curve radius in inches (for curved components)")
    arc_angle: Optional[float] = Field(None, description="Arc angle in degrees (for curved components)")

class SurfaceConfig(BaseModel):
    front: SurfaceTreatment = SurfaceTreatment.LAMINATE
    back: SurfaceTreatment = SurfaceTreatment.RAW
    sides: SurfaceTreatment = SurfaceTreatment.LAMINATE
    top: Optional[SurfaceTreatment] = None
    bottom: Optional[SurfaceTreatment] = None

class CalculateRequest(BaseModel):
    component_type: ComponentType
    dimensions: Dimensions
    surfaces: Optional[SurfaceConfig] = None
    quantity: int = Field(1, ge=1)

    # Optional overrides
    material_overrides: Optional[dict] = None
    labor_rate_overrides: Optional[dict] = None

class Part(BaseModel):
    label: str
    length: float  # inches
    width: float   # inches
    thickness: float  # inches
    material: str
    quantity: int
    grain_direction: Optional[Literal["length", "width", "any"]] = "any"
    notes: Optional[str] = None

class MaterialSummary(BaseModel):
    material: str
    total_quantity: float
    unit: str  # "sheet", "sqft", "linear_ft", "gallon", etc.
    unit_cost: float
    total_cost: float

class LaborOperation(BaseModel):
    operation: str
    hours: float
    rate_per_hour: float
    total_cost: float

class CutListResponse(BaseModel):
    success: bool
    component_type: str
    dimensions: Dimensions

    # Cut list
    parts: list[Part]

    # Rollups
    materials: list[MaterialSummary]
    labor: list[LaborOperation]

    # Totals
    material_cost: float
    labor_cost: float
    total_cost: float

    # Metadata
    calculation_time_ms: float
    template_used: str
    warnings: list[str] = []

class ImportRequest(BaseModel):
    """For importing user's own .FCStd files"""
    filename: str
    file_content_base64: str

class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    component_type: ComponentType
    parameters: list[str]  # e.g., ["width", "height", "depth", "radius"]
    thumbnail_url: Optional[str] = None

class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]

class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    freecad_version: str
    woodworking_wb_version: str
    templates_loaded: int
    uptime_seconds: float
```

### api/main.py

```python
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.config import get_settings
from api.routers import calculate, import_file, templates, health

start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize FreeCAD, load templates
    from api.services.freecad_worker import initialize_freecad
    from api.services.template_loader import load_templates

    settings = get_settings()
    initialize_freecad(settings.freecad_path)
    load_templates(settings.template_dir)

    yield

    # Shutdown: cleanup if needed
    pass

app = FastAPI(
    title="ShowSpec CAD Bench",
    description="FreeCAD-powered cut list and BOM generation service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for ShowSpec frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://showspec.cc", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(calculate.router, prefix="/calculate", tags=["Calculate"])
app.include_router(import_file.router, prefix="/import", tags=["Import"])
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(health.router, tags=["Health"])

@app.get("/")
async def root():
    return {
        "service": "ShowSpec CAD Bench",
        "version": "1.0.0",
        "docs": "/docs"
    }
```

### api/routers/calculate.py

```python
import time
from fastapi import APIRouter, HTTPException
from api.models import CalculateRequest, CutListResponse
from api.services.freecad_worker import run_calculation
from api.services.cost_calculator import calculate_costs

router = APIRouter()

@router.post("", response_model=CutListResponse)
async def calculate_cut_list(request: CalculateRequest):
    """
    Calculate cut list and BOM for a parametric component.

    Takes component type and dimensions, returns:
    - Parts list with exact dimensions
    - Material quantities and costs
    - Labor hours and costs
    - Total cost
    """
    start = time.time()

    try:
        # Run FreeCAD calculation
        parts = await run_calculation(
            component_type=request.component_type,
            dimensions=request.dimensions,
            surfaces=request.surfaces
        )

        # Calculate costs
        materials, labor, totals = calculate_costs(
            parts=parts,
            quantity=request.quantity,
            material_overrides=request.material_overrides,
            labor_rate_overrides=request.labor_rate_overrides
        )

        calc_time = (time.time() - start) * 1000

        return CutListResponse(
            success=True,
            component_type=request.component_type.value,
            dimensions=request.dimensions,
            parts=parts,
            materials=materials,
            labor=labor,
            material_cost=totals["material"],
            labor_cost=totals["labor"],
            total_cost=totals["total"],
            calculation_time_ms=calc_time,
            template_used=f"{request.component_type.value}.py",
            warnings=[]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### api/services/freecad_worker.py

```python
"""
FreeCAD headless worker for parametric calculations.

This module handles:
1. Initializing FreeCAD in headless/console mode
2. Loading parametric templates
3. Setting parameters and regenerating geometry
4. Extracting cut list data using Woodworking Workbench tools
"""

import subprocess
import json
import tempfile
import os
from typing import Optional
from api.models import ComponentType, Dimensions, SurfaceConfig, Part

# FreeCAD path (set during initialization)
FREECAD_CMD: Optional[str] = None
TEMPLATE_DIR: Optional[str] = None

def initialize_freecad(freecad_path: str):
    """Initialize FreeCAD path and verify installation."""
    global FREECAD_CMD

    # Try freecadcmd first (headless), fall back to freecad
    for cmd in [f"{freecad_path}cmd", freecad_path, "freecadcmd", "freecad"]:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                FREECAD_CMD = cmd
                print(f"FreeCAD initialized: {cmd}")
                print(f"Version: {result.stdout.strip()}")
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    raise RuntimeError("FreeCAD not found. Please install FreeCAD.")

def set_template_dir(template_dir: str):
    """Set the template directory."""
    global TEMPLATE_DIR
    TEMPLATE_DIR = template_dir

async def run_calculation(
    component_type: ComponentType,
    dimensions: Dimensions,
    surfaces: Optional[SurfaceConfig] = None
) -> list[Part]:
    """
    Run a FreeCAD calculation for the given component type and dimensions.

    This creates a temporary Python script that:
    1. Loads the appropriate template
    2. Sets the parametric dimensions
    3. Regenerates the model
    4. Extracts the cut list using Woodworking Workbench
    5. Outputs JSON to stdout
    """

    if not FREECAD_CMD:
        raise RuntimeError("FreeCAD not initialized")

    # Build the FreeCAD script
    script = _build_calculation_script(component_type, dimensions, surfaces)

    # Write script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        # Run FreeCAD with the script
        result = subprocess.run(
            [FREECAD_CMD, "-c", script_path],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "DISPLAY": ":99"}  # Use virtual display
        )

        if result.returncode != 0:
            raise RuntimeError(f"FreeCAD error: {result.stderr}")

        # Parse JSON output from stdout
        # Look for JSON between markers
        output = result.stdout
        start_marker = "<<<CUTLIST_JSON>>>"
        end_marker = "<<<END_CUTLIST_JSON>>>"

        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            raise RuntimeError(f"Could not find cut list in output: {output}")

        json_str = output[start_idx + len(start_marker):end_idx].strip()
        data = json.loads(json_str)

        # Convert to Part objects
        parts = [Part(**p) for p in data["parts"]]
        return parts

    finally:
        os.unlink(script_path)

def _build_calculation_script(
    component_type: ComponentType,
    dimensions: Dimensions,
    surfaces: Optional[SurfaceConfig]
) -> str:
    """Build the Python script to run inside FreeCAD."""

    template_name = f"{component_type.value}"

    script = f'''
import sys
import json

# Add template directory to path
sys.path.insert(0, "{TEMPLATE_DIR}")

# Import the specific template generator
from {template_name} import generate_component, get_cut_list

# Set dimensions
dimensions = {{
    "width": {dimensions.width},
    "height": {dimensions.height},
    "depth": {dimensions.depth},
    "radius": {dimensions.radius if dimensions.radius else "None"},
    "arc_angle": {dimensions.arc_angle if dimensions.arc_angle else "None"}
}}

# Set surfaces
surfaces = {surfaces.model_dump() if surfaces else "None"}

# Generate the component
doc = generate_component(dimensions, surfaces)

# Get the cut list
cut_list = get_cut_list(doc)

# Output as JSON with markers
print("<<<CUTLIST_JSON>>>")
print(json.dumps(cut_list, indent=2))
print("<<<END_CUTLIST_JSON>>>")
'''

    return script

def get_freecad_version() -> str:
    """Get FreeCAD version string."""
    if not FREECAD_CMD:
        return "Not initialized"

    try:
        result = subprocess.run(
            [FREECAD_CMD, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"
```

---

## 3. Parametric Templates

Each template is a Python module that FreeCAD executes. It must implement:
- `generate_component(dimensions, surfaces)` - Creates the FreeCAD document with geometry
- `get_cut_list(doc)` - Extracts part list from the document

### templates/wall_straight.py

```python
"""
Parametric straight wall panel generator.

Creates a wall panel with:
- Plywood core (3/4" or as specified)
- Optional surface treatments (front/back/sides)
- Proper cut list for shop fabrication
"""

import FreeCAD
import Part
from typing import Optional

# Material thickness constants (inches)
PLYWOOD_THICKNESS = 0.75
LAMINATE_THICKNESS = 0.05
FABRIC_THICKNESS = 0.1

def generate_component(dimensions: dict, surfaces: Optional[dict] = None) -> FreeCAD.Document:
    """
    Generate a straight wall panel.

    Args:
        dimensions: {width, height, depth}
        surfaces: {front, back, sides, top, bottom}

    Returns:
        FreeCAD Document with the wall geometry
    """
    doc = FreeCAD.newDocument("WallStraight")

    width = dimensions["width"]
    height = dimensions["height"]
    depth = dimensions.get("depth", PLYWOOD_THICKNESS)

    # Create main panel (plywood core)
    panel = doc.addObject("Part::Box", "PlywoodCore")
    panel.Length = width
    panel.Width = depth
    panel.Height = height

    # Add material property for cut list
    panel.addProperty("App::PropertyString", "Material", "CutList")
    panel.Material = "Plywood 3/4"

    panel.addProperty("App::PropertyString", "PartType", "CutList")
    panel.PartType = "Panel"

    # Add surface treatments as separate parts
    if surfaces:
        if surfaces.get("front") == "laminate":
            front_lam = doc.addObject("Part::Box", "FrontLaminate")
            front_lam.Length = width
            front_lam.Width = LAMINATE_THICKNESS
            front_lam.Height = height
            front_lam.Placement.Base.y = depth  # Position on front face
            front_lam.addProperty("App::PropertyString", "Material", "CutList")
            front_lam.Material = "Laminate"
            front_lam.addProperty("App::PropertyString", "PartType", "CutList")
            front_lam.PartType = "Surface"

        if surfaces.get("back") == "laminate":
            back_lam = doc.addObject("Part::Box", "BackLaminate")
            back_lam.Length = width
            back_lam.Width = LAMINATE_THICKNESS
            back_lam.Height = height
            back_lam.Placement.Base.y = -LAMINATE_THICKNESS
            back_lam.addProperty("App::PropertyString", "Material", "CutList")
            back_lam.Material = "Laminate"
            back_lam.addProperty("App::PropertyString", "PartType", "CutList")
            back_lam.PartType = "Surface"

    doc.recompute()
    return doc

def get_cut_list(doc: FreeCAD.Document) -> dict:
    """
    Extract cut list from the document.

    Returns:
        {
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
                ...
            ]
        }
    """
    parts = []

    for obj in doc.Objects:
        if hasattr(obj, "Material") and hasattr(obj, "Shape"):
            # Get bounding box dimensions
            bbox = obj.Shape.BoundBox

            # Determine length/width/thickness based on orientation
            dims = sorted([bbox.XLength, bbox.YLength, bbox.ZLength], reverse=True)

            part = {
                "label": obj.Label,
                "length": dims[0],  # Longest dimension
                "width": dims[1],   # Second longest
                "thickness": dims[2],  # Shortest (thickness)
                "material": obj.Material,
                "quantity": 1,
                "grain_direction": "length" if obj.Material.startswith("Plywood") else "any",
                "notes": None
            }
            parts.append(part)

    return {"parts": parts}
```

### templates/wall_curved.py

```python
"""
Parametric curved wall panel generator.

Creates a curved wall using:
- Bendable plywood for tight radii (< 24" radius)
- Kerfed plywood for medium radii (24-48" radius)
- Standard plywood segments for large radii (> 48" radius)
"""

import FreeCAD
import Part
import math
from typing import Optional

PLYWOOD_THICKNESS = 0.75
BENDABLE_PLY_THICKNESS = 0.25  # 1/4" bendable
MIN_BEND_RADIUS = 24  # inches - below this needs bendable ply
SEGMENT_MAX_WIDTH = 48  # Max width of a single plywood sheet

def generate_component(dimensions: dict, surfaces: Optional[dict] = None) -> FreeCAD.Document:
    """
    Generate a curved wall panel.

    Args:
        dimensions: {width (arc length), height, depth, radius, arc_angle}
        surfaces: {front, back}

    Returns:
        FreeCAD Document with curved wall geometry
    """
    doc = FreeCAD.newDocument("WallCurved")

    arc_length = dimensions["width"]  # Width is arc length for curved walls
    height = dimensions["height"]
    depth = dimensions.get("depth", PLYWOOD_THICKNESS)
    radius = dimensions.get("radius")
    arc_angle = dimensions.get("arc_angle")

    # Calculate radius or arc_angle if only one provided
    if radius and not arc_angle:
        arc_angle = math.degrees(arc_length / radius)
    elif arc_angle and not radius:
        radius = arc_length / math.radians(arc_angle)
    elif not radius and not arc_angle:
        # Default to 90 degree arc
        arc_angle = 90
        radius = arc_length / math.radians(arc_angle)

    # Determine construction method based on radius
    if radius < MIN_BEND_RADIUS:
        material = "Bendable Plywood 1/4"
        num_layers = 3  # Laminate multiple layers for strength
    elif radius < 48:
        material = "Plywood 3/4 (Kerfed)"
        num_layers = 1
    else:
        material = "Plywood 3/4"
        num_layers = 1

    # Calculate number of segments needed
    num_segments = max(1, math.ceil(arc_length / SEGMENT_MAX_WIDTH))
    segment_arc = arc_angle / num_segments
    segment_length = arc_length / num_segments

    # Create arc geometry
    center = FreeCAD.Vector(0, 0, 0)
    start_angle = 0

    for i in range(num_segments):
        seg_start = math.radians(start_angle + i * segment_arc)
        seg_end = math.radians(start_angle + (i + 1) * segment_arc)

        # Create arc profile
        arc = Part.makeCircle(radius, center, FreeCAD.Vector(0, 0, 1),
                              math.degrees(seg_start), math.degrees(seg_end))

        # Extrude to height
        face = Part.Face(Part.Wire(arc))
        segment = face.extrude(FreeCAD.Vector(0, 0, height))

        # Add to document
        obj = doc.addObject("Part::Feature", f"CurvedSegment_{i+1}")
        obj.Shape = segment

        obj.addProperty("App::PropertyString", "Material", "CutList")
        obj.Material = material

        obj.addProperty("App::PropertyString", "PartType", "CutList")
        obj.PartType = "CurvedPanel"

        obj.addProperty("App::PropertyFloat", "ArcLength", "CutList")
        obj.ArcLength = segment_length

        obj.addProperty("App::PropertyFloat", "Radius", "CutList")
        obj.Radius = radius

    doc.recompute()
    return doc

def get_cut_list(doc: FreeCAD.Document) -> dict:
    """Extract cut list from curved wall document."""
    parts = []

    for obj in doc.Objects:
        if hasattr(obj, "Material"):
            # For curved panels, use arc length as "length"
            arc_length = getattr(obj, "ArcLength", 0)
            radius = getattr(obj, "Radius", 0)

            # Get height from bounding box
            bbox = obj.Shape.BoundBox
            height = bbox.ZLength

            # Determine flat sheet size needed
            # For curved panels, we need extra material for bending
            flat_length = arc_length * 1.05  # 5% extra for curve

            part = {
                "label": obj.Label,
                "length": flat_length,
                "width": height,
                "thickness": PLYWOOD_THICKNESS if "3/4" in obj.Material else BENDABLE_PLY_THICKNESS,
                "material": obj.Material,
                "quantity": 1,
                "grain_direction": "length",
                "notes": f"Curve radius: {radius}in, Arc length: {arc_length}in"
            }
            parts.append(part)

    return {"parts": parts}
```

### templates/circular_platform.py

```python
"""
Parametric circular raised platform generator.

Creates a circular platform with:
- Circular plywood top
- Radial support structure
- Adjustable height with step
- Optional curved fascia/ribbon element
"""

import FreeCAD
import Part
import math
from typing import Optional

def generate_component(dimensions: dict, surfaces: Optional[dict] = None) -> FreeCAD.Document:
    """
    Generate a circular raised platform (like for a car turntable).

    Args:
        dimensions: {
            width: diameter in inches,
            height: platform height in inches,
            depth: deck thickness (default 0.75),
            radius: inner cutout radius if any (optional)
        }
    """
    doc = FreeCAD.newDocument("CircularPlatform")

    diameter = dimensions["width"]
    radius = diameter / 2
    platform_height = dimensions["height"]
    deck_thickness = dimensions.get("depth", 0.75)
    inner_radius = dimensions.get("radius", 0)  # Optional center cutout

    # Platform deck (circular)
    # Calculate how many pie segments we need
    # Each segment should be cuttable from a 4x8 sheet
    segment_angle = 45  # 8 segments for a full circle
    num_segments = 8

    for i in range(num_segments):
        start_angle = i * segment_angle
        end_angle = (i + 1) * segment_angle

        # Create pie segment
        outer_arc = Part.makeCircle(radius, FreeCAD.Vector(0, 0, platform_height),
                                    FreeCAD.Vector(0, 0, 1), start_angle, end_angle)

        if inner_radius > 0:
            inner_arc = Part.makeCircle(inner_radius, FreeCAD.Vector(0, 0, platform_height),
                                        FreeCAD.Vector(0, 0, 1), end_angle, start_angle)
            # Create closed wire
            edges = [outer_arc]
            # Add radial lines and inner arc
            # ... (simplified for this example)

        obj = doc.addObject("Part::Feature", f"DeckSegment_{i+1}")
        # ... set shape

        obj.addProperty("App::PropertyString", "Material", "CutList")
        obj.Material = "Plywood 3/4"

        obj.addProperty("App::PropertyString", "PartType", "CutList")
        obj.PartType = "DeckSegment"

    # Support structure (radial ribs)
    num_ribs = 8
    rib_height = platform_height - deck_thickness

    for i in range(num_ribs):
        angle = math.radians(i * (360 / num_ribs))

        rib = doc.addObject("Part::Box", f"SupportRib_{i+1}")
        rib.Length = radius - 6  # Leave 6" from center
        rib.Width = 0.75
        rib.Height = rib_height

        # Position and rotate
        rib.Placement.Base = FreeCAD.Vector(6, 0, 0)
        rib.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), math.degrees(angle))

        rib.addProperty("App::PropertyString", "Material", "CutList")
        rib.Material = "Plywood 3/4"

        rib.addProperty("App::PropertyString", "PartType", "CutList")
        rib.PartType = "StructuralRib"

    # Perimeter ring
    ring_width = 4  # 4" wide perimeter
    ring = doc.addObject("Part::Feature", "PerimeterRing")
    # ... create ring geometry

    doc.recompute()
    return doc

def get_cut_list(doc: FreeCAD.Document) -> dict:
    """Extract cut list from circular platform document."""
    parts = []

    for obj in doc.Objects:
        if hasattr(obj, "Material"):
            bbox = obj.Shape.BoundBox
            dims = sorted([bbox.XLength, bbox.YLength, bbox.ZLength], reverse=True)

            part_type = getattr(obj, "PartType", "Unknown")

            # For pie segments, calculate flat size needed
            if part_type == "DeckSegment":
                # Pie segment fits in a rectangle
                length = dims[0]
                width = dims[1]
            else:
                length = dims[0]
                width = dims[1]

            part = {
                "label": obj.Label,
                "length": length,
                "width": width,
                "thickness": dims[2],
                "material": obj.Material,
                "quantity": 1,
                "grain_direction": "any",
                "notes": f"Part type: {part_type}"
            }
            parts.append(part)

    return {"parts": parts}
```

---

## 4. Material Library

### materials/material_library.json

```json
{
  "materials": {
    "plywood_3/4": {
      "name": "Plywood 3/4\"",
      "description": "3/4 inch cabinet-grade plywood",
      "thickness": 0.75,
      "sheet_size": {"length": 96, "width": 48},
      "unit": "sheet",
      "cost_per_unit": 65.00,
      "weight_per_sqft": 2.3,
      "aliases": ["Plywood 3/4", "3/4 Plywood", "Cabinet Plywood"]
    },
    "plywood_1/2": {
      "name": "Plywood 1/2\"",
      "thickness": 0.5,
      "sheet_size": {"length": 96, "width": 48},
      "unit": "sheet",
      "cost_per_unit": 48.00,
      "weight_per_sqft": 1.5
    },
    "bendable_plywood": {
      "name": "Bendable Plywood 1/4\"",
      "description": "Flexible plywood for curved applications",
      "thickness": 0.25,
      "sheet_size": {"length": 96, "width": 48},
      "unit": "sheet",
      "cost_per_unit": 55.00,
      "min_bend_radius": 12,
      "weight_per_sqft": 0.8
    },
    "laminate_white": {
      "name": "Laminate (White)",
      "description": "High-pressure laminate, white finish",
      "thickness": 0.05,
      "sheet_size": {"length": 120, "width": 60},
      "unit": "sheet",
      "cost_per_unit": 85.00,
      "weight_per_sqft": 0.5
    },
    "laminate_custom": {
      "name": "Laminate (Custom Print)",
      "description": "Digitally printed laminate",
      "thickness": 0.05,
      "sheet_size": {"length": 120, "width": 60},
      "unit": "sheet",
      "cost_per_unit": 150.00
    },
    "seg_fabric": {
      "name": "SEG Fabric (Dye-Sub)",
      "description": "Silicone-edge graphics fabric, dye-sublimation printed",
      "unit": "sqft",
      "cost_per_unit": 12.00,
      "weight_per_sqft": 0.1
    },
    "seg_frame_aluminum": {
      "name": "SEG Frame (Aluminum)",
      "description": "Aluminum extrusion for SEG frames",
      "unit": "linear_ft",
      "cost_per_unit": 8.50
    },
    "led_strip": {
      "name": "LED Strip (Backlight)",
      "description": "24V LED strip for lightbox backlighting",
      "unit": "linear_ft",
      "cost_per_unit": 4.50
    },
    "connector_type_a": {
      "name": "Panel Connector (Type A)",
      "description": "Standard panel-to-panel connector",
      "unit": "each",
      "cost_per_unit": 12.00
    },
    "connector_corner": {
      "name": "Corner Connector",
      "description": "90-degree corner connector",
      "unit": "each",
      "cost_per_unit": 18.00
    }
  }
}
```

### materials/labor_rates.json

```json
{
  "labor_operations": {
    "carpentry_standard": {
      "name": "Carpentry (Standard)",
      "description": "Standard panel cutting, assembly",
      "rate_per_hour": 75.00,
      "unit": "hour",
      "calc_methods": {
        "per_sqft": 0.02,
        "per_panel": 0.5,
        "per_joint": 0.15
      }
    },
    "carpentry_curved": {
      "name": "Carpentry (Curved)",
      "description": "Curved panel fabrication, bending, laminating",
      "rate_per_hour": 95.00,
      "calc_methods": {
        "per_sqft": 0.05,
        "per_panel": 1.5
      }
    },
    "laminate_application": {
      "name": "Laminate Application",
      "description": "Contact cement and laminate application",
      "rate_per_hour": 65.00,
      "calc_methods": {
        "per_sqft": 0.015
      }
    },
    "paint_prep": {
      "name": "Paint Prep",
      "description": "Sanding, priming, masking",
      "rate_per_hour": 55.00,
      "calc_methods": {
        "per_sqft": 0.01
      }
    },
    "paint_finish": {
      "name": "Paint (Finish Coat)",
      "description": "Spray finish application",
      "rate_per_hour": 65.00,
      "calc_methods": {
        "per_sqft": 0.008
      }
    },
    "seg_frame_assembly": {
      "name": "SEG Frame Assembly",
      "description": "Aluminum frame cutting and assembly",
      "rate_per_hour": 70.00,
      "calc_methods": {
        "per_linear_ft": 0.05,
        "per_frame": 0.75
      }
    },
    "electrical_led": {
      "name": "Electrical (LED)",
      "description": "LED strip installation and wiring",
      "rate_per_hour": 85.00,
      "calc_methods": {
        "per_linear_ft": 0.03,
        "per_connection": 0.25
      }
    },
    "qc_inspection": {
      "name": "QC Inspection",
      "description": "Quality control and final inspection",
      "rate_per_hour": 60.00,
      "calc_methods": {
        "per_component": 0.25,
        "minimum": 0.5
      }
    },
    "site_install": {
      "name": "Site Install (I&D)",
      "description": "On-site installation and dismantle",
      "rate_per_hour": 125.00,
      "calc_methods": {
        "per_component": 0.5,
        "per_sqft": 0.005
      }
    }
  }
}
```

---

## 5. AWS Infrastructure

### infrastructure/terraform/main.tf

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "showspec-terraform-state"
    key    = "cad-bench/terraform.tfstate"
    region = "us-west-2"
  }
}

provider "aws" {
  region = var.aws_region
}

# ECR Repository
resource "aws_ecr_repository" "cad_bench" {
  name                 = "showspec-cad-bench"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "cad_bench" {
  name = "showspec-cad-bench"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "cad_bench" {
  family                   = "showspec-cad-bench"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024  # 1 vCPU
  memory                   = 2048  # 2 GB
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "cad-bench"
      image = "${aws_ecr_repository.cad_bench.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        },
        {
          name  = "S3_TEMPLATE_BUCKET"
          value = aws_s3_bucket.templates.id
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.cad_bench.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "cad_bench" {
  name            = "showspec-cad-bench"
  cluster         = aws_ecs_cluster.cad_bench.id
  task_definition = aws_ecs_task_definition.cad_bench.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.cad_bench.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.cad_bench.arn
    container_name   = "cad-bench"
    container_port   = 8000
  }
}

# Application Load Balancer
resource "aws_lb" "cad_bench" {
  name               = "showspec-cad-bench"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "cad_bench" {
  name        = "showspec-cad-bench"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.cad_bench.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.ssl_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.cad_bench.arn
  }
}

# S3 Bucket for templates
resource "aws_s3_bucket" "templates" {
  bucket = "showspec-cad-bench-templates"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "cad_bench" {
  name              = "/ecs/showspec-cad-bench"
  retention_in_days = 30
}

# Outputs
output "api_endpoint" {
  value = "https://${aws_lb.cad_bench.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.cad_bench.repository_url
}
```

### infrastructure/terraform/variables.tf

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
}

variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate for HTTPS"
  type        = string
}
```

---

## 6. GitHub Actions CI/CD

### infrastructure/github-actions/deploy.yml

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-west-2
  ECR_REPOSITORY: showspec-cad-bench
  ECS_SERVICE: showspec-cad-bench
  ECS_CLUSTER: showspec-cad-bench

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx

      - name: Run tests
        run: pytest tests/ -v

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG -f docker/Dockerfile .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster $ECS_CLUSTER --service $ECS_SERVICE --force-new-deployment
```

---

## 7. Testing

### tests/test_calculate.py

```python
import pytest
from httpx import AsyncClient
from api.main import app
from api.models import ComponentType

@pytest.fixture
def client():
    return AsyncClient(app=app, base_url="http://test")

@pytest.mark.asyncio
async def test_calculate_straight_wall(client):
    response = await client.post("/calculate", json={
        "component_type": "wall_straight",
        "dimensions": {
            "width": 120,  # 10 feet
            "height": 96,  # 8 feet
            "depth": 0.75
        },
        "surfaces": {
            "front": "laminate",
            "back": "raw"
        },
        "quantity": 1
    })

    assert response.status_code == 200
    data = response.json()

    assert data["success"] == True
    assert len(data["parts"]) > 0
    assert data["total_cost"] > 0

    # Should have plywood and laminate
    materials = [p["material"] for p in data["parts"]]
    assert any("Plywood" in m for m in materials)
    assert any("Laminate" in m for m in materials)

@pytest.mark.asyncio
async def test_calculate_curved_wall(client):
    response = await client.post("/calculate", json={
        "component_type": "wall_curved",
        "dimensions": {
            "width": 180,  # 15 feet arc length
            "height": 96,
            "depth": 0.75,
            "radius": 60  # 5 foot radius - tight curve
        },
        "quantity": 1
    })

    assert response.status_code == 200
    data = response.json()

    assert data["success"] == True
    # Tight radius should use bendable plywood
    materials = [p["material"] for p in data["parts"]]
    assert any("Bendable" in m for m in materials)

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
```

---

## Quick Start (Local Development)

```bash
# Clone repo
git clone https://github.com/yourorg/showspec-cad-bench.git
cd showspec-cad-bench

# Build and run with Docker
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

---

## Integration with ShowSpec

In the ShowSpec frontend, create `src/services/freecadService.ts`:

```typescript
const CAD_BENCH_URL = import.meta.env.VITE_CAD_BENCH_URL || 'http://localhost:8000';

export interface CutListResult {
  success: boolean;
  parts: Array<{
    label: string;
    length: number;
    width: number;
    thickness: number;
    material: string;
    quantity: number;
  }>;
  materials: Array<{
    material: string;
    total_quantity: number;
    unit: string;
    total_cost: number;
  }>;
  labor: Array<{
    operation: string;
    hours: number;
    total_cost: number;
  }>;
  material_cost: number;
  labor_cost: number;
  total_cost: number;
}

export async function calculateMaterials(
  componentType: string,
  dimensions: { width: number; height: number; depth: number; radius?: number }
): Promise<CutListResult> {
  const response = await fetch(`${CAD_BENCH_URL}/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      component_type: componentType,
      dimensions
    })
  });

  if (!response.ok) {
    throw new Error(`CAD Bench error: ${response.statusText}`);
  }

  return response.json();
}
```

---

## Priority Order for Implementation

1. **Docker setup** - Get FreeCAD + Woodworking WB running in container
2. **Basic API** - FastAPI with /health and /calculate endpoints
3. **wall_straight template** - Simplest case, validate the pipeline
4. **wall_curved template** - Curved geometry, bendable plywood logic
5. **Cost calculator** - Wire up material library and labor rates
6. **AWS infrastructure** - Deploy to ECS
7. **Additional templates** - circular_platform, counter, seg_lightbox
8. **Import endpoint** - Allow uploading custom .FCStd files
