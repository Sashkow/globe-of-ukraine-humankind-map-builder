#!/usr/bin/env python3
"""
Generate Ukraine heightmap PNG for Humankind map editor import.

This script creates:
1. ukraine_heightmap.png - Elevation data for Ukraine
2. ukraine_palette.png - Color palette reference

The heightmap uses 16 elevation levels (-3 to 12) where:
- -3 to -1: Deep water (Black Sea, Sea of Azov)
- 0: Sea level / coastal
- 1-12: Increasing elevation (plains -> mountains)
"""

import numpy as np
from PIL import Image
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point
import yaml

# Humankind elevation palette (16 levels: -3 to 12)
# Each level maps to a distinct color for import
ELEVATION_PALETTE = {
    -3: (0, 0, 80),      # Deep ocean - dark blue
    -2: (0, 0, 120),     # Ocean - blue
    -1: (0, 60, 180),    # Shallow water - light blue
    0:  (0, 150, 200),   # Sea level / coast - cyan
    1:  (100, 200, 100), # Low plains - light green
    2:  (80, 180, 80),   # Plains - green
    3:  (60, 160, 60),   # Low hills - darker green
    4:  (150, 180, 80),  # Hills - yellow-green
    5:  (180, 180, 60),  # Higher hills - olive
    6:  (200, 170, 100), # Upland - tan
    7:  (180, 140, 80),  # Low mountains - brown
    8:  (160, 120, 80),  # Mountains - darker brown
    9:  (140, 100, 70),  # High mountains - dark brown
    10: (180, 180, 180), # Alpine - gray
    11: (220, 220, 220), # High alpine - light gray
    12: (255, 255, 255), # Peak / snow - white
}


class UkraineHeightmapGenerator:
    """Generate heightmap PNG for Ukraine suitable for Humankind import."""

    def __init__(self):
        """Initialize generator using config.yaml values."""
        # Load config
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Grid dimensions from config
        self.width = config['grid']['width']
        self.height = config['grid']['height']

        # Geographic bounds from config (use active config)
        active = config['active_config']
        bounds = config['bounds'][active]
        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']

        print(f"Config: {self.width}x{self.height}, bounds: {self.min_lon}-{self.max_lon}°E, {self.min_lat}-{self.max_lat}°N")

        self.elevation_data = None

        # Load Ukraine boundary from raion data
        self.ukraine_gdf = None
        raion_path = Path(__file__).parent / config['ukraine']['raions_file']
        if raion_path.exists():
            self.ukraine_gdf = gpd.read_file(raion_path)
            # Dissolve to get country outline
            self.ukraine_boundary = self.ukraine_gdf.dissolve().geometry.iloc[0]
        else:
            self.ukraine_boundary = None

    def download_elevation_data(self) -> np.ndarray:
        """
        Generate elevation data for Ukraine region.

        Returns:
            numpy array of elevation values
        """
        print("Generating elevation data for Ukraine...")

        # Create base elevation grid
        lons = np.linspace(self.min_lon, self.max_lon, self.width)
        lats = np.linspace(self.max_lat, self.min_lat, self.height)  # Note: lat decreases going down
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # Start with ocean everywhere
        elevation = np.full((self.height, self.width), -2, dtype=np.float32)

        # Create Ukraine land mask
        ukraine_mask = self._create_ukraine_mask(lon_grid, lat_grid)

        # Land = level 2 (green plains)
        elevation[ukraine_mask] = 2

        self.elevation_data = elevation
        return elevation

    def _create_ukraine_mask(self, lon_grid: np.ndarray, lat_grid: np.ndarray) -> np.ndarray:
        """Create a mask for Ukraine land area using actual boundary data."""
        mask = np.zeros(lon_grid.shape, dtype=bool)

        if self.ukraine_boundary is not None:
            # Use actual Ukraine boundary from GeoJSON
            print("  Using actual Ukraine boundary from raion data...")
            for i in range(lon_grid.shape[0]):
                for j in range(lon_grid.shape[1]):
                    lon, lat = lon_grid[i, j], lat_grid[i, j]
                    point = Point(lon, lat)
                    if self.ukraine_boundary.contains(point):
                        mask[i, j] = True
        else:
            # Fallback to simplified boundary
            print("  Using simplified Ukraine boundary (no GeoJSON found)...")
            for i in range(lon_grid.shape[0]):
                for j in range(lon_grid.shape[1]):
                    lon, lat = lon_grid[i, j], lat_grid[i, j]

                    # Very simplified boundary check
                    if 22 <= lon <= 40 and 45 <= lat <= 52:
                        if lat > 51.5 and lon < 24:
                            continue
                        if lat > 51.5 and lon > 38:
                            continue
                        if lon > 40 - (lat - 46) * 2:
                            continue
                        if lat < 46 and lon > 35:
                            continue
                        if lat < 45.5 and lon < 29:
                            continue
                        mask[i, j] = True

                    # Western Ukraine
                    if 22 <= lon <= 25 and 48 <= lat <= 51:
                        if lon > 22 + (lat - 48) * 0.5:
                            mask[i, j] = True

                    # Crimea
                    if 33 <= lon <= 36.5 and 44.3 <= lat <= 46:
                        if lat > 44.5 or (lon > 33.5 and lon < 36):
                            mask[i, j] = True

        return mask

    def _add_carpathians(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray) -> np.ndarray:
        """Add Carpathian Mountains in western Ukraine."""
        # Carpathians roughly at 23-25°E, 47.5-49°N
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                lon, lat = lon_grid[i, j], lat_grid[i, j]

                # Carpathian core
                if 23 <= lon <= 25 and 47.5 <= lat <= 49:
                    # Distance from mountain center
                    center_lon, center_lat = 24, 48.3
                    dist = np.sqrt((lon - center_lon)**2 + (lat - center_lat)**2)

                    if dist < 1.5:
                        # Highest peaks near center
                        peak_elev = 12 - dist * 5
                        elevation[i, j] = max(elevation[i, j], peak_elev)
                    elif dist < 2.5:
                        # Foothills
                        foothill_elev = 6 - (dist - 1.5) * 3
                        elevation[i, j] = max(elevation[i, j], foothill_elev)

                # Extended Carpathian foothills
                if 22.5 <= lon <= 26 and 47 <= lat <= 49.5:
                    if elevation[i, j] < 3:
                        elevation[i, j] = max(elevation[i, j], 3)

        return elevation

    def _add_crimean_mountains(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray) -> np.ndarray:
        """Add Crimean Mountains along southern coast."""
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                lon, lat = lon_grid[i, j], lat_grid[i, j]

                # Crimean mountains along south coast (44.3-44.8°N, 33.5-35°E)
                if 33.5 <= lon <= 35 and 44.3 <= lat <= 44.8:
                    # Distance from coast (higher near south)
                    coast_dist = lat - 44.3
                    if coast_dist < 0.3:
                        elevation[i, j] = max(elevation[i, j], 8 - coast_dist * 15)
                    elif coast_dist < 0.5:
                        elevation[i, j] = max(elevation[i, j], 5)

        return elevation

    def _add_donets_ridge(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray) -> np.ndarray:
        """Add Donets Ridge in eastern Ukraine."""
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                lon, lat = lon_grid[i, j], lat_grid[i, j]

                # Donets Ridge (gentle hills, 37-40°E, 48-50°N)
                if 37 <= lon <= 40 and 48 <= lat <= 50:
                    # Gentle elevation increase
                    elevation[i, j] = max(elevation[i, j], 3 + np.sin((lon - 37) * 2) * 1.5)

        return elevation

    def _add_podolian_upland(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray) -> np.ndarray:
        """Add Podolian Upland in west-central Ukraine."""
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                lon, lat = lon_grid[i, j], lat_grid[i, j]

                # Podolian Upland (26-32°E, 48-50°N)
                if 26 <= lon <= 32 and 48 <= lat <= 50:
                    # Moderate elevation
                    elevation[i, j] = max(elevation[i, j], 4 + np.sin((lon - 26) * 0.5) * 1.5)

        return elevation

    def _add_river_valleys(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray,
                          ukraine_mask: np.ndarray) -> np.ndarray:
        """Add river valleys (slightly lower elevation)."""
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                if not ukraine_mask[i, j]:
                    continue

                lon, lat = lon_grid[i, j], lat_grid[i, j]

                # Dnipro River (runs roughly 30.5°E from north to south)
                if abs(lon - 30.5) < 0.5 and 46.5 <= lat <= 51.5:
                    elevation[i, j] = max(0, elevation[i, j] - 1)

                # Dniester River (southwest, roughly follows 27-30°E at lower latitudes)
                if 27 <= lon <= 30 and 46 <= lat <= 48.5:
                    if abs(lon - (28 + (lat - 46) * 0.5)) < 0.3:
                        elevation[i, j] = max(0, elevation[i, j] - 1)

                # Southern Bug
                if 29 <= lon <= 32 and 47 <= lat <= 49:
                    if abs(lon - (30 + (lat - 47) * 0.5)) < 0.3:
                        elevation[i, j] = max(0, elevation[i, j] - 0.5)

        return elevation

    def _add_water_bodies(self, elevation: np.ndarray, lon_grid: np.ndarray, lat_grid: np.ndarray,
                         ukraine_mask: np.ndarray) -> np.ndarray:
        """Add Black Sea, Sea of Azov, and other water."""
        for i in range(elevation.shape[0]):
            for j in range(elevation.shape[1]):
                lon, lat = lon_grid[i, j], lat_grid[i, j]

                if ukraine_mask[i, j]:
                    continue  # Skip land

                # Black Sea (south of Ukraine)
                if lat < 46 and 28 <= lon <= 42:
                    # Deeper further from coast
                    depth = min(3, (46 - lat) * 1.5)
                    elevation[i, j] = -depth

                # Sea of Azov (shallower)
                if 35 <= lon <= 40 and 45 <= lat <= 47:
                    elevation[i, j] = -1.5

                # General ocean
                if elevation[i, j] == 0 and not ukraine_mask[i, j]:
                    elevation[i, j] = -2

        return elevation

    def quantize_elevation(self, elevation: np.ndarray) -> np.ndarray:
        """
        Quantize continuous elevation to 16 discrete levels (-3 to 12).

        Args:
            elevation: Continuous elevation values

        Returns:
            Quantized elevation as integers from -3 to 12
        """
        # Clip to valid range
        elevation = np.clip(elevation, -3, 12)

        # Round to nearest integer
        quantized = np.round(elevation).astype(np.int8)

        return quantized

    def elevation_to_image(self, quantized_elevation: np.ndarray) -> Image.Image:
        """
        Convert quantized elevation to RGB image using palette.

        Args:
            quantized_elevation: Integer elevation values (-3 to 12)

        Returns:
            PIL Image with colored heightmap
        """
        height, width = quantized_elevation.shape
        img_array = np.zeros((height, width, 3), dtype=np.uint8)

        for level, color in ELEVATION_PALETTE.items():
            mask = quantized_elevation == level
            img_array[mask] = color

        return Image.fromarray(img_array, mode='RGB')

    def generate_palette_image(self) -> Image.Image:
        """
        Generate palette reference image (16 color squares).

        Returns:
            PIL Image showing all elevation colors with labels
        """
        square_size = 30
        padding = 2
        total_levels = 16  # -3 to 12

        width = total_levels * (square_size + padding) + padding
        height = square_size + padding * 2 + 20  # Extra for labels

        img = Image.new('RGB', (width, height), (255, 255, 255))

        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)

        for i, level in enumerate(range(-3, 13)):
            x = padding + i * (square_size + padding)
            y = padding

            color = ELEVATION_PALETTE[level]
            draw.rectangle([x, y, x + square_size, y + square_size], fill=color, outline=(0, 0, 0))

            # Add level label
            label = str(level)
            draw.text((x + square_size // 2 - 5, y + square_size + 2), label, fill=(0, 0, 0))

        return img

    def generate(self, output_dir: Path = None) -> tuple[Path, Path]:
        """
        Generate heightmap and palette PNGs.

        Args:
            output_dir: Directory to save output files

        Returns:
            Tuple of (heightmap_path, palette_path)
        """
        if output_dir is None:
            output_dir = Path(__file__).parent / "output" / "heightmaps"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate elevation data
        print(f"Generating Ukraine heightmap ({self.width}x{self.height})...")
        elevation = self.download_elevation_data()

        # Quantize to 16 levels
        print("Quantizing elevation to 16 levels...")
        quantized = self.quantize_elevation(elevation)

        # Print statistics
        print("\nElevation statistics:")
        for level in range(-3, 13):
            count = np.sum(quantized == level)
            pct = count / quantized.size * 100
            if count > 0:
                print(f"  Level {level:3d}: {count:5d} pixels ({pct:5.1f}%)")

        # Generate heightmap image
        print("\nGenerating heightmap image...")
        heightmap_img = self.elevation_to_image(quantized)
        heightmap_path = output_dir / "ukraine_heightmap.png"
        heightmap_img.save(heightmap_path)
        print(f"  Saved: {heightmap_path}")

        # Generate palette image
        print("Generating palette image...")
        palette_img = self.generate_palette_image()
        palette_path = output_dir / "ukraine_palette.png"
        palette_img.save(palette_path)
        print(f"  Saved: {palette_path}")

        return heightmap_path, palette_path


def main():
    """Main entry point."""
    generator = UkraineHeightmapGenerator()
    heightmap_path, palette_path = generator.generate()

    print("\n" + "=" * 60)
    print("HEIGHTMAP GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nOutput files:")
    print(f"  - {heightmap_path}")
    print(f"  - {palette_path}")
    print(f"\nTo use in Humankind Map Editor:")
    print("  1. Launch Map Editor from game menu")
    print("  2. Create new map or open existing")
    print("  3. Use 'Import Heightmap' feature")
    print("  4. Select ukraine_heightmap.png")
    print("  5. Apply ukraine_palette.png as color reference")


if __name__ == "__main__":
    main()
