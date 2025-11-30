"""
SUMO Network Parser
Parses SUMO network files (.net.xml) and extracts graph structure
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from pathlib import Path


@dataclass
class SUMONode:
    """Represents a junction/intersection in SUMO network"""
    id: str
    x: float
    y: float
    node_type: str
    
    
@dataclass
class SUMOEdge:
    """Represents a road segment in SUMO network"""
    id: str
    from_node: str
    to_node: str
    priority: int
    num_lanes: int
    speed_limit: float  # m/s
    length: float  # meters
    shape: List[Tuple[float, float]]  # List of coordinates
    edge_type: str = "default"
    
    @property
    def capacity(self) -> float:
        """
        Estimate road capacity (vehicles per hour)
        Based on: capacity = num_lanes * 2000 vehicles/hour/lane
        """
        return self.num_lanes * 2000
    
    @property
    def speed_limit_kmh(self) -> float:
        """Speed limit in km/h"""
        return self.speed_limit * 3.6
    
    def __repr__(self):
        return f"Edge({self.id}: {self.from_node}→{self.to_node}, {self.num_lanes} lanes, {self.speed_limit_kmh:.1f}km/h)"


class SUMONetworkParser:
    """
    Parse SUMO network XML file and extract topology
    """
    
    def __init__(self, net_file: str):
        """
        Initialize parser
        
        Args:
            net_file: Path to SUMO .net.xml file
        """
        self.net_file = Path(net_file)
        
        if not self.net_file.exists():
            raise FileNotFoundError(f"SUMO network file not found: {net_file}")
        
        self.nodes: Dict[str, SUMONode] = {}
        self.edges: Dict[str, SUMOEdge] = {}
        self.tree = None
        
        self._parse()
    
    def _parse(self):
        """Parse the XML file"""
        print(f"📂 Parsing SUMO network: {self.net_file}")
        
        self.tree = ET.parse(self.net_file)
        root = self.tree.getroot()
        
        # Parse nodes (junctions)
        for node_elem in root.findall('.//junction'):
            node_id = node_elem.get('id')
            
            # Skip internal nodes
            if ':' in node_id:
                continue
            
            node = SUMONode(
                id=node_id,
                x=float(node_elem.get('x', 0)),
                y=float(node_elem.get('y', 0)),
                node_type=node_elem.get('type', 'unknown')
            )
            self.nodes[node_id] = node
        
        # Parse edges (roads)
        for edge_elem in root.findall('.//edge'):
            edge_id = edge_elem.get('id')
            
            # Skip internal edges
            if ':' in edge_id:
                continue
            
            # Get first lane to extract properties
            lane = edge_elem.find('lane')
            if lane is None:
                continue
            
            # Parse shape coordinates
            shape_str = lane.get('shape', '')
            shape = []
            if shape_str:
                for coord_pair in shape_str.split():
                    x, y = map(float, coord_pair.split(','))
                    shape.append((x, y))
            
            edge = SUMOEdge(
                id=edge_id,
                from_node=edge_elem.get('from'),
                to_node=edge_elem.get('to'),
                priority=int(edge_elem.get('priority', 0)),
                num_lanes=len(edge_elem.findall('lane')),
                speed_limit=float(lane.get('speed', 13.89)),  # default: 50 km/h
                length=float(lane.get('length', 0)),
                shape=shape,
                edge_type=edge_elem.get('type', 'default')
            )
            self.edges[edge_id] = edge
        
        print(f"   ✓ Loaded {len(self.nodes)} nodes")
        print(f"   ✓ Loaded {len(self.edges)} edges")
    
    def get_edge(self, edge_id: str) -> Optional[SUMOEdge]:
        """Get edge by ID"""
        return self.edges.get(edge_id)
    
    def get_node(self, node_id: str) -> Optional[SUMONode]:
        """Get node by ID"""
        return self.nodes.get(node_id)
    
    def get_outgoing_edges(self, node_id: str) -> List[SUMOEdge]:
        """Get all edges starting from a node"""
        return [edge for edge in self.edges.values() if edge.from_node == node_id]
    
    def get_incoming_edges(self, node_id: str) -> List[SUMOEdge]:
        """Get all edges ending at a node"""
        return [edge for edge in self.edges.values() if edge.to_node == node_id]
    
    def get_network_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get bounding box of network
        
        Returns:
            (min_x, min_y, max_x, max_y)
        """
        if not self.nodes:
            return (0, 0, 0, 0)
        
        x_coords = [node.x for node in self.nodes.values()]
        y_coords = [node.y for node in self.nodes.values()]
        
        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
    
    def get_network_stats(self) -> Dict:
        """Get statistics about the network"""
        
        total_length = sum(edge.length for edge in self.edges.values())
        avg_lanes = np.mean([edge.num_lanes for edge in self.edges.values()])
        avg_speed = np.mean([edge.speed_limit_kmh for edge in self.edges.values()])
        
        return {
            'num_nodes': len(self.nodes),
            'num_edges': len(self.edges),
            'total_length_km': total_length / 1000,
            'avg_lanes': avg_lanes,
            'avg_speed_limit_kmh': avg_speed,
            'network_bounds': self.get_network_bounds()
        }
    
    def print_summary(self):
        """Print network summary"""
        stats = self.get_network_stats()
        bounds = stats['network_bounds']
        
        print("\n" + "="*70)
        print("SUMO NETWORK SUMMARY")
        print("="*70)
        print(f"  Nodes (Junctions):    {stats['num_nodes']}")
        print(f"  Edges (Roads):        {stats['num_edges']}")
        print(f"  Total Road Length:    {stats['total_length_km']:.2f} km")
        print(f"  Average Lanes:        {stats['avg_lanes']:.2f}")
        print(f"  Average Speed Limit:  {stats['avg_speed_limit_kmh']:.1f} km/h")
        print(f"  Network Bounds:")
        print(f"    X: [{bounds[0]:.1f}, {bounds[2]:.1f}]")
        print(f"    Y: [{bounds[1]:.1f}, {bounds[3]:.1f}]")
        print("="*70 + "\n")
    
    def to_dict(self) -> Dict:
        """Export network to dictionary format"""
        return {
            'nodes': {
                node_id: {
                    'x': node.x,
                    'y': node.y,
                    'type': node.node_type
                }
                for node_id, node in self.nodes.items()
            },
            'edges': {
                edge_id: {
                    'from': edge.from_node,
                    'to': edge.to_node,
                    'length': edge.length,
                    'lanes': edge.num_lanes,
                    'speed_limit': edge.speed_limit_kmh,
                    'capacity': edge.capacity,
                    'type': edge.edge_type
                }
                for edge_id, edge in self.edges.items()
            }
        }


if __name__ == "__main__":
    # Test the parser with a sample file
    import sys
    
    if len(sys.argv) > 1:
        net_file = sys.argv[1]
    else:
        net_file = "./data/sumo/map.net.xml"
    
    try:
        parser = SUMONetworkParser(net_file)
        parser.print_summary()
        
        # Show sample edges
        print("Sample edges:")
        for i, (edge_id, edge) in enumerate(parser.edges.items()):
            if i >= 5:
                break
            print(f"  {edge}")
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Usage: python sumo_parser.py <path_to_net.xml>")
