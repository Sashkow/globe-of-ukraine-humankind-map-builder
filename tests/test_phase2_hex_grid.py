"""
Tests for hexagonal grid coordinate system.

Task 2.2: Implement hex grid coordinate system matching Humankind's format.
"""

from pathlib import Path

import numpy as np
import pytest

from hex_grid import (
    HexGrid,
    offset_to_pixel,
    pixel_to_offset,
    hex_corners,
    hex_distance,
)


class TestHexCoordinates:
    """Task 2.2: Verify hex positions match expected pattern."""

    def test_create_hex_grid(self):
        """Create a basic hex grid with correct dimensions."""
        grid = HexGrid(width=10, height=10, hex_size=10.0)

        assert grid.width == 10
        assert grid.height == 10
        assert grid.hex_size == 10.0

    def test_hex_center_positions(self):
        """Verify hex center positions for flat-top odd-q offset."""
        grid = HexGrid(width=10, height=10, hex_size=10.0)

        # Column 0 (even) should have no vertical offset
        center_0_0 = grid.hex_center(0, 0)
        center_0_1 = grid.hex_center(0, 1)

        # Hex width = size * 2
        # Hex height = size * sqrt(3)
        hex_width = 10.0 * 2.0
        hex_height = 10.0 * np.sqrt(3)

        # First hex center at (hex_width/2, hex_height/2)
        assert center_0_0[0] == pytest.approx(hex_width / 2)
        assert center_0_0[1] == pytest.approx(hex_height / 2)

        # Next hex in same column: vertical spacing = hex_height
        expected_y = hex_height / 2 + hex_height
        assert center_0_1[0] == pytest.approx(hex_width / 2)
        assert center_0_1[1] == pytest.approx(expected_y)

    def test_hex_center_odd_column_offset(self):
        """Verify odd columns are shifted down by height/2."""
        grid = HexGrid(width=10, height=10, hex_size=10.0)

        hex_width = 10.0 * 2.0
        hex_height = 10.0 * np.sqrt(3)

        # Even column (col=0)
        center_even = grid.hex_center(0, 0)

        # Odd column (col=1) - should be shifted down by hex_height/2
        center_odd = grid.hex_center(1, 0)

        # Horizontal: offset by 0.75 * hex_width
        assert center_odd[0] == pytest.approx(center_even[0] + 0.75 * hex_width)

        # Vertical: shifted down by hex_height/2 for odd-q offset
        assert center_odd[1] == pytest.approx(center_even[1] + hex_height / 2)

    def test_hex_corners_calculation(self):
        """Verify hex vertices are calculated correctly for flat-top."""
        grid = HexGrid(width=1, height=1, hex_size=10.0)

        corners = grid.hex_corners(0, 0)

        # Should have 6 corners
        assert len(corners) == 6

        # For flat-top hex, verify corners are at correct angles
        # Starting at 0 degrees, every 60 degrees
        cx, cy = grid.hex_center(0, 0)

        for i, (x, y) in enumerate(corners):
            angle = i * np.pi / 3  # 0°, 60°, 120°, 180°, 240°, 300°
            expected_x = cx + 10.0 * np.cos(angle)
            expected_y = cy + 10.0 * np.sin(angle)

            assert x == pytest.approx(expected_x, abs=1e-10)
            assert y == pytest.approx(expected_y, abs=1e-10)

    def test_hex_tiling_no_gaps(self):
        """Verify hexes tile properly with no gaps or overlaps."""
        grid = HexGrid(width=5, height=5, hex_size=10.0)

        # Get corners for adjacent hexes
        hex_00 = grid.hex_corners(0, 0)
        hex_10 = grid.hex_corners(1, 0)

        # For flat-top odd-q offset, hex (0,0) and hex (1,0) share vertices
        # The hex (1,0) is shifted right by 0.75*width and down by 0.5*height

        # Check that there are shared vertices
        # Convert to sets of tuples for comparison
        corners_00 = set((round(x, 10), round(y, 10)) for x, y in hex_00)
        corners_10 = set((round(x, 10), round(y, 10)) for x, y in hex_10)

        # Should share exactly 2 corners
        shared = corners_00 & corners_10
        assert len(shared) == 2, f"Expected 2 shared corners, got {len(shared)}"

    def test_pixel_to_offset_and_back(self):
        """Test converting pixel coordinates to offset and back."""
        grid = HexGrid(width=20, height=20, hex_size=10.0)

        # Test several hex positions
        test_positions = [(0, 0), (5, 5), (10, 3), (15, 18)]

        for col, row in test_positions:
            # Get hex center in pixels
            px, py = grid.hex_center(col, row)

            # Convert back to offset coordinates
            result_col, result_row = grid.pixel_to_offset(px, py)

            assert result_col == col
            assert result_row == row

    def test_hex_distance_calculation(self):
        """Test distance calculation between hexes in offset coordinates."""
        grid = HexGrid(width=20, height=20, hex_size=10.0)

        # Adjacent hexes should have distance 1
        dist_01 = grid.hex_distance(0, 0, 1, 0)
        assert dist_01 == 1

        dist_02 = grid.hex_distance(0, 0, 0, 1)
        assert dist_02 == 1

        # Hex to itself should have distance 0
        dist_00 = grid.hex_distance(5, 5, 5, 5)
        assert dist_00 == 0


class TestHexGridBounds:
    """Test hex grid bounding box calculations."""

    def test_grid_pixel_bounds(self):
        """Verify pixel bounds of the entire grid."""
        grid = HexGrid(width=10, height=10, hex_size=10.0)

        bounds = grid.pixel_bounds()

        # Should return (min_x, min_y, max_x, max_y)
        assert len(bounds) == 4
        min_x, min_y, max_x, max_y = bounds

        # Min should be near 0 (allowing floating point error)
        assert min_x >= -1e-10
        assert min_y >= -1e-10

        # Max should accommodate all hexes
        # For flat-top hexagons:
        # Width: ~10 hexes * 0.75 * hex_width + hex_width/2
        # Height: ~10 hexes * hex_height
        hex_width = 10.0 * 2.0
        hex_height = 10.0 * np.sqrt(3)

        expected_max_x = 0.75 * hex_width * 9 + hex_width
        expected_max_y = hex_height * 10

        assert max_x == pytest.approx(expected_max_x, abs=hex_width)
        assert max_y == pytest.approx(expected_max_y, abs=hex_height)

    def test_all_hexes_within_bounds(self):
        """Verify all hex centers are within pixel bounds."""
        grid = HexGrid(width=15, height=15, hex_size=8.0)

        min_x, min_y, max_x, max_y = grid.pixel_bounds()

        for row in range(grid.height):
            for col in range(grid.width):
                cx, cy = grid.hex_center(col, row)

                assert min_x <= cx <= max_x
                assert min_y <= cy <= max_y


class TestHexGridIteration:
    """Test iterating over hex grid."""

    def test_iter_all_hexes(self):
        """Test iterating over all hexes in grid."""
        grid = HexGrid(width=5, height=4, hex_size=10.0)

        hexes = list(grid.iter_hexes())

        # Should have width * height hexes
        assert len(hexes) == 5 * 4

        # Each hex should be (col, row) tuple
        assert hexes[0] == (0, 0)
        assert hexes[-1] == (4, 3)

    def test_iter_hexes_order(self):
        """Verify hexes are iterated in row-major order."""
        grid = HexGrid(width=3, height=2, hex_size=10.0)

        hexes = list(grid.iter_hexes())

        expected = [
            (0, 0), (1, 0), (2, 0),  # Row 0
            (0, 1), (1, 1), (2, 1),  # Row 1
        ]

        assert hexes == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
