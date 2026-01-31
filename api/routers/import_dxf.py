"""
DXF/DWG Import Router

Endpoints for importing DXF/DWG files and extracting layer information.
"""

import tempfile
import os
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks

from api.models import (
    DXFImportJob,
    DXFImportJobStatus,
    DXFUploadResponse,
    DXFJobStatusResponse,
    DXFLayersResponse,
    DXFPreviewRequest,
    DXFPreviewResponse,
    CADLayer,
)
from api.services.job_store import get_job_store
from api.services.dxf_processor import process_dxf_file
from api.services.gltf_exporter import generate_gltf_preview


router = APIRouter()


async def _process_dxf_job(job_id: str, file_path: str, source_unit: str = "feet"):
    """Background task to process a DXF file."""
    store = get_job_store()

    try:
        # Update status to processing
        store.update_job(
            job_id,
            status=DXFImportJobStatus.PROCESSING,
            progress=10,
            message="Starting DXF processing..."
        )

        await asyncio.sleep(0.1)  # Allow status update to propagate

        # Update to extracting layers
        store.update_job(
            job_id,
            status=DXFImportJobStatus.EXTRACTING_LAYERS,
            progress=30,
            message="Extracting layer information..."
        )

        # Process the DXF file
        layers = await process_dxf_file(file_path, source_unit)

        # Update to converting geometry
        store.update_job(
            job_id,
            status=DXFImportJobStatus.CONVERTING_GEOMETRY,
            progress=60,
            message="Converting geometry..."
        )

        await asyncio.sleep(0.1)

        # Update to optimizing
        store.update_job(
            job_id,
            status=DXFImportJobStatus.OPTIMIZING,
            progress=80,
            message="Optimizing for preview..."
        )

        await asyncio.sleep(0.1)

        # Mark as ready for mapping
        store.update_job(
            job_id,
            status=DXFImportJobStatus.READY_FOR_MAPPING,
            progress=100,
            message="Ready for layer mapping",
            layers=layers
        )

    except Exception as e:
        store.update_job(
            job_id,
            status=DXFImportJobStatus.FAILED,
            progress=0,
            message=f"Processing failed: {str(e)}",
            error=str(e)
        )

    finally:
        # Clean up temp file
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass


@router.post("/dxf/upload", response_model=DXFUploadResponse)
async def upload_dxf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_unit: str = Form("feet"),
):
    """
    Upload a DXF/DWG file and start processing.

    Accepts DXF, DWG, STEP, or IGES files and begins background processing
    to extract layer information.

    Args:
        file: The CAD file to upload
        source_unit: Unit of the source file (millimeters, centimeters, meters, inches, feet)

    Returns:
        Job ID and initial status
    """

    # Validate file extension
    filename = file.filename or "unknown"
    extension = filename.lower().split(".")[-1] if "." in filename else ""

    valid_extensions = {"dxf", "dwg", "step", "stp", "iges", "igs"}
    if extension not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Supported formats: {', '.join(valid_extensions)}"
        )

    # Normalize format
    format_map = {"stp": "step", "igs": "iges"}
    file_format = format_map.get(extension, extension)

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Write to temp file
    suffix = f".{extension}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name

    # Create job
    store = get_job_store()
    job = store.create_job(
        file_name=filename,
        file_size=file_size,
        file_format=file_format,
        temp_file_path=temp_path,
    )

    # Start background processing
    background_tasks.add_task(_process_dxf_job, job.id, temp_path, source_unit)

    return DXFUploadResponse(
        jobId=job.id,
        status=job.status,
        message="File uploaded, processing started"
    )


@router.get("/dxf/jobs/{job_id}", response_model=DXFJobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a DXF import job.

    Args:
        job_id: The job ID returned from upload

    Returns:
        Current job status and data
    """

    store = get_job_store()
    job = store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    return DXFJobStatusResponse(job=job)


@router.get("/dxf/jobs/{job_id}/layers", response_model=DXFLayersResponse)
async def get_job_layers(job_id: str):
    """
    Get extracted layers for a completed job.

    Args:
        job_id: The job ID

    Returns:
        List of CAD layers with suggested mappings
    """

    store = get_job_store()
    job = store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    if job.status == DXFImportJobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Job failed: {job.error}"
        )

    if job.status not in [
        DXFImportJobStatus.READY_FOR_MAPPING,
        DXFImportJobStatus.IMPORTING,
        DXFImportJobStatus.COMPLETED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready. Current status: {job.status.value}"
        )

    if not job.layers:
        raise HTTPException(
            status_code=500,
            detail="Layers not available"
        )

    return DXFLayersResponse(
        jobId=job.id,
        layers=job.layers
    )


@router.post("/dxf/jobs/{job_id}/preview", response_model=DXFPreviewResponse)
async def generate_preview(
    job_id: str,
    request: DXFPreviewRequest,
):
    """
    Generate a GLTF preview for a job.

    Args:
        job_id: The job ID
        request: Preview options (layer IDs to include, quality)

    Returns:
        Base64-encoded GLTF/GLB content
    """

    store = get_job_store()
    job = store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    if job.status == DXFImportJobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Job failed: {job.error}"
        )

    # Get the file path
    file_path = store.get_file_path(job_id)

    # If file no longer exists (cleaned up), try to recreate from original
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=400,
            detail="Source file no longer available. Please re-upload."
        )

    try:
        # Generate GLTF preview
        encoded_content, format_type = await generate_gltf_preview(
            dxf_file_path=file_path,
            layer_ids=request.layerIds,
            quality=request.quality,
            output_format="glb",
        )

        # Create data URL
        mime_type = "model/gltf-binary" if format_type == "glb" else "model/gltf+json"
        preview_url = f"data:{mime_type};base64,{encoded_content}"

        # Update job with preview URL
        store.update_job(job_id, preview_url=preview_url)

        return DXFPreviewResponse(
            jobId=job_id,
            previewUrl=preview_url,
            format=format_type
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Preview generation failed: {str(e)}"
        )


@router.delete("/dxf/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a job and clean up resources.

    Args:
        job_id: The job ID

    Returns:
        Confirmation of deletion
    """

    store = get_job_store()

    # Get file path before deletion
    file_path = store.get_file_path(job_id)

    # Delete job
    if not store.delete_job(job_id):
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    # Clean up file if it exists
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except Exception:
            pass

    return {"message": f"Job {job_id} deleted"}
