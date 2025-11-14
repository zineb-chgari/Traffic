# app/services/density_analyzer.py
import numpy as np
from typing import Dict, List, Tuple
from shapely.geometry import Point, Polygon
import geopandas as gpd

class DensityAnalyzer:
    """
    Analyse la densité urbaine pour optimiser les itinéraires
    Prend en compte: population, POIs, commerces, bureaux
    """
    
    def __init__(self, google_maps_service):
        """
        Args:
            google_maps_service: Instance du service Google Maps
        """
        self.maps_service = google_maps_service
    
    def calculate_area_density(
        self,
        center: Tuple[float, float],
        radius: int = 1000
    ) -> Dict:
        """
        Calcule la densité d'une zone circulaire
        
        Args:
            center: Coordonnées du centre (lat, lng)
            radius: Rayon en mètres
        
        Returns:
            Score de densité et détails
        """
        # Recherche des POIs (Points d'Intérêt)
        poi_types = [
            'school', 'hospital', 'shopping_mall', 
            'restaurant', 'cafe', 'store',
            'university', 'bank', 'gym'
        ]
        
        total_pois = 0
        poi_breakdown = {}
        
        for poi_type in poi_types:
            pois = self.maps_service.client.places_nearby(
                location=center,
                radius=radius,
                type=poi_type
            )
            count = len(pois.get('results', []))
            total_pois += count
            poi_breakdown[poi_type] = count
        
        # Calcul du score de densité (0-100)
        # Formule: plus il y a de POIs, plus la densité est élevée
        density_score = min(100, (total_pois / radius) * 10000)
        
        return {
            'density_score': round(density_score, 2),
            'total_pois': total_pois,
            'poi_breakdown': poi_breakdown,
            'density_level': self._classify_density(density_score)
        }
    
    def analyze_route_corridor(
        self,
        waypoints: List[Tuple[float, float]],
        corridor_width: int = 500
    ) -> Dict:
        """
        Analyse la densité le long d'un corridor de route
        
        Args:
            waypoints: Liste de points formant la route
            corridor_width: Largeur du corridor en mètres
        
        Returns:
            Analyse de densité du corridor
        """
        densities = []
        
        # Échantillonnage de points le long du corridor
        for waypoint in waypoints:
            density = self.calculate_area_density(waypoint, corridor_width)
            densities.append(density['density_score'])
        
        avg_density = np.mean(densities)
        max_density = np.max(densities)
        min_density = np.min(densities)
        
        # Variance pour détecter les zones inégales
        density_variance = np.var(densities)
        
        return {
            'average_density': round(avg_density, 2),
            'max_density': round(max_density, 2),
            'min_density': round(min_density, 2),
            'density_variance': round(density_variance, 2),
            'density_samples': densities,
            'uniformity': 'uniform' if density_variance < 100 else 'variable'
        }
    
    def identify_high_demand_zones(
        self,
        area_bounds: Tuple[Tuple[float, float], Tuple[float, float]],
        grid_size: int = 10
    ) -> List[Dict]:
        """
        Identifie les zones à forte demande dans une région
        
        Args:
            area_bounds: ((lat_min, lng_min), (lat_max, lng_max))
            grid_size: Nombre de divisions de la grille
        
        Returns:
            Liste des zones à forte demande
        """
        (lat_min, lng_min), (lat_max, lng_max) = area_bounds
        
        # Créer une grille
        lat_step = (lat_max - lat_min) / grid_size
        lng_step = (lng_max - lng_min) / grid_size
        
        high_demand_zones = []
        
        for i in range(grid_size):
            for j in range(grid_size):
                center_lat = lat_min + (i + 0.5) * lat_step
                center_lng = lng_min + (j + 0.5) * lng_step
                
                density = self.calculate_area_density(
                    (center_lat, center_lng),
                    radius=int(max(lat_step, lng_step) * 111000 / 2)  # Conversion degrés -> mètres
                )
                
                # Seuil pour zone à forte demande
                if density['density_score'] > 60:
                    high_demand_zones.append({
                        'center': (center_lat, center_lng),
                        'density_score': density['density_score'],
                        'grid_position': (i, j)
                    })
        
        # Trier par densité décroissante
        high_demand_zones.sort(key=lambda x: x['density_score'], reverse=True)
        
        return high_demand_zones
    
    def calculate_connectivity_score(
        self,
        location: Tuple[float, float],
        transit_types: List[str] = None
    ) -> Dict:
        """
        Calcule le score de connectivité d'un point
        (nombre et proximité des stations de transport)
        
        Args:
            location: Coordonnées du point
            transit_types: Types de transport à considérer
        
        Returns:
            Score de connectivité
        """
        if transit_types is None:
            transit_types = ['bus_station', 'subway_station', 'light_rail_station']
        
        total_stations = 0
        nearby_stations = []
        
        for transit_type in transit_types:
            stations = self.maps_service.get_nearby_transit_stations(
                location,
                radius=800,  # 800m = distance de marche acceptable
                transit_type=transit_type
            )
            total_stations += len(stations)
            nearby_stations.extend(stations)
        
        # Score basé sur le nombre de stations
        connectivity_score = min(100, total_stations * 10)
        
        return {
            'connectivity_score': connectivity_score,
            'total_stations': total_stations,
            'stations': nearby_stations[:5],  # Top 5
            'connectivity_level': self._classify_connectivity(connectivity_score)
        }
    
    def _classify_density(self, score: float) -> str:
        """Classifie le niveau de densité"""
        if score < 20:
            return 'very_low'
        elif score < 40:
            return 'low'
        elif score < 60:
            return 'moderate'
        elif score < 80:
            return 'high'
        else:
            return 'very_high'
    
    def _classify_connectivity(self, score: float) -> str:
        """Classifie le niveau de connectivité"""
        if score < 30:
            return 'poor'
        elif score < 60:
            return 'fair'
        elif score < 80:
            return 'good'
        else:
            return 'excellent'