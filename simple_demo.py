"""
Simplified Demo Script
Works directly with SUMO .net.xml files

Usage:
1. Ensure you have map.net.xml (your SUMO network)
2. Run: python simple_demo.py --map map.net.xml
3. Watch SUMO simulation with A* routing
"""

import os
import sys
import numpy as np
import networkx as nx
import traci
import sumolib
import heapq
from typing import Dict, List, Tuple

# ============================================================================
# STEP 1: LOAD & PREPARE MAP
# ============================================================================

def load_map_from_sumo(net_file: str):
    """Load map directly from SUMO .net.xml file"""
    print(f"📍 Loading SUMO network: {net_file}")
    
    import sumolib
    
    # Load SUMO network
    sumo_net = sumolib.net.readNet(net_file)
    
    # Build NetworkX graph
    G = nx.DiGraph()
    edges = {}
    
    for edge in sumo_net.getEdges():
        if edge.getFunction() == 'internal':
            continue  # Skip internal edges (junctions)
        
        edge_id = edge.getID()
        from_node = edge.getFromNode().getID()
        to_node = edge.getToNode().getID()
        
        length = edge.getLength()
        speed = edge.getSpeed()  # m/s
        lanes = len(edge.getLanes())
        
        # Add nodes
        G.add_node(from_node)
        G.add_node(to_node)
        
        # Add edge
        G.add_edge(from_node, to_node, 
                  edge_id=edge_id,
                  weight=(length / speed) if speed > 0 else length / 13.9)
        
        edges[edge_id] = {
            'from': from_node,
            'to': to_node,
            'length': length,
            'maxspeed': speed * 3.6,  # Convert to km/h
            'travel_time': (length / speed) if speed > 0 else length / 13.9,
            'vehicle_count': 0
        }
    
    print(f"  ✓ Loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    return G, edges


# ============================================================================
# STEP 2: A* ROUTING
# ============================================================================

def astar_route(G, edges, start_node, goal_node, congestion_data=None):
    """
    A* algorithm with congestion awareness
    
    Args:
        G: NetworkX graph
        edges: Edge dictionary
        start_node, goal_node: Node IDs
        congestion_data: Dict of {edge_id: vehicle_count}
    """
    print(f"  🔍 A* routing: {start_node} → {goal_node}")
    
    def heuristic(n1, n2):
        """Haversine distance / 60 km/h"""
        try:
            lat1, lon1 = G.nodes[n1]['y'], G.nodes[n1]['x']
            lat2, lon2 = G.nodes[n2]['y'], G.nodes[n2]['x']
            
            R = 6371000
            dlat = np.radians(lat2 - lat1)
            dlon = np.radians(lon2 - lon1)
            
            a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            distance = R * c
            
            return (distance / 1000) / 60 * 3600  # Time at 60 km/h
        except:
            return 0
    
    def edge_cost(u, v, key):
        """Cost with congestion penalty"""
        edge_id = f"{u}_{v}_{key}"
        
        if edge_id not in edges:
            return float('inf')
        
        base_time = edges[edge_id]['travel_time']
        
        # Apply congestion penalty
        if congestion_data and edge_id in congestion_data:
            load = congestion_data[edge_id]
            if load > 30:
                base_time *= 2.0  # Heavy congestion
            elif load > 15:
                base_time *= 1.5  # Medium congestion
        
        return base_time
    
    # A* implementation
    open_set = [(0, start_node, None, None)]
    g_score = {start_node: 0}
    came_from = {}
    closed = set()
    
    while open_set:
        f, current, parent, key = heapq.heappop(open_set)
        
        if current == goal_node:
            # Reconstruct path
            path = [goal_node]
            edges_path = []
            node = goal_node
            
            while node in came_from:
                parent, key = came_from[node]
                path.append(parent)
                edges_path.append(f"{parent}_{node}_{key}")
                node = parent
            
            path.reverse()
            edges_path.reverse()
            
            print(f"  ✓ Route found: {len(path)} nodes, {g_score[goal_node]:.1f}s")
            return path, edges_path
        
        if current in closed:
            continue
        closed.add(current)
        
        if parent is not None:
            came_from[current] = (parent, key)
        
        # Explore neighbors
        for neighbor in G.successors(current):
            if neighbor in closed:
                continue
            
            # Find best edge
            best_cost = float('inf')
            best_key = None
            
            for k in G[current][neighbor]:
                cost = edge_cost(current, neighbor, k)
                if cost < best_cost:
                    best_cost = cost
                    best_key = k
            
            if best_cost == float('inf'):
                continue
            
            tentative_g = g_score[current] + best_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                h = heuristic(neighbor, goal_node)
                f = tentative_g + h
                heapq.heappush(open_set, (f, neighbor, current, best_key))
    
    print(f"  ❌ No route found")
    return None, None


# ============================================================================
# STEP 3: EXPORT TO SUMO
# ============================================================================

def create_sumo_config(net_file):
    """Create SUMO config for existing network file"""
    print(f"\n📦 Creating SUMO configuration...")
    
    cfg_file = "simulation.sumocfg"
    cfg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{net_file}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
    </time>
</configuration>"""
    
    with open(cfg_file, 'w') as f:
        f.write(cfg_content)
    
    print(f"  ✓ Created: {cfg_file}")
    return cfg_file, net_file


# ============================================================================
# STEP 4: RUN SIMULATION
# ============================================================================

def run_demo(net_file: str, gui: bool = True):
    """
    Complete demo: Load SUMO network → Route with A* → Simulate
    """
    print("="*70)
    print(" "*15 + "A* + SUMO DEMO")
    print("="*70)
    
    # Load SUMO network
    G, edges = load_map_from_sumo(net_file)
    
    # Get some nodes for demo
    nodes = list(G.nodes)
    if len(nodes) < 2:
        print("❌ Map too small (need at least 2 nodes)")
        return
    
    start_node = nodes[0]
    goal_node = nodes[-1]
    
    print(f"\n🎯 Demo route: Node {start_node} → Node {goal_node}")
    
    # Calculate route with A*
    path_nodes, path_edges = astar_route(G, edges, start_node, goal_node)
    
    if not path_nodes:
        print("❌ Could not find route")
        return
    
    # Create SUMO config
    cfg_file, _ = create_sumo_config(net_file)
    
    # Start SUMO
    print(f"\n🚀 Starting SUMO...")
    
    sumo_cmd = ["sumo-gui" if gui else "sumo", "-c", cfg_file]
    traci.start(sumo_cmd)
    
    try:
        print("\n▶️  Simulation running...")
        print("   (Close SUMO window to stop)")
        
        # Get SUMO edge IDs
        sumo_edges = traci.edge.getIDList()
        
        if len(sumo_edges) < 2:
            print("⚠️  No edges in SUMO network")
            return
        
        # Spawn test vehicle
        start_edge = sumo_edges[0]
        
        traci.vehicle.add("car_0", "", typeID="DEFAULT_VEHTYPE")
        
        # Set route using calculated path
        if path_edges and all(e in sumo_edges for e in path_edges[:5]):
            route_edges = path_edges[:min(5, len(path_edges))]
        else:
            # Fallback to simple route
            route_edges = sumo_edges[:min(5, len(sumo_edges))]
        
        try:
            traci.vehicle.setRoute("car_0", route_edges)
            print(f"  ✓ Route set: {route_edges}")
        except Exception as e:
            print(f"  ⚠️  Could not set route: {e}")
        
        # Run simulation
        step = 0
        while step < 500 and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            
            if step % 50 == 0:
                num_vehicles = len(traci.vehicle.getIDList())
                print(f"  Step {step}: {num_vehicles} vehicles")
        
        print("\n✓ Simulation complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        traci.close()


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='A* + SUMO Demo')
    parser.add_argument('--map', type=str, default='map.net.xml',
                       help='Path to SUMO .net.xml file')
    parser.add_argument('--no-gui', action='store_true',
                       help='Run without GUI')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.map):
        print(f"❌ Network file not found: {args.map}")
        print("\n💡 Usage:")
        print(f"   python simple_demo.py --map map.net.xml")
        print(f"\n   Or place your SUMO network as 'map.net.xml'")
        sys.exit(1)
    
    try:
        run_demo(args.map, gui=not args.no_gui)
    except KeyboardInterrupt:
        print("\n\n👋 Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()