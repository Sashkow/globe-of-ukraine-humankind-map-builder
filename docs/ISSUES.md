# Known Issues - Ukraine Humankind Map

This document tracks issues identified in the map generation based on in-game testing (screenshots from 2025-12-25).

## Rendering Issues

### 1. Mountains not rendered properly

**Status:** FIXED (v0.1.16)
**Priority:** High

**Description:**
Mountains appear as flat cliff-like terrain rather than proper 3D mountain visuals in-game. The elevation data is present (visible in editor as topographic contour lines), but the game doesn't render them as proper mountain graphics.

**Observed in:**
- `Screenshot from 2025-12-25 00-35-31.png` - Mountains appear as stepped cliffs/plateaus
- `Screenshot from 2025-12-25 00-37-51.png` - Terrain shows elevation but lacks mountain visual style

**Fix Applied (2025-12-25):**

1. **Enabled `UseProceduralMountainChains=true`** in `incremental_map_builder.py`:
   - Added `_enable_procedural_mountains()` method that changes the flag from `false` to `true`
   - This tells the game to automatically generate mountain chain visuals

2. **Verified terrain type encoding** in `terrain_mapper.py`:
   - `Mountain` (index 5) for high elevation (level 7-9) - CORRECT
   - `MountainSnow` (index 6) for very high elevation (level 10+) - CORRECT
   - Indices match the template file

3. **Analyzed corrected mountains file:**
   - The manually-corrected file had `UseProceduralMountainChains=false`
   - Manual mountain painting was done in the editor
   - Our procedural approach should achieve similar results automatically

**If still not working after testing:**
- Consider manual mountain chain generation algorithm for Carpathians and Crimean Mountains
- Reference file: `~/.steam/.../Humankind/Maps/Ukraine_v0.1.11_with corrected mountains.hmap`

---

### 2. Rivers on adjacent tiles are rendered fragmented

**Status:** Fix applied (v0.1.17) - needs testing
**Priority:** High

**Description:**
Rivers don't connect smoothly between hexagonal tiles. They appear as disconnected segments at tile boundaries, breaking visual continuity.

**Observed in:**
- `Screenshot from 2025-12-25 00-35-52.png` - River segments don't connect at hex edges
- `Screenshot from 2025-12-25 00-39-40.png` - Fragmented river in central map area
- `Screenshot from 2025-12-25 00-40-23.png` - Rivers visible but disjointed in gameplay view
- `Screenshot from 2025-12-25 00-40-42.png` - Same fragmentation issue visible

**Root Cause Identified (2025-12-25):**
Analysis of working Earth map revealed the B channel (exit_edge) encoding was wrong:

- **Wrong understanding:** exit_edge should point to the next river hex in the segment
- **Correct understanding:** exit_edge represents **visual downstream flow direction**

In Earth map: 78% of exit_edges point to NON-river hexes (flow toward sea)
In Ukraine v0.1.16: 94% pointed to river hexes (wrong - following segment path)

**Fix Applied (v0.1.17):**

1. Modified `river_mapper.py` `_trace_river_segments()` to calculate flow direction
2. Added `_calculate_flow_direction()` method that:
   - Uses elevation data to determine downstream direction
   - Points exit_edge toward lowest-elevation neighbor (toward sea)
   - Falls back to geographic heuristic (SE/SW for Ukrainian rivers)
3. Updated `create_river_texture()` to accept elevation_map parameter
4. Updated `incremental_map_builder.py` to pass elevation data

**Results:**
- Exit→river: 94% → 55% (closer to Earth's 22%)
- Exit edges now favor SE (83) and SW (52) - southward flow toward Black Sea

**Edge direction reference:**
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

---

## Validation Warnings (from Map Editor)

### 3. Territory size warnings

**Status:** Informational
**Priority:** Low

**Observed messages:**
- "Territory too small" - Some territories have fewer than ~10 tiles
- "Territory not valid" - Territory validation failures

**Screenshots:**
- `Screenshot from 2025-12-25 00-37-51.png`
- `Screenshot from 2025-12-25 00-38-02.png`
- `Screenshot from 2025-12-25 00-38-21.png`

**Notes:**
Territory constraints from game documentation:
- Minimum size: ~10 tiles
- Maximum size: ~199 tiles
- Ocean territories: must be >=50% water
- Land territories: must be >=50% land

---

### 4. Spawn points too close to each other

**Status:** Informational
**Priority:** Low

**Observed in:**
- `Screenshot from 2025-12-25 00-39-40.png` - Warning about spawn point proximity

**Notes:**
Spawn points should have sufficient distance for fair gameplay. Consider spacing them across different regions of Ukraine.

---

## Feature Requests

### 5. Implement automated mountain chain generation

**Priority:** Medium

**Description:**
Rather than relying solely on `UseProceduralMountainChains=true` (which may produce generic results), implement custom mountain chain logic that:

1. Identifies high-elevation regions from SRTM data
2. Creates connected mountain chains following real topography
3. Applies appropriate terrain types (Mountain, MountainSnow)
4. Optionally adds mountain landmarks for named ranges

**Reference implementation:**
The manually-corrected map file shows how mountain chains should look:
```
Ukraine_v0.1.11_with corrected mountains.hmap
```

This can be compared against the generated version to understand what manual corrections were made.

---

## Screenshot Index

| Screenshot | Description | Issues Shown |
|------------|-------------|--------------|
| 00-35-04.png | Editor view - terrain contours | Mountains as contours only |
| 00-35-31.png | In-game view - cliffs | Mountains render as cliffs |
| 00-35-52.png | Editor view - rivers | Fragmented rivers |
| 00-37-24.png | Editor with dialog | River fragmentation |
| 00-37-51.png | Editor - territory warning | Territory size error |
| 00-38-02.png | Editor - validation | Territory validation |
| 00-38-21.png | Editor - adjacency | Territory adjacency |
| 00-39-40.png | Editor - spawn warning | Spawn proximity + rivers |
| 00-40-23.png | In-game - forest/rivers | Fragmented rivers |
| 00-40-42.png | In-game view | River fragmentation |

---

*Last updated: 2025-12-25*
