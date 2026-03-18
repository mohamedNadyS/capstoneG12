import json
import sys
from pathlib import Path
import statistics

def load_metrics(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def _extract_vehicle_statistics(vehicles, vehicle_type=None):
    if vehicle_type:
        filtered = [v for v in vehicles if v.get('type') == vehicle_type]
    else:
        filtered = vehicles
    
    if not filtered:
        return {}
    
    return {
        'count': len(filtered),
        'avg_travel': statistics.mean([v['baseline_travel_time'] for v in filtered]),
        'avg_ai_travel': statistics.mean([v['ai_travel_time'] for v in filtered]),
        'avg_pollution': statistics.mean([v.get('baseline_pollution', 0) for v in filtered]),
        'avg_ai_pollution': statistics.mean([v.get('ai_pollution', 0) for v in filtered]),
    }

def _calculate_improvement_metrics(baseline_val, ai_val):
    if baseline_val <= 0:
        return 0.0
    return ((baseline_val - ai_val) / baseline_val) * 100.0

def compare_approaches(baseline_file, ai_file, output_dir):
    
    print("="*70)
    print("VEHICLE-LEVEL COMPARISON ANALYSIS")
    print("="*70)
    
    print("\n[1/4] Loading metrics...")
    baseline = load_metrics(baseline_file)
    ai = load_metrics(ai_file)
    
    print(f"   Baseline:    {baseline['summary']['total_vehicles']} vehicles")
    print(f"   Full AI:     {ai['summary']['total_vehicles']} vehicles")
    
    baseline_vehicles = {v['id']: v for v in baseline['vehicles']}
    ai_vehicles = {v['id']: v for v in ai['vehicles']}
    
    common_ids = set(baseline_vehicles.keys()) & set(ai_vehicles.keys())
    
    print(f"\n[2/4] Comparing {len(common_ids)} common vehicles...")
    
    vehicle_comparisons = []
    
    for vehicle_id in common_ids:
        b = baseline_vehicles[vehicle_id]
        a = ai_vehicles[vehicle_id]
        
        comparison = {
            'id': vehicle_id,
            'type': b['type'],
            'baseline_travel_time': b['travel_time'],
            'baseline_pollution': b.get('pollution', 0),
            'ai_travel_time': a['travel_time'],
            'ai_pollution': a.get('pollution', 0),
            'baseline_waiting_time': b['waiting_time'],
            'ai_waiting_time': a['waiting_time'],
            'baseline_time_loss': b['time_loss'],
            'ai_time_loss': a['time_loss'],
        }
        
        vehicle_comparisons.append(comparison)

    for v in vehicle_comparisons:
        v['ai_travel_improvement'] = _calculate_improvement_metrics(
            v['baseline_travel_time'], v['ai_travel_time'])
        v['ai_pollution_improvement'] = _calculate_improvement_metrics(
            v['baseline_pollution'], v['ai_pollution'])
    
    print(f"\n[3/4] Calculating aggregate statistics...")
    
    emergency_comps = [v for v in vehicle_comparisons if v['type'] == 'emergency']
    normal_comps = [v for v in vehicle_comparisons if v['type'] == 'normal']
    
    print(f"   Emergency vehicles: {len(emergency_comps)}")
    print(f"   Normal vehicles: {len(normal_comps)}")
    
    def calc_type_stats(vehicle_list):
        if not vehicle_list:
            return {}
        baseline_avg = statistics.mean([v['baseline_travel_time'] for v in vehicle_list])
        ai_avg = statistics.mean([v['ai_travel_time'] for v in vehicle_list])
        improvement = _calculate_improvement_metrics(baseline_avg, ai_avg)
        return {
            'count': len(vehicle_list),
            'baseline_avg_travel': baseline_avg,
            'ai_avg_travel': ai_avg,
            'ai_travel_improvement': improvement,
        }
    
    emergency_stats = calc_type_stats(emergency_comps)
    normal_stats = calc_type_stats(normal_comps)
    
    all_baseline_pollution = statistics.mean([v['baseline_pollution'] for v in vehicle_comparisons])
    all_ai_pollution = statistics.mean([v['ai_pollution'] for v in vehicle_comparisons])
    pollution_improvement = _calculate_improvement_metrics(all_baseline_pollution, all_ai_pollution)
    
    summary_stats = {
        'common_vehicles': len(common_ids),
        'by_type': {
            'emergency': emergency_stats if emergency_stats else {
                'count': 0,
                'ai_travel_improvement': 0,
            },
            'normal': normal_stats if normal_stats else {
                'count': 0,
                'ai_travel_improvement': 0,
            }
        },
        'pollution': {
            'baseline_avg': all_baseline_pollution,
            'ai_avg': all_ai_pollution,
            'improvement': pollution_improvement
        }
    }
    
    print(f"\n[4/4] Saving comparison results...")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    with open(output_path / 'vehicle_comparisons.json', 'w') as f:
        json.dump(vehicle_comparisons, f, indent=2)
    
    with open(output_path / 'comparison_summary.json', 'w') as f:
        json.dump(summary_stats, f, indent=2)
    
    print(f"   ✅ Saved to {output_path}")
    
    print(f"\n{'='*70}")
    print("COMPARISON RESULTS")
    print(f"{'='*70}")
    
    if emergency_comps and emergency_stats:
        print(f"\n🚨 EMERGENCY VEHICLES ({len(emergency_comps)} vehicles):")
        print(f"   Baseline Avg Travel Time:  {emergency_stats['baseline_avg_travel']:.1f}s")
        print(f"   AI Avg Travel Time:        {emergency_stats['ai_avg_travel']:.1f}s")
        print(f"   Travel Time Improvement:   {emergency_stats['ai_travel_improvement']:.1f}% ⭐")
    
    if normal_comps and normal_stats:
        print(f"\n🚗 NORMAL VEHICLES ({len(normal_comps)} vehicles):")
        print(f"   Baseline Avg Travel Time:  {normal_stats['baseline_avg_travel']:.1f}s")
        print(f"   AI Avg Travel Time:        {normal_stats['ai_avg_travel']:.1f}s")
        print(f"   Travel Time Improvement:   {normal_stats['ai_travel_improvement']:.1f}% ⭐")
    
    print(f"\n🌱 POLLUTION (All Vehicles):")
    print(f"   Baseline Avg:  {all_baseline_pollution:.1f}g CO2")
    print(f"   AI Avg:        {all_ai_pollution:.1f}g CO2")
    print(f"   Reduction:     {pollution_improvement:.1f}% ⭐")
    
    print(f"\n{'='*70}")
    
    return summary_stats, vehicle_comparisons

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Compare vehicle metrics across approaches')
    parser.add_argument('--baseline', required=True, help='Baseline metrics JSON')
    parser.add_argument('--ai', required=True, help='AI metrics JSON')
    parser.add_argument('--output', default='data/comparison_results', help='Output directory')
    
    args = parser.parse_args()
    
    compare_approaches(args.baseline, args.ai, args.output)