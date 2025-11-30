#!/usr/bin/env python3
"""
Traffic Routing Script
Generates optimal routes using predicted speeds

Usage:
    python scripts/3_generate_routes.py --scenario data/generated
"""

import argparse
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import get_config_loader
from src.utils.logger import get_logger
from src.sumo_integration.sumo_parser import SUMONetworkParser
from src.routing.graph_builder import RoutingGraphBuilder
from src.routing.decision_engine import RoutingDecisionEngine
from src.routing.sumo_route_generator import SUMORouteGenerator


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Generate optimal routes using GNN predictions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate routes from scenario
  python scripts/3_generate_routes.py --scenario data/generated
  
  # Custom output directory
  python scripts/3_generate_routes.py \\
      --scenario data/generated \\
      --output data/routes
  
  # Without emergency priority
  python scripts/3_generate_routes.py \\
      --scenario data/generated \\
      --no-emergency-priority
        """
    )
    
    parser.add_argument(
        '--scenario',
        type=str,
        required=True,
        help='Path to traffic scenario directory (must contain predictions.json)'
    )
    
    parser.add_argument(
        '--net-file',
        type=str,
        default=None,
        help='Path to SUMO network file. Default: from config'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for routes. Default: scenario_dir'
    )
    
    parser.add_argument(
        '--no-emergency-priority',
        action='store_true',
        help='Disable emergency vehicle priority routing'
    )
    
    parser.add_argument(
        '--simulation-time',
        type=int,
        default=3600,
        help='Simulation duration in seconds (default: 3600)'
    )
    
    return parser.parse_args()


def load_scenario_data(scenario_dir: Path, logger):
    """Load traffic scenario and predictions"""
    logger.info(f"[DATA] Loading scenario data from: {scenario_dir}")
    
    # Load predictions
    predictions_file = scenario_dir / "predictions.json"
    if not predictions_file.exists():
        raise FileNotFoundError(
            f"Predictions not found: {predictions_file}\n"
            "Run prediction first: python scripts/2_run_prediction.py"
        )
    
    with open(predictions_file, 'r') as f:
        predictions_data = json.load(f)
    
    logger.info(f"   [OK] Loaded predictions for {len(predictions_data['predictions'])} edges")
    
    # Load vehicles
    vehicles_file = scenario_dir / "vehicles.json"
    if not vehicles_file.exists():
        raise FileNotFoundError(f"Vehicles not found: {vehicles_file}")
    
    with open(vehicles_file, 'r') as f:
        vehicles_data = json.load(f)
    
    logger.info(f"   [OK] Loaded {len(vehicles_data)} vehicles")
    
    # Load edge states
    edge_states_file = scenario_dir / "edge_states.json"
    edge_states = None
    if edge_states_file.exists():
        with open(edge_states_file, 'r') as f:
            edge_states = json.load(f)
        logger.info(f"   [OK] Loaded edge states")
    
    return predictions_data, vehicles_data, edge_states


def prepare_vehicles_for_routing(vehicles_data, sumo_network, logger):
    """Convert vehicle data to routing format"""
    logger.info(f"\n[PREP] Preparing vehicles for routing...")
    
    # First, check network connectivity
    from src.utils.network_analyzer import NetworkAnalyzer
    import networkx as nx
    
    analyzer = NetworkAnalyzer(sumo_network)
    analysis = analyzer.analyze_connectivity()
    
    # Get usable nodes (largest strongly connected component)
    usable_nodes = analyzer.get_usable_nodes()
    
    logger.info(f"   Network connectivity:")
    logger.info(f"      Total nodes: {analysis['total_nodes']}")
    logger.info(f"      Usable nodes: {len(usable_nodes)} ({len(usable_nodes)/analysis['total_nodes']*100:.1f}%)")
    logger.info(f"      Connected components: {analysis['connected_components']}")
    logger.info(f"      Strongly connected: {analysis['is_strongly_connected']}")
    
    if analysis['connected_components'] > 1:
        logger.warning(f"   [WARNING] Network has {analysis['connected_components']} disconnected components")
        logger.warning(f"   Only routing vehicles within largest component")
    
    vehicles = []
    edges = list(sumo_network.edges.keys())
    skipped = 0
    skipped_reasons = {'edge_not_found': 0, 'not_in_scc': 0, 'no_path': 0, 'same_node': 0}
    
    for vehicle in vehicles_data:
        # Get origin and destination nodes
        origin_edge_id = vehicle['origin_edge']
        dest_edge_id = vehicle['destination_edge']
        
        if origin_edge_id not in sumo_network.edges or dest_edge_id not in sumo_network.edges:
            skipped += 1
            skipped_reasons['edge_not_found'] += 1
            continue
        
        origin_edge = sumo_network.edges[origin_edge_id]
        dest_edge = sumo_network.edges[dest_edge_id]
        
        # Use the 'from' node of origin edge and 'to' node of destination edge
        origin_node = origin_edge.from_node
        dest_node = dest_edge.to_node
        
        # Skip if same node
        if origin_node == dest_node:
            skipped += 1
            skipped_reasons['same_node'] += 1
            continue
        
        # Check if both nodes are in the usable set (largest SCC)
        if origin_node not in usable_nodes or dest_node not in usable_nodes:
            skipped += 1
            skipped_reasons['not_in_scc'] += 1
            continue
        
        # CRITICAL: Check if directed path actually exists
        # Even in same SCC, some paths may not exist due to one-way streets
        if not nx.has_path(analyzer.graph, origin_node, dest_node):
            skipped += 1
            skipped_reasons['no_path'] += 1
            continue
        
        vehicles.append({
            'id': vehicle['id'],
            'type': vehicle['vehicle_type'],
            'origin': origin_node,
            'destination': dest_node,
            'depart_time': vehicle.get('depart_time', 0)
        })
    
    logger.info(f"   [OK] Prepared {len(vehicles)} vehicles")
    logger.info(f"      Emergency: {len([v for v in vehicles if v['type'] == 'emergency'])}")
    logger.info(f"      Normal: {len([v for v in vehicles if v['type'] == 'normal'])}")
    if skipped > 0:
        logger.info(f"      Skipped: {skipped} vehicles")
        logger.info(f"         Edge not found: {skipped_reasons['edge_not_found']}")
        logger.info(f"         Same origin/dest: {skipped_reasons['same_node']}")
        logger.info(f"         Not in largest SCC: {skipped_reasons['not_in_scc']}")
        logger.info(f"         No directed path: {skipped_reasons['no_path']}")
    
    return vehicles


def main():
    """Main function"""
    args = parse_arguments()
    
    # Load configurations
    config_loader = get_config_loader()
    system_config = config_loader.load_system_config()
    
    # Setup logger
    logger = get_logger(
        name="Routing",
        log_file=system_config['logging']['file'],
        level=system_config['logging']['level']
    )
    
    logger.info("="*70)
    logger.info("ITS TRAFFIC ROUTING")
    logger.info("="*70)
    
    scenario_dir = Path(args.scenario)
    if not scenario_dir.exists():
        logger.error(f"Scenario directory not found: {scenario_dir}")
        sys.exit(1)
    
    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = scenario_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine network file
    if args.net_file:
        net_file = args.net_file
    else:
        sumo_dir = config_loader.get('system_config', 'paths.sumo_dir', './data/sumo')
        net_file_name = config_loader.get('system_config', 'sumo.net_file', 'map.net.xml')
        net_file = str(Path(sumo_dir) / net_file_name)
    
    logger.info(f"\nConfiguration:")
    logger.info(f"   Scenario: {scenario_dir}")
    logger.info(f"   Network: {net_file}")
    logger.info(f"   Output: {output_dir}")
    logger.info(f"   Emergency priority: {not args.no_emergency_priority}")
    logger.info("")
    
    try:
        # Step 1: Load data
        logger.info("[Step 1/6] Loading scenario data...")
        predictions_data, vehicles_data, edge_states = load_scenario_data(scenario_dir, logger)
        
        # Step 2: Parse SUMO network
        logger.info("[Step 2/6] Parsing SUMO network...")
        sumo_network = SUMONetworkParser(net_file)
        sumo_network.print_summary()
        
        # Step 3: Build routing graph
        logger.info("[Step 3/6] Building routing graph...")
        graph_builder = RoutingGraphBuilder(sumo_network)
        
        # Extract predictions - handle different formats
        predicted_speeds = {}
        pred_data = predictions_data.get('predictions', {})
        
        for edge_id, speeds in pred_data.items():
            if isinstance(speeds, list):
                # Already a list [t+5, t+10, t+15]
                predicted_speeds[edge_id] = speeds
            else:
                # Single value, convert to list
                predicted_speeds[edge_id] = [float(speeds)] * 3
        
        logger.info(f"   Loaded predictions for {len(predicted_speeds)} edges")
        
        # Extract current congestion from edge states
        current_congestion = {}
        if edge_states:
            # Handle both list and dict formats
            if isinstance(edge_states, list):
                # List of edge state dicts
                for edge_state in edge_states:
                    if isinstance(edge_state, dict):
                        current_congestion[edge_state['edge_id']] = edge_state.get('congestion_factor', 0.0)
            elif isinstance(edge_states, dict):
                # Dict mapping edge_id -> state dict or value
                for edge_id, edge_state in edge_states.items():
                    if isinstance(edge_state, dict):
                        current_congestion[edge_id] = edge_state.get('congestion_factor', 0.0)
                    else:
                        # Direct value
                        current_congestion[edge_id] = float(edge_state) if edge_state else 0.0
        
        logger.info(f"   Loaded congestion for {len(current_congestion)} edges")
        
        # Build graph with predictions
        graph = graph_builder.build_graph(
            predicted_speeds=predicted_speeds,
            current_congestion=current_congestion
        )
        
        # Show graph stats
        stats = graph_builder.get_graph_statistics()
        logger.info(f"\n   Graph statistics:")
        logger.info(f"      Nodes: {stats['num_nodes']}")
        logger.info(f"      Edges: {stats['num_edges']}")
        logger.info(f"      Avg predicted speed: {stats['avg_speed']:.2f} km/h")
        logger.info(f"      Avg travel time: {stats['avg_travel_time']:.2f} seconds")
        logger.info(f"      Avg congestion: {stats['avg_congestion']:.2%}")
        logger.info(f"      Avg safety score: {stats['avg_safety']:.2f}")
        
        # Step 4: Prepare vehicles
        logger.info("\n[Step 4/6] Preparing vehicles...")
        vehicles = prepare_vehicles_for_routing(vehicles_data, sumo_network, logger)
        
        # Step 5: Route all vehicles
        logger.info("\n[Step 5/6] Routing vehicles...")
        decision_engine = RoutingDecisionEngine(
            graph_builder=graph_builder,
            enable_emergency_priority=not args.no_emergency_priority
        )
        
        routing_results = decision_engine.route_all_vehicles(vehicles)
        
        routes = routing_results['routes']
        routing_stats = routing_results['statistics']
        
        logger.info(f"\n   Routing summary:")
        logger.info(f"      Total vehicles: {routing_stats['total_vehicles']}")
        logger.info(f"      Emergency: {routing_stats['emergency_vehicles']}")
        logger.info(f"      Normal: {routing_stats['normal_vehicles']}")
        logger.info(f"      Avg cost: {routing_stats['avg_cost']:.2f} seconds")
        logger.info(f"      Avg length: {routing_stats['avg_length']:.2f} meters")
        logger.info(f"      Algorithm usage:")
        for algo, count in routing_stats['algorithm_usage'].items():
            logger.info(f"         {algo}: {count}")
        
        # Step 6: Generate SUMO files
        logger.info("\n[Step 6/6] Generating SUMO files...")
        route_generator = SUMORouteGenerator()
        
        # Generate route file
        route_file = str(output_dir / "routes.rou.xml")
        route_generator.generate_route_file(
            routes=routes,
            output_file=route_file,
            simulation_time=args.simulation_time
        )
        
        # Generate SUMO config file
        config_file = str(output_dir / "simulation.sumocfg")
        route_generator.generate_sumo_config(
            network_file=net_file,
            route_file=route_file,
            output_file=config_file,
            end_time=args.simulation_time
        )
        
        # Save routing metadata
        metadata_file = str(output_dir / "routing_metadata.json")
        route_generator.save_routing_metadata(
            routes=routes,
            statistics=routing_stats,
            output_file=metadata_file
        )
        
        logger.info(f"\n[OK] Routing completed successfully!")
        logger.info(f"\n   Generated files:")
        logger.info(f"      Routes: {route_file}")
        logger.info(f"      Config: {config_file}")
        logger.info(f"      Metadata: {metadata_file}")
        logger.info("")
        logger.info("Next steps:")
        logger.info(f"   1. Run SUMO-GUI: sumo-gui -c {config_file}")
        logger.info(f"   2. Or use script: python scripts/4_run_sumo_gui.py --config {config_file}")
        logger.info("")
        
    except Exception as e:
        logger.error(f"[ERROR] Error during routing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
