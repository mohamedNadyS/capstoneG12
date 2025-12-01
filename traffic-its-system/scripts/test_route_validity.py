"""
Test script to verify edge connection fix is working correctly.

This script checks if your route generation is creating valid SUMO routes.
Run this BEFORE and AFTER applying the fix to see the difference.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

def load_network(network_file):
    """Load SUMO network and return edge mapping"""
    tree = ET.parse(network_file)
    root = tree.getroot()
    
    edges = {}
    for edge in root.findall('.//edge'):
        edge_id = edge.get('id')
        if edge_id and ':' not in edge_id:  # Skip internal edges
            edges[edge_id] = {
                'from': edge.get('from'),
                'to': edge.get('to')
            }
    
    return edges

def check_route_validity(edge_path, edges):
    """Check if a route has valid edge connections"""
    problems = []
    
    for i in range(len(edge_path) - 1):
        edge1_id = edge_path[i]
        edge2_id = edge_path[i + 1]
        
        # Check edges exist
        if edge1_id not in edges:
            problems.append(f"Edge {edge1_id} not found in network")
            continue
        if edge2_id not in edges:
            problems.append(f"Edge {edge2_id} not found in network")
            continue
        
        # Check edges connect
        edge1 = edges[edge1_id]
        edge2 = edges[edge2_id]
        
        if edge1['to'] != edge2['from']:
            problems.append(
                f"Edge {edge1_id} (ends at {edge1['to']}) "
                f"does not connect to edge {edge2_id} (starts at {edge2['from']})"
            )
    
    return problems

def main():
    print("=" * 80)
    print("ROUTE VALIDITY CHECKER")
    print("=" * 80)
    
    # Paths - Windows compatible
    base_dir = Path('data/generated')
    network_file = base_dir / 'sumo' / 'map.net.xml'
    routing_file = base_dir / 'routing_metadata.json'
    
    # Alternative paths to check
    alt_network = Path('data/generated/map.net.xml')
    alt_routing = Path('data/generated/routing_metadata.json')
    
    # Check files exist (try alternatives)
    if not network_file.exists():
        if alt_network.exists():
            network_file = alt_network
            print(f"✓ Using alternative network path")
        else:
            print(f"❌ Network file not found!")
            print(f"   Tried: {network_file}")
            print(f"   Tried: {alt_network}")
            print(f"\n💡 Make sure you've run: python scripts/3_generate_routes.py")
            return False
    
    if not routing_file.exists():
        if alt_routing.exists():
            routing_file = alt_routing
            print(f"✓ Using alternative routing path")
        else:
            print(f"❌ Routing file not found!")
            print(f"   Tried: {routing_file}")
            print(f"   Tried: {alt_routing}")
            print(f"\n💡 Make sure you've run: python scripts/3_generate_routes.py")
            return False
    
    print(f"\n📁 Loading network: {network_file}")
    edges = load_network(network_file)
    print(f"   Found {len(edges)} edges")
    
    print(f"\n📁 Loading routes: {routing_file}")
    with open(routing_file, 'r') as f:
        routing_data = json.load(f)
    
    routes = routing_data.get('routes', {})
    print(f"   Found {len(routes)} routes")
    
    # Check all routes
    print(f"\n🔍 Checking route validity...")
    print("-" * 80)
    
    valid_count = 0
    invalid_count = 0
    total_problems = 0
    
    for vehicle_id, route_data in routes.items():
        edge_path = route_data.get('edges', [])
        
        if not edge_path:
            continue
        
        problems = check_route_validity(edge_path, edges)
        
        if problems:
            invalid_count += 1
            total_problems += len(problems)
            
            if invalid_count <= 5:  # Show first 5 problem routes
                print(f"\n❌ {vehicle_id}:")
                print(f"   Route: {' → '.join(edge_path[:5])}{'...' if len(edge_path) > 5 else ''}")
                for problem in problems[:3]:  # Show first 3 problems
                    print(f"   • {problem}")
        else:
            valid_count += 1
    
    # Summary
    total_routes = len([r for r in routes.values() if r.get('edges')])
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"✅ Valid routes:   {valid_count:4d} ({valid_count/total_routes*100:.1f}%)")
    print(f"❌ Invalid routes: {invalid_count:4d} ({invalid_count/total_routes*100:.1f}%)")
    print(f"⚠️  Total problems: {total_problems:4d}")
    
    if invalid_count == 0:
        print("\n🎉 SUCCESS! All routes are valid!")
        print("   Your SUMO simulation should work correctly.")
    else:
        print("\n⚠️  PROBLEM DETECTED!")
        print("   Your routes have edge connection problems.")
        print("   The MultiDiGraph fix should have resolved this.")
        print("   Try regenerating routes: python scripts/3_generate_routes.py")
    
    print("=" * 80)
    
    return invalid_count == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
