"""Visualization helpers — static publication-quality figures (matplotlib + seaborn).

This is the most academic-econ project in the portfolio; figures are static by
design. The plotting code was prototyped inline in ``02_main.ipynb`` and
``03_robustness.ipynb`` and consolidated here in Session 7 so both notebooks
draw on one consistent style.

Public helpers:
    set_style()         — apply the shared seaborn/matplotlib theme
    event_time_plot()   — stacked per-crop event-study panels with CI bands
                          (the hero figure)
    event_time_overlay()— several event-time curves overlaid per crop
                          (e.g. one curve per SPI threshold)
    coefficient_plot()  — a forest plot of point estimates ± CI
    robustness_panel()  — the 2x3 grid of et0 ± CI across robustness axes

The hero figure must read well at ~800x800 (LinkedIn thumbnail): visible
confidence bands, legible coefficient labels.

Implemented in Session 7.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Shared crop palette — used across every figure so colour means "crop"
# consistently between the hero and the robustness panels.
CROP_COLOR = {"millet": "#2a6f97", "sorghum": "#bc6c25"}

# A neutral grey used for zero lines, the drought-year band, and footnotes.
_GREY_LINE = "0.55"
_GREY_BAND = "0.92"
_GREY_TEXT = "0.45"


def set_style() -> None:
    """Apply the shared figure theme (call once per notebook, after imports)."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["figure.facecolor"] = "white"


def _crop_color(crop: str, fallback: str = "#444444") -> str:
    """Colour for a crop label, tolerant of unknown / display-cased names."""
    return CROP_COLOR.get(str(crop).lower(), fallback)


def event_time_plot(
    tables: dict[str, pd.DataFrame],
    *,
    title: str | None = None,
    subtitle: str | None = None,
    footnote: str | None = None,
    annotate_et0: bool = True,
    figsize: tuple[float, float] = (8.0, 8.0),
    savepath=None,
) -> plt.Figure:
    """Stacked event-study panels — one crop per row, with shaded CI bands.

    This is the hero-figure helper. Each value of ``tables`` is an
    :func:`sahel_yields.econ.event_study` result (columns ``event_time, coef,
    ci_low, ci_high``); the key is the panel title (e.g. ``"Millet"``).

    Parameters
    ----------
    tables : dict[str, pd.DataFrame]
        Panel title -> event-study table. Drawn top-to-bottom in dict order.
    title, subtitle, footnote : str, optional
        Figure suptitle, the grey line under it, and the small grey caption
        along the bottom.
    annotate_et0 : bool
        If True, label the event-time-0 coefficient as a percentage.
    figsize : tuple
        Figure size; the default 8x8 is the LinkedIn-thumbnail constraint.
    savepath : path-like, optional
        If given, save to this path at 100 dpi with a tight bounding box.

    Returns
    -------
    matplotlib.figure.Figure
    """
    n = len(tables)
    fig, axes = plt.subplots(n, 1, figsize=figsize, sharex=True)
    axes = np.atleast_1d(axes)

    for ax, (label, tab) in zip(axes, tables.items()):
        color = _crop_color(label)
        ax.axvspan(-0.4, 0.4, color=_GREY_BAND, zorder=0)       # drought year
        ax.axhline(0, color=_GREY_LINE, lw=1.0, zorder=1)
        ax.fill_between(tab.event_time, tab.ci_low, tab.ci_high,
                        color=color, alpha=0.22, zorder=2)
        ax.plot(tab.event_time, tab.coef, "-o", color=color, lw=2.2,
                ms=7, zorder=3)
        if annotate_et0:
            et0 = tab.loc[tab.event_time == 0].iloc[0]
            ax.annotate(f"{et0.coef * 100:+.1f}%", (0, et0.coef),
                        textcoords="offset points", xytext=(10, -16),
                        fontsize=12, fontweight="bold", color=color)
        ax.set_title(label, fontsize=14, fontweight="bold", loc="left")
        ax.set_ylabel("log-yield deviation")
        ax.set_xticks(range(int(tab.event_time.min()),
                            int(tab.event_time.max()) + 1))
        ax.margins(x=0.04)

    axes[-1].set_xlabel("years relative to drought (event time)")
    if title:
        fig.suptitle(title, fontsize=15, fontweight="bold", y=0.985)
    if subtitle:
        fig.text(0.5, 0.945, subtitle, ha="center", fontsize=10,
                 color="0.35")
    if footnote:
        fig.text(0.5, 0.012, footnote, ha="center", fontsize=8,
                 color=_GREY_TEXT)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93 if subtitle else 0.97))

    if savepath is not None:
        fig.savefig(savepath, dpi=100, bbox_inches="tight")
    return fig


def event_time_overlay(
    curves: dict[str, dict[str, pd.DataFrame]],
    *,
    styles: dict | None = None,
    legend_title: str | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (11.0, 4.2),
    savepath=None,
) -> plt.Figure:
    """Overlaid event-time curves — one panel per crop, several curves each.

    Used for the robustness event-time figure (one curve per SPI threshold).

    Parameters
    ----------
    curves : dict[str, dict[str, pd.DataFrame]]
        ``{crop: {curve_label: event_study_table}}``. One subplot per crop;
        each inner table is overlaid as a labelled line.
    styles : dict, optional
        ``{curve_label: linestyle}``; defaults to solid for every curve.
    legend_title : str, optional
        Title for the per-panel legend.
    title : str, optional
        Figure suptitle.
    figsize : tuple
    savepath : path-like, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    crops = list(curves)
    fig, axes = plt.subplots(1, len(crops), figsize=figsize, sharey=True)
    axes = np.atleast_1d(axes)

    for ax, crop in zip(axes, crops):
        color = _crop_color(crop)
        ax.axvspan(-0.4, 0.4, color=_GREY_BAND, zorder=0)
        ax.axhline(0, color=_GREY_LINE, lw=1.0)
        for clabel, es in curves[crop].items():
            ls = (styles or {}).get(clabel, "-")
            ax.plot(es.event_time, es.coef, ls, color=color, lw=1.9,
                    marker="o", ms=4, label=clabel)
        ax.set_title(crop, fontsize=12, fontweight="bold", loc="left")
        ax.set_xlabel("years relative to drought")
        ax.set_xticks(range(-5, 6))
    axes[0].set_ylabel("log-yield deviation")
    axes[0].legend(fontsize=8, title=legend_title)

    if title:
        fig.suptitle(title, fontsize=12, fontweight="bold")
    fig.tight_layout()
    if savepath is not None:
        fig.savefig(savepath, dpi=100, bbox_inches="tight")
    return fig


def coefficient_plot(
    estimates: pd.DataFrame,
    *,
    label_col: str = "label",
    coef_col: str = "coef",
    ci: tuple[str, str] = ("ci_low", "ci_high"),
    color_col: str | None = None,
    title: str | None = None,
    xlabel: str = "coefficient",
    figsize: tuple[float, float] | None = None,
    ax: plt.Axes | None = None,
    savepath=None,
) -> plt.Figure:
    """Horizontal forest plot of point estimates with confidence intervals.

    A general coefficient plot — used for the DiD cross-check (one row per
    crop) and reusable for any small set of estimates with CIs.

    Parameters
    ----------
    estimates : pd.DataFrame
        One row per coefficient; must contain ``label_col``, ``coef_col`` and
        the two ``ci`` columns.
    label_col, coef_col : str
        Column names for the row label and the point estimate.
    ci : tuple[str, str]
        Column names for the CI lower and upper bounds.
    color_col : str, optional
        Column whose value selects the crop colour; if omitted a single
        neutral colour is used.
    title, xlabel : str
        Plot title and x-axis label.
    figsize : tuple, optional
        Defaults to a height that scales with the number of rows.
    ax : matplotlib.axes.Axes, optional
        Draw into an existing axis instead of creating a figure.
    savepath : path-like, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    rows = estimates.reset_index(drop=True)
    if ax is None:
        if figsize is None:
            figsize = (7.0, 0.6 * len(rows) + 1.5)
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    ypos = np.arange(len(rows))[::-1]  # first row at the top
    ax.axvline(0, color=_GREY_LINE, lw=1.0, zorder=1)
    for y, (_, r) in zip(ypos, rows.iterrows()):
        color = _crop_color(r[color_col]) if color_col else "#444444"
        lo, hi = r[ci[0]], r[ci[1]]
        ax.plot([lo, hi], [y, y], color=color, lw=2.0, zorder=2)
        ax.plot(r[coef_col], y, "o", color=color, ms=8, zorder=3)
    ax.set_yticks(ypos)
    ax.set_yticklabels(rows[label_col])
    ax.set_xlabel(xlabel)
    ax.margins(y=0.15)
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")

    fig.tight_layout()
    if savepath is not None:
        fig.savefig(savepath, dpi=100, bbox_inches="tight")
    return fig


def robustness_panel(
    rob: pd.DataFrame,
    axes_order: list[str],
    *,
    crops: tuple[str, ...] = ("millet", "sorghum"),
    title: str | None = None,
    footnote: str | None = None,
    ncols: int = 3,
    figsize: tuple[float, float] = (15.0, 9.0),
    savepath=None,
) -> plt.Figure:
    """Grid of et0 ± CI across robustness axes — one subplot per axis.

    Each subplot perturbs one assumption; ``rob`` is the long accumulator
    built in ``03_robustness.ipynb`` with columns ``axis, label, crop, coef,
    ci_low, ci_high``.

    Parameters
    ----------
    rob : pd.DataFrame
        Long frame of refit results (one row per axis x label x crop).
    axes_order : list[str]
        Which ``axis`` values to draw, in order. Unused grid cells are blanked.
    crops : tuple[str, ...]
        Crops to plot side-by-side within each subplot.
    title, footnote : str, optional
    ncols : int
        Columns in the subplot grid (rows derived from len(axes_order)).
    figsize : tuple
    savepath : path-like, optional

    Returns
    -------
    matplotlib.figure.Figure
    """
    nrows = int(np.ceil(len(axes_order) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    flat = np.atleast_1d(axes).flatten()

    for ax, axis in zip(flat, axes_order):
        sub = rob[rob.axis == axis]
        labels = list(dict.fromkeys(sub.label))
        xpos = np.arange(len(labels))
        ax.axhline(0, color=_GREY_LINE, lw=1.0)
        for k, crop in enumerate(crops):
            off = (k - (len(crops) - 1) / 2) * 0.18
            g = sub[sub.crop == crop].set_index("label").loc[labels]
            ax.errorbar(xpos + off, g.coef.to_numpy(),
                        yerr=[(g.coef - g.ci_low).to_numpy(),
                              (g.ci_high - g.coef).to_numpy()],
                        fmt="o", color=_crop_color(crop), capsize=3,
                        lw=1.7, ms=6, label=crop)
        ax.set_xticks(xpos)
        ax.set_xticklabels(labels, fontsize=8, rotation=25, ha="right")
        ax.set_title(axis, fontsize=11, fontweight="bold", loc="left")
        ax.set_ylabel("event-study et0 (log-yield deviation)")
    flat[0].legend(fontsize=9, loc="lower left")
    for ax in flat[len(axes_order):]:        # blank any unused grid cells
        ax.axis("off")

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold")
    if footnote:
        fig.text(0.5, 0.01, footnote, ha="center", fontsize=9,
                 color=_GREY_TEXT)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    if savepath is not None:
        fig.savefig(savepath, dpi=100, bbox_inches="tight")
    return fig
