"""
Traffic Prediction Model - Testing & Inference System
Evaluates trained GNN model and provides real-time inference capabilities
"""

import os
import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
import seaborn as sns
from torch.utils.data import DataLoader
from torch_geometric.utils import dense_to_sparse
import joblib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd

# Import your model architecture (must match training)
from torch_geometric.nn import GATConv


# ============================
# MODEL DEFINITION (same as training)
# ============================
class SpatioTemporalGAT(nn.Module):
    """Graph Attention Network + GRU for traffic prediction"""
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


# ============================
# LOAD TRAINED MODEL
# ============================
def load_trained_model(model_path: str, num_nodes: int, device='cpu'):
    """Load trained model from checkpoint"""
    print(f"\n[1] Loading trained model from: {model_path}")
    
    model = SpatioTemporalGAT(
        num_nodes=num_nodes,
        in_dim=1,
        hidden=64,
        heads=4,
        horizon=3,
        dropout=0.1
    ).to(device)
    
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
        print(f"    Model from epoch {checkpoint.get('epoch', 'unknown')}")
        print(f"    Best val loss: {checkpoint.get('val_loss', 'unknown'):.4f}")
    else:
        model.load_state_dict(checkpoint)
    
    model.eval()
    print(f"    ✓ Model loaded successfully!")
    return model


# ============================
# EVALUATION METRICS
# ============================
def calculate_metrics(predictions: np.ndarray, targets: np.ndarray, scaler=None):
    """
    Calculate comprehensive evaluation metrics
    
    Args:
        predictions: (num_samples, horizon, num_nodes)
        targets: (num_samples, horizon, num_nodes)
        scaler: StandardScaler to inverse transform
    """
    # Inverse transform if scaler provided
    if scaler is not None:
        # Reshape for inverse transform
        pred_shape = predictions.shape
        tgt_shape = targets.shape
        
        predictions_orig = []
        targets_orig = []
        
        for h in range(pred_shape[1]):  # For each horizon
            pred_h = scaler.inverse_transform(predictions[:, h, :])
            tgt_h = scaler.inverse_transform(targets[:, h, :])
            predictions_orig.append(pred_h)
            targets_orig.append(tgt_h)
        
        predictions = np.stack(predictions_orig, axis=1)
        targets = np.stack(targets_orig, axis=1)
    
    # Calculate metrics
    mae = np.mean(np.abs(predictions - targets))
    rmse = np.sqrt(np.mean((predictions - targets) ** 2))
    mape = np.mean(np.abs((predictions - targets) / (targets + 1e-5))) * 100
    
    # R² score
    ss_res = np.sum((targets - predictions) ** 2)
    ss_tot = np.sum((targets - np.mean(targets)) ** 2)
    r2 = 1 - (ss_res / ss_tot)
    
    # Per-horizon metrics
    horizon_metrics = []
    for h in range(predictions.shape[1]):
        h_mae = np.mean(np.abs(predictions[:, h, :] - targets[:, h, :]))
        h_rmse = np.sqrt(np.mean((predictions[:, h, :] - targets[:, h, :]) ** 2))
        horizon_metrics.append({'horizon': h+1, 'MAE': h_mae, 'RMSE': h_rmse})
    
    return {
        'MAE': mae,
        'RMSE': rmse,
        'MAPE': mape,
        'R2': r2,
        'horizon_metrics': horizon_metrics
    }


# ============================
# TEST MODEL
# ============================
def test_model(model, test_loader, edge_index, scaler, device='cpu'):
    """
    Evaluate model on test set
    """
    print("\n[2] Evaluating model on test set...")
    
    model.eval()
    all_predictions = []
    all_targets = []
    
    with torch.no_grad():
        for batch_idx, (xb, yb) in enumerate(test_loader):
            xb = xb.to(device)
            yb = yb.to(device)
            
            preds = model(xb, edge_index)
            
            all_predictions.append(preds.cpu().numpy())
            all_targets.append(yb.cpu().numpy())
            
            if (batch_idx + 1) % 20 == 0:
                print(f"    Processed {batch_idx+1}/{len(test_loader)} batches", end='\r')
    
    predictions = np.concatenate(all_predictions, axis=0)
    targets = np.concatenate(all_targets, axis=0)
    
    print(f"\n    Predictions shape: {predictions.shape}")
    print(f"    Targets shape: {targets.shape}")
    
    # Calculate metrics
    print("\n[3] Calculating metrics...")
    metrics = calculate_metrics(predictions, targets, scaler)
    
    print("\n" + "="*70)
    print("TEST SET RESULTS")
    print("="*70)
    print(f"  Overall MAE:  {metrics['MAE']:.4f} km/h")
    print(f"  Overall RMSE: {metrics['RMSE']:.4f} km/h")
    print(f"  Overall MAPE: {metrics['MAPE']:.2f}%")
    print(f"  R² Score:     {metrics['R2']:.4f}")
    print("\n  Per-Horizon Performance:")
    for h_metric in metrics['horizon_metrics']:
        print(f"    Horizon {h_metric['horizon']} (t+{h_metric['horizon']*5}min): "
              f"MAE={h_metric['MAE']:.4f}, RMSE={h_metric['RMSE']:.4f}")
    print("="*70)
    
    return predictions, targets, metrics


# ============================
# VISUALIZATION
# ============================
def visualize_predictions(predictions, targets, scaler, num_samples=5, save_dir='./results'):
    """
    Create comprehensive visualization of predictions
    """
    os.makedirs(save_dir, exist_ok=True)
    
    print("\n[4] Generating visualizations...")
    
    # 1. Sample predictions over time
    fig, axes = plt.subplots(num_samples, 3, figsize=(15, 3*num_samples))
    
    for i in range(num_samples):
        sample_idx = np.random.randint(0, predictions.shape[0])
        
        for h in range(3):  # 3 horizons
            ax = axes[i, h] if num_samples > 1 else axes[h]
            
            pred = predictions[sample_idx, h, :]
            tgt = targets[sample_idx, h, :]
            
            # Inverse transform
            if scaler is not None:
                pred = scaler.inverse_transform(pred.reshape(1, -1)).flatten()
                tgt = scaler.inverse_transform(tgt.reshape(1, -1)).flatten()
            
            ax.plot(tgt[:50], 'b-', label='Actual', linewidth=2, alpha=0.7)
            ax.plot(pred[:50], 'r--', label='Predicted', linewidth=2, alpha=0.7)
            ax.set_xlabel('Node ID')
            ax.set_ylabel('Speed (km/h)')
            ax.set_title(f'Sample {i+1} - Horizon {h+1} (t+{(h+1)*5}min)')
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{save_dir}/predictions_samples.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {save_dir}/predictions_samples.png")
    plt.close()
    
    # 2. Error distribution
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    for h in range(3):
        errors = predictions[:, h, :] - targets[:, h, :]
        
        if scaler is not None:
            # Approximate error in original scale
            errors = errors * scaler.scale_[0]
        
        axes[h].hist(errors.flatten(), bins=50, edgecolor='black', alpha=0.7)
        axes[h].axvline(0, color='r', linestyle='--', linewidth=2)
        axes[h].set_xlabel('Prediction Error (km/h)')
        axes[h].set_ylabel('Frequency')
        axes[h].set_title(f'Error Distribution - Horizon {h+1}')
        axes[h].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{save_dir}/error_distribution.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {save_dir}/error_distribution.png")
    plt.close()
    
    # 3. Scatter plot: Predicted vs Actual
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    for h in range(3):
        pred_h = predictions[:, h, :]  # (samples, nodes)
        tgt_h = targets[:, h, :]
        
        # Inverse transform properly
        if scaler is not None:
            pred_h = scaler.inverse_transform(pred_h)
            tgt_h = scaler.inverse_transform(tgt_h)
        
        pred = pred_h.flatten()
        tgt = tgt_h.flatten()
        
        # Sample for visualization (too many points)
        sample_indices = np.random.choice(len(pred), size=min(5000, len(pred)), replace=False)
        
        axes[h].scatter(tgt[sample_indices], pred[sample_indices], alpha=0.3, s=1)
        axes[h].plot([tgt.min(), tgt.max()], [tgt.min(), tgt.max()], 'r--', linewidth=2)
        axes[h].set_xlabel('Actual Speed (km/h)')
        axes[h].set_ylabel('Predicted Speed (km/h)')
        axes[h].set_title(f'Horizon {h+1} - Predicted vs Actual')
        axes[h].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{save_dir}/scatter_plot.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {save_dir}/scatter_plot.png")
    plt.close()
    
    # 4. Per-node performance heatmap
    node_mae = np.mean(np.abs(predictions - targets), axis=(0, 1))  # Average over samples and horizons
    
    if scaler is not None:
        # Scale the error appropriately
        node_mae = node_mae * scaler.scale_[0] if hasattr(scaler, 'scale_') else node_mae
    
    plt.figure(figsize=(12, 6))
    plt.bar(range(len(node_mae)), node_mae, alpha=0.7, edgecolor='black')
    plt.xlabel('Node ID (Sensor)')
    plt.ylabel('MAE (km/h)')
    plt.title('Per-Node Prediction Error (Average across all horizons)')
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f'{save_dir}/per_node_mae.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {save_dir}/per_node_mae.png")
    plt.close()
    
    print(f"\n    ✓ All visualizations saved to: {save_dir}/")


# ============================
# REAL-TIME INFERENCE
# ============================
class TrafficPredictor:
    """
    Real-time traffic prediction for deployment
    """
    def __init__(self, model_path: str, scaler_path: str, adj_matrix: np.ndarray, 
                 input_window: int = 12, device='cpu'):
        self.device = device
        self.input_window = input_window
        
        # Load scaler
        self.scaler = joblib.load(scaler_path)
        print(f"✓ Loaded scaler from: {scaler_path}")
        
        # Prepare graph
        self.adj = adj_matrix
        edge_index, _ = dense_to_sparse(torch.tensor(adj_matrix, dtype=torch.float32))
        self.edge_index = edge_index.to(device)
        
        # Load model
        self.model = load_trained_model(model_path, adj_matrix.shape[0], device)
        self.num_nodes = adj_matrix.shape[0]
        
        print(f"✓ Predictor initialized for {self.num_nodes} nodes")
    
    def predict(self, recent_speeds: np.ndarray) -> Dict:
        """
        Predict future traffic from recent observations
        
        Args:
            recent_speeds: (input_window, num_nodes) array of recent speed measurements
        
        Returns:
            dict with predictions and metadata
        """
        if recent_speeds.shape != (self.input_window, self.num_nodes):
            raise ValueError(f"Expected shape ({self.input_window}, {self.num_nodes}), "
                           f"got {recent_speeds.shape}")
        
        # Normalize
        normalized = self.scaler.transform(recent_speeds)
        
        # Convert to tensor
        x = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        # Predict
        self.model.eval()
        with torch.no_grad():
            preds = self.model(x, self.edge_index)
        
        # Denormalize
        preds_np = preds.cpu().numpy()[0]  # (horizon, num_nodes)
        
        predictions_denorm = []
        for h in range(preds_np.shape[0]):
            pred_h = self.scaler.inverse_transform(preds_np[h].reshape(1, -1))[0]
            predictions_denorm.append(pred_h)
        
        predictions_denorm = np.array(predictions_denorm)
        
        # Calculate confidence (based on recent variance)
        recent_variance = np.var(recent_speeds, axis=0)
        confidence = 1.0 / (1.0 + recent_variance / 100)  # Simple confidence measure
        
        return {
            'predictions': predictions_denorm,  # (horizon, num_nodes)
            'horizons': [5, 10, 15],  # minutes ahead
            'confidence': confidence,  # per node
            'timestamp': datetime.now().isoformat()
        }
    
    def predict_for_node(self, recent_speeds: np.ndarray, node_id: int) -> Dict:
        """Predict for a specific node/sensor"""
        result = self.predict(recent_speeds)
        
        return {
            'node_id': node_id,
            'current_speed': recent_speeds[-1, node_id],
            'predictions': {
                't+5min': result['predictions'][0, node_id],
                't+10min': result['predictions'][1, node_id],
                't+15min': result['predictions'][2, node_id],
            },
            'confidence': result['confidence'][node_id],
            'timestamp': result['timestamp']
        }


# ============================
# MAIN TESTING SCRIPT
# ============================
def main_test():
    """Run complete testing pipeline"""
    print("="*70)
    print("TRAFFIC PREDICTION MODEL - TESTING & EVALUATION")
    print("="*70)
    
    # Configuration
    DATA_DIR = "./data/metr-la"
    MODEL_PATH = "gat_metrla_best.pth"
    SCALER_PATH = "scaler_metrla.pkl"
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load data (reuse loading function from training)
    print("\n[1] Loading test data...")
    from main1 import load_metr_la, TrafficDataset  # Import from your training script
    
    speeds, adj = load_metr_la(DATA_DIR)
    T, N = speeds.shape
    
    # Split data (same as training)
    val_split = int(T * 0.85)
    test_speeds = speeds[val_split:]
    
    print(f"    Test set: {test_speeds.shape[0]} timesteps")
    
    # Load scaler
    scaler = joblib.load(SCALER_PATH)
    
    # Create test dataset
    test_ds = TrafficDataset(test_speeds, input_window=12, pred_horizon=3, scaler=scaler)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)
    
    print(f"    Test samples: {len(test_ds)}")
    
    # Prepare graph
    edge_index, _ = dense_to_sparse(torch.tensor(adj, dtype=torch.float32))
    edge_index = edge_index.to(DEVICE)
    
    # Load model
    model = load_trained_model(MODEL_PATH, N, DEVICE)
    
    # Test model
    predictions, targets, metrics = test_model(model, test_loader, edge_index, scaler, DEVICE)
    
    # Visualize
    visualize_predictions(predictions, targets, scaler)
    
    # Save results
    print("\n[5] Saving results...")
    results = {
        'metrics': metrics,
        'timestamp': datetime.now().isoformat(),
        'model_path': MODEL_PATH,
        'test_samples': len(test_ds),
        'num_nodes': N
    }
    
    with open('./results/test_results.json', 'w') as f:
        # Convert numpy types to native Python for JSON serialization
        def convert(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj
        
        json.dump(results, f, indent=2, default=convert)
    
    print(f"    ✓ Results saved to: ./results/test_results.json")
    
    # Demo real-time inference
    print("\n[6] Testing real-time inference...")
    predictor = TrafficPredictor(MODEL_PATH, SCALER_PATH, adj, device=DEVICE)
    
    # Use a random sample from test set
    sample_idx = np.random.randint(0, test_speeds.shape[0] - 12)
    recent_data = test_speeds[sample_idx:sample_idx+12]
    
    prediction = predictor.predict(recent_data)
    
    print("\n    Sample Real-Time Prediction:")
    print(f"    Timestamp: {prediction['timestamp']}")
    print(f"    Predicted speeds (first 5 nodes):")
    for i in range(min(5, N)):
        print(f"      Node {i}: ", end='')
        for h, t in enumerate(prediction['horizons']):
            print(f"t+{t}min: {prediction['predictions'][h, i]:.2f} km/h  ", end='')
        print()
    
    print("\n" + "="*70)
    print("✓ Testing complete!")
    print("="*70)


if __name__ == "__main__":
    main_test()