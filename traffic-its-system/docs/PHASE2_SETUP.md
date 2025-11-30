# 🚀 Phase 2 Setup Guide: GNN Prediction

## 📋 Prerequisites

Before running predictions, you need to copy your trained model files.

---

## 📦 Required Files

You need these 2 files from your training:

### 1. Trained GNN Model
**File:** `gat_metrla_best.pth`  
**Source:** Your training output  
**Destination:** `models/trained/gat_metrla_best.pth`

### 2. Fitted Scaler
**File:** `scaler_metrla.pkl`  
**Source:** Your training output  
**Destination:** `models/trained/scaler_metrla.pkl`

---

## 🔧 Setup Steps

### Step 1: Create Model Directory
```bash
cd traffic-its-system
mkdir -p models/trained
```

### Step 2: Copy Model Files
```bash
# Copy your trained model
cp /path/to/your/gat_metrla_best.pth models/trained/

# Copy your scaler
cp /path/to/your/scaler_metrla.pkl models/trained/
```

### Step 3: Verify Files
```bash
ls -lh models/trained/
```

**Expected output:**
```
-rw-r--r--  1 user  group   15M  gat_metrla_best.pth
-rw-r--r--  1 user  group  2.0K  scaler_metrla.pkl
```

---

## ✅ Test Installation

Run this command to verify everything is set up:

```bash
python -c "
import torch
from pathlib import Path

model_path = Path('models/trained/gat_metrla_best.pth')
scaler_path = Path('models/trained/scaler_metrla.pkl')

if model_path.exists() and scaler_path.exists():
    print('✅ All files found!')
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    print(f'✅ Model loaded successfully')
    if 'model_state_dict' in checkpoint:
        print(f'   Epoch: {checkpoint.get(\"epoch\", \"unknown\")}')
        print(f'   Val loss: {checkpoint.get(\"val_loss\", \"unknown\")}')
else:
    print('❌ Files missing!')
    if not model_path.exists():
        print(f'   Missing: {model_path}')
    if not scaler_path.exists():
        print(f'   Missing: {scaler_path}')
"
```

---

## 🚀 Run Prediction

Once files are copied, run prediction:

```bash
# Basic usage
python scripts/2_run_prediction.py --scenario data/generated

# With custom options
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --mapping-strategy interpolate \
    --device auto
```

---

## 📊 Understanding Model Adaptation

### The Challenge

Your GNN was trained on:
- **METR-LA dataset**: 207 traffic sensors
- **Los Angeles network**: Large highway system

Your SUMO network has:
- **95 edges**: Smaller urban network
- **Different topology**: Different road structure

### The Solution

The system handles this mismatch using **3 strategies**:

#### 1. **Interpolate** (Default - Recommended)
- Smoothly maps 207 predictions → 95 edges
- Preserves spatial patterns
- Best for general use

```bash
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --mapping-strategy interpolate
```

#### 2. **Average**
- Groups predictions and averages them
- Good when GNN nodes > SUMO edges
- More stable predictions

```bash
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --mapping-strategy average
```

#### 3. **Direct**
- Takes first N predictions directly
- Simplest approach
- Fast but may miss patterns

```bash
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --mapping-strategy direct
```

---

## 📈 Expected Output

### Console Output
```
🧠 Initializing GNN Predictor...
   Device: cuda
   Nodes: 95
   ✓ Loaded scaler from: models/trained/scaler_metrla.pkl
   ✓ Loaded model from epoch 40 (val_loss: 3.2156)
   ✓ Model ready for prediction

🔮 Running GNN prediction...
   ✓ Predicted shape: (3, 95)
   ✓ Horizons: [5, 10, 15] minutes

🗺️  Mapping to SUMO edges...
   ✓ Mapped to 95 edges

✅ Prediction Complete!
   Mean predicted speed: 34.5 km/h
   Speed range: [12.3, 58.7] km/h
```

### Generated Files
```
data/generated/
└── predictions.json          # Prediction results
```

### Prediction Format
```json
{
  "predictions": {
    "E0": [35.2, 33.8, 32.1],    # t+5min, t+10min, t+15min
    "E1": [42.1, 40.5, 39.2],
    ...
  },
  "horizons_minutes": [5, 10, 15],
  "confidence": {
    "E0": 0.85,
    "E1": 0.92,
    ...
  },
  "validation": {
    "mean_speed": 34.5,
    "valid": true
  }
}
```

---

## 🐛 Troubleshooting

### Error: "Model file not found"
```bash
# Check if files exist
ls models/trained/

# If missing, copy them:
cp /path/to/gat_metrla_best.pth models/trained/
cp /path/to/scaler_metrla.pkl models/trained/
```

### Error: "Shape mismatch"
```bash
# Use interpolate strategy (handles different sizes)
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --mapping-strategy interpolate
```

### Error: "CUDA out of memory"
```bash
# Use CPU instead
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --device cpu
```

### Error: "Scenario not found"
```bash
# Generate traffic first
python scripts/1_generate_traffic.py --congestion 0.3 --vehicles 1200

# Then run prediction
python scripts/2_run_prediction.py --scenario data/generated
```

---

## 📚 Additional Options

### Custom Model Path
```bash
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --model /path/to/custom_model.pth \
    --scaler /path/to/custom_scaler.pkl
```

### Custom Output Location
```bash
python scripts/2_run_prediction.py \
    --scenario data/generated \
    --output results/my_predictions.json
```

### Use Specific GPU
```bash
CUDA_VISIBLE_DEVICES=0 python scripts/2_run_prediction.py \
    --scenario data/generated \
    --device cuda
```

---

## 🎯 Next Steps

After successful prediction:

1. **Review Predictions**
   ```bash
   cat data/generated/predictions.json | python -m json.tool | head -50
   ```

2. **Phase 3: Generate Routes**
   ```bash
   python scripts/3_generate_routes.py
   ```

3. **Phase 4: Run SUMO Simulation**
   ```bash
   python scripts/4_run_sumo_gui.py
   ```

---

## ✅ Checklist

- [ ] Copied `gat_metrla_best.pth` to `models/trained/`
- [ ] Copied `scaler_metrla.pkl` to `models/trained/`
- [ ] Verified files with test command
- [ ] Generated traffic scenario (Phase 1)
- [ ] Ran prediction successfully
- [ ] Reviewed predictions.json output
- [ ] Ready for Phase 3 (Routing)

---

**Status:** Phase 2 Code Complete  
**Ready:** After model files are copied  
**Next Phase:** Routing Engine (Phase 3)

**Need Help?** Check `outputs/logs/system.log` for detailed error messages.
