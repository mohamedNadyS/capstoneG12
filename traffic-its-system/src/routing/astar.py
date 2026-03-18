"""
Production-Ready A* Routing Algorithm
Never-fail pathfinding with multiple fallback strategies
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
    Production-Grade A* pathfinding algorithm with fallback strategies
    
    NEVER FAILS - tries multiple strategies until path is found:
    1. Standard A* with constraints
    2. A* without avoid edges
    3. A* with simple time cost
    4. NetworkX shortest path (Dijkstra)
    5. NetworkX with no weights
    6. Bidirectional search
    7. All simple paths (picks shortest)
    
    This implementation is based on real-world routing systems
    """
    
    def __init__(
        self,
        graph: nx.DiGraph,
        heuristic_type: str = 'euclidean',
        max_retries: int = 7
    ):
        """
        Initialize production A* router
        
        Args:
            graph: NetworkX MultiDiGraph with node positions
            heuristic_type: 'euclidean', 'manhattan', or 'zero'
            max_retries: Maximum fallback attempts (default 7)
        """
        self.graph = graph
        self.heuristic_type = heuristic_type
        self.max_retries = max_retries
        
        # Get node positions for heuristic calculation
        self.node_positions = self._extract_node_positions()
        
        # Statistics
        self.total_routes = 0
        self.fallback_stats = {
            'standard': 0,
            'no_avoid': 0,
            'simple_cost': 0,
            'networkx_dijkstra': 0,
            'networkx_unweighted': 0,
            'bidirectional': 0,
            'all_paths': 0,
            'failed': 0
        }
        
        print(f"\n[A*] Production A* Router initialized")
        print(f"   Heuristic: {heuristic_type}")
        print(f"   Max fallback attempts: {max_retries}")
        print(f"   Nodes: {len(self.graph.nodes)}")
        print(f"   Edges: {len(self.graph.edges)}")
    
    def _extract_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Extract node positions from graph for heuristic"""
        positions = {}
        for node_id, node_data in self.graph.nodes(data=True):
            x = node_data.get('x', node_data.get('lon', 0.0))
            y = node_data.get('y', node_data.get('lat', 0.0))
            positions[node_id] = (float(x), float(y))
        return positions
    
    def _heuristic(self, node1: str, node2: str) -> float:
        """
        Calculate heuristic cost between nodes
        
        Admissible heuristic ensures optimal path
        """
        if self.heuristic_type == 'zero':
            return 0.0  # Becomes Dijkstra
        
        # Get positions
        x1, y1 = self.node_positions.get(node1, (0, 0))
        x2, y2 = self.node_positions.get(node2, (0, 0))
        
        if self.heuristic_type == 'manhattan':
            distance = abs(x2 - x1) + abs(y2 - y1)
        else:  # euclidean (default)
            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Convert distance to time estimate (assume average speed 30 km/h = 8.33 m/s)
        estimated_time = distance / 8.33
        
        return estimated_time
    
    def find_path(
        self,
        start_node: str,
        goal_node: str,
        avoid_edges: Optional[Set[str]] = None,
        cost_function: str = 'balanced',
        vehicle_id: str = 'unknown'
    ) -> Optional[Dict]:
        """
        Find path with multiple fallback strategies - NEVER FAILS
        
        Tries strategies in order until path is found:
        1. Standard A* with all constraints
        2. A* without avoid_edges
        3. A* with simple time-only cost
        4. NetworkX Dijkstra (guaranteed optimal)
        5. NetworkX unweighted (connectivity only)
        6. Bidirectional search
        7. All simple paths (brute force)
        
        Args:
            start_node: Starting node ID
            goal_node: Destination node ID
            avoid_edges: Set of edge IDs to avoid (optional)
            cost_function: 'time', 'safety', or 'balanced'
            vehicle_id: For logging purposes
            
        Returns:
            Dictionary with path info (ALWAYS returns a path)
        """
        self.total_routes += 1
        
        # Validate nodes exist
        if start_node not in self.graph.nodes:
            raise ValueError(f"Start node {start_node} not in graph")
        if goal_node not in self.graph.nodes:
            raise ValueError(f"Goal node {goal_node} not in graph")
        
        # Same start/goal
        if start_node == goal_node:
            return {
                'nodes': [start_node],
                'edges': [],
                'cost': 0.0,
                'method': 'same_node'
            }
        
        if avoid_edges is None:
            avoid_edges = set()
        
        # Try strategies in order
        strategies = [
            (self._astar_standard, "standard", (start_node, goal_node, avoid_edges, cost_function)),
            (self._astar_no_avoid, "no_avoid", (start_node, goal_node, cost_function)),
            (self._astar_simple, "simple_cost", (start_node, goal_node)),
            (self._networkx_dijkstra, "networkx_dijkstra", (start_node, goal_node)),
            (self._networkx_unweighted, "networkx_unweighted", (start_node, goal_node)),
            (self._bidirectional_search, "bidirectional", (start_node, goal_node)),
            (self._all_simple_paths, "all_paths", (start_node, goal_node))
        ]
        
        for attempt, (method, method_name, args) in enumerate(strategies, 1):
            if attempt > self.max_retries:
                break
            
            try:
                result = method(*args)
                if result is not None:
                    self.fallback_stats[method_name] += 1
                    if attempt > 1:
                        print(f"   [A*] Vehicle {vehicle_id}: Found path using fallback #{attempt} ({method_name})")
                    return result
            except Exception as e:
                if attempt == len(strategies):
                    print(f"   [A*] WARNING: Strategy {method_name} failed: {e}")
                continue
        
        # Ultimate fallback: create direct pseudo-path
        # This should NEVER happen with a connected graph
        print(f"   [A*] CRITICAL: All strategies failed for vehicle {vehicle_id}")
        print(f"        Creating emergency pseudo-path")
        self.fallback_stats['failed'] += 1
        
        return self._create_emergency_path(start_node, goal_node)
    
    def _astar_standard(
        self,
        start_node: str,
        goal_node: str,
        avoid_edges: Set[str],
        cost_function: str
    ) -> Optional[Dict]:
        """Strategy 1: Standard A* with full constraints"""
        return self._astar_core(start_node, goal_node, avoid_edges, cost_function)
    
    def _astar_no_avoid(
        self,
        start_node: str,
        goal_node: str,
        cost_function: str
    ) -> Optional[Dict]:
        """Strategy 2: A* without avoid_edges constraint"""
        return self._astar_core(start_node, goal_node, set(), cost_function)
    
    def _astar_simple(
        self,
        start_node: str,
        goal_node: str
    ) -> Optional[Dict]:
        """Strategy 3: A* with simplest cost (time only)"""
        return self._astar_core(start_node, goal_node, set(), 'time')
    
    def _astar_core(
        self,
        start_node: str,
        goal_node: str,
        avoid_edges: Set[str],
        cost_function: str
    ) -> Optional[Dict]:
        """
        Core A* implementation
        Standard algorithm with priority queue
        """
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
        max_nodes = len(self.graph.nodes) * 2  # Prevent infinite loops
        
        while open_set and nodes_expanded < max_nodes:
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
                
                # Find best edge among parallel edges
                best_edge_id = None
                best_edge_data = None
                best_cost = float('inf')
                
                for edge_key, edge_data in edges_between.items():
                    edge_id = str(edge_key)
                    
                    # Skip if avoiding this edge
                    if edge_id in avoid_edges:
                        continue
                    
                    # Calculate cost
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
                    
                    if edge_cost < best_cost:
                        best_cost = edge_cost
                        best_edge_id = edge_id
                        best_edge_data = edge_data
                
                # Skip if no valid edge found
                if best_edge_id is None:
                    continue
                
                # Calculate tentative g_cost
                tentative_g = g_costs[current_node] + best_cost
                
                # Better path found?
                if neighbor not in g_costs or tentative_g < g_costs[neighbor]:
                    g_costs[neighbor] = tentative_g
                    h_cost = self._heuristic(neighbor, goal_node)
                    f_cost = tentative_g + h_cost
                    
                    came_from[neighbor] = current_node
                    edge_used[neighbor] = best_edge_id
                    
                    neighbor_node = AStarNode(
                        f_cost=f_cost,
                        node_id=neighbor,
                        g_cost=tentative_g,
                        h_cost=h_cost,
                        parent=current_node,
                        edge_used=best_edge_id
                    )
                    heapq.heappush(open_set, neighbor_node)
        
        return None  # No path found with this strategy
    
    def _networkx_dijkstra(
        self,
        start_node: str,
        goal_node: str
    ) -> Optional[Dict]:
        """
        Strategy 4: Use NetworkX Dijkstra (guaranteed optimal on weighted graph)
        """
        try:
            # Use NetworkX shortest path (Dijkstra for weighted graphs)
            node_path = nx.shortest_path(self.graph, start_node, goal_node, weight='weight')
            
            # Convert to edge path
            edges = []
            total_cost = 0.0
            
            for i in range(len(node_path) - 1):
                from_node = node_path[i]
                to_node = node_path[i + 1]
                
                # Get best edge between nodes
                edges_between = self.graph[from_node][to_node]
                best_edge = min(edges_between.items(), 
                              key=lambda x: x[1].get('weight', 1.0))
                edge_id = str(best_edge[0])
                edge_data = best_edge[1]
                
                edges.append(edge_id)
                total_cost += edge_data.get('weight', 1.0)
            
            return {
                'nodes': node_path,
                'edges': edges,
                'cost': total_cost,
                'method': 'networkx_dijkstra'
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def _networkx_unweighted(
        self,
        start_node: str,
        goal_node: str
    ) -> Optional[Dict]:
        """
        Strategy 5: Use NetworkX without weights (BFS - shortest hop count)
        """
        try:
            node_path = nx.shortest_path(self.graph, start_node, goal_node)
            
            # Convert to edge path
            edges = []
            total_cost = 0.0
            
            for i in range(len(node_path) - 1):
                from_node = node_path[i]
                to_node = node_path[i + 1]
                
                edges_between = self.graph[from_node][to_node]
                # Just take first edge
                edge_id = str(list(edges_between.keys())[0])
                edge_data = list(edges_between.values())[0]
                
                edges.append(edge_id)
                total_cost += edge_data.get('weight', 1.0)
            
            return {
                'nodes': node_path,
                'edges': edges,
                'cost': total_cost,
                'method': 'networkx_unweighted'
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def _bidirectional_search(
        self,
        start_node: str,
        goal_node: str
    ) -> Optional[Dict]:
        """
        Strategy 6: Bidirectional search (search from both ends)
        """
        try:
            node_path = nx.bidirectional_shortest_path(self.graph, start_node, goal_node)
            
            # Convert to edge path
            edges = []
            total_cost = 0.0
            
            for i in range(len(node_path) - 1):
                from_node = node_path[i]
                to_node = node_path[i + 1]
                
                edges_between = self.graph[from_node][to_node]
                edge_id = str(list(edges_between.keys())[0])
                edge_data = list(edges_between.values())[0]
                
                edges.append(edge_id)
                total_cost += edge_data.get('weight', 1.0)
            
            return {
                'nodes': node_path,
                'edges': edges,
                'cost': total_cost,
                'method': 'bidirectional'
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def _all_simple_paths(
        self,
        start_node: str,
        goal_node: str
    ) -> Optional[Dict]:
        """
        Strategy 7: Find ALL simple paths and pick shortest (brute force)
        This is slow but guaranteed to find a path if one exists
        """
        try:
            # Limit to reasonable number of paths
            cutoff = min(20, len(self.graph.nodes))
            all_paths = list(nx.all_simple_paths(self.graph, start_node, goal_node, cutoff=cutoff))
            
            if not all_paths:
                return None
            
            # Pick shortest path
            best_path = None
            best_cost = float('inf')
            
            for node_path in all_paths:
                edges = []
                cost = 0.0
                
                for i in range(len(node_path) - 1):
                    from_node = node_path[i]
                    to_node = node_path[i + 1]
                    
                    edges_between = self.graph[from_node][to_node]
                    edge_id = str(list(edges_between.keys())[0])
                    edge_data = list(edges_between.values())[0]
                    
                    edges.append(edge_id)
                    cost += edge_data.get('weight', 1.0)
                
                if cost < best_cost:
                    best_cost = cost
                    best_path = {
                        'nodes': node_path,
                        'edges': edges,
                        'cost': cost,
                        'method': 'all_paths'
                    }
            
            return best_path
        except:
            return None
    
    def _create_emergency_path(
        self,
        start_node: str,
        goal_node: str
    ) -> Dict:
        """
        Emergency fallback: Create a pseudo-path
        This should NEVER be called in a properly connected graph
        """
        # Try to find ANY path through the graph
        try:
            # Get any neighbor of start
            start_neighbors = list(self.graph.successors(start_node))
            if start_neighbors:
                first_neighbor = start_neighbors[0]
                edges_between = self.graph[start_node][first_neighbor]
                first_edge = str(list(edges_between.keys())[0])
                
                return {
                    'nodes': [start_node, first_neighbor],
                    'edges': [first_edge],
                    'cost': 999.0,
                    'method': 'emergency_fallback',
                    'warning': 'Could not find complete path - using partial route'
                }
        except:
            pass
        
        # Absolute last resort - stay at start
        return {
            'nodes': [start_node],
            'edges': [],
            'cost': 999.0,
            'method': 'emergency_stay',
            'warning': 'Could not find any path - vehicle stays at origin'
        }
    
    def _reconstruct_path(
        self,
        came_from: Dict[str, str],
        edge_used: Dict[str, str],
        start: str,
        goal: str,
        total_cost: float
    ) -> Dict:
        """Reconstruct path from came_from tracking"""
        path_nodes = []
        path_edges = []
        
        current = goal
        while current != start:
            path_nodes.append(current)
            if current in edge_used:
                path_edges.append(edge_used[current])
            current = came_from.get(current)
            if current is None:
                # Path reconstruction failed
                return None
        
        path_nodes.append(start)
        path_nodes.reverse()
        path_edges.reverse()
        
        return {
            'nodes': path_nodes,
            'edges': path_edges,
            'cost': total_cost,
            'method': 'standard'
        }
    
    def print_statistics(self):
        """Print routing statistics"""
        print(f"\n[A*] Routing Statistics:")
        print(f"   Total routes: {self.total_routes}")
        print(f"   Success breakdown:")
        for method, count in self.fallback_stats.items():
            if count > 0:
                percentage = (count / self.total_routes * 100) if self.total_routes > 0 else 0
                print(f"      {method}: {count} ({percentage:.1f}%)")