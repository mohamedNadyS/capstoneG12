"""
Speed Mapper
Maps GNN predictions (trained on METR-LA: 207 nodes) to SUMO network edges (95 edges)
"""

import numpy as np
from typing import Dict, List, Tuple
import json
from pathlib import Path


class SpeedMapper:
    """
    Handle mapping between different network sizes
    
    Problem: GNN trained on METR-LA (207 nodes) but SUMO has 95 edges
    Solution: Use various mapping strategies
    """
    
    def __init__(self, num_sumo_edges: int, mapping_strategy: str = 'direct'):
        """
        Initialize mapper
        
        Args:
            num_sumo_edges: Number of edges in SUMO network (e.g., 95)
            mapping_strategy: How to map predictions
                - 'direct': Use first N predictions (simple)
                - 'average': Average groups of predictions
                - 'interpolate': Interpolate to match size
                - 'weighted': Weighted mapping based on similarity
        """
        self.num_sumo_edges = num_sumo_edges
        self.strategy = mapping_strategy
        
        print(f"🗺️  Speed Mapper initialized")
        print(f"   Target edges: {num_sumo_edges}")
        print(f"   Strategy: {mapping_strategy}")
    
    def map_predictions(
        self,
        predictions: np.ndarray,
        edge_ids: List[str] = None
    ) -> Dict[str, np.ndarray]:
        """
        Map predictions to SUMO edges
        
        Args:
            predictions: GNN predictions, shape (horizon, num_gnn_nodes)
            edge_ids: List of SUMO edge IDs (optional)
            
        Returns:
            Dictionary mapping edge_id -> predicted_speeds (horizon,)
        """
        horizon, num_gnn_nodes = predictions.shape
        
        print(f"\n📊 Mapping predictions...")
        print(f"   Input shape: {predictions.shape} (horizon × GNN nodes)")
        print(f"   Target: {self.num_sumo_edges} SUMO edges")
        
        if self.strategy == 'direct':
            mapped = self._map_direct(predictions)
        elif self.strategy == 'average':
            mapped = self._map_average(predictions)
        elif self.strategy == 'interpolate':
            mapped = self._map_interpolate(predictions)
        elif self.strategy == 'weighted':
            mapped = self._map_weighted(predictions)
        else:
            raise ValueError(f"Unknown mapping strategy: {self.strategy}")
        
        # Create edge_id mapping
        if edge_ids is None:
            edge_ids = [f"edge_{i}" for i in range(self.num_sumo_edges)]
        
        result = {}
        for i, edge_id in enumerate(edge_ids):
            result[edge_id] = mapped[:, i]  # All horizons for this edge
        
        print(f"   ✓ Mapped to {len(result)} edges")
        
        return result
    
    def _map_direct(self, predictions: np.ndarray) -> np.ndarray:
        """
        Direct mapping: Use first N predictions
        
        Simple but works when GNN nodes >= SUMO edges
        """
        horizon, num_gnn_nodes = predictions.shape
        
        if num_gnn_nodes < self.num_sumo_edges:
            # Need to expand - repeat last predictions
            shortage = self.num_sumo_edges - num_gnn_nodes
            extra = np.tile(predictions[:, -1:], (1, shortage))
            mapped = np.concatenate([predictions, extra], axis=1)
        else:
            # Just take first N
            mapped = predictions[:, :self.num_sumo_edges]
        
        return mapped
    
    def _map_average(self, predictions: np.ndarray) -> np.ndarray:
        """
        Average mapping: Group GNN nodes and average them
        
        Better for when GNN nodes > SUMO edges
        """
        horizon, num_gnn_nodes = predictions.shape
        
        # Calculate group size
        group_size = num_gnn_nodes / self.num_sumo_edges
        
        mapped = np.zeros((horizon, self.num_sumo_edges))
        
        for i in range(self.num_sumo_edges):
            start_idx = int(i * group_size)
            end_idx = int((i + 1) * group_size)
            mapped[:, i] = np.mean(predictions[:, start_idx:end_idx], axis=1)
        
        return mapped
    
    def _map_interpolate(self, predictions: np.ndarray) -> np.ndarray:
        """
        Interpolate predictions to match SUMO network size
        
        Smooth mapping that preserves patterns
        """
        horizon, num_gnn_nodes = predictions.shape
        
        mapped = np.zeros((horizon, self.num_sumo_edges))
        
        # Original indices
        original_indices = np.linspace(0, num_gnn_nodes - 1, num_gnn_nodes)
        # Target indices
        target_indices = np.linspace(0, num_gnn_nodes - 1, self.num_sumo_edges)
        
        for h in range(horizon):
            # Interpolate each horizon
            mapped[h, :] = np.interp(target_indices, original_indices, predictions[h, :])
        
        return mapped
    
    def _map_weighted(self, predictions: np.ndarray) -> np.ndarray:
        """
        Weighted mapping based on spatial proximity
        
        Most sophisticated but requires position information
        For now, falls back to interpolation
        """
        # TODO: Implement if we have node coordinates
        return self._map_interpolate(predictions)
    
    def create_mapping_config(
        self,
        sumo_edge_ids: List[str],
        save_path: str = None
    ) -> Dict:
        """
        Create and optionally save mapping configuration
        
        Args:
            sumo_edge_ids: List of SUMO edge IDs
            save_path: Path to save config JSON (optional)
            
        Returns:
            Mapping configuration dictionary
        """
        config = {
            'num_sumo_edges': self.num_sumo_edges,
            'mapping_strategy': self.strategy,
            'edge_ids': sumo_edge_ids,
            'edge_count': len(sumo_edge_ids)
        }
        
        if save_path:
            with open(save_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"   ✓ Saved mapping config to: {save_path}")
        
        return config
    
    def validate_predictions(
        self,
        predictions: Dict[str, np.ndarray],
        min_speed: float = 0.0,
        max_speed: float = 150.0
    ) -> Dict:
        """
        Validate predicted speeds are realistic
        
        Args:
            predictions: Edge predictions from map_predictions()
            min_speed: Minimum realistic speed (km/h)
            max_speed: Maximum realistic speed (km/h)
            
        Returns:
            Validation report
        """
        speeds = np.array([pred for pred in predictions.values()])
        
        report = {
            'num_edges': len(predictions),
            'mean_speed': float(np.mean(speeds)),
            'std_speed': float(np.std(speeds)),
            'min_speed': float(np.min(speeds)),
            'max_speed': float(np.max(speeds)),
            'out_of_range_count': int(np.sum((speeds < min_speed) | (speeds > max_speed))),
            'valid': True
        }
        
        if report['out_of_range_count'] > 0:
            report['valid'] = False
            report['warning'] = f"{report['out_of_range_count']} predictions outside [{min_speed}, {max_speed}] km/h"
        
        return report


def create_sumo_to_gnn_mapping(
    sumo_edge_ids: List[str],
    gnn_node_count: int = 207,
    strategy: str = 'interpolate'
) -> SpeedMapper:
    """
    Factory function to create mapper for SUMO network
    
    Args:
        sumo_edge_ids: List of SUMO edge IDs
        gnn_node_count: Number of nodes in trained GNN (default: 207 for METR-LA)
        strategy: Mapping strategy
        
    Returns:
        Configured SpeedMapper
    """
    mapper = SpeedMapper(
        num_sumo_edges=len(sumo_edge_ids),
        mapping_strategy=strategy
    )
    
    return mapper


if __name__ == "__main__":
    # Test the mapper
    print("="*70)
    print("SPEED MAPPER TEST")
    print("="*70)
    
    # Simulate GNN predictions (207 nodes from METR-LA)
    gnn_predictions = np.random.uniform(20, 60, size=(3, 207))  # 3 horizons, 207 nodes
    print(f"\nGNN predictions shape: {gnn_predictions.shape}")
    
    # SUMO network has 95 edges
    sumo_edge_ids = [f"E{i}" for i in range(95)]
    print(f"SUMO edges: {len(sumo_edge_ids)}")
    
    # Test different strategies
    for strategy in ['direct', 'average', 'interpolate']:
        print(f"\n{'='*70}")
        print(f"Testing strategy: {strategy}")
        print('='*70)
        
        mapper = SpeedMapper(num_sumo_edges=95, mapping_strategy=strategy)
        mapped = mapper.map_predictions(gnn_predictions, sumo_edge_ids)
        
        print(f"\nResults:")
        print(f"  Mapped edges: {len(mapped)}")
        print(f"  Sample (E0): {mapped['E0']}")
        
        # Validate
        validation = mapper.validate_predictions(mapped)
        print(f"\nValidation:")
        for key, value in validation.items():
            print(f"  {key}: {value}")
