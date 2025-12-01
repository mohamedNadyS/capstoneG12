"""
Diagnostic: Check edge ID mismatch between graph and SUMO network
"""

import json
import xml.etree.ElementTree as ET
import networkx as nx
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sumo_integration.sumo_parser import SUMONetworkParser

def check_edge_ids():
    print("=" * 80)
    print("EDGE ID DIAGNOSTIC")
    print("=" * 80)
    
    # Load SUMO network XML
    network_file = Path('data/generated/sumo/map.net.xml')
    print(f"\n1. Loading SUMO network: {network_file}")
    
    tree = ET.parse(network_file)
    root = tree.getroot()
    
    sumo_edges = {}
    for edge in root.findall('.//edge'):
        edge_id = edge.get('id')
        if edge_id and ':' not in edge_id:  # Skip internal edges
            sumo_edges[edge_id] = {
                'from': edge.get('from'),
                'to': edge.get('to')
            }
    
    print(f"   Found {len(sumo_edges)} edges in SUMO network")
    print(f"   Sample edge IDs: {list(sumo_edges.keys())[:5]}")
    
    # Parse with SUMONetworkParser
    print(f"\n2. Parsing with SUMONetworkParser...")
    parser = SUMONetworkParser(str(network_file))
    print(f"   Parsed {len(parser.edges)} edges")
    print(f"   Sample parsed IDs: {list(parser.edges.keys())[:5]}")
    
    # Build graph
    print(f"\n3. Building routing graph...")
    from src.routing.graph_builder import RoutingGraphBuilder
    
    graph_builder = RoutingGraphBuilder(parser)
    graph = graph_builder.build_graph()
    
    print(f"   Graph has {graph.number_of_nodes()} nodes")
    print(f"   Graph has {graph.number_of_edges()} edges")
    
    # Check edge data in graph
    print(f"\n4. Checking edge data in graph...")
    
    sample_count = 5
    for i, (u, v, key) in enumerate(graph.edges(keys=True)):
        if i >= sample_count:
            break
        
        edge_data = graph[u][v][key]
        edge_id = edge_data.get('edge_id', 'MISSING!')
        
        print(f"\n   Edge {i+1}:")
        print(f"      Nodes: {u} → {v} (key={key})")
        print(f"      Edge ID: {edge_id}")
        print(f"      In SUMO?: {'✅' if edge_id in sumo_edges else '❌'}")
        
        if edge_id not in sumo_edges:
            print(f"      ERROR: Edge ID '{edge_id}' not in SUMO network!")
            print(f"      Available edges from node {u}:")
            for eid, edata in sumo_edges.items():
                if edata['from'] == str(u):
                    print(f"         - {eid}: {edata['from']} → {edata['to']}")
    
    # Load routing metadata and check
    print(f"\n5. Checking routing metadata...")
    
    routing_file = Path('data/generated/routing_metadata.json')
    if routing_file.exists():
        with open(routing_file) as f:
            routing_data = json.load(f)
        
        routes = routing_data.get('routes', {})
        print(f"   Found {len(routes)} routes")
        
        # Check first route
        first_route = list(routes.values())[0] if routes else None
        if first_route:
            edges = first_route.get('edges', [])
            print(f"\n   Sample route edges: {edges[:5]}")
            
            # Check if they exist in SUMO
            invalid_edges = [e for e in edges if e not in sumo_edges]
            if invalid_edges:
                print(f"   ❌ Invalid edges found: {invalid_edges[:5]}")
                print(f"   These edges don't exist in SUMO network!")
            else:
                print(f"   ✅ All edges valid in SUMO network")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    check_edge_ids()
