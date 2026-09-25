from fastapi.testclient import TestClient

from app.main import app


def test_health_contract():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok", "service": "nexora-api", "version": "0.1.0"
        }


def test_openapi_includes_health_schema():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        assert "/api/v1/health" in schema["paths"]
        assert "HealthResponse" in schema["components"]["schemas"]
