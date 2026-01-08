#!/usr/bin/env python3
"""
Copernicus Land Cover Data Fetcher for Ukraine Map.

Uses Copernicus Global Land Service 100m (CGLS-LC100) data from Zenodo.
Much smaller than ESA WorldCover 10m (~500MB vs ~45GB for Ukraine).

Copernicus CGLS-LC100 Classes:
    0   = Unknown
    20  = Shrubs
    30  = Herbaceous vegetation
    40  = Cultivated and managed vegetation/agriculture
    50  = Urban / built up
    60  = Bare / sparse vegetation
    70  = Snow and ice
    80  = Permanent water bodies
    90  = Herbaceous wetland
    100 = Moss and lichen
    111 = Closed forest, evergreen needle leaf
    112 = Closed forest, evergreen broad leaf
    113 = Closed forest, deciduous needle leaf
    114 = Closed forest, deciduous broad leaf
    115 = Closed forest, mixed
    116 = Closed forest, not matching any of the other definitions
    121 = Open forest, evergreen needle leaf
    122 = Open forest, evergreen broad leaf
    123 = Open forest, deciduous needle leaf
    124 = Open forest, deciduous broad leaf
    125 = Open forest, mixed
    126 = Open forest, not matching any of the other definitions
    200 = Oceans, seas
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import pickle

try:
    import rasterio
    from rasterio.windows import from_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("Warning: rasterio not installed. Install with: pip install rasterio")


class CopernicusLandCoverClass:
    """Copernicus CGLS-LC100 land cover class values."""
    UNKNOWN = 0
    SHRUBS = 20
    HERBACEOUS = 30
    CULTIVATED = 40
    URBAN = 50
    BARE_SPARSE = 60
    SNOW_ICE = 70
    WATER = 80
    WETLAND = 90
    MOSS_LICHEN = 100
    # Closed forests (111-116)
    CLOSED_FOREST_EVERGREEN_NEEDLE = 111
    CLOSED_FOREST_EVERGREEN_BROAD = 112
    CLOSED_FOREST_DECIDUOUS_NEEDLE = 113
    CLOSED_FOREST_DECIDUOUS_BROAD = 114
    CLOSED_FOREST_MIXED = 115
    CLOSED_FOREST_OTHER = 116
    # Open forests (121-126)
    OPEN_FOREST_EVERGREEN_NEEDLE = 121
    OPEN_FOREST_EVERGREEN_BROAD = 122
    OPEN_FOREST_DECIDUOUS_NEEDLE = 123
    OPEN_FOREST_DECIDUOUS_BROAD = 124
    OPEN_FOREST_MIXED = 125
    OPEN_FOREST_OTHER = 126
    OCEAN = 200

    NAMES = {
        0: "Unknown",
        20: "Shrubs",
        30: "Herbaceous vegetation",
        40: "Cultivated/agriculture",
        50: "Urban/built up",
        60: "Bare/sparse vegetation",
        70: "Snow and ice",
        80: "Permanent water",
        90: "Herbaceous wetland",
        100: "Moss and lichen",
        111: "Closed forest (evergreen needle)",
        112: "Closed forest (evergreen broad)",
        113: "Closed forest (deciduous needle)",
        114: "Closed forest (deciduous broad)",
        115: "Closed forest (mixed)",
        116: "Closed forest (other)",
        121: "Open forest (evergreen needle)",
        122: "Open forest (evergreen broad)",
        123: "Open forest (deciduous needle)",
        124: "Open forest (deciduous broad)",
        125: "Open forest (mixed)",
        126: "Open forest (other)",
        200: "Oceans/seas",
    }


class CopernicusLandCoverFetcher:
    """
    Fetches land cover data from Copernicus CGLS-LC100 (100m resolution).

    Uses global GeoTIFF from Zenodo - downloads once and caches.
    Much more efficient than ESA WorldCover 10m for our ~5km hex grid.
    """

    # Direct download URL for 2019 discrete classification map
    ZENODO_URL = (
        "https://zenodo.org/api/records/3939050/files/"
        "PROBAV_LC100_global_v3.0.1_2019-nrt_Discrete-Classification-map_EPSG-4326.tif/content"
    )

    def __init__(self, bounds: dict, cache_dir: Optional[Path] = None):
        """
        Initialize the Copernicus land cover fetcher.

        Args:
            bounds: Dictionary with min_lon, max_lon, min_lat, max_lat
            cache_dir: Directory to cache downloaded data (default: data/landcover_cache)
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

        # Cache files
        self.region_cache_file = self.cache_dir / "copernicus_ukraine_region.npy"
        self.region_meta_file = self.cache_dir / "copernicus_ukraine_region_meta.pkl"
        self.grid_cache_file = self.cache_dir / "copernicus_ukraine_grid.npy"
        self.grid_meta_file = self.cache_dir / "copernicus_ukraine_grid_meta.pkl"

        # Loaded data
        self._region_data: Optional[np.ndarray] = None
        self._region_transform = None

    def _validate_cache(self, npy_path: Path, meta_path: Path, min_size: int = 1000) -> bool:
        """
        Check if cached files are valid (both exist and npy is non-empty).

        Args:
            npy_path: Path to .npy cache file
            meta_path: Path to .pkl metadata file
            min_size: Minimum file size in bytes to be considered valid

        Returns:
            True if cache is valid, False otherwise
        """
        if not npy_path.exists() or not meta_path.exists():
            return False
        if npy_path.stat().st_size < min_size:
            # Corrupt/incomplete file - remove it
            print(f"  Removing corrupt cache: {npy_path}")
            npy_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            return False
        return True

    def _load_region_data(self) -> Tuple[np.ndarray, dict]:
        """
        Load land cover data for Ukraine region from cache or download.

        Uses rasterio's windowed reading to only download the region we need
        from the Cloud Optimized GeoTIFF on Zenodo.

        Returns:
            Tuple of (data array, metadata dict with transform)
        """
        # Check cache first
        if self._validate_cache(self.region_cache_file, self.region_meta_file, min_size=10000):
            print(f"  Loading cached region data: {self.region_cache_file}")
            data = np.load(self.region_cache_file)
            with open(self.region_meta_file, 'rb') as f:
                meta = pickle.load(f)
            return data, meta

        print(f"  Fetching Copernicus 100m land cover for Ukraine region...")
        print(f"  Bounds: {self.min_lon}-{self.max_lon}°E, {self.min_lat}-{self.max_lat}°N")
        print(f"  Source: Zenodo (Cloud Optimized GeoTIFF)")
        print(f"  This may take a few minutes on first run...")

        try:
            # Open remote COG and read only the window we need
            with rasterio.open(self.ZENODO_URL) as src:
                # Calculate window for our bounds
                window = from_bounds(
                    self.min_lon, self.min_lat,
                    self.max_lon, self.max_lat,
                    src.transform
                )

                # Read the windowed data
                data = src.read(1, window=window)

                # Get the transform for this window
                window_transform = src.window_transform(window)

                meta = {
                    'transform': window_transform,
                    'crs': str(src.crs),
                    'width': data.shape[1],
                    'height': data.shape[0],
                    'bounds': (self.min_lon, self.min_lat, self.max_lon, self.max_lat),
                }

            # Cache the data
            np.save(self.region_cache_file, data)
            with open(self.region_meta_file, 'wb') as f:
                pickle.dump(meta, f)

            print(f"  Downloaded region: {data.shape[1]}x{data.shape[0]} pixels")
            print(f"  Cached to: {self.region_cache_file}")
            print(f"  Cache size: {self.region_cache_file.stat().st_size / 1024 / 1024:.1f} MB")

            return data, meta

        except Exception as e:
            print(f"  Error fetching data: {e}")
            raise

    def get_landcover_at(self, lon: float, lat: float) -> int:
        """
        Get land cover class at a specific coordinate.

        Args:
            lon: Longitude in degrees
            lat: Latitude in degrees

        Returns:
            Land cover class value (0, 20, 30, etc.) or 0 if no data
        """
        if self._region_data is None:
            data, meta = self._load_region_data()
            self._region_data = data
            self._region_transform = meta['transform']

        # Convert lon/lat to pixel coordinates using the transform
        transform = self._region_transform
        col = int((lon - transform.c) / transform.a)
        row = int((lat - transform.f) / transform.e)

        # Check bounds
        if 0 <= row < self._region_data.shape[0] and 0 <= col < self._region_data.shape[1]:
            return int(self._region_data[row, col])

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
            grid_width: Number of columns (hex grid width)
            grid_height: Number of rows (hex grid height)
            use_cache: Whether to use cached grid data if available

        Returns:
            2D numpy array of land cover class values (grid_height x grid_width)
        """
        # Check for cached grid
        if use_cache and self._validate_cache(self.grid_cache_file, self.grid_meta_file, min_size=100):
            with open(self.grid_meta_file, 'rb') as f:
                cached_meta = pickle.load(f)

            if (cached_meta.get('width') == grid_width and
                cached_meta.get('height') == grid_height and
                cached_meta.get('bounds') == (self.min_lon, self.max_lon, self.min_lat, self.max_lat)):
                print(f"  Loading cached grid from {self.grid_cache_file}")
                return np.load(self.grid_cache_file)

        print(f"  Generating land cover grid ({grid_width}x{grid_height})...")

        # Ensure region data is loaded
        if self._region_data is None:
            self._load_region_data()

        # Create output array
        landcover = np.zeros((grid_height, grid_width), dtype=np.uint8)

        for row in range(grid_height):
            if row % 20 == 0:
                progress = row / grid_height * 100
                print(f"    Row {row}/{grid_height} ({progress:.0f}%)...")

            for col in range(grid_width):
                # Calculate geographic coordinates for this grid cell center
                lon = self.min_lon + (col + 0.5) / grid_width * (self.max_lon - self.min_lon)
                lat = self.max_lat - (row + 0.5) / grid_height * (self.max_lat - self.min_lat)

                landcover[row, col] = self.get_landcover_at(lon, lat)

        # Cache the grid
        np.save(self.grid_cache_file, landcover)
        with open(self.grid_meta_file, 'wb') as f:
            pickle.dump({
                'width': grid_width,
                'height': grid_height,
                'bounds': (self.min_lon, self.max_lon, self.min_lat, self.max_lat),
            }, f)
        print(f"  Saved grid cache to {self.grid_cache_file}")

        # Print distribution
        self._print_distribution(landcover)

        return landcover

    def _print_distribution(self, data: np.ndarray):
        """Print land cover class distribution."""
        print("\n  Land cover distribution:")
        unique, counts = np.unique(data, return_counts=True)
        total = data.size

        for val, count in sorted(zip(unique, counts), key=lambda x: -x[1]):
            name = CopernicusLandCoverClass.NAMES.get(val, f"Unknown ({val})")
            pct = 100 * count / total
            print(f"    {name:35}: {count:>6} ({pct:>5.1f}%)")

    def get_stats(self) -> dict:
        """Get statistics about loaded/cached data."""
        stats = {
            'region_cached': self.region_cache_file.exists(),
            'grid_cached': self.grid_cache_file.exists(),
        }

        if self.region_cache_file.exists():
            stats['region_size_mb'] = self.region_cache_file.stat().st_size / 1024 / 1024

        if self.grid_cache_file.exists():
            stats['grid_size_kb'] = self.grid_cache_file.stat().st_size / 1024

        return stats


def main():
    """Test the Copernicus land cover fetcher with Ukraine bounds."""
    import yaml

    # Load config
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid = config['grid']

    print("=" * 60)
    print("COPERNICUS LAND COVER FETCHER TEST (CGLS-LC100 100m)")
    print("=" * 60)
    print(f"\nBounds: {bounds['min_lon']}-{bounds['max_lon']}°E, {bounds['min_lat']}-{bounds['max_lat']}°N")
    print(f"Grid: {grid['width']}x{grid['height']}")

    fetcher = CopernicusLandCoverFetcher(bounds)

    # Test specific locations
    print(f"\nTest Locations:")
    test_points = [
        ("Kyiv (urban)", 30.5234, 50.4501, CopernicusLandCoverClass.URBAN),
        ("Carpathian Forest", 24.5, 48.5, CopernicusLandCoverClass.CLOSED_FOREST_DECIDUOUS_BROAD),
        ("Southern Steppe (farm)", 35.0, 47.0, CopernicusLandCoverClass.CULTIVATED),
        ("Black Sea", 31.0, 44.5, CopernicusLandCoverClass.OCEAN),
        ("Polesia Forest", 28.0, 51.5, CopernicusLandCoverClass.CLOSED_FOREST_MIXED),
    ]

    for name, lon, lat, expected in test_points:
        lc = fetcher.get_landcover_at(lon, lat)
        lc_name = CopernicusLandCoverClass.NAMES.get(lc, f"Unknown ({lc})")
        expected_name = CopernicusLandCoverClass.NAMES.get(expected, f"Unknown ({expected})")
        status = "✓" if lc == expected else "?"
        print(f"  {status} {name}: {lc_name} (expected {expected_name})")

    # Generate full grid
    print(f"\nGenerating full grid ({grid['width']}x{grid['height']})...")
    grid_data = fetcher.get_grid_landcover(grid['width'], grid['height'])
    print(f"  Grid shape: {grid_data.shape}")

    # Print stats
    print(f"\nCache stats: {fetcher.get_stats()}")


if __name__ == "__main__":
    main()
