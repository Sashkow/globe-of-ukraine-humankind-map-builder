"""
Data fetchers for geographic data (elevation, land cover, etc.)

These modules download and cache remote geospatial data:
- srtm_elevation.py: SRTM elevation data (30m/90m resolution)
- landcover_fetcher_copernicus.py: Copernicus CGLS-LC100 land cover (100m)
- landcover_fetcher.py: ESA WorldCover land cover (10m) - deprecated, use Copernicus
"""

from .srtm_elevation import SRTMElevationFetcher
from .landcover_fetcher_copernicus import CopernicusLandCoverFetcher, CopernicusLandCoverClass

__all__ = [
    'SRTMElevationFetcher',
    'CopernicusLandCoverFetcher',
    'CopernicusLandCoverClass',
]
