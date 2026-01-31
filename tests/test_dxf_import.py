"""
Tests for DXF/DWG import endpoints.
"""

import pytest
import io
from httpx import AsyncClient, ASGITransport
from api.main import app
from api.models import DXFImportJobStatus


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def create_mock_dxf_content():
    """Create minimal valid DXF content for testing."""
    # Minimal DXF file structure (ASCII format)
    dxf_content = """0
SECTION
2
HEADER
0
ENDSEC
0
SECTION
2
TABLES
0
TABLE
2
LAYER
70
1
0
LAYER
2
WALLS
70
0
62
1
6
CONTINUOUS
0
ENDTAB
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
WALLS
10
0.0
20
0.0
30
0.0
11
10.0
21
0.0
31
0.0
0
ENDSEC
0
EOF
"""
    return dxf_content.encode('utf-8')


@pytest.mark.asyncio
async def test_upload_dxf(client):
    """Test uploading a DXF file."""
    async with client as c:
        # Create mock DXF file
        dxf_content = create_mock_dxf_content()

        response = await c.post(
            "/import/dxf/upload",
            files={"file": ("test_booth.dxf", io.BytesIO(dxf_content), "application/dxf")},
            data={"source_unit": "feet"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "jobId" in data
        assert data["status"] == "pending"
        assert data["message"] == "File uploaded, processing started"


@pytest.mark.asyncio
async def test_upload_invalid_file_type(client):
    """Test uploading an invalid file type."""
    async with client as c:
        response = await c.post(
            "/import/dxf/upload",
            files={"file": ("test.txt", io.BytesIO(b"not a dxf file"), "text/plain")},
            data={"source_unit": "feet"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]


@pytest.mark.asyncio
async def test_get_job_status(client):
    """Test getting job status."""
    async with client as c:
        # First upload a file
        dxf_content = create_mock_dxf_content()
        upload_response = await c.post(
            "/import/dxf/upload",
            files={"file": ("test_booth.dxf", io.BytesIO(dxf_content), "application/dxf")},
            data={"source_unit": "feet"}
        )

        assert upload_response.status_code == 200
        job_id = upload_response.json()["jobId"]

        # Get status
        status_response = await c.get(f"/import/dxf/jobs/{job_id}")
        assert status_response.status_code == 200
        data = status_response.json()

        assert "job" in data
        assert data["job"]["id"] == job_id
        assert data["job"]["fileName"] == "test_booth.dxf"


@pytest.mark.asyncio
async def test_get_nonexistent_job(client):
    """Test getting status for a non-existent job."""
    async with client as c:
        response = await c.get("/import/dxf/jobs/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_job(client):
    """Test deleting a job."""
    async with client as c:
        # First upload a file
        dxf_content = create_mock_dxf_content()
        upload_response = await c.post(
            "/import/dxf/upload",
            files={"file": ("test_booth.dxf", io.BytesIO(dxf_content), "application/dxf")},
            data={"source_unit": "feet"}
        )

        job_id = upload_response.json()["jobId"]

        # Delete the job
        delete_response = await c.delete(f"/import/dxf/jobs/{job_id}")
        assert delete_response.status_code == 200

        # Verify it's gone
        status_response = await c.get(f"/import/dxf/jobs/{job_id}")
        assert status_response.status_code == 404


@pytest.mark.asyncio
async def test_supported_file_formats(client):
    """Test that all supported file formats are accepted."""
    async with client as c:
        for ext in ["dxf", "dwg", "step", "stp", "iges", "igs"]:
            dxf_content = create_mock_dxf_content()
            response = await c.post(
                "/import/dxf/upload",
                files={"file": (f"test.{ext}", io.BytesIO(dxf_content), "application/octet-stream")},
                data={"source_unit": "feet"}
            )

            assert response.status_code == 200, f"Failed for extension: {ext}"


@pytest.mark.asyncio
async def test_layer_suggestion_patterns():
    """Test that layer name pattern matching works correctly."""
    from api.services.dxf_processor import suggest_layer_mapping

    # Test wall patterns
    suggestion = suggest_layer_mapping("WALLS")
    assert suggestion is not None
    assert suggestion.componentCategory == "walls"
    assert suggestion.componentType == "wall-panel"

    # Test counter patterns
    suggestion = suggest_layer_mapping("Reception_Counter")
    assert suggestion is not None
    assert suggestion.componentCategory == "counters"
    assert suggestion.componentType == "counter"

    # Test display patterns
    suggestion = suggest_layer_mapping("display_stands")
    assert suggestion is not None
    assert suggestion.componentCategory == "displays"

    # Test exclusion patterns
    suggestion = suggest_layer_mapping("People_Reference")
    assert suggestion is not None
    assert suggestion.componentCategory == "exclude"

    # Test unknown pattern
    suggestion = suggest_layer_mapping("XYZABC123")
    assert suggestion is None
