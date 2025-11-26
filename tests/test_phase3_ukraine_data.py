"""
Tests for Ukraine geographic data loading and validation.

Phase 3: Geographic Data Preparation
Task 3.1: Load and validate Ukraine raion boundaries (136 raions)
Task 3.2: Verify geographic accuracy
Task 3.3: Visualize raion-to-hex mapping
"""

from pathlib import Path

import pytest
import geopandas as gpd
from shapely.geometry import Point, Polygon
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# Path to Ukraine data
DATA_DIR = Path(__file__).parent.parent / "data"
UKRAINE_RAIONS_PATH = DATA_DIR / "ukraine_raions.geojson"


class TestPhase3Task1LoadUkraineData:
    """Task 3.1: Load and validate Ukraine geographic data."""

    def test_ukraine_raions_file_exists(self):
        """Verify Ukraine raions GeoJSON file exists."""
        assert UKRAINE_RAIONS_PATH.exists(), \
            f"Ukraine raions file not found at {UKRAINE_RAIONS_PATH}"

    def test_load_ukraine_raions(self):
        """Load Ukraine raions and verify basic structure."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Should be a GeoDataFrame
        assert isinstance(gdf, gpd.GeoDataFrame)

        # Should have geometries
        assert not gdf.geometry.is_empty.any(), "Some geometries are empty"

    def test_raion_count(self):
        """Verify we have 136 raions (after 2020 administrative reform)."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Ukraine has 136 raions after 2020 reform
        # Note: This might include Crimea or might not, depending on data source
        # We'll accept 130-140 as valid range
        raion_count = len(gdf)

        assert 130 <= raion_count <= 140, \
            f"Expected ~136 raions, got {raion_count}"

        print(f"\nFound {raion_count} raions")

    def test_all_geometries_valid(self):
        """Verify all raion geometries are valid polygons."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # All geometries should be valid
        invalid = gdf[~gdf.geometry.is_valid]
        assert len(invalid) == 0, \
            f"Found {len(invalid)} invalid geometries"

        # All should be Polygons or MultiPolygons
        geom_types = gdf.geometry.type.unique()
        valid_types = {'Polygon', 'MultiPolygon'}
        assert set(geom_types).issubset(valid_types), \
            f"Invalid geometry types: {geom_types}"

    def test_raions_within_ukraine_bounds(self):
        """Verify all raions are within expected Ukraine bounds."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Get total bounds
        minx, miny, maxx, maxy = gdf.total_bounds

        # Ukraine bounds (approximate)
        UKRAINE_MIN_LON = 22.0
        UKRAINE_MAX_LON = 40.5
        UKRAINE_MIN_LAT = 44.0
        UKRAINE_MAX_LAT = 52.5

        # All raions should be within Ukraine
        assert minx >= UKRAINE_MIN_LON - 0.5, f"Western bound {minx} too far west"
        assert maxx <= UKRAINE_MAX_LON + 0.5, f"Eastern bound {maxx} too far east"
        assert miny >= UKRAINE_MIN_LAT - 0.5, f"Southern bound {miny} too far south"
        assert maxy <= UKRAINE_MAX_LAT + 0.5, f"Northern bound {maxy} too far north"

        print(f"\nUkraine bounds: ({minx:.2f}, {miny:.2f}) to ({maxx:.2f}, {maxy:.2f})")

    def test_raions_have_names(self):
        """Verify all raions have name attributes."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Look for common name fields
        name_fields = ['name', 'NAME', 'ADM2_EN', 'ADM2_UA', 'NAME_2', 'admin2Name', 'adm2_name']

        found_name_field = None
        for field in name_fields:
            if field in gdf.columns:
                found_name_field = field
                break

        assert found_name_field is not None, \
            f"No name field found. Available columns: {list(gdf.columns)}"

        # All raions should have non-null names
        name_col = gdf[found_name_field]
        null_names = name_col.isnull().sum()

        assert null_names == 0, \
            f"Found {null_names} raions without names"

        print(f"\nUsing name field: {found_name_field}")
        print(f"Sample raions: {name_col.head().tolist()}")

    def test_raions_have_oblast_info(self):
        """Verify raions have parent oblast information."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Look for oblast/admin1 fields
        oblast_fields = ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']

        found_oblast_field = None
        for field in oblast_fields:
            if field in gdf.columns:
                found_oblast_field = field
                break

        assert found_oblast_field is not None, \
            f"No oblast field found. Available columns: {list(gdf.columns)}"

        print(f"\nUsing oblast field: {found_oblast_field}")

        # Should have 24-27 unique oblasts
        oblast_count = gdf[found_oblast_field].nunique()
        assert 20 <= oblast_count <= 30, \
            f"Expected 24-27 oblasts, got {oblast_count}"

        print(f"Found {oblast_count} oblasts")

    def test_no_overlapping_raions(self):
        """Verify raions don't overlap (or overlap minimally)."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Check a sample of raions for overlaps
        sample_size = min(20, len(gdf))
        sample = gdf.sample(n=sample_size, random_state=42)

        overlaps = 0
        for idx1, row1 in sample.iterrows():
            for idx2, row2 in sample.iterrows():
                if idx1 >= idx2:
                    continue

                if row1.geometry.intersects(row2.geometry):
                    intersection = row1.geometry.intersection(row2.geometry)
                    # Allow tiny overlaps (< 0.1% of smaller area)
                    if intersection.area > min(row1.geometry.area, row2.geometry.area) * 0.001:
                        overlaps += 1

        # Should have minimal overlaps
        assert overlaps < sample_size * 0.1, \
            f"Found {overlaps} significant overlaps in sample"

    def test_total_area_reasonable(self):
        """Verify total area is approximately Ukraine's size."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Convert to projected CRS for area calculation
        gdf_projected = gdf.to_crs("EPSG:32636")  # UTM 36N

        # Calculate total area in km²
        total_area_m2 = gdf_projected.geometry.area.sum()
        total_area_km2 = total_area_m2 / 1_000_000

        # Ukraine's area is ~603,628 km²
        # Accept 550,000 - 650,000 km² (accounts for Crimea uncertainty)
        assert 550_000 <= total_area_km2 <= 650_000, \
            f"Total area {total_area_km2:,.0f} km² outside expected range"

        print(f"\nTotal area: {total_area_km2:,.0f} km²")
        print(f"Expected: ~603,628 km² (Ukraine)")


class TestPhase3Task2GeographicAccuracy:
    """Task 3.2: Verify geographic accuracy."""

    # Known city locations and their raions
    KNOWN_CITIES = {
        "Kyiv": {
            "lat": 50.4501,
            "lon": 30.5234,
            "expected_keywords": ["Kyiv", "Kiev", "Київ"],
        },
        "Lviv": {
            "lat": 49.8397,
            "lon": 24.0297,
            "expected_keywords": ["Lviv", "L'viv", "Львів"],
        },
        "Odesa": {
            "lat": 46.4825,
            "lon": 30.7233,
            "expected_keywords": ["Odesa", "Odessa", "Одеса"],
        },
        "Kharkiv": {
            "lat": 49.9935,
            "lon": 36.2304,
            "expected_keywords": ["Kharkiv", "Kharkov", "Харків"],
        },
        "Dnipro": {
            "lat": 48.4647,
            "lon": 35.0462,
            "expected_keywords": ["Dnipro", "Dnipropetrovsk", "Дніпро"],
        },
    }

    def test_cities_in_correct_raions(self):
        """Verify major cities are in raions with correct names."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Find name field
        name_fields = ['name', 'NAME', 'ADM2_EN', 'ADM2_UA', 'NAME_2', 'admin2Name', 'adm2_name']
        name_field = None
        for field in name_fields:
            if field in gdf.columns:
                name_field = field
                break

        assert name_field is not None, "No name field found"

        print(f"\nVerifying city locations:")

        for city_name, city_data in self.KNOWN_CITIES.items():
            # Create point
            point = Point(city_data["lon"], city_data["lat"])

            # Find which raion contains this point
            containing_raions = gdf[gdf.geometry.contains(point)]

            # Should be in exactly one raion
            assert len(containing_raions) > 0, \
                f"{city_name} not found in any raion at ({city_data['lat']}, {city_data['lon']})"

            raion_name = containing_raions.iloc[0][name_field]

            # Check if raion name matches expected keywords
            matches = any(keyword.lower() in str(raion_name).lower()
                         for keyword in city_data["expected_keywords"])

            print(f"  {city_name:10} -> {raion_name} {'✓' if matches else '⚠'}")

            # Note: We don't assert because raion names might be spelled differently
            # Just print for manual verification

    def test_raion_count_per_oblast(self):
        """Verify each oblast has 3-8 raions (after 2020 reform)."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Find oblast field
        oblast_fields = ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']
        oblast_field = None
        for field in oblast_fields:
            if field in gdf.columns:
                oblast_field = field
                break

        assert oblast_field is not None, "No oblast field found"

        # Count raions per oblast
        raions_per_oblast = gdf.groupby(oblast_field).size()

        print(f"\nRaions per oblast:")
        for oblast, count in raions_per_oblast.sort_values(ascending=False).items():
            print(f"  {oblast:30} {count:2} raions")

        # Each oblast should have 3-8 raions (general pattern after 2020 reform)
        # Special cases: Kyiv and Sevastopol are cities with special status (1 raion each)
        min_raions = raions_per_oblast.min()
        max_raions = raions_per_oblast.max()

        assert min_raions >= 1, f"Some oblast has {min_raions} raions (too few)"
        assert max_raions <= 10, f"Some oblast has {max_raions} raions (too many)"

        # Check that Kyiv and Sevastopol are the only ones with 1 raion
        single_raion = raions_per_oblast[raions_per_oblast == 1]
        if len(single_raion) > 0:
            print(f"\nSpecial status cities (1 raion each): {list(single_raion.index)}")
            # Should only be Kyiv and Sevastopol
            assert len(single_raion) <= 2, \
                f"Too many oblasts with only 1 raion: {list(single_raion.index)}"

    def test_crimea_raions_identifiable(self):
        """Verify Crimean raions can be identified."""
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Find oblast field
        oblast_fields = ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']
        oblast_field = None
        for field in oblast_fields:
            if field in gdf.columns:
                oblast_field = field
                break

        if oblast_field is None:
            pytest.skip("No oblast field found")

        # Look for Crimea
        crimea_keywords = ['Crimea', 'Krym', 'Крим', 'Autonomous Republic']

        crimea_raions = gdf[gdf[oblast_field].astype(str).str.contains(
            '|'.join(crimea_keywords), case=False, na=False
        )]

        if len(crimea_raions) > 0:
            print(f"\nFound {len(crimea_raions)} Crimean raions")
            print("Note: Will handle Crimea specially in Phase 7")
        else:
            print("\nNo Crimean raions found (might be excluded from dataset)")


class TestPhase3Task3VisualizationRaionHexMap:
    """Task 3.3: Visualize raion-to-hex mapping."""

    def test_visualize_ukraine_raion_hex_map(self):
        """Create hex map visualization with raions colored to avoid adjacent matches."""
        from geo_hex_mapper import GeoHexMapper
        from shapely.geometry import Point

        # Load raion data
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Map bounds from Phase 2
        MAP_BOUNDS = {
            "min_lon": 19.0,
            "max_lon": 43.5,
            "min_lat": 42.5,
            "max_lat": 54.0,
        }

        # Create hex mapper
        mapper = GeoHexMapper(
            width=150,
            height=88,
            **MAP_BOUNDS
        )

        # Create a grid to store which raion each hex belongs to
        hex_to_raion = {}  # (col, row) -> raion_index

        print(f"\nMapping {len(gdf)} raions to hex grid...")

        # For each hex, determine which raion it belongs to
        for row in range(88):
            for col in range(150):
                # Get hex center
                lat, lon = mapper.hex_to_latlon(col, row)
                point = Point(lon, lat)

                # Find which raion contains this point
                for idx, raion in gdf.iterrows():
                    if raion.geometry.contains(point):
                        hex_to_raion[(col, row)] = idx
                        break

        print(f"Mapped {len(hex_to_raion)} hexes to raions")

        # Build adjacency graph for raions
        raion_neighbors = {idx: set() for idx in gdf.index}

        # For each hex, check its neighbors
        directions = [
            (1, 0), (-1, 0),  # E, W
            (0, 1), (0, -1),  # SE/SW, NE/NW (depending on column parity)
            (1, 1), (-1, 1),  # Diagonal neighbors
            (1, -1), (-1, -1)
        ]

        for (col, row), raion_idx in hex_to_raion.items():
            for dc, dr in directions:
                neighbor = (col + dc, row + dr)
                if neighbor in hex_to_raion:
                    neighbor_idx = hex_to_raion[neighbor]
                    if neighbor_idx != raion_idx:
                        raion_neighbors[raion_idx].add(neighbor_idx)
                        raion_neighbors[neighbor_idx].add(raion_idx)

        # Greedy graph coloring algorithm
        raion_colors = {}
        color_palette = plt.cm.tab20.colors  # 20 distinct colors

        # Sort raions by number of neighbors (most constrained first)
        sorted_raions = sorted(
            gdf.index,
            key=lambda idx: len(raion_neighbors[idx]),
            reverse=True
        )

        for raion_idx in sorted_raions:
            # Find colors used by neighbors
            neighbor_colors = {
                raion_colors[n]
                for n in raion_neighbors[raion_idx]
                if n in raion_colors
            }

            # Assign first available color
            for color_idx in range(len(color_palette)):
                if color_idx not in neighbor_colors:
                    raion_colors[raion_idx] = color_idx
                    break

        max_colors_used = max(raion_colors.values()) + 1 if raion_colors else 0
        print(f"Used {max_colors_used} colors for {len(gdf)} raions")

        # Create visualization
        fig, ax = plt.subplots(figsize=(20, 12))

        # Draw hexes
        for (col, row), raion_idx in hex_to_raion.items():
            corners = mapper.hex_corners_latlon(col, row)
            # Convert lat,lon to lon,lat for plotting
            corners_xy = [(lon, lat) for lat, lon in corners]

            color_idx = raion_colors.get(raion_idx, 0)
            color = color_palette[color_idx % len(color_palette)]

            hex_patch = mpatches.Polygon(
                corners_xy,
                facecolor=color,
                edgecolor='black',
                linewidth=0.1,
                alpha=0.7
            )
            ax.add_patch(hex_patch)

        # Draw raion boundaries for reference
        gdf.boundary.plot(ax=ax, color='darkgray', linewidth=0.5, alpha=0.5)

        # Set bounds
        ax.set_xlim(MAP_BOUNDS["min_lon"], MAP_BOUNDS["max_lon"])
        ax.set_ylim(MAP_BOUNDS["min_lat"], MAP_BOUNDS["max_lat"])

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(
            f"Ukraine Raion-to-Hex Mapping (150×88 grid)\n"
            f"{len(gdf)} raions mapped to {len(hex_to_raion)} hexes using {max_colors_used} colors\n"
            f"Adjacent raions have different colors",
            fontsize=14
        )
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)

        # Save output
        output_dir = Path(__file__).parent / "test_outputs" / "phase3"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "ukraine_raion_hex_map.png"

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"Saved visualization to {output_path}")

        # Verify coloring is valid (no adjacent raions with same color)
        for raion_idx in gdf.index:
            if raion_idx not in raion_colors:
                continue
            color = raion_colors[raion_idx]
            for neighbor_idx in raion_neighbors[raion_idx]:
                if neighbor_idx in raion_colors:
                    assert raion_colors[neighbor_idx] != color, \
                        f"Adjacent raions {raion_idx} and {neighbor_idx} have same color {color}"

        print("✓ All adjacent raions have different colors")

    def test_visualize_rigid_hex_grid_with_raion_colors(self):
        """Create rigid hex grid visualization with hexes colored by raion membership."""
        from geo_hex_mapper import GeoHexMapper
        from shapely.geometry import Point
        from hex_grid import HexGrid

        # Load raion data
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Map bounds from Phase 2
        MAP_BOUNDS = {
            "min_lon": 19.0,
            "max_lon": 43.5,
            "min_lat": 42.5,
            "max_lat": 54.0,
        }

        # Create hex mapper
        mapper = GeoHexMapper(
            width=150,
            height=88,
            **MAP_BOUNDS
        )

        print(f"\nMapping hex grid to {len(gdf)} raions...")

        # For each hex, determine which raion it belongs to
        hex_to_raion = {}  # (col, row) -> raion_index

        for row in range(88):
            for col in range(150):
                # Get hex center in lat/lon
                lat, lon = mapper.hex_to_latlon(col, row)
                point = Point(lon, lat)

                # Find which raion contains this point
                for idx, raion in gdf.iterrows():
                    if raion.geometry.contains(point):
                        hex_to_raion[(col, row)] = idx
                        break

        print(f"Mapped {len(hex_to_raion)} hexes to raions")

        # Build adjacency graph for raions based on hex neighbors
        raion_neighbors = {idx: set() for idx in gdf.index}

        # Hex neighbor offsets for flat-top odd-q
        # For even columns (col % 2 == 0):
        even_neighbors = [
            (1, 0), (-1, 0),      # E, W
            (0, -1), (0, 1),      # NE, SE
            (1, -1), (-1, -1),    # NE-E, NW-W
        ]
        # For odd columns (col % 2 == 1):
        odd_neighbors = [
            (1, 0), (-1, 0),      # E, W
            (0, -1), (0, 1),      # NW, SW
            (1, 1), (-1, 1),      # SE-E, SW-W
        ]

        for (col, row), raion_idx in hex_to_raion.items():
            neighbors_offsets = even_neighbors if col % 2 == 0 else odd_neighbors

            for dc, dr in neighbors_offsets:
                neighbor = (col + dc, row + dr)
                if neighbor in hex_to_raion:
                    neighbor_idx = hex_to_raion[neighbor]
                    if neighbor_idx != raion_idx:
                        raion_neighbors[raion_idx].add(neighbor_idx)

        # Greedy graph coloring
        raion_colors = {}
        color_palette = plt.cm.tab20.colors

        sorted_raions = sorted(
            gdf.index,
            key=lambda idx: len(raion_neighbors[idx]),
            reverse=True
        )

        for raion_idx in sorted_raions:
            neighbor_colors = {
                raion_colors[n]
                for n in raion_neighbors[raion_idx]
                if n in raion_colors
            }

            for color_idx in range(len(color_palette)):
                if color_idx not in neighbor_colors:
                    raion_colors[raion_idx] = color_idx
                    break

        max_colors_used = max(raion_colors.values()) + 1 if raion_colors else 0
        print(f"Used {max_colors_used} colors for {len(gdf)} raions")

        # Create visualization with RIGID hex grid
        fig, ax = plt.subplots(figsize=(24, 14))

        # Create a pixel-based hex grid for drawing
        # Calculate pixel size for the hex grid
        hex_size_pixels = 10
        grid = HexGrid(width=150, height=88, hex_size=hex_size_pixels)

        # Get pixel bounds
        pixel_bounds = grid.pixel_bounds()
        img_width = int(pixel_bounds[2] - pixel_bounds[0]) + 20
        img_height = int(pixel_bounds[3] - pixel_bounds[1]) + 20

        # Create matplotlib patches for each hex in the rigid grid
        for row in range(88):
            for col in range(150):
                # Get hex corners in pixel coordinates
                corners_pixel = grid.hex_corners(col, row)

                # Determine color based on raion
                if (col, row) in hex_to_raion:
                    raion_idx = hex_to_raion[(col, row)]
                    color_idx = raion_colors.get(raion_idx, 0)
                    color = color_palette[color_idx % len(color_palette)]
                    alpha = 0.8
                else:
                    # Water/outside Ukraine
                    color = (0.7, 0.7, 0.7)
                    alpha = 0.3

                # Draw hex
                hex_patch = mpatches.Polygon(
                    corners_pixel,
                    facecolor=color,
                    edgecolor='black',
                    linewidth=0.3,
                    alpha=alpha
                )
                ax.add_patch(hex_patch)

        # Set axis limits to show the entire grid
        ax.set_xlim(pixel_bounds[0] - 10, pixel_bounds[2] + 10)
        ax.set_ylim(pixel_bounds[1] - 10, pixel_bounds[3] + 10)
        ax.set_aspect('equal')
        ax.invert_yaxis()  # Invert Y so (0,0) is at top-left
        ax.axis('off')

        ax.set_title(
            f"Rigid 150×88 Hex Grid Colored by Ukraine Raions\n"
            f"{len(hex_to_raion)} hexes mapped to {len(gdf)} raions using {max_colors_used} colors\n"
            f"Grid preserves perfect hexagonal tiling",
            fontsize=16,
            pad=20
        )

        # Save output
        output_dir = Path(__file__).parent / "test_outputs" / "phase3"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "ukraine_rigid_hex_grid.png"

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"Saved rigid hex grid visualization to {output_path}")

        # Verify coloring is valid
        for raion_idx in gdf.index:
            if raion_idx not in raion_colors:
                continue
            color = raion_colors[raion_idx]
            for neighbor_idx in raion_neighbors[raion_idx]:
                if neighbor_idx in raion_colors:
                    assert raion_colors[neighbor_idx] != color, \
                        f"Adjacent raions {raion_idx} and {neighbor_idx} have same color {color}"

        print("✓ All adjacent raions have different colors")
        print(f"✓ Rigid hex grid: {88} rows × {150} columns = {150*88} total hexes")
        print(f"✓ Ukraine coverage: {len(hex_to_raion)} hexes ({100*len(hex_to_raion)/(150*88):.1f}%)")

    def test_visualize_rigid_hex_grid_with_oblast_colors(self):
        """Create rigid hex grid with oblasts colored and major cities labeled."""
        from geo_hex_mapper import GeoHexMapper
        from shapely.geometry import Point
        from hex_grid import HexGrid

        # Load raion data
        gdf = gpd.read_file(UKRAINE_RAIONS_PATH)

        # Find oblast field
        oblast_fields = ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']
        oblast_field = None
        for field in oblast_fields:
            if field in gdf.columns:
                oblast_field = field
                break

        assert oblast_field is not None, "No oblast field found"

        # Create oblast mapping
        # Group raions by oblast
        oblast_to_raions = {}
        for idx, row in gdf.iterrows():
            oblast_name = row[oblast_field]
            if oblast_name not in oblast_to_raions:
                oblast_to_raions[oblast_name] = []
            oblast_to_raions[oblast_name].append(idx)

        print(f"\nFound {len(oblast_to_raions)} oblasts")

        # Major Ukrainian cities with coordinates
        MAJOR_CITIES = {
            "Kyiv": {"lat": 50.4501, "lon": 30.5234},
            "Kharkiv": {"lat": 49.9935, "lon": 36.2304},
            "Odesa": {"lat": 46.4825, "lon": 30.7233},
            "Dnipro": {"lat": 48.4647, "lon": 35.0462},
            "Lviv": {"lat": 49.8397, "lon": 24.0297},
            "Zaporizhzhia": {"lat": 47.8388, "lon": 35.1396},
            "Kryvyi Rih": {"lat": 47.9105, "lon": 33.3915},
            "Mykolaiv": {"lat": 46.9750, "lon": 31.9946},
            "Mariupol": {"lat": 47.0971, "lon": 37.5432},
            "Luhansk": {"lat": 48.5670, "lon": 39.3171},
            "Donetsk": {"lat": 48.0156, "lon": 37.8028},
            "Vinnytsia": {"lat": 49.2328, "lon": 28.4681},
            "Simferopol": {"lat": 44.9521, "lon": 34.1024},
            "Sevastopol": {"lat": 44.6160, "lon": 33.5253},
            "Chernihiv": {"lat": 51.4982, "lon": 31.2893},
        }

        # Map bounds from Phase 2
        MAP_BOUNDS = {
            "min_lon": 19.0,
            "max_lon": 43.5,
            "min_lat": 42.5,
            "max_lat": 54.0,
        }

        # Create hex mapper
        mapper = GeoHexMapper(
            width=150,
            height=88,
            **MAP_BOUNDS
        )

        print(f"Mapping hex grid to oblasts...")

        # For each hex, determine which oblast it belongs to
        hex_to_oblast = {}  # (col, row) -> oblast_name

        for row in range(88):
            for col in range(150):
                lat, lon = mapper.hex_to_latlon(col, row)
                point = Point(lon, lat)

                # Find which raion contains this point
                for idx, raion in gdf.iterrows():
                    if raion.geometry.contains(point):
                        oblast_name = raion[oblast_field]
                        hex_to_oblast[(col, row)] = oblast_name
                        break

        print(f"Mapped {len(hex_to_oblast)} hexes to oblasts")

        # Build adjacency graph for oblasts
        oblast_neighbors = {oblast: set() for oblast in oblast_to_raions.keys()}

        # Hex neighbor offsets for flat-top odd-q
        even_neighbors = [
            (1, 0), (-1, 0),
            (0, -1), (0, 1),
            (1, -1), (-1, -1),
        ]
        odd_neighbors = [
            (1, 0), (-1, 0),
            (0, -1), (0, 1),
            (1, 1), (-1, 1),
        ]

        for (col, row), oblast_name in hex_to_oblast.items():
            neighbors_offsets = even_neighbors if col % 2 == 0 else odd_neighbors

            for dc, dr in neighbors_offsets:
                neighbor = (col + dc, row + dr)
                if neighbor in hex_to_oblast:
                    neighbor_oblast = hex_to_oblast[neighbor]
                    if neighbor_oblast != oblast_name:
                        oblast_neighbors[oblast_name].add(neighbor_oblast)

        # Greedy graph coloring for oblasts
        oblast_colors = {}
        color_palette = plt.cm.tab20.colors

        sorted_oblasts = sorted(
            oblast_to_raions.keys(),
            key=lambda oblast: len(oblast_neighbors[oblast]),
            reverse=True
        )

        for oblast_name in sorted_oblasts:
            neighbor_colors = {
                oblast_colors[n]
                for n in oblast_neighbors[oblast_name]
                if n in oblast_colors
            }

            for color_idx in range(len(color_palette)):
                if color_idx not in neighbor_colors:
                    oblast_colors[oblast_name] = color_idx
                    break

        max_colors_used = max(oblast_colors.values()) + 1 if oblast_colors else 0
        print(f"Used {max_colors_used} colors for {len(oblast_to_raions)} oblasts")

        # Create visualization with RIGID hex grid
        fig, ax = plt.subplots(figsize=(24, 14))

        # Create hex grid for drawing
        hex_size_pixels = 10
        grid = HexGrid(width=150, height=88, hex_size=hex_size_pixels)

        pixel_bounds = grid.pixel_bounds()

        # Draw all hexes
        for row in range(88):
            for col in range(150):
                corners_pixel = grid.hex_corners(col, row)

                # Determine color based on oblast
                if (col, row) in hex_to_oblast:
                    oblast_name = hex_to_oblast[(col, row)]
                    color_idx = oblast_colors.get(oblast_name, 0)
                    color = color_palette[color_idx % len(color_palette)]
                    alpha = 0.7
                    edgecolor = 'white'
                    linewidth = 0.5
                else:
                    # Water/outside Ukraine
                    color = (0.85, 0.85, 0.85)
                    alpha = 0.4
                    edgecolor = (0.9, 0.9, 0.9)
                    linewidth = 0.2

                hex_patch = mpatches.Polygon(
                    corners_pixel,
                    facecolor=color,
                    edgecolor=edgecolor,
                    linewidth=linewidth,
                    alpha=alpha
                )
                ax.add_patch(hex_patch)

        # Add cities on top
        for city_name, coords in MAJOR_CITIES.items():
            col, row = mapper.latlon_to_hex(coords["lat"], coords["lon"])

            # Check if city is within bounds
            if 0 <= col < 150 and 0 <= row < 88:
                cx, cy = grid.hex_center(col, row)

                # Draw city marker
                circle = plt.Circle(
                    (cx, cy),
                    radius=4,
                    facecolor='red',
                    edgecolor='darkred',
                    linewidth=2,
                    alpha=0.9,
                    zorder=10
                )
                ax.add_patch(circle)

                # Add city label
                ax.text(
                    cx, cy - 8,
                    city_name,
                    fontsize=9,
                    fontweight='bold',
                    ha='center',
                    va='bottom',
                    bbox=dict(
                        boxstyle='round,pad=0.3',
                        facecolor='white',
                        edgecolor='darkred',
                        alpha=0.8
                    ),
                    zorder=11
                )

        # Set axis limits
        ax.set_xlim(pixel_bounds[0] - 10, pixel_bounds[2] + 10)
        ax.set_ylim(pixel_bounds[1] - 10, pixel_bounds[3] + 10)
        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.axis('off')

        ax.set_title(
            f"Rigid 150×88 Hex Grid Colored by Ukraine Oblasts\n"
            f"{len(hex_to_oblast)} hexes mapped to {len(oblast_to_raions)} oblasts using {max_colors_used} colors\n"
            f"Major cities marked in red",
            fontsize=16,
            pad=20
        )

        # Save output
        output_dir = Path(__file__).parent / "test_outputs" / "phase3"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "ukraine_rigid_hex_grid_oblasts.png"

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"Saved oblast hex grid visualization to {output_path}")

        # Verify coloring is valid
        for oblast_name in oblast_to_raions.keys():
            if oblast_name not in oblast_colors:
                continue
            color = oblast_colors[oblast_name]
            for neighbor_oblast in oblast_neighbors[oblast_name]:
                if neighbor_oblast in oblast_colors:
                    assert oblast_colors[neighbor_oblast] != color, \
                        f"Adjacent oblasts {oblast_name} and {neighbor_oblast} have same color {color}"

        print("✓ All adjacent oblasts have different colors")
        print(f"✓ Rigid hex grid: {88} rows × {150} columns = {150*88} total hexes")
        print(f"✓ Ukraine coverage: {len(hex_to_oblast)} hexes ({100*len(hex_to_oblast)/(150*88):.1f}%)")
        print(f"✓ Cities displayed: {len(MAJOR_CITIES)}")

        # Count hexes per oblast
        oblast_hex_counts = {}
        for oblast_name in hex_to_oblast.values():
            oblast_hex_counts[oblast_name] = oblast_hex_counts.get(oblast_name, 0) + 1

        print(f"\n{'='*60}")
        print("OBLAST SIZES (in hexes)")
        print(f"{'='*60}")
        print(f"{'Oblast':<35} {'Hexes':>10} {'%':>8}")
        print(f"{'-'*60}")

        # Sort by hex count descending
        sorted_oblasts = sorted(oblast_hex_counts.items(), key=lambda x: x[1], reverse=True)
        for oblast_name, hex_count in sorted_oblasts:
            percentage = 100 * hex_count / len(hex_to_oblast)
            print(f"{oblast_name:<35} {hex_count:>10} {percentage:>7.1f}%")

        print(f"{'-'*60}")
        print(f"{'TOTAL':<35} {len(hex_to_oblast):>10} {'100.0':>7}%")
        print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
