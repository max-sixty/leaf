"""The real-browser gate the everyday suite keeps."""

from pathlib import Path

import test_render
from conftest import interact

serve = test_render.serve

ROOT = Path(__file__).parent.parent


def test_a_shipped_page_passes_the_real_browser_gate(browser, serve):
    example = ROOT / "examples" / "ship-review.html"
    assert interact.render_version(browser, serve(example.read_text())) == []
