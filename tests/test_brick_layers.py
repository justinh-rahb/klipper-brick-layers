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
        # In simple.gcode, counting G1 commands (not file lines):
        # G1 #1-5: Layer 1 external perimeter (file lines 6-10)
        # G1 #6-10: Layer 1 inner wall (file lines 12-16) <- Transform!
        # G1 #11-15: Layer 2 external perimeter (file lines 20-24)
        # G1 #16-20: Layer 2 inner wall (file lines 26-30) <- Transform!

        # File line 12 = G1 command #6 (first inner wall of layer 1)
        self.assertIn(6, self.bl.transform_map)
        self.assertEqual(self.bl.transform_map[6]['layer'], 1)
        self.assertEqual(self.bl.transform_map[6]['offset_state'], True) # layer 1 >= start_layer 1

        # File line 27 = G1 command #17 (second inner wall move of layer 2)
        self.assertIn(17, self.bl.transform_map)
        self.assertEqual(self.bl.transform_map[17]['layer'], 2)
        self.assertEqual(self.bl.transform_map[17]['offset_state'], False) # layer 2 toggles it

    def test_apply_transform_z(self):
        self.bl.current_gcode_line = 12
        # New behavior: brick_z is pre-calculated during preprocessing
        self.bl.transform_map = {12: {
            'layer': 1,
            'offset_state': True,
            'current_z': 0.2,
            'layer_height': 0.2,
            'brick_z': 0.3  # 0.2 + 0.2/2 = 0.3 (half layer higher)
        }}
        self.bl.z_offset = 0.1

        params = {'X': 1, 'Y': 1, 'Z': 0.2, 'E': 0.1, 'F': None}
        transformed = self.bl._apply_transform(params)

        self.assertAlmostEqual(transformed['Z'], 0.3) # brick_z value
        
    def test_apply_transform_z_injection(self):
        """Test that Z is injected even when not originally present"""
        self.bl.current_gcode_line = 12
        self.bl.transform_map = {12: {
            'layer': 1,
            'offset_state': True,
            'current_z': 0.2,
            'layer_height': 0.2,
            'brick_z': 0.3  # 0.2 + 0.2/2 = 0.3
        }}

        # Original move has NO Z parameter
        params = {'X': 1, 'Y': 1, 'Z': None, 'E': 0.1, 'F': None}
        transformed = self.bl._apply_transform(params)

        # Z should be injected!
        self.assertAlmostEqual(transformed['Z'], 0.3)

    def test_apply_transform_e(self):
        self.bl.current_gcode_line = 12
        self.bl.transform_map = {12: {
            'layer': 1,
            'offset_state': True,
            'brick_z': 0.3
        }}
        self.bl.extrusion_multiplier = 1.1

        params = {'X': 1, 'Y': 1, 'Z': 0.2, 'E': 1.0, 'F': None}
        transformed = self.bl._apply_transform(params)

        self.assertAlmostEqual(transformed['E'], 1.1)

if __name__ == '__main__':
    unittest.main()
