#!/usr/bin/env python3
"""
SUMO-GUI Simulation Launcher
Launch and manage SUMO simulations with visualization

Usage:
    python scripts/4_run_sumo_gui.py --config data/generated/simulation.sumocfg
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import get_config_loader
from src.utils.logger import get_logger
from src.simulation.sumo_runner import SUMORunner
from src.simulation.metrics_collector import MetricsCollector


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Launch SUMO-GUI simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch GUI
  python scripts/4_run_sumo_gui.py --config data/generated/simulation.sumocfg
  
  # Start simulation immediately
  python scripts/4_run_sumo_gui.py \\
      --config data/generated/simulation.sumocfg \\
      --start
  
  # Headless mode (no GUI) with metrics
  python scripts/4_run_sumo_gui.py \\
      --config data/generated/simulation.sumocfg \\
      --headless \\
      --collect-metrics
  
  # Custom delay
  python scripts/4_run_sumo_gui.py \\
      --config data/generated/simulation.sumocfg \\
      --delay 50
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to SUMO configuration file (.sumocfg)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run without GUI (headless mode)'
    )
    
    parser.add_argument(
        '--start',
        action='store_true',
        help='Start simulation immediately (GUI mode)'
    )
    
    parser.add_argument(
        '--quit-on-end',
        action='store_true',
        help='Quit GUI when simulation ends'
    )
    
    parser.add_argument(
        '--delay',
        type=int,
        default=100,
        help='Delay between simulation steps in ms (default: 100)'
    )
    
    parser.add_argument(
        '--collect-metrics',
        action='store_true',
        help='Collect and save simulation metrics'
    )
    
    parser.add_argument(
        '--tripinfo-output',
        type=str,
        default=None,
        help='Path to save tripinfo.xml (for metrics collection)'
    )
    
    parser.add_argument(
        '--metrics-output',
        type=str,
        default=None,
        help='Path to save metrics JSON file'
    )
    
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_arguments()
    
    # Load configurations
    config_loader = get_config_loader()
    system_config = config_loader.load_system_config()
    
    # Setup logger
    logger = get_logger(
        name="SUMO",
        log_file=system_config['logging']['file'],
        level=system_config['logging']['level']
    )
    
    logger.info("="*70)
    logger.info("ITS SUMO SIMULATION")
    logger.info("="*70)
    
    # Check config file
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {args.config}")
        logger.error("Generate routes first: python scripts/3_generate_routes.py")
        sys.exit(1)
    
    logger.info(f"\nConfiguration:")
    logger.info(f"   Config: {args.config}")
    logger.info(f"   Mode: {'Headless' if args.headless else 'GUI'}")
    logger.info(f"   Collect metrics: {args.collect_metrics}")
    logger.info("")
    
    try:
        # Initialize SUMO runner
        logger.info("[Step 1/3] Initializing SUMO...")
        runner = SUMORunner()
        
        # Check installation
        status = runner.check_installation()
        if not status['ready']:
            logger.error("SUMO not found!")
            logger.error("")
            logger.error("Please install SUMO:")
            logger.error("  Windows: https://sumo.dlr.de/docs/Downloads.php")
            logger.error("  Linux: sudo apt-get install sumo sumo-tools sumo-doc")
            logger.error("  Mac: brew install sumo")
            logger.error("")
            logger.error("After installation, set SUMO_HOME environment variable")
            sys.exit(1)
        
        logger.info(f"   [OK] SUMO installation found")
        if status['sumo_home']:
            logger.info(f"   SUMO_HOME: {status['sumo_home']}")
        
        # Get simulation info
        sim_info = runner.get_simulation_info(args.config)
        if sim_info:
            logger.info(f"\n   Simulation info:")
            logger.info(f"      Duration: {sim_info.get('duration', 'Unknown')} seconds")
            logger.info(f"      Network: {sim_info.get('network_file', 'Unknown')}")
            logger.info(f"      Routes: {sim_info.get('route_file', 'Unknown')}")
        
        # Prepare additional options
        additional_options = {}
        
        # Add tripinfo output if collecting metrics
        if args.collect_metrics:
            if args.tripinfo_output:
                tripinfo_file = args.tripinfo_output
            else:
                tripinfo_file = str(config_path.parent / "tripinfo.xml")
            
            additional_options['tripinfo-output'] = tripinfo_file
            logger.info(f"\n   Tripinfo output: {tripinfo_file}")
        
        # Step 2: Run simulation
        logger.info(f"\n[Step 2/3] Running simulation...")
        
        if args.headless:
            # Headless mode
            logger.info(f"   Mode: Headless (no GUI)")
            exit_code = runner.run_headless(
                config_file=args.config,
                verbose=True,
                additional_options=additional_options
            )
        else:
            # GUI mode
            logger.info(f"   Mode: GUI")
            logger.info(f"   Starting SUMO-GUI...")
            logger.info(f"   Use GUI controls to:")
            logger.info(f"      • Start/pause/stop simulation")
            logger.info(f"      • Adjust simulation speed")
            logger.info(f"      • View vehicle routes")
            logger.info(f"      • Monitor traffic flow")
            logger.info("")
            
            exit_code = runner.run_gui(
                config_file=args.config,
                start_immediately=args.start,
                quit_on_end=args.quit_on_end,
                delay=args.delay,
                additional_options=additional_options
            )
        
        if exit_code != 0:
            logger.error(f"\n   [ERROR] Simulation exited with code: {exit_code}")
            sys.exit(exit_code)
        
        # Step 3: Collect metrics (if requested)
        if args.collect_metrics:
            logger.info(f"\n[Step 3/3] Collecting metrics...")
            
            tripinfo_file = additional_options.get('tripinfo-output')
            if not tripinfo_file or not Path(tripinfo_file).exists():
                logger.warning(f"   Tripinfo file not found: {tripinfo_file}")
                logger.warning(f"   Skipping metrics collection")
            else:
                collector = MetricsCollector()
                
                # Parse tripinfo
                vehicle_metrics = collector.parse_tripinfo(tripinfo_file)
                
                # Calculate overall metrics
                duration = sim_info.get('duration', 3600) if sim_info else 3600
                metrics = collector.calculate_metrics(vehicle_metrics, duration)
                
                # Print metrics
                collector.print_metrics(metrics)
                
                # Save metrics
                if args.metrics_output:
                    metrics_file = args.metrics_output
                else:
                    metrics_file = str(config_path.parent / "simulation_metrics.json")
                
                collector.save_metrics(metrics, vehicle_metrics, metrics_file)
        else:
            logger.info(f"\n[Step 3/3] Skipping metrics collection")
            logger.info(f"   Use --collect-metrics to enable")
        
        logger.info(f"\n[OK] Simulation completed successfully!")
        logger.info("")
        
        if args.collect_metrics:
            logger.info("Generated files:")
            logger.info(f"   Tripinfo: {tripinfo_file}")
            if 'metrics_file' in locals():
                logger.info(f"   Metrics: {metrics_file}")
        
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Analyze metrics: python scripts/5_analyze_results.py")
        logger.info("  2. Generate report: python scripts/6_generate_report.py")
        logger.info("")
        
    except Exception as e:
        logger.error(f"[ERROR] Error during simulation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
