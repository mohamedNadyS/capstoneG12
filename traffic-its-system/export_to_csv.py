"""
Export Vehicle Comparisons to CSV
Travel Time + Pollution Only
"""

import json
import csv
from pathlib import Path

def export_to_csv(comparison_dir, output_dir):
    
    print("="*70)
    print("EXPORTING TO CSV FOR EXCEL ANALYSIS")
    print("="*70)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[1/3] Loading vehicle comparison data...")
    with open(Path(comparison_dir) / 'vehicle_comparisons.json', 'r') as f:
        vehicles = json.load(f)
    
    print(f"   Loaded {len(vehicles)} vehicle records")
    
    print(f"\n[2/3] Exporting detailed vehicle data...")
    
    with open(output_path / 'vehicle_comparison_detailed.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        writer.writerow([
            'Vehicle ID',
            'Type',
            'Baseline Travel Time (s)',
            'AI Travel Time (s)',
            'Travel Time Improvement (%)',
            'Baseline Pollution (g CO2)',
            'AI Pollution (g CO2)',
            'Pollution Reduction (%)'
        ])
        
        for v in vehicles:
            writer.writerow([
                v['id'],
                v['type'],
                f"{v['baseline_travel_time']:.2f}",
                f"{v['ai_travel_time']:.2f}",
                f"{v['ai_travel_improvement']:.2f}",
                f"{v.get('baseline_pollution', 0):.2f}",
                f"{v.get('ai_pollution', 0):.2f}",
                f"{v.get('ai_pollution_improvement', 0):.2f}"
            ])
    
    print(f"   ✅ Saved: vehicle_comparison_detailed.csv")
    
    print(f"\n[3/3] Exporting summary statistics...")
    
    with open(Path(comparison_dir) / 'comparison_summary.json', 'r') as f:
        summary = json.load(f)
    
    with open(output_path / 'results_summary.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        writer.writerow(['Vehicle Type', 'Baseline Travel Time (s)', 'AI Travel Time (s)', 'Travel Time Improvement (%)'])
        
        if 'by_type' in summary:
            if 'emergency' in summary['by_type']:
                e = summary['by_type']['emergency']
                writer.writerow(['Emergency', 
                               f"{e.get('baseline_avg_travel', 0):.2f}",
                               f"{e.get('ai_avg_travel', 0):.2f}",
                               f"{e.get('ai_travel_improvement', 0):.2f}"])
            
            if 'normal' in summary['by_type']:
                n = summary['by_type']['normal']
                writer.writerow(['Normal',
                               f"{n.get('baseline_avg_travel', 0):.2f}",
                               f"{n.get('ai_avg_travel', 0):.2f}",
                               f"{n.get('ai_travel_improvement', 0):.2f}"])
        
        writer.writerow([])
        writer.writerow(['Metric', 'Baseline', 'AI', 'Improvement (%)'])
        
        if 'pollution' in summary:
            p = summary['pollution']
            writer.writerow(['Overall Pollution (g CO2)',
                           f"{p.get('baseline_avg', 0):.2f}",
                           f"{p.get('ai_avg', 0):.2f}",
                           f"{p.get('improvement', 0):.2f}"])
    
    print(f"   ✅ Saved: results_summary.csv")
    
    print(f"\n{'='*70}")
    print(f"✅ All CSV files saved to: {output_path}")
    print(f"{'='*70}")
    print(f"\nYou can now open these files in Excel:")
    print(f"  - vehicle_comparison_detailed.csv")
    print(f"  - results_summary.csv")
    print(f"{'='*70}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Export comparison to CSV')
    parser.add_argument('--comparison-dir', required=True, help='Directory with comparison JSON files')
    parser.add_argument('--output', default='data/comparison_results/csv', help='Output directory')
    
    args = parser.parse_args()
    
    export_to_csv(args.comparison_dir, args.output)