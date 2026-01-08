"""
Tests for configuration system.
"""

import pytest
from pathlib import Path

from utils.config_loader import get_config, reload_config
from utils.geo_hex_mapper import GeoHexMapper


class TestConfigLoader:
    """Test configuration loading and access."""

    def test_config_loads(self):
        """Test that config.yaml loads successfully."""
        config = get_config()
        assert config is not None
        assert config.active in ['new', 'original']

    def test_grid_dimensions(self):
        """Test grid dimensions from config."""
        config = get_config()
        assert config.grid_width == 150
        assert config.grid_height == 88

    def test_map_bounds(self):
        """Test map bounds are accessible."""
        config = get_config()
        bounds = config.map_bounds

        assert 'min_lon' in bounds
        assert 'max_lon' in bounds
        assert 'min_lat' in bounds
        assert 'max_lat' in bounds

        # Bounds should be valid
        assert bounds['min_lon'] < bounds['max_lon']
        assert bounds['min_lat'] < bounds['max_lat']

    def test_cities_list(self):
        """Test cities list is accessible."""
        config = get_config()
        cities = config.cities

        assert len(cities) == 15
        assert all('name' in city for city in cities)
        assert all('lat' in city for city in cities)
        assert all('lon' in city for city in cities)

    def test_mapper_from_config(self):
        """Test creating GeoHexMapper from config."""
        config = get_config()

        mapper = GeoHexMapper(
            width=config.grid_width,
            height=config.grid_height,
            **config.map_bounds
        )

        assert mapper is not None
        assert mapper.width == 150
        assert mapper.height == 88


class TestConfigComparison:
    """Compare original vs new configuration."""

    def test_compare_configs(self):
        """Compare original and new configurations side by side."""
        # Load original config
        config_orig = get_config()
        config_orig._config['active_config'] = 'original'

        # Load new config
        config_new = reload_config()

        print("\n" + "="*70)
        print("CONFIGURATION COMPARISON: Original vs New")
        print("="*70)

        # Original
        mapper_orig = GeoHexMapper(
            width=config_orig.grid_width,
            height=config_orig.grid_height,
            min_lon=19.0, max_lon=43.5, min_lat=42.5, max_lat=54.0
        )

        # New
        mapper_new = GeoHexMapper(
            width=config_new.grid_width,
            height=config_new.grid_height,
            **config_new.map_bounds
        )

        print(f"\n{'Metric':<30} {'Original':>15} {'New':>15} {'Change':>15}")
        print("-"*70)

        # Bounds
        print(f"{'Longitude Range':<30} "
              f"{'19.0-43.5°':>15} "
              f"{'22.0-40.5°':>15} "
              f"{'Tighter':>15}")
        print(f"{'Latitude Range':<30} "
              f"{'42.5-54.0°':>15} "
              f"{'44.0-52.5°':>15} "
              f"{'Tighter':>15}")

        # Hex size
        print(f"{'Hex Size (km)':<30} "
              f"{mapper_orig.hex_size_km:>15.2f} "
              f"{mapper_new.hex_size_km:>15.2f} "
              f"{mapper_new.hex_size_km - mapper_orig.hex_size_km:>+15.2f}")

        # Expected results from config
        orig_results = config_orig.get('expected_results.original', {})
        new_results = config_new.get('expected_results.new', {})

        print(f"{'Ukraine Hexes':<30} "
              f"{orig_results.get('ukraine_hexes', 0):>15} "
              f"{new_results.get('ukraine_hexes', 0):>15} "
              f"{new_results.get('ukraine_hexes', 0) - orig_results.get('ukraine_hexes', 0):>+15}")

        print(f"{'Coverage %':<30} "
              f"{orig_results.get('coverage_percent', 0):>15.1f} "
              f"{new_results.get('coverage_percent', 0):>15.1f} "
              f"{new_results.get('coverage_percent', 0) - orig_results.get('coverage_percent', 0):>+15.1f}")

        print(f"{'Hexes per Raion':<30} "
              f"{orig_results.get('hexes_per_raion', 0):>15.1f} "
              f"{new_results.get('hexes_per_raion', 0):>15.1f} "
              f"{new_results.get('hexes_per_raion', 0) - orig_results.get('hexes_per_raion', 0):>+15.1f}")

        print("="*70)
        print("\nConclusion:")
        print(f"  • New config provides +{new_results.get('ukraine_hexes', 0) - orig_results.get('ukraine_hexes', 0)} more hexes for Ukraine")
        print(f"  • Hexes per raion: {new_results.get('hexes_per_raion', 0):.1f} (target range: 50-90)")
        print(f"  • Smaller hexes: {mapper_new.hex_size_km:.2f} km vs {mapper_orig.hex_size_km:.2f} km")
        print("="*70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
