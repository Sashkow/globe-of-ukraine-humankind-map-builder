#!/usr/bin/env python3
"""
Render Humankind maps with proper hexagonal visualization
"""
import xml.etree.ElementTree as ET
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import sys
import os
import math

# Biome colors (same as before)
BIOME_COLORS = {
    0: (220, 238, 255),  # Arctic
    1: (200, 150, 100),  # Badlands
    2: (255, 220, 150),  # Desert
    3: (150, 200, 100),  # Grassland
    4: (180, 170, 120),  # Mediterranean
    5: (210, 180, 120),  # Savanna
    6: (120, 150, 120),  # Taiga
    7: (130, 180, 110),  # Temperate
    8: (100, 180, 100),  # Tropical
    9: (170, 190, 190),  # Tundra
}

OCEAN_COLOR = (70, 130, 180)
BORDER_COLOR = (50, 50, 50)


def parse_map_file(file_path):
    """Parse Humankind map file"""
    print(f"Parsing map file: {file_path}")
    tree = ET.parse(file_path)
    root = tree.getroot()

    terrain_save = root.find('.//TerrainSave')
    if terrain_save is None:
        raise ValueError("Could not find TerrainSave element")

    width = int(terrain_save.find('Width').text)
    height = int(terrain_save.find('Height').text)
    print(f"Map dimensions: {width}x{height}")

    # Get biome names
    biome_names_elem = terrain_save.find('BiomeNames')
    biome_names = [elem.text for elem in biome_names_elem.findall('String')]

    # Get territories
    territory_db = terrain_save.find('.//TerritoryDatabase')
    territories = territory_db.find('Territories')

    territory_data = []
    for item in territories.findall('Item'):
        continent = int(item.find('ContinentIndex').text)
        biome = int(item.find('Biome').text)
        is_ocean_elem = item.find('IsOcean')
        is_ocean = is_ocean_elem.text.lower() == 'true' if is_ocean_elem is not None else False

        territory_data.append({
            'continent': continent,
            'biome': biome,
            'is_ocean': is_ocean
        })

    print(f"Found {len(territory_data)} territories")

    # Load zones texture
    zones_texture_bytes = terrain_save.find('.//ZonesTexture.Bytes')
    zones_image = None
    if zones_texture_bytes is not None:
        try:
            png_data = base64.b64decode(zones_texture_bytes.text)
            zones_image = Image.open(BytesIO(png_data))
            print(f"Loaded zones texture: {zones_image.size}")
        except Exception as e:
            print(f"Warning: Could not decode zones texture: {e}")

    return {
        'width': width,
        'height': height,
        'territories': territory_data,
        'zones_image': zones_image,
        'biome_names': biome_names
    }


def hex_corner(center_x, center_y, size, i):
    """Calculate corner position of hexagon"""
    angle_deg = 60 * i
    angle_rad = math.pi / 180 * angle_deg
    return (
        center_x + size * math.cos(angle_rad),
        center_y + size * math.sin(angle_rad)
    )


def draw_hexagon(draw, center_x, center_y, size, fill_color, outline_color=None):
    """Draw a single hexagon"""
    points = [hex_corner(center_x, center_y, size, i) for i in range(6)]

    if fill_color:
        draw.polygon(points, fill=fill_color, outline=outline_color)
    elif outline_color:
        draw.polygon(points, outline=outline_color)


def render_hex_map(map_data, output_path, hex_size=30):
    """Render map with proper hexagonal tiles"""
    width = map_data['width']
    height = map_data['height']
    territories = map_data['territories']
    zones_image = map_data['zones_image']

    if zones_image is None:
        print("Error: No zones texture found")
        return

    # Convert zones to array
    zones_array = np.array(zones_image)
    if len(zones_array.shape) == 3:
        zones_array = zones_array[:, :, 0]  # Use first channel

    # Calculate output image size
    # Hexagons: width = size*2, height = size*sqrt(3)
    hex_width = hex_size * 2
    hex_height = hex_size * math.sqrt(3)

    img_width = int(width * hex_width * 0.75 + hex_width * 0.25)
    img_height = int(height * hex_height + hex_height * 0.5)

    print(f"Rendering {width}x{height} hex map to {img_width}x{img_height} image...")

    # Create image
    img = Image.new('RGB', (img_width, img_height), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw hexagons
    for row in range(height):
        for col in range(width):
            # Calculate hex center
            x = col * hex_width * 0.75
            y = row * hex_height

            # Offset every other column
            if col % 2 == 1:
                y += hex_height / 2

            # Get territory
            if 0 <= row < zones_array.shape[0] and 0 <= col < zones_array.shape[1]:
                territory_idx = zones_array[row, col]
            else:
                territory_idx = 0

            if territory_idx < len(territories):
                territory = territories[territory_idx]

                if territory['is_ocean']:
                    color = OCEAN_COLOR
                else:
                    biome = territory['biome']
                    color = BIOME_COLORS.get(biome, (128, 128, 128))
            else:
                color = (128, 128, 128)

            # Draw hexagon
            draw_hexagon(draw, x + hex_width/2, y + hex_height/2,
                        hex_size, color, BORDER_COLOR)

    img.save(output_path)
    print(f"Hexagonal map rendered to: {output_path}")


def render_simple_map(map_data, output_path):
    """Simple square-tile rendering (fast preview)"""
    width = map_data['width']
    height = map_data['height']
    territories = map_data['territories']
    zones_image = map_data['zones_image']

    if zones_image is None:
        print("Error: No zones texture found")
        return

    zones_array = np.array(zones_image)
    if len(zones_array.shape) == 3:
        zones_array = zones_array[:, :, 0]

    # Create output image (upscale)
    scale = 8
    img = Image.new('RGB', (width * scale, height * scale))
    pixels = img.load()

    print(f"Rendering simple {width}x{height} map...")

    for y in range(height):
        for x in range(width):
            if y < zones_array.shape[0] and x < zones_array.shape[1]:
                territory_idx = zones_array[y, x]
            else:
                territory_idx = 0

            if territory_idx < len(territories):
                territory = territories[territory_idx]

                if territory['is_ocean']:
                    color = OCEAN_COLOR
                else:
                    biome = territory['biome']
                    color = BIOME_COLORS.get(biome, (128, 128, 128))
            else:
                color = (128, 128, 128)

            # Fill scaled pixels
            for dy in range(scale):
                for dx in range(scale):
                    pixels[x * scale + dx, y * scale + dy] = color

    img.save(output_path)
    print(f"Simple map rendered to: {output_path}")


def create_legend(biome_names, output_path):
    """Create legend image"""
    legend_height = len(BIOME_COLORS) * 30 + 60
    legend_width = 300

    img = Image.new('RGB', (legend_width, legend_height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Title
    draw.text((10, 10), "Biome Legend", fill=(0, 0, 0))

    # Draw biome entries
    for idx, (biome_idx, color) in enumerate(BIOME_COLORS.items()):
        y_pos = idx * 30 + 40
        name = biome_names[biome_idx] if biome_idx < len(biome_names) else f"Biome {biome_idx}"

        # Color box
        draw.rectangle([10, y_pos, 40, y_pos + 20], fill=color, outline=(0, 0, 0))

        # Label
        draw.text((50, y_pos + 5), name, fill=(0, 0, 0))

    # Ocean
    y_pos = len(BIOME_COLORS) * 30 + 40
    draw.rectangle([10, y_pos, 40, y_pos + 20], fill=OCEAN_COLOR, outline=(0, 0, 0))
    draw.text((50, y_pos + 5), "Ocean", fill=(0, 0, 0))

    img.save(output_path)
    print(f"Legend saved to: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Render Humankind map with hexagons')
    parser.add_argument('input', help='Input .hms map file')
    parser.add_argument('output', nargs='?', default='output_map.png', help='Output PNG file')
    parser.add_argument('--hex', action='store_true', help='Use hexagonal rendering (slower)')
    parser.add_argument('--hex-size', type=int, default=30, help='Hexagon size for hex rendering')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    # Parse map
    map_data = parse_map_file(args.input)

    # Render
    if args.hex:
        render_hex_map(map_data, args.output, args.hex_size)
    else:
        render_simple_map(map_data, args.output)

    # Create legend
    legend_path = args.output.replace('.png', '_legend.png')
    create_legend(map_data['biome_names'], legend_path)


if __name__ == '__main__':
    main()
