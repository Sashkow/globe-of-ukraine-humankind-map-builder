"""
Parse and render all Humankind maps in humankind_maps directory.

Outputs:
- parsed_maps/ - Compact .npz files
- rendered_maps/ - PNG renderings (simple, hex, and biome views)
"""

from pathlib import Path
import sys

from humankind_map_parser import load_map, save_compact_map
from humankind_map_renderer import render_map_simple, render_map_hex


def main():
    # Setup directories
    maps_dir = Path("humankind_maps")
    parsed_dir = Path("parsed_maps")
    rendered_dir = Path("rendered_maps")

    parsed_dir.mkdir(exist_ok=True)
    rendered_dir.mkdir(exist_ok=True)

    # Find all .hmap and .hms files
    hmap_files = list(maps_dir.rglob("*.hmap"))
    hms_files = list(maps_dir.rglob("*.hms"))

    all_maps = hmap_files + hms_files

    print(f"Found {len(all_maps)} map files:")
    for map_file in all_maps:
        print(f"  - {map_file.relative_to(maps_dir)}")

    print("\n" + "="*60)

    # Process each map
    for i, map_path in enumerate(all_maps, 1):
        # Generate a clean name for outputs
        relative_path = map_path.relative_to(maps_dir)
        map_name = relative_path.parent.name if relative_path.parent.name else relative_path.stem
        map_name = map_name.replace(" ", "_").replace(".", "_")

        print(f"\n[{i}/{len(all_maps)}] Processing: {relative_path}")
        print(f"  Map name: {map_name}")

        try:
            # Parse map
            print(f"  Parsing...")
            map_data = load_map(map_path)

            print(f"  Size: {map_data.width}x{map_data.height} ({map_data.width * map_data.height} hexes)")
            print(f"  Territories: {map_data.territory_count} ({map_data.land_territory_count} land, {map_data.ocean_territory_count} ocean)")

            # Save compact format
            compact_path = parsed_dir / f"{map_name}.npz"
            save_compact_map(map_data, compact_path)
            print(f"  ✓ Saved parsed: {compact_path}")

            # Render simple view (colored by biome)
            simple_path = rendered_dir / f"{map_name}_biome.png"
            render_map_simple(map_data, simple_path, color_by="biome", scale=4)
            print(f"  ✓ Rendered biome view: {simple_path}")

            # Render hex view (colored by territory)
            hex_path = rendered_dir / f"{map_name}_territory_hex.png"
            hex_size = max(4, min(12, 800 // max(map_data.width, map_data.height)))
            render_map_hex(map_data, hex_path, color_by="territory", hex_size=hex_size, show_borders=True)
            print(f"  ✓ Rendered hex view: {hex_path}")

            # Render simple territory view
            territory_path = rendered_dir / f"{map_name}_territory.png"
            render_map_simple(map_data, territory_path, color_by="territory", scale=4)
            print(f"  ✓ Rendered territory view: {territory_path}")

            # Print hex count statistics
            hex_counts = map_data.get_hex_counts()
            land_hex_counts = {tid: count for tid, count in hex_counts.items()
                             if not map_data.territories[tid].is_ocean}

            if land_hex_counts:
                avg_land_hexes = sum(land_hex_counts.values()) / len(land_hex_counts)
                min_land_hexes = min(land_hex_counts.values())
                max_land_hexes = max(land_hex_counts.values())
                print(f"  Land territory hexes: avg={avg_land_hexes:.1f}, min={min_land_hexes}, max={max_land_hexes}")

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            continue

    print("\n" + "="*60)
    print(f"\nDone! Processed {len(all_maps)} maps")
    print(f"  Parsed maps: {parsed_dir}/")
    print(f"  Rendered maps: {rendered_dir}/")


if __name__ == "__main__":
    main()
