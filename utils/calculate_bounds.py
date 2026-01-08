"""
Calculate optimal map bounds for 6-hex margins.

Given:
- Grid: 150×88 hexes
- Margins: 6 hexes on each side
- Ukraine bounds: 22.0-40.5°E, 44.0-52.5°N

Calculate map bounds that give exactly 6-hex margins.
"""

from .geo_hex_mapper import GeoHexMapper

# Ukraine's actual boundaries
UKRAINE_BOUNDS = {
    "min_lon": 22.0,
    "max_lon": 40.5,
    "min_lat": 44.0,
    "max_lat": 52.5,
}

# Desired margins in hexes
MARGIN_HEXES = 6

# Grid dimensions
GRID_WIDTH = 150
GRID_HEIGHT = 88

print("="*70)
print("CALCULATING MAP BOUNDS FOR 6-HEX MARGINS")
print("="*70)
print()
print(f"Grid dimensions: {GRID_WIDTH}×{GRID_HEIGHT} hexes")
print(f"Desired margin: {MARGIN_HEXES} hexes on each side")
print(f"Ukraine bounds: {UKRAINE_BOUNDS['min_lon']:.1f}-{UKRAINE_BOUNDS['max_lon']:.1f}°E, "
      f"{UKRAINE_BOUNDS['min_lat']:.1f}-{UKRAINE_BOUNDS['max_lat']:.1f}°N")
print()

# Strategy: Start with Ukraine bounds, then expand outward
# We'll create a mapper with Ukraine bounds first to get hex size
test_mapper = GeoHexMapper(
    width=GRID_WIDTH,
    height=GRID_HEIGHT,
    min_lon=UKRAINE_BOUNDS["min_lon"],
    max_lon=UKRAINE_BOUNDS["max_lon"],
    min_lat=UKRAINE_BOUNDS["min_lat"],
    max_lat=UKRAINE_BOUNDS["max_lat"],
)

print(f"With Ukraine-only bounds:")
print(f"  Hex size: {test_mapper.hex_size_km:.2f} km")
print(f"  Hex width: {test_mapper.hex_size_km * 2:.2f} km")
print(f"  Hex height: {test_mapper.hex_size_km * 1.732:.2f} km")
print()

# Calculate how much to expand bounds
# For flat-top hexagons:
# - Horizontal spacing: 0.75 * hex_width
# - Vertical spacing: hex_height

hex_width_km = test_mapper.hex_size_km * 2
hex_height_km = test_mapper.hex_size_km * 1.732

horizontal_spacing_km = hex_width_km * 0.75
vertical_spacing_km = hex_height_km

# Margins in km
margin_horizontal_km = MARGIN_HEXES * horizontal_spacing_km
margin_vertical_km = MARGIN_HEXES * vertical_spacing_km

print(f"Margin dimensions:")
print(f"  Horizontal: {MARGIN_HEXES} hexes × {horizontal_spacing_km:.2f} km = {margin_horizontal_km:.2f} km")
print(f"  Vertical: {MARGIN_HEXES} hexes × {vertical_spacing_km:.2f} km = {margin_vertical_km:.2f} km")
print()

# Convert km to degrees (very approximate)
# At Ukraine's latitude (~48°):
# - 1° longitude ≈ 75 km
# - 1° latitude ≈ 111 km

km_per_lon_deg = 75.0
km_per_lat_deg = 111.0

margin_lon_deg = margin_horizontal_km / km_per_lon_deg
margin_lat_deg = margin_vertical_km / km_per_lat_deg

print(f"Margin in degrees (approximate):")
print(f"  Longitude: {margin_lon_deg:.2f}°")
print(f"  Latitude: {margin_lat_deg:.2f}°")
print()

# Calculate new bounds
new_bounds = {
    "min_lon": UKRAINE_BOUNDS["min_lon"] - margin_lon_deg,
    "max_lon": UKRAINE_BOUNDS["max_lon"] + margin_lon_deg,
    "min_lat": UKRAINE_BOUNDS["min_lat"] - margin_lat_deg,
    "max_lat": UKRAINE_BOUNDS["max_lat"] + margin_lat_deg,
}

print("="*70)
print("RECOMMENDED MAP BOUNDS FOR 6-HEX MARGINS")
print("="*70)
print(f"min_lon: {new_bounds['min_lon']:.1f}")
print(f"max_lon: {new_bounds['max_lon']:.1f}")
print(f"min_lat: {new_bounds['min_lat']:.1f}")
print(f"max_lat: {new_bounds['max_lat']:.1f}")
print()

# Verify with a new mapper
verify_mapper = GeoHexMapper(
    width=GRID_WIDTH,
    height=GRID_HEIGHT,
    **new_bounds
)

# Count hexes in Ukraine
from shapely.geometry import Point
import geopandas as gpd

gdf = gpd.read_file("data/ukraine_raions.geojson")

ukraine_hexes = 0
for row in range(GRID_HEIGHT):
    for col in range(GRID_WIDTH):
        lat, lon = verify_mapper.hex_to_latlon(col, row)
        point = Point(lon, lat)

        for idx, raion in gdf.iterrows():
            if raion.geometry.contains(point):
                ukraine_hexes += 1
                break

coverage_pct = 100 * ukraine_hexes / (GRID_WIDTH * GRID_HEIGHT)

print("="*70)
print("VERIFICATION")
print("="*70)
print(f"Ukraine hexes: {ukraine_hexes} ({coverage_pct:.1f}% of grid)")
print(f"Ocean/buffer hexes: {GRID_WIDTH * GRID_HEIGHT - ukraine_hexes} ({100 - coverage_pct:.1f}%)")
print(f"Hex size: {verify_mapper.hex_size_km:.2f} km")
print(f"Hexes per raion (avg): {ukraine_hexes / 139:.1f}")
print("="*70)
