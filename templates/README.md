# Parametric Templates

Each template is a Python module that can be executed by FreeCAD in headless mode.

## Template Interface

Every template must implement two functions:

### `generate_component(dimensions: dict, surfaces: dict | None) -> FreeCAD.Document`

Creates the FreeCAD geometry based on the input parameters.

**Arguments:**
- `dimensions`: Dictionary with:
  - `width`: Width in inches
  - `height`: Height in inches
  - `depth`: Depth/thickness in inches
  - `radius`: (optional) Curve radius in inches
  - `arc_angle`: (optional) Arc angle in degrees
- `surfaces`: (optional) Dictionary with surface treatments:
  - `front`, `back`, `sides`, `top`, `bottom`: Surface treatment type

**Returns:** FreeCAD Document with geometry objects

### `get_cut_list(doc: FreeCAD.Document) -> dict`

Extracts the cut list from the generated document.

**Returns:** Dictionary with structure:
```python
{
    "parts": [
        {
            "label": "PartName",
            "length": 120.0,  # inches
            "width": 96.0,    # inches
            "thickness": 0.75,  # inches
            "material": "Plywood 3/4",
            "quantity": 1,
            "grain_direction": "length",  # "length", "width", or "any"
            "notes": "Optional notes"
        },
        ...
    ]
}
```

## Adding Custom Properties

To ensure parts are properly extracted, add these properties to FreeCAD objects:

```python
obj.addProperty("App::PropertyString", "Material", "CutList")
obj.Material = "Plywood 3/4"

obj.addProperty("App::PropertyString", "PartType", "CutList")
obj.PartType = "Panel"  # Panel, Rib, Frame, etc.
```

## Available Templates

- `wall_straight.py` - Standard flat wall panel
- `wall_curved.py` - Curved wall using bendable/kerfed plywood
- `counter_straight.py` - Straight counter or desk
- `counter_curved.py` - Curved counter or reception desk
- `circular_platform.py` - Raised circular platform
- `tower_square.py` - Square tower/column
- `seg_lightbox.py` - Backlit SEG fabric lightbox
