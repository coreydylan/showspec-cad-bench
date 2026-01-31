"""
DXF/DWG processor using FreeCAD's importDXF module.

Handles:
1. Loading DXF/DWG files via FreeCAD subprocess
2. Extracting layer information with geometry bounds
3. Auto-suggesting component mappings based on layer names
"""

import subprocess
import json
import tempfile
import os
import re
import uuid
from typing import Optional

from api.models import (
    CADLayer,
    DXFLayerBounds,
    DXFLayerDimensions,
    LayerMappingSuggestion,
)

# FreeCAD command path (set during initialization)
FREECAD_CMD: Optional[str] = None


def set_freecad_cmd(cmd: Optional[str]):
    """Set the FreeCAD command path."""
    global FREECAD_CMD
    FREECAD_CMD = cmd


def get_freecad_cmd() -> Optional[str]:
    """Get the FreeCAD command path."""
    return FREECAD_CMD


# =============================================================================
# Layer Name Pattern Matching (matches frontend types.ts)
# =============================================================================

LAYER_NAME_PATTERNS = [
    # Walls and structural
    (r"wall|partition|divider|blade", "walls", "wall-panel", 0.9),
    (r"perimeter", "walls", "perimeter-wall", 0.85),
    (r"backdrop|back.?drop", "walls", "backdrop", 0.9),

    # Counters and surfaces
    (r"counter|reception|desk", "counters", "counter", 0.9),
    (r"cabinet|storage", "counters", "storage-cabinet", 0.85),
    (r"table|surface", "counters", "table", 0.7),

    # Displays
    (r"display|pedestal|stand", "displays", "display-pedestal", 0.85),
    (r"monitor|screen|tv", "displays", "monitor-mount", 0.9),
    (r"kiosk", "displays", "kiosk", 0.9),

    # Lighting
    (r"light|lamp|fixture", "lighting", "light-fixture", 0.9),
    (r"canopy|header|overhead", "lighting", "overhead-structure", 0.8),

    # Flooring
    (r"floor|carpet|tile|platform", "flooring", "floor-section", 0.85),

    # Accessories
    (r"logo|brand|sign", "accessories", "signage", 0.9),
    (r"chair|seat|stool", "accessories", "seating", 0.85),
    (r"plant|greenery", "accessories", "plant", 0.9),

    # Exclusions (reference geometry, not buildable)
    (r"vehicle|car|truck", "exclude", "reference", 0.95),
    (r"person|people|human|figure", "exclude", "reference", 0.95),
    (r"scene|environment|context", "exclude", "reference", 0.8),
]


def suggest_layer_mapping(layer_name: str) -> Optional[LayerMappingSuggestion]:
    """
    Analyze a layer name and suggest a component mapping.
    Matches the frontend's suggestLayerMapping function.
    """
    normalized_name = layer_name.lower()

    for pattern, category, component_type, confidence in LAYER_NAME_PATTERNS:
        if re.search(pattern, normalized_name, re.IGNORECASE):
            return LayerMappingSuggestion(
                componentCategory=category,
                componentType=component_type,
                confidence=confidence,
                reasoning=f'Layer name "{layer_name}" matches pattern for {component_type}',
            )

    return None


def aci_to_hex(aci_color: int) -> str:
    """
    Convert AutoCAD Color Index (ACI) to hex color.
    This is a simplified mapping for common colors.
    """
    # Common ACI colors
    aci_colors = {
        0: "#000000",  # ByBlock
        1: "#FF0000",  # Red
        2: "#FFFF00",  # Yellow
        3: "#00FF00",  # Green
        4: "#00FFFF",  # Cyan
        5: "#0000FF",  # Blue
        6: "#FF00FF",  # Magenta
        7: "#FFFFFF",  # White/Black
        8: "#808080",  # Gray
        9: "#C0C0C0",  # Light Gray
        256: "#FFFFFF",  # ByLayer
    }
    return aci_colors.get(aci_color, "#CCCCCC")


async def process_dxf_file(
    file_path: str,
    source_unit: str = "feet",
) -> list[CADLayer]:
    """
    Process a DXF/DWG file and extract layer information.

    Args:
        file_path: Path to the DXF/DWG file
        source_unit: Unit of the source file ('millimeters', 'centimeters', 'meters', 'inches', 'feet')

    Returns:
        List of CADLayer objects with extracted data
    """

    # If FreeCAD is not available, return mock data
    if not FREECAD_CMD:
        return _mock_process_dxf(file_path)

    # Build the FreeCAD script for DXF processing
    script = _build_dxf_processing_script(file_path, source_unit)

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
            timeout=120,  # DXF processing can take longer
            env={**os.environ, "DISPLAY": ":99"}
        )

        if result.returncode != 0:
            raise RuntimeError(f"FreeCAD DXF processing error: {result.stderr}")

        # Parse JSON output from stdout
        output = result.stdout
        start_marker = "<<<DXF_LAYERS_JSON>>>"
        end_marker = "<<<END_DXF_LAYERS_JSON>>>"

        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            raise RuntimeError(f"Could not find layer data in output: {output[:500]}")

        json_str = output[start_idx + len(start_marker):end_idx].strip()
        data = json.loads(json_str)

        # Convert to CADLayer objects and add suggestions
        layers = []
        for layer_data in data.get("layers", []):
            layer = CADLayer(
                id=layer_data["id"],
                name=layer_data["name"],
                originalName=layer_data["originalName"],
                color=layer_data["color"],
                entityCount=layer_data["entityCount"],
                vertexCount=layer_data["vertexCount"],
                bounds=DXFLayerBounds(**layer_data["bounds"]),
                dimensions=DXFLayerDimensions(**layer_data["dimensions"]),
                previewUrl=layer_data.get("previewUrl"),
                thumbnailUrl=layer_data.get("thumbnailUrl"),
                meshCount=layer_data["meshCount"],
                isVisible=layer_data["isVisible"],
                suggestedMapping=None,
            )

            # Add AI-suggested mapping
            suggestion = suggest_layer_mapping(layer.originalName)
            if suggestion:
                layer = layer.model_copy(update={"suggestedMapping": suggestion})

            layers.append(layer)

        return layers

    finally:
        os.unlink(script_path)


def _build_dxf_processing_script(file_path: str, source_unit: str) -> str:
    """Build the FreeCAD Python script for DXF processing."""

    # Unit conversion to feet
    unit_to_feet = {
        "millimeters": 1 / 304.8,
        "centimeters": 1 / 30.48,
        "meters": 3.28084,
        "inches": 1 / 12,
        "feet": 1.0,
    }
    conversion_factor = unit_to_feet.get(source_unit, 1.0)

    script = f'''
import sys
import json
import uuid
import FreeCAD
import importDXF

# Helper to convert ACI color to hex
def aci_to_hex(aci):
    colors = {{
        0: "#000000", 1: "#FF0000", 2: "#FFFF00", 3: "#00FF00",
        4: "#00FFFF", 5: "#0000FF", 6: "#FF00FF", 7: "#FFFFFF",
        8: "#808080", 9: "#C0C0C0", 256: "#FFFFFF"
    }}
    return colors.get(aci, "#CCCCCC")

# Import the DXF file
file_path = "{file_path}"
doc = FreeCAD.newDocument("DXFImport")

try:
    importDXF.insert(file_path, doc.Name)
except Exception as e:
    # Try open instead of insert
    importDXF.open(file_path)
    doc = FreeCAD.ActiveDocument

# Conversion factor to feet
conversion = {conversion_factor}

# Group objects by layer
layer_objects = {{}}
for obj in doc.Objects:
    # Get layer name from object
    layer_name = getattr(obj, "Layer", None)
    if not layer_name:
        # Try to get from label prefix
        if "_" in obj.Label:
            layer_name = obj.Label.split("_")[0]
        else:
            layer_name = "Default"

    if layer_name not in layer_objects:
        layer_objects[layer_name] = []
    layer_objects[layer_name].append(obj)

# Process each layer
layers = []
for layer_name, objects in layer_objects.items():
    # Initialize bounds
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    entity_count = 0
    vertex_count = 0
    mesh_count = 0
    layer_color = "#CCCCCC"

    for obj in objects:
        entity_count += 1

        # Get color from object if available
        if hasattr(obj, "ViewObject") and obj.ViewObject:
            try:
                color = obj.ViewObject.ShapeColor
                if color:
                    r, g, b = int(color[0]*255), int(color[1]*255), int(color[2]*255)
                    layer_color = f"#{{r:02x}}{{g:02x}}{{b:02x}}"
            except:
                pass

        # Get geometry bounds
        if hasattr(obj, "Shape") and obj.Shape:
            shape = obj.Shape
            bbox = shape.BoundBox

            min_x = min(min_x, bbox.XMin)
            min_y = min(min_y, bbox.YMin)
            min_z = min(min_z, bbox.ZMin)
            max_x = max(max_x, bbox.XMax)
            max_y = max(max_y, bbox.YMax)
            max_z = max(max_z, bbox.ZMax)

            # Count vertices
            if hasattr(shape, "Vertexes"):
                vertex_count += len(shape.Vertexes)

            # Count meshes/faces
            if hasattr(shape, "Faces"):
                mesh_count += len(shape.Faces)

    # Handle empty layers
    if min_x == float('inf'):
        min_x = min_y = min_z = 0
        max_x = max_y = max_z = 0

    # Calculate dimensions in feet
    width = (max_x - min_x) * conversion
    height = (max_y - min_y) * conversion
    depth = (max_z - min_z) * conversion

    layer = {{
        "id": str(uuid.uuid4()),
        "name": layer_name.replace("_", " ").title(),
        "originalName": layer_name,
        "color": layer_color,
        "entityCount": entity_count,
        "vertexCount": vertex_count,
        "bounds": {{
            "minX": min_x,
            "minY": min_y,
            "minZ": min_z,
            "maxX": max_x,
            "maxY": max_y,
            "maxZ": max_z
        }},
        "dimensions": {{
            "width": round(width, 4),
            "height": round(height, 4),
            "depth": round(depth, 4)
        }},
        "previewUrl": None,
        "thumbnailUrl": None,
        "meshCount": mesh_count,
        "isVisible": True
    }}
    layers.append(layer)

# Output as JSON with markers
print("<<<DXF_LAYERS_JSON>>>")
print(json.dumps({{"layers": layers}}, indent=2))
print("<<<END_DXF_LAYERS_JSON>>>")

FreeCAD.closeDocument(doc.Name)
'''
    return script


def _mock_process_dxf(file_path: str) -> list[CADLayer]:
    """
    Generate mock layer data when FreeCAD is not available.
    Used for development/testing.
    """
    # Extract filename for mock data
    file_name = os.path.basename(file_path)

    mock_layers = [
        CADLayer(
            id=str(uuid.uuid4()),
            name="Walls",
            originalName="WALLS",
            color="#FF5722",
            entityCount=12,
            vertexCount=48,
            bounds=DXFLayerBounds(minX=0, minY=0, minZ=0, maxX=20, maxY=10, maxZ=8),
            dimensions=DXFLayerDimensions(width=20.0, height=10.0, depth=8.0),
            meshCount=6,
            isVisible=True,
            suggestedMapping=LayerMappingSuggestion(
                componentCategory="walls",
                componentType="wall-panel",
                confidence=0.9,
                reasoning='Layer name "WALLS" matches pattern for wall-panel',
            ),
        ),
        CADLayer(
            id=str(uuid.uuid4()),
            name="Counter",
            originalName="COUNTER",
            color="#2196F3",
            entityCount=4,
            vertexCount=24,
            bounds=DXFLayerBounds(minX=5, minY=2, minZ=0, maxX=15, maxY=5, maxZ=3),
            dimensions=DXFLayerDimensions(width=10.0, height=3.0, depth=3.0),
            meshCount=2,
            isVisible=True,
            suggestedMapping=LayerMappingSuggestion(
                componentCategory="counters",
                componentType="counter",
                confidence=0.9,
                reasoning='Layer name "COUNTER" matches pattern for counter',
            ),
        ),
        CADLayer(
            id=str(uuid.uuid4()),
            name="Display Stands",
            originalName="DISPLAY_STANDS",
            color="#4CAF50",
            entityCount=3,
            vertexCount=36,
            bounds=DXFLayerBounds(minX=2, minY=6, minZ=0, maxX=4, maxY=8, maxZ=4),
            dimensions=DXFLayerDimensions(width=2.0, height=2.0, depth=4.0),
            meshCount=3,
            isVisible=True,
            suggestedMapping=LayerMappingSuggestion(
                componentCategory="displays",
                componentType="display-pedestal",
                confidence=0.85,
                reasoning='Layer name "DISPLAY_STANDS" matches pattern for display-pedestal',
            ),
        ),
        CADLayer(
            id=str(uuid.uuid4()),
            name="Lighting",
            originalName="LIGHTING",
            color="#FFC107",
            entityCount=8,
            vertexCount=16,
            bounds=DXFLayerBounds(minX=0, minY=0, minZ=8, maxX=20, maxY=10, maxZ=9),
            dimensions=DXFLayerDimensions(width=20.0, height=10.0, depth=1.0),
            meshCount=8,
            isVisible=True,
            suggestedMapping=LayerMappingSuggestion(
                componentCategory="lighting",
                componentType="light-fixture",
                confidence=0.9,
                reasoning='Layer name "LIGHTING" matches pattern for light-fixture',
            ),
        ),
        CADLayer(
            id=str(uuid.uuid4()),
            name="Floor",
            originalName="FLOOR",
            color="#9E9E9E",
            entityCount=1,
            vertexCount=4,
            bounds=DXFLayerBounds(minX=0, minY=0, minZ=0, maxX=20, maxY=10, maxZ=0),
            dimensions=DXFLayerDimensions(width=20.0, height=10.0, depth=0.0),
            meshCount=1,
            isVisible=True,
            suggestedMapping=LayerMappingSuggestion(
                componentCategory="flooring",
                componentType="floor-section",
                confidence=0.85,
                reasoning='Layer name "FLOOR" matches pattern for floor-section',
            ),
        ),
    ]

    return mock_layers
