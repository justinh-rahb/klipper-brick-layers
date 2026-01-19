# Troubleshooting

## Module Not Loading

**Symptom:** `Unknown command: "BRICK_LAYERS_STATUS"`

**Solutions:**
1. Verify installation: `ls -la ~/klipper/klippy/extras/brick_layers.py`
2. Check Klipper logs: `tail -f ~/printer_data/logs/klippy.log`
3. Verify config section exists: `[brick_layers]` in printer.cfg
4. Restart Klipper: `RESTART`

## No Transformation Happening

**Symptom:** Prints look normal, no brick pattern visible

**Solutions:**
1. Check if enabled: `BRICK_LAYERS_STATUS`
2. Enable manually: `BRICK_LAYERS_ENABLE`
3. Verify G-code has TYPE comments: `./scripts/validate_gcode.py file.gcode`
4. Check start_layer setting - you may not be printing enough layers

## Artifacts on External Surfaces

**Symptom:** External walls show defects or irregularities

**Solutions:**
1. This should NOT happen - external perimeters should be untransformed
2. Check slicer TYPE comments are correct
3. Report as bug with sample G-code

## Performance Issues / Stuttering

**Symptom:** Printer pauses or stutters during prints

**Solutions:**
1. Ensure the print file is located on the virtual SD card.
2. Reduce system load (close other services)
3. Upgrade to faster Pi (Pi 4 recommended)

## Getting Help

1. Check logs: `~/printer_data/logs/klippy.log`
2. Test with sample G-code: Use files in `tests/sample_gcode/`
3. Open GitHub issue with:
   - Klipper version
   - Printer config
   - Sample G-code
   - Logs showing the error

## Known Issues

- [ ] Binary G-code not supported (PrusaSlicer binary mode)
- [ ] Cura requires plugin for TYPE comments
- [ ] Performance on Pi 3 not tested (Pi 4 recommended)
