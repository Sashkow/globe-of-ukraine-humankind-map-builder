#!/usr/bin/env python3
"""
Map Validator - Extract and display map info and potential issues.

Usage:
    uv run python utils/map_validator.py output/incremental/step10_spawn_points.hmap
"""

import zipfile
import base64
import io
import re
import sys
from pathlib import Path
from PIL import Image
import numpy as np


def extract_map_info(hmap_path: Path) -> dict:
    """Extract map information from an hmap file."""
    info = {
        'path': str(hmap_path),
        'errors': [],
        'warnings': [],
    }

    with zipfile.ZipFile(hmap_path, 'r') as zf:
        # Read descriptor
        descriptor = zf.read('Descriptor.hmd').decode('utf-8-sig')
        save = zf.read('Save.hms').decode('utf-8-sig')

    # Extract basic info
    width_match = re.search(r'<Width>(\d+)</Width>', save)
    height_match = re.search(r'<Height>(\d+)</Height>', save)
    empires_match = re.search(r'<EmpiresCount>(\d+)</EmpiresCount>', descriptor)
    failure_match = re.search(r'<FailureFlags>(\d+)</FailureFlags>', save)

    info['width'] = int(width_match.group(1)) if width_match else 0
    info['height'] = int(height_match.group(1)) if height_match else 0
    info['empires_count'] = int(empires_match.group(1)) if empires_match else 0
    info['failure_flags'] = int(failure_match.group(1)) if failure_match else 0

    # Count spawn points
    spawn_match = re.search(r'<SpawnPoints Length="(\d+)">', save)
    info['spawn_count'] = int(spawn_match.group(1)) if spawn_match else 0

    # Count territories
    territory_match = re.search(r'<Territories Length="(\d+)">', save)
    info['territory_count'] = int(territory_match.group(1)) if territory_match else 0

    # Check natural wonders
    wonder_names_match = re.search(r'<NaturalWonderNames Length="(\d+)">', save)
    info['wonder_names_count'] = int(wonder_names_match.group(1)) if wonder_names_match else 0

    # Extract and analyze textures
    info['textures'] = {}

    for texture_name in ['ElevationTexture', 'ZonesTexture', 'NaturalWonderTexture', 'RiverTexture', 'POITexture']:
        pattern = rf'<{texture_name}\.Bytes Length="(\d+)">([^<]+)</{texture_name}\.Bytes>'
        match = re.search(pattern, save)
        if match:
            length = int(match.group(1))
            b64_data = match.group(2)
            try:
                png_data = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(png_data))
                arr = np.array(img)
                info['textures'][texture_name] = {
                    'length': length,
                    'shape': arr.shape,
                    'non_zero': np.count_nonzero(arr),
                }
            except Exception as e:
                info['textures'][texture_name] = {'error': str(e)}

    # Validation checks
    if info['spawn_count'] != info['empires_count']:
        info['warnings'].append(f"Spawn count ({info['spawn_count']}) != EmpiresCount ({info['empires_count']})")

    if info['spawn_count'] < 2:
        info['errors'].append(f"Too few spawn points: {info['spawn_count']} (minimum 2)")

    if info['territory_count'] < 2:
        info['errors'].append(f"Too few territories: {info['territory_count']} (need at least ocean + 1 land)")

    # Check if natural wonders texture has any wonders placed
    if 'NaturalWonderTexture' in info['textures']:
        nw_info = info['textures']['NaturalWonderTexture']
        if 'shape' in nw_info:
            # Count non-zero R channel values (wonder indices)
            pattern = rf'<NaturalWonderTexture\.Bytes Length="\d+">([^<]+)</NaturalWonderTexture\.Bytes>'
            match = re.search(pattern, save)
            if match:
                png_data = base64.b64decode(match.group(1))
                img = Image.open(io.BytesIO(png_data))
                arr = np.array(img)
                wonder_pixels = np.count_nonzero(arr[:, :, 0])  # R channel
                info['wonder_pixels'] = wonder_pixels
                if wonder_pixels == 0 and info['wonder_names_count'] > 0:
                    info['warnings'].append(f"No wonder pixels placed but {info['wonder_names_count']} wonder names defined")

    # Decode failure flags (if non-zero)
    if info['failure_flags'] != 0:
        flags = info['failure_flags']
        flag_meanings = []
        # These are guesses based on common validation issues
        if flags & 1: flag_meanings.append("Invalid spawn location")
        if flags & 2: flag_meanings.append("Territory connectivity issue")
        if flags & 4: flag_meanings.append("Missing resources")
        if flags & 8: flag_meanings.append("Invalid terrain")
        if flags & 16: flag_meanings.append("Landmark error")
        if flags & 32: flag_meanings.append("Natural wonder error")
        info['failure_meanings'] = flag_meanings if flag_meanings else [f"Unknown flags: {flags}"]

    return info


def print_map_info(info: dict):
    """Print map information in a readable format."""
    print("=" * 60)
    print(f"MAP VALIDATION REPORT")
    print("=" * 60)
    print(f"File: {info['path']}")
    print()
    print("BASIC INFO:")
    print(f"  Dimensions: {info['width']} x {info['height']}")
    print(f"  Empires Count: {info['empires_count']}")
    print(f"  Spawn Points: {info['spawn_count']}")
    print(f"  Territories: {info['territory_count']}")
    print(f"  Wonder Names: {info['wonder_names_count']}")
    if 'wonder_pixels' in info:
        print(f"  Wonder Pixels: {info['wonder_pixels']}")
    print(f"  Failure Flags: {info['failure_flags']}")

    if info.get('failure_meanings'):
        print("\nFAILURE FLAGS MEANING:")
        for meaning in info['failure_meanings']:
            print(f"  - {meaning}")

    print("\nTEXTURES:")
    for name, tex_info in info.get('textures', {}).items():
        if 'error' in tex_info:
            print(f"  {name}: ERROR - {tex_info['error']}")
        else:
            print(f"  {name}: {tex_info['shape']}, non-zero: {tex_info['non_zero']}")

    if info['errors']:
        print("\nERRORS:")
        for error in info['errors']:
            print(f"  ❌ {error}")

    if info['warnings']:
        print("\nWARNINGS:")
        for warning in info['warnings']:
            print(f"  ⚠️  {warning}")

    if not info['errors'] and not info['warnings']:
        print("\n✅ No obvious issues detected")

    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        # Default to latest step10 output
        hmap_path = Path(__file__).parent.parent / "output" / "incremental" / "step10_spawn_points.hmap"
    else:
        hmap_path = Path(sys.argv[1])

    if not hmap_path.exists():
        print(f"Error: File not found: {hmap_path}")
        sys.exit(1)

    info = extract_map_info(hmap_path)
    print_map_info(info)


if __name__ == "__main__":
    main()
