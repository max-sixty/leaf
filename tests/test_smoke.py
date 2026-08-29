"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import render_support
from leaf.render_gate import version as render_gate_model

serve = render_support.serve

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert render_gate_model.render_version(browser, serve(example.read_text())) == []
