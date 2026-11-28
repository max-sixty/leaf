"""A custom element that is no `LeafElement` is a widget Leaf drives from outside.

`tests/fixtures/packages/verdict` holds `lf-verdict`, whose module imports nothing: Leaf
sets its `state` and its bound `notes`, hears the `lf-action` a press dispatches, and
reads each choice as a comment target from its `data-lf-part` mark
(module-plain-elements.md). `tests/fixtures/packages/shortlist` holds one with a pick
for each row, which `test_widget_composition.py` holds to Undo, a revision and an
export. `tests/fixtures/packages/controls` holds three components with no code written
for Leaf, each recorded because a declaration's `record` names the property that
holds its state: Web Awesome's select, which the page writes inside the `lf-select`
that keeps its value, `lf-level`, a range that announces every change of its
value, a script's set included, and `lf-pick-form`, a form of native radios or
checkboxes whose attribute record names each input's `checked`. The select's value
is also an output, which `lf-chosen` reads. The starter `leaf package init --widget`
writes is such an element too, tested here as the command writes it.
"""

import json

import pytest
from click.testing import CliRunner
from interact_support import append_carried_log_record, append_command
from playwright.sync_api import expect
from render_cases_interaction import NESTED_OBLIGATION_PAGE, live_url
from render_cases_navigation import actions
from render_harness import (
    consume_browser_errors,
    expect_obligations_answered,
    holding,
    http_error_console,
    leaf_page,
    navigate,
    open_page,
    panel_control,
    round_trip,
    said,
    sending,
    tab_onto,
    told,
    undo,
    write,
)

from browser.threads import open_panel_thread
from leaf.base.schema import PLUGIN_ROOT
from leaf.commands import cli as cli_model
from leaf.log import event_log
from leaf.records import page_data as page_data_model

FIXTURES = PLUGIN_ROOT / "tests" / "fixtures" / "packages"
VERDICT = FIXTURES / "verdict"
SHORTLIST = FIXTURES / "shortlist"
CONTROLS = FIXTURES / "controls"

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
SEND = """([id, type, detail, inside]) => {
  const element = document.getElementById(id);
  const event = new CustomEvent(type, {detail, bubbles: Boolean(inside)});
  (inside ? element.querySelector(inside) : element).dispatchEvent(event);
  window.sent = {taken: Boolean(event.delivery), settled: false};
  event.delivery?.then((admitted) =>
    Object.assign(window.sent, {settled: true, admitted}));
  return {taken: window.sent.taken, decided: element.state.decide?.value ?? null};
}"""


def send(page, widget, kind, detail, inside=None):
    """Dispatch one event from `widget` as its module would, or a bubbling one from
    the node `inside` it. Answers what `SEND` read as `dispatchEvent` returned and, for
    an event Leaf took, what its `delivery` resolved to as `admitted`."""
    sent = page.evaluate(SEND, [widget, kind, detail, inside])
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
            "facts": {"answered": bool(value)},
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
    page_data_model.cmd_data_set(
        serve.page_dir, "verdict-notes", {"ship": "Cheapest", "hold": "Safest"}
    )
    decided(serve.page_dir, "hold")
    page = open_page(browser, url)
    ship, hold = choice(page, "verdict", "ship"), choice(page, "verdict", "hold")

    expect(hold).to_have_attribute("aria-pressed", "true")
    expect(hold).to_have_attribute("aria-disabled", "false")
    expect(hold).to_have_attribute("title", "Safest")
    expect_obligations_answered(page, "1/1")
    page_data_model.cmd_data_set(
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
    names where the verb has a state for each, and one that bubbles to the element
    from a node inside it is the element's too. A quoted element's event is never sent,
    and neither is one from an element that has left the page."""
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
        withdrawn = send(page, "verdict", "lf-undo", {"verb": "decide"}, "button")
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

    # The page's last element, so its leaving moves nothing.
    gone = """detail => {
      const element = document.getElementById("hires");
      element.remove();
      const event = new CustomEvent("lf-action", {detail});
      element.dispatchEvent(event);
      return Boolean(event.delivery);
    }"""
    drop = {"verb": "pick", "detail": {"candidate": "ada", "picked": False}}
    assert not page.evaluate(gone, drop)


def test_an_event_that_reaches_nobody_is_its_elements_failure(browser, serve):
    """Leaf hears a hold at the document, so an `lf-hold` that does not bubble begins
    no hold and tells nobody. Leaf reports it as the failure of the element that
    dispatched it, and says nothing of one dispatched to bubble and be composed. In a
    shadow stage it reports one that bubbles and is not composed, which never leaves
    the stage."""
    url = live_url(serve(leaf_page("Release 4.2", QUESTION), packages=(VERDICT,)))
    page = open_page(browser, url)
    hold = """async ([options, staged]) => {
      let origin = document.getElementById("verdict");
      if (staged) {
        const {shadowStage} = await window.__lfWidgetApi();
        origin = document.createElement("lf-part");
        shadowStage(document.getElementById("verdict"), [origin]);
      }
      const event = Object.assign(new Event("lf-hold", options), {
        complete: Promise.resolve(),
      });
      origin.dispatchEvent(event);
    }"""

    page.evaluate(hold, [{"bubbles": True, "composed": True}, False])
    page.evaluate(hold, [{}, False])
    [reported] = consume_browser_errors(page, '<lf-verdict id="verdict"> failed: ')
    assert "`lf-hold` did not reach Leaf" in said(reported)

    page.evaluate(hold, [{"bubbles": True, "composed": True}, True])
    page.evaluate(hold, [{"bubbles": True}, True])
    [reported] = consume_browser_errors(page, "<lf-part> failed: ")
    assert "`lf-hold` did not reach Leaf" in said(reported)


def test_a_record_that_bubbles_belongs_to_the_nearest_widget(browser, serve):
    """A widget standing inside another may dispatch a bubbling `lf-action`, as a
    module written for a document listener does. The outer widget hears it too, and
    records nothing for it: the action is the inner widget's alone."""
    page = open_page(browser, live_url(serve(NESTED_OBLIGATION_PAGE)))
    pick = """() => document.getElementById("inner").dispatchEvent(
      new CustomEvent("lf-action", {
        bubbles: true,
        composed: true,
        detail: {verb: "choose", detail: {value: ["in-now"]}},
      }),
    )"""
    with sending(page, "the pick"):
        page.evaluate(pick)
    expect(page.locator("#in-now")).to_have_attribute("selected", "")
    assert [
        (event["widget"], event["detail"]) for event in actions(serve.page_dir)
    ] == [("inner", {"value": ["in-now"]})]


def test_the_starter_package_init_writes_draws_and_records(browser, serve, tmp_path):
    """The widget `package init --widget` writes works as written: it draws its two
    choices, a press shows as chosen and reaches the log, Undo takes it back, and a
    quoted copy draws its choices disabled and records nothing."""
    package = tmp_path / "starter"
    made = CliRunner().invoke(
        cli_model.cli, ["package", "init", str(package), "--widget", "lf-thing"]
    )
    assert made.exit_code == 0, made.output
    markup = (
        '<h1 id="title">Starter</h1><lf-thing id="thing"></lf-thing>'
        '<lf-sample id="quoted" label="A quoted starter">'
        '<lf-thing id="quoted-thing"></lf-thing></lf-sample>'
    )
    url = live_url(serve(leaf_page("Starter", markup), packages=(package,)))
    page = open_page(browser, url)
    yes, no = (
        page.locator("#thing").get_by_role("button", name=name)
        for name in ("Yes", "No")
    )
    expect(yes).to_have_attribute("aria-pressed", "false")
    expect(no).to_have_attribute("aria-pressed", "false")

    def chosen():
        return [
            (event["widget"], event["action"], event["detail"])
            for event in event_log.read_events(serve.page_dir)
            if event["kind"] == "action"
        ]

    with sending(page, "the choice"):
        yes.click()
    expect(yes).to_have_attribute("aria-pressed", "true")
    assert chosen() == [("thing", "choose", {"value": "yes"})]

    undo(page)
    expect(yes).to_have_attribute("aria-pressed", "false")

    quoted = page.locator("#quoted-thing").get_by_role("button", name="Yes")
    expect(quoted).to_have_attribute("aria-disabled", "true")
    # Playwright presses no disabled control, so the click is forced onto it.
    quoted.click(force=True)
    round_trip(page)
    expect(quoted).to_have_attribute("aria-pressed", "false")
    assert len(chosen()) == 1


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


PLAN = """
<h1 id="title">Seats</h1>
<lf-group id="plan" label="Which plan?">
  <p id="premise">Seats are billed monthly on every plan.</p>
  <lf-select id="plan-choice">
    <wa-select placeholder="Choose a plan">
      <wa-option value="starter">Starter</wa-option>
      <wa-option value="team">Team</wa-option>
      <wa-option value="scale">Scale</wa-option>
    </wa-select>
  </lf-select>
</lf-group>
"""
CHOSEN = '<lf-chosen id="plan-chosen" for="plan-choice"></lf-chosen>'
QUOTED_PLAN = """
<lf-sample id="quoted-plan" label="A quoted choice">
  <lf-select id="quoted-choice" value="starter">
    <wa-select>
      <wa-option value="starter">Starter</wa-option>
      <wa-option value="team">Team</wa-option>
    </wa-select>
  </lf-select>
</lf-sample>
"""


def chose(page_dir, value):
    """Record a choice of plan as another tab's pick reaches the log."""
    return append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "plan-choice",
            "action": "choose",
            "detail": {"value": value},
            "facts": {"answered": bool(value)},
        },
    )


def chosen(page_dir):
    return [
        (event["widget"], event["detail"]["value"])
        for event in event_log.read_events(page_dir)
        if event["kind"] == "action" and event["action"] == "choose"
    ]


def pick(page, widget, value):
    """Choose `value` in the select `widget` with the pointer. The select says
    `change` once it has drawn the choice, after the press returns."""
    select = page.locator(f"#{widget}")
    select.get_by_role("combobox").click()
    select.locator(f'wa-option[value="{value}"]').click()


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_component_with_no_code_for_leaf_records_what_its_declaration_names(
    engine, serve, request
):
    """The select holds its value in `value` and says `change`. The `lf-select` round
    it keeps that property on it, and the tag's `record` names the property. A pick by
    pointer and one by keyboard are each recorded and answer the question on On Me, a
    reload shows the recorded pick, and Undo takes it back and asks again. The select
    stands under the library's own tag, where an option whose words change finds it,
    so it shows the new words."""
    url = live_url(serve(leaf_page("Seats", PLAN), packages=(CONTROLS,)))
    page = open_page(request.getfixturevalue(engine), url)
    select = page.locator("#plan-choice")
    shown = select.get_by_role("combobox")
    expect_obligations_answered(page, "0/1")

    with sending(page, "the pick"):
        pick(page, "plan-choice", "team")
    assert chosen(serve.page_dir) == [("plan-choice", "team")]
    expect_obligations_answered(page, "1/1")

    select.locator('wa-option[value="team"]').evaluate(
        "node => { node.textContent = 'Team, billed yearly'; }"
    )
    expect(shown).to_have_value("Team, billed yearly")

    navigate(page, url)
    expect(shown).to_have_value("Team")
    expect_obligations_answered(page, "1/1")

    undo(page)
    expect(shown).to_have_value("")
    expect_obligations_answered(page, "0/1")

    tab_onto(shown)
    page.keyboard.press("Enter")
    expect(select.locator("wa-select")).to_have_js_property("open", True)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    with sending(page, "the pick"):
        page.keyboard.press("Enter")
    expect(shown).to_have_value("Scale")
    # The reload's set and the Undo's recorded nothing of their own.
    assert chosen(serve.page_dir) == [("plan-choice", "team"), ("plan-choice", "scale")]
    expect_obligations_answered(page, "1/1")


def test_a_recorded_property_shows_what_the_page_holds(browser, serve):
    """The element shows the recorded value whoever wrote it, and an event it
    dispatches while its property reads that value, as a later answer to Leaf's set
    does, records nothing. A change made where the user may not act, and one the
    server refuses, returns to the recorded value. A value the user is still changing
    survives a move of the reading that leaves the recorded value alone, and is
    recorded once the element says `change`. The select's `value` is also an output.
    `lf-chosen`, which reads it, shows each value Leaf sets, for which the element
    says no `change`, and the user's pick, whose `change` only bubbles to the element
    from the select inside it."""
    url = live_url(
        serve(leaf_page("Seats", PLAN + CHOSEN + QUOTED_PLAN), packages=(CONTROLS,))
    )
    chose(serve.page_dir, "scale")
    page = open_page(browser, url)
    select, quoted = page.locator("#plan-choice"), page.locator("#quoted-choice")
    reader = page.locator("#plan-chosen")
    expect(select).to_have_js_property("value", "scale")
    expect(reader).to_have_text("scale")

    chose(serve.page_dir, "starter")
    told(page)
    expect(select).to_have_js_property("value", "starter")
    expect(reader).to_have_text("starter")
    select.dispatch_event("change")

    # The quoted select says `change` before the trip of the pick behind it ends.
    pick(page, "quoted-choice", "team")

    def refuse(route):
        command = route.request.post_data_json
        if command["kind"] != "action":
            return route.continue_()
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": command["attempt"],
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse)
    with sending(page, "the pick the server refuses"):
        pick(page, "plan-choice", "team")
    page.unroute("**/api/event")
    consume_browser_errors(page, http_error_console(400))
    assert select.evaluate("node => node.value") == "starter"
    assert quoted.evaluate("node => node.value") == "starter"
    assert reader.text_content() == "starter"

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    pick(page, "plan-choice", "team")
    holding(page, held, 1, "the pick whose delivery is held")
    expect(reader).to_have_text("team")
    # A value still being changed, as a slider's is through a drag.
    select.evaluate("node => { node.value = 'scale'; }")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)
    assert select.evaluate("node => node.value") == "scale"
    with sending(page, "the value the user settled on"):
        select.dispatch_event("change")
    assert chosen(serve.page_dir) == [
        ("plan-choice", "scale"),
        ("plan-choice", "starter"),
        ("plan-choice", "team"),
        ("plan-choice", "scale"),
    ]


LEVEL = """
<h1 id="title">Report</h1>
<p id="premise">Set how much detail the report carries.</p>
<lf-level id="detail" label="Detail" min="0" max="10" value="3"></lf-level>
"""


def levels(page_dir):
    return [
        event["detail"]["value"]
        for event in event_log.read_events(page_dir)
        if event["kind"] == "action" and event["action"] == "set"
    ]


def test_what_an_element_says_from_inside_leaf_s_set_is_not_the_user_s_act(
    browser, serve
):
    """The range keeps its value within its scale and says `level-change` from
    inside every set that moves it, so as Leaf sets a recorded 70 it comes to hold 10
    and says so. Leaf records nothing of that, on arrival or as Undo sets the value
    again, and records the step the user makes, which the range says with the same
    event."""
    url = live_url(serve(leaf_page("Report", LEVEL), packages=(CONTROLS,)))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "detail",
            "action": "set",
            "detail": {"value": "70"},
        },
    )
    page = open_page(browser, url)
    level = page.locator("#detail")
    expect(level).to_have_js_property("value", "10")

    tab_onto(level.get_by_role("slider"))
    with sending(page, "the step"):
        page.keyboard.press("ArrowLeft")
    assert levels(serve.page_dir) == ["70", "9"]

    undo(page)
    expect(level).to_have_js_property("value", "10")
    tab_onto(level.get_by_role("slider"))
    with sending(page, "the step"):
        page.keyboard.press("ArrowLeft")
    assert levels(serve.page_dir) == ["70", "9", "9"]


PICKS = """
<h1 id="title">Release 4.2</h1>
<lf-group id="release-q" label="Ship 4.2 today?">
  <p id="premise">The fix is ready and the canary is clean.</p>
  <lf-pick-form id="release">
    <form>
      <label><input type="radio" name="release" id="release-ship" /> Ship</label>
      <label><input type="radio" name="release" id="release-hold" /> Hold</label>
    </form>
  </lf-pick-form>
</lf-group>
<lf-group id="platforms-q" label="Which platforms?">
  <p id="platforms-premise">The build passes on all three.</p>
  <lf-pick-form id="platforms">
    <form>
      <label><input type="checkbox" id="platforms-mac" checked /> macOS</label>
      <label><input type="checkbox" id="platforms-linux" /> Linux</label>
      <label><input type="checkbox" id="platforms-windows" /> Windows</label>
    </form>
  </lf-pick-form>
</lf-group>
"""
QUOTED_PICKS = """
<lf-sample id="quoted-picks" label="A quoted form">
  <lf-pick-form id="quoted-form">
    <form>
      <label><input type="checkbox" id="quoted-a" checked /> A</label>
      <label><input type="checkbox" id="quoted-b" /> B</label>
    </form>
  </lf-pick-form>
</lf-sample>
"""
MAC, LINUX, WINDOWS = "platforms-mac", "platforms-linux", "platforms-windows"


def pick_set(page_dir, widget, *ids):
    """Record a set of picks as another tab's reaches the log."""
    return append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": widget,
            "action": "choose",
            "detail": {"value": [*ids]},
            "facts": {"answered": bool(ids)},
        },
    )


def checked(page, widget):
    """The ids of the inputs in `widget` whose `checked` reads true, in page order."""
    return page.locator(f"#{widget} input").evaluate_all(
        "inputs => inputs.filter((input) => input.checked).map((input) => input.id)"
    )


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_form_of_native_inputs_records_the_set_its_declaration_names(
    engine, serve, request
):
    """The form's inputs hold their own `checked`, and the tag's attribute record
    names that property. One radio picked and several checkboxes picked are each
    recorded as the ids of the checked inputs and answer their questions on On Me. A
    reload shows the recorded sets, over the pick the markup writes. Undo takes the
    last pick back, and the first back to the markup's own, which answers nothing. A
    pick by keyboard is recorded as a pointer's is, and a second press on the picked
    radio records the empty set, which asks again."""
    url = live_url(serve(leaf_page("Release 4.2", PICKS), packages=(CONTROLS,)))
    page = open_page(request.getfixturevalue(engine), url)
    expect_obligations_answered(page, "0/2")
    assert checked(page, "platforms") == [MAC]

    with sending(page, "the pick"):
        page.get_by_label("Hold").check()
    expect_obligations_answered(page, "1/2")
    with sending(page, "the second platform"):
        page.get_by_label("Linux").check()
    with sending(page, "the third platform"):
        page.get_by_label("Windows").check()
    picks = [
        ("release", ["release-hold"]),
        ("platforms", [MAC, LINUX]),
        ("platforms", [MAC, LINUX, WINDOWS]),
    ]
    assert chosen(serve.page_dir) == picks
    expect_obligations_answered(page, "2/2")

    navigate(page, url)
    assert checked(page, "release") == ["release-hold"]
    assert checked(page, "platforms") == [MAC, LINUX, WINDOWS]
    expect_obligations_answered(page, "2/2")

    undo(page)
    assert checked(page, "platforms") == [MAC, LINUX]
    undo(page)
    assert checked(page, "platforms") == [MAC]
    expect_obligations_answered(page, "1/2")
    undo(page)
    assert checked(page, "release") == []
    expect_obligations_answered(page, "0/2")

    tab_onto(page.locator(f"#{LINUX}"))
    with sending(page, "the platform"):
        page.keyboard.press("Space")
    ship = page.locator("#release-ship")
    tab_onto(ship)
    with sending(page, "the pick"):
        page.keyboard.press("Space")
    expect(ship).to_be_checked()
    expect_obligations_answered(page, "2/2")
    with sending(page, "the cleared pick"):
        page.keyboard.press("Space")
    expect(ship).not_to_be_checked()
    expect_obligations_answered(page, "1/2")
    # The reload's sets and the Undos' recorded nothing of their own.
    assert chosen(serve.page_dir) == [
        *picks,
        ("platforms", [MAC, LINUX]),
        ("release", ["release-ship"]),
        ("release", []),
    ]


def test_a_recorded_set_shows_what_the_page_holds(browser, serve):
    """The inputs show the recorded set whoever wrote it, over the pick the markup
    writes, and an event the form hears while they read that set records nothing. A
    change made where the user may not act returns to the recorded set. The server
    refuses a pick of an input the form lacks, and the inputs return to the set the
    page holds. Undo names another tab's pick by the inputs' labels."""
    url = live_url(
        serve(leaf_page("Release 4.2", PICKS + QUOTED_PICKS), packages=(CONTROLS,))
    )
    pick_set(serve.page_dir, "platforms", LINUX)
    page = open_page(browser, url)
    assert checked(page, "platforms") == [LINUX]

    pick_set(serve.page_dir, "platforms", MAC, WINDOWS)
    told(page)
    assert checked(page, "platforms") == [MAC, WINDOWS]
    page.locator("#platforms").dispatch_event("change")

    page.locator("#quoted-b").click()
    assert checked(page, "quoted-form") == ["quoted-a"]

    lacking = {"verb": "choose", "detail": {"value": [MAC, "platforms-bsd"]}}
    refused = send(page, "platforms", "lf-action", lacking)
    assert (refused["taken"], refused["admitted"]) == (True, None)
    consume_browser_errors(page, http_error_console(400))
    round_trip(page)
    assert checked(page, "platforms") == [MAC, WINDOWS]
    assert chosen(serve.page_dir) == [
        ("platforms", [LINUX]),
        ("platforms", [MAC, WINDOWS]),
    ]
    # Undo names the pick by the inputs' labels, as it names an option by its label.
    expect(
        panel_control(page, "command:history.undo").locator(".lf-fp-label")
    ).to_have_text("Undo: chose “macOS”, “Windows” in “Which platforms?”")


RESET_PICKS = PICKS.replace(
    '<label><input type="checkbox" id="platforms-windows" /> Windows</label>',
    '<label><input type="checkbox" id="platforms-windows" /> Windows</label>'
    '<button type="reset" id="platforms-reset">Reset</button>',
)


def test_a_native_pick_says_itself_returns_when_refused_and_records_a_reset(
    browser, serve
):
    """Until the server answers, Undo names a pick of a checkbox by its label, as the
    widget's words for the change. A pick the server refuses returns the checkbox to
    the set the page holds. A form's reset changes its inputs with no event of
    theirs, and the set it leaves is recorded as the user's pick."""
    url = live_url(serve(leaf_page("Release 4.2", RESET_PICKS), packages=(CONTROLS,)))
    page = open_page(browser, url)

    held = []
    page.route("**/api/event", lambda route: held.append(route))
    page.get_by_label("Linux").check()
    holding(page, held, 1, "the pick whose answer is held")
    undo_row = panel_control(page, "command:history.undo").locator(".lf-fp-label")
    expect(undo_row).to_have_text("Undo: Chose “Linux”")
    page.keyboard.press("Escape")
    held[0].continue_()
    page.unroute("**/api/event")
    round_trip(page)

    def refuse(route):
        command = route.request.post_data_json
        if command["kind"] != "action":
            return route.continue_()
        route.fulfill(
            status=400,
            json={
                "ok": False,
                "attempt": command["attempt"],
                "error": "refused before append",
                "final": True,
            },
        )

    page.route("**/api/event", refuse)
    with sending(page, "the pick the server refuses"):
        page.get_by_label("Windows").check()
    page.unroute("**/api/event")
    consume_browser_errors(page, http_error_console(400))
    assert checked(page, "platforms") == [MAC, LINUX]

    with sending(page, "the set the reset leaves"):
        page.locator("#platforms-reset").click()
    assert checked(page, "platforms") == [MAC]
    assert chosen(serve.page_dir) == [("platforms", [MAC, LINUX]), ("platforms", [MAC])]


LABEL_CASES = json.loads((PLUGIN_ROOT / "tests" / "label_cases.json").read_text())


def test_the_browser_reads_a_controls_label_as_the_server_does(browser):
    """Which `<label>` names a control, as the browser's own `labels` gives it, the
    relation the chrome names a control by (`accessibleName`) and the server reads
    off the markup (`passages.control_labels`, `tests/label_cases.json`)."""
    page = browser.new_page()
    for case in LABEL_CASES:
        page.set_content(f"<!doctype html><body>{case['markup']}</body>")
        read = page.evaluate(
            """(ids) => Object.fromEntries(ids.map((id) => [id,
                (document.getElementById(id).labels?.[0]?.textContent ?? "")
                  .replace(/\\s+/g, " ").trim()]))""",
            list(case["labels"]),
        )
        assert read == case["labels"], case["id"]


WORKER = {
    "lf-plain-worker": {
        "description": "A worker, which says what its agent last reported.",
        "attributes": {
            "properties": {"state": {"enum": ["idle", "working"]}},
            "required": ["id", "state"],
        },
        "content": "empty",
        "verbs": {
            "state": {
                "writer": "agent",
                "unit": "widget",
                "text": True,
                "record": {"kind": "value", "attr": "state"},
            }
        },
    }
}
WORKER_MODULE = """import { readReports } from "/runtime/widget-api.js";
customElements.define("lf-plain-worker", class extends HTMLElement {
  #line = null;
  set state({ state }) {
    const { phase, reports } = readReports(this);
    if (phase !== "ready") return;
    const said = reports.findLast((report) => report.disposition === "effective");
    this.#line ??= this.appendChild(document.createElement("output"));
    this.#line.textContent = `${state.value}: ${said?.text ?? "no report yet"}`;
  }
});"""


def roster(serve):
    """A page holding one worker, `wren`, that has reported nothing."""
    return live_url(
        serve(
            leaf_page(
                "Roster", '<lf-plain-worker id="wren" state="idle"></lf-plain-worker>'
            ),
            layer_registry=WORKER,
            layer_widgets={"lf-plain-worker.js": WORKER_MODULE},
        )
    )


def report_working(page, page_dir):
    """Log wren's report that it is working, and wait for the page to take it in."""
    report = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(page_dir),
            "wren",
            "state",
            "value=working",
            "text=checking the mount prices",
        ],
    )
    assert report.exit_code == 0, report.output
    told(page)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_plain_element_draws_its_reports_once_they_are_ready(engine, serve, request):
    """An element with no base class reads its own reports in its `state` setter. A
    reading is not ready inside the set that a report moves, so the element draws
    nothing then, and Leaf sets its `state` again once the reports are ready: on
    arrival, as a report comes in, and on a page that opens holding one."""
    url = roster(serve)
    page = open_page(request.getfixturevalue(engine), url)
    worker = page.locator("#wren output")
    expect(worker).to_have_text("idle: no report yet")

    report_working(page, serve.page_dir)
    expect(worker).to_have_text("working: checking the mount prices")

    navigate(page, url)
    expect(worker).to_have_text("working: checking the mount prices")


def test_a_plain_element_that_left_waits_again_for_the_work_it_left_with(
    browser, serve
):
    """A report waits for work under way inside its element. The element leaves and
    returns before that work is in: Leaf sets its `state` again as it returns, and it
    is still told to wait, since the work it left with holds its preparation again
    before it draws. It draws the report once the work is in."""
    page = open_page(browser, roster(serve))
    worker = page.locator("#wren output")
    expect(worker).to_have_text("idle: no report yet")
    page.evaluate(
        """async () => {
          const {PendingTaskEvent} = await window.__lfLibImport('pending-task.js');
          const {readApplicationPresentation} = await window.__lfCheckApi();
          window.wren = document.querySelector('#wren');
          window.home = wren.parentNode;
          window.work = Promise.withResolvers();
          window.preparing = () => readApplicationPresentation().pending
            .includes('widget:wren:preparation');
          // Said from inside the element, the work is its preparation.
          wren.querySelector('output').dispatchEvent(new PendingTaskEvent(work.promise));
        }"""
    )
    report_working(page, serve.page_dir)
    assert worker.text_content() == "idle: no report yet"

    page.evaluate("() => { wren.remove(); }")
    page.wait_for_function("() => !preparing()")
    page.evaluate("() => { home.append(wren); }")
    # The return has drawn by the time the work it left with is presented again.
    page.wait_for_function("() => preparing()")
    assert worker.text_content() == "idle: no report yet"

    page.evaluate("() => { work.resolve(); }")
    expect(worker).to_have_text("working: checking the mount prices")
