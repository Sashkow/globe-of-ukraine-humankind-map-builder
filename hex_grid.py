"""
Hexagonal grid coordinate system for Humankind maps.

Implements flat-top hexagons with odd-q offset coordinates,
matching the coordinate system used by Humankind.

Coordinate Systems:
- Offset (col, row): Game grid coordinates (0-based)
- Pixel (x, y): World/screen coordinates
- Cube (q, r, s): For distance calculations (q+r+s=0)

References:
- https://www.redblobgames.com/grids/hexagons/
"""

from dataclasses import dataclass
from typing import Iterator, Tuple

import numpy as np


@dataclass
class HexGrid:
    """
    Hexagonal grid with flat-top orientation and odd-q offset.

    Attributes:
        width: Number of columns
        height: Number of rows
        hex_size: Radius of hexagon (distance from center to vertex)
    """
    width: int
    height: int
    hex_size: float

    @property
    def hex_width(self) -> float:
        """Width of a hexagon (flat edge to flat edge horizontally)."""
        return self.hex_size * 2.0

    @property
    def hex_height(self) -> float:
        """Height of a hexagon (point to point vertically)."""
        return self.hex_size * np.sqrt(3)

    def hex_center(self, col: int, row: int) -> Tuple[float, float]:
        """
        Get pixel coordinates of hex center.

        For flat-top with odd-q offset:
        - Odd columns (col % 2 == 1) are shifted down by hex_height/2
        - Horizontal spacing: 0.75 * hex_width
        - Vertical spacing: hex_height

        Args:
            col: Column index (0-based)
            row: Row index (0-based)

        Returns:
            (x, y) pixel coordinates of hex center
        """
        x = self.hex_width * 0.75 * col + self.hex_width * 0.5

        # Odd-q offset: odd columns shifted down by half height
        if col % 2 == 1:
            y = self.hex_height * (row + 1.0)
        else:
            y = self.hex_height * (row + 0.5)

        return (x, y)

    def hex_corners(self, col: int, row: int) -> list[Tuple[float, float]]:
        """
        Get vertices of a hexagon.

        Returns 6 corner points in clockwise order starting from
        the right corner (0 degrees) for flat-top hexagons.

        Args:
            col: Column index
            row: Row index

        Returns:
            List of 6 (x, y) tuples representing corners
        """
        cx, cy = self.hex_center(col, row)

        corners = []
        for i in range(6):
            angle = i * np.pi / 3  # 0°, 60°, 120°, 180°, 240°, 300°
            x = cx + self.hex_size * np.cos(angle)
            y = cy + self.hex_size * np.sin(angle)
            corners.append((x, y))

        return corners

    def pixel_to_offset(self, x: float, y: float) -> Tuple[int, int]:
        """
        Convert pixel coordinates to offset hex coordinates.

        Uses the inverse of the hex_center calculation with rounding
        to find the nearest hex.

        Args:
            x: Pixel x coordinate
            y: Pixel y coordinate

        Returns:
            (col, row) offset coordinates
        """
        # Approximate column (horizontal spacing is 0.75 * hex_width)
        col_approx = (x - self.hex_width * 0.5) / (self.hex_width * 0.75)

        # For odd-q offset, need to handle row differently based on column
        # Try both even and odd column and pick nearest

        candidates = []

        for col in [int(np.floor(col_approx)), int(np.ceil(col_approx))]:
            if col % 2 == 0:
                # Even column
                row = (y / self.hex_height) - 0.5
            else:
                # Odd column (shifted down by half height)
                row = (y / self.hex_height) - 1.0

            row = int(round(row))

            # Calculate actual center and distance
            center_x, center_y = self.hex_center(col, row)
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)

            candidates.append((dist, col, row))

        # Return closest candidate
        candidates.sort()
        _, best_col, best_row = candidates[0]

        return (best_col, best_row)

    def offset_to_cube(self, col: int, row: int) -> Tuple[int, int, int]:
        """
        Convert offset coordinates to cube coordinates.

        Cube coordinates (q, r, s) satisfy q + r + s = 0 and are
        useful for distance calculations.

        Args:
            col: Column in offset coordinates
            row: Row in offset coordinates

        Returns:
            (q, r, s) cube coordinates
        """
        # For odd-q offset to cube conversion
        q = col
        r = row - (col - (col & 1)) // 2
        s = -q - r

        return (q, r, s)

    def cube_to_offset(self, q: int, r: int, s: int) -> Tuple[int, int]:
        """
        Convert cube coordinates to offset coordinates.

        Args:
            q, r, s: Cube coordinates (must satisfy q+r+s=0)

        Returns:
            (col, row) offset coordinates
        """
        col = q
        row = r + (q - (q & 1)) // 2

        return (col, row)

    def hex_distance(self, col1: int, row1: int, col2: int, row2: int) -> int:
        """
        Calculate distance between two hexes (in hex steps).

        Args:
            col1, row1: First hex offset coordinates
            col2, row2: Second hex offset coordinates

        Returns:
            Distance in hex steps
        """
        # Convert to cube coordinates for easier distance calculation
        q1, r1, s1 = self.offset_to_cube(col1, row1)
        q2, r2, s2 = self.offset_to_cube(col2, row2)

        # In cube coordinates, distance is:
        # (|q1-q2| + |r1-r2| + |s1-s2|) / 2
        return (abs(q1 - q2) + abs(r1 - r2) + abs(s1 - s2)) // 2

    def pixel_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get bounding box of the entire grid in pixel coordinates.

        Returns:
            (min_x, min_y, max_x, max_y)
        """
        # Get all corner points
        all_x = []
        all_y = []

        for row in range(self.height):
            for col in range(self.width):
                corners = self.hex_corners(col, row)
                for x, y in corners:
                    all_x.append(x)
                    all_y.append(y)

        return (min(all_x), min(all_y), max(all_x), max(all_y))

    def iter_hexes(self) -> Iterator[Tuple[int, int]]:
        """
        Iterate over all hexes in row-major order.

        Yields:
            (col, row) tuples for each hex
        """
        for row in range(self.height):
            for col in range(self.width):
                yield (col, row)


# Standalone helper functions

def offset_to_pixel(col: int, row: int, hex_size: float) -> Tuple[float, float]:
    """
    Convert offset coordinates to pixel coordinates.

    Args:
        col: Column index
        row: Row index
        hex_size: Hexagon radius

    Returns:
        (x, y) pixel coordinates
    """
    grid = HexGrid(width=1, height=1, hex_size=hex_size)
    return grid.hex_center(col, row)


def pixel_to_offset(x: float, y: float, hex_size: float) -> Tuple[int, int]:
    """
    Convert pixel coordinates to offset coordinates.

    Args:
        x: Pixel x coordinate
        y: Pixel y coordinate
        hex_size: Hexagon radius

    Returns:
        (col, row) offset coordinates
    """
    # Create temporary grid (size doesn't matter for this calculation)
    grid = HexGrid(width=1, height=1, hex_size=hex_size)
    return grid.pixel_to_offset(x, y)


def hex_corners(col: int, row: int, hex_size: float) -> list[Tuple[float, float]]:
    """
    Get corners of a hexagon.

    Args:
        col: Column index
        row: Row index
        hex_size: Hexagon radius

    Returns:
        List of 6 (x, y) corner coordinates
    """
    grid = HexGrid(width=1, height=1, hex_size=hex_size)
    return grid.hex_corners(col, row)


def hex_distance(col1: int, row1: int, col2: int, row2: int) -> int:
    """
    Calculate distance between two hexes.

    Args:
        col1, row1: First hex offset coordinates
        col2, row2: Second hex offset coordinates

    Returns:
        Distance in hex steps
    """
    grid = HexGrid(width=1, height=1, hex_size=1.0)
    return grid.hex_distance(col1, row1, col2, row2)
