#!/usr/bin/env python3
"""
Land Cover Data Fetcher for Ukraine Map.

Uses ESA WorldCover 10m v200 (2021) data from AWS S3 bucket.
Provides land cover classification that maps to Humankind terrain types.

ESA WorldCover Classes:
    10 = Tree cover
    20 = Shrubland
    30 = Grassland
    40 = Cropland
    50 = Built-up
    60 = Bare / sparse vegetation
    70 = Snow and ice
    80 = Permanent water bodies
    90 = Herbaceous wetland
    95 = Mangroves
    100 = Moss and lichen
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import pickle

# rasterio for reading Cloud Optimized GeoTIFFs
try:
    import rasterio
    from rasterio.windows import Window
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("Warning: rasterio not installed. Install with: pip install rasterio")


# ESA WorldCover land cover class values
class LandCoverClass:
    TREE_COVER = 10
    SHRUBLAND = 20
    GRASSLAND = 30
    CROPLAND = 40
    BUILT_UP = 50
    BARE_SPARSE = 60
    SNOW_ICE = 70
    WATER = 80
    WETLAND = 90
    MANGROVE = 95
    MOSS_LICHEN = 100

    # Human-readable names
    NAMES = {
        10: "Tree cover",
        20: "Shrubland",
        30: "Grassland",
        40: "Cropland",
        50: "Built-up",
        60: "Bare/sparse vegetation",
        70: "Snow and ice",
        80: "Permanent water",
        90: "Herbaceous wetland",
        95: "Mangroves",
        100: "Moss and lichen",
    }


class LandCoverFetcher:
    """
    Fetches land cover data from ESA WorldCover via AWS S3.

    Uses Cloud Optimized GeoTIFFs for efficient partial reads.
    Caches downloaded data to avoid repeated API calls.
    """

    # Base URL for ESA WorldCover on AWS S3
    S3_BASE_URL = "https://esa-worldcover.s3.amazonaws.com/v200/2021/map"

    # Tile size in degrees (3x3 degree tiles)
    TILE_SIZE = 3

    # Resolution: 10m per pixel, approximately 0.00009 degrees at equator
    RESOLUTION_DEG = 10 / 111320  # ~0.0000899 degrees

    def __init__(self, bounds: dict, cache_dir: Optional[Path] = None):
        """
        Initialize the land cover fetcher.

        Args:
            bounds: Dictionary with min_lon, max_lon, min_lat, max_lat
            cache_dir: Directory to cache downloaded tiles (default: data/landcover_cache)
        """
        if not RASTERIO_AVAILABLE:
            raise ImportError("rasterio is required. Install with: pip install rasterio")

        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']

        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "data" / "landcover_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache file for grid land cover data
        self.cache_file = self.cache_dir / "ukraine_landcover.npy"
        self.metadata_file = self.cache_dir / "ukraine_landcover_meta.pkl"

        # Grid cache
        self._grid_cache: Optional[np.ndarray] = None

        # Track which tiles we've loaded
        self._loaded_tiles = {}

    def _get_tile_name(self, lat: float, lon: float) -> str:
        """
        Get the tile filename for a given coordinate.

        Tiles are named by their lower-left corner, rounded down to 3-degree boundaries.
        Format: ESA_WorldCover_10m_2021_v200_N{lat}E{lon}_Map.tif

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Tile filename
        """
        # Round down to 3-degree tile boundary
        tile_lat = int(lat // self.TILE_SIZE) * self.TILE_SIZE
        tile_lon = int(lon // self.TILE_SIZE) * self.TILE_SIZE

        # Format coordinates
        lat_str = f"N{abs(tile_lat):02d}" if tile_lat >= 0 else f"S{abs(tile_lat):02d}"
        lon_str = f"E{abs(tile_lon):03d}" if tile_lon >= 0 else f"W{abs(tile_lon):03d}"

        return f"ESA_WorldCover_10m_2021_v200_{lat_str}{lon_str}_Map.tif"

    def _get_tile_url(self, tile_name: str) -> str:
        """Get the S3 URL for a tile."""
        return f"{self.S3_BASE_URL}/{tile_name}"

    def _get_required_tiles(self) -> list:
        """
        Determine which tiles are needed to cover the bounds.

        Returns:
            List of (tile_name, tile_bounds) tuples
        """
        tiles = []

        # Iterate over tile boundaries that cover our bounds
        lat = int(self.min_lat // self.TILE_SIZE) * self.TILE_SIZE
        while lat < self.max_lat:
            lon = int(self.min_lon // self.TILE_SIZE) * self.TILE_SIZE
            while lon < self.max_lon:
                tile_name = self._get_tile_name(lat + 0.1, lon + 0.1)  # Offset to ensure correct tile
                tile_bounds = {
                    'min_lat': lat,
                    'max_lat': lat + self.TILE_SIZE,
                    'min_lon': lon,
                    'max_lon': lon + self.TILE_SIZE,
                }
                tiles.append((tile_name, tile_bounds))
                lon += self.TILE_SIZE
            lat += self.TILE_SIZE

        return tiles

    def _load_tile(self, tile_name: str) -> Optional[Tuple[np.ndarray, dict]]:
        """
        Load a single tile from S3 or cache.

        Args:
            tile_name: Name of the tile file

        Returns:
            Tuple of (data array, transform dict) or None if failed
        """
        # Check local cache first
        cached_path = self.cache_dir / tile_name.replace('.tif', '.npy')
        meta_path = self.cache_dir / tile_name.replace('.tif', '_meta.pkl')

        if cached_path.exists() and meta_path.exists():
            print(f"    Loading cached: {tile_name}")
            data = np.load(cached_path)
            with open(meta_path, 'rb') as f:
                meta = pickle.load(f)
            return data, meta

        # Fetch from S3
        url = self._get_tile_url(tile_name)
        print(f"    Fetching from S3: {tile_name}")

        try:
            with rasterio.open(url) as src:
                data = src.read(1)  # Single band
                meta = {
                    'transform': src.transform,
                    'crs': str(src.crs),
                    'width': src.width,
                    'height': src.height,
                    'bounds': src.bounds,
                }

            # Cache the data
            np.save(cached_path, data)
            with open(meta_path, 'wb') as f:
                pickle.dump(meta, f)
            print(f"    Cached to: {cached_path}")

            return data, meta

        except Exception as e:
            print(f"    Warning: Failed to load {tile_name}: {e}")
            return None

    def get_landcover_at(self, lon: float, lat: float) -> int:
        """
        Get land cover class at a specific coordinate.

        Args:
            lon: Longitude in degrees
            lat: Latitude in degrees

        Returns:
            Land cover class value (10, 20, 30, etc.) or 0 if no data
        """
        tile_name = self._get_tile_name(lat, lon)

        # Load tile if not already loaded
        if tile_name not in self._loaded_tiles:
            result = self._load_tile(tile_name)
            if result is None:
                return 0
            self._loaded_tiles[tile_name] = result

        data, meta = self._loaded_tiles[tile_name]

        # Convert lon/lat to pixel coordinates
        transform = meta['transform']
        # Inverse transform: geo -> pixel
        col = int((lon - transform.c) / transform.a)
        row = int((lat - transform.f) / transform.e)

        # Check bounds
        if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
            return int(data[row, col])

        return 0

    def get_grid_landcover(
        self,
        grid_width: int,
        grid_height: int,
        use_cache: bool = True,
    ) -> np.ndarray:
        """
        Get land cover values for a regular grid covering the bounds.

        Args:
            grid_width: Number of columns
            grid_height: Number of rows
            use_cache: Whether to use cached data if available

        Returns:
            2D numpy array of land cover class values (grid_height x grid_width)
        """
        # Check if we have a cached grid of the same size
        if use_cache and self.cache_file.exists() and self.metadata_file.exists():
            with open(self.metadata_file, 'rb') as f:
                cached_meta = pickle.load(f)

            if (cached_meta.get('width') == grid_width and
                cached_meta.get('height') == grid_height and
                cached_meta.get('bounds') == (self.min_lon, self.max_lon, self.min_lat, self.max_lat)):
                print(f"  Loading cached land cover grid from {self.cache_file}")
                self._grid_cache = np.load(self.cache_file)
                return self._grid_cache

        print(f"  Fetching land cover grid ({grid_width}x{grid_height} = {grid_width * grid_height} points)...")

        # Get required tiles
        tiles = self._get_required_tiles()
        print(f"  Need {len(tiles)} tiles to cover bounds")

        # Pre-load all tiles
        for tile_name, _ in tiles:
            if tile_name not in self._loaded_tiles:
                result = self._load_tile(tile_name)
                if result is not None:
                    self._loaded_tiles[tile_name] = result

        # Create output array
        landcover = np.zeros((grid_height, grid_width), dtype=np.uint8)

        total_points = grid_width * grid_height
        for row in range(grid_height):
            if row % 10 == 0:
                progress = (row * grid_width) / total_points * 100
                print(f"    Row {row}/{grid_height} ({progress:.0f}%)...")

            for col in range(grid_width):
                # Calculate geographic coordinates for this grid cell
                lon = self.min_lon + (col + 0.5) / grid_width * (self.max_lon - self.min_lon)
                lat = self.max_lat - (row + 0.5) / grid_height * (self.max_lat - self.min_lat)

                landcover[row, col] = self.get_landcover_at(lon, lat)

        # Cache the result
        self._grid_cache = landcover
        np.save(self.cache_file, landcover)
        with open(self.metadata_file, 'wb') as f:
            pickle.dump({
                'width': grid_width,
                'height': grid_height,
                'bounds': (self.min_lon, self.max_lon, self.min_lat, self.max_lat),
            }, f)
        print(f"  Saved grid cache to {self.cache_file}")

        # Print stats
        self._print_distribution(landcover)

        return landcover

    def _print_distribution(self, data: np.ndarray):
        """Print land cover class distribution."""
        print("\n  Land cover distribution:")
        unique, counts = np.unique(data, return_counts=True)
        total = data.size

        for val, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
            name = LandCoverClass.NAMES.get(val, f"Unknown ({val})")
            pct = 100 * count / total
            print(f"    {name:25}: {count:>6} ({pct:>5.1f}%)")

    def get_stats(self) -> dict:
        """Get statistics about cached land cover data."""
        if self._grid_cache is None:
            return {'cached': False}

        unique, counts = np.unique(self._grid_cache, return_counts=True)

        return {
            'cached': True,
            'shape': self._grid_cache.shape,
            'classes': dict(zip(unique.tolist(), counts.tolist())),
        }


def main():
    """Test the land cover fetcher with Ukraine bounds."""
    import yaml

    # Load config
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]

    print("=" * 60)
    print("LAND COVER FETCHER TEST (ESA WorldCover)")
    print("=" * 60)
    print(f"\nBounds: {bounds}")

    fetcher = LandCoverFetcher(bounds)

    # Test specific locations
    print(f"\nTest Locations:")
    test_points = [
        ("Kyiv (urban)", 30.5234, 50.4501, LandCoverClass.BUILT_UP),
        ("Carpathian Forest", 24.5, 48.5, LandCoverClass.TREE_COVER),
        ("Southern Steppe", 35.0, 47.0, LandCoverClass.CROPLAND),
        ("Black Sea", 31.0, 45.0, LandCoverClass.WATER),
        ("Polesia Forest", 28.0, 51.5, LandCoverClass.TREE_COVER),
    ]

    for name, lon, lat, expected in test_points:
        lc = fetcher.get_landcover_at(lon, lat)
        lc_name = LandCoverClass.NAMES.get(lc, f"Unknown ({lc})")
        expected_name = LandCoverClass.NAMES.get(expected, f"Unknown ({expected})")
        status = "✓" if lc == expected else "?"
        print(f"  {status} {name}: {lc_name} (expected {expected_name})")

    # Test small grid
    print(f"\nTesting small grid fetch (30x18)...")
    small_grid = fetcher.get_grid_landcover(30, 18, use_cache=False)
    print(f"  Grid shape: {small_grid.shape}")


if __name__ == "__main__":
    main()
