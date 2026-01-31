"""
Cut list generator service.

Wrapper around FreeCAD Woodworking Workbench tools.
"""

from typing import Optional
from api.models import Part


def extract_cut_list_from_document(doc) -> list[Part]:
    """
    Extract cut list from a FreeCAD document.

    Uses the getDimensions function from Woodworking Workbench if available,
    otherwise falls back to manual geometry extraction.

    Args:
        doc: FreeCAD Document object

    Returns:
        List of Part objects
    """
    parts = []

    for obj in doc.Objects:
        if not hasattr(obj, "Shape"):
            continue

        # Get bounding box dimensions
        bbox = obj.Shape.BoundBox

        # Sort dimensions to get length > width > thickness
        dims = sorted([bbox.XLength, bbox.YLength, bbox.ZLength], reverse=True)

        # Get material from object property or default
        material = "Unknown"
        if hasattr(obj, "Material"):
            material = obj.Material
        elif hasattr(obj, "Label"):
            # Try to infer from label
            label = obj.Label.lower()
            if "plywood" in label:
                material = "Plywood 3/4"
            elif "laminate" in label:
                material = "Laminate"

        # Get grain direction
        grain = "any"
        if hasattr(obj, "GrainDirection"):
            grain = obj.GrainDirection

        part = Part(
            label=obj.Label,
            length=dims[0],
            width=dims[1],
            thickness=dims[2],
            material=material,
            quantity=1,
            grain_direction=grain,
            notes=None
        )
        parts.append(part)

    return parts


def optimize_for_sheet_goods(parts: list[Part], sheet_width: float = 48, sheet_length: float = 96) -> dict:
    """
    Optimize parts layout for cutting from sheet goods.

    Returns nesting suggestions and waste calculations.

    Args:
        parts: List of parts to nest
        sheet_width: Sheet width in inches (default 48")
        sheet_length: Sheet length in inches (default 96")

    Returns:
        dict with nesting info and waste percentage
    """
    # Group parts by material and thickness
    groups: dict[str, list[Part]] = {}
    for part in parts:
        key = f"{part.material}_{part.thickness}"
        if key not in groups:
            groups[key] = []
        groups[key].append(part)

    results = {}
    for key, group_parts in groups.items():
        sheet_area = sheet_width * sheet_length
        total_part_area = sum(p.length * p.width * p.quantity for p in group_parts)

        # Simple sheet calculation (actual nesting would be more complex)
        sheets_needed = (total_part_area / sheet_area) * 1.15  # 15% waste factor

        results[key] = {
            "parts": len(group_parts),
            "total_area_sqin": total_part_area,
            "sheets_needed": max(1, round(sheets_needed + 0.49)),
            "estimated_waste_pct": 15.0
        }

    return results
