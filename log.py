print("""METR-LA Traffic Prediction GAT GRU Training
======================================================================

[1] Loading METR-LA dataset...
Loading HDF5 file: ./data/metr-la\METR-LA.h5
  Found df/block0_values
  Loaded speeds: shape=(34272, 207), dtype=float32

Loading adjacency matrix: ./data/metr-la\\adj_METR-LA.pkl
  Using adjacency from list index [2]
  Loaded adjacency: shape=(207, 207), dtype=float32

  Checking for missing data...
  Zero values: 575302/7094304 (8.11%)
  ⚠️  Found 575302 zero speed values (likely missing data)
  Handling: Replace zeros with forward-fill

✓ Data loaded successfully!
  Speeds: (34272, 207) (timesteps, nodes)
  Adjacency: (207, 207) (nodes, nodes)
  Time range: 34272 timesteps (~2856.0 hours)

[2] Dataset summary:
    Total timesteps: 34272
    Number of sensors: 207
    Total hours: ~2856.0

[3] Data split:
    Train: 23990 samples (1999.2 hours)
    Val:   5141 samples (428.4 hours)
    Test:  5141 samples (428.4 hours)
    ✓ Scaler saved to scaler_metrla.pkl

[4] Created datasets:
    Train samples: 23975
    Val samples:   5126

[5] Preparing graph structure...
    Edges: 1722
    Average degree: 8.32

[6] Initializing model...
C:\\Users\\Mohamed\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\torch\\nn\\modules\\rnn.py:123: UserWarning: dropout option adds dropout after all but last recurrent layer, so non-zero dropout expects num_layers greater than 1, but got drC:\\Users\\Mohamed\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\torch\\nn\\modules\\rnn.py:123: UserWarning: dropout option adds dropout after all but last recurrent layer, so non-zero dropout expects num_layers greater than 1, but got drt option adds dropout after all but last recurrent layer, so non-zero dropout expects num_layers greater than 1, but got dropout=0.1 and num_layers=1
  warnings.warn(
    Parameters: 29,571
    Device: cpu

  warnings.warn(
    Parameters: 29,571
    Device: cpu


[7] Starting training...
    Epochs: 40
    Batch size: 32
    Learning rate: 0.001
======================================================================
Epoch   1/40 | Train: 0.4285 | Val: 0.3358 | LR: 0.001000 ✓ [BEST]
Epoch   2/40 | Train: 0.3311 | Val: 0.3185 | LR: 0.001000 ✓ [BEST]
Epoch   3/40 | Train: 0.3215 | Val: 0.3107 | LR: 0.001000 ✓ [BEST]
Epoch   4/40 | Train: 0.3170 | Val: 0.3030 | LR: 0.001000 ✓ [BEST]
Epoch   5/40 | Train: 0.3142 | Val: 0.3046 | LR: 0.001000
Epoch   6/40 | Train: 0.3120 | Val: 0.3013 | LR: 0.001000 ✓ [BEST]
Epoch   7/40 | Train: 0.3111 | Val: 0.2960 | LR: 0.001000 ✓ [BEST]
Epoch   8/40 | Train: 0.3093 | Val: 0.2982 | LR: 0.001000
Epoch   9/40 | Train: 0.3083 | Val: 0.2971 | LR: 0.001000
Epoch  10/40 | Train: 0.3075 | Val: 0.2948 | LR: 0.001000 ✓ [BEST]
Epoch  11/40 | Train: 0.3066 | Val: 0.2951 | LR: 0.001000
Epoch  12/40 | Train: 0.3063 | Val: 0.2938 | LR: 0.001000 ✓ [BEST]
Epoch  13/40 | Train: 0.3058 | Val: 0.2940 | LR: 0.001000
Epoch  14/40 | Train: 0.3057 | Val: 0.2917 | LR: 0.001000 ✓ [BEST]
Epoch  15/40 | Train: 0.3052 | Val: 0.2957 | LR: 0.001000
Epoch  16/40 | Train: 0.3043 | Val: 0.2939 | LR: 0.001000
Epoch  17/40 | Train: 0.3037 | Val: 0.3003 | LR: 0.001000
Epoch  18/40 | Train: 0.3037 | Val: 0.2969 | LR: 0.001000
Epoch  19/40 | Train: 0.3039 | Val: 0.2949 | LR: 0.001000
Epoch  20/40 | Train: 0.3032 | Val: 0.2926 | LR: 0.000500
Epoch  21/40 | Train: 0.3014 | Val: 0.2923 | LR: 0.000500
Epoch  22/40 | Train: 0.3009 | Val: 0.2900 | LR: 0.000500 ✓ [BEST]
Epoch  23/40 | Train: 0.3012 | Val: 0.2905 | LR: 0.000500
Epoch  24/40 | Train: 0.3007 | Val: 0.2966 | LR: 0.000500
Epoch  25/40 | Train: 0.3007 | Val: 0.2922 | LR: 0.000500
Epoch  26/40 | Train: 0.3006 | Val: 0.2900 | LR: 0.000500 ✓ [BEST]
Epoch  27/40 | Train: 0.3004 | Val: 0.2892 | LR: 0.000500 ✓ [BEST]
Epoch  28/40 | Train: 0.3002 | Val: 0.2887 | LR: 0.000500 ✓ [BEST]
Epoch  29/40 | Train: 0.2999 | Val: 0.2903 | LR: 0.000500
Epoch  30/40 | Train: 0.3001 | Val: 0.2899 | LR: 0.000500
Epoch  31/40 | Train: 0.2997 | Val: 0.2902 | LR: 0.000500
Epoch  32/40 | Train: 0.2999 | Val: 0.2888 | LR: 0.000500
Epoch  33/40 | Train: 0.2997 | Val: 0.2971 | LR: 0.000500
Epoch  34/40 | Train: 0.2998 | Val: 0.2885 | LR: 0.000500 ✓ [BEST]
Epoch  35/40 | Train: 0.2996 | Val: 0.2907 | LR: 0.000500
Epoch  37/40 | Train: 0.2989 | Val: 0.2895 | LR: 0.000500
Epoch  38/40 | Train: 0.2991 | Val: 0.2887 | LR: 0.000500
Epoch  39/40 | Train: 0.2989 | Val: 0.2886 | LR: 0.000500
Epoch  40/40 | Train: 0.2984 | Val: 0.2882 | LR: 0.000500 ✓ [BEST]

======================================================================
✓ Training complete!
  Best validation loss: 0.2882
  Model saved to: gat_metrla_best.pth
======================================================================

🎉 Training complete!
Best model: gat_metrla_best.pth""")