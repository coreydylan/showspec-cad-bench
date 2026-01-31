"""
Parametric straight wall panel generator.

Creates a wall panel with:
- Plywood core (3/4" or as specified)
- Optional surface treatments (front/back/sides)
- Proper cut list for shop fabrication
"""

try:
    import FreeCAD
    import Part
    FREECAD_AVAILABLE = True
except ImportError:
    FREECAD_AVAILABLE = False

from typing import Optional

# Material thickness constants (inches)
PLYWOOD_THICKNESS = 0.75
LAMINATE_THICKNESS = 0.05
FABRIC_THICKNESS = 0.1


def generate_component(dimensions: dict, surfaces: Optional[dict] = None):
    """
    Generate a straight wall panel.

    Args:
        dimensions: {width, height, depth}
        surfaces: {front, back, sides, top, bottom}

    Returns:
        FreeCAD Document with the wall geometry (or mock data if FreeCAD not available)
    """
    if not FREECAD_AVAILABLE:
        return _mock_generate(dimensions, surfaces)

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


def get_cut_list(doc) -> dict:
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
    if not FREECAD_AVAILABLE:
        return doc  # Mock data is already in the right format

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


def _mock_generate(dimensions: dict, surfaces: Optional[dict] = None) -> dict:
    """Generate mock cut list data when FreeCAD is not available."""
    parts = []

    width = dimensions["width"]
    height = dimensions["height"]
    depth = dimensions.get("depth", PLYWOOD_THICKNESS)

    # Main plywood panel
    parts.append({
        "label": "PlywoodCore",
        "length": width,
        "width": height,
        "thickness": depth,
        "material": "Plywood 3/4",
        "quantity": 1,
        "grain_direction": "length",
        "notes": None
    })

    # Surface treatments
    if surfaces:
        if surfaces.get("front") == "laminate":
            parts.append({
                "label": "FrontLaminate",
                "length": width,
                "width": height,
                "thickness": LAMINATE_THICKNESS,
                "material": "Laminate",
                "quantity": 1,
                "grain_direction": "any",
                "notes": None
            })

        if surfaces.get("back") == "laminate":
            parts.append({
                "label": "BackLaminate",
                "length": width,
                "width": height,
                "thickness": LAMINATE_THICKNESS,
                "material": "Laminate",
                "quantity": 1,
                "grain_direction": "any",
                "notes": None
            })

    return {"parts": parts}
