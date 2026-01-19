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
    line_count = 0
    transform_moves = 0
    current_type = None
    feature_lines = {} # type -> first line found
    
    with open(filepath, 'r') as f:
        for line in f:
            line_count += 1
            line = line.strip()
            
            if ';LAYER_CHANGE' in line:
                has_layer_change = True
                layer_count += 1
            
            if ';TYPE:' in line:
                has_type_comments = True
                comment_type = line.split(':', 1)[1].strip()
                type_comments.add(comment_type)
                current_type = comment_type
                if comment_type not in feature_lines:
                    feature_lines[comment_type] = line_count
            
            if line.startswith('G1') and current_type and 'inner' in current_type.lower():
                transform_moves += 1
    
    # Report findings
    print("📊 Validation Results:")
    print(f"  Total lines analyzed: {line_count}")
    print(f"  Layer changes found: {'✅ Yes' if has_layer_change else '❌ No'}")
    print(f"  Layer count: {layer_count}")
    print(f"  TYPE comments found: {'✅ Yes' if has_type_comments else '❌ No'}")
    
    if type_comments:
        print(f"\n  Detected feature types:")
        for t in sorted(type_comments):
            line_info = f"(first seen at L{feature_lines[t]})"
            print(f"    - {t:<20} {line_info}")
    
    print(f"\n  Transform points estimate: {transform_moves}")
    print()
    
    # Determine compatibility
    if has_layer_change and has_type_comments:
        print("✅ G-code is compatible with BrickLayers!")
        if transform_moves > 0:
            print(f"✅ Found {transform_moves} potential transform points")
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
