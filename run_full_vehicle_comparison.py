"""
COMPLETE AUTOMATED VEHICLE COMPARISON WORKFLOW

This script:
1. Generates all 3 routing scenarios (if needed)
2. Runs SUMO simulations with tripinfo collection
3. Extracts per-vehicle metrics
4. Compares all approaches
5. Generates visualizations
6. Exports to CSV

ONE SCRIPT TO RULE THEM ALL!
"""

import subprocess
import sys
import time
from pathlib import Path
import shutil
SUMO_EXEC = "/home/mohamednady/.local/bin/sumo"
SUMO_GUI_EXEC = "/home/mohamednady/.local/bin/sumo-gui"

def run_command(cmd, description, capture=False):
    """Run a command with progress display"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}")
    
    start = time.time()
    
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd)
    
    duration = time.time() - start
    
    if result.returncode != 0:
        print(f"\n❌ Failed! (took {duration:.1f}s)")
        if capture:
            print(f"Error: {result.stderr}")
        return False, None
    
    print(f"\n✅ Success! (took {duration:.1f}s)")
    return True, result

def run_sumo_with_metrics(config_file, tripinfo_file):
    """Run SUMO simulation and collect tripinfo"""
    print(f"\n{'─'*70}")
    print(f"Running SUMO: {config_file}")
    print(f"Output: {tripinfo_file}")
    print(f"{'─'*70}")
    
    # Create SUMO command with tripinfo output
    cmd = [
        SUMO_EXEC,
        "-c", config_file,
        "--tripinfo-output", tripinfo_file,
        "--no-step-log",
        "--no-warnings"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)


    
    if result.returncode != 0:
        print(f"❌ SUMO failed!")
        print(result.stderr)
        return False
    
    print(f"✅ SUMO completed")
    return True

def main():
    print("="*70)
    print("🚗 COMPLETE VEHICLE-LEVEL COMPARISON")
    print("="*70)
    print("\nThis will:")
    print("  1. Generate/verify all 3 routing scenarios")
    print("  2. Run SUMO simulations with detailed metrics")
    print("  3. Extract per-vehicle performance data")
    print("  4. Compare all approaches vehicle-by-vehicle")
    print("  5. Generate visualizations and CSV exports")
    print("\n" + "="*70)
    
    input("\nPress Enter to start...")
    
    # Step 0: Check if scenarios exist
    print("\n\n")
    print("█" * 70)
    print("STEP 0: CHECKING SCENARIOS")
    print("█" * 70)
    
    scenarios_exist = (
        Path('data/comparison/routes.rou.xml').exists() and
        Path('data/comparison_baseline/routes.rou.xml').exists() and
        Path('data/comparison_prediction/routes.rou.xml').exists()
    )
    
    if not scenarios_exist:
        print("\n⚠️  Scenarios not found. Generating now...")
        print("\nThis will take ~5-10 minutes...")
        
        success, _ = run_command(
            [sys.executable, 'run_complete_comparison.py'],
            "Generating all 3 routing scenarios..."
        )
        
        if not success:
            print("\n❌ Failed to generate scenarios!")
            print("Please run: python run_complete_comparison.py")
            return
    else:
        print("\n✅ All scenarios already exist")
    
    # Step 1: Run SUMO simulations with metrics
    print("\n\n")
    print("█" * 70)
    print("STEP 1: RUNNING SUMO SIMULATIONS")
    print("█" * 70)
    
    simulations = [
        ('data/comparison_baseline/simulation.sumocfg', 
         'data/comparison_baseline/tripinfo.xml',
         'Baseline (Shortest Path)'),
        ('data/comparison_prediction/simulation.sumocfg',
         'data/comparison_prediction/tripinfo.xml',
         'Prediction-Simple (Greedy)'),
        ('data/comparison/simulation.sumocfg',
         'data/comparison/tripinfo.xml',
         'Full AI (A*/Dijkstra)')
    ]
    
    for config, tripinfo, name in simulations:
        print(f"\n{'▓'*70}")
        print(f"Running: {name}")
        print(f"{'▓'*70}")
        
        if not run_sumo_with_metrics(config, tripinfo):
            print(f"\n❌ Failed to run {name}")
            return
    
    # Step 2: Extract vehicle metrics
    print("\n\n")
    print("█" * 70)
    print("STEP 2: EXTRACTING VEHICLE METRICS")
    print("█" * 70)
    
    metrics_files = []
    
    for tripinfo, output, name in [
        ('data/comparison_baseline/tripinfo.xml', 
         'data/comparison_baseline/vehicle_metrics.json',
         'Baseline'),
        ('data/comparison_prediction/tripinfo.xml',
         'data/comparison_prediction/vehicle_metrics.json',
         'Prediction-Simple'),
        ('data/comparison/tripinfo.xml',
         'data/comparison/vehicle_metrics.json',
         'Full AI')
    ]:
        print(f"\n{'▓'*70}")
        print(f"Extracting: {name}")
        print(f"{'▓'*70}")
        
        success, _ = run_command(
            [sys.executable, 'collect_vehicle_metrics.py',
             '--tripinfo', tripinfo,
             '--output', output],
            f"Extracting metrics from {name}..."
        )
        
        if not success:
            print(f"\n❌ Failed to extract metrics for {name}")
            return
        
        metrics_files.append(output)
    
    # Step 3: Compare approaches
    print("\n\n")
    print("█" * 70)
    print("STEP 3: COMPARING APPROACHES")
    print("█" * 70)
    
    success, _ = run_command(
        [sys.executable, 'compare_vehicle_metrics.py',
         '--baseline', 'data/comparison_baseline/vehicle_metrics.json',
         '--prediction', 'data/comparison_prediction/vehicle_metrics.json',
         '--ai', 'data/comparison/vehicle_metrics.json',
         '--output', 'data/comparison_results'],
        "Comparing all approaches vehicle-by-vehicle..."
    )
    
    if not success:
        print("\n❌ Failed to compare approaches")
        return
    
    # Step 4: Generate visualizations
    print("\n\n")
    print("█" * 70)
    print("STEP 4: GENERATING VISUALIZATIONS")
    print("█" * 70)
    
    success, _ = run_command(
        [sys.executable, 'visualize_comparison.py',
         '--comparison', 'data/comparison_results/comparison_summary.json',
         '--output', 'data/comparison_results/charts'],
        "Creating comparison charts..."
    )
    
    if not success:
        print("\n⚠️  Failed to generate charts (matplotlib may not be installed)")
        print("   Install with: pip install matplotlib")
        print("   Continuing without charts...")
    
    # Step 5: Export to CSV
    print("\n\n")
    print("█" * 70)
    print("STEP 5: EXPORTING TO CSV")
    print("█" * 70)
    
    success, _ = run_command(
        [sys.executable, 'export_to_csv.py',
         '--comparison-dir', 'data/comparison_results',
         '--output', 'data/comparison_results/csv'],
        "Exporting data to CSV for Excel..."
    )
    
    if not success:
        print("\n❌ Failed to export CSV")
        return
    
    # Final Summary
    print("\n\n")
    print("="*70)
    print("✅ COMPLETE! ALL COMPARISONS DONE!")
    print("="*70)
    
    # Show summary results
    import json
    with open('data/comparison_results/comparison_summary.json', 'r') as f:
        summary = json.load(f)
    
    print("\n📊 QUICK SUMMARY:")
    print(f"   Vehicles compared: {summary['common_vehicles']}")
    print(f"\n   Full AI Improvements vs Baseline:")
    print(f"      Travel Time:  {summary['improvements']['ai_vs_baseline']['travel_time']:.1f}% better ⭐")
    print(f"      Waiting Time: {summary['improvements']['ai_vs_baseline']['waiting_time']:.1f}% better ⭐")
    
    print(f"\n📁 RESULTS LOCATION: data/comparison_results/")
    print(f"\n📊 View Charts:")
    print(f"   - data/comparison_results/charts/comparison_dashboard.png")
    print(f"   - data/comparison_results/charts/travel_time_comparison.png")
    print(f"   - data/comparison_results/charts/waiting_time_comparison.png")
    print(f"\n📈 Excel Analysis:")
    print(f"   - data/comparison_results/csv/vehicle_comparison_detailed.csv")
    print(f"   - data/comparison_results/csv/summary_statistics.csv")
    print(f"   - data/comparison_results/csv/by_vehicle_type.csv")
    print(f"\n📋 JSON Data:")
    print(f"   - data/comparison_results/vehicle_comparisons.json (all vehicles)")
    print(f"   - data/comparison_results/comparison_summary.json (statistics)")
    
    print("\n" + "="*70)
    print("🎓 FOR YOUR CAPSTONE REPORT:")
    print("="*70)
    print("\n1. Use the charts from: data/comparison_results/charts/")
    print("2. Reference the CSV data for detailed analysis")
    print("3. Highlight the improvement percentages")
    print("4. Show vehicle-by-vehicle evidence (CSV file)")
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
