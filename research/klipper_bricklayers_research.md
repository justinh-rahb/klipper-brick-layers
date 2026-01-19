# Real-Time BrickLayers in Klipper: Research & Implementation Plan

## Executive Summary

BrickLayers is a G-code post-processor that creates interlocking "brick-like" layer patterns by shifting inner perimeters in Z-height. This creates mechanical interlocking similar to masonry, dramatically improving part strength without changing external appearance.

**The Goal**: Port this from a Python post-processor to a **native Klipper module** that operates in real-time during printing.

---

## How BrickLayers Works (Current Implementation)

### Core Algorithm

Based on the repository analysis:

1. **Parses G-code** to identify layer changes and perimeter types
2. **Detects inner perimeters** (orphaned loops) vs external perimeters
3. **Applies Z-offset transformations** to inner perimeters:
   - Alternates Z-height by small amounts (typically 0.1-0.2mm)
   - Creates "brick-like" offset pattern between layers
   - Maintains external surface smoothness
4. **Adjusts extrusion multiplier** to compensate for the non-planar movement
5. **Handles travel moves** with retraction/wiping to prevent stringing

### Key Detection Patterns

From the code structure:
- `;LAYER_CHANGE` comments mark layer boundaries
- `;TYPE:Inner wall` / `;TYPE:External wall` marks perimeter types  
- `;WIDTH:` comments indicate extrusion width
- Wall depth detection (counting perimeter loops from outside-in)

### Current Limitations

- Requires post-processing (no live preview)
- Adds time to the slicing workflow
- Can't be adjusted mid-print
- No integration with Klipper's motion planning

---

## Klipper Architecture for Real-Time Implementation

### 1. G-code Command Flow in Klipper

```
Slicer → G-code File → gcode.py → gcode_move.py → ToolHead → Kinematics → MCU
```

**Critical insight**: Commands flow through `klippy/extras/gcode_move.py` which handles:
- G92 (set position)
- G90/G91 (absolute/relative mode)
- M82/M83 (extruder modes)
- **G1 move command translation**

This is our interception point!

### 2. Klipper Module System

Modules are loaded from `klippy/extras/` when a matching config section exists:

```python
# If printer.cfg contains [brick_layers]
# Klipper automatically loads klippy/extras/brick_layers.py

def load_config(config):
    return BrickLayers(config)
```

### 3. Existing G-code Transformation Examples

Klipper already has several movement transformation modules:

- **bed_mesh**: Applies Z-compensation based on bed topology
- **bed_tilt**: Adds Z-offset based on X/Y position
- **skew_correction**: Transforms XY coordinates to fix mechanical skew
- **gcode_arcs**: Converts G2/G3 arc commands to segmented moves

**These prove it's possible to transform G1 commands in real-time!**

---

## Implementation Strategy

### Approach 1: Transform Layer (Recommended)

Create a transform that sits between `gcode_move.py` and `ToolHead`:

```python
# klippy/extras/brick_layers.py

class BrickLayers:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        
        # Configuration
        self.enabled = config.getboolean('enabled', False)
        self.start_layer = config.getint('start_layer', 3)
        self.extrusion_multiplier = config.getfloat('extrusion_multiplier', 1.05)
        self.z_offset = config.getfloat('z_offset', 0.1)  # Amount to shift Z
        
        # State tracking
        self.current_layer = 0
        self.current_feature = None  # Track TYPE comments
        self.inner_wall_depth = 0
        self.brick_offset_state = 0  # 0 or 1 for alternating pattern
        
        # Register commands
        self.gcode.register_command('BRICK_LAYERS_ENABLE', self.cmd_ENABLE)
        self.gcode.register_command('BRICK_LAYERS_DISABLE', self.cmd_DISABLE)
        
        # Hook into move command processing
        self.gcode_move = self.printer.lookup_object('gcode_move')
        self.original_cmd_G1 = self.gcode_move.cmd_G1
        self.gcode_move.cmd_G1 = self._cmd_G1_wrapper
        
    def _cmd_G1_wrapper(self, gcmd):
        """Intercept G1 commands and apply brick layering transform"""
        
        if not self.enabled or self.current_layer < self.start_layer:
            # Pass through untransformed
            return self.original_cmd_G1(gcmd)
        
        # Check if this is an inner perimeter move
        if self._is_inner_perimeter():
            # Apply Z transformation
            params = self._get_move_params(gcmd)
            
            if params.get('Z') is not None:
                # Apply brick offset
                offset = self.z_offset if self.brick_offset_state else -self.z_offset
                params['Z'] += offset
            
            # Adjust extrusion if E parameter present
            if params.get('E') is not None:
                params['E'] *= self.extrusion_multiplier
            
            # Create modified command
            self._execute_modified_move(params)
        else:
            # External perimeter or other - pass through
            return self.original_cmd_G1(gcmd)
    
    def _is_inner_perimeter(self):
        """Determine if current move is an inner perimeter"""
        # Logic based on tracking TYPE comments and depth
        return (self.current_feature == 'Inner wall' and 
                self.inner_wall_depth > 0)
```

### Approach 2: Macro Override (Simpler but Limited)

Override G1 using a gcode_macro with Jinja2:

```ini
[gcode_macro G1]
rename_existing: G1.1
gcode:
    {% if printer["brick_layers"].enabled %}
        # Check if inner perimeter and transform
        {% set z_offset = printer["brick_layers"].get_offset() %}
        G1.1 Z{params.Z|float + z_offset} E{params.E|float * 1.05}
    {% else %}
        G1.1 {rawparams}
    {% endif %}
```

**Problem**: Macros are evaluated at call-time, making complex state tracking difficult.

### Approach 3: Python Extra with Transform Registration

Most elegant - register as a coordinate transform like bed_mesh:

```python
class BrickLayers:
    def __init__(self, config):
        # ... init code ...
        
        # Register as a transform
        gcode_move = self.printer.lookup_object('gcode_move')
        gcode_move.set_move_transform(self, force=False)
    
    def get_position(self):
        """Return current position in our transformed coordinate system"""
        # Get base position
        pos = self.base_transform.get_position()
        
        # Apply brick layer transform to Z if needed
        if self._should_transform():
            offset = self._calculate_z_offset(pos)
            pos[2] += offset
        
        return pos
    
    def move(self, newpos, speed):
        """Transform a requested move"""
        if self._should_transform():
            # Modify Z component
            newpos = list(newpos)
            newpos[2] += self._calculate_z_offset(newpos)
            
            # Adjust extrusion (E is part of move in Klipper)
            # This is trickier - may need to hook into extruder directly
        
        # Pass to next transform in chain
        self.base_transform.move(newpos, speed)
```

---

## Critical Challenges & Solutions

### Challenge 1: Detecting Inner vs External Perimeters

**Problem**: BrickLayers relies on slicer comments (`; TYPE:Inner wall`). What if comments aren't present?

**Solutions**:
1. **Require slicer comments** (document which slicers support this)
2. **Geometric detection**: Track recent moves to detect loop closure
3. **Hybrid**: Use comments if present, fall back to geometry

### Challenge 2: Layer Change Detection

**Current**: BrickLayers looks for `;LAYER_CHANGE` comments

**Klipper Alternative**:
- Hook into the `SDCARD_PRINT_FILE` virtual SD system
- Parse the file ahead-of-time to find layer boundaries
- Or: Detect layer changes by Z movement patterns

### Challenge 3: Extrusion Adjustment

**Problem**: Klipper separates movement (XYZ) from extrusion (E) in different code paths.

**Solution**: 
- Override both the move transform AND extruder commands
- Or: Use a `SET_EXTRUDE_FACTOR` multiplier when in brick mode
- Track moves that should get modified extrusion

### Challenge 4: Preview in Slicer

**Problem**: Slicer won't show the brick layering effect

**Partial Solutions**:
1. **Accept limitation** - most Klipper features (input shaping, PA) aren't previewed either
2. **Post-process export**: Add a "export transformed G-code" command
3. **Moonraker integration**: Create a preview generator for Mainsail/Fluidd

### Challenge 5: Performance

**Problem**: Real-time transformation adds computational overhead

**Solutions**:
- **Pre-parse file** when print starts to identify inner perimeter segments
- **Cache decisions** per layer
- **Use C extensions** for hot paths (Klipper supports this via chelper/)
- Profile and optimize - modern Raspberry Pis are quite powerful

---

## Proposed Architecture: The "Hybrid" Approach

Combine the best of all approaches:

```python
class BrickLayers:
    """
    Real-time brick layering transform for Klipper
    
    Architecture:
    1. Pre-parse G-code file when print starts
    2. Build a map of [layer, line_number] -> transform_type
    3. Hook into move command chain
    4. Apply transform based on pre-built map
    """
    
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        
        # Config
        self.z_offset = config.getfloat('z_offset', 0.1)
        self.extrusion_multiplier = config.getfloat('extrusion_multiplier', 1.05)
        self.start_layer = config.getint('start_layer', 3)
        
        # Runtime state
        self.enabled = False
        self.transform_map = {}  # {line_num: transform_params}
        self.current_line = 0
        self.brick_state = False  # Alternates per layer
        
        # Register commands
        self.gcode.register_command('BRICK_LAYERS_ENABLE', self.cmd_ENABLE)
        self.gcode.register_command('BRICK_LAYERS_STATUS', self.cmd_STATUS)
        
        # Hook into virtual_sdcard for file preprocessing
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
    
    def _handle_ready(self):
        """Called when Klipper is ready"""
        # Look for virtual_sdcard module
        try:
            self.sdcard = self.printer.lookup_object('virtual_sdcard')
            # Monkey-patch the do_resume method to preprocess file
            self.original_do_resume = self.sdcard.do_resume
            self.sdcard.do_resume = self._do_resume_wrapper
        except:
            logging.info("BrickLayers: virtual_sdcard not found, preprocessing disabled")
    
    def _do_resume_wrapper(self):
        """Intercept print start to preprocess the file"""
        # Get current file path
        filename = self.sdcard.file_path
        
        if filename and self.enabled:
            logging.info(f"BrickLayers: Preprocessing {filename}")
            self._preprocess_file(filename)
        
        return self.original_do_resume()
    
    def _preprocess_file(self, filename):
        """
        Scan G-code file and build transform map
        This runs ONCE when print starts
        """
        self.transform_map = {}
        layer = 0
        current_type = None
        line_num = 0
        
        with open(filename, 'r') as f:
            for line in f:
                line_num += 1
                
                # Track layer changes
                if ';LAYER_CHANGE' in line:
                    layer += 1
                    continue
                
                # Track feature type
                if ';TYPE:' in line:
                    current_type = line.split(':')[1].strip()
                    continue
                
                # Mark inner wall moves for transformation
                if line.startswith('G1') and current_type == 'Inner wall' and layer >= self.start_layer:
                    self.transform_map[line_num] = {
                        'layer': layer,
                        'type': 'inner_wall',
                        'apply_offset': True
                    }
        
        logging.info(f"BrickLayers: Mapped {len(self.transform_map)} transform points")
    
    def _cmd_G1_wrapper(self, gcmd):
        """Apply transformation based on pre-built map"""
        self.current_line += 1
        
        transform = self.transform_map.get(self.current_line)
        
        if transform and transform['apply_offset']:
            # Get move parameters
            orig_params = {
                'X': gcmd.get_float('X', None),
                'Y': gcmd.get_float('Y', None),
                'Z': gcmd.get_float('Z', None),
                'E': gcmd.get_float('E', None),
                'F': gcmd.get_float('F', None),
            }
            
            # Apply Z offset (alternates per layer)
            if orig_params['Z'] is not None:
                offset = self.z_offset if self.brick_state else -self.z_offset
                orig_params['Z'] += offset
            
            # Apply extrusion multiplier
            if orig_params['E'] is not None:
                orig_params['E'] *= self.extrusion_multiplier
            
            # Build new command string
            new_cmd = 'G1'
            for axis, value in orig_params.items():
                if value is not None:
                    new_cmd += f' {axis}{value}'
            
            # Execute modified command
            self.gcode.run_script(new_cmd)
        else:
            # Pass through unchanged
            self.original_cmd_G1(gcmd)
```

---

## Configuration Example

```ini
[brick_layers]
enabled: False                  # Start disabled, enable via macro or command
z_offset: 0.1                   # mm to shift inner walls
extrusion_multiplier: 1.05      # compensate for non-planar extrusion
start_layer: 3                  # begin brick layering after layer 3
require_slicer_comments: True   # fail if TYPE comments not found

# Optional: specific feature types to transform
transform_types: Inner wall, Inner wall 2

# Optional: exclude certain layers
# exclude_layers: 1, 2, 100-105
```

---

## Integration with Mainsail/Fluidd

### Add UI Controls

Create a Mainsail power device or custom panel:

```yaml
# moonraker.conf
[power brick_layers]
type: klipper_device
object_name: brick_layers
```

### Macro Shortcuts

```ini
[gcode_macro BRICK_ON]
gcode:
    BRICK_LAYERS_ENABLE

[gcode_macro BRICK_OFF]
gcode:
    BRICK_LAYERS_DISABLE
    
[gcode_macro BRICK_STATUS]
gcode:
    BRICK_LAYERS_STATUS
```

---

## Development Roadmap

### Phase 1: Proof of Concept (1-2 weeks)
- [ ] Create basic module that hooks G1 commands
- [ ] Implement simple Z-offset on ALL moves (no detection yet)
- [ ] Test that it doesn't crash Klipper
- [ ] Verify moves are being transformed

### Phase 2: Layer Detection (1 week)
- [ ] Add slicer comment parsing
- [ ] Track layer changes
- [ ] Implement start_layer logic
- [ ] Test with real G-code from OrcaSlicer/PrusaSlicer

### Phase 3: Perimeter Detection (1-2 weeks)
- [ ] Parse TYPE comments
- [ ] Differentiate inner vs external perimeters
- [ ] Only transform inner walls
- [ ] Test on complex prints (Benchy, etc)

### Phase 4: Preprocessing System (1 week)
- [ ] Implement file scanning on print start
- [ ] Build transform map
- [ ] Optimize for performance

### Phase 5: Extrusion Compensation (1 week)
- [ ] Hook extrusion commands
- [ ] Apply multiplier to transformed moves
- [ ] Verify no under/over-extrusion

### Phase 6: Polish & Documentation (1 week)
- [ ] Add configuration validation
- [ ] Error handling
- [ ] Write user documentation
- [ ] Create example configs for popular printers

### Phase 7: Community Testing (2-4 weeks)
- [ ] Beta release
- [ ] Gather feedback
- [ ] Fix bugs
- [ ] Optimize based on real-world usage

---

## Testing Strategy

### Unit Tests
- Mock Klipper objects
- Test transform calculations
- Verify layer detection logic
- Test comment parsing

### Integration Tests
- Test with sample G-code files
- Verify no conflicts with bed_mesh, input_shaper, etc.
- Test error handling (bad G-code, missing comments)

### Hardware Tests
- Print calibration cubes
- Measure actual Z-offsets with calipers
- Strength testing (compare brick vs non-brick prints)
- Visual inspection (no artifacts on external surfaces)

---

## Alternative/Complementary Ideas

### 1. **Slicer Plugin Instead**
- Write a PrusaSlicer/OrcaSlicer plugin
- Would give preview capability
- But loses "live tuning" benefit

### 2. **Hybrid: Plugin + Klipper Module**
- Plugin adds metadata to G-code
- Klipper module reads metadata and applies transform
- Best of both worlds?

### 3. **Moonraker Preprocessing Service**
- Moonraker intercepts uploads
- Automatically processes files
- Caches transformed version
- No Klipper modification needed
- But less dynamic

### 4. **MQTT Control Integration**
Since you're building Bambu-Moonraker bridge:
- Expose brick layer controls via MQTT
- Allow external tools to enable/disable
- Report status via MQTT
- Could build a dedicated tuning UI

---

## Questions to Resolve

1. **Performance**: Can a Raspberry Pi 3/4 handle real-time transformation without stuttering?
   - Likely yes if we pre-process
   - May need C extension for hot path

2. **Compatibility**: Which slicers reliably emit TYPE comments?
   - PrusaSlicer: Yes
   - OrcaSlicer: Yes
   - Cura: Needs plugin
   - Simplify3D: Unknown

3. **Extrusion Math**: How exactly does BrickLayers calculate the extrusion multiplier?
   - Need to examine source code more closely
   - May need to account for path length changes due to Z offset

4. **Conflicts**: Will this break existing transforms (bed_mesh, skew_correction)?
   - Need to test transform chaining
   - May need careful ordering

5. **File Format**: Does this work with binary G-code (Prusa)?
   - No - binary G-code doesn't support comments
   - Document this limitation

---

## Success Criteria

1. ✅ No impact on print quality when disabled
2. ✅ Inner perimeters show visible brick pattern when enabled
3. ✅ External surfaces remain smooth (no artifacts)
4. ✅ No performance degradation (<1% CPU increase)
5. ✅ Works with standard slicers (PrusaSlicer, OrcaSlicer)
6. ✅ Can be enabled/disabled mid-print (bonus)
7. ✅ Clean configuration interface
8. ✅ No conflicts with other Klipper features

---

## Resources & References

### Klipper Documentation
- Code Overview: https://www.klipper3d.org/Code_Overview.html
- Command Templates: https://www.klipper3d.org/Command_Templates.html
- Config Reference: https://www.klipper3d.org/Config_Reference.html

### BrickLayers
- GitHub: https://github.com/GeekDetour/BrickLayers
- Hackaday Article: https://hackaday.com/2025/01/23/brick-layer-post-processor

### Klipper Module Examples
- gcode_move.py: Movement transformation
- bed_mesh.py: Z-compensation
- skew_correction.py: Coordinate transformation
- exclude_object.py: Comment parsing

### Community Resources
- Klipper Discourse: https://klipper.discourse.group/
- Voron Discord: #klipper_firmware channel
- r/klippers subreddit

---

## Next Steps

1. **Clone Klipper source**: Study existing transform modules
2. **Set up dev environment**: Klipper in a VM or spare Pi
3. **Prototype the hook**: Get G1 interception working
4. **Parse BrickLayers source**: Understand exact algorithm
5. **Build MVP**: Simple Z-offset on inner walls
6. **Test on real printer**: Verify it doesn't break anything

---

## Conclusion

Real-time BrickLayers in Klipper is **absolutely feasible**. The architecture exists to support it through Klipper's module system and transformation chain. The main challenges are:

1. Efficiently detecting which moves to transform
2. Hooking into the right places in Klipper's code
3. Not breaking existing functionality

The **Hybrid Approach** (pre-process + runtime transform) seems most promising:
- Pre-scan file at print start = fast runtime decisions
- Hook move commands = real-time transformation  
- Clean module = no Klipper core modifications

This could be a killer feature for the open-source 3D printing community - especially combined with your Mainsail integration work!

Let's build this thing! 🚀
