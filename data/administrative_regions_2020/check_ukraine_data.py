#!/usr/bin/env python3
"""
Quick script to check Ukraine admin2 data properties.
"""
import geopandas as gpd

# Load the data
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, "ukr_admin2.geojson")
print(f"Loading {data_path}...")
gdf = gpd.read_file(data_path)

print(f"\n{'='*60}")
print("COORDINATE REFERENCE SYSTEM (CRS)")
print(f"{'='*60}")
print(f"CRS: {gdf.crs}")
print(f"EPSG Code: {gdf.crs.to_epsg() if gdf.crs else 'Unknown'}")

print(f"\n{'='*60}")
print("BASIC STATISTICS")
print(f"{'='*60}")
print(f"Number of features (raions): {len(gdf)}")
print(f"Number of columns: {len(gdf.columns)}")

print(f"\n{'='*60}")
print("COLUMN NAMES")
print(f"{'='*60}")
for i, col in enumerate(gdf.columns, 1):
    print(f"{i:2d}. {col}")

print(f"\n{'='*60}")
print("SAMPLE DATA (first raion)")
print(f"{'='*60}")
for col in gdf.columns:
    if col != 'geometry':
        print(f"{col:20s}: {gdf[col].iloc[0]}")

print(f"\n{'='*60}")
print("GEOMETRY STATISTICS")
print(f"{'='*60}")
print(f"Geometry type(s): {gdf.geometry.type.unique()}")
print(f"Valid geometries: {gdf.geometry.is_valid.sum()}/{len(gdf)}")
print(f"Empty geometries: {gdf.geometry.is_empty.sum()}/{len(gdf)}")

print(f"\n{'='*60}")
print("BOUNDING BOX")
print(f"{'='*60}")
minx, miny, maxx, maxy = gdf.total_bounds
print(f"Longitude: {minx:.4f}° to {maxx:.4f}°")
print(f"Latitude:  {miny:.4f}° to {maxy:.4f}°")

print(f"\n{'='*60}")
print("COMPATIBILITY CHECK")
print(f"{'='*60}")
print(f"✓ CRS is WGS84 (EPSG:4326): {gdf.crs.to_epsg() == 4326}")
print(f"✓ Expected ~136 raions: {130 <= len(gdf) <= 140} ({len(gdf)} found)")
print(f"✓ All geometries valid: {gdf.geometry.is_valid.all()}")
print(f"✓ No empty geometries: {not gdf.geometry.is_empty.any()}")

# Check if within Ukraine bounds
ukraine_ok = (
    minx >= 22.0 - 1.0 and
    maxx <= 40.5 + 1.0 and
    miny >= 44.0 - 1.0 and
    maxy <= 52.5 + 1.0
)
print(f"✓ Within Ukraine bounds: {ukraine_ok}")

print(f"\n{'='*60}")
print("CONCLUSION")
print(f"{'='*60}")
if gdf.crs.to_epsg() == 4326:
    print("✓ Data uses WGS84 (EPSG:4326) - COMPATIBLE with Phase 2!")
    print("  Phase 2 used WGS84 for lat/lon and converts to UTM 36N for projection.")
else:
    print("⚠ Data uses different CRS - may need conversion")
