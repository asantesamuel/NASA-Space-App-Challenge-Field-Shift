# FAO GAEZ v5 suitability at the Ghana pilot references

Sampled 14 November 2026. The FAO Theme 4 layer represents whole-cell crop suitability class. Both selections use AgERA5 historical climate for 2001–2020 and assume rain-fed production with low inputs. The specific rasters have a native resolution of 5 arc-minutes (roughly 9 km in Ghana) in EPSG:4326. [FAO layer catalog](https://data.apps.fao.org/catalog/iso/00cffd62-2ebf-47ab-9777-332cd1071aa0) · [FAO model documentation](https://github.com/un-fao/gaezv5/wiki/07.-Module-V-(Integration-of-climatic-and-edaphic-evaluation)) · [Official class legend](https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/STYLE/GAEZ-V5.SIX.json)

| Location key | NovaYield crop | FAO crop and layer suffix | Native class | Applicability |
| --- | --- | --- | --- | --- |
| ejura | maize | Grain maize · `MZE.LRLM` | 4 · Medium | Regional grain-maize scenario |
| ejura | yam | Yam (best modeled type) · `YAM.LRLM` | 5 · Moderate | Not comparable to generic yam or a Dente-specific result |
| anyinasu | maize | Grain maize · `MZE.LRLM` | 3 · Good | Regional grain-maize scenario |
| anyinasu | yam | Yam (best modeled type) · `YAM.LRLM` | 3 · Good | Not comparable to generic yam or a Dente-specific result |
| kintampo | maize | Grain maize · `MZE.LRLM` | 5 · Moderate | Regional grain-maize scenario |
| kintampo | yam | Yam (best modeled type) · `YAM.LRLM` | 4 · Medium | Not comparable to generic yam or a Dente-specific result |

The full layer IDs and SHA-256 hashes identify the exact rasters sampled.

| Layer | SHA-256 |
| --- | --- |
| [GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.LRLM](https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/RES05-SIX/GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.MZE.LRLM.tif) | `2faebf03fee99822b92ec7d22d797393c58a4ab6fc584e6deb63e4bdcb9f30b4` |
| [GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.YAM.LRLM](https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/MAPSET/RES05-SIX/GAEZ-V5.RES05-SIX.HP0120.AGERA5.HIST.YAM.LRLM.tif) | `6003ca81ae1559d6b77b2079749ffe5c7eabb73b3fdcf27828728332a3680b25` |

To reproduce, download the rasters and their same-name JSON sidecars from the FAO bucket. Resolve the three supported town references inside private operator tooling. Use Rasterio `sample(..., masked=True)` or an equivalent single containing-cell lookup with the source affine transform, without interpolation. Read the raw class and map it to the FAO legend. The raster and legend mark 0 as missing and 8 as a valid unsuitable class. Publish only the location keys and class labels. The pilot samples all had valid raster values.

Kintampo's grain-maize value is lower than the other two sampled cells. Ask local extension which conditions constrain rain-fed maize at the communities the pilot serves and how that should inform advice. The coarse cells and modeled management assumptions do not establish plot soil condition, maturity, or current planting dates. The calendar seeds draw their timing from Ghana MoFA and the Kintampo North trial. These model classes stay in the evidence record, outside the recommendation engine.
