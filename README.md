# capstoneG12 - Intelligent Traffic Management System (ITS)

A capstone project that builds an end-to-end intelligent transportation system: a graph neural network predicts near-future traffic speeds, a routing engine turns those predictions into per-vehicle routes (with priority handling for emergency vehicles), and SUMO simulates the whole network so the results can be measured. A Flask server for Raspberry Pi 5 packages the same prediction and routing pipeline behind an API for a companion Flutter app.

## What it does

- **Predicts traffic speeds** on the METR-LA highway sensor network with a spatio-temporal GNN (Graph Attention Network + GRU), forecasting 5, 10 and 15 minutes ahead from the last hour of readings.
- **Generates realistic traffic scenarios** for a custom SUMO city network (33 junctions, 95 roads, 1.68 km): configurable vehicle counts, congestion levels and emergency vehicle ratios.
- **Routes every vehicle** with a decision engine that picks the algorithm (A* or Dijkstra), cost function and priority per vehicle type. Emergency vehicles get priority routing with congestion tolerance.
- **Simulates and measures** the result in SUMO, then compares AI-routed vehicles against a baseline on travel time, waiting time and estimated pollution.
- **Serves it live from a Raspberry Pi 5**: a Flask server that hosts a WiFi hotspot, receives live traffic data from a Flutter app, keeps a rolling one-hour history, predicts with the trained GAT model and returns optimized routes.

## System pipeline

```
Traffic scenario generation  ->  Speed history (GNN input)
        |                              |
        v                              v
   SUMO network (map.net.xml)   GAT + GRU prediction
        |                              |
        +------------>  Routing decision engine (A* / Dijkstra)
                               |
                               v
                     SUMO simulation + metrics
                     (travel time, waiting, pollution)
```

The runnable pipeline lives in `traffic-its-system/scripts/`:

1. `1_generate_traffic.py` - build a scenario (vehicles, congestion, emergency ratio)
2. `2_run_prediction.py` - predict edge speeds with the trained model
3. `3_generate_routes.py` - route all vehicles with the decision engine
4. `4_run_sumo_gui.py` - launch the simulation in SUMO-GUI

## The prediction model

`SpatioTemporalGAT` (see `train.py`):

- **GATConv** layer (4 attention heads, hidden dim 64) captures spatial dependencies between the 207 METR-LA sensors using the dataset's adjacency matrix.
- **GRU** layer captures temporal patterns over the input window.
- **MLP head** outputs the next 3 timesteps.

Training setup: input window of 12 timesteps (1 hour), prediction horizon of 3 timesteps (15 minutes), 40 epochs, batch size 32, Adam at 1e-3. Missing sensor readings (zero speeds) are forward-filled. The trained weights (`gat_metrla_best.pth`) and fitted scaler (`scaler_metrla.pkl`) are included.

## Results

Test set: 5,126 samples from METR-LA (207 sensors, ~428 hours). Full details in `test_results/test_report.txt`, with plots (time series, scatter, error distribution, per-node MAE) in `test_results/`.

| Horizon | MAE | RMSE | MAPE |
|---|---|---|---|
| Overall | 2.89 km/h | 5.08 km/h | 7.79% |
| t+5 min | 2.58 km/h | 4.32 km/h | 6.73% |
| t+10 min | 2.92 km/h | 5.12 km/h | 7.87% |
| t+15 min | 3.16 km/h | 5.69 km/h | 8.77% |

Validated traffic scenarios on the custom network (average speed):

| Scenario | Vehicles | Congestion | Avg speed |
|---|---|---|---|
| Baseline | 300 | 5% | 48.2 km/h |
| Normal | 1,200 | 30% | 36.7 km/h |
| Rush hour | 2,150 | 60% | 16.1 km/h |

### Efficiency

Numbers below come from the project's own logs (`traffic-its-system/outputs/logs/system.log`) and saved routing metadata, not estimates.

- **Routing is fast enough to be live**: the largest logged run routed **4,831 vehicles** (4,587 normal on A*, 244 emergency on Dijkstra) in **~2.2 seconds**, roughly 2,200 routes per second. A later run routed 1,926 vehicles in ~0.4 seconds.
- **Emergency priority works**: in the saved routing metadata, emergency vehicles averaged a route cost of **7.2 seconds vs 14.3 seconds** for normal vehicles, about **50% lower**, because the decision engine switches them to Dijkstra with congestion tolerance and priority handling.
- **Prediction accuracy holds up over time**: average error stays under 9% even 15 minutes out (MAPE 6.73% at t+5 min, 8.77% at t+15 min), so the routing engine is working from dependable forecasts.
- **The whole network stays routable**: all 33 nodes are usable and strongly connected, and 0 vehicles were skipped for missing paths across the logged runs.

`compare_vehicle_metrics.py` and `run_full_vehicle_comparison.py` quantify the AI routing improvement over baseline routing on travel time, waiting time and pollution.

## Repository layout

```
train.py, test.py, test_inference_system.py   # GNN training, evaluation, inference
gat_metrla_best.pth, scaler_metrla.pkl        # trained model + scaler
data/metr-la/                                 # METR-LA dataset (h5 + adjacency)
test_results/                                 # metrics, report and plots
map.net.xml                                   # custom SUMO network (33 nodes, 95 edges)
raspberry_pi_traffic_server.py                # Flask server for Raspberry Pi 5 + Flutter app
traffic-its-system/                           # the full ITS pipeline
  scripts/                                    # pipeline steps 1-4 + measurement tools
  src/
    data_generation/                          # scenario + speed history generation
    prediction/                               # GNN predictor, pipeline, speed mapper
    routing/                                  # A*, Dijkstra, decision engine, graph builder
    simulation/                               # SUMO runner, metrics collector
    sumo_integration/                         # SUMO network parser
  configs/                                    # system and traffic generation config
  data/                                       # generated scenarios and routing output
```

## Getting started

Requirements: Python 3.11+, SUMO (with `sumolib` and `traci`), PyTorch 2.x and PyTorch Geometric. Python dependencies are in `traffic-its-system/requirements.txt`.

```bash
pip install -r traffic-its-system/requirements.txt

cd traffic-its-system

# generate a normal-traffic scenario (1,200 vehicles, 30% congestion)
python scripts/1_generate_traffic.py --congestion 0.3 --vehicles 1200 --scenario normal

# predict speeds, route vehicles, then open the simulation
python scripts/2_run_prediction.py
python scripts/3_generate_routes.py
python scripts/4_run_sumo_gui.py
```

To retrain the prediction model from the repo root:

```bash
python train.py   # trains on data/metr-la, saves gat_metrla_best.pth + scaler_metrla.pkl
python test.py    # writes metrics and plots to test_results/
```

## Tech stack

Python, PyTorch, PyTorch Geometric (GAT), GRU, scikit-learn, SUMO (TraCI/sumolib), NetworkX, Flask, NumPy/pandas, Matplotlib/Seaborn. Dataset: [METR-LA](https://github.com/liyaguang/DCRNN) (207 loop detectors on Los Angeles highways, 5-minute resolution).

Capstone project, Group 12.
