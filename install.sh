#!/bin/bash
# BrickLayers installation script

set -e

KLIPPER_DIR="$HOME/klipper"
KLIPPER_EXTRAS="$KLIPPER_DIR/klippy/extras"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧱 Installing Klipper BrickLayers..."

# Check for Klipper installation
if [ ! -d "$KLIPPER_DIR" ]; then
    echo "❌ Klipper not found at $KLIPPER_DIR"
    echo "Please install Klipper first or set KLIPPER_DIR environment variable"
    exit 1
fi

if [ ! -d "$KLIPPER_EXTRAS" ]; then
    echo "❌ Klipper extras directory not found at $KLIPPER_EXTRAS"
    exit 1
fi

echo "✅ Found Klipper at $KLIPPER_DIR"

# Install the module
echo "📦 Installing brick_layers.py..."
ln -sf "$SCRIPT_DIR/brick_layers.py" "$KLIPPER_EXTRAS/brick_layers.py"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Add [brick_layers] section to your printer.cfg"
echo "     See examples/printer.cfg.example for reference"
echo "  2. Restart Klipper: RESTART"
echo "  3. Verify: BRICK_LAYERS_STATUS"
echo ""
echo "📖 Documentation: https://github.com/justinh-rahb/klipper-brick-layers"
