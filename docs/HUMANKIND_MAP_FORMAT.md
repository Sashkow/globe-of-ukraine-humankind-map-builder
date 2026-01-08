# Humankind Map File Format (.hmap)

This document describes the internal format of Humankind map files, based on analysis of the bhktools project and reverse engineering of working maps.

## File Structure

A `.hmap` file is a **ZIP archive** containing two XML files:

```
mapname.hmap (ZIP)
├── Descriptor.hmd    # Map metadata (empire count, etc.)
└── Save.hms          # Map data (textures, territories, spawns)
```

## Descriptor.hmd

Contains map metadata:

```xml
<Document>
  <TerrainSaveDescriptor>
    <EmpiresCount>10</EmpiresCount>
  </TerrainSaveDescriptor>
</Document>
```

## Save.hms Structure

The main map data file containing:

- Map dimensions (Width, Height)
- Author info
- Map options (UseMapCycling, UseProceduralMountainChains)
- Texture data (base64-encoded PNGs)
- Territory database
- Spawn points
- Landmark database
- Natural wonder names

### Map Dimensions

```xml
<Width>150</Width>
<Height>88</Height>
```

---

## Texture Encoding

All textures are stored as **base64-encoded PNG images** with RGBA channels. Each texture uses the channels differently.

### Common Pattern

```xml
<TextureName.Width>150</TextureName.Width>
<TextureName.Height>88</TextureName.Height>
<TextureName.Format>4</TextureName.Format>
<TextureName.Bytes Length="1234">iVBORw0KGgo...base64data...</TextureName.Bytes>
```

---

## ElevationTexture

Controls terrain height and type. Most complex encoding.

### Channel Usage

| Channel | Purpose | Range |
|---------|---------|-------|
| R | Elevation level | 1-15 (level = R - 4) |
| G | Terrain type + biome variant | 0-255 |
| B | Unused/flags | 0 |
| A | Unused | 0 |

### Bit-Level Encoding (from bhktools)

The elevation texture uses bit packing within the u32 pixel value:

```
Bits 0-3  (0x0F):       Heightfield value (0-15)
Bits 4-7:               Reserved/unused
Bits 8-11 (0x0F00>>8):  Tile type index (0-14)
Bits 12-31:             Reserved/unused
```


**Extraction code:**
```cpp
const ubyte height = elevation & 0x0F;
const ubyte tileIndex = (elevation >> 8) & 0x0F;
```

### R Channel: Elevation

When stored as PNG RGBA, elevation is encoded with an offset of 4:

| R Value | Game Level | Description |
|---------|------------|-------------|
| 1 | -3 | Deep ocean |
| 2 | -2 | Ocean |
| 3 | -1 | Shallow water / coastal |
| 4 | 0 | Sea level / beach |
| 5 | 1 | Low plains |
| 6 | 2 | Plains |
| 7 | 3 | Rolling hills |
| 8 | 4 | Hills |
| 9 | 5 | High hills |
| 10 | 6 | Low mountains |
| 11 | 7 | Mountains |
| 12 | 8 | High mountains |
| 13 | 9 | Alpine |
| 14 | 10 | High alpine |
| 15 | 11-12 | Peaks |

**Formula:** `R = elevation_level + 4`

### G Channel: Terrain Type Encoding

The G channel encodes both terrain type and biome variant:

```
G = (biome_variant << 4) | terrain_index
```

- **Lower 4 bits (G & 0x0F):** Terrain type index (0-14)
- **Upper 4 bits (G >> 4):** Biome variant (0-15, typically 0-9 used)

### Terrain Type Indices

The order comes from `<TerrainTypeNames>` in Save.hms. Default alphabetical order:

| Index | Terrain Name | Description |
|-------|--------------|-------------|
| 0 | CityTerrain | Default buildable land |
| 1 | CoastalWater | Shallow water near coast |
| 2 | DryGrass | Dry steppe/savanna |
| 3 | Forest | Dense forest |
| 4 | Lake | Inland water body |
| 5 | Mountain | Rocky mountains |
| 6 | MountainSnow | Snow-capped peaks |
| 7 | Ocean | Deep ocean |
| 8 | Prairie | Open grassland |
| 9 | RockyField | Rocky terrain |
| 10 | RockyForest | Forest on rocky ground |
| 11 | Sterile | Barren land |
| 12 | StoneField | Stony terrain |
| 13 | Wasteland | Desert-like |
| 14 | WoodLand | Light forest / woodland |

### Biome Variants

| Variant | Appearance |
|---------|------------|
| 0 | Arctic/snowy |
| 1 | Cold/tundra |
| 5 | Coastal |
| 7 | Temperate (most common default) |
| 3-8 | Various temperate biomes |

### Example: Mountain at Level 7, Temperate

```
R = 11  (7 + 4)
G = 117 ((7 << 4) | 5) = (112 | 5)
B = 0
A = 0
```

### Elevated Lakes

The game editor prevents elevated lakes, but the format supports them:

```
R = 9   (level 5 + 4)
G = 20  ((1 << 4) | 4) = Lake terrain, cold variant
B = 0
A = 0
```

---

## ZonesTexture

Assigns each hex to a territory.

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | Territory index (0-255) |
| G | Unused (0) |
| B | Unused (0) |
| A | Always 255 |

- **Territory 0** = Ocean (IsOcean=true)
- **Territory 1+** = Land territories

Must match entries in `<TerritoryDatabase>`.

---

## RiverTexture

Encodes river paths with flow direction.

### Channel Usage

| Channel | Purpose | Range |
|---------|---------|-------|
| R | River segment ID | 0-254 (255 = no river) |
| G | Position along segment | 0-255 |
| B | Exit edge direction | 0-5 |
| A | Always 0 |

### No River Marker

```
R = 255
G = 255
B = 6
A = 0
```

### River Encoding

Each connected river path gets a unique segment ID. Within each segment:

- **R** = Segment ID (0, 1, 2, ...)
- **G** = Sequential position (0 = start, 1, 2, ... along the river)
- **B** = Exit edge direction (which hex edge the river flows through)

### Hex Edge Directions (B value)

```
      0 (NE)
       ___
  5   /   \   1
(NW) /     \ (E)
     \     /
  4   \___/   2
 (W)    3    (SE)
       (SW)
```

| B | Direction |
|---|-----------|
| 0 | North-East |
| 1 | East |
| 2 | South-East |
| 3 | South-West |
| 4 | West |
| 5 | North-West |

### Example River Segment

A 3-hex river segment (ID=5) flowing SE:

| Hex | R | G | B |
|-----|---|---|---|
| Start | 5 | 0 | 2 |
| Middle | 5 | 1 | 2 |
| End | 5 | 2 | 2 |

---

## POITexture

Points of Interest - resources and terrain modifiers.

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | POI index (resource/modifier type) |
| G | Unused (0) |
| B | Unused (0) |
| A | Unused (0) |

**Decoding (from bhktools):**
```cpp
const u32 resourceIndex = poiData & 0xFF;
```

### POI Indices

#### Natural Modifiers (1-24)

| Index | Name | Description |
|-------|------|-------------|
| 0 | None | No POI |
| 1-24 | POI_NaturalModifier01-24 | Various terrain modifiers |

#### Strategic Resources (from bhktools resourceinfo.h)

| Index (Hex) | Index (Dec) | Name |
|-------------|-------------|------|
| 0x19 | 25 | Horse |
| 0x1A | 26 | Copper |
| 0x1B | 27 | Iron |
| 0x1C | 28 | Coal |
| 0x1D | 29 | Saltpetre |
| 0x1E | 30 | Oil |
| 0x1F | 31 | Aluminium |
| 0x20 | 32 | Uranium |

#### Luxury Resources (from bhktools resourceinfo.h)

| Index (Hex) | Index (Dec) | Name |
|-------------|-------------|------|
| 0x21 | 33 | Salt |
| 0x22 | 34 | Sage |
| 0x23 | 35 | Coffee |
| 0x24 | 36 | Tea |
| 0x25 | 37 | Saffron |
| 0x2A | 42 | Dye |
| 0x2B | 43 | Ebony |
| 0x2C | 44 | Marble |
| 0x2D | 45 | Obsidian |
| 0x2E | 46 | Silk |
| 0x2F | 47 | Incense |
| 0x30 | 48 | Porcelain |
| 0x31 | 49 | Pearls |
| 0x32 | 50 | Gold |
| 0x33 | 51 | Gemstone |
| 0x34 | 52 | Ambergris |
| 0x35 | 53 | Papyrus |
| 0x36 | 54 | Lead |
| 0x37 | 55 | Mercury |
| 0x38 | 56 | Silver |
| 0x39 | 57 | Weapon |

---

## NaturalWonderTexture

Places natural wonders on the map.

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | Wonder index (into NaturalWonderNames) |
| G | Unused |
| B | Unused |
| A | Unused |

- **R = 0xFF (255)** = No wonder (Invalid)
- **R = 0-N** = Index into `<NaturalWonderNames>` list

### Natural Wonder Indices (from bhktools)

| Index | Name |
|-------|------|
| 0 | Danakil Desert |
| 1 | Great Barrier Reef |
| 2 | Great Blue Hole |
| 3 | Halong Bay |
| 4 | Kawah Ijen |
| 5 | Lake Baikal |
| 6 | Lake Hillier |
| 7 | Mount Everest |
| 8 | Mount Mulu |
| 9 | Mount Roraima |
| 10 | Mount Vesuvius |
| 11 | Perito Moreno Glacier |
| 12 | Vinicunca |
| 13 | Yellowstone |

### NaturalWonderNames XML

```xml
<NaturalWonderNames Length="14">
    <String>DanakilDesert</String>
    <String>GreatBarrierReef</String>
    <String>GreatBlueHole</String>
    <String>HalongBay</String>
    <String>KawahIjen</String>
    <String>LakeBaikal</String>
    <String>LakeHillier</String>
    <String>MountEverest</String>
    <String>MountMulu</String>
    <String>MountRoraima</String>
    <String>MountVesuvius</String>
    <String>PeritoMorenoGlacier</String>
    <String>Vinicunca</String>
    <String>Yellowstone</String>
</NaturalWonderNames>
```

---

## LandmarksTexture

Landmark regions (Desert, Forest, Lake, Mountain, River).

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | Landmark index (into LandmarkDatabase) |
| G | Unused |
| B | Unused |
| A | Unused |

- **R = 255 (0xFF)** = No landmark

### Landmark Definition Types

| Index | Type |
|-------|------|
| 0 | Desert |
| 1 | Forest |
| 2 | Lake |
| 3 | Mountain |
| 4 | River |

---

## VisibilityTexture

Controls hex visibility/fog of war state.

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | Visibility flags |
| G | Unused |
| B | Unused |
| A | Unused |

---

## RoadTexture

Pre-placed roads on the map.

### Channel Usage

| Channel | Purpose |
|---------|---------|
| R | Road type/presence |
| G | Unused |
| B | Unused |
| A | Unused |

---

## MatchingSeedTexture

Used for procedural generation matching/seeding.

---

## TerritoryDatabase

Defines territories and their properties.

```xml
<TerritoryDatabase>
    <Territories Length="142">
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
        <!-- ... more territories ... -->
    </Territories>
</TerritoryDatabase>
```

### Territory Fields

| Field | Description |
|-------|-------------|
| ContinentIndex | 0 = Ocean, 1+ = Continent ID |
| Biome | Biome type (see below) |
| IsOcean | true for water territories |

### Territory Constraints (from community testing)

| Constraint | Value |
|------------|-------|
| Maximum territories | **255** (index 0-255, 256 total) |
| Minimum size | ~10 tiles |
| Maximum size | ~199 tiles |
| Recommended size | ~50 tiles for land |
| Ocean water ratio | Must be ≥50% water tiles |
| Continent land ratio | Must be ≥50% land tiles |

**Validation Rules:**
- All tiles in a territory must be connected (no islands in land territories)
- Territories with disconnected parts (islands) must be Ocean type
- The entire map must be covered by territories
- Territory index 0 is reserved for ocean

### Biome Types

| Index | Biome |
|-------|-------|
| 0 | Arctic |
| 1 | Badlands |
| 2 | Desert |
| 3 | Grassland |
| 4 | Mediterranean |
| 5 | Savanna |
| 6 | Taiga |
| 7 | Temperate |
| 8 | Tropical |
| 9 | Tundra |

---

## SpawnPoints

Player starting locations.

```xml
<EntitiesProvider>
    <SpawnPoints Length="10">
        <Item>
            <SpawnPoints>
                <Column>45</Column>
                <Row>32</Row>
            </SpawnPoints>
            <Flags>1023</Flags>
        </Item>
        <!-- ... more spawn points ... -->
    </SpawnPoints>
</EntitiesProvider>
```

### Spawn Fields

| Field | Description |
|-------|-------------|
| Column | X coordinate (0 to Width-1) |
| Row | Y coordinate (0 to Height-1, **inverted in file**) |
| Flags | Bitmask for player counts |

### Row Inversion

**Important:** Rows are stored inverted in the file:
```
file_row = height - game_row - 1
```

### Flags Bitmask

Each bit indicates the spawn is valid for that player count:

| Bit | Player Count |
|-----|--------------|
| 0 (1) | 1 player |
| 1 (2) | 2 players |
| 2 (4) | 3 players |
| ... | ... |
| 9 (512) | 10 players |

**Flags = 1023 (0x3FF)** = Valid for all player counts (1-10)

### Spawn Point Constraints

| Constraint | Value |
|------------|-------|
| Maximum spawns | **10** (one per player) |
| Default editor limit | 8 (must manually edit XML for 9-10) |

**Important Notes:**
- Spawn order in the file determines player assignment order
- To add 9th/10th player spawns, manually edit `Save.hms` and update `EmpiresCount` in `Descriptor.hmd`
- The spawn order can be reordered by changing the `<Item>` order in the XML

---

## Hex Coordinate System

Humankind uses **odd-r offset coordinates** for its hex grid.

### Odd-R Offset

- Odd rows are shifted right by 0.5 hex widths
- Origin (0,0) is top-left

```
Row 0:  [0,0] [1,0] [2,0] [3,0]
Row 1:    [0,1] [1,1] [2,1] [3,1]
Row 2:  [0,2] [1,2] [2,2] [3,2]
Row 3:    [0,3] [1,3] [2,3] [3,3]
```

### Neighbor Offsets

**Even rows (row % 2 == 0):**
| Direction | Offset (col, row) |
|-----------|-------------------|
| NE | (0, -1) |
| E | (+1, 0) |
| SE | (0, +1) |
| SW | (-1, +1) |
| W | (-1, 0) |
| NW | (-1, -1) |

**Odd rows (row % 2 == 1):**
| Direction | Offset (col, row) |
|-----------|-------------------|
| NE | (+1, -1) |
| E | (+1, 0) |
| SE | (+1, +1) |
| SW | (0, +1) |
| W | (-1, 0) |
| NW | (0, -1) |

### Hex UV Adjustment (from bhktools shader)

When rendering hex grids, odd/even rows need UV coordinate adjustment:

```glsl
// From territories_ps.fx
float2 hexUV(float2 uv)
{
    if (0 != (PASS_FLAG_HEXES & passFlags))
    {
        if (0 != (int(uv.y * texSize.y) & 1))
            uv.x += 0.25f / texSize.x;   // Odd rows offset right
        else
            uv.x -= 0.25f / texSize.x;   // Even rows offset left
    }
    return uv;
}
```

**For sprite positioning:**
```cpp
spriteOffset.x = (row & 1) ? -0.25f * cellWidth : +0.25f * cellWidth;
```

---

## Texel Flags (from bhktools shader/common.h)

When rendering, the B channel of certain textures contains flags:

### Texel Flags

```c
#define TEXEL_FLAG_WATER_TILE       0x20  // 32 - Tile is water (coastal/ocean/lake)
#define TEXEL_FLAG_OCEAN_TERRITORY  0x40  // 64 - Territory is ocean
#define TEXEL_FLAG_VISIBLE          0x80  // 128 - Tile is visible
```

### Pass Type Flags

```c
#define PASS_TYPE_TILE      0   // Tile type display
#define PASS_TYPE_TERRITORY 1   // Territory display
#define PASS_TYPE_LANDMARK  2   // Landmark display
#define PASS_TYPE_BIOME     3   // Biome display
#define PASS_TYPE_WONDER    4   // Wonder display
#define PASS_TYPE_MASK      0xF

#define PASS_FLAG_BORDERS   0x40000000  // Draw territory borders
#define PASS_FLAG_HEXES     0x80000000  // Apply hex offset
```

### Usage in Rendering (from map_refresh.hpp)

```cpp
// Water tile detection
switch ((TileType)tileIndex) {
    case TileType::Coastal:
    case TileType::Ocean:
    case TileType::Lake:
        territoryColor.b |= TEXEL_FLAG_WATER_TILE;
        heightfieldColor.b |= TEXEL_FLAG_WATER_TILE;
        break;
}

// Ocean territory
if (territory.ocean)
    territoryColor.b |= TEXEL_FLAG_OCEAN_TERRITORY;
```

---

## TerrainTypeNames

Defines the order of terrain types used in G channel encoding.

```xml
<TerrainTypeNames Length="15">
    <String>CityTerrain</String>
    <String>CoastalWater</String>
    <String>DryGrass</String>
    <String>Forest</String>
    <String>Lake</String>
    <String>Mountain</String>
    <String>MountainSnow</String>
    <String>Ocean</String>
    <String>Prairie</String>
    <String>RockyField</String>
    <String>RockyForest</String>
    <String>Sterile</String>
    <String>StoneField</String>
    <String>Wasteland</String>
    <String>WoodLand</String>
</TerrainTypeNames>
```

**Important:** The terrain index in the G channel corresponds to the position in this list. Different maps may have different orders!

---

## Map Options

```xml
<UseMapCycling>false</UseMapCycling>
<UseProceduralMountainChains>false</UseProceduralMountainChains>
```

| Option | Description |
|--------|-------------|
| UseMapCycling | East-west map wrapping |
| UseProceduralMountainChains | Auto-generate mountain chains |

---

## Creating/Modifying Maps

### Basic Workflow

1. Extract .hmap (unzip)
2. Parse Save.hms XML
3. Decode base64 texture data
4. Load as PNG (RGBA)
5. Modify pixel values
6. Save as PNG
7. Encode to base64
8. Update XML with new base64 and Length
9. Repackage as .hmap (zip)

### Python Example

```python
import zipfile
import base64
from PIL import Image
import io

# Extract
with zipfile.ZipFile('map.hmap', 'r') as zf:
    save_content = zf.read('Save.hms').decode('utf-8-sig')

# Decode texture
import re
match = re.search(r'<ElevationTexture\.Bytes[^>]*>([^<]+)</ElevationTexture\.Bytes>', save_content)
b64_data = match.group(1)
png_data = base64.b64decode(b64_data)
img = Image.open(io.BytesIO(png_data))
pixels = img.load()

# Modify (example: set hex at col=50, row=30 to mountain level 7)
col, row = 50, 30
elevation = 7
terrain_idx = 5  # Mountain
biome_variant = 7  # Temperate
pixels[col, row] = (elevation + 4, (biome_variant << 4) | terrain_idx, 0, 0)

# Encode
buffer = io.BytesIO()
img.save(buffer, format='PNG')
new_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')

# Update XML and repackage...
```

---

## Heightmap Import (Map Editor)

The in-game map editor can import heightmap images.

### Requirements

| Property | Specification |
|----------|---------------|
| Format | PNG only |
| Aspect ratio | **2:1** (width:height matching map size) |
| Location | `Documents/Humankind/Maps/` |
| Required files | Heightmap PNG + palette reference image |

### Elevation Levels

| Level | Description |
|-------|-------------|
| -3 to -1 | Ocean/water (4 levels) |
| 0 | Sea level / first land level |
| 1 to 12 | Land elevations (12 levels) |

**Total: 16 height levels (-3 to 12)**

---

## Community Tools

### bhktools

Unofficial map viewer/editor for Humankind .hmap files.

- **GitHub:** [vimontgames/bhktools](https://github.com/vimontgames/bhktools)
- **Features:**
  - Read/write .hmap files
  - Visualize elevation, territories, biomes, resources
  - Manage spawn points (up to 10 players)
  - Fix corrupted saves from landmark issues
- **Dependencies:** SFML, Dear ImGui, TinyXML-2, miniz-cpp

### Alpha Channel Fix Script (Java)

The decoded PNG textures have transparent pixels. This script fixes them:

```java
// From community: https://pastebin.com/7FnN71ec
BufferedImage img = ImageIO.read(new File("image.png"));
for (int x = 0; x < img.getWidth(); x++) {
    for (int y = 0; y < img.getHeight(); y++) {
        int argb = img.getRGB(x, y);
        argb = argb | 0xFF000000;  // Set alpha to 255
        img.setRGB(x, y, argb);
    }
}
ImageIO.write(img, "png", new File("imageout.png"));
```

---

## References

### Primary Sources

- **bhktools**: Map editor/viewer for Humankind (C++/SFML)
  - Source analyzed: `/home/shivers/py/bhktools/`
  - Key files: `map.h`, `map_import.hpp`, `map_export.hpp`, `map_refresh.hpp`, `resourceinfo.h`
  - Shader files: `common.h`, `territories_ps.fx`, `heightfield_ps.fx`
- **Humankind Map Editor**: In-game tool (limited compared to raw file editing)

### Community Resources

- [Humankind Fandom Wiki - Map Editor Manual](https://humankind.fandom.com/wiki/Map_Editor)
- [Amplitude Studios Forums - Humankind Save Format](https://community.amplitude-studios.com/amplitude-studios/humankind/forums/178-modding/threads/44781-humankind-save-format)
- [Amplitude Studios Forums - World Wrap and Custom Map Size](https://community.amplitude-studios.com/amplitude-studios/humankind/forums/214-maps/threads/42349-world-wrap-and-custom-map-size-how-to)
- [mod.io - Map Editor Manual Guide](https://mod.io/g/humankind/r/map-editor-manual)
- [GitHub - bhktools Releases](https://github.com/vimontgames/bhktools/releases)

---

## Complete File Examples

### Descriptor.hmd (Minimal)

```xml
<?xml version="1.0" encoding="utf-8"?>
<Document>
    <TerrainSaveDescriptor>
        <EmpiresCount>2</EmpiresCount>
    </TerrainSaveDescriptor>
</Document>
```

### Save.hms (Minimal "1-2 of Everything")

```xml
<?xml version="1.0" encoding="utf-8"?>
<Document>
    <TerrainSave>
        <!-- Map dimensions -->
        <FormatRevision>10</FormatRevision>
        <Width>10</Width>
        <Height>8</Height>

        <!-- Map options -->
        <UseMapCycling>false</UseMapCycling>
        <UseProceduralMountainChains>false</UseProceduralMountainChains>

        <!-- Biome names (fixed order, all 10) -->
        <BiomeNames Length="10">
            <String>Arctic</String>
            <String>Badlands</String>
            <String>Desert</String>
            <String>Grassland</String>
            <String>Mediterranean</String>
            <String>Savanna</String>
            <String>Taiga</String>
            <String>Temperate</String>
            <String>Tropical</String>
            <String>Tundra</String>
        </BiomeNames>

        <!-- Terrain type names (order defines G channel indices) -->
        <TerrainTypeNames Length="15">
            <String>CityTerrain</String>
            <String>CoastalWater</String>
            <String>DryGrass</String>
            <String>Forest</String>
            <String>Lake</String>
            <String>Mountain</String>
            <String>MountainSnow</String>
            <String>Ocean</String>
            <String>Prairie</String>
            <String>RockyField</String>
            <String>RockyForest</String>
            <String>Sterile</String>
            <String>StoneField</String>
            <String>Wasteland</String>
            <String>WoodLand</String>
        </TerrainTypeNames>

        <!-- POI/Resource names -->
        <POINames Length="54">
            <String>None</String>
            <String>POI_NaturalModifier01</String>
            <!-- ... POI_NaturalModifier02-24 ... -->
            <String>POI_ResourceDeposit01</String>
            <!-- ... POI_ResourceDeposit02-31 ... -->
        </POINames>

        <!-- Natural wonder names -->
        <NaturalWonderNames Length="2">
            <String>MountEverest</String>
            <String>LakeBaikal</String>
        </NaturalWonderNames>

        <!-- Landmark definition names -->
        <LandmarksDefinitionNames Length="5">
            <String>Landmark_Desert</String>
            <String>Landmark_Forest</String>
            <String>Landmark_Lake</String>
            <String>Landmark_Mountain</String>
            <String>Landmark_River</String>
        </LandmarksDefinitionNames>

        <!-- ========== TEXTURES (base64 PNG) ========== -->

        <!-- Elevation: R=level+4, G=(variant<<4)|terrain_idx -->
        <ElevationTexture.Width>10</ElevationTexture.Width>
        <ElevationTexture.Height>8</ElevationTexture.Height>
        <ElevationTexture.Format>4</ElevationTexture.Format>
        <ElevationTexture.Bytes Length="123">iVBORw0KGgo...base64...</ElevationTexture.Bytes>

        <!-- Zones: R=territory_idx (0=ocean, 1+=land) -->
        <ZonesTexture.Width>10</ZonesTexture.Width>
        <ZonesTexture.Height>8</ZonesTexture.Height>
        <ZonesTexture.Format>4</ZonesTexture.Format>
        <ZonesTexture.Bytes Length="123">iVBORw0KGgo...base64...</ZonesTexture.Bytes>

        <!-- POI: R=poi_index -->
        <POITexture.Width>10</POITexture.Width>
        <POITexture.Height>8</POITexture.Height>
        <POITexture.Format>4</POITexture.Format>
        <POITexture.Bytes Length="123">iVBORw0KGgo...base64...</POITexture.Bytes>

        <!-- Visibility: R=visibility_flags -->
        <VisibilityTexture.Width>10</VisibilityTexture.Width>
        <VisibilityTexture.Height>8</VisibilityTexture.Height>
        <VisibilityTexture.Format>4</VisibilityTexture.Format>
        <VisibilityTexture.Bytes Length="123">iVBORw0KGgo...base64...</VisibilityTexture.Bytes>

        <!-- Roads: R=road_type -->
        <RoadTexture.Width>10</RoadTexture.Width>
        <RoadTexture.Height>8</RoadTexture.Height>
        <RoadTexture.Format>4</RoadTexture.Format>
        <RoadTexture.Bytes Length="117">iVBORw0KGgo...base64...</RoadTexture.Bytes>

        <!-- Rivers: R=segment_id (255=none), G=position, B=edge(0-5) -->
        <RiverTexture.Width>10</RiverTexture.Width>
        <RiverTexture.Height>8</RiverTexture.Height>
        <RiverTexture.Format>4</RiverTexture.Format>
        <RiverTexture.Bytes Length="123">iVBORw0KGgo...base64...</RiverTexture.Bytes>

        <!-- Natural Wonders: R=wonder_idx (255=none) -->
        <NaturalWonderTexture.Width>10</NaturalWonderTexture.Width>
        <NaturalWonderTexture.Height>8</NaturalWonderTexture.Height>
        <NaturalWonderTexture.Format>4</NaturalWonderTexture.Format>
        <NaturalWonderTexture.Bytes Length="123">iVBORw0KGgo...base64...</NaturalWonderTexture.Bytes>

        <!-- Matching Seed (procedural gen) -->
        <MatchingSeedTexture.Width>10</MatchingSeedTexture.Width>
        <MatchingSeedTexture.Height>8</MatchingSeedTexture.Height>
        <MatchingSeedTexture.Format>4</MatchingSeedTexture.Format>
        <MatchingSeedTexture.Bytes Length="117">iVBORw0KGgo...base64...</MatchingSeedTexture.Bytes>

        <!-- Landmarks: R=landmark_idx (255=none) -->
        <LandmarksTexture.Width>10</LandmarksTexture.Width>
        <LandmarksTexture.Height>8</LandmarksTexture.Height>
        <LandmarksTexture.Format>4</LandmarksTexture.Format>
        <LandmarksTexture.Bytes Length="123">iVBORw0KGgo...base64...</LandmarksTexture.Bytes>

        <!-- ========== DATABASES ========== -->

        <!-- Landmark database (can be null/empty) -->
        <LandmarkDatabase>
            <Landmarks Null="true" />
        </LandmarkDatabase>

        <!-- Territory database: 1 ocean + 2 land territories -->
        <TerritoryDatabase>
            <Territories Length="3">
                <!-- Territory 0: Ocean -->
                <Item>
                    <ContinentIndex>0</ContinentIndex>
                    <Biome>0</Biome>
                    <IsOcean>true</IsOcean>
                </Item>
                <!-- Territory 1: Land (Temperate) -->
                <Item>
                    <ContinentIndex>1</ContinentIndex>
                    <Biome>7</Biome>
                    <IsOcean>false</IsOcean>
                </Item>
                <!-- Territory 2: Land (Desert) -->
                <Item>
                    <ContinentIndex>1</ContinentIndex>
                    <Biome>2</Biome>
                    <IsOcean>false</IsOcean>
                </Item>
            </Territories>
        </TerritoryDatabase>

        <!-- ========== SPAWN POINTS ========== -->

        <EntitiesProvider>
            <SpawnPoints Length="2">
                <!-- Player 1 spawn (for 1-2 player games) -->
                <Item>
                    <SpawnPoints>
                        <Column>3</Column>
                        <Row>4</Row>
                    </SpawnPoints>
                    <Flags>3</Flags>  <!-- bits 0+1 = 1+2 player games -->
                </Item>
                <!-- Player 2 spawn (for 2 player games only) -->
                <Item>
                    <SpawnPoints>
                        <Column>7</Column>
                        <Row>4</Row>
                    </SpawnPoints>
                    <Flags>2</Flags>  <!-- bit 1 = 2 player games -->
                </Item>
            </SpawnPoints>
        </EntitiesProvider>

        <!-- ========== METADATA ========== -->

        <Author Null="true" />
        <Description Null="true" />
        <CreationDate>0</CreationDate>
        <LastEditionDate>0</LastEditionDate>
        <FailureFlags>0</FailureFlags>
        <MapName Null="true" />

    </TerrainSave>
</Document>
```

### Notes on the Example

1. **Texture Format**: All textures use `Format=4` (RGBA PNG)

2. **Texture Sizes**: Must match `Width` and `Height` at the top

3. **Territory Count**: `Territories Length` must match the highest territory index + 1 used in ZonesTexture

4. **Spawn Flags**:
   - `Flags=1` → spawn for 1 player game only
   - `Flags=2` → spawn for 2 player game only
   - `Flags=3` → spawn for 1-2 player games
   - `Flags=1023` → spawn for all player counts (1-10)

5. **Empty/Default Textures**: Roads, Visibility, MatchingSeed can be "empty" (all zeros) for basic maps

6. **River No-Data**: Use `(255, 255, 6, 0)` RGBA for hexes without rivers

7. **Wonder/Landmark No-Data**: Use `R=255` for hexes without wonders/landmarks

---
> UseProceduralMountainChains is it set true or false j 
## Version History

- **2024-12-24**: Initial documentation based on bhktools analysis and map reverse engineering
