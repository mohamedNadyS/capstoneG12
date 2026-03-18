"""
High Congestion Scenario Generator
Creates traffic scenarios with visible congestion
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def generate_congested_scenario(
    num_vehicles=5000,
    congestion_level=0.9,
    pattern='congestion_hotspot',
    peak_duration=1800  # 30 minutes
):
    """
    Generate high-congestion scenario
    
    Args:
        num_vehicles: Total number of vehicles
        congestion_level: 0.0-1.0
        pattern: 'rush_hour', 'congestion_hotspot', 'mixed'
        peak_duration: Time window for peak traffic (seconds)
    """
    
    print("="*70)
    print("HIGH CONGESTION SCENARIO GENERATOR")
    print("="*70)
    print(f"\nParameters:")
    print(f"  Vehicles: {num_vehicles}")
    print(f"  Congestion: {congestion_level}")
    print(f"  Pattern: {pattern}")
    print(f"  Peak duration: {peak_duration}s ({peak_duration/60:.0f} minutes)")
    
    # Generate traffic with concentrated departure times
    from src.traffic_generation.traffic_generator import TrafficGenerator
    
    generator = TrafficGenerator(
        network_file='data/sumo/map.net.xml',
        output_dir='data/congested'
    )
    
    print(f"\n[1/3] Generating {num_vehicles} vehicles...")
    
    # Generate with specified pattern
    traffic_data = generator.generate_traffic(
        num_vehicles=num_vehicles,
        congestion_level=congestion_level,
        variable_pattern=pattern,
        emergency_ratio=0.05
    )
    
    print(f"   ✅ Generated {len(traffic_data['vehicles'])} vehicles")
    
    # Adjust departure times for peak congestion
    print(f"\n[2/3] Concentrating departures for visible congestion...")
    
    vehicles = traffic_data['vehicles']
    
    # Concentrate 80% of vehicles in first peak_duration seconds
    peak_vehicles = int(len(vehicles) * 0.8)
    
    for i, vehicle in enumerate(vehicles):
        if i < peak_vehicles:
            # Peak period: concentrated departures
            vehicle['depart_time'] = int((i / peak_vehicles) * peak_duration)
        else:
            # Off-peak: spread remaining vehicles
            vehicle['depart_time'] = peak_duration + int(((i - peak_vehicles) / (len(vehicles) - peak_vehicles)) * 1800)
    
    print(f"   ✅ Peak: {peak_vehicles} vehicles in first {peak_duration/60:.0f} minutes")
    print(f"   ✅ Off-peak: {len(vehicles) - peak_vehicles} vehicles in next 30 minutes")
    
    # Save updated scenario
    import json
    from pathlib import Path
    
    output_dir = Path('data/congested')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'vehicles.json', 'w') as f:
        json.dump(traffic_data, f, indent=2)
    
    print(f"\n[3/3] Scenario saved to: {output_dir}")
    print(f"\n✅ High congestion scenario ready!")
    print(f"\nNext steps:")
    print(f"  1. Run prediction: python scripts/2_run_prediction.py --scenario data/congested")
    print(f"  2. Generate routes: python scripts/3_generate_routes.py --scenario data/congested")
    print(f"  3. Simulate: sumo-gui -c data/congested/simulation.sumocfg")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate high congestion scenario')
    parser.add_argument('--vehicles', type=int, default=5000, help='Number of vehicles')
    parser.add_argument('--congestion', type=float, default=0.9, help='Congestion level (0-1)')
    parser.add_argument('--pattern', default='congestion_hotspot', 
                       choices=['uniform', 'rush_hour', 'congestion_hotspot', 'mixed'],
                       help='Traffic pattern')
    parser.add_argument('--peak-duration', type=int, default=1800, 
                       help='Peak period duration in seconds')
    
    args = parser.parse_args()
    
    generate_congested_scenario(
        num_vehicles=args.vehicles,
        congestion_level=args.congestion,
        pattern=args.pattern,
        peak_duration=args.peak_duration
    )
