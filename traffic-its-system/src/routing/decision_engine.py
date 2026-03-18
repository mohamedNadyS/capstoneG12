"""
Routing Decision Engine
Intelligently selects routing algorithm and parameters based on vehicle type and conditions
"""

import numpy as np
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from src.routing.graph_builder import RoutingGraphBuilder, RouteEdge
from src.routing.astar import AStarRouter
from src.routing.dijkstra import DijkstraRouter


@dataclass
class RoutingDecision:
    """Decision made by the routing engine"""
    vehicle_id: str
    vehicle_type: str  # 'normal' or 'emergency'
    algorithm: str  # 'A*' or 'Dijkstra'
    cost_function: str  # 'time', 'safety', 'balanced'
    priority_level: int  # 1-5 (5 = highest)
    ignore_congestion: bool
    can_use_emergency_lanes: bool
    max_speed_multiplier: float


class RoutingDecisionEngine:
    """
    Intelligent decision engine for routing
    Selects optimal algorithm and parameters for each vehicle
    """
    
    def __init__(
        self,
        graph_builder: RoutingGraphBuilder,
        enable_emergency_priority: bool = True
    ):
        """
        Initialize decision engine
        
        Args:
            graph_builder: Routing graph with predicted speeds
            enable_emergency_priority: Enable special rules for emergency vehicles
        """
        self.graph_builder = graph_builder
        self.graph = graph_builder.graph
        self.enable_emergency_priority = enable_emergency_priority
        
        # Initialize both routers
        self.astar = AStarRouter(self.graph, heuristic_type='euclidean')
        self.dijkstra = DijkstraRouter(self.graph)
        
        # Track vehicle routes for congestion management
        self.active_routes: Dict[str, List[str]] = {}  # vehicle_id -> edge_ids
        self.edge_usage: Dict[str, int] = {}  # edge_id -> count
        
        print(f"\n[ENGINE] Routing Decision Engine initialized")
        print(f"   Emergency priority: {enable_emergency_priority}")
        print(f"   Algorithms: A*, Dijkstra")
    
    def make_routing_decision(
        self,
        vehicle_id: str,
        vehicle_type: str,
        current_conditions: Optional[Dict] = None
    ) -> RoutingDecision:
        """
        Decide routing strategy for a vehicle
        
        Args:
            vehicle_id: Vehicle identifier
            vehicle_type: 'normal' or 'emergency'
            current_conditions: Optional dict with current traffic state
            
        Returns:
            RoutingDecision with algorithm and parameters
        """
        if vehicle_type == 'emergency':
            # Emergency vehicles: Use Dijkstra for guaranteed optimal path
            return RoutingDecision(
                vehicle_id=vehicle_id,
                vehicle_type=vehicle_type,
                algorithm='Dijkstra',
                cost_function='time',  # Minimize time
                priority_level=5,
                ignore_congestion=True,  # Can bypass traffic
                can_use_emergency_lanes=True,
                max_speed_multiplier=1.2  # Can exceed speed limit slightly
            )
        
        else:
            # Normal vehicles: Use A* for faster computation
            # Choose cost function based on conditions
            if current_conditions:
                avg_congestion = current_conditions.get('avg_congestion', 0.5)
                avg_safety = current_conditions.get('avg_safety', 0.7)
                
                if avg_congestion > 0.7:
                    # High congestion - prioritize safety
                    cost_function = 'safety'
                elif avg_safety < 0.5:
                    # Low safety - avoid risky roads
                    cost_function = 'safety'
                else:
                    # Normal conditions - balance time and safety
                    cost_function = 'balanced'
            else:
                cost_function = 'balanced'
            
            return RoutingDecision(
                vehicle_id=vehicle_id,
                vehicle_type=vehicle_type,
                algorithm='A*',
                cost_function=cost_function,
                priority_level=1,
                ignore_congestion=False,
                can_use_emergency_lanes=False,
                max_speed_multiplier=1.0
            )
    
    def route_vehicle(
        self,
        vehicle_id: str,
        vehicle_type: str,
        origin_node: str,
        destination_node: str,
        avoid_edges: Optional[Set[str]] = None
    ) -> Optional[Dict]:
        """
        Route a single vehicle
        
        Args:
            vehicle_id: Vehicle identifier
            vehicle_type: 'normal' or 'emergency'
            origin_node: Starting node
            destination_node: Destination node
            avoid_edges: Edges to avoid
            
        Returns:
            Route dictionary or None if no path found
        """
        # Make routing decision
        decision = self.make_routing_decision(vehicle_id, vehicle_type)
        
        # Check for overcrowded edges
        if avoid_edges is None:
            avoid_edges = set()
        
        # Add overcrowded edges to avoid set (for normal vehicles)
        if vehicle_type == 'normal':
            # ✅ NEW: Gradual threshold based on network load
            # Start with 0.99, relax to 1.0 if too many fallbacks
            threshold = 0.99
            
            # If too many recent fallbacks, become more permissive
            if hasattr(self.astar, 'fallback_stats'):
                no_avoid_pct = self.astar.fallback_stats.get('no_avoid', 0) / max(self.astar.total_routes, 1)
                if no_avoid_pct > 0.3:  # More than 30% using fallback
                    threshold = 1.0  # Only avoid completely full edges
            
            overcrowded = self._get_overcrowded_edges(threshold=threshold)
            
            # Only 30% of vehicles avoid
            if hash(vehicle_id) % 10 < 3:
                avoid_edges.update(overcrowded)
        
        # Route using selected algorithm
        if decision.algorithm == 'A*':
            route = self.astar.find_path(
                start_node=origin_node,
                goal_node=destination_node,
                avoid_edges=avoid_edges,
                cost_function='time',
                vehicle_id=vehicle_id
            )

            if route and avoid_edges:
                # Try without avoidance to compare
                direct_route = self.astar.find_path(
                    start_node=origin_node,
                    goal_node=destination_node,
                    avoid_edges=set(),  # No avoidance
                    cost_function='time',
                    vehicle_id=vehicle_id
                )
                
                if direct_route:
                    # If AI route is >50% longer, use direct route instead
                    if len(route['edges']) > len(direct_route['edges']) * 1.5:
                        route = direct_route
                        route['note'] = 'Used direct route (detour too long)'
                        
        else:  # Dijkstra
            route = self.dijkstra.find_path(
                start_node=origin_node,
                goal_node=destination_node,
                emergency=True,
                avoid_edges=avoid_edges if vehicle_type != 'emergency' else set(),
                ignore_congestion=decision.ignore_congestion
            )
        
        if route:
            # Add decision info to route
            route['vehicle_id'] = vehicle_id
            route['vehicle_type'] = vehicle_type
            route['decision'] = decision
            route['algorithm'] = decision.algorithm  # Add for stats
            
            # Add calculated fields if missing
            if 'num_edges' not in route:
                route['num_edges'] = len(route.get('edges', []))
            
            if 'length' not in route:
                # Calculate total length from edges
                total_length = 0.0
                nodes = route.get('nodes', [])
                edges = route.get('edges', [])
                
                # Try to get length from graph edges
                for i, edge_id in enumerate(edges):
                    if i < len(nodes) - 1:
                        from_node = nodes[i]
                        to_node = nodes[i + 1]
                        try:
                            # Access MultiDiGraph edge data
                            edge_data = self.graph_builder.graph[from_node][to_node][edge_id]
                            total_length += edge_data.get('length', edge_data.get('distance', 0.0))
                        except:
                            # Fallback: estimate 100m per edge
                            total_length += 100.0
                
                route['length'] = total_length if total_length > 0 else len(edges) * 100.0
            
            # Update tracking
            self._track_route(vehicle_id, route['edges'])
        
        return route
    
    def route_all_vehicles(
        self,
        vehicles: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Route multiple vehicles with priority handling
        
        Args:
            vehicles: List of vehicle dicts with id, type, origin, destination
            
        Returns:
            Dictionary mapping vehicle_id -> route
        """
        print(f"\n[ENGINE] Routing {len(vehicles)} vehicles...")
        
        # Separate by priority
        emergency_vehicles = [v for v in vehicles if v.get('type') == 'emergency']
        normal_vehicles = [v for v in vehicles if v.get('type') != 'emergency']
        
        print(f"   Emergency: {len(emergency_vehicles)}")
        print(f"   Normal: {len(normal_vehicles)}")
        
        routes = {}
        
        # Route emergency vehicles first (priority)
        for vehicle in emergency_vehicles:
            route = self.route_vehicle(
                vehicle_id=vehicle['id'],
                vehicle_type='emergency',
                origin_node=vehicle['origin'],
                destination_node=vehicle['destination']
            )
            
            if route:
                routes[vehicle['id']] = route
        
        print(f"   [OK] Routed {len([r for r in routes.values() if r['vehicle_type'] == 'emergency'])} emergency vehicles")
        
        # Route normal vehicles
        for vehicle in normal_vehicles:
            route = self.route_vehicle(
                vehicle_id=vehicle['id'],
                vehicle_type='normal',
                origin_node=vehicle['origin'],
                destination_node=vehicle['destination']
            )
            
            if route:
                routes[vehicle['id']] = route
        
        print(f"   [OK] Routed {len([r for r in routes.values() if r['vehicle_type'] == 'normal'])} normal vehicles")
        
        # Calculate statistics
        stats = self._calculate_routing_stats(routes)
        
        # Print A* fallback statistics if available
        if 'astar_fallback_stats' in stats and stats.get('astar_total_routes', 0) > 0:
            print(f"\n   [A*] Fallback Strategy Usage:")
            total = stats['astar_total_routes']
            for method, count in stats['astar_fallback_stats'].items():
                if count > 0:
                    percentage = (count / total * 100)
                    print(f"      {method}: {count} ({percentage:.1f}%)")
        
        return {
            'routes': routes,
            'statistics': stats
        }
    
    def _track_route(self, vehicle_id: str, edges: List[str]):
        """Track vehicle route for congestion management"""
        self.active_routes[vehicle_id] = edges
        
        for edge_id in edges:
            self.edge_usage[edge_id] = self.edge_usage.get(edge_id, 0) + 1
    
    def _get_overcrowded_edges(self, threshold: float = 0.9) -> Set[str]:
        """Get edges that are over capacity"""
        overcrowded = set()
        
        for edge_id, count in self.edge_usage.items():
            if edge_id in self.graph_builder.edge_attributes:
                edge = self.graph_builder.edge_attributes[edge_id]
                
                # Check if usage exceeds capacity
                usage_ratio = count / max(1, edge.capacity * 0.01)  # capacity is per hour, scale down
                
                if usage_ratio > threshold:
                    overcrowded.add(edge_id)
        
        return overcrowded
    
    def _calculate_routing_stats(self, routes: Dict[str, Dict]) -> Dict:
        """Calculate routing statistics"""
        if not routes:
            return {}
        
        route_list = list(routes.values())
        
        costs = [r['cost'] for r in route_list]
        lengths = [r['length'] for r in route_list]
        num_edges = [r['num_edges'] for r in route_list]
        
        # Separate by type
        emergency_routes = [r for r in route_list if r['vehicle_type'] == 'emergency']
        normal_routes = [r for r in route_list if r['vehicle_type'] == 'normal']
        
        stats = {
            'total_vehicles': len(routes),
            'emergency_vehicles': len(emergency_routes),
            'normal_vehicles': len(normal_routes),
            'avg_cost': float(np.mean(costs)),
            'avg_length': float(np.mean(lengths)),
            'avg_edges': float(np.mean(num_edges)),
            'total_length': float(np.sum(lengths))
        }
        
        if emergency_routes:
            stats['emergency_avg_cost'] = float(np.mean([r['cost'] for r in emergency_routes]))
        
        if normal_routes:
            stats['normal_avg_cost'] = float(np.mean([r['cost'] for r in normal_routes]))
        
        # Algorithm usage
        astar_count = len([r for r in route_list if r['algorithm'] == 'A*'])
        dijkstra_count = len([r for r in route_list if r['algorithm'] == 'Dijkstra'])
        
        stats['algorithm_usage'] = {
            'A*': astar_count,
            'Dijkstra': dijkstra_count
        }
        
        # Add A* fallback statistics if available
        if hasattr(self.astar, 'fallback_stats'):
            stats['astar_fallback_stats'] = dict(self.astar.fallback_stats)
            stats['astar_total_routes'] = self.astar.total_routes
        
        return stats


if __name__ == "__main__":
    print("="*70)
    print("ROUTING DECISION ENGINE TEST")
    print("="*70)
    
    print("\nFeatures:")
    print("  • Intelligent algorithm selection")
    print("  • Emergency vehicle priority")
    print("  • Congestion-aware routing")
    print("  • Multi-objective optimization")
    print("  • Capacity management")
    
    print("\nAlgorithm Selection:")
    print("  Emergency vehicles → Dijkstra (guaranteed optimal)")
    print("  Normal vehicles → A* (fast heuristic search)")
    
    print("\nCost Function Selection:")
    print("  High congestion → Safety-focused")
    print("  Low safety → Avoid risky roads")
    print("  Normal conditions → Balanced (time + safety)")
