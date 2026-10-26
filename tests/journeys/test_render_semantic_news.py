"""Meaningful notices from successfully presented server readings."""

from playwright.sync_api import expect
from render_harness import panel_field


def said(page):
    """The panel's empty field, whose placeholder says a passing notice."""
    return expect(panel_field(page))
