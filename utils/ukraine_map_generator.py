#!/usr/bin/env python3
"""
Ukraine Map Generator for Humankind

Generates a complete .hms map file with Ukrainian raions as territories.
"""

import base64
import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
from PIL import Image
import geopandas as gpd

from .config_loader import get_config
from .geo_hex_mapper import GeoHexMapper
from .territory_assigner import TerritoryAssigner
from .biome_mapper import BiomeMapper


@dataclass
class TerritoryData:
    """Data for a single territory."""
    index: int
    continent_index: int
    biome: int
    is_ocean: bool
    hex_count: int = 0
    name: str = ""


class UkraineMapGenerator:
    """
    Generates a Humankind map file for Ukraine with raion territories.
    """

    # Standard Humankind biome names (order matters!)
    BIOME_NAMES = [
        "Arctic", "Badlands", "Desert", "Grassland", "Mediterranean",
        "Savanna", "Taiga", "Temperate", "Tropical", "Tundra"
    ]

    # Standard terrain type names
    TERRAIN_TYPE_NAMES = [
        "CityTerrain", "CoastalWater", "DryGrass", "Forest", "Lake",
        "Mountain", "MountainSnow", "Ocean", "Prairie", "RockyField",
        "RockyForest", "Sterile", "StoneField", "Wasteland", "WoodLand"
    ]

    # POI names (basic set)
    POI_NAMES = ["None"] + [f"POI_NaturalModifier{i:02d}" for i in range(1, 25)] + \
                [f"POI_ResourceDeposit{i:02d}" for i in range(1, 32)]

    # Natural wonder names
    NATURAL_WONDER_NAMES = [
        "DanakilDesert", "GreatBarrierReef", "GreatBlueHole", "HalongBay",
        "KawahIjen", "LakeBaikal", "LakeHillier", "MountEverest",
        "MountMulu", "MountRoraima", "MountVesuvius", "PeritoMorenoGlacier",
        "Vinicunca", "Yellowstone"
    ]

    # Landmark definition names
    LANDMARK_DEF_NAMES = [
        "Landmark_Desert", "Landmark_Forest", "Landmark_Lake",
        "Landmark_Mountain", "Landmark_River"
    ]

    def __init__(
        self,
        width: int = 150,
        height: int = 88,
        hex_to_raion: Dict[Tuple[int, int], int] = None,
        raion_biomes: Dict[int, int] = None,
        raion_gdf: gpd.GeoDataFrame = None,
        name_field: str = "adm2_name"
    ):
        """
        Initialize the map generator.

        Args:
            width: Map width in hexes
            height: Map height in hexes
            hex_to_raion: Mapping of (col, row) -> raion_index
            raion_biomes: Mapping of raion_index -> biome_index
            raion_gdf: GeoDataFrame with raion data
            name_field: Column name for raion names
        """
        self.width = width
        self.height = height
        self.hex_to_raion = hex_to_raion or {}
        self.raion_biomes = raion_biomes or {}
        self.raion_gdf = raion_gdf
        self.name_field = name_field

        self.territories: List[TerritoryData] = []
        self.zones_texture: np.ndarray = None
        self.elevation_texture: np.ndarray = None

    def build_territory_database(self) -> List[TerritoryData]:
        """
        Build territory database from hex assignments.

        Returns:
            List of TerritoryData objects
        """
        print("\nBuilding territory database...")

        # Count hexes per raion
        raion_hex_counts = {}
        for (col, row), raion_idx in self.hex_to_raion.items():
            raion_hex_counts[raion_idx] = raion_hex_counts.get(raion_idx, 0) + 1

        # Territory 0 is always ocean
        territories = [TerritoryData(
            index=0,
            continent_index=0,
            biome=0,  # Arctic for ocean (matches reference)
            is_ocean=True,
            hex_count=0,
            name="Ocean"
        )]

        # Build raion index to territory index mapping
        # Only include raions that have hexes
        raion_to_territory = {}
        territory_idx = 1

        for raion_idx in sorted(raion_hex_counts.keys()):
            hex_count = raion_hex_counts[raion_idx]
            biome = self.raion_biomes.get(raion_idx, BiomeMapper.BIOME_GRASSLAND)

            # Get raion name if available
            name = ""
            if self.raion_gdf is not None and raion_idx in self.raion_gdf.index:
                name = self.raion_gdf.loc[raion_idx, self.name_field]

            territories.append(TerritoryData(
                index=territory_idx,
                continent_index=1,  # All Ukraine on continent 1
                biome=biome,
                is_ocean=False,
                hex_count=hex_count,
                name=name
            ))

            raion_to_territory[raion_idx] = territory_idx
            territory_idx += 1

        # Count ocean hexes
        total_hexes = self.width * self.height
        ukraine_hexes = sum(raion_hex_counts.values())
        territories[0].hex_count = total_hexes - ukraine_hexes

        self.territories = territories
        self.raion_to_territory = raion_to_territory

        print(f"  Created {len(territories)} territories:")
        print(f"    - 1 ocean territory ({territories[0].hex_count} hexes)")
        print(f"    - {len(territories) - 1} land territories ({ukraine_hexes} hexes)")

        return territories

    def build_zones_texture(self) -> np.ndarray:
        """
        Build zones texture mapping each hex to territory index.

        Returns:
            2D numpy array (height x width) of territory indices
        """
        print("\nBuilding zones texture...")

        # Initialize with ocean (territory 0)
        zones = np.zeros((self.height, self.width), dtype=np.uint8)

        # Assign territory indices
        for (col, row), raion_idx in self.hex_to_raion.items():
            if raion_idx in self.raion_to_territory:
                territory_idx = self.raion_to_territory[raion_idx]
                zones[row, col] = territory_idx

        self.zones_texture = zones
        unique_territories = len(np.unique(zones))
        print(f"  Zones texture: {self.width}x{self.height}")
        print(f"  Unique territory indices: {unique_territories}")

        return zones

    def build_elevation_texture(self) -> np.ndarray:
        """
        Build elevation texture (flat for now, can add mountains later).

        Returns:
            2D numpy array (height x width) with elevation values
        """
        print("\nBuilding elevation texture...")

        # Default flat elevation (128 = neutral)
        elevation = np.full((self.height, self.width), 128, dtype=np.uint8)

        # TODO: Add Carpathian mountains and Crimean mountains
        # For now, keep flat

        self.elevation_texture = elevation
        print(f"  Elevation texture: {self.width}x{self.height} (flat)")

        return elevation

    def encode_texture_to_base64(self, texture: np.ndarray) -> str:
        """
        Encode a texture as base64 PNG.

        Args:
            texture: 2D numpy array

        Returns:
            Base64-encoded PNG string
        """
        # Convert to RGBA (Humankind uses RGBA format)
        if texture.ndim == 2:
            # Single channel - store in R, set G/B/A to 0
            # Note: Humankind expects Alpha=0, not 255!
            rgba = np.zeros((texture.shape[0], texture.shape[1], 4), dtype=np.uint8)
            rgba[:, :, 0] = texture  # R channel holds the data
            # G, B, A all stay 0
        else:
            rgba = texture

        img = Image.fromarray(rgba, mode='RGBA')

        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        png_bytes = buffer.getvalue()

        return base64.b64encode(png_bytes).decode('ascii')

    def create_empty_texture_base64(self) -> str:
        """Create an empty (black) texture for unused texture slots."""
        empty = np.zeros((self.height, self.width), dtype=np.uint8)
        return self.encode_texture_to_base64(empty)

    def build_visibility_texture(self) -> np.ndarray:
        """
        Build visibility texture - 255 for visible hexes, 0 for fog.

        Returns:
            2D numpy array (height x width) with visibility values
        """
        print("\nBuilding visibility texture...")

        # Set all hexes to fully visible (255)
        visibility = np.full((self.height, self.width), 255, dtype=np.uint8)

        self.visibility_texture = visibility
        print(f"  Visibility texture: {self.width}x{self.height} (all visible)")

        return visibility

    def generate_xml(self, map_name: str = "Ukraine Raions") -> str:
        """
        Generate complete .hms XML content.

        Args:
            map_name: Name of the map

        Returns:
            XML string
        """
        print("\nGenerating XML...")

        # Build components if not already built
        if not self.territories:
            self.build_territory_database()
        if self.zones_texture is None:
            self.build_zones_texture()
        if self.elevation_texture is None:
            self.build_elevation_texture()
        if not hasattr(self, 'visibility_texture') or self.visibility_texture is None:
            self.build_visibility_texture()

        # Encode textures
        zones_base64 = self.encode_texture_to_base64(self.zones_texture)
        elevation_base64 = self.encode_texture_to_base64(self.elevation_texture)
        visibility_base64 = self.encode_texture_to_base64(self.visibility_texture)
        empty_base64 = self.create_empty_texture_base64()

        # Build XML structure
        root = ET.Element("Document")
        terrain_save = ET.SubElement(root, "TerrainSave")

        # Basic properties
        ET.SubElement(terrain_save, "FormatRevision").text = "10"
        ET.SubElement(terrain_save, "Width").text = str(self.width)
        ET.SubElement(terrain_save, "Height").text = str(self.height)
        ET.SubElement(terrain_save, "UseMapCycling").text = "false"
        ET.SubElement(terrain_save, "UseProceduralMountainChains").text = "false"

        # Biome names
        biome_names_elem = ET.SubElement(terrain_save, "BiomeNames", Length=str(len(self.BIOME_NAMES)))
        for name in self.BIOME_NAMES:
            ET.SubElement(biome_names_elem, "String").text = name

        # Terrain type names
        terrain_names_elem = ET.SubElement(terrain_save, "TerrainTypeNames", Length=str(len(self.TERRAIN_TYPE_NAMES)))
        for name in self.TERRAIN_TYPE_NAMES:
            ET.SubElement(terrain_names_elem, "String").text = name

        # POI names
        poi_names_elem = ET.SubElement(terrain_save, "POINames", Length=str(len(self.POI_NAMES)))
        for name in self.POI_NAMES:
            ET.SubElement(poi_names_elem, "String").text = name

        # Natural wonder names
        nw_names_elem = ET.SubElement(terrain_save, "NaturalWonderNames", Length=str(len(self.NATURAL_WONDER_NAMES)))
        for name in self.NATURAL_WONDER_NAMES:
            ET.SubElement(nw_names_elem, "String").text = name

        # Landmark definition names
        ld_names_elem = ET.SubElement(terrain_save, "LandmarksDefinitionNames", Length=str(len(self.LANDMARK_DEF_NAMES)))
        for name in self.LANDMARK_DEF_NAMES:
            ET.SubElement(ld_names_elem, "String").text = name

        # Elevation texture
        ET.SubElement(terrain_save, "ElevationTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "ElevationTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "ElevationTexture.Format").text = "4"  # RGBA
        ET.SubElement(terrain_save, "ElevationTexture.Bytes", Length=str(len(elevation_base64))).text = elevation_base64

        # Zones texture
        ET.SubElement(terrain_save, "ZonesTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "ZonesTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "ZonesTexture.Format").text = "4"  # RGBA
        ET.SubElement(terrain_save, "ZonesTexture.Bytes", Length=str(len(zones_base64))).text = zones_base64

        # POI texture (empty)
        ET.SubElement(terrain_save, "POITexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "POITexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "POITexture.Format").text = "4"
        ET.SubElement(terrain_save, "POITexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # Visibility texture - 255 for visible hexes (no fog)
        ET.SubElement(terrain_save, "VisibilityTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "VisibilityTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "VisibilityTexture.Format").text = "4"
        ET.SubElement(terrain_save, "VisibilityTexture.Bytes", Length=str(len(visibility_base64))).text = visibility_base64

        # Road texture (empty)
        ET.SubElement(terrain_save, "RoadTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "RoadTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "RoadTexture.Format").text = "4"
        ET.SubElement(terrain_save, "RoadTexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # River texture (empty)
        ET.SubElement(terrain_save, "RiverTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "RiverTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "RiverTexture.Format").text = "4"
        ET.SubElement(terrain_save, "RiverTexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # Natural wonder texture (empty)
        ET.SubElement(terrain_save, "NaturalWonderTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "NaturalWonderTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "NaturalWonderTexture.Format").text = "4"
        ET.SubElement(terrain_save, "NaturalWonderTexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # Matching seed texture (empty)
        ET.SubElement(terrain_save, "MatchingSeedTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "MatchingSeedTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "MatchingSeedTexture.Format").text = "4"
        ET.SubElement(terrain_save, "MatchingSeedTexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # Landmarks texture (empty)
        ET.SubElement(terrain_save, "LandmarksTexture.Width").text = str(self.width)
        ET.SubElement(terrain_save, "LandmarksTexture.Height").text = str(self.height)
        ET.SubElement(terrain_save, "LandmarksTexture.Format").text = "4"
        ET.SubElement(terrain_save, "LandmarksTexture.Bytes", Length=str(len(empty_base64))).text = empty_base64

        # Landmark database (empty)
        landmark_db = ET.SubElement(terrain_save, "LandmarkDatabase")
        ET.SubElement(landmark_db, "Landmarks", Length="0")

        # Territory database
        territory_db = ET.SubElement(terrain_save, "TerritoryDatabase")
        territories_elem = ET.SubElement(territory_db, "Territories", Length=str(len(self.territories)))

        for territory in self.territories:
            item = ET.SubElement(territories_elem, "Item")
            ET.SubElement(item, "ContinentIndex").text = str(territory.continent_index)
            ET.SubElement(item, "Biome").text = str(territory.biome)
            ET.SubElement(item, "IsOcean").text = str(territory.is_ocean).lower()

        # Entities provider (spawn points)
        entities_provider = ET.SubElement(terrain_save, "EntitiesProvider")
        ET.SubElement(entities_provider, "SpawnPoints", Null="true")

        # Metadata
        ET.SubElement(terrain_save, "Author", Null="true")
        ET.SubElement(terrain_save, "Description", Null="true")
        ET.SubElement(terrain_save, "CreationDate").text = "0"
        ET.SubElement(terrain_save, "LastEditionDate").text = "0"
        ET.SubElement(terrain_save, "FailureFlags").text = "0"
        ET.SubElement(terrain_save, "MapName", Null="true")
        ET.SubElement(terrain_save, "DownloadContentNeeded").text = "0"

        # Generate XML string with proper formatting
        # Read revision tags from external file (matches game format)
        revision_tags_file = Path(__file__).parent / "revision_tags.txt"
        if revision_tags_file.exists():
            xml_declaration = revision_tags_file.read_text(encoding='utf-8')
            if not xml_declaration.endswith('\n'):
                xml_declaration += '\n'
        else:
            # Fallback to basic version 5 header
            xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
            xml_declaration += '<?amplitude-serialization-serializer version="5"?>\n'
            # Add minimal terrain revision tags
            revision_tags = [
                ('Amplitude.Mercury.Terrain.TerrainSave, Amplitude.Mercury.Terrain', '4,0,0,0,0,0'),
                ('Amplitude.Mercury.Terrain.TerrainSaveDescriptor, Amplitude.Mercury.Terrain', '7,0,0,0,0,0'),
                ('Amplitude.Mercury.Terrain.Territory, Amplitude.Mercury.Terrain', '1,0,0,0,0,0'),
                ('Amplitude.Mercury.Terrain.TerritoryDatabase, Amplitude.Mercury.Terrain', '1,0,0,0,0,0'),
                ('Amplitude.Mercury.Terrain.WorldMapEntitiesProvider, Amplitude.Mercury.Terrain', '1,0,0,0,0,0'),
                ('Amplitude.Mercury.Terrain.SpawnPoint, Amplitude.Mercury.Terrain', '1,0,0,0,0,0'),
            ]
            for type_name, number in revision_tags:
                xml_declaration += f'<?amplitude-serialization-serializer-revision type="{type_name}" number="{number}"?>\n'

        # Convert tree to string with indentation
        self._indent_xml(root)
        xml_content = ET.tostring(root, encoding='unicode')

        full_xml = xml_declaration + xml_content

        print(f"  Generated XML: {len(full_xml)} characters")

        return full_xml

    def _indent_xml(self, elem, level=0):
        """Add indentation to XML element."""
        indent = "\n" + "    " * level
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "    "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def save_hms(self, output_path: Path, map_name: str = "Ukraine Raions") -> Path:
        """
        Save the map as .hms file.

        Args:
            output_path: Path to save the file
            map_name: Name of the map

        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        xml_content = self.generate_xml(map_name)

        # Write with BOM for UTF-8
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write(xml_content)

        print(f"\n  Saved: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")

        return output_path

    def generate_descriptor_xml(self, empires_count: int = 8) -> str:
        """
        Generate Descriptor.hmd XML content.

        Args:
            empires_count: Number of empires supported (based on spawn points)

        Returns:
            XML string for descriptor
        """
        # XML declaration and revision tags (same as Save.hms)
        # Read revision tags from external file (matches game format)
        revision_tags_file = Path(__file__).parent / "revision_tags.txt"
        if revision_tags_file.exists():
            xml_declaration = revision_tags_file.read_text(encoding='utf-8')
            if not xml_declaration.endswith('\n'):
                xml_declaration += '\n'
        else:
            # Fallback to basic version 5 header
            xml_declaration = '<?xml version="1.0" encoding="utf-8"?>\n'
            xml_declaration += '<?amplitude-serialization-serializer version="5"?>\n'
            xml_declaration += '<?amplitude-serialization-serializer-revision type="Amplitude.Mercury.Terrain.TerrainSaveDescriptor, Amplitude.Mercury.Terrain" number="7,0,0,0,0,0"?>\n'

        # Build XML structure
        root = ET.Element("Document")
        descriptor = ET.SubElement(root, "TerrainSaveDescriptor")

        ET.SubElement(descriptor, "Name", Null="true")
        ET.SubElement(descriptor, "Description", Null="true")
        ET.SubElement(descriptor, "Author", Null="true")
        ET.SubElement(descriptor, "UserVersion").text = "0"
        ET.SubElement(descriptor, "CreationDate").text = "0"
        ET.SubElement(descriptor, "LastEditionDate").text = "0"
        ET.SubElement(descriptor, "EmpiresCount").text = str(empires_count)
        ET.SubElement(descriptor, "Width").text = str(self.width)
        ET.SubElement(descriptor, "Height").text = str(self.height)
        ET.SubElement(descriptor, "FailureFlags").text = "0"
        ET.SubElement(descriptor, "DownloadContentNeeded").text = "0"

        # Convert tree to string with indentation
        self._indent_xml(root)
        xml_content = ET.tostring(root, encoding='unicode')

        return xml_declaration + xml_content

    def save_hmap(self, output_path: Path, map_name: str = "Ukraine Raions", empires_count: int = 8) -> Path:
        """
        Save the map as .hmap file (ZIP containing Save.hms and Descriptor.hmd).

        Args:
            output_path: Path to save the .hmap file
            map_name: Name of the map
            empires_count: Number of empires supported

        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate XML content for both files
        hms_content = self.generate_xml(map_name)
        hmd_content = self.generate_descriptor_xml(empires_count)

        # Create ZIP file
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add Save.hms with BOM
            hms_bytes = ('\ufeff' + hms_content).encode('utf-8')
            zf.writestr('Save.hms', hms_bytes)

            # Add Descriptor.hmd with BOM
            hmd_bytes = ('\ufeff' + hmd_content).encode('utf-8')
            zf.writestr('Descriptor.hmd', hmd_bytes)

        print(f"\n  Saved: {output_path}")
        print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")

        return output_path

    def print_summary(self):
        """Print summary of generated map."""
        print("\n" + "=" * 70)
        print("MAP GENERATION SUMMARY")
        print("=" * 70)

        print(f"\nMap Dimensions: {self.width}x{self.height} ({self.width * self.height} hexes)")

        if self.territories:
            land_territories = [t for t in self.territories if not t.is_ocean]
            ocean_territories = [t for t in self.territories if t.is_ocean]

            print(f"\nTerritories: {len(self.territories)} total")
            print(f"  Land territories: {len(land_territories)}")
            print(f"  Ocean territories: {len(ocean_territories)}")

            land_hexes = sum(t.hex_count for t in land_territories)
            ocean_hexes = sum(t.hex_count for t in ocean_territories)

            print(f"\nHex Distribution:")
            print(f"  Land hexes: {land_hexes} ({100 * land_hexes / (self.width * self.height):.1f}%)")
            print(f"  Ocean hexes: {ocean_hexes} ({100 * ocean_hexes / (self.width * self.height):.1f}%)")

            if land_territories:
                hex_counts = [t.hex_count for t in land_territories]
                print(f"\nHexes per Territory:")
                print(f"  Min: {min(hex_counts)}")
                print(f"  Max: {max(hex_counts)}")
                print(f"  Avg: {sum(hex_counts) / len(hex_counts):.1f}")

        print("=" * 70)


def generate_ukraine_map(output_dir: Path = None) -> Path:
    """
    Generate complete Ukraine raions map.

    Args:
        output_dir: Directory to save output files

    Returns:
        Path to generated .hms file
    """
    print("=" * 70)
    print("UKRAINE MAP GENERATOR")
    print("=" * 70)

    # Load configuration
    print("\n[1/6] Loading configuration...")
    config = get_config()

    # Load raion data
    print("\n[2/6] Loading raion data...")
    data_dir = Path(__file__).parent / "data"
    raion_path = data_dir / "ukraine_raions.geojson"

    if not raion_path.exists():
        raise FileNotFoundError(f"Raion data not found at {raion_path}")

    raion_gdf = gpd.read_file(raion_path)
    print(f"  Loaded {len(raion_gdf)} raions")

    # Find field names
    oblast_field = None
    for field in ['oblast', 'ADM1_EN', 'ADM1_UA', 'NAME_1', 'admin1Name', 'adm1_name']:
        if field in raion_gdf.columns:
            oblast_field = field
            break

    name_field = None
    for field in ['name', 'NAME', 'ADM2_EN', 'ADM2_UA', 'NAME_2', 'admin2Name', 'adm2_name']:
        if field in raion_gdf.columns:
            name_field = field
            break

    # Create hex mapper
    print("\n[3/6] Creating hex grid mapper...")
    mapper = GeoHexMapper(
        width=config.grid_width,
        height=config.grid_height,
        **config.map_bounds
    )

    # Assign territories
    print("\n[4/6] Assigning hexes to raions...")
    assigner = TerritoryAssigner(mapper, raion_gdf)
    hex_to_raion = assigner.assign_all_hexes()

    # Assign biomes
    print("\n[5/6] Assigning biomes to raions...")
    biome_mapper = BiomeMapper(raion_gdf, oblast_field)
    raion_biomes = biome_mapper.assign_biomes()

    # Generate map
    print("\n[6/6] Generating map file...")
    generator = UkraineMapGenerator(
        width=config.grid_width,
        height=config.grid_height,
        hex_to_raion=hex_to_raion,
        raion_biomes=raion_biomes,
        raion_gdf=raion_gdf,
        name_field=name_field
    )

    # Build map components
    generator.build_territory_database()
    generator.build_zones_texture()
    generator.build_elevation_texture()

    # Save map
    if output_dir is None:
        output_dir = Path(__file__).parent / "output" / "maps"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save both .hms and .hmap formats
    hms_path = generator.save_hms(output_dir / "ukraine_raions.hms")
    hmap_path = generator.save_hmap(output_dir / "ukraine_raions.hmap")

    # Print summary
    generator.print_summary()

    print("\n" + "=" * 70)
    print("MAP GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nOutputs:")
    print(f"  - {hms_path} (raw XML)")
    print(f"  - {hmap_path} (game-ready package)")
    print(f"\nTo install in Humankind:")
    print(f"  1. Copy {hmap_path.name} to:")
    print(f"     %USERPROFILE%\\Documents\\Humankind\\Maps\\")
    print(f"  2. Launch Humankind and select the map in game setup")

    return hmap_path


if __name__ == "__main__":
    generate_ukraine_map()
