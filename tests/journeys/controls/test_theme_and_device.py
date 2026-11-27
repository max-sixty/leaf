"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.controls.test_theme_and_device import (
    LEAF_CONTROLS,
    RESET,
)
from render_harness import leaf_page, open_page

pytestmark = pytest.mark.shifts_unsurveyed


def test_a_page_s_reset_leaves_leaf_s_controls_their_faces(browser, serve):
    """A page that brings its own framework takes no theme, and its reset, in the `base`
    layer Tailwind keeps it in, clears the page's own elements and leaves what Leaf
    draws as it was: Leaf's faces for its controls and widgets rank above the page's
    `base` (layer.py, `DOCUMENT_LAYER_ORDER`). Ranked below it, as a theme's rules
    are, the reset would take the padding, border and ground from Leaf's buttons and
    fields and the frame from a choice group."""
    body = (
        '<h1>Retention</h1><p id="own">Words.</p><p id="controls"></p>'
        '<lf-group id="window-q" label="How long?">'
        '<lf-options id="window"><lf-option id="short" label="30 days"><strong>30 days</strong> '
        ' In budget.</lf-option><lf-option id="long" label="90 days"><strong>90 days</strong> '
        " Covers the hold.</lf-option></lf-options></lf-group>"
    )
    faces = """() => Object.fromEntries(['press', 'field', 'window', 'short'].map((id) => {
        const style = getComputedStyle(document.getElementById(id));
        return [id, ['paddingTop', 'paddingLeft', 'borderTopWidth', 'borderTopLeftRadius',
            'backgroundColor', 'fontFamily'].map((p) => style[p])];
    }))"""
    plain = open_page(browser, serve(leaf_page("Retention", body), reading=False))
    plain.evaluate(LEAF_CONTROLS)
    expected = plain.evaluate(faces)
    assert expected["press"][0] != "0px" and expected["window"][2] != "0px", expected
    reset = open_page(
        browser,
        serve(
            leaf_page("Retention", body, head=f"<style>{RESET}</style>"), reading=False
        ),
    )
    reset.evaluate(LEAF_CONTROLS)
    assert reset.evaluate(faces) == expected
    assert (
        reset.evaluate("getComputedStyle(document.getElementById('own')).marginTop")
        == "0px"
    ), "the reset still clears the page's own elements"
    # An author's own layer outranks the theme's look.
    themed = open_page(
        browser,
        serve(
            leaf_page(
                "Retention",
                body,
                head="<style>@layer base { h1 { font-size: 80px; } }</style>",
            )
        ),
    )
    assert (
        themed.evaluate("getComputedStyle(document.querySelector('h1')).fontSize")
        == "80px"
    ), "a page's own layer lost to the theme"
