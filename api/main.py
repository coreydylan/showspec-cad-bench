import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.config import get_settings
from api.routers import calculate, import_file, templates, health, import_dxf

start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize FreeCAD, load templates
    from api.services.freecad_worker import initialize_freecad, set_template_dir, FREECAD_CMD
    from api.services.template_loader import load_templates
    from api.services.dxf_processor import set_freecad_cmd as set_dxf_freecad_cmd
    from api.services.gltf_exporter import set_freecad_cmd as set_gltf_freecad_cmd

    settings = get_settings()
    initialize_freecad(settings.freecad_path)
    set_template_dir(settings.template_dir)
    load_templates(settings.template_dir)

    # Share FreeCAD path with DXF processor and GLTF exporter
    from api.services.freecad_worker import FREECAD_CMD
    set_dxf_freecad_cmd(FREECAD_CMD)
    set_gltf_freecad_cmd(FREECAD_CMD)

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="ShowSpec CAD Bench",
    description="FreeCAD-powered cut list and BOM generation service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for ShowSpec frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://showspec.cc", "https://cad.showspec.cc", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(calculate.router, prefix="/calculate", tags=["Calculate"])
app.include_router(import_file.router, prefix="/import", tags=["Import"])
app.include_router(import_dxf.router, prefix="/import", tags=["DXF Import"])
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    return {
        "service": "ShowSpec CAD Bench",
        "version": "1.0.0",
        "docs": "/docs"
    }
