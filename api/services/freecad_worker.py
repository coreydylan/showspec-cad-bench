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

    # In development, FreeCAD might not be available - log warning but don't fail
    print("WARNING: FreeCAD not found. Template calculations will use mock data.")
    FREECAD_CMD = None


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

    # If FreeCAD not available, use mock calculation
    if not FREECAD_CMD:
        return _mock_calculation(component_type, dimensions, surfaces)

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


async def run_import_calculation(file_path: str) -> list[Part]:
    """
    Run a cut list calculation on an imported FreeCAD file.
    """
    if not FREECAD_CMD:
        # Return mock data for imported files
        return [
            Part(
                label="ImportedPart_1",
                length=48.0,
                width=24.0,
                thickness=0.75,
                material="Plywood 3/4",
                quantity=1,
                grain_direction="length",
                notes="Extracted from imported file"
            )
        ]

    script = f'''
import sys
import json
import FreeCAD

# Open the imported document
doc = FreeCAD.open("{file_path}")

parts = []
for obj in doc.Objects:
    if hasattr(obj, "Shape"):
        bbox = obj.Shape.BoundBox
        dims = sorted([bbox.XLength, bbox.YLength, bbox.ZLength], reverse=True)

        material = getattr(obj, "Material", "Unknown Material") if hasattr(obj, "Material") else "Unknown Material"

        part = {{
            "label": obj.Label,
            "length": dims[0],
            "width": dims[1],
            "thickness": dims[2],
            "material": material,
            "quantity": 1,
            "grain_direction": "any",
            "notes": None
        }}
        parts.append(part)

print("<<<CUTLIST_JSON>>>")
print(json.dumps({{"parts": parts}}, indent=2))
print("<<<END_CUTLIST_JSON>>>")
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [FREECAD_CMD, "-c", script_path],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "DISPLAY": ":99"}
        )

        if result.returncode != 0:
            raise RuntimeError(f"FreeCAD error: {result.stderr}")

        output = result.stdout
        start_marker = "<<<CUTLIST_JSON>>>"
        end_marker = "<<<END_CUTLIST_JSON>>>"

        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            raise RuntimeError(f"Could not find cut list in output")

        json_str = output[start_idx + len(start_marker):end_idx].strip()
        data = json.loads(json_str)
        return [Part(**p) for p in data["parts"]]

    finally:
        os.unlink(script_path)


def _build_calculation_script(
    component_type: ComponentType,
    dimensions: Dimensions,
    surfaces: Optional[SurfaceConfig]
) -> str:
    """Build the Python script to run inside FreeCAD."""

    template_name = f"{component_type.value}"

    surfaces_dict = surfaces.model_dump() if surfaces else None

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
surfaces = {surfaces_dict}

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


def _mock_calculation(
    component_type: ComponentType,
    dimensions: Dimensions,
    surfaces: Optional[SurfaceConfig]
) -> list[Part]:
    """
    Generate mock cut list data when FreeCAD is not available.
    Used for development/testing.
    """
    parts = []

    # Main panel
    parts.append(Part(
        label="PlywoodCore",
        length=dimensions.width,
        width=dimensions.height,
        thickness=dimensions.depth or 0.75,
        material="Plywood 3/4",
        quantity=1,
        grain_direction="length",
        notes=None
    ))

    # Add laminate if specified
    if surfaces and surfaces.front.value == "laminate":
        parts.append(Part(
            label="FrontLaminate",
            length=dimensions.width,
            width=dimensions.height,
            thickness=0.05,
            material="Laminate",
            quantity=1,
            grain_direction="any",
            notes=None
        ))

    if surfaces and surfaces.back.value == "laminate":
        parts.append(Part(
            label="BackLaminate",
            length=dimensions.width,
            width=dimensions.height,
            thickness=0.05,
            material="Laminate",
            quantity=1,
            grain_direction="any",
            notes=None
        ))

    return parts


def get_freecad_version() -> str:
    """Get FreeCAD version string."""
    if not FREECAD_CMD:
        return "Not available (mock mode)"

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
