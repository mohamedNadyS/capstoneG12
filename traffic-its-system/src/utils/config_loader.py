"""
Configuration Loader Utility
Loads and validates YAML configuration files
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Load and manage system configurations"""
    
    def __init__(self, config_dir: str = "./configs"):
        self.config_dir = Path(config_dir)
        self._configs = {}
        
    def load(self, config_name: str) -> Dict[str, Any]:
        """
        Load a configuration file
        
        Args:
            config_name: Name of config file (without .yaml extension)
            
        Returns:
            Dictionary containing configuration
        """
        if config_name in self._configs:
            return self._configs[config_name]
            
        config_path = self.config_dir / f"{config_name}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        self._configs[config_name] = config
        return config
    
    def load_system_config(self) -> Dict[str, Any]:
        """Load main system configuration"""
        return self.load("system_config")
    
    def load_traffic_config(self) -> Dict[str, Any]:
        """Load traffic generation configuration"""
        return self.load("traffic_generation")
    
    def get(self, config_name: str, key_path: str, default=None):
        """
        Get a specific value from config using dot notation
        
        Example:
            config.get('system_config', 'sumo.net_file')
        """
        config = self.load(config_name)
        
        keys = key_path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value


# Global config loader instance
_config_loader = None

def get_config_loader(config_dir: str = "./configs") -> ConfigLoader:
    """Get global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
    return _config_loader
