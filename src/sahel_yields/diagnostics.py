"""Diagnostic helpers — operationalize the five-part decision blocks.

Per CLAUDE.md Principle 4 ("Show Your Work"), every meaningful data-processing
decision is presented in five parts; part 2 is *diagnostic code that explores
the data to inform the choice*. These helpers are that diagnostic step,
factored out so the notebook stays readable.

Mirrors the canonical helpers from the monorepo ``_template/`` — they are kept
deliberately generic (operate on plain Series / DataFrames) so the same six
functions serve every decision block. Project-specific one-off diagnostics stay
inline in the notebook; anything reused across blocks lives here.

Implemented in Session 5A.
"""

from __future__ import annotations

import pandas as pd


# --- Missingness ------------------------------------------------------------
def missingness_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing-value count and percentage.

    Part-2 diagnostic for any "do we need to impute / drop?" choice point.
    Returns one row per column, sorted most-missing first.
    """
    n = len(df)
    miss = df.isna().sum()
    out = pd.DataFrame(
        {"n_missing": miss, "pct_missing": (miss / n * 100.0).round(2)}
    )
    return out.sort_values("n_missing", ascending=False)


def missingness_pattern(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Distinct missingness patterns across ``columns`` and how often each occurs.

    Each row is a combination of present/absent flags (``True`` = present); the
    ``count`` column is how many rows of ``df`` share that pattern. Reveals
    whether missingness is monotone, co-occurring, or scattered.
    """
    cols = columns or list(df.columns)
    present = df[cols].notna()
    patterns = present.value_counts().reset_index(name="count")
    return patterns.sort_values("count", ascending=False).reset_index(drop=True)


# --- Distributions ----------------------------------------------------------
def distribution_summary(s: pd.Series) -> pd.Series:
    """Compact distributional fingerprint of a numeric series.

    n, mean, sd, min, the quartiles, max, plus skew — enough to judge spread,
    tail behaviour and asymmetry without a plot.
    """
    s = pd.to_numeric(s, errors="coerce").dropna()
    return pd.Series(
        {
            "n": int(s.size),
            "mean": s.mean(),
            "sd": s.std(),
            "min": s.min(),
            "q25": s.quantile(0.25),
            "median": s.median(),
            "q75": s.quantile(0.75),
            "max": s.max(),
            "skew": s.skew(),
        }
    )


def distribution_compare(named: dict[str, pd.Series]) -> pd.DataFrame:
    """Side-by-side :func:`distribution_summary` for several named series.

    ``named`` maps a label to a series; the result is one column per label, so
    two candidate constructions of the same quantity can be eyeballed together.
    """
    return pd.DataFrame({name: distribution_summary(s) for name, s in named.items()})


# --- Transform / alternative comparison -------------------------------------
def before_after(before: pd.Series, after: pd.Series, *, name: str = "value") -> pd.DataFrame:
    """Distribution of a quantity before vs after a transform, with the delta.

    Two columns (``before``, ``after``) of :func:`distribution_summary` stats
    plus a ``delta`` column — the part-5 sensitivity check for any transform
    (detrending, log, winsorising).
    """
    b = distribution_summary(before).rename("before")
    a = distribution_summary(after).rename("after")
    out = pd.concat([b, a], axis=1)
    out["delta"] = out["after"] - out["before"]
    out.attrs["name"] = name
    return out


def compare_alternatives(alternatives: dict[str, dict]) -> pd.DataFrame:
    """Tabulate named alternatives by their summary metrics.

    ``alternatives`` maps an option label (e.g. ``"SPI < -1.0"``) to a dict of
    metric → value. The result is one row per option, one column per metric —
    the part-3 "options considered" table that the part-4 decision points back
    to. Columns that are fully numeric are coerced to numeric dtype.
    """
    out = pd.DataFrame.from_dict(alternatives, orient="index")
    for col in out.columns:
        converted = pd.to_numeric(out[col], errors="coerce")
        if converted.notna().all():
            out[col] = converted
    return out
