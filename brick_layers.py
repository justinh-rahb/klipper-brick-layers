# Klipper BrickLayers Module
# Real-time brick layering transformation for improved part strength
#
# Copyright (C) 2025 Justin Hayes
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging

class BrickLayers:
    """
    BrickLayers - Real-time G-code transformation for interlocking layer patterns
    
    This module intercepts G1 move commands and applies Z-offset transformations
    to inner perimeters, creating a "brick-like" interlocking pattern that
    significantly improves part strength.
    
    Configuration:
        [brick_layers]
        enabled: False                  # Enable/disable at startup
        z_offset: 0.1                   # Z-offset in mm (positive/negative alternates)
        extrusion_multiplier: 1.05      # Extrusion compensation factor
        start_layer: 3                  # Start applying after this layer
        require_slicer_comments: True   # Require TYPE comments in G-code
        verbose: False                  # Log all transformations to console
    """
    
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.name = config.get_name()
        
        # Configuration parameters
        self.enabled = config.getboolean('enabled', False)
        self.z_offset = config.getfloat('z_offset', 0.1)
        self.extrusion_multiplier = config.getfloat('extrusion_multiplier', 1.05)
        self.start_layer = config.getint('start_layer', 3)
        self.require_comments = config.getboolean('require_slicer_comments', True)
        self.verbose = config.getboolean('verbose', False)
        
        # Runtime state
        self.current_layer = 0
        self.current_feature_type = None
        self.brick_offset_state = False  # Alternates each layer
        self.transform_map = {}          # Pre-computed transform decisions
        self.current_gcode_line = 0
        
        # Statistics
        self.stats_moves_transformed = 0
        self.stats_moves_total = 0
        
        # Register G-code commands
        self.gcode.register_command(
            'BRICK_LAYERS_ENABLE',
            self.cmd_ENABLE,
            desc="Enable brick layering transformations"
        )
        self.gcode.register_command(
            'BRICK_LAYERS_DISABLE', 
            self.cmd_DISABLE,
            desc="Disable brick layering transformations"
        )
        self.gcode.register_command(
            'BRICK_LAYERS_STATUS',
            self.cmd_STATUS,
            desc="Report current brick layers status"
        )
        
        # Hook into Klipper ready event
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        
        logging.info(f"BrickLayers initialized: z_offset={self.z_offset}, "
                     f"multiplier={self.extrusion_multiplier}, "
                     f"start_layer={self.start_layer}")
    
    def _handle_ready(self):
        """Called when Klipper is ready - set up hooks"""
        logging.info("BrickLayers: Klipper ready, installing hooks")
        
        try:
            self.sdcard = self.printer.lookup_object('virtual_sdcard')
            logging.info("BrickLayers: Connected to virtual_sdcard")
        except self.printer.command_error:
            self.sdcard = None
            logging.warn("BrickLayers: virtual_sdcard not found, "
                         "preprocessing will be disabled")
            
        # Hook into print file loading
        if self.sdcard:
            self.original_work_handler = self.sdcard.work_handler
            self.sdcard.work_handler = self._work_handler_wrapper
            logging.info("BrickLayers: Hooked into virtual_sdcard file loading")
            
        try:
            self.gcode_move = self.printer.lookup_object('gcode_move')
            # Monkey-patch the G1 command
            self.original_cmd_G1 = self.gcode_move.cmd_G1
            self.gcode_move.cmd_G1 = self._cmd_G1_wrapper
            logging.info("BrickLayers: G1 command interception installed")
        except self.printer.command_error:
            self.gcode_move = None
            logging.error("BrickLayers: gcode_move not found, "
                          "transformation disabled")
        
        logging.info(f"BrickLayers: Module ready. Config: z_offset={self.z_offset}, "
                     f"multiplier={self.extrusion_multiplier}, "
                     f"start_layer={self.start_layer}")
        
    def cmd_ENABLE(self, gcmd):
        """Enable brick layering"""
        self.enabled = True

        # Check if we need to preprocess
        if not self.transform_map:
            if self.sdcard and self.sdcard.file_path():
                gcmd.respond_info("BrickLayers: ENABLED - preprocessing G-code...")
                logging.info("BrickLayers: Triggering catch-up preprocessing")
                self._preprocess_gcode_file(self.sdcard.file_path())
                gcmd.respond_info(f"BrickLayers: Found {len(self.transform_map)} "
                                  f"transform points")
            else:
                gcmd.respond_info("BrickLayers: ENABLED (no file loaded, "
                                  "will preprocess when print starts)")
        else:
            gcmd.respond_info(f"BrickLayers: ENABLED "
                              f"({len(self.transform_map)} transform points ready)")

        logging.info(f"BrickLayers enabled via command - "
                     f"transform_map size: {len(self.transform_map)}")
    
    def cmd_DISABLE(self, gcmd):
        """Disable brick layering"""
        self.enabled = False
        gcmd.respond_info("BrickLayers: DISABLED")
        logging.info("BrickLayers disabled via command")
    
    def cmd_STATUS(self, gcmd):
        """Report status"""
        status = (
            f"BrickLayers Status:\n"
            f"  Enabled: {self.enabled}\n"
            f"  Current Layer: {self.current_layer}\n"
            f"  Z Offset: {self.z_offset}mm\n"
            f"  Extrusion Multiplier: {self.extrusion_multiplier}\n"
            f"  Start Layer: {self.start_layer}\n"
            f"  Moves Transformed: {self.stats_moves_transformed}/{self.stats_moves_total}"
        )
        gcmd.respond_info(status)
    
    def get_status(self, eventtime):
        """Return status for Moonraker/Mainsail integration"""
        return {
            'enabled': self.enabled,
            'current_layer': self.current_layer,
            'z_offset': self.z_offset,
            'extrusion_multiplier': self.extrusion_multiplier,
            'start_layer': self.start_layer,
            'moves_transformed': self.stats_moves_transformed,
            'moves_total': self.stats_moves_total,
        }
    
    def _cmd_G1_wrapper(self, gcmd):
        """Intercept and transform G1 commands"""
        self.current_gcode_line += 1
        self.stats_moves_total += 1

        # Update current layer tracking from transform map
        if self.current_gcode_line in self.transform_map:
            layer = self.transform_map[self.current_gcode_line].get('layer', 0)
            if layer > self.current_layer:
                old_layer = self.current_layer
                self.current_layer = layer
                if self.verbose:
                    logging.info(f"BrickLayers: Layer change {old_layer} -> {layer} "
                                 f"at G1 command #{self.current_gcode_line}")

        # Extract parameters
        params = {
            'X': gcmd.get_float('X', None),
            'Y': gcmd.get_float('Y', None),
            'Z': gcmd.get_float('Z', None),
            'E': gcmd.get_float('E', None),
            'F': gcmd.get_float('F', None),
        }

        # Check if this move should be transformed
        should_transform = self._should_transform_move()

        if self.verbose and self.current_gcode_line <= 5:
            # Log first few moves for debugging
            logging.info(f"BrickLayers: G1 #{self.current_gcode_line} - "
                         f"enabled={self.enabled}, should_transform={should_transform}, "
                         f"in_map={self.current_gcode_line in self.transform_map}")

        if self.enabled and should_transform:
            # Apply transformation
            params = self._apply_transform(params)
            self.stats_moves_transformed += 1

            # Execute modified command
            self._execute_transformed_move(params)
        else:
            # Pass through unchanged
            self.original_cmd_G1(gcmd)

    def _should_transform_move(self):
        """Determine if current move should be transformed"""
        if not self.enabled:
            return False
        
        # Check transform map
        if self.current_gcode_line not in self.transform_map:
            return False
            
        transform_info = self.transform_map[self.current_gcode_line]
        
        # Verify layer threshold
        if transform_info['layer'] < self.start_layer:
            return False
            
        return True

    def _apply_transform(self, params):
        """Apply brick layer transformation to move parameters"""
        transform_info = self.transform_map.get(self.current_gcode_line, {})
        offset_state = transform_info.get('offset_state', False)
        layer = transform_info.get('layer', 0)
        feature_type = transform_info.get('type', 'unknown')
        brick_z = transform_info.get('brick_z', None)

        # INJECT Z coordinate for brick layering (even if not originally present!)
        # This is the key difference from just offsetting existing Z values
        if brick_z is not None:
            original_z = params['Z']  # May be None

            # Use the pre-calculated brick layer Z height
            params['Z'] = brick_z

            if self.verbose:
                if original_z is not None:
                    logging.info(f"BrickLayers: Layer {layer} ({feature_type}) - "
                                 f"Z override: {original_z:.3f} -> {params['Z']:.3f}")
                else:
                    logging.info(f"BrickLayers: Layer {layer} ({feature_type}) - "
                                 f"Z injected: {params['Z']:.3f} (brick layer)")
            else:
                logging.debug(f"BrickLayers: Injected Z={params['Z']:.3f}mm "
                              f"at line {self.current_gcode_line}")

        # Apply extrusion multiplier if E parameter present
        if params['E'] is not None:
            original_e = params['E']
            params['E'] *= self.extrusion_multiplier

            if self.verbose:
                logging.info(f"BrickLayers: Extrusion adjust: "
                             f"{original_e:.5f} -> {params['E']:.5f} "
                             f"(x{self.extrusion_multiplier})")

        return params

    def _execute_transformed_move(self, params):
        """Execute a transformed G1 move command"""
        # Build G-code command string
        cmd_parts = ['G1']
        
        for axis in ['X', 'Y', 'Z', 'E', 'F']:
            if params[axis] is not None:
                cmd_parts.append(f'{axis}{params[axis]:.6f}')
        
        cmd_string = ' '.join(cmd_parts)
        
        # Execute via gcode runner
        try:
            self.gcode.run_script(cmd_string)
        except Exception as e:
            logging.error(f"BrickLayers: Failed to execute transformed move: {e}")
            # No easy way to "fall back" since we already consumed the gcmd
            # and increments the line counter, but run_script failure 
            # might be critical.
            raise

    def _work_handler_wrapper(self, eventtime):
        """Wrapper for virtual_sdcard work handler"""
        # Check if a new file was just loaded
        if self.sdcard.file_path() and self.enabled:
            # Only preprocess if we haven't already
            if not hasattr(self, '_last_preprocessed_file'):
                self._last_preprocessed_file = None
            
            if self.sdcard.file_path() != self._last_preprocessed_file:
                self._preprocess_gcode_file(self.sdcard.file_path())
                self._last_preprocessed_file = self.sdcard.file_path()
        
        # Call original handler
        return self.original_work_handler(eventtime)

    def _preprocess_gcode_file(self, filename):
        """
        Scan G-code file and build transformation map
        This runs ONCE when print starts
        """
        import time
        import re
        self.transform_map = {}
        self.current_layer = 0  # Reset layer tracking for new print
        self.current_gcode_line = 0  # Reset line counter for new print
        layer = 0
        current_type = None
        line_num = 0
        g1_command_num = 0  # Count G1 commands specifically
        brick_offset_state = False
        current_z = 0.0
        layer_height = 0.2  # Default, will be updated from G-code

        logging.info(f"BrickLayers: Preprocessing {filename}")
        start_time = time.time()

        try:
            with open(filename, 'r') as f:
                for line in f:
                    line_num += 1
                    line_stripped = line.strip()

                    # Track layer changes
                    if ';LAYER_CHANGE' in line_stripped:
                        layer += 1
                        # Alternate brick offset state each layer
                        if layer >= self.start_layer:
                            brick_offset_state = not brick_offset_state
                        continue

                    # Track Z height from comments
                    if line_stripped.startswith(';Z:'):
                        try:
                            current_z = float(line_stripped.split(':')[1])
                        except (ValueError, IndexError):
                            pass
                        continue

                    # Track layer height from comments
                    if line_stripped.startswith(';HEIGHT:'):
                        try:
                            layer_height = float(line_stripped.split(':')[1])
                        except (ValueError, IndexError):
                            pass
                        continue

                    # Track feature type
                    if ';TYPE:' in line_stripped:
                        try:
                            current_type = line_stripped.split(':', 1)[1].strip()
                        except IndexError:
                            pass
                        continue

                    # Process G1 commands
                    if line_stripped.startswith('G1'):
                        g1_command_num += 1

                        # Track Z from actual G1 commands (fallback)
                        if 'Z' in line:
                            z_match = re.search(r'Z([-+]?[0-9]*\.?[0-9]+)', line)
                            if z_match:
                                current_z = float(z_match.group(1))

                        # Mark inner wall moves for transformation
                        # Note: We look for 'inner' in type to catch 'Inner wall',
                        # 'Inner wall 2', etc.
                        is_inner = current_type and 'inner' in current_type.lower()

                        if is_inner and layer >= self.start_layer:
                            # Calculate brick layer Z (half a layer higher)
                            brick_z = current_z + (layer_height / 2.0)

                            # KEY FIX: Use g1_command_num instead of line_num
                            self.transform_map[g1_command_num] = {
                                'layer': layer,
                                'type': current_type,
                                'offset_state': brick_offset_state,
                                'current_z': current_z,
                                'layer_height': layer_height,
                                'brick_z': brick_z
                            }

            elapsed = time.time() - start_time
            logging.info(f"BrickLayers: Preprocessed {line_num} lines "
                         f"({g1_command_num} G1 commands) in {elapsed:.2f}s")
            logging.info(f"BrickLayers: Found {len(self.transform_map)} "
                         f"transform points")

        except Exception as e:
            logging.error(f"BrickLayers: Preprocessing failed: {e}")
            self.transform_map = {}

def load_config(config):
    """Klipper module entry point"""
    return BrickLayers(config)
