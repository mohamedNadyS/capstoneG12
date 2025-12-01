"""
Routing Graph Builder
Builds routing graph from SUMO network with predicted speeds
"""

import networkx as nx
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from src.sumo_integration.sumo_parser import SUMONetworkParser, SUMOEdge


@dataclass
class RouteEdge:
    """Edge in routing graph with all attributes"""
    edge_id: str
    from_node: str
    to_node: str
    length: float  # meters
    speed_limit: float  # km/h
    predicted_speed: float  # km/h (from GNN)
    num_lanes: int
    capacity: float
    travel_time: float  # seconds
    congestion_factor: float  # 0.0 - 1.0
    safety_score: float  # 0.0 - 1.0 (higher is safer)
    

class RoutingGraphBuilder:
    """
    Build routing graph from SUMO network and predicted speeds
    """
    
    def __init__(self, sumo_network: SUMONetworkParser):
        """
        Initialize graph builder
        
        Args:
            sumo_network: Parsed SUMO network
        """
        self.sumo_network = sumo_network
        self.graph = None
        self.edge_attributes = {}
        
        print(f"\n[GRAPH] Initializing routing graph builder")
        print(f"   Nodes: {len(sumo_network.nodes)}")
        print(f"   Edges: {len(sumo_network.edges)}")
    
    def build_graph(
        self,
        predicted_speeds: Optional[Dict[str, np.ndarray]] = None,
        current_congestion: Optional[Dict[str, float]] = None
    ) -> nx.DiGraph:
        """
        Build routing graph with all attributes
        
        Args:
            predicted_speeds: Dict[edge_id -> [t+5, t+10, t+15] speeds]
            current_congestion: Dict[edge_id -> congestion_factor]
            
        Returns:
            NetworkX directed graph ready for routing
        """
        print(f"\n[GRAPH] Building routing graph...")
        
        # Use MultiDiGraph to handle multiple edges between same node pairs
        self.graph = nx.MultiDiGraph()
        
        # Add nodes (junctions) with positions
        for node_id, sumo_node in self.sumo_network.nodes.items():
            self.graph.add_node(
                node_id,
                x=sumo_node.x,
                y=sumo_node.y,
                node_type=sumo_node.node_type
            )
        
        print(f"   Added {len(self.graph.nodes)} nodes with positions")
        
        # Add edges with all attributes
        edges_added = 0
        for edge_id, sumo_edge in self.sumo_network.edges.items():
            # Get predicted speed (use t+5min forecast)
            if predicted_speeds and edge_id in predicted_speeds:
                pred_value = predicted_speeds[edge_id]
                if isinstance(pred_value, list) and len(pred_value) > 0:
                    predicted_speed = float(pred_value[0])  # First horizon (t+5min)
                elif isinstance(pred_value, (int, float)):
                    predicted_speed = float(pred_value)
                else:
                    predicted_speed = sumo_edge.speed_limit_kmh
            else:
                # Fallback to speed limit if no prediction
                predicted_speed = sumo_edge.speed_limit_kmh
            
            # Get congestion
            if current_congestion and edge_id in current_congestion:
                congestion = float(current_congestion[edge_id])
            else:
                # Estimate from speed
                congestion = max(0, 1.0 - (predicted_speed / sumo_edge.speed_limit_kmh))
            
            # Calculate travel time (in seconds)
            # time = distance / speed
            if predicted_speed > 0:
                travel_time = (sumo_edge.length / 1000) / (predicted_speed / 3600)
            else:
                travel_time = float('inf')
            
            # Calculate safety score
            # Higher speed variance → lower safety
            # Fewer lanes → lower safety
            safety_score = self._calculate_safety_score(
                sumo_edge, predicted_speed, congestion
            )
            
            # Create route edge
            route_edge = RouteEdge(
                edge_id=edge_id,
                from_node=sumo_edge.from_node,
                to_node=sumo_edge.to_node,
                length=sumo_edge.length,
                speed_limit=sumo_edge.speed_limit_kmh,
                predicted_speed=predicted_speed,
                num_lanes=sumo_edge.num_lanes,
                capacity=sumo_edge.capacity,
                travel_time=travel_time,
                congestion_factor=congestion,
                safety_score=safety_score
            )
            
            # Add to graph - use edge_id as key for MultiDiGraph
            self.graph.add_edge(
                sumo_edge.from_node,
                sumo_edge.to_node,
                key=edge_id,  # Use edge_id as the key!
                edge_id=edge_id,
                weight=travel_time,  # Used by routing algorithms
                length=sumo_edge.length,
                speed=predicted_speed,
                congestion=congestion,
                safety=safety_score,
                capacity=sumo_edge.capacity,
                num_lanes=sumo_edge.num_lanes
            )
            
            self.edge_attributes[edge_id] = route_edge
            edges_added += 1
        
        print(f"   Added {edges_added} edges with attributes")
        print(f"   [OK] Routing graph ready")
        
        return self.graph
    
    def _calculate_safety_score(
        self,
        edge: SUMOEdge,
        predicted_speed: float,
        congestion: float
    ) -> float:
        """
        Calculate safety score for an edge
        
        Factors:
        - Lower congestion → higher safety
        - More lanes → higher safety
        - Speed closer to limit → higher safety
        
        Returns:
            Safety score 0.0 - 1.0
        """
        # Congestion factor (less congestion = safer)
        congestion_safety = 1.0 - (congestion * 0.5)
        
        # Lane factor (more lanes = safer)
        lane_safety = min(1.0, edge.num_lanes / 2.0)
        
        # Speed factor (not too fast, not too slow)
        speed_ratio = predicted_speed / edge.speed_limit_kmh
        if 0.6 <= speed_ratio <= 0.9:
            speed_safety = 1.0  # Optimal range
        else:
            speed_safety = max(0.3, 1.0 - abs(0.75 - speed_ratio))
        
        # Weighted average
        safety = (
            0.4 * congestion_safety +
            0.3 * lane_safety +
            0.3 * speed_safety
        )
        
        return float(np.clip(safety, 0, 1))
    
    def get_edge_cost(
        self,
        edge_id: str,
        cost_function: str = 'time',
        emergency: bool = False
    ) -> float:
        """
        Get cost of traversing an edge
        
        Args:
            edge_id: Edge identifier
            cost_function: 'time', 'safety', 'balanced'
            emergency: If True, ignore some constraints
            
        Returns:
            Edge cost for routing
        """
        if edge_id not in self.edge_attributes:
            return float('inf')
        
        edge = self.edge_attributes[edge_id]
        
        if cost_function == 'time':
            # Pure time optimization
            return edge.travel_time
        
        elif cost_function == 'safety':
            # Optimize for safety (inverse score)
            return edge.travel_time * (2.0 - edge.safety_score)
        
        elif cost_function == 'balanced':
            # Balance time and safety
            time_cost = edge.travel_time
            safety_penalty = (1.0 - edge.safety_score) * 30  # Up to 30 seconds penalty
            congestion_penalty = edge.congestion_factor * 20  # Up to 20 seconds penalty
            
            total_cost = time_cost + safety_penalty + congestion_penalty
            
            # Emergency vehicles ignore congestion penalty
            if emergency:
                total_cost = time_cost + (safety_penalty * 0.5)
            
            return total_cost
        
        else:
            return edge.travel_time
    
    def check_capacity_constraint(
        self,
        edge_id: str,
        current_usage: float = 0.0,
        threshold: float = 0.8
    ) -> bool:
        """
        Check if edge has capacity for another vehicle
        
        Args:
            edge_id: Edge identifier
            current_usage: Current capacity usage (0.0 - 1.0)
            threshold: Maximum allowed usage
            
        Returns:
            True if edge has capacity
        """
        if edge_id not in self.edge_attributes:
            return False
        
        edge = self.edge_attributes[edge_id]
        
        # High congestion means near capacity
        estimated_usage = current_usage + edge.congestion_factor
        
        return estimated_usage < threshold
    
    def get_alternative_edges(
        self,
        from_node: str,
        to_node: str
    ) -> List[str]:
        """
        Get alternative edges between two nodes
        
        Args:
            from_node: Origin node
            to_node: Destination node
            
        Returns:
            List of edge IDs connecting the nodes
        """
        alternatives = []
        
        for edge_id, edge in self.edge_attributes.items():
            if edge.from_node == from_node and edge.to_node == to_node:
                alternatives.append(edge_id)
        
        return alternatives
    
    def get_graph_statistics(self) -> Dict:
        """Get statistics about the routing graph"""
        if not self.graph:
            return {}
        
        speeds = [attr.predicted_speed for attr in self.edge_attributes.values()]
        times = [attr.travel_time for attr in self.edge_attributes.values()]
        congestions = [attr.congestion_factor for attr in self.edge_attributes.values()]
        safeties = [attr.safety_score for attr in self.edge_attributes.values()]
        
        return {
            'num_nodes': len(self.graph.nodes),
            'num_edges': len(self.graph.edges),
            'avg_speed': np.mean(speeds),
            'avg_travel_time': np.mean(times),
            'avg_congestion': np.mean(congestions),
            'avg_safety': np.mean(safeties),
            'total_network_length': sum(e.length for e in self.edge_attributes.values())
        }


if __name__ == "__main__":
    print("="*70)
    print("ROUTING GRAPH BUILDER TEST")
    print("="*70)
    
    print("\nThis module builds routing graphs from SUMO networks")
    print("Integrates with GNN predictions for intelligent routing")
    print("\nUsage:")
    print("  1. Parse SUMO network")
    print("  2. Get predicted speeds from GNN")
    print("  3. Build routing graph")
    print("  4. Use for A* or Dijkstra routing")
