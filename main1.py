import os
import pickle
import h5py
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torch_geometric.nn import GATConv
from torch_geometric.utils import dense_to_sparse
from sklearn.preprocessing import StandardScaler
import joblib

# ============================
# CONFIG
# ============================
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
INPUT_WINDOW = 12      # 12 × 5 min = 1 hour history
PRED_HORIZON = 3       # predict 15 minutes ahead
BATCH_SIZE = 32
EPOCHS = 40
LR = 1e-3

HIDDEN_DIM = 64
NUM_HEADS = 4
DROPOUT = 0.1


# ============================
# DATA LOADER (FIXED)
# ============================
def load_metr_la(data_dir):
    """
    Load METR-LA dataset from H5 and pickle files
    Fixed version for your specific file structure
    """
    h5_path = os.path.join(data_dir, "METR-LA.h5")
    adj_path = os.path.join(data_dir, "adj_METR-LA.pkl")

    # ---- Load H5 file ----
    print(f"Loading HDF5 file: {h5_path}")
    with h5py.File(h5_path, "r") as f:
        # Your file has structure: df/block0_values
        if "df" in f and "block0_values" in f["df"]:
            print("  Found df/block0_values")
            speeds = f["df"]["block0_values"][:]  # Shape: (34272, 207) = (timesteps, nodes)
            speeds = speeds.astype(np.float32)
            print(f"  Loaded speeds: shape={speeds.shape}, dtype={speeds.dtype}")
        else:
            raise KeyError("Cannot find df/block0_values in HDF5 file")

    # ---- Load adjacency matrix ----
    print(f"\nLoading adjacency matrix: {adj_path}")
    with open(adj_path, "rb") as f:
        adj_data = pickle.load(f, encoding='latin1')
    
    # Your file is a list with 3 elements, adjacency is at index [2]
    if isinstance(adj_data, (list, tuple)) and len(adj_data) > 2:
        adj = adj_data[2]  # Get the matrix at index 2
        print(f"  Using adjacency from list index [2]")
    elif isinstance(adj_data, dict):
        adj = adj_data.get("adj_mx", list(adj_data.values())[0])
    elif isinstance(adj_data, np.ndarray):
        adj = adj_data
    else:
        raise TypeError(f"Unexpected adjacency format: {type(adj_data)}")
    
    adj = adj.astype(np.float32)
    print(f"  Loaded adjacency: shape={adj.shape}, dtype={adj.dtype}")
    
    # Verify dimensions match
    num_nodes = speeds.shape[1]
    if adj.shape[0] != num_nodes or adj.shape[1] != num_nodes:
        raise ValueError(f"Adjacency matrix shape {adj.shape} doesn't match number of nodes {num_nodes}")
    
    # Handle zero speeds (missing data)
    print(f"\n  Checking for missing data...")
    zero_count = np.sum(speeds == 0)
    total_count = speeds.size
    print(f"  Zero values: {zero_count}/{total_count} ({100*zero_count/total_count:.2f}%)")
    
    if zero_count > 0:
        print(f"  ⚠️  Found {zero_count} zero speed values (likely missing data)")
        print(f"  Handling: Replace zeros with forward-fill")
        # Simple forward fill for zeros
        for node_idx in range(speeds.shape[1]):
            node_speeds = speeds[:, node_idx]
            zero_mask = (node_speeds == 0)
            if np.any(zero_mask):
                # Forward fill
                last_valid = None
                for t in range(len(node_speeds)):
                    if node_speeds[t] == 0:
                        if last_valid is not None:
                            node_speeds[t] = last_valid
                        else:
                            node_speeds[t] = 50.0  # Default speed if no previous valid
                    else:
                        last_valid = node_speeds[t]
                speeds[:, node_idx] = node_speeds
    
    print(f"\n✓ Data loaded successfully!")
    print(f"  Speeds: {speeds.shape} (timesteps, nodes)")
    print(f"  Adjacency: {adj.shape} (nodes, nodes)")
    print(f"  Time range: {speeds.shape[0]} timesteps (~{speeds.shape[0]*5/60:.1f} hours)")
    
    return speeds, adj
    


# ============================
# DATASET CLASS
# ============================
class TrafficDataset(Dataset):
    def __init__(self, speeds, input_window, pred_horizon, scaler=None):
        """
        Traffic dataset for spatiotemporal prediction
        
        Args:
            speeds: (T, N) array of speed measurements
            input_window: Number of past timesteps to use
            pred_horizon: Number of future timesteps to predict
            scaler: Optional pre-fitted StandardScaler
        """
        self.speeds = speeds
        self.T, self.N = speeds.shape
        self.input_window = input_window
        self.pred_horizon = pred_horizon

        if scaler is None:
            self.scaler = StandardScaler()
            self.scaler.fit(speeds)
        else:
            self.scaler = scaler

        self.norm = self.scaler.transform(speeds)
        
        # Create valid indices
        self.indices = [
            i for i in range(self.T - input_window - pred_horizon)
        ]

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, idx):
        t = self.indices[idx]
        x = self.norm[t:t+self.input_window]        # (W, N)
        y = self.norm[t+self.input_window : t+self.input_window+self.pred_horizon]  # (H, N)
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


# ============================
# MODEL: GAT + GRU
# ============================
class SpatioTemporalGAT(nn.Module):
    """
    Graph Attention Network + GRU for traffic prediction
    """
    def __init__(self, num_nodes, in_dim=1, hidden=64, heads=4, horizon=3, dropout=0.1):
        super().__init__()
        self.N = num_nodes
        self.hidden = hidden
        self.horizon = horizon

        # Graph attention layer
        self.gat = GATConv(in_dim, hidden // heads, heads=heads, dropout=dropout)
        
        # Temporal layer
        self.gru = nn.GRU(hidden, hidden, batch_first=True, dropout=dropout if horizon > 1 else 0)
        
        # Output layer
        self.mlp = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, horizon)
        )

    def forward(self, x, edge_index):
        """
        Args:
            x: (B, W, N) - batch of sequences
            edge_index: (2, E) - graph edges
        Returns:
            pred: (B, H, N) - predictions
        """
        B, W, N = x.shape
        x = x.to(torch.float32)

        # Process each timestep through GAT
        outputs = []
        for t in range(W):
            node_feat = x[:, t, :].unsqueeze(-1)  # (B, N, 1)
            
            # Apply GAT to each sample in batch
            batch_outputs = []
            for b in range(B):
                nf = node_feat[b]  # (N, 1)
                nf = self.gat(nf, edge_index)  # (N, H)
                batch_outputs.append(nf.unsqueeze(0))
            
            outputs.append(torch.cat(batch_outputs, dim=0))  # (B, N, H)

        h = torch.stack(outputs, dim=1)  # (B, W, N, H)
        B, W, N, H = h.shape

        # Reshape for GRU: process each node's time series
        h = h.permute(0, 2, 1, 3).reshape(B*N, W, H)  # (B*N, W, H)
        
        # GRU temporal processing
        out, _ = self.gru(h)  # (B*N, W, H)
        out = out[:, -1, :]  # Take last timestep (B*N, H)
        
        # Predict future
        pred = self.mlp(out)  # (B*N, horizon)
        pred = pred.reshape(B, N, self.horizon).permute(0, 2, 1)  # (B, H, N)
        
        return pred


# ============================
# TRAINING PIPELINE
# ============================
def train(data_dir):
    """
    Main training function
    """
    print("="*70)
    print("METR-LA Traffic Prediction - GAT+GRU Training")
    print("="*70)
    
    # Load data
    print("\n[1] Loading METR-LA dataset...")
    try:
        speeds, adj = load_metr_la(data_dir)
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        print("\nTroubleshooting steps:")
        print("1. Verify files exist:")
        print(f"   - {os.path.join(data_dir, 'METR-LA.h5')}")
        print(f"   - {os.path.join(data_dir, 'adj_METR-LA.pkl')}")
        print("2. Check HDF5 file structure:")
        print("   Run: h5dump -n METR-LA.h5")
        print("3. Verify you have the correct METR-LA dataset")
        raise
    
    T, N = speeds.shape
    print(f"\n[2] Dataset summary:")
    print(f"    Total timesteps: {T}")
    print(f"    Number of sensors: {N}")
    print(f"    Total hours: ~{T*5/60:.1f}")
    
    # Split data
    train_split = int(T * 0.7)
    val_split = int(T * 0.85)
    
    train_speeds = speeds[:train_split]
    val_speeds = speeds[train_split:val_split]
    test_speeds = speeds[val_split:]
    
    print(f"\n[3] Data split:")
    print(f"    Train: {train_speeds.shape[0]} samples ({train_speeds.shape[0]*5/60:.1f} hours)")
    print(f"    Val:   {val_speeds.shape[0]} samples ({val_speeds.shape[0]*5/60:.1f} hours)")
    print(f"    Test:  {test_speeds.shape[0]} samples ({test_speeds.shape[0]*5/60:.1f} hours)")
    
    # Create scaler
    scaler = StandardScaler()
    scaler.fit(train_speeds)
    joblib.dump(scaler, "scaler_metrla.pkl")
    print(f"    ✓ Scaler saved to scaler_metrla.pkl")
    
    # Create datasets
    train_ds = TrafficDataset(train_speeds, INPUT_WINDOW, PRED_HORIZON, scaler)
    val_ds = TrafficDataset(val_speeds, INPUT_WINDOW, PRED_HORIZON, scaler)
    
    print(f"\n[4] Created datasets:")
    print(f"    Train samples: {len(train_ds)}")
    print(f"    Val samples:   {len(val_ds)}")
    
    # Create dataloaders
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_dl = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    # Prepare graph
    print(f"\n[5] Preparing graph structure...")
    edge_index, edge_attr = dense_to_sparse(torch.tensor(adj, dtype=torch.float32))
    edge_index = edge_index.to(DEVICE)
    print(f"    Edges: {edge_index.shape[1]}")
    print(f"    Average degree: {edge_index.shape[1] / N:.2f}")
    
    # Create model
    print(f"\n[6] Initializing model...")
    model = SpatioTemporalGAT(
        num_nodes=N,
        in_dim=1,
        hidden=HIDDEN_DIM,
        heads=NUM_HEADS,
        horizon=PRED_HORIZON,
        dropout=DROPOUT
    ).to(DEVICE)
    
    num_params = sum(p.numel() for p in model.parameters())
    print(f"    Parameters: {num_params:,}")
    print(f"    Device: {DEVICE}")
    
    # Training setup
    opt = optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(opt, mode='min', factor=0.5, patience=5)
    loss_fn = nn.MSELoss()
    
    print(f"\n[7] Starting training...")
    print(f"    Epochs: {EPOCHS}")
    print(f"    Batch size: {BATCH_SIZE}")
    print(f"    Learning rate: {LR}")
    print("="*70)
    
    best_val_loss = float('inf')
    patience_counter = 0
    patience = 10
    
    for epoch in range(1, EPOCHS+1):
        # Training
        model.train()
        train_losses = []
        
        for batch_idx, (xb, yb) in enumerate(train_dl):
            xb = xb.to(DEVICE)
            yb = yb.to(DEVICE)
            
            opt.zero_grad()
            preds = model(xb, edge_index)
            loss = loss_fn(preds, yb)
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            
            opt.step()
            train_losses.append(loss.item())
            
            # Progress bar
            if (batch_idx + 1) % 20 == 0:
                print(f"  Epoch {epoch}/{EPOCHS} | Batch {batch_idx+1}/{len(train_dl)} | Loss: {loss.item():.4f}", end='\r')
        
        # Validation
        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                preds = model(xb, edge_index)
                val_losses.append(loss_fn(preds, yb).item())
        
        train_loss = np.mean(train_losses)
        val_loss = np.mean(val_losses)
        
        # Update learning rate
        scheduler.step(val_loss)
        current_lr = opt.param_groups[0]['lr']
        
        print(f"Epoch {epoch:3d}/{EPOCHS} | Train: {train_loss:.4f} | Val: {val_loss:.4f} | LR: {current_lr:.6f}", end='')
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': opt.state_dict(),
                'val_loss': val_loss,
            }, "gat_metrla_best.pth")
            print(" ✓ [BEST]")
        else:
            patience_counter += 1
            print()
            
            if patience_counter >= patience:
                print(f"\n⚠️  Early stopping triggered after {epoch} epochs")
                break
    
    print("\n" + "="*70)
    print(f"✓ Training complete!")
    print(f"  Best validation loss: {best_val_loss:.4f}")
    print(f"  Model saved to: gat_metrla_best.pth")
    print("="*70)
    
    return "gat_metrla_best.pth"


# ============================
# MAIN
# ============================
if __name__ == "__main__":
    import sys
    
    # Check if data directory provided
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        data_dir = "./data/metr-la"
    
    print(f"Using data directory: {data_dir}")
    
    if not os.path.exists(data_dir):
        print(f"❌ Error: Directory '{data_dir}' does not exist")
        print(f"Please create it and place the following files:")
        print(f"  - METR-LA.h5")
        print(f"  - adj_METR-LA.pkl")
        sys.exit(1)
    
    try:
        model_file = train(data_dir)
        print("\n🎉 Training complete!")
        print(f"Best model: {model_file}")
    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)