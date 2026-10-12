"""The widget quality report (`leaf/render_gate/widget_quality.py`): Leaf's own widgets
held to it, and `package check --render` telling a package's author what it found. And
the first box a widget keeps where the report's served examples do not reach: a tab set
opening on a later panel, and an export."""

from known_widget_findings import KNOWN, PACKAGES


def test_every_known_finding_names_a_bundled_package():
    """An entry under a package that is gone is never compared, so never deleted."""
    assert set(KNOWN) <= {package.name for package in PACKAGES}
