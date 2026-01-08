#!/usr/bin/env python3
"""
Tests for Copernicus land cover data accuracy.

Verifies that the fetched Copernicus CGLS-LC100 data correctly identifies:
- Known land locations as land (not water classes)
- Known water locations as water (ocean/sea classes)
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_fetchers.landcover_fetcher_copernicus import (
    CopernicusLandCoverFetcher,
    CopernicusLandCoverClass,
)


# Copernicus water classes (should NOT appear on land)
WATER_CLASSES = {80, 90, 200}  # Permanent water, Wetland, Oceans/seas

# Copernicus land classes (should NOT appear in open sea)
LAND_CLASSES = {20, 30, 40, 50, 60, 70, 100, 111, 112, 113, 114, 115, 116, 121, 122, 123, 124, 125, 126}


@pytest.fixture(scope="module")
def ukraine_bounds():
    """Ukraine map bounds from config."""
    return {
        'min_lon': 20,
        'max_lon': 44,
        'min_lat': 43,
        'max_lat': 53,
    }


@pytest.fixture(scope="module")
def fetcher(ukraine_bounds):
    """Copernicus land cover fetcher instance."""
    return CopernicusLandCoverFetcher(ukraine_bounds)


class TestKnownLandLocations:
    """Test that known land locations are NOT classified as water."""

    # Known Ukrainian cities and land points (lon, lat, name)
    # Note: coordinates must be precise to avoid hitting reservoirs/rivers
    LAND_POINTS = [
        (30.5234, 50.4501, "Kyiv"),
        (36.2304, 49.9935, "Kharkiv"),
        (35.0462, 48.4647, "Dnipro"),
        (30.7233, 46.4825, "Odesa"),
        (24.0297, 49.8397, "Lviv"),
        (34.0987, 44.9572, "Simferopol (Crimea)"),
        (37.5498, 47.0971, "Mariupol (city center)"),  # Adjusted coordinates
        (32.0597, 46.9659, "Mykolaiv"),
        (35.1396, 47.8388, "Zaporizhzhia"),
        (24.7111, 48.9226, "Ivano-Frankivsk"),
        # Rural land points (avoiding major reservoirs)
        (32.5, 49.5, "Central Ukraine (farmland - Poltava oblast)"),
        (28.0, 51.0, "Polesia (forest)"),
        (37.0, 48.0, "Donbas (steppe)"),
        (23.5, 48.5, "Carpathian foothills"),
        (33.5, 47.5, "Southern steppe (Zaporizhzhia oblast)"),
    ]

    @pytest.mark.parametrize("lon,lat,name", LAND_POINTS)
    def test_land_not_classified_as_water(self, fetcher, lon, lat, name):
        """Known land locations should NOT have water land cover class."""
        landcover = fetcher.get_landcover_at(lon, lat)

        assert landcover not in WATER_CLASSES, (
            f"{name} ({lon}, {lat}) incorrectly classified as water! "
            f"Got class {landcover} ({CopernicusLandCoverClass.NAMES.get(landcover, 'Unknown')})"
        )


class TestKnownWaterLocations:
    """Test that known water locations ARE classified as water."""

    # Known water points in Black Sea and Sea of Azov (lon, lat, name)
    # Note: coordinates must be well into open water, not near coasts
    WATER_POINTS = [
        (31.0, 44.0, "Black Sea (south)"),
        (33.0, 43.5, "Black Sea (far south)"),  # Well into open sea
        (30.0, 45.0, "Black Sea (west)"),
        (37.0, 45.0, "Black Sea (east)"),  # Adjusted south to avoid coast
        (36.0, 46.0, "Sea of Azov (center)"),  # More central
        (37.5, 46.3, "Sea of Azov (east)"),  # Adjusted
        (35.8, 45.8, "Kerch Strait area"),  # Adjusted
    ]

    @pytest.mark.parametrize("lon,lat,name", WATER_POINTS)
    def test_water_classified_as_water(self, fetcher, lon, lat, name):
        """Known water locations should have water land cover class (80, 90, or 200)."""
        landcover = fetcher.get_landcover_at(lon, lat)

        assert landcover in WATER_CLASSES, (
            f"{name} ({lon}, {lat}) should be water but got class {landcover} "
            f"({CopernicusLandCoverClass.NAMES.get(landcover, 'Unknown')})"
        )


class TestLandCoverDistribution:
    """Test overall land cover distribution for Ukraine."""

    def test_grid_has_reasonable_land_water_ratio(self, fetcher):
        """Grid should have reasonable land/water ratio for Ukraine bounds."""
        grid = fetcher.get_grid_landcover(150, 88)

        total = grid.size
        water_count = sum(1 for val in grid.flat if val in WATER_CLASSES)
        land_count = total - water_count

        land_pct = land_count / total * 100
        water_pct = water_count / total * 100

        # Ukraine bounds (20-44E, 43-53N) include mostly land with Black Sea in south
        # Copernicus grid shows ~85% land, ~15% water which is reasonable
        assert 50 <= land_pct <= 95, (
            f"Unexpected land percentage: {land_pct:.1f}% "
            f"(expected 50-95% for Ukraine bounds)"
        )
        assert 5 <= water_pct <= 50, (
            f"Unexpected water percentage: {water_pct:.1f}% "
            f"(expected 5-50% for Ukraine bounds)"
        )

    def test_grid_has_forests(self, fetcher):
        """Grid should have some forest coverage (Carpathians, Polesia)."""
        grid = fetcher.get_grid_landcover(150, 88)

        forest_classes = {111, 112, 113, 114, 115, 116, 121, 122, 123, 124, 125, 126}
        forest_count = sum(1 for val in grid.flat if val in forest_classes)
        forest_pct = forest_count / grid.size * 100

        # Ukraine should have at least 5% forest
        assert forest_pct >= 5, (
            f"Too little forest: {forest_pct:.1f}% (expected >= 5%)"
        )

    def test_grid_has_cropland(self, fetcher):
        """Grid should have significant cropland (Ukraine is agricultural)."""
        grid = fetcher.get_grid_landcover(150, 88)

        cropland_count = sum(1 for val in grid.flat if val == 40)
        cropland_pct = cropland_count / grid.size * 100

        # Ukraine is heavily agricultural - should have at least 20% cropland
        assert cropland_pct >= 20, (
            f"Too little cropland: {cropland_pct:.1f}% (expected >= 20%)"
        )


class TestCoastalBoundary:
    """Test land/water classification near coastal boundaries."""

    # Coastal points that should be LAND (ports, coastal cities)
    # Note: use city centers, not harbor areas which may show as water
    COASTAL_LAND = [
        (30.7326, 46.4775, "Odesa (city center)"),
        (33.5224, 44.6054, "Sevastopol (city center)"),
        (36.4681, 45.3567, "Kerch (city center)"),
    ]

    # Points that should definitely be WATER (open sea)
    COASTAL_WATER = [
        (30.5, 44.5, "Black Sea off Odesa (far)"),
        (33.5, 43.5, "Black Sea south of Crimea"),
    ]

    @pytest.mark.parametrize("lon,lat,name", COASTAL_LAND)
    def test_coastal_cities_are_land(self, fetcher, lon, lat, name):
        """Coastal cities should be classified as land."""
        landcover = fetcher.get_landcover_at(lon, lat)

        # Should be urban (50) or other land class
        assert landcover not in {200}, (  # Ocean class
            f"{name} ({lon}, {lat}) classified as ocean! "
            f"Got class {landcover} ({CopernicusLandCoverClass.NAMES.get(landcover, 'Unknown')})"
        )

    @pytest.mark.parametrize("lon,lat,name", COASTAL_WATER)
    def test_open_sea_is_water(self, fetcher, lon, lat, name):
        """Open sea should be classified as ocean."""
        landcover = fetcher.get_landcover_at(lon, lat)

        assert landcover == 200, (
            f"{name} ({lon}, {lat}) should be ocean but got class {landcover} "
            f"({CopernicusLandCoverClass.NAMES.get(landcover, 'Unknown')})"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
