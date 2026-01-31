from fastapi import APIRouter
from api.models import TemplatesResponse, TemplateInfo, ComponentType
from api.services.template_loader import get_available_templates

router = APIRouter()


@router.get("", response_model=TemplatesResponse)
async def list_templates():
    """
    List all available parametric templates.

    Returns template metadata including:
    - Component type
    - Available parameters
    - Description
    """
    templates = get_available_templates()
    return TemplatesResponse(templates=templates)


@router.get("/{template_id}", response_model=TemplateInfo)
async def get_template(template_id: str):
    """
    Get details for a specific template.
    """
    templates = get_available_templates()
    for template in templates:
        if template.id == template_id:
            return template

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
