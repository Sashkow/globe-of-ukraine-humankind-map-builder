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

## Phase 4: Hex Grid Generation (TDD Approach)

### Task 4.1: Create hex grid for Ukraine bounding box
**Goal:** Generate hex grid covering Ukraine geography at maximum detail

**Test:** `test_create_ukraine_hex_grid()` - verify grid coverage and hex count

**Steps:**
1. Write test: grid should be 150×88 hexes (maximum map size)
2. Calculate hex size: ~6.7 km side length to fit Ukraine (1,300×900 km)
3. Position grid to cover Ukraine bbox (22°E-40.5°E, 44°N-52.5°N) centered
4. Generate all 13,200 hexes with proper pointy-top coordinates
5. Test: verify dimensions exactly 150×88

**Expected result:** 150×88 grid with ~9,750 hexes covering Ukraine landmass, ~3,450 for ocean/buffer

### Task 4.2: Assign hexes to raions (core algorithm)
**Goal:** Map each hex to the correct raion (district)

**Test:** `test_hex_to_raion_assignment()` - verify sample hexes are assigned correctly

**Sample test cases:**
- Hex at Kyiv center → specific Kyiv raion
- Hex at Lviv center → specific Lviv raion
- Hex in Black Sea → Ocean territory
- Hex on border between raions → assign to one with larger overlap
- Verify no raion gets 0 hexes

**Algorithm (based on research from 2.1):**
1. Write test with known hex positions
2. For each hex, compute centroid point
3. Check which raion polygon contains centroid (136 raions to check)
4. If no raion contains it, check for intersection and use largest overlap
5. Assign to ocean if no overlap with any raion
6. Track assignment counts for validation

**Validation criterion:** At least 74% of hexes should be assigned to non-ocean territories (~9,750 / 13,200)

### Task 4.3: Validate raion sizes
**Goal:** Ensure each raion has reasonable hex count for gameplay

**Test:** `test_raion_hex_counts()` - verify each raion has 30-150 hexes

**Steps:**
1. Write test with min/max thresholds per raion
2. Count hexes assigned to each of 136 raions
3. Identify outliers (too small or too large)
4. Assert: no raion has < 20 hexes (minimum playable size)
5. Assert: average is ~72 hexes per raion
6. Print statistics table grouped by oblast

**Expected distribution:**
- Small raions: 30-50 hexes
- Medium raions: 50-90 hexes
- Large raions: 90-150 hexes
- Average: ~72 hexes

**Adjustment strategy:** If hex counts are wrong, adjust overall grid density

---

## Phase 5: Map Generation

### Task 5.1: Assign biomes to raions
**Goal:** Map each raion to appropriate climate biome based on parent oblast

**Test:** `test_biome_assignment()` - verify biomes match climate zones

**Reference data (from climate maps):**
- Western oblasts (Lviv, Volyn, etc.): All raions → Temperate (7)
- Central oblasts (Kyiv, Cherkasy, Poltava): All raions → Grassland (3) or Temperate (7)
- Eastern oblasts (Kharkiv, Donetsk, Luhansk, Dnipropetrovsk): All raions → Grassland (3)
- Southern oblasts (Odesa, Mykolaiv, Kherson, Zaporizhzhia): All raions → Mediterranean (4) or Savanna (5)
- Crimea raions: Mediterranean (4)

**Steps:**
1. Write test checking biome assignments for all 136 raions
2. Create oblast → biome mapping, apply to all raions in that oblast
3. Verify against climate zone maps
4. Handle edge cases: Carpathian raions (Ivano-Frankivsk, Zakarpattia) could use Taiga (6) for mountain areas
5. Ensure all 136 raions have valid biome assigned

### Task 5.2: Generate zone texture
**Goal:** Create the PNG texture that maps hex coordinates to territories

**Test:** `test_generate_zone_texture()` - verify texture dimensions and value range

**Steps:**
1. Write test: texture size should match grid dimensions
2. Create numpy array: shape = (height, width), dtype = uint8
3. For each hex (row, col), set pixel value to territory index
4. Verify: max value < 255 (territory limit)
5. Convert to PIL Image, verify can encode as PNG

**Validation:** Render zone texture as colored image, visually verify raion shapes and Ukraine outline

### Task 5.3: Create complete map XML
**Goal:** Generate valid Humankind .hms file with 136 raion territories

**Test:** `test_generate_map_xml()` - parse generated XML and verify structure

**Steps:**
1. Write test that validates XML against expected schema
2. Create Document root with TerrainSave element
3. Add map metadata: Width=150, Height=88
4. Add all required elements: BiomeNames (10 biomes), TerrainTypeNames (15 types)
5. Encode zone texture as base64 PNG
6. Create TerritoryDatabase with 137 territories (136 raions + 1 ocean)
7. For each territory: set ContinentIndex, Biome, IsOcean flag
8. Generate elevation texture (flat/128 for first version)
9. Pretty-print and save as .hms file

**Validation:**
- XML is well-formed
- Territory count exactly 137
- All territory indices 0-136 are used in zone texture
- Max zone texture value is 136

---

## Phase 6: Rendering & Validation

### Task 6.1: Render generated Ukraine map
**Goal:** Visualize the generated map to verify correctness

**Test:** `test_render_ukraine_map()` - verify rendered image shows Ukraine shape

**Steps:**
1. Write test: rendered image should have expected aspect ratio (~1.7:1 for 150×88)
2. Use hex rendering code from Phase 1
3. Color code by raion with different colors per oblast for clarity
4. Generate both hexagonal and simple square renderings
5. Count pixels per raion, verify proportions roughly match real areas

**Validation criteria:**
- Ukraine shape should be recognizable (not mostly ocean!)
- Western border (Polish/Slovak/Hungarian) should be clear
- Black Sea should be visible in south (~26% of map)
- Crimean peninsula should be identifiable
- Internal raion divisions should be visible

### Task 6.2: Create raion label overlay
**Goal:** Add raion/oblast names to rendered map for verification

**Test:** Visual inspection (label key raions and oblast boundaries)

**Steps:**
1. Calculate centroid hex for each of 136 raions
2. Convert hex coordinates to image pixels
3. Draw raion names (may be too many, prioritize major ones)
4. Draw oblast boundaries as thicker lines between raions
5. Export as separate labeled version

**Output:** `ukraine_map_labeled.png` for manual verification

### Task 6.3: Statistical validation
**Goal:** Verify map metrics are reasonable for 136 raions

**Test:** `test_map_statistics()` - check multiple quality metrics

**Metrics to validate:**
- Total hexes: exactly 13,200 (150×88)
- Landmass hexes: 9,000-10,500 (target ~9,750 for 136 raions)
- Each raion: 30-150 hexes
- Average raion size: 65-80 hexes (target ~72)
- Ocean hexes: 2,700-4,200 (~26% of map)
- Hex size: ~6.7 km per hex side
- No raion has 0 hexes
- All 136 raions have at least 20 hexes (playable minimum)

---

## Phase 7: Refinement

### Task 7.1: Adjust hex resolution if needed
**Goal:** Fine-tune for optimal gameplay with 136 raions

**Based on validation results:**
- If raions too small (< 50 hexes avg): Map is already at maximum size (150×88), cannot increase
- If raions too large (> 90 hexes avg): Unlikely given our calculations, but could reduce map if needed
- Target: 65-80 hexes per raion average
- Accept range: 30-150 hexes per raion

**Note:** Since we're using maximum map size, adjustment options are limited. Focus on validating the assignment algorithm.

### Task 7.2: Handle edge cases
**Goal:** Fix any geometric issues with raion assignments

**Potential issues:**
- Crimean peninsula raions might be disconnected from mainland
- Small raions might get too few hexes (<20)
- Coastal raions might have irregular shapes
- Border raions might be assigned incorrectly

**Solutions:**
- Manual adjustments to hex assignments
- Coastline smoothing
- Minimum hex count enforcement

### Task 7.3: Split Crimea into Geographic-Historical Regions
**Goal:** Divide Crimea into 6 territories based on natural geography AND historical Crimean Tatar population divisions

**Background:** Rather than using modern administrative divisions for Crimea, use historically and geographically meaningful regions that align with the traditional Crimean Tatar subgroups:

**6 Crimean Territories:**
1. **Western Steppe** (Tarkhankut-Kezlev Nogay region)
   - Northwestern peninsula area around Yevpatoria
   - Flat steppe terrain, historically Nogay Tatar population

2. **Northern Steppe** (Perekop-Dzhankoy Nogay region)
   - Northern Crimea connecting to mainland via Perekop isthmus
   - Steppe terrain, gateway to Crimea

3. **Kerch Peninsula** (Eastern Nogay region)
   - Eastern peninsula toward Kerch Strait
   - Steppe terrain, historically Nogay Tatar area

4. **Mountain Region** (Tatlar/Mountain Tatars)
   - Central mountainous area (Crimean Mountains)
   - Home of the Mountain Tatars (Tatlar)

5. **Southern Coast** (Yalıboylular)
   - Narrow coastal strip from Sevastopol to Feodosia
   - Mediterranean climate, historically Yalıboylular (coastal Tatars)

6. **Sevastopol** (Special city status)
   - Historic naval port city
   - Distinct strategic and cultural significance

**Target hex counts:** 25-50 hexes per Crimean territory (playable size)

**Implementation:**
- Create custom polygon boundaries for these 6 regions
- Override standard raion assignment for Crimea hexes
- Assign appropriate biomes:
  - Steppe regions (1, 2, 3): Mediterranean (4) or Grassland (3)
  - Mountain Region (4): Taiga (6) or Mediterranean (4)
  - Southern Coast (5): Mediterranean (4)
  - Sevastopol (6): Mediterranean (4)

### Task 7.4: Add optional features
**Goal:** Enhance map if time permits

**Optional additions:**
- Elevation data (Carpathian Mountains, Crimean Mountains)
- Major rivers (Dnipro, Dniester)
- Strategic resources based on real geology
- Starting positions for empires

---

## Phase 8: Documentation & Delivery

### Task 8.1: Create user guide
**Goal:** Document how to use the map in Humankind

**Contents:**
- How to install the map
- What each raion represents (136 districts organized by 27 oblasts)
- Recommended game settings (8-10 empires for 136 territories)
- Known limitations

### Task 8.2: Create development documentation
**Goal:** Explain the code for future improvements

**Contents:**
- Architecture overview
- Key algorithms used
- How to adjust parameters
- How to generate maps for other regions

### Task 8.3: Package map for distribution
**Goal:** Create game-ready map file

**Steps:**
1. Generate final .hms file
2. Create Descriptor.hmd with metadata
3. Package as .hmap (ZIP archive)
4. Test: verify file can be unzipped and structure is correct

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

**Must Have:**
✓ Map loads in Humankind game
✓ 136 Ukrainian raions (districts) are territories
✓ Geographic shape of Ukraine is recognizable
✓ Each raion has 20-150 hexes (target: 30-120)
✓ Average raion size: 65-80 hexes
✓ Biomes match climate zones (based on parent oblast)
✓ Rendered map shows Ukraine clearly with <30% ocean
✓ All 136 raions have at least some hexes (no 0-hex territories)
✓ Map uses full 150×88 maximum size efficiently

**Nice to Have:**
- Elevation data for mountains (Carpathians, Crimean ranges)
- Major rivers (Dnipro, Dniester, Southern Bug)
- Optimized hex sizes for all raions
- Starting positions for 8-10 empires
- Historical/strategic resources based on real Ukrainian geography

**Failure Conditions:**
✗ Map shows mostly ocean (>50% ocean hexes)
✗ Raions not geographically accurate
✗ Any raion has 0 hexes
✗ More than 5 raions have <20 hexes
✗ Ukraine shape not recognizable
✗ Map doesn't load in game
✗ Territory count ≠ 137 (136 raions + 1 ocean)

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
