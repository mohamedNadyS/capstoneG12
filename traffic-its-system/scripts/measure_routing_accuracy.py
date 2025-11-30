#!/usr/bin/env python3
"""
Routing Decision Accuracy Measurement
Compares AI routing against baseline routing
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict
import matplotlib.pyplot as plt


def measure_routing_accuracy(ai_scenario: str, baseline_scenario: str) -> Dict:
    """
    Compare AI routing against baseline
    
    Args:
        ai_scenario: Directory with AI routing results
        baseline_scenario: Directory with baseline routing results
        
    Returns:
        Accuracy metrics
    """
    print("\n" + "="*70)
    print("ROUTING DECISION ACCURACY MEASUREMENT")
    print("="*70)
    
    # Load AI results
    ai_path = Path(ai_scenario) / 'simulation_metrics.json'
    with open(ai_path) as f:
        ai_data = json.load(f)['simulation_metrics']
    
    # Load baseline results
    baseline_path = Path(baseline_scenario) / 'simulation_metrics.json'
    with open(baseline_path) as f:
        baseline_data = json.load(f)['simulation_metrics']
    
    # Calculate improvements
    metrics = {}
    
    # Travel time improvement
    travel_improvement = (
        (baseline_data['avg_travel_time'] - ai_data['avg_travel_time']) /
        baseline_data['avg_travel_time'] * 100
    )
    metrics['travel_time_improvement'] = travel_improvement
    
    # Waiting time improvement
    waiting_improvement = (
        (baseline_data['avg_waiting_time'] - ai_data['avg_waiting_time']) /
        baseline_data['avg_waiting_time'] * 100
    )
    metrics['waiting_time_improvement'] = waiting_improvement
    
    # Time loss improvement
    loss_improvement = (
        (baseline_data['avg_time_loss'] - ai_data['avg_time_loss']) /
        baseline_data['avg_time_loss'] * 100
    )
    metrics['time_loss_improvement'] = loss_improvement
    
    # Overall routing accuracy (average improvement)
    metrics['routing_accuracy'] = np.mean([
        travel_improvement,
        waiting_improvement,
        loss_improvement
    ])
    
    # Store raw values for reference
    metrics['ai_results'] = {
        'avg_travel_time': ai_data['avg_travel_time'],
        'avg_waiting_time': ai_data['avg_waiting_time'],
        'avg_time_loss': ai_data['avg_time_loss'],
        'throughput': ai_data['throughput']
    }
    
    metrics['baseline_results'] = {
        'avg_travel_time': baseline_data['avg_travel_time'],
        'avg_waiting_time': baseline_data['avg_waiting_time'],
        'avg_time_loss': baseline_data['avg_time_loss'],
        'throughput': baseline_data['throughput']
    }
    
    # Targets
    metrics['targets'] = {
        'travel_time_improvement': 20.0,  # 20% better than baseline
        'waiting_time_improvement': 30.0,  # 30% better
        'time_loss_improvement': 25.0,  # 25% better
        'routing_accuracy': 25.0  # 25% overall improvement
    }
    
    # Check if targets met
    metrics['requirements_met'] = {
        'travel_time': travel_improvement >= 20.0,
        'waiting_time': waiting_improvement >= 30.0,
        'time_loss': loss_improvement >= 25.0,
        'overall': metrics['routing_accuracy'] >= 25.0
    }
    
    return metrics


def print_routing_accuracy_report(metrics: Dict):
    """Print formatted report"""
    print("\n" + "="*70)
    print("ROUTING DECISION ACCURACY REPORT")
    print("="*70)
    
    print("\n📊 Baseline (Random/Shortest Path) Results:")
    baseline = metrics['baseline_results']
    print(f"   Avg travel time:  {baseline['avg_travel_time']:.2f}s")
    print(f"   Avg waiting time: {baseline['avg_waiting_time']:.2f}s")
    print(f"   Avg time loss:    {baseline['avg_time_loss']:.2f}s")
    print(f"   Throughput:       {baseline['throughput']:.2f} veh/hr")
    
    print("\n🤖 AI Routing Results:")
    ai = metrics['ai_results']
    print(f"   Avg travel time:  {ai['avg_travel_time']:.2f}s")
    print(f"   Avg waiting time: {ai['avg_waiting_time']:.2f}s")
    print(f"   Avg time loss:    {ai['avg_time_loss']:.2f}s")
    print(f"   Throughput:       {ai['throughput']:.2f} veh/hr")
    
    print("\n✨ Improvements (AI vs Baseline):")
    print(f"   Travel time:  {metrics['travel_time_improvement']:+.2f}%")
    print(f"   Waiting time: {metrics['waiting_time_improvement']:+.2f}%")
    print(f"   Time loss:    {metrics['time_loss_improvement']:+.2f}%")
    
    print(f"\n🎯 Overall Routing Accuracy: {metrics['routing_accuracy']:.2f}%")
    print(f"   (Measures how much better AI routing is than baseline)")
    
    print("\n✅ Requirements Check:")
    targets = metrics['targets']
    met = metrics['requirements_met']
    
    checks = [
        ("Travel time improvement > 20%",
         metrics['travel_time_improvement'],
         targets['travel_time_improvement'],
         met['travel_time']),
        ("Waiting time improvement > 30%",
         metrics['waiting_time_improvement'],
         targets['waiting_time_improvement'],
         met['waiting_time']),
        ("Time loss improvement > 25%",
         metrics['time_loss_improvement'],
         targets['time_loss_improvement'],
         met['time_loss']),
        ("Overall routing accuracy > 25%",
         metrics['routing_accuracy'],
         targets['routing_accuracy'],
         met['overall'])
    ]
    
    for requirement, actual, target, passed in checks:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"   {status:8} - {requirement:35} "
              f"(actual: {actual:+.2f}%, target: {target:.2f}%)")
    
    all_passed = all(met.values())
    print("\n" + "="*70)
    if all_passed:
        print("✅ ROUTING DECISION ACCURACY MEETS REQUIREMENTS")
        print("   AI routing significantly outperforms baseline!")
    else:
        print("⚠️  SOME REQUIREMENTS NOT MET")
    print("="*70)


def visualize_routing_accuracy(metrics: Dict, output_file: str):
    """Create visualization"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Baseline vs AI comparison
    ax1 = axes[0, 0]
    categories = ['Travel\nTime', 'Waiting\nTime', 'Time\nLoss']
    baseline_vals = [
        metrics['baseline_results']['avg_travel_time'],
        metrics['baseline_results']['avg_waiting_time'],
        metrics['baseline_results']['avg_time_loss']
    ]
    ai_vals = [
        metrics['ai_results']['avg_travel_time'],
        metrics['ai_results']['avg_waiting_time'],
        metrics['ai_results']['avg_time_loss']
    ]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax1.bar(x - width/2, baseline_vals, width, label='Baseline', color='#e74c3c')
    bars2 = ax1.bar(x + width/2, ai_vals, width, label='AI Routing', color='#2ecc71')
    
    ax1.set_ylabel('Time (seconds)')
    ax1.set_title('Baseline vs AI Routing Performance')
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. Improvement percentages
    ax2 = axes[0, 1]
    improvements = [
        metrics['travel_time_improvement'],
        metrics['waiting_time_improvement'],
        metrics['time_loss_improvement']
    ]
    colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in improvements]
    
    bars = ax2.barh(categories, improvements, color=colors)
    ax2.set_xlabel('Improvement (%)')
    ax2.set_title('AI Routing Improvements')
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='x')
    
    # Add value labels
    for bar, val in zip(bars, improvements):
        ax2.text(val, bar.get_y() + bar.get_height()/2,
                f' {val:+.1f}%',
                va='center')
    
    # 3. Overall accuracy gauge
    ax3 = axes[1, 0]
    accuracy = metrics['routing_accuracy']
    target = metrics['targets']['routing_accuracy']
    
    # Create gauge
    theta = np.linspace(0, np.pi, 100)
    r = np.ones(100)
    
    ax3.plot(theta, r, 'k-', linewidth=2)
    ax3.fill_between(theta[:50], 0, r[:50], alpha=0.3, color='#e74c3c', label='Below Target')
    ax3.fill_between(theta[50:], 0, r[50:], alpha=0.3, color='#2ecc71', label='Above Target')
    
    # Add accuracy needle
    accuracy_norm = min(accuracy / 50, 1.0)  # Normalize to 0-50% range
    needle_angle = np.pi * (1 - accuracy_norm)
    ax3.plot([0, np.cos(needle_angle)], [0, np.sin(needle_angle)], 
             'r-', linewidth=3, label=f'Accuracy: {accuracy:.1f}%')
    
    ax3.set_xlim(-0.1, 1.1)
    ax3.set_ylim(0, 1.1)
    ax3.set_aspect('equal')
    ax3.axis('off')
    ax3.set_title(f'Routing Accuracy: {accuracy:.1f}%\n(Target: {target:.1f}%)')
    ax3.legend(loc='upper right')
    
    # 4. Requirements check
    ax4 = axes[1, 1]
    requirements = ['Travel\nTime', 'Waiting\nTime', 'Time\nLoss', 'Overall']
    actual_vals = [
        metrics['travel_time_improvement'],
        metrics['waiting_time_improvement'],
        metrics['time_loss_improvement'],
        metrics['routing_accuracy']
    ]
    target_vals = [
        metrics['targets']['travel_time_improvement'],
        metrics['targets']['waiting_time_improvement'],
        metrics['targets']['time_loss_improvement'],
        metrics['targets']['routing_accuracy']
    ]
    
    x = np.arange(len(requirements))
    width = 0.35
    
    bars1 = ax4.bar(x - width/2, actual_vals, width, label='Actual', color='#3498db')
    bars2 = ax4.bar(x + width/2, target_vals, width, label='Target', 
                    color='#95a5a6', alpha=0.7)
    
    ax4.set_ylabel('Improvement (%)')
    ax4.set_title('Requirements vs Actual Performance')
    ax4.set_xticks(x)
    ax4.set_xticklabels(requirements)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')
    
    # Color bars based on pass/fail
    for bar, passed in zip(bars1, metrics['requirements_met'].values()):
        if passed:
            bar.set_color('#2ecc71')
        else:
            bar.set_color('#e74c3c')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[PLOT] Saved accuracy visualization: {output_file}")


def main():
    """Main function"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python measure_routing_accuracy.py <ai_scenario> <baseline_scenario>")
        print("\nExample:")
        print("  python measure_routing_accuracy.py data/ai_routing data/baseline_routing")
        sys.exit(1)
    
    ai_scenario = sys.argv[1]
    baseline_scenario = sys.argv[2]
    
    # Measure accuracy
    print(f"[1/3] Comparing AI routing vs baseline...")
    metrics = measure_routing_accuracy(ai_scenario, baseline_scenario)
    
    # Print report
    print(f"[2/3] Generating report...")
    print_routing_accuracy_report(metrics)
    
    # Visualize
    print(f"[3/3] Creating visualization...")
    output_file = Path(ai_scenario) / 'routing_accuracy.png'
    visualize_routing_accuracy(metrics, str(output_file))
    
    # Save metrics
    metrics_file = Path(ai_scenario) / 'routing_accuracy.json'
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\n[SAVE] Metrics saved to: {metrics_file}")
    
    print("\n✅ Routing accuracy measurement complete!")


if __name__ == "__main__":
    main()
