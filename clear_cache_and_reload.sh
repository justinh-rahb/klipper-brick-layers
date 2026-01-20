#!/bin/bash
# Script to clear Python bytecode cache and reload BrickLayers module

echo "BrickLayers Cache Clear and Reload Script"
echo "=========================================="
echo ""

# Find and remove all Python cache files for brick_layers
echo "1. Removing Python bytecode cache files..."
find ~/klipper -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find ~/klipper -name "brick_layers.pyc" -delete 2>/dev/null
find ~/klipper -name "*.pyc" -path "*/extras/*" -delete 2>/dev/null
echo "   Cache files cleared."
echo ""

# Verify the source file is in place
echo "2. Verifying brick_layers.py is in place..."
if [ -f ~/klipper/klippy/extras/brick_layers.py ]; then
    echo "   ✓ Found: ~/klipper/klippy/extras/brick_layers.py"
    grep -q "self.verbose = config.getboolean('verbose', False)" ~/klipper/klippy/extras/brick_layers.py
    if [ $? -eq 0 ]; then
        echo "   ✓ Verbose option is present in the code"
    else
        echo "   ✗ WARNING: Verbose option NOT found in the code!"
    fi
else
    echo "   ✗ File not found!"
    exit 1
fi
echo ""

# Restart Klipper service
echo "3. Restarting Klipper service..."
sudo systemctl restart klipper
if [ $? -eq 0 ]; then
    echo "   ✓ Klipper service restarted successfully"
else
    echo "   ✗ Failed to restart Klipper service"
    exit 1
fi
echo ""

# Wait for Klipper to start
echo "4. Waiting for Klipper to initialize..."
sleep 3
echo "   Done."
echo ""

echo "=========================================="
echo "Cache cleared and Klipper restarted!"
echo ""
echo "Next steps:"
echo "  1. Check Klipper logs: tail -f /tmp/klippy.log"
echo "  2. Try your configuration with the 'verbose' option again"
echo "  3. Use FIRMWARE_RESTART in Klipper console if needed"
echo ""
