# Data-access manifest

Provenance record for the four raw datasets ingested by `src/sahel_yields/data.py`.
FAOSTAT revises history, so the access date is load-bearing — it is encoded into
the pinned snapshot file name. See `docs/DATA_MANIFEST.md` for download URLs and
exact on-disk paths.

| Dataset | Source | Version | Access date | Used for | Loader |
|---------|--------|---------|-------------|----------|--------|
| FAOSTAT crop yields | FAO, Production: Crops and Livestock Products (QCL) | bulk file dated 2024-12-23 | 2026-05-19 | Millet & sorghum national annual yields, 1961–2024 | `load_faostat` |
| CRU TS precipitation | UEA CRU, CRU TS 4.09 | v4.09 (1901–2024) | 2026-05-19 | Monthly precip on 0.5° grid → SPI | `load_cru_pre` |
| GADM boundaries | GADM 4.1 | v4.1 | 2026-05-19 | Country / admin-1 polygons for spatial weighting | `load_gadm` |
| Cropland mask | EarthStat (Ramankutty et al.) Cropland & Pasture Area 2000 | year-2000 product, 5-arc-min | 2026-05-19 | Cropland-weighted CRU aggregation (decision #3) | `load_cropland` |

## Pinned snapshot

- **File:** `data/processed/faostat_snapshot_2026-05-19.parquet` (committed; canonical analytic input)
- **Contents:** 768 rows = 6 countries × {millet, sorghum} × 64 years (1961–2024),
  Element = Yield (FAOSTAT element code 5412, kg/ha). No missing yields.
- **Written by:** `write_faostat_snapshot()` — an explicit, documented re-fetch
  step. The notebook reads the snapshot via `load_faostat_snapshot()`; it never
  reads the raw CSV. Re-pinning requires running `write_faostat_snapshot()` with
  a new access date and the revision-magnitude diagnostic (decision block #6).

## Verification (2026-05-19)

All four loaders exercised; smoke checks passed: 768 FAOSTAT rows with no NaN
yields and no all-NaN country/crop group; CRU `pre` subset (time=1488, lat=44,
lon=88) covers every country's bounding box; GADM 6 admin-0 / 80 admin-1
features; cropland raster opens (2160×4320, EPSG:4326).
