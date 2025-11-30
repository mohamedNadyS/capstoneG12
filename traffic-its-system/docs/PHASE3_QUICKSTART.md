# 🚀 Quick Start: Phase 3 + Variable Traffic

## 🎯 What's New

1. **Variable Traffic Patterns** - Generate realistic, changing traffic
2. **Intelligent Routing** - A* + Dijkstra algorithms
3. **Emergency Priority** - Special handling for emergency vehicles
4. **SUMO Integration** - Ready-to-run simulation files

---

## ⚡ 3-Step Quickstart

### Step 1: Generate Challenging Traffic

```powershell
python scripts/1_generate_traffic.py `
    --congestion 0.4 `
    --vehicles 1500 `
    --variable-pattern mixed
```

**What it does:**
- Creates 1500 vehicles (8% emergency)
- Generates **time-varying speeds** (not constant!)
- Uses "mixed" pattern (most challenging for GNN)

**Output:** `data/generated/` with variable speed patterns

---

### Step 2: Predict Future Speeds

```powershell
python scripts/2_run_prediction.py --scenario data/generated
```

**What it does:**
- Loads variable traffic data
- Runs GNN prediction
- Predicts speeds for t+5, t+10, t+15 minutes

**Output:** `data/generated/predictions.json`

---

### Step 3: Generate Optimal Routes

```powershell
python scripts/3_generate_routes.py --scenario data/generated
```

**What it does:**
- Builds routing graph with predicted speeds
- Routes emergency vehicles with Dijkstra (optimal)
- Routes normal vehicles with A* (fast)
- Generates SUMO files

**Output:**
- `data/generated/routes.rou.xml` - Vehicle routes
- `data/generated/simulation.sumocfg` - SUMO config
- `data/generated/routing_metadata.json` - Analysis data

---

## 🌊 Understanding Variable Patterns

### Why Variable Patterns Matter

**Before (Standard):**
```
Time:  0  →  2  →  4  →  6  →  8  → 10
Speed: 35 → 35 → 34 → 35 → 36 → 35 km/h
```
↑ Almost constant - EASY to predict

**After (Mixed Pattern):**
```
Time:  0  →  2  →  4  →  6  →  8  → 10
Speed: 45 → 38 → 15 → 12 → 28 → 42 km/h
```
↑ Highly variable - CHALLENGES the model!

---

### Pattern Types Quick Reference

```powershell
# Pattern 1: Morning Rush
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern morning_rush
# Effect: Gradual buildup → peak → release

# Pattern 2: Traffic Incident
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern incident
# Effect: Normal → sudden spike → slow recovery

# Pattern 3: Gradual Increase
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern gradual
# Effect: Steady linear increase

# Pattern 4: Variable
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern variable
# Effect: Random fluctuations (smoothed)

# Pattern 5: Mixed (RECOMMENDED)
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern mixed
# Effect: Combination of all patterns
```

---

## 🎯 Complete Example Workflow

### Scenario: Rush Hour with Traffic Incident

```powershell
# 1. Generate rush hour pattern with incident
python scripts/1_generate_traffic.py `
    --congestion 0.45 `
    --vehicles 1800 `
    --variable-pattern incident `
    --emergency-ratio 0.10 `
    --scenario rush_hour

# 2. Predict speeds
python scripts/2_run_prediction.py `
    --scenario data/generated `
    --mapping-strategy interpolate

# 3. Generate routes with emergency priority
python scripts/3_generate_routes.py `
    --scenario data/generated `
    --simulation-time 3600

# 4. View results
cat data/generated/routing_metadata.json
```

**What you get:**
- Realistic incident scenario
- GNN predictions during crisis
- Optimal routes for 180 emergency vehicles
- Efficient routes for 1620 normal vehicles

---

## 📊 Checking Results

### View Traffic Pattern

```powershell
# Load speed history
python -c "
import numpy as np
speeds = np.load('data/generated/speed_matrix.npy')
print(f'Shape: {speeds.shape}')
print(f'Mean speed: {speeds.mean():.1f} km/h')
print(f'Std dev: {speeds.std():.1f} km/h')
print(f'Range: [{speeds.min():.1f}, {speeds.max():.1f}] km/h')

# Check variability (high = challenging!)
changes = np.abs(np.diff(speeds, axis=0))
print(f'Avg change per timestep: {changes.mean():.1f} km/h')
print(f'Max change: {changes.max():.1f} km/h')
"
```

**Good indicators:**
- Std dev > 10 km/h (high variability)
- Avg change > 5 km/h (dynamic)
- Max change > 20 km/h (has incidents)

---

### View Predictions

```powershell
python -c "
import json
pred = json.load(open('data/generated/predictions.json'))
stats = pred['validation']
print(f\"Predictions for {stats['num_edges']} edges\")
print(f\"Mean: {stats['mean_speed']:.1f} km/h\")
print(f\"Range: [{stats['min_speed']:.1f}, {stats['max_speed']:.1f}] km/h\")
print(f\"Valid: {stats['valid']}\")
"
```

---

### View Routing Statistics

```powershell
python -c "
import json
meta = json.load(open('data/generated/routing_metadata.json'))
stats = meta['statistics']
print(f\"Total vehicles: {stats['total_vehicles']}\")
print(f\"Emergency: {stats['emergency_vehicles']}\")
print(f\"Normal: {stats['normal_vehicles']}\")
print(f\"Avg cost: {stats['avg_cost']:.1f} seconds\")
print(f\"Algorithms: {stats['algorithm_usage']}\")
"
```

---

## 🎓 Testing Model Robustness

### Test on All Patterns

```powershell
# Generate all patterns
foreach ($pattern in @('morning_rush', 'incident', 'gradual', 'variable', 'mixed')) {
    python scripts/1_generate_traffic.py `
        --congestion 0.35 --vehicles 1300 `
        --variable-pattern $pattern `
        --output-dir "data/patterns/$pattern"
    
    python scripts/2_run_prediction.py `
        --scenario "data/patterns/$pattern"
}

# Compare prediction accuracy
python -c "
import json
from pathlib import Path

patterns = ['morning_rush', 'incident', 'gradual', 'variable', 'mixed']
for pattern in patterns:
    path = Path(f'data/patterns/{pattern}/predictions.json')
    if path.exists():
        data = json.load(open(path))
        mean = data['validation']['mean_speed']
        std = data['validation']['std_speed']
        print(f'{pattern:15s}: mean={mean:.1f}, std={std:.1f}')
"
```

**Expected:** 
- `gradual`: Low std (easy to predict)
- `mixed`: High std (hard to predict)

---

## ⚡ Performance Tips

### For Large Scenarios (2000+ vehicles)

```powershell
# Use A* for all (faster)
python scripts/3_generate_routes.py `
    --scenario data/generated `
    --no-emergency-priority
# This routes emergency vehicles with A* too
```

### For Maximum Accuracy

```powershell
# Let emergency vehicles use Dijkstra (default)
python scripts/3_generate_routes.py `
    --scenario data/generated
# Guarantees optimal paths for emergencies
```

---

## 🐛 Troubleshooting

### Issue: "No route found for vehicle"

**Cause:** Disconnected network or overcrowded edges

**Solution:**
```powershell
# Generate with lower congestion
python scripts/1_generate_traffic.py `
    --congestion 0.3 --vehicles 1000 `
    --variable-pattern mixed
```

---

### Issue: Prediction errors high

**Cause:** Pattern too random for model

**Solution:** Use smoother patterns
```powershell
# Try gradual or morning_rush instead of mixed
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 1300 `
    --variable-pattern morning_rush
```

---

### Issue: Routing takes too long

**Cause:** Too many vehicles

**Solution:** Batch routing or reduce vehicles
```powershell
python scripts/1_generate_traffic.py `
    --congestion 0.35 --vehicles 800
```

---

## ✅ Success Checklist

After running all 3 steps, verify:

- [ ] `data/generated/speed_matrix.npy` exists (12 × 95)
- [ ] Speed std dev > 8 km/h (variable traffic)
- [ ] `data/generated/predictions.json` exists
- [ ] Prediction valid = true
- [ ] `data/generated/routes.rou.xml` exists
- [ ] `data/generated/simulation.sumocfg` exists
- [ ] All vehicles routed successfully
- [ ] Algorithm usage shows A* + Dijkstra

---

## 🚀 Next Steps

### Option 1: Analyze Results
```powershell
# Compare routing methods
python scripts/analyze_results.py  # (Phase 5)
```

### Option 2: Run SUMO Simulation
```powershell
sumo-gui -c data/generated/simulation.sumocfg
```

### Option 3: Generate More Scenarios
```powershell
# Try different combinations
python scripts/1_generate_traffic.py `
    --congestion 0.5 --vehicles 2000 `
    --variable-pattern incident
```

---

**You now have a complete intelligent routing system with realistic, challenging traffic patterns!** 🎉

**For full details:** See `docs/PHASE3_COMPLETE.md`
