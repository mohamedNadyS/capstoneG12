"""
Variable Traffic Pattern Generator
Creates realistic time-varying traffic patterns that challenge the prediction model
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class TrafficPattern:
    """Defines a traffic pattern over time"""
    name: str
    description: str
    base_congestion: float
    congestion_variance: float
    speed_fluctuation: float
    pattern_type: str  # 'rush_hour', 'incident', 'gradual', 'random', 'mixed'


class VariableTrafficGenerator:
    """
    Generate realistic time-varying traffic patterns
    Makes prediction more challenging and realistic
    """
    
    def __init__(self, num_timesteps: int = 12):
        self.num_timesteps = num_timesteps
        
        # Define realistic patterns
        self.patterns = {
            'morning_rush': TrafficPattern(
                name='morning_rush',
                description='Morning rush hour - gradual buildup then release',
                base_congestion=0.4,
                congestion_variance=0.3,
                speed_fluctuation=0.15,
                pattern_type='rush_hour'
            ),
            'incident': TrafficPattern(
                name='incident',
                description='Sudden traffic incident causing jam',
                base_congestion=0.3,
                congestion_variance=0.5,
                speed_fluctuation=0.25,
                pattern_type='incident'
            ),
            'gradual_buildup': TrafficPattern(
                name='gradual_buildup',
                description='Steady increase in traffic',
                base_congestion=0.2,
                congestion_variance=0.4,
                speed_fluctuation=0.12,
                pattern_type='gradual'
            ),
            'variable': TrafficPattern(
                name='variable',
                description='Highly variable conditions',
                base_congestion=0.3,
                congestion_variance=0.4,
                speed_fluctuation=0.20,
                pattern_type='random'
            ),
            'mixed': TrafficPattern(
                name='mixed',
                description='Mix of different conditions',
                base_congestion=0.35,
                congestion_variance=0.35,
                speed_fluctuation=0.18,
                pattern_type='mixed'
            )
        }
    
    def generate_congestion_timeline(
        self,
        pattern: TrafficPattern,
        num_edges: int
    ) -> np.ndarray:
        """
        Generate time-varying congestion levels
        
        Args:
            pattern: Traffic pattern to follow
            num_edges: Number of road edges
            
        Returns:
            Congestion levels: (num_timesteps, num_edges)
        """
        congestion = np.zeros((self.num_timesteps, num_edges))
        
        if pattern.pattern_type == 'rush_hour':
            # Morning rush: low → peak → medium
            timeline = self._rush_hour_pattern()
        elif pattern.pattern_type == 'incident':
            # Sudden spike in middle
            timeline = self._incident_pattern()
        elif pattern.pattern_type == 'gradual':
            # Steady increase
            timeline = self._gradual_pattern()
        elif pattern.pattern_type == 'random':
            # Random fluctuations
            timeline = self._random_pattern()
        else:  # mixed
            # Combination
            timeline = self._mixed_pattern()
        
        # Apply pattern to each edge with variation
        for e in range(num_edges):
            # Each edge has slightly different timing
            edge_offset = np.random.uniform(-0.1, 0.1)
            edge_timeline = np.clip(timeline + edge_offset, 0, 1)
            
            # Scale to pattern parameters
            congestion[:, e] = (
                pattern.base_congestion + 
                edge_timeline * pattern.congestion_variance
            )
            
            # Add noise
            noise = np.random.normal(0, 0.05, self.num_timesteps)
            congestion[:, e] = np.clip(congestion[:, e] + noise, 0, 1)
        
        return congestion
    
    def _rush_hour_pattern(self) -> np.ndarray:
        """
        Morning rush hour pattern
        Time: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
        Cong: 0.2 → 0.4 → 0.7 → 0.9 → 0.8 → 0.6 → 0.4 → 0.3 → 0.2 → 0.2 → 0.1 → 0.1
        """
        # Gaussian-like peak around timestep 3-4
        timeline = np.zeros(self.num_timesteps)
        peak_time = 3.5
        
        for t in range(self.num_timesteps):
            # Gaussian curve
            timeline[t] = np.exp(-0.5 * ((t - peak_time) / 2.5) ** 2)
        
        return timeline
    
    def _incident_pattern(self) -> np.ndarray:
        """
        Traffic incident pattern - sudden spike
        Time: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
        Cong: 0.2 → 0.2 → 0.3 → 0.9 → 0.95 → 0.85 → 0.6 → 0.4 → 0.3 → 0.2 → 0.2 → 0.1
        """
        timeline = np.full(self.num_timesteps, 0.1)
        
        # Incident occurs at timestep 3
        incident_time = 3
        
        for t in range(self.num_timesteps):
            if t < incident_time:
                timeline[t] = 0.1 + (t / incident_time) * 0.2
            elif t == incident_time:
                timeline[t] = 1.0  # Spike!
            elif t == incident_time + 1:
                timeline[t] = 0.95
            else:
                # Decay
                decay_time = t - incident_time
                timeline[t] = max(0.1, 0.95 * np.exp(-0.3 * decay_time))
        
        return timeline
    
    def _gradual_pattern(self) -> np.ndarray:
        """
        Gradual buildup - linear increase
        Time: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11
        Cong: 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 → 0.65 → 0.7 → 0.75 → 0.8 → 0.85 → 0.9
        """
        return np.linspace(0.1, 0.9, self.num_timesteps)
    
    def _random_pattern(self) -> np.ndarray:
        """
        Random fluctuations
        """
        timeline = np.random.uniform(0.2, 0.8, self.num_timesteps)
        
        # Smooth it a bit
        smoothed = np.zeros(self.num_timesteps)
        for t in range(self.num_timesteps):
            window_start = max(0, t - 1)
            window_end = min(self.num_timesteps, t + 2)
            smoothed[t] = np.mean(timeline[window_start:window_end])
        
        return smoothed
    
    def _mixed_pattern(self) -> np.ndarray:
        """
        Mix of different patterns
        """
        # Combine rush hour + incident + random
        rush = self._rush_hour_pattern()
        incident = self._incident_pattern()
        random = self._random_pattern()
        
        # Weighted combination
        timeline = 0.4 * rush + 0.3 * incident + 0.3 * random
        return np.clip(timeline, 0, 1)
    
    def generate_variable_speeds(
        self,
        edges: Dict,  # Dict[edge_id -> SUMOEdge]
        pattern_name: str = 'mixed',
        noise_std: float = 4.0
    ) -> Dict[str, List[float]]:
        """
        Generate realistic time-varying speeds for all edges
        
        Args:
            edges: Dictionary of SUMO edges
            pattern_name: Which pattern to use
            noise_std: Speed noise standard deviation
            
        Returns:
            Dictionary mapping edge_id -> [speed at each timestep]
        """
        pattern = self.patterns.get(pattern_name, self.patterns['mixed'])
        num_edges = len(edges)
        
        print(f"\n🌊 Generating variable traffic pattern: {pattern.name}")
        print(f"   Description: {pattern.description}")
        print(f"   Base congestion: {pattern.base_congestion:.2f}")
        print(f"   Variance: {pattern.congestion_variance:.2f}")
        
        # Generate congestion timeline
        congestion_timeline = self.generate_congestion_timeline(pattern, num_edges)
        
        # Convert to speeds
        edge_ids = list(edges.keys())
        speed_history = {}
        
        for i, edge_id in enumerate(edge_ids):
            edge = edges[edge_id]
            base_speed = edge.speed_limit_kmh
            
            speeds = []
            for t in range(self.num_timesteps):
                congestion = congestion_timeline[t, i]
                
                # Speed decreases with congestion
                # congestion=0 → 100% speed, congestion=1 → 10% speed
                speed_factor = 1.0 - (congestion * 0.9)
                speed = base_speed * speed_factor
                
                # Add realistic noise
                noise = np.random.normal(0, noise_std)
                speed = max(5.0, min(speed + noise, base_speed * 1.1))
                
                speeds.append(speed)
            
            speed_history[edge_id] = speeds
        
        # Calculate statistics
        all_speeds = [s for speeds in speed_history.values() for s in speeds]
        speed_changes = []
        for speeds in speed_history.values():
            for t in range(1, len(speeds)):
                speed_changes.append(abs(speeds[t] - speeds[t-1]))
        
        print(f"\n   ✓ Generated {len(speed_history)} edge speed timelines")
        print(f"   📊 Speed statistics:")
        print(f"      • Mean: {np.mean(all_speeds):.2f} km/h")
        print(f"      • Std dev: {np.std(all_speeds):.2f} km/h")
        print(f"      • Range: [{np.min(all_speeds):.1f}, {np.max(all_speeds):.1f}] km/h")
        print(f"      • Avg change per timestep: {np.mean(speed_changes):.2f} km/h")
        print(f"      • Max change: {np.max(speed_changes):.2f} km/h")
        
        return speed_history
    
    def visualize_pattern(self, pattern_name: str = 'mixed') -> str:
        """
        Generate ASCII visualization of the pattern
        
        Args:
            pattern_name: Pattern to visualize
            
        Returns:
            ASCII art string
        """
        pattern = self.patterns.get(pattern_name, self.patterns['mixed'])
        
        if pattern.pattern_type == 'rush_hour':
            timeline = self._rush_hour_pattern()
        elif pattern.pattern_type == 'incident':
            timeline = self._incident_pattern()
        elif pattern.pattern_type == 'gradual':
            timeline = self._gradual_pattern()
        elif pattern.pattern_type == 'random':
            timeline = self._random_pattern()
        else:
            timeline = self._mixed_pattern()
        
        # Create ASCII chart
        chart = f"\n   Pattern: {pattern.name}\n"
        chart += f"   {pattern.description}\n\n"
        chart += "   Congestion Level Over Time:\n"
        chart += "   1.0 |"
        
        # 10 rows
        for level in range(10, -1, -1):
            chart += "\n   "
            if level == 10:
                chart += "1.0 |"
            elif level == 5:
                chart += "0.5 |"
            elif level == 0:
                chart += "0.0 |"
            else:
                chart += "    |"
            
            for t in range(self.num_timesteps):
                value = timeline[t] * 10
                if value >= level:
                    chart += "██"
                else:
                    chart += "  "
        
        chart += "\n       └" + "──" * self.num_timesteps
        chart += "\n        "
        for t in range(self.num_timesteps):
            chart += f"{t:<2}"
        chart += "\n        Time (5-minute intervals)\n"
        
        return chart


if __name__ == "__main__":
    # Test the generator
    print("="*70)
    print("VARIABLE TRAFFIC PATTERN GENERATOR TEST")
    print("="*70)
    
    generator = VariableTrafficGenerator(num_timesteps=12)
    
    # Show all patterns
    for pattern_name in generator.patterns.keys():
        viz = generator.visualize_pattern(pattern_name)
        print(viz)
        print()
