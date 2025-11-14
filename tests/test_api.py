# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

client = TestClient(app)


# ----------------------
# Tests endpoints santé
# ----------------------
class TestHealthEndpoint:
    """Tests pour l'endpoint de santé"""

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_root_endpoint(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "endpoints" in data


# ----------------------
# Tests optimisation itinéraires
# ----------------------
class TestRoutesOptimization:
    """Tests pour l'optimisation d'itinéraires"""

    def test_optimize_routes_valid_request(self):
        payload = {
            "origin": {"latitude": 33.9716, "longitude": -6.8498},
            "destination": {"latitude": 33.5731, "longitude": -7.5898},
            "transit_modes": ["bus"]
        }
        response = client.post("/api/routes/optimize", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "optimized_route" in data
        assert isinstance(data["optimized_route"], list)
        assert len(data["optimized_route"]) > 1
        for point in data["optimized_route"]:
            assert "latitude" in point or "lat" in point
            assert "longitude" in point or "lng" in point

    def test_optimize_routes_invalid_coordinates(self):
        payload = {
            "origin": {"latitude": 999, "longitude": -6.8498},
            "destination": {"latitude": 33.5731, "longitude": -7.5898}
        }
        response = client.post("/api/routes/optimize", json=payload)
        assert response.status_code == 422

    def test_optimize_routes_missing_fields(self):
        payload = {
            "origin": {"latitude": 33.9716, "longitude": -6.8498}
        }
        response = client.post("/api/routes/optimize", json=payload)
        assert response.status_code == 422


# ----------------------
# Tests analyse densité
# ----------------------
class TestDensityAnalysis:
    """Tests pour l'analyse de densité"""

    def test_analyze_density_valid(self):
        payload = {
            "center": {"latitude": 33.9716, "longitude": -6.8498},
            "radius": 1000
        }
        response = client.post("/api/density/analyze", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "density" in data
        assert isinstance(data["density"], (int, float))

    def test_analyze_density_invalid_radius(self):
        payload = {
            "center": {"latitude": 33.9716, "longitude": -6.8498},
            "radius": 10000
        }
        response = client.post("/api/density/analyze", json=payload)
        assert response.status_code == 422


# ----------------------
# Tests conditions trafic
# ----------------------
class TestTrafficConditions:
    """Tests pour les conditions de trafic"""

    def test_get_traffic_conditions(self):
        response = client.get(
            "/api/traffic/conditions",
            params={
                "origin_lat": 33.9716,
                "origin_lng": -6.8498,
                "dest_lat": 33.5731,
                "dest_lng": -7.5898
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "duration" in data or "status" in data

    def test_get_traffic_missing_params(self):
        response = client.get("/api/traffic/conditions")
        assert response.status_code == 422


# ----------------------
# Tests stations à proximité
# ----------------------
class TestNearbyStations:
    """Tests pour la recherche de stations"""

    def test_get_nearby_stations(self):
        response = client.get(
            "/api/stations/nearby",
            params={
                "lat": 33.9716,
                "lng": -6.8498,
                "radius": 500
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "stations" in data
        assert isinstance(data["stations"], list)

    def test_get_nearby_stations_custom_type(self):
        response = client.get(
            "/api/stations/nearby",
            params={
                "lat": 33.9716,
                "lng": -6.8498,
                "station_type": "subway_station"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "stations" in data
        assert isinstance(data["stations"], list)


# ----------------------
# Tests d'intégration
# ----------------------
class TestIntegration:
    """Tests d'intégration bout en bout"""

    @pytest.mark.integration
    def test_full_route_optimization_flow(self):
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        density_origin = client.post(
            "/api/density/analyze",
            json={
                "center": {"latitude": 33.9716, "longitude": -6.8498},
                "radius": 500
            }
        )
        assert density_origin.status_code == 200
        assert "density" in density_origin.json()

        routes = client.post(
            "/api/routes/optimize",
            json={
                "origin": {"latitude": 33.9716, "longitude": -6.8498},
                "destination": {"latitude": 33.5731, "longitude": -7.5898},
                "transit_modes": ["bus", "tram"]
            }
        )
        assert routes.status_code == 200
        data = routes.json()
        assert "optimized_route" in data
        assert isinstance(data["optimized_route"], list)


# ----------------------
# Fixtures réutilisables
# ----------------------
@pytest.fixture
def sample_location():
    return {"latitude": 33.9716, "longitude": -6.8498}


@pytest.fixture
def sample_route_request(sample_location):
    return {
        "origin": sample_location,
        "destination": {"latitude": 33.5731, "longitude": -7.5898},
        "transit_modes": ["bus"]
    }
