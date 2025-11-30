#!/usr/bin/env python3
"""
Traffic Speed Prediction Script
Runs GNN prediction on generated traffic scenarios

Usage:
    python scripts/2_run_prediction.py --scenario data/generated
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import get_config_loader
from src.utils.logger import get_logger
from src.sumo_integration.sumo_parser import SUMONetworkParser
from src.prediction.prediction_pipeline import TrafficPredictionPipeline


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run GNN prediction on traffic scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Predict from generated scenario
  python scripts/2_run_prediction.py --scenario data/generated
  
  # Predict with custom model
  python scripts/2_run_prediction.py \\
      --scenario data/generated \\
      --model models/trained/gat_metrla_best.pth \\
      --scaler models/trained/scaler_metrla.pkl
  
  # Use different mapping strategy
  python scripts/2_run_prediction.py \\
      --scenario data/generated \\
      --mapping-strategy average
        """
    )
    
    parser.add_argument(
        '--scenario',
        type=str,
        required=True,
        help='Path to traffic scenario directory'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Path to trained GNN model (.pth). Default: from config'
    )
    
    parser.add_argument(
        '--scaler',
        type=str,
        default=None,
        help='Path to fitted scaler (.pkl). Default: from config'
    )
    
    parser.add_argument(
        '--net-file',
        type=str,
        default=None,
        help='Path to SUMO network file. Default: from config'
    )
    
    parser.add_argument(
        '--mapping-strategy',
        type=str,
        default='interpolate',
        choices=['direct', 'average', 'interpolate', 'weighted'],
        help='Speed mapping strategy (default: interpolate)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file for predictions. Default: scenario_dir/predictions.json'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default='auto',
        choices=['auto', 'cpu', 'cuda'],
        help='Device for computation (default: auto)'
    )
    
    return parser.parse_args()


def validate_files(args, config_loader):
    """Validate that required files exist"""
    errors = []
    
    # Check scenario directory
    scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        errors.append(f"Scenario directory not found: {args.scenario}")
    elif not (scenario_path / "speed_matrix.npy").exists():
        errors.append(f"Speed matrix not found in scenario: {scenario_path / 'speed_matrix.npy'}")
    
    # Check model file
    if args.model:
        model_path = Path(args.model)
    else:
        model_dir = config_loader.get('system_config', 'paths.models_dir', './models/trained')
        model_file = config_loader.get('system_config', 'prediction.model_file', 'gat_metrla_best.pth')
        model_path = Path(model_dir) / model_file
    
    if not model_path.exists():
        errors.append(f"GNN model not found: {model_path}")
        errors.append("  Please copy your trained model to models/trained/gat_metrla_best.pth")
    
    # Check scaler file
    if args.scaler:
        scaler_path = Path(args.scaler)
    else:
        model_dir = config_loader.get('system_config', 'paths.models_dir', './models/trained')
        scaler_file = config_loader.get('system_config', 'prediction.scaler_file', 'scaler_metrla.pkl')
        scaler_path = Path(model_dir) / scaler_file
    
    if not scaler_path.exists():
        errors.append(f"Scaler not found: {scaler_path}")
        errors.append("  Please copy your scaler to models/trained/scaler_metrla.pkl")
    
    # Check network file
    if args.net_file:
        net_path = Path(args.net_file)
    else:
        sumo_dir = config_loader.get('system_config', 'paths.sumo_dir', './data/sumo')
        net_file = config_loader.get('system_config', 'sumo.net_file', 'map.net.xml')
        net_path = Path(sumo_dir) / net_file
    
    if not net_path.exists():
        errors.append(f"SUMO network not found: {net_path}")
    
    if errors:
        print("❌ Validation errors:")
        for error in errors:
            print(f"   {error}")
        sys.exit(1)
    
    return str(model_path), str(scaler_path), str(net_path)


def main():
    """Main function"""
    args = parse_arguments()
    
    # Load configurations
    config_loader = get_config_loader()
    system_config = config_loader.load_system_config()
    
    # Setup logger
    logger = get_logger(
        name="Prediction",
        log_file=system_config['logging']['file'],
        level=system_config['logging']['level']
    )
    
    logger.info("="*70)
    logger.info("ITS TRAFFIC SPEED PREDICTION")
    logger.info("="*70)
    
    # Validate files
    model_path, scaler_path, net_path = validate_files(args, config_loader)
    
    logger.info(f"\n📂 Configuration:")
    logger.info(f"   Scenario: {args.scenario}")
    logger.info(f"   Model: {model_path}")
    logger.info(f"   Scaler: {scaler_path}")
    logger.info(f"   Network: {net_path}")
    logger.info(f"   Mapping: {args.mapping_strategy}")
    logger.info(f"   Device: {args.device}")
    logger.info("")
    
    try:
        # Step 1: Parse SUMO network
        logger.info("[Step 1/3] Parsing SUMO network...")
        parser = SUMONetworkParser(net_path)
        parser.print_summary()
        
        # Step 2: Initialize prediction pipeline
        logger.info("[Step 2/3] Initializing prediction pipeline...")
        pipeline = TrafficPredictionPipeline(
            model_path=model_path,
            scaler_path=scaler_path,
            sumo_network=parser,
            mapping_strategy=args.mapping_strategy,
            device=args.device
        )
        
        # Step 3: Run prediction
        logger.info("[Step 3/3] Running prediction...")
        predictions = pipeline.predict_from_scenario(args.scenario)
        
        # Calculate summary statistics
        logger.info("\n📊 Prediction Summary:")
        stats = pipeline.summary_statistics(predictions)
        
        for horizon_stat in stats['per_horizon']:
            logger.info(f"\n  Horizon: t+{horizon_stat['horizon_min']} minutes")
            logger.info(f"    Mean speed: {horizon_stat['mean_speed']:.2f} km/h")
            logger.info(f"    Speed range: [{horizon_stat['min_speed']:.2f}, {horizon_stat['max_speed']:.2f}] km/h")
            logger.info(f"    Std dev: {horizon_stat['std_speed']:.2f} km/h")
        
        # Show sample predictions
        logger.info(f"\n📋 Sample Predictions:")
        sample_edges = list(predictions['predictions'].keys())[:3]
        for edge_id in sample_edges:
            edge_pred = pipeline.get_edge_predictions(predictions, edge_id)
            logger.info(f"\n  {edge_id}:")
            logger.info(f"    t+5min:  {edge_pred['t+5min']:.2f} km/h")
            logger.info(f"    t+10min: {edge_pred['t+10min']:.2f} km/h")
            logger.info(f"    t+15min: {edge_pred['t+15min']:.2f} km/h")
            logger.info(f"    Confidence: {edge_pred['confidence']:.3f}")
        
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            output_path = str(Path(args.scenario) / "predictions.json")
        
        # Save predictions
        pipeline.save_predictions(predictions, output_path)
        
        logger.info(f"\n✅ Prediction completed successfully!")
        logger.info(f"   Predictions saved to: {output_path}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review predictions: cat " + output_path + " | python -m json.tool")
        logger.info("  2. Generate routes: python scripts/3_generate_routes.py")
        logger.info("  3. Run SUMO simulation: python scripts/4_run_sumo_gui.py")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Error during prediction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
