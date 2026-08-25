"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import render_support
from conftest import interact

serve = render_support.serve

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert interact.render_version(browser, serve(example.read_text())) == []
