#!/usr/bin/env python3
"""
Render a Humankind map file to an image
"""
import xml.etree.ElementTree as ET
import base64
from io import BytesIO
from PIL import Image
import numpy as np
import sys
import os

# Biome color mapping
BIOME_COLORS = {
    0: (220, 238, 255),  # Arctic - light blue
    1: (200, 150, 100),  # Badlands - tan
    2: (255, 220, 150),  # Desert - sandy yellow
    3: (150, 200, 100),  # Grassland - light green
    4: (180, 170, 120),  # Mediterranean - olive
    5: (210, 180, 120),  # Savanna - tan/yellow
    6: (120, 150, 120),  # Taiga - dark green
    7: (130, 180, 110),  # Temperate - green
    8: (100, 180, 100),  # Tropical - bright green
    9: (170, 190, 190),  # Tundra - gray-blue
}

OCEAN_COLOR = (70, 130, 180)  # Steel blue for ocean


def parse_map_file(file_path):
    """Parse the Humankind map file and extract map data"""
    print(f"Parsing map file: {file_path}")
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Find TerrainSave element
    terrain_save = root.find('.//TerrainSave')
    if terrain_save is None:
        raise ValueError("Could not find TerrainSave element")

    # Get map dimensions
    width = int(terrain_save.find('Width').text)
    height = int(terrain_save.find('Height').text)
    print(f"Map dimensions: {width}x{height}")

    # Get territory database
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

    # Try to extract zone texture (which maps hex cells to territories)
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
        'zones_image': zones_image
    }


def render_map(map_data, output_path):
    """Render the map to an image"""
    width = map_data['width']
    height = map_data['height']
    territories = map_data['territories']
    zones_image = map_data['zones_image']

    # Create output image (upscale for better visibility)
    scale = 8
    img = Image.new('RGB', (width * scale, height * scale))
    pixels = img.load()

    if zones_image is not None:
        # Convert zones image to numpy array
        zones_array = np.array(zones_image)

        # Handle different image formats
        if len(zones_array.shape) == 2:
            # Grayscale image
            territory_indices = zones_array
        elif zones_array.shape[2] == 4:
            # RGBA - use red channel for territory index
            territory_indices = zones_array[:, :, 0]
        else:
            # RGB - use red channel
            territory_indices = zones_array[:, :, 0]

        # Render each pixel
        for y in range(height):
            for x in range(width):
                territory_idx = territory_indices[y, x]

                if territory_idx < len(territories):
                    territory = territories[territory_idx]

                    if territory['is_ocean']:
                        color = OCEAN_COLOR
                    else:
                        biome = territory['biome']
                        color = BIOME_COLORS.get(biome, (128, 128, 128))
                else:
                    color = (128, 128, 128)  # Gray for unknown

                # Fill the scaled pixels
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[x * scale + dx, y * scale + dy] = color
    else:
        # Fallback: just render territories in order
        print("Warning: No zones texture found, using simplified rendering")
        territories_per_row = int(np.sqrt(len(territories)))

        for idx, territory in enumerate(territories):
            tx = (idx % territories_per_row) * scale
            ty = (idx // territories_per_row) * scale

            if territory['is_ocean']:
                color = OCEAN_COLOR
            else:
                biome = territory['biome']
                color = BIOME_COLORS.get(biome, (128, 128, 128))

            for dy in range(scale):
                for dx in range(scale):
                    if tx + dx < width * scale and ty + dy < height * scale:
                        pixels[tx + dx, ty + dy] = color

    img.save(output_path)
    print(f"Map rendered to: {output_path}")

    # Create legend
    create_legend(output_path.replace('.png', '_legend.png'))


def create_legend(output_path):
    """Create a legend showing biome colors"""
    biome_names = [
        "Arctic", "Badlands", "Desert", "Grassland", "Mediterranean",
        "Savanna", "Taiga", "Temperate", "Tropical", "Tundra"
    ]

    legend_height = len(biome_names) * 30 + 40
    legend_width = 300

    img = Image.new('RGB', (legend_width, legend_height), (255, 255, 255))
    pixels = img.load()

    # Draw legend items
    for idx, name in enumerate(biome_names):
        y_pos = idx * 30 + 20
        color = BIOME_COLORS[idx]

        # Draw color box
        for y in range(y_pos, y_pos + 20):
            for x in range(10, 40):
                pixels[x, y] = color

    # Draw ocean
    y_pos = len(biome_names) * 30 + 20
    for y in range(y_pos, y_pos + 20):
        for x in range(10, 40):
            pixels[x, y] = OCEAN_COLOR

    img.save(output_path)
    print(f"Legend saved to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_map.py <path_to_Save.hms> [output.png]")
        sys.exit(1)

    map_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "map_render.png"

    if not os.path.exists(map_file):
        print(f"Error: Map file not found: {map_file}")
        sys.exit(1)

    map_data = parse_map_file(map_file)
    render_map(map_data, output_file)


if __name__ == '__main__':
    main()
