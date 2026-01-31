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
