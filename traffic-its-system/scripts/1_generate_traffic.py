#!/usr/bin/env python3
"""
Traffic Generation Script
User-facing script to generate synthetic traffic scenarios

Usage:
    python scripts/1_generate_traffic.py --congestion 0.5 --vehicles 500
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import get_config_loader
from src.utils.logger import get_logger
from src.sumo_integration.sumo_parser import SUMONetworkParser
from src.data_generation.traffic_generator import TrafficGenerator


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate synthetic traffic scenario for ITS simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate light traffic (10% congestion, 200 vehicles)
  python scripts/1_generate_traffic.py --congestion 0.1 --vehicles 200 --scenario free_flow
  
  # Generate rush hour traffic (60% congestion, 1000 vehicles)
  python scripts/1_generate_traffic.py --congestion 0.6 --vehicles 1000 --scenario rush_hour
  
  # Generate heavy jam (90% congestion, 1500 vehicles)
  python scripts/1_generate_traffic.py --congestion 0.9 --vehicles 1500 --scenario heavy_jam
        """
    )
    
    parser.add_argument(
        '--net-file',
        type=str,
        default=None,
        help='Path to SUMO network file (.net.xml). Default: from config'
    )
    
    parser.add_argument(
        '--congestion',
        type=float,
        required=True,
        help='Congestion level (0.0 = free flow, 1.0 = jammed)'
    )
    
    parser.add_argument(
        '--vehicles',
        type=int,
        required=True,
        help='Number of vehicles to generate'
    )
    
    parser.add_argument(
        '--scenario',
        type=str,
        default='normal',
        choices=['free_flow', 'normal', 'rush_hour', 'heavy_jam'],
        help='Scenario type (default: normal)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for generated files. Default: from config'
    )
    
    parser.add_argument(
        '--emergency-ratio',
        type=float,
        default=None,
        help='Ratio of emergency vehicles (0.0 - 1.0). Default: from config'
    )
    
    parser.add_argument(
        '--variable-pattern',
        type=str,
        default=None,
        choices=['morning_rush', 'incident', 'gradual', 'variable', 'mixed'],
        help='Use variable traffic pattern (challenges prediction model)'
    )
    
    return parser.parse_args()


def validate_inputs(args):
    """Validate user inputs"""
    errors = []
    
    if not (0.0 <= args.congestion <= 1.0):
        errors.append(f"Congestion must be between 0.0 and 1.0, got {args.congestion}")
    
    if args.vehicles < 1:
        errors.append(f"Number of vehicles must be positive, got {args.vehicles}")
    
    if args.emergency_ratio is not None and not (0.0 <= args.emergency_ratio <= 1.0):
        errors.append(f"Emergency ratio must be between 0.0 and 1.0, got {args.emergency_ratio}")
    
    if errors:
        print("❌ Input validation errors:")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)


def main():
    """Main function"""
    args = parse_arguments()
    validate_inputs(args)
    
    # Load configurations
    config_loader = get_config_loader()
    system_config = config_loader.load_system_config()
    traffic_config = config_loader.load_traffic_config()
    
    # Setup logger
    logger = get_logger(
        name="TrafficGen",
        log_file=system_config['logging']['file'],
        level=system_config['logging']['level']
    )
    
    logger.info("="*70)
    logger.info("ITS TRAFFIC GENERATION")
    logger.info("="*70)
    
    # Determine paths
    if args.net_file:
        net_file = args.net_file
    else:
        sumo_dir = system_config['paths']['sumo_dir']
        net_file = f"{sumo_dir}/{system_config['sumo']['net_file']}"
    
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = system_config['paths']['generated_dir']
    
    logger.info(f"Network file: {net_file}")
    logger.info(f"Output directory: {output_dir}")
    logger.info("")
    
    # Check if network file exists
    if not Path(net_file).exists():
        logger.error(f"Network file not found: {net_file}")
        logger.error("Please provide a valid SUMO network file (.net.xml)")
        sys.exit(1)
    
    try:
        # Step 1: Parse SUMO network
        logger.info("[Step 1/3] Parsing SUMO network...")
        parser = SUMONetworkParser(net_file)
        parser.print_summary()
        
        # Step 2: Create traffic generator
        logger.info("[Step 2/3] Initializing traffic generator...")
        
        # Merge configs
        generator_config = {
            **traffic_config['generation'],
            **traffic_config['speed_generation'],
            **traffic_config['vehicle_distribution']
        }
        
        if args.emergency_ratio is not None:
            generator_config['emergency_vehicle_ratio'] = args.emergency_ratio
        
        generator = TrafficGenerator(parser, generator_config)
        
        # Step 3: Generate scenario
        logger.info("[Step 3/3] Generating traffic scenario...")
        logger.info("")
        
        scenario = generator.generate_traffic_scenario(
            num_vehicles=args.vehicles,
            congestion_level=args.congestion,
            scenario_type=args.scenario,
            output_dir=output_dir,
            variable_pattern=args.variable_pattern
        )
        
        # Summary
        logger.info("📊 Scenario Summary:")
        logger.info(f"   • Vehicles: {len(scenario['vehicles'])}")
        logger.info(f"   • Edges with traffic: {len(scenario['edge_states'])}")
        logger.info(f"   • Speed history timesteps: {len(next(iter(scenario['speed_history'].values()))['speeds'])}")
        logger.info("")
        logger.info("✅ Traffic generation completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run GNN prediction: python scripts/2_run_prediction.py")
        logger.info("  2. Generate routes: python scripts/3_generate_routes.py")
        logger.info("  3. Run SUMO simulation: python scripts/4_run_sumo_gui.py")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Error during traffic generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
