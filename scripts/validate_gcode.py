#!/usr/bin/env python3
"""
Validate G-code file for BrickLayers compatibility

Checks if G-code contains required TYPE comments for perimeter detection.
"""

import sys
import os

def validate_gcode(filepath):
    """Validate G-code file has required comments"""
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False
    
    print(f"🔍 Analyzing: {filepath}")
    print()
    
    has_layer_change = False
    has_type_comments = False
    type_comments = set()
    layer_count = 0
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            if ';LAYER_CHANGE' in line:
                has_layer_change = True
                layer_count += 1
            
            if ';TYPE:' in line:
                has_type_comments = True
                comment_type = line.split(':', 1)[1].strip()
                type_comments.add(comment_type)
    
    # Report findings
    print("📊 Validation Results:")
    print(f"  Layer changes found: {'✅ Yes' if has_layer_change else '❌ No'}")
    print(f"  Layer count: {layer_count}")
    print(f"  TYPE comments found: {'✅ Yes' if has_type_comments else '❌ No'}")
    
    if type_comments:
        print(f"\n  Detected feature types:")
        for t in sorted(type_comments):
            print(f"    - {t}")
    
    print()
    
    # Determine compatibility
    if has_layer_change and has_type_comments:
        print("✅ G-code is compatible with BrickLayers!")
        has_inner_wall = any('inner' in t.lower() for t in type_comments)
        if has_inner_wall:
            print("✅ Inner wall perimeters detected")
        else:
            print("⚠️  No inner walls detected - check wall count in slicer")
        return True
    else:
        print("❌ G-code is NOT compatible with BrickLayers")
        if not has_layer_change:
            print("  Missing: ;LAYER_CHANGE comments")
        if not has_type_comments:
            print("  Missing: ;TYPE: comments")
        print("\n  💡 Try slicing with PrusaSlicer or OrcaSlicer")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: validate_gcode.py <gcode_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    result = validate_gcode(filepath)
    sys.exit(0 if result else 1)
