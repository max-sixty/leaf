"""Reuse the canonical product fixtures without importing its tier-selection hooks."""

from conftest import (  # noqa: F401
    _browser,
    _page_pool,
    _playwright,
    browser,
    codex_env,
    compiled_checkout,
    compiled_pages,
    dead_pid,
    failing_harness_programs,
    firefox_browser,
    headless_shell,
    initialized_page,
    iphone,
    isolated_session,
    scrollbar_browser,
    sessionless,
    spawn,
    webkit_browser,
)

pytest_plugins = ("interact_support", "render_harness")
