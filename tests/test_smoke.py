"""Smoke tests — fast checks for the data artifacts, estimators, and viz.

Light by design (Session 7): the tests exercise the *committed / derived
artifacts* (the pinned FAOSTAT snapshot, the analytic-panel parquet) and the
pure estimator logic — never the 6 GB raw CRU file or the 545 MB FAOSTAT CSV.
Tests that need the analytic panel skip gracefully if it has not been built yet
(it is written by ``notebooks/02_main.ipynb`` and is gitignored).

Run with: ``pytest tests/``
"""

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # headless — no display needed for the viz smoke test

from sahel_yields import COUNTRIES, __version__, data, econ, climate, viz


# --- package -----------------------------------------------------------------
def test_package_imports():
    assert __version__
    assert len(COUNTRIES) == 6


# --- FAOSTAT snapshot --------------------------------------------------------
@pytest.fixture(scope="module")
def faostat():
    return data.load_faostat_snapshot()


def test_faostat_snapshot_shape(faostat):
    # 6 countries x 2 crops x 64 years (1961-2024).
    assert faostat.shape == (768, 6)
    assert faostat["iso3"].nunique() == 6
    assert set(faostat["crop"]) == {"millet", "sorghum"}
    assert faostat["year"].min() == 1961 and faostat["year"].max() == 2024


def test_faostat_snapshot_no_missing_yields(faostat):
    assert faostat["yield_kg_ha"].notna().all()
    assert (faostat["yield_kg_ha"] > 0).all()  # log() downstream needs positives


# --- panel assembly (pure function, synthetic climate) -----------------------
def test_build_panel_merges_and_logs(faostat):
    # A synthetic climate frame over the FAOSTAT (iso3, year) grid — exercises
    # build_panel without touching the heavy CRU pipeline.
    grid = faostat[["iso3", "year"]].drop_duplicates().reset_index(drop=True)
    rng = np.random.default_rng(0)
    clim = grid.assign(
        season_precip=rng.uniform(200, 600, len(grid)),
        spi=rng.normal(0, 1, len(grid)),
    )
    clim = climate.flag_drought(clim, threshold=-1.0)

    panel = econ.build_panel(faostat, clim, write=False)
    assert len(panel) == 768
    assert {"log_yield", "spi", "drought"} <= set(panel.columns)
    assert panel["drought"].dtype == bool
    np.testing.assert_allclose(
        panel["log_yield"], np.log(panel["yield_kg_ha"])
    )


# --- analytic panel + estimators (need the built parquet) --------------------
@pytest.fixture(scope="module")
def panel_dt():
    if not econ.PANEL_PATH.exists():
        pytest.skip(f"{econ.PANEL_PATH.name} not built — run 02_main.ipynb first")
    panel = pd.read_parquet(econ.PANEL_PATH)
    return econ.detrend_yields(panel, "linear")


def test_detrend_adds_residual_columns(panel_dt):
    assert {"trend_fit", "yield_dev"} <= set(panel_dt.columns)
    assert panel_dt["yield_dev"].notna().all()
    # A detrend residual is mean-zero per (crop, country) by construction.
    grp_means = panel_dt.groupby(["crop", "iso3"])["yield_dev"].mean()
    np.testing.assert_allclose(grp_means.to_numpy(), 0.0, atol=1e-9)


def test_event_study_shape_and_sign(panel_dt):
    es = econ.event_study(panel_dt, "sorghum", se="country")
    assert list(es.columns) == [
        "event_time", "coef", "se", "ci_low", "ci_high", "pvalue"
    ]
    assert len(es) == 11  # event time -5..+5
    # Reference period -1 is included with coef pinned to zero.
    assert es.loc[es.event_time == -1, "coef"].iloc[0] == 0.0
    # Sign sanity: a drought year depresses yield (et0 < 0) for both crops.
    for crop in ("millet", "sorghum"):
        et0 = econ.event_study(panel_dt, crop, se="country")
        et0 = et0.loc[et0.event_time == 0, "coef"].iloc[0]
        assert et0 < 0, f"{crop} et0 should be negative, got {et0:.4f}"


def test_did_sign(panel_dt):
    for crop in ("millet", "sorghum"):
        d = econ.did(panel_dt, crop, se="country")
        assert {"coef", "se", "ci_low", "ci_high", "pvalue", "nobs"} <= set(d.index)
        assert d["coef"] < 0, f"{crop} DiD coef should be negative, got {d['coef']:.4f}"


# --- viz ---------------------------------------------------------------------
def test_event_time_plot_returns_figure():
    fake = pd.DataFrame({
        "event_time": range(-5, 6),
        "coef": np.linspace(0.05, -0.05, 11),
        "ci_low": np.linspace(-0.05, -0.15, 11),
        "ci_high": np.linspace(0.15, 0.05, 11),
    })
    fig = viz.event_time_plot({"Millet": fake})
    assert fig.axes  # at least one panel was drawn
