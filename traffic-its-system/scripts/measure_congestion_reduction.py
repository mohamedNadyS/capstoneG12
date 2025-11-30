#!/usr/bin/env python3
"""
Congestion Reduction Effectiveness Measurement
Measures how well the system reduces traffic congestion
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt


def analyze_congestion(scenario_dir: str) -> Dict:
    """
    Analyze congestion levels in simulation
    
    Args:
        scenario_dir: Path to scenario directory
        
    Returns:
        Congestion metrics
    """
    scenario_path = Path(scenario_dir)
    
    # Load simulation metrics
    metrics_file = scenario_path / 'simulation_metrics.json'
    with open(metrics_file) as f:
        sim_data = json.load(f)['simulation_metrics']
    
    # Load routing metadata for edge congestion
    routing_file = scenario_path / 'routing_metadata.json'
    with open(routing_file) as f:
        routing_data = json.load(f)
    
    metrics = {
        'avg_waiting_time': sim_data['avg_waiting_time'],
        'avg_time_loss': sim_data['avg_time_loss'],
        'avg_travel_time': sim_data['avg_travel_time'],
        'throughput': sim_data['throughput'],
        'completed_vehicles': sim_data['completed_vehicles'],
        'total_vehicles': sim_data['total_vehicles']
    }
    
    # Calculate congestion indicators
    # High waiting time = high congestion
    metrics['congestion_score'] = (
        metrics['avg_waiting_time'] / metrics['avg_travel_time'] * 100
        if metrics['avg_travel_time'] > 0 else 0
    )
    
    # Time loss percentage
    metrics['time_loss_percentage'] = (
        metrics['avg_time_loss'] / metrics['avg_travel_time'] * 100
        if metrics['avg_travel_time'] > 0 else 0
    )
    
    return metrics


def measure_congestion_reduction(
    ai_scenario: str,
    baseline_scenario: str
) -> Dict:
    """
    Compare congestion between AI and baseline
    
    Args:
        ai_scenario: AI routing scenario
        baseline_scenario: Baseline routing scenario
        
    Returns:
        Congestion reduction metrics
    """
    print("\n" + "="*70)
    print("CONGESTION REDUCTION EFFECTIVENESS MEASUREMENT")
    print("="*70)
    
    # Analyze both scenarios
    ai_metrics = analyze_congestion(ai_scenario)
    baseline_metrics = analyze_congestion(baseline_scenario)
    
    # Calculate reductions
    results = {}
    
    # Waiting time reduction
    waiting_reduction = (
        (baseline_metrics['avg_waiting_time'] - ai_metrics['avg_waiting_time']) /
        baseline_metrics['avg_waiting_time'] * 100
    )
    results['waiting_time_reduction'] = waiting_reduction
    
    # Time loss reduction
    loss_reduction = (
        (baseline_metrics['avg_time_loss'] - ai_metrics['avg_time_loss']) /
        baseline_metrics['avg_time_loss'] * 100
    )
    results['time_loss_reduction'] = loss_reduction
    
    # Congestion score reduction
    congestion_reduction = (
        (baseline_metrics['congestion_score'] - ai_metrics['congestion_score']) /
        baseline_metrics['congestion_score'] * 100
    )
    results['congestion_score_reduction'] = congestion_reduction
    
    # Throughput improvement
    throughput_improvement = (
        (ai_metrics['throughput'] - baseline_metrics['throughput']) /
        baseline_metrics['throughput'] * 100
    )
    results['throughput_improvement'] = throughput_improvement
    
    # Overall effectiveness (average of reductions)
    results['congestion_reduction_effectiveness'] = np.mean([
        waiting_reduction,
        loss_reduction,
        congestion_reduction
    ])
    
    # Store raw values
    results['ai_metrics'] = ai_metrics
    results['baseline_metrics'] = baseline_metrics
    
    # Targets
    results['targets'] = {
        'waiting_time_reduction': 30.0,  # 30% reduction
        'time_loss_reduction': 25.0,  # 25% reduction
        'congestion_score_reduction': 20.0,  # 20% reduction
        'throughput_improvement': 15.0,  # 15% improvement
        'overall_effectiveness': 25.0  # 25% overall
    }
    
    # Check requirements
    results['requirements_met'] = {
        'waiting_time': waiting_reduction >= 30.0,
        'time_loss': loss_reduction >= 25.0,
        'congestion_score': congestion_reduction >= 20.0,
        'throughput': throughput_improvement >= 15.0,
        'overall': results['congestion_reduction_effectiveness'] >= 25.0
    }
    
    return results


def print_congestion_report(results: Dict):
    """Print formatted congestion report"""
    print("\n" + "="*70)
    print("CONGESTION REDUCTION EFFECTIVENESS REPORT")
    print("="*70)
    
    print("\n📊 Baseline Congestion Levels:")
    baseline = results['baseline_metrics']
    print(f"   Avg waiting time:    {baseline['avg_waiting_time']:.2f}s")
    print(f"   Avg time loss:       {baseline['avg_time_loss']:.2f}s")
    print(f"   Congestion score:    {baseline['congestion_score']:.2f}%")
    print(f"   Throughput:          {baseline['throughput']:.2f} veh/hr")
    
    print("\n🤖 AI System Congestion Levels:")
    ai = results['ai_metrics']
    print(f"   Avg waiting time:    {ai['avg_waiting_time']:.2f}s")
    print(f"   Avg time loss:       {ai['avg_time_loss']:.2f}s")
    print(f"   Congestion score:    {ai['congestion_score']:.2f}%")
    print(f"   Throughput:          {ai['throughput']:.2f} veh/hr")
    
    print("\n✨ Congestion Reductions:")
    print(f"   Waiting time:   {results['waiting_time_reduction']:+.2f}%")
    print(f"   Time loss:      {results['time_loss_reduction']:+.2f}%")
    print(f"   Congestion:     {results['congestion_score_reduction']:+.2f}%")
    print(f"   Throughput:     {results['throughput_improvement']:+.2f}%")
    
    print(f"\n🎯 Overall Effectiveness: {results['congestion_reduction_effectiveness']:.2f}%")
    print(f"   (Measures congestion reduction achieved by AI system)")
    
    print("\n✅ Requirements Check:")
    targets = results['targets']
    met = results['requirements_met']
    
    checks = [
        ("Waiting time reduction > 30%",
         results['waiting_time_reduction'],
         targets['waiting_time_reduction'],
         met['waiting_time']),
        ("Time loss reduction > 25%",
         results['time_loss_reduction'],
         targets['time_loss_reduction'],
         met['time_loss']),
        ("Congestion score reduction > 20%",
         results['congestion_score_reduction'],
         targets['congestion_score_reduction'],
         met['congestion_score']),
        ("Throughput improvement > 15%",
         results['throughput_improvement'],
         targets['throughput_improvement'],
         met['throughput']),
        ("Overall effectiveness > 25%",
         results['congestion_reduction_effectiveness'],
         targets['overall_effectiveness'],
         met['overall'])
    ]
    
    for requirement, actual, target, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"   {status:8} - {requirement:40} "
              f"(actual: {actual:+.2f}%, target: {target:.2f}%)")
    
    all_passed = all(met.values())
    print("\n" + "="*70)
    if all_passed:
        print("✅ CONGESTION REDUCTION REQUIREMENTS MET")
        print("   System successfully reduces traffic congestion!")
    else:
        print("⚠️  SOME REQUIREMENTS NOT MET")
    print("="*70)


def visualize_congestion_reduction(results: Dict, output_file: str):
    """Create visualization"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Before/After comparison
    ax1 = axes[0, 0]
    categories = ['Waiting\nTime', 'Time\nLoss', 'Congestion\nScore']
    baseline_vals = [
        results['baseline_metrics']['avg_waiting_time'],
        results['baseline_metrics']['avg_time_loss'],
        results['baseline_metrics']['congestion_score']
    ]
    ai_vals = [
        results['ai_metrics']['avg_waiting_time'],
        results['ai_metrics']['avg_time_loss'],
        results['ai_metrics']['congestion_score']
    ]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, baseline_vals, width, 
                    label='Baseline (High Congestion)', color='#e74c3c')
    bars2 = ax1.bar(x + width/2, ai_vals, width,
                    label='AI System (Reduced Congestion)', color='#2ecc71')
    
    ax1.set_ylabel('Value')
    ax1.set_title('Congestion Levels: Baseline vs AI System')
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. Reduction percentages
    ax2 = axes[0, 1]
    reductions = {
        'Waiting\nTime': results['waiting_time_reduction'],
        'Time\nLoss': results['time_loss_reduction'],
        'Congestion\nScore': results['congestion_score_reduction'],
        'Throughput': results['throughput_improvement']
    }
    
    colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in reductions.values()]
    bars = ax2.barh(list(reductions.keys()), list(reductions.values()), color=colors)
    ax2.set_xlabel('Reduction/Improvement (%)')
    ax2.set_title('Congestion Reduction Achieved')
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='x')
    
    # Add value labels
    for bar, val in zip(bars, reductions.values()):
        ax2.text(val, bar.get_y() + bar.get_height()/2,
                f' {val:+.1f}%',
                va='center')
    
    # 3. Throughput comparison
    ax3 = axes[1, 0]
    throughput_data = [
        results['baseline_metrics']['throughput'],
        results['ai_metrics']['throughput']
    ]
    colors = ['#e74c3c', '#2ecc71']
    labels = ['Baseline', 'AI System']
    
    bars = ax3.bar(labels, throughput_data, color=colors)
    ax3.set_ylabel('Vehicles per Hour')
    ax3.set_title('Network Throughput')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add value labels and percentage
    for bar, val in zip(bars, throughput_data):
        ax3.text(bar.get_x() + bar.get_width()/2, val,
                f'{val:.0f}',
                ha='center', va='bottom')
    
    improvement = results['throughput_improvement']
    ax3.text(0.5, max(throughput_data) * 0.9,
            f'+{improvement:.1f}% improvement',
            ha='center', transform=ax3.transData,
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    # 4. Overall effectiveness gauge
    ax4 = axes[1, 1]
    effectiveness = results['congestion_reduction_effectiveness']
    target = results['targets']['overall_effectiveness']
    
    # Requirements check bars
    requirements = ['Waiting', 'Time Loss', 'Congestion', 'Throughput', 'Overall']
    actual_vals = [
        results['waiting_time_reduction'],
        results['time_loss_reduction'],
        results['congestion_score_reduction'],
        results['throughput_improvement'],
        effectiveness
    ]
    
    colors = ['#2ecc71' if v >= t else '#e74c3c' 
              for v, t in zip(actual_vals[:-1], 
                            [30, 25, 20, 15]) + [(actual_vals[-1] >= target)]]
    
    bars = ax4.barh(requirements, actual_vals, color=colors)
    ax4.set_xlabel('Reduction/Improvement (%)')
    ax4.set_title(f'Requirements Check\n(Overall: {effectiveness:.1f}%)')
    ax4.axvline(x=25, color='gray', linestyle='--', label='Target', alpha=0.7)
    ax4.grid(True, alpha=0.3, axis='x')
    ax4.legend()
    
    # Add value labels
    for bar, val in zip(bars, actual_vals):
        ax4.text(val, bar.get_y() + bar.get_height()/2,
                f' {val:.1f}%',
                va='center')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[PLOT] Saved congestion visualization: {output_file}")


def main():
    """Main function"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python measure_congestion_reduction.py <ai_scenario> <baseline_scenario>")
        print("\nExample:")
        print("  python measure_congestion_reduction.py data/ai_routing data/baseline_routing")
        sys.exit(1)
    
    ai_scenario = sys.argv[1]
    baseline_scenario = sys.argv[2]
    
    # Measure congestion reduction
    print(f"[1/3] Analyzing congestion levels...")
    results = measure_congestion_reduction(ai_scenario, baseline_scenario)
    
    # Print report
    print(f"[2/3] Generating report...")
    print_congestion_report(results)
    
    # Visualize
    print(f"[3/3] Creating visualization...")
    output_file = Path(ai_scenario) / 'congestion_reduction.png'
    visualize_congestion_reduction(results, str(output_file))
    
    # Save metrics
    metrics_file = Path(ai_scenario) / 'congestion_metrics.json'
    with open(metrics_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n[SAVE] Metrics saved to: {metrics_file}")
    
    print("\n✅ Congestion reduction measurement complete!")


if __name__ == "__main__":
    main()
