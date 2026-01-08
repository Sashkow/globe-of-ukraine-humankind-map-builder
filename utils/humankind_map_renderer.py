"""
Renderer for Humankind maps.

Renders map data to images for visualization and validation.
"""

import colorsys
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw

from humankind_map_parser import HumankindMap, load_map


# Biome colors (index -> RGB)
BIOME_COLORS = {
    0: (200, 230, 255),   # Arctic - light blue/white
    1: (180, 120, 80),    # Badlands - brown
    2: (230, 210, 150),   # Desert - sandy yellow
    3: (140, 180, 90),    # Grassland - light green
    4: (180, 150, 80),    # Mediterranean - olive
    5: (200, 170, 100),   # Savanna - tan
    6: (60, 100, 60),     # Taiga - dark green
    7: (100, 160, 80),    # Temperate - medium green
    8: (30, 120, 50),     # Tropical - bright green
    9: (180, 200, 200),   # Tundra - gray
}

OCEAN_COLOR = (50, 80, 140)  # Deep blue


def generate_territory_colors(n_territories: int) -> dict[int, tuple[int, int, int]]:
    """Generate distinct colors for each territory."""
    colors = {}
    for i in range(n_territories):
        # Use golden ratio to spread colors evenly in hue space
        hue = (i * 0.618033988749895) % 1.0
        saturation = 0.6 + (i % 3) * 0.15  # Vary saturation slightly
        value = 0.7 + (i % 4) * 0.075  # Vary brightness slightly
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        colors[i] = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
    return colors


def render_map_simple(
    map_data: HumankindMap,
    output_path: Optional[Path] = None,
    color_by: str = "territory",
    scale: int = 4,
) -> Image.Image:
    """Render map as a simple pixel grid (no hex shapes).

    Args:
        map_data: Parsed map data
        output_path: Optional path to save image
        color_by: "territory" for unique territory colors, "biome" for biome colors
        scale: Pixels per hex (for visibility)

    Returns:
        PIL Image
    """
    height, width = map_data.zones_texture.shape

    # Generate colors
    if color_by == "territory":
        territory_colors = generate_territory_colors(map_data.territory_count)
    else:
        territory_colors = {}

    # Create image
    img = Image.new('RGB', (width * scale, height * scale))
    pixels = img.load()

    for y in range(height):
        for x in range(width):
            territory_idx = map_data.zones_texture[y, x]
            territory = map_data.territories[territory_idx]

            if territory.is_ocean:
                color = OCEAN_COLOR
            elif color_by == "biome":
                color = BIOME_COLORS.get(territory.biome, (128, 128, 128))
            else:
                color = territory_colors.get(territory_idx, (128, 128, 128))

            # Fill scaled pixel
            for sy in range(scale):
                for sx in range(scale):
                    pixels[x * scale + sx, y * scale + sy] = color

    if output_path:
        img.save(output_path)

    return img


def render_map_hex(
    map_data: HumankindMap,
    output_path: Optional[Path] = None,
    color_by: str = "territory",
    hex_size: int = 8,
    show_borders: bool = True,
) -> Image.Image:
    """Render map with hexagonal tiles.

    Args:
        map_data: Parsed map data
        output_path: Optional path to save image
        color_by: "territory" for unique territory colors, "biome" for biome colors
        hex_size: Radius of each hex in pixels
        show_borders: Draw territory borders

    Returns:
        PIL Image
    """
    height, width = map_data.zones_texture.shape

    # Hex geometry (pointy-top)
    hex_width = hex_size * np.sqrt(3)
    hex_height = hex_size * 2

    # Image size with hex spacing
    img_width = int(hex_width * width + hex_width / 2)
    img_height = int(hex_height * 0.75 * height + hex_height * 0.25)

    # Generate colors
    if color_by == "territory":
        territory_colors = generate_territory_colors(map_data.territory_count)
    else:
        territory_colors = {}

    # Create image
    img = Image.new('RGB', (img_width, img_height), OCEAN_COLOR)
    draw = ImageDraw.Draw(img)

    def hex_corners(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
        """Get corners of a pointy-top hexagon."""
        corners = []
        for i in range(6):
            angle = np.pi / 6 + i * np.pi / 3  # Start at 30 degrees
            corners.append((
                cx + size * np.cos(angle),
                cy + size * np.sin(angle)
            ))
        return corners

    def hex_center(col: int, row: int) -> tuple[float, float]:
        """Get center position of hex at (col, row)."""
        cx = hex_width * (col + 0.5)
        if col % 2 == 1:
            cy = hex_height * 0.75 * row + hex_height * 0.5 + hex_height * 0.25
        else:
            cy = hex_height * 0.75 * row + hex_height * 0.5
        return cx, cy

    # Draw hexes
    for row in range(height):
        for col in range(width):
            territory_idx = map_data.zones_texture[row, col]
            territory = map_data.territories[territory_idx]

            if territory.is_ocean:
                color = OCEAN_COLOR
            elif color_by == "biome":
                color = BIOME_COLORS.get(territory.biome, (128, 128, 128))
            else:
                color = territory_colors.get(territory_idx, (128, 128, 128))

            cx, cy = hex_center(col, row)
            corners = hex_corners(cx, cy, hex_size * 0.95)  # Slightly smaller to show gaps

            draw.polygon(corners, fill=color)

    # Draw territory borders if requested
    if show_borders:
        border_color = (40, 40, 40)
        for row in range(height):
            for col in range(width):
                territory_idx = map_data.zones_texture[row, col]

                # Check neighbors (6 directions for hex)
                # For pointy-top with odd-q offset:
                if col % 2 == 0:
                    neighbors = [
                        (col, row - 1),      # N
                        (col + 1, row - 1),  # NE
                        (col + 1, row),      # SE
                        (col, row + 1),      # S
                        (col - 1, row),      # SW
                        (col - 1, row - 1),  # NW
                    ]
                else:
                    neighbors = [
                        (col, row - 1),      # N
                        (col + 1, row),      # NE
                        (col + 1, row + 1),  # SE
                        (col, row + 1),      # S
                        (col - 1, row + 1),  # SW
                        (col - 1, row),      # NW
                    ]

                cx, cy = hex_center(col, row)
                corners = hex_corners(cx, cy, hex_size)

                for i, (nc, nr) in enumerate(neighbors):
                    if 0 <= nc < width and 0 <= nr < height:
                        neighbor_idx = map_data.zones_texture[nr, nc]
                        if neighbor_idx != territory_idx:
                            # Draw border edge
                            p1 = corners[i]
                            p2 = corners[(i + 1) % 6]
                            draw.line([p1, p2], fill=border_color, width=1)

    if output_path:
        img.save(output_path)

    return img


def render_map_with_legend(
    map_data: HumankindMap,
    output_path: Path,
    color_by: str = "territory",
    hex_size: int = 8,
) -> None:
    """Render map with a legend showing territory/biome information.

    Creates two files: the map and a separate legend image.
    """
    # Render main map
    map_img = render_map_hex(map_data, color_by=color_by, hex_size=hex_size)

    # Create legend
    if color_by == "biome":
        items = [(name, BIOME_COLORS.get(i, (128, 128, 128)))
                 for i, name in enumerate(map_data.biome_names)]
    else:
        territory_colors = generate_territory_colors(map_data.territory_count)
        # Only show land territories in legend
        items = []
        for t in map_data.territories:
            if not t.is_ocean:
                biome_name = map_data.get_biome_name(t.biome)
                items.append((f"T{t.index} ({biome_name})", territory_colors[t.index]))

    # Legend dimensions
    legend_width = 300
    line_height = 20
    legend_height = max(100, len(items) * line_height + 40)

    legend_img = Image.new('RGB', (legend_width, legend_height), (255, 255, 255))
    draw = ImageDraw.Draw(legend_img)

    # Draw legend items
    y = 20
    for name, color in items[:50]:  # Limit to 50 items
        draw.rectangle([10, y, 30, y + 15], fill=color, outline=(0, 0, 0))
        draw.text((40, y), name, fill=(0, 0, 0))
        y += line_height

    # Save both images
    map_img.save(output_path)
    legend_path = output_path.with_name(output_path.stem + "_legend" + output_path.suffix)
    legend_img.save(legend_path)


if __name__ == "__main__":
    # Quick test with tiny_australia
    map_path = Path("humankind_maps/tiny_australia/The_Amplipodes.hmap")
    if map_path.exists():
        print(f"Loading {map_path}...")
        map_data = load_map(map_path)
        print(f"Map size: {map_data.width}x{map_data.height}")
        print(f"Territories: {map_data.territory_count} ({map_data.land_territory_count} land)")

        output_path = Path("test_render.png")
        render_map_with_legend(map_data, output_path, color_by="biome")
        print(f"Rendered to {output_path}")
