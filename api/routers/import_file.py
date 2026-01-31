import base64
import tempfile
import os
from fastapi import APIRouter, HTTPException
from api.models import ImportRequest, CutListResponse, Dimensions
from api.services.freecad_worker import run_import_calculation
from api.services.cost_calculator import calculate_costs

router = APIRouter()


@router.post("", response_model=CutListResponse)
async def import_and_calculate(request: ImportRequest):
    """
    Import a user-uploaded .FCStd file and calculate its cut list.

    Accepts base64-encoded FreeCAD file content and returns the cut list.
    """
    # Validate filename
    if not request.filename.endswith('.FCStd'):
        raise HTTPException(
            status_code=400,
            detail="File must be a FreeCAD document (.FCStd)"
        )

    try:
        # Decode base64 content
        file_content = base64.b64decode(request.file_content_base64)

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.FCStd', delete=False) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            # Run calculation on imported file
            parts = await run_import_calculation(temp_path)

            # Calculate costs
            materials, labor, totals = calculate_costs(
                parts=parts,
                quantity=1
            )

            # Create dummy dimensions for imported files
            dimensions = Dimensions(width=0, height=0, depth=0)

            return CutListResponse(
                success=True,
                component_type="custom",
                dimensions=dimensions,
                parts=parts,
                materials=materials,
                labor=labor,
                material_cost=totals["material"],
                labor_cost=totals["labor"],
                total_cost=totals["total"],
                calculation_time_ms=0,
                template_used=request.filename,
                warnings=["Dimensions extracted from imported file"]
            )

        finally:
            os.unlink(temp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
