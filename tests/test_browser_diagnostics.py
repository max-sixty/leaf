"""Browser diagnostics retain the evidence available at the reporting boundary."""

import pytest
from leaf_dev.probe import console_errors
from leaf_dev.verify_site import observe_startup
from render_harness import consume_browser_errors, take_browser_errors, watched


@pytest.mark.parametrize("collector", [watched, console_errors, observe_startup])
def test_uncaught_errors_keep_the_throw_site_in_each_document(browser, collector):
    """Identical messages in separate documents must keep their distinct call sites."""
    page = browser.unwatched.new_page()
    errors = collector(page)
    page.route(
        "https://diagnostics.test/**",
        lambda route: route.fulfill(
            content_type="text/html", body='<iframe srcdoc="<p>Child</p>"></iframe>'
        ),
    )
    page.goto("https://diagnostics.test/")
    child = page.frames[1]
    for frame, function in ((page, "readCamera"), (child, "readChildCamera")):
        with page.expect_event("pageerror"):
            frame.evaluate(
                f"setTimeout(function {function}() {{ throw Error('camera failed'); }}, 0)"
            )
    if collector is watched:
        errors = take_browser_errors(page)
    assert len(errors) == 2, errors
    assert all("camera failed" in error for error in errors)
    assert "readCamera" in errors[0], errors
    assert "readChildCamera" in errors[1], errors


def test_expected_http_status_does_not_consume_an_unrelated_stack(browser):
    """A port or source line is evidence, never the reason an error is expected."""
    page = browser.new_page()
    with page.expect_event("pageerror"):
        page.evaluate(
            "setTimeout(function camera() { throw Error('unrelated fault'); }, 0)"
            "\n//# sourceURL=https://diagnostics.test:40041/camera.js"
        )
    with pytest.raises(AssertionError, match="unrelated fault"):
        consume_browser_errors(page, "400")
