"""Data loaders — FAOSTAT yields, CRU TS precip, GADM boundaries, cropland mask.

This module owns ingestion and snapshot pinning. Per CLAUDE.md, FAOSTAT revises
historical figures, so the main notebook reads a *pinned parquet snapshot*
(``data/processed/faostat_snapshot_YYYY-MM-DD.parquet``) — never the live API or
the raw zip directly. Re-fetching is an explicit, documented function.

Raw file locations are per ``docs/DATA_MANIFEST.md`` (the "AS DOWNLOADED"
section). CRU TS is a ~6 GB uncompressed .nc — subset to a Sahel bbox early.

Implemented in Session 2.
"""

# def load_faostat(...): ...
# def write_faostat_snapshot(...): ...
# def load_cru_pre(...): ...
# def load_gadm(...): ...
# def load_cropland(...): ...
