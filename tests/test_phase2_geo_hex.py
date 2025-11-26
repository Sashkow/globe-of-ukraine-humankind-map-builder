"""
Tests for geographic coordinate to hex mapping.

Task 2.3: Implement lat/lon to hex grid conversion.
"""

from pathlib import Path

import numpy as np
import pytest

from geo_hex_mapper import GeoHexMapper


# Ukraine bounding box (actual territory)
UKRAINE_BOUNDS = {
    "min_lon": 22.0,
    "max_lon": 40.5,
    "min_lat": 44.0,
    "max_lat": 52.5,
}

# Expanded bounding box for map (includes buffer for Black Sea, neighbors)
# This gives ~74% land, ~26% ocean/buffer in the 150x88 grid
MAP_BOUNDS = {
    "min_lon": 19.0,
    "max_lon": 43.5,
    "min_lat": 42.5,
    "max_lat": 54.0,
}

# Known city locations for testing
KNOWN_CITIES = {
    "Kyiv": {"lat": 50.4501, "lon": 30.5234},
    "Lviv": {"lat": 49.8397, "lon": 24.0297},
    "Odesa": {"lat": 46.4825, "lon": 30.7233},
    "Kharkiv": {"lat": 49.9935, "lon": 36.2304},
    "Dnipro": {"lat": 48.4647, "lon": 35.0462},
}


class TestGeoHexMapper:
    """Task 2.3: Test geographic coordinate to hex mapping."""

    def test_create_mapper_for_ukraine(self):
        """Create a geo-hex mapper for Ukraine bounds."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        assert mapper.width == 150
        assert mapper.height == 88
        assert mapper.min_lon == UKRAINE_BOUNDS["min_lon"]
        assert mapper.max_lon == UKRAINE_BOUNDS["max_lon"]

    def test_latlon_to_hex_conversion(self):
        """Convert known city lat/lon to hex coordinates."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # Test Kyiv
        kyiv_col, kyiv_row = mapper.latlon_to_hex(
            KNOWN_CITIES["Kyiv"]["lat"],
            KNOWN_CITIES["Kyiv"]["lon"]
        )

        # Kyiv should be within grid bounds
        assert 0 <= kyiv_col < 150
        assert 0 <= kyiv_row < 88

        # Kyiv is roughly in the center-north of Ukraine
        # Should be in roughly the upper-middle vertically and east of center horizontally
        assert 40 < kyiv_col < 110  # East of center
        assert 10 < kyiv_row < 50   # Upper-middle (Kyiv is in northern Ukraine)

    def test_hex_to_latlon_conversion(self):
        """Convert hex coordinates back to lat/lon."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # Test a hex in the middle of the grid
        col, row = 75, 44

        lat, lon = mapper.hex_to_latlon(col, row)

        # Should be within Ukraine bounds
        assert UKRAINE_BOUNDS["min_lat"] <= lat <= UKRAINE_BOUNDS["max_lat"]
        assert UKRAINE_BOUNDS["min_lon"] <= lon <= UKRAINE_BOUNDS["max_lon"]

    def test_latlon_to_hex_and_back(self):
        """Test round-trip conversion: lat/lon -> hex -> lat/lon."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # Test Kyiv
        kyiv_lat = KNOWN_CITIES["Kyiv"]["lat"]
        kyiv_lon = KNOWN_CITIES["Kyiv"]["lon"]

        # Convert to hex
        col, row = mapper.latlon_to_hex(kyiv_lat, kyiv_lon)

        # Convert back
        lat_back, lon_back = mapper.hex_to_latlon(col, row)

        # Should be close to original (within ~one hex)
        # Hex size is ~6.7 km, which is ~0.06 degrees at Ukraine's latitude
        assert abs(lat_back - kyiv_lat) < 0.15
        assert abs(lon_back - kyiv_lon) < 0.15

    def test_all_cities_within_bounds(self):
        """Verify all known Ukrainian cities map to valid hexes."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        for city_name, coords in KNOWN_CITIES.items():
            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])

            # All cities should be within grid
            assert 0 <= col < 150, f"{city_name} col {col} out of bounds"
            assert 0 <= row < 88, f"{city_name} row {row} out of bounds"

    def test_western_vs_eastern_cities(self):
        """Verify relative positions: Lviv (west) vs Kharkiv (east)."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        lviv_col, _ = mapper.latlon_to_hex(
            KNOWN_CITIES["Lviv"]["lat"],
            KNOWN_CITIES["Lviv"]["lon"]
        )

        kharkiv_col, _ = mapper.latlon_to_hex(
            KNOWN_CITIES["Kharkiv"]["lat"],
            KNOWN_CITIES["Kharkiv"]["lon"]
        )

        # Kharkiv is east of Lviv
        assert kharkiv_col > lviv_col

    def test_northern_vs_southern_cities(self):
        """Verify relative positions: Kyiv (north) vs Odesa (south)."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        _, kyiv_row = mapper.latlon_to_hex(
            KNOWN_CITIES["Kyiv"]["lat"],
            KNOWN_CITIES["Kyiv"]["lon"]
        )

        _, odesa_row = mapper.latlon_to_hex(
            KNOWN_CITIES["Odesa"]["lat"],
            KNOWN_CITIES["Odesa"]["lon"]
        )

        # Odesa is south of Kyiv, and row increases downward
        assert odesa_row > kyiv_row

    def test_hex_size_in_km(self):
        """Verify hex size is approximately 6.7 km as planned."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        hex_size_km = mapper.hex_size_km

        # Target is ~6.7 km per hex side
        # With 150x88 grid over Ukraine (1300x900 km), hex size will be ~5.2 km
        # Allow range 5-7 km to account for projection distortion
        assert 5.0 <= hex_size_km <= 7.0, \
            f"Hex size {hex_size_km:.2f} km is outside target range"

    def test_corner_coordinates(self):
        """Test hexes at map corners are within bounds."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        corners = [
            (0, 0),        # Top-left
            (149, 0),      # Top-right
            (0, 87),       # Bottom-left
            (149, 87),     # Bottom-right
        ]

        for col, row in corners:
            lat, lon = mapper.hex_to_latlon(col, row)

            # Corner hexes might be slightly outside bounds due to
            # hex shape extending beyond grid, but should be close
            # Allow 2 degrees margin for corner hexes
            assert UKRAINE_BOUNDS["min_lat"] - 2.0 <= lat <= UKRAINE_BOUNDS["max_lat"] + 2.0
            assert UKRAINE_BOUNDS["min_lon"] - 2.0 <= lon <= UKRAINE_BOUNDS["max_lon"] + 2.0


class TestProjectionConsistency:
    """Test that projection is consistent and accurate."""

    def test_utm_projection_for_ukraine(self):
        """Verify UTM Zone 36N is used for Ukraine."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # UTM 36N is EPSG:32636
        assert mapper.projected_crs == "EPSG:32636"

    def test_distance_accuracy(self):
        """Test that distances in projected coordinates are accurate."""
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # Kyiv to Lviv is approximately 470 km
        kyiv_lat, kyiv_lon = KNOWN_CITIES["Kyiv"]["lat"], KNOWN_CITIES["Kyiv"]["lon"]
        lviv_lat, lviv_lon = KNOWN_CITIES["Lviv"]["lat"], KNOWN_CITIES["Lviv"]["lon"]

        # Get projected coordinates
        kyiv_x, kyiv_y = mapper.latlon_to_projected(kyiv_lat, kyiv_lon)
        lviv_x, lviv_y = mapper.latlon_to_projected(lviv_lat, lviv_lon)

        # Calculate distance
        distance_m = np.sqrt((kyiv_x - lviv_x)**2 + (kyiv_y - lviv_y)**2)
        distance_km = distance_m / 1000

        # Should be approximately 470 km (allow ±50 km margin)
        assert 420 <= distance_km <= 520, \
            f"Kyiv-Lviv distance {distance_km:.1f} km is outside expected range"


class TestPhase2Visualization:
    """Visual tests for manual inspection of Phase 2 results."""

    def test_render_ukraine_grid_with_cities(self):
        """Render 150x88 hex grid with Ukrainian cities marked."""
        from PIL import Image, ImageDraw, ImageFont
        from pathlib import Path

        # Create output directory
        output_dir = Path(__file__).parent / "test_outputs" / "phase2"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create mapper
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        # Convert cities to hex coordinates
        city_hexes = {}
        for city_name, coords in KNOWN_CITIES.items():
            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])
            city_hexes[city_name] = (col, row)

        # Create hex grid visualization
        from hex_grid import HexGrid

        # Use larger hex size for visibility
        hex_size = 8
        grid = HexGrid(width=150, height=88, hex_size=hex_size)

        # Calculate image size
        hex_width = hex_size * np.sqrt(3)
        hex_height = hex_size * 2
        img_width = int(hex_width * 150 + hex_width / 2)
        img_height = int(hex_height * 0.75 * 88 + hex_height * 0.25)

        # Create image
        img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw all hex borders (light gray)
        for row in range(88):
            for col in range(150):
                corners = grid.hex_corners(col, row)
                draw.polygon(corners, outline=(220, 220, 220), width=1)

        # Highlight city hexes
        for city_name, (col, row) in city_hexes.items():
            cx, cy = grid.hex_center(col, row)
            corners = grid.hex_corners(col, row)

            # Fill hex with color
            draw.polygon(corners, fill=(100, 150, 255), outline=(0, 0, 200), width=2)

            # Draw city label
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
            except:
                font = ImageFont.load_default()

            # Draw text with background for readability
            text_bbox = draw.textbbox((cx, cy), city_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Center text
            text_x = cx - text_width / 2
            text_y = cy - text_height / 2

            # Background rectangle
            padding = 2
            draw.rectangle(
                [text_x - padding, text_y - padding,
                 text_x + text_width + padding, text_y + text_height + padding],
                fill=(255, 255, 255, 200)
            )

            # Draw text
            draw.text((text_x, text_y), city_name, fill=(0, 0, 0), font=font)

        # Save image
        output_path = output_dir / "ukraine_grid_with_cities.png"
        img.save(output_path)
        print(f"\n✓ Saved: {output_path}")

        # Print city coordinates for reference
        print(f"\nCity hex coordinates:")
        for city_name, (col, row) in sorted(city_hexes.items()):
            lat, lon = mapper.hex_to_latlon(col, row)
            print(f"  {city_name:10} -> hex({col:3}, {row:2}) -> ({lat:.2f}°N, {lon:.2f}°E)")

        # Verify output exists
        assert output_path.exists()

    def test_render_grid_with_coordinate_labels(self):
        """Render grid with coordinate labels every 10 hexes for reference."""
        from PIL import Image, ImageDraw, ImageFont
        from pathlib import Path

        output_dir = Path(__file__).parent / "test_outputs" / "phase2"
        output_dir.mkdir(parents=True, exist_ok=True)

        from hex_grid import HexGrid

        hex_size = 8
        grid = HexGrid(width=150, height=88, hex_size=hex_size)

        hex_width = hex_size * np.sqrt(3)
        hex_height = hex_size * 2
        img_width = int(hex_width * 150 + hex_width / 2)
        img_height = int(hex_height * 0.75 * 88 + hex_height * 0.25)

        img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        except:
            font = ImageFont.load_default()

        # Draw grid with labels every 10 hexes
        for row in range(88):
            for col in range(150):
                corners = grid.hex_corners(col, row)

                # Highlight every 10th row/col
                if col % 10 == 0 or row % 10 == 0:
                    draw.polygon(corners, fill=(240, 240, 255), outline=(150, 150, 200), width=1)

                    # Label key intersections
                    if col % 10 == 0 and row % 10 == 0:
                        cx, cy = grid.hex_center(col, row)
                        label = f"{col},{row}"
                        draw.text((cx - 15, cy - 5), label, fill=(0, 0, 150), font=font)
                else:
                    draw.polygon(corners, outline=(220, 220, 220), width=1)

        # Draw axis labels
        draw.text((10, 10), "Ukraine Hex Grid: 150x88", fill=(0, 0, 0), font=font)
        draw.text((10, img_height - 20), f"Hex size: ~5.2 km", fill=(0, 0, 0), font=font)

        output_path = output_dir / "ukraine_grid_coordinates.png"
        img.save(output_path)
        print(f"✓ Saved: {output_path}")

        assert output_path.exists()

    def test_render_ukraine_bounds_outline(self):
        """Render grid showing Ukraine bounding box - green inside, gray outside (buffer)."""
        from PIL import Image, ImageDraw, ImageFont
        from pathlib import Path

        output_dir = Path(__file__).parent / "test_outputs" / "phase2"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use expanded bounds for the map grid (includes buffer zones)
        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=MAP_BOUNDS["min_lon"],
            max_lon=MAP_BOUNDS["max_lon"],
            min_lat=MAP_BOUNDS["min_lat"],
            max_lat=MAP_BOUNDS["max_lat"],
        )

        from hex_grid import HexGrid

        hex_size = 8
        grid = HexGrid(width=150, height=88, hex_size=hex_size)

        hex_width = hex_size * np.sqrt(3)
        hex_height = hex_size * 2
        img_width = int(hex_width * 150 + hex_width / 2)
        img_height = int(hex_height * 0.75 * 88 + hex_height * 0.25)

        img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
        except:
            font = ImageFont.load_default()

        # Draw all hexes
        # Green = hex center is within the bounding box we specified
        # Gray = hex center is outside the bounding box
        for row in range(88):
            for col in range(150):
                lat, lon = mapper.hex_to_latlon(col, row)

                # Check if hex center is within the specified bounding box
                within_bbox = (
                    UKRAINE_BOUNDS["min_lat"] <= lat <= UKRAINE_BOUNDS["max_lat"] and
                    UKRAINE_BOUNDS["min_lon"] <= lon <= UKRAINE_BOUNDS["max_lon"]
                )

                corners = grid.hex_corners(col, row)

                if within_bbox:
                    # Inside bounding box - light green (no border to avoid overlap appearance)
                    draw.polygon(corners, fill=(220, 255, 220), outline=(180, 220, 180))
                else:
                    # Outside bounding box - light gray (no border)
                    draw.polygon(corners, fill=(240, 240, 240), outline=(220, 220, 220))

        # Mark corner coordinates
        corners_latlon = [
            (UKRAINE_BOUNDS["min_lat"], UKRAINE_BOUNDS["min_lon"], "SW"),
            (UKRAINE_BOUNDS["max_lat"], UKRAINE_BOUNDS["min_lon"], "NW"),
            (UKRAINE_BOUNDS["min_lat"], UKRAINE_BOUNDS["max_lon"], "SE"),
            (UKRAINE_BOUNDS["max_lat"], UKRAINE_BOUNDS["max_lon"], "NE"),
        ]

        for lat, lon, label in corners_latlon:
            col, row = mapper.latlon_to_hex(lat, lon)
            cx, cy = grid.hex_center(col, row)
            corners = grid.hex_corners(col, row)

            draw.polygon(corners, fill=(255, 100, 100), outline=(200, 0, 0), width=2)
            draw.text((cx - 10, cy - 5), label, fill=(0, 0, 0), font=font)

        # Add cities
        for city_name, coords in KNOWN_CITIES.items():
            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])
            cx, cy = grid.hex_center(col, row)
            corners = grid.hex_corners(col, row)

            draw.polygon(corners, fill=(100, 150, 255), outline=(0, 0, 200), width=2)
            draw.circle((cx, cy), 3, fill=(0, 0, 200))

        # Draw bounding box outline
        # Get corner hexes of bounding box
        bbox_corners = [
            mapper.latlon_to_hex(UKRAINE_BOUNDS["min_lat"], UKRAINE_BOUNDS["min_lon"]),  # SW
            mapper.latlon_to_hex(UKRAINE_BOUNDS["max_lat"], UKRAINE_BOUNDS["min_lon"]),  # NW
            mapper.latlon_to_hex(UKRAINE_BOUNDS["max_lat"], UKRAINE_BOUNDS["max_lon"]),  # NE
            mapper.latlon_to_hex(UKRAINE_BOUNDS["min_lat"], UKRAINE_BOUNDS["max_lon"]),  # SE
        ]

        # Draw thick border on hexes at the edge of bbox
        border_hexes = set()
        for row in range(88):
            for col in range(150):
                lat, lon = mapper.hex_to_latlon(col, row)

                # Check if this hex is near the boundary
                lat_near_edge = (abs(lat - UKRAINE_BOUNDS["min_lat"]) < 0.2 or
                                abs(lat - UKRAINE_BOUNDS["max_lat"]) < 0.2)
                lon_near_edge = (abs(lon - UKRAINE_BOUNDS["min_lon"]) < 0.2 or
                                abs(lon - UKRAINE_BOUNDS["max_lon"]) < 0.2)

                within = (UKRAINE_BOUNDS["min_lat"] <= lat <= UKRAINE_BOUNDS["max_lat"] and
                         UKRAINE_BOUNDS["min_lon"] <= lon <= UKRAINE_BOUNDS["max_lon"])

                if within and (lat_near_edge or lon_near_edge):
                    corners = grid.hex_corners(col, row)
                    draw.polygon(corners, outline=(0, 150, 0), width=2)

        # Legend
        legend_y = 20
        draw.text((10, legend_y), "Green: Inside bounding box", fill=(0, 100, 0), font=font)
        draw.text((10, legend_y + 15), f"  ({UKRAINE_BOUNDS['min_lat']}°-{UKRAINE_BOUNDS['max_lat']}°N, {UKRAINE_BOUNDS['min_lon']}°-{UKRAINE_BOUNDS['max_lon']}°E)", fill=(0, 100, 0), font=font)
        draw.text((10, legend_y + 30), "Gray: Outside bounding box", fill=(100, 100, 100), font=font)
        draw.text((10, legend_y + 45), "Blue: Major cities", fill=(0, 0, 200), font=font)
        draw.text((10, legend_y + 60), "Red: Bounding box corners", fill=(200, 0, 0), font=font)

        output_path = output_dir / "ukraine_bounds_visualization.png"
        img.save(output_path)
        print(f"✓ Saved: {output_path}")

        # Calculate bounding box coverage statistics
        within_count = 0
        for row in range(88):
            for col in range(150):
                lat, lon = mapper.hex_to_latlon(col, row)
                if (UKRAINE_BOUNDS["min_lat"] <= lat <= UKRAINE_BOUNDS["max_lat"] and
                    UKRAINE_BOUNDS["min_lon"] <= lon <= UKRAINE_BOUNDS["max_lon"]):
                    within_count += 1

        total_hexes = 150 * 88
        coverage_pct = (within_count / total_hexes) * 100

        print(f"\nBounding box coverage:")
        print(f"  Bounding box: {UKRAINE_BOUNDS['min_lat']}°-{UKRAINE_BOUNDS['max_lat']}°N, {UKRAINE_BOUNDS['min_lon']}°-{UKRAINE_BOUNDS['max_lon']}°E")
        print(f"  Total hexes: {total_hexes}")
        print(f"  Inside bbox: {within_count} ({coverage_pct:.1f}%)")
        print(f"  Outside bbox: {total_hexes - within_count} ({100 - coverage_pct:.1f}%)")
        print(f"  Note: This is just the rectangular bounding box, not actual Ukraine territory")

        assert output_path.exists()

    def test_render_hex_distance_rings(self):
        """Render hex grid showing distance rings from Kyiv."""
        from PIL import Image, ImageDraw, ImageFont
        from pathlib import Path

        output_dir = Path(__file__).parent / "test_outputs" / "phase2"
        output_dir.mkdir(parents=True, exist_ok=True)

        mapper = GeoHexMapper(
            width=150,
            height=88,
            min_lon=UKRAINE_BOUNDS["min_lon"],
            max_lon=UKRAINE_BOUNDS["max_lon"],
            min_lat=UKRAINE_BOUNDS["min_lat"],
            max_lat=UKRAINE_BOUNDS["max_lat"],
        )

        from hex_grid import HexGrid

        hex_size = 8
        grid = HexGrid(width=150, height=88, hex_size=hex_size)

        hex_width = hex_size * np.sqrt(3)
        hex_height = hex_size * 2
        img_width = int(hex_width * 150 + hex_width / 2)
        img_height = int(hex_height * 0.75 * 88 + hex_height * 0.25)

        img = Image.new('RGB', (img_width, img_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        except:
            font = ImageFont.load_default()

        # Get Kyiv hex
        kyiv_col, kyiv_row = mapper.latlon_to_hex(
            KNOWN_CITIES["Kyiv"]["lat"],
            KNOWN_CITIES["Kyiv"]["lon"]
        )

        # Color scale for distances
        max_dist = 30
        colors = [
            (255, 100, 100),  # Close - red
            (255, 150, 100),
            (255, 200, 100),
            (255, 255, 100),  # Medium - yellow
            (200, 255, 100),
            (150, 255, 150),
            (100, 200, 200),  # Far - blue
        ]

        # Draw hexes colored by distance from Kyiv
        for row in range(88):
            for col in range(150):
                dist = grid.hex_distance(col, row, kyiv_col, kyiv_row)

                corners = grid.hex_corners(col, row)

                if dist == 0:
                    # Kyiv - special color
                    draw.polygon(corners, fill=(200, 0, 0), outline=(100, 0, 0), width=2)
                elif dist <= max_dist:
                    # Color by distance
                    color_idx = min(int((dist / max_dist) * len(colors)), len(colors) - 1)
                    color = colors[color_idx]
                    draw.polygon(corners, fill=color, outline=(150, 150, 150), width=1)
                else:
                    # Too far - gray
                    draw.polygon(corners, fill=(240, 240, 240), outline=(200, 200, 200), width=1)

        # Mark other cities
        for city_name, coords in KNOWN_CITIES.items():
            if city_name == "Kyiv":
                continue

            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])
            cx, cy = grid.hex_center(col, row)

            # Draw dot and label
            draw.circle((cx, cy), 4, fill=(0, 0, 0), outline=(255, 255, 255), width=1)

            dist = grid.hex_distance(col, row, kyiv_col, kyiv_row)
            label = f"{city_name}\n({dist}h)"

            draw.text((cx + 6, cy - 8), label, fill=(0, 0, 0), font=font)

        # Legend
        legend_y = 20
        draw.text((10, legend_y), "Distance from Kyiv (in hex steps)", fill=(0, 0, 0), font=font)
        draw.text((10, legend_y + 15), f"1 hex ≈ {mapper.hex_size_km:.1f} km", fill=(0, 0, 0), font=font)

        output_path = output_dir / "ukraine_distance_rings_from_kyiv.png"
        img.save(output_path)
        print(f"✓ Saved: {output_path}")

        # Print distances
        print(f"\nDistances from Kyiv:")
        print(f"  Kyiv at hex({kyiv_col}, {kyiv_row})")
        for city_name, coords in KNOWN_CITIES.items():
            if city_name == "Kyiv":
                continue
            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])
            dist = grid.hex_distance(col, row, kyiv_col, kyiv_row)
            dist_km = dist * mapper.hex_size_km
            print(f"  {city_name:10} -> {dist:3} hexes (~{dist_km:.0f} km)")

        assert output_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
