"""A custom element that is no `LeafElement` is a widget Leaf drives from outside.

`tests/fixtures/packages/verdict` holds `lf-verdict`, whose module imports nothing: Leaf
sets its `state` and its bound `notes`, hears the `lf-action` a press dispatches, and
reads each choice as a comment target from its `data-lf-part` mark
(module-plain-elements.md). `tests/fixtures/packages/shortlist` holds one with a pick
for each row, which `test_widget_composition.py` holds to Undo, a revision and an
export.
"""

from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import live_url
from render_harness import (
    consume_browser_errors,
    expect_obligations_answered,
    holding,
    http_error_console,
    leaf_page,
    open_page,
    round_trip,
    sending,
    undo,
    write,
)

from browser.threads import open_panel_thread
from leaf import data as data_model
from leaf import event_log
from leaf.schema import PLUGIN_ROOT

FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "packages"
VERDICT = FIXTURES / "verdict"
SHORTLIST = FIXTURES / "shortlist"

QUESTION = """
<h1 id="title">Release 4.2</h1>
<lf-group id="release" label="Ship 4.2 today?">
  <p id="premise">The fix is ready and the canary is clean.</p>
  <lf-verdict id="verdict" source="verdict-notes"></lf-verdict>
</lf-group>
"""
QUOTED = """
<lf-sample id="quoted" label="A quoted verdict">
  <lf-verdict id="quoted-verdict"></lf-verdict>
</lf-sample>
"""
HIRES = """
<lf-shortlist id="hires"><ul>
  <li><button type="button" commandfor="hires" command="--toggle" value="ada">Ada</button></li>
  <li><button type="button" commandfor="hires" command="--toggle" value="grace">Grace</button></li>
</ul></lf-shortlist>
"""

# What a module does to record or take back. It answers what the module knows as
# `dispatchEvent` returns: whether Leaf took the event, and the decision the element's
# state then holds. The outcome of a taken event lands on `window.sent`.
SEND = """([id, type, detail]) => {
  const element = document.getElementById(id);
  const event = new CustomEvent(type, {bubbles: true, composed: true, detail});
  element.dispatchEvent(event);
  window.sent = {taken: Boolean(event.delivery), settled: false};
  event.delivery?.then((admitted) =>
    Object.assign(window.sent, {settled: true, admitted}));
  return {taken: window.sent.taken, decided: element.state.decide?.value ?? null};
}"""


def send(page, widget, kind, detail):
    """Dispatch one event from `widget` as its module would. Answers what `SEND` read
    as `dispatchEvent` returned and, for an event Leaf took, what its `delivery`
    resolved to as `admitted`."""
    sent = page.evaluate(SEND, [widget, kind, detail])
    if sent["taken"]:
        page.wait_for_function("() => window.sent.settled")
        sent["admitted"] = page.evaluate("() => window.sent.admitted")
    return sent


def decide(value):
    return {"verb": "decide", "detail": {"value": value}}


def choice(page, widget, value):
    return page.locator(f'#{widget} [data-lf-part="choice:{value}"]')


def decided(page_dir, value, widget="verdict"):
    return append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": widget,
            "action": "decide",
            "detail": {"value": value},
        },
    )


def decisions(page_dir):
    return [
        (event["widget"], event["detail"]["value"])
        for event in event_log.read_events(page_dir)
        if event["kind"] == "action" and event["action"] == "decide"
    ]


def test_a_plain_element_draws_records_and_takes_a_comment(browser, serve):
    """Leaf sets the recorded decision and the bound notes on the element, a press is
    drawn before its delivery returns and then recorded, Undo takes a decision back,
    each moves the question on On Me, and a comment lands on the one choice aimed at."""
    url = live_url(serve(leaf_page("Release 4.2", QUESTION), packages=(VERDICT,)))
    data_model.cmd_data_set(
        serve.page_dir, "verdict-notes", {"ship": "Cheapest", "hold": "Safest"}
    )
    decided(serve.page_dir, "hold")
    page = open_page(browser, url)
    ship, hold = choice(page, "verdict", "ship"), choice(page, "verdict", "hold")

    expect(hold).to_have_attribute("aria-pressed", "true")
    expect(hold).to_have_attribute("aria-disabled", "false")
    expect(hold).to_have_attribute("title", "Safest")
    expect_obligations_answered(page, "1/1")
    data_model.cmd_data_set(
        serve.page_dir, "verdict-notes", {"ship": "Cheapest", "hold": "Slowest"}
    )
    expect(hold).to_have_attribute("title", "Slowest")

    undo(page)
    expect(hold).to_have_attribute("aria-pressed", "false")
    expect_obligations_answered(page, "0/1")

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    ship.click()
    holding(page, held, 1, "the decision whose delivery is held")
    assert ship.get_attribute("aria-pressed") == "true", (
        "the press waited for the server before it was drawn"
    )
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert decisions(serve.page_dir) == [("verdict", "hold"), ("verdict", "ship")]
    expect_obligations_answered(page, "1/1")

    hold.click(modifiers=["Alt"])
    expect(page.locator('[data-lf-mark~="pending"]')).to_have_attribute(
        "data-lf-part", "choice:hold"
    )
    write(page.locator(".lf-composer leaf-text"), "What would holding cost us?")
    page.keyboard.press("ControlOrMeta+Enter")
    round_trip(page)
    assert [
        event["anchor"]
        for event in event_log.read_events(serve.page_dir)
        if event["kind"] == "comment"
    ] == [{"section": "verdict", "visual": "choice:hold"}]
    assert ship.get_attribute("aria-pressed") == "true", "aiming at a choice decided it"


def test_a_plain_element_learns_what_became_of_each_event(browser, serve):
    """The state holds an action's result as `dispatchEvent` returns. `delivery`
    resolves to the event the server admitted, or to null where the server refuses it
    and the state returns. `lf-undo` takes back the action in force, on the unit it
    names where the verb has a state for each. A quoted element's event is never sent."""
    url = live_url(
        serve(
            leaf_page("Release 4.2", QUESTION + QUOTED + HIRES),
            packages=(VERDICT, SHORTLIST),
        )
    )
    page = open_page(browser, url)

    with sending(page, "the decision"):
        recorded = send(page, "verdict", "lf-action", decide("ship"))
    assert recorded["decided"] == "ship", "the state was set after dispatchEvent"
    admitted = recorded["admitted"]
    assert (admitted["action"], admitted["detail"]) == ("decide", {"value": "ship"})

    # The registry admits `ship` and `hold` alone.
    refused = send(page, "verdict", "lf-action", decide("later"))
    assert (refused["decided"], refused["admitted"]) == ("later", None)
    consume_browser_errors(page, http_error_console(400))
    round_trip(page)
    expect(choice(page, "verdict", "ship")).to_have_attribute("aria-pressed", "true")

    with sending(page, "the withdrawal"):
        withdrawn = send(page, "verdict", "lf-undo", {"verb": "decide"})
    assert withdrawn["decided"] is None
    assert withdrawn["admitted"]["undoes"] == admitted["id"]
    assert not send(page, "verdict", "lf-undo", {"verb": "decide"})["taken"]

    expect(choice(page, "quoted-verdict", "ship")).to_have_attribute(
        "aria-disabled", "true"
    )
    assert not send(page, "quoted-verdict", "lf-action", decide("ship"))["taken"]
    round_trip(page)
    assert decisions(serve.page_dir) == [("verdict", "ship")]

    ada, grace = (
        page.locator("#hires").get_by_role("button", name=name)
        for name in ("Ada", "Grace")
    )
    for candidate in (ada, grace):
        with sending(page, "the pick"):
            candidate.click()
    undoable = "key => document.getElementById('hires').state.pick.units[key].undoable"
    assert page.evaluate(undoable, "grace") is True
    assert not send(page, "hires", "lf-undo", {"verb": "pick"})["taken"]
    with sending(page, "the withdrawal"):
        send(page, "hires", "lf-undo", {"verb": "pick", "unit": "grace"})
    expect(grace).to_have_attribute("aria-pressed", "false")
    expect(ada).to_have_attribute("aria-pressed", "true")


def test_a_plain_element_in_an_agent_s_reply_draws_and_records(browser, serve):
    """A reply's markup mounts after the page has started, inside the thread's shadow
    tree, on a page that holds no such element: the element there is set its recorded
    decision, and its press reaches the page's log."""
    url = live_url(
        serve(
            leaf_page("Release 4.2", '<p id="premise">The fix is ready.</p>'),
            packages=(VERDICT,),
        )
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-ship",
            "author": "user",
            "revision": 1,
            "text": "When should this ship?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-ship",
            "revision": 1,
            "text": "Decide here.\n\n"
            '<lf-group id="reply-release" label="Ship 4.2 today?">'
            '<lf-verdict id="reply-verdict"></lf-verdict></lf-group>',
        },
    )
    decided(serve.page_dir, "hold", widget="reply-verdict")
    page = open_page(browser, url)
    open_panel_thread(page, "c-ship")
    ship = choice(page, "reply-verdict", "ship")
    expect(choice(page, "reply-verdict", "hold")).to_have_attribute(
        "aria-pressed", "true"
    )

    with sending(page, "the decision"):
        ship.click()
    expect(ship).to_have_attribute("aria-pressed", "true")
    assert decisions(serve.page_dir) == [
        ("reply-verdict", "hold"),
        ("reply-verdict", "ship"),
    ]
