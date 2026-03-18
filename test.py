import os
import sys
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json

from train import load_metr_la, TrafficDataset, SpatioTemporalGAT
from torch.utils.data import DataLoader
from torch_geometric.utils import dense_to_sparse
import joblib


def test_model_comprehensive():
    """
    Complete testing pipeline with all metrics and visualizations
    """
    print("="*80)
    print(" "*20 + "MODEL TESTING & EVALUATION")
    print("="*80 + "\n")
    
    DATA_DIR = "./data/metr-la"
    MODEL_PATH = "gat_metrla_best.pth"
    SCALER_PATH = "scaler_metrla.pkl"
    OUTPUT_DIR = "./test_results"
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("📂 [1/7] Loading test data...")
    speeds, adj = load_metr_la(DATA_DIR)
    T, N = speeds.shape
    
    val_split = int(T * 0.85)
    test_speeds = speeds[val_split:]
    
    print(f"    Test timesteps: {test_speeds.shape[0]} ({test_speeds.shape[0]*5/60:.1f} hours)")
    print(f"    Number of sensors: {N}")
    
    scaler = joblib.load(SCALER_PATH)
    
    test_ds = TrafficDataset(test_speeds, input_window=12, pred_horizon=3, scaler=scaler)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False, num_workers=0)
    
    print(f"    Test samples: {len(test_ds)}\n")
    
    # ===== STEP 2: LOAD MODEL =====
    print("🧠 [2/7] Loading trained model...")
    
    # Suppress GRU dropout warning (dropout only works with num_layers > 1)
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, message='.*dropout option adds dropout.*')
    
    model = SpatioTemporalGAT(num_nodes=N, in_dim=1, hidden=64, heads=4, horizon=3, dropout=0.1).to(DEVICE)
    
    checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
        train_epoch = checkpoint.get('epoch', 'unknown')
        train_loss = checkpoint.get('val_loss', 'unknown')
        print(f"    Model from epoch: {train_epoch}")
        print(f"    Training val loss: {train_loss}\n")
    else:
        model.load_state_dict(checkpoint)
    
    model.eval()
    
    # Prepare graph
    edge_index, _ = dense_to_sparse(torch.tensor(adj, dtype=torch.float32))
    edge_index = edge_index.to(DEVICE)
    
    # ===== STEP 3: RUN PREDICTIONS =====
    print("🔮 [3/7] Running predictions on test set...")
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for batch_idx, (xb, yb) in enumerate(test_loader):
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            preds = model(xb, edge_index)
            
            all_preds.append(preds.cpu().numpy())
            all_targets.append(yb.cpu().numpy())
            
            if (batch_idx + 1) % 50 == 0:
                print(f"    Progress: {batch_idx+1}/{len(test_loader)} batches", end='\r')
    
    predictions = np.concatenate(all_preds, axis=0)
    targets = np.concatenate(all_targets, axis=0)
    
    print(f"\n    Predictions shape: {predictions.shape}")
    print(f"    (samples={predictions.shape[0]}, horizons={predictions.shape[1]}, nodes={predictions.shape[2]})\n")
    
    # ===== STEP 4: CALCULATE METRICS =====
    print("📊 [4/7] Calculating performance metrics...")
    
    # Denormalize
    def denormalize(data, scaler):
        """Denormalize predictions/targets"""
        result = []
        for h in range(data.shape[1]):
            denorm = scaler.inverse_transform(data[:, h, :])
            result.append(denorm)
        return np.stack(result, axis=1)
    
    preds_orig = denormalize(predictions, scaler)
    targets_orig = denormalize(targets, scaler)
    
    # Calculate metrics
    mae = np.mean(np.abs(preds_orig - targets_orig))
    rmse = np.sqrt(np.mean((preds_orig - targets_orig) ** 2))
    mape = np.mean(np.abs((preds_orig - targets_orig) / (targets_orig + 1e-5))) * 100
    
    # Per-horizon metrics
    horizon_metrics = []
    for h in range(3):
        h_mae = np.mean(np.abs(preds_orig[:, h, :] - targets_orig[:, h, :]))
        h_rmse = np.sqrt(np.mean((preds_orig[:, h, :] - targets_orig[:, h, :]) ** 2))
        h_mape = np.mean(np.abs((preds_orig[:, h, :] - targets_orig[:, h, :]) / (targets_orig[:, h, :] + 1e-5))) * 100
        horizon_metrics.append({
            'horizon': h + 1,
            'time_ahead': f'{(h+1)*5} min',
            'MAE': float(h_mae),
            'RMSE': float(h_rmse),
            'MAPE': float(h_mape)
        })
    
    # Print results
    print("\n" + "="*80)
    print(" "*25 + "TEST SET RESULTS")
    print("="*80)
    print(f"  Overall Metrics:")
    print(f"    MAE:  {mae:.4f} km/h")
    print(f"    RMSE: {rmse:.4f} km/h")
    print(f"    MAPE: {mape:.2f}%")
    print(f"\n  Per-Horizon Performance:")
    print("  " + "-"*76)
    print(f"  {'Horizon':<12} {'Time Ahead':<15} {'MAE':<15} {'RMSE':<15} {'MAPE':<15}")
    print("  " + "-"*76)
    for h_metric in horizon_metrics:
        print(f"  {h_metric['horizon']:<12} {h_metric['time_ahead']:<15} "
              f"{h_metric['MAE']:<15.4f} {h_metric['RMSE']:<15.4f} {h_metric['MAPE']:<15.2f}%")
    print("="*80 + "\n")
    
    # ===== STEP 5: VISUALIZATIONS =====
    print("📈 [5/7] Creating visualizations...")
    
    # 1. Time series comparison
    fig, axes = plt.subplots(3, 1, figsize=(14, 10))
    sample_node = 50
    num_samples = 100
    
    for h in range(3):
        axes[h].plot(targets_orig[:num_samples, h, sample_node], 'b-', 
                    label='Actual', linewidth=2, alpha=0.7)
        axes[h].plot(preds_orig[:num_samples, h, sample_node], 'r--', 
                    label='Predicted', linewidth=2, alpha=0.7)
        axes[h].set_xlabel('Time Step')
        axes[h].set_ylabel('Speed (km/h)')
        axes[h].set_title(f'Horizon {h+1} (t+{(h+1)*5}min) - Node {sample_node}')
        axes[h].legend()
        axes[h].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/timeseries_comparison.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {OUTPUT_DIR}/timeseries_comparison.png")
    plt.close()
    
    # 2. Scatter plots
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    for h in range(3):
        sample_size = min(10000, predictions.shape[0] * N)
        indices = np.random.choice(predictions.shape[0] * N, sample_size, replace=False)
        
        pred_flat = preds_orig[:, h, :].flatten()[indices]
        tgt_flat = targets_orig[:, h, :].flatten()[indices]
        
        axes[h].scatter(tgt_flat, pred_flat, alpha=0.2, s=1)
        axes[h].plot([tgt_flat.min(), tgt_flat.max()], 
                    [tgt_flat.min(), tgt_flat.max()], 'r--', linewidth=2)
        axes[h].set_xlabel('Actual Speed (km/h)')
        axes[h].set_ylabel('Predicted Speed (km/h)')
        axes[h].set_title(f'Horizon {h+1} (t+{(h+1)*5}min)')
        axes[h].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/scatter_plots.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {OUTPUT_DIR}/scatter_plots.png")
    plt.close()
    
    # 3. Error distribution
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    
    for h in range(3):
        errors = preds_orig[:, h, :] - targets_orig[:, h, :]
        
        axes[h].hist(errors.flatten(), bins=50, edgecolor='black', alpha=0.7)
        axes[h].axvline(0, color='r', linestyle='--', linewidth=2)
        axes[h].set_xlabel('Prediction Error (km/h)')
        axes[h].set_ylabel('Frequency')
        axes[h].set_title(f'Error Distribution - Horizon {h+1}')
        axes[h].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/error_distribution.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {OUTPUT_DIR}/error_distribution.png")
    plt.close()
    
    # 4. Per-node performance
    node_mae = np.mean(np.abs(preds_orig - targets_orig), axis=(0, 1))
    
    plt.figure(figsize=(14, 5))
    plt.bar(range(len(node_mae)), node_mae, alpha=0.7, edgecolor='black')
    plt.xlabel('Node ID (Sensor)')
    plt.ylabel('MAE (km/h)')
    plt.title('Per-Sensor Prediction Error (Average across all horizons)')
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/per_node_mae.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {OUTPUT_DIR}/per_node_mae.png")
    plt.close()
    # ------------------------------------------------------------------------------------
    # 5. ERROR DISTRIBUTION (Poster Style)
    # ------------------------------------------------------------------------------------
    print("    ✓ Creating poster-style error distribution graphs...")

    # Custom Poster Theme
    plt.style.use('default')
    plt.rcParams.update({
        "axes.facecolor": "#0f1116",
        "figure.facecolor": "#0f1116",
        "axes.edgecolor": "#ffffff",
        "axes.labelcolor": "#ffffff",
        "xtick.color": "#ffffff",
        "ytick.color": "#ffffff",
        "text.color": "#ffffff",
        "font.size": 12,
        "grid.color": "#444444",
        "grid.linestyle": "--",
    })

    # Color palette (strong, vibrant)
    POSTER_COLORS = ["#4CC9F0", "#F72585", "#7209B7"]   # horizon 1,2,3

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.patch.set_facecolor("#0f1116")

    for h in range(3):
        errors = preds_orig[:, h, :] - targets_orig[:, h, :]
        
        ax = axes[h]
        ax.set_facecolor("#0f1116")

        bins = np.linspace(errors.min(), errors.max(), 35)
        ax.hist(errors.flatten(), bins=bins, 
                edgecolor="#ffffff", 
                alpha=0.8,
                color=POSTER_COLORS[h])

        ax.axvline(0, color="#ffffff", linestyle='--', linewidth=1.5)

        ax.set_title(f"Error Distribution – Horizon {h+1}", fontsize=14, weight="bold")
        ax.set_xlabel("Prediction Error (km/h)")
        ax.set_ylabel("Frequency")
        ax.grid(True, axis="y")

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/error_distribution_poster.png", dpi=200, bbox_inches="tight")
    plt.close()

    # ------------------------------------------------------------------------------------
    # 6. Combined Average Error Distribution
    # ------------------------------------------------------------------------------------
    print("    ✓ Creating combined average error distribution graph...")

    avg_errors = np.mean(preds_orig - targets_orig, axis=1)  # average across horizons
    avg_errors_flat = avg_errors.flatten()

    plt.figure(figsize=(10, 5))
    plt.gca().set_facecolor("#0f1116")

    bins = np.linspace(avg_errors_flat.min(), avg_errors_flat.max(), 40)

    plt.hist(avg_errors_flat, 
            bins=bins, 
            color="#4CC9F0", 
            edgecolor="#ffffff",
            alpha=0.85)

    plt.axvline(0, color="#ffffff", linestyle='--', linewidth=1.5)

    plt.title("Combined Average Error Distribution (All Horizons)",
            fontsize=16, weight="bold", color="white")
    plt.xlabel("Average Prediction Error (km/h)")
    plt.ylabel("Frequency")
    plt.grid(True, axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/error_distribution_avg.png", dpi=200, bbox_inches="tight")
    plt.close()

    # 5. Metrics comparison chart
    fig, ax = plt.subplots(figsize=(10, 6))
    horizons = [1, 2, 3]
    mae_values = [h['MAE'] for h in horizon_metrics]
    rmse_values = [h['RMSE'] for h in horizon_metrics]
    
    x = np.arange(len(horizons))
    width = 0.35
    
    ax.bar(x - width/2, mae_values, width, label='MAE', alpha=0.8)
    ax.bar(x + width/2, rmse_values, width, label='RMSE', alpha=0.8)
    
    ax.set_xlabel('Prediction Horizon')
    ax.set_ylabel('Error (km/h)')
    ax.set_title('Prediction Error by Horizon')
    ax.set_xticks(x)
    ax.set_xticklabels([f'H{h}\n(t+{h*5}min)' for h in horizons])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/metrics_comparison.png', dpi=150, bbox_inches='tight')
    print(f"    ✓ Saved: {OUTPUT_DIR}/metrics_comparison.png\n")
    plt.close()
    
    # ===== STEP 6: SAVE RESULTS =====
    print("💾 [6/7] Saving results to JSON...")
    
    results = {
        'test_date': datetime.now().isoformat(),
        'model_path': MODEL_PATH,
        'test_samples': int(len(test_ds)),
        'num_nodes': int(N),
        'overall_metrics': {
            'MAE': float(mae),
            'RMSE': float(rmse),
            'MAPE': float(mape)
        },
        'per_horizon_metrics': horizon_metrics,
        'per_node_mae': {
            'mean': float(np.mean(node_mae)),
            'std': float(np.std(node_mae)),
            'min': float(np.min(node_mae)),
            'max': float(np.max(node_mae))
        }
    }
    
    with open(f'{OUTPUT_DIR}/test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"    ✓ Saved: {OUTPUT_DIR}/test_results.json\n")
    
    # ===== STEP 7: GENERATE REPORT =====
    print("📄 [7/7] Generating test report...")
    
    report = f"""
{'='*80}
TRAFFIC PREDICTION MODEL - TEST REPORT
{'='*80}

Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Model: {MODEL_PATH}
Dataset: METR-LA

TEST SET INFORMATION
--------------------
Total Timesteps: {test_speeds.shape[0]} ({test_speeds.shape[0]*5/60:.1f} hours)
Number of Sensors: {N}
Test Samples: {len(test_ds)}

OVERALL PERFORMANCE
-------------------
MAE:  {mae:.4f} km/h
RMSE: {rmse:.4f} km/h
MAPE: {mape:.2f}%

PER-HORIZON PERFORMANCE
-----------------------
"""
    
    for h_metric in horizon_metrics:
        report += f"\nHorizon {h_metric['horizon']} (t+{h_metric['time_ahead']}):\n"
        report += f"  MAE:  {h_metric['MAE']:.4f} km/h\n"
        report += f"  RMSE: {h_metric['RMSE']:.4f} km/h\n"
        report += f"  MAPE: {h_metric['MAPE']:.2f}%\n"
    
    report += f"""
PER-NODE STATISTICS
-------------------
Mean MAE across all nodes: {np.mean(node_mae):.4f} km/h
Std Dev: {np.std(node_mae):.4f} km/h
Min MAE: {np.min(node_mae):.4f} km/h (Node {np.argmin(node_mae)})
Max MAE: {np.max(node_mae):.4f} km/h (Node {np.argmax(node_mae)})

GENERATED FILES
---------------
1. timeseries_comparison.png - Time series predictions vs actual
2. scatter_plots.png - Predicted vs actual scatter plots
3. error_distribution.png - Error histograms by horizon
4. per_node_mae.png - Error by sensor/node
5. metrics_comparison.png - MAE/RMSE comparison chart
6. test_results.json - Complete results in JSON format
7. test_report.txt - This report

{'='*80}
"""
    
    with open(f'{OUTPUT_DIR}/test_report.txt', 'w') as f:
        f.write(report)
    
    print(report)
    print(f"    ✓ Saved: {OUTPUT_DIR}/test_report.txt")
    
    print("\n" + "="*80)
    print("✅ TESTING COMPLETE!")
    print("="*80)
    print(f"\nAll results saved to: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    for filename in os.listdir(OUTPUT_DIR):
        print(f"  - {filename}")
    print()


if __name__ == "__main__":
    try:
        test_model_comprehensive()
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)