# Sahel cereal yields & climate shocks

> How much do drought years actually reduce millet and sorghum yields in the Sahel, once we control for trend?

![Hero figure](figures/hero.png)

## The question

Across six Sahel countries — Burkina Faso, Mali, Niger, Senegal, Chad, and Mauritania — millet and sorghum are the primary subsistence cereals, and drought is the dominant climate shock that perturbs them. This project asks: when a drought year happens, how much does cereal yield actually fall, *after* controlling for the long-run trend in yields? We are **not** building a yield-forecasting model — that requires more granular weather, planting, and market data than this study uses — and we are **not** attempting to attribute droughts themselves to climate change, which is a different methodology. We are estimating a single descriptive causal quantity: the average yield deviation around drought years in this region, with the standard event-study and difference-in-differences toolkit.

## Data

| Source | Granularity | Time coverage | Access |
|--------|-------------|---------------|--------|
| [FAOSTAT crop production & yields](https://www.fao.org/faostat/en/#data/QCL) | National (admin-0) annual | 1961–latest | Public |
| [CRU TS climate reanalysis](https://crudata.uea.ac.uk/cru/data/hrg/) | 0.5° grid monthly | 1901–latest | Public |
| [MODIS NDVI via Google Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/MODIS_006_MOD13Q1) (optional) | 250m monthly | 2000–latest | Public, registration |
| [GADM 4.1 administrative boundaries](https://gadm.org/) | Admin-0 / admin-1 polygons | Current | Public |

Access date: planned 2026-05-XX (to be filled when ingestion notebook is first run). **FAOSTAT revises historical figures** — pin the access date and write a parquet snapshot to `data/processed/faostat_snapshot_YYYY-MM-DD.parquet`; treat that snapshot as the canonical analytic input.

## Method

The analysis is a standard event-study design with a difference-in-differences cross-check. **Drought years** are identified using the Standardized Precipitation Index (SPI) computed from CRU TS precipitation, aggregated over each country's growing-season window. **Yields** come from FAOSTAT (millet, sorghum) by country and year, 1961–latest, log-transformed to give a percent-change interpretation and detrended against a country-specific time trend. The **event study** plots yield deviation from trend at event-time −5 through +5 around each country-year flagged as a drought, pooling across countries. The **DiD cross-check** compares yields in drought-hit countries against non-drought-hit countries in the same year, when granularity permits. The strongest critique of this approach is that "drought" defined on rainfall alone misses heat stress, planting-date shifts, and pest dynamics — all of which matter for yield — and that with six countries the panel is small enough that any one country's idiosyncrasies can drive the headline. Robustness checks address this directly.

## Methodological decisions

Each major data-processing decision was made by **diagnostic first, choice second**. The table below is an at-a-glance summary; the full five-part rationale (problem / diagnostic / options / decision + rationale / sensitivity) lives inline in `notebooks/02_main.ipynb`.

| Decision | Chose | Why (anchored in diagnostic) | Sensitivity |
|----------|-------|------------------------------|-------------|
| Drought definition (SPI threshold + growing-season window + single-month vs. multi-month) | *to be filled during implementation* | *anchored in diagnostic — see notebook §4* | *to be filled* |
| Trend specification (linear vs. quadratic vs. spline detrend; yield baselines drift over decades) | *to be filled during implementation* | *anchored in diagnostic — see notebook §5* | *to be filled* |
| Spatial weighting from CRU 0.5° grid to country aggregate (area-weighted vs. cropland-area-weighted vs. population-weighted) | *to be filled during implementation* | *anchored in diagnostic — see notebook §3* | *to be filled* |
| Inclusion / exclusion of partial drought years (one country in drought, others not) | *to be filled during implementation* | *anchored in diagnostic — see notebook §5* | *to be filled* |
| Robust standard errors (clustered by country, by year, two-way cluster, or wild bootstrap with n=6) | *to be filled during implementation* | *anchored in diagnostic — see notebook §6* | *to be filled* |
| FAOSTAT revision snapshot (which access-date snapshot is canonical) | *to be filled during implementation* | *anchored in revision-magnitude diagnostic — see notebook §3* | *to be filled* |

> Brand note: every choice above is an *educated* decision, not a convention. If you'd defend it differently, the diagnostic data is in the notebook — read it and tell me where I'm wrong.

## Findings

*To be filled during implementation. Each finding will be a falsifiable statement anchored in a specific number from the analysis (e.g., "a drought year reduces millet yield by X% relative to trend, 95% CI [Y, Z], averaged across six Sahel countries 1961–2024").*

## Limitations

*To be filled during implementation. Expected categories: rainfall-only drought definition misses heat stress and pest dynamics, six-country panel is small enough that any one country's idiosyncrasies can drive results, FAOSTAT yields are national annual aggregates that hide within-country heterogeneity, CRU TS is a reanalysis (interpolated from station data with known sparseness in the Sahel), and the design estimates an average effect — not country-specific or year-specific effects with the precision to inform policy in any single year.*

## Visual style

This project uses **matplotlib + seaborn** for the event-study plot, the DiD coefficient plots, the robustness panels, and the hero figure (event-time yield deviation ± 5 years around drought, pooled). Justification: this is the most "academic econ" project in the portfolio, and event-time coefficient plots with shaded confidence bands read best as static publication-quality figures. The deliverables here are figures that should land cleanly in a static PDF or a recruiter-facing LinkedIn post, not interactive widgets.

## How to reproduce

```bash
git clone <url>
cd 02-sahel-yields-climate

# Install with the stats + viz extras
pip install -e ".[viz,stats]"

# Run the main notebook
jupyter lab notebooks/02_main.ipynb
```

Full run time: ~X minutes (CRU TS download is the slow step, ~hundreds of MB, cached after first run; FAOSTAT and GADM are small).

## Files

- `notebooks/02_main.ipynb` — the analysis (start here)
- `notebooks/03_robustness.ipynb` — alternate drought definitions, alternate trend controls, partial-year sensitivity, alternate clustering of SEs
- `src/sahel_yields/data.py` — FAOSTAT, CRU TS, (optional) MODIS NDVI loaders with caching + snapshot pinning
- `src/sahel_yields/climate.py` — SPI computation, growing-season aggregation, gridcell → country spatial weighting
- `src/sahel_yields/econ.py` — event-study and DiD estimators with chosen SE clustering
- `src/sahel_yields/viz.py` — event-time plot, coefficient plot, robustness-panel helpers (matplotlib + seaborn)
- `src/sahel_yields/diagnostics.py` — diagnostic helpers used in decision blocks
- `data/raw/` — fetched source files (gitignored if large)
- `data/processed/faostat_snapshot_YYYY-MM-DD.parquet` — pinned FAOSTAT snapshot (committed)
- `data/processed/` — derived analytic dataset (parquet, committed)
- `figures/` — saved figures, including `hero.png` (committed)
- `tests/test_smoke.py` — minimal smoke tests

## Author

Muhanad — [LinkedIn](URL) · [Twitter](URL)
