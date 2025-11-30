#!/usr/bin/env python3
"""
Network Connectivity Analyzer
Analyzes SUMO network for connectivity issues

Usage:
    python scripts/analyze_network.py --network data/sumo/map.net.xml
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sumo_integration.sumo_parser import SUMONetworkParser
from src.utils.network_analyzer import NetworkAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Analyze SUMO network connectivity")
    parser.add_argument('--network', type=str, required=True, help='Path to SUMO network file')
    args = parser.parse_args()
    
    print("="*70)
    print("NETWORK CONNECTIVITY ANALYZER")
    print("="*70)
    
    # Parse network
    print(f"\n[1/3] Loading network: {args.network}")
    sumo_parser = SUMONetworkParser(args.network)
    print(f"   Loaded {len(sumo_parser.nodes)} nodes, {len(sumo_parser.edges)} edges")
    
    # Analyze
    print(f"\n[2/3] Analyzing connectivity...")
    analyzer = NetworkAnalyzer(sumo_parser)
    analysis = analyzer.analyze_connectivity()
    
    # Print results
    print(f"\n[3/3] Results:")
    analyzer.print_analysis(analysis)
    
    # Suggestions
    suggestions = analyzer.suggest_fixes(analysis)
    if suggestions:
        print(f"\n" + "="*70)
        print("RECOMMENDED ACTIONS")
        print("="*70)
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. {suggestion}")
        print("="*70)
    
    # Usable nodes
    usable = analyzer.get_usable_nodes()
    unusable = set(sumo_parser.nodes.keys()) - usable
    
    print(f"\n" + "="*70)
    print("ROUTING CAPABILITY")
    print("="*70)
    print(f"\nUsable for routing: {len(usable)} / {len(sumo_parser.nodes)} nodes ({len(usable)/len(sumo_parser.nodes)*100:.1f}%)")
    
    if unusable:
        print(f"\nUnusable nodes ({len(unusable)}):")
        for node in sorted(unusable):
            print(f"  - {node}")
        print(f"\nThese nodes should NOT be used as origins or destinations")
    
    print("="*70)
    
    # Summary
    if analysis['is_strongly_connected']:
        print(f"\n[OK] Network is STRONGLY CONNECTED - all routing will work!")
    elif len(usable) >= len(sumo_parser.nodes) * 0.8:
        print(f"\n[WARNING] {len(usable)/len(sumo_parser.nodes)*100:.1f}% of nodes are usable")
        print(f"Some vehicles may not find routes - this is OK")
    else:
        print(f"\n[ERROR] Only {len(usable)/len(sumo_parser.nodes)*100:.1f}% of nodes are usable!")
        print(f"Network has serious connectivity issues")
    
    print()


if __name__ == "__main__":
    main()
