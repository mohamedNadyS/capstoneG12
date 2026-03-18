"""
Baseline Routing - SUMO's Built-in Shortest Path
No AI, no predictions, just pure distance-based routing
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sumo_integration.sumo_parser import SUMONetworkParser
import networkx as nx

def generate_baseline_routes(vehicles_file, output_dir):
    """Generate routes using only shortest path by distance"""
    
    print("="*70)
    print("BASELINE ROUTING - SHORTEST PATH ONLY")
    print("="*70)
    
    # Load vehicles
    print("\n[1/4] Loading vehicles...")
    with open(vehicles_file, 'r') as f:
        vehicles_data = json.load(f)
    if isinstance(vehicles_data, list):
        vehicles = vehicles_data
    elif isinstance(vehicles_data, dict) and 'vehicles' in vehicles_data:
        vehicles = vehicles_data['vehicles']
    else:
        print("❌ Error: Unexpected vehicles.json format")
        return
    print(f"   Loaded {len(vehicles)} vehicles")
    
    # Parse network
    print("\n[2/4] Parsing SUMO network...")
    network_file = Path('data/sumo/map.net.xml')
    parser = SUMONetworkParser(str(network_file))
    print(f"   Nodes: {len(parser.nodes)}, Edges: {len(parser.edges)}")
    
    # Build simple graph (distance only)
    print("\n[3/4] Building distance-based graph...")
    graph = nx.MultiDiGraph()
    
    for node_id in parser.nodes:
        graph.add_node(node_id)
    
    for edge_id, edge in parser.edges.items():
        graph.add_edge(
            edge.from_node,
            edge.to_node,
            key=edge_id,
            edge_id=edge_id,
            weight=edge.length  # ONLY DISTANCE!
        )
    
    print(f"   Graph ready: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    
    # Route vehicles
    print("\n[4/4] Routing vehicles (shortest path by distance)...")
    routed = 0
    skipped = 0
    routes = []
    
    for vehicle in vehicles:
        # Get origin and destination - try multiple field name variations
        origin_edge_id = vehicle.get('origin_edge') or vehicle.get('origin') or vehicle.get('from_edge')
        dest_edge_id = vehicle.get('destination_edge') or vehicle.get('destination') or vehicle.get('to_edge')
        vehicle_type = vehicle.get('vehicle_type') or vehicle.get('type', 'normal')
        vehicle_id = vehicle.get('id', f'vehicle_{routed}')
        
        if not origin_edge_id or not dest_edge_id:
            print(f"   ⚠️  Skipping {vehicle_id}: missing origin or destination")
            skipped += 1
            continue
        
        # Convert edge IDs to nodes for routing
        origin_edge = parser.edges.get(str(origin_edge_id))
        dest_edge = parser.edges.get(str(dest_edge_id))
        
        if not origin_edge or not dest_edge:
            print(f"   ⚠️  Skipping {vehicle_id}: edge not found in network")
            skipped += 1
            continue
        
        # Use from_node of origin edge and to_node of destination edge
        origin_node = origin_edge.from_node
        dest_node = dest_edge.to_node
        
        # Skip same origin/dest
        if origin_node == dest_node:
            skipped += 1
            continue
        
        # Find shortest path by distance
        try:
            node_path = nx.shortest_path(graph, origin_node, dest_node, weight='weight')
            
            # Convert to edges
            edge_path = []
            for i in range(len(node_path) - 1):
                from_node = node_path[i]
                to_node = node_path[i + 1]
                
                # Get edge between nodes
                edges = graph[from_node][to_node]
                edge_id = list(edges.keys())[0]  # First edge
                edge_path.append(edge_id)
            
            if edge_path:
                routes.append({
                    'vehicle_id': vehicle_id,
                    'vehicle_type': vehicle_type,
                    'origin': origin_node,
                    'destination': dest_node,
                    'edges': edge_path,
                    'depart_time': vehicle.get('depart_time', 0)
                })
                routed += 1
        except nx.NetworkXNoPath:
            skipped += 1
    
    print(f"   Routed: {routed} vehicles")
    print(f"   Skipped: {skipped} vehicles (no path)")
    
    # Save routes
    print("\n[5/5] Saving baseline routes...")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save routing metadata
    metadata = {
        'method': 'baseline_shortest_path',
        'description': 'SUMO shortest path by distance only (no AI)',
        'total_vehicles': len(vehicles),
        'routed': routed,
        'skipped': skipped,
        'routes': {r['vehicle_id']: r for r in routes}
    }
    
    with open(output_dir / 'routing_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Generate SUMO files
    from src.routing.sumo_route_generator import SUMORouteGenerator
    generator = SUMORouteGenerator()
    
    # Create routes dict for generator
    routes_dict = {}
    for route in routes:
        routes_dict[route['vehicle_id']] = {
            'vehicle_type': route['vehicle_type'],
            'edges': route['edges']
        }
    
    generator.generate_route_file(
        routes_dict,
        str(output_dir / 'routes.rou.xml'),
        simulation_time=3600
    )
    
    generator.generate_sumo_config(
        network_file='sumo/map.net.xml',
        route_file='routes.rou.xml',
        output_file=str(output_dir / 'simulation.sumocfg')
    )
    
    print(f"\n✅ Baseline routing complete!")
    print(f"   Files saved to: {output_dir}")
    print(f"   Run: sumo-gui -c {output_dir / 'simulation.sumocfg'}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate baseline routes (shortest path only)')
    parser.add_argument('--vehicles', default='data/generated/vehicles.json', help='Vehicles file')
    parser.add_argument('--output', default='data/baseline', help='Output directory')
    
    args = parser.parse_args()
    
    generate_baseline_routes(args.vehicles, args.output)
