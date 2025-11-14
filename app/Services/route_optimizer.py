# app/services/route_optimizer.py
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np

class RouteOptimizer:
    """
    Optimise les itinéraires en combinant:
    - Données de trafic en temps réel
    - Densité urbaine
    - Connectivité des transports
    """
    
    def __init__(self, maps_service, density_analyzer):
        """
        Args:
            maps_service: Service Google Maps
            density_analyzer: Analyseur de densité
        """
        self.maps_service = maps_service
        self.density_analyzer = density_analyzer
        
        # Poids pour l'algorithme de scoring
        self.weights = {
            'time': 0.35,           # Temps de trajet
            'traffic': 0.25,        # Conditions de trafic
            'density': 0.20,        # Densité desservie
            'connectivity': 0.20    # Connectivité
        }
    
    def find_optimal_routes(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime = None,
        preferences: Dict = None
    ) -> List[Dict]:
        """
        Trouve et classe les meilleurs itinéraires
        
        Args:
            origin: Point de départ (lat, lng)
            destination: Point d'arrivée (lat, lng)
            departure_time: Heure de départ
            preferences: Préférences utilisateur (ex: {'prefer': 'bus'})
        
        Returns:
            Liste d'itinéraires classés par score d'optimisation
        """
        if departure_time is None:
            departure_time = datetime.now()
        
        if preferences is None:
            preferences = {}
        
        # 1. Obtenir les itinéraires de transport en commun
        transit_modes = preferences.get('transit_modes', ['bus', 'subway', 'tram'])
        routes = self.maps_service.get_directions_transit(
            origin,
            destination,
            departure_time,
            transit_modes
        )
        
        if not routes:
            return []
        
        # 2. Évaluer chaque itinéraire
        evaluated_routes = []
        for route in routes:
            score = self._evaluate_route(route, origin, destination, departure_time)
            route['optimization_score'] = score
            route['recommendation'] = self._generate_recommendation(score, route)
            evaluated_routes.append(route)
        
        # 3. Trier par score décroissant
        evaluated_routes.sort(key=lambda x: x['optimization_score']['total_score'], reverse=True)
        
        return evaluated_routes
    
    def _evaluate_route(
        self,
        route: Dict,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        departure_time: datetime
    ) -> Dict:
        """
        Évalue un itinéraire selon multiples critères
        
        Args:
            route: Données de l'itinéraire
            origin: Point de départ
            destination: Point d'arrivée
            departure_time: Heure de départ
        
        Returns:
            Scores détaillés
        """
        # Score de temps (inversement proportionnel)
        duration = route['total_duration_seconds']
        time_score = max(0, 100 - (duration / 60))  # Pénalité par minute
        
        # Score de trafic
        traffic_info = self.maps_service.get_traffic_conditions(
            origin, destination, departure_time
        )
        traffic_score = self._calculate_traffic_score(traffic_info) if traffic_info else 50
        
        # Score de densité du corridor
        waypoints = self._extract_waypoints(route)
        density_analysis = self.density_analyzer.analyze_route_corridor(waypoints)
        density_score = density_analysis['average_density']
        
        # Score de connectivité (début et fin)
        origin_connectivity = self.density_analyzer.calculate_connectivity_score(origin)
        dest_connectivity = self.density_analyzer.calculate_connectivity_score(destination)
        connectivity_score = (origin_connectivity['connectivity_score'] + 
                             dest_connectivity['connectivity_score']) / 2
        
        # Calcul du score total pondéré
        total_score = (
            time_score * self.weights['time'] +
            traffic_score * self.weights['traffic'] +
            density_score * self.weights['density'] +
            connectivity_score * self.weights['connectivity']
        )
        
        return {
            'total_score': round(total_score, 2),
            'time_score': round(time_score, 2),
            'traffic_score': round(traffic_score, 2),
            'density_score': round(density_score, 2),
            'connectivity_score': round(connectivity_score, 2),
            'breakdown': {
                'duration_minutes': duration / 60,
                'traffic_level': traffic_info.get('traffic_level') if traffic_info else 'unknown',
                'average_corridor_density': density_analysis['average_density'],
                'route_uniformity': density_analysis['uniformity']
            }
        }
    
    def _calculate_traffic_score(self, traffic_info: Dict) -> float:
        """
        Convertit les infos de trafic en score (0-100)
        
        Args:
            traffic_info: Données de trafic
        
        Returns:
            Score (100 = trafic fluide, 0 = trafic sévère)
        """
        traffic_level = traffic_info['traffic_level']
        
        score_map = {
            'low': 95,
            'moderate': 70,
            'heavy': 40,
            'severe': 15
        }
        
        return score_map.get(traffic_level, 50)
    
    def _extract_waypoints(self, route: Dict) -> List[Tuple[float, float]]:
        """
        Extrait les points clés d'un itinéraire pour analyse
        
        Args:
            route: Données de l'itinéraire
        
        Returns:
            Liste de coordonnées
        """
        waypoints = []
        
        for step in route['steps']:
            # Pour les étapes de transport, on prend arrêts départ et arrivée
            if 'transit' in step:
                # On pourrait extraire les coordonnées des arrêts ici
                # Pour simplifier, on échantillonne le long de la route
                pass
        
        # Échantillonnage simple: début, milieu, fin
        # Dans une vraie implémentation, on décoderait le polyline
        # Pour l'exemple, on retourne des points fictifs
        # TODO: Implémenter le décodage du polyline pour vrais waypoints
        
        return waypoints
    
    def _generate_recommendation(self, score: Dict, route: Dict) -> str:
        """
        Génère une recommandation textuelle
        
        Args:
            score: Scores d'évaluation
            route: Données de l'itinéraire
        
        Returns:
            Texte de recommandation
        """
        total = score['total_score']
        duration = score['breakdown']['duration_minutes']
        traffic = score['breakdown']['traffic_level']
        
        if total >= 80:
            return f"⭐ Excellent choix! Trajet de {duration:.0f} min avec trafic {traffic}."
        elif total >= 60:
            return f"✓ Bon itinéraire. Durée: {duration:.0f} min, conditions: {traffic}."
        elif total >= 40:
            return f"↔ Option acceptable. {duration:.0f} min mais trafic {traffic}."
        else:
            return f"⚠ Itinéraire moins optimal. {duration:.0f} min, éviter si possible."
    
    def suggest_new_route(
        self,
        area_bounds: Tuple[Tuple[float, float], Tuple[float, float]],
        vehicle_type: str = 'bus'
    ) -> Dict:
        """
        Suggère un nouvel itinéraire de transport basé sur la demande
        
        Args:
            area_bounds: Limites de la zone à analyser
            vehicle_type: Type de véhicule (bus, tram, etc.)
        
        Returns:
            Suggestion d'itinéraire avec justification
        """
        # Identifier zones à forte demande
        high_demand = self.density_analyzer.identify_high_demand_zones(
            area_bounds,
            grid_size=8
        )
        
        if len(high_demand) < 2:
            return {
                'status': 'insufficient_data',
                'message': 'Pas assez de zones à forte demande identifiées'
            }
        
        # Connecter les zones les plus denses
        top_zones = high_demand[:5]
        
        return {
            'status': 'success',
            'vehicle_type': vehicle_type,
            'suggested_stops': top_zones,
            'rationale': f"Itinéraire proposé desservant {len(top_zones)} zones à haute densité",
            'expected_coverage': sum(z['density_score'] for z in top_zones) / len(top_zones),
            'priority': 'high' if len(high_demand) > 10 else 'medium'
        }
    
    def compare_routes(self, routes: List[Dict]) -> Dict:
        """
        Compare plusieurs itinéraires et fournit un résumé
        
        Args:
            routes: Liste d'itinéraires évalués
        
        Returns:
            Analyse comparative
        """
        if not routes:
            return {'error': 'No routes to compare'}
        
        best = routes[0]
        scores = [r['optimization_score']['total_score'] for r in routes]
        
        return {
            'best_route_index': 0,
            'best_route_summary': best['summary'],
            'score_range': {
                'min': min(scores),
                'max': max(scores),
                'average': np.mean(scores)
            },
            'recommendation': f"Le meilleur itinéraire ({best['summary']}) surpasse les alternatives de {scores[0] - np.mean(scores[1:]) if len(scores) > 1 else 0:.1f} points."
        }