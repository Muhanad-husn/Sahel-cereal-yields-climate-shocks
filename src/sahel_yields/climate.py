"""Climate layer — SPI from CRU precip, with gridcell-to-country aggregation.

Builds the Standardized Precipitation Index (SPI) used to flag drought
country-years. CRU TS is on a 0.5deg grid; rolling it up to a country aggregate
requires a spatial-weighting choice (load-bearing decision #3): this module
implements BOTH area-overlap weighting and cropland-area weighting; the
diagnostic comparing them lives in the main notebook, not here.

Growing-season windows are country-specific and hard-coded from the FAO crop
calendar (see ``GROWING_SEASON``).

Pipeline, in call order:
    gridcells_to_country()  -> per-country cell weights (both modes)
    growing_season_precip() -> country-year growing-season precip total
    compute_spi()           -> SPI per country-year
    flag_drought()          -> boolean drought flag

Implemented in Session 3.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import xarray as xr
from rasterio.windows import from_bounds
from scipy.stats import gamma, norm
from shapely.geometry import box

from . import COUNTRIES

# --- Growing-season windows -------------------------------------------------
# Months whose rainfall feeds the rainfed millet/sorghum crop cycle, by country.
# The Sahel has a single rainy season: rains onset May-Jun, harvest Sep-Nov.
# Windows are the core rainy-season months from the FAO GIEWS country crop
# calendars (https://cropcalendar.apps.fao.org/ ; FAO/GIEWS Country Briefs).
# Mauritania's window is shorter and later: rainfed cropping is confined to the
# far south and the rains arrive last and retreat first.
GROWING_SEASON: dict[str, list[int]] = {
    "BFA": [6, 7, 8, 9],      # Burkina Faso — Jun–Sep
    "MLI": [6, 7, 8, 9],      # Mali — Jun–Sep
    "NER": [6, 7, 8, 9],      # Niger — Jun–Sep
    "SEN": [6, 7, 8, 9, 10],  # Senegal — Jun–Oct (rains linger on the coast)
    "TCD": [6, 7, 8, 9],      # Chad — Jun–Sep
    "MRT": [7, 8, 9],         # Mauritania — Jul–Sep (shortest window)
}

_MODE_COL = {"area": "w_area", "cropland": "w_cropland"}


# --- Spatial weighting ------------------------------------------------------
def gridcells_to_country(pre, gadm, cropland_src) -> pd.DataFrame:
    """Compute per-country CRU gridcell weights under both weighting modes.

    For every CRU 0.5deg cell that overlaps a country, two weights are derived:

    * ``w_area``     — area of the cell-country overlap (decision #3 option 1).
    * ``w_cropland`` — that overlap area scaled by the mean cropland fraction
      inside the cell (decision #3 option 2: rainfall *where crops grow*).

    Overlap areas are computed in degrees-squared then multiplied by
    ``cos(latitude)`` so higher-latitude cells are not over-counted. Both weight
    columns are normalised to sum to 1 per country, so they are ready to use as
    weighted-average coefficients.

    Parameters
    ----------
    pre : xr.DataArray
        CRU precip from :func:`sahel_yields.data.load_cru_pre` — needs ``lat``
        and ``lon`` coords; only the grid geometry is read here.
    gadm : geopandas.GeoDataFrame
        Admin-0 boundaries from :func:`sahel_yields.data.load_gadm` (has ``iso3``).
    cropland_src : rasterio.DatasetReader
        Open cropland-fraction raster from :func:`sahel_yields.data.load_cropland`.

    Returns
    -------
    pd.DataFrame
        Long frame, columns ``iso3, lat, lon, w_area, w_cropland``.
    """
    lats = np.asarray(pre["lat"].values, dtype=float)
    lons = np.asarray(pre["lon"].values, dtype=float)
    half_lat = abs(float(lats[1] - lats[0])) / 2.0
    half_lon = abs(float(lons[1] - lons[0])) / 2.0

    rows = []
    for iso3 in COUNTRIES:
        geom = gadm.loc[gadm["iso3"] == iso3, "geometry"].union_all()
        # Simplify at ~1 km tolerance — negligible vs a 0.5deg (~55 km) cell,
        # but it speeds up the hundreds of intersection tests below.
        geom = geom.simplify(0.01)
        minx, miny, maxx, maxy = geom.bounds

        for la in lats:
            if la + half_lat < miny or la - half_lat > maxy:
                continue
            for lo in lons:
                if lo + half_lon < minx or lo - half_lon > maxx:
                    continue
                cell = box(lo - half_lon, la - half_lat, lo + half_lon, la + half_lat)
                inter = geom.intersection(cell)
                if inter.is_empty or inter.area == 0.0:
                    continue
                # deg^2 overlap corrected to true area by the latitude cosine.
                area = inter.area * np.cos(np.radians(la))
                crop = _cell_cropland_fraction(cropland_src, la, lo, half_lat, half_lon)
                rows.append((iso3, float(la), float(lo), area, area * crop))

    weights = pd.DataFrame(rows, columns=["iso3", "lat", "lon", "w_area", "w_cropland"])

    # Normalise each weight column to sum to 1 within each country.
    for iso3, grp in weights.groupby("iso3"):
        idx = grp.index
        weights.loc[idx, "w_area"] = grp["w_area"] / grp["w_area"].sum()
        crop_total = grp["w_cropland"].sum()
        if crop_total > 0:
            weights.loc[idx, "w_cropland"] = grp["w_cropland"] / crop_total
        else:
            # No cropland in any overlapping cell — fall back to area weights so
            # the cropland mode still yields a defined series (semantic safety).
            warnings.warn(
                f"{iso3}: cropland weights all zero; falling back to area weights.",
                stacklevel=2,
            )
            weights.loc[idx, "w_cropland"] = grp["w_area"] / grp["w_area"].sum()

    return weights.sort_values(["iso3", "lat", "lon"]).reset_index(drop=True)


def _cell_cropland_fraction(src, lat, lon, half_lat, half_lon) -> float:
    """Mean cropland fraction within one CRU cell (window-read, nodata-masked)."""
    win = from_bounds(
        lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat, src.transform
    )
    arr = src.read(1, window=win).astype("float64")
    valid = np.isfinite(arr) & (arr >= 0.0)
    if src.nodata is not None:
        valid &= arr != src.nodata
    return float(arr[valid].mean()) if valid.any() else 0.0


# --- Growing-season aggregation ---------------------------------------------
def growing_season_precip(pre, weights: pd.DataFrame, mode: str = "area") -> pd.DataFrame:
    """Aggregate CRU precip into a country-year growing-season total.

    For each country the weighted average of monthly cell precip is taken
    (weights from :func:`gridcells_to_country`, selected by ``mode``), then the
    months in :data:`GROWING_SEASON` are summed within each calendar year.

    Parameters
    ----------
    pre : xr.DataArray
        CRU precip (dims time, lat, lon), mm/month.
    weights : pd.DataFrame
        Output of :func:`gridcells_to_country`.
    mode : {"area", "cropland"}
        Which weighting column to apply.

    Returns
    -------
    pd.DataFrame
        Columns ``iso3, year, season_precip`` (mm), one row per country-year.
    """
    if mode not in _MODE_COL:
        raise ValueError(f"mode must be one of {sorted(_MODE_COL)}, got {mode!r}")
    wcol = _MODE_COL[mode]

    years = np.asarray(pre["time"].dt.year.values)
    months = np.asarray(pre["time"].dt.month.values)

    out = []
    for iso3, grp in weights.groupby("iso3"):
        # Pointwise (vectorised) selection: shared "cell" dim -> one value per cell.
        cell_lat = xr.DataArray(grp["lat"].values, dims="cell")
        cell_lon = xr.DataArray(grp["lon"].values, dims="cell")
        sub = pre.sel(lat=cell_lat, lon=cell_lon)
        w = xr.DataArray(grp[wcol].values, dims="cell")
        monthly = (sub * w).sum("cell").values  # weighted-avg precip, per month

        mdf = pd.DataFrame({"year": years, "month": months, "precip": monthly})
        mdf = mdf[mdf["month"].isin(GROWING_SEASON[iso3])]
        seasonal = mdf.groupby("year", as_index=False)["precip"].sum()
        seasonal = seasonal.rename(columns={"precip": "season_precip"})
        seasonal.insert(0, "iso3", iso3)
        out.append(seasonal)

    return pd.concat(out, ignore_index=True)


# --- SPI --------------------------------------------------------------------
def compute_spi(season_precip: pd.DataFrame) -> pd.DataFrame:
    """Compute the Standardized Precipitation Index per country-year.

    SPI follows McKee et al. (1993): fit a gamma distribution to the country's
    growing-season precip totals, map each total through the gamma CDF, then
    through the inverse standard-normal CDF. A zero-precip mass term ``q`` is
    carried per the standard mixed-distribution form ``H(x) = q + (1-q)·G(x)``,
    though Sahel growing-season totals are effectively never zero.

    The gamma is fit per country (each has its own climatology); ``loc`` is
    pinned to 0 since precipitation totals are non-negative.

    Returns
    -------
    pd.DataFrame
        ``season_precip`` input with an added ``spi`` column.
    """
    out = []
    for iso3, grp in season_precip.groupby("iso3"):
        grp = grp.copy()
        x = grp["season_precip"].to_numpy(dtype=float)
        positive = x[x > 0]
        q = (len(x) - len(positive)) / len(x)  # zero-precip probability mass

        a, _, scale = gamma.fit(positive, floc=0.0)
        cdf = np.where(
            x > 0,
            q + (1.0 - q) * gamma.cdf(x, a, loc=0.0, scale=scale),
            q / 2.0,  # convention for the zero-precip mass point
        )
        grp["spi"] = norm.ppf(cdf)
        out.append(grp)

    return pd.concat(out, ignore_index=True)


# --- Drought flag -----------------------------------------------------------
def flag_drought(spi_df: pd.DataFrame, threshold: float = -1.0) -> pd.DataFrame:
    """Flag drought country-years as those with SPI below ``threshold``.

    Default ``threshold = -1.0`` is the McKee et al. "moderately dry" cutoff.
    The threshold is a load-bearing choice (decision #1); the notebook varies it
    (-0.8 / -1.0 / -1.5) — this function just applies whatever it is given.

    Returns
    -------
    pd.DataFrame
        Input with an added boolean ``drought`` column.
    """
    out = spi_df.copy()
    out["drought"] = out["spi"] < threshold
    return out
