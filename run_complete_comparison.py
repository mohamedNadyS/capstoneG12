"""
COMPLETE COMPARISON WORKFLOW
Runs all 3 routing approaches and creates comparison
"""

import subprocess
import sys
from pathlib import Path
import time

def run_command(cmd, description):
    """Run a command and show progress"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    start = time.time()
    result = subprocess.run(cmd)
    duration = time.time() - start
    
    if result.returncode != 0:
        print(f"\n❌ Failed! (took {duration:.1f}s)")
        return False
    
    print(f"\n✅ Success! (took {duration:.1f}s)")
    return True

def main():
    print("="*70)
    print("COMPLETE ROUTING COMPARISON")
    print("="*70)
    print("\nThis will generate 2 scenarios:")
    print("  1. Baseline: SUMO shortest path (distance only)")
    print("  2. Full AI: A*/Dijkstra with GNN predictions")
    print("\nEach will use the SAME traffic conditions")
    print("="*70)
    
    input("\nPress Enter to start...")
    
    # Step 1: Generate high-congestion traffic
    print("\n\n")
    print("█" * 70)
    print("STEP 1: GENERATE HIGH-CONGESTION TRAFFIC")
    print("█" * 70)
    
    if not run_command(
        [sys.executable, 'scripts/1_generate_traffic.py',
         '--vehicles', '2000',
         '--congestion', '0.9',
         '--emergency-ratio', '0.02',
         '--variable-pattern', 'incident',
         '--output', 'data/comparison'],
        "Generating 5000 vehicles with high congestion..."
    ):
        return
    
    # Adjust departure times for visible congestion
    print("\n[ADJUSTING] Concentrating vehicle departures...")
    import json
    
    vehicles_file = Path('data/comparison/vehicles.json')
    with open(vehicles_file, 'r') as f:
        data = json.load(f)
    
    vehicles = data['vehicles']
    peak_vehicles = int(len(vehicles) * 0.8)
    peak_duration = 1800  # 30 minutes
    
    for i, vehicle in enumerate(vehicles):
        if i < peak_vehicles:
            vehicle['depart_time'] = int((i / peak_vehicles) * peak_duration)
        else:
            vehicle['depart_time'] = peak_duration + int(((i - peak_vehicles) / (len(vehicles) - peak_vehicles)) * 1800)
    
    with open(vehicles_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Concentrated {peak_vehicles} vehicles in first 30 minutes")
    
    # Step 2: Run GNN predictions
    print("\n\n")
    print("█" * 70)
    print("STEP 2: RUN GNN PREDICTIONS")
    print("█" * 70)
    
    if not run_command(
        [sys.executable, 'scripts/2_run_prediction.py',
         '--scenario', 'data/comparison'],
        "Running GNN speed predictions..."
    ):
        return
    
    # Step 3A: Generate baseline routes
    print("\n\n")
    print("█" * 70)
    print("STEP 3A: BASELINE ROUTING (Shortest Path)")
    print("█" * 70)
    
    if not run_command(
        [sys.executable, 'generate_baseline_routes.py',
         '--vehicles', 'data/comparison/vehicles.json',
         '--output', 'data/comparison_baseline'],
        "Generating baseline routes (distance only)..."
    ):
        return
    
    # Step 3B: Generate full AI routes
    print("\n\n")
    print("█" * 70)
    print("STEP 3B: FULL AI ROUTING (A*/Dijkstra)")
    print("█" * 70)
    
    if not run_command(
        [sys.executable, 'scripts/3_generate_routes.py',
         '--scenario', 'data/comparison'],
        "Generating full AI routes (A*/Dijkstra with predictions)..."
    ):
        return
    
    # Summary
    print("\n\n")
    print("=" * 70)
    print("✅ ALL SCENARIOS GENERATED SUCCESSFULLY!")
    print("=" * 70)
    print("\nYou now have 2 scenarios to compare:")
    print("\n1️⃣  BASELINE (Shortest Path - No AI):")
    print("   sumo-gui -c data/comparison_baseline/simulation.sumocfg")
    print("\n2️⃣  FULL AI (A*/Dijkstra with GNN predictions):")
    print("   sumo-gui -c data/comparison/simulation.sumocfg")
    print("\n" + "=" * 70)
    print("\n📊 To analyze results:")
    print("   python compare_vehicle_metrics.py")
    print("\n💡 Tips:")
    print("   - Baseline should be WORSE (more congestion)")
    print("   - Full AI should be BETTER (less congestion)")
    print("   - If AI is worse, model needs retraining!")
    print("=" * 70)

if __name__ == "__main__":
    main()
