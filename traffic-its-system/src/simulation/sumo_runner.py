"""
SUMO Simulation Runner
Launch and manage SUMO/SUMO-GUI simulations
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict
import platform
import shutil


class SUMORunner:
    """
    SUMO simulation runner and manager
    """
    
    def __init__(self):
        """Initialize SUMO runner"""
        self.sumo_binary = None
        self.sumo_gui_binary = None
        self.sumo_home = None
        
        # Detect SUMO installation
        self._detect_sumo()
        
        print(f"\n[SUMO] SUMO Runner initialized")
        if self.sumo_home:
            print(f"   SUMO_HOME: {self.sumo_home}")
        if self.sumo_gui_binary:
            print(f"   SUMO-GUI: Found")
        if self.sumo_binary:
            print(f"   SUMO: Found")
    
    def _detect_sumo(self):
        """Detect SUMO installation"""
        import os
        
        # Check SUMO_HOME environment variable
        self.sumo_home = os.environ.get('SUMO_HOME')
        
        # Try to find SUMO binaries
        if platform.system() == 'Windows':
            sumo_names = ['sumo.exe', 'sumo']
            sumo_gui_names = ['sumo-gui.exe', 'sumo-gui']
        else:
            sumo_names = ['sumo']
            sumo_gui_names = ['sumo-gui']
        
        # Try common locations
        search_paths = []
        if self.sumo_home:
            search_paths.append(Path(self.sumo_home) / 'bin')
        
        # Add system PATH
        path_env = os.environ.get('PATH', '').split(os.pathsep)
        search_paths.extend([Path(p) for p in path_env])
        
        # Search for binaries
        for path in search_paths:
            if not path.exists():
                continue
            
            # Look for sumo-gui
            for name in sumo_gui_names:
                binary = path / name
                if binary.exists() or shutil.which(str(binary)):
                    self.sumo_gui_binary = str(binary)
                    break
            
            # Look for sumo
            for name in sumo_names:
                binary = path / name
                if binary.exists() or shutil.which(str(binary)):
                    self.sumo_binary = str(binary)
                    break
            
            if self.sumo_gui_binary and self.sumo_binary:
                break
        
        # Try system-wide
        if not self.sumo_gui_binary:
            self.sumo_gui_binary = shutil.which('sumo-gui')
        if not self.sumo_binary:
            self.sumo_binary = shutil.which('sumo')
    
    def check_installation(self) -> Dict:
        """
        Check SUMO installation status
        
        Returns:
            Dictionary with installation info
        """
        status = {
            'sumo_home': self.sumo_home,
            'sumo_found': self.sumo_binary is not None,
            'sumo_gui_found': self.sumo_gui_binary is not None,
            'sumo_path': self.sumo_binary,
            'sumo_gui_path': self.sumo_gui_binary,
            'ready': False
        }
        
        if self.sumo_gui_binary or self.sumo_binary:
            status['ready'] = True
        
        return status
    
    def run_gui(
        self,
        config_file: str,
        start_immediately: bool = False,
        quit_on_end: bool = False,
        delay: int = 100,
        additional_options: Optional[Dict] = None
    ) -> int:
        """
        Run SUMO-GUI simulation
        
        Args:
            config_file: Path to .sumocfg file
            start_immediately: Start simulation without user interaction
            quit_on_end: Quit GUI when simulation ends
            delay: Delay between simulation steps (ms)
            additional_options: Additional SUMO options
            
        Returns:
            Exit code
        """
        if not self.sumo_gui_binary:
            raise RuntimeError(
                "SUMO-GUI not found. Please install SUMO:\n"
                "  Windows: https://sumo.dlr.de/docs/Downloads.php\n"
                "  Linux: sudo apt-get install sumo sumo-tools sumo-doc\n"
                "  Mac: brew install sumo"
            )
        
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        print(f"\n[SUMO] Launching SUMO-GUI...")
        print(f"   Config: {config_file}")
        print(f"   Binary: {self.sumo_gui_binary}")
        
        # Build command
        cmd = [self.sumo_gui_binary, '-c', str(config_file)]
        
        # Add options
        if start_immediately:
            cmd.append('--start')
        if quit_on_end:
            cmd.append('--quit-on-end')
        if delay:
            cmd.extend(['--delay', str(delay)])
        
        # Additional options
        if additional_options:
            for key, value in additional_options.items():
                if value is True:
                    cmd.append(f'--{key}')
                elif value is not False and value is not None:
                    cmd.extend([f'--{key}', str(value)])
        
        print(f"   Command: {' '.join(cmd)}")
        print(f"\n   [OK] Starting SUMO-GUI...")
        print(f"   Use GUI controls to start/pause/stop simulation")
        print(f"   Close GUI window when done\n")
        
        # Run SUMO-GUI
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"\n   [ERROR] SUMO-GUI exited with error: {e.returncode}")
            return e.returncode
        except KeyboardInterrupt:
            print(f"\n   [INFO] Simulation interrupted by user")
            return 130
    
    def run_headless(
        self,
        config_file: str,
        output_file: Optional[str] = None,
        verbose: bool = False,
        additional_options: Optional[Dict] = None
    ) -> int:
        """
        Run SUMO simulation without GUI (headless)
        
        Args:
            config_file: Path to .sumocfg file
            output_file: Path to output statistics file
            verbose: Print detailed output
            additional_options: Additional SUMO options
            
        Returns:
            Exit code
        """
        if not self.sumo_binary:
            raise RuntimeError("SUMO (headless) not found. Please install SUMO.")
        
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        print(f"\n[SUMO] Running headless simulation...")
        print(f"   Config: {config_file}")
        
        # Build command
        cmd = [self.sumo_binary, '-c', str(config_file)]
        
        # Add options
        if output_file:
            cmd.extend(['--statistic-output', str(output_file)])
        if verbose:
            cmd.append('--verbose')
        
        # Additional options
        if additional_options:
            for key, value in additional_options.items():
                if value is True:
                    cmd.append(f'--{key}')
                elif value is not False and value is not None:
                    cmd.extend([f'--{key}', str(value)])
        
        print(f"   Running simulation...")
        
        # Run SUMO
        try:
            result = subprocess.run(cmd, check=True, capture_output=not verbose)
            print(f"   [OK] Simulation completed successfully")
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"\n   [ERROR] Simulation failed: {e.returncode}")
            if e.stderr:
                print(f"   Error output: {e.stderr.decode()}")
            return e.returncode
    
    def get_simulation_info(self, config_file: str) -> Dict:
        """
        Extract simulation information from config file
        
        Args:
            config_file: Path to .sumocfg file
            
        Returns:
            Dictionary with simulation info
        """
        import xml.etree.ElementTree as ET
        
        config_path = Path(config_file)
        if not config_path.exists():
            return {}
        
        tree = ET.parse(config_file)
        root = tree.getroot()
        
        info = {}
        
        # Get input files
        input_elem = root.find('input')
        if input_elem is not None:
            net_elem = input_elem.find('net-file')
            if net_elem is not None:
                info['network_file'] = net_elem.get('value')
            
            route_elem = input_elem.find('route-files')
            if route_elem is not None:
                info['route_file'] = route_elem.get('value')
        
        # Get time settings
        time_elem = root.find('time')
        if time_elem is not None:
            begin_elem = time_elem.find('begin')
            if begin_elem is not None:
                info['begin_time'] = int(begin_elem.get('value', 0))
            
            end_elem = time_elem.find('end')
            if end_elem is not None:
                info['end_time'] = int(end_elem.get('value', 3600))
            
            step_elem = time_elem.find('step-length')
            if step_elem is not None:
                info['step_length'] = float(step_elem.get('value', 1.0))
        
        # Calculate duration
        if 'begin_time' in info and 'end_time' in info:
            info['duration'] = info['end_time'] - info['begin_time']
        
        return info


if __name__ == "__main__":
    print("="*70)
    print("SUMO SIMULATION RUNNER TEST")
    print("="*70)
    
    runner = SUMORunner()
    status = runner.check_installation()
    
    print("\nInstallation Status:")
    print(f"  SUMO_HOME: {status['sumo_home'] or 'Not set'}")
    print(f"  SUMO found: {status['sumo_found']}")
    print(f"  SUMO-GUI found: {status['sumo_gui_found']}")
    
    if status['ready']:
        print(f"\n  [OK] SUMO is ready to use!")
    else:
        print(f"\n  [WARNING] SUMO not found. Please install SUMO:")
        print(f"    Windows: https://sumo.dlr.de/docs/Downloads.php")
        print(f"    Linux: sudo apt-get install sumo sumo-tools")
        print(f"    Mac: brew install sumo")
