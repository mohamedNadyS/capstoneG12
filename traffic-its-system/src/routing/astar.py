"""
A* Routing Algorithm
Optimized pathfinding for normal vehicles using heuristic search
"""

import heapq
import networkx as nx
import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field


@dataclass(order=True)
class AStarNode:
    """Node in A* search with priority"""
    f_cost: float  # g + h (total estimated cost)
    node_id: str = field(compare=False)
    g_cost: float = field(compare=False)  # Cost from start
    h_cost: float = field(compare=False)  # Heuristic to goal
    parent: Optional[str] = field(default=None, compare=False)
    edge_used: Optional[str] = field(default=None, compare=False)


class AStarRouter:
    """
    A* pathfinding algorithm
    Faster than Dijkstra, uses heuristic to guide search
    Best for normal vehicles
    """
    
    def __init__(
        self,
        graph: nx.DiGraph,
        heuristic_type: str = 'euclidean'
    ):
        """
        Initialize A* router
        
        Args:
            graph: NetworkX graph with node positions
            heuristic_type: 'euclidean', 'manhattan', or 'zero' (becomes Dijkstra)
        """
        self.graph = graph
        self.heuristic_type = heuristic_type
        
        # Get node positions for heuristic calculation
        self.node_positions = self._extract_node_positions()
        
        print(f"\n[A*] A* Router initialized")
        print(f"   Heuristic: {heuristic_type}")
        print(f"   Nodes: {len(graph.nodes)}")
        print(f"   Edges: {len(graph.edges)}")
    
    def _extract_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Extract node coordinates from graph"""
        positions = {}
        
        # Try to get positions from graph nodes
        for node_id, data in self.graph.nodes(data=True):
            if 'x' in data and 'y' in data:
                positions[node_id] = (data['x'], data['y'])
        
        return positions
    
    def _heuristic(
        self,
        node: str,
        goal: str
    ) -> float:
        """
        Calculate heuristic cost from node to goal
        
        Args:
            node: Current node
            goal: Goal node
            
        Returns:
            Estimated cost to goal
        """
        if self.heuristic_type == 'zero':
            # Zero heuristic = Dijkstra
            return 0.0
        
        if node not in self.node_positions or goal not in self.node_positions:
            # No position info, use zero heuristic
            return 0.0
        
        x1, y1 = self.node_positions[node]
        x2, y2 = self.node_positions[goal]
        
        if self.heuristic_type == 'euclidean':
            # Straight-line distance
            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        elif self.heuristic_type == 'manhattan':
            # Manhattan distance
            distance = abs(x2 - x1) + abs(y2 - y1)
        else:
            distance = 0.0
        
        # Convert distance to time estimate (assume average speed 30 km/h = 8.33 m/s)
        estimated_time = distance / 8.33
        
        return estimated_time
    
    def find_path(
        self,
        start_node: str,
        goal_node: str,
        avoid_edges: Optional[Set[str]] = None,
        cost_function: str = 'balanced'
    ) -> Optional[Dict]:
        """
        Find optimal path using A* algorithm
        
        Args:
            start_node: Starting node ID
            goal_node: Destination node ID
            avoid_edges: Set of edge IDs to avoid (blocked/congested)
            cost_function: 'time', 'safety', or 'balanced'
            
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
        open_set = []  # Priority queue
        closed_set = set()  # Visited nodes
        g_costs = {start_node: 0.0}
        came_from = {}  # Parent tracking
        edge_used = {}  # Edge tracking
        
        # Add start node
        start_h = self._heuristic(start_node, goal_node)
        start_astar_node = AStarNode(
            f_cost=start_h,
            node_id=start_node,
            g_cost=0.0,
            h_cost=start_h
        )
        heapq.heappush(open_set, start_astar_node)
        
        nodes_expanded = 0
        
        while open_set:
            # Get node with lowest f_cost
            current = heapq.heappop(open_set)
            current_node = current.node_id
            
            # Goal reached?
            if current_node == goal_node:
                return self._reconstruct_path(
                    came_from, edge_used, start_node, goal_node, g_costs[goal_node]
                )
            
            if current_node in closed_set:
                continue
            
            closed_set.add(current_node)
            nodes_expanded += 1
            
            # Explore neighbors
            for neighbor in self.graph.successors(current_node):
                if neighbor in closed_set:
                    continue
                
                # Get all edges between current_node and neighbor (MultiDiGraph)
                edges_between = self.graph[current_node][neighbor]
                
                # Find best edge among parallel edges (lowest cost)
                best_edge_id = None
                best_edge_data = None
                best_cost = float('inf')
                
                for edge_key, edge_data in edges_between.items():
                    # edge_key IS the edge_id now!
                    edge_id = str(edge_key)
                    
                    # Skip if avoiding this edge
                    if edge_id in avoid_edges:
                        continue
                    
                    # Calculate cost for this edge
                    if cost_function == 'time':
                        edge_cost = edge_data.get('weight', 1.0)
                    elif cost_function == 'safety':
                        base_cost = edge_data.get('weight', 1.0)
                        safety = edge_data.get('safety', 0.5)
                        edge_cost = base_cost * (2.0 - safety)
                    else:  # balanced
                        base_cost = edge_data.get('weight', 1.0)
                        safety = edge_data.get('safety', 0.5)
                        congestion = edge_data.get('congestion', 0.0)
                        edge_cost = base_cost * (1.0 + congestion * 0.5) * (2.0 - safety)
                    
                    # Keep track of best edge
                    if edge_cost < best_cost:
                        best_cost = edge_cost
                        best_edge_id = edge_id
                        best_edge_data = edge_data
                
                # Skip if no valid edge found
                if best_edge_id is None:
                    continue
                
                edge_id = best_edge_id
                edge_data = best_edge_data
                edge_cost = best_cost  # Already calculated above
                
                # Calculate tentative g_cost
                tentative_g = g_costs[current_node] + edge_cost
                
                # Better path found?
                if neighbor not in g_costs or tentative_g < g_costs[neighbor]:
                    g_costs[neighbor] = tentative_g
                    h_cost = self._heuristic(neighbor, goal_node)
                    f_cost = tentative_g + h_cost
                    
                    came_from[neighbor] = current_node
                    edge_used[neighbor] = edge_id
                    
                    neighbor_node = AStarNode(
                        f_cost=f_cost,
                        node_id=neighbor,
                        g_cost=tentative_g,
                        h_cost=h_cost,
                        parent=current_node,
                        edge_used=edge_id
                    )
                    heapq.heappush(open_set, neighbor_node)
        
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
        total_cost: float
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
        
        # Calculate total length
        total_length = 0.0
        for edge_id in path_edges:
            for u, v, data in self.graph.edges(data=True):
                if data.get('edge_id') == edge_id:
                    total_length += data.get('length', 0.0)
                    break
        
        return {
            'nodes': path_nodes,
            'edges': path_edges,
            'cost': total_cost,
            'length': total_length,
            'num_nodes': len(path_nodes),
            'num_edges': len(path_edges),
            'algorithm': 'A*'
        }


if __name__ == "__main__":
    print("="*70)
    print("A* ROUTING ALGORITHM TEST")
    print("="*70)
    
    print("\nA* Algorithm Features:")
    print("  • Heuristic-guided search (faster than Dijkstra)")
    print("  • Optimal if heuristic is admissible")
    print("  • Best for normal vehicle routing")
    print("  • Supports cost functions: time, safety, balanced")
    print("\nUsage:")
    print("  1. Build routing graph with predicted speeds")
    print("  2. Create A* router")
    print("  3. Find path from origin to destination")
    print("  4. Get route with nodes and edges")
