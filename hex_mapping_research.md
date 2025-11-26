# Hex-to-Geography Mapping Research

## Goal
Find established methods for mapping real-world geography (lat/lon coordinates and polygon boundaries) to hexagonal grids for game maps.

---

## Technique 1: Centroid-Based Assignment (Simple Point-in-Polygon)

### Description
Each hex has a center point. Convert that center to lat/lon and check which geographic polygon (e.g., raion boundary) contains it.

### Algorithm
1. Generate hex grid in offset coordinates (col, row)
2. Calculate center of each hex in pixel/world coordinates
3. Convert hex center to geographic coordinates (lat, lon)
4. For each hex, check which polygon contains its centroid
5. Assign hex to that polygon's territory

### Pros
- Simple to implement
- Deterministic (each hex assigned to exactly one territory)
- Works well when hexes are much smaller than territories
- No ambiguity in assignment

### Cons
- May miss small territories if hex centers don't fall within them
- Doesn't account for hex area coverage - a hex may overlap multiple territories but be assigned to only one
- Can produce "jaggy" borders that don't follow natural boundaries well

### Best For
Our Ukraine map use case where:
- 136 raions (large polygons)
- Each raion target: 50-90 hexes
- Hexes are small relative to raions (~6.7 km side length)

---

## Technique 2: Area-Weighted Assignment

### Description
For each hex, calculate how much of its area overlaps with each territory polygon. Assign to the territory with largest overlap.

### Algorithm
1. Generate hex grid
2. Calculate hex polygon vertices
3. For each hex:
   - Compute intersection area with each territory polygon
   - Assign to territory with maximum intersection area
4. Handle edge case: if no intersection, use centroid fallback

### Pros
- More accurate representation of geographic boundaries
- Handles small territories better
- Smoother borders that follow real geography
- Accounts for hexes that straddle boundaries

### Cons
- Computationally expensive (polygon intersection for every hex)
- Requires robust geometry library (Shapely)
- Still deterministic but more complex

### Implementation Note
Use Shapely library:
```python
from shapely.geometry import Polygon, Point

hex_polygon = Polygon(hex_corners)
for territory_polygon in territories:
    intersection_area = hex_polygon.intersection(territory_polygon).area
```

### Best For
- High-precision maps
- When computational cost is acceptable
- Situations with many small territories

---

## Technique 3: H3 Hierarchical Hexagonal Indexing (Uber H3)

### Description
H3 is a geospatial indexing system that divides Earth into hexagons at multiple resolutions. Instead of creating custom hex grids, use H3's pre-defined global grid.

### Algorithm
1. Choose H3 resolution level (0-15, where higher = smaller hexes)
2. For each territory polygon:
   - Use `h3.polyfill()` to get all H3 hexagons within polygon
   - Map H3 index to territory
3. Convert H3 hexagons to game grid coordinates

### Pros
- Industry-standard system (used by Uber, mapping companies)
- Optimized spatial indexing
- Multi-resolution support
- Global coordinate system

### Cons
- **Not compatible with Humankind's fixed rectangular grid**
- H3 uses different coordinate system than offset grid
- Would require complex translation layer
- Hexagons don't align with game's existing maps
- Overkill for a single fixed-size map

### Best For
- Web mapping applications
- Multi-resolution zoom systems
- Global-scale applications
- **NOT suitable for Humankind map generation**

---

## Technique 4: Rasterization + Sampling

### Description
Rasterize territory polygons to a high-resolution bitmap, then sample at hex centers.

### Algorithm
1. Create high-res raster (e.g., 4000×4000 pixels) covering map bounds
2. Rasterize each territory polygon to unique color/ID
3. For each hex center:
   - Convert to raster coordinates
   - Sample pixel value
   - Assign hex to corresponding territory
4. Optional: multi-sample (check multiple points per hex) for better accuracy

### Pros
- Very fast lookups (O(1) per hex)
- Easy to implement with PIL/Pillow or rasterio
- Can handle complex polygons efficiently
- Good for large numbers of hexes

### Cons
- Requires choosing raster resolution (trade-off: memory vs accuracy)
- Potential precision loss at boundaries
- Less accurate than vector methods
- Memory intensive for very high resolutions

### Best For
- Very large hex grids (>20,000 hexes)
- Performance-critical applications
- When boundaries don't need to be perfectly precise

---

## Technique 5: Distance-Based Assignment (Voronoi-like)

### Description
Assign each hex to the nearest territory centroid or reference point.

### Algorithm
1. Calculate centroid of each territory polygon
2. For each hex:
   - Calculate distance to all territory centroids
   - Assign to nearest territory

### Pros
- Simple and fast
- Works when polygon data is unavailable

### Cons
- **Terrible for geographic accuracy**
- Ignores actual boundaries completely
- Will assign hexes to wrong territories
- Not suitable for realistic maps

### Best For
- **NOT recommended for our use case**
- Only useful when actual boundaries are unknown

---

## Recommended Approach for Ukraine Map

### Primary Method: Centroid-Based (Technique 1)
**Rationale:**
- Hexes (~6.7 km) are much smaller than raions (~60 km average width)
- Each raion should get 50-90 hexes, so centroid sampling is sufficient
- Simple, deterministic, and fast
- Proven approach used by Civilization and Humankind modding community

### Fallback for Edge Cases: Area-Weighted (Technique 2)
**When to use:**
- If any raion gets 0 hexes (none contain hex centers)
- For very small raions or narrow coastal areas
- As validation check

### Implementation Strategy
1. Start with centroid-based assignment
2. Validate: check that all 136 raions have at least 20 hexes
3. If any raions have < 20 hexes:
   - For those raions only, switch to area-weighted method
   - Or manually adjust grid positioning
4. Run tests to verify total hex distribution

### Coordinate Systems to Use

**Geographic (Input):**
- WGS84 lat/lon (EPSG:4326)
- Ukraine bounds: 22°E-40.5°E, 44°N-52.5°N

**Projected (Calculations):**
- Use UTM Zone 36N (EPSG:32636) for Ukraine
- Or Web Mercator (EPSG:3857) for simpler calculations
- Better for distance/area calculations than lat/lon

**Game Grid (Output):**
- Offset coordinates (col, row)
- 150 columns × 88 rows
- Pointy-top hexagons
- Odd-q column offset (odd columns shifted down by hex_height/2)

---

## Libraries and Tools

### Python Libraries
```python
# Geometry operations
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

# Geographic projections
import pyproj
from pyproj import Transformer

# GIS data loading
import geopandas as gpd

# Array operations
import numpy as np
```

### Coordinate Transformation
```python
# Transform from WGS84 (lat/lon) to UTM 36N
transformer = Transformer.from_crs("EPSG:4326", "EPSG:32636", always_xy=True)
x_utm, y_utm = transformer.transform(lon, lat)
```

---

## Test Cases for Validation

### Known City Locations (for testing)
```python
KNOWN_CITIES = {
    "Kyiv": {"lat": 50.4501, "lon": 30.5234, "raion": "Kyiv City"},
    "Lviv": {"lat": 49.8397, "lon": 24.0297, "raion": "Lviv City"},
    "Odesa": {"lat": 46.4825, "lon": 30.7233, "raion": "Odesa City"},
    "Kharkiv": {"lat": 49.9935, "lon": 36.2304, "raion": "Kharkiv City"},
    "Dnipro": {"lat": 48.4647, "lon": 35.0462, "raion": "Dnipro City"},
}
```

### Validation Tests
1. Verify major cities are in correct raions
2. Verify all 136 raions have hexes assigned
3. Verify hex count distribution (min >= 20, avg ~72)
4. Verify total land hexes ≈ 9,750 (74% of 13,200)
5. Visual inspection: rendered map shows Ukraine shape

---

## References

1. **Red Blob Games - Hexagonal Grids**: https://www.redblobgames.com/grids/hexagons/
   - Excellent resource for hex coordinate systems
   - Covers offset, cube, and axial coordinates
   - Algorithms for hex-to-pixel conversion

2. **Humankind Modding Community** (mod.io forums)
   - How existing map mods handle geography
   - Zone texture encoding format

3. **Shapely Documentation**: https://shapely.readthedocs.io/
   - Point-in-polygon tests
   - Polygon intersection calculations

4. **Civilization VI Map Scripts**
   - Similar hex-to-geography problem
   - Often use rasterization approach

---

## Decision Matrix

| Technique | Accuracy | Speed | Complexity | Suitable? |
|-----------|----------|-------|------------|-----------|
| Centroid-Based | Good | Very Fast | Low | ✅ **YES - Primary** |
| Area-Weighted | Excellent | Slow | Medium | ✅ YES - Fallback |
| H3 System | N/A | Fast | High | ❌ NO - Incompatible |
| Rasterization | Good | Fast | Medium | ⚠️ Maybe - If needed |
| Distance-Based | Poor | Fast | Low | ❌ NO - Inaccurate |

---

## Conclusion

**Recommended Implementation:**
1. Use **Centroid-Based Assignment** (Technique 1) as primary method
2. Implement **Area-Weighted Assignment** (Technique 2) as fallback for edge cases
3. Use Shapely for geometry operations
4. Project to UTM 36N for accurate distance calculations
5. Validate with known city locations and hex count statistics

This approach balances simplicity, accuracy, and performance for the Ukraine map generation task.
