import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app
from api.models import ComponentType


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_calculate_straight_wall(client):
    async with client as c:
        response = await c.post("/calculate", json={
            "component_type": "wall_straight",
            "dimensions": {
                "width": 120,  # 10 feet
                "height": 96,  # 8 feet
                "depth": 0.75
            },
            "surfaces": {
                "front": "laminate",
                "back": "raw",
                "sides": "laminate"
            },
            "quantity": 1
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert len(data["parts"]) > 0
        assert data["total_cost"] > 0

        # Should have plywood and laminate
        materials = [p["material"] for p in data["parts"]]
        assert any("Plywood" in m for m in materials)


@pytest.mark.asyncio
async def test_calculate_with_quantity(client):
    async with client as c:
        response = await c.post("/calculate", json={
            "component_type": "wall_straight",
            "dimensions": {
                "width": 48,
                "height": 96,
                "depth": 0.75
            },
            "quantity": 5
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        # Cost should be higher with quantity > 1
        assert data["total_cost"] > 0


@pytest.mark.asyncio
async def test_health_check(client):
    async with client as c:
        response = await c.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


@pytest.mark.asyncio
async def test_root_endpoint(client):
    async with client as c:
        response = await c.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ShowSpec CAD Bench"


@pytest.mark.asyncio
async def test_templates_list(client):
    async with client as c:
        response = await c.get("/templates")
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data


@pytest.mark.asyncio
async def test_invalid_component_type(client):
    async with client as c:
        response = await c.post("/calculate", json={
            "component_type": "invalid_type",
            "dimensions": {
                "width": 48,
                "height": 96,
                "depth": 0.75
            }
        })

        # Should return 422 for invalid enum value
        assert response.status_code == 422
