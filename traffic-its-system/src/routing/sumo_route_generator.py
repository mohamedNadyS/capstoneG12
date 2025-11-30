"""
SUMO Route File Generator
Converts routing results to SUMO-compatible route files
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List
from pathlib import Path
import json


class SUMORouteGenerator:
    """
    Generate SUMO route files (.rou.xml) from routing results
    """
    
    def __init__(self):
        """Initialize route generator"""
        print(f"\n[SUMO-GEN] SUMO Route Generator initialized")
    
    def generate_route_file(
        self,
        routes: Dict[str, Dict],
        output_file: str,
        simulation_time: int = 3600
    ):
        """
        Generate SUMO route XML file
        
        Args:
            routes: Dictionary of routes from decision engine
            output_file: Output .rou.xml file path
            simulation_time: Simulation duration in seconds
        """
        print(f"\n[SUMO-GEN] Generating SUMO route file...")
        print(f"   Routes: {len(routes)}")
        print(f"   Output: {output_file}")
        
        # Create root element
        root = ET.Element('routes')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/routes_file.xsd')
        
        # Define vehicle types
        self._add_vehicle_types(root)
        
        # Add routes and vehicles
        route_count = 0
        vehicle_count = 0
        
        for vehicle_id, route_data in routes.items():
            # Create route element
            route_id = f"route_{vehicle_id}"
            route_elem = ET.SubElement(root, 'route')
            route_elem.set('id', route_id)
            
            # Get edge sequence
            edges = route_data['edges']
            if edges:
                route_elem.set('edges', ' '.join(edges))
                route_count += 1
            else:
                # Skip vehicles with no route
                continue
            
            # Create vehicle element
            vehicle_elem = ET.SubElement(root, 'vehicle')
            vehicle_elem.set('id', vehicle_id)
            vehicle_elem.set('route', route_id)
            
            # Set vehicle type
            vehicle_type = route_data.get('vehicle_type', 'normal')
            if vehicle_type == 'emergency':
                vehicle_elem.set('type', 'emergency')
                vehicle_elem.set('color', 'red')
            else:
                vehicle_elem.set('type', 'normal')
                vehicle_elem.set('color', 'blue')
            
            # Set departure time (spread vehicles over simulation)
            depart_time = int((vehicle_count / len(routes)) * min(simulation_time, 3600))
            vehicle_elem.set('depart', str(depart_time))
            
            vehicle_count += 1
        
        # Write to file
        self._write_xml(root, output_file)
        
        print(f"   [OK] Generated {route_count} routes")
        print(f"   [OK] Generated {vehicle_count} vehicles")
        print(f"   [OK] Saved to: {output_file}")
    
    def _add_vehicle_types(self, root: ET.Element):
        """Add vehicle type definitions"""
        # Normal vehicle type
        vtype_normal = ET.SubElement(root, 'vType')
        vtype_normal.set('id', 'normal')
        vtype_normal.set('accel', '2.6')
        vtype_normal.set('decel', '4.5')
        vtype_normal.set('sigma', '0.5')
        vtype_normal.set('length', '4.5')
        vtype_normal.set('maxSpeed', '50')
        vtype_normal.set('color', '0,0,255')
        
        # Emergency vehicle type
        vtype_emergency = ET.SubElement(root, 'vType')
        vtype_emergency.set('id', 'emergency')
        vtype_emergency.set('accel', '3.5')
        vtype_emergency.set('decel', '6.0')
        vtype_emergency.set('sigma', '0.3')
        vtype_emergency.set('length', '5.5')
        vtype_emergency.set('maxSpeed', '60')
        vtype_emergency.set('color', '255,0,0')
        vtype_emergency.set('speedFactor', '1.2')  # Can go 20% over limit
    
    def _write_xml(self, root: ET.Element, output_file: str):
        """Write XML with pretty formatting"""
        # Convert to string
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')
        
        # Remove extra blank lines
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        pretty_xml = '\n'.join(lines)
        
        # Write to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            f.write(pretty_xml)
    
    def generate_sumo_config(
        self,
        network_file: str,
        route_file: str,
        output_file: str,
        begin_time: int = 0,
        end_time: int = 3600,
        step_length: float = 0.1
    ):
        """
        Generate SUMO configuration file (.sumocfg)
        
        Args:
            network_file: Path to .net.xml file
            route_file: Path to .rou.xml file
            output_file: Output .sumocfg file path
            begin_time: Simulation start time
            end_time: Simulation end time
            step_length: Simulation time step
        """
        print(f"\n[SUMO-GEN] Generating SUMO config file...")
        
        root = ET.Element('configuration')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xsi:noNamespaceSchemaLocation', 'http://sumo.dlr.de/xsd/sumoConfiguration.xsd')
        
        # Input section
        input_elem = ET.SubElement(root, 'input')
        net_elem = ET.SubElement(input_elem, 'net-file')
        net_elem.set('value', network_file)
        route_elem = ET.SubElement(input_elem, 'route-files')
        route_elem.set('value', route_file)
        
        # Time section
        time_elem = ET.SubElement(root, 'time')
        begin_elem = ET.SubElement(time_elem, 'begin')
        begin_elem.set('value', str(begin_time))
        end_elem = ET.SubElement(time_elem, 'end')
        end_elem.set('value', str(end_time))
        step_elem = ET.SubElement(time_elem, 'step-length')
        step_elem.set('value', str(step_length))
        
        # Processing section
        proc_elem = ET.SubElement(root, 'processing')
        collision_elem = ET.SubElement(proc_elem, 'collision.action')
        collision_elem.set('value', 'warn')
        
        # Routing section (for rerouting)
        routing_elem = ET.SubElement(root, 'routing')
        device_elem = ET.SubElement(routing_elem, 'device.rerouting.adaptation-steps')
        device_elem.set('value', '180')
        
        # Write to file
        self._write_xml(root, output_file)
        
        print(f"   [OK] Saved to: {output_file}")
    
    def save_routing_metadata(
        self,
        routes: Dict[str, Dict],
        statistics: Dict,
        output_file: str
    ):
        """
        Save routing metadata as JSON for analysis
        
        Args:
            routes: Routing results
            statistics: Routing statistics
            output_file: Output JSON file path
        """
        print(f"\n[SUMO-GEN] Saving routing metadata...")
        
        # Prepare serializable data
        metadata = {
            'statistics': statistics,
            'routes': {}
        }
        
        for vehicle_id, route_data in routes.items():
            metadata['routes'][vehicle_id] = {
                'vehicle_type': route_data.get('vehicle_type'),
                'algorithm': route_data.get('algorithm'),
                'cost': route_data.get('cost'),
                'length': route_data.get('length'),
                'num_edges': route_data.get('num_edges'),
                'edges': route_data.get('edges', []),
                'nodes': route_data.get('nodes', [])
            }
        
        # Write to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"   [OK] Saved to: {output_file}")


if __name__ == "__main__":
    print("="*70)
    print("SUMO ROUTE GENERATOR TEST")
    print("="*70)
    
    print("\nGenerates SUMO-compatible files:")
    print("  • .rou.xml - Vehicle routes")
    print("  • .sumocfg - SUMO configuration")
    print("  • routing_metadata.json - Analysis data")
    
    print("\nOutput format:")
    print("  <routes>")
    print("    <vType id='normal' .../> ")
    print("    <vType id='emergency' .../>")
    print("    <route id='route_v1' edges='E1 E2 E3'/>")
    print("    <vehicle id='v1' route='route_v1' depart='0'/>")
    print("  </routes>")
