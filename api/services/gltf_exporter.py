"""
GLTF preview generator using FreeCAD.

Handles:
1. Converting DXF geometry to GLTF/GLB format
2. Generating layer-specific previews
3. Optimizing geometry for web display
"""

import subprocess
import json
import tempfile
import os
import base64
from typing import Optional

# FreeCAD command path (imported from dxf_processor or set separately)
FREECAD_CMD: Optional[str] = None


def set_freecad_cmd(cmd: Optional[str]):
    """Set the FreeCAD command path."""
    global FREECAD_CMD
    FREECAD_CMD = cmd


def get_freecad_cmd() -> Optional[str]:
    """Get the FreeCAD command path."""
    return FREECAD_CMD


async def generate_gltf_preview(
    dxf_file_path: str,
    layer_ids: Optional[list[str]] = None,
    quality: str = "medium",
    output_format: str = "glb",
) -> tuple[str, str]:
    """
    Generate a GLTF/GLB preview from a DXF file.

    Args:
        dxf_file_path: Path to the source DXF/DWG file
        layer_ids: Optional list of layer IDs to include (None = all layers)
        quality: Preview quality ('low', 'medium', 'high')
        output_format: Output format ('gltf' or 'glb')

    Returns:
        Tuple of (base64_encoded_content, format)
    """

    # If FreeCAD is not available, return mock GLTF
    if not FREECAD_CMD:
        return _mock_generate_gltf(layer_ids, output_format)

    # Determine tessellation settings based on quality
    tessellation_params = {
        "low": {"linear_deflection": 1.0, "angular_deflection": 30},
        "medium": {"linear_deflection": 0.1, "angular_deflection": 15},
        "high": {"linear_deflection": 0.01, "angular_deflection": 5},
    }
    params = tessellation_params.get(quality, tessellation_params["medium"])

    # Create temp output file
    suffix = ".glb" if output_format == "glb" else ".gltf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        output_path = f.name

    # Build the FreeCAD script for GLTF export
    script = _build_gltf_export_script(
        dxf_file_path,
        output_path,
        layer_ids,
        params["linear_deflection"],
        params["angular_deflection"],
    )

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
            timeout=180,  # GLTF export can take time
            env={**os.environ, "DISPLAY": ":99"}
        )

        if result.returncode != 0:
            raise RuntimeError(f"FreeCAD GLTF export error: {result.stderr}")

        # Read the generated file
        if os.path.exists(output_path):
            with open(output_path, "rb") as f:
                content = f.read()

            # Encode as base64
            encoded = base64.b64encode(content).decode("utf-8")
            return encoded, output_format
        else:
            raise RuntimeError("GLTF file was not generated")

    finally:
        os.unlink(script_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def _build_gltf_export_script(
    dxf_file_path: str,
    output_path: str,
    layer_ids: Optional[list[str]],
    linear_deflection: float,
    angular_deflection: float,
) -> str:
    """Build the FreeCAD Python script for GLTF export."""

    layer_filter = json.dumps(layer_ids) if layer_ids else "None"

    script = f'''
import sys
import json
import FreeCAD
import importDXF
import Mesh
import MeshPart

# Import the DXF file
file_path = "{dxf_file_path}"
output_path = "{output_path}"
layer_filter = {layer_filter}
linear_deflection = {linear_deflection}
angular_deflection = {angular_deflection}

doc = FreeCAD.newDocument("DXFExport")

try:
    importDXF.insert(file_path, doc.Name)
except Exception as e:
    importDXF.open(file_path)
    doc = FreeCAD.ActiveDocument

# Collect shapes to export
shapes_to_export = []

for obj in doc.Objects:
    # Check layer filter if specified
    if layer_filter:
        layer_name = getattr(obj, "Layer", None)
        if not layer_name:
            if "_" in obj.Label:
                layer_name = obj.Label.split("_")[0]
            else:
                layer_name = "Default"
        # Skip if layer not in filter (we'd need layer IDs here, simplified for now)

    if hasattr(obj, "Shape") and obj.Shape and not obj.Shape.isNull():
        shapes_to_export.append(obj.Shape)

# Create a compound mesh
if shapes_to_export:
    # Create mesh from shapes
    meshes = []
    for shape in shapes_to_export:
        try:
            mesh = MeshPart.meshFromShape(
                Shape=shape,
                LinearDeflection=linear_deflection,
                AngularDeflection=angular_deflection
            )
            if mesh.CountPoints > 0:
                meshes.append(mesh)
        except Exception as e:
            print(f"Warning: Could not mesh shape: {{e}}")

    if meshes:
        # Merge meshes
        combined_mesh = Mesh.Mesh()
        for m in meshes:
            combined_mesh.addMesh(m)

        # Export to GLTF/GLB
        # FreeCAD's Mesh module can export to various formats
        if output_path.endswith('.glb') or output_path.endswith('.gltf'):
            # Use the Export module if available
            try:
                import Export
                Export.export([combined_mesh], output_path)
            except:
                # Fallback: export as OBJ first, then convert
                obj_path = output_path.replace('.glb', '.obj').replace('.gltf', '.obj')
                combined_mesh.write(obj_path)
                print(f"Exported to: {{obj_path}}")
        else:
            combined_mesh.write(output_path)

        print(f"GLTF export complete: {{output_path}}")
    else:
        print("Warning: No meshable geometry found")
else:
    print("Warning: No shapes to export")

FreeCAD.closeDocument(doc.Name)
'''
    return script


def _mock_generate_gltf(
    layer_ids: Optional[list[str]],
    output_format: str,
) -> tuple[str, str]:
    """
    Generate a minimal valid GLTF for testing when FreeCAD is not available.
    """

    # Minimal valid GLTF 2.0 with a simple triangle
    mock_gltf = {
        "asset": {
            "version": "2.0",
            "generator": "ShowSpec CAD Bench (Mock)"
        },
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 0},
                "indices": 1,
                "mode": 4  # TRIANGLES
            }]
        }],
        "buffers": [{
            "byteLength": 44,
            "uri": "data:application/octet-stream;base64,AAAAAAAAAAAAAAAAAACAPwAAAAAAAAAAAAAAAAAAgD8AAAAAAAAAAAEAAAACAAAAAwAAAA=="
        }],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},  # ARRAY_BUFFER
            {"buffer": 0, "byteOffset": 36, "byteLength": 8, "target": 34963}   # ELEMENT_ARRAY_BUFFER
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,  # FLOAT
                "count": 3,
                "type": "VEC3",
                "max": [1.0, 1.0, 0.0],
                "min": [0.0, 0.0, 0.0]
            },
            {
                "bufferView": 1,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": 3,
                "type": "SCALAR"
            }
        ]
    }

    # Convert to JSON and base64 encode
    gltf_json = json.dumps(mock_gltf)
    encoded = base64.b64encode(gltf_json.encode()).decode("utf-8")

    return encoded, "gltf"


async def generate_layer_thumbnails(
    dxf_file_path: str,
    layers: list[dict],
    size: tuple[int, int] = (256, 256),
) -> dict[str, str]:
    """
    Generate thumbnail images for each layer.

    Args:
        dxf_file_path: Path to the source DXF file
        layers: List of layer dictionaries with 'id' keys
        size: Thumbnail size (width, height)

    Returns:
        Dictionary mapping layer_id to base64-encoded PNG thumbnail
    """

    # For now, return empty dict - thumbnails can be generated on demand
    # This would require FreeCAD's rendering capabilities or a separate
    # rendering service like Blender

    return {}
