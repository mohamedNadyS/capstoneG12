# 🚦 ITS - Intelligent Transportation System

**Information and Communication Technology for Intelligent Transportation Systems**

A complete AI-powered traffic management system that uses Graph Neural Networks (GNN) for speed prediction and intelligent routing algorithms to optimize traffic flow, reduce congestion, and prioritize emergency vehicles.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

This system addresses urban traffic congestion through:

1. **Traffic Prediction**: GNN-based model predicts road speeds 5-15 minutes ahead
2. **Intelligent Routing**: A* and Dijkstra algorithms find optimal paths
3. **Emergency Priority**: Automatic priority routing for emergency vehicles
4. **Real-time Adaptation**: Dynamic route adjustment based on current conditions
5. **SUMO Integration**: Full visualization and simulation using SUMO-GUI

---

## ✨ Features

### Core Capabilities
- ✅ **GNN Speed Prediction** - Predict traffic speeds using Graph Attention Networks
- ✅ **Synthetic Traffic Generation** - Create realistic traffic scenarios
- ✅ **Multi-objective Routing** - Optimize for time, safety, and efficiency
- ✅ **Emergency Vehicle Priority** - Automatic route optimization for emergencies
- ✅ **Congestion Detection** - Real-time traffic jam identification
- ✅ **SUMO Simulation** - Visual simulation with SUMO-GUI
- ✅ **Performance Metrics** - Track trip time, fuel consumption, throughput

### Design Requirements (Capstone Compliance)
- ✅ Measurable design requirements (time response, accuracy)
- ✅ Traffic quality and safety improvement metrics
- ✅ ICT and AI integration (IoT, Machine Learning)
- ✅ Hardware-ready (sensor integration capable)
- ✅ Testable, workable, reliable, portable prototype

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│     INTELLIGENT TRANSPORTATION SYSTEM    │
└─────────────────────────────────────────┘
              │
    ┌─────────┴──────────┐
    │                    │
    ▼                    ▼
┌─────────┐      ┌──────────────┐
│ TRAFFIC │─────▶│  GNN MODEL   │
│  DATA   │      │  PREDICTION  │
└─────────┘      └──────┬───────┘
                        │
                        ▼
              ┌─────────────────┐
              │ ROUTING ENGINE  │
              │  • A* (Normal)  │
              │  • Dijkstra(EM) │
              └────────┬────────┘
                       │
                       ▼
              ┌────────────────┐
              │ SUMO SIMULATION│
              │   (GUI/TraCI)  │
              └────────────────┘
```

---

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- SUMO 1.18+ installed
- 4GB RAM minimum
- CUDA-capable GPU (optional, for faster training)

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd traffic-its-system
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Install SUMO
```bash
# Ubuntu/Debian
sudo add-apt-repository ppa:sumo/stable
sudo apt-get update
sudo apt-get install sumo sumo-tools sumo-doc

# macOS
brew install sumo

# Windows
# Download from: https://sumo.dlr.de/docs/Downloads.php
```

### Step 4: Verify Installation
```bash
# Check SUMO
sumo --version

# Check Python packages
python -c "import torch; import torch_geometric; print('✓ All packages installed')"
```

---

## ⚡ Quick Start

### Generate Traffic Scenario

```bash
# Generate moderate traffic (30% congestion, 500 vehicles)
python scripts/1_generate_traffic.py --congestion 0.3 --vehicles 500 --scenario normal
```

### Run Complete Pipeline

```bash
# 1. Generate traffic
python scripts/1_generate_traffic.py --congestion 0.5 --vehicles 1000 --scenario rush_hour

# 2. Run GNN prediction (Phase 2)
# python scripts/2_run_prediction.py

# 3. Generate optimal routes (Phase 3)
# python scripts/3_generate_routes.py

# 4. Run SUMO visualization (Phase 4)
# python scripts/4_run_sumo_gui.py
```

---

## 📖 Usage Guide

### 1. Traffic Generation

The traffic generator creates synthetic traffic scenarios based on your input parameters.

**Basic Usage:**
```bash
python scripts/1_generate_traffic.py \
    --congestion 0.4 \
    --vehicles 800 \
    --scenario normal
```

**Parameters:**
- `--congestion`: Congestion level (0.0 = free flow, 1.0 = jammed)
- `--vehicles`: Number of vehicles to generate
- `--scenario`: Scenario type
  - `free_flow`: Light traffic (10% congestion)
  - `normal`: Moderate traffic (30% congestion)
  - `rush_hour`: Heavy traffic (60% congestion)
  - `heavy_jam`: Severe congestion (90% congestion)

**Examples:**

```bash
# Light morning traffic
python scripts/1_generate_traffic.py --congestion 0.1 --vehicles 200 --scenario free_flow

# Rush hour chaos
python scripts/1_generate_traffic.py --congestion 0.8 --vehicles 1500 --scenario rush_hour

# Custom emergency ratio
python scripts/1_generate_traffic.py \
    --congestion 0.5 \
    --vehicles 1000 \
    --emergency-ratio 0.10 \
    --scenario normal
```

**Output Files:**
```
data/generated/
├── traffic_scenario.json       # Complete scenario
├── vehicles.json               # Vehicle list
├── edge_states.json           # Road conditions
├── speed_history.json         # Historical speeds
├── speed_matrix.npy           # GNN input matrix
└── edge_order.json            # Edge ID mapping
```

### 2. Understanding Output

After generation, you'll see:

```
📊 Scenario Summary:
   • Vehicles: 1000
   • Edges with traffic: 48
   • Speed history timesteps: 12

✅ Traffic generation completed successfully!

Next steps:
  1. Run GNN prediction: python scripts/2_run_prediction.py
  2. Generate routes: python scripts/3_generate_routes.py
  3. Run SUMO simulation: python scripts/4_run_sumo_gui.py
```

### 3. Configuration

Customize behavior in `configs/`:

**System Configuration** (`configs/system_config.yaml`):
```yaml
sumo:
  net_file: "map.net.xml"
  gui: true
  step_length: 1.0

prediction:
  model_file: "gat_metrla_best.pth"
  input_window: 12
  prediction_horizon: 3
```

**Traffic Generation** (`configs/traffic_generation.yaml`):
```yaml
generation:
  default_num_vehicles: 500
  default_congestion_level: 0.3
  emergency_vehicle_ratio: 0.05

scenarios:
  rush_hour:
    congestion_level: 0.6
    num_vehicles: 1000
```

---

## 📁 Project Structure

```
traffic-its-system/
│
├── data/                           # Data storage
│   ├── sumo/                      # SUMO network files
│   │   └── map.net.xml           # Network definition
│   ├── generated/                 # Generated traffic data
│   └── metr-la/                  # GNN training data
│
├── models/                        # Trained models
│   └── trained/
│       ├── gat_metrla_best.pth   # GNN model
│       └── scaler_metrla.pkl     # Data scaler
│
├── src/                           # Source code
│   ├── 1_data_generation/        # Traffic generation
│   ├── 2_prediction/             # GNN prediction
│   ├── 3_routing/                # Routing algorithms
│   ├── 4_sumo_integration/       # SUMO interface
│   ├── 5_control/                # Traffic control
│   ├── 6_visualization/          # Plotting & vis
│   └── utils/                    # Utilities
│
├── scripts/                       # Executable scripts
│   ├── 1_generate_traffic.py     # Generate scenarios
│   ├── 2_run_prediction.py       # Run GNN (Phase 2)
│   ├── 3_generate_routes.py      # Create routes (Phase 3)
│   └── 4_run_sumo_gui.py         # Launch SUMO (Phase 4)
│
├── configs/                       # Configuration files
├── outputs/                       # Results & logs
├── tests/                         # Unit tests
└── notebooks/                     # Jupyter demos
```

---

## 🔬 Development Phases

### Phase 1: Foundation ✅ **COMPLETED**
- [x] Project structure
- [x] SUMO network parser
- [x] Traffic generator
- [x] Speed history generator
- [x] Configuration system
- [x] Documentation

### Phase 2: GNN Prediction (Next)
- [ ] GNN predictor wrapper
- [ ] Speed mapping to SUMO edges
- [ ] Prediction pipeline
- [ ] Integration tests

### Phase 3: Routing Engine
- [ ] Graph builder
- [ ] Dijkstra implementation
- [ ] A* implementation
- [ ] Decision engine
- [ ] Route optimization

### Phase 4: SUMO Integration
- [ ] Route file generator
- [ ] SUMO configuration builder
- [ ] SUMO-GUI runner
- [ ] TraCI controller
- [ ] Real-time visualization

### Phase 5: Validation
- [ ] Metrics collection
- [ ] Performance analysis
- [ ] Documentation
- [ ] Final report

---

## 📊 Performance Metrics

The system tracks these key metrics (per capstone requirements):

1. **Trip Time** - Total travel time reduction
2. **Fuel Consumption** - Estimated fuel savings
3. **Traffic Comfort** - Speed stability
4. **Accident Rate** - Safety risk assessment
5. **Traffic Flow Efficiency** - Throughput improvement
6. **Waiting Time** - Intersection delays
7. **Emergency Vehicle Priority** - Response time
8. **Pollution Reduction** - Environmental impact

---

## 🧪 Testing

Run tests with:

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_traffic_generation.py -v

# Test traffic generation
python src/1_data_generation/traffic_generator.py data/sumo/map.net.xml
```

---

## 🤝 Contributing

This is a capstone project. External contributions are not currently accepted.

---

## 📝 License

Academic Project - All Rights Reserved

---

## 📞 Support

For questions or issues:
1. Check documentation in `docs/`
2. Review configuration files
3. Check logs in `outputs/logs/`

---

## 🎓 Academic Context

This project is part of a Capstone Challenge (2025-2026, Grade 3, Semester 1) on:
**"Information and Communication Technology (ICT) for Intelligent Transportation Systems (ITS)"**

**Grand Challenges Addressed:**
- Urban congestion reduction
- Pollution mitigation
- Population growth accommodation
- Public health improvement

---

## 🙏 Acknowledgments

- SUMO (Simulation of Urban MObility)
- PyTorch & PyTorch Geometric
- METR-LA dataset for GNN training

---

**Version:** 1.0.0 (Phase 1 Complete)  
**Last Updated:** November 2025  
**Status:** ✅ Phase 1 Complete | 🚧 Phase 2 In Progress
