"""
Traffic Generator
Main component for generating synthetic traffic scenarios
"""

import numpy as np
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import random

from src.sumo_integration.sumo_parser import SUMONetworkParser, SUMOEdge
from src.data_generation.speed_history_generator import SpeedHistoryGenerator
from src.data_generation.variable_traffic import VariableTrafficGenerator


@dataclass
class Vehicle:
    """Represents a vehicle in the simulation"""
    id: str
    origin_edge: str
    destination_edge: str
    depart_time: float  # seconds
    vehicle_type: str  # 'normal' or 'emergency'
    
    def to_dict(self):
        return asdict(self)


@dataclass
class EdgeState:
    """Current state of an edge/road"""
    edge_id: str
    vehicle_count: int
    current_speed: float  # km/h
    capacity: float
    congestion_factor: float  # 0.0 - 1.0
    
    @property
    def is_congested(self) -> bool:
        """Check if edge is congested (>80% capacity)"""
        return self.congestion_factor > 0.8
    
    def to_dict(self):
        return asdict(self)


class TrafficGenerator:
    """
    Generate realistic traffic scenarios for SUMO simulation
    """
    
    def __init__(
        self,
        network_parser: SUMONetworkParser,
        config: Dict = None
    ):
        """
        Initialize traffic generator
        
        Args:
            network_parser: Parsed SUMO network
            config: Configuration dictionary
        """
        self.parser = network_parser
        self.config = config or {}
        
        # Configuration parameters
        self.emergency_ratio = self.config.get('emergency_vehicle_ratio', 0.05)
        self.default_congestion = self.config.get('default_congestion_level', 0.3)
        
        # Speed history generator
        speed_config = self.config.get('speed_generation', {})
        self.speed_generator = SpeedHistoryGenerator(speed_config)
        
        print(f"✓ Traffic Generator initialized")
        print(f"  Network: {len(self.parser.nodes)} nodes, {len(self.parser.edges)} edges")
    
    def generate_traffic_scenario(
        self,
        num_vehicles: int,
        congestion_level: float,
        scenario_type: str = "normal",
        output_dir: str = "./data/generated",
        variable_pattern: str = None  # NEW: 'morning_rush', 'incident', 'gradual', 'variable', 'mixed'
    ) -> Dict:
        """
        Generate complete traffic scenario
        
        Args:
            num_vehicles: Total number of vehicles to generate
            congestion_level: 0.0 (free) to 1.0 (jammed)
            scenario_type: Type of scenario (free_flow, normal, rush_hour, heavy_jam)
            output_dir: Where to save generated files
            
        Returns:
            Dictionary containing complete scenario data
        """
        print("\n" + "="*70)
        print("GENERATING TRAFFIC SCENARIO")
        print("="*70)
        print(f"  Vehicles: {num_vehicles}")
        print(f"  Congestion Level: {congestion_level:.2f}")
        print(f"  Scenario Type: {scenario_type}")
        print("="*70 + "\n")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Generate vehicles with origins and destinations
        print("[1/5] Generating vehicle trips...")
        vehicles = self._generate_vehicles(num_vehicles)
        print(f"   ✓ Created {len(vehicles)} vehicles")
        print(f"      • Normal: {sum(1 for v in vehicles if v.vehicle_type == 'normal')}")
        print(f"      • Emergency: {sum(1 for v in vehicles if v.vehicle_type == 'emergency')}")
        
        # Step 2: Calculate edge states (vehicle counts, speeds)
        print("\n[2/5] Calculating edge states...")
        edge_states = self._calculate_edge_states(vehicles, congestion_level)
        print(f"   ✓ Calculated state for {len(edge_states)} edges")
        congested_count = sum(1 for es in edge_states.values() if es.is_congested)
        print(f"      • Congested edges: {congested_count} ({100*congested_count/len(edge_states):.1f}%)")
        
        # Step 3: Generate speed history for GNN input
        print("\n[3/5] Generating speed history (last 1 hour)...")
        
        if variable_pattern:
            # Use variable traffic pattern generator
            print(f"   Using VARIABLE pattern: {variable_pattern}")
            var_generator = VariableTrafficGenerator(num_timesteps=12)
            speed_dict = var_generator.generate_variable_speeds(
                edges=self.parser.edges,
                pattern_name=variable_pattern,
                noise_std=self.speed_generator.noise_std
            )
            
            # Convert to SpeedTimeSeries format
            from src.data_generation.speed_history_generator import SpeedTimeSeries
            speed_history = {}
            for edge_id, speeds in speed_dict.items():
                timestamps = [i * 5 for i in range(12)]  # 5 minute intervals
                speed_history[edge_id] = SpeedTimeSeries(
                    edge_id=edge_id,
                    speeds=speeds,
                    timestamps=timestamps
                )
        else:
            # Use standard generation (uniform congestion)
            print(f"   Using STANDARD pattern (uniform congestion)")
            speed_history = self.speed_generator.generate_hourly_history(
                edges=self.parser.edges,
                congestion_level=congestion_level,
                num_timesteps=12
            )
            
            # Add realistic patterns
            if scenario_type == "rush_hour":
                self.speed_generator.add_rush_hour_pattern(speed_history)
        
        stats = self.speed_generator.get_statistics(speed_history)
        print(f"      • Mean speed: {stats['mean_speed']:.1f} km/h")
        print(f"      • Speed range: [{stats['min_speed']:.1f}, {stats['max_speed']:.1f}] km/h")
        
        # Step 4: Build complete scenario data structure
        print("\n[4/5] Building scenario data structure...")
        scenario = {
            'metadata': {
                'scenario_type': scenario_type,
                'num_vehicles': num_vehicles,
                'congestion_level': congestion_level,
                'emergency_ratio': self.emergency_ratio,
                'network_stats': self.parser.get_network_stats()
            },
            'vehicles': [v.to_dict() for v in vehicles],
            'edge_states': {eid: es.to_dict() for eid, es in edge_states.items()},
            'speed_history': {
                eid: {
                    'speeds': ts.speeds,
                    'timestamps': ts.timestamps
                }
                for eid, ts in speed_history.items()
            }
        }
        
        # Step 5: Save to files
        print("\n[5/5] Saving scenario data...")
        
        # Save complete scenario
        scenario_file = output_path / "traffic_scenario.json"
        with open(scenario_file, 'w') as f:
            json.dump(scenario, f, indent=2)
        print(f"   ✓ Saved: {scenario_file}")
        
        # Save vehicle list separately (for SUMO route generation)
        vehicles_file = output_path / "vehicles.json"
        with open(vehicles_file, 'w') as f:
            json.dump([v.to_dict() for v in vehicles], f, indent=2)
        print(f"   ✓ Saved: {vehicles_file}")
        
        # Save edge states separately
        edge_states_file = output_path / "edge_states.json"
        with open(edge_states_file, 'w') as f:
            json.dump({eid: es.to_dict() for eid, es in edge_states.items()}, f, indent=2)
        print(f"   ✓ Saved: {edge_states_file}")
        
        # Save speed history for GNN
        speed_history_file = output_path / "speed_history.json"
        with open(speed_history_file, 'w') as f:
            json.dump(scenario['speed_history'], f, indent=2)
        print(f"   ✓ Saved: {speed_history_file}")
        
        # Export speed matrix for GNN
        edge_order = list(self.parser.edges.keys())
        speed_matrix = self.speed_generator.export_for_gnn(speed_history, edge_order)
        speed_matrix_file = output_path / "speed_matrix.npy"
        np.save(speed_matrix_file, speed_matrix)
        print(f"   ✓ Saved: {speed_matrix_file} (shape: {speed_matrix.shape})")
        
        # Save edge order for reference
        edge_order_file = output_path / "edge_order.json"
        with open(edge_order_file, 'w') as f:
            json.dump(edge_order, f, indent=2)
        print(f"   ✓ Saved: {edge_order_file}")
        
        print("\n" + "="*70)
        print("✅ SCENARIO GENERATION COMPLETE")
        print("="*70)
        print(f"  Output directory: {output_path.absolute()}")
        print("="*70 + "\n")
        
        return scenario
    
    def _generate_vehicles(self, num_vehicles: int) -> List[Vehicle]:
        """
        Generate vehicle trips with random origins and destinations
        """
        vehicles = []
        edge_ids = list(self.parser.edges.keys())
        
        if len(edge_ids) < 2:
            raise ValueError("Need at least 2 edges to generate traffic")
        
        # Calculate number of emergency vehicles
        num_emergency = int(num_vehicles * self.emergency_ratio)
        num_normal = num_vehicles - num_emergency
        
        # Generate normal vehicles
        for i in range(num_normal):
            origin, destination = random.sample(edge_ids, 2)
            depart_time = random.uniform(0, 3600)  # Spread over 1 hour
            
            vehicles.append(Vehicle(
                id=f"vehicle_{i}",
                origin_edge=origin,
                destination_edge=destination,
                depart_time=depart_time,
                vehicle_type="normal"
            ))
        
        # Generate emergency vehicles
        for i in range(num_emergency):
            origin, destination = random.sample(edge_ids, 2)
            depart_time = random.uniform(0, 3600)
            
            vehicles.append(Vehicle(
                id=f"emergency_{i}",
                origin_edge=origin,
                destination_edge=destination,
                depart_time=depart_time,
                vehicle_type="emergency"
            ))
        
        # Sort by departure time
        vehicles.sort(key=lambda v: v.depart_time)
        
        return vehicles
    
    def _calculate_edge_states(
        self,
        vehicles: List[Vehicle],
        congestion_level: float
    ) -> Dict[str, EdgeState]:
        """
        Calculate current state of each edge based on vehicles
        """
        edge_states = {}
        
        # Count vehicles per edge (as origins - rough approximation)
        vehicle_counts = {}
        for vehicle in vehicles:
            edge_id = vehicle.origin_edge
            vehicle_counts[edge_id] = vehicle_counts.get(edge_id, 0) + 1
        
        # Calculate state for each edge
        for edge_id, edge in self.parser.edges.items():
            vehicle_count = vehicle_counts.get(edge_id, 0)
            
            # Calculate congestion based on capacity
            capacity = edge.capacity
            congestion_factor = min(1.0, vehicle_count / (capacity * 0.01))  # Rough estimate
            
            # Adjust congestion by global level
            congestion_factor = min(1.0, congestion_factor + congestion_level * 0.5)
            
            # Calculate current speed based on congestion
            speed_limit = edge.speed_limit_kmh
            current_speed = speed_limit * (1.0 - congestion_factor * 0.9)  # max 90% reduction
            current_speed = max(5.0, current_speed)  # Minimum 5 km/h
            
            edge_states[edge_id] = EdgeState(
                edge_id=edge_id,
                vehicle_count=vehicle_count,
                current_speed=current_speed,
                capacity=capacity,
                congestion_factor=congestion_factor
            )
        
        return edge_states
    
    def load_scenario(self, scenario_file: str) -> Dict:
        """Load a previously generated scenario"""
        with open(scenario_file, 'r') as f:
            return json.load(f)


if __name__ == "__main__":
    # Test the traffic generator
    import sys
    
    # Use sample network or command-line argument
    net_file = sys.argv[1] if len(sys.argv) > 1 else "./data/sumo/map.net.xml"
    
    try:
        # Parse network
        parser = SUMONetworkParser(net_file)
        parser.print_summary()
        
        # Create generator
        config = {
            'emergency_vehicle_ratio': 0.05,
            'default_congestion_level': 0.3,
            'speed_generation': {
                'timestep_minutes': 5,
                'noise_std': 3.0,
                'min_speed_factor': 0.1,
                'temporal_smoothing': 0.8
            }
        }
        
        generator = TrafficGenerator(parser, config)
        
        # Generate scenario
        scenario = generator.generate_traffic_scenario(
            num_vehicles=100,
            congestion_level=0.4,
            scenario_type="normal"
        )
        
        print("\n✅ Test completed successfully!")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Usage: python traffic_generator.py <path_to_net.xml>")
