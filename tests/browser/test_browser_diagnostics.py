"""Browser diagnostics retain the evidence available at the reporting boundary."""

import pytest
from leaf_dev.commands.probe import console_errors
from leaf_dev.commands.verify_site import observe_startup
from playwright.sync_api import Error as PlaywrightError
from render_harness import (
    consume_browser_errors,
    judge_watches,
    take_browser_errors,
    watched,
)


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
    stacks = [error.values["text"] for error in errors]
    assert [error.code for error in errors] == ["page-exception"] * 2, stacks
    assert all("camera failed" in stack for stack in stacks)
    assert "readCamera" in stacks[0], stacks
    assert "readChildCamera" in stacks[1], stacks


def test_a_stack_location_does_not_consume_an_unrelated_error(browser):
    """A port or source line is evidence, never the reason an error is expected."""
    page = browser.new_page()
    with page.expect_event("pageerror"):
        page.evaluate(
            "setTimeout(function camera() { throw Error('unrelated fault'); }, 0)"
            "\n//# sourceURL=https://diagnostics.test:40041/camera.js"
        )
    with pytest.raises(AssertionError, match="unrelated fault"):
        consume_browser_errors(page, "40041")


@pytest.mark.parametrize("owner_read", [1, 2])
def test_health_judgement_releases_a_frame_removed_during_its_read(
    browser, monkeypatch, owner_read
):
    """A native frame can disappear between enumeration, owner lookup and drain.

    Hold the driver's owner request at the causal edge and remove the real iframe
    before forwarding it to Chrome; no scheduling speed decides whether it races.
    """
    page = browser.new_page()
    page.route(
        "https://diagnostics.test/**",
        lambda route: route.fulfill(
            content_type="text/html", body='<iframe srcdoc="<p>Child</p>"></iframe>'
        ),
    )
    page.goto("https://diagnostics.test/")
    child = page.frames[1]
    frame_element = child.frame_element
    reads = 0

    def remove_before_owner_read():
        nonlocal reads
        reads += 1
        if reads == owner_read:
            page.locator("iframe").evaluate("element => element.remove()")
        return frame_element()

    monkeypatch.setattr(child, "frame_element", remove_before_owner_read)
    judge_watches()
    assert reads == owner_read
    assert child.is_detached()


@pytest.mark.parametrize("call", ["start", "read"])
def test_health_judgement_releases_a_frame_removed_inside_its_evaluation(
    browser, monkeypatch, call
):
    """The child ends its own lifetime while the driver's native call is in flight."""
    page = browser.new_page()
    page.route(
        "https://diagnostics.test/**",
        lambda route: route.fulfill(
            content_type="text/html", body='<iframe srcdoc="<p>Child</p>"></iframe>'
        ),
    )
    page.goto("https://diagnostics.test/")
    child = page.frames[1]
    child.evaluate(
        """call => {
          const remove = () => {
            parent.removedDuringJudgement = call;
            parent.document.querySelector('iframe').remove();
          };
          let judgement;
          Object.defineProperty(window, 'lfWatchJudgement', {
            configurable: true,
            get: () => judgement,
            set(value) {
              judgement = value;
              if (call === 'start') remove();
              else {
                const drawn = value.ancestorsDrawn;
                Object.defineProperty(value, 'ancestorsDrawn', {
                  get: () => drawn,
                  set: remove,
                });
              }
            },
          });
        }""",
        call,
    )
    evaluate = child.evaluate
    failed_evaluations = []

    def observe_evaluation(*args, **kwargs):
        try:
            return evaluate(*args, **kwargs)
        except PlaywrightError as error:
            failed_evaluations.append((str(error), child.is_detached()))
            raise

    monkeypatch.setattr(child, "evaluate", observe_evaluation)
    judge_watches()
    assert page.evaluate("removedDuringJudgement") == call
    assert child.is_detached()
    assert failed_evaluations, "the in-flight native evaluation must fail"
    assert all(detached for _, detached in failed_evaluations), failed_evaluations


def test_health_judgement_still_fails_a_sensor_error(browser):
    page = browser.new_page()
    page.evaluate("""() => {
      window.savedJudgement = window.lfShiftsJudged;
      window.lfShiftsJudged = () => Promise.reject(Error('sensor failed'));
    }""")
    try:
        with pytest.raises(PlaywrightError, match="sensor failed"):
            judge_watches()
    finally:
        page.evaluate("window.lfShiftsJudged = window.savedJudgement")
