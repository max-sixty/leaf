"""Approved appearance across a real message delivery journey.

Run
``uv run pytest -n0 tests/*/test_render_thread_snapshots.py``. Baselines are
reviewed PNG images pinned in leaf-assets; run evidence stays in .tmp.
``leaf-dev thread-snapshots --help`` owns snapshot review and acceptance.
"""

import sys

import pytest
from render_harness import leaf_page, open_page


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux's fixed native font contract"
)
def test_linux_browser_resolves_the_fixed_fonts(browser, serve):
    """Native UI, serif and mono styles all use the faces the fixed fontconfig names."""
    faces = {
        "system-ui": ("DejaVu Sans", "DejaVuSans", "Oblique"),
        "serif": ("DejaVu Serif", "DejaVuSerif", "Italic"),
        "monospace": ("DejaVu Sans Mono", "DejaVuSansMono", "Oblique"),
    }
    styles = (
        ("normal", "normal"),
        ("bold", "normal"),
        ("normal", "italic"),
        ("bold", "italic"),
    )
    readings = {
        f"{name}-{weight}-{style}": (
            family,
            base
            + ("-" if weight == "bold" or style == "italic" else "")
            + ("Bold" if weight == "bold" else "")
            + (italic if style == "italic" else ""),
        )
        for name, (family, base, italic) in faces.items()
        for weight, style in styles
    }
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Font contract",
                "".join(
                    f'<p id="{name}">Native Leaf words 0123</p>' for name in readings
                ),
                head="<style>"
                + "".join(
                    f"#{name}-{weight}-{style} {{ font-family: {name}; "
                    f"font-weight: {weight}; font-style: {style}; }}"
                    for name in faces
                    for weight, style in styles
                )
                + "</style>",
            )
        ),
    )
    session = page.context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    root = session.send("DOM.getDocument")["root"]["nodeId"]
    for name, (family, postscript) in readings.items():
        node = session.send(
            "DOM.querySelector", {"nodeId": root, "selector": f"#{name}"}
        )["nodeId"]
        fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        assert {font["familyName"] for font in fonts} == {family}, (
            fonts,
            page.locator(f"#{name}").evaluate(
                "node => getComputedStyle(node).fontFamily"
            ),
        )
        assert all(not font["isCustomFont"] for font in fonts), fonts
        assert {font["postScriptName"] for font in fonts} == {postscript}, fonts
    session.detach()
