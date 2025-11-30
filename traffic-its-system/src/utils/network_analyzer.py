"""
Network Connectivity Analyzer
Analyzes SUMO network for connectivity issues and suggests fixes
"""

import networkx as nx
from typing import Dict, List, Set, Tuple
from pathlib import Path

from src.sumo_integration.sumo_parser import SUMONetworkParser


class NetworkAnalyzer:
    """
    Analyze network connectivity and find issues
    """
    
    def __init__(self, sumo_network: SUMONetworkParser):
        """Initialize analyzer"""
        self.sumo_network = sumo_network
        self.graph = None
        
    def build_connectivity_graph(self) -> nx.DiGraph:
        """Build NetworkX graph for connectivity analysis"""
        G = nx.DiGraph()
        
        # Add all nodes
        for node_id in self.sumo_network.nodes.keys():
            G.add_node(node_id)
        
        # Add all edges
        for edge in self.sumo_network.edges.values():
            G.add_edge(edge.from_node, edge.to_node)
        
        self.graph = G
        return G
    
    def analyze_connectivity(self) -> Dict:
        """
        Analyze network connectivity
        
        Returns:
            Dictionary with connectivity analysis
        """
        if self.graph is None:
            self.build_connectivity_graph()
        
        print(f"\n[ANALYZER] Analyzing network connectivity...")
        
        # Convert to undirected for component analysis
        undirected = self.graph.to_undirected()
        
        # Find connected components
        components = list(nx.connected_components(undirected))
        num_components = len(components)
        
        # Find strongly connected components (directed)
        strong_components = list(nx.strongly_connected_components(self.graph))
        num_strong = len(strong_components)
        
        # Largest component
        largest_component = max(components, key=len)
        largest_size = len(largest_component)
        
        # Calculate reachability
        total_pairs = len(self.graph.nodes) * (len(self.graph.nodes) - 1)
        reachable_pairs = 0
        
        for source in self.graph.nodes:
            reachable = nx.descendants(self.graph, source)
            reachable_pairs += len(reachable)
        
        connectivity_ratio = reachable_pairs / total_pairs if total_pairs > 0 else 0
        
        analysis = {
            'total_nodes': len(self.graph.nodes),
            'total_edges': len(self.graph.edges),
            'connected_components': num_components,
            'strongly_connected_components': num_strong,
            'largest_component_size': largest_size,
            'connectivity_ratio': connectivity_ratio,
            'is_fully_connected': num_components == 1,
            'is_strongly_connected': num_strong == 1,
            'components': components,
            'strong_components': strong_components
        }
        
        return analysis
    
    def print_analysis(self, analysis: Dict):
        """Print connectivity analysis"""
        print(f"\n" + "="*70)
        print("NETWORK CONNECTIVITY ANALYSIS")
        print("="*70)
        
        print(f"\nBasic Statistics:")
        print(f"  Nodes: {analysis['total_nodes']}")
        print(f"  Edges: {analysis['total_edges']}")
        
        print(f"\nConnectivity:")
        print(f"  Connected components: {analysis['connected_components']}")
        if analysis['connected_components'] > 1:
            print(f"    [WARNING] Network is DISCONNECTED!")
            print(f"    Vehicles cannot travel between all nodes")
        else:
            print(f"    [OK] Network is connected (undirected)")
        
        print(f"\n  Strongly connected components: {analysis['strongly_connected_components']}")
        if analysis['strongly_connected_components'] > 1:
            print(f"    [WARNING] Network is NOT strongly connected!")
            print(f"    Some node pairs don't have directed paths")
        else:
            print(f"    [OK] Network is strongly connected")
        
        print(f"\n  Largest component: {analysis['largest_component_size']} nodes "
              f"({analysis['largest_component_size']/analysis['total_nodes']*100:.1f}%)")
        
        print(f"  Reachability: {analysis['connectivity_ratio']*100:.1f}% of node pairs")
        
        if analysis['connected_components'] > 1:
            print(f"\n  Component sizes:")
            for i, comp in enumerate(analysis['components'], 1):
                print(f"    Component {i}: {len(comp)} nodes")
                if len(comp) <= 5:
                    print(f"      Nodes: {sorted(comp)}")
        
        print("="*70)
    
    def find_isolated_nodes(self) -> List[str]:
        """Find nodes with no connections"""
        isolated = []
        for node in self.graph.nodes:
            in_degree = self.graph.in_degree(node)
            out_degree = self.graph.out_degree(node)
            if in_degree == 0 and out_degree == 0:
                isolated.append(node)
        return isolated
    
    def find_dead_ends(self) -> List[str]:
        """Find nodes with no outgoing edges"""
        dead_ends = []
        for node in self.graph.nodes:
            if self.graph.out_degree(node) == 0 and self.graph.in_degree(node) > 0:
                dead_ends.append(node)
        return dead_ends
    
    def find_sources(self) -> List[str]:
        """Find nodes with no incoming edges"""
        sources = []
        for node in self.graph.nodes:
            if self.graph.in_degree(node) == 0 and self.graph.out_degree(node) > 0:
                sources.append(node)
        return sources
    
    def suggest_fixes(self, analysis: Dict) -> List[str]:
        """Suggest fixes for connectivity issues"""
        suggestions = []
        
        if analysis['connected_components'] > 1:
            suggestions.append(
                "ISSUE: Network has disconnected components\n"
                "FIX: Add edges to connect all components\n"
                f"     Currently {analysis['connected_components']} separate networks"
            )
        
        if analysis['connectivity_ratio'] < 0.5:
            suggestions.append(
                f"ISSUE: Low connectivity ({analysis['connectivity_ratio']*100:.1f}%)\n"
                "FIX: Add more edges to improve connectivity\n"
                "     Many node pairs cannot reach each other"
            )
        
        isolated = self.find_isolated_nodes()
        if isolated:
            suggestions.append(
                f"ISSUE: {len(isolated)} isolated nodes (no connections)\n"
                f"     Nodes: {isolated}\n"
                "FIX: Remove these nodes or connect them to the network"
            )
        
        dead_ends = self.find_dead_ends()
        if dead_ends:
            suggestions.append(
                f"ISSUE: {len(dead_ends)} dead-end nodes (no way out)\n"
                "FIX: Add outgoing edges or mark as destinations only"
            )
        
        sources = self.find_sources()
        if sources:
            suggestions.append(
                f"ISSUE: {len(sources)} source nodes (no way in)\n"
                "FIX: Add incoming edges or mark as origins only"
            )
        
        return suggestions
    
    def get_usable_nodes(self) -> Set[str]:
        """
        Get nodes that are usable for routing
        (part of the largest strongly connected component)
        """
        if self.graph is None:
            self.build_connectivity_graph()
        
        strong_components = list(nx.strongly_connected_components(self.graph))
        largest_strong = max(strong_components, key=len)
        
        return largest_strong


def analyze_network(network_file: str):
    """
    Analyze network connectivity
    
    Args:
        network_file: Path to SUMO network file
    """
    print(f"\n[ANALYZER] Loading network: {network_file}")
    
    # Parse network
    parser = SUMONetworkParser(network_file)
    
    # Analyze
    analyzer = NetworkAnalyzer(parser)
    analysis = analyzer.analyze_connectivity()
    
    # Print results
    analyzer.print_analysis(analysis)
    
    # Get suggestions
    suggestions = analyzer.suggest_fixes(analysis)
    
    if suggestions:
        print(f"\n" + "="*70)
        print("SUGGESTED FIXES")
        print("="*70)
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n{i}. {suggestion}")
        print("="*70)
    
    # Get usable nodes
    usable = analyzer.get_usable_nodes()
    print(f"\n[ANALYZER] Usable nodes for routing: {len(usable)} / {len(parser.nodes)}")
    print(f"   Usable: {sorted(usable)}")
    
    return analyzer, analysis


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        network_file = sys.argv[1]
    else:
        network_file = "data/sumo/map.net.xml"
    
    analyze_network(network_file)
