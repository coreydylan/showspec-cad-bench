import time
from fastapi import APIRouter
from api.models import HealthResponse
from api.services.freecad_worker import get_freecad_version
from api.services.template_loader import get_loaded_templates_count

router = APIRouter()

# Import start_time from main module
_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for ALB and monitoring.

    Returns:
        HealthResponse with service status and version info
    """
    freecad_version = get_freecad_version()
    templates_count = get_loaded_templates_count()

    # Determine status
    if "Error" in freecad_version or "Not initialized" in freecad_version:
        status = "unhealthy"
    elif templates_count == 0:
        status = "degraded"
    else:
        status = "healthy"

    return HealthResponse(
        status=status,
        freecad_version=freecad_version,
        woodworking_wb_version="1.0",  # TODO: detect actual version
        templates_loaded=templates_count,
        uptime_seconds=time.time() - _start_time
    )
