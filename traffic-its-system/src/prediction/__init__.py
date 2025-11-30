"""
Traffic Speed Prediction Module
GNN-based prediction with SUMO network integration
"""

from .gnn_predictor import GNNTrafficPredictor, SpatioTemporalGAT
from .speed_mapper import SpeedMapper, create_sumo_to_gnn_mapping
from .prediction_pipeline import TrafficPredictionPipeline

__all__ = [
    'GNNTrafficPredictor',
    'SpatioTemporalGAT',
    'SpeedMapper',
    'create_sumo_to_gnn_mapping',
    'TrafficPredictionPipeline'
]
