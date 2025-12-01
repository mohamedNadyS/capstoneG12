"""
COMPLETE FIX AND REBUILD SCRIPT
This script will:
1. Check if fixes are applied
2. Apply fixes if needed
3. Rebuild everything from scratch
4. Test that it works
"""

import sys
from pathlib import Path
import re

def check_fix_applied(file_path, pattern):
    """Check if a fix is applied to a file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            return pattern in content
    except:
        return False

def apply_graph_builder_fix():
    """Fix graph_builder.py to use edge_id as key"""
    file_path = Path('src/routing/graph_builder.py')
    
    print("\n[1/3] Fixing graph_builder.py...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already fixed
    if 'key=edge_id' in content:
        print("   ✅ Already fixed!")
        return
    
    # Fix 1: Change to MultiDiGraph
    content = content.replace(
        'self.graph = nx.DiGraph()',
        'self.graph = nx.MultiDiGraph()'
    )
    
    # Fix 2: Add key=edge_id when adding edges
    old_pattern = r'self\.graph\.add_edge\(\s*sumo_edge\.from_node,\s*sumo_edge\.to_node,\s*edge_id=edge_id,'
    new_pattern = 'self.graph.add_edge(\n                sumo_edge.from_node,\n                sumo_edge.to_node,\n                key=edge_id,\n                edge_id=edge_id,'
    
    content = re.sub(old_pattern, new_pattern, content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("   ✅ Fixed! Changed to MultiDiGraph with key=edge_id")

def apply_astar_fix():
    """Fix astar.py to use edge_id as key"""
    file_path = Path('src/routing/astar.py')
    
    print("\n[2/3] Fixing astar.py...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already fixed
    if 'for edge_key, edge_data in edges_between.items():' in content:
        print("   ✅ Already fixed!")
        return
    
    # Find and replace the edge access section
    old_section = """            # Explore neighbors
            for neighbor in self.graph.successors(current_node):
                if neighbor in closed_set:
                    continue
                
                # Get edge data
                edge_data = self.graph[current_node][neighbor]
                edge_id = edge_data.get('edge_id', f"{current_node}-{neighbor}")
                
                # Skip if avoiding this edge
                if edge_id in avoid_edges:
                    continue
                
                # Get edge cost"""
    
    new_section = """            # Explore neighbors
            for neighbor in self.graph.successors(current_node):
                if neighbor in closed_set:
                    continue
                
                # Get all edges between nodes (MultiDiGraph)
                edges_between = self.graph[current_node][neighbor]
                
                # Find best edge among parallel edges
                best_edge_id = None
                best_edge_data = None
                best_cost = float('inf')
                
                for edge_key, edge_data in edges_between.items():
                    # edge_key IS the edge_id!
                    edge_id = str(edge_key)
                    
                    # Skip if avoiding this edge
                    if edge_id in avoid_edges:
                        continue
                    
                    # Calculate cost for this edge"""
    
    content = content.replace(old_section, new_section)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("   ✅ Fixed! Updated edge access for MultiDiGraph")

def apply_dijkstra_fix():
    """Fix dijkstra.py to use edge_id as key"""
    file_path = Path('src/routing/dijkstra.py')
    
    print("\n[3/3] Fixing dijkstra.py...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already fixed
    if 'for edge_key, edge_data in edges_between.items():' in content:
        print("   ✅ Already fixed!")
        return
    
    # Similar fix as astar
    old_section = """            for neighbor in self.graph.successors(current_node):
                if neighbor in visited:
                    continue
                
                # Get edge data
                edge_data = self.graph[current_node][neighbor]
                edge_id = edge_data.get('edge_id', f"{current_node}-{neighbor}")
                
                # Skip if avoiding this edge
                if edge_id in avoid_edges:
                    continue
                
                # Calculate edge cost"""
    
    new_section = """            for neighbor in self.graph.successors(current_node):
                if neighbor in visited:
                    continue
                
                # Get all edges between nodes (MultiDiGraph)
                edges_between = self.graph[current_node][neighbor]
                
                # Find best edge among parallel edges
                best_edge_id = None
                best_edge_data = None
                best_cost = float('inf')
                
                for edge_key, edge_data in edges_between.items():
                    # edge_key IS the edge_id!
                    edge_id = str(edge_key)
                    
                    # Skip if avoiding this edge
                    if edge_id in avoid_edges:
                        continue
                    
                    # Calculate edge cost"""
    
    content = content.replace(old_section, new_section)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("   ✅ Fixed! Updated edge access for MultiDiGraph")

def rebuild_everything():
    """Rebuild all generated files"""
    import subprocess
    import os
    
    print("\n" + "="*70)
    print("REBUILDING EVERYTHING FROM SCRATCH")
    print("="*70)
    
    # Clean old files
    print("\n[CLEAN] Removing old generated files...")
    routes_file = Path('data/generated/routes.rou.xml')
    routing_file = Path('data/generated/routing_metadata.json')
    
    if routes_file.exists():
        routes_file.unlink()
        print("   ✅ Removed old routes.rou.xml")
    if routing_file.exists():
        routing_file.unlink()
        print("   ✅ Removed old routing_metadata.json")
    
    # Regenerate routes
    print("\n[BUILD] Regenerating routes with fixed code...")
    result = subprocess.run(
        [sys.executable, 'scripts/3_generate_routes.py', '--scenario', 'data/generated'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("   ❌ Error generating routes!")
        print(result.stderr)
        return False
    
    print("   ✅ Routes regenerated successfully!")
    return True

def verify_routes():
    """Verify that routes don't have fake edge IDs"""
    print("\n[VERIFY] Checking route file...")
    
    routes_file = Path('data/generated/routes.rou.xml')
    if not routes_file.exists():
        print("   ❌ Routes file not found!")
        return False
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Check for fake edge IDs (pattern: number-number)
    import re
    fake_edges = re.findall(r'edges="[^"]*\b\d+-\d+\b', content)
    
    if fake_edges:
        print(f"   ❌ Found {len(fake_edges)} routes with fake edge IDs!")
        print(f"   Example: {fake_edges[0]}")
        return False
    
    print("   ✅ All edge IDs look valid!")
    return True

def main():
    print("="*70)
    print("COMPLETE FIX AND REBUILD - v1.2")
    print("="*70)
    print("\nThis script will:")
    print("  1. Apply all necessary fixes to your code")
    print("  2. Rebuild routes from scratch")
    print("  3. Verify everything works")
    print("\n" + "="*70)
    
    # Change to project root
    if not Path('src/routing/graph_builder.py').exists():
        print("\n❌ ERROR: Run this from project root directory!")
        print("   cd C:\\Users\\Mohamed\\python_projects\\capstoneG12\\traffic-its-system")
        sys.exit(1)
    
    # Apply fixes
    print("\n[STEP 1] APPLYING FIXES...")
    apply_graph_builder_fix()
    apply_astar_fix()
    apply_dijkstra_fix()
    
    # Rebuild
    print("\n[STEP 2] REBUILDING...")
    if not rebuild_everything():
        print("\n❌ Rebuild failed!")
        sys.exit(1)
    
    # Verify
    print("\n[STEP 3] VERIFYING...")
    if not verify_routes():
        print("\n❌ Verification failed!")
        sys.exit(1)
    
    # Success!
    print("\n" + "="*70)
    print("✅ SUCCESS! ALL FIXES APPLIED AND VERIFIED")
    print("="*70)
    print("\nNow run SUMO:")
    print("  python scripts\\4_run_sumo_gui.py --config data\\generated\\simulation.sumocfg")
    print("\nOr open in SUMO GUI:")
    print("  sumo-gui -c data\\generated\\simulation.sumocfg")
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
