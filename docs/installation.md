# Installation Guide

## Prerequisites

- Klipper firmware installed
- SSH access to your printer's host (Raspberry Pi, etc.)
- Compatible slicer (PrusaSlicer, OrcaSlicer recommended)

## Installation Steps

### 1. Clone the Repository

```bash
cd ~/
git clone https://github.com/yourusername/klipper-brick-layers
cd klipper-brick-layers
```

### 2. Run the Installer

```bash
./install.sh
```

This will create a symlink in `~/klipper/klippy/extras/brick_layers.py`

### 3. Update Configuration

Add to your `printer.cfg`:

```ini
[brick_layers]
enabled: False
z_offset: 0.1
extrusion_multiplier: 1.05
start_layer: 3
```

### 4. Restart Klipper

Via Mainsail/Fluidd console:
```
RESTART
```

Or via command line:
```bash
sudo systemctl restart klipper
```

### 5. Verify Installation

```
BRICK_LAYERS_STATUS
```

You should see status output without errors.

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues.
