#!/usr/bin/env python3
"""
Generate Baseline Routing (Random/Shortest Path Only)
For comparison against AI routing
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sumo_integration.sumo_parser import SUMONetworkParser
from src.routing.sumo_route_generator import SUMORouteGenerator
import networkx as nx
import json


def generate_baseline_routes(
    network_file: str,
    vehicles_file: str,
    output_dir: str,
    method: str = 'shortest'
):
    """
    Generate baseline routes using simple methods
    
    Args:
        network_file: SUMO network file
        vehicles_file: Vehicles JSON file
        output_dir: Output directory
        method: 'shortest' or 'random'
    """
    print(f"\n[BASELINE] Generating {method} path routing...")
    
    # Parse network
    print(f"[1/4] Loading network...")
    parser = SUMONetworkParser(network_file)
    
    # Build simple graph
    print(f"[2/4] Building graph...")
    G = nx.DiGraph()
    for edge in parser.edges.values():
        G.add_edge(edge.from_node, edge.to_node, 
                  weight=edge.length_m,  # Use only distance, ignore predictions
                  edge_id=edge.edge_id)
    
    # Load vehicles
    print(f"[3/4] Loading vehicles...")
    with open(vehicles_file) as f:
        vehicles_data = json.load(f)
    
    # Generate routes
    print(f"[4/4] Generating {method} routes...")
    routes = []
    failed = 0
    
    for i, vehicle in enumerate(vehicles_data):
        origin_edge = parser.edges.get(vehicle['origin_edge'])
        dest_edge = parser.edges.get(vehicle['destination_edge'])
        
        if not origin_edge or not dest_edge:
            failed += 1
            continue
        
        origin_node = origin_edge.from_node
        dest_node = dest_edge.to_node
        
        try:
            if method == 'shortest':
                # Shortest path only (no traffic consideration)
                path = nx.shortest_path(G, origin_node, dest_node, weight='weight')
            elif method == 'random':
                # Random path (pick random neighbors)
                path = _random_path(G, origin_node, dest_node, max_tries=10)
            
            # Convert node path to edge path
            edge_path = []
            for j in range(len(path) - 1):
                edge_data = G[path[j]][path[j+1]]
                edge_path.append(edge_data['edge_id'])
            
            if edge_path:
                routes.append({
                    'id': vehicle['id'],
                    'type': vehicle['vehicle_type'],
                    'edges': edge_path,
                    'depart': vehicle.get('depart_time', i)
                })
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            failed += 1
    
    print(f"   Generated {len(routes)} routes ({failed} failed)")
    
    # Save routes
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generator = SUMORouteGenerator()
    route_file = output_path / 'routes.rou.xml'
    config_file = output_path / 'simulation.sumocfg'
    
    # Generate SUMO files
    generator.generate_route_file(
        routes,
        network_file,
        str(route_file)
    )
    
    generator.generate_sumo_config(
        network_file,
        str(route_file),
        str(config_file),
        simulation_time=3600
    )
    
    # Save metadata
    metadata = {
        'method': method,
        'total_routes': len(routes),
        'failed_routes': failed,
        'routes': routes
    }
    
    with open(output_path / 'routing_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n[BASELINE] Generated files:")
    print(f"   Routes: {route_file}")
    print(f"   Config: {config_file}")
    print(f"   Metadata: {output_path / 'routing_metadata.json'}")


def _random_path(G, source, target, max_tries=10):
    """Generate a random path (for testing)"""
    for _ in range(max_tries):
        try:
            # Random walk with bias toward target
            path = [source]
            current = source
            visited = {source}
            max_steps = 20
            
            for step in range(max_steps):
                if current == target:
                    return path
                
                neighbors = [n for n in G.neighbors(current) if n not in visited]
                if not neighbors:
                    break
                
                # Pick random neighbor
                next_node = random.choice(neighbors)
                path.append(next_node)
                visited.add(next_node)
                current = next_node
            
            # If we didn't reach target, try shortest from here
            if current != target and nx.has_path(G, current, target):
                remaining = nx.shortest_path(G, current, target)
                path.extend(remaining[1:])
                return path
        except:
            continue
    
    # Fallback to shortest
    return nx.shortest_path(G, source, target, weight='weight')


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate baseline routing")
    parser.add_argument('--network', type=str, default='data/sumo/map.net.xml',
                       help='SUMO network file')
    parser.add_argument('--vehicles', type=str, default='data/generated/vehicles.json',
                       help='Vehicles JSON file')
    parser.add_argument('--output', type=str, default='data/baseline_routing',
                       help='Output directory')
    parser.add_argument('--method', type=str, default='shortest',
                       choices=['shortest', 'random'],
                       help='Routing method')
    args = parser.parse_args()
    
    generate_baseline_routes(
        args.network,
        args.vehicles,
        args.output,
        args.method
    )
    
    print(f"\n✅ Baseline routing complete!")
    print(f"\nNext step: Run simulation")
    print(f"  python scripts/4_run_sumo_gui.py \\")
    print(f"      --config {args.output}/simulation.sumocfg \\")
    print(f"      --collect-metrics \\")
    print(f"      --headless")


if __name__ == "__main__":
    main()
