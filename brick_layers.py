# Klipper BrickLayers Module
# Real-time brick layering transformation for improved part strength
#
# Copyright (C) 2025 Justin Hayes
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import re

class BrickLayers:
    """
    BrickLayers - Real-time G-code transformation for interlocking layer patterns
    
    This module intercepts G1 move commands and applies Z-offset transformations
    to inner perimeters, creating a "brick-like" interlocking pattern that
    significantly improves part strength.
    
    Configuration:
        [brick_layers]
        enabled: False                  # Enable/disable at startup
        z_offset: 0.1                   # Z-offset in mm (typically layer_height/2)
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
        self.transform_map = {}          # Maps G1 command number -> transform info
        self.g1_command_count = 0        # Counts G1 commands during execution
        self.last_preprocessed_file = None
        
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
        self.gcode.register_command(
            'BRICK_LAYERS_RELOAD',
            self.cmd_RELOAD,
            desc="Force reload/reprocess current G-code file"
        )
        
        # Hook into Klipper ready event
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        
        logging.info(f"BrickLayers initialized: z_offset={self.z_offset}, "
                     f"multiplier={self.extrusion_multiplier}, "
                     f"start_layer={self.start_layer}")
    
    def _handle_ready(self):
        """Called when Klipper is ready - set up hooks"""
        logging.info("BrickLayers: Klipper ready, installing hooks")
        
        # Try to hook into virtual_sdcard
        try:
            self.sdcard = self.printer.lookup_object('virtual_sdcard')
            logging.info("BrickLayers: Connected to virtual_sdcard")
            
            # Hook into the work handler to detect file loads
            self.original_work_handler = self.sdcard.work_handler
            self.sdcard.work_handler = self._work_handler_wrapper
        except:
            self.sdcard = None
            logging.warning("BrickLayers: virtual_sdcard not found, "
                          "preprocessing will be disabled")
        
        # Hook into gcode_move for G1 interception
        try:
            # Get the GCodeMove object
            gcode_move = self.printer.lookup_object('gcode_move')
            
            # Store original G1 handler
            self.original_cmd_G1 = gcode_move.cmd_G1
            
            # Replace with our wrapper
            gcode_move.cmd_G1 = self._cmd_G1_wrapper
            
            logging.info("BrickLayers: G1 command interception installed")
        except Exception as e:
            logging.error(f"BrickLayers: Failed to hook G1 command: {e}")
            self.original_cmd_G1 = None
        
        logging.info(f"BrickLayers: Module ready")
    
    def cmd_ENABLE(self, gcmd):
        """Enable brick layering"""
        self.enabled = True
        
        # Check if we need to preprocess
        if not self.transform_map:
            try:
                current_file = self.sdcard.file_path() if self.sdcard else None
            except:
                current_file = None
                
            if current_file:
                gcmd.respond_info("BrickLayers: ENABLED - preprocessing G-code...")
                logging.info("BrickLayers: Triggering catch-up preprocessing")
                self._preprocess_gcode_file(current_file)
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
            f"  G1 Commands Executed: {self.g1_command_count}\n"
            f"  Transform Points Loaded: {len(self.transform_map)}\n"
            f"  Moves Transformed: {self.stats_moves_transformed}/{self.stats_moves_total}"
        )
        gcmd.respond_info(status)
        
        if self.verbose and self.transform_map:
            # Show next few upcoming transforms
            upcoming = []
            for cmd_num in sorted(self.transform_map.keys()):
                if cmd_num > self.g1_command_count:
                    upcoming.append(cmd_num)
                    if len(upcoming) >= 5:
                        break
            if upcoming:
                gcmd.respond_info(f"  Next transforms at G1 commands: {upcoming}")
    
    def cmd_RELOAD(self, gcmd):
        """Force reload of current file"""
        if not self.sdcard:
            gcmd.respond_info("BrickLayers: No virtual_sdcard available")
            return
        
        try:
            current_file = self.sdcard.file_path()
        except:
            current_file = None
        
        if not current_file:
            gcmd.respond_info("BrickLayers: No file currently loaded")
            return
        
        gcmd.respond_info(f"BrickLayers: Reprocessing {current_file}...")
        self._preprocess_gcode_file(current_file)
        gcmd.respond_info("BrickLayers: Reload complete")
    
    def get_status(self, eventtime):
        """Return status for Moonraker/Mainsail integration"""
        return {
            'enabled': self.enabled,
            'current_layer': self.current_layer,
            'z_offset': self.z_offset,
            'extrusion_multiplier': self.extrusion_multiplier,
            'start_layer': self.start_layer,
            'g1_commands_executed': self.g1_command_count,
            'transform_points': len(self.transform_map),
            'moves_transformed': self.stats_moves_transformed,
            'moves_total': self.stats_moves_total,
        }
    
    def _work_handler_wrapper(self, eventtime):
        """Wrapper for virtual_sdcard work handler to detect file loads"""
        # Get current file path safely
        try:
            current_file = self.sdcard.file_path()
        except:
            current_file = None
        
        # Check if a new file was loaded
        if current_file and self.enabled:
            if current_file != self.last_preprocessed_file:
                logging.info(f"BrickLayers: New file detected: {current_file}")
                self._preprocess_gcode_file(current_file)
                self.last_preprocessed_file = current_file
        
        # Call original handler
        return self.original_work_handler(eventtime)
    
    def _cmd_G1_wrapper(self, gcmd):
        """Intercept and potentially transform G1 commands"""
        # Increment our command counter
        self.g1_command_count += 1
        self.stats_moves_total += 1
        
        # Update current layer tracking from transform map
        if self.g1_command_count in self.transform_map:
            layer = self.transform_map[self.g1_command_count].get('layer', 0)
            if layer > self.current_layer:
                old_layer = self.current_layer
                self.current_layer = layer
                if self.verbose:
                    logging.info(f"BrickLayers: Layer change {old_layer} -> {layer} "
                                 f"at G1 command #{self.g1_command_count}")
        
        # Check if this command should be transformed
        if self.enabled and self.g1_command_count in self.transform_map:
            transform_info = self.transform_map[self.g1_command_count]
            
            # Apply the transformation
            self._execute_transformed_move(gcmd, transform_info)
            self.stats_moves_transformed += 1
            
        else:
            # Pass through unchanged
            if self.original_cmd_G1:
                self.original_cmd_G1(gcmd)
            else:
                # Fallback: shouldn't happen, but just in case
                logging.error("BrickLayers: No original G1 handler available!")
    
    def _execute_transformed_move(self, gcmd, transform_info):
        """Execute a G1 move with brick layer transformation applied"""
        # Build new command with transformed Z
        cmd_parts = ['G1']
        
        # Add X if present
        try:
            x = gcmd.get_float('X')
            cmd_parts.append(f"X{x:.6f}")
        except:
            pass
        
        # Add Y if present
        try:
            y = gcmd.get_float('Y')
            cmd_parts.append(f"Y{y:.6f}")
        except:
            pass
        
        # ALWAYS add/override Z with brick layer height
        cmd_parts.append(f"Z{transform_info['brick_z']:.6f}")
        
        # Add E if present, with multiplier applied
        try:
            original_e = gcmd.get_float('E')
            modified_e = original_e * self.extrusion_multiplier
            cmd_parts.append(f"E{modified_e:.6f}")
        except:
            pass
        
        # Add F if present
        try:
            f = gcmd.get_float('F')
            cmd_parts.append(f"F{f:.6f}")
        except:
            pass
        
        cmd_string = ' '.join(cmd_parts)
        
        # Log if verbose
        if self.verbose:
            try:
                original_z = gcmd.get_float('Z')
                logging.info(f"BrickLayers: G1 #{self.g1_command_count} - "
                           f"Layer {transform_info['layer']} ({transform_info['type']}) - "
                           f"Z: {original_z:.3f} -> {transform_info['brick_z']:.3f}")
            except:
                logging.info(f"BrickLayers: G1 #{self.g1_command_count} - "
                           f"Layer {transform_info['layer']} ({transform_info['type']}) - "
                           f"Z injected: {transform_info['brick_z']:.3f}")
        
        # Execute the transformed command
        try:
            self.gcode.run_script(cmd_string)
        except Exception as e:
            logging.error(f"BrickLayers: Failed to execute transformed move: {e}")
            logging.error(f"  Command: {cmd_string}")
            raise
    
    def _preprocess_gcode_file(self, filename):
        """
        Scan G-code file and build transformation map.
        This runs ONCE when a print file is loaded.
        
        Key: We count G1 COMMANDS, not file lines, so the numbering
        matches what we'll see during execution.
        """
        import time
        
        self.transform_map = {}
        self.g1_command_count = 0  # Reset for new file
        self.current_layer = 0     # Reset for new file
        self.stats_moves_transformed = 0
        self.stats_moves_total = 0
        
        # Preprocessing state
        layer = 0
        current_type = None
        brick_offset_state = False
        current_z = 0.0
        layer_height = 0.2  # Default
        g1_count = 0  # Count G1 commands during preprocessing
        line_count = 0
        
        logging.info(f"BrickLayers: Preprocessing {filename}")
        start_time = time.time()
        
        feature_type_seen = {}  # Track what feature types we see
        
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line_count += 1
                    line_stripped = line.strip()
                    
                    # Track layer changes (common in most slicers)
                    if ';LAYER_CHANGE' in line_stripped or line_stripped.startswith(';LAYER:'):
                        layer += 1
                        # Alternate brick offset state each layer (after start_layer)
                        if layer >= self.start_layer:
                            brick_offset_state = not brick_offset_state
                        
                        if self.verbose:
                            logging.info(f"BrickLayers: Layer {layer} "
                                       f"(offset_state={brick_offset_state})")
                        continue
                    
                    # Track Z height from comments (PrusaSlicer/OrcaSlicer style)
                    if line_stripped.startswith(';Z:'):
                        try:
                            current_z = float(line_stripped.split(':')[1])
                        except (ValueError, IndexError):
                            pass
                        continue
                    
                    # Track layer height from comments
                    if line_stripped.startswith(';HEIGHT:') or line_stripped.startswith(';layer_height'):
                        try:
                            layer_height = float(line_stripped.split(':')[1].split()[0])
                            if self.verbose:
                                logging.info(f"BrickLayers: Detected layer height: {layer_height}mm")
                        except (ValueError, IndexError):
                            pass
                        continue
                    
                    # Track feature type (critical for identifying inner walls!)
                    if ';TYPE:' in line_stripped:
                        try:
                            current_type = line_stripped.split(':', 1)[1].strip()
                            
                            # Track what types we see for debugging
                            feature_type_seen[current_type] = feature_type_seen.get(current_type, 0) + 1
                            
                            if self.verbose:
                                logging.info(f"BrickLayers: Feature type: {current_type}")
                        except IndexError:
                            pass
                        continue
                    
                    # Check if this is a G1 move command
                    if line_stripped.startswith('G1'):
                        # Increment G1 counter (THIS IS THE KEY)
                        g1_count += 1
                        
                        # Extract Z from the actual G1 command if present
                        if 'Z' in line_stripped:
                            z_match = re.search(r'Z([-+]?[0-9]*\.?[0-9]+)', line_stripped)
                            if z_match:
                                current_z = float(z_match.group(1))
                        
                        # Determine if this move should be transformed
                        # Look for "inner" in the type name to catch:
                        # - "Internal perimeter" (PrusaSlicer)
                        # - "Inner wall" (Bambu Studio)
                        # - "Internal perimeters" (SuperSlicer)
                        # - "WALL-INNER" (Cura - lowercase conversion catches this)
                        is_inner = current_type and 'inner' in current_type.lower()
                        
                        if is_inner and layer >= self.start_layer:
                            # Calculate brick layer Z (half layer height offset)
                            brick_z = current_z + (layer_height / 2.0)
                            
                            # Store transform info keyed by G1 command number
                            self.transform_map[g1_count] = {
                                'layer': layer,
                                'type': current_type,
                                'offset_state': brick_offset_state,
                                'current_z': current_z,
                                'layer_height': layer_height,
                                'brick_z': brick_z,
                                'file_line': line_count  # Keep for debugging
                            }
                            
                            if self.verbose and len(self.transform_map) <= 10:
                                logging.info(f"BrickLayers: Marked G1 command #{g1_count} "
                                           f"for transformation (file line {line_count}, "
                                           f"layer {layer}, type: {current_type}, "
                                           f"Z: {current_z:.3f} -> {brick_z:.3f})")
            
            elapsed = time.time() - start_time
            logging.info(f"BrickLayers: Preprocessing complete in {elapsed:.2f}s")
            logging.info(f"BrickLayers: Processed {line_count} lines, found {g1_count} G1 commands")
            logging.info(f"BrickLayers: Marked {len(self.transform_map)} commands for transformation")
            
            # Report feature types seen (helpful for debugging)
            if feature_type_seen:
                logging.info(f"BrickLayers: Feature types detected:")
                for ftype, count in sorted(feature_type_seen.items()):
                    is_inner = 'inner' in ftype.lower()
                    marker = " <-- WILL TRANSFORM" if is_inner else ""
                    logging.info(f"  {ftype}: {count} occurrences{marker}")
            
            # Warn if no transforms found
            if not self.transform_map:
                logging.warning("BrickLayers: No inner perimeter moves found! "
                              "Check that your slicer outputs ;TYPE: comments.")
                if not feature_type_seen:
                    logging.warning("BrickLayers: No ;TYPE: comments found at all. "
                                  "Your slicer may not be compatible, or comments may be disabled.")
            
        except Exception as e:
            logging.error(f"BrickLayers: Preprocessing failed: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.transform_map = {}

def load_config(config):
    """Klipper module entry point"""
    return BrickLayers(config)
