"""
Parser for Humankind .hms map files.

Extracts terrain data, territories, and zone textures from map save files.
"""

import base64
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import zipfile

import numpy as np
from PIL import Image


@dataclass
class Territory:
    """A single territory in the map."""
    index: int
    continent_index: int
    biome: int
    is_ocean: bool


@dataclass
class SpawnPoint:
    """A spawn point for empires."""
    column: int
    row: int
    flags: int


@dataclass
class HumankindMap:
    """Parsed Humankind map data."""
    width: int
    height: int
    use_map_cycling: bool
    biome_names: list[str]
    terrain_type_names: list[str]
    territories: list[Territory]
    spawn_points: list[SpawnPoint]
    zones_texture: np.ndarray  # 2D array of territory indices
    elevation_texture: Optional[np.ndarray] = None

    @property
    def territory_count(self) -> int:
        return len(self.territories)

    @property
    def land_territory_count(self) -> int:
        return sum(1 for t in self.territories if not t.is_ocean)

    @property
    def ocean_territory_count(self) -> int:
        return sum(1 for t in self.territories if t.is_ocean)

    def get_hex_counts(self) -> dict[int, int]:
        """Count hexes per territory."""
        unique, counts = np.unique(self.zones_texture, return_counts=True)
        return dict(zip(unique.tolist(), counts.tolist()))

    def get_biome_name(self, biome_index: int) -> str:
        """Get biome name by index."""
        if 0 <= biome_index < len(self.biome_names):
            return self.biome_names[biome_index]
        return f"Unknown({biome_index})"


def decode_texture(base64_data: str, single_channel: bool = False) -> np.ndarray:
    """Decode base64 PNG texture to numpy array.

    Args:
        base64_data: Base64-encoded PNG data
        single_channel: If True, return only the first channel (for zone textures)
    """
    png_bytes = base64.b64decode(base64_data)
    img = Image.open(io.BytesIO(png_bytes))
    arr = np.array(img)
    if single_channel and arr.ndim == 3:
        # Zone texture stores territory index in first channel (R of RGBA)
        return arr[:, :, 0]
    return arr


def parse_hms_file(hms_path: Path) -> HumankindMap:
    """Parse a .hms (XML) map save file."""
    tree = ET.parse(hms_path)
    root = tree.getroot()

    terrain_save = root.find('TerrainSave')
    if terrain_save is None:
        raise ValueError("No TerrainSave element found")

    # Basic dimensions
    width = int(terrain_save.findtext('Width', '0'))
    height = int(terrain_save.findtext('Height', '0'))
    use_map_cycling = terrain_save.findtext('UseMapCycling', 'false').lower() == 'true'

    # Biome names
    biome_names = []
    biome_names_elem = terrain_save.find('BiomeNames')
    if biome_names_elem is not None:
        for string_elem in biome_names_elem.findall('String'):
            biome_names.append(string_elem.text or '')

    # Terrain type names
    terrain_type_names = []
    terrain_names_elem = terrain_save.find('TerrainTypeNames')
    if terrain_names_elem is not None:
        for string_elem in terrain_names_elem.findall('String'):
            terrain_type_names.append(string_elem.text or '')

    # Territories
    territories = []
    territory_db = terrain_save.find('TerritoryDatabase')
    if territory_db is not None:
        territories_elem = territory_db.find('Territories')
        if territories_elem is not None:
            for idx, item in enumerate(territories_elem.findall('Item')):
                continent_index = int(item.findtext('ContinentIndex', '0'))
                biome = int(item.findtext('Biome', '0'))
                is_ocean = item.findtext('IsOcean', 'false').lower() == 'true'
                territories.append(Territory(
                    index=idx,
                    continent_index=continent_index,
                    biome=biome,
                    is_ocean=is_ocean
                ))

    # Spawn points
    spawn_points = []
    entities_provider = terrain_save.find('EntitiesProvider')
    if entities_provider is not None:
        spawn_points_elem = entities_provider.find('SpawnPoints')
        if spawn_points_elem is not None:
            for item in spawn_points_elem.findall('Item'):
                sp_elem = item.find('SpawnPoints')
                if sp_elem is not None:
                    column = int(sp_elem.findtext('Column', '0'))
                    row = int(sp_elem.findtext('Row', '0'))
                    flags = int(item.findtext('Flags', '0'))
                    spawn_points.append(SpawnPoint(column=column, row=row, flags=flags))

    # Zone texture - single channel, stores territory index
    zones_bytes = terrain_save.findtext('ZonesTexture.Bytes', '')
    zones_texture = decode_texture(zones_bytes, single_channel=True)

    # Elevation texture (optional) - keep all channels
    elevation_texture = None
    elevation_bytes = terrain_save.findtext('ElevationTexture.Bytes', '')
    if elevation_bytes:
        elevation_texture = decode_texture(elevation_bytes)

    return HumankindMap(
        width=width,
        height=height,
        use_map_cycling=use_map_cycling,
        biome_names=biome_names,
        terrain_type_names=terrain_type_names,
        territories=territories,
        spawn_points=spawn_points,
        zones_texture=zones_texture,
        elevation_texture=elevation_texture,
    )


def parse_hmap_file(hmap_path: Path) -> HumankindMap:
    """Parse a .hmap (ZIP) map file containing Save.hms."""
    with zipfile.ZipFile(hmap_path, 'r') as zf:
        with zf.open('Save.hms') as hms_file:
            # Write to temp file or parse directly
            content = hms_file.read()
            tree = ET.fromstring(content)

            terrain_save = tree.find('TerrainSave')
            if terrain_save is None:
                raise ValueError("No TerrainSave element found")

            # Basic dimensions
            width = int(terrain_save.findtext('Width', '0'))
            height = int(terrain_save.findtext('Height', '0'))
            use_map_cycling = terrain_save.findtext('UseMapCycling', 'false').lower() == 'true'

            # Biome names
            biome_names = []
            biome_names_elem = terrain_save.find('BiomeNames')
            if biome_names_elem is not None:
                for string_elem in biome_names_elem.findall('String'):
                    biome_names.append(string_elem.text or '')

            # Terrain type names
            terrain_type_names = []
            terrain_names_elem = terrain_save.find('TerrainTypeNames')
            if terrain_names_elem is not None:
                for string_elem in terrain_names_elem.findall('String'):
                    terrain_type_names.append(string_elem.text or '')

            # Territories
            territories = []
            territory_db = terrain_save.find('TerritoryDatabase')
            if territory_db is not None:
                territories_elem = territory_db.find('Territories')
                if territories_elem is not None:
                    for idx, item in enumerate(territories_elem.findall('Item')):
                        continent_index = int(item.findtext('ContinentIndex', '0'))
                        biome = int(item.findtext('Biome', '0'))
                        is_ocean = item.findtext('IsOcean', 'false').lower() == 'true'
                        territories.append(Territory(
                            index=idx,
                            continent_index=continent_index,
                            biome=biome,
                            is_ocean=is_ocean
                        ))

            # Spawn points
            spawn_points = []
            entities_provider = terrain_save.find('EntitiesProvider')
            if entities_provider is not None:
                spawn_points_elem = entities_provider.find('SpawnPoints')
                if spawn_points_elem is not None:
                    for item in spawn_points_elem.findall('Item'):
                        sp_elem = item.find('SpawnPoints')
                        if sp_elem is not None:
                            column = int(sp_elem.findtext('Column', '0'))
                            row = int(sp_elem.findtext('Row', '0'))
                            flags = int(item.findtext('Flags', '0'))
                            spawn_points.append(SpawnPoint(column=column, row=row, flags=flags))

            # Zone texture - single channel, stores territory index
            zones_bytes = terrain_save.findtext('ZonesTexture.Bytes', '')
            zones_texture = decode_texture(zones_bytes, single_channel=True)

            # Elevation texture (optional) - keep all channels
            elevation_texture = None
            elevation_bytes = terrain_save.findtext('ElevationTexture.Bytes', '')
            if elevation_bytes:
                elevation_texture = decode_texture(elevation_bytes)

            return HumankindMap(
                width=width,
                height=height,
                use_map_cycling=use_map_cycling,
                biome_names=biome_names,
                terrain_type_names=terrain_type_names,
                territories=territories,
                spawn_points=spawn_points,
                zones_texture=zones_texture,
                elevation_texture=elevation_texture,
            )


def load_map(path: Path) -> HumankindMap:
    """Load a map from either .hms or .hmap file."""
    path = Path(path)
    if path.suffix.lower() == '.hmap':
        return parse_hmap_file(path)
    elif path.suffix.lower() == '.hms':
        return parse_hms_file(path)
    else:
        raise ValueError(f"Unknown file type: {path.suffix}")


def save_compact_map(map_data: HumankindMap, output_path: Path) -> None:
    """Save map data in compact numpy format.

    Output file contains:
    - zones: 2D array of territory indices (height x width)
    - width, height: map dimensions
    - territory_count: number of territories
    - territory_biomes: 1D array of biome index per territory
    - territory_is_ocean: 1D array of boolean per territory
    - territory_continent: 1D array of continent index per territory
    - biome_names: list of biome names (stored as string)
    """
    territory_biomes = np.array([t.biome for t in map_data.territories], dtype=np.uint8)
    territory_is_ocean = np.array([t.is_ocean for t in map_data.territories], dtype=np.bool_)
    territory_continent = np.array([t.continent_index for t in map_data.territories], dtype=np.uint8)

    np.savez_compressed(
        output_path,
        zones=map_data.zones_texture,
        width=map_data.width,
        height=map_data.height,
        territory_count=map_data.territory_count,
        territory_biomes=territory_biomes,
        territory_is_ocean=territory_is_ocean,
        territory_continent=territory_continent,
        biome_names=np.array(map_data.biome_names, dtype=object),
    )


def load_compact_map(npz_path: Path) -> dict:
    """Load compact map data from numpy format.

    Returns dict with same keys as save_compact_map.
    """
    data = np.load(npz_path, allow_pickle=True)
    return {
        'zones': data['zones'],
        'width': int(data['width']),
        'height': int(data['height']),
        'territory_count': int(data['territory_count']),
        'territory_biomes': data['territory_biomes'],
        'territory_is_ocean': data['territory_is_ocean'],
        'territory_continent': data['territory_continent'],
        'biome_names': data['biome_names'].tolist(),
    }
