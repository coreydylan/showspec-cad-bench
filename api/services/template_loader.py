"""
Template loader service.

Discovers and loads parametric templates from the templates directory.
"""

import os
from typing import Optional
from api.models import TemplateInfo, ComponentType

# Loaded templates cache
_templates: list[TemplateInfo] = []
_template_dir: Optional[str] = None


# Template metadata (could be loaded from each template file)
TEMPLATE_METADATA = {
    "wall_straight": {
        "name": "Straight Wall Panel",
        "description": "Standard flat wall panel with optional surface treatments",
        "parameters": ["width", "height", "depth"],
    },
    "wall_curved": {
        "name": "Curved Wall Panel",
        "description": "Curved wall panel using bendable or kerfed plywood",
        "parameters": ["width", "height", "depth", "radius", "arc_angle"],
    },
    "counter_straight": {
        "name": "Straight Counter",
        "description": "Counter or desk with surface and structure",
        "parameters": ["width", "height", "depth"],
    },
    "counter_curved": {
        "name": "Curved Counter",
        "description": "Curved counter or reception desk",
        "parameters": ["width", "height", "depth", "radius", "arc_angle"],
    },
    "circular_platform": {
        "name": "Circular Platform",
        "description": "Raised circular platform with radial support structure",
        "parameters": ["width", "height", "depth", "radius"],
    },
    "tower_square": {
        "name": "Square Tower",
        "description": "Square tower or column structure",
        "parameters": ["width", "height", "depth"],
    },
    "seg_lightbox": {
        "name": "SEG Lightbox",
        "description": "Backlit SEG fabric lightbox",
        "parameters": ["width", "height", "depth"],
    },
}


def load_templates(template_dir: str) -> int:
    """
    Load all templates from the template directory.

    Returns the number of templates loaded.
    """
    global _templates, _template_dir
    _template_dir = template_dir
    _templates = []

    if not os.path.exists(template_dir):
        print(f"WARNING: Template directory not found: {template_dir}")
        return 0

    # Scan for Python template files
    for filename in os.listdir(template_dir):
        if filename.endswith('.py') and not filename.startswith('_'):
            template_id = filename[:-3]  # Remove .py extension

            # Get metadata if available
            meta = TEMPLATE_METADATA.get(template_id, {
                "name": template_id.replace('_', ' ').title(),
                "description": f"Parametric {template_id} generator",
                "parameters": ["width", "height", "depth"],
            })

            # Map template_id to ComponentType
            try:
                component_type = ComponentType(template_id)
            except ValueError:
                component_type = ComponentType.CUSTOM

            template = TemplateInfo(
                id=template_id,
                name=meta["name"],
                description=meta["description"],
                component_type=component_type,
                parameters=meta["parameters"],
                thumbnail_url=None
            )
            _templates.append(template)

    print(f"Loaded {len(_templates)} templates from {template_dir}")
    return len(_templates)


def get_available_templates() -> list[TemplateInfo]:
    """Get list of all available templates."""
    return _templates


def get_loaded_templates_count() -> int:
    """Get count of loaded templates."""
    return len(_templates)


def get_template_path(template_id: str) -> Optional[str]:
    """Get the file path for a template."""
    if not _template_dir:
        return None

    path = os.path.join(_template_dir, f"{template_id}.py")
    if os.path.exists(path):
        return path
    return None
