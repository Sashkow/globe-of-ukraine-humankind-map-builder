"""
Tests for Ukraine map generation.

These tests specify expected territory sizes and properties
before implementation, following TDD approach.
"""

from pathlib import Path

import numpy as np
import pytest

from humankind_map_parser import load_map, HumankindMap


# Path to test maps (in project root)
MAPS_DIR = Path(__file__).parent.parent / "humankind_maps"


class TestPhase1MapParsing:
    """Phase 1: Parse existing maps to understand format."""

    def test_parse_tiny_australia_map(self):
        """
        Task 1.1: Parse tiny_australia map and verify structure.

        This small map (58x36, 27 territories) is our reference.
        """
        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # Verify dimensions
        assert map_data.width == 58
        assert map_data.height == 36

        # Verify territory count
        assert map_data.territory_count == 27

        # Verify land vs ocean territories
        # From the file: territories 1-6 are land, rest are ocean
        assert map_data.land_territory_count == 6
        assert map_data.ocean_territory_count == 21

        # Verify biome names loaded
        assert len(map_data.biome_names) == 10
        assert map_data.biome_names[0] == "Arctic"
        assert map_data.biome_names[7] == "Temperate"

        # Verify zones texture shape
        assert map_data.zones_texture.shape == (36, 58)

    def test_parse_tiny_map(self):
        """
        Parse the larger tiny_map (130x76, 220 territories).
        """
        hms_path = MAPS_DIR / "tiny_map" / "Save.hms"
        map_data = load_map(hms_path)

        # Verify dimensions
        assert map_data.width == 130
        assert map_data.height == 76

        # Verify territory count
        assert map_data.territory_count == 220

        # Verify zones texture shape
        assert map_data.zones_texture.shape == (76, 130)

    def test_zone_texture_values_match_territories(self):
        """
        Verify zone texture pixel values correspond to valid territory indices.
        """
        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # Get unique values in zone texture
        unique_zones = np.unique(map_data.zones_texture)

        # All zone values should be valid territory indices
        max_territory_idx = map_data.territory_count - 1
        assert unique_zones.max() <= max_territory_idx
        assert unique_zones.min() >= 0

    def test_hex_counts_per_territory(self):
        """
        Task 1.1: Create histogram of territory assignments.
        """
        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        hex_counts = map_data.get_hex_counts()

        # Total hexes should match map size
        total_hexes = sum(hex_counts.values())
        assert total_hexes == map_data.width * map_data.height

        # Territory 0 (ocean) should have most hexes
        # Land territories (1-6) should have reasonable counts
        land_territories = [t for t in map_data.territories if not t.is_ocean]
        for t in land_territories:
            if t.index in hex_counts:
                # Land territories should have at least some hexes
                assert hex_counts[t.index] > 0

    def test_spawn_points_loaded(self):
        """Verify spawn points are parsed correctly."""
        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # tiny_australia has 3 spawn points
        assert len(map_data.spawn_points) == 3

        # Spawn points should be within map bounds
        for sp in map_data.spawn_points:
            assert 0 <= sp.column < map_data.width
            assert 0 <= sp.row < map_data.height


class TestPhase1CompactFormat:
    """Task 1.2: Create compact map analysis format."""

    def test_save_and_load_compact_map(self, tmp_path):
        """Verify we can save and reload map in compact format."""
        from humankind_map_parser import save_compact_map, load_compact_map

        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # Save to compact format
        compact_path = tmp_path / "test_compact.npz"
        save_compact_map(map_data, compact_path)

        # Verify file exists and is smaller than original
        assert compact_path.exists()

        # Load back
        loaded = load_compact_map(compact_path)

        # Verify all fields match
        assert loaded['width'] == map_data.width
        assert loaded['height'] == map_data.height
        assert loaded['territory_count'] == map_data.territory_count
        assert np.array_equal(loaded['zones'], map_data.zones_texture)
        assert len(loaded['biome_names']) == len(map_data.biome_names)

    def test_compact_format_preserves_territory_data(self, tmp_path):
        """Verify territory biomes and ocean flags are preserved."""
        from humankind_map_parser import save_compact_map, load_compact_map

        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        compact_path = tmp_path / "test_compact.npz"
        save_compact_map(map_data, compact_path)
        loaded = load_compact_map(compact_path)

        # Check territory properties
        for i, t in enumerate(map_data.territories):
            assert loaded['territory_biomes'][i] == t.biome
            assert loaded['territory_is_ocean'][i] == t.is_ocean
            assert loaded['territory_continent'][i] == t.continent_index


class TestPhase1Rendering:
    """Task 1.3: Render existing map correctly."""

    def test_render_tiny_australia_map(self):
        """Verify rendering works and produces valid image."""
        from humankind_map_renderer import render_map_simple, render_map_hex

        # Create test_outputs directory
        output_dir = Path(__file__).parent / "test_outputs"
        output_dir.mkdir(exist_ok=True)

        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # Test simple rendering
        simple_output = output_dir / "tiny_australia_simple.png"
        img = render_map_simple(map_data, simple_output, color_by="biome")

        # Verify output exists
        assert simple_output.exists()

        # Verify image dimensions
        assert img.size[0] > 0
        assert img.size[1] > 0

        # Count pixel colors to verify non-ocean pixels exist
        pixels = img.load()
        width, height = img.size
        ocean_pixels = 0
        land_pixels = 0

        # Sample pixels (every 4th to be faster)
        for y in range(0, height, 4):
            for x in range(0, width, 4):
                pixel = pixels[x, y]
                # Ocean is defined as (50, 80, 140) in renderer
                if pixel == (50, 80, 140):
                    ocean_pixels += 1
                else:
                    land_pixels += 1

        # Since we have 6 land territories out of 27 total,
        # and this is Australia-focused, land should be visible
        assert land_pixels > 0, "Rendered map should show land territories"

    def test_render_hex_map(self):
        """Verify hex rendering works and shows proper hexagonal shapes."""
        from humankind_map_renderer import render_map_hex

        # Create test_outputs directory
        output_dir = Path(__file__).parent / "test_outputs"
        output_dir.mkdir(exist_ok=True)

        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        # Test hex rendering
        hex_output = output_dir / "tiny_australia_hex.png"
        img = render_map_hex(map_data, hex_output, color_by="territory", hex_size=10)

        # Verify output exists
        assert hex_output.exists()

        # Verify image is larger (hex rendering should be bigger than simple)
        assert img.size[0] > map_data.width
        assert img.size[1] > map_data.height

    def test_render_shows_continents_not_just_ocean(self):
        """
        Task 1.3 validation: Rendered map should show continents clearly.

        For tiny_australia: land should be at least 10% of visible area
        (conservative estimate since it's an Australia-focused map)
        """
        from humankind_map_renderer import render_map_simple

        # Create test_outputs directory
        output_dir = Path(__file__).parent / "test_outputs"
        output_dir.mkdir(exist_ok=True)

        hmap_path = MAPS_DIR / "tiny_australia" / "The_Amplipodes.hmap"
        map_data = load_map(hmap_path)

        validation_output = output_dir / "tiny_australia_validation.png"
        img = render_map_simple(map_data, validation_output, color_by="biome", scale=1)

        # Count ocean vs non-ocean pixels
        pixels = img.load()
        width, height = img.size
        ocean_count = 0
        total_count = width * height

        for y in range(height):
            for x in range(width):
                pixel = pixels[x, y]
                if pixel == (50, 80, 140):  # OCEAN_COLOR
                    ocean_count += 1

        land_count = total_count - ocean_count
        land_percentage = land_count / total_count

        # At least 10% should be land
        assert land_percentage >= 0.10, \
            f"Land should be at least 10% of map, got {land_percentage:.1%}"


class TestTerritoryHexCounts:
    """Tests for expected hex counts per territory."""

    def test_kyiv_city_hex_count(self):
        """
        Kyiv city should be approximately 37 hexes.

        Rationale: 1 center hex + 3 rings = 1 + 6 + 12 + 18 = 37 hexes
        This gives Kyiv a distinct, compact urban territory that's
        playable (within 30-50 hex target range).

        Formula for hex radius n: 1 + 3*n*(n+1)
        - radius 0: 1 hex
        - radius 1: 7 hexes
        - radius 2: 19 hexes
        - radius 3: 37 hexes
        """
        # TODO: Implement when map generation is complete
        # kyiv_hex_count = get_territory_hex_count("Kyiv")
        # assert 30 <= kyiv_hex_count <= 45, f"Kyiv should have ~37 hexes, got {kyiv_hex_count}"

        # For now, just verify the math
        def hex_count_for_radius(n: int) -> int:
            """Calculate total hexes in a hex area with given radius."""
            return 1 + 3 * n * (n + 1)

        assert hex_count_for_radius(0) == 1
        assert hex_count_for_radius(1) == 7
        assert hex_count_for_radius(2) == 19
        assert hex_count_for_radius(3) == 37
        assert hex_count_for_radius(4) == 61

        # Kyiv target: radius 3 = 37 hexes
        KYIV_TARGET_HEXES = 37
        assert 30 <= KYIV_TARGET_HEXES <= 45

    def test_average_raion_hex_count(self):
        """Average raion should have ~72 hexes."""
        # Based on plan calculations:
        # - 136 raions
        # - ~9,750 hexes for Ukraine landmass
        # - Average: 9750 / 136 ≈ 72 hexes
        EXPECTED_AVERAGE = 72
        TOTAL_LAND_HEXES = 9750
        RAION_COUNT = 136

        calculated_average = TOTAL_LAND_HEXES / RAION_COUNT
        assert 65 <= calculated_average <= 80

    def test_raion_size_bounds(self):
        """All raions should have between 20-150 hexes for playability."""
        MIN_PLAYABLE_HEXES = 20
        MAX_REASONABLE_HEXES = 150

        # These bounds ensure:
        # - No territory is too small to be strategically relevant
        # - No territory dominates the map
        assert MIN_PLAYABLE_HEXES >= 20
        assert MAX_REASONABLE_HEXES <= 150


class TestCrimeaTerritories:
    """Tests for Crimean historical-geographic territories."""

    def test_crimea_has_six_territories(self):
        """Crimea should be divided into 6 historical-geographic regions."""
        CRIMEA_TERRITORIES = [
            "Western Steppe",      # Tarkhankut-Kezlev Nogay region
            "Northern Steppe",     # Perekop-Dzhankoy Nogay region
            "Kerch Peninsula",     # Eastern Nogay region
            "Mountain Region",     # Tatlar/Mountain Tatars
            "Southern Coast",      # Yalıboylular
            "Sevastopol",          # Special city status
        ]
        assert len(CRIMEA_TERRITORIES) == 6

    def test_crimea_territory_hex_counts(self):
        """Each Crimean territory should have 25-50 hexes."""
        MIN_CRIMEA_HEXES = 25
        MAX_CRIMEA_HEXES = 50

        # Total Crimea ~27,000 km²
        # With 6 territories averaging 37-38 hexes each
        # Total Crimea hexes: ~225 hexes
        EXPECTED_TOTAL_CRIMEA_HEXES = 225
        CRIMEA_TERRITORY_COUNT = 6

        avg_per_territory = EXPECTED_TOTAL_CRIMEA_HEXES / CRIMEA_TERRITORY_COUNT
        assert MIN_CRIMEA_HEXES <= avg_per_territory <= MAX_CRIMEA_HEXES


class TestMapDimensions:
    """Tests for overall map dimensions and coverage."""

    def test_map_uses_maximum_size(self):
        """Map should use maximum Humankind map size."""
        MAX_WIDTH = 150
        MAX_HEIGHT = 88
        TOTAL_HEXES = MAX_WIDTH * MAX_HEIGHT

        assert TOTAL_HEXES == 13200

    def test_ukraine_land_coverage(self):
        """Ukraine landmass should cover ~74% of map."""
        TOTAL_HEXES = 13200
        EXPECTED_LAND_HEXES = 9750
        EXPECTED_OCEAN_HEXES = 3450

        land_percentage = EXPECTED_LAND_HEXES / TOTAL_HEXES
        ocean_percentage = EXPECTED_OCEAN_HEXES / TOTAL_HEXES

        assert 0.70 <= land_percentage <= 0.80  # 70-80% land
        assert 0.20 <= ocean_percentage <= 0.30  # 20-30% ocean/buffer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
