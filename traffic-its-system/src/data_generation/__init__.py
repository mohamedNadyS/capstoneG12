"""
Traffic Data Generation Module
Generates synthetic traffic scenarios for simulation
"""

from .traffic_generator import TrafficGenerator, Vehicle, EdgeState
from .speed_history_generator import SpeedHistoryGenerator, SpeedTimeSeries

__all__ = [
    'TrafficGenerator',
    'Vehicle',
    'EdgeState',
    'SpeedHistoryGenerator',
    'SpeedTimeSeries'
]
