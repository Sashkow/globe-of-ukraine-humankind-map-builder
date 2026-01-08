#!/usr/bin/env python3
"""
Incremental Ukraine Map Builder

Builds Ukraine map incrementally from a working template, making ONE change at a time
to identify exactly what breaks editor compatibility.

Steps:
1. step1_baseline.hmap - Just re-package template (verify ZIP works)
2. step2_land_ocean.hmap - Set zones to match Ukraine shape (1 land territory + ocean)
3. step3_territories.hmap - Add 140 territories (zones texture + territory DB)
4. step4_biomes.hmap - Add biome assignments to territories
5. step5_elevation.hmap - Add SRTM elevation data
6. step6_rivers.hmap - Add Natural Earth rivers
7. step7_terrain.hmap - Add terrain types (forest, steppe, mountains, etc.)
"""

import zipfile
import base64
import io
import re
import shutil
import json
from pathlib import Path
from datetime import datetime
from PIL import Image
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import yaml
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import RegularPolygon
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D


VERSION_FILE = Path(__file__).parent / "output" / ".build_version.json"


def get_next_version() -> dict:
    """Get and increment the build version."""
    if VERSION_FILE.exists():
        with open(VERSION_FILE, 'r') as f:
            data = json.load(f)
        data['build'] += 1
    else:
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {'major': 0, 'minor': 1, 'build': 1}

    data['timestamp'] = datetime.now().isoformat()

    with open(VERSION_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    return data


def get_version_string(version: dict) -> str:
    """Format version as string."""
    return f"v{version['major']}.{version['minor']}.{version['build']}"


class IncrementalMapBuilder:
    """Build Ukraine maps incrementally from a template."""

    def __init__(self, template_path: Path):
        """Load template and config."""
        self.template_path = template_path
        print(f"Loading template: {template_path}")

        # Load config
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Load template files
        with zipfile.ZipFile(template_path, 'r') as zf:
            self.descriptor_content = zf.read('Descriptor.hmd').decode('utf-8-sig')
            self.save_content = zf.read('Save.hms').decode('utf-8-sig')

        # Parse dimensions from template
        width_match = re.search(r'<Width>(\d+)</Width>', self.save_content)
        height_match = re.search(r'<Height>(\d+)</Height>', self.save_content)
        self.width = int(width_match.group(1))
        self.height = int(height_match.group(1))
        print(f"Template dimensions: {self.width}x{self.height}")

        # Geographic bounds from config
        active = self.config['active_config']
        bounds = self.config['bounds'][active]
        self.min_lon = bounds['min_lon']
        self.max_lon = bounds['max_lon']
        self.min_lat = bounds['min_lat']
        self.max_lat = bounds['max_lat']
        print(f"Bounds: {self.min_lon}-{self.max_lon}°E, {self.min_lat}-{self.max_lat}°N")

        # Load Ukraine raion data
        raion_path = Path(__file__).parent / self.config['ukraine']['raions_file']
        self.raions_gdf = gpd.read_file(raion_path)
        print(f"Loaded {len(self.raions_gdf)} raions")

        # Output directory
        self.output_dir = Path(__file__).parent / "output" / "incremental"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Store intermediate results
        self.current_save_content = self.save_content
        self.current_descriptor_content = self.descriptor_content
        self.hex_to_territory = None

        # Enable procedural mountain chains for proper mountain rendering
        self._enable_procedural_mountains()

    def _enable_procedural_mountains(self):
        """Enable UseProceduralMountainChains flag for proper mountain rendering."""
        # Update in both template and current content
        old_value = '<UseProceduralMountainChains>false</UseProceduralMountainChains>'
        new_value = '<UseProceduralMountainChains>true</UseProceduralMountainChains>'

        if old_value in self.save_content:
            self.save_content = self.save_content.replace(old_value, new_value)
            self.current_save_content = self.current_save_content.replace(old_value, new_value)
            print("Enabled UseProceduralMountainChains=true")

    def _pixel_to_geo(self, col: int, row: int) -> tuple[float, float]:
        """Convert pixel coordinates to geographic coordinates."""
        lon = self.min_lon + (col / self.width) * (self.max_lon - self.min_lon)
        lat = self.max_lat - (row / self.height) * (self.max_lat - self.min_lat)
        return lon, lat

    def _geo_to_pixel(self, lon: float, lat: float) -> tuple[int, int]:
        """Convert geographic coordinates to pixel coordinates."""
        col = int((lon - self.min_lon) / (self.max_lon - self.min_lon) * self.width)
        row = int((self.max_lat - lat) / (self.max_lat - self.min_lat) * self.height)
        # Clamp to valid range
        col = max(0, min(self.width - 1, col))
        row = max(0, min(self.height - 1, row))
        return col, row

    def _save_hmap(self, save_content: str, descriptor_content: str, output_path: Path):
        """Save as .hmap file (ZIP archive)."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('Save.hms', save_content.encode('utf-8-sig'))
            zf.writestr('Descriptor.hmd', descriptor_content.encode('utf-8-sig'))
        print(f"  Saved: {output_path.name}")

    def _update_texture_bytes(self, content: str, texture_name: str, new_base64: str) -> str:
        """Update a texture's base64 bytes in the save content."""
        pattern = rf'(<{texture_name}\.Bytes Length=")(\d+)(">)([^<]*)(</)'

        def replacer(match):
            return f'{match.group(1)}{len(new_base64)}{match.group(3)}{new_base64}{match.group(5)}'

        result = re.sub(pattern, replacer, content)
        return result

    def step1_baseline(self) -> Path:
        """Step 1: Just re-package template unchanged."""
        print("\n" + "=" * 60)
        print("STEP 1: Baseline (re-package template)")
        print("=" * 60)
        print("  Change: None (just verify ZIP packaging works)")

        output_path = self.output_dir / "step1_baseline.hmap"
        self._save_hmap(self.save_content, self.descriptor_content, output_path)

        return output_path

    def step2_land_ocean(self) -> Path:
        """Step 2: Set zones to match Ukraine shape (1 land + ocean)."""
        print("\n" + "=" * 60)
        print("STEP 2: Land/Ocean Match Ukraine Shape")
        print("=" * 60)
        print("  Change: ZonesTexture.Bytes + TerritoryDatabase (2 territories: ocean + land)")

        # Build Ukraine mask
        self.hex_to_territory = {}
        print("  Building Ukraine land mask...")

        total_pixels = self.height * self.width
        for row in range(self.height):
            if row % 10 == 0:
                progress = (row * self.width) / total_pixels * 100
                print(f"    Row {row}/{self.height} ({progress:.0f}%)...")
            for col in range(self.width):
                lon, lat = self._pixel_to_geo(col, row)
                point = Point(lon, lat)

                # Check if point is in any raion (= land)
                is_land = False
                for idx, raion in self.raions_gdf.iterrows():
                    if raion.geometry.contains(point):
                        is_land = True
                        break

                # 0 = ocean, 1 = land
                self.hex_to_territory[(col, row)] = 1 if is_land else 0

        # Statistics
        land_pixels = sum(1 for t in self.hex_to_territory.values() if t == 1)
        ocean_pixels = sum(1 for t in self.hex_to_territory.values() if t == 0)
        print(f"  Land pixels: {land_pixels} ({land_pixels / (self.width * self.height) * 100:.1f}%)")
        print(f"  Ocean pixels: {ocean_pixels}")

        # Create zones texture PNG (0=ocean, 1=land)
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 255))
        pixels = img.load()
        for (col, row), territory_idx in self.hex_to_territory.items():
            pixels[col, row] = (territory_idx, 0, 0, 255)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        zones_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')

        # Create territory database: 0=ocean, 1=land (Temperate biome like template)
        territory_db_xml = """        <TerritoryDatabase>
            <Territories Length="2">
                <Item>
                    <ContinentIndex>0</ContinentIndex>
                    <Biome>0</Biome>
                    <IsOcean>true</IsOcean>
                </Item>
                <Item>
                    <ContinentIndex>1</ContinentIndex>
                    <Biome>7</Biome>
                    <IsOcean>false</IsOcean>
                </Item>
            </Territories>
        </TerritoryDatabase>"""

        # Update save content
        content = self._update_texture_bytes(self.save_content, 'ZonesTexture', zones_b64)
        content = re.sub(
            r'<TerritoryDatabase>.*?</TerritoryDatabase>',
            territory_db_xml.strip(),
            content,
            flags=re.DOTALL
        )

        self.current_save_content = content

        output_path = self.output_dir / "step2_land_ocean.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        return output_path

    def step3_territories(self) -> Path:
        """Step 3: Add 141 territories (zones texture + territory database).

        Includes:
        - 140 raions from GeoJSON
        - Snake Island (Zmiinyi) as special 1-hex territory
        """
        print("\n" + "=" * 60)
        print("STEP 3: Add Territories (140 raions + Snake Island)")
        print("=" * 60)
        print("  Change: ZonesTexture.Bytes + TerritoryDatabase")

        # Assign each pixel to a raion
        hex_to_raion = {}
        print("  Assigning pixels to raions...")

        total_pixels = self.height * self.width
        for row in range(self.height):
            if row % 10 == 0:
                progress = (row * self.width) / total_pixels * 100
                print(f"    Row {row}/{self.height} ({progress:.0f}%)...")
            for col in range(self.width):
                lon, lat = self._pixel_to_geo(col, row)
                point = Point(lon, lat)

                # Find containing raion
                found = False
                for idx, raion in self.raions_gdf.iterrows():
                    if raion.geometry.contains(point):
                        # Territory index = raion index + 1 (0 is ocean)
                        hex_to_raion[(col, row)] = idx + 1
                        found = True
                        break

                if not found:
                    hex_to_raion[(col, row)] = 0  # Ocean

        # Add Snake Island (Zmiinyi) - 45.255°N, 30.204°E
        # Use territory index = len(raions) + 1 (after all raions)
        snake_island_idx = len(self.raions_gdf) + 1
        snake_island_col, snake_island_row = self._geo_to_pixel(30.204, 45.255)
        if 0 <= snake_island_col < self.width and 0 <= snake_island_row < self.height:
            hex_to_raion[(snake_island_col, snake_island_row)] = snake_island_idx
            print(f"  Added Snake Island at ({snake_island_col}, {snake_island_row}) as territory {snake_island_idx}")
        else:
            print(f"  WARNING: Snake Island coordinates outside map bounds")
            snake_island_idx = None

        # NOTE: Coastal extension into sea was removed - it caused the Perekop/Syvash
        # strait between mainland Ukraine and Crimea to fill in completely.
        # If coastal territory extension is needed, it should exclude narrow straits.

        self.hex_to_raion = hex_to_raion
        self.snake_island_idx = snake_island_idx

        # Statistics
        # Total territories: ocean (0) + raions (1-140) + Snake Island (141)
        num_territories = len(self.raions_gdf) + 1  # +1 for ocean
        if snake_island_idx is not None:
            num_territories += 1  # +1 for Snake Island

        counts = {}
        for t in hex_to_raion.values():
            counts[t] = counts.get(t, 0) + 1
        land_pixels = sum(c for t, c in counts.items() if t > 0)
        print(f"  Total territories: {num_territories} (including ocean and Snake Island)")
        print(f"  Land/coastal pixels: {land_pixels} ({land_pixels / (self.width * self.height) * 100:.1f}%)")
        print(f"  Deep ocean pixels: {counts.get(0, 0)}")
        if snake_island_idx:
            print(f"  Snake Island pixels: {counts.get(snake_island_idx, 0)}")

        # Create zones texture PNG
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 255))
        pixels = img.load()
        for (col, row), territory_idx in hex_to_raion.items():
            pixels[col, row] = (territory_idx, 0, 0, 255)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        zones_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        print(f"  Zones texture: {len(zones_b64)} chars")

        # Create territory database XML
        territory_items = []
        # Territory 0 = ocean
        territory_items.append("""            <Item>
                <ContinentIndex>0</ContinentIndex>
                <Biome>0</Biome>
                <IsOcean>true</IsOcean>
            </Item>""")
        # Territories 1-140 = raions (all with Temperate biome 7)
        for i in range(len(self.raions_gdf)):
            territory_items.append(f"""            <Item>
                <ContinentIndex>1</ContinentIndex>
                <Biome>7</Biome>
                <IsOcean>false</IsOcean>
            </Item>""")
        # Territory 141 = Snake Island (if added)
        if snake_island_idx is not None:
            territory_items.append(f"""            <Item>
                <ContinentIndex>1</ContinentIndex>
                <Biome>7</Biome>
                <IsOcean>false</IsOcean>
            </Item>""")

        territory_db_xml = f"""        <TerritoryDatabase>
            <Territories Length="{num_territories}">
{chr(10).join(territory_items)}
            </Territories>
        </TerritoryDatabase>"""

        # Update save content from step2 (land/ocean)
        content = self._update_texture_bytes(self.current_save_content, 'ZonesTexture', zones_b64)

        # Replace territory database
        content = re.sub(
            r'<TerritoryDatabase>.*?</TerritoryDatabase>',
            territory_db_xml.strip(),
            content,
            flags=re.DOTALL
        )

        self.current_save_content = content

        output_path = self.output_dir / "step3_territories.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        return output_path

    def step4_biomes(self) -> Path:
        """Step 4: Add biome assignments to territories."""
        print("\n" + "=" * 60)
        print("STEP 4: Add Biomes")
        print("=" * 60)
        print("  Change: Biome field in TerritoryDatabase items")

        # Humankind biome IDs:
        # 0=Arctic, 1=Badlands, 2=Desert, 3=Grassland, 4=Mediterranean,
        # 5=Savanna, 6=Taiga, 7=Temperate, 8=Tropical, 9=Tundra

        # Ukrainian geography biome mapping:
        # - Western Ukraine (Carpathians, forests): Temperate (7)
        # - Northern Ukraine (Polesia, marshes/forests): Taiga (6) or Temperate (7)
        # - Central Ukraine (forest-steppe): Temperate (7) / Grassland (3) mix
        # - Southern/Eastern Ukraine (steppe): Grassland (3)
        # - Black Sea coast: Mediterranean (4)
        # - Crimea mountains/coast: Mediterranean (4)
        # - Dry steppe areas (SE): Savanna (5) or Badlands (1)

        oblast_biomes = {
            # Western (Carpathian/Forest) - Temperate
            'Lvivska': 7, 'Volynska': 7, 'Rivnenska': 7,
            'Ivano-Frankivska': 7, 'Zakarpatska': 7, 'Chernivetska': 7, 'Ternopilska': 7,

            # Northern (Polesia - marshes/forests) - Taiga
            'Zhytomyrska': 6, 'Chernihivska': 6,

            # Central (Forest-steppe) - Temperate
            'Kyiv': 7, 'Kyivska': 7, 'Khmelnytska': 7, 'Vinnytska': 7,
            'Cherkaska': 7, 'Sumska': 7,

            # Central-East (Steppe transition) - Grassland
            'Poltavska': 3, 'Kharkivska': 3,

            # Eastern (Steppe/Industrial) - Grassland with some Badlands
            'Donetska': 3, 'Luhanska': 3, 'Dnipropetrovska': 3,

            # Southern (Steppe) - Grassland
            'Kirovohradska': 3, 'Zaporizka': 3,

            # Southern coast (Dry steppe) - Savanna
            'Khersonska': 5, 'Mykolaivska': 5,

            # Southwest (Black Sea coast) - Mediterranean
            'Odeska': 4,

            # Crimea - Mediterranean
            'Autonomous Republic of Crimea': 4, 'Sevastopol': 4,
        }

        # Get biome for each raion based on oblast
        # Store as instance variable for use in step7
        self.raion_biomes = []
        for idx, raion in self.raions_gdf.iterrows():
            oblast = raion.get('adm1_name', '')
            biome = oblast_biomes.get(oblast, 7)  # Default to Temperate
            self.raion_biomes.append(biome)

        # Count biomes
        biome_counts = {}
        for b in self.raion_biomes:
            biome_counts[b] = biome_counts.get(b, 0) + 1
        print(f"  Biome distribution: {biome_counts}")

        # Create updated territory database
        territory_items = []
        # Territory 0 = ocean (Arctic biome = 0)
        territory_items.append("""            <Item>
                <ContinentIndex>0</ContinentIndex>
                <Biome>0</Biome>
                <IsOcean>true</IsOcean>
            </Item>""")
        # Territories 1-139 = raions with biomes
        for i, biome in enumerate(self.raion_biomes):
            territory_items.append(f"""            <Item>
                <ContinentIndex>1</ContinentIndex>
                <Biome>{biome}</Biome>
                <IsOcean>false</IsOcean>
            </Item>""")

        num_territories = len(self.raions_gdf) + 1
        territory_db_xml = f"""        <TerritoryDatabase>
            <Territories Length="{num_territories}">
{chr(10).join(territory_items)}
            </Territories>
        </TerritoryDatabase>"""

        # Update content
        content = re.sub(
            r'<TerritoryDatabase>.*?</TerritoryDatabase>',
            territory_db_xml.strip(),
            self.current_save_content,
            flags=re.DOTALL
        )

        self.current_save_content = content

        output_path = self.output_dir / "step4_biomes.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        return output_path

    def step5_elevation(self) -> Path:
        """Step 5: Add SRTM-based elevation data."""
        print("\n" + "=" * 60)
        print("STEP 5: SRTM Elevation")
        print("=" * 60)
        print("  Change: ElevationTexture.Bytes from real SRTM data")

        from data_fetchers.srtm_elevation import SRTMElevationFetcher
        from hex_elevation_mapper import HexElevationMapper

        # Build bounds dict
        bounds = {
            'min_lon': self.min_lon,
            'max_lon': self.max_lon,
            'min_lat': self.min_lat,
            'max_lat': self.max_lat
        }

        # Fetch SRTM data
        print("  Fetching SRTM elevation data...")
        fetcher = SRTMElevationFetcher(bounds)
        fetcher.fetch()

        # Create mapper
        mapper = HexElevationMapper(fetcher, self.width, self.height, bounds)

        # Build ukraine mask from hex_to_raion (land = raion > 0)
        ukraine_mask = None
        if hasattr(self, 'hex_to_raion') and self.hex_to_raion:
            ukraine_mask = {k: v > 0 for k, v in self.hex_to_raion.items()}
            print(f"  Using Ukraine land mask ({sum(ukraine_mask.values())} land hexes)")

        # Get quantized elevations
        hex_elevations = mapper.get_hex_elevations(ukraine_mask)

        # Print statistics
        stats = mapper.get_elevation_stats()
        print(f"\n  Elevation Statistics:")
        print(f"    Raw range: {stats['raw_min']:.0f} to {stats['raw_max']:.0f} m")
        print(f"    NoData hexes: {stats['nodata_count']}")
        print(f"    Level distribution:")
        for level, count in stats['level_distribution'].items():
            pct = count / stats['total_hexes'] * 100
            print(f"      Level {level:3d}: {count:5d} hexes ({pct:4.1f}%)")

        # Validate known points
        print(f"\n  Validation:")
        validation = mapper.validate_known_points()
        all_ok = True
        for name, data in validation.items():
            status = "✓" if data['ok'] else "✗"
            if not data['ok']:
                all_ok = False
            print(f"    {status} {name}: {data['meters']:.0f}m → level {data['level']}")
        if all_ok:
            print("    All validation points OK!")

        # Create elevation texture PNG
        # Based on template analysis:
        # - R channel: elevation level (1=water base, higher=land elevation)
        # - G channel: 119 for water, 120 for land
        # - B channel: 0
        # - A channel: 0 (not 255!)
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        pixels = img.load()

        for (col, row), level in hex_elevations.items():
            # Convert level (-3 to 12) to pixel values
            # Ocean (level < 0): R=1, G=119
            # Land (level >= 0): R=level+4 (so level 0 -> R=4, level 1 -> R=5, etc.), G=120
            if level < 0:
                # Water - use R=1 for ocean depth variation could be 1-3
                r_value = max(1, 4 + level)  # level -3 -> 1, level -1 -> 3
                g_value = 119
            else:
                # Land - R increases with elevation
                r_value = min(15, 4 + level)  # level 0 -> 4, level 1 -> 5, etc.
                g_value = 120
            pixels[col, row] = (r_value, g_value, 0, 0)

        # Encode as base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        elevation_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        print(f"\n  Elevation texture: {len(elevation_b64)} chars")

        # Update save content
        content = self._update_texture_bytes(
            self.current_save_content, 'ElevationTexture', elevation_b64
        )

        self.current_save_content = content

        output_path = self.output_dir / "step5_elevation.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        # Save elevation visualization
        self._save_elevation_visualization(hex_elevations)

        return output_path

    def _save_elevation_visualization(self, hex_elevations: dict):
        """Save a visualization of the elevation data with hex grid overlay."""

        # Create elevation array
        elev_array = np.zeros((self.height, self.width), dtype=np.float32)
        for (col, row), level in hex_elevations.items():
            elev_array[row, col] = level

        # Custom colormap: blue (ocean) -> green (low) -> brown (mid) -> white (high)
        colors = [
            '#000080',  # -3: Deep ocean (dark blue)
            '#0000CD',  # -2: Ocean (medium blue)
            '#4169E1',  # -1: Shallow water (royal blue)
            '#90EE90',  # 0: Coastal (light green)
            '#32CD32',  # 1: Low plains (lime green)
            '#228B22',  # 2: Plains (forest green)
            '#6B8E23',  # 3: Rolling plains (olive drab)
            '#BDB76B',  # 4: Low hills (dark khaki)
            '#D2B48C',  # 5: Hills (tan)
            '#CD853F',  # 6: High hills (peru)
            '#8B4513',  # 7: Low mountains (saddle brown)
            '#A0522D',  # 8: Mountains (sienna)
            '#D2691E',  # 9: High mountains (chocolate)
            '#BC8F8F',  # 10: Alpine (rosy brown)
            '#C0C0C0',  # 11: High alpine (silver)
            '#FFFFFF',  # 12: Peaks (white)
        ]
        cmap = mcolors.ListedColormap(colors)
        bounds_cmap = list(range(-3, 14))
        norm = mcolors.BoundaryNorm(bounds_cmap, cmap.N)

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)

        # === Figure 1: Simple elevation raster ===
        _fig, ax = plt.subplots(figsize=(16, 9))
        im = ax.imshow(elev_array, cmap=cmap, norm=norm, aspect='auto')
        ax.set_title('Ukraine SRTM Elevation (Quantized to Game Levels)', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')
        cbar = plt.colorbar(im, ax=ax, ticks=range(-3, 13))
        cbar.set_label('Elevation Level')
        viz_path = viz_dir / "ukraine_srtm_elevation.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved elevation visualization: {viz_path}")

        # === Figure 2: Hex grid visualization ===
        _fig, ax = plt.subplots(figsize=(20, 12))

        # Create hexagons for each cell
        hex_size = 0.5  # Radius of hexagon
        patches = []
        patch_colors = []

        for row in range(self.height):
            for col in range(self.width):
                level = hex_elevations.get((col, row), -2)

                # Offset coordinates for hex grid (odd rows shifted)
                x = col + (0.5 if row % 2 == 1 else 0)
                y = self.height - row - 1  # Flip Y for display

                # Create hexagon (pointy-top orientation)
                hex_patch = RegularPolygon(
                    (x, y * 0.866),  # 0.866 = sqrt(3)/2 for hex spacing
                    numVertices=6,
                    radius=hex_size,
                    orientation=np.pi / 6,  # Pointy top
                    edgecolor='#333333',
                    linewidth=0.3
                )
                patches.append(hex_patch)

                # Map level to color index (level -3 to 12 -> index 0 to 15)
                color_idx = max(0, min(15, level + 3))
                patch_colors.append(colors[color_idx])

        # Add all hexagons
        for patch, color in zip(patches, patch_colors):
            patch.set_facecolor(color)
            ax.add_patch(patch)

        ax.set_xlim(-1, self.width + 1)
        ax.set_ylim(-1, self.height * 0.866 + 1)
        ax.set_aspect('equal')
        ax.set_title('Ukraine Elevation Hex Map (SRTM Data)', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        # Add colorbar manually
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, ticks=range(-3, 13), shrink=0.8)
        cbar.set_label('Elevation Level')

        hex_viz_path = viz_dir / "ukraine_elevation_hexmap.png"
        plt.savefig(hex_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved hex map visualization: {hex_viz_path}")

    def step6_rivers(self) -> Path:
        """Step 6: Add rivers from Natural Earth data.

        Rivers are classified into:
        - Regular rivers: Mapped with river texture (R=1)
        - Reservoirs: Large artificial lakes, mapped as Lake terrain in step7
        - Porohy: Rapids where banks have steep elevation difference, mapped as Lake terrain

        Reservoirs and porohy are stored for use in step7_terrain.
        """
        print("\n" + "=" * 60)
        print("STEP 6: Rivers")
        print("=" * 60)
        print("  Change: RiverTexture.Bytes from Natural Earth data")
        print("  Classification: regular rivers, reservoirs, porohy")

        from river_mapper import RiverMapper
        from data_fetchers.srtm_elevation import SRTMElevationFetcher

        # Build bounds dict
        bounds = {
            'min_lon': self.min_lon,
            'max_lon': self.max_lon,
            'min_lat': self.min_lat,
            'max_lat': self.max_lat
        }

        # Create river mapper
        mapper = RiverMapper(bounds, self.width, self.height)

        # Build ukraine mask from hex_to_raion (land = raion > 0)
        ukraine_mask = None
        if hasattr(self, 'hex_to_raion') and self.hex_to_raion:
            ukraine_mask = {k: v > 0 for k, v in self.hex_to_raion.items()}
            print(f"  Using Ukraine land mask ({sum(ukraine_mask.values())} land hexes)")

        # Get elevation data for porohy detection
        print("  Loading elevation data for porohy detection...")
        srtm_fetcher = SRTMElevationFetcher(bounds)
        elevation_grid = srtm_fetcher.get_grid_elevations(self.width, self.height)

        # Classify rivers
        print("  Classifying rivers...")
        classification = mapper.classify_rivers(
            elevation_grid=elevation_grid,
            land_mask=ukraine_mask
        )

        # Store classification, elevation_grid, and mapper for step7
        self.river_classification = classification
        self.river_elevation_grid = elevation_grid
        self.river_mapper = mapper

        # Summary
        print(f"\n  River Classification Summary:")
        print(f"    Regular rivers: {len(classification.regular_rivers)} hexes (river texture)")
        print(f"    Dnipro: {len(classification.dnipro)} hexes (Lake terrain, consecutive chain)")
        print(f"    Lakes + Reservoirs: {len(classification.lakes)} hexes (Lake terrain)")
        lake_terrain_total = len(classification.dnipro) + len(classification.lakes)
        print(f"    Total Lake terrain: {lake_terrain_total} hexes")

        # Convert elevation grid to dict for flow direction calculation
        elevation_map = {}
        for row in range(self.height):
            for col in range(self.width):
                elevation_map[(col, row)] = int(elevation_grid[row, col])

        # Create river texture ONLY for regular rivers
        # Reservoirs and porohy will be handled as Lake terrain in step7
        # Pass elevation_map for proper downstream flow direction encoding
        river_texture = mapper.create_river_texture(
            ukraine_mask=ukraine_mask,
            river_hexes=classification.regular_rivers,
            elevation_map=elevation_map
        )

        # Count river hexes in texture (R < 255 means river, R=255 means no river)
        river_count = np.sum(river_texture[:, :, 0] < 255)
        print(f"  River hexes in texture: {river_count}")

        # Convert to PIL Image and encode
        img = Image.fromarray(river_texture, mode='RGBA')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        river_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        print(f"  River texture: {len(river_b64)} chars")

        # Update save content
        content = self._update_texture_bytes(
            self.current_save_content, 'RiverTexture', river_b64
        )

        self.current_save_content = content

        output_path = self.output_dir / "step6_rivers.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        # Save river visualization with classification
        self._save_river_visualization_classified(classification, ukraine_mask)

        return output_path

    def _save_river_visualization(self, river_hexes: set, ukraine_mask: dict = None):
        """Save a visualization of rivers."""

        # Create array: 0=ocean, 1=land, 2=river
        arr = np.zeros((self.height, self.width), dtype=np.uint8)

        if ukraine_mask:
            for (col, row), is_land in ukraine_mask.items():
                if is_land:
                    arr[row, col] = 1

        for col, row in river_hexes:
            if ukraine_mask is None or ukraine_mask.get((col, row), False):
                arr[row, col] = 2

        _fig, ax = plt.subplots(figsize=(16, 9))
        cmap = plt.cm.colors.ListedColormap(['#4169E1', '#90EE90', '#0000CD'])
        ax.imshow(arr, cmap=cmap, aspect='auto')
        ax.set_title('Ukraine Rivers (Natural Earth)', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        viz_path = viz_dir / "ukraine_rivers.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved river visualization: {viz_path}")

    def _save_river_visualization_classified(self, classification, ukraine_mask: dict = None):
        """Save a visualization of classified rivers (regular, reservoir, porohy, lakes)."""

        # Create array: 0=ocean, 1=land, 2=regular river, 3=reservoir, 4=porohy, 5=lake
        arr = np.zeros((self.height, self.width), dtype=np.uint8)

        if ukraine_mask:
            for (col, row), is_land in ukraine_mask.items():
                if is_land:
                    arr[row, col] = 1

        for col, row in classification.regular_rivers:
            if ukraine_mask is None or ukraine_mask.get((col, row), False):
                arr[row, col] = 2

        for col, row in classification.lakes:
            if ukraine_mask is None or ukraine_mask.get((col, row), False):
                arr[row, col] = 3

        for col, row in classification.dnipro:
            if ukraine_mask is None or ukraine_mask.get((col, row), False):
                arr[row, col] = 4

        _fig, ax = plt.subplots(figsize=(16, 9))
        # 0=ocean, 1=land, 2=river, 3=lake/reservoir, 4=dnipro
        cmap = plt.cm.colors.ListedColormap([
            '#4169E1',  # 0: Ocean - royal blue
            '#90EE90',  # 1: Land - light green
            '#0000CD',  # 2: Regular river - medium blue
            '#1E90FF',  # 3: Lake/Reservoir - dodger blue
            '#00008B',  # 4: Dnipro - dark blue
        ])
        ax.imshow(arr, cmap=cmap, aspect='auto')
        ax.set_title('Ukraine Rivers & Lakes - Classified', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        # Add legend
        legend_elements = [
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#4169E1', markersize=10, label='Ocean'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#90EE90', markersize=10, label='Land'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#0000CD', markersize=10, label='Regular River'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#1E90FF', markersize=10, label='Lake/Reservoir'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#00008B', markersize=10, label='Dnipro (Lake Chain)'),
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=9)

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        viz_path = viz_dir / "ukraine_rivers_classified.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved classified river visualization: {viz_path}")

    def _get_terrain_names_order(self) -> list:
        """Parse terrain names order from current Save.hms TerrainTypeNames."""
        match = re.search(
            r'<TerrainTypeNames[^>]*>(.*?)</TerrainTypeNames>',
            self.current_save_content,
            re.DOTALL
        )
        if match:
            terrain_xml = match.group(1)
            names = re.findall(r'<String>([^<]+)</String>', terrain_xml)
            return names
        return None

    def step7_terrain(self) -> Path:
        """Step 7: Add terrain types based on Copernicus land cover data."""
        print("\n" + "=" * 60)
        print("STEP 7: Terrain Types (Copernicus Land Cover)")
        print("=" * 60)
        print("  Change: ElevationTexture G channel with terrain encoding")

        from terrain_mapper import TerrainMapper
        from data_fetchers.srtm_elevation import SRTMElevationFetcher
        from data_fetchers.landcover_fetcher_copernicus import CopernicusLandCoverFetcher
        from hex_elevation_mapper import HexElevationMapper
        from river_mapper import RiverMapper

        bounds = {
            'min_lon': self.min_lon,
            'max_lon': self.max_lon,
            'min_lat': self.min_lat,
            'max_lat': self.max_lat
        }

        # Get terrain names order from Save.hms
        terrain_names = self._get_terrain_names_order()
        if terrain_names:
            print(f"  Terrain names from Save.hms: {terrain_names}")
        else:
            print("  WARNING: Could not parse TerrainTypeNames, using defaults")

        # Get elevation data
        print("  Loading elevation data...")
        fetcher = SRTMElevationFetcher(bounds)
        elev_mapper = HexElevationMapper(fetcher, self.width, self.height, bounds)

        # Build land mask
        ukraine_mask = None
        if hasattr(self, 'hex_to_raion') and self.hex_to_raion:
            ukraine_mask = {k: v > 0 for k, v in self.hex_to_raion.items()}
            print(f"  Using Ukraine land mask ({sum(ukraine_mask.values())} land hexes)")

        hex_elevations = elev_mapper.get_hex_elevations(ukraine_mask)

        # Get Copernicus land cover data
        print("  Loading Copernicus land cover data...")
        landcover_fetcher = CopernicusLandCoverFetcher(bounds)
        landcover_grid = landcover_fetcher.get_grid_landcover(self.width, self.height)
        print(f"  Land cover grid shape: {landcover_grid.shape}")

        # Get lake-terrain hexes from step6 classification
        # These are: Dnipro (consecutive lake chain) and natural lakes ONLY
        # Regular rivers are NOT rendered as lakes anymore
        print("  Getting lake terrain hexes from step6 classification...")
        lake_terrain_hexes = set()
        dnipro_elevations = {}  # Special elevation overrides for Dnipro
        lake_elevations = {}    # Elevation overrides for natural lakes
        if hasattr(self, 'river_classification') and self.river_classification:
            lake_terrain_hexes = (
                self.river_classification.dnipro |
                self.river_classification.lakes
            )
            print(f"  Lake terrain hexes: {len(lake_terrain_hexes)}")
            print(f"    Dnipro: {len(self.river_classification.dnipro)}")
            print(f"    Lakes + Reservoirs: {len(self.river_classification.lakes)}")

            # Calculate Dnipro bank elevations (one level lower than minimum bank)
            # Use hex_elevations (game levels) not raw SRTM meters
            if hasattr(self, 'river_mapper') and self.river_mapper:
                print("  Calculating Dnipro bank elevations...")
                dnipro_elevations = self.river_mapper.get_dnipro_bank_elevations(
                    self.river_classification.dnipro,
                    hex_elevations,
                    ukraine_mask
                )
                print(f"  Dnipro elevation overrides: {len(dnipro_elevations)}")

                # Show elevation distribution for debugging
                if dnipro_elevations:
                    elev_counts = {}
                    for level in dnipro_elevations.values():
                        elev_counts[level] = elev_counts.get(level, 0) + 1
                    print(f"  Dnipro elevation distribution: {dict(sorted(elev_counts.items()))}")

                # Calculate lake bank elevations (one level lower than minimum bank)
                print("  Calculating natural lake bank elevations...")
                lake_elevations = self.river_mapper.get_dnipro_bank_elevations(
                    self.river_classification.lakes,
                    hex_elevations,
                    ukraine_mask
                )
                print(f"  Lake elevation overrides: {len(lake_elevations)}")
        else:
            # Fallback: no lake terrain if no classification
            print("  WARNING: No classification from step6, no lake terrain applied")
            lake_terrain_hexes = set()

        # Create terrain mapper with terrain names order from Save.hms
        terrain_mapper = TerrainMapper(bounds, self.width, self.height, terrain_names)

        # Create land mask dict for terrain mapper
        land_mask = {}
        for row in range(self.height):
            for col in range(self.width):
                pos = (col, row)
                if ukraine_mask:
                    land_mask[pos] = ukraine_mask.get(pos, False)
                else:
                    land_mask[pos] = hex_elevations.get(pos, -3) >= 0

        # Create hex_biome_map from hex_to_raion and raion_biomes
        # This ensures biome variant in G channel matches territory biome
        hex_biome_map = {}
        if hasattr(self, 'hex_to_raion') and self.hex_to_raion:
            if hasattr(self, 'raion_biomes') and self.raion_biomes:
                for pos, raion_idx in self.hex_to_raion.items():
                    if raion_idx > 0 and raion_idx <= len(self.raion_biomes):
                        # raion_idx is 1-based (0 is ocean)
                        hex_biome_map[pos] = self.raion_biomes[raion_idx - 1]
                    else:
                        # Ocean or invalid - use Arctic (0)
                        hex_biome_map[pos] = 0
                print(f"  Created hex_biome_map for {len(hex_biome_map)} hexes")
            else:
                print("  WARNING: raion_biomes not available, using default biome variant")
        else:
            print("  WARNING: hex_to_raion not available, using default biome variant")

        # Find the highest and second-highest elevation levels on land
        land_elevations = [elev for pos, elev in hex_elevations.items() if land_mask.get(pos, False)]
        unique_elevations = sorted(set(land_elevations), reverse=True)
        max_elev = unique_elevations[0] if unique_elevations else 12
        second_max = unique_elevations[1] if len(unique_elevations) > 1 else max_elev - 1
        print(f"  Max elevation level: {max_elev} (MountainSnow)")
        print(f"  Second max elevation level: {second_max} (Mountain)")
        terrain_mapper.set_elevation_range(max_elev, second_max)

        # Get terrain for all hexes using Copernicus land cover
        # Returns terrain map, elevation overrides for water tiles, and mountain hexes
        # lake_terrain_hexes contains Dnipro, reservoirs, porohy, and lakes (NOT regular rivers)
        terrain_map, elevation_overrides, mountain_hexes = terrain_mapper.create_terrain_map(
            hex_elevations, land_mask, lake_terrain_hexes, landcover_grid, hex_biome_map
        )

        # Calculate mountain chain connectivity flags (B channel)
        from terrain_mapper import calculate_mountain_chain_flags
        mountain_b_channel = calculate_mountain_chain_flags(mountain_hexes, self.width, self.height)
        print(f"  Mountain chain flags calculated: {len(mountain_b_channel)} hexes")

        # Apply lake elevation overrides (one level lower than minimum bank)
        if lake_elevations:
            for pos, level in lake_elevations.items():
                elevation_overrides[pos] = level
            print(f"  Applied {len(lake_elevations)} natural lake elevation overrides")

        # Apply Dnipro elevation overrides (one level lower than minimum bank)
        if dnipro_elevations:
            for pos, level in dnipro_elevations.items():
                elevation_overrides[pos] = level
            print(f"  Applied {len(dnipro_elevations)} Dnipro elevation overrides")

        # Create elevation texture with proper terrain encoding
        # R channel: elevation level (offset by 4 so level 0 -> R=4)
        # G channel: terrain_type * 8 + variant
        # B channel: mountain chain connectivity flags (0 for non-mountains)
        # A channel: 0
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        pixels = img.load()

        for row in range(self.height):
            for col in range(self.width):
                pos = (col, row)
                # Use elevation override for water tiles if available
                level = elevation_overrides.get(pos, hex_elevations.get(pos, -3))
                g_value = terrain_map.get(pos, 7)  # Default to CityTerrain variant 7

                # R value: level offset
                if level < 0:
                    r_value = max(1, 4 + level)
                else:
                    r_value = min(15, 4 + level)

                # B value: mountain chain connectivity (makes 3D mountains render)
                b_value = mountain_b_channel.get(pos, 0)

                pixels[col, row] = (r_value, g_value, b_value, 0)

        # Encode as base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        elevation_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        print(f"\n  Elevation+Terrain texture: {len(elevation_b64)} chars")

        # Update save content
        content = self._update_texture_bytes(
            self.current_save_content, 'ElevationTexture', elevation_b64
        )

        self.current_save_content = content

        output_path = self.output_dir / "step7_terrain.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        # Save terrain visualization
        self._save_terrain_visualization(terrain_map, ukraine_mask)

        return output_path

    def _save_terrain_visualization(self, terrain_map: dict, _ukraine_mask: dict = None):
        """Save a visualization of terrain types."""

        from terrain_mapper import TERRAIN_TYPES

        # Create array of terrain indices
        # G encoding: (biome_variant << 4) | terrain_idx
        # So terrain_idx = G & 0x0F (lower 4 bits)
        arr = np.zeros((self.height, self.width), dtype=np.uint8)
        for (col, row), g_value in terrain_map.items():
            terrain_idx = g_value & 0x0F  # Lower 4 bits = terrain index
            arr[row, col] = terrain_idx

        # Terrain colors
        terrain_colors = {
            0: '#808080',   # CityTerrain - gray (default land)
            1: '#87CEEB',   # CoastalWater - sky blue
            2: '#DAA520',   # DryGrass - goldenrod
            3: '#228B22',   # Forest - forest green
            4: '#4169E1',   # Lake - royal blue
            5: '#8B4513',   # Mountain - saddle brown
            6: '#FFFAFA',   # MountainSnow - snow
            7: '#000080',   # Ocean - navy
            8: '#9ACD32',   # Prairie - yellow green
            9: '#BC8F8F',   # RockyField - rosy brown
            10: '#556B2F',  # RockyForest - dark olive green
            11: '#D2B48C',  # Sterile - tan
            12: '#A9A9A9',  # StoneField - dark gray
            13: '#F4A460',  # Wasteland - sandy brown
            14: '#6B8E23',  # WoodLand - olive drab
        }

        # Create colormap
        colors = [terrain_colors.get(i, '#FF00FF') for i in range(15)]
        cmap = mcolors.ListedColormap(colors)

        _fig, ax = plt.subplots(figsize=(16, 9))
        im = ax.imshow(arr, cmap=cmap, vmin=0, vmax=14, aspect='auto')
        ax.set_title('Ukraine Terrain Types', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        # Create legend
        terrain_names = {v: k for k, v in TERRAIN_TYPES.items()}
        labels = [terrain_names.get(i, f'Unknown({i})') for i in range(15)]
        cbar = plt.colorbar(im, ax=ax, ticks=range(15))
        cbar.ax.set_yticklabels(labels, fontsize=8)
        cbar.set_label('Terrain Type')

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        viz_path = viz_dir / "ukraine_terrain.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved terrain visualization: {viz_path}")

    def step8_features(self) -> Path:
        """Step 8: Add natural features and resources based on real geography."""
        print("\n" + "=" * 60)
        print("STEP 8: Natural Features & Resources")
        print("=" * 60)
        print("  Change: POITexture.Bytes with terrain modifiers and resources")

        from feature_mapper import FeatureMapper

        bounds = {
            'min_lon': self.min_lon,
            'max_lon': self.max_lon,
            'min_lat': self.min_lat,
            'max_lat': self.max_lat
        }

        # Create feature mapper
        mapper = FeatureMapper(bounds, self.width, self.height)

        # Load features from terrain modifiers document
        md_path = Path(__file__).parent / "data" / "humankind_ukraine_terrain_modifiers.md"
        mapper.load_from_markdown(md_path)

        # Build ukraine mask from hex_to_raion (land = raion > 0)
        ukraine_mask = None
        if hasattr(self, 'hex_to_raion') and self.hex_to_raion:
            ukraine_mask = {k: v > 0 for k, v in self.hex_to_raion.items()}
            print(f"  Using Ukraine land mask ({sum(ukraine_mask.values())} land hexes)")

        # Create POI texture
        poi_texture = mapper.create_poi_texture(ukraine_mask)

        # Print statistics
        stats = mapper.get_feature_stats()
        print("\n  Feature distribution:")
        for name, count in sorted(stats.items()):
            print(f"    {name}: {count}")

        # Convert to PIL Image and encode
        from PIL import Image
        img = Image.fromarray(poi_texture, mode='RGBA')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        poi_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        print(f"\n  POI texture: {len(poi_b64)} chars")

        # Update save content
        content = self._update_texture_bytes(
            self.current_save_content, 'POITexture', poi_b64
        )

        self.current_save_content = content

        output_path = self.output_dir / "step8_features.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        # Save feature visualization
        self._save_feature_visualization(mapper, ukraine_mask)

        return output_path

    def step9_natural_wonders(self) -> Path:
        """Step 9: Natural wonders (DISABLED - pass-through)."""
        print("\n" + "=" * 60)
        print("STEP 9: Natural Wonders (SKIPPED)")
        print("=" * 60)
        print("  No changes - passing through from step 8")

        # Just save current content without modification
        output_path = self.output_dir / "step9_natural_wonders.hmap"
        self._save_hmap(self.current_save_content, self.descriptor_content, output_path)

        return output_path

    def step10_spawn_points(self) -> Path:
        """Step 10: Add player spawn points at major Ukrainian cities."""
        print("\n" + "=" * 60)
        print("STEP 10: Spawn Points (Starting Locations)")
        print("=" * 60)
        print("  Change: SpawnPoints in EntitiesProvider")

        # Ukrainian cities with coordinates (lat, lon)
        # Max 10 spawn points for Humankind
        SPAWN_CITIES = [
            # Kyiv - 2 spawn points (west and east bank)
            {"name": "Kyiv (West Bank)", "lat": 50.45, "lon": 30.40},
            {"name": "Kyiv (East Bank)", "lat": 50.45, "lon": 30.65},
            # Dnipro - 2 spawn points (opposite banks)
            {"name": "Dnipro (West Bank)", "lat": 48.46, "lon": 34.95},
            {"name": "Dnipro (East Bank)", "lat": 48.46, "lon": 35.15},
            # Other major cities - 1 each
            {"name": "Kharkiv", "lat": 49.99, "lon": 36.23},
            {"name": "Odesa", "lat": 46.48, "lon": 30.72},
            {"name": "Lviv", "lat": 49.84, "lon": 24.03},
            {"name": "Zaporizhzhia", "lat": 47.84, "lon": 35.14},
            # Shepetivka (user request)
            {"name": "Shepetivka", "lat": 50.18, "lon": 27.06},
            # One more major city
            {"name": "Vinnytsia", "lat": 49.23, "lon": 28.48},
        ]

        # Use step9 content as base
        if not hasattr(self, 'current_save_content') or not self.current_save_content:
            raise RuntimeError("Step 10 requires step 9 content")

        content = self.current_save_content

        # Get bounds from config
        import yaml
        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        active = config['active_config']
        bounds = config['bounds'][active]
        spawn_points = []

        print("\n  City spawn points:")
        for city in SPAWN_CITIES:
            # Convert lat/lon to hex coordinates
            col = int((city['lon'] - bounds['min_lon']) / (bounds['max_lon'] - bounds['min_lon']) * self.width)
            row = int((bounds['max_lat'] - city['lat']) / (bounds['max_lat'] - bounds['min_lat']) * self.height)

            # Clamp to grid bounds
            col = max(0, min(self.width - 1, col))
            row = max(0, min(self.height - 1, row))

            # Row inversion for file format: file_row = height - game_row - 1
            file_row = self.height - row - 1

            spawn_points.append({
                "name": city['name'],
                "col": col,
                "row": row,
                "file_row": file_row
            })
            print(f"    {city['name']}: col={col}, row={row} (file_row={file_row})")

        # Build SpawnPoints XML with proper indentation
        spawn_xml_items = []
        for i, sp in enumerate(spawn_points):
            # Flags = 1023 means valid for all player counts (1-10)
            spawn_xml_items.append(f"""            <Item>
                <SpawnPoints>
                    <Column>{sp['col']}</Column>
                    <Row>{sp['file_row']}</Row>
                </SpawnPoints>
                <Flags>1023</Flags>
            </Item>""")

        spawn_xml = f"""<SpawnPoints Length="{len(spawn_points)}">
{chr(10).join(spawn_xml_items)}
            </SpawnPoints>"""

        # Find and replace existing SpawnPoints section
        import re

        # Try to match <SpawnPoints Null="true" /> first (empty spawns)
        null_pattern = r'<SpawnPoints\s+Null="true"\s*/>'
        if re.search(null_pattern, content):
            content = re.sub(null_pattern, spawn_xml, content)
            print(f"\n  Replaced null SpawnPoints: {len(spawn_points)} spawn locations")
        else:
            # Try to match existing <SpawnPoints Length=...>...</SpawnPoints>
            spawn_pattern = r'<SpawnPoints Length="[^"]*">.*?</SpawnPoints>'
            if re.search(spawn_pattern, content, re.DOTALL):
                content = re.sub(spawn_pattern, spawn_xml, content, flags=re.DOTALL)
                print(f"\n  Updated SpawnPoints: {len(spawn_points)} spawn locations")
            else:
                print("  WARNING: Could not find SpawnPoints section to replace")

        self.current_save_content = content

        output_path = self.output_dir / "step10_spawn_points.hmap"
        self._save_hmap(content, self.descriptor_content, output_path)

        return output_path

    def _save_wonder_visualization(self, mapper, ukraine_mask: dict = None):
        """Save a visualization of natural wonders."""

        from natural_wonder_mapper import UKRAINE_WONDERS

        # Create base map (land/ocean)
        arr = np.zeros((self.height, self.width), dtype=np.uint8)
        if ukraine_mask:
            for (col, row), is_land in ukraine_mask.items():
                if is_land:
                    arr[row, col] = 1

        # Get wonder placements
        placements = mapper.get_wonder_placements(ukraine_mask)
        for (col, row), wonder_idx in placements.items():
            arr[row, col] = 2 + (wonder_idx % 7)  # Different values for different wonders

        _fig, ax = plt.subplots(figsize=(16, 9))
        # Create colormap with distinct colors for each wonder
        cmap = plt.cm.colors.ListedColormap([
            '#4169E1',  # 0: Ocean
            '#90EE90',  # 1: Land
            '#FFD700',  # 2: Wonder 1 (gold)
            '#FF6347',  # 3: Wonder 2 (tomato)
            '#00CED1',  # 4: Wonder 3 (dark turquoise)
            '#9932CC',  # 5: Wonder 4 (dark orchid)
            '#32CD32',  # 6: Wonder 5 (lime green)
            '#FF69B4',  # 7: Wonder 6 (hot pink)
            '#FFA500',  # 8: Wonder 7 (orange)
        ])
        ax.imshow(arr, cmap=cmap, aspect='auto')
        ax.set_title('Ukraine Natural Wonders', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        # Add legend with wonder names
        legend_elements = [
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#4169E1', markersize=10, label='Ocean'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#90EE90', markersize=10, label='Land'),
        ]
        wonder_colors = ['#FFD700', '#FF6347', '#00CED1', '#9932CC', '#32CD32', '#FF69B4', '#FFA500']
        for i, wonder in enumerate(UKRAINE_WONDERS):
            color = wonder_colors[i % len(wonder_colors)]
            legend_elements.append(
                Line2D([0], [0], marker='s', color='w', markerfacecolor=color, markersize=10,
                       label=f"{wonder.ukrainian_name}")
            )
        ax.legend(handles=legend_elements, loc='upper right', fontsize=8)

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        viz_path = viz_dir / "ukraine_natural_wonders.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved wonder visualization: {viz_path}")

    def _save_feature_visualization(self, mapper, ukraine_mask: dict = None):
        """Save a visualization of features and resources."""

        from feature_mapper import NATURAL_MODIFIERS, RESOURCE_DEPOSITS

        # Create base map (land/ocean)
        arr = np.zeros((self.height, self.width), dtype=np.uint8)
        if ukraine_mask:
            for (col, row), is_land in ukraine_mask.items():
                if is_land:
                    arr[row, col] = 1

        _fig, ax = plt.subplots(figsize=(18, 10))

        # Draw land/ocean background
        land_cmap = mcolors.ListedColormap(['#4169E1', '#90EE90'])
        ax.imshow(arr, cmap=land_cmap, aspect='auto', alpha=0.5)

        # Define colors for feature types
        feature_colors = {
            # Natural modifiers - greens/browns
            'BlackSoil': '#2F4F4F',
            'Marsh': '#6B8E23',
            'Cave': '#8B4513',
            'HugeTrees': '#228B22',
            'DimensionStones': '#708090',
            'Clay': '#D2691E',
            'DomesticableAnimals': '#DAA520',
            'BerryBushes': '#DC143C',
            'River': '#4169E1',
            'RiverSpring': '#00CED1',
            # Strategic resources - reds/oranges
            'Horse': '#FF6347',
            'Copper': '#CD7F32',
            'Iron': '#B22222',
            'Coal': '#2F2F2F',
            'Oil': '#1C1C1C',
            'Uranium': '#7FFF00',
            'Saltpetre': '#F5DEB3',
            # Luxury resources - golds/purples
            'Salt': '#FFFFFF',
            'Mercury': '#C0C0C0',
            'Marble': '#FAEBD7',
            'Gold': '#FFD700',
            'Lead': '#778899',
            'Silver': '#C0C0C0',
            'Gemstone': '#E6E6FA',
            'Porcelain': '#F0F8FF',
        }

        # Plot features
        for col, row, poi_index in mapper.features:
            # Skip if outside Ukraine
            if ukraine_mask and not ukraine_mask.get((col, row), False):
                continue

            # Find feature name
            feature_name = None
            for name, idx in {**NATURAL_MODIFIERS, **RESOURCE_DEPOSITS}.items():
                if idx == poi_index:
                    feature_name = name
                    break

            if feature_name:
                color = feature_colors.get(feature_name, '#FF00FF')
                # Use different markers for natural vs resources
                if poi_index <= 24:
                    marker = 'o'  # Circle for natural
                    size = 60
                else:
                    marker = 's'  # Square for resources
                    size = 80
                ax.scatter(col, row, c=color, s=size, marker=marker, edgecolors='black', linewidths=0.5)

        ax.set_xlim(-1, self.width + 1)
        ax.set_ylim(self.height + 1, -1)
        ax.set_title('Ukraine Features & Resources', fontsize=14)
        ax.set_xlabel('Column')
        ax.set_ylabel('Row')

        # Create legend
        legend_elements = []
        for name in sorted(feature_colors.keys()):
            if any(f[2] == {**NATURAL_MODIFIERS, **RESOURCE_DEPOSITS}.get(name) for f in mapper.features):
                idx = {**NATURAL_MODIFIERS, **RESOURCE_DEPOSITS}.get(name, 0)
                marker = 'o' if idx <= 24 else 's'
                legend_elements.append(
                    Line2D([0], [0], marker=marker, color='w', markerfacecolor=feature_colors[name],
                           markersize=8, label=name, markeredgecolor='black', markeredgewidth=0.5)
                )

        if legend_elements:
            ax.legend(handles=legend_elements, loc='upper left', fontsize=8, ncol=2)

        viz_dir = Path(__file__).parent / "output" / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        viz_path = viz_dir / "ukraine_features.png"
        plt.savefig(viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved feature visualization: {viz_path}")

    def build_all(self) -> list[Path]:
        """Build all incremental steps."""
        paths = []
        paths.append(self.step1_baseline())
        paths.append(self.step2_land_ocean())
        paths.append(self.step3_territories())
        paths.append(self.step4_biomes())
        paths.append(self.step5_elevation())
        paths.append(self.step6_rivers())
        paths.append(self.step7_terrain())
        paths.append(self.step8_features())
        paths.append(self.step9_natural_wonders())
        paths.append(self.step10_spawn_points())
        return paths


def main():
    # Increment version
    version = get_next_version()
    version_str = get_version_string(version)

    print("=" * 60)
    print(f"UKRAINE MAP BUILDER - {version_str}")
    print(f"Build time: {version['timestamp']}")
    print("=" * 60)

    template_path = Path(__file__).parent / "output" / "maps" / "Huge_Ukraine_template.hmap"

    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        print("Please copy Huge_Ukraine_template.hmap from game Maps folder")
        return

    builder = IncrementalMapBuilder(template_path)
    paths = builder.build_all()

    # Game folder for final map
    game_maps = Path("/home/shivers/.steam/debian-installation/steamapps/compatdata/1124300/pfx/drive_c/users/steamuser/Documents/Humankind/Maps")

    # Remove previous incremental maps folder if it exists
    old_incremental = game_maps / "incremental_ukraine"
    if old_incremental.exists():
        print(f"\nRemoving old incremental folder: {old_incremental}")
        shutil.rmtree(old_incremental)

    # Copy only the final map (step10) to game folder with a clean name
    final_map = paths[-1]  # step10_spawn_points.hmap
    dest_name = f"Ukraine_{version_str}.hmap"
    dest_path = game_maps / dest_name

    print("\n" + "=" * 60)
    print(f"COPYING FINAL MAP TO GAME FOLDER ({version_str})")
    print("=" * 60)
    shutil.copy(final_map, dest_path)
    print(f"  {final_map.name} -> {dest_name}")

    print("\n" + "=" * 60)
    print(f"BUILD COMPLETE - {version_str}")
    print("=" * 60)
    print(f"\nFinal map: {dest_path}")
    print(f"\nIntermediate steps available in: {builder.output_dir}")
    print(f"Version: {version_str}")


if __name__ == "__main__":
    main()
