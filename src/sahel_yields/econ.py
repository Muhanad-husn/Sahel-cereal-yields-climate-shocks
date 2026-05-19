"""Econ layer — analytic panel assembly and event-study / DiD estimators.

Builds the country-year analytic panel (log yields + SPI/drought flags) and the
estimators. Built on ``statsmodels`` — not reinvented.

With n=6 clusters, conventional cluster-robust SEs are biased downward; the
wild-cluster bootstrap (Cameron, Gelbach & Miller 2008, via ``wildboottest``) is
the standard correction. The decision blocks that *choose* trend spec, SE
clustering, and partial-drought inclusion are notebook work — this module just
exposes the knobs.

Pipeline, in call order:
    build_panel()    -> country-year-crop panel with log_yield + drought flags
    detrend_yields() -> per-country trend removed -> ``yield_dev``
    event_study()    -> event-time -5..+5 coefficients + CIs
    did()            -> drought-hit vs non-drought-hit within-year effect
    cluster_se()     -> SEs/CIs under a chosen clustering scheme (helper)

Implemented in Session 4.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import dmatrix
from wildboottest.wildboottest import WildboottestCL

from .data import PROCESSED_DIR

# Default location of the pinned analytic panel.
PANEL_PATH = PROCESSED_DIR / "analytic_panel.parquet"

# Event-study half-window: dummies span event time -WINDOW .. +WINDOW.
_EVENT_WINDOW = 5

_TREND_SPECS = ("linear", "quadratic", "spline")
_SE_MODES = ("country", "year", "twoway", "wild")


# --- Panel assembly ---------------------------------------------------------
def build_panel(
    faostat: pd.DataFrame,
    climate: pd.DataFrame,
    *,
    write: bool = False,
    panel_path=PANEL_PATH,
) -> pd.DataFrame:
    """Merge FAOSTAT yields with the SPI/drought series into a country-year panel.

    The join is an inner merge on ``(iso3, year)``: the SPI series spans CRU's
    1901–2024 but FAOSTAT yields span 1961–2024, so the merge drops the
    pre-1961 climate years (their longer climatology already fed the gamma fit
    in :func:`sahel_yields.climate.compute_spi` — only the panel needs overlap).

    Parameters
    ----------
    faostat : pd.DataFrame
        Pinned FAOSTAT snapshot from
        :func:`sahel_yields.data.load_faostat_snapshot` — columns
        ``iso3, country, crop, year, yield_kg_ha, flag``.
    climate : pd.DataFrame
        Flagged SPI series from :func:`sahel_yields.climate.flag_drought` —
        columns ``iso3, year, season_precip, spi, drought``. This is
        mode-specific (area vs cropland weighting); the caller passes whichever
        the spatial-weighting decision (#3) selects.
    write : bool
        If True, write the panel to ``panel_path`` as parquet.

    Returns
    -------
    pd.DataFrame
        One row per ``(crop, iso3, year)`` with an added ``log_yield`` column.
    """
    clim_cols = ["iso3", "year", "season_precip", "spi", "drought"]
    panel = faostat.merge(climate[clim_cols], on=["iso3", "year"], how="inner")

    if (panel["yield_kg_ha"] <= 0).any():
        raise ValueError("Non-positive yield values — cannot take log.")
    panel["log_yield"] = np.log(panel["yield_kg_ha"])

    panel = panel.sort_values(["crop", "iso3", "year"]).reset_index(drop=True)

    if write:
        panel_path.parent.mkdir(parents=True, exist_ok=True)
        panel.to_parquet(panel_path, index=False)

    return panel


# --- Detrending -------------------------------------------------------------
def detrend_yields(
    panel: pd.DataFrame,
    spec: str = "linear",
    *,
    dv: str = "log_yield",
    spline_df: int = 4,
) -> pd.DataFrame:
    """Remove a country-specific time trend from yields → ``yield_dev``.

    Yield baselines drift over decades (seed varieties, fertiliser, area under
    cultivation). A trend is fit *per (crop, country)* and the residual is the
    yield deviation the event study works on. Trend spec is a load-bearing
    choice (decision #2); all three specs are supported here so the notebook can
    compare them.

    Parameters
    ----------
    panel : pd.DataFrame
        Output of :func:`build_panel`.
    spec : {"linear", "quadratic", "spline"}
        ``linear`` / ``quadratic`` — polynomial in (centred) year. ``spline`` —
        a natural cubic regression spline (``patsy`` ``cr``) with ``spline_df``
        degrees of freedom; flexible without the tail blow-up of a high-order
        polynomial.
    dv : str
        Column to detrend (default ``log_yield``).
    spline_df : int
        Degrees of freedom for the spline basis (ignored unless ``spec="spline"``).

    Returns
    -------
    pd.DataFrame
        Copy of ``panel`` with added ``trend_fit`` and ``yield_dev`` columns.
    """
    if spec not in _TREND_SPECS:
        raise ValueError(f"spec must be one of {_TREND_SPECS}, got {spec!r}")

    out = panel.copy()
    out["trend_fit"] = np.nan
    out["yield_dev"] = np.nan

    for (_crop, _iso3), grp in out.groupby(["crop", "iso3"], sort=False):
        t = grp["year"].to_numpy(dtype=float)
        t = t - t.mean()  # centre so the polynomial design is well-conditioned
        y = grp[dv].to_numpy(dtype=float)

        if spec == "linear":
            x = np.column_stack([np.ones_like(t), t])
        elif spec == "quadratic":
            x = np.column_stack([np.ones_like(t), t, t**2])
        else:  # spline — cr() carries its own intercept
            x = dmatrix(
                f"cr(t, df={spline_df})", {"t": t}, return_type="dataframe"
            ).to_numpy()

        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        fit = x @ beta
        out.loc[grp.index, "trend_fit"] = fit
        out.loc[grp.index, "yield_dev"] = y - fit

    return out


# --- Event-time dummies -----------------------------------------------------
def _et_col(tau: int) -> str:
    """Event-time offset → dummy column name (``-3`` → ``etm3``, ``2`` → ``etp2``)."""
    if tau == 0:
        return "et0"
    return f"etm{abs(tau)}" if tau < 0 else f"etp{tau}"


def _et_tau(col: str) -> int:
    """Inverse of :func:`_et_col`."""
    if col == "et0":
        return 0
    return -int(col[3:]) if col.startswith("etm") else int(col[3:])


def _add_event_dummies(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Add event-time dummies ``etm{k}`` / ``et0`` / ``etp{k}`` for one crop.

    Distributed-lag construction: ``etp{k}`` flags a country-year exactly *k*
    years after a drought, ``etm{k}`` exactly *k* years before, ``et0`` the
    drought year itself. With multiple droughts a country-year can carry several
    dummies (e.g. 2 years after one drought and 3 before the next) — the
    standard distributed-lag interpretation. Country-years outside every ±window
    are the reference group.
    """
    df = df.sort_values(["iso3", "year"]).reset_index(drop=True).copy()
    cols = [_et_col(tau) for tau in range(-window, window + 1)]
    for c in cols:
        df[c] = 0

    for iso3, grp in df.groupby("iso3", sort=False):
        d = grp["drought"].astype(int)
        df.loc[grp.index, "et0"] = d.to_numpy()
        for k in range(1, window + 1):
            # drought k years ago -> this row is at event time +k
            df.loc[grp.index, f"etp{k}"] = d.shift(k).fillna(0).astype(int).to_numpy()
            # drought k years ahead -> this row is at event time -k
            df.loc[grp.index, f"etm{k}"] = d.shift(-k).fillna(0).astype(int).to_numpy()

    return df


# --- Estimators -------------------------------------------------------------
def event_study(
    panel: pd.DataFrame,
    crop: str,
    *,
    dv: str = "yield_dev",
    window: int = _EVENT_WINDOW,
    ref: int = -1,
    se: str = "country",
    B: int = 9999,
    seed: int = 12345,
) -> pd.DataFrame:
    """Event study of yield deviation around drought years.

    Regresses ``dv`` on event-time dummies (event time ``-window..+window``,
    with ``ref`` omitted as the baseline period) plus country and year fixed
    effects. SEs/CIs come from :func:`cluster_se` under the chosen scheme.

    Parameters
    ----------
    panel : pd.DataFrame
        Output of :func:`detrend_yields` (must contain ``dv``).
    crop : {"millet", "sorghum"}
        Crop to estimate for.
    dv : str
        Dependent variable (default the detrended ``yield_dev``).
    window : int
        Event-time half-window.
    ref : int
        Event-time period omitted as the reference (default ``-1``, the year
        before the drought — the conventional event-study normalisation).
    se : {"country", "year", "twoway", "wild"}
        Clustering scheme for SEs/CIs (see :func:`cluster_se`).
    B, seed : int
        Bootstrap iterations / seed, used only when ``se="wild"``.

    Returns
    -------
    pd.DataFrame
        One row per event time, columns ``event_time, coef, se, ci_low,
        ci_high, pvalue``. The reference period is included with ``coef=0``.
        ``.attrs`` carries ``crop``, ``dv``, ``se``, ``nobs``, ``ref``.
    """
    sub = panel.loc[panel["crop"] == crop]
    if sub.empty:
        raise ValueError(f"No rows for crop {crop!r}.")
    sub = _add_event_dummies(sub, window)

    all_cols = [_et_col(tau) for tau in range(-window, window + 1)]
    ref_col = _et_col(ref)
    if ref_col not in all_cols:
        raise ValueError(f"ref={ref} outside the +/-{window} window.")
    rhs = [c for c in all_cols if c != ref_col]

    data = sub.dropna(subset=[dv]).reset_index(drop=True)
    formula = f"{dv} ~ " + " + ".join(rhs) + " + C(iso3) + C(year)"
    res = smf.ols(formula, data=data).fit()

    est = cluster_se(res, data, mode=se, params=rhs, B=B, seed=seed)

    rows = []
    for c in all_cols:
        tau = _et_tau(c)
        if c == ref_col:
            rows.append((tau, 0.0, 0.0, 0.0, 0.0, np.nan))
        else:
            r = est.loc[c]
            rows.append(
                (tau, res.params[c], r["se"], r["ci_low"], r["ci_high"], r["pvalue"])
            )

    tab = pd.DataFrame(
        rows, columns=["event_time", "coef", "se", "ci_low", "ci_high", "pvalue"]
    ).sort_values("event_time").reset_index(drop=True)
    tab.attrs.update(crop=crop, dv=dv, se=se, nobs=int(res.nobs), ref=ref)
    return tab


def did(
    panel: pd.DataFrame,
    crop: str,
    *,
    dv: str = "yield_dev",
    se: str = "country",
    B: int = 9999,
    seed: int = 12345,
) -> pd.Series:
    """Difference-in-differences cross-check: drought-hit vs non-hit within year.

    Regresses ``dv`` on a current-year drought indicator plus country and year
    fixed effects. The year FE makes the comparison *within* each year — the
    drought coefficient is the average yield deviation of drought-hit
    country-years relative to non-drought-hit country-years observed the same
    year. This is the panel-DiD analogue of the event study's ``et0`` term.

    Returns
    -------
    pd.Series
        ``coef, se, ci_low, ci_high, pvalue, nobs``.
    """
    data = panel.loc[panel["crop"] == crop].dropna(subset=[dv]).reset_index(drop=True)
    if data.empty:
        raise ValueError(f"No rows for crop {crop!r}.")
    data = data.copy()
    data["drought_i"] = data["drought"].astype(int)

    res = smf.ols(f"{dv} ~ drought_i + C(iso3) + C(year)", data=data).fit()
    est = cluster_se(res, data, mode=se, params=["drought_i"], B=B, seed=seed)
    r = est.loc["drought_i"]

    return pd.Series(
        {
            "coef": res.params["drought_i"],
            "se": r["se"],
            "ci_low": r["ci_low"],
            "ci_high": r["ci_high"],
            "pvalue": r["pvalue"],
            "nobs": int(res.nobs),
        },
        name=f"{crop}:{se}",
    )


# --- Standard errors --------------------------------------------------------
def _group_codes(s: pd.Series) -> np.ndarray:
    """Integer cluster codes for a grouping column."""
    return pd.factorize(s)[0]


def cluster_se(
    res,
    data: pd.DataFrame,
    mode: str = "country",
    *,
    params: list[str] | None = None,
    B: int = 9999,
    seed: int = 12345,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """SEs / CIs / p-values for a fitted OLS under a chosen clustering scheme.

    Parameters
    ----------
    res : statsmodels OLS results
        A fitted ``statsmodels`` OLS results object (the model is refit with the
        requested covariance for the conventional modes).
    data : pd.DataFrame
        The estimation frame — must have ``iso3`` and ``year`` columns aligned
        row-for-row with ``res.model.exog``.
    mode : {"country", "year", "twoway", "wild"}
        ``country`` / ``year`` — one-way cluster-robust. ``twoway`` — Cameron-
        Gelbach-Miller two-way (country × year). ``wild`` — wild-cluster
        bootstrap by country.
    params : list[str] or None
        Coefficients to report (default: all).
    B, seed : int
        Bootstrap iterations / seed (``wild`` mode only). Note: with 6 country
        clusters there are only 2**6 = 64 distinct Rademacher sign vectors, so
        the bootstrap is effectively fully enumerated and ``B`` beyond 64 adds
        nothing — ``wildboottest`` handles the enumeration internally.
    alpha : float
        CI level (default 0.05 → 95% CI).

    Returns
    -------
    pd.DataFrame
        Indexed by parameter name, columns ``se, ci_low, ci_high, pvalue``.

    Notes
    -----
    The ``wild`` CI is a **percentile-t** (bootstrap-t) interval:
    ``beta_hat -/+ se * quantile(t_boot)``, using the bootstrap distribution of
    the studentised statistic. This is the standard practical wild-bootstrap
    interval; the fully rigorous CGM interval inverts the test over a grid of
    null values (many bootstrap re-runs per coefficient), which is not worth the
    cost here (portfolio Principle 2) — the percentile-t interval delivers the
    same headline point: the wild CI is wider than the conventional one.
    """
    if mode not in _SE_MODES:
        raise ValueError(f"mode must be one of {_SE_MODES}, got {mode!r}")

    exog_names = list(res.model.exog_names)
    if params is None:
        params = exog_names

    if mode in ("country", "year", "twoway"):
        if mode == "country":
            groups = _group_codes(data["iso3"])
        elif mode == "year":
            groups = _group_codes(data["year"])
        else:
            groups = np.column_stack(
                [_group_codes(data["iso3"]), _group_codes(data["year"])]
            )
        cres = res.model.fit(cov_type="cluster", cov_kwds={"groups": groups})
        ci = cres.conf_int(alpha=alpha)
        rows = {
            p: (cres.bse[p], ci.loc[p, 0], ci.loc[p, 1], cres.pvalues[p])
            for p in params
        }
        return pd.DataFrame.from_dict(
            rows, orient="index", columns=["se", "ci_low", "ci_high", "pvalue"]
        )

    # --- wild-cluster bootstrap ---------------------------------------------
    x = np.asarray(res.model.exog, dtype=float)
    y = np.asarray(res.model.endog, dtype=float)
    # wildboottest's numba kernels need a numeric cluster array, not strings.
    cluster = _group_codes(data["iso3"])
    k = x.shape[1]
    q_lo, q_hi = alpha / 2.0, 1.0 - alpha / 2.0

    rows = {}
    for p in params:
        j = exog_names.index(p)
        contrast = np.zeros(k)
        contrast[j] = 1.0

        wb = WildboottestCL(X=x, Y=y, cluster=cluster, R=contrast, B=B, seed=seed)
        wb.get_scores(bootstrap_type="11", impose_null=True)
        wb.get_weights(weights_type="rademacher")
        wb.get_numer()
        wb.get_denom()
        wb.get_tboot()
        wb.get_vcov()
        wb.get_tstat()
        wb.get_pvalue()

        beta = float(res.params[p])
        t_stat = float(np.ravel(wb.t_stat)[0])
        # t_stat = (R @ beta_hat) / se  ->  recover the studentising SE.
        se = abs(beta / t_stat) if t_stat != 0 else np.nan
        t_boot = np.asarray(wb.t_boot, dtype=float)
        lo, hi = np.quantile(t_boot, [q_lo, q_hi])
        # percentile-t: invert beta_hat - se * t_boot
        rows[p] = (se, beta - se * hi, beta - se * lo, float(wb.pvalue))

    return pd.DataFrame.from_dict(
        rows, orient="index", columns=["se", "ci_low", "ci_high", "pvalue"]
    )
