#!/usr/bin/env python3
"""
River Mapper for Ukraine Map.

Maps Natural Earth river data to hex grid for Humankind map.

River Classification:
- Regular rivers: Normal river flow, mapped with river texture
- Reservoirs: Artificial lakes (dams), mapped as Lake terrain
- Porohy (rapids): Areas where one bank is significantly steeper than
  the other, indicating rapids or gorges - mapped as Lake terrain
"""

import geopandas as gpd
from shapely.geometry import box, Point, LineString
from shapely.ops import unary_union
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Set, Optional, List
from dataclasses import dataclass


# Major Ukrainian rivers to include (by importance)
UKRAINE_RIVERS = [
    'Dnieper',      # Main river - Dnipro
    'Dnipro',       # Alternative name
    'Dniester',     # Western Ukraine
    'Southern Bug', # Southern Ukraine
    'Donets',       # Eastern Ukraine - Siverskyi Donets
    'Desna',        # Northern tributary of Dnipro
    'Pripyat',      # Northern Ukraine (Chornobyl area)
    'Bug',          # Western Bug (border with Poland)
    'Prut',         # SW Ukraine (border with Romania/Moldova)
    'Don',          # Eastern edge
    'Danube',       # SW corner (delta)
]


# Major Dnipro reservoirs (bounding boxes: min_lon, min_lat, max_lon, max_lat)
# These are mapped as Lake terrain, not regular rivers
DNIPRO_RESERVOIRS = {
    'Kyiv': (30.0, 50.35, 31.2, 51.4),           # Kyiv Reservoir
    'Kaniv': (31.2, 49.55, 31.7, 50.35),         # Kaniv Reservoir
    'Kremenchuk': (32.0, 48.85, 33.8, 49.55),    # Kremenchuk Reservoir
    'Kamenskoye': (34.0, 48.35, 35.0, 48.85),    # Dniprodzerzhinsk Reservoir
    'Dnipro': (34.8, 47.65, 35.3, 48.35),        # Zaporizhzhia Reservoir
    'Kakhovka': (33.5, 46.65, 35.2, 47.65),      # Kakhovka Reservoir (pre-2023)
}

# Dnipro river names in various data sources
DNIPRO_NAMES = [
    # English variants
    'Dnieper', 'Dnipro', 'Dnepr', 'Dniepr',
    # Ukrainian
    'Дніпро',
    # Russian
    'Днепр',
    # Belarusian
    'Дняпро',
    # Mixed/bilingual
    'Дняпро / Дніпро', 'Днепр / Дніпро',
]

# Major natural lakes in Ukraine (bounding boxes: min_lon, min_lat, max_lon, max_lat)
# These are the 5 biggest lakes, mapped as Lake terrain
MAJOR_LAKES = {
    # Lake Sasyk (Kunduk) - largest lake in Ukraine proper, ~200 km²
    # Near Odesa, brackish lagoon
    'Sasyk': (29.75, 45.85, 30.0, 46.1),

    # Lake Yalpuh - second largest, ~150 km²
    # Near Izmail, in Odesa Oblast, connected to Danube
    'Yalpuh': (28.55, 45.25, 28.85, 45.55),

    # Lake Kahul - ~90 km²
    # Near Moldova border, Odesa Oblast
    'Kahul': (28.2, 45.35, 28.55, 45.65),

    # Lake Katlabuh - ~68 km²
    # Between Yalpuh and Kahul, Odesa Oblast
    'Katlabuh': (28.4, 45.55, 28.7, 45.85),

    # Lake Svitjaz - largest natural lake in Polesia, ~27 km²
    # Volyn Oblast, part of Shatsk Lakes
    'Svitjaz': (23.8, 51.45, 23.95, 51.55),
}

# Threshold for detecting porohy (rapids) - elevation difference in meters
# between opposing banks. If one bank is this much higher than the other,
# it's considered a rapid/gorge area
POROHY_ELEVATION_THRESHOLD = 30  # meters


@dataclass
class RiverClassification:
    """Classification of river hexes into categories."""
    regular_rivers: Set[Tuple[int, int]]   # Normal river - use river texture
    lakes: Set[Tuple[int, int]]            # Natural lakes + reservoirs - use Lake terrain
    dnipro: Set[Tuple[int, int]]           # Dnipro river - consecutive lake chain


class RiverMapper:
    """Maps rivers to hex grid."""

    def __init__(self, bounds: dict, grid_width: int, grid_height: int):
        """
        Initialize river mapper.

        Args:
            bounds: {min_lon, max_lon, min_lat, max_lat}
            grid_width: Number of hex columns
            grid_height: Number of hex rows
        """
        self.bounds = bounds
        self.width = grid_width
        self.height = grid_height

        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']

        # Load river data
        self.rivers_gdf = self._load_rivers()

    def _load_rivers(self) -> gpd.GeoDataFrame:
        """Load and filter rivers for Ukraine region."""
        # Try OSM data first (much more detailed), fall back to Natural Earth
        osm_path = Path(__file__).parent / "data" / "osm_waterways" / "gis_osm_waterways_free_1.shp"
        ne_path = Path(__file__).parent / "data" / "rivers" / "ne_10m_rivers_lake_centerlines.shp"

        if osm_path.exists():
            rivers = gpd.read_file(osm_path)
            print(f"  Loaded {len(rivers)} OSM waterway features")

            # Filter to relevant waterway types
            # fclass values: river (21k), stream (139k), canal (9k), drain (65k)
            # At ~15-20km per hex, only include major named rivers
            if 'fclass' in rivers.columns:
                rivers = rivers[rivers['fclass'] == 'river']

                # Filter to major Ukrainian rivers by name (Ukrainian/English)
                major_river_patterns = [
                    'Дніпро', 'Дністер', 'Південний Буг', 'Сіверський Донець',
                    'Десна', 'Прип\'ять', 'Буг', 'Прут', 'Дунай', 'Дон',
                    'Інгул', 'Ворскла', 'Псел', 'Сула', 'Рось', 'Тетерів',
                    'Случ', 'Горинь', 'Стир', 'Збруч', 'Серет', 'Оскіл',
                    'Сейм', 'Інгулець', 'Самара', 'Оріль', 'Кальміус',
                    # English names as fallback
                    'Dnieper', 'Dniester', 'Southern Bug', 'Donets',
                ]

                # Keep rivers matching any of the major river names
                mask = rivers['name'].str.contains('|'.join(major_river_patterns),
                                                    case=False, na=False, regex=True)
                rivers = rivers[mask]
                print(f"  After filtering (major rivers): {len(rivers)} features")

            # Filter to map bounding box with margin
            ukraine_box = box(
                self.min_lon - 0.5,
                self.min_lat - 0.5,
                self.max_lon + 0.5,
                self.max_lat + 0.5
            )
            rivers = rivers[rivers.intersects(ukraine_box)]
            rivers = rivers.clip(ukraine_box)
            print(f"  After clipping to bounds: {len(rivers)} features")

        elif ne_path.exists():
            print("  Warning: OSM data not found, falling back to Natural Earth")
            rivers = gpd.read_file(ne_path)

            # Filter to Ukraine bounding box with some margin
            ukraine_box = box(
                self.min_lon - 1,
                self.min_lat - 1,
                self.max_lon + 1,
                self.max_lat + 1
            )
            rivers = rivers[rivers.intersects(ukraine_box)]
            rivers = rivers.clip(ukraine_box)
            print(f"  Loaded {len(rivers)} Natural Earth river segments")

        else:
            print(f"  Warning: No river data found")
            return gpd.GeoDataFrame()

        return rivers

    def _pixel_to_geo(self, col: int, row: int) -> Tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates."""
        lon = self.min_lon + (col / self.width) * (self.max_lon - self.min_lon)
        lat = self.max_lat - (row / self.height) * (self.max_lat - self.min_lat)
        return lon, lat

    def _geo_to_pixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        col = int((lon - self.min_lon) / (self.max_lon - self.min_lon) * self.width)
        row = int((self.max_lat - lat) / (self.max_lat - self.min_lat) * self.height)
        return col, row

    def get_river_hexes(self, buffer_km: float = 5.0) -> Set[Tuple[int, int]]:
        """
        Get set of hex coordinates that contain rivers.

        Args:
            buffer_km: Buffer around rivers in km (to catch hexes near rivers)

        Returns:
            Set of (col, row) tuples for hexes containing rivers
        """
        if self.rivers_gdf.empty:
            return set()

        print(f"  Mapping rivers to hex grid ({self.width}x{self.height})...")

        river_hexes = set()

        # Convert buffer from km to degrees (approximate)
        # 1 degree lat ≈ 111 km, 1 degree lon ≈ 111 * cos(lat) km
        avg_lat = (self.min_lat + self.max_lat) / 2
        buffer_deg = buffer_km / 111.0  # Simplified, good enough for this purpose

        # Buffer the rivers slightly to catch adjacent hexes
        buffered_rivers = self.rivers_gdf.geometry.buffer(buffer_deg / 2)
        all_rivers = unary_union(buffered_rivers)

        # Check each hex
        for row in range(self.height):
            for col in range(self.width):
                lon, lat = self._pixel_to_geo(col, row)
                point = Point(lon, lat)

                # Check if hex center is near a river
                if all_rivers.contains(point) or all_rivers.distance(point) < buffer_deg / 2:
                    river_hexes.add((col, row))

        print(f"  Found {len(river_hexes)} river hexes")
        return river_hexes

    def get_river_hexes_fast(self) -> Set[Tuple[int, int]]:
        """
        Fast method to get river hexes by rasterizing river lines.

        Returns:
            Set of (col, row) tuples for hexes containing rivers
        """
        if self.rivers_gdf.empty:
            return set()

        print(f"  Mapping rivers to hex grid (fast method)...")

        river_hexes = set()

        # Calculate hex size in degrees for proper sampling
        # We need to sample at least once per hex to avoid gaps
        hex_width_deg = (self.max_lon - self.min_lon) / self.width
        hex_height_deg = (self.max_lat - self.min_lat) / self.height
        sample_interval = min(hex_width_deg, hex_height_deg) * 0.5  # Sample twice per hex

        # For each river segment, walk along it and mark hexes
        for idx, river in self.rivers_gdf.iterrows():
            geom = river.geometry

            if geom is None or geom.is_empty:
                continue

            # Handle both LineString and MultiLineString
            if geom.geom_type == 'LineString':
                lines = [geom]
            elif geom.geom_type == 'MultiLineString':
                lines = list(geom.geoms)
            else:
                continue

            for line in lines:
                # Sample points along the line
                length = line.length
                if length == 0:
                    continue

                # Sample at hex resolution to ensure no gaps
                num_samples = max(2, int(length / sample_interval) + 1)
                prev_col, prev_row = None, None

                for i in range(num_samples + 1):
                    fraction = i / num_samples
                    point = line.interpolate(fraction, normalized=True)
                    col, row = self._geo_to_pixel(point.x, point.y)

                    # Check bounds
                    if 0 <= col < self.width and 0 <= row < self.height:
                        river_hexes.add((col, row))

                        # Fill gaps between samples using Bresenham-like interpolation
                        if prev_col is not None and prev_row is not None:
                            if abs(col - prev_col) > 1 or abs(row - prev_row) > 1:
                                # There's a gap, fill it
                                steps = max(abs(col - prev_col), abs(row - prev_row))
                                for step in range(1, steps):
                                    interp_col = prev_col + (col - prev_col) * step // steps
                                    interp_row = prev_row + (row - prev_row) * step // steps
                                    if 0 <= interp_col < self.width and 0 <= interp_row < self.height:
                                        river_hexes.add((interp_col, interp_row))

                        prev_col, prev_row = col, row

        print(f"  Found {len(river_hexes)} river hexes")

        # Connect nearby river segments (fill gaps up to 2 hexes)
        river_hexes = self._connect_nearby_river_hexes(river_hexes)

        return river_hexes

    def _connect_nearby_river_hexes(
        self,
        river_hexes: Set[Tuple[int, int]],
        max_gap: int = 3
    ) -> Set[Tuple[int, int]]:
        """
        Connect nearby river hexes by filling small gaps and removing tiny isolated components.

        Finds river endpoints that are close but not adjacent, and adds
        intermediate hexes to connect them. Also removes tiny isolated
        components (1-2 hexes) that look like noise.

        Args:
            river_hexes: Set of river hex coordinates
            max_gap: Maximum gap distance to fill (in hexes)

        Returns:
            Set of river hexes with gaps filled and noise removed
        """
        if len(river_hexes) < 2:
            return river_hexes

        result = set(river_hexes)

        # First: remove tiny isolated components (1-2 hexes)
        result = self._remove_tiny_components(result, min_size=3)

        # Find endpoints (hexes with only 0-1 river neighbors)
        endpoints = []
        for col, row in result:
            neighbors = self._get_hex_neighbors(col, row)
            river_neighbors = sum(1 for nc, nr, _ in neighbors if (nc, nr) in result)
            if river_neighbors <= 1:
                endpoints.append((col, row))

        # Try to connect nearby endpoints (multiple passes)
        for _ in range(3):  # Multiple passes to connect chains
            connected_pairs = set()
            added_this_pass = 0

            for i, ep1 in enumerate(endpoints):
                for ep2 in endpoints[i+1:]:
                    # Skip if already connected
                    if (ep1, ep2) in connected_pairs or (ep2, ep1) in connected_pairs:
                        continue

                    # Calculate Manhattan-like distance
                    dist = abs(ep1[0] - ep2[0]) + abs(ep1[1] - ep2[1])
                    if 2 <= dist <= max_gap * 2:  # Within connection range
                        # Find path between them
                        path = self._find_short_path(ep1, ep2, max_gap + 1)
                        if path:
                            for h in path:
                                result.add(h)
                                added_this_pass += 1
                            connected_pairs.add((ep1, ep2))

            if added_this_pass == 0:
                break

            # Recalculate endpoints for next pass
            endpoints = []
            for col, row in result:
                neighbors = self._get_hex_neighbors(col, row)
                river_neighbors = sum(1 for nc, nr, _ in neighbors if (nc, nr) in result)
                if river_neighbors <= 1:
                    endpoints.append((col, row))

        if len(result) != len(river_hexes):
            diff = len(result) - len(river_hexes)
            if diff > 0:
                print(f"  Connected river gaps: added {diff} hexes")
            else:
                print(f"  Removed tiny river components: {-diff} hexes")

        return result

    def _remove_tiny_components(
        self,
        hexes: Set[Tuple[int, int]],
        min_size: int = 3
    ) -> Set[Tuple[int, int]]:
        """Remove connected components smaller than min_size."""
        from collections import deque

        remaining = set(hexes)
        valid_hexes = set()

        while remaining:
            start = remaining.pop()
            component = {start}
            queue = deque([start])

            while queue:
                curr = queue.popleft()
                for nc, nr, _ in self._get_hex_neighbors(curr[0], curr[1]):
                    if (nc, nr) in remaining:
                        remaining.remove((nc, nr))
                        component.add((nc, nr))
                        queue.append((nc, nr))

            # Keep only large enough components
            if len(component) >= min_size:
                valid_hexes.update(component)

        return valid_hexes

    def _find_short_path(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        max_length: int
    ) -> List[Tuple[int, int]]:
        """Find short path between two hexes using BFS, limited by max_length."""
        from collections import deque

        if start == end:
            return []

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            if len(path) > max_length:
                continue

            for nc, nr, _ in self._get_hex_neighbors(current[0], current[1]):
                if (nc, nr) == end:
                    return path + [end]

                if (nc, nr) not in visited and 0 <= nc < self.width and 0 <= nr < self.height:
                    visited.add((nc, nr))
                    queue.append(((nc, nr), path + [(nc, nr)]))

        return []  # No short path found

    def _is_in_reservoir(self, lon: float, lat: float) -> bool:
        """Check if a coordinate is within a known reservoir."""
        for name, (min_lon, min_lat, max_lon, max_lat) in DNIPRO_RESERVOIRS.items():
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                return True
        return False

    def _is_in_lake(self, lon: float, lat: float) -> bool:
        """Check if a coordinate is within a known major lake."""
        for name, (min_lon, min_lat, max_lon, max_lat) in MAJOR_LAKES.items():
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                return True
        return False

    def _get_reservoir_hexes(self, river_hexes: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        Identify river hexes that are within reservoir areas.

        Args:
            river_hexes: Set of all river hex coordinates

        Returns:
            Set of (col, row) tuples for reservoir hexes
        """
        reservoir_hexes = set()

        for col, row in river_hexes:
            lon, lat = self._pixel_to_geo(col, row)
            if self._is_in_reservoir(lon, lat):
                reservoir_hexes.add((col, row))

        return reservoir_hexes

    def _get_dnipro_hexes(self) -> Set[Tuple[int, int]]:
        """
        Get all hexes that are part of the Dnipro river.

        The entire Dnipro is treated as a lake for gameplay purposes.

        Returns:
            Set of (col, row) tuples for Dnipro hexes
        """
        if self.rivers_gdf.empty or 'name' not in self.rivers_gdf.columns:
            return set()

        dnipro_hexes = set()

        # Filter to Dnipro river segments
        dnipro_rivers = self.rivers_gdf[
            self.rivers_gdf['name'].isin(DNIPRO_NAMES)
        ]

        if dnipro_rivers.empty:
            print("  Warning: No Dnipro river segments found in data")
            return set()

        print(f"  Found {len(dnipro_rivers)} Dnipro river segments")

        # Calculate hex size in degrees for proper sampling
        hex_width_deg = (self.max_lon - self.min_lon) / self.width
        hex_height_deg = (self.max_lat - self.min_lat) / self.height
        sample_interval = min(hex_width_deg, hex_height_deg) * 0.5

        # Trace each Dnipro segment
        for idx, river in dnipro_rivers.iterrows():
            geom = river.geometry
            if geom is None or geom.is_empty:
                continue

            if geom.geom_type == 'LineString':
                lines = [geom]
            elif geom.geom_type == 'MultiLineString':
                lines = list(geom.geoms)
            else:
                continue

            for line in lines:
                length = line.length
                if length == 0:
                    continue

                num_samples = max(2, int(length / sample_interval) + 1)
                prev_col, prev_row = None, None

                for i in range(num_samples + 1):
                    fraction = i / num_samples
                    point = line.interpolate(fraction, normalized=True)
                    col, row = self._geo_to_pixel(point.x, point.y)

                    if 0 <= col < self.width and 0 <= row < self.height:
                        dnipro_hexes.add((col, row))

                        # Fill gaps
                        if prev_col is not None and prev_row is not None:
                            if abs(col - prev_col) > 1 or abs(row - prev_row) > 1:
                                steps = max(abs(col - prev_col), abs(row - prev_row))
                                for step in range(1, steps):
                                    interp_col = prev_col + (col - prev_col) * step // steps
                                    interp_row = prev_row + (row - prev_row) * step // steps
                                    if 0 <= interp_col < self.width and 0 <= interp_row < self.height:
                                        dnipro_hexes.add((interp_col, interp_row))

                        prev_col, prev_row = col, row

        print(f"  Total Dnipro hexes: {len(dnipro_hexes)}")
        return dnipro_hexes

    def get_dnipro_chain(
        self,
        dnipro_hexes: Set[Tuple[int, int]],
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> List[Tuple[int, int]]:
        """
        Order Dnipro hexes as a FULLY CONTIGUOUS chain from north to south.

        Every hex in the chain is adjacent to the next, ensuring boats can navigate.
        Fills gaps where river data is incomplete and extends to the sea.

        Args:
            dnipro_hexes: Set of Dnipro hex coordinates
            land_mask: Optional dict marking which hexes are land

        Returns:
            List of (col, row) tuples ordered from north to south, fully contiguous
        """
        if not dnipro_hexes:
            return []

        # Filter to land hexes
        if land_mask:
            hexes = {h for h in dnipro_hexes if land_mask.get(h, False)}
        else:
            hexes = set(dnipro_hexes)

        if not hexes:
            return []

        # Sort by row (north to south) then by column
        sorted_hexes = sorted(hexes, key=lambda h: (h[1], h[0]))

        # Build the chain by always moving to the nearest southward hex
        chain = []
        remaining = set(hexes)
        current = sorted_hexes[0]  # Start from northernmost
        chain.append(current)
        remaining.discard(current)

        while remaining:
            # Find the nearest remaining hex (prefer southward)
            best_next = None
            best_distance = float('inf')

            for candidate in remaining:
                # Calculate distance with preference for southward movement
                dx = abs(candidate[0] - current[0])
                dy = candidate[1] - current[1]  # Positive = southward
                # Penalize northward movement, reward southward
                distance = dx + abs(dy) - (dy * 0.1 if dy > 0 else 0)
                if distance < best_distance:
                    best_distance = distance
                    best_next = candidate

            if best_next is None:
                break

            # Fill gap between current and best_next if not adjacent
            gap_hexes = self._fill_contiguous_gap(current, best_next, land_mask, set(chain))
            chain.extend(gap_hexes)
            chain.append(best_next)
            remaining.discard(best_next)
            current = best_next

        # Extend to sea: find path from southernmost hex to nearest ocean
        if chain and land_mask:
            chain = self._extend_to_sea(chain, land_mask)

        # Final pass: ensure chain is fully contiguous
        chain = self._ensure_contiguous(chain, land_mask)

        print(f"  Dnipro chain: {len(chain)} hexes (from row {chain[0][1]} to row {chain[-1][1]})")
        return chain

    def _fill_contiguous_gap(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        land_mask: Optional[Dict[Tuple[int, int], bool]],
        existing: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Fill gap between two hexes with a contiguous path using BFS."""
        # Check if already adjacent
        neighbors = self._get_hex_neighbors(start[0], start[1])
        if any((nc, nr) == end for nc, nr, _ in neighbors):
            return []  # Already adjacent

        # BFS to find shortest path - consider ALL land hexes
        from collections import deque
        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            for nc, nr, _ in self._get_hex_neighbors(current[0], current[1]):
                if (nc, nr) == end:
                    # Found path - return intermediate hexes (exclude start and end)
                    return path[1:]

                if (nc, nr) not in visited and 0 <= nc < self.width and 0 <= nr < self.height:
                    is_land = land_mask is None or land_mask.get((nc, nr), False)
                    if is_land:  # Allow any land hex, even if in existing
                        visited.add((nc, nr))
                        queue.append(((nc, nr), path + [(nc, nr)]))

        # Second pass: allow existing chain hexes as path (for connecting components)
        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            for nc, nr, _ in self._get_hex_neighbors(current[0], current[1]):
                if (nc, nr) == end:
                    return path[1:]

                if (nc, nr) not in visited and 0 <= nc < self.width and 0 <= nr < self.height:
                    is_land = land_mask is None or land_mask.get((nc, nr), False)
                    if is_land or (nc, nr) in existing:
                        visited.add((nc, nr))
                        queue.append(((nc, nr), path + [(nc, nr)]))

        # Fallback: direct interpolation
        return self._interpolate_gap(start, end, land_mask)

    def _extend_to_sea(
        self,
        chain: List[Tuple[int, int]],
        land_mask: Dict[Tuple[int, int], bool]
    ) -> List[Tuple[int, int]]:
        """Extend chain southward until it reaches ocean."""
        if not chain:
            return chain

        current = chain[-1]
        extended = list(chain)
        extended_set = set(extended)
        max_extensions = 30  # Safety limit

        for iteration in range(max_extensions):
            # Check if current hex is adjacent to ocean
            neighbors = self._get_hex_neighbors(current[0], current[1])
            ocean_neighbor = None
            best_candidates = []

            for nc, nr, _ in neighbors:
                if 0 <= nc < self.width and 0 <= nr < self.height:
                    is_land = land_mask.get((nc, nr), False)
                    if not is_land:
                        ocean_neighbor = (nc, nr)
                    elif (nc, nr) not in extended_set:
                        # Score: prefer south (higher row), slight preference for center
                        score = nr * 10 - abs(nc - current[0])
                        best_candidates.append(((nc, nr), score))

            if ocean_neighbor:
                # We're at the coast - done
                print(f"  Dnipro extends to sea at row {current[1]}")
                break

            if best_candidates:
                # Pick best candidate (highest score = most southward)
                best_candidates.sort(key=lambda x: x[1], reverse=True)
                best_next = best_candidates[0][0]
                extended.append(best_next)
                extended_set.add(best_next)
                current = best_next
            else:
                # Try BFS to find path to any coastal hex
                coastal_hex = self._find_nearest_coastal_hex(current, land_mask, extended_set)
                if coastal_hex:
                    # Find path to coastal hex
                    path = self._bfs_path(current, coastal_hex, land_mask)
                    if path:
                        for h in path[1:]:  # Skip current
                            if h not in extended_set:
                                extended.append(h)
                                extended_set.add(h)
                        current = extended[-1]
                        continue
                # Can't go further
                print(f"  Dnipro stopped at row {current[1]} (no path to sea)")
                break

        return extended

    def _find_nearest_coastal_hex(
        self,
        start: Tuple[int, int],
        land_mask: Dict[Tuple[int, int], bool],
        exclude: Set[Tuple[int, int]]
    ) -> Optional[Tuple[int, int]]:
        """Find nearest land hex that is adjacent to ocean."""
        from collections import deque
        queue = deque([start])
        visited = {start}

        while queue:
            current = queue.popleft()
            col, row = current

            # Check if this hex is coastal (land adjacent to ocean)
            if land_mask.get(current, False):
                for nc, nr, _ in self._get_hex_neighbors(col, row):
                    if 0 <= nc < self.width and 0 <= nr < self.height:
                        if not land_mask.get((nc, nr), False):
                            return current  # Found coastal hex

            # Explore neighbors
            for nc, nr, _ in self._get_hex_neighbors(col, row):
                if (nc, nr) not in visited and 0 <= nc < self.width and 0 <= nr < self.height:
                    if land_mask.get((nc, nr), False):
                        visited.add((nc, nr))
                        queue.append((nc, nr))

        return None

    def _bfs_path(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        land_mask: Dict[Tuple[int, int], bool]
    ) -> List[Tuple[int, int]]:
        """Find shortest path between two hexes on land."""
        from collections import deque
        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            current, path = queue.popleft()

            if current == end:
                return path

            for nc, nr, _ in self._get_hex_neighbors(current[0], current[1]):
                if (nc, nr) not in visited and 0 <= nc < self.width and 0 <= nr < self.height:
                    if land_mask.get((nc, nr), False):
                        visited.add((nc, nr))
                        queue.append(((nc, nr), path + [(nc, nr)]))

        return []

    def _ensure_contiguous(
        self,
        chain: List[Tuple[int, int]],
        land_mask: Optional[Dict[Tuple[int, int], bool]]
    ) -> List[Tuple[int, int]]:
        """Ensure every hex in chain is adjacent to the next."""
        if len(chain) <= 1:
            return chain

        result = [chain[0]]
        chain_set = set(chain)

        for i in range(1, len(chain)):
            prev = result[-1]
            curr = chain[i]

            # Check if adjacent
            neighbors = self._get_hex_neighbors(prev[0], prev[1])
            if any((nc, nr) == curr for nc, nr, _ in neighbors):
                result.append(curr)
            else:
                # Need to fill gap
                gap = self._fill_contiguous_gap(prev, curr, land_mask, chain_set)
                result.extend(gap)
                result.append(curr)

        return result

    def _interpolate_gap(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> List[Tuple[int, int]]:
        """Interpolate hexes between two points to fill gaps."""
        gap_hexes = []
        sc, sr = start
        ec, er = end

        # Bresenham-like interpolation
        steps = max(abs(ec - sc), abs(er - sr))
        if steps <= 1:
            return gap_hexes

        for step in range(1, steps):
            col = sc + (ec - sc) * step // steps
            row = sr + (er - sr) * step // steps
            if land_mask is None or land_mask.get((col, row), False):
                gap_hexes.append((col, row))

        return gap_hexes

    def get_dnipro_bank_elevations(
        self,
        dnipro_hexes: Set[Tuple[int, int]],
        hex_elevations: Dict[Tuple[int, int], int],
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> Dict[Tuple[int, int], int]:
        """
        Calculate the target elevation for each Dnipro hex.

        The Dnipro should be one elevation level lower than the minimum
        of its two banks.

        Args:
            dnipro_hexes: Set of Dnipro hex coordinates
            hex_elevations: Dict mapping (col, row) -> elevation level (game units -3 to 12)
            land_mask: Optional dict marking which hexes are land

        Returns:
            Dict mapping (col, row) -> target elevation level
        """
        dnipro_elevations = {}

        for col, row in dnipro_hexes:
            # Get neighbors on each bank
            eastern, western = self._get_hex_neighbors_by_side(col, row)

            # Collect bank elevations (non-river land neighbors)
            bank_levels = []

            for neighbors in [eastern, western]:
                for nc, nr in neighbors:
                    if (nc, nr) not in dnipro_hexes:  # Not part of Dnipro
                        if land_mask is None or land_mask.get((nc, nr), False):
                            level = hex_elevations.get((nc, nr), -3)
                            if level >= 0:  # Valid land elevation
                                bank_levels.append(level)

            if bank_levels:
                # Find minimum bank elevation level
                min_bank_level = min(bank_levels)

                # Dnipro is one level lower than the bank
                dnipro_level = max(-1, min_bank_level - 1)
                dnipro_elevations[(col, row)] = dnipro_level
            else:
                # Default to shallow water level if no banks found
                dnipro_elevations[(col, row)] = -1

        return dnipro_elevations

    def _get_lake_hexes(
        self,
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> Set[Tuple[int, int]]:
        """
        Get all hexes that fall within major lake bounds.

        Unlike reservoirs (which are detected along river lines), lakes are
        detected by scanning all hexes within their bounding boxes.

        Args:
            land_mask: Optional dict marking which hexes are land

        Returns:
            Set of (col, row) tuples for lake hexes
        """
        lake_hexes = set()

        for name, (min_lon, min_lat, max_lon, max_lat) in MAJOR_LAKES.items():
            lake_count = 0
            for row in range(self.height):
                for col in range(self.width):
                    # Only consider land hexes if mask provided
                    if land_mask and not land_mask.get((col, row), False):
                        continue

                    lon, lat = self._pixel_to_geo(col, row)
                    if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                        lake_hexes.add((col, row))
                        lake_count += 1

            if lake_count > 0:
                print(f"    Lake {name}: {lake_count} hexes")

        return lake_hexes

    def _get_hex_neighbors_by_side(
        self, col: int, row: int
    ) -> Tuple[list, list]:
        """
        Get eastern (left bank) and western (right bank) neighbors of a hex.

        For rivers flowing generally south (like Dnipro), the left bank
        is on the east side and right bank on the west side.

        Args:
            col, row: Hex coordinates

        Returns:
            Tuple of (eastern_neighbors, western_neighbors) - each is list of (col, row)
        """
        eastern = []
        western = []

        if row % 2 == 0:  # Even row
            # Eastern neighbors: NE, E, SE
            eastern_offsets = [(0, -1), (1, 0), (0, 1)]
            # Western neighbors: NW, W, SW
            western_offsets = [(-1, -1), (-1, 0), (-1, 1)]
        else:  # Odd row
            # Eastern neighbors: NE, E, SE
            eastern_offsets = [(1, -1), (1, 0), (1, 1)]
            # Western neighbors: NW, W, SW
            western_offsets = [(0, -1), (-1, 0), (0, 1)]

        for dc, dr in eastern_offsets:
            nc, nr = col + dc, row + dr
            if 0 <= nc < self.width and 0 <= nr < self.height:
                eastern.append((nc, nr))

        for dc, dr in western_offsets:
            nc, nr = col + dc, row + dr
            if 0 <= nc < self.width and 0 <= nr < self.height:
                western.append((nc, nr))

        return eastern, western

    def _detect_porohy(
        self,
        river_hexes: Set[Tuple[int, int]],
        elevation_grid: np.ndarray,
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> Set[Tuple[int, int]]:
        """
        Detect porohy (rapids) where one bank is significantly steeper.

        A porohy is detected when the elevation difference between
        the east and west banks exceeds the threshold.

        Args:
            river_hexes: Set of river hex coordinates
            elevation_grid: 2D array of elevation in meters (height x width)
            land_mask: Optional dict marking which hexes are land

        Returns:
            Set of (col, row) tuples for porohy hexes
        """
        porohy_hexes = set()

        for col, row in river_hexes:
            # Skip if not on land (we only care about rivers on land)
            if land_mask and not land_mask.get((col, row), False):
                continue

            # Get neighboring land hexes on each side
            eastern, western = self._get_hex_neighbors_by_side(col, row)

            # Get elevations for land neighbors on each side
            east_elevations = []
            west_elevations = []

            for nc, nr in eastern:
                if (nc, nr) not in river_hexes:  # Only consider non-river hexes
                    if land_mask is None or land_mask.get((nc, nr), False):
                        elev = elevation_grid[nr, nc]
                        if elev > -9000:  # Valid elevation
                            east_elevations.append(elev)

            for nc, nr in western:
                if (nc, nr) not in river_hexes:
                    if land_mask is None or land_mask.get((nc, nr), False):
                        elev = elevation_grid[nr, nc]
                        if elev > -9000:
                            west_elevations.append(elev)

            # Check for significant elevation difference
            if east_elevations and west_elevations:
                east_avg = sum(east_elevations) / len(east_elevations)
                west_avg = sum(west_elevations) / len(west_elevations)
                diff = abs(east_avg - west_avg)

                if diff >= POROHY_ELEVATION_THRESHOLD:
                    porohy_hexes.add((col, row))

        return porohy_hexes

    def classify_rivers(
        self,
        elevation_grid: Optional[np.ndarray] = None,
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> RiverClassification:
        """
        Classify river hexes into categories: regular rivers, lakes, and Dnipro.

        Lakes include both natural lakes (MAJOR_LAKES) and reservoirs (DNIPRO_RESERVOIRS).
        Regular rivers are everything else.
        Dnipro is rendered as a consecutive chain of lakes.

        Args:
            elevation_grid: 2D array of elevation in meters (height x width).
            land_mask: Optional dict marking which hexes are land

        Returns:
            RiverClassification with categorized river/water hexes
        """
        # Get all river hexes
        all_river_hexes = self.get_river_hexes_fast()

        # Filter to land only if mask provided
        if land_mask:
            all_river_hexes = {h for h in all_river_hexes if land_mask.get(h, False)}

        # Identify Dnipro hexes (rendered as consecutive lake chain)
        print("  Detecting Dnipro river...")
        dnipro_hexes_raw = self._get_dnipro_hexes()
        if land_mask:
            dnipro_hexes_raw = {h for h in dnipro_hexes_raw if land_mask.get(h, False)}
        print(f"  Dnipro hexes (on land): {len(dnipro_hexes_raw)}")

        # Create consecutive chain from north to south
        dnipro_chain = self.get_dnipro_chain(dnipro_hexes_raw, land_mask)
        # Convert chain back to set for classification, but store chain for later use
        dnipro_hexes = set(dnipro_chain)
        self.dnipro_chain = dnipro_chain  # Store for later use

        # Identify natural lakes
        print("  Detecting major natural lakes...")
        natural_lake_hexes = self._get_lake_hexes(land_mask)
        print(f"  Natural lake hexes: {len(natural_lake_hexes)}")

        # Identify reservoirs (non-Dnipro) - treated as lakes
        print("  Detecting reservoirs...")
        reservoir_hexes = self._get_reservoir_hexes(all_river_hexes)
        reservoir_hexes = reservoir_hexes - dnipro_hexes  # Exclude Dnipro
        print(f"  Reservoir hexes (non-Dnipro): {len(reservoir_hexes)}")

        # Combine natural lakes and reservoirs
        lake_hexes = natural_lake_hexes | reservoir_hexes
        # Exclude Dnipro from lakes (Dnipro has its own handling)
        lake_hexes = lake_hexes - dnipro_hexes
        print(f"  Total lake hexes (lakes + reservoirs): {len(lake_hexes)}")

        # Regular rivers are ALL rivers except Dnipro and lakes/reservoirs
        regular_rivers = all_river_hexes - lake_hexes - dnipro_hexes
        print(f"  Regular river hexes: {len(regular_rivers)}")

        return RiverClassification(
            regular_rivers=regular_rivers,
            lakes=lake_hexes,
            dnipro=dnipro_hexes
        )

    def _get_hex_neighbors(self, col: int, row: int) -> List[Tuple[int, int, int]]:
        """
        Get all 6 neighbors of a hex with their edge directions.

        Hex edge directions (B values):
        - 0: NE (north-east)
        - 1: E (east)
        - 2: SE (south-east)
        - 3: SW (south-west)
        - 4: W (west)
        - 5: NW (north-west)

        Returns:
            List of (col, row, edge_direction) for each neighbor
        """
        neighbors = []

        if row % 2 == 0:  # Even row
            offsets = [
                (0, -1, 0),   # NE
                (1, 0, 1),    # E
                (0, 1, 2),    # SE
                (-1, 1, 3),   # SW
                (-1, 0, 4),   # W
                (-1, -1, 5),  # NW
            ]
        else:  # Odd row
            offsets = [
                (1, -1, 0),   # NE
                (1, 0, 1),    # E
                (1, 1, 2),    # SE
                (0, 1, 3),    # SW
                (-1, 0, 4),   # W
                (0, -1, 5),   # NW
            ]

        for dc, dr, edge in offsets:
            nc, nr = col + dc, row + dr
            if 0 <= nc < self.width and 0 <= nr < self.height:
                neighbors.append((nc, nr, edge))

        return neighbors

    def _trace_river_segments(
        self,
        river_hexes: Set[Tuple[int, int]],
        elevation_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> List[List[Tuple[int, int, int]]]:
        """
        Trace connected river hexes into ordered segments with proper flow directions.

        Each segment is a list of (col, row, exit_edge) tuples representing
        the path of the river. The exit_edge indicates the DOWNSTREAM flow
        direction - the visual direction the river flows out of the hex.

        IMPORTANT: exit_edge represents visual flow direction for rendering,
        NOT the edge connecting to the next hex in the segment. Rivers should
        visually flow from high to low elevation (toward the sea).

        Args:
            river_hexes: Set of (col, row) hex coordinates with rivers
            elevation_map: Optional {(col, row): level} for determining flow direction

        Returns:
            List of river segments, each segment is a list of (col, row, exit_edge)
        """
        if not river_hexes:
            return []

        remaining = set(river_hexes)
        segments = []

        # Build adjacency graph for river hexes
        adjacency = {hex_pos: [] for hex_pos in river_hexes}
        for col, row in river_hexes:
            neighbors = self._get_hex_neighbors(col, row)
            for nc, nr, edge in neighbors:
                if (nc, nr) in river_hexes:
                    adjacency[(col, row)].append((nc, nr, edge))

        while remaining:
            # Start from an endpoint (hex with only 1 neighbor) if possible
            # This creates more natural river flows
            start = None
            for hex_pos in remaining:
                neighbor_count = sum(1 for n, _, _ in adjacency[hex_pos] if n in remaining)
                if neighbor_count <= 1:
                    start = hex_pos
                    break
            if start is None:
                start = next(iter(remaining))

            remaining.discard(start)
            segment = []
            current = start
            visited_in_segment = {start}

            # Follow the river path
            while True:
                # Find next unvisited river hex neighbor
                next_hex = None

                for nc, nr, edge in adjacency[current]:
                    if (nc, nr) in remaining:
                        next_hex = (nc, nr)
                        break

                # Calculate downstream flow direction for this hex
                exit_edge = self._calculate_flow_direction(
                    current[0], current[1], elevation_map
                )

                # Add current hex to segment
                segment.append((current[0], current[1], exit_edge))

                if next_hex is None:
                    break

                # Move to next hex
                remaining.discard(next_hex)
                visited_in_segment.add(next_hex)
                current = next_hex

            if segment:
                segments.append(segment)

        # Merge small segments into larger ones if they connect
        # This reduces fragmentation
        merged_segments = self._merge_connected_segments(segments, adjacency)

        return merged_segments

    def _calculate_flow_direction(
        self,
        col: int,
        row: int,
        elevation_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> int:
        """
        Calculate the downstream flow direction for a river hex.

        The flow direction is determined by:
        1. If elevation data available: direction toward lowest neighbor
        2. Otherwise: use geographic heuristic (rivers flow south toward Black Sea)

        Ukrainian rivers generally flow:
        - South (toward Black Sea): Dnipro, Southern Bug, Dnister
        - Southeast: Rivers in eastern Ukraine
        - Southwest: Rivers near Danube delta

        Args:
            col, row: Hex coordinates
            elevation_map: Optional elevation data

        Returns:
            Edge direction (0-5) representing downstream flow
        """
        neighbors = self._get_hex_neighbors(col, row)

        # If we have elevation data, flow toward lowest neighbor
        if elevation_map:
            my_elev = elevation_map.get((col, row), 0)
            lowest_elev = my_elev
            best_edge = None

            for nc, nr, edge in neighbors:
                neighbor_elev = elevation_map.get((nc, nr), 0)
                if neighbor_elev < lowest_elev:
                    lowest_elev = neighbor_elev
                    best_edge = edge

            if best_edge is not None:
                return best_edge

        # Fallback: geographic heuristic for Ukraine
        # Most rivers flow generally south toward the Black Sea
        # Prefer SE (2) and SW (3) as they represent southward flow
        # Use latitude (row) to bias direction:
        # - Northern rivers: prefer SE (2) - flowing toward center
        # - Southern rivers: prefer SW (3) - flowing toward sea
        # - Eastern rivers: prefer SW (3)
        # - Western rivers: prefer SE (2)

        # Simple heuristic based on position
        center_col = self.width // 2
        center_row = self.height // 2

        if col > center_col:
            # Eastern side - rivers flow SW
            return 3  # SW
        else:
            # Western side - rivers flow SE
            return 2  # SE

    def _merge_connected_segments(
        self,
        segments: List[List[Tuple[int, int, int]]],
        adjacency: dict
    ) -> List[List[Tuple[int, int, int]]]:
        """Merge connected segments into longer rivers."""
        if len(segments) <= 1:
            return segments

        # Build segment endpoint index
        segment_by_start = {}
        segment_by_end = {}
        for i, seg in enumerate(segments):
            if seg:
                start_pos = (seg[0][0], seg[0][1])
                end_pos = (seg[-1][0], seg[-1][1])
                segment_by_start[start_pos] = i
                segment_by_end[end_pos] = i

        merged = []
        used = set()

        for i, seg in enumerate(segments):
            if i in used:
                continue

            # Try to extend this segment by connecting to others
            current_seg = list(seg)
            used.add(i)

            # Try to prepend segments
            while True:
                if not current_seg:
                    break
                start_pos = (current_seg[0][0], current_seg[0][1])
                # Find a segment that ends adjacent to our start
                found = False
                for col, row in [(start_pos[0], start_pos[1])]:
                    for nc, nr, edge in adjacency.get((col, row), []):
                        if (nc, nr) in segment_by_end:
                            other_idx = segment_by_end[(nc, nr)]
                            if other_idx not in used:
                                # Prepend the other segment
                                other_seg = segments[other_idx]
                                # Update last hex's exit edge to connect
                                if other_seg:
                                    other_seg[-1] = (other_seg[-1][0], other_seg[-1][1], edge)
                                current_seg = list(other_seg) + current_seg
                                used.add(other_idx)
                                found = True
                                break
                    if found:
                        break
                if not found:
                    break

            # Try to append segments
            while True:
                if not current_seg:
                    break
                end_pos = (current_seg[-1][0], current_seg[-1][1])
                # Find a segment that starts adjacent to our end
                found = False
                for nc, nr, edge in adjacency.get(end_pos, []):
                    if (nc, nr) in segment_by_start:
                        other_idx = segment_by_start[(nc, nr)]
                        if other_idx not in used:
                            # Update our exit edge to connect
                            current_seg[-1] = (end_pos[0], end_pos[1], edge)
                            # Append the other segment
                            current_seg = current_seg + list(segments[other_idx])
                            used.add(other_idx)
                            found = True
                            break
                if not found:
                    break

            merged.append(current_seg)

        return merged

    def create_river_texture(
        self,
        ukraine_mask: Optional[Dict[Tuple[int, int], bool]] = None,
        river_hexes: Optional[Set[Tuple[int, int]]] = None,
        elevation_map: Optional[Dict[Tuple[int, int], int]] = None
    ) -> np.ndarray:
        """
        Create river texture array for the map.

        River texture encoding (from analysis of working maps):
        - No river: (255, 255, 6, 0)
        - River hex: (segment_id, position_in_segment, exit_edge, 0)
          - R = River segment ID (unique per connected river path)
          - G = Position along river (0, 1, 2, ... for each hex in segment)
          - B = Exit edge direction (0-5, DOWNSTREAM flow direction for rendering)
          - A = 0

        IMPORTANT: The exit_edge (B channel) represents the visual downstream
        flow direction, NOT the edge connecting to the next hex. Rivers should
        visually flow from high to low elevation.

        Args:
            ukraine_mask: Optional land mask to only place rivers on land
            river_hexes: Optional set of river hexes to mark. If not provided,
                        uses get_river_hexes_fast() to get all rivers.
            elevation_map: Optional {(col, row): level} for calculating flow direction

        Returns:
            RGBA array (height, width, 4)
        """
        # Get river hexes if not provided
        if river_hexes is None:
            river_hexes = self.get_river_hexes_fast()

        # Filter to land hexes if mask provided
        if ukraine_mask is not None:
            river_hexes = {h for h in river_hexes if ukraine_mask.get(h, False)}

        # Create texture - default is "no river" (255, 255, 6, 0)
        texture = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        texture[:, :, 0] = 255  # R
        texture[:, :, 1] = 255  # G
        texture[:, :, 2] = 6    # B
        texture[:, :, 3] = 0    # A

        # Trace river hexes into connected segments with proper flow direction
        segments = self._trace_river_segments(river_hexes, elevation_map)

        print(f"  Traced {len(segments)} river segments")

        # Encode each segment
        for segment_id, segment in enumerate(segments):
            if segment_id > 254:  # R channel limit (255 reserved for no-river)
                print(f"  Warning: More than 255 river segments, skipping excess")
                break

            for position, (col, row, exit_edge) in enumerate(segment):
                if position > 255:  # G channel limit
                    print(f"  Warning: River segment {segment_id} has more than 256 hexes")
                    break

                texture[row, col, 0] = segment_id       # R = segment ID
                texture[row, col, 1] = position         # G = position in segment
                texture[row, col, 2] = exit_edge        # B = exit edge (0-5)
                texture[row, col, 3] = 0                # A = 0

        return texture


def main():
    """Test river mapper."""
    import yaml

    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid_width = config['grid']['width']
    grid_height = config['grid']['height']

    print("=" * 60)
    print("RIVER MAPPER TEST")
    print("=" * 60)

    mapper = RiverMapper(bounds, grid_width, grid_height)

    # Get river hexes
    river_hexes = mapper.get_river_hexes_fast()

    print(f"\nAll river hexes: {len(river_hexes)}")
    print(f"Sample hexes: {list(river_hexes)[:10]}")

    # Test classification (without elevation data for porohy)
    print("\n--- Classification without elevation data ---")
    classification = mapper.classify_rivers()
    print(f"Regular rivers: {len(classification.regular_rivers)}")
    print(f"Reservoirs: {len(classification.reservoirs)}")
    print(f"Porohy: {len(classification.porohy)}")
    print(f"Natural lakes: {len(classification.lakes)}")

    # Calculate lake terrain total
    lake_terrain = classification.reservoirs | classification.porohy | classification.lakes
    print(f"\nTotal hexes for Lake terrain: {len(lake_terrain)}")
    print(f"Total hexes for River texture: {len(classification.regular_rivers)}")

    # Test with mock elevation data (for porohy detection demo)
    print("\n--- Classification with mock elevation data ---")
    # Create mock elevation grid with steep banks at certain locations
    mock_elevation = np.ones((grid_height, grid_width), dtype=np.float32) * 100
    # Add steep bank simulation: east side higher at some points
    for col in range(grid_width // 2, grid_width):
        for row in range(grid_height):
            mock_elevation[row, col] = 150  # East side 50m higher

    classification_with_elev = mapper.classify_rivers(elevation_grid=mock_elevation)
    print(f"Regular rivers: {len(classification_with_elev.regular_rivers)}")
    print(f"Reservoirs: {len(classification_with_elev.reservoirs)}")
    print(f"Porohy: {len(classification_with_elev.porohy)}")
    print(f"Natural lakes: {len(classification_with_elev.lakes)}")

    # Create texture for regular rivers only
    texture = mapper.create_river_texture(river_hexes=classification.regular_rivers)
    # River pixels have R < 255 (no-river is 255, 255, 6, 0)
    river_count = np.sum(texture[:, :, 0] < 255)
    print(f"\nRiver pixels in texture (regular only): {river_count}")

    # Analyze the texture
    print("\nTexture analysis:")
    unique_r = set(texture[:, :, 0].flatten())
    print(f"  Unique R values (segment IDs): {len(unique_r) - 1} (excluding 255)")
    print(f"  R values sample: {sorted(unique_r)[:10]}...")

    # Show sample river data
    print("\nSample river hexes in texture:")
    shown = 0
    for row in range(grid_height):
        for col in range(grid_width):
            r, g, b, a = texture[row, col]
            if r < 255:  # River hex
                print(f"  ({col}, {row}): R={r} G={g} B={b} A={a}")
                shown += 1
                if shown >= 5:
                    break
        if shown >= 5:
            break


if __name__ == "__main__":
    main()
