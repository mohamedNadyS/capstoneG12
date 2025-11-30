#!/usr/bin/env python3
"""
System Time Response Measurement
Measures end-to-end and per-component latency
"""

import time
import json
from pathlib import Path
from typing import Dict
import subprocess
import sys


class TimingProfiler:
    """Profile system timing"""
    
    def __init__(self):
        self.timings = {}
        self.start_times = {}
    
    def start(self, component: str):
        """Start timing a component"""
        self.start_times[component] = time.time()
    
    def stop(self, component: str):
        """Stop timing a component"""
        if component in self.start_times:
            elapsed = time.time() - self.start_times[component]
            self.timings[component] = elapsed
            del self.start_times[component]
            return elapsed
        return 0
    
    def get_summary(self) -> Dict:
        """Get timing summary"""
        total = sum(self.timings.values())
        
        return {
            'total_time': total,
            'components': self.timings,
            'breakdown_percentage': {
                k: (v / total * 100) if total > 0 else 0
                for k, v in self.timings.items()
            }
        }


def measure_pipeline_time(
    scenario_dir: str,
    num_vehicles: int = 1500,
    pattern: str = 'mixed'
) -> Dict:
    """
    Measure complete pipeline timing
    
    Args:
        scenario_dir: Output directory
        num_vehicles: Number of vehicles to generate
        pattern: Traffic pattern
        
    Returns:
        Timing measurements
    """
    profiler = TimingProfiler()
    
    print("\n" + "="*70)
    print("SYSTEM TIME RESPONSE MEASUREMENT")
    print("="*70)
    
    # Component 1: Traffic Generation
    print("\n[1/4] Traffic Generation...")
    profiler.start('traffic_generation')
    
    cmd = [
        sys.executable,
        'scripts/1_generate_traffic.py',
        '--congestion', '0.4',
        '--vehicles', str(num_vehicles),
        '--variable-pattern', pattern,
        '--output-dir', scenario_dir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ERROR: {result.stderr}")
        return {}
    
    traffic_time = profiler.stop('traffic_generation')
    print(f"   ✓ Completed in {traffic_time:.2f} seconds")
    
    # Component 2: Speed Prediction
    print("\n[2/4] Speed Prediction...")
    profiler.start('speed_prediction')
    
    cmd = [
        sys.executable,
        'scripts/2_run_prediction.py',
        '--scenario', scenario_dir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ERROR: {result.stderr}")
        return {}
    
    prediction_time = profiler.stop('speed_prediction')
    print(f"   ✓ Completed in {prediction_time:.2f} seconds")
    
    # Component 3: Route Generation
    print("\n[3/4] Route Generation...")
    profiler.start('route_generation')
    
    cmd = [
        sys.executable,
        'scripts/3_generate_routes.py',
        '--scenario', scenario_dir
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   ERROR: {result.stderr}")
        return {}
    
    routing_time = profiler.stop('route_generation')
    print(f"   ✓ Completed in {routing_time:.2f} seconds")
    
    # Component 4: Load routing metadata for detailed metrics
    print("\n[4/4] Analyzing routing performance...")
    metadata_file = Path(scenario_dir) / 'routing_metadata.json'
    
    with open(metadata_file) as f:
        routing_data = json.load(f)
    
    # Calculate per-vehicle metrics
    total_vehicles = routing_data['statistics']['total_vehicles']
    avg_route_time = routing_time / total_vehicles if total_vehicles > 0 else 0
    
    # Get summary
    summary = profiler.get_summary()
    
    # Add detailed metrics
    summary['per_vehicle_metrics'] = {
        'avg_route_calculation_time': avg_route_time * 1000,  # Convert to ms
        'total_vehicles_routed': total_vehicles
    }
    
    summary['targets'] = {
        'total_time_target': 60.0,
        'prediction_time_target': 5.0,
        'routing_time_target': 10.0,
        'per_vehicle_target': 10.0  # ms
    }
    
    # Check requirements
    summary['requirements_met'] = {
        'total_time': summary['total_time'] < 60.0,
        'prediction_time': summary['components']['speed_prediction'] < 5.0,
        'routing_time': summary['components']['route_generation'] < 10.0,
        'per_vehicle_time': avg_route_time * 1000 < 10.0
    }
    
    return summary


def print_timing_report(summary: Dict):
    """Print formatted timing report"""
    print("\n" + "="*70)
    print("TIME RESPONSE REPORT")
    print("="*70)
    
    print("\n⏱️  Component Timing:")
    for component, time_val in summary['components'].items():
        percentage = summary['breakdown_percentage'][component]
        print(f"   {component:25} {time_val:8.2f}s  ({percentage:5.1f}%)")
    
    print(f"\n   {'TOTAL TIME':25} {summary['total_time']:8.2f}s")
    
    print("\n📊 Per-Vehicle Metrics:")
    pv = summary['per_vehicle_metrics']
    print(f"   Avg route calculation:  {pv['avg_route_calculation_time']:.2f} ms")
    print(f"   Total vehicles routed:  {pv['total_vehicles_routed']}")
    
    print("\n🎯 Design Requirements:")
    targets = summary['targets']
    met = summary['requirements_met']
    
    checks = [
        ("Total time < 60s", 
         summary['total_time'], 
         targets['total_time_target'],
         met['total_time']),
        ("Prediction time < 5s", 
         summary['components']['speed_prediction'],
         targets['prediction_time_target'],
         met['prediction_time']),
        ("Routing time < 10s",
         summary['components']['route_generation'],
         targets['routing_time_target'],
         met['routing_time']),
        ("Per-vehicle < 10ms",
         pv['avg_route_calculation_time'],
         targets['per_vehicle_target'],
         met['per_vehicle_time'])
    ]
    
    for requirement, actual, target, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        unit = "ms" if "vehicle" in requirement else "s"
        print(f"   {status:8} - {requirement:25} "
              f"(actual: {actual:.2f}{unit}, target: {target:.2f}{unit})")
    
    # Overall verdict
    all_passed = all(met.values())
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TIME RESPONSE REQUIREMENTS MET")
    else:
        print("⚠️  SOME REQUIREMENTS NOT MET - OPTIMIZATION NEEDED")
    print("="*70)


def visualize_timing(summary: Dict, output_file: str):
    """Create timing visualization"""
    import matplotlib.pyplot as plt
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # 1. Component breakdown
    ax1 = axes[0]
    components = list(summary['components'].keys())
    times = list(summary['components'].values())
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']
    
    ax1.barh(components, times, color=colors[:len(components)])
    ax1.set_xlabel('Time (seconds)')
    ax1.set_title('Component Time Breakdown')
    ax1.grid(True, alpha=0.3, axis='x')
    
    # Add value labels
    for i, v in enumerate(times):
        ax1.text(v, i, f' {v:.2f}s', va='center')
    
    # 2. Requirements vs Actual
    ax2 = axes[1]
    requirements = ['Total\nTime', 'Prediction\nTime', 'Routing\nTime', 'Per-Vehicle\nTime']
    actual_values = [
        summary['total_time'],
        summary['components']['speed_prediction'],
        summary['components']['route_generation'],
        summary['per_vehicle_metrics']['avg_route_calculation_time'] / 1000  # Convert to seconds
    ]
    target_values = [
        summary['targets']['total_time_target'],
        summary['targets']['prediction_time_target'],
        summary['targets']['routing_time_target'],
        summary['targets']['per_vehicle_target'] / 1000
    ]
    
    x = range(len(requirements))
    width = 0.35
    
    bars1 = ax2.bar([i - width/2 for i in x], actual_values, width, 
                     label='Actual', color='#3498db')
    bars2 = ax2.bar([i + width/2 for i in x], target_values, width,
                     label='Target', color='#2ecc71')
    
    ax2.set_ylabel('Time (seconds)')
    ax2.set_title('Requirements vs Actual Performance')
    ax2.set_xticks(x)
    ax2.set_xticklabels(requirements)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Color bars based on pass/fail
    for i, (bar, passed) in enumerate(zip(bars1, summary['requirements_met'].values())):
        if not passed:
            bar.set_color('#e74c3c')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[PLOT] Saved timing visualization: {output_file}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Measure system time response")
    parser.add_argument('--scenario', type=str, default='data/timing_test',
                       help='Scenario directory')
    parser.add_argument('--vehicles', type=int, default=1500,
                       help='Number of vehicles')
    parser.add_argument('--pattern', type=str, default='mixed',
                       help='Traffic pattern')
    args = parser.parse_args()
    
    # Create scenario dir
    Path(args.scenario).mkdir(parents=True, exist_ok=True)
    
    # Measure timing
    summary = measure_pipeline_time(args.scenario, args.vehicles, args.pattern)
    
    if summary:
        # Print report
        print_timing_report(summary)
        
        # Visualize
        output_file = Path(args.scenario) / 'timing_report.png'
        visualize_timing(summary, str(output_file))
        
        # Save results
        results_file = Path(args.scenario) / 'timing_metrics.json'
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n[SAVE] Timing metrics saved to: {results_file}")
        
        print("\n✅ Time response measurement complete!")
    else:
        print("\n❌ Measurement failed!")


if __name__ == "__main__":
    main()
