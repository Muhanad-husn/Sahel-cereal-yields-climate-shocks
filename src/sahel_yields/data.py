"""Data loaders — FAOSTAT yields, CRU TS precip, GADM boundaries, cropland mask.

This module owns ingestion and snapshot pinning. Per CLAUDE.md, FAOSTAT revises
historical figures, so the main notebook reads a *pinned parquet snapshot*
(``data/processed/faostat_snapshot_YYYY-MM-DD.parquet``) — never the raw CSV
directly. ``load_faostat`` reads the raw CSV; ``write_faostat_snapshot`` pins it;
``load_faostat_snapshot`` is what downstream code (notebook) should call.

Raw file locations are per ``docs/DATA_MANIFEST.md`` ("AS DOWNLOADED" section).
CRU TS is a ~6 GB uncompressed .nc — ``load_cru_pre`` subsets to a Sahel bbox
before materialising anything.

Implemented in Session 2.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
import xarray as xr

from . import COUNTRIES

# --- Paths ------------------------------------------------------------------
# Repo root is two levels above this package (src/sahel_yields/data.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = _REPO_ROOT / "data" / "raw"
PROCESSED_DIR = _REPO_ROOT / "data" / "processed"
DOCS_DIR = _REPO_ROOT / "docs"

# --- Constants --------------------------------------------------------------
# Bounding box covering all six Sahel countries with a margin. Senegal/Mauritania
# reach ~-17.5°W, Chad ~24°E; latitudes span ~7.4°N (south Chad) to ~27.7°N
# (north Mauritania). Generous margins so no edge gridcell is clipped.
SAHEL_BBOX = {"lon_min": -19.0, "lon_max": 25.0, "lat_min": 6.0, "lat_max": 28.0}

# FAOSTAT numeric "Area Code" → ISO3. (Distinct from the M49 code.)
_FAO_AREA_CODE = {233: "BFA", 39: "TCD", 133: "MLI", 136: "MRT", 158: "NER", 195: "SEN"}

# FAOSTAT numeric "Item Code" → crop label.
_FAO_ITEM_CODE = {79: "millet", 83: "sorghum"}

# FAOSTAT "Element Code" for crop yield (unit kg/ha).
_FAO_YIELD_ELEMENT = 5412

# Default snapshot access date (encoded into the pinned parquet file name).
SNAPSHOT_DATE = "2026-05-19"

_FAOSTAT_CSV = (
    RAW_DIR
    / "Production_Crops_Livestock_E_All_Data_(Normalized)"
    / "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
)
_CRU_NC = RAW_DIR / "cru_ts4.09.1901.2024.pre.dat.nc"
_CROPLAND_TIF = (
    RAW_DIR
    / "CroplandPastureArea2000_Geotiff"
    / "CroplandPastureArea2000_Geotiff"
    / "Cropland2000_5m.tif"
)


# --- FAOSTAT ----------------------------------------------------------------
def load_faostat(csv_path: Path = _FAOSTAT_CSV) -> pd.DataFrame:
    """Read the raw FAOSTAT crops CSV, filtered to the analysis subset.

    Returns a tidy country-year-crop long frame: the six Sahel countries,
    millet & sorghum, Element=Yield only. The CSV is ~545 MB, so it is read in
    chunks and each chunk filtered before concatenation.

    Columns: ``iso3``, ``country``, ``crop``, ``year``, ``yield_kg_ha``, ``flag``.
    """
    usecols = ["Area Code", "Item Code", "Element Code", "Year", "Unit", "Value", "Flag"]
    keep = []
    for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=500_000):
        m = (
            chunk["Area Code"].isin(_FAO_AREA_CODE)
            & chunk["Item Code"].isin(_FAO_ITEM_CODE)
            & (chunk["Element Code"] == _FAO_YIELD_ELEMENT)
        )
        if m.any():
            keep.append(chunk.loc[m])
    if not keep:
        raise ValueError(f"No matching FAOSTAT rows found in {csv_path}")
    df = pd.concat(keep, ignore_index=True)

    units = set(df["Unit"].unique())
    if units != {"kg/ha"}:
        raise ValueError(f"Unexpected FAOSTAT yield units: {units}")

    out = pd.DataFrame(
        {
            "iso3": df["Area Code"].map(_FAO_AREA_CODE),
            "country": df["Area Code"].map(_FAO_AREA_CODE).map(COUNTRIES),
            "crop": df["Item Code"].map(_FAO_ITEM_CODE),
            "year": df["Year"].astype("int32"),
            "yield_kg_ha": df["Value"].astype("float64"),
            "flag": df["Flag"].astype("string"),
        }
    )
    return out.sort_values(["iso3", "crop", "year"]).reset_index(drop=True)


def write_faostat_snapshot(
    access_date: str = SNAPSHOT_DATE, csv_path: Path = _FAOSTAT_CSV
) -> Path:
    """Pin the current FAOSTAT extract to a dated parquet snapshot.

    Writes ``data/processed/faostat_snapshot_<access_date>.parquet``. This is an
    explicit, documented re-fetch step (CLAUDE.md) — the notebook never calls it
    implicitly; it reads the snapshot via :func:`load_faostat_snapshot`.
    """
    df = load_faostat(csv_path)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / f"faostat_snapshot_{access_date}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path


def load_faostat_snapshot(access_date: str = SNAPSHOT_DATE) -> pd.DataFrame:
    """Load the pinned FAOSTAT snapshot parquet — the canonical analytic input."""
    path = PROCESSED_DIR / f"faostat_snapshot_{access_date}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot {path.name} not found — run write_faostat_snapshot() first."
        )
    return pd.read_parquet(path)


# --- CRU TS precipitation ---------------------------------------------------
def load_cru_pre(nc_path: Path = _CRU_NC, bbox: dict = SAHEL_BBOX) -> xr.DataArray:
    """Open CRU TS precipitation and subset to the Sahel bounding box.

    The source file is a ~6 GB uncompressed netCDF spanning the globe and
    1901–2024. xarray opens it lazily; this returns the ``pre`` variable
    subset to ``bbox`` and loaded into memory (the subset is small).

    Returns a DataArray with dims (time, lat, lon), units mm/month.
    """
    ds = xr.open_dataset(nc_path)
    try:
        pre = ds["pre"].sel(
            lon=slice(bbox["lon_min"], bbox["lon_max"]),
            lat=slice(bbox["lat_min"], bbox["lat_max"]),
        )
        return pre.load()
    finally:
        ds.close()


# --- GADM boundaries --------------------------------------------------------
def load_gadm(level: int = 0, raw_dir: Path = RAW_DIR) -> gpd.GeoDataFrame:
    """Read the six per-country GADM GeoPackages into one GeoDataFrame.

    ``level`` selects the admin level: 0 (country, default) or 1 (first
    subdivision). Each GeoPackage has layers ``ADM_ADM_0`` .. ``ADM_ADM_3``.
    An ``iso3`` column is added from the file name for convenient joins.
    """
    if level not in (0, 1):
        raise ValueError("level must be 0 or 1")
    layer = f"ADM_ADM_{level}"
    parts = []
    for iso3 in COUNTRIES:
        gdf = gpd.read_file(raw_dir / f"gadm41_{iso3}.gpkg", layer=layer)
        gdf["iso3"] = iso3
        parts.append(gdf)
    out = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry", crs=parts[0].crs)


# --- Cropland mask ----------------------------------------------------------
def load_cropland(tif_path: Path = _CROPLAND_TIF) -> rasterio.DatasetReader:
    """Open the EarthStat year-2000 cropland-fraction raster (5-arc-minute).

    Returns an open :class:`rasterio.DatasetReader`; the caller is responsible
    for closing it (or using it as a context manager). The climate layer
    window-reads from it for the cropland-weighted aggregation diagnostic.
    """
    return rasterio.open(tif_path)
