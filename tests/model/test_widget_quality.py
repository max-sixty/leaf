"""Widget quality examples and their data contracts."""

from known_widget_findings import KNOWN, PACKAGES


def test_every_known_finding_names_a_bundled_package():
    """An entry under a package that is gone is never compared, so never deleted."""
    assert set(KNOWN) <= {package.name for package in PACKAGES}
