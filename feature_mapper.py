#!/usr/bin/env python3
"""
Feature Mapper for Ukraine Map.

Places natural features (terrain modifiers) and resources on the hex grid
based on real-world geographic locations from the terrain modifiers document.

POI Texture encoding:
- R channel: POI index from POINames list
- 0 = None (no feature)
- 1-24 = POI_NaturalModifier01-24
- 25-55 = POI_ResourceDeposit01-31
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml
import re


# Natural Modifier mapping (POI_NaturalModifier01-24)
# Based on game data analysis and wiki
NATURAL_MODIFIERS = {
    'BerryBushes': 1,       # POI_NaturalModifier01
    'BlackSoil': 2,         # POI_NaturalModifier02
    'Cave': 3,              # POI_NaturalModifier03
    'Clay': 4,              # POI_NaturalModifier04
    'Crater': 5,            # POI_NaturalModifier05
    'DimensionStones': 6,   # POI_NaturalModifier06
    'DomesticableAnimals': 7,  # POI_NaturalModifier07
    'Geysers': 8,           # POI_NaturalModifier08
    'HotSprings': 9,        # POI_NaturalModifier09
    'HugeTrees': 10,        # POI_NaturalModifier10
    'Marsh': 11,            # POI_NaturalModifier11
    'Oasis': 12,            # POI_NaturalModifier12
    'River': 13,            # POI_NaturalModifier13
    'RiverSpring': 14,      # POI_NaturalModifier14
    'TerraRosa': 15,        # POI_NaturalModifier15
    'VolcanoEarth': 16,     # POI_NaturalModifier16
    # 17-24 may be additional modifiers or unused
}

# Resource Deposit mapping (POI_ResourceDeposit01-31)
# Strategic resources first, then luxury
RESOURCE_DEPOSITS = {
    # Strategic Resources
    'Horse': 25,            # POI_ResourceDeposit01
    'Copper': 26,           # POI_ResourceDeposit02
    'Iron': 27,             # POI_ResourceDeposit03
    'Saltpetre': 28,        # POI_ResourceDeposit04
    'Coal': 29,             # POI_ResourceDeposit05
    'Oil': 30,              # POI_ResourceDeposit06
    'Aluminium': 31,        # POI_ResourceDeposit07
    'Uranium': 32,          # POI_ResourceDeposit08
    # Luxury Resources (Food-based)
    'Salt': 33,             # POI_ResourceDeposit09
    'Sage': 34,             # POI_ResourceDeposit10
    'Coffee': 35,           # POI_ResourceDeposit11
    'Tea': 36,              # POI_ResourceDeposit12
    'Saffron': 37,          # POI_ResourceDeposit13
    # Luxury Resources (Industry-based)
    'Dye': 38,              # POI_ResourceDeposit14
    'Ebony': 39,            # POI_ResourceDeposit15
    'Marble': 40,           # POI_ResourceDeposit16
    'Obsidian': 41,         # POI_ResourceDeposit17
    'Silk': 42,             # POI_ResourceDeposit18
    # Luxury Resources (Money-based)
    'Incense': 43,          # POI_ResourceDeposit19
    'Porcelain': 44,        # POI_ResourceDeposit20
    'Pearls': 45,           # POI_ResourceDeposit21
    'Gold': 46,             # POI_ResourceDeposit22
    'Gemstone': 47,         # POI_ResourceDeposit23
    # Luxury Resources (Science-based)
    'Ambergris': 48,        # POI_ResourceDeposit24
    'Papyrus': 49,          # POI_ResourceDeposit25
    'Lead': 50,             # POI_ResourceDeposit26
    'Mercury': 51,          # POI_ResourceDeposit27
    'Silver': 52,           # POI_ResourceDeposit28
    # Additional resources
    'Weapon': 53,           # POI_ResourceDeposit29
    'SaltedBeef': 54,       # POI_ResourceDeposit30
    'Pharmaceuticals': 55,  # POI_ResourceDeposit31
}

# Combined lookup
POI_INDICES = {**NATURAL_MODIFIERS, **RESOURCE_DEPOSITS}


class FeatureMapper:
    """Maps natural features and resources to hex grid based on real geography."""

    def __init__(self, bounds: dict, grid_width: int, grid_height: int):
        """
        Initialize feature mapper.

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

        # Features to place: list of (col, row, poi_index)
        self.features: List[Tuple[int, int, int]] = []

    def _geo_to_pixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        col = int((lon - self.min_lon) / (self.max_lon - self.min_lon) * self.width)
        row = int((self.max_lat - lat) / (self.max_lat - self.min_lat) * self.height)

        # Clamp to valid range
        col = max(0, min(self.width - 1, col))
        row = max(0, min(self.height - 1, row))

        return col, row

    def add_feature(self, feature_name: str, lat: float, lon: float) -> bool:
        """
        Add a feature at the specified location.

        Args:
            feature_name: Name of the feature (must be in POI_INDICES)
            lat: Latitude
            lon: Longitude

        Returns:
            True if feature was added, False if feature name unknown
        """
        if feature_name not in POI_INDICES:
            print(f"  WARNING: Unknown feature '{feature_name}'")
            return False

        poi_index = POI_INDICES[feature_name]
        col, row = self._geo_to_pixel(lon, lat)

        self.features.append((col, row, poi_index))
        return True

    def load_from_markdown(self, md_path: Path) -> int:
        """
        Load features from the terrain modifiers markdown document.

        Parses tables with Location | Lat | Lon format.

        Args:
            md_path: Path to humankind_ukraine_terrain_modifiers.md

        Returns:
            Number of features loaded
        """
        if not md_path.exists():
            print(f"ERROR: Terrain modifiers file not found: {md_path}")
            return 0

        content = md_path.read_text()
        count = 0

        # Current section being parsed
        current_feature = None

        # Feature name mapping from markdown headers to POI names
        header_to_feature = {
            'Black Soil': 'BlackSoil',
            'Marsh': 'Marsh',
            'River': 'River',
            'River Spring': 'RiverSpring',
            'Cave': 'Cave',
            'Huge Trees': 'HugeTrees',
            'Dimension Stones': 'DimensionStones',
            'Clay': 'Clay',
            'Domesticable Animals': 'DomesticableAnimals',
            'Berry Bushes': 'BerryBushes',
            # Strategic Resources
            'Horse': 'Horse',
            'Copper': 'Copper',
            'Iron': 'Iron',
            'Coal': 'Coal',
            'Oil': 'Oil',
            'Uranium': 'Uranium',
            'Saltpetre': 'Saltpetre',
            # Luxury Resources
            'Salt': 'Salt',
            'Mercury': 'Mercury',
            'Marble': 'Marble',
            'Gold': 'Gold',
            'Lead': 'Lead',
            'Silver': 'Silver',
            'Gemstone': 'Gemstone',
            'Porcelain': 'Porcelain',
        }

        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Check for section headers (## Feature Name)
            if line.startswith('## '):
                header = line[3:].strip()
                # Remove emoji and extra text
                header = re.sub(r'[^\w\s/]', '', header).strip()
                # Handle "River / River Spring" type headers
                for key in header_to_feature:
                    if key in header:
                        current_feature = header_to_feature[key]
                        break
                else:
                    current_feature = None

            # Parse table rows (| Location | Lat | Lon |)
            if current_feature and '|' in line and not line.startswith('|--'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    try:
                        # parts[0] is empty, parts[1] is location, parts[2] is lat, parts[3] is lon
                        lat = float(parts[2])
                        lon = float(parts[3])
                        if self.add_feature(current_feature, lat, lon):
                            count += 1
                    except (ValueError, IndexError):
                        # Not a data row (header row or invalid)
                        pass

        print(f"  Loaded {count} features from {md_path.name}")
        return count

    def create_poi_texture(self, ukraine_mask: Optional[Dict[Tuple[int, int], bool]] = None) -> np.ndarray:
        """
        Create POI texture array.

        Args:
            ukraine_mask: Optional dict of {(col, row): is_land} to filter features

        Returns:
            numpy array of shape (height, width, 4) with RGBA values
        """
        # Initialize with zeros (no features)
        texture = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Set alpha to 255 for all pixels
        texture[:, :, 3] = 255

        placed = 0
        skipped_ocean = 0

        for col, row, poi_index in self.features:
            # Skip if outside Ukraine land mass
            if ukraine_mask and not ukraine_mask.get((col, row), False):
                skipped_ocean += 1
                continue

            # Set R channel to POI index
            texture[row, col, 0] = poi_index
            placed += 1

        print(f"  Placed {placed} features on land")
        if skipped_ocean > 0:
            print(f"  Skipped {skipped_ocean} features (in ocean/outside Ukraine)")

        return texture

    def get_feature_stats(self) -> Dict[str, int]:
        """Get statistics about features by type."""
        stats = {}
        for col, row, poi_index in self.features:
            # Find feature name
            for name, idx in POI_INDICES.items():
                if idx == poi_index:
                    stats[name] = stats.get(name, 0) + 1
                    break
        return stats


def main():
    """Test feature mapper."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    active = config['active_config']
    bounds = config['bounds'][active]
    grid_width = config['grid']['width']
    grid_height = config['grid']['height']

    print("=" * 60)
    print("FEATURE MAPPER TEST")
    print("=" * 60)

    mapper = FeatureMapper(bounds, grid_width, grid_height)

    # Load features from terrain modifiers document
    md_path = Path(__file__).parent / "data" / "humankind_ukraine_terrain_modifiers.md"
    mapper.load_from_markdown(md_path)

    # Print statistics
    print("\nFeature Statistics:")
    stats = mapper.get_feature_stats()
    for name, count in sorted(stats.items()):
        print(f"  {name}: {count}")

    # Create POI texture (without mask for testing)
    print("\nCreating POI texture...")
    texture = mapper.create_poi_texture()
    print(f"  Texture shape: {texture.shape}")

    # Count non-zero pixels
    non_zero = np.sum(texture[:, :, 0] > 0)
    print(f"  Non-zero pixels: {non_zero}")


if __name__ == "__main__":
    main()
