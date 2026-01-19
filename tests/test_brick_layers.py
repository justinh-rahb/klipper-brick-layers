import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add the directory containing brick_layers.py to the path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))

from brick_layers import BrickLayers

class TestBrickLayers(unittest.TestCase):
    def setUp(self):
        self.mock_printer = MagicMock()
        self.mock_gcode = MagicMock()
        self.mock_config = MagicMock()
        
        self.mock_config.get_printer.return_value = self.mock_printer
        self.mock_printer.lookup_object.side_effect = self.lookup_object_side_effect
        
        # Default config values
        self.mock_config.getboolean.side_effect = lambda k, d: d
        self.mock_config.getfloat.side_effect = lambda k, d: d
        self.mock_config.getint.side_effect = lambda k, d: d
        self.mock_config.get_name.return_value = 'brick_layers'

        self.bl = BrickLayers(self.mock_config)
        self.bl.gcode = self.mock_gcode

    def lookup_object_side_effect(self, name):
        if name == 'gcode':
            return self.mock_gcode
        if name == 'virtual_sdcard':
            mock_sdcard = MagicMock()
            mock_sdcard.file_path = None
            return mock_sdcard
        if name == 'gcode_move':
            return MagicMock()
        return MagicMock()

    def test_init(self):
        self.assertEqual(self.bl.z_offset, 0.1)
        self.assertEqual(self.bl.start_layer, 3)
        self.assertFalse(self.bl.enabled)

    def test_preprocess_simple_gcode(self):
        sample_path = os.path.abspath(os.path.dirname(__file__) + '/sample_gcode/simple.gcode')
        self.bl.start_layer = 1 # Start early for testing
        self.bl._preprocess_gcode_file(sample_path)
        
        # Check if we found transform points
        # In simple.gcode:
        # Layer 1 (0.2): Internal moves lines 12-16
        # Layer 2 (0.4): Internal moves lines 27-31
        
        # Wait, let's check line numbers exactly.
        # Line 1: ; simple.gcode
        # Line 2: G28
        # Line 3: ;LAYER_CHANGE
        # Line 4: ;Z:0.2 (Layer 1)
        # Line 5: ;TYPE:External perimeter
        # Line 6: G1 X0 Y0 Z0.2 E0 F3000
        # Line 7: G1 X10 Y0 E0.5
        # Line 8: G1 X10 Y10 E1.0
        # Line 9: G1 X0 Y10 E1.5
        # Line 10: G1 X0 Y0 E2.0
        # Line 11: ;TYPE:Inner wall
        # Line 12: G1 X1 Y1 E2.1  <- Transform!
        # Line 13: G1 X9 Y1 E2.6  <- Transform!
        # Line 14: G1 X9 Y9 E3.1  <- Transform!
        # Line 15: G1 X1 Y9 E3.6  <- Transform!
        # Line 16: G1 X1 Y1 E4.1  <- Transform!
        # Line 17: ;LAYER_CHANGE
        # Line 18: ;Z:0.4 (Layer 2)
        # ...
        
        self.assertIn(12, self.bl.transform_map)
        self.assertEqual(self.bl.transform_map[12]['layer'], 1)
        self.assertEqual(self.bl.transform_map[12]['offset_state'], True) # layer 1 >= start_layer 1
        
        self.assertIn(27, self.bl.transform_map)
        self.assertEqual(self.bl.transform_map[27]['layer'], 2)
        self.assertEqual(self.bl.transform_map[27]['offset_state'], False) # layer 2 toggles it

    def test_apply_transform_z(self):
        self.bl.current_gcode_line = 12
        self.bl.transform_map = {12: {'layer': 1, 'offset_state': True}}
        self.bl.z_offset = 0.1
        
        params = {'X': 1, 'Y': 1, 'Z': 0.2, 'E': 0.1, 'F': None}
        transformed = self.bl._apply_transform(params)
        
        self.assertAlmostEqual(transformed['Z'], 0.3) # 0.2 + 0.1
        
    def test_apply_transform_e(self):
        self.bl.current_gcode_line = 12
        self.bl.transform_map = {12: {'layer': 1, 'offset_state': True}}
        self.bl.extrusion_multiplier = 1.1
        
        params = {'X': 1, 'Y': 1, 'Z': 0.2, 'E': 1.0, 'F': None}
        transformed = self.bl._apply_transform(params)
        
        self.assertAlmostEqual(transformed['E'], 1.1)

if __name__ == '__main__':
    unittest.main()
