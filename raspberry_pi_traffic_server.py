#!/usr/bin/env python3
"""
Raspberry Pi 5 Traffic Prediction & Routing Server
===================================================
This server:
1. Creates WiFi hotspot "Raspberry_Pi_5"
2. Receives traffic data from Flutter app
3. Maintains 1-hour rolling history (12 timestamps)
4. Uses GAT model for traffic prediction
5. Implements A* algorithm for optimal routing
6. Sends routes back to Flutter app

Author: Traffic AI System
Date: 2026-01-15
"""

import os
import sys
import json
import time
import pickle
import logging
import subprocess
from datetime import datetime, timedelta
from collections import deque, defaultdict
from threading import Lock, Thread
import heapq

import numpy as np
import torch
import torch.nn as nn
from flask import Flask, request, jsonify
from flask_cors import CORS
from torch_geometric.nn import GATConv
from torch_geometric.utils import dense_to_sparse
import joblib

# ============================================================================
# CONFIGURATION
# ============================================================================

# Server Configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 5000
HOTSPOT_SSID = "Raspberry_Pi_5"
HOTSPOT_PASSWORD = "traffic2026"  # Change this for security

# Traffic Data Configuration
NUM_NODES = 207  # METR-LA has 207 sensors - map your streets to these
INPUT_WINDOW = 12  # 12 timesteps = 1 hour (5 min each)
PRED_HORIZON = 3   # Predict 3 steps ahead (15 minutes)
UPDATE_INTERVAL = 300  # 5 minutes in seconds

# Model Configuration
MODEL_PATH = "gat_metrla_best.pth"
SCALER_PATH = "scaler_metrla.pkl"
HIDDEN_DIM = 64
NUM_HEADS = 4
DROPOUT = 0.1

# Device
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('traffic_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# STREET-TO-NODE MAPPING
# ============================================================================
# Map Flutter app streets (A-Z) to METR-LA node indices (0-206)
# This is a simplified mapping - adjust based on your actual street network

STREET_TO_NODE = {
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7, 'I': 8, 'J': 9,
    'K': 10, 'L': 11, 'M': 12, 'N': 13, 'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19,
    'U': 20, 'V': 21, 'W': 22, 'X': 23, 'Y': 24, 'Z': 25
}

# Street adjacency (from your Flutter app graph)
STREET_ADJACENCY = {
    'A': ['B', 'F'],
    'B': ['A', 'C', 'G'],
    'C': ['B', 'D', 'H'],
    'D': ['C', 'E', 'I'],
    'E': ['D', 'J'],
    'F': ['A', 'G', 'K'],
    'G': ['B', 'F', 'H', 'L'],
    'H': ['C', 'G', 'I', 'M'],
    'I': ['D', 'H', 'J', 'N'],
    'J': ['E', 'I', 'O'],
    'K': ['F', 'L', 'P'],
    'L': ['G', 'K', 'M', 'Q'],
    'M': ['H', 'L', 'N', 'R'],
    'N': ['I', 'M', 'O', 'S'],
    'O': ['J', 'N', 'T'],
    'P': ['K', 'Q'],
    'Q': ['L', 'P', 'R'],
    'R': ['M', 'Q', 'S'],
    'S': ['N', 'R', 'T'],
    'T': ['O', 'S']
}

# ============================================================================
# GAT MODEL DEFINITION (Same as training)
# ============================================================================

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
        """
        Args:
            x: (B, W, N) - batch of sequences
            edge_index: (2, E) - graph edges
        Returns:
            pred: (B, H, N) - predictions
        """
        B, W, N = x.shape
        x = x.to(torch.float32)

        outputs = []
        for t in range(W):
            node_feat = x[:, t, :].unsqueeze(-1)  # (B, N, 1)
            
            batch_outputs = []
            for b in range(B):
                nf = node_feat[b]  # (N, 1)
                nf = self.gat(nf, edge_index)  # (N, H)
                batch_outputs.append(nf.unsqueeze(0))
            
            outputs.append(torch.cat(batch_outputs, dim=0))

        h = torch.stack(outputs, dim=1)  # (B, W, N, H)
        B, W, N, H = h.shape

        h = h.permute(0, 2, 1, 3).reshape(B*N, W, H)
        
        out, _ = self.gru(h)
        out = out[:, -1, :]
        
        pred = self.mlp(out)
        pred = pred.reshape(B, N, self.horizon).permute(0, 2, 1)
        
        return pred

# ============================================================================
# TRAFFIC DATA MANAGER
# ============================================================================

class TrafficDataManager:
    """Manages real-time traffic data collection and history"""
    
    def __init__(self, num_nodes, window_size=12):
        self.num_nodes = num_nodes
        self.window_size = window_size
        self.lock = Lock()
        
        # Rolling history: deque of (timestamp, speed_array)
        self.history = deque(maxlen=window_size)
        
        # Current data: node_id -> {speeds: list, car_counts: list, timestamps: list}
        self.current_data = defaultdict(lambda: {
            'speeds': [],
            'car_counts': [],
            'timestamps': []
        })
        
        # Last update time
        self.last_update = datetime.now()
        
        logger.info(f"TrafficDataManager initialized: {num_nodes} nodes, {window_size} window")
    
    def add_speed_data(self, street_id, speed, car_count=1):
        """Add speed data from a car"""
        with self.lock:
            if street_id not in STREET_TO_NODE:
                logger.warning(f"Unknown street ID: {street_id}")
                return False
            
            node_id = STREET_TO_NODE[street_id]
            timestamp = datetime.now()
            
            self.current_data[node_id]['speeds'].append(speed)
            self.current_data[node_id]['car_counts'].append(car_count)
            self.current_data[node_id]['timestamps'].append(timestamp)
            
            logger.debug(f"Added speed data: Street {street_id} (Node {node_id}) = {speed:.2f} km/h")
            return True
    
    def aggregate_and_update(self):
        """Aggregate current data and add to history"""
        with self.lock:
            timestamp = datetime.now()
            speed_array = np.zeros(self.num_nodes, dtype=np.float32)
            
            # Aggregate data for each node
            for node_id in range(self.num_nodes):
                if node_id in self.current_data and self.current_data[node_id]['speeds']:
                    # Average speed weighted by car count
                    speeds = np.array(self.current_data[node_id]['speeds'])
                    counts = np.array(self.current_data[node_id]['car_counts'])
                    
                    if len(speeds) > 0:
                        # Weighted average
                        speed_array[node_id] = np.average(speeds, weights=counts)
                    else:
                        speed_array[node_id] = 50.0  # Default speed
                else:
                    # No data - use previous value or default
                    if len(self.history) > 0:
                        speed_array[node_id] = self.history[-1][1][node_id]
                    else:
                        speed_array[node_id] = 50.0  # Default speed
            
            # Add to history
            self.history.append((timestamp, speed_array))
            
            # Clear current data
            self.current_data.clear()
            self.last_update = timestamp
            
            logger.info(f"Aggregated data: {len(self.history)}/{self.window_size} timesteps")
            return speed_array
    
    def get_history_array(self):
        """Get history as numpy array for model input"""
        with self.lock:
            if len(self.history) < self.window_size:
                # Pad with default values
                padding_needed = self.window_size - len(self.history)
                default_speeds = np.full(self.num_nodes, 50.0, dtype=np.float32)
                
                padded_history = [default_speeds] * padding_needed
                padded_history.extend([speeds for _, speeds in self.history])
                
                return np.array(padded_history, dtype=np.float32)
            else:
                return np.array([speeds for _, speeds in self.history], dtype=np.float32)
    
    def get_latest_speeds(self):
        """Get latest speed data as dict"""
        with self.lock:
            if len(self.history) > 0:
                _, speeds = self.history[-1]
                return {street_id: float(speeds[node_id]) 
                       for street_id, node_id in STREET_TO_NODE.items()}
            return {}

# ============================================================================
# TRAFFIC PREDICTOR
# ============================================================================

class TrafficPredictor:
    """Handles traffic prediction using GAT model"""
    
    def __init__(self, model_path, scaler_path, num_nodes, device):
        self.num_nodes = num_nodes
        self.device = device
        
        # Load scaler
        logger.info(f"Loading scaler from {scaler_path}")
        self.scaler = joblib.load(scaler_path)
        
        # Load model
        logger.info(f"Loading model from {model_path}")
        self.model = SpatioTemporalGAT(
            num_nodes=num_nodes,
            in_dim=1,
            hidden=HIDDEN_DIM,
            heads=NUM_HEADS,
            horizon=PRED_HORIZON,
            dropout=DROPOUT
        ).to(device)
        
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        if 'model_state_dict' in checkpoint:
            self.model.load_state_dict(checkpoint['model_state_dict'])
        else:
            self.model.load_state_dict(checkpoint)
        
        self.model.eval()
        
        # Load adjacency matrix
        logger.info("Loading adjacency matrix")
        with open('adj_METR-LA.pkl', 'rb') as f:
            adj_data = pickle.load(f, encoding='latin1')
        
        if isinstance(adj_data, (list, tuple)) and len(adj_data) > 2:
            adj = adj_data[2]
        elif isinstance(adj_data, dict):
            adj = adj_data.get("adj_mx", list(adj_data.values())[0])
        else:
            adj = adj_data
        
        self.adj = adj.astype(np.float32)
        self.edge_index, _ = dense_to_sparse(torch.tensor(self.adj, dtype=torch.float32))
        self.edge_index = self.edge_index.to(device)
        
        logger.info(f"TrafficPredictor initialized on {device}")
        logger.info(f"  Nodes: {num_nodes}")
        logger.info(f"  Edges: {self.edge_index.shape[1]}")
    
    def predict(self, history):
        """
        Predict future traffic
        
        Args:
            history: (W, N) array of historical speeds
        
        Returns:
            predictions: (H, N) array of predicted speeds
        """
        # Normalize
        history_norm = self.scaler.transform(history)
        
        # Convert to tensor
        x = torch.tensor(history_norm, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        # Predict
        with torch.no_grad():
            pred = self.model(x, self.edge_index)  # (1, H, N)
        
        # Denormalize
        pred_np = pred.cpu().numpy()[0]  # (H, N)
        
        predictions = []
        for h in range(PRED_HORIZON):
            pred_denorm = self.scaler.inverse_transform(pred_np[h:h+1, :])[0]
            predictions.append(pred_denorm)
        
        predictions = np.array(predictions)  # (H, N)
        
        logger.info(f"Predictions: shape={predictions.shape}, range=[{predictions.min():.1f}, {predictions.max():.1f}]")
        
        return predictions

# ============================================================================
# A* PATHFINDING
# ============================================================================

class AStarRouter:
    """A* pathfinding with traffic-aware costs"""
    
    def __init__(self, adjacency, node_positions=None):
        self.adjacency = adjacency
        self.node_positions = node_positions or self._generate_default_positions()
        logger.info(f"AStarRouter initialized with {len(adjacency)} nodes")
    
    def _generate_default_positions(self):
        """Generate default grid positions for heuristic"""
        positions = {}
        for i, node in enumerate(sorted(self.adjacency.keys())):
            positions[node] = (i % 10, i // 10)
        return positions
    
    def euclidean_distance(self, a, b):
        """Calculate Euclidean distance between two nodes"""
        pos_a = self.node_positions[a]
        pos_b = self.node_positions[b]
        return ((pos_a[0] - pos_b[0])**2 + (pos_a[1] - pos_b[1])**2)**0.5
    
    def calculate_edge_cost(self, from_node, to_node, predicted_speeds):
        """
        Calculate cost of edge based on predicted traffic
        Lower speed = higher cost (longer travel time)
        """
        if from_node not in STREET_TO_NODE or to_node not in STREET_TO_NODE:
            return 1.0  # Default cost
        
        from_idx = STREET_TO_NODE[from_node]
        to_idx = STREET_TO_NODE[to_node]
        
        # Average speed on both nodes
        avg_speed = (predicted_speeds[from_idx] + predicted_speeds[to_idx]) / 2
        
        # Avoid division by zero
        if avg_speed < 5.0:
            avg_speed = 5.0
        
        # Cost is inversely proportional to speed
        # Also include distance component
        distance = self.euclidean_distance(from_node, to_node)
        time_cost = distance / avg_speed
        
        return time_cost
    
    def find_path(self, start, goal, predicted_speeds):
        """
        Find optimal path using A* algorithm
        
        Args:
            start: Starting node
            goal: Goal node
            predicted_speeds: (N,) array of predicted speeds for next timestep
        
        Returns:
            path: List of nodes in optimal path
            total_cost: Total cost of path
        """
        if start not in self.adjacency or goal not in self.adjacency:
            logger.error(f"Invalid start ({start}) or goal ({goal})")
            return None, float('inf')
        
        # Priority queue: (f_score, node, path)
        open_set = [(0, start, [start])]
        closed_set = set()
        
        # g_score: cost from start to node
        g_score = {start: 0}
        
        # f_score: estimated total cost from start to goal through node
        h = self.euclidean_distance(start, goal)
        f_score = {start: h}
        
        while open_set:
            current_f, current, path = heapq.heappop(open_set)
            
            if current == goal:
                logger.info(f"Path found: {' -> '.join(path)} (cost: {current_f:.2f})")
                return path, current_f
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            
            # Explore neighbors
            for neighbor in self.adjacency[current]:
                if neighbor in closed_set:
                    continue
                
                # Calculate cost to neighbor
                edge_cost = self.calculate_edge_cost(current, neighbor, predicted_speeds)
                tentative_g = g_score[current] + edge_cost
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    h = self.euclidean_distance(neighbor, goal)
                    f_score[neighbor] = tentative_g + h
                    
                    new_path = path + [neighbor]
                    heapq.heappush(open_set, (f_score[neighbor], neighbor, new_path))
        
        logger.warning(f"No path found from {start} to {goal}")
        return None, float('inf')

# ============================================================================
# FLASK SERVER
# ============================================================================

class TrafficServer:
    """Main Flask server for handling requests"""
    
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        
        # Initialize components
        self.data_manager = TrafficDataManager(NUM_NODES, INPUT_WINDOW)
        self.predictor = TrafficPredictor(MODEL_PATH, SCALER_PATH, NUM_NODES, DEVICE)
        self.router = AStarRouter(STREET_ADJACENCY)
        
        # Latest predictions
        self.latest_predictions = None
        self.predictions_lock = Lock()
        
        # Setup routes
        self._setup_routes()
        
        # Start background update thread
        self.update_thread = Thread(target=self._background_updates, daemon=True)
        self.update_thread.start()
        
        logger.info("TrafficServer initialized")
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/ping', methods=['GET'])
        def ping():
            """Health check endpoint"""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'message': 'Raspberry Pi Traffic Server is running'
            })
        
        @self.app.route('/speed', methods=['POST'])
        def receive_speed():
            """Receive speed data from car"""
            try:
                data = request.get_json()
                speed = data.get('speed', 0)
                timestamp = data.get('timestamp')
                street_id = data.get('street_id', 'A')  # Default to A if not provided
                car_count = data.get('car_count', 1)
                
                success = self.data_manager.add_speed_data(street_id, speed, car_count)
                
                if success:
                    return jsonify({
                        'status': 'success',
                        'message': f'Speed data received for street {street_id}'
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid street ID'
                    }), 400
                    
            except Exception as e:
                logger.error(f"Error receiving speed: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/location', methods=['POST'])
        def receive_location():
            """Receive location update from car"""
            try:
                data = request.get_json()
                latitude = data.get('latitude')
                longitude = data.get('longitude')
                timestamp = data.get('timestamp')
                
                # Map location to street (simplified - implement proper logic)
                # For now, just acknowledge
                
                logger.info(f"Location received: ({latitude}, {longitude})")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Location received'
                }), 200
                
            except Exception as e:
                logger.error(f"Error receiving location: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/traffic', methods=['GET'])
        def get_traffic():
            """Get current traffic data and predictions"""
            try:
                # Get latest speeds
                current_speeds = self.data_manager.get_latest_speeds()
                
                # Get predictions
                with self.predictions_lock:
                    predictions = self.latest_predictions
                
                if predictions is not None:
                    # Convert predictions to street-based dict
                    pred_dict = {}
                    for street_id, node_id in STREET_TO_NODE.items():
                        pred_dict[street_id] = {
                            'current': float(current_speeds.get(street_id, 50.0)),
                            'predicted_5min': float(predictions[0, node_id]),
                            'predicted_10min': float(predictions[1, node_id]),
                            'predicted_15min': float(predictions[2, node_id])
                        }
                    
                    return jsonify({
                        'status': 'success',
                        'timestamp': datetime.now().isoformat(),
                        'traffic': pred_dict
                    }), 200
                else:
                    return jsonify({
                        'status': 'success',
                        'timestamp': datetime.now().isoformat(),
                        'traffic': current_speeds,
                        'message': 'Predictions not yet available'
                    }), 200
                    
            except Exception as e:
                logger.error(f"Error getting traffic: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/route', methods=['POST'])
        def calculate_route():
            """Calculate optimal route using A* and traffic predictions"""
            try:
                data = request.get_json()
                start = data.get('start', 'A')
                goal = data.get('goal', 'T')
                
                # Get latest predictions
                with self.predictions_lock:
                    predictions = self.latest_predictions
                
                if predictions is None:
                    # Use current speeds if no predictions
                    history = self.data_manager.get_history_array()
                    if history.shape[0] == INPUT_WINDOW:
                        predictions = self.predictor.predict(history)
                        with self.predictions_lock:
                            self.latest_predictions = predictions
                    else:
                        return jsonify({
                            'status': 'error',
                            'message': 'Not enough data for predictions yet'
                        }), 400
                
                # Use first prediction timestep (5 min ahead)
                predicted_speeds = predictions[0, :]
                
                # Find optimal path
                path, cost = self.router.find_path(start, goal, predicted_speeds)
                
                if path:
                    # Calculate travel time estimate
                    total_distance = len(path) - 1
                    avg_speed = np.mean([predicted_speeds[STREET_TO_NODE[node]] 
                                       for node in path if node in STREET_TO_NODE])
                    estimated_time = (total_distance / avg_speed) * 60  # minutes
                    
                    return jsonify({
                        'status': 'success',
                        'route': {
                            'path': path,
                            'cost': float(cost),
                            'distance': total_distance,
                            'estimated_time_minutes': float(estimated_time),
                            'avg_speed_kmh': float(avg_speed)
                        },
                        'timestamp': datetime.now().isoformat()
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'message': f'No path found from {start} to {goal}'
                    }), 404
                    
            except Exception as e:
                logger.error(f"Error calculating route: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        @self.app.route('/user', methods=['POST'])
        def receive_user_data():
            """Receive user/car data"""
            try:
                data = request.get_json()
                logger.info(f"User data received: {data}")
                
                return jsonify({
                    'status': 'success',
                    'message': 'User data received'
                }), 200
                
            except Exception as e:
                logger.error(f"Error receiving user data: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
    
    def _background_updates(self):
        """Background thread for periodic updates"""
        logger.info("Background update thread started")
        
        while True:
            try:
                time.sleep(UPDATE_INTERVAL)
                
                # Aggregate current data
                self.data_manager.aggregate_and_update()
                
                # Get history
                history = self.data_manager.get_history_array()
                
                # Make predictions if we have enough data
                if history.shape[0] == INPUT_WINDOW:
                    logger.info("Making traffic predictions...")
                    predictions = self.predictor.predict(history)
                    
                    with self.predictions_lock:
                        self.latest_predictions = predictions
                    
                    logger.info(f"Predictions updated: {predictions.shape}")
                else:
                    logger.info(f"Not enough data yet: {history.shape[0]}/{INPUT_WINDOW}")
                
            except Exception as e:
                logger.error(f"Error in background update: {e}")
    
    def run(self):
        """Run the Flask server"""
        logger.info(f"Starting server on {HOST}:{PORT}")
        self.app.run(host=HOST, port=PORT, debug=False, threaded=True)

# ============================================================================
# HOTSPOT SETUP
# ============================================================================

def setup_hotspot():
    """Setup WiFi hotspot on Raspberry Pi"""
    logger.info("Setting up WiFi hotspot...")
    
    try:
        # Check if running on Raspberry Pi
        if not os.path.exists('/proc/device-tree/model'):
            logger.warning("Not running on Raspberry Pi - skipping hotspot setup")
            return
        
        # Install required packages
        logger.info("Installing required packages...")
        subprocess.run(['sudo', 'apt-get', 'update'], check=False)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'hostapd', 'dnsmasq'], check=False)
        
        # Stop services
        subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], check=False)
        subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq'], check=False)
        
        # Configure dhcpcd
        logger.info("Configuring network...")
        dhcpcd_config = """
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
"""
        with open('/tmp/dhcpcd.conf', 'w') as f:
            f.write(dhcpcd_config)
        
        subprocess.run(['sudo', 'cp', '/tmp/dhcpcd.conf', '/etc/dhcpcd.conf'], check=False)
        
        # Configure dnsmasq
        dnsmasq_config = """
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
"""
        with open('/tmp/dnsmasq.conf', 'w') as f:
            f.write(dnsmasq_config)
        
        subprocess.run(['sudo', 'cp', '/tmp/dnsmasq.conf', '/etc/dnsmasq.conf'], check=False)
        
        # Configure hostapd
        hostapd_config = f"""
interface=wlan0
driver=nl80211
ssid={HOTSPOT_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={HOTSPOT_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
        with open('/tmp/hostapd.conf', 'w') as f:
            f.write(hostapd_config)
        
        subprocess.run(['sudo', 'cp', '/tmp/hostapd.conf', '/etc/hostapd/hostapd.conf'], check=False)
        
        # Update hostapd defaults
        with open('/tmp/hostapd', 'w') as f:
            f.write('DAEMON_CONF="/etc/hostapd/hostapd.conf"\n')
        
        subprocess.run(['sudo', 'cp', '/tmp/hostapd', '/etc/default/hostapd'], check=False)
        
        # Enable IP forwarding
        subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'], check=False)
        
        # Start services
        logger.info("Starting hotspot services...")
        subprocess.run(['sudo', 'systemctl', 'unmask', 'hostapd'], check=False)
        subprocess.run(['sudo', 'systemctl', 'enable', 'hostapd'], check=False)
        subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], check=False)
        subprocess.run(['sudo', 'systemctl', 'restart', 'dnsmasq'], check=False)
        
        logger.info(f"✓ Hotspot '{HOTSPOT_SSID}' created successfully!")
        logger.info(f"  IP: 192.168.4.1")
        logger.info(f"  Password: {HOTSPOT_PASSWORD}")
        
    except Exception as e:
        logger.error(f"Error setting up hotspot: {e}")
        logger.warning("Continuing without hotspot - you can connect via existing network")

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    print("="*80)
    print(" "*15 + "RASPBERRY PI TRAFFIC PREDICTION SERVER")
    print("="*80)
    print()
    
    # Check if model files exist
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model file not found: {MODEL_PATH}")
        logger.error("Please place the trained model in the current directory")
        sys.exit(1)
    
    if not os.path.exists(SCALER_PATH):
        logger.error(f"Scaler file not found: {SCALER_PATH}")
        logger.error("Please place the scaler in the current directory")
        sys.exit(1)
    
    # Setup hotspot (optional - will skip if not on Raspberry Pi)
    setup_hotspot()
    
    # Create and run server
    try:
        server = TrafficServer()
        logger.info("\n" + "="*80)
        logger.info("🚀 Server ready!")
        logger.info("="*80)
        logger.info(f"  Connect to WiFi: {HOTSPOT_SSID}")
        logger.info(f"  Server URL: http://192.168.4.1:{PORT}")
        logger.info(f"  Flutter app should connect automatically")
        logger.info("="*80 + "\n")
        
        server.run()
        
    except KeyboardInterrupt:
        logger.info("\n\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
