"""Latency goals consume admission and presentation of the gesture being measured."""

from leaf.render_checks import rendered
from leaf_dev.bench_latency import PROBE
from playwright.sync_api import expect
from render_harness import (
    BOARD_PAGE,
    consume_browser_errors,
    holding,
    leaf_page,
    open_page,
)


def test_delivery_benchmark_does_not_borrow_an_older_thread_receipt(browser, serve):
    page = open_page(
        browser,
        serve(
            leaf_page("Delivery benchmark", '<p id="p">A short passage.</p>'),
            comments=1,
        ),
        init_script=PROBE.read_text(),
    )
    page.locator(".lf-threads-toggle").click()
    thread = page.locator(".lf-thread").last
    thread.locator(".lf-thread-summary").click()
    expect(thread.locator(".lf-msg-sending")).to_have_text("Sent")
    field = thread.locator("leaf-text")
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json["kind"] == "reply"
            else route.continue_()
        ),
    )
    words = "Measure this reply's delivery."

    def send(*, type_words=True):
        page.evaluate(
            "goals => window.__leafBench.arm(goals)",
            [
                {"name": "painted", "fact": "message", "arg": words},
                {"name": "sent", "fact": "delivered", "arg": {"kind": "reply"}},
            ],
        )
        field.click()
        if type_words:
            page.keyboard.insert_text(words)
        with page.expect_request("**/api/event"):
            page.keyboard.press("Enter")
        page.wait_for_function("window.__leafBench.watch().goals[0].at !== null")
        holding(page, held, 1, "the benchmark reply")
        [route] = held
        attempt = route.request.post_data_json["attempt"]
        goal = page.evaluate("window.__leafBench.watch().goals[1]")
        assert goal["attempt"] == attempt
        assert goal["at"] is None
        expect(thread.locator('.lf-msg[aria-busy="true"]')).to_have_count(1)
        return route, attempt

    refused, first = send()
    refused.fulfill(
        status=400,
        json={"ok": False, "final": True, "attempt": first, "error": "refused"},
    )
    held.clear()
    expect(field).to_have_js_property("value", words)
    consume_browser_errors(page, "400")
    rendered(page)
    assert page.evaluate("window.__leafBench.watch().goals[1].at") is None
    page.evaluate("window.__leafBench.disarm()")

    # Resend the restored draft: only its actual admission completes delivery.
    admitted, second = send(type_words=False)
    with page.expect_response("**/api/event"):
        admitted.continue_()
    held.clear()
    page.wait_for_function("window.__leafBench.watch().goals[1].at !== null")
    goal = page.evaluate("window.__leafBench.watch().goals[1]")
    assert goal["attempt"] == second
    assert goal["at"] >= page.evaluate("window.__leafBench.watch().goals[0].at")
    expect(thread.locator('.lf-msg[aria-busy="true"]')).to_have_count(0)
    page.evaluate("window.__leafBench.disarm()")


def test_card_delivery_benchmark_tracks_the_card_unit_and_its_admission(browser, serve):
    page = open_page(browser, serve(BOARD_PAGE), init_script=PROBE.read_text())
    held = []
    page.route(
        "**/api/event",
        lambda route: (
            held.append(route)
            if route.request.post_data_json["kind"] == "action"
            else route.continue_()
        ),
    )
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.evaluate(
        "goals => window.__leafBench.arm(goals)",
        [
            {
                "name": "painted",
                "fact": "card",
                "arg": {"card": "card-heater", "to": "col-done"},
            },
            {
                "name": "sent",
                "fact": "delivered",
                "arg": {"kind": "action", "unit": "card-heater"},
            },
        ],
    )
    with page.expect_request("**/api/event"):
        page.keyboard.press("Enter")
    page.wait_for_function("window.__leafBench.watch().goals[0].at !== null")
    holding(page, held, 1, "the benchmark card move")
    [route] = held
    posted = route.request.post_data_json
    assert posted["widget"] == "sprint"
    assert posted["detail"]["unit"] == "card-heater"
    goal = page.evaluate("window.__leafBench.watch().goals[1]")
    assert goal["attempt"] == posted["attempt"]
    assert goal["at"] is None
    with page.expect_response("**/api/event"):
        route.continue_()
    held.clear()
    page.wait_for_function("window.__leafBench.watch().goals[1].at !== null")
    page.evaluate("window.__leafBench.disarm()")


def test_delivery_benchmark_reloads_with_its_exact_attempt(browser, serve):
    page = open_page(browser, serve(BOARD_PAGE), init_script=PROBE.read_text())
    held = []
    page.route("**/api/event", lambda route: held.append(route))
    grip = page.locator("#card-heater .lf-grip")
    grip.focus()
    page.keyboard.press("Enter")
    page.keyboard.press("ArrowRight")
    page.evaluate(
        "goals => window.__leafBench.arm(goals)",
        [{"name": "sent", "fact": "delivered", "arg": {"kind": "action"}}],
    )
    with page.expect_request("**/api/event"):
        page.keyboard.press("Enter")
    holding(page, held, 1, "the benchmark move before reload")
    [route] = held
    attempt = route.request.post_data_json["attempt"]
    # The server admits it while this document still awaits the answer. A reload
    # must observe that admission using the new document's diagnostic instance.
    assert route.fetch().ok
    goal = page.evaluate("window.__leafBench.watch().goals[0]")
    assert goal["attempt"] == attempt
    assert goal["at"] is None
    page.reload()
    rendered(page)
    page.wait_for_function("window.__leafBench.watch().goals[0].at !== null")
    goal = page.evaluate("window.__leafBench.watch().goals[0]")
    assert goal["attempt"] == attempt
    page.evaluate("window.__leafBench.disarm()")
