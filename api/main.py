import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.config import get_settings
from api.routers import calculate, import_file, templates, health

start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize FreeCAD, load templates
    from api.services.freecad_worker import initialize_freecad, set_template_dir
    from api.services.template_loader import load_templates

    settings = get_settings()
    initialize_freecad(settings.freecad_path)
    set_template_dir(settings.template_dir)
    load_templates(settings.template_dir)

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
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root():
    return {
        "service": "ShowSpec CAD Bench",
        "version": "1.0.0",
        "docs": "/docs"
    }
