"""
Traffic Prediction Pipeline
Integrates GNN predictor, speed mapper, and traffic data
"""

import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from src.prediction.gnn_predictor import GNNTrafficPredictor
from src.prediction.speed_mapper import SpeedMapper
from src.sumo_integration.sumo_parser import SUMONetworkParser


class TrafficPredictionPipeline:
    """
    Complete pipeline for traffic speed prediction
    """
    
    def __init__(
        self,
        model_path: str,
        scaler_path: str,
        sumo_network: SUMONetworkParser,
        mapping_strategy: str = 'interpolate',
        device: str = 'auto'
    ):
        """
        Initialize prediction pipeline
        
        Args:
            model_path: Path to trained GNN model
            scaler_path: Path to fitted scaler
            sumo_network: Parsed SUMO network
            mapping_strategy: How to map GNN nodes to SUMO edges
            device: 'auto', 'cpu', or 'cuda'
        """
        print("\n" + "="*70)
        print("INITIALIZING TRAFFIC PREDICTION PIPELINE")
        print("="*70)
        
        self.sumo_network = sumo_network
        self.num_edges = len(sumo_network.edges)
        self.edge_ids = list(sumo_network.edges.keys())
        
        print(f"\n📍 SUMO Network:")
        print(f"   Edges: {self.num_edges}")
        print(f"   Nodes: {len(sumo_network.nodes)}")
        
        # Initialize GNN predictor
        # Note: We'll use the SUMO network size directly
        # The model was trained on 207 nodes, but we'll adapt it
        print(f"\n🧠 Loading GNN Model...")
        self.predictor = GNNTrafficPredictor(
            model_path=model_path,
            scaler_path=scaler_path,
            num_nodes=self.num_edges,  # Use SUMO network size
            device=device
        )
        
        # Initialize speed mapper
        print(f"\n🗺️  Initializing Speed Mapper...")
        self.mapper = SpeedMapper(
            num_sumo_edges=self.num_edges,
            mapping_strategy=mapping_strategy
        )
        
        print(f"\n✅ Pipeline Ready!")
        print("="*70)
    
    def predict_from_history(
        self,
        speed_history: np.ndarray,
        adjacency_matrix: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Predict future speeds from historical data
        
        Args:
            speed_history: Historical speeds (timesteps, num_edges) or (num_edges, timesteps)
            adjacency_matrix: Optional adjacency matrix for graph structure
            
        Returns:
            Prediction results with mapped speeds
        """
        print("\n" + "="*70)
        print("RUNNING PREDICTION")
        print("="*70)
        
        # Ensure correct shape
        if speed_history.shape[0] == self.num_edges:
            speed_history = speed_history.T
        
        print(f"\n📥 Input:")
        print(f"   Shape: {speed_history.shape}")
        print(f"   Mean speed: {np.mean(speed_history):.2f} km/h")
        print(f"   Speed range: [{np.min(speed_history):.2f}, {np.max(speed_history):.2f}] km/h")
        
        # Create adjacency if not provided
        if adjacency_matrix is None:
            print(f"\n📊 Creating graph structure...")
            adjacency_matrix = self._create_adjacency_from_sumo()
        
        # Run GNN prediction
        print(f"\n🔮 Running GNN prediction...")
        gnn_result = self.predictor.predict(
            speed_history=speed_history,
            adjacency_matrix=adjacency_matrix
        )
        
        print(f"   ✓ Predicted shape: {gnn_result['predictions'].shape}")
        print(f"   ✓ Horizons: {gnn_result['horizons_minutes']} minutes")
        
        # Map to SUMO edges
        print(f"\n🗺️  Mapping to SUMO edges...")
        mapped_predictions = self.mapper.map_predictions(
            predictions=gnn_result['predictions'],
            edge_ids=self.edge_ids
        )
        
        # Validate predictions
        validation = self.mapper.validate_predictions(mapped_predictions)
        
        print(f"\n✅ Prediction Complete!")
        print(f"   Mean predicted speed: {validation['mean_speed']:.2f} km/h")
        print(f"   Speed range: [{validation['min_speed']:.2f}, {validation['max_speed']:.2f}] km/h")
        
        if not validation['valid']:
            print(f"   ⚠️  {validation.get('warning', 'Validation warning')}")
        
        # Compile results
        result = {
            'predictions': mapped_predictions,  # Dict[edge_id -> speeds for 3 horizons]
            'horizons_minutes': gnn_result['horizons_minutes'],
            'confidence': {eid: gnn_result['confidence'][i] for i, eid in enumerate(self.edge_ids)},
            'validation': validation,
            'timestamp': datetime.now().isoformat(),
            'input_summary': {
                'shape': speed_history.shape,
                'mean_speed': float(np.mean(speed_history)),
                'std_speed': float(np.std(speed_history))
            }
        }
        
        return result
    
    def predict_from_scenario(
        self,
        scenario_path: str
    ) -> Dict:
        """
        Predict from a generated traffic scenario
        
        Args:
            scenario_path: Path to traffic scenario directory
            
        Returns:
            Prediction results
        """
        scenario_path = Path(scenario_path)
        
        print(f"\n📂 Loading scenario from: {scenario_path}")
        
        # Load speed history
        speed_history_file = scenario_path / "speed_matrix.npy"
        if not speed_history_file.exists():
            raise FileNotFoundError(f"Speed history not found: {speed_history_file}")
        
        speed_history = np.load(speed_history_file)
        print(f"   ✓ Loaded speed history: {speed_history.shape}")
        
        # Load edge order
        edge_order_file = scenario_path / "edge_order.json"
        if edge_order_file.exists():
            with open(edge_order_file, 'r') as f:
                edge_order = json.load(f)
            print(f"   ✓ Loaded edge order: {len(edge_order)} edges")
        
        # Run prediction
        return self.predict_from_history(speed_history)
    
    def _create_adjacency_from_sumo(self) -> np.ndarray:
        """
        Create adjacency matrix from SUMO network topology
        
        Returns:
            Adjacency matrix (num_edges, num_edges)
        """
        adjacency = np.zeros((self.num_edges, self.num_edges))
        
        edge_to_idx = {eid: i for i, eid in enumerate(self.edge_ids)}
        
        # Build adjacency based on connectivity
        for i, edge_id in enumerate(self.edge_ids):
            edge = self.sumo_network.edges[edge_id]
            
            # Find edges that connect to this edge
            # (edges that start from this edge's end node)
            outgoing = self.sumo_network.get_outgoing_edges(edge.to_node)
            
            for out_edge in outgoing:
                if out_edge.id in edge_to_idx:
                    j = edge_to_idx[out_edge.id]
                    adjacency[i, j] = 1.0
        
        # Add self-connections
        adjacency += np.eye(self.num_edges)
        
        num_connections = np.sum(adjacency > 0)
        print(f"   Graph connections: {num_connections}")
        print(f"   Average degree: {num_connections / self.num_edges:.2f}")
        
        return adjacency
    
    def save_predictions(
        self,
        predictions: Dict,
        output_path: str
    ):
        """
        Save predictions to file
        
        Args:
            predictions: Prediction results
            output_path: Output file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy arrays to lists for JSON
        serializable = {
            'predictions': {
                eid: pred.tolist() for eid, pred in predictions['predictions'].items()
            },
            'horizons_minutes': predictions['horizons_minutes'],
            'confidence': predictions['confidence'],
            'validation': predictions['validation'],
            'timestamp': predictions['timestamp'],
            'input_summary': predictions['input_summary']
        }
        
        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2)
        
        print(f"\n💾 Predictions saved to: {output_path}")
    
    def get_edge_predictions(
        self,
        predictions: Dict,
        edge_id: str
    ) -> Dict:
        """
        Get predictions for a specific edge
        
        Args:
            predictions: Full prediction results
            edge_id: SUMO edge ID
            
        Returns:
            Edge-specific predictions
        """
        if edge_id not in predictions['predictions']:
            raise ValueError(f"Edge {edge_id} not found in predictions")
        
        speeds = predictions['predictions'][edge_id]
        horizons = predictions['horizons_minutes']
        
        return {
            'edge_id': edge_id,
            't+5min': float(speeds[0]),
            't+10min': float(speeds[1]),
            't+15min': float(speeds[2]),
            'horizons': horizons,
            'confidence': predictions['confidence'][edge_id]
        }
    
    def summary_statistics(self, predictions: Dict) -> Dict:
        """
        Calculate summary statistics of predictions
        
        Args:
            predictions: Prediction results
            
        Returns:
            Summary statistics
        """
        all_speeds = np.array([pred for pred in predictions['predictions'].values()])
        
        stats = {
            'num_edges': len(predictions['predictions']),
            'horizons': predictions['horizons_minutes'],
            'per_horizon': []
        }
        
        for h, horizon in enumerate(predictions['horizons_minutes']):
            horizon_speeds = all_speeds[:, h]
            stats['per_horizon'].append({
                'horizon_min': horizon,
                'mean_speed': float(np.mean(horizon_speeds)),
                'std_speed': float(np.std(horizon_speeds)),
                'min_speed': float(np.min(horizon_speeds)),
                'max_speed': float(np.max(horizon_speeds))
            })
        
        return stats


if __name__ == "__main__":
    print("="*70)
    print("TRAFFIC PREDICTION PIPELINE TEST")
    print("="*70)
    
    print("\n⚠️  This test requires:")
    print("  1. Trained GNN model: models/trained/gat_metrla_best.pth")
    print("  2. Fitted scaler: models/trained/scaler_metrla.pkl")
    print("  3. SUMO network: data/sumo/map.net.xml")
    print("  4. Generated scenario: data/generated/")
    
    print("\nOnce these are available, the pipeline can:")
    print("  • Load historical speed data")
    print("  • Run GNN prediction")
    print("  • Map to SUMO edges")
    print("  • Validate results")
    print("  • Save predictions")
