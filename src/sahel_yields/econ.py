"""Econ layer — analytic panel assembly and event-study / DiD estimators.

Builds the country-year analytic panel (log yields + SPI/drought flags) and the
estimators. Built on ``linearmodels`` / ``statsmodels`` — not reinvented.

With n=6 clusters, conventional cluster-robust SEs are biased downward; the
wild-cluster bootstrap (Cameron, Gelbach & Miller 2008, via ``wildboottest``) is
the standard correction. The decision blocks that *choose* trend spec, SE
clustering, and partial-drought inclusion are notebook work — this module just
exposes the knobs.

Implemented in Session 4.
"""

# def build_panel(...): ...
# def detrend_yields(..., spec="linear"): ...
# def event_study(...): ...
# def did(...): ...
# def cluster_se(..., mode="country"): ...
