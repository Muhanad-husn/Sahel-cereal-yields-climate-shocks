"""Climate layer — SPI from CRU precip, with gridcell-to-country aggregation.

Builds the Standardized Precipitation Index (SPI) used to flag drought
country-years. CRU TS is on a 0.5deg grid; rolling it up to a country aggregate
requires a spatial-weighting choice (load-bearing decision #3): this module
implements BOTH area-overlap weighting and cropland-area weighting; the
diagnostic comparing them lives in the main notebook, not here.

Growing-season windows are country-specific (FAO crop calendar) and hard-coded
as a dict with the citation in the docstring.

Implemented in Session 3.
"""

# def gridcells_to_country(...): ...
# def growing_season_precip(...): ...
# def compute_spi(...): ...
# def flag_drought(spi, threshold=-1.0): ...
