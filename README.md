# Klipper BrickLayers

Real-time brick layering transformation for Klipper 3D printer firmware.

## 🧱 What is BrickLayers?

BrickLayers improves 3D print strength by applying Z-offset transformations to inner perimeters, creating interlocking "brick-like" layer patterns. This dramatically increases part strength without affecting external surface quality.

**Key Features:**
- ✨ Real-time transformation (no post-processing needed!)
- 🎯 Smart perimeter detection via slicer comments
- 🔧 Live enable/disable during prints
- 📊 Mainsail/Fluidd integration ready
- ⚡ Optimized with file preprocessing

## 🚀 Installation

```bash
cd ~/
git clone https://github.com/justinh-rahb/klipper-brick-layers
cd klipper-brick-layers
./install.sh
```

Then add to your `printer.cfg`:

```ini
[brick_layers]
enabled: False                  # Start disabled
z_offset: 0.1                   # Z-offset in mm
extrusion_multiplier: 1.05      # Extrusion compensation
start_layer: 3                  # Begin after layer 3
verbose: False                  # Log transformations to console
```

Restart Klipper: `RESTART`

## 📖 Usage

### Basic Commands

```gcode
BRICK_LAYERS_ENABLE    # Turn on brick layering
BRICK_LAYERS_DISABLE   # Turn off brick layering
BRICK_LAYERS_STATUS    # Show current status
```

### Macros

See `examples/macros.cfg` for ready-to-use macros.

## ⚙️ Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `False` | Enable at startup |
| `z_offset` | `0.1` | Z-offset in mm (alternates ±) |
| `extrusion_multiplier` | `1.05` | Extrusion compensation factor |
| `start_layer` | `3` | Layer to start transformations |
| `require_slicer_comments` | `True` | Require TYPE comments in G-code |
| `verbose` | `False` | Log all transformations to console |

## 🎯 Slicer Setup

BrickLayers requires slicer-generated comments to identify perimeter types.

### PrusaSlicer / OrcaSlicer
✅ Works out of the box! These slicers automatically add TYPE comments.

### Cura
⚠️ Requires the "Display Info on LCD" plugin or similar to add comments.

### Simplify3D
❓ Untested - may require custom scripts.

## 🧪 Testing

Run the test suite:

```bash
cd tests
python3 test_brick_layers.py
```

Validate your G-code has required comments:

```bash
./scripts/validate_gcode.py ~/path/to/your/file.gcode
```

## 📚 Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Reference](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)

## 🤝 Contributing

Contributions welcome! This is an experimental module - testing, feedback, and PRs appreciated.

## 📄 License

GPLv3 - See LICENSE file

## 🙏 Credits

Based on the original [BrickLayers post-processor](https://github.com/GeekDetour/BrickLayers) by Everson Siqueira.

Ported to Klipper by Justin Hayes.

## ⚠️ Disclaimer

This is experimental software. Always supervise your prints. Not responsible for failed prints, broken printers, or spontaneous brick formations.
