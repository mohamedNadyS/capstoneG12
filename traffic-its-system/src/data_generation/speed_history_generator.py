"""
Speed History Generator
Generates realistic historical speed data for GNN model input
"""

import numpy as np
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class SpeedTimeSeries:
    """Time series of speeds for an edge"""
    edge_id: str
    speeds: List[float]  # Speed at each timestep
    timestamps: List[float]  # Time in minutes
    
    def __len__(self):
        return len(self.speeds)
    
    def get_latest(self) -> float:
        """Get most recent speed"""
        return self.speeds[-1] if self.speeds else 0.0


class SpeedHistoryGenerator:
    """
    Generate synthetic speed history with realistic patterns
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize generator
        
        Args:
            config: Configuration dictionary from traffic_generation.yaml
        """
        self.config = config or {}
        
        # Default parameters
        self.timestep_minutes = self.config.get('timestep_minutes', 5)
        self.noise_std = self.config.get('noise_std', 3.0)
        self.min_speed_factor = self.config.get('min_speed_factor', 0.1)
        self.max_speed_factor = self.config.get('max_speed_factor', 1.0)
        self.temporal_smoothing = self.config.get('temporal_smoothing', 0.8)
        
    def generate_hourly_history(
        self,
        edges: Dict,  # Dict[edge_id -> SUMOEdge]
        congestion_level: float,
        num_timesteps: int = 12
    ) -> Dict[str, SpeedTimeSeries]:
        """
        Generate 1 hour of speed history for all edges
        
        Args:
            edges: Dictionary of SUMO edges
            congestion_level: Overall congestion (0.0 - 1.0)
            num_timesteps: Number of timesteps (default: 12 = 1 hour)
            
        Returns:
            Dictionary mapping edge_id -> SpeedTimeSeries
        """
        print(f"\n🕐 Generating speed history ({num_timesteps} timesteps)...")
        
        history = {}
        
        # Generate base speeds based on congestion
        for edge_id, edge in edges.items():
            base_speed = edge.speed_limit_kmh
            
            # Apply congestion: reduce speed based on congestion level
            # congestion=0.0 -> 100% of speed limit
            # congestion=1.0 -> 10% of speed limit (jam)
            congestion_factor = 1.0 - (congestion_level * (1.0 - self.min_speed_factor))
            target_speed = base_speed * congestion_factor
            
            # Generate time series with realistic variations
            speeds = self._generate_time_series(
                target_speed=target_speed,
                num_steps=num_timesteps,
                noise_std=self.noise_std
            )
            
            # Create timestamps
            timestamps = [i * self.timestep_minutes for i in range(num_timesteps)]
            
            history[edge_id] = SpeedTimeSeries(
                edge_id=edge_id,
                speeds=speeds,
                timestamps=timestamps
            )
        
        print(f"   ✓ Generated history for {len(history)} edges")
        return history
    
    def _generate_time_series(
        self,
        target_speed: float,
        num_steps: int,
        noise_std: float
    ) -> List[float]:
        """
        Generate realistic speed time series
        
        Features:
        - Gradual changes (no sudden jumps)
        - Random variations around target
        - Temporal smoothing
        """
        speeds = []
        current_speed = target_speed
        
        for _ in range(num_steps):
            # Add random noise
            noise = np.random.normal(0, noise_std)
            
            # Move gradually toward target with noise
            new_speed = (self.temporal_smoothing * current_speed + 
                        (1 - self.temporal_smoothing) * (target_speed + noise))
            
            # Clamp to reasonable bounds
            new_speed = max(5.0, min(new_speed, target_speed * self.max_speed_factor))
            
            speeds.append(new_speed)
            current_speed = new_speed
        
        return speeds
    
    def add_congestion_propagation(
        self,
        history: Dict[str, SpeedTimeSeries],
        edges: Dict,
        adjacency: Dict[str, List[str]],
        propagation_factor: float = 0.3
    ):
        """
        Simulate congestion propagation to neighboring roads
        
        Args:
            history: Speed history to modify
            edges: Edge definitions
            adjacency: Dict mapping edge_id -> list of downstream edge_ids
            propagation_factor: How much congestion spreads (0.0 - 1.0)
        """
        print(f"   🔄 Applying congestion propagation (factor={propagation_factor:.2f})...")
        
        # For each timestep, propagate congestion
        num_steps = len(next(iter(history.values())).speeds)
        
        for t in range(1, num_steps):
            # Calculate congestion (speed reduction) for each edge
            for edge_id, time_series in history.items():
                if edge_id not in adjacency:
                    continue
                
                # Get upstream neighbors
                neighbors = adjacency.get(edge_id, [])
                if not neighbors:
                    continue
                
                # Average speed reduction of neighbors
                neighbor_speeds = []
                for neighbor_id in neighbors:
                    if neighbor_id in history:
                        neighbor_speeds.append(history[neighbor_id].speeds[t-1])
                
                if neighbor_speeds:
                    avg_neighbor_speed = np.mean(neighbor_speeds)
                    current_speed = time_series.speeds[t]
                    
                    # If neighbors are slow, reduce this edge's speed
                    edge_speed_limit = edges[edge_id].speed_limit_kmh
                    
                    if avg_neighbor_speed < edge_speed_limit * 0.7:
                        # Apply propagation
                        reduction = (edge_speed_limit - avg_neighbor_speed) * propagation_factor
                        new_speed = max(current_speed - reduction, avg_neighbor_speed * 0.8)
                        time_series.speeds[t] = new_speed
    
    def add_rush_hour_pattern(
        self,
        history: Dict[str, SpeedTimeSeries],
        peak_timestep: int = 6,
        peak_factor: float = 0.5
    ):
        """
        Add rush hour traffic pattern (speeds dip in the middle)
        
        Args:
            history: Speed history to modify
            peak_timestep: When rush hour peaks (default: middle of period)
            peak_factor: How much to reduce speeds (0.5 = 50% reduction)
        """
        print(f"   🚗 Adding rush hour pattern (peak at timestep {peak_timestep})...")
        
        num_steps = len(next(iter(history.values())).speeds)
        
        for time_series in history.values():
            for t in range(num_steps):
                # Gaussian-like pattern centered at peak_timestep
                distance_from_peak = abs(t - peak_timestep)
                factor = np.exp(-0.5 * (distance_from_peak / 3) ** 2)
                
                # Reduce speed during rush hour
                reduction = time_series.speeds[t] * peak_factor * factor
                time_series.speeds[t] = max(5.0, time_series.speeds[t] - reduction)
    
    def export_for_gnn(
        self,
        history: Dict[str, SpeedTimeSeries],
        edge_order: List[str]
    ) -> np.ndarray:
        """
        Export speed history in GNN input format
        
        Args:
            history: Speed time series data
            edge_order: Ordered list of edge IDs (defines node order for GNN)
            
        Returns:
            numpy array of shape (num_timesteps, num_nodes)
            where each node corresponds to an edge
        """
        num_timesteps = len(next(iter(history.values())).speeds)
        num_edges = len(edge_order)
        
        # Create matrix
        speed_matrix = np.zeros((num_timesteps, num_edges))
        
        for i, edge_id in enumerate(edge_order):
            if edge_id in history:
                speed_matrix[:, i] = history[edge_id].speeds
        
        return speed_matrix
    
    def get_statistics(self, history: Dict[str, SpeedTimeSeries]) -> Dict:
        """Calculate statistics of generated history"""
        all_speeds = []
        for time_series in history.values():
            all_speeds.extend(time_series.speeds)
        
        return {
            'mean_speed': np.mean(all_speeds),
            'std_speed': np.std(all_speeds),
            'min_speed': np.min(all_speeds),
            'max_speed': np.max(all_speeds),
            'num_edges': len(history),
            'num_timesteps': len(next(iter(history.values())).speeds)
        }


if __name__ == "__main__":
    # Test the generator
    from src.sumo_integration.sumo_parser import SUMONetworkParser, SUMOEdge
    
    # Create dummy edges for testing
    dummy_edges = {
        'edge1': SUMOEdge('edge1', 'n1', 'n2', 1, 2, 13.89, 100, [], 'primary'),
        'edge2': SUMOEdge('edge2', 'n2', 'n3', 1, 2, 13.89, 100, [], 'primary'),
        'edge3': SUMOEdge('edge3', 'n3', 'n4', 1, 2, 13.89, 100, [], 'primary'),
    }
    
    config = {
        'timestep_minutes': 5,
        'noise_std': 3.0,
        'min_speed_factor': 0.1,
        'temporal_smoothing': 0.8
    }
    
    generator = SpeedHistoryGenerator(config)
    history = generator.generate_hourly_history(
        edges=dummy_edges,
        congestion_level=0.5,
        num_timesteps=12
    )
    
    stats = generator.get_statistics(history)
    print("\nGenerated Speed History Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Show sample data
    print("\nSample edge speeds:")
    sample_edge = next(iter(history.values()))
    print(f"  Edge: {sample_edge.edge_id}")
    print(f"  Speeds: {[f'{s:.1f}' for s in sample_edge.speeds]}")
