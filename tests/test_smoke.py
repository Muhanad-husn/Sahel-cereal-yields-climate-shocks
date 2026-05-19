"""Smoke tests — minimal checks for data loaders and econ estimators.

Filled in Session 7. For now, one trivial test confirms the package imports so
`pytest` has something to run.
"""


def test_package_imports():
    import sahel_yields

    assert sahel_yields.__version__
    assert len(sahel_yields.COUNTRIES) == 6
