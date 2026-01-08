"""
Calculate optimal map bounds for Ukraine + margins.

This script calculates the proper geographic bounds (lat/lon) that will
give us a 150×88 hex grid with approximately 6 hexes of margin around Ukraine.

The calculation is done entirely in projected space (UTM 36N) to avoid
distortion issues with lat/lon coordinates.
"""

import geopandas as gpd
import numpy as np
from pyproj import Transformer

# Grid dimensions
GRID_WIDTH = 150
GRID_HEIGHT = 88

# Target margin (in hexes)
TARGET_MARGIN_HEXES = 6

# Load Ukraine data
gdf = gpd.read_file('data/ukraine_raions.geojson')
gdf_utm = gdf.to_crs("EPSG:32636")  # UTM Zone 36N

# Get Ukraine bounds in UTM
ukraine_bounds_utm = gdf_utm.total_bounds
ukraine_min_x, ukraine_min_y, ukraine_max_x, ukraine_max_y = ukraine_bounds_utm

ukraine_width_m = ukraine_max_x - ukraine_min_x
ukraine_height_m = ukraine_max_y - ukraine_min_y

print("=" * 70)
print("CALCULATING OPTIMAL BOUNDS FOR UKRAINE HEX GRID")
print("=" * 70)
print()
print(f"Grid dimensions: {GRID_WIDTH}×{GRID_HEIGHT}")
print(f"Target margin: {TARGET_MARGIN_HEXES} hexes on each side")
print()
print("Ukraine extent in UTM 36N:")
print(f"  X: {ukraine_min_x:.0f} to {ukraine_max_x:.0f} ({ukraine_width_m/1000:.1f} km)")
print(f"  Y: {ukraine_min_y:.0f} to {ukraine_max_y:.0f} ({ukraine_height_m/1000:.1f} km)")
print()

# Calculate hex size needed to fit Ukraine in the grid with margins
# Available grid space = total - 2*margin on each side
available_width_hexes = GRID_WIDTH - 2 * TARGET_MARGIN_HEXES
available_height_hexes = GRID_HEIGHT - 2 * TARGET_MARGIN_HEXES

print(f"Available grid space (excluding margins):")
print(f"  Width: {available_width_hexes} hexes")
print(f"  Height: {available_height_hexes} hexes")
print()

# For flat-top hexagons:
# - Grid width = (width - 0.25) * 2 * hex_size
# - Grid height ≈ (height + 0.5) * sqrt(3) * hex_size

hex_size_from_width = ukraine_width_m / ((available_width_hexes - 0.25) * 2)
hex_size_from_height = ukraine_height_m / ((available_height_hexes + 0.5) * np.sqrt(3))

print("Hex size to fit Ukraine in available space:")
print(f"  From width:  {hex_size_from_width/1000:.2f} km")
print(f"  From height: {hex_size_from_height/1000:.2f} km")

hex_size_m = min(hex_size_from_width, hex_size_from_height)
print(f"  Using: {hex_size_m/1000:.2f} km (minimum)")
print()

# Now calculate the full grid extent in UTM
full_grid_width_m = (GRID_WIDTH - 0.25) * 2 * hex_size_m
full_grid_height_m = (GRID_HEIGHT + 0.5) * np.sqrt(3) * hex_size_m

print("Full grid extent:")
print(f"  Width:  {full_grid_width_m/1000:.1f} km")
print(f"  Height: {full_grid_height_m/1000:.1f} km")
print()

# Center the grid on Ukraine's center
ukraine_center_x = (ukraine_min_x + ukraine_max_x) / 2
ukraine_center_y = (ukraine_min_y + ukraine_max_y) / 2

grid_min_x = ukraine_center_x - full_grid_width_m / 2
grid_max_x = ukraine_center_x + full_grid_width_m / 2
grid_min_y = ukraine_center_y - full_grid_height_m / 2
grid_max_y = ukraine_center_y + full_grid_height_m / 2

print("Grid bounds in UTM (centered on Ukraine):")
print(f"  X: {grid_min_x:.0f} to {grid_max_x:.0f}")
print(f"  Y: {grid_min_y:.0f} to {grid_max_y:.0f}")
print()

# Calculate actual margins
margin_west_m = ukraine_min_x - grid_min_x
margin_east_m = grid_max_x - ukraine_max_x
margin_south_m = ukraine_min_y - grid_min_y
margin_north_m = grid_max_y - ukraine_max_y

print("Actual margins:")
print(f"  West:  {margin_west_m/1000:.1f} km ({margin_west_m / (hex_size_m * 2 * 0.75):.1f} hexes)")
print(f"  East:  {margin_east_m/1000:.1f} km ({margin_east_m / (hex_size_m * 2 * 0.75):.1f} hexes)")
print(f"  South: {margin_south_m/1000:.1f} km ({margin_south_m / (hex_size_m * np.sqrt(3)):.1f} hexes)")
print(f"  North: {margin_north_m/1000:.1f} km ({margin_north_m / (hex_size_m * np.sqrt(3)):.1f} hexes)")
print()

# Convert to WGS84
transformer = Transformer.from_crs("EPSG:32636", "EPSG:4326", always_xy=True)

sw_lon, sw_lat = transformer.transform(grid_min_x, grid_min_y)
ne_lon, ne_lat = transformer.transform(grid_max_x, grid_max_y)
nw_lon, nw_lat = transformer.transform(grid_min_x, grid_max_y)
se_lon, se_lat = transformer.transform(grid_max_x, grid_min_y)

print("Grid bounds in WGS84:")
print(f"  SW corner: {sw_lat:.2f}°N, {sw_lon:.2f}°E")
print(f"  NE corner: {ne_lat:.2f}°N, {ne_lon:.2f}°E")
print(f"  NW corner: {nw_lat:.2f}°N, {nw_lon:.2f}°E")
print(f"  SE corner: {se_lat:.2f}°N, {se_lon:.2f}°E")
print()

# Use the min/max of all corners
min_lon = min(sw_lon, nw_lon)
max_lon = max(se_lon, ne_lon)
min_lat = min(sw_lat, se_lat)
max_lat = max(nw_lat, ne_lat)

print("=" * 70)
print("RECOMMENDED CONFIG.YAML VALUES:")
print("=" * 70)
print(f"  min_lon: {min_lon:.1f}")
print(f"  max_lon: {max_lon:.1f}")
print(f"  min_lat: {min_lat:.1f}")
print(f"  max_lat: {max_lat:.1f}")
print("=" * 70)
