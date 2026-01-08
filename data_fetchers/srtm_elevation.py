#!/usr/bin/env python3
"""
SRTM Elevation Data Fetcher for Ukraine Map.

Uses the srtm.py package which automatically downloads and caches
SRTM tiles as needed. Much simpler than manual tile management.
"""

import srtm
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Tuple


class SRTMElevationFetcher:
    """
    Fetches elevation data using srtm.py package.

    The srtm.py package automatically downloads and caches SRTM tiles
    from NASA servers as needed.
    """

    # No data value
    NODATA = -9999

    def __init__(self, bounds: dict, cache_dir: Optional[Path] = None):
        """
        Initialize the elevation fetcher.

        Args:
            bounds: Dictionary with min_lon, max_lon, min_lat, max_lat
            cache_dir: Directory to cache data (default: data/srtm_cache)
        """
        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']

        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "data" / "srtm_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache file for grid elevations
        self.cache_file = self.cache_dir / "ukraine_elevations.npy"

        # Grid cache
        self._grid_cache: Optional[np.ndarray] = None

        # Initialize SRTM data fetcher
        self._elevation_data = srtm.get_data()
        print(f"  SRTM data initialized")

    def fetch(self, force_download: bool = False) -> Path:
        """Compatibility method - just returns cache dir."""
        return self.cache_dir

    def load(self) -> None:
        """Load cached data if available."""
        if self.cache_file.exists():
            print(f"  Loading cached elevation grid from: {self.cache_file}")
            self._grid_cache = np.load(self.cache_file)
            print(f"  Grid shape: {self._grid_cache.shape}")

    def get_elevation_at(self, lon: float, lat: float) -> float:
        """
        Get elevation at a specific coordinate.

        Args:
            lon: Longitude in degrees
            lat: Latitude in degrees

        Returns:
            Elevation in meters, or -9999 if no data
        """
        try:
            elev = self._elevation_data.get_elevation(lat, lon)
            if elev is None:
                return self.NODATA
            return float(elev)
        except Exception as e:
            return self.NODATA

    def get_grid_elevations(self,
                            grid_width: int,
                            grid_height: int,
                            **kwargs) -> np.ndarray:
        """
        Get elevation values for a regular grid covering the bounds.

        Args:
            grid_width: Number of columns
            grid_height: Number of rows

        Returns:
            2D numpy array of elevation values (grid_height x grid_width)
        """
        # Check if we have a cached grid of the same size
        if (self._grid_cache is not None and
            self._grid_cache.shape == (grid_height, grid_width)):
            print(f"  Using cached grid ({grid_width}x{grid_height})")
            return self._grid_cache

        # Check file cache
        if self.cache_file.exists():
            cached = np.load(self.cache_file)
            if cached.shape == (grid_height, grid_width):
                print(f"  Loaded cached grid from {self.cache_file}")
                self._grid_cache = cached
                return cached

        print(f"  Fetching elevation grid ({grid_width}x{grid_height} = {grid_width * grid_height} points)...")
        print(f"  Using SRTM data (tiles will be downloaded as needed)...")

        # Create output array
        elevations = np.full((grid_height, grid_width), self.NODATA, dtype=np.float32)

        total_points = grid_width * grid_height
        for row in range(grid_height):
            if row % 10 == 0:
                progress = (row * grid_width) / total_points * 100
                print(f"    Row {row}/{grid_height} ({progress:.0f}%)...")

            for col in range(grid_width):
                lon = self.min_lon + (col / grid_width) * (self.max_lon - self.min_lon)
                lat = self.max_lat - (row / grid_height) * (self.max_lat - self.min_lat)

                try:
                    elev = self._elevation_data.get_elevation(lat, lon)
                    if elev is not None:
                        elevations[row, col] = float(elev)
                except Exception:
                    pass  # Keep NODATA

        # Cache the result
        self._grid_cache = elevations
        np.save(self.cache_file, elevations)
        print(f"  Saved grid cache to {self.cache_file}")

        # Print stats
        valid = elevations[elevations != self.NODATA]
        if len(valid) > 0:
            print(f"  Elevation range: {valid.min():.0f} to {valid.max():.0f} m")
            print(f"  Mean elevation: {valid.mean():.0f} m")
            print(f"  Valid points: {len(valid)}/{total_points} ({len(valid)/total_points*100:.1f}%)")

        return elevations

    def get_stats(self) -> dict:
        """Get statistics about cached elevation data."""
        if self._grid_cache is None:
            return {'cached': False}

        valid = self._grid_cache[self._grid_cache != self.NODATA]

        return {
            'cached': True,
            'shape': self._grid_cache.shape,
            'min': float(np.min(valid)) if len(valid) > 0 else 0,
            'max': float(np.max(valid)) if len(valid) > 0 else 0,
            'mean': float(np.mean(valid)) if len(valid) > 0 else 0,
            'nodata_count': int(np.sum(self._grid_cache == self.NODATA))
        }


def main():
    """Test the elevation fetcher with Ukraine bounds."""
    import yaml

    # Load config
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]

    print("=" * 60)
    print("ELEVATION FETCHER TEST (srtm.py)")
    print("=" * 60)

    fetcher = SRTMElevationFetcher(bounds)

    # Test specific locations first (quick test)
    print(f"\nTest Locations:")
    test_points = [
        ("Kyiv", 30.5234, 50.4501, (150, 200)),
        ("Hoverla (Carpathians)", 24.5003, 48.1603, (1800, 2100)),
        ("Odesa", 30.7233, 46.4825, (0, 80)),
        ("Ai-Petri (Crimea)", 34.0587, 44.4508, (1000, 1300)),
        ("Kharkiv", 36.2304, 49.9935, (100, 200)),
        ("Dnipro", 35.0462, 48.4647, (50, 150)),
    ]

    all_ok = True
    for name, lon, lat, expected in test_points:
        elev = fetcher.get_elevation_at(lon, lat)
        if elev == fetcher.NODATA:
            status = "?"
            print(f"  {status} {name}: NO DATA (expected {expected[0]}-{expected[1]})")
            continue
        in_range = expected[0] <= elev <= expected[1]
        status = "✓" if in_range else "✗"
        if not in_range:
            all_ok = False
        print(f"  {status} {name}: {elev:.0f} m (expected {expected[0]}-{expected[1]})")

    if all_ok:
        print("\n  All test points within expected range!")

    # Test small grid
    print(f"\nTesting small grid fetch (10x10)...")
    small_grid = fetcher.get_grid_elevations(10, 10)
    print(f"  Grid shape: {small_grid.shape}")


if __name__ == "__main__":
    main()
