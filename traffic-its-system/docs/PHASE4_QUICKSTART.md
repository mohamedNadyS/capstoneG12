# 🚀 Quick Start: Phase 4 SUMO Simulation

## ⚡ 4-Command Complete Workflow

```powershell
# 1. Generate traffic
python scripts/1_generate_traffic.py --congestion 0.4 --vehicles 1500 --variable-pattern mixed

# 2. Predict speeds
python scripts/2_run_prediction.py --scenario data/generated

# 3. Generate routes
python scripts/3_generate_routes.py --scenario data/generated

# 4. Run simulation (NEW!)
python scripts/4_run_sumo_gui.py --config data/generated/simulation.sumocfg --collect-metrics
```

**Done!** You've run a complete intelligent traffic simulation.

---

## 🎯 What You'll See

### SUMO-GUI Window

When you run the simulation, SUMO-GUI opens with:

- **Blue vehicles** = Normal traffic
- **Red vehicles** = Emergency vehicles (faster routes!)
- **Real-time animation** of traffic flow
- **Controls** to start/pause/speed up

### Console Output

```
[SUMO] Launching SUMO-GUI...
   [OK] Starting SUMO-GUI...
   Use GUI controls to start/pause/stop simulation

[METRICS] Parsing tripinfo...
   [OK] Parsed 1500 vehicle trips

======================================================================
SIMULATION METRICS SUMMARY
======================================================================

Vehicles:
  Total: 1500
  Completed: 1485
  
Performance:
  Avg travel time: 124.56 seconds
  Avg waiting time: 18.32 seconds
  
Emergency Vehicles:
  Count: 118
  Avg travel time: 98.23 seconds  ← FASTER!

Normal Vehicles:
  Count: 1367
  Avg travel time: 127.89 seconds

Overall:
  Throughput: 1485 vehicles/hour
======================================================================
```

---

## 🔧 Quick Options

### Visual Simulation (Default)

```powershell
python scripts/4_run_sumo_gui.py --config data/generated/simulation.sumocfg
```

**Use:** Visual demonstration, debugging

---

### Fast Headless Mode

```powershell
python scripts/4_run_sumo_gui.py `
    --config data/generated/simulation.sumocfg `
    --headless `
    --collect-metrics
```

**Use:** Quick testing, batch runs

---

### Auto-Start GUI

```powershell
python scripts/4_run_sumo_gui.py `
    --config data/generated/simulation.sumocfg `
    --start `
    --delay 50 `
    --collect-metrics
```

**Use:** Fast visual verification

---

## 📊 Check Your Results

### View Metrics

```powershell
cat data\generated\simulation_metrics.json
```

### Extract Key Stats

```powershell
python -c "import json; d=json.load(open('data/generated/simulation_metrics.json'))['simulation_metrics']; print(f'Completed: {d[\"completed_vehicles\"]}\nEmergency avg: {d[\"emergency_avg_travel_time\"]:.1f}s\nNormal avg: {d[\"normal_avg_travel_time\"]:.1f}s\nImprovement: {((d[\"normal_avg_travel_time\"]-d[\"emergency_avg_travel_time\"])/d[\"normal_avg_travel_time\"]*100):.1f}%')"
```

**Output:**
```
Completed: 1485
Emergency avg: 98.2s
Normal avg: 127.9s
Improvement: 23.2%
```

---

## 🎓 For Your Demo

### Show Emergency Priority

1. Run simulation with GUI
2. Point out **red vehicles** (emergencies)
3. Show they take **different routes**
4. Show metrics: emergencies are **20-30% faster**

### Show Variable Traffic Handling

1. Generate with `--variable-pattern incident`
2. Run prediction
3. Run routing
4. Show simulation handles **sudden traffic jam**

---

## 🐛 Quick Fixes

### SUMO Not Found?

```powershell
# Install SUMO first
# Windows: https://sumo.dlr.de/docs/Downloads.php

# Then set SUMO_HOME
setx SUMO_HOME "C:\Program Files\SUMO"
```

### GUI Won't Start?

```powershell
# Use headless instead
python scripts/4_run_sumo_gui.py `
    --config data/generated/simulation.sumocfg `
    --headless `
    --collect-metrics
```

### Simulation Too Slow?

```powershell
# Increase delay (lower = faster)
python scripts/4_run_sumo_gui.py `
    --config data/generated/simulation.sumocfg `
    --delay 10
```

---

## ✅ Success Checklist

After running Phase 4:

- [ ] SUMO-GUI launched successfully
- [ ] Saw vehicles moving on network
- [ ] Emergency vehicles (red) visible
- [ ] Simulation completed
- [ ] `tripinfo.xml` generated
- [ ] `simulation_metrics.json` generated
- [ ] Emergency vehicles faster than normal

---

## 🚀 What's Next?

**Phase 5: Analysis & Reporting**

- Compare different scenarios
- Generate charts and visualizations
- Create final capstone report

**Say "start phase 5" to continue!**

---

**You now have a working, visual traffic simulation!** 🎉
