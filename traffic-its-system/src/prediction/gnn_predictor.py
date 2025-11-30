"""
GNN Traffic Speed Predictor
Wraps the trained GAT+GRU model for traffic speed prediction
"""

import torch
import torch.nn as nn
import numpy as np
from torch_geometric.nn import GATConv
from torch_geometric.utils import dense_to_sparse
import joblib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import warnings

warnings.filterwarnings('ignore', category=UserWarning, message='.*dropout option adds dropout.*')


class SpatioTemporalGAT(nn.Module):
    """
    Graph Attention Network + GRU for traffic prediction
    (Same architecture as training)
    """
    def __init__(self, num_nodes, in_dim=1, hidden=64, heads=4, horizon=3, dropout=0.1):
        super().__init__()
        self.N = num_nodes
        self.hidden = hidden
        self.horizon = horizon

        self.gat = GATConv(in_dim, hidden // heads, heads=heads, dropout=dropout)
        self.gru = nn.GRU(hidden, hidden, batch_first=True, dropout=dropout if horizon > 1 else 0)
        
        self.mlp = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, horizon)
        )

    def forward(self, x, edge_index):
        B, W, N = x.shape
        x = x.to(torch.float32)

        outputs = []
        for t in range(W):
            node_feat = x[:, t, :].unsqueeze(-1)
            batch_outputs = []
            for b in range(B):
                nf = node_feat[b]
                nf = self.gat(nf, edge_index)
                batch_outputs.append(nf.unsqueeze(0))
            outputs.append(torch.cat(batch_outputs, dim=0))

        h = torch.stack(outputs, dim=1)
        B, W, N, H = h.shape
        h = h.permute(0, 2, 1, 3).reshape(B*N, W, H)
        out, _ = self.gru(h)
        out = out[:, -1, :]
        pred = self.mlp(out)
        pred = pred.reshape(B, N, self.horizon).permute(0, 2, 1)
        return pred


class GNNTrafficPredictor:
    """
    High-level interface for traffic speed prediction
    """
    
    def __init__(
        self,
        model_path: str,
        scaler_path: str,
        num_nodes: int,
        device: str = 'auto'
    ):
        """
        Initialize GNN predictor
        
        Args:
            model_path: Path to trained model (.pth file)
            scaler_path: Path to fitted scaler (.pkl file)
            num_nodes: Number of nodes in the graph
            device: 'auto', 'cpu', or 'cuda'
        """
        self.num_nodes = num_nodes
        
        # Determine device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        print(f"🧠 Initializing GNN Predictor...")
        print(f"   Device: {self.device}")
        print(f"   Nodes: {num_nodes}")
        
        # Load scaler
        self.scaler = joblib.load(scaler_path)
        print(f"   ✓ Loaded scaler from: {scaler_path}")
        
        # Initialize model
        self.model = SpatioTemporalGAT(
            num_nodes=num_nodes,
            in_dim=1,
            hidden=64,
            heads=4,
            horizon=3,
            dropout=0.1
        ).to(self.device)
        
        # Load trained weights
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        
        if 'model_state_dict' in checkpoint:
            self.model.load_state_dict(checkpoint['model_state_dict'])
            epoch = checkpoint.get('epoch', 'unknown')
            val_loss = checkpoint.get('val_loss', 'unknown')
            print(f"   ✓ Loaded model from epoch {epoch} (val_loss: {val_loss})")
        else:
            self.model.load_state_dict(checkpoint)
            print(f"   ✓ Loaded model weights")
        
        self.model.eval()
        
        # Model config
        self.input_window = 12  # Last 12 timesteps (1 hour)
        self.prediction_horizon = 3  # Predict 3 steps ahead (15 minutes)
        self.timestep_minutes = 5
        
        print(f"   ✓ Model ready for prediction")
        print(f"     • Input window: {self.input_window} steps ({self.input_window * self.timestep_minutes} min)")
        print(f"     • Prediction horizon: {self.prediction_horizon} steps ({self.prediction_horizon * self.timestep_minutes} min)")
    
    def predict(
        self,
        speed_history: np.ndarray,
        edge_index: torch.Tensor = None,
        adjacency_matrix: np.ndarray = None
    ) -> Dict:
        """
        Predict future speeds from historical data
        
        Args:
            speed_history: Historical speeds, shape (timesteps, num_nodes) or (num_nodes, timesteps)
            edge_index: Graph edge indices (optional if adjacency_matrix provided)
            adjacency_matrix: Adjacency matrix (optional if edge_index provided)
            
        Returns:
            Dictionary with predictions and metadata
        """
        # Validate input shape
        if speed_history.shape[0] == self.num_nodes and speed_history.shape[1] == self.input_window:
            # Shape is (num_nodes, timesteps) - transpose it
            speed_history = speed_history.T
        
        if speed_history.shape[0] != self.input_window or speed_history.shape[1] != self.num_nodes:
            raise ValueError(
                f"Expected shape ({self.input_window}, {self.num_nodes}), "
                f"got {speed_history.shape}"
            )
        
        # Create edge_index if not provided
        if edge_index is None:
            if adjacency_matrix is None:
                # Create fully connected graph as fallback
                print("   ⚠️  No graph structure provided, using fully connected graph")
                adjacency_matrix = np.ones((self.num_nodes, self.num_nodes)) - np.eye(self.num_nodes)
            
            edge_index, _ = dense_to_sparse(torch.tensor(adjacency_matrix, dtype=torch.float32))
        
        edge_index = edge_index.to(self.device)
        
        # Handle scaler dimension mismatch
        # The scaler was trained on 207 nodes but we have different size
        if hasattr(self.scaler, 'n_features_in_') and self.scaler.n_features_in_ != self.num_nodes:
            print(f"   ⚠️  Scaler size mismatch: scaler expects {self.scaler.n_features_in_} features, got {self.num_nodes}")
            print(f"   Creating new scaler fitted to current data...")
            from sklearn.preprocessing import StandardScaler
            # Fit new scaler on current data
            self.scaler = StandardScaler()
            self.scaler.fit(speed_history)
        
        # Normalize input
        speed_normalized = self.scaler.transform(speed_history)
        
        # Convert to tensor
        x = torch.tensor(speed_normalized, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        # Predict
        self.model.eval()
        with torch.no_grad():
            predictions = self.model(x, edge_index)
        
        # Denormalize predictions
        predictions_np = predictions.cpu().numpy()[0]  # Shape: (horizon, num_nodes)
        
        predictions_denorm = []
        for h in range(predictions_np.shape[0]):
            pred_h = self.scaler.inverse_transform(predictions_np[h].reshape(1, -1))[0]
            predictions_denorm.append(pred_h)
        
        predictions_denorm = np.array(predictions_denorm)  # Shape: (horizon, num_nodes)
        
        # Calculate confidence based on recent variance
        recent_variance = np.var(speed_history, axis=0)
        confidence = 1.0 / (1.0 + recent_variance / 100)
        
        # Prepare results
        result = {
            'predictions': predictions_denorm,  # (3, num_nodes)
            'horizons_minutes': [5, 10, 15],
            'timestep_minutes': self.timestep_minutes,
            'confidence': confidence,  # (num_nodes,)
            'input_shape': speed_history.shape,
            'output_shape': predictions_denorm.shape,
            'num_nodes': self.num_nodes
        }
        
        return result
    
    def predict_batch(
        self,
        speed_histories: List[np.ndarray],
        edge_index: torch.Tensor = None,
        adjacency_matrix: np.ndarray = None
    ) -> List[Dict]:
        """
        Predict for multiple historical windows
        
        Args:
            speed_histories: List of historical speed arrays
            edge_index: Graph edge indices
            adjacency_matrix: Adjacency matrix
            
        Returns:
            List of prediction dictionaries
        """
        results = []
        for speed_history in speed_histories:
            result = self.predict(speed_history, edge_index, adjacency_matrix)
            results.append(result)
        return results
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            'num_nodes': self.num_nodes,
            'input_window': self.input_window,
            'prediction_horizon': self.prediction_horizon,
            'timestep_minutes': self.timestep_minutes,
            'device': str(self.device),
            'num_parameters': sum(p.numel() for p in self.model.parameters())
        }


if __name__ == "__main__":
    # Test the predictor
    import sys
    
    print("="*70)
    print("GNN PREDICTOR TEST")
    print("="*70)
    
    # Create dummy data for testing
    num_nodes = 95  # Your network size
    input_window = 12
    
    print(f"\nCreating test data...")
    print(f"  Nodes: {num_nodes}")
    print(f"  Input window: {input_window} timesteps")
    
    # Generate random speed history
    speed_history = np.random.uniform(20, 60, size=(input_window, num_nodes))
    print(f"  Speed history shape: {speed_history.shape}")
    
    # Create simple adjacency (fully connected for testing)
    adjacency = np.ones((num_nodes, num_nodes)) - np.eye(num_nodes)
    print(f"  Adjacency shape: {adjacency.shape}")
    
    # Note: In actual use, you need to provide the trained model files
    print("\n⚠️  Note: This test requires trained model files:")
    print("  • models/trained/gat_metrla_best.pth")
    print("  • models/trained/scaler_metrla.pkl")
    print("\nPlease copy these files before running predictions.")
