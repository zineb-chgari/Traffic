# app/services/google_maps_service.py
import os
import requests
from datetime import datetime
from typing import Dict, List, Tuple


class GoogleMapsService:
    """
    Service pour interagir avec les nouvelles APIs Google Maps :
    - Routes API v2 pour itinéraires et trafic
    - Places API New pour stations de transport
    """

    def __init__(self, api_key: str = None):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("Google Maps API key is required")

    # ---------------- Routes API v2 ----------------
    def get_traffic_conditions(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict:
        """
        Récupère les conditions de trafic en utilisant Routes API v2
        """
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {"Content-Type": "application/json"}
        body = {
    "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}}, 
    "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}}, 
    "travelMode": "DRIVE",
    "computeAlternativeRoutes": False,
    "routingPreference": "TRAFFIC_AWARE"
}

        resp = requests.post(url, headers=headers, json=body, params={"key": self.api_key})
        data = resp.json()

        if resp.status_code != 200 or "routes" not in data:
            raise ValueError(f"Error fetching traffic: {data}")

        leg = data["routes"][0]["legs"][0]
        duration = leg["duration"]["seconds"]
        duration_in_traffic = leg.get("durationWithTraffic", {}).get("seconds", duration)
        traffic_factor = duration_in_traffic / duration if duration > 0 else 1.0

        return {
            "distance_meters": leg["distance"]["meters"],
            "duration_seconds": duration,
            "duration_with_traffic_seconds": duration_in_traffic,
            "traffic_factor": traffic_factor,
            "traffic_level": self._classify_traffic(traffic_factor)
        }

    def get_directions_transit(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime = None,
        transit_modes: List[str] = None
    ) -> List[Dict]:
        """
        Obtient les itinéraires de transport en commun via Routes API v2
        """
        if departure_time is None:
            departure_time = datetime.now()
        if transit_modes is None:
            transit_modes = ["BUS", "SUBWAY", "TRAM", "RAIL"]

        body = {
    "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}}, 
    "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}}, 
    "travelMode": "TRANSIT",
    "computeAlternativeRoutes": True,
    "transitPreferences": {"modes": transit_modes},
    "departureTime": departure_time.isoformat()
}


        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        resp = requests.post(url, json=body, params={"key": self.api_key})
        data = resp.json()

        routes_parsed = []
        for route in data.get("routes", []):
            leg = route["legs"][0]
            steps = []
            for step in leg.get("steps", []):
                steps.append({
                    "travel_mode": step.get("travelMode"),
                    "duration_seconds": step.get("duration", {}).get("seconds"),
                    "distance_meters": step.get("distance", {}).get("meters"),
                    "instructions": step.get("instruction", "")
                })
            routes_parsed.append({
                "summary": route.get("summary", ""),
                "total_duration_seconds": leg.get("duration", {}).get("seconds"),
                "total_distance_meters": leg.get("distance", {}).get("meters"),
                "departure_time": leg.get("departureTime", {}).get("text"),
                "arrival_time": leg.get("arrivalTime", {}).get("text"),
                "steps": steps
            })

        return routes_parsed

    # ---------------- Places API New ----------------
    def get_nearby_transit_stations(self, location: Tuple[float, float], radius: int = 500, station_type: str = "bus_station") -> List[Dict]:
        """
        Trouve les stations de transport à proximité (Places API New)
        """
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "key": self.api_key,
            "location": f"{location[0]},{location[1]}",
            "radius": radius,
            "type": station_type
        }
        resp = requests.get(url, params=params)
        data = resp.json()

        if resp.status_code != 200 or "results" not in data:
            raise ValueError(f"Error fetching nearby stations: {data}")

        stations = []
        for place in data["results"]:
            stations.append({
                "name": place["name"],
                "location": place["geometry"]["location"],
                "address": place.get("vicinity", ""),
                "rating": place.get("rating", 0),
                "types": place.get("types", [])
            })
        return stations

    # ---------------- Helper ----------------
    def _classify_traffic(self, traffic_factor: float) -> str:
        """
        Classifie le niveau de trafic selon le facteur
        """
        if traffic_factor < 1.1:
            return "low"
        elif traffic_factor < 1.3:
            return "moderate"
        elif traffic_factor < 1.6:
            return "heavy"
        else:
            return "severe"
