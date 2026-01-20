#!/bin/bash
# Diagnostic script to investigate the verbose validation issue

echo "BrickLayers Verbose Option Diagnostic"
echo "======================================"
echo ""

# Check if the file exists and has the verbose option
echo "1. Checking brick_layers.py file..."
BRICK_FILE=~/klipper/klippy/extras/brick_layers.py
if [ -f "$BRICK_FILE" ]; then
    echo "   ✓ File exists: $BRICK_FILE"
    echo ""
    echo "   Verbose-related lines:"
    grep -n "verbose" "$BRICK_FILE"
    echo ""
else
    echo "   ✗ File not found: $BRICK_FILE"
    exit 1
fi

# Check for Python cache files
echo "2. Checking for Python bytecode cache..."
CACHE_FILES=$(find ~/klipper/klippy/extras -name "*.pyc" -o -name "__pycache__" 2>/dev/null)
if [ -z "$CACHE_FILES" ]; then
    echo "   ✓ No cache files found"
else
    echo "   ⚠ Cache files found:"
    echo "$CACHE_FILES"
fi
echo ""

# Check Klipper logs for errors
echo "3. Checking Klipper logs for brick_layers errors..."
if [ -f /tmp/klippy.log ]; then
    echo "   Last 20 lines mentioning brick_layers:"
    grep -i "brick" /tmp/klippy.log | tail -20
    echo ""
    echo "   Last 10 config errors:"
    grep -i "option.*not valid" /tmp/klippy.log | tail -10
else
    echo "   ✗ Klippy log not found at /tmp/klippy.log"
fi
echo ""

# Check the printer.cfg for brick_layers section
echo "4. Checking printer.cfg for brick_layers configuration..."
if [ -f ~/printer_data/config/printer.cfg ]; then
    echo "   Found printer.cfg, brick_layers section:"
    sed -n '/\[brick_layers\]/,/^\[/p' ~/printer_data/config/printer.cfg | head -20
elif [ -f ~/klipper_config/printer.cfg ]; then
    echo "   Found printer.cfg, brick_layers section:"
    sed -n '/\[brick_layers\]/,/^\[/p' ~/klipper_config/printer.cfg | head -20
else
    echo "   ⚠ Could not locate printer.cfg"
fi
echo ""

# Check Klipper service status
echo "5. Checking Klipper service status..."
systemctl is-active --quiet klipper
if [ $? -eq 0 ]; then
    echo "   ✓ Klipper service is running"
else
    echo "   ✗ Klipper service is NOT running"
fi
echo ""

echo "======================================"
echo "Diagnostic complete!"
echo ""
echo "If you see cache files, run: ./clear_cache_and_reload.sh"
echo "To monitor live logs: tail -f /tmp/klippy.log"
echo ""
