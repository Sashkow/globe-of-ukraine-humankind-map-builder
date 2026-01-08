#!/usr/bin/env python3
"""
Hex Elevation Mapper for Ukraine Map.

Maps SRTM elevation data to hex grid cells and quantizes to Humankind's
16 elevation levels (-3 to 12).

Elevation Level Mapping:
    Level  Elevation (m)    Terrain Type
    -----  -------------    ------------
    -3     < -100           Deep ocean (Black Sea abyss, >200m depth)
    -2     -100 to -50      Ocean (Black Sea shelf, 50-200m depth)
    -1     -50 to 0         Shallow water / coastal (Sea of Azov, coast)
     0     0 to 50          Coastal lowlands
     1     50 to 100        Low plains
     2     100 to 150       Plains (most of Ukraine)
     3     150 to 200       Rolling plains
     4     200 to 300       Low hills
     5     300 to 400       Hills (Podolian Upland)
     6     400 to 600       High hills (Donets Ridge)
     7     600 to 800       Low mountains
     8     800 to 1000      Mountains (Crimean)
     9     1000 to 1200     High mountains
    10     1200 to 1500     Alpine (Carpathian foothills)
    11     1500 to 1800     High alpine
    12     > 1800           Peaks (Hoverla: 2061m)

Ocean Depth Logic:
    - Sea of Azov (max 14m): Always shallow (-1)
    - Black Sea coastal (1-3 tiles from land): Shallow (-1)
    - Black Sea shelf (4-6 tiles): Medium (-2)
    - Black Sea deep (>6 tiles): Deep (-3)
    - Exception: Near cliffs (land >100m), skip shallow water
"""

from pathlib import Path
from typing import Dict, Tuple, Optional, Set
import numpy as np

from data_fetchers.srtm_elevation import SRTMElevationFetcher


# Elevation thresholds for quantization (meters)
ELEVATION_THRESHOLDS = [
    (-9999, -100, -3),   # Deep ocean / nodata for water
    (-100, -50, -2),     # Ocean
    (-50, 0, -1),        # Shallow water
    (0, 50, 0),          # Coastal lowlands
    (50, 100, 1),        # Low plains
    (100, 150, 2),       # Plains
    (150, 200, 3),       # Rolling plains
    (200, 300, 4),       # Low hills
    (300, 400, 5),       # Hills
    (400, 600, 6),       # High hills
    (600, 800, 7),       # Low mountains
    (800, 1000, 8),      # Mountains
    (1000, 1200, 9),     # High mountains
    (1200, 1500, 10),    # Alpine
    (1500, 1800, 11),    # High alpine
    (1800, 10000, 12),   # Peaks
]

# Ocean depth configuration
SHALLOW_WATER_DISTANCE = 3    # Tiles from land for shallow water (-1)
MEDIUM_WATER_DISTANCE = 6     # Tiles from land for medium water (-2)
CLIFF_ELEVATION_THRESHOLD = 100  # Meters - land above this is considered "cliff"

# Sea of Azov bounding box (always shallow)
SEA_OF_AZOV_BOUNDS = {
    'min_lon': 34.5,
    'max_lon': 39.5,
    'min_lat': 45.0,
    'max_lat': 47.5,
}


class HexElevationMapper:
    """
    Maps SRTM elevation data to hex grid and quantizes to game levels.
    """

    def __init__(self,
                 srtm_fetcher: SRTMElevationFetcher,
                 grid_width: int,
                 grid_height: int,
                 bounds: dict,
                 ocean_default_level: int = -2):
        """
        Initialize the hex elevation mapper.

        Args:
            srtm_fetcher: SRTM data fetcher instance
            grid_width: Number of hex columns (150 for Humankind)
            grid_height: Number of hex rows (88 for Humankind)
            bounds: Geographic bounds {min_lon, max_lon, min_lat, max_lat}
            ocean_default_level: Default level for ocean/nodata (-2)
        """
        self.srtm = srtm_fetcher
        self.width = grid_width
        self.height = grid_height
        self.bounds = bounds
        self.ocean_default_level = ocean_default_level

        # Cache for elevation data
        self._hex_elevations: Optional[Dict[Tuple[int, int], int]] = None
        self._raw_elevations: Optional[Dict[Tuple[int, int], float]] = None
        self._distance_from_land: Optional[Dict[Tuple[int, int], int]] = None

    def _get_hex_neighbors(self, col: int, row: int) -> list:
        """Get all 6 neighbors of a hex."""
        neighbors = []
        if row % 2 == 0:  # Even row
            offsets = [(-1, -1), (0, -1), (-1, 0), (1, 0), (-1, 1), (0, 1)]
        else:  # Odd row
            offsets = [(0, -1), (1, -1), (-1, 0), (1, 0), (0, 1), (1, 1)]

        for dc, dr in offsets:
            nc, nr = col + dc, row + dr
            if 0 <= nc < self.width and 0 <= nr < self.height:
                neighbors.append((nc, nr))
        return neighbors

    def _calculate_distance_from_land(
        self,
        land_mask: Dict[Tuple[int, int], bool]
    ) -> Dict[Tuple[int, int], int]:
        """
        Calculate distance from land for each ocean hex using BFS.

        Args:
            land_mask: Dict mapping (col, row) -> is_land

        Returns:
            Dict mapping (col, row) -> distance from nearest land (0 for land)
        """
        if self._distance_from_land is not None:
            return self._distance_from_land

        print("  Calculating distance from land for ocean hexes...")

        distance = {}
        queue = []

        # Initialize: land hexes have distance 0, ocean hexes start with infinity
        for row in range(self.height):
            for col in range(self.width):
                pos = (col, row)
                if land_mask.get(pos, False):
                    distance[pos] = 0
                    queue.append(pos)
                else:
                    distance[pos] = 9999  # Large number for ocean

        # BFS from all land hexes simultaneously
        head = 0
        while head < len(queue):
            col, row = queue[head]
            head += 1
            current_dist = distance[(col, row)]

            for nc, nr in self._get_hex_neighbors(col, row):
                neighbor_pos = (nc, nr)
                if distance.get(neighbor_pos, 9999) > current_dist + 1:
                    distance[neighbor_pos] = current_dist + 1
                    queue.append(neighbor_pos)

        self._distance_from_land = distance
        return distance

    def _get_max_adjacent_land_elevation(
        self,
        col: int,
        row: int,
        land_mask: Dict[Tuple[int, int], bool],
        raw_elevations: Dict[Tuple[int, int], float]
    ) -> float:
        """
        Get the maximum elevation of adjacent land hexes.

        Used to detect cliffs - if adjacent land is very high,
        the water should be deeper (not shallow coastal).
        """
        max_elev = 0.0
        for nc, nr in self._get_hex_neighbors(col, row):
            neighbor_pos = (nc, nr)
            if land_mask.get(neighbor_pos, False):
                elev = raw_elevations.get(neighbor_pos, 0)
                if elev > max_elev:
                    max_elev = elev
        return max_elev

    def _is_in_sea_of_azov(self, lon: float, lat: float) -> bool:
        """Check if coordinates are in the Sea of Azov."""
        return (SEA_OF_AZOV_BOUNDS['min_lon'] <= lon <= SEA_OF_AZOV_BOUNDS['max_lon'] and
                SEA_OF_AZOV_BOUNDS['min_lat'] <= lat <= SEA_OF_AZOV_BOUNDS['max_lat'])

    def _assign_ocean_depth(
        self,
        col: int,
        row: int,
        land_mask: Dict[Tuple[int, int], bool],
        raw_elevations: Dict[Tuple[int, int], float],
        distance_from_land: Dict[Tuple[int, int], int]
    ) -> int:
        """
        Assign ocean depth level based on location and distance from land.

        Returns:
            -1 (shallow), -2 (medium), or -3 (deep)
        """
        lon, lat = self._pixel_to_geo(col, row)
        pos = (col, row)
        dist = distance_from_land.get(pos, 9999)

        # Sea of Azov is always shallow (max depth 14m)
        if self._is_in_sea_of_azov(lon, lat):
            return -1

        # Check for cliffs - if adjacent land is high, skip shallow water
        max_adjacent_elev = self._get_max_adjacent_land_elevation(
            col, row, land_mask, raw_elevations
        )
        is_near_cliff = max_adjacent_elev > CLIFF_ELEVATION_THRESHOLD

        # Assign depth based on distance from land
        if dist <= SHALLOW_WATER_DISTANCE:
            # Near coast - shallow unless near cliffs
            if is_near_cliff:
                return -2  # Medium depth near cliffs
            return -1  # Shallow coastal water

        elif dist <= MEDIUM_WATER_DISTANCE:
            return -2  # Medium depth (Black Sea shelf)

        else:
            return -3  # Deep ocean (Black Sea abyss)

    def _pixel_to_geo(self, col: int, row: int) -> Tuple[float, float]:
        """Convert pixel/hex coordinates to geographic coordinates."""
        lon = self.bounds['min_lon'] + (col / self.width) * (self.bounds['max_lon'] - self.bounds['min_lon'])
        lat = self.bounds['max_lat'] - (row / self.height) * (self.bounds['max_lat'] - self.bounds['min_lat'])
        return lon, lat

    def _quantize_elevation(self, meters: float) -> int:
        """
        Convert elevation in meters to game level (-3 to 12).

        Args:
            meters: Elevation in meters (or -9999 for nodata)

        Returns:
            Game elevation level from -3 to 12
        """
        # Handle nodata (typically ocean)
        if meters <= -9000:
            return self.ocean_default_level

        # Find matching threshold
        for min_elev, max_elev, level in ELEVATION_THRESHOLDS:
            if min_elev <= meters < max_elev:
                return level

        # Fallback for very high elevations
        if meters >= 1800:
            return 12

        # Fallback for unexpected values
        return self.ocean_default_level

    def get_hex_elevations(self,
                           ukraine_mask: Optional[Dict[Tuple[int, int], bool]] = None
                           ) -> Dict[Tuple[int, int], int]:
        """
        Get quantized elevation level for each hex.

        Args:
            ukraine_mask: Optional dict of (col, row) -> bool indicating
                          if hex is land (True) or ocean (False).
                          Used to assign ocean levels to water hexes.

        Returns:
            Dictionary mapping (col, row) -> elevation_level (-3 to 12)
        """
        if self._hex_elevations is not None:
            return self._hex_elevations

        print(f"  Mapping elevations for {self.width}x{self.height} hex grid...")

        # Fetch grid elevations using srtm.py (auto-downloads and caches tiles)
        elevation_grid = self.srtm.get_grid_elevations(self.width, self.height)

        self._hex_elevations = {}
        self._raw_elevations = {}

        # First pass: get all raw elevations
        for row in range(self.height):
            for col in range(self.width):
                elev_meters = float(elevation_grid[row, col])
                self._raw_elevations[(col, row)] = elev_meters

        # Calculate distance from land if we have a mask
        if ukraine_mask is not None:
            self._distance_from_land = self._calculate_distance_from_land(ukraine_mask)

        # Second pass: assign elevation levels
        ocean_depth_stats = {-1: 0, -2: 0, -3: 0}

        for row in range(self.height):
            for col in range(self.width):
                pos = (col, row)
                elev_meters = self._raw_elevations[pos]

                # If we have a ukraine mask and this is ocean, use sophisticated depth assignment
                if ukraine_mask is not None:
                    is_land = ukraine_mask.get(pos, False)
                    if not is_land:
                        # Use sophisticated depth assignment
                        depth_level = self._assign_ocean_depth(
                            col, row, ukraine_mask, self._raw_elevations,
                            self._distance_from_land
                        )
                        self._hex_elevations[pos] = depth_level
                        ocean_depth_stats[depth_level] = ocean_depth_stats.get(depth_level, 0) + 1
                        continue

                # Quantize elevation for land
                level = self._quantize_elevation(elev_meters)
                self._hex_elevations[pos] = level

        # Print ocean depth statistics
        if ukraine_mask is not None:
            total_ocean = sum(ocean_depth_stats.values())
            print(f"  Ocean depth distribution ({total_ocean} hexes):")
            print(f"    Shallow (-1): {ocean_depth_stats[-1]} hexes")
            print(f"    Medium (-2): {ocean_depth_stats[-2]} hexes")
            print(f"    Deep (-3): {ocean_depth_stats[-3]} hexes")

        return self._hex_elevations

    def get_raw_elevations(self) -> Dict[Tuple[int, int], float]:
        """Get raw elevation values in meters for each hex."""
        if self._raw_elevations is None:
            self.get_hex_elevations()
        return self._raw_elevations

    def get_elevation_stats(self) -> dict:
        """Get statistics about the elevation distribution."""
        if self._hex_elevations is None:
            self.get_hex_elevations()

        # Count hexes per level
        level_counts = {}
        for level in self._hex_elevations.values():
            level_counts[level] = level_counts.get(level, 0) + 1

        # Raw elevation stats (excluding nodata)
        valid_elevations = [e for e in self._raw_elevations.values() if e > -9000]

        return {
            'level_distribution': dict(sorted(level_counts.items())),
            'total_hexes': len(self._hex_elevations),
            'raw_min': min(valid_elevations) if valid_elevations else 0,
            'raw_max': max(valid_elevations) if valid_elevations else 0,
            'raw_mean': sum(valid_elevations) / len(valid_elevations) if valid_elevations else 0,
            'nodata_count': sum(1 for e in self._raw_elevations.values() if e <= -9000),
        }

    def create_elevation_array(self) -> np.ndarray:
        """
        Create a 2D numpy array of elevation levels.

        Returns:
            Array of shape (height, width) with values -3 to 12
        """
        if self._hex_elevations is None:
            self.get_hex_elevations()

        arr = np.zeros((self.height, self.width), dtype=np.int8)
        for (col, row), level in self._hex_elevations.items():
            arr[row, col] = level

        return arr

    def validate_known_points(self) -> dict:
        """
        Validate elevation at known geographic points.

        Returns:
            Dictionary of point name -> (expected_level, actual_level, meters)
        """
        if self._raw_elevations is None:
            self.get_hex_elevations()

        # Known validation points with expected elevation ranges
        validation_points = {
            'Hoverla (Carpathians)': {
                'lon': 24.5003, 'lat': 48.1603,
                'expected_meters': (1800, 2100),
                'expected_level': 12
            },
            'Ai-Petri (Crimea)': {
                'lon': 34.0587, 'lat': 44.4508,
                'expected_meters': (1000, 1300),
                'expected_level': (9, 10)
            },
            'Kyiv': {
                'lon': 30.5234, 'lat': 50.4501,
                'expected_meters': (150, 200),
                'expected_level': 3
            },
            'Odesa': {
                'lon': 30.7233, 'lat': 46.4825,
                'expected_meters': (0, 80),
                'expected_level': (0, 1)
            },
            'Kharkiv': {
                'lon': 36.2304, 'lat': 49.9935,
                'expected_meters': (100, 200),
                'expected_level': (2, 3)
            },
            'Dnipro': {
                'lon': 35.0462, 'lat': 48.4647,
                'expected_meters': (50, 150),
                'expected_level': (1, 2)
            },
        }

        results = {}

        for name, data in validation_points.items():
            elev_meters = self.srtm.get_elevation_at(data['lon'], data['lat'])
            level = self._quantize_elevation(elev_meters)

            expected_level = data['expected_level']
            if isinstance(expected_level, tuple):
                level_ok = expected_level[0] <= level <= expected_level[1]
            else:
                level_ok = level == expected_level

            expected_meters = data['expected_meters']
            meters_ok = expected_meters[0] <= elev_meters <= expected_meters[1]

            results[name] = {
                'lon': data['lon'],
                'lat': data['lat'],
                'meters': elev_meters,
                'level': level,
                'expected_level': expected_level,
                'expected_meters': expected_meters,
                'level_ok': level_ok,
                'meters_ok': meters_ok,
                'ok': level_ok and meters_ok
            }

        return results


def main():
    """Test the hex elevation mapper."""
    import yaml

    # Load config
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid_width = config['grid']['width']
    grid_height = config['grid']['height']

    print("=" * 60)
    print("HEX ELEVATION MAPPER TEST")
    print("=" * 60)

    # Create fetcher and mapper
    fetcher = SRTMElevationFetcher(bounds)
    fetcher.fetch()

    mapper = HexElevationMapper(fetcher, grid_width, grid_height, bounds)

    # Get elevations
    print("\nMapping hex elevations...")
    elevations = mapper.get_hex_elevations()

    # Stats
    stats = mapper.get_elevation_stats()
    print(f"\nElevation Statistics:")
    print(f"  Total hexes: {stats['total_hexes']}")
    print(f"  Raw elevation range: {stats['raw_min']:.1f} to {stats['raw_max']:.1f} m")
    print(f"  Raw elevation mean: {stats['raw_mean']:.1f} m")
    print(f"  NoData hexes: {stats['nodata_count']}")
    print(f"\n  Level distribution:")
    for level, count in stats['level_distribution'].items():
        pct = count / stats['total_hexes'] * 100
        bar = '█' * int(pct / 2)
        print(f"    Level {level:3d}: {count:5d} ({pct:5.1f}%) {bar}")

    # Validation
    print(f"\nValidation Points:")
    validation = mapper.validate_known_points()
    for name, data in validation.items():
        status = "✓" if data['ok'] else "✗"
        print(f"  {status} {name}:")
        print(f"      Elevation: {data['meters']:.1f} m (expected {data['expected_meters'][0]}-{data['expected_meters'][1]} m)")
        print(f"      Level: {data['level']} (expected {data['expected_level']})")


if __name__ == "__main__":
    main()
