# Configuration Reference

## Basic Configuration

```ini
[brick_layers]
enabled: False                  # Enable at startup
z_offset: 0.1                   # Z-offset in mm
extrusion_multiplier: 1.05      # Extrusion compensation
start_layer: 3                  # Start layer
require_slicer_comments: True   # Require TYPE comments
```

## Parameter Details

### enabled
- **Type:** Boolean
- **Default:** `False`
- **Description:** Enable BrickLayers at Klipper startup
- **Recommended:** Keep `False`, enable via macro or command

### z_offset
- **Type:** Float (mm)
- **Default:** `0.1`
- **Range:** `0.05 - 0.2`
- **Description:** Z-offset applied to inner perimeters (alternates ±)
- **Tuning:** Start at 0.1mm, adjust based on layer height and visual inspection

### extrusion_multiplier
- **Type:** Float
- **Default:** `1.05`
- **Range:** `1.0 - 1.1`
- **Description:** Multiplier for extrusion on transformed moves
- **Tuning:** Increase if inner walls appear under-extruded

### start_layer
- **Type:** Integer
- **Default:** `3`
- **Range:** `1 - 10`
- **Description:** Layer number to begin transformations
- **Recommended:** 3-5 to ensure good bed adhesion

### require_slicer_comments
- **Type:** Boolean
- **Default:** `True`
- **Description:** Require TYPE comments in G-code for perimeter detection
- **Note:** Set to `False` for experimental geometric detection

## Advanced Options

Currently, BrickLayers focus on the core interlocking pattern. Additional geometric detection and multi-axis transforms are planned for future releases.

## Slicer-Specific Settings

### PrusaSlicer / OrcaSlicer
No special settings required - TYPE comments are automatic.

### Cura
Install "Display Info on LCD" plugin to add TYPE comments.

### Simplify3D
Manual comment insertion is required via post-processing script.
