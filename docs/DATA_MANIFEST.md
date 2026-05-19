# Data manifest — files to download

Download each file to the indicated path under `data/raw/`. Create the
subfolders as needed. Once all four sets are present, the notebook can be run
top-to-bottom; nothing downstream re-fetches from the network.

All access dates assumed **2026-05-19** (encoded into the FAOSTAT snapshot name).

---

## 1. FAOSTAT — crop yields (millet & sorghum)

- **File:** `Production_Crops_Livestock_E_All_Data_(Normalized).zip` (~33 MB)
- **URL:** https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip
- **Save to:** `data/raw/faostat/Production_Crops_Livestock_E_All_Data_(Normalized).zip`
- **Notes:** Global file — all countries, all crops. We filter to the six
  countries + Item `Millet` / `Sorghum`, Element `Yield`. No Africa-only bulk
  file exists. Do **not** unzip manually; the loader reads the zip directly.

## 2. CRU TS 4.09 — precipitation

- **File:** `cru_ts4.09.1901.2024.pre.dat.nc.gz` (~250 MB, full 1901–2024)
- **URL:** https://data.ceda.ac.uk/badc/cru/data/cru_ts/cru_ts_4.09/data/pre/cru_ts4.09.1901.2024.pre.dat.nc.gz
- **Save to:** `data/raw/cru/cru_ts4.09.1901.2024.pre.dat.nc.gz`
- **Notes:** CEDA may require a **free CEDA account** to download. Only the
  precipitation variable (`pre`) is needed — SPI uses precip only. Keep it
  gzipped; the loader / xarray reads it directly. This is the slow ingestion
  step — download once.

## 3. GADM 4.1 — country boundary polygons

- **Files:** six per-country GeoPackages (admin-0 + admin-1)
- **URL pattern:** `https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_<ISO3>.gpkg`
  - Burkina Faso → `gadm41_BFA.gpkg`
  - Mali → `gadm41_MLI.gpkg`
  - Niger → `gadm41_NER.gpkg`
  - Senegal → `gadm41_SEN.gpkg`
  - Chad → `gadm41_TCD.gpkg`
  - Mauritania → `gadm41_MRT.gpkg`
- **Save to:** `data/raw/gadm/gadm41_<ISO3>.gpkg`
- **Notes:** Used to clip / area-weight CRU 0.5° gridcells to each country.

## 4. Cropland mask — for the spatial-weighting decision (#3)

- **File:** `CroplandPastureArea2000_Geotiff.zip` (EarthStat / Ramankutty et al.)
- **URL:** http://www.earthstat.org/cropland-pasture-area-2000/  → "Download"
  button (single GeoTIFF zip, ~small; contains `Cropland2000_5m.tif`)
- **Save to:** `data/raw/cropland/CroplandPastureArea2000_Geotiff.zip`
- **Notes:** 5-arc-minute global cropland-fraction raster. Used **only** for the
  cropland-weighted aggregation diagnostic. If this download is awkward, the
  analysis can ship with area-weighting as primary and note the cropland check
  as future work — but the EarthStat file is a single small GeoTIFF and is the
  lightest credible option (lighter than ESA CCI or MIRCA2000).

---

## Out of scope (decided)

- **MODIS NDVI** — dropped. Would require Google Earth Engine setup; CLAUDE.md
  marks it "only if cheap" and it is not.

---

## AS DOWNLOADED (verified 2026-05-19)

All four datasets are present. Actual paths (loaders point here, not at the
idealized paths above):

- FAOSTAT — `data/raw/Production_Crops_Livestock_E_All_Data_(Normalized)/Production_Crops_Livestock_E_All_Data_(Normalized).csv`
  (545 MB, unzipped) + sibling codelist CSVs (`*_AreaCodes.csv`,
  `*_Elements.csv`, `*_ItemCodes.csv`, `*_Flags.csv`).
- CRU TS — `data/raw/cru_ts4.09.1901.2024.pre.dat.nc` (6.17 GB, **uncompressed**
  `.nc` — open directly with xarray; subset to a Sahel bbox early).
- GADM — `data/raw/gadm41_{BFA,MLI,NER,SEN,TCD,MRT}.gpkg`.
- Cropland — `data/raw/CroplandPastureArea2000_Geotiff/CroplandPastureArea2000_Geotiff/Cropland2000_5m.tif`
  (37.9 MB; the genuine EarthStat year-2000 product — confirmed by sidecars and
  metadata PDF). A `__MACOSX/` artifact folder sits alongside; `.gitignore` it.

