"""
Biome assignment system for mapping raions to climate biomes.

This module handles assigning appropriate Humankind biomes to Ukrainian
raions based on their geographic location and parent oblast.
"""

from typing import Dict
import geopandas as gpd


class BiomeMapper:
    """
    Assigns biomes to raions based on geographic location.

    Uses oblast-level climate zones to determine appropriate biomes
    for each raion.
    """

    # Humankind biome indices
    BIOME_ARCTIC = 0
    BIOME_BADLANDS = 1
    BIOME_DESERT = 2
    BIOME_GRASSLAND = 3
    BIOME_MEDITERRANEAN = 4
    BIOME_SAVANNA = 5
    BIOME_TAIGA = 6
    BIOME_TEMPERATE = 7
    BIOME_TROPICAL = 8
    BIOME_TUNDRA = 9

    # Oblast to biome mapping based on Ukrainian climate zones
    # Includes multiple spelling variants (Latin transliteration, Ukrainian, etc.)
    OBLAST_BIOME_MAPPING = {
        # Western Ukraine - Forested, temperate climate
        "Lviv": BIOME_TEMPERATE,
        "L'vivs'ka": BIOME_TEMPERATE,
        "Lvivska": BIOME_TEMPERATE,
        "Volyn": BIOME_TEMPERATE,
        "Volynska": BIOME_TEMPERATE,
        "Rivne": BIOME_TEMPERATE,
        "Rivnens'ka": BIOME_TEMPERATE,
        "Rivnenska": BIOME_TEMPERATE,
        "Ternopil": BIOME_TEMPERATE,
        "Ternopil's'ka": BIOME_TEMPERATE,
        "Ternopilska": BIOME_TEMPERATE,
        "Khmelnytskyi": BIOME_TEMPERATE,
        "Khmel'nyts'ka": BIOME_TEMPERATE,
        "Khmelnytska": BIOME_TEMPERATE,

        # Carpathian oblasts - Mountain forests
        "Ivano-Frankivsk": BIOME_TEMPERATE,
        "Ivano-Frankivs'ka": BIOME_TEMPERATE,
        "Ivano-Frankivska": BIOME_TEMPERATE,
        "Zakarpattia": BIOME_TEMPERATE,
        "Zakarpats'ka": BIOME_TEMPERATE,
        "Zakarpatska": BIOME_TEMPERATE,
        "Chernivtsi": BIOME_TEMPERATE,
        "Chernivets'ka": BIOME_TEMPERATE,
        "Chernivetska": BIOME_TEMPERATE,

        # Central Ukraine - Black earth steppe, grasslands
        "Kyiv": BIOME_GRASSLAND,
        "Kyivs'ka": BIOME_GRASSLAND,
        "Kyivska": BIOME_GRASSLAND,
        "Kiev": BIOME_GRASSLAND,
        "Cherkasy": BIOME_GRASSLAND,
        "Cherkas'ka": BIOME_GRASSLAND,
        "Cherkaska": BIOME_GRASSLAND,
        "Poltava": BIOME_GRASSLAND,
        "Poltavs'ka": BIOME_GRASSLAND,
        "Poltavska": BIOME_GRASSLAND,
        "Vinnytsia": BIOME_GRASSLAND,
        "Vinnyts'ka": BIOME_GRASSLAND,
        "Vinnytska": BIOME_GRASSLAND,
        "Kirovohrad": BIOME_GRASSLAND,
        "Kirovohrads'ka": BIOME_GRASSLAND,
        "Kirovohradska": BIOME_GRASSLAND,
        "Kropyvnytskyi": BIOME_GRASSLAND,

        # Northern Ukraine - Mixed forests and grasslands
        "Chernihiv": BIOME_TEMPERATE,
        "Chernihivs'ka": BIOME_TEMPERATE,
        "Chernihivska": BIOME_TEMPERATE,
        "Sumy": BIOME_TEMPERATE,
        "Sums'ka": BIOME_TEMPERATE,
        "Sumska": BIOME_TEMPERATE,
        "Zhytomyr": BIOME_TEMPERATE,
        "Zhytomyrs'ka": BIOME_TEMPERATE,
        "Zhytomyrska": BIOME_TEMPERATE,

        # Eastern Ukraine - Steppe regions
        "Kharkiv": BIOME_GRASSLAND,
        "Kharkivs'ka": BIOME_GRASSLAND,
        "Kharkivska": BIOME_GRASSLAND,
        "Donetsk": BIOME_GRASSLAND,
        "Donets'ka": BIOME_GRASSLAND,
        "Donetska": BIOME_GRASSLAND,
        "Luhansk": BIOME_GRASSLAND,
        "Luhans'ka": BIOME_GRASSLAND,
        "Luhanska": BIOME_GRASSLAND,
        "Dnipropetrovsk": BIOME_GRASSLAND,
        "Dnipropetrovs'ka": BIOME_GRASSLAND,
        "Dnipropetrovska": BIOME_GRASSLAND,
        "Dnipro": BIOME_GRASSLAND,

        # Southern Ukraine - Coastal, Mediterranean-like climate
        "Odesa": BIOME_MEDITERRANEAN,
        "Odes'ka": BIOME_MEDITERRANEAN,
        "Odeska": BIOME_MEDITERRANEAN,
        "Mykolaiv": BIOME_MEDITERRANEAN,
        "Mykolaivs'ka": BIOME_MEDITERRANEAN,
        "Mykolaivska": BIOME_MEDITERRANEAN,
        "Kherson": BIOME_MEDITERRANEAN,
        "Khersons'ka": BIOME_MEDITERRANEAN,
        "Khersonska": BIOME_MEDITERRANEAN,
        "Zaporizhzhia": BIOME_GRASSLAND,  # Transitional steppe
        "Zaporiz'ka": BIOME_GRASSLAND,
        "Zaporizka": BIOME_GRASSLAND,

        # Crimea - Mediterranean coastal climate
        "Crimea": BIOME_MEDITERRANEAN,
        "Autonomous Republic of Crimea": BIOME_MEDITERRANEAN,
        "Avtonomna Respublika Krym": BIOME_MEDITERRANEAN,
        "Sevastopol": BIOME_MEDITERRANEAN,
        "Sevastopol'": BIOME_MEDITERRANEAN,
    }

    def __init__(self, raion_gdf: gpd.GeoDataFrame, oblast_field: str):
        """
        Initialize biome mapper.

        Args:
            raion_gdf: GeoDataFrame with raion geometries
            oblast_field: Column name containing oblast names
        """
        self.raion_gdf = raion_gdf
        self.oblast_field = oblast_field
        self.raion_biomes: Dict[int, int] = {}

    def assign_biomes(self) -> Dict[int, int]:
        """
        Assign biomes to all raions based on their oblast.

        Returns:
            Dictionary mapping raion_index -> biome_index
        """
        print(f"\nAssigning biomes to {len(self.raion_gdf)} raions...")

        self.raion_biomes = {}
        unmatched_oblasts = set()

        for idx, raion in self.raion_gdf.iterrows():
            oblast_name = raion[self.oblast_field]

            # Try to find biome for this oblast
            biome = self._get_biome_for_oblast(oblast_name)

            if biome is not None:
                self.raion_biomes[idx] = biome
            else:
                # Default to grassland if oblast not found
                self.raion_biomes[idx] = self.BIOME_GRASSLAND
                unmatched_oblasts.add(oblast_name)

        if unmatched_oblasts:
            print(f"\n⚠ Warning: {len(unmatched_oblasts)} oblasts not in mapping, using default (Grassland):")
            for oblast in sorted(unmatched_oblasts):
                print(f"    - {oblast}")

        # Print biome distribution
        self._print_biome_distribution()

        return self.raion_biomes

    def _get_biome_for_oblast(self, oblast_name: str) -> int:
        """
        Get biome for a given oblast name.

        Args:
            oblast_name: Name of the oblast

        Returns:
            Biome index or None if not found
        """
        # Try exact match first
        if oblast_name in self.OBLAST_BIOME_MAPPING:
            return self.OBLAST_BIOME_MAPPING[oblast_name]

        # Try case-insensitive match
        oblast_lower = oblast_name.lower()
        for key, biome in self.OBLAST_BIOME_MAPPING.items():
            if key.lower() == oblast_lower:
                return biome

        # Try partial match (oblast name contains key or vice versa)
        for key, biome in self.OBLAST_BIOME_MAPPING.items():
            if key.lower() in oblast_lower or oblast_lower in key.lower():
                return biome

        return None

    def _print_biome_distribution(self):
        """Print statistics about biome assignment."""
        biome_names = {
            self.BIOME_ARCTIC: "Arctic",
            self.BIOME_BADLANDS: "Badlands",
            self.BIOME_DESERT: "Desert",
            self.BIOME_GRASSLAND: "Grassland",
            self.BIOME_MEDITERRANEAN: "Mediterranean",
            self.BIOME_SAVANNA: "Savanna",
            self.BIOME_TAIGA: "Taiga",
            self.BIOME_TEMPERATE: "Temperate",
            self.BIOME_TROPICAL: "Tropical",
            self.BIOME_TUNDRA: "Tundra",
        }

        biome_counts = {}
        for biome in self.raion_biomes.values():
            biome_counts[biome] = biome_counts.get(biome, 0) + 1

        print("\n" + "=" * 50)
        print("BIOME DISTRIBUTION")
        print("=" * 50)

        for biome_idx, count in sorted(biome_counts.items()):
            biome_name = biome_names.get(biome_idx, f"Unknown ({biome_idx})")
            percent = 100 * count / len(self.raion_biomes)
            print(f"  {biome_name:15} {count:>3} raions ({percent:>5.1f}%)")

        print("=" * 50)

    def get_biome_for_raion(self, raion_idx: int) -> int:
        """
        Get biome assigned to a specific raion.

        Args:
            raion_idx: Raion index

        Returns:
            Biome index
        """
        return self.raion_biomes.get(raion_idx, self.BIOME_GRASSLAND)

    def get_raions_by_biome(self, name_field: str) -> Dict[int, list]:
        """
        Group raions by biome.

        Args:
            name_field: Column name for raion names

        Returns:
            Dictionary mapping biome_index -> list of raion names
        """
        biome_raions = {}

        for raion_idx, biome in self.raion_biomes.items():
            if biome not in biome_raions:
                biome_raions[biome] = []

            raion_name = self.raion_gdf.loc[raion_idx, name_field]
            biome_raions[biome].append(raion_name)

        return biome_raions
