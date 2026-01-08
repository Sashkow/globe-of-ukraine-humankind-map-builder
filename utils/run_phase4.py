#!/usr/bin/env python3
"""
Run Phase 4: Territory Assignment and Biome Mapping

This script demonstrates the complete Phase 4 workflow:
1. Load configuration and raion data
2. Create hex grid mapper
3. Assign territories
4. Assign biomes
5. Generate statistics and reports
6. Generate visualizations
"""

from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from config_loader import get_config
from geo_hex_mapper import GeoHexMapper
from hex_grid import HexGrid
from territory_assigner import TerritoryAssigner
from biome_mapper import BiomeMapper


def main():
    """Run Phase 4 territory assignment and biome mapping."""

    print("=" * 70)
    print("PHASE 4: TERRITORY ASSIGNMENT & BIOME MAPPING")
    print("=" * 70)

    # Load configuration
    print("\n[1/5] Loading configuration...")
    config = get_config()
    print(f"✓ Configuration loaded")
    print(f"  Grid: {config.grid_width}×{config.grid_height}")
    print(f"  Bounds: {config.map_bounds}")

    # Load raion data
    print("\n[2/5] Loading raion data...")
    data_dir = Path(__file__).parent / "data"
    raion_path = data_dir / "ukraine_raions.geojson"

    if not raion_path.exists():
        print(f"✗ Error: Raion data not found at {raion_path}")
        return

    raion_gdf = gpd.read_file(raion_path)
    print(f"✓ Loaded {len(raion_gdf)} raions")

    # Find oblast and name fields
    oblast_field = None
    for field in ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']:
        if field in raion_gdf.columns:
            oblast_field = field
            break

    name_field = None
    for field in ['name', 'NAME', 'ADM2_EN', 'ADM2_UA', 'NAME_2', 'admin2Name', 'adm2_name']:
        if field in raion_gdf.columns:
            name_field = field
            break

    if not oblast_field or not name_field:
        print(f"✗ Error: Could not find oblast or name fields")
        print(f"  Available columns: {list(raion_gdf.columns)}")
        return

    print(f"  Using oblast field: {oblast_field}")
    print(f"  Using name field: {name_field}")

    # Create hex mapper
    print("\n[3/5] Creating hex grid mapper...")
    mapper = GeoHexMapper(
        width=config.grid_width,
        height=config.grid_height,
        **config.map_bounds
    )
    print(f"✓ Hex grid mapper created")
    print(f"  Hex size: {mapper.hex_size_km:.2f} km")
    print(f"  Total hexes: {mapper.width * mapper.height}")

    # Assign territories
    print("\n[4/5] Assigning hexes to raions...")
    assigner = TerritoryAssigner(mapper, raion_gdf)
    hex_to_raion = assigner.assign_all_hexes()

    # Print statistics
    assigner.print_statistics()

    # Check for raions without hexes
    raion_counts = assigner.get_raion_hex_counts()
    raions_without_hexes = []
    for idx in raion_gdf.index:
        if idx not in raion_counts:
            raion_name = raion_gdf.loc[idx, name_field]
            raions_without_hexes.append(raion_name)

    if raions_without_hexes:
        print(f"\n⚠ Warning: {len(raions_without_hexes)} raions have no hexes:")
        for raion in raions_without_hexes[:10]:  # Show first 10
            print(f"    - {raion}")
        if len(raions_without_hexes) > 10:
            print(f"    ... and {len(raions_without_hexes) - 10} more")

    # Assign biomes
    print("\n[5/5] Assigning biomes to raions...")
    biome_mapper = BiomeMapper(raion_gdf, oblast_field)
    raion_biomes = biome_mapper.assign_biomes()

    # Generate detailed report
    print("\n" + "=" * 70)
    print("RAION SIZES BY OBLAST")
    print("=" * 70)

    oblast_data = assigner.get_raion_sizes_by_oblast(oblast_field, name_field)

    # Sort oblasts by total hex count
    oblast_totals = {
        oblast: sum(count for _, count in raions)
        for oblast, raions in oblast_data.items()
    }

    for oblast, total_hexes in sorted(oblast_totals.items(), key=lambda x: x[1], reverse=True):
        raions = oblast_data[oblast]
        raion_count = len(raions)

        print(f"\n{oblast} ({raion_count} raions, {total_hexes} hexes total):")
        for raion_name, hex_count in raions[:5]:  # Show top 5 raions
            print(f"  {raion_name:35} {hex_count:>4} hexes")
        if len(raions) > 5:
            print(f"  ... and {len(raions) - 5} more raions")

    # Create output directory
    output_dir = Path(__file__).parent / "output" / "phase4"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate visualizations
    print("\n" + "=" * 70)
    print("GENERATING VISUALIZATIONS")
    print("=" * 70)

    # 1. Territory assignment map (raion colors)
    print("\n[6/8] Generating territory assignment map...")
    generate_territory_map(
        mapper, hex_to_raion, raion_gdf, name_field,
        output_dir / "territory_assignment.png"
    )

    # 2. Biome map
    print("\n[7/8] Generating biome map...")
    generate_biome_map(
        mapper, hex_to_raion, raion_biomes,
        output_dir / "biome_map.png"
    )

    # 3. Statistics text file
    print("\n[8/8] Generating statistics report...")
    generate_statistics_report(
        assigner, biome_mapper, raion_gdf, oblast_field, name_field,
        output_dir / "statistics.txt"
    )

    print("\n" + "=" * 70)
    print("PHASE 4 COMPLETE")
    print("=" * 70)
    print(f"\n✓ {len(hex_to_raion)} hexes assigned to {len(raion_counts)} raions")
    print(f"✓ {len(raion_biomes)} raions assigned biomes")
    print(f"\nOutputs saved to: {output_dir}")
    print(f"  - territory_assignment.png")
    print(f"  - biome_map.png")
    print(f"  - statistics.txt")
    print(f"\nReady for Phase 5: Map Generation")


def generate_territory_map(mapper, hex_to_raion, raion_gdf, name_field, output_path):
    """Generate territory assignment visualization."""
    # Build adjacency graph for raions
    raion_neighbors = {idx: set() for idx in raion_gdf.index}

    # Hex neighbor offsets for flat-top odd-q
    even_neighbors = [(1, 0), (-1, 0), (0, -1), (0, 1), (1, -1), (-1, -1)]
    odd_neighbors = [(1, 0), (-1, 0), (0, -1), (0, 1), (1, 1), (-1, 1)]

    for (col, row), raion_idx in hex_to_raion.items():
        neighbors_offsets = even_neighbors if col % 2 == 0 else odd_neighbors
        for dc, dr in neighbors_offsets:
            neighbor = (col + dc, row + dr)
            if neighbor in hex_to_raion:
                neighbor_idx = hex_to_raion[neighbor]
                if neighbor_idx != raion_idx:
                    raion_neighbors[raion_idx].add(neighbor_idx)

    # Greedy graph coloring
    raion_colors = {}
    color_palette = plt.cm.tab20.colors

    sorted_raions = sorted(
        raion_gdf.index,
        key=lambda idx: len(raion_neighbors.get(idx, set())),
        reverse=True
    )

    for raion_idx in sorted_raions:
        neighbor_colors = {
            raion_colors[n]
            for n in raion_neighbors.get(raion_idx, set())
            if n in raion_colors
        }
        for color_idx in range(len(color_palette)):
            if color_idx not in neighbor_colors:
                raion_colors[raion_idx] = color_idx
                break

    # Create visualization
    fig, ax = plt.subplots(figsize=(24, 14))

    hex_size_pixels = 10
    grid = HexGrid(width=150, height=88, hex_size=hex_size_pixels)
    pixel_bounds = grid.pixel_bounds()

    # Draw all hexes
    for row in range(88):
        for col in range(150):
            corners_pixel = grid.hex_corners(col, row)

            if (col, row) in hex_to_raion:
                raion_idx = hex_to_raion[(col, row)]
                color_idx = raion_colors.get(raion_idx, 0)
                color = color_palette[color_idx % len(color_palette)]
                alpha = 0.8
                edgecolor = 'white'
                linewidth = 0.3
            else:
                color = (0.85, 0.85, 0.85)
                alpha = 0.4
                edgecolor = (0.9, 0.9, 0.9)
                linewidth = 0.2

            hex_patch = mpatches.Polygon(
                corners_pixel,
                facecolor=color,
                edgecolor=edgecolor,
                linewidth=linewidth,
                alpha=alpha
            )
            ax.add_patch(hex_patch)

    ax.set_xlim(pixel_bounds[0] - 10, pixel_bounds[2] + 10)
    ax.set_ylim(pixel_bounds[1] - 10, pixel_bounds[3] + 10)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.axis('off')

    stats = f"{len(hex_to_raion)} hexes assigned to {len(set(hex_to_raion.values()))} raions"
    ax.set_title(
        f"Phase 4: Territory Assignment\n{stats}",
        fontsize=16, pad=20
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"✓ Saved: {output_path}")


def generate_biome_map(mapper, hex_to_raion, raion_biomes, output_path):
    """Generate biome visualization."""
    # Biome colors (matching Humankind's color scheme)
    biome_colors = {
        0: (0.7, 0.85, 0.95),   # Arctic - light blue
        1: (0.76, 0.60, 0.42),  # Badlands - tan/brown
        2: (0.93, 0.87, 0.68),  # Desert - sandy yellow
        3: (0.68, 0.85, 0.45),  # Grassland - light green
        4: (0.75, 0.78, 0.45),  # Mediterranean - olive
        5: (0.85, 0.78, 0.55),  # Savanna - tan/yellow
        6: (0.25, 0.50, 0.35),  # Taiga - dark green
        7: (0.45, 0.70, 0.40),  # Temperate - green
        8: (0.30, 0.75, 0.45),  # Tropical - bright green
        9: (0.65, 0.70, 0.75),  # Tundra - gray-blue
    }

    biome_names = {
        0: "Arctic", 1: "Badlands", 2: "Desert", 3: "Grassland",
        4: "Mediterranean", 5: "Savanna", 6: "Taiga", 7: "Temperate",
        8: "Tropical", 9: "Tundra"
    }

    fig, ax = plt.subplots(figsize=(24, 14))

    hex_size_pixels = 10
    grid = HexGrid(width=150, height=88, hex_size=hex_size_pixels)
    pixel_bounds = grid.pixel_bounds()

    # Count biomes for legend
    biome_hex_counts = {}

    # Draw all hexes
    for row in range(88):
        for col in range(150):
            corners_pixel = grid.hex_corners(col, row)

            if (col, row) in hex_to_raion:
                raion_idx = hex_to_raion[(col, row)]
                biome = raion_biomes.get(raion_idx, 3)  # Default grassland
                color = biome_colors.get(biome, (0.5, 0.5, 0.5))
                alpha = 0.9
                edgecolor = 'white'
                linewidth = 0.2

                biome_hex_counts[biome] = biome_hex_counts.get(biome, 0) + 1
            else:
                color = (0.6, 0.75, 0.85)  # Ocean blue
                alpha = 0.5
                edgecolor = (0.7, 0.8, 0.9)
                linewidth = 0.1

            hex_patch = mpatches.Polygon(
                corners_pixel,
                facecolor=color,
                edgecolor=edgecolor,
                linewidth=linewidth,
                alpha=alpha
            )
            ax.add_patch(hex_patch)

    # Add legend
    legend_patches = []
    for biome_idx in sorted(biome_hex_counts.keys()):
        count = biome_hex_counts[biome_idx]
        name = biome_names.get(biome_idx, f"Biome {biome_idx}")
        color = biome_colors.get(biome_idx, (0.5, 0.5, 0.5))
        patch = mpatches.Patch(color=color, label=f"{name} ({count} hexes)")
        legend_patches.append(patch)

    ax.legend(handles=legend_patches, loc='upper left', fontsize=10)

    ax.set_xlim(pixel_bounds[0] - 10, pixel_bounds[2] + 10)
    ax.set_ylim(pixel_bounds[1] - 10, pixel_bounds[3] + 10)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.axis('off')

    ax.set_title(
        f"Phase 4: Biome Assignment\n{len(biome_hex_counts)} biome types across {sum(biome_hex_counts.values())} hexes",
        fontsize=16, pad=20
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"✓ Saved: {output_path}")


def generate_statistics_report(assigner, biome_mapper, raion_gdf, oblast_field, name_field, output_path):
    """Generate detailed statistics report."""
    stats = assigner.get_statistics()
    raion_counts = assigner.get_raion_hex_counts()

    lines = []
    lines.append("=" * 70)
    lines.append("PHASE 4: TERRITORY ASSIGNMENT & BIOME MAPPING - STATISTICS REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Grid coverage
    lines.append("GRID COVERAGE")
    lines.append("-" * 40)
    lines.append(f"Total hexes:         {stats['total_hexes']:>6}")
    lines.append(f"Ukraine hexes:       {stats['ukraine_hexes']:>6} ({stats['coverage_percent']:.1f}%)")
    lines.append(f"Ocean/buffer hexes:  {stats['ocean_hexes']:>6} ({100-stats['coverage_percent']:.1f}%)")
    lines.append("")

    # Raion coverage
    lines.append("RAION COVERAGE")
    lines.append("-" * 40)
    lines.append(f"Total raions:           {stats['total_raions']:>3}")
    lines.append(f"Raions with hexes:      {stats['raions_with_hexes']:>3}")
    lines.append(f"Raions without hexes:   {stats['raions_without_hexes']:>3}")
    lines.append("")

    # Hexes per raion
    if "min_hexes_per_raion" in stats:
        lines.append("HEXES PER RAION")
        lines.append("-" * 40)
        lines.append(f"Minimum:   {stats['min_hexes_per_raion']:>3} hexes")
        lines.append(f"Maximum:   {stats['max_hexes_per_raion']:>3} hexes")
        lines.append(f"Average:   {stats['avg_hexes_per_raion']:>6.1f} hexes")
        lines.append(f"Median:    {stats['median_hexes_per_raion']:>3} hexes")
        lines.append("")

    # Biome distribution
    lines.append("BIOME DISTRIBUTION")
    lines.append("-" * 40)
    biome_names = {
        0: "Arctic", 1: "Badlands", 2: "Desert", 3: "Grassland",
        4: "Mediterranean", 5: "Savanna", 6: "Taiga", 7: "Temperate",
        8: "Tropical", 9: "Tundra"
    }
    biome_counts = {}
    for biome in biome_mapper.raion_biomes.values():
        biome_counts[biome] = biome_counts.get(biome, 0) + 1

    for biome_idx, count in sorted(biome_counts.items()):
        name = biome_names.get(biome_idx, f"Biome {biome_idx}")
        percent = 100 * count / len(biome_mapper.raion_biomes)
        lines.append(f"{name:15} {count:>3} raions ({percent:>5.1f}%)")
    lines.append("")

    # Raions by oblast
    lines.append("=" * 70)
    lines.append("RAION SIZES BY OBLAST")
    lines.append("=" * 70)

    oblast_data = assigner.get_raion_sizes_by_oblast(oblast_field, name_field)
    oblast_totals = {
        oblast: sum(count for _, count in raions)
        for oblast, raions in oblast_data.items()
    }

    for oblast, total_hexes in sorted(oblast_totals.items(), key=lambda x: x[1], reverse=True):
        raions = oblast_data[oblast]
        lines.append("")
        lines.append(f"{oblast} ({len(raions)} raions, {total_hexes} hexes)")
        lines.append("-" * 50)
        for raion_name, hex_count in raions:
            lines.append(f"  {raion_name:40} {hex_count:>4} hexes")

    # Raions without hexes
    raions_without = []
    for idx in raion_gdf.index:
        if idx not in raion_counts:
            raions_without.append(raion_gdf.loc[idx, name_field])

    if raions_without:
        lines.append("")
        lines.append("=" * 70)
        lines.append("RAIONS WITHOUT HEXES")
        lines.append("=" * 70)
        for raion in raions_without:
            lines.append(f"  - {raion}")

    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
