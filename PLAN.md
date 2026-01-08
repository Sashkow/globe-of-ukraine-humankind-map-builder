# Plan: Geographically Accurate Ukraine Map for Humankind

## Goal
Create a playable, geographically accurate map of Ukraine in Humankind game format at the maximum detail level the game supports, with Ukrainian raions (districts) as game territories.

## Constraints Analysis

### Map Size Limits
- Maximum Humankind map: 150×88 hexes (13,200 total hexes)
- Recommended territory size: 50-90 hexes per territory
- Ukraine has 136 raions (districts) after 2020 administrative reform
- Each oblast has 3-8 raions
- Target: ~72 hexes per raion for optimal gameplay

### Geographic Scale
- Ukraine dimensions: ~1,300 km (W-E) × ~900 km (N-S)
- Ukraine area: ~603,628 km²
- Average raion size: ~4,439 km² (603,628 km² ÷ 136 raions)
- With 136 territories at 72 hexes each: ~9,750 hexes for Ukraine landmass
- Remaining hexes: ~3,450 for ocean/buffer (26% of map - much better!)

### Hex Size Calculation
- Target: Use ~130 hexes width × ~75 hexes height for Ukraine
- Horizontal coverage: 1,300 km ÷ 130 hexes = 10 km spacing
- Hex side length: **~6.7 km**
- Hex area: **~116 km² per hex**
- Map coverage with 150×88 grid: adequate for Ukraine + Black Sea buffer
- Territory sizes: 136 raions × 72 hexes avg = 9,792 hexes (74% of map for landmass)

---

## Phase 1: Foundation & Data Understanding

### Task 1.1: Parse existing map completely
**Goal:** Fully understand the zone texture encoding used by actual Humankind maps

**Test:** Create test that verifies we can read the Earth map and confirm it has 91 territories with expected hex counts

**Steps:**
1. Write test: `test_parse_earth_map()` that loads Earth map and asserts territory count = 91
2. Read zones texture, get unique pixel values
3. Create histogram of territory assignments (how many hexes per territory)
4. Verify against known map structure (Australia should be ~X hexes)
5. Only proceed when test passes and histogram looks reasonable

**Validation:** Print first 10×10 region of zone texture as ASCII art showing territory indices, manually verify it makes sense

### Task 1.2: Create compact map analysis format
**Goal:** Since large files exceed token limits, extract just the essential data

**Test:** `test_extract_map_summary()` - verify extracted summary contains all territories and their hex positions

**Steps:**
1. Write test that checks summary has all required fields
2. Create function to extract: (a) territory list with biomes, (b) zone texture as numpy array, (c) map dimensions
3. Save as compact .npz file (NumPy compressed format)
4. Verify we can reload and reconstruct full zone texture
5. Compare file sizes (XML vs NPZ)

**Output:** `map_name_compact.npz` with keys: zones, territories, width, height, biomes

### Task 1.3: Render existing map correctly
**Goal:** Prove our rendering pipeline works before generating new maps

**Test:** `test_render_earth_map()` - render Earth map, verify output image shows continents not just ocean

**Steps:**
1. Write test that renders Earth map to temp file
2. Load rendered image, count pixels of each color
3. Assert that non-ocean pixels are at least 5% of total (continents should be visible)
4. Manually inspect rendered image
5. Fix rendering until test passes

**Validation:** Earth map should clearly show Australia, Americas, Africa, Eurasia

---

## Phase 2: Hexagonal Mapping Research & Implementation

### Task 2.1: Research hex-to-geography mapping techniques
**Goal:** Find established methods for mapping real-world geography to hex grids

**Test:** Document findings in `hex_mapping_research.md` with at least 3 different techniques

**Research areas:**
1. GIS hex binning methods (H3 by Uber, etc.)
2. Game development hex mapping (Civ series, Humankind modding community)
3. Geospatial tessellation algorithms
4. How to handle coastlines and boundaries

**Output:** Written summary of techniques with pros/cons for our use case

### Task 2.2: Implement hex grid coordinate system
**Goal:** Create correct hexagonal coordinate system matching Humankind's format

**Test:** `test_hex_coordinates()` - verify hex positions match expected pattern

**Steps:**
1. Write test: create 10×10 hex grid, verify each hex center is at correct (x,y)
2. Implement pointy-top hex coordinate calculation
3. Test column offset (every other column should be shifted by height/2)
4. Verify hex vertices calculation for drawing
5. Test that hexes tile properly (no gaps or overlaps)

**Validation:** Render small test grid as image, manually verify hexagonal pattern is correct

### Task 2.3: Implement geographic coordinate to hex mapping
**Goal:** Convert lat/lon coordinates to hex grid coordinates

**Test:** `test_geo_to_hex()` - given known lat/lon points, verify they map to expected hex cells

**Steps:**
1. Write test with sample points (e.g., Kyiv center should map to specific hex)
2. Define bounding box for Ukraine + buffer
3. Calculate hex size in degrees based on target coverage
4. Implement lat/lon → hex(row, col) conversion
5. Test inverse: hex center → lat/lon
6. Verify edge cases (map boundaries)

**Output:** Bidirectional mapping functions with unit tests

---

## Phase 3: Geographic Data Preparation

### Task 3.1: Load and validate Ukraine geographic data
**Goal:** Get clean raion (district) boundary data in usable format

**Test:** `test_load_ukraine_data()` - verify we have 136 raions with valid geometries

**Steps:**
1. Write test asserting 136 raion features loaded
2. Download ADM2 (raion-level) boundaries from HDX or alternative GeoJSON source
3. For each raion: validate geometry, check it's valid polygon, verify bounds are within Ukraine
4. Test: compute centroid for each raion, verify they're within parent oblast bounds
5. Extract raion names and parent oblast information

**Data sources to try:**
- HDX Ukraine ADM2 boundaries: https://data.humdata.org/dataset/cod-ab-ukr
- Alternative GeoJSON sources if primary fails

**Validation:** Plot all 136 raion boundaries on matplotlib map, visually verify Ukraine shape and internal divisions

### Task 3.2: Verify geographic accuracy
**Goal:** Ensure raion geometries are correct before using them

**Test:** `test_raion_locations()` - verify major cities are in correct raions

**Known points to test:**
- Kyiv (50.45°N, 30.52°E) should be in specific Kyiv raion
- Lviv (49.84°N, 24.03°E) should be in specific Lviv raion
- Odesa (46.48°N, 30.73°E) should be in specific Odesa raion
- Kharkiv (49.99°N, 36.23°E) should be in specific Kharkiv raion

**Steps:**
1. Write test with city coordinates
2. For each city, check which raion polygon contains it
3. Assert correct raion name (and verify parent oblast is correct too)
4. If any fail, investigate data quality issues
5. Verify raion count per oblast (should be 3-8 per oblast)

---

## Phase 4: Territory Assignment & Biome Mapping ✓ READY TO IMPLEMENT

**Status:** Configuration optimized, hex grid validated, raion data loaded. Ready for territory assignment implementation.

### Task 4.1: Create territory assignment system
**Goal:** Build the core system that assigns hexes to raion territories

**Implementation approach:**
1. Create `TerritoryAssigner` class in `territory_assigner.py`
2. Use existing `GeoHexMapper` for coordinate conversion
3. Use loaded raion GeoDataFrame for polygon containment
4. Implement efficient point-in-polygon algorithm

**Key components:**
- **Input:** Hex grid (150×88), raion geometries (139 raions)
- **Output:** Dictionary mapping (col, row) → raion_index
- **Algorithm:** For each hex, test centroid against all raion polygons
- **Ocean handling:** Hexes not in any raion → ocean territory (index 0)

**Expected results (from config):**
- Total hexes: 13,200
- Ukraine hexes: ~8,102 (61.4% coverage)
- Ocean/buffer hexes: ~5,098 (38.6%)
- Hex size: ~5.20 km

### Task 4.2: Implement biome assignment
**Goal:** Map each raion to appropriate climate biome

**Biome mapping strategy:**
- Group raions by oblast
- Assign biome based on geographic location of oblast
- Use Humankind's 10 biome types

**Oblast → Biome mapping:**
```
Western Ukraine (Lviv, Volyn, Rivne, etc.):
  → Temperate (7) - forested regions

Central Ukraine (Kyiv, Cherkasy, Poltava, Vinnytsia):
  → Grassland (3) - fertile black earth steppes

Eastern Ukraine (Kharkiv, Donetsk, Luhansk, Dnipro):
  → Grassland (3) - steppe regions

Southern Ukraine (Odesa, Mykolaiv, Kherson, Zaporizhzhia):
  → Mediterranean (4) - coastal regions

Crimea:
  → Mediterranean (4) - warm coastal climate

Carpathian oblasts (Ivano-Frankivsk, Zakarpattia):
  → Temperate (7) with mountain terrain
```

### Task 4.3: Generate zone texture and territory database
**Goal:** Create the PNG zone texture and territory XML structure

**Zone texture generation:**
1. Create numpy array: shape=(88, 150), dtype=uint8
2. For each hex (col, row):
   - If assigned to raion → set pixel to raion territory index (1-139)
   - If ocean → set pixel to 0
3. Encode as PNG
4. Base64 encode for XML embedding

**Territory database:**
- Territory 0: Ocean (IsOcean=true)
- Territories 1-139: Raion territories with assigned biomes
- Each territory: ContinentIndex, Biome, IsOcean flag

**Validation:**
- All 139 raions have hexes assigned
- No territory has 0 hexes
- Average hexes per raion: ~58 (acceptable range: 30-90)

---

## Phase 5: Template-Based Incremental Map Generation

**Goal:** Build Ukraine map incrementally from a working template, testing each change to identify what breaks editor compatibility.

**Why this approach:**
- Start from a known-working template (`Huge_Ukraine_template.hmap`) created in the game editor
- Make ONE small change at a time
- Test each step in the game editor
- Identify exactly which modification breaks compatibility
- Avoid debugging complex multi-change failures

### Template: `Huge_Ukraine_template.hmap`
- Created in Humankind Map Editor from heightmap import
- Dimensions: 150×88 (matches config.yaml)
- Known working: can be opened and edited in game
- Contains: elevation, terrain types, coastlines from editor

### Incremental Steps

**Step 1: Baseline (step1_baseline.hmap)**
- Just copy the template unchanged
- Purpose: Verify our ZIP packaging doesn't break anything
- Expected: Opens in editor ✓

**Step 2: Add Territories (step2_territories.hmap)**
- Modify ONLY: ZonesTexture.Bytes (territory assignments)
- Modify ONLY: TerritoryDatabase (139 raions + 1 ocean)
- Keep everything else from template
- Purpose: Test if territory changes break editor
- Expected: Shows 140 territories instead of 1

**Step 3: Add Biomes (step3_biomes.hmap)**
- Modify ONLY: Biome field in each Territory item
- Keep zones texture from step 2
- Purpose: Test if biome assignments break editor
- Expected: Territories have correct biome colors

**Step 4: Add Elevation (step4_elevation.hmap)**
- Modify ONLY: ElevationTexture.Bytes
- Add Carpathian and Crimean mountain heights
- Keep everything else from step 3
- Purpose: Test if elevation changes break editor

**Step 5: Add Rivers (step5_rivers.hmap)**
- Modify ONLY: RiverTexture.Bytes
- Add Dnipro, Dniester, Southern Bug rivers
- Keep everything else from step 4
- Purpose: Test if river changes break editor

### Implementation: `incremental_map_builder.py`

```python
class IncrementalMapBuilder:
    def __init__(self, template_path):
        # Load template (Huge_Ukraine_template.hmap)
        # Parse Save.hms and Descriptor.hmd

    def step1_baseline(self) -> Path:
        # Just re-package template unchanged

    def step2_territories(self) -> Path:
        # Modify zones texture + territory database only

    def step3_biomes(self) -> Path:
        # Modify biome assignments only

    def step4_elevation(self) -> Path:
        # Modify elevation texture only

    def step5_rivers(self) -> Path:
        # Modify river texture only
```

### Output Directory
All incremental maps saved to:
- `output/incremental/step1_baseline.hmap`
- `output/incremental/step2_territories.hmap`
- `output/incremental/step3_biomes.hmap`
- `output/incremental/step4_elevation.hmap`
- `output/incremental/step5_rivers.hmap`

Also copied to game folder:
- `Humankind/Maps/incremental_ukraine/`

### Testing Protocol
For each step:
1. Generate the .hmap file
2. Copy to game Maps folder
3. Open Humankind Map Editor
4. Try to open the map
5. Record: Does it open? Can you edit? Any errors?
6. If broken: previous step is last known good

### Validation Checklist
- [ ] Step 1: Opens in editor
- [ ] Step 2: Shows 140 territories, opens in editor
- [ ] Step 3: Biomes display correctly, opens in editor
- [ ] Step 4: Mountains visible, opens in editor
- [ ] Step 5: Rivers visible, opens in editor

---

## Phase 6: Visualization & Testing

### Task 6.1: Create comprehensive visualizations
**Goal:** Generate multiple views of the map for validation

**Visualizations to create:**
1. **Rigid hex grid with raion colors**
   - Each hex properly rendered as hexagon
   - Raions colored using graph coloring (adjacent raions different colors)
   - Shows actual hex boundaries

2. **Oblast-level map with cities**
   - Hexes colored by oblast (not raion)
   - Major cities marked with labels
   - Easier to verify high-level geography

3. **Zone texture preview**
   - Direct rendering of zone texture PNG
   - Each pixel = territory index as color
   - Verifies zone texture encoding

4. **Coverage analysis map**
   - Ukraine land vs ocean/buffer zones
   - Shows hex density and coverage

**Output directory:** `output/visualizations/`

### Task 6.2: Run comprehensive test suite
**Goal:** Validate all aspects of generated map

**Test categories:**
1. **Grid tests** (Phase 2)
   - Hex coordinate system
   - Geographic bounds coverage

2. **Data tests** (Phase 3)
   - Raion geometries loaded correctly
   - 139 raions present

3. **Territory tests** (Phase 4)
   - All hexes assigned
   - Coverage statistics correct
   - No raion with 0 hexes

4. **Generation tests** (Phase 5)
   - XML well-formed
   - Zone texture dimensions correct
   - Territory count = 140

**Test execution:**
```bash
pytest tests/ -v --tb=short
```

### Task 6.3: Statistical analysis and reporting
**Goal:** Generate comprehensive statistics about the map

**Statistics to compute:**
1. **Coverage metrics:**
   - Total hexes: 13,200
   - Ukraine hexes: ~8,102 (61.4%)
   - Ocean hexes: ~5,098 (38.6%)

2. **Territory size distribution:**
   - Min/max/average hexes per raion
   - Size histogram
   - Outliers (< 30 or > 90 hexes)

3. **Oblast analysis:**
   - Hexes per oblast
   - Raions per oblast
   - Geographic accuracy check

4. **Biome distribution:**
   - Hexes per biome type
   - Biome diversity

**Output:** `output/statistics/map_analysis.txt`

---

## Phase 7: SRTM Elevation Data Integration

**Goal:** Download real SRTM elevation data and assign elevation levels to each hex in the map grid, integrated into the incremental map builder pipeline.

### Data Source: SRTM (Shuttle Radar Topography Mission)

**Why SRTM:**
- Free, well-documented, widely used
- 30m resolution (SRTM GL1) or 90m (SRTM GL3) - more than enough for our ~5km hexes
- Covers Ukraine completely (between 60°N and 56°S)
- Same source type as raion data (authoritative geospatial data)

**Data access options:**
1. **OpenTopography API** - direct download, requires free account
2. **USGS EarthExplorer** - official source, manual download
3. **elevation** Python package - automated SRTM download and caching
4. **rasterio + SRTM tiles** - download .hgt files directly

**Recommended: `elevation` package**
```bash
pip install elevation
```
- Automatically downloads and caches SRTM tiles
- Clips to bounding box
- Returns GeoTIFF ready for processing

### Task 7.1: Create SRTM Data Fetcher

**Goal:** Download and cache SRTM elevation data for Ukraine bounds

**File:** `srtm_elevation.py`

**Implementation:**
```python
class SRTMElevationFetcher:
    def __init__(self, bounds: dict):
        """
        bounds: {min_lon, max_lon, min_lat, max_lat}
        From config.yaml: 20-44°E, 43-53°N
        """
        self.bounds = bounds
        self.cache_dir = Path("data/srtm_cache")

    def fetch(self) -> np.ndarray:
        """
        Download SRTM data for bounds, return elevation array.
        Uses elevation package or direct .hgt download.
        """
        # Returns: 2D numpy array of elevation in meters
        pass

    def get_elevation_at(self, lon: float, lat: float) -> float:
        """Get elevation at specific coordinate."""
        pass
```

**Caching strategy:**
- Store downloaded tiles in `data/srtm_cache/`
- Cache merged GeoTIFF for Ukraine bounds
- Re-use cached data on subsequent runs

### Task 7.2: Create Hex Elevation Mapper

**Goal:** Sample SRTM elevation for each hex center and quantize to game levels

**File:** `hex_elevation_mapper.py`

**Humankind elevation levels (16 total, -3 to 12):**
```
Level  Elevation (m)    Terrain Type
-----  -------------    ------------
-3     < -100           Deep ocean
-2     -100 to -50      Ocean
-1     -50 to 0         Shallow water / Sea of Azov
 0     0 to 50          Coastal lowlands
 1     50 to 100        Low plains
 2     100 to 150       Plains (most of Ukraine)
 3     150 to 200       Rolling plains
 4     200 to 300       Low hills
 5     300 to 400       Hills (Podolian Upland)
 6     400 to 600       High hills (Donets Ridge)
 7     600 to 800       Low mountains
 8     800 to 1000      Mountains (Crimean)
 9     1000 to 1200     High mountains
10     1200 to 1500     Alpine (Carpathian foothills)
11     1500 to 1800     High alpine
12     > 1800           Peaks (Hoverla: 2061m)
```

**Implementation:**
```python
class HexElevationMapper:
    def __init__(self, srtm_fetcher: SRTMElevationFetcher,
                 grid_width: int, grid_height: int,
                 bounds: dict):
        self.srtm = srtm_fetcher
        self.width = grid_width
        self.height = grid_height
        self.bounds = bounds

    def get_hex_elevations(self) -> Dict[Tuple[int, int], int]:
        """
        For each hex (col, row), sample SRTM and return quantized level.
        Returns: {(col, row): elevation_level} where level is -3 to 12
        """
        hex_elevations = {}
        for row in range(self.height):
            for col in range(self.width):
                lon, lat = self._pixel_to_geo(col, row)
                elev_meters = self.srtm.get_elevation_at(lon, lat)
                level = self._quantize_elevation(elev_meters)
                hex_elevations[(col, row)] = level
        return hex_elevations

    def _quantize_elevation(self, meters: float) -> int:
        """Convert meters to game elevation level (-3 to 12)."""
        if meters < -100: return -3
        if meters < -50: return -2
        if meters < 0: return -1
        if meters < 50: return 0
        if meters < 100: return 1
        if meters < 150: return 2
        if meters < 200: return 3
        if meters < 300: return 4
        if meters < 400: return 5
        if meters < 600: return 6
        if meters < 800: return 7
        if meters < 1000: return 8
        if meters < 1200: return 9
        if meters < 1500: return 10
        if meters < 1800: return 11
        return 12
```

**Ocean handling:**
- Hexes outside Ukraine boundary → check if water body
- Black Sea / Sea of Azov → negative elevation levels
- SRTM has "no data" for ocean → use bathymetry or assign -2

### Task 7.3: Integrate into Incremental Map Builder

**Goal:** Add `step5_elevation()` that uses real SRTM data

**Update `incremental_map_builder.py`:**

```python
def step5_elevation(self) -> Path:
    """Step 5: Add SRTM-based elevation data."""
    print("STEP 5: SRTM Elevation")
    print("  Change: ElevationTexture.Bytes from real SRTM data")

    # Fetch SRTM data
    from srtm_elevation import SRTMElevationFetcher
    from hex_elevation_mapper import HexElevationMapper

    fetcher = SRTMElevationFetcher(self.bounds)
    mapper = HexElevationMapper(fetcher, self.width, self.height, self.bounds)

    hex_elevations = mapper.get_hex_elevations()

    # Create elevation texture PNG
    # Humankind uses R channel for elevation: 0-15 maps to levels -3 to 12
    img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 255))
    pixels = img.load()

    for (col, row), level in hex_elevations.items():
        # Convert level (-3 to 12) to pixel value (0 to 15)
        pixel_value = level + 3  # -3→0, 0→3, 12→15
        pixels[col, row] = (pixel_value, 0, 0, 255)

    # Encode and update save content
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    elevation_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')

    content = self._update_texture_bytes(
        self.current_save_content, 'ElevationTexture', elevation_b64
    )

    # Statistics
    level_counts = {}
    for level in hex_elevations.values():
        level_counts[level] = level_counts.get(level, 0) + 1
    print(f"  Elevation distribution: {dict(sorted(level_counts.items()))}")

    self.current_save_content = content
    output_path = self.output_dir / "step5_elevation.hmap"
    self._save_hmap(content, self.descriptor_content, output_path)

    return output_path
```

### Task 7.4: Validation and Visualization

**Goal:** Verify elevation data is correct before game import

**Validation steps:**
1. Generate elevation heatmap visualization
2. Verify Carpathians show highest values (levels 10-12)
3. Verify Crimean mountains show medium-high (levels 7-9)
4. Verify central plains are flat (levels 1-3)
5. Verify Black Sea is negative (levels -1 to -3)

**Visualization output:** `output/visualizations/ukraine_srtm_elevation.png`
- Color gradient from blue (ocean) to white (peaks)
- Overlay hex grid
- Mark key geographic features

**Expected elevation ranges (validation):**
- Hoverla (Carpathians): 2061m → level 12 ✓
- Ai-Petri (Crimea): 1234m → level 10 ✓
- Kyiv: 179m → level 3 ✓
- Odesa: 40m → level 0 ✓
- Black Sea: -2200m max → level -3 ✓

### Task 7.5: Handle Edge Cases

**Ocean/water bodies:**
- SRTM returns "no data" (-32768) for ocean
- Solution: If no data AND outside Ukraine boundary → assign ocean level
- Black Sea depth: use -2 (medium depth)
- Sea of Azov depth: use -1 (shallow)

**Border smoothing:**
- Coastal hexes may have mixed land/water
- Solution: Use hex center elevation, or average of samples within hex

**Missing tiles:**
- Some SRTM tiles may be unavailable
- Solution: Fall back to interpolation from neighbors, or use SRTM void-filled version

### Dependencies

**Python packages:**
```
elevation>=1.1.3      # SRTM download and processing
rasterio>=1.3.0       # GeoTIFF reading
numpy>=1.24.0         # Array operations
```

**Alternative if `elevation` package fails:**
```python
# Direct .hgt file download from USGS
# Files named like: N44E033.hgt (1°×1° tiles)
# Ukraine needs tiles from N43-N52, E020-E040
```

### Output Files

1. `data/srtm_cache/ukraine_srtm.tif` - Cached SRTM GeoTIFF
2. `output/visualizations/ukraine_srtm_elevation.png` - Visualization
3. `output/incremental/step5_elevation.hmap` - Map with real elevation

### Task 7.6: Add Major Rivers

**Goal:** Mark river hexes in RiverTexture

**Major rivers to include:**
1. **Dnipro** - Main river, bisects Ukraine north to south
2. **Dniester** - Western border with Moldova
3. **Southern Bug** - Southern Ukraine
4. **Danube Delta** - Southwest corner
5. **Donets** - Eastern Ukraine

**Data source options:**
- Natural Earth rivers (1:10m scale)
- OpenStreetMap waterways
- HydroSHEDS river network

**Implementation in `step6_rivers()`:**
- Load river geometries
- For each hex, check if river passes through
- Mark in RiverTexture

### Task 7.7: Package Final Map

**Goal:** Create distributable .hmap with all features

**Final map includes:**
- 140 territories (139 raions + ocean)
- Biomes by oblast
- SRTM elevation
- Major rivers

**Output:** `output/maps/ukraine_raions_final.hmap`

---

## Phase 8: Documentation & Completion

### Task 8.1: Update main README
**Goal:** Document the complete Ukraine raion map system

**Sections to update:**
1. **Project overview**
   - Add Ukraine raion map as main deliverable
   - Update statistics (150×88, 139 raions, 61% coverage)

2. **Usage guide**
   - How to generate the map
   - How to install in Humankind
   - Configuration options

3. **Technical details**
   - Hex grid system
   - Territory assignment algorithm
   - Biome mapping strategy

4. **File structure**
   - Describe key Python modules
   - Configuration system
   - Test organization

### Task 8.2: Create comprehensive examples
**Goal:** Provide working examples for users

**Examples to create:**
1. **generate_ukraine_map.py** - Main generation script
2. **visualize_map.py** - Create all visualizations
3. **analyze_map.py** - Run statistical analysis
4. **Configuration examples** - Different map variants

### Task 8.3: Final validation and delivery
**Goal:** Ensure everything works end-to-end

**Validation checklist:**
- [ ] All tests pass (pytest tests/ -v)
- [ ] Configuration system works
- [ ] Map generates without errors
- [ ] Visualizations render correctly
- [ ] Statistics compute properly
- [ ] Documentation is complete
- [ ] README is up to date
- [ ] Code is well-commented

**Deliverables:**
1. `ukraine_raions.hms` - Generated map file
2. Visualization images in `output/visualizations/`
3. Statistics report in `output/statistics/`
4. Complete documentation
5. Working test suite

---

## Testing Strategy (TDD Approach)

### Unit Tests
Each task should have tests written BEFORE implementation:
- Parse operations: verify data structures
- Coordinate conversions: verify math
- Geometry operations: verify correctness
- XML generation: verify schema compliance

### Integration Tests
- End-to-end: load data → generate map → render image
- Verify complete workflow succeeds
- Check output files exist and are valid

### Validation Tests
- Visual inspection of rendered maps
- Statistical analysis of hex distributions
- Comparison with reference maps

### Test Execution Order
1. Write test (FAIL - test fails because function doesn't exist)
2. Implement minimal code to make test pass (PASS)
3. Refactor code while keeping test passing
4. Validate manually
5. Move to next task only when current task passes all tests

---

## Success Criteria

**Phase 1-3 Completed ✅:**
✅ Configuration system with optimized bounds
✅ Hex grid system (150×88, ~5.2km hex size)
✅ Geographic coordinate mapping (lat/lon ↔ hex)
✅ Ukraine raion data loaded (139 raions)
✅ Visualizations working (rigid hex grid, oblast maps)

**Phase 4-5 Must Have:**
- [ ] Territory assignment algorithm (hex → raion mapping)
- [ ] 61% Ukraine coverage (~8,102 hexes)
- [ ] Average ~58 hexes per raion
- [ ] Biome assignment by oblast
- [ ] Zone texture generation (150×88 PNG)
- [ ] Complete .hms XML file generation
- [ ] All 139 raions have hexes (no 0-hex territories)

**Phase 6 Must Have:**
- [ ] Comprehensive visualizations
- [ ] All tests pass
- [ ] Statistical analysis report
- [ ] Geographic accuracy validated

**Phase 7 Must Have (SRTM Elevation):**
- [ ] SRTM data fetcher (download/cache tiles)
- [ ] Hex elevation mapper (sample + quantize to 16 levels)
- [ ] Integration into step5_elevation() in incremental builder
- [ ] Validation: Carpathians=10-12, Crimea=7-9, Plains=1-3, Sea=-1 to -3
- [ ] Elevation visualization

**Phase 7-8 Nice to Have:**
- [ ] Major rivers (Dnipro, Dniester) via step6_rivers()
- [ ] .hmap packaging
- [ ] User documentation
- [ ] Installation guide

**Current Status:**
- Configuration: ✅ Optimized (20-44°E, 43-52°N, 6-hex margins)
- Hex Grid: ✅ 150×88 working
- Raion Data: ✅ 139 raions loaded
- Visualization: ✅ Phase 3 complete
- Territory Assignment: 🔄 Ready to implement
- Map Generation: ⏳ Pending
- Testing: ⏳ Pending

**Quality Metrics:**
- Target coverage: 61.4% Ukraine, 38.6% ocean/buffer ✅
- Target raion size: 30-90 hexes (avg ~58) ✅
- Hex size: ~5.20 km ✅
- No raion < 20 hexes (TBD)
- Ukraine shape recognizable (TBD)

---

## Risk Mitigation

**Risk 1: TopoJSON parsing fails**
- Mitigation: Have backup GeoJSON sources ready
- Alternative: Manually simplify TopoJSON to GeoJSON

**Risk 2: Hex assignments produce too many ocean hexes**
- Mitigation: Validate at each step with test assertions
- Fix: Adjust bounding box or check geometry validity

**Risk 3: Generated map doesn't load in game**
- Mitigation: Compare byte-by-byte with working map
- Fix: Ensure XML structure exactly matches reference

**Risk 4: Task scope too large**
- Mitigation: Each phase broken into small, testable tasks
- Fix: Further subdivide any task that takes > 30 minutes

---

## Execution Notes

- Run tests after EVERY code change
- Don't proceed to next task until current tests pass
- Validate manually at each phase boundary
- Save working versions before making major changes
- Use version control (git) to track progress

---

## Phase 9: Land Cover Data Migration (Copernicus 100m)

**Goal:** Replace ESA WorldCover 10m with Copernicus 100m to reduce storage requirements from ~45GB to ~500MB.

### Problem

The original `landcover_fetcher.py` uses ESA WorldCover 10m data:
- Resolution: 10m per pixel
- Tile size: 3°×3° tiles, each ~1.3GB
- Ukraine bounds (20-44°E, 43-53°N) require 36 tiles
- Total storage: **~45GB**
- Many tiles failed to download (0-byte cache files)

This is overkill for our hex grid (~5km hexes).

### Solution: Copernicus Global Land Service 100m (CGLS-LC100)

**Dataset:** Copernicus Global Land Cover Layers Collection 3
- Resolution: 100m per pixel (10x coarser)
- Coverage: Global
- Format: Cloud Optimized GeoTIFF on AWS S3
- Years: 2015-2019 (annual)
- Access: Free, no authentication required
- Estimated size for Ukraine: **~400-500MB**

**Data source:**
- AWS S3: `s3://copernicus-land/global/lcv/`
- Google Earth Engine: `COPERNICUS/Landcover/100m/Proba-V-C3/Global`
- Direct download: https://land.copernicus.eu/global/products/lc

### Land Cover Classes (CGLS-LC100)

```
Value   Class Name              → Humankind Terrain
-----   ----------              ------------------
0       Unknown                 → CityTerrain (default)
20      Shrubs                  → DryGrass
30      Herbaceous vegetation   → Prairie
40      Cultivated              → Prairie (cropland)
50      Urban / built up        → CityTerrain
60      Bare / sparse           → Sterile
70      Snow and ice            → MountainSnow
80      Permanent water         → Ocean/Lake
90      Herbaceous wetland      → CoastalWater
100     Moss and lichen         → RockyField
111     Closed forest (evergreen needle) → Forest
112     Closed forest (evergreen broad)  → Forest
113     Closed forest (deciduous needle) → Forest
114     Closed forest (deciduous broad)  → Forest
115     Closed forest (mixed)   → Forest
116     Closed forest (unknown) → Forest
121     Open forest (evergreen needle)   → WoodLand
122     Open forest (evergreen broad)    → WoodLand
123     Open forest (deciduous needle)   → WoodLand
124     Open forest (deciduous broad)    → WoodLand
125     Open forest (mixed)     → WoodLand
126     Open forest (unknown)   → WoodLand
200     Oceans, seas            → Ocean
```

### Task 9.1: Create Copernicus Land Cover Fetcher

**File:** `landcover_fetcher_copernicus.py` (or update existing)

**Implementation:**
```python
class CopernicusLandCoverFetcher:
    """
    Fetches land cover data from Copernicus CGLS-LC100.
    Uses 100m resolution - much smaller than ESA WorldCover 10m.
    """

    # AWS S3 URL for Copernicus data
    S3_BASE_URL = "https://s3.eu-central-1.amazonaws.com/copernicus-land/lcv/..."

    def __init__(self, bounds: dict, cache_dir: Path):
        self.bounds = bounds
        self.cache_dir = cache_dir

    def _validate_cache(self, path: Path) -> bool:
        """Check if cached file is valid (exists and non-empty)."""
        return path.exists() and path.stat().st_size > 1000

    def fetch_tile(self, tile_id: str) -> Optional[np.ndarray]:
        """Download tile if not cached, skip if already valid."""
        cache_path = self.cache_dir / f"{tile_id}.npy"

        if self._validate_cache(cache_path):
            print(f"  Using cached: {tile_id}")
            return np.load(cache_path)

        # Download from S3...

    def get_landcover_grid(self, width: int, height: int) -> np.ndarray:
        """Get land cover for hex grid."""
        pass
```

**Key improvements:**
1. Cache validation checks file size > 1000 bytes (not just exists)
2. Removes corrupt/incomplete cache files before re-downloading
3. Uses 100m data instead of 10m (100x fewer pixels)

### Task 9.2: Update Terrain Mapper Integration

**File:** `terrain_mapper.py`

Update to use new Copernicus class mapping:
```python
COPERNICUS_TO_TERRAIN = {
    0: 'CityTerrain',      # Unknown → default land
    20: 'DryGrass',        # Shrubs
    30: 'Prairie',         # Herbaceous
    40: 'Prairie',         # Cultivated (cropland)
    50: 'CityTerrain',     # Urban
    60: 'Sterile',         # Bare
    70: 'MountainSnow',    # Snow/ice
    80: 'Ocean',           # Water
    90: 'CoastalWater',    # Wetland
    111: 'Forest',         # Closed forest types
    112: 'Forest',
    113: 'Forest',
    114: 'Forest',
    115: 'Forest',
    116: 'Forest',
    121: 'WoodLand',       # Open forest types
    122: 'WoodLand',
    123: 'WoodLand',
    124: 'WoodLand',
    125: 'WoodLand',
    126: 'WoodLand',
    200: 'Ocean',          # Sea
}
```

### Task 9.3: Clean Up Old Cache

**Action:** Remove corrupt ESA WorldCover cache files
```bash
# Remove 0-byte and small corrupt cache files
find data/landcover_cache -name "*.npy" -size -1k -delete
find data/landcover_cache -name "*_meta.pkl" -size 0 -delete
```

### Task 9.4: Test and Validate

**Validation steps:**
1. Download Copernicus data for Ukraine bounds
2. Generate land cover grid (150×88)
3. Compare distribution with expected Ukraine geography:
   - Majority should be Cultivated (40) - Ukraine is heavily farmed
   - Some Forest (111-126) in Carpathians and Polesia
   - Some Herbaceous (30) in steppes
   - Water (80, 200) for Black Sea and rivers

**Expected storage:**
- Cache files: ~400-500MB total (vs 45GB for ESA 10m)
- Grid cache: ~few KB (150×88 = 13,200 bytes)

### Dependencies

**Python packages (already installed):**
```
rasterio>=1.3.0    # GeoTIFF reading
numpy>=1.24.0      # Array operations
```

**No new packages required** - same as ESA WorldCover fetcher.

### Implementation Status

**Completed:**
- [x] Created `landcover_fetcher_copernicus.py` with CopernicusLandCoverFetcher class
- [x] Cache validation (checks file size, removes corrupt files)
- [x] Uses rasterio windowed reading for efficient partial download
- [x] Cleaned up old corrupt ESA WorldCover cache files

**To test:**
```bash
cd /home/shivers/py/humankind
python landcover_fetcher_copernicus.py
```

This will:
1. Download only the Ukraine region from the global GeoTIFF (~100-200MB vs full 8GB file)
2. Cache it locally in `data/landcover_cache/copernicus_ukraine_region.npy`
3. Generate a 150×88 grid of land cover values
4. Print distribution statistics

### References

- [Copernicus CGLS-LC100 Documentation](https://land.copernicus.eu/global/products/lc)
- [Google Earth Engine Catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_Landcover_100m_Proba-V-C3_Global)
- [Zenodo Direct Download](https://zenodo.org/records/3939050)
- [AWS S3 Access (Digital Earth Africa)](https://docs.digitalearthafrica.org/en/latest/data_specs/CGLS_LULC_specs.html)
