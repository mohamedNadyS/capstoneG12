"""
Simulation Metrics Collector
Collects and analyzes metrics from SUMO simulations
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import json
import numpy as np
from dataclasses import dataclass, asdict


@dataclass
class VehicleMetrics:
    """Metrics for a single vehicle"""
    vehicle_id: str
    vehicle_type: str
    departure_time: float
    arrival_time: Optional[float]
    travel_time: Optional[float]
    waiting_time: float
    time_loss: float
    route_length: float
    average_speed: float
    completed: bool


@dataclass
class SimulationMetrics:
    """Overall simulation metrics"""
    total_vehicles: int
    completed_vehicles: int
    running_vehicles: int
    waiting_vehicles: int
    
    avg_travel_time: float
    avg_waiting_time: float
    avg_time_loss: float
    avg_speed: float
    
    emergency_vehicles: int
    emergency_avg_travel_time: float
    
    normal_vehicles: int
    normal_avg_travel_time: float
    
    total_distance: float
    simulation_duration: float
    throughput: float  # vehicles per hour


class MetricsCollector:
    """
    Collect and analyze SUMO simulation metrics
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        print(f"\n[METRICS] Metrics Collector initialized")
    
    def parse_tripinfo(self, tripinfo_file: str) -> List[VehicleMetrics]:
        """
        Parse SUMO tripinfo output file
        
        Args:
            tripinfo_file: Path to tripinfo.xml file
            
        Returns:
            List of vehicle metrics
        """
        tripinfo_path = Path(tripinfo_file)
        if not tripinfo_path.exists():
            raise FileNotFoundError(f"Tripinfo file not found: {tripinfo_file}")
        
        print(f"\n[METRICS] Parsing tripinfo: {tripinfo_file}")
        
        tree = ET.parse(tripinfo_file)
        root = tree.getroot()
        
        vehicle_metrics = []
        
        for tripinfo in root.findall('tripinfo'):
            vehicle_id = tripinfo.get('id')
            
            # Determine vehicle type (emergency if id contains 'emergency' or starts with 'e')
            vehicle_type = 'emergency' if 'emergency' in vehicle_id.lower() or vehicle_id.startswith('e') else 'normal'
            
            # Extract metrics
            depart = float(tripinfo.get('depart', 0))
            arrival = tripinfo.get('arrival')
            duration = tripinfo.get('duration')
            waiting_time = float(tripinfo.get('waitingTime', 0))
            time_loss = float(tripinfo.get('timeLoss', 0))
            route_length = float(tripinfo.get('routeLength', 0))
            
            # Calculate metrics
            if arrival and arrival != '-1':
                arrival_time = float(arrival)
                travel_time = float(duration) if duration else arrival_time - depart
                completed = True
                avg_speed = route_length / travel_time if travel_time > 0 else 0
            else:
                arrival_time = None
                travel_time = None
                completed = False
                avg_speed = 0
            
            metrics = VehicleMetrics(
                vehicle_id=vehicle_id,
                vehicle_type=vehicle_type,
                departure_time=depart,
                arrival_time=arrival_time,
                travel_time=travel_time,
                waiting_time=waiting_time,
                time_loss=time_loss,
                route_length=route_length,
                average_speed=avg_speed,
                completed=completed
            )
            
            vehicle_metrics.append(metrics)
        
        print(f"   [OK] Parsed {len(vehicle_metrics)} vehicle trips")
        
        return vehicle_metrics
    
    def calculate_metrics(
        self,
        vehicle_metrics: List[VehicleMetrics],
        simulation_duration: float
    ) -> SimulationMetrics:
        """
        Calculate overall simulation metrics
        
        Args:
            vehicle_metrics: List of individual vehicle metrics
            simulation_duration: Total simulation time in seconds
            
        Returns:
            Overall simulation metrics
        """
        print(f"\n[METRICS] Calculating overall metrics...")
        
        if not vehicle_metrics:
            return SimulationMetrics(
                total_vehicles=0,
                completed_vehicles=0,
                running_vehicles=0,
                waiting_vehicles=0,
                avg_travel_time=0,
                avg_waiting_time=0,
                avg_time_loss=0,
                avg_speed=0,
                emergency_vehicles=0,
                emergency_avg_travel_time=0,
                normal_vehicles=0,
                normal_avg_travel_time=0,
                total_distance=0,
                simulation_duration=simulation_duration,
                throughput=0
            )
        
        # Filter completed vehicles
        completed = [v for v in vehicle_metrics if v.completed]
        
        # Separate by type
        emergency = [v for v in completed if v.vehicle_type == 'emergency']
        normal = [v for v in completed if v.vehicle_type == 'normal']
        
        # Calculate averages
        if completed:
            avg_travel_time = np.mean([v.travel_time for v in completed])
            avg_waiting_time = np.mean([v.waiting_time for v in completed])
            avg_time_loss = np.mean([v.time_loss for v in completed])
            avg_speed = np.mean([v.average_speed for v in completed])
            total_distance = np.sum([v.route_length for v in completed])
        else:
            avg_travel_time = 0
            avg_waiting_time = 0
            avg_time_loss = 0
            avg_speed = 0
            total_distance = 0
        
        # Emergency vehicles
        if emergency:
            emergency_avg_travel = np.mean([v.travel_time for v in emergency])
        else:
            emergency_avg_travel = 0
        
        # Normal vehicles
        if normal:
            normal_avg_travel = np.mean([v.travel_time for v in normal])
        else:
            normal_avg_travel = 0
        
        # Throughput (vehicles per hour)
        if simulation_duration > 0:
            throughput = (len(completed) / simulation_duration) * 3600
        else:
            throughput = 0
        
        metrics = SimulationMetrics(
            total_vehicles=len(vehicle_metrics),
            completed_vehicles=len(completed),
            running_vehicles=len(vehicle_metrics) - len(completed),
            waiting_vehicles=len([v for v in vehicle_metrics if v.waiting_time > 0]),
            avg_travel_time=float(avg_travel_time),
            avg_waiting_time=float(avg_waiting_time),
            avg_time_loss=float(avg_time_loss),
            avg_speed=float(avg_speed),
            emergency_vehicles=len(emergency),
            emergency_avg_travel_time=float(emergency_avg_travel),
            normal_vehicles=len(normal),
            normal_avg_travel_time=float(normal_avg_travel),
            total_distance=float(total_distance),
            simulation_duration=simulation_duration,
            throughput=float(throughput)
        )
        
        print(f"   [OK] Metrics calculated")
        
        return metrics
    
    def print_metrics(self, metrics: SimulationMetrics):
        """Print metrics summary"""
        print(f"\n" + "="*70)
        print("SIMULATION METRICS SUMMARY")
        print("="*70)
        
        print(f"\nVehicles:")
        print(f"  Total: {metrics.total_vehicles}")
        print(f"  Completed: {metrics.completed_vehicles}")
        print(f"  Running: {metrics.running_vehicles}")
        print(f"  With waiting: {metrics.waiting_vehicles}")
        
        print(f"\nPerformance:")
        print(f"  Avg travel time: {metrics.avg_travel_time:.2f} seconds")
        print(f"  Avg waiting time: {metrics.avg_waiting_time:.2f} seconds")
        print(f"  Avg time loss: {metrics.avg_time_loss:.2f} seconds")
        print(f"  Avg speed: {metrics.avg_speed:.2f} m/s ({metrics.avg_speed * 3.6:.2f} km/h)")
        
        print(f"\nEmergency Vehicles:")
        print(f"  Count: {metrics.emergency_vehicles}")
        print(f"  Avg travel time: {metrics.emergency_avg_travel_time:.2f} seconds")
        
        print(f"\nNormal Vehicles:")
        print(f"  Count: {metrics.normal_vehicles}")
        print(f"  Avg travel time: {metrics.normal_avg_travel_time:.2f} seconds")
        
        print(f"\nOverall:")
        print(f"  Total distance: {metrics.total_distance:.2f} meters ({metrics.total_distance/1000:.2f} km)")
        print(f"  Simulation duration: {metrics.simulation_duration:.2f} seconds")
        print(f"  Throughput: {metrics.throughput:.2f} vehicles/hour")
        
        print("="*70)
    
    def save_metrics(
        self,
        metrics: SimulationMetrics,
        vehicle_metrics: List[VehicleMetrics],
        output_file: str
    ):
        """
        Save metrics to JSON file
        
        Args:
            metrics: Overall simulation metrics
            vehicle_metrics: Individual vehicle metrics
            output_file: Output JSON file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'simulation_metrics': asdict(metrics),
            'vehicle_metrics': [asdict(v) for v in vehicle_metrics]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n[METRICS] Metrics saved to: {output_file}")


if __name__ == "__main__":
    print("="*70)
    print("METRICS COLLECTOR TEST")
    print("="*70)
    
    print("\nThis module collects metrics from SUMO simulations:")
    print("  • Parse tripinfo.xml output")
    print("  • Calculate performance metrics")
    print("  • Analyze emergency vs normal vehicles")
    print("  • Export to JSON for analysis")
