"""
Geographic coordinate to hexagonal grid mapping.

Converts between lat/lon coordinates and hex grid coordinates,
using appropriate projections for accurate distance calculations.
"""

from typing import Tuple

import numpy as np
from pyproj import Transformer

from hex_grid import HexGrid


class GeoHexMapper:
    """
    Maps between geographic coordinates (lat/lon) and hex grid coordinates.

    Uses UTM projection for accurate distance calculations within Ukraine.
    """

    def __init__(
        self,
        width: int,
        height: int,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
        projected_crs: str = "EPSG:32636",  # UTM Zone 36N for Ukraine
    ):
        """
        Initialize geo-hex mapper.

        Args:
            width: Number of hex columns
            height: Number of hex rows
            min_lon: Minimum longitude (west bound)
            max_lon: Maximum longitude (east bound)
            min_lat: Minimum latitude (south bound)
            max_lat: Maximum latitude (north bound)
            projected_crs: Projected CRS to use (default: UTM 36N for Ukraine)
        """
        self.width = width
        self.height = height
        self.min_lon = min_lon
        self.max_lon = max_lon
        self.min_lat = min_lat
        self.max_lat = max_lat
        self.projected_crs = projected_crs

        # Create transformer from WGS84 to projected CRS
        self.to_projected = Transformer.from_crs(
            "EPSG:4326",  # WGS84
            projected_crs,
            always_xy=True
        )

        # Create transformer from projected CRS back to WGS84
        self.to_wgs84 = Transformer.from_crs(
            projected_crs,
            "EPSG:4326",  # WGS84
            always_xy=True
        )

        # Calculate bounds in projected coordinates
        self.min_x, self.min_y = self.to_projected.transform(min_lon, min_lat)
        self.max_x, self.max_y = self.to_projected.transform(max_lon, max_lat)

        # Calculate hex size to fit the bounding box
        # We want to cover the geographic area with the hex grid
        self._calculate_hex_grid()

    def _calculate_hex_grid(self):
        """Calculate hex grid parameters to fit the geographic bounds."""
        # Calculate dimensions in projected coordinates (meters)
        width_m = self.max_x - self.min_x
        height_m = self.max_y - self.min_y

        # For pointy-top hexagons:
        # - Horizontal spacing: hex_width = hex_size * sqrt(3)
        # - Vertical spacing: 0.75 * hex_height = 0.75 * (2 * hex_size)
        #
        # Grid width in meters: width * hex_width = width * hex_size * sqrt(3)
        # Grid height in meters: (height - 1) * 0.75 * hex_height + hex_height
        #                       = height * hex_height - 0.25 * hex_height
        #                       = (height - 0.25) * 2 * hex_size

        # Solve for hex_size based on width constraint
        hex_size_from_width = width_m / (self.width * np.sqrt(3))

        # Solve for hex_size based on height constraint
        hex_size_from_height = height_m / ((self.height - 0.25) * 2)

        # Use the smaller to ensure grid fits within bounds
        self.hex_size_m = min(hex_size_from_width, hex_size_from_height)

        # Create hex grid in projected space
        self.hex_grid = HexGrid(
            width=self.width,
            height=self.height,
            hex_size=self.hex_size_m
        )

        # Calculate offset to center the grid in the bounding box
        grid_bounds = self.hex_grid.pixel_bounds()
        grid_width = grid_bounds[2] - grid_bounds[0]
        grid_height = grid_bounds[3] - grid_bounds[1]

        # Center the grid
        self.offset_x = self.min_x + (width_m - grid_width) / 2 - grid_bounds[0]
        self.offset_y = self.min_y + (height_m - grid_height) / 2 - grid_bounds[1]

    @property
    def hex_size_km(self) -> float:
        """Get hex size in kilometers."""
        return self.hex_size_m / 1000

    def latlon_to_projected(self, lat: float, lon: float) -> Tuple[float, float]:
        """
        Convert lat/lon to projected coordinates (meters).

        Args:
            lat: Latitude (degrees)
            lon: Longitude (degrees)

        Returns:
            (x, y) in projected coordinates (meters)
        """
        x, y = self.to_projected.transform(lon, lat)
        return (x, y)

    def projected_to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert projected coordinates to lat/lon.

        Args:
            x, y: Projected coordinates (meters)

        Returns:
            (lat, lon) in degrees
        """
        lon, lat = self.to_wgs84.transform(x, y)
        return (lat, lon)

    def latlon_to_hex(self, lat: float, lon: float) -> Tuple[int, int]:
        """
        Convert geographic coordinates to hex grid coordinates.

        Args:
            lat: Latitude (degrees)
            lon: Longitude (degrees)

        Returns:
            (col, row) hex offset coordinates
        """
        # Convert to projected coordinates
        x, y = self.latlon_to_projected(lat, lon)

        # Invert Y because latitude increases northward but row increases southward
        # Map max_y to row 0 and min_y to row (height-1)
        y_inverted = self.max_y - y + self.min_y

        # Adjust for grid offset
        x -= self.offset_x
        y_inverted -= self.offset_y

        # Convert to hex coordinates
        col, row = self.hex_grid.pixel_to_offset(x, y_inverted)

        return (col, row)

    def hex_to_latlon(self, col: int, row: int) -> Tuple[float, float]:
        """
        Convert hex grid coordinates to geographic coordinates (center of hex).

        Args:
            col: Hex column
            row: Hex row

        Returns:
            (lat, lon) in degrees
        """
        # Get hex center in grid pixel coordinates
        x, y = self.hex_grid.hex_center(col, row)

        # Adjust for grid offset
        x += self.offset_x
        y += self.offset_y

        # Invert Y back to geographic coordinates
        y_geo = self.max_y - y + self.min_y

        # Convert to lat/lon
        lat, lon = self.projected_to_latlon(x, y_geo)

        return (lat, lon)

    def hex_corners_latlon(self, col: int, row: int) -> list[Tuple[float, float]]:
        """
        Get corners of a hex in lat/lon coordinates.

        Args:
            col: Hex column
            row: Hex row

        Returns:
            List of 6 (lat, lon) tuples for hex corners
        """
        # Get corners in grid pixel coordinates
        corners_xy = self.hex_grid.hex_corners(col, row)

        # Convert each corner to lat/lon
        corners_latlon = []
        for x, y in corners_xy:
            # Adjust for grid offset
            x += self.offset_x
            y += self.offset_y

            # Invert Y back to geographic coordinates
            y_geo = self.max_y - y + self.min_y

            # Convert to lat/lon
            lat, lon = self.projected_to_latlon(x, y_geo)
            corners_latlon.append((lat, lon))

        return corners_latlon
