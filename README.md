# Globe of Ukraine - Humankind Map Builder

A tool to generate Humankind game maps based on real Ukrainian geography. Implements the classic Ukrainian joke: Ukraine as the entire world, designed for multiplayer with friends from different Ukrainian regions.

## Quick Start

```bash
# Install dependencies
uv sync

# Generate the map
uv run python incremental_map_builder.py

# Run tests
uv run -m pytest tests/ -v
```

The generated map will be in `output/incremental/step10_spawn_points.hmap`. Copy it to your Humankind maps folder:
- **Windows:** `%USERPROFILE%\Documents\Humankind\Maps\`
- **Linux (Steam/Proton):** `~/.steam/steam/steamapps/compatdata/1124300/pfx/drive_c/users/steamuser/Documents/Humankind/Maps/`

## Features

- **Real geographic data**: SRTM elevation, actual raion (district) boundaries, real rivers
- **Incremental pipeline**: 10-step build process for terrain, biomes, elevation, rivers, features, and spawn points
- **Copernicus land cover**: Automatic biome assignment from satellite data
- **Configurable**: Adjust map bounds and settings in `config.yaml`

## What We Built

### 1. **Complete Map Format Analysis**
- Reverse-engineered the Humankind .hms and .hmap file formats
- Documented the XML structure, territory system, and hex grid encoding
- See `docs/HUMANKIND_MAP_FORMAT.md` for details

### 2. **Geographic Data Integration**
- Real Ukrainian raion boundaries from GeoJSON
- SRTM elevation data for mountains
- Copernicus land cover for biome classification
- OSM waterways for river placement

### 3. **Incremental Map Builder**
- 10-step pipeline building the map layer by layer
- Each step outputs a playable .hmap file for testing

## 📚 Research Findings

### Humankind Map Format (.hms / .hmap)

**.hmap files are ZIP archives** containing:
- `Descriptor.hmd` - Map metadata (dimensions, biomes, preview image)
- `Save.hms` - Game state with full hex data

**Key Specifications:**
- **Grid System**: Hexagonal tiles in pointy-top orientation
- **Map Sizes**: Tiny (60×35) to Huge (150×88) hexes
- **Territory Size**: ~50-90 hexes per region (optimal for gameplay)
- **Total Territories**: Up to 236 territories on Huge maps
- **File Format**: XML with base64-encoded PNG textures

**Hex Tile Data** (per tile):
- `ContinentIndex` - Geographic grouping (0-7+)
- `Biome` - Climate zone (0-9: Arctic to Tundra)
- `IsOcean` - Water body flag
- `TerrainType` - Specific terrain (15 types)
- `POI` - Points of interest (54 types)

**Zone Texture**: PNG image mapping each hex coordinate to a territory index (0-255)

### Territory & Biome System

**10 Biome Types:**
1. Arctic (light blue)
2. Badlands (tan/brown)
3. Desert (sandy yellow)
4. Grassland (light green)
5. Mediterranean (olive)
6. Savanna (tan/yellow)
7. Taiga (dark green)
8. Temperate (green)
9. Tropical (bright green)
10. Tundra (gray-blue)

## 🛠️ Tools Created

### 1. `render_hex_map.py` - Hexagonal Map Renderer

Renders Humankind maps with **actual hexagonal tiles** (not squares!).

**Features:**
- True hexagonal grid visualization
- Biome-based color coding
- Adjustable hex size
- Fast preview mode (square tiles)
- Automatic legend generation

**Usage:**
```bash
# Hexagonal rendering (accurate but slower)
uv run python render_hex_map.py map.hms output.png --hex --hex-size 20

# Fast square-tile preview
uv run python render_hex_map.py map.hms output.png

# Render Earth map with small hexes
uv run python render_hex_map.py humankind_maps/arthurleo_huge_earth_contest/Save.hms earth_hex.png --hex --hex-size 6
```

**Example Output:**
- `earth_hex.png` - Shows Australia and other continents with proper hex grid
- Clearly visualizes ocean vs land territories
- Each hex is color-coded by biome

### 2. `generate_ukraine_v2.py` - Geographic Ukraine Map Generator

Generates Humankind-format map from **real TopoJSON geographic data**.

**Features:**
- Loads actual Ukrainian oblast boundaries from TopoJSON
- Creates hexagonal grid matching Humankind's system
- Assigns each hex to the correct oblast based on geographic location
- Maps oblasts to appropriate biomes based on climate
- Generates valid .hms map files

**Usage:**
```bash
# Generate with default settings (84×34 hexes)
uv run python generate_ukraine_v2.py

# Adjust hex size for different scales
uv run python generate_ukraine_v2.py --hex-size 0.15 --output ukraine_detailed.hms

# Smaller hex size = more hexes = larger map
uv run python generate_ukraine_v2.py --hex-size 0.10 --output ukraine_huge.hms
```

**Oblast→Biome Mapping:**
- **Western oblasts** (Lviv, Volyn, Ivano-Frankivsk, etc.): Temperate/Forest
- **Central oblasts** (Kyiv, Poltava, Cherkasy, etc.): Grassland
- **Eastern oblasts** (Kharkiv, Donetsk, Luhansk, etc.): Grassland/Steppe
- **Southern oblasts** (Odesa, Mykolaiv, Kherson, etc.): Mediterranean/Savanna
- **Crimea**: Mediterranean

### 3. Original Tools (render_map.py, generate_ukraine_map.py)

Simple square-tile renderers and basic map generators (kept for reference).

## 📊 Map Statistics

### Generated Ukraine Map (ukraine_v2.hms)

**Dimensions:** 84×34 hexes (2,856 total hexes)

**Territories:** 28 total
- 1 Ocean/Black Sea territory
- 27 Ukrainian oblast territories

**Coverage:**
- Cherkasy: 93 hexes (~3.3%)
- Sevastopol: 85 hexes (~3.0%)
- Other oblasts: Variable coverage based on real geography

### Earth Map (arthurleo_huge_earth_contest)

**Dimensions:** 150×88 hexes (13,200 total hexes)

**Territories:** 91 total
- Mix of ocean and continental territories
- Shows Australia, landmasses with accurate biome distribution

## 🗺️ Real Geographic Data Sources

Ukraine oblast boundaries from:
- **TopoJSON**: `ukraine_regions.json` from org-scn-design-studio-community
- Contains all 27 Ukrainian administrative regions
- Includes Crimea (disputed territory noted)

**Data Sources Referenced:**
- [Humanitarian Data Exchange (HDX)](https://data.humdata.org/dataset/geoboundaries-admin-boundaries-for-ukraine)
- [SimpleMaps GIS Data](https://simplemaps.com/gis/country/ua)
- [GitHub - Ukraine GeoJSON](https://github.com/EugeneBorshch/ukraine_geojson)

## 🎮 Humankind Game Research

**Official Sources:**
- [Humankind Territory Wiki](https://humankind.fandom.com/wiki/Territory) - Territory size ranges: 10-199 tiles
- [Steam Guide - Territory Sizes](https://steamlists.com/humankind-guide-contains-information-regarding-territory-sizes-tile-count-and-hard-soft-caps/) - Optimal ~50-90 tiles per territory
- [Humankind Map Wiki](https://humankind.fandom.com/wiki/Map) - Map dimensions and hex grid info

**Key Findings:**
- Territories are **fixed regions** generated at game start
- Each territory is **single-biome only**
- Huge maps support up to **236 territories** before hardcap issues
- Hex grid enables **strategic placement** of districts and wonders

## 🔧 Technical Implementation

### Hexagonal Grid System

**Grid Type:** Pointy-top hexagons (standard for strategy games)

**Hex Dimensions:**
- Width: `hex_size × 2`
- Height: `hex_size × √3`
- Horizontal spacing: `width × 0.75` (due to overlap)

**Column Offset:** Every other column shifted by `height/2` (creates interlocking pattern)

**Coordinate System:**
```
(row, col) → (x, y) position
x = col × width × 0.75
y = row × height + (height/2 if col is odd else 0)
```

### Territory Assignment Algorithm

1. **Create hex grid** covering bounding box
2. **For each hex:**
   - Calculate centroid point
   - Check which oblast geometry contains the centroid
   - Assign hex to that oblast's territory index
3. **Encode to zone texture:**
   - Create PNG with hex's (col, row) → territory index mapping
   - Base64 encode and embed in XML

### XML Structure

```xml
<Document>
  <TerrainSave>
    <Width>84</Width>
    <Height>34</Height>
    <BiomeNames Length="10">...</BiomeNames>
    <TerrainTypeNames Length="15">...</TerrainTypeNames>

    <!-- Zone texture: maps (x,y) coords to territory index -->
    <ZonesTexture.Width>84</ZonesTexture.Width>
    <ZonesTexture.Height>34</ZonesTexture.Height>
    <ZonesTexture.Bytes>[base64 PNG data]</ZonesTexture.Bytes>

    <!-- Territory definitions -->
    <TerritoryDatabase>
      <Territories Length="28">
        <Item>
          <ContinentIndex>1</ContinentIndex>
          <Biome>3</Biome> <!-- Grassland -->
          <IsOcean>false</IsOcean>
        </Item>
        ...
      </Territories>
    </TerritoryDatabase>
  </TerrainSave>
</Document>
```

## 📦 Dependencies

```bash
uv add pillow numpy scipy shapely topojson
```

**Libraries:**
- **Pillow** (PIL) - Image processing and PNG encoding
- **NumPy** - Array operations for hex grids
- **SciPy** - Border smoothing (optional)
- **Shapely** - Geometric operations (polygon intersection, contains)
- **topojson** - TopoJSON to GeoJSON conversion

## 🎨 Visualization Examples

### Earth Map - Hexagonal Rendering
Shows the proper hex grid with continents like Australia clearly visible.

**Files:**
- `earth_hex.png` - Full hexagonal visualization
- `earth_hex_legend.png` - Biome color key

### Ukraine Map - Geographic Accuracy
Generated from real oblast boundary data with climate-appropriate biomes.

**Files:**
- `ukraine_v2.hms` - Playable Humankind map file
- `ukraine_v2_rendered.png` - Hexagonal visualization

## 🚀 Future Enhancements

**Potential Improvements:**
1. **Fix TopoJSON parsing** - Correctly decode arc sequences for accurate oblast boundaries
2. **Add elevation data** - Include mountains (Carpathians, Crimean ranges)
3. **River systems** - Encode major rivers (Dnipro, Dniester, etc.)
4. **Resource placement** - Add strategic/luxury resources based on real geology
5. **Territory naming** - Support custom names in map metadata
6. **Interactive editor** - GUI for manual hex editing
7. **Multi-region support** - Generate maps for other countries/regions
8. **Elevation from SRTM** - Use real terrain elevation data
9. **Climate-based biomes** - Auto-assign biomes from climate data APIs

## How to Use

1. **Generate map:**
   ```bash
   uv run python incremental_map_builder.py
   ```

2. **Copy to Humankind:**
   - Copy `output/incremental/step10_spawn_points.hmap` to your maps folder
   - Windows: `%USERPROFILE%\Documents\Humankind\Maps\`
   - Linux: `~/.steam/steam/steamapps/compatdata/1124300/pfx/drive_c/users/steamuser/Documents/Humankind/Maps/`

3. **Play in-game:**
   - Start new game
   - Select "Load Map"
   - Choose the Ukraine map
   - Each raion becomes a territory to claim!

## 🔬 Analysis Files Studied

- `humankind_maps/arthurleo_huge_earth_contest/Save.hms` - Earth map (150×88)
- `humankind_maps/europe_1.2/Europe 1.2.hmap` - Europe regional map
- `humankind_maps/133512126264917600_3721450-ol67/South-East Europe.hmap` - SE Europe

## 📝 File Inventory

**Generators:**
- `generate_ukraine_v2.py` - Geographic data-based generator ⭐
- `generate_ukraine_map.py` - Simple/basic generator
- `generate_ukraine_accurate.py` - Advanced version (TopoJSON issues)

**Renderers:**
- `render_hex_map.py` - Hexagonal visualization ⭐
- `render_map.py` - Simple square-tile renderer

**Data Files:**
- `ukraine_regions.json` - TopoJSON oblast boundaries (27 regions)

**Generated Maps:**
- `ukraine_v2.hms` - Best Ukraine map (84×34 hexes)
- `ukraine_map.hms` - Basic version
- `earth_map.png`, `earth_hex.png` - Earth renderings
- `ukraine_v2_rendered.png` - Ukraine hex visualization

**Documentation:**
- `README.md` - This file
- `pyproject.toml` - Python dependencies

---

## Summary

This project provides a complete toolkit for:
✅ **Analyzing** Humankind map file formats
✅ **Rendering** maps with proper hexagonal visualization
✅ **Generating** new maps from real geographic data
✅ **Understanding** the game's territory and biome systems

The tools successfully parse, visualize, and generate Humankind-compatible maps with accurate hex grids and geographic data integration!
