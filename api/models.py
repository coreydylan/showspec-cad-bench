from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class ComponentType(str, Enum):
    WALL_STRAIGHT = "wall_straight"
    WALL_CURVED = "wall_curved"
    COUNTER_STRAIGHT = "counter_straight"
    COUNTER_CURVED = "counter_curved"
    CIRCULAR_PLATFORM = "circular_platform"
    TOWER_SQUARE = "tower_square"
    SEG_LIGHTBOX = "seg_lightbox"
    CUSTOM = "custom"


class SurfaceTreatment(str, Enum):
    LAMINATE = "laminate"
    PAINT = "paint"
    FABRIC_SEG = "fabric_seg"
    FABRIC_WRAPPED = "fabric_wrapped"
    VINYL = "vinyl"
    RAW = "raw"


class Dimensions(BaseModel):
    width: float = Field(..., description="Width in inches")
    height: float = Field(..., description="Height in inches")
    depth: float = Field(..., description="Depth/thickness in inches")
    radius: Optional[float] = Field(None, description="Curve radius in inches (for curved components)")
    arc_angle: Optional[float] = Field(None, description="Arc angle in degrees (for curved components)")


class SurfaceConfig(BaseModel):
    front: SurfaceTreatment = SurfaceTreatment.LAMINATE
    back: SurfaceTreatment = SurfaceTreatment.RAW
    sides: SurfaceTreatment = SurfaceTreatment.LAMINATE
    top: Optional[SurfaceTreatment] = None
    bottom: Optional[SurfaceTreatment] = None


class CalculateRequest(BaseModel):
    component_type: ComponentType
    dimensions: Dimensions
    surfaces: Optional[SurfaceConfig] = None
    quantity: int = Field(1, ge=1)

    # Optional overrides
    material_overrides: Optional[dict] = None
    labor_rate_overrides: Optional[dict] = None


class Part(BaseModel):
    label: str
    length: float  # inches
    width: float   # inches
    thickness: float  # inches
    material: str
    quantity: int
    grain_direction: Optional[Literal["length", "width", "any"]] = "any"
    notes: Optional[str] = None


class MaterialSummary(BaseModel):
    material: str
    total_quantity: float
    unit: str  # "sheet", "sqft", "linear_ft", "gallon", etc.
    unit_cost: float
    total_cost: float


class LaborOperation(BaseModel):
    operation: str
    hours: float
    rate_per_hour: float
    total_cost: float


class CutListResponse(BaseModel):
    success: bool
    component_type: str
    dimensions: Dimensions

    # Cut list
    parts: list[Part]

    # Rollups
    materials: list[MaterialSummary]
    labor: list[LaborOperation]

    # Totals
    material_cost: float
    labor_cost: float
    total_cost: float

    # Metadata
    calculation_time_ms: float
    template_used: str
    warnings: list[str] = []


class ImportRequest(BaseModel):
    """For importing user's own .FCStd files"""
    filename: str
    file_content_base64: str


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    component_type: ComponentType
    parameters: list[str]  # e.g., ["width", "height", "depth", "radius"]
    thumbnail_url: Optional[str] = None


class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    freecad_version: str
    woodworking_wb_version: str
    templates_loaded: int
    uptime_seconds: float


# =============================================================================
# DXF/DWG Import Models
# =============================================================================

class DXFImportJobStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    EXTRACTING_LAYERS = "extracting_layers"
    CONVERTING_GEOMETRY = "converting_geometry"
    OPTIMIZING = "optimizing"
    READY_FOR_MAPPING = "ready_for_mapping"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class DXFLayerBounds(BaseModel):
    minX: float
    minY: float
    minZ: float
    maxX: float
    maxY: float
    maxZ: float


class DXFLayerDimensions(BaseModel):
    width: float  # feet
    height: float  # feet
    depth: float  # feet


class LayerMappingSuggestion(BaseModel):
    componentCategory: str  # ComponentCategory | 'custom' | 'exclude'
    componentType: str  # e.g., 'wall-panel', 'counter', 'display-stand'
    confidence: float  # 0-1
    reasoning: str


class CADLayer(BaseModel):
    id: str
    name: str
    originalName: str  # Raw name from file
    color: str  # Hex color from CAD
    entityCount: int
    vertexCount: int
    bounds: DXFLayerBounds
    dimensions: DXFLayerDimensions
    previewUrl: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    meshCount: int
    isVisible: bool
    suggestedMapping: Optional[LayerMappingSuggestion] = None


class DXFImportJob(BaseModel):
    id: str
    status: DXFImportJobStatus
    progress: int  # 0-100
    message: str
    createdAt: str
    updatedAt: str
    fileName: str
    fileSize: int
    fileFormat: Literal["dxf", "dwg", "step", "iges"]
    layers: Optional[list[CADLayer]] = None
    previewUrl: Optional[str] = None
    error: Optional[str] = None


class DXFUploadResponse(BaseModel):
    jobId: str
    status: DXFImportJobStatus
    message: str


class DXFJobStatusResponse(BaseModel):
    job: DXFImportJob


class DXFLayersResponse(BaseModel):
    jobId: str
    layers: list[CADLayer]


class DXFPreviewRequest(BaseModel):
    layerIds: Optional[list[str]] = None  # If None, preview all layers
    quality: Literal["low", "medium", "high"] = "medium"


class DXFPreviewResponse(BaseModel):
    jobId: str
    previewUrl: str
    format: str  # "gltf" or "glb"
