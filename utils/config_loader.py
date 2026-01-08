"""
Configuration loader for Humankind Ukraine map project.

Loads configuration from config.yaml and provides easy access to parameters.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class Config:
    """Configuration loader and accessor."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = Path(config_path)
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)

        # Determine which configuration to use
        self.active = self._config.get('active_config', 'new')

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.

        Examples:
            config.get('grid.width') -> 150
            config.get('bounds.new.min_lon') -> 22.0

        Args:
            path: Dot-separated path to configuration value
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        parts = path.split('.')
        value = self._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    @property
    def grid_width(self) -> int:
        """Get grid width in hexes."""
        return self.get('grid.width', 150)

    @property
    def grid_height(self) -> int:
        """Get grid height in hexes."""
        return self.get('grid.height', 88)

    @property
    def map_bounds(self) -> Dict[str, float]:
        """
        Get active map bounds.

        Returns:
            Dictionary with min_lon, max_lon, min_lat, max_lat
        """
        bounds = self.get(f'bounds.{self.active}', {})
        return {
            'min_lon': bounds.get('min_lon', 22.0),
            'max_lon': bounds.get('max_lon', 40.5),
            'min_lat': bounds.get('min_lat', 44.0),
            'max_lat': bounds.get('max_lat', 52.5),
        }

    @property
    def margins(self) -> Dict[str, int]:
        """
        Get active margins in hexes.

        Returns:
            Dictionary with north, south, east, west margins
        """
        margins = self.get(f'margins.{self.active}', {})
        return {
            'north': margins.get('north', 6),
            'south': margins.get('south', 6),
            'east': margins.get('east', 6),
            'west': margins.get('west', 6),
        }

    @property
    def ukraine_bounds(self) -> Dict[str, float]:
        """
        Get Ukraine's actual geographic bounds.

        Returns:
            Dictionary with min_lon, max_lon, min_lat, max_lat
        """
        # Ukraine's approximate boundaries
        return {
            'min_lon': 22.0,
            'max_lon': 40.5,
            'min_lat': 44.0,
            'max_lat': 52.5,
        }

    @property
    def cities(self) -> List[Dict[str, Any]]:
        """
        Get list of major cities.

        Returns:
            List of city dictionaries with name, lat, lon
        """
        return self.get('cities', [])

    @property
    def raions_file(self) -> Path:
        """Get path to raions GeoJSON file."""
        return Path(self.get('ukraine.raions_file', 'data/ukraine_raions.geojson'))

    @property
    def projection_input_crs(self) -> str:
        """Get input CRS (WGS84)."""
        return self.get('projection.input_crs', 'EPSG:4326')

    @property
    def projection_output_crs(self) -> str:
        """Get projected CRS (UTM 36N)."""
        return self.get('projection.projected_crs', 'EPSG:32636')

    @property
    def hex_orientation(self) -> str:
        """Get hexagon orientation (flat-top or pointy-top)."""
        return self.get('hexagon.orientation', 'flat-top')

    @property
    def visualization_output_dir(self) -> Path:
        """Get visualization output directory."""
        return Path(self.get('visualization.output_dir', 'tests/test_outputs'))

    @property
    def hex_pixel_size(self) -> int:
        """Get hex size in pixels for visualizations."""
        return self.get('visualization.hex_pixel_size', 10)

    def __repr__(self) -> str:
        """String representation."""
        return f"Config(active='{self.active}', bounds={self.map_bounds})"


# Global config instance
_config_instance = None


def get_config(config_path: str = "config.yaml") -> Config:
    """
    Get or create global config instance.

    Args:
        config_path: Path to config file

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance


def reload_config(config_path: str = "config.yaml") -> Config:
    """
    Reload configuration from file.

    Args:
        config_path: Path to config file

    Returns:
        New Config instance
    """
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance


if __name__ == "__main__":
    # Test config loader
    config = get_config()
    print(f"Config loaded: {config}")
    print(f"Grid: {config.grid_width}×{config.grid_height}")
    print(f"Bounds: {config.map_bounds}")
    print(f"Margins: {config.margins}")
    print(f"Cities: {len(config.cities)}")
