"""
Cost calculator service.

Calculates material and labor costs from a parts list.
"""

import json
import os
from typing import Optional
from api.models import Part, MaterialSummary, LaborOperation
from api.config import get_settings


# Material library cache
_material_library: dict = {}
_labor_rates: dict = {}


def _load_data():
    """Load material library and labor rates from JSON files."""
    global _material_library, _labor_rates

    settings = get_settings()

    # Load material library
    if os.path.exists(settings.material_library):
        with open(settings.material_library) as f:
            data = json.load(f)
            _material_library = data.get("materials", {})
    else:
        # Use defaults
        _material_library = _get_default_materials()

    # Load labor rates
    if os.path.exists(settings.labor_rates):
        with open(settings.labor_rates) as f:
            data = json.load(f)
            _labor_rates = data.get("labor_operations", {})
    else:
        # Use defaults
        _labor_rates = _get_default_labor_rates()


def _get_default_materials() -> dict:
    """Default material costs."""
    return {
        "plywood_3/4": {
            "name": "Plywood 3/4\"",
            "sheet_size": {"length": 96, "width": 48},
            "unit": "sheet",
            "cost_per_unit": 65.00,
            "aliases": ["Plywood 3/4", "3/4 Plywood"]
        },
        "laminate": {
            "name": "Laminate",
            "sheet_size": {"length": 120, "width": 60},
            "unit": "sheet",
            "cost_per_unit": 85.00,
            "aliases": ["Laminate", "HPL"]
        },
        "bendable_plywood": {
            "name": "Bendable Plywood 1/4\"",
            "sheet_size": {"length": 96, "width": 48},
            "unit": "sheet",
            "cost_per_unit": 55.00,
            "aliases": ["Bendable Plywood", "Wiggle Board"]
        }
    }


def _get_default_labor_rates() -> dict:
    """Default labor rates."""
    return {
        "carpentry_standard": {
            "name": "Carpentry (Standard)",
            "rate_per_hour": 75.00,
            "calc_methods": {"per_sqft": 0.02}
        },
        "laminate_application": {
            "name": "Laminate Application",
            "rate_per_hour": 65.00,
            "calc_methods": {"per_sqft": 0.015}
        }
    }


def _find_material(material_name: str) -> Optional[dict]:
    """Find material by name or alias."""
    if not _material_library:
        _load_data()

    # Direct match
    for key, mat in _material_library.items():
        if mat.get("name") == material_name:
            return mat
        if material_name in mat.get("aliases", []):
            return mat
        if material_name.lower() in key.lower():
            return mat

    # Fuzzy match
    material_lower = material_name.lower()
    for key, mat in _material_library.items():
        if any(alias.lower() in material_lower for alias in mat.get("aliases", [])):
            return mat

    return None


def _calculate_sheets_needed(parts: list[Part], material_name: str, material_info: dict) -> float:
    """Calculate number of sheets needed for parts of a specific material."""
    sheet_length = material_info.get("sheet_size", {}).get("length", 96)
    sheet_width = material_info.get("sheet_size", {}).get("width", 48)
    sheet_area = sheet_length * sheet_width

    # Sum up area for all parts of this material
    total_area = 0
    for part in parts:
        if material_name.lower() in part.material.lower():
            part_area = part.length * part.width * part.quantity
            # Add 10% waste factor
            total_area += part_area * 1.10

    # Calculate sheets needed (round up)
    sheets = total_area / sheet_area
    return max(1, round(sheets + 0.49, 0)) if total_area > 0 else 0


def calculate_costs(
    parts: list[Part],
    quantity: int = 1,
    material_overrides: Optional[dict] = None,
    labor_rate_overrides: Optional[dict] = None
) -> tuple[list[MaterialSummary], list[LaborOperation], dict]:
    """
    Calculate material and labor costs from a parts list.

    Returns:
        Tuple of (materials, labor, totals)
    """
    if not _material_library:
        _load_data()

    materials: list[MaterialSummary] = []
    labor: list[LaborOperation] = []
    material_cost = 0.0
    labor_cost = 0.0

    # Group parts by material
    material_groups: dict[str, list[Part]] = {}
    for part in parts:
        if part.material not in material_groups:
            material_groups[part.material] = []
        material_groups[part.material].append(part)

    # Calculate material costs
    for material_name, group_parts in material_groups.items():
        material_info = _find_material(material_name)

        if material_info:
            unit = material_info.get("unit", "sheet")
            cost_per_unit = material_info.get("cost_per_unit", 50.0)

            # Apply overrides
            if material_overrides and material_name in material_overrides:
                cost_per_unit = material_overrides[material_name]

            if unit == "sheet":
                qty = _calculate_sheets_needed(group_parts, material_name, material_info)
            else:
                # Calculate based on unit type
                qty = sum(p.length * p.width * p.quantity for p in group_parts)

            total = qty * cost_per_unit * quantity

            materials.append(MaterialSummary(
                material=material_name,
                total_quantity=qty * quantity,
                unit=unit,
                unit_cost=cost_per_unit,
                total_cost=total
            ))
            material_cost += total
        else:
            # Unknown material - estimate
            total_sqft = sum(p.length * p.width * p.quantity / 144 for p in group_parts)
            estimated_cost = total_sqft * 5.0 * quantity  # $5 per sqft default

            materials.append(MaterialSummary(
                material=material_name,
                total_quantity=total_sqft * quantity,
                unit="sqft",
                unit_cost=5.0,
                total_cost=estimated_cost
            ))
            material_cost += estimated_cost

    # Calculate labor costs
    total_sqft = sum(p.length * p.width * p.quantity / 144 for p in parts) * quantity

    # Standard carpentry labor
    carp_rate = _labor_rates.get("carpentry_standard", {})
    carp_hours = total_sqft * carp_rate.get("calc_methods", {}).get("per_sqft", 0.02)
    carp_rate_per_hour = carp_rate.get("rate_per_hour", 75.0)
    carp_cost = carp_hours * carp_rate_per_hour

    labor.append(LaborOperation(
        operation="Carpentry (Standard)",
        hours=round(carp_hours, 2),
        rate_per_hour=carp_rate_per_hour,
        total_cost=round(carp_cost, 2)
    ))
    labor_cost += carp_cost

    # Laminate application labor (if applicable)
    has_laminate = any("laminate" in p.material.lower() for p in parts)
    if has_laminate:
        lam_rate = _labor_rates.get("laminate_application", {})
        lam_sqft = sum(
            p.length * p.width * p.quantity / 144
            for p in parts if "laminate" in p.material.lower()
        ) * quantity
        lam_hours = lam_sqft * lam_rate.get("calc_methods", {}).get("per_sqft", 0.015)
        lam_rate_per_hour = lam_rate.get("rate_per_hour", 65.0)
        lam_cost = lam_hours * lam_rate_per_hour

        labor.append(LaborOperation(
            operation="Laminate Application",
            hours=round(lam_hours, 2),
            rate_per_hour=lam_rate_per_hour,
            total_cost=round(lam_cost, 2)
        ))
        labor_cost += lam_cost

    totals = {
        "material": round(material_cost, 2),
        "labor": round(labor_cost, 2),
        "total": round(material_cost + labor_cost, 2)
    }

    return materials, labor, totals
