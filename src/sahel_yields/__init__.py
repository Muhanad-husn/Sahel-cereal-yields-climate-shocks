"""sahel_yields — analysis package for Project 2.

Event-study + DiD estimation of how Sahel drought years depress millet and
sorghum yields across six countries (Burkina Faso, Mali, Niger, Senegal, Chad,
Mauritania).

Layers, in build order:
    data        — FAOSTAT, CRU TS, GADM, cropland loaders + snapshot pinning
    climate     — SPI computation, growing-season aggregation, spatial weighting
    econ        — analytic panel assembly, event-study / DiD estimators
    viz         — event-time plot, coefficient plot, robustness-panel helpers
    diagnostics — diagnostic helpers used inside the notebook decision blocks
"""

__version__ = "0.1.0"

# The six Sahel countries, with ISO3 codes used across the data loaders.
COUNTRIES = {
    "BFA": "Burkina Faso",
    "MLI": "Mali",
    "NER": "Niger",
    "SEN": "Senegal",
    "TCD": "Chad",
    "MRT": "Mauritania",
}
