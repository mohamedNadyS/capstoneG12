"""
Dijkstra Routing Algorithm
Guaranteed optimal pathfinding for emergency vehicles
"""

import heapq
import networkx as nx
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field


@dataclass(order=True)
class DijkstraNode:
    """Node in Dijkstra search with priority"""
    cost: float
    node_id: str = field(compare=False)
    parent: Optional[str] = field(default=None, compare=False)
    edge_used: Optional[str] = field(default=None, compare=False)


class DijkstraRouter:
    """
    Dijkstra's algorithm for pathfinding
    Guaranteed optimal path, no heuristic
    Best for emergency vehicles that need guaranteed shortest path
    """
    
    def __init__(self, graph: nx.DiGraph):
        """
        Initialize Dijkstra router
        
        Args:
            graph: NetworkX directed graph
        """
        self.graph = graph
        
        print(f"\n[DIJKSTRA] Dijkstra Router initialized")
        print(f"   Nodes: {len(graph.nodes)}")
        print(f"   Edges: {len(graph.edges)}")
        print(f"   Guarantees: Optimal path, Complete search")
    
    def find_path(
        self,
        start_node: str,
        goal_node: str,
        emergency: bool = True,
        avoid_edges: Optional[Set[str]] = None,
        ignore_congestion: bool = True
    ) -> Optional[Dict]:
        """
        Find optimal path using Dijkstra's algorithm
        
        Args:
            start_node: Starting node ID
            goal_node: Destination node ID
            emergency: If True, applies emergency routing rules
            avoid_edges: Set of edge IDs to avoid
            ignore_congestion: If True (emergency), ignore congestion penalties
            
        Returns:
            Dictionary with path info or None if no path found
        """
        if start_node not in self.graph.nodes:
            raise ValueError(f"Start node {start_node} not in graph")
        if goal_node not in self.graph.nodes:
            raise ValueError(f"Goal node {goal_node} not in graph")
        
        if avoid_edges is None:
            avoid_edges = set()
        
        # Initialize
        distances = {node: float('inf') for node in self.graph.nodes}
        distances[start_node] = 0.0
        
        came_from = {}
        edge_used = {}
        
        priority_queue = []
        start_dnode = DijkstraNode(cost=0.0, node_id=start_node)
        heapq.heappush(priority_queue, start_dnode)
        
        visited = set()
        nodes_expanded = 0
        
        while priority_queue:
            current = heapq.heappop(priority_queue)
            current_node = current.node_id
            current_cost = current.cost
            
            # Already processed?
            if current_node in visited:
                continue
            
            visited.add(current_node)
            nodes_expanded += 1
            
            # Goal reached?
            if current_node == goal_node:
                return self._reconstruct_path(
                    came_from, edge_used, start_node, goal_node,
                    distances[goal_node], nodes_expanded
                )
            
            # Skip if we've found a better path already
            if current_cost > distances[current_node]:
                continue
            
            # Explore neighbors
            for neighbor in self.graph.successors(current_node):
                if neighbor in visited:
                    continue
                
                # Get edge data
                edge_data = self.graph[current_node][neighbor]
                edge_id = edge_data.get('edge_id', f"{current_node}-{neighbor}")
                
                # Skip if avoiding this edge
                if edge_id in avoid_edges:
                    continue
                
                # Calculate edge cost
                base_cost = edge_data.get('weight', 1.0)
                
                if emergency:
                    # Emergency vehicles
                    if ignore_congestion:
                        # Pure travel time, ignore congestion
                        edge_cost = base_cost
                    else:
                        # Minimal congestion penalty
                        congestion = edge_data.get('congestion', 0.0)
                        edge_cost = base_cost * (1.0 + congestion * 0.2)
                else:
                    # Normal vehicles
                    congestion = edge_data.get('congestion', 0.0)
                    safety = edge_data.get('safety', 0.5)
                    edge_cost = base_cost * (1.0 + congestion * 0.5) * (2.0 - safety)
                
                # Relaxation step
                tentative_distance = distances[current_node] + edge_cost
                
                if tentative_distance < distances[neighbor]:
                    distances[neighbor] = tentative_distance
                    came_from[neighbor] = current_node
                    edge_used[neighbor] = edge_id
                    
                    neighbor_dnode = DijkstraNode(
                        cost=tentative_distance,
                        node_id=neighbor,
                        parent=current_node,
                        edge_used=edge_id
                    )
                    heapq.heappush(priority_queue, neighbor_dnode)
        
        # No path found
        print(f"   [WARNING] No path from {start_node} to {goal_node}")
        print(f"   Nodes expanded: {nodes_expanded}")
        return None
    
    def _reconstruct_path(
        self,
        came_from: Dict[str, str],
        edge_used: Dict[str, str],
        start: str,
        goal: str,
        total_cost: float,
        nodes_expanded: int
    ) -> Dict:
        """
        Reconstruct path from parent tracking
        
        Returns:
            Dictionary with path details
        """
        path_nodes = []
        path_edges = []
        
        # Backtrack from goal to start
        current = goal
        while current != start:
            path_nodes.append(current)
            if current in edge_used:
                path_edges.append(edge_used[current])
            current = came_from.get(current)
            if current is None:
                break
        
        path_nodes.append(start)
        
        # Reverse to get start→goal order
        path_nodes.reverse()
        path_edges.reverse()
        
        # Calculate total length and detailed metrics
        total_length = 0.0
        total_congestion = 0.0
        avg_safety = 0.0
        
        for edge_id in path_edges:
            for u, v, data in self.graph.edges(data=True):
                if data.get('edge_id') == edge_id:
                    total_length += data.get('length', 0.0)
                    total_congestion += data.get('congestion', 0.0)
                    avg_safety += data.get('safety', 0.5)
                    break
        
        if path_edges:
            avg_safety /= len(path_edges)
            total_congestion /= len(path_edges)
        
        return {
            'nodes': path_nodes,
            'edges': path_edges,
            'cost': total_cost,
            'length': total_length,
            'avg_congestion': total_congestion,
            'avg_safety': avg_safety,
            'num_nodes': len(path_nodes),
            'num_edges': len(path_edges),
            'nodes_expanded': nodes_expanded,
            'algorithm': 'Dijkstra'
        }
    
    def find_all_shortest_paths(
        self,
        start_node: str
    ) -> Dict[str, float]:
        """
        Find shortest paths from start to all other nodes
        Useful for calculating multiple routes at once
        
        Args:
            start_node: Source node
            
        Returns:
            Dictionary mapping node -> distance
        """
        distances = {node: float('inf') for node in self.graph.nodes}
        distances[start_node] = 0.0
        
        priority_queue = []
        start_dnode = DijkstraNode(cost=0.0, node_id=start_node)
        heapq.heappush(priority_queue, start_dnode)
        
        visited = set()
        
        while priority_queue:
            current = heapq.heappop(priority_queue)
            current_node = current.node_id
            
            if current_node in visited:
                continue
            
            visited.add(current_node)
            
            for neighbor in self.graph.successors(current_node):
                edge_data = self.graph[current_node][neighbor]
                edge_cost = edge_data.get('weight', 1.0)
                
                tentative_distance = distances[current_node] + edge_cost
                
                if tentative_distance < distances[neighbor]:
                    distances[neighbor] = tentative_distance
                    
                    neighbor_dnode = DijkstraNode(
                        cost=tentative_distance,
                        node_id=neighbor
                    )
                    heapq.heappush(priority_queue, neighbor_dnode)
        
        return distances


if __name__ == "__main__":
    print("="*70)
    print("DIJKSTRA ROUTING ALGORITHM TEST")
    print("="*70)
    
    print("\nDijkstra Algorithm Features:")
    print("  • Guaranteed optimal path")
    print("  • Complete graph search")
    print("  • Best for emergency vehicles")
    print("  • Can ignore congestion/traffic rules")
    print("  • Slower than A* but always optimal")
    print("\nUsage:")
    print("  1. Build routing graph with predicted speeds")
    print("  2. Create Dijkstra router")
    print("  3. Find path with emergency=True")
    print("  4. Get guaranteed shortest route")
