#!/usr/bin/env python3
"""
Natural Wonder Mapper for Ukraine Map.

Places natural wonders on the hex grid based on real Ukrainian geographic features
mapped to corresponding Humankind natural wonders.

NaturalWonderTexture encoding:
- R channel: Wonder index (1-based, matching NaturalWonderNames order)
- G channel: 0
- B channel: 0
- A channel: 0 (or 255)
- All zeros = no wonder at this hex

Ukrainian Features → Humankind Wonders:
1. Lake Synevyr (largest mountain lake) → LakeBaikal
2. Optimistic Cave (world's longest gypsum cave) → MountMulu
3. Mount Hoverla (highest peak, 2061m) → MountEverest
4. Askania-Nova (unique biosphere reserve) → Yellowstone
5. Aktovsky Canyon (Ukraine's "Grand Canyon") → MountRoraima
6. Donbas Terricones (coal mining slag heaps) → ChocolateHills
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass


@dataclass
class NaturalWonder:
    """Definition of a natural wonder placement."""
    humankind_name: str      # Name in Humankind (e.g., "LakeBaikal")
    ukrainian_name: str      # Real Ukrainian feature name
    lat: float               # Latitude
    lon: float               # Longitude
    radius: int              # Radius in hexes (wonders can span multiple hexes)
    description: str         # Description of why this mapping makes sense


# Ukrainian natural wonders mapped to Humankind wonders
UKRAINE_WONDERS = [
    NaturalWonder(
        humankind_name="KawahIjen",
        ukrainian_name="Lake Synevyr",
        lat=48.617,
        lon=23.683,
        radius=1,
        description="Largest mountain lake in Ukrainian Carpathians, 'Pearl of the Carpathians', turquoise waters at 989m elevation"
    ),
    NaturalWonder(
        humankind_name="MountMulu",
        ukrainian_name="Marble Cave (Mramorna)",
        lat=44.80,
        lon=34.28,
        radius=1,
        description="One of Europe's most visited caves in Crimean Chatyr-Dag massif, with stunning stalactites"
    ),
    NaturalWonder(
        humankind_name="HalongBay",
        ukrainian_name="Cape Fiolent",
        lat=44.50,
        lon=33.49,
        radius=2,
        description="Dramatic volcanic cliffs on Crimean coast near Sevastopol, with sea stacks and grottoes"
    ),
    NaturalWonder(
        humankind_name="MountEverest",
        ukrainian_name="Mount Hoverla",
        lat=48.1603,
        lon=24.5003,
        radius=2,
        description="Highest peak in Ukraine at 2,061m, in the Carpathian Mountains"
    ),
    NaturalWonder(
        humankind_name="Yellowstone",
        ukrainian_name="Askania-Nova",
        lat=46.45,
        lon=33.87,
        radius=2,
        description="Unique biosphere reserve with world's largest Przewalski's Horse population, pristine steppe"
    ),
    NaturalWonder(
        humankind_name="MountRoraima",
        ukrainian_name="Aktovsky Canyon",
        lat=47.72,
        lon=31.45,
        radius=1,
        description="Ukraine's 'Grand Canyon' with dramatic granite cliffs and unique rock formations"
    ),
    NaturalWonder(
        humankind_name="ChocolateHills",
        ukrainian_name="Donbas Terricones",
        lat=48.30,
        lon=38.10,
        radius=2,
        description="Numerous cone-shaped coal mining slag heaps near Horlivka, iconic Donbas landscape"
    ),
]

# Standard Humankind natural wonder names (subset commonly used)
# Index in this list = R channel value (1-based)
NATURAL_WONDER_NAMES = [
    "ChocolateHills",
    "DanakilDesert",
    "GreatBarrierReef",
    "GreatBlueHole",
    "HalongBay",
    "KawahIjen",
    "LakeBaikal",
    "LakeHillier",
    "MountEverest",
    "MountMulu",
    "MountRoraima",
    "MountVesuvius",
    "PeritoMorenoGlacier",
    "Yellowstone",
]


class NaturalWonderMapper:
    """Maps natural wonders to hex grid."""

    def __init__(self, bounds: dict, grid_width: int, grid_height: int):
        """
        Initialize natural wonder mapper.

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

        # Build wonder name to index mapping (1-based)
        self.wonder_indices = {name: idx + 1 for idx, name in enumerate(NATURAL_WONDER_NAMES)}

    def _geo_to_pixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        col = int((lon - self.min_lon) / (self.max_lon - self.min_lon) * self.width)
        row = int((self.max_lat - lat) / (self.max_lat - self.min_lat) * self.height)

        # Clamp to valid range
        col = max(0, min(self.width - 1, col))
        row = max(0, min(self.height - 1, row))

        return col, row

    def _get_hex_circle(self, center_col: int, center_row: int, radius: int) -> Set[Tuple[int, int]]:
        """
        Get all hexes within a radius of a center hex.

        Uses simple rectangular approximation for hex grid.
        """
        hexes = set()

        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                # Approximate hex distance
                if abs(dr) + abs(dc) <= radius + (radius // 2):
                    nc, nr = center_col + dc, center_row + dr
                    if 0 <= nc < self.width and 0 <= nr < self.height:
                        hexes.add((nc, nr))

        return hexes

    def get_wonder_placements(
        self,
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> Dict[Tuple[int, int], int]:
        """
        Get wonder placements as {(col, row): wonder_index}.

        Args:
            land_mask: Optional dict of {(col, row): is_land}

        Returns:
            Dict mapping hex coordinates to wonder index (1-based)
        """
        placements = {}

        for wonder in UKRAINE_WONDERS:
            # Check if wonder name is in our list
            if wonder.humankind_name not in self.wonder_indices:
                print(f"  WARNING: Unknown wonder '{wonder.humankind_name}', skipping")
                continue

            wonder_idx = self.wonder_indices[wonder.humankind_name]
            center_col, center_row = self._geo_to_pixel(wonder.lon, wonder.lat)

            # Check if center is on land
            if land_mask and not land_mask.get((center_col, center_row), False):
                print(f"  WARNING: {wonder.ukrainian_name} center is in ocean, adjusting...")
                # Try to find nearby land hex
                found = False
                for dr in range(-3, 4):
                    for dc in range(-3, 4):
                        test_pos = (center_col + dc, center_row + dr)
                        if land_mask.get(test_pos, False):
                            center_col, center_row = test_pos
                            found = True
                            break
                    if found:
                        break
                if not found:
                    print(f"  ERROR: Could not place {wonder.ukrainian_name}, no land nearby")
                    continue

            # Get all hexes for this wonder
            wonder_hexes = self._get_hex_circle(center_col, center_row, wonder.radius)

            # Filter to land only
            if land_mask:
                wonder_hexes = {h for h in wonder_hexes if land_mask.get(h, False)}

            if not wonder_hexes:
                print(f"  WARNING: No valid hexes for {wonder.ukrainian_name}")
                continue

            # Place wonder
            for hex_pos in wonder_hexes:
                placements[hex_pos] = wonder_idx

            print(f"  {wonder.ukrainian_name} -> {wonder.humankind_name}: {len(wonder_hexes)} hexes at ({center_col}, {center_row})")

        return placements

    def create_wonder_texture(
        self,
        land_mask: Optional[Dict[Tuple[int, int], bool]] = None
    ) -> np.ndarray:
        """
        Create natural wonder texture array.

        Args:
            land_mask: Optional dict of {(col, row): is_land}

        Returns:
            numpy array of shape (height, width, 4) with RGBA values
        """
        # Get placements
        placements = self.get_wonder_placements(land_mask)

        # Initialize with zeros (no wonders)
        texture = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Place wonders
        for (col, row), wonder_idx in placements.items():
            texture[row, col, 0] = wonder_idx  # R = wonder index
            # G, B, A remain 0

        print(f"  Total wonder hexes: {len(placements)}")

        return texture

    def get_wonder_names_xml(self) -> str:
        """Generate XML for NaturalWonderNames section."""
        items = "\n".join(f"            <String>{name}</String>" for name in NATURAL_WONDER_NAMES)
        return f"""        <NaturalWonderNames Length="{len(NATURAL_WONDER_NAMES)}">
{items}
        </NaturalWonderNames>"""


def main():
    """Test natural wonder mapper."""
    import yaml

    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid_width = config['grid']['width']
    grid_height = config['grid']['height']

    print("=" * 60)
    print("NATURAL WONDER MAPPER TEST")
    print("=" * 60)

    mapper = NaturalWonderMapper(bounds, grid_width, grid_height)

    print("\nUkrainian Natural Wonders:")
    for wonder in UKRAINE_WONDERS:
        col, row = mapper._geo_to_pixel(wonder.lon, wonder.lat)
        print(f"  {wonder.ukrainian_name}")
        print(f"    -> {wonder.humankind_name} at ({col}, {row})")
        print(f"    {wonder.description}")
        print()

    # Create texture (without land mask for testing)
    print("\nCreating wonder texture...")
    texture = mapper.create_wonder_texture()
    print(f"  Texture shape: {texture.shape}")

    # Count non-zero pixels
    non_zero = np.sum(texture[:, :, 0] > 0)
    print(f"  Wonder pixels: {non_zero}")

    # Print wonder names XML
    print("\nNaturalWonderNames XML:")
    print(mapper.get_wonder_names_xml())


if __name__ == "__main__":
    main()
