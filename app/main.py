# app/main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple
from datetime import datetime
import os
from dotenv import load_dotenv

from .Services.google_maps_service import GoogleMapsService
from .Services.density_analyzer import DensityAnalyzer
from .Services.route_optimizer import RouteOptimizer

# Charger variables d'environnement
load_dotenv()

# Initialiser FastAPI
app = FastAPI(
    title="Smart Transport Optimizer API",
    description="API intelligente d'optimisation des transports publics",
    version="1.0.0"
)

# CORS pour permettre les requêtes cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialiser les services
maps_service = GoogleMapsService()
density_analyzer = DensityAnalyzer(maps_service)
route_optimizer = RouteOptimizer(maps_service, density_analyzer)


# ==================== Modèles Pydantic ====================

class Location(BaseModel):
    """Modèle pour une localisation"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)


class RouteRequest(BaseModel):
    """Requête pour trouver des itinéraires"""
    origin: Location
    destination: Location
    departure_time: Optional[datetime] = None
    transit_modes: Optional[List[str]] = Field(
        default=['bus', 'subway', 'tram'],
        description="Types de transport souhaités"
    )


class DensityRequest(BaseModel):
    """Requête pour analyser la densité"""
    center: Location
    radius: int = Field(default=1000, ge=100, le=5000, description="Rayon en mètres")


class AreaBounds(BaseModel):
    """Limites d'une zone géographique"""
    southwest: Location
    northeast: Location


class NewRouteRequest(BaseModel):
    """Requête pour suggérer un nouveau trajet"""
    area_bounds: AreaBounds
    vehicle_type: str = Field(default='bus', description="Type de véhicule")


# ==================== Endpoints ====================

@app.get("/")
async def root():
    """Endpoint racine avec info API"""
    return {
        "name": "Smart Transport Optimizer API",
        "version": "1.0.0",
        "endpoints": {
            "routes": "/api/routes/optimize",
            "density": "/api/density/analyze",
            "traffic": "/api/traffic/conditions",
            "suggest": "/api/routes/suggest"
        }
    }


@app.post("/api/routes/optimize")
async def optimize_routes(request: RouteRequest):
    """
    Trouve et optimise les itinéraires de transport
    
    Analyse les itinéraires disponibles en tenant compte de:
    - Temps de trajet
    - Conditions de trafic
    - Densité urbaine
    - Connectivité des transports
    """
    try:
        routes = route_optimizer.find_optimal_routes(
            origin=request.origin.to_tuple(),
            destination=request.destination.to_tuple(),
            departure_time=request.departure_time,
            preferences={'transit_modes': request.transit_modes}
        )
        
        if not routes:
            raise HTTPException(
                status_code=404,
                detail="Aucun itinéraire trouvé pour cette requête"
            )
        
        # Ajouter une comparaison
        comparison = route_optimizer.compare_routes(routes)
        
        return {
            "status": "success",
            "query": {
                "origin": request.origin.dict(),
                "destination": request.destination.dict(),
                "departure_time": request.departure_time
            },
            "routes_found": len(routes),
            "routes": routes,
            "comparison": comparison
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/api/density/analyze")
async def analyze_density(request: DensityRequest):
    """
    Analyse la densité urbaine d'une zone
    
    Retourne:
    - Score de densité
    - Points d'intérêt
    - Niveau de densité
    """
    try:
        density = density_analyzer.calculate_area_density(
            center=request.center.to_tuple(),
            radius=request.radius
        )
        
        connectivity = density_analyzer.calculate_connectivity_score(
            location=request.center.to_tuple()
        )
        
        return {
            "status": "success",
            "location": request.center.dict(),
            "radius_meters": request.radius,
            "density": density,
            "connectivity": connectivity
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.get("/api/traffic/conditions")
async def get_traffic_conditions(
    origin_lat: float = Query(..., description="Latitude origine"),
    origin_lng: float = Query(..., description="Longitude origine"),
    dest_lat: float = Query(..., description="Latitude destination"),
    dest_lng: float = Query(..., description="Longitude destination")
):
    """
    Obtient les conditions de trafic entre deux points
    
    Retourne:
    - Durée estimée
    - Niveau de trafic
    - Distance
    """
    try:
        traffic = maps_service.get_traffic_conditions(
            origin=(origin_lat, origin_lng),
            destination=(dest_lat, dest_lng)
        )
        
        if not traffic:
            raise HTTPException(
                status_code=404,
                detail="Impossible d'obtenir les données de trafic"
            )
        
        return {
            "status": "success",
            "origin": {"latitude": origin_lat, "longitude": origin_lng},
            "destination": {"latitude": dest_lat, "longitude": dest_lng},
            "traffic": traffic
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.post("/api/routes/suggest")
async def suggest_new_route(request: NewRouteRequest):
    """
    Suggère un nouvel itinéraire de transport basé sur l'analyse de demande
    
    Identifie les zones à forte densité et propose un trajet optimal
    """
    try:
        suggestion = route_optimizer.suggest_new_route(
            area_bounds=(
                request.area_bounds.southwest.to_tuple(),
                request.area_bounds.northeast.to_tuple()
            ),
            vehicle_type=request.vehicle_type
        )
        
        return {
            "status": "success",
            "area_analyzed": {
                "southwest": request.area_bounds.southwest.dict(),
                "northeast": request.area_bounds.northeast.dict()
            },
            "suggestion": suggestion
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


@app.get("/api/stations/nearby")
async def get_nearby_stations(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: int = Query(default=500, ge=100, le=2000, description="Rayon en mètres"),
    station_type: str = Query(default='bus_station', description="Type de station")
):
    """
    Trouve les stations de transport à proximité
    """
    try:
        stations = maps_service.get_nearby_transit_stations(
            location=(lat, lng),
            radius=radius,
            transit_type=station_type
        )
        
        return {
            "status": "success",
            "location": {"latitude": lat, "longitude": lng},
            "radius_meters": radius,
            "stations_found": len(stations),
            "stations": stations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")


# ==================== Santé de l'API ====================

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "google_maps": "connected" if maps_service.api_key else "not_configured"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)