"""Reuse the canonical product fixtures, and the hooks that set and check the process
state a test runs under, without importing its tier-selection hooks."""

from conftest import (  # noqa: F401
    _browser,
    _page_pool,
    _playwright,
    browser,
    codex_env,
    dead_pid,
    firefox_browser,
    headless_shell,
    initialized_page,
    iphone,
    isolated_session,
    pytest_configure,
    pytest_runtest_setup,
    pytest_runtest_teardown,
    scrollbar_browser,
    sessionless,
    spawn,
    webkit_browser,
)

pytest_plugins = ("interact_support", "render_harness")
