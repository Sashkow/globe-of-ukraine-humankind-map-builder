#!/usr/bin/env python3
"""
Terrain Mapper for Ukraine Map.

Maps terrain types to hex grid based on:
1. Copernicus land cover data (100m resolution)
2. Elevation from SRTM
3. River data from Natural Earth

Terrain is encoded in the G channel of ElevationTexture.

IMPORTANT: The terrain index must match the ORDER of terrain names in
TerrainTypeNames in Save.hms. This order may vary between maps!
"""

import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Set, Optional
import yaml


# Default terrain type indices (alphabetical order as in our Save.hms)
# These are used when terrain_names_order is not provided
TERRAIN_TYPES = {
    'CityTerrain': 0,    # Default land
    'CoastalWater': 1,   # Shallow water near coast
    'DryGrass': 2,       # Dry steppe
    'Forest': 3,         # Dense forest
    'Lake': 4,           # Inland water body
    'Mountain': 5,       # Mountains
    'MountainSnow': 6,   # Snow-capped peaks
    'Ocean': 7,          # Deep ocean
    'Prairie': 8,        # Open grassland
    'RockyField': 9,     # Rocky terrain
    'RockyForest': 10,   # Forest on rocky/hilly terrain
    'Sterile': 11,       # Barren land
    'StoneField': 12,    # Rocky/stony terrain
    'Wasteland': 13,     # Desert-like
    'WoodLand': 14,      # Light forest / woodland (lisostep)
}

# Copernicus CGLS-LC100 land cover to Humankind terrain mapping
# See landcover_fetcher_copernicus.py for class definitions
COPERNICUS_TO_TERRAIN = {
    0: 'CityTerrain',      # Unknown → default land
    20: 'DryGrass',        # Shrubs → dry grass (steppe shrubland)
    30: 'Prairie',         # Herbaceous vegetation → grassland
    40: 'Prairie',         # Cultivated/cropland → prairie (farmland)
    50: 'CityTerrain',     # Urban/built-up → city terrain
    60: 'Mountain',        # Bare/sparse vegetation → mountain (rocky high terrain)
    70: 'MountainSnow',    # Snow and ice → snow peaks
    80: 'Lake',            # Permanent water → lake
    90: 'CoastalWater',    # Herbaceous wetland → shallow water/marsh
    100: 'RockyField',     # Moss and lichen → rocky (tundra-like)
    # Closed forests (dense)
    111: 'Forest',         # Closed forest, evergreen needle (conifer)
    112: 'Forest',         # Closed forest, evergreen broad (tropical)
    113: 'Forest',         # Closed forest, deciduous needle
    114: 'Forest',         # Closed forest, deciduous broad (temperate)
    115: 'Forest',         # Closed forest, mixed
    116: 'Forest',         # Closed forest, other
    # Open forests (sparse) → woodland
    121: 'WoodLand',       # Open forest, evergreen needle
    122: 'WoodLand',       # Open forest, evergreen broad
    123: 'WoodLand',       # Open forest, deciduous needle
    124: 'WoodLand',       # Open forest, deciduous broad
    125: 'WoodLand',       # Open forest, mixed
    126: 'WoodLand',       # Open forest, other
    200: 'Ocean',          # Oceans/seas → ocean
}

# G channel encoding (discovered from bhktools and testing):
# G = (biome_variant << 4) | terrain_index
#
# Where:
#   - terrain_index (lower 4 bits, G & 0x0F) = index into TerrainTypeNames (0-14)
#   - biome_variant (upper 4 bits, G >> 4) = climate/biome variant (0-9 observed)
#
# Biome variants observed in Huge Earth map:
#   - Variant 0: Arctic/snowy appearance
#   - Variant 7: Most common, default temperate (used for most Ocean hexes)
#   - Variants 3-8: Various temperate/normal biomes
#
# For Ukraine map, we'll use variant 7 as the default (temperate).


def get_hex_neighbors(col: int, row: int, width: int, height: int) -> list:
    """
    Get neighboring hex coordinates in offset coordinate system (odd-r).

    In odd-r offset coordinates, odd rows are shifted right by 0.5.
    Returns list of (col, row) tuples for valid neighbors within bounds.

    Neighbor directions (for reference):
    - For even rows: NW(-1,-1), NE(0,-1), W(-1,0), E(+1,0), SW(-1,+1), SE(0,+1)
    - For odd rows:  NW(0,-1), NE(+1,-1), W(-1,0), E(+1,0), SW(0,+1), SE(+1,+1)
    """
    neighbors = []

    if row % 2 == 0:  # Even row
        offsets = [
            (-1, -1), (0, -1),   # NW, NE
            (-1, 0), (1, 0),     # W, E
            (-1, 1), (0, 1),     # SW, SE
        ]
    else:  # Odd row
        offsets = [
            (0, -1), (1, -1),    # NW, NE
            (-1, 0), (1, 0),     # W, E
            (0, 1), (1, 1),      # SW, SE
        ]

    for dc, dr in offsets:
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and 0 <= nr < height:
            neighbors.append((nc, nr))

    return neighbors


def get_hex_neighbor_directions(col: int, row: int, width: int, height: int) -> list:
    """
    Get neighboring hex coordinates with direction indices (0-5).

    Returns list of (direction, col, row) tuples for valid neighbors.
    Direction indices match the B channel bit positions for mountain chains.

    Direction encoding:
    - Bit 0 (1): NW
    - Bit 1 (2): NE
    - Bit 2 (4): W
    - Bit 3 (8): E
    - Bit 4 (16): SW
    - Bit 5 (32): SE
    """
    neighbors = []

    if row % 2 == 0:  # Even row
        offsets = [
            (0, -1, -1),   # NW
            (1, 0, -1),    # NE
            (2, -1, 0),    # W
            (3, 1, 0),     # E
            (4, -1, 1),    # SW
            (5, 0, 1),     # SE
        ]
    else:  # Odd row
        offsets = [
            (0, 0, -1),    # NW
            (1, 1, -1),    # NE
            (2, -1, 0),    # W
            (3, 1, 0),     # E
            (4, 0, 1),     # SW
            (5, 1, 1),     # SE
        ]

    for direction, dc, dr in offsets:
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and 0 <= nr < height:
            neighbors.append((direction, nc, nr))

    return neighbors


def calculate_mountain_chain_flags(
    mountain_hexes: Set[Tuple[int, int]],
    width: int,
    height: int
) -> Dict[Tuple[int, int], int]:
    """
    Calculate B channel values for mountain chain connectivity.

    The B channel encodes which neighboring hexes are also mountains,
    creating connected mountain chains for proper 3D rendering.

    Each bit in B represents a direction:
    - Bit 0 (1): NW neighbor is mountain
    - Bit 1 (2): NE neighbor is mountain
    - Bit 2 (4): W neighbor is mountain
    - Bit 3 (8): E neighbor is mountain
    - Bit 4 (16): SW neighbor is mountain
    - Bit 5 (32): SE neighbor is mountain

    B=0 means isolated (won't render as 3D mountain)
    B=63 means connected in all 6 directions

    Args:
        mountain_hexes: Set of (col, row) tuples that are Mountain or MountainSnow terrain
        width: Grid width
        height: Grid height

    Returns:
        Dict mapping (col, row) -> B channel value for each mountain hex
    """
    b_channel = {}

    for col, row in mountain_hexes:
        flags = 0
        neighbors = get_hex_neighbor_directions(col, row, width, height)

        for direction, nc, nr in neighbors:
            if (nc, nr) in mountain_hexes:
                flags |= (1 << direction)

        # Ensure isolated mountains still render - set minimum connectivity
        # If a hex has no mountain neighbors, set B=63 to force rendering
        if flags == 0:
            flags = 63  # All directions - makes isolated peaks render

        b_channel[(col, row)] = flags

    return b_channel


def get_east_neighbors(col: int, row: int, width: int, height: int) -> list:
    """
    Get eastern/right-side neighbors of a hex (E, NE, SE).

    For rivers flowing south (like Dnipro), the "left bank" is on the east side.
    Returns list of (col, row) tuples for valid eastern neighbors.
    """
    neighbors = []

    if row % 2 == 0:  # Even row
        offsets = [
            (0, -1),   # NE
            (1, 0),    # E
            (0, 1),    # SE
        ]
    else:  # Odd row
        offsets = [
            (1, -1),   # NE
            (1, 0),    # E
            (1, 1),    # SE
        ]

    for dc, dr in offsets:
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and 0 <= nr < height:
            neighbors.append((nc, nr))

    return neighbors


def encode_terrain(terrain_idx: int, biome_variant: int = 7) -> int:
    """Encode terrain type and biome variant to G channel value.

    Args:
        terrain_idx: Index into TerrainTypeNames (0-14)
        biome_variant: Climate/biome variant (0-9, default 7 = temperate)

    Returns:
        G channel value = (biome_variant << 4) | terrain_idx
    """
    return (biome_variant << 4) | (terrain_idx & 0x0F)


def decode_terrain(g_value: int) -> Tuple[int, int]:
    """Decode G channel value to (terrain_idx, biome_variant)."""
    terrain_idx = g_value & 0x0F
    biome_variant = g_value >> 4
    return terrain_idx, biome_variant


class TerrainMapper:
    """Maps terrain types to hex grid based on geography."""

    # Default elevation levels for water tiles
    # These control the R channel in ElevationTexture
    DEFAULT_OCEAN_ELEVATION = -3      # Deep ocean (R=1)
    DEFAULT_COASTAL_ELEVATION = -1    # Shallow coastal water (R=3)
    DEFAULT_LAKE_ELEVATION = -1       # Lakes/rivers (R=3)

    def __init__(self, bounds: dict, grid_width: int, grid_height: int,
                 terrain_names_order: list = None,
                 ocean_elevation: int = None,
                 coastal_elevation: int = None,
                 lake_elevation: int = None):
        """
        Initialize terrain mapper.

        Args:
            bounds: {min_lon, max_lon, min_lat, max_lat}
            grid_width: Number of hex columns
            grid_height: Number of hex rows
            terrain_names_order: List of terrain names in order from Save.hms TerrainTypeNames.
                               If None, uses default TERRAIN_TYPES dict.
            ocean_elevation: Elevation level for deep ocean tiles (-3 to 0, default -3)
            coastal_elevation: Elevation level for coastal/shallow water (-3 to 0, default -1)
            lake_elevation: Elevation level for lakes/rivers (-3 to 0, default -1)
        """
        self.bounds = bounds
        self.width = grid_width
        self.height = grid_height

        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']

        # Water elevation settings
        self.ocean_elevation = ocean_elevation if ocean_elevation is not None else self.DEFAULT_OCEAN_ELEVATION
        self.coastal_elevation = coastal_elevation if coastal_elevation is not None else self.DEFAULT_COASTAL_ELEVATION
        self.lake_elevation = lake_elevation if lake_elevation is not None else self.DEFAULT_LAKE_ELEVATION

        # Build terrain type indices from the provided order
        if terrain_names_order:
            self.terrain_types = {name: idx for idx, name in enumerate(terrain_names_order)}
            print(f"  Using terrain order from Save.hms: {len(self.terrain_types)} types")
        else:
            self.terrain_types = TERRAIN_TYPES.copy()
            print(f"  Using default terrain order: {len(self.terrain_types)} types")

        print(f"  Water elevations: ocean={self.ocean_elevation}, coastal={self.coastal_elevation}, lake={self.lake_elevation}")

    def _pixel_to_geo(self, col: int, row: int) -> Tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates."""
        lon = self.min_lon + (col / self.width) * (self.max_lon - self.min_lon)
        lat = self.max_lat - (row / self.height) * (self.max_lat - self.min_lat)
        return lon, lat

    def set_elevation_range(self, max_elevation: int, second_max_elevation: int):
        """Set the max elevation levels for terrain assignment."""
        self.max_elevation = max_elevation
        self.second_max_elevation = second_max_elevation

    def get_terrain_for_hex(
        self,
        col: int,
        row: int,
        elevation: int,  # Game level -3 to 12
        is_land: bool,
        is_river: bool = False,
        landcover: Optional[int] = None,  # Copernicus land cover class
        biome: Optional[int] = None,  # Territory biome (0-9) for variant encoding
    ) -> Tuple[int, Optional[int]]:
        """
        Determine terrain type for a hex based on elevation and Copernicus land cover data.

        IMPORTANT: The is_land flag (from Ukraine raion boundaries) is authoritative.
        If is_land=True, the hex MUST get a land terrain type, even if Copernicus
        says it's water (Copernicus may show reservoirs, rivers, wetlands as water).

        IMPORTANT: High elevation land MUST use Mountain/MountainSnow terrain for
        proper in-game rendering. Elevation overrides Copernicus landcover for terrain.

        IMPORTANT: The biome parameter should match the territory's biome to ensure
        proper in-game visual rendering. If biome is not provided, defaults to 7 (Temperate).

        Args:
            col, row: Hex coordinates
            elevation: Game elevation level (-3 to 12)
            is_land: True if land hex (from raion boundaries - AUTHORITATIVE)
            is_river: True if river hex
            landcover: Copernicus CGLS-LC100 land cover class (0-200)
            biome: Territory biome index (0-9) to use as biome variant

        Returns:
            Tuple of (G channel value encoding terrain type, optional elevation override)
            The elevation override is set for water tiles (ocean/coastal/lake) to ensure
            they render correctly in-game.
        """
        # Use territory biome as variant, or default to 7 (Temperate)
        biome_variant = biome if biome is not None else 7

        # Water terrain (not land according to raion boundaries)
        if not is_land:
            if elevation <= -2:
                return encode_terrain(self.terrain_types['Ocean'], biome_variant), self.ocean_elevation
            else:
                return encode_terrain(self.terrain_types['CoastalWater'], biome_variant), self.coastal_elevation

        # === LAND HEXES ONLY BELOW (raion says this is land) ===

        # Rivers on land - Lake terrain
        if is_river:
            return encode_terrain(self.terrain_types['Lake'], biome_variant), self.lake_elevation

        # === ELEVATION-BASED TERRAIN (mountains MUST be Mountain terrain) ===
        # This is critical for in-game rendering - high elevation with wrong
        # terrain type renders as flat land

        # MountainSnow for very high elevation (level 10+, or at max elevation)
        # Use Arctic variant (0) for snow-capped peaks
        if elevation >= 10 or (hasattr(self, 'max_elevation') and elevation == self.max_elevation):
            return encode_terrain(self.terrain_types['MountainSnow'], 0), None

        # Mountain for high elevation (level 7-9)
        if elevation >= 7:
            return encode_terrain(self.terrain_types['Mountain'], biome_variant), None

        # RockyField for moderately high elevation (level 5-6, hills/high hills)
        if elevation >= 5:
            # Check if Copernicus says forest - use RockyForest instead
            if landcover is not None and landcover in (111, 112, 113, 114, 115, 116):
                return encode_terrain(self.terrain_types['RockyForest'], biome_variant), None
            return encode_terrain(self.terrain_types['RockyField'], biome_variant), None

        # === LANDCOVER-BASED TERRAIN (for lower elevations) ===
        if landcover is not None and landcover in COPERNICUS_TO_TERRAIN:
            terrain_name = COPERNICUS_TO_TERRAIN[landcover]

            # Override: if Copernicus says water but raion says land,
            # use default land terrain (this catches reservoirs, rivers, wetlands)
            if terrain_name in ('Ocean', 'Lake', 'CoastalWater'):
                return encode_terrain(self.terrain_types['Prairie'], biome_variant), None

            # Don't use Mountain/MountainSnow from landcover for low elevation
            # (already handled above for high elevation)
            if terrain_name == 'Mountain' and elevation < 7:
                return encode_terrain(self.terrain_types['RockyField'], biome_variant), None
            if terrain_name == 'MountainSnow' and elevation < 10:
                return encode_terrain(self.terrain_types['Mountain'], biome_variant), None

            return encode_terrain(self.terrain_types[terrain_name], biome_variant), None

        # Fallback: default land (Prairie)
        return encode_terrain(self.terrain_types['Prairie'], biome_variant), None

    def _get_river_elevation_from_bank(
        self,
        col: int,
        row: int,
        elevation_map: Dict[Tuple[int, int], int],
        land_mask: Dict[Tuple[int, int], bool],
        river_hexes: Set[Tuple[int, int]],
    ) -> int:
        """
        Get elevation for a river hex based on adjacent land.

        Uses the lowest elevation among adjacent land tiles (valley floor).

        Args:
            col, row: River hex coordinates
            elevation_map: {(col, row): level} elevation per hex
            land_mask: {(col, row): is_land} land/ocean per hex
            river_hexes: Set of river hex coordinates

        Returns:
            Lowest elevation level from adjacent land, or default lake elevation
        """
        all_neighbors = get_hex_neighbors(col, row, self.width, self.height)

        land_elevations = []
        for nc, nr in all_neighbors:
            neighbor_pos = (nc, nr)
            # Check if neighbor is land (not river, not ocean)
            if land_mask.get(neighbor_pos, False) and neighbor_pos not in river_hexes:
                land_elevations.append(elevation_map.get(neighbor_pos, self.lake_elevation))

        if land_elevations:
            return min(land_elevations)

        # Fallback to default lake elevation
        return self.lake_elevation

    def create_terrain_map(
        self,
        elevation_map: Dict[Tuple[int, int], int],
        land_mask: Dict[Tuple[int, int], bool],
        river_hexes: Optional[Set[Tuple[int, int]]] = None,
        landcover_grid: Optional[np.ndarray] = None,
        hex_biome_map: Optional[Dict[Tuple[int, int], int]] = None,
    ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], int], Set[Tuple[int, int]]]:
        """
        Create terrain map for all hexes.

        Args:
            elevation_map: {(col, row): level} elevation per hex
            land_mask: {(col, row): is_land} land/ocean per hex
            river_hexes: Optional set of (col, row) for river hexes
            landcover_grid: Optional numpy array (height x width) of Copernicus land cover classes
            hex_biome_map: Optional {(col, row): biome} map for biome variant encoding

        Returns:
            Tuple of:
            - terrain_map: {(col, row): g_value} terrain encoding per hex
            - elevation_overrides: {(col, row): level} elevation overrides for water tiles
            - mountain_hexes: set of (col, row) for Mountain/MountainSnow terrain (for B channel)
        """
        if river_hexes is None:
            river_hexes = set()

        terrain_map = {}
        elevation_overrides = {}
        terrain_counts = {}
        mountain_hexes = set()  # Track Mountain and MountainSnow terrain

        # First pass: assign terrain types to all hexes
        for row in range(self.height):
            for col in range(self.width):
                pos = (col, row)
                elevation = elevation_map.get(pos, 0)
                is_land = land_mask.get(pos, False)
                is_river = pos in river_hexes

                # Get land cover from grid if available
                landcover = None
                if landcover_grid is not None:
                    landcover = int(landcover_grid[row, col])

                # Get biome for this hex
                biome = None
                if hex_biome_map is not None:
                    biome = hex_biome_map.get(pos)

                g_value, elev_override = self.get_terrain_for_hex(
                    col, row, elevation, is_land, is_river, landcover, biome
                )
                terrain_map[pos] = g_value

                # Store elevation override if provided (for non-river water tiles)
                # River tiles get special handling below
                if elev_override is not None and not is_river:
                    elevation_overrides[pos] = elev_override

                # Count terrain types and track mountains
                terrain_idx = g_value & 0x0F
                terrain_counts[terrain_idx] = terrain_counts.get(terrain_idx, 0) + 1

                # Track mountain hexes (Mountain=5, MountainSnow=6 in default order)
                mountain_idx = self.terrain_types.get('Mountain', 5)
                mountain_snow_idx = self.terrain_types.get('MountainSnow', 6)
                if terrain_idx in (mountain_idx, mountain_snow_idx):
                    mountain_hexes.add(pos)

        # Second pass: set river elevations based on adjacent land (left bank)
        river_bank_elevations = 0
        for pos in river_hexes:
            col, row = pos
            bank_elevation = self._get_river_elevation_from_bank(
                col, row, elevation_map, land_mask, river_hexes
            )
            elevation_overrides[pos] = bank_elevation
            river_bank_elevations += 1

        # Print terrain distribution
        print("  Terrain distribution:")
        terrain_names = {v: k for k, v in TERRAIN_TYPES.items()}
        for idx in sorted(terrain_counts.keys()):
            name = terrain_names.get(idx, f"Unknown({idx})")
            count = terrain_counts[idx]
            print(f"    {name}: {count} hexes")

        print(f"  Elevation overrides: {len(elevation_overrides)} water hexes")
        print(f"    - River hexes with bank elevation: {river_bank_elevations}")
        print(f"  Mountain hexes: {len(mountain_hexes)} (for B channel connectivity)")

        return terrain_map, elevation_overrides, mountain_hexes


def main():
    """Test terrain mapper."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid_width = config['grid']['width']
    grid_height = config['grid']['height']

    print("=" * 60)
    print("TERRAIN MAPPER TEST")
    print("=" * 60)

    mapper = TerrainMapper(bounds, grid_width, grid_height)

    # Test with sample data
    print("\nSample terrain encodings:")
    test_cases = [
        ("Ocean deep", 50, 50, -3, False, False),
        ("Coast shallow", 50, 50, -1, False, False),
        ("River", 50, 50, 2, True, True),
        ("Low plain", 50, 50, 1, True, False),
        ("Forest-steppe", 50, 25, 3, True, False),
        ("Mountain", 25, 40, 8, True, False),
        ("Peak", 25, 40, 11, True, False),
    ]

    for name, col, row, elev, is_land, is_river in test_cases:
        g, elev_override = mapper.get_terrain_for_hex(col, row, elev, is_land, is_river)
        terrain_idx, biome_var = decode_terrain(g)
        terrain_names = {v: k for k, v in TERRAIN_TYPES.items()}
        terrain_name = terrain_names.get(terrain_idx, f"Unknown({terrain_idx})")
        elev_str = f", elev_override={elev_override}" if elev_override is not None else ""
        print(f"  {name}: G={g} -> {terrain_name} (biome variant {biome_var}){elev_str}")


if __name__ == "__main__":
    main()
