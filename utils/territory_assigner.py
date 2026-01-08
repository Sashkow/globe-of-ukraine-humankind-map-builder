"""
Territory assignment system for mapping hexes to raion territories.

This module handles the core algorithm for assigning each hex in the grid
to the appropriate Ukrainian raion (district) based on geographic containment.
"""

from typing import Dict, Tuple, Optional
import geopandas as gpd
from shapely.geometry import Point
from geo_hex_mapper import GeoHexMapper


class TerritoryAssigner:
    """
    Assigns hexes to raion territories based on geographic containment.

    Uses point-in-polygon testing to determine which raion contains
    each hex's centroid.
    """

    def __init__(self, mapper: GeoHexMapper, raion_gdf: gpd.GeoDataFrame):
        """
        Initialize territory assigner.

        Args:
            mapper: GeoHexMapper for coordinate conversion
            raion_gdf: GeoDataFrame with raion geometries
        """
        self.mapper = mapper
        self.raion_gdf = raion_gdf
        self.hex_to_raion: Dict[Tuple[int, int], int] = {}

    def assign_all_hexes(self) -> Dict[Tuple[int, int], int]:
        """
        Assign all hexes in the grid to raions.

        Returns:
            Dictionary mapping (col, row) -> raion_index
            Hexes not in any raion are excluded (ocean/buffer)
        """
        print(f"\nAssigning {self.mapper.width * self.mapper.height} hexes to {len(self.raion_gdf)} raions...")

        self.hex_to_raion = {}

        for row in range(self.mapper.height):
            if row % 10 == 0:
                print(f"  Processing row {row}/{self.mapper.height}")

            for col in range(self.mapper.width):
                raion_idx = self._find_containing_raion(col, row)
                if raion_idx is not None:
                    self.hex_to_raion[(col, row)] = raion_idx

        ukraine_hexes = len(self.hex_to_raion)
        total_hexes = self.mapper.width * self.mapper.height
        ocean_hexes = total_hexes - ukraine_hexes
        coverage_percent = 100 * ukraine_hexes / total_hexes

        print(f"\n✓ Assignment complete:")
        print(f"  Total hexes: {total_hexes}")
        print(f"  Ukraine hexes: {ukraine_hexes} ({coverage_percent:.1f}%)")
        print(f"  Ocean/buffer hexes: {ocean_hexes} ({100-coverage_percent:.1f}%)")

        return self.hex_to_raion

    def _find_containing_raion(self, col: int, row: int) -> Optional[int]:
        """
        Find which raion contains the given hex.

        Args:
            col: Hex column
            row: Hex row

        Returns:
            Raion index (GeoDataFrame index) or None if not in any raion
        """
        # Get hex center in lat/lon
        lat, lon = self.mapper.hex_to_latlon(col, row)
        point = Point(lon, lat)

        # Test against all raions
        for idx, raion in self.raion_gdf.iterrows():
            if raion.geometry.contains(point):
                return idx

        return None

    def get_raion_hex_counts(self) -> Dict[int, int]:
        """
        Count hexes assigned to each raion.

        Returns:
            Dictionary mapping raion_index -> hex_count
        """
        raion_counts = {}
        for raion_idx in self.hex_to_raion.values():
            raion_counts[raion_idx] = raion_counts.get(raion_idx, 0) + 1
        return raion_counts

    def get_statistics(self) -> Dict[str, any]:
        """
        Calculate assignment statistics.

        Returns:
            Dictionary with various statistics
        """
        raion_counts = self.get_raion_hex_counts()
        hex_counts = list(raion_counts.values())

        total_hexes = self.mapper.width * self.mapper.height
        ukraine_hexes = len(self.hex_to_raion)

        stats = {
            "total_hexes": total_hexes,
            "ukraine_hexes": ukraine_hexes,
            "ocean_hexes": total_hexes - ukraine_hexes,
            "coverage_percent": 100 * ukraine_hexes / total_hexes,
            "raions_with_hexes": len(raion_counts),
            "total_raions": len(self.raion_gdf),
            "raions_without_hexes": len(self.raion_gdf) - len(raion_counts),
        }

        if hex_counts:
            stats.update({
                "min_hexes_per_raion": min(hex_counts),
                "max_hexes_per_raion": max(hex_counts),
                "avg_hexes_per_raion": sum(hex_counts) / len(hex_counts),
                "median_hexes_per_raion": sorted(hex_counts)[len(hex_counts) // 2],
            })

        return stats

    def print_statistics(self):
        """Print detailed statistics about the assignment."""
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print("TERRITORY ASSIGNMENT STATISTICS")
        print("=" * 70)

        print(f"\nGrid Coverage:")
        print(f"  Total hexes:        {stats['total_hexes']:>6}")
        print(f"  Ukraine hexes:      {stats['ukraine_hexes']:>6} ({stats['coverage_percent']:.1f}%)")
        print(f"  Ocean/buffer hexes: {stats['ocean_hexes']:>6} ({100-stats['coverage_percent']:.1f}%)")

        print(f"\nRaion Coverage:")
        print(f"  Total raions:            {stats['total_raions']:>3}")
        print(f"  Raions with hexes:       {stats['raions_with_hexes']:>3}")
        print(f"  Raions without hexes:    {stats['raions_without_hexes']:>3}")

        if "min_hexes_per_raion" in stats:
            print(f"\nHexes per Raion:")
            print(f"  Minimum:  {stats['min_hexes_per_raion']:>3} hexes")
            print(f"  Maximum:  {stats['max_hexes_per_raion']:>3} hexes")
            print(f"  Average:  {stats['avg_hexes_per_raion']:>6.1f} hexes")
            print(f"  Median:   {stats['median_hexes_per_raion']:>3} hexes")

        print("=" * 70)

    def get_raion_sizes_by_oblast(self, oblast_field: str, name_field: str) -> Dict[str, list]:
        """
        Group raion sizes by oblast.

        Args:
            oblast_field: Column name for oblast
            name_field: Column name for raion name

        Returns:
            Dictionary mapping oblast -> list of (raion_name, hex_count)
        """
        raion_counts = self.get_raion_hex_counts()

        oblast_data = {}
        for raion_idx, hex_count in raion_counts.items():
            raion = self.raion_gdf.loc[raion_idx]
            oblast = raion[oblast_field]
            raion_name = raion[name_field]

            if oblast not in oblast_data:
                oblast_data[oblast] = []

            oblast_data[oblast].append((raion_name, hex_count))

        # Sort raions within each oblast by hex count
        for oblast in oblast_data:
            oblast_data[oblast].sort(key=lambda x: x[1], reverse=True)

        return oblast_data
