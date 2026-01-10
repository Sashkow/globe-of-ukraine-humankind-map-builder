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
from collections import defaultdict
from PIL import Image
import numpy as np
from scipy import ndimage


def get_hex_neighbors(col: int, row: int, width: int, height: int) -> list[tuple[int, int]]:
    """Get valid hex neighbors for a given position using offset coordinates.

    Even rows: neighbors at (col-1,row), (col+1,row), (col-1,row-1), (col,row-1), (col-1,row+1), (col,row+1)
    Odd rows: neighbors at (col-1,row), (col+1,row), (col,row-1), (col+1,row-1), (col,row+1), (col+1,row+1)
    """
    neighbors = []
    if row % 2 == 0:  # Even row
        offsets = [(-1, 0), (1, 0), (-1, -1), (0, -1), (-1, 1), (0, 1)]
    else:  # Odd row
        offsets = [(-1, 0), (1, 0), (0, -1), (1, -1), (0, 1), (1, 1)]

    for dc, dr in offsets:
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and 0 <= nr < height:
            neighbors.append((nc, nr))
    return neighbors


def check_territory_contiguity(zones_array: np.ndarray) -> dict:
    """Check if all territories have contiguous tiles.

    Returns dict with:
      - 'non_contiguous_territories': list of territory IDs with multiple disconnected regions
      - 'edge_territory_issues': list of territory 0 tiles that don't touch edge or other t0 tiles
    """
    height, width = zones_array.shape[:2]

    # R channel contains territory IDs (per HUMANKIND_MAP_FORMAT.md)
    if len(zones_array.shape) == 3:
        territory_map = zones_array[:, :, 0]  # R channel
    else:
        territory_map = zones_array

    result = {
        'non_contiguous_territories': [],
        'edge_territory_issues': [],
        'territory_region_counts': {},
    }

    # Get unique territory IDs
    unique_territories = np.unique(territory_map)

    for territory_id in unique_territories:
        # Create binary mask for this territory
        mask = (territory_map == territory_id).astype(np.int32)

        # Use connected components to find separate regions
        # For hex grids, we need a custom structure, but as approximation use 8-connectivity
        structure = np.array([[1, 1, 1],
                             [1, 1, 1],
                             [1, 1, 1]])
        labeled, num_regions = ndimage.label(mask, structure=structure)

        result['territory_region_counts'][int(territory_id)] = num_regions

        if num_regions > 1:
            result['non_contiguous_territories'].append({
                'territory_id': int(territory_id),
                'region_count': num_regions,
            })

    # Special check for territory 0 (edge of world)
    # Each t0 tile must either touch the map edge or connect to other t0 tiles
    t0_mask = territory_map == 0
    t0_positions = np.argwhere(t0_mask)

    for pos in t0_positions:
        row, col = pos
        touches_edge = (row == 0 or row == height - 1 or col == 0 or col == width - 1)

        if not touches_edge:
            # Check if connected to other t0 tiles using hex neighbors
            neighbors = get_hex_neighbors(col, row, width, height)
            connected_to_t0 = any(territory_map[nr, nc] == 0 for nc, nr in neighbors)

            if not connected_to_t0:
                result['edge_territory_issues'].append({
                    'position': (int(col), int(row)),
                    'issue': 'Territory 0 tile not touching edge and not connected to other T0 tiles'
                })

    return result


def extract_zones_texture(save_content: str) -> np.ndarray | None:
    """Extract ZonesTexture array from save content."""
    pattern = r'<ZonesTexture\.Bytes Length="\d+">([^<]+)</ZonesTexture\.Bytes>'
    match = re.search(pattern, save_content)
    if match:
        try:
            png_data = base64.b64decode(match.group(1))
            img = Image.open(io.BytesIO(png_data))
            return np.array(img)
        except Exception:
            return None
    return None


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

    # Check territory contiguity
    zones_array = extract_zones_texture(save)
    if zones_array is not None:
        contiguity = check_territory_contiguity(zones_array)
        info['territory_contiguity'] = contiguity

        # Add errors for non-contiguous territories
        for nc_territory in contiguity['non_contiguous_territories']:
            info['errors'].append(
                f"Territory {nc_territory['territory_id']} is not contiguous "
                f"({nc_territory['region_count']} disconnected regions)"
            )

        # Add errors for edge territory issues (specific to territory 0)
        edge_issues = contiguity['edge_territory_issues']
        if edge_issues:
            info['errors'].append(
                f"Edge of world territory (T0) has {len(edge_issues)} tiles not properly connected"
            )

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

    # Display territory contiguity info
    if 'territory_contiguity' in info:
        contiguity = info['territory_contiguity']
        print("\nTERRITORY CONTIGUITY:")
        nc_territories = contiguity.get('non_contiguous_territories', [])
        if nc_territories:
            print(f"  Non-contiguous territories: {len(nc_territories)}")
            for nc in nc_territories:
                print(f"    - Territory {nc['territory_id']}: {nc['region_count']} disconnected regions")
        else:
            print("  All territories are contiguous")

        edge_issues = contiguity.get('edge_territory_issues', [])
        if edge_issues:
            print(f"  Edge territory (T0) issues: {len(edge_issues)}")
            # Show first few issues
            for issue in edge_issues[:5]:
                print(f"    - Position {issue['position']}: {issue['issue']}")
            if len(edge_issues) > 5:
                print(f"    ... and {len(edge_issues) - 5} more")

        # Show territory 0 region info
        t0_regions = contiguity.get('territory_region_counts', {}).get(0, 0)
        if t0_regions > 1:
            print(f"  WARNING: Territory 0 (edge of world) has {t0_regions} disconnected regions!")
        else:
            t0_count = sum(1 for tid, cnt in contiguity.get('territory_region_counts', {}).items()
                          if tid == 0)
            print(f"  Territory 0 tiles: forms {t0_regions} region(s)")

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
