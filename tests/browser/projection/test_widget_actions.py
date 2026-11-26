"""Widget actions and decisions: verbs local to their owning widget, declared obligation
conditions, replay and undo, and suggestion settlements retiring their slots."""

import json
import re

import pytest
from interact_support import (
    add_test_widget,
    append_carried_log_record,
    append_command,
    trial_family,
    wait_for,
)
from playwright.sync_api import expect
from render_cases_interaction import (
    RELATIVE_WIDGET_PAGE,
    RETIRED_WIDGET_PAGE,
    SUGGESTION_PAGE,
    TWO_HOLDER_PAGE,
    drifting_widget,
    live_url,
)
from render_cases_layout import unfolded_button
from render_cases_navigation import actions, composer_quote, painted
from render_harness import (
    EXAMPLE_PACKAGES,
    consume_browser_errors,
    expect_obligations_answered,
    leaf_page,
    navigate,
    open_page,
    panel_settled,
    panel_view,
    post_event,
    resized,
    round_trip,
    sending,
    show_done,
    stamp_page,
    suggestion_control,
    told,
    undo,
    wait_for_revision,
    write,
)

from browser.threads import open_panel_thread
from leaf.base.schema import PLUGIN_ROOT
from leaf.log import event_log as events_model
from leaf.source import render_checks as render_checks_model
from leaf.source.render_checks import rendered
from leaf_dev.browser import choose_threads_in_panel, open_on_me

pytestmark = pytest.mark.shifts_unsurveyed

# `lf-test-list` orders its own `lf-test-entry` members: no element stands between.
SORTABLE = PLUGIN_ROOT / "tests" / "fixtures" / "packages" / "sortable"
STEPS = """
<h1 id="title">Release steps</h1>
<lf-test-list id="steps">
  <lf-test-entry id="tag">Tag the release</lf-test-entry>
  <lf-test-entry id="notes">Write the notes</lf-test-entry>
  <lf-test-entry id="ship">Ship it</lf-test-entry>
</lf-test-list>
"""


def expect_steps(page, ids):
    for index, identity in enumerate(ids):
        expect(page.locator("#steps > lf-test-entry").nth(index)).to_have_id(identity)


@pytest.mark.parametrize("engine", ["browser", "firefox_browser"])
def test_a_list_that_is_its_own_container_keeps_the_order_the_user_gives_it(
    engine, serve, request
):
    """A list whose entries stand directly in it records a drag and a keyboard move
    with itself as the container, shows both after a reload, and Undo takes the
    last one back, naming the list once."""
    url = live_url(serve(leaf_page("Release steps", STEPS), packages=(SORTABLE,)))
    page = open_page(request.getfixturevalue(engine), url)
    expect_steps(page, ["tag", "notes", "ship"])

    with sending(page, "the drag"):
        page.locator("#ship").drag_to(
            page.locator("#tag"), target_position={"x": 8, "y": 2}
        )
    expect_steps(page, ["ship", "tag", "notes"])

    page.locator("#notes").focus()
    with sending(page, "the key move"):
        page.keyboard.press("Alt+ArrowUp")
    expect_steps(page, ["ship", "notes", "tag"])
    assert [
        (event["detail"]["unit"], event["detail"]["value"])
        for event in actions(serve.page_dir)
    ] == [("ship", "steps"), ("notes", "steps")]

    navigate(page, url)
    expect_steps(page, ["ship", "notes", "tag"])

    undo(page)
    expect_steps(page, ["ship", "tag", "notes"])
    expect(page.locator(".lf-live")).to_contain_text(
        "Undone: moved “Write the notes” in the test-list"
    )


def thread_head(page, page_dir, skipping=None):
    """The head of the page's first thread, or first but `skipping`, in that thread's
    view in the panel, once every gesture the page sent has been delivered: the words
    the thread quotes and where they stand."""
    round_trip(page)
    thread = next(
        event["id"]
        for event in events_model.read_events(page_dir)
        if event["kind"] == "comment" and event["id"] != skipping
    )
    return open_panel_thread(page, thread).locator(".lf-thread-quote-head")


def test_a_projected_attribute_opens_an_obligation_captured_from_authored_markup(
    browser, serve
):
    """Predicate operands survive upgrade even when the obligation starts closed."""
    entry = {
        "description": "A test-owned conditional Ask.",
        "attributes": {
            "properties": {
                "phase": {"enum": ["closed", "open"]},
            },
            "required": ["id", "phase"],
        },
        "content": "markup",
        "verbs": {
            "phase": {
                "unit": "widget",
                "record": {"kind": "value", "attr": "phase"},
            },
            "answer": {
                "detail": {"properties": {}},
                "unit": "widget",
            },
        },
        "awaits": {
            "when": {"phase": ["open"]},
            "value": "answer",
        },
        "example": '<lf-conditional id="example" phase="closed">Choose.</lf-conditional>',
    }
    module = """\
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-conditional", class extends LeafElement {
  render() { keeps(this, "phase", this.state.phase.value); }
});
"""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Conditional Ask",
                '<lf-conditional id="question" phase="closed">Choose.</lf-conditional>',
            ),
            layer_registry={"lf-conditional": entry},
            layer_widgets={"lf-conditional.js": module},
        ),
    )
    expect(page.locator(".lf-fp-leaf")).to_have_attribute(
        "aria-label", re.compile(r"^Page menu · ")
    )
    view = page.locator(panel_view("queue"))
    items = ".lf-fp-on-item[data-lf-key^='widget:']"

    for phase, count in (("open", 1), ("closed", 0)):
        append_command(
            serve.page_dir,
            {
                "kind": "action",
                "author": "user",
                "revision": 1,
                "widget": "question",
                "action": "phase",
                "detail": {"value": phase},
                "answered": False,
            },
        )
        told(page)
        if count:
            expect_obligations_answered(page, "0/1")
        # The phase move is the agent's to answer. The obligation leaves the user's
        # queue when its condition closes, retaining its withdrawn line under Done.
        # An open view keeps its cards seated, so each reading is a fresh opening.
        if view.count():
            page.locator(".lf-fp-close").click()
            panel_settled(page, open=False)
        open_on_me(page)
        panel_settled(page, view="queue")
        expect(view.locator(f'{items}[data-lf-list="you"]')).to_have_count(count)
        if not count:
            show_done(page)
        withdrawn = view.locator(f'{items}[data-lf-list="done"]')
        expect(withdrawn).to_have_count(1 - count)
        if not count:
            expect(withdrawn).to_contain_text("Withdrawn")


def test_a_user_verb_and_an_agent_verb_stand_side_by_side(
    browser, serve, tmp_path, monkeypatch
):
    """A verb has one writer, so a user's action and a worker's report on one widget
    fold on coordinates of their own: each paints its own record, every log record is
    ready once its coordinate is committed, and undoing the user's action restores
    the authored value without replacing the node."""
    monkeypatch.chdir(tmp_path)
    add_test_widget(tmp_path / ".leaf", "lf-tally", upgrade=True)
    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    declarations["lf-tally"]["attributes"]["properties"]["count"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    declarations["lf-tally"]["example"] = (
        '<lf-tally id="tally-example" count="0"><pre>Nothing yet.</pre></lf-tally>'
    )
    declarations["lf-tally"]["attributes"]["properties"]["restated"] = {
        "type": "boolean"
    }
    declarations["lf-tally"]["attributes"]["properties"]["overruled"] = {
        "type": "boolean"
    }
    declarations["lf-tally"]["attributes"]["properties"]["seen"] = {
        "type": "string",
        "pattern": "^[0-9]+$",
    }
    record = {"kind": "value", "attr": "count"}
    declarations["lf-tally"]["verbs"] = {
        "set": {
            "unit": "widget",
            "record": record,
        },
        "observe": {
            "writer": "agent",
            "unit": "widget",
            "record": {"kind": "value", "attr": "seen"},
        },
    }
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-tally.js").write_text(
        """\
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-tally", class extends LeafElement {
  render() {
    const { state } = this;
    if (state.set.value === null) this.removeAttribute("count");
    else keeps(this, "count", state.set.value);
    if (state.observe.value === null) this.removeAttribute("seen");
    else keeps(this, "seen", state.observe.value);
  }
});
"""
    )
    url = serve(RELATIVE_WIDGET_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    for kind, author, widget, action, count in [
        ("action", "user", "tally-fitted", "set", "7"),
        ("report", "agent", "tally-fitted", "observe", "9"),
        ("action", "user", "tally-seen", "set", "5"),
    ]:
        append_command(
            serve.page_dir,
            {
                "kind": kind,
                "author": author,
                "revision": 1,
                "widget": widget,
                "action": action,
                "detail": {"value": count},
            },
        )

    page = open_page(browser, url)
    expect(page.locator("#tally-fitted")).to_have_attribute("count", "7")
    expect(page.locator("#tally-fitted")).to_have_attribute("seen", "9")
    expect(page.locator("#tally-seen")).to_have_attribute("count", "5")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "3")
    kept = page.evaluate(
        """async () => {
          const {state} = (await window.__lfWidgetApi())
            .widgetController(document.getElementById('tally-fitted')).read();
          return [state.set.value, state.observe.value];
        }"""
    )
    assert kept == ["7", "9"]

    original = page.locator("#tally-seen").element_handle()
    page.keyboard.press("ControlOrMeta+z")
    round_trip(page)
    assert page.locator("#tally-seen").get_attribute("count") == "0"
    assert original.evaluate("node => node === document.getElementById('tally-seen')")


LEAF_OWNER = """\
import { nothing } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
customElements.define("lf-owner", class extends LeafElement {
  render() {
    for (const [id, order] of Object.entries(this.state.move.value)) {
      const zone = document.getElementById(id);
      for (const child of order) {
        const member = document.getElementById(child);
        if (member.parentElement !== zone) zone.append(member);
      }
    }
    return nothing;
  }
});
"""


LEAF_PIECE = """\
import { nothing } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-piece", class extends LeafElement {
  render() {
    keeps(this, "pinned", this.state.move.value);
    return nothing;
  }
});
"""


def test_lit_parent_moves_before_controller_members_render_selection(
    browser, serve, tmp_path, monkeypatch
):
    """A later-upgraded parent moves a member before its destination clears it."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    for tag, upgrade in (("lf-owner", True), ("lf-zone", True), ("lf-piece", False)):
        add_test_widget(package, tag, upgrade=upgrade)
    path = package / "registry.json"
    declarations = json.loads(path.read_text())
    markup = (
        '<lf-owner id="owner"><lf-zone id="north">'
        '<lf-piece id="piece" selected>Piece</lf-piece></lf-zone>'
        '<lf-zone id="south"></lf-zone></lf-owner>'
    )
    declarations["lf-owner"].update(
        {
            "content": "members",
            "verbs": {
                "move": {
                    "unit": "unit",
                    "record": {"kind": "position", "within": "lf-zone"},
                }
            },
            "example": markup,
        }
    )
    zone = declarations["lf-zone"]
    zone.update(
        {
            "content": "members",
            "owners": ["lf-owner"],
        }
    )
    zone["attributes"]["properties"]["restated"] = {"type": "boolean"}
    zone["verbs"] = {
        "choose": {
            "unit": "widget",
            "record": {"kind": "attribute", "attr": "selected"},
        }
    }
    piece = declarations["lf-piece"]
    piece["owners"] = ["lf-zone"]
    piece["attributes"]["properties"]["selected"] = {"type": "boolean"}
    for declaration in (zone, piece):
        declaration.pop("example", None)
    path.write_text(json.dumps(declarations))
    (package / "widgets/lf-owner.js").write_text(
        'await customElements.whenDefined("lf-zone");\n' + LEAF_OWNER
    )
    (package / "widgets/lf-zone.js").write_text("""\
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define("lf-zone", class extends LeafElement {
  render() {
    for (const piece of this.querySelectorAll("lf-piece"))
      keeps(piece, "selected", this.state.choose.value.includes(piece.id) ? "" : null);
  }
});
""")
    page = open_page(
        browser, serve(leaf_page("Moved selection", markup), packages=["./.leaf"])
    )
    expect(page.locator("#piece")).to_have_attribute("selected", "")
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "owner",
            "action": "move",
            "detail": {"unit": "piece", "value": "south", "rank": "1"},
        },
    )
    expect(page.locator("#south > #piece")).to_have_count(1)
    expect(page.locator("#piece")).not_to_have_attribute("selected", "")


def test_a_part_and_its_own_widget_keep_same_named_verbs_independent(
    browser, serve, tmp_path, monkeypatch
):
    """Verbs are local to their owning widget contract. A container's `move` of part
    `piece` and that element's own `move` therefore coexist even though unit and verb
    text are identical; both owners reconcile, and a remounted part has its owner
    place it."""
    monkeypatch.chdir(tmp_path)
    for tag, upgrade in (
        ("lf-owner", True),
        ("lf-zone", False),
        ("lf-piece", True),
    ):
        add_test_widget(tmp_path / ".leaf", tag, upgrade=upgrade)

    registry_path = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(registry_path.read_text())
    owner = declarations["lf-owner"]
    owner["content"] = "members"
    owner["verbs"] = {
        "move": {
            "unit": "unit",
            "record": {
                "kind": "position",
                "within": "lf-zone",
            },
        }
    }
    owner["example"] = (
        '<lf-owner id="sample-owner"><lf-zone id="sample-zone">'
        '<lf-piece id="sample-piece" pinned="no">Piece</lf-piece>'
        "</lf-zone></lf-owner>"
    )
    zone = declarations["lf-zone"]
    zone["owners"] = ["lf-owner"]
    zone["content"] = "members"
    zone.pop("example", None)
    piece = declarations["lf-piece"]
    piece["owners"] = ["lf-zone"]
    piece["attributes"]["properties"] |= {
        "pinned": {"type": "string"},
    }
    piece["attributes"].setdefault("required", []).append("pinned")
    piece["verbs"] = {
        "move": {
            "unit": "widget",
            "record": {"kind": "value", "attr": "pinned"},
        }
    }
    piece.pop("example", None)
    registry_path.write_text(json.dumps(declarations, indent=2))
    (tmp_path / ".leaf" / "widgets" / "lf-owner.js").write_text(LEAF_OWNER)
    (tmp_path / ".leaf" / "widgets" / "lf-piece.js").write_text(LEAF_PIECE)
    html = leaf_page(
        "owned coordinates",
        """<h1>Owned coordinates</h1><lf-owner id="owner">
<lf-zone id="zone-a"><lf-piece id="piece" pinned="no">Piece</lf-piece></lf-zone>
<lf-zone id="zone-b"></lf-zone></lf-owner>""",
    )
    url = serve(html, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    for event in (
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "owner",
            "action": "move",
            "detail": {"unit": "piece", "value": "zone-b", "rank": "0i"},
        },
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "piece",
            "action": "move",
            "detail": {"value": "yes"},
        },
    ):
        append_command(serve.page_dir, event)

    page = open_page(browser, url)
    expect(page.locator("#zone-b > #piece")).to_have_count(1)
    expect(page.locator("#piece")).to_have_attribute("pinned", "yes")
    kept = page.evaluate(
        """async () => {
          const {widgetController} = await window.__lfWidgetApi();
          return ['owner', 'piece'].map(id => {
            const widget = document.getElementById(id);
            const {state} = widgetController(widget).read();
            return [id, (state.move.units?.piece ?? state.move).action];
          });
        }"""
    )
    assert kept == [["owner", "move"], ["piece", "move"]]
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "2")
    # A data renderer can remount a part while retaining its owner. Both owning
    # coordinates must render onto the new node even when no winning event changed.
    page.evaluate("""() => {
      const piece = document.createElement('lf-piece');
      piece.id = 'piece';
      piece.setAttribute('pinned', 'no');
      document.getElementById('piece').replaceWith(piece);
      document.getElementById('zone-a').append(piece);
    }""")
    response = post_event(
        page,
        url.rsplit("/versions/", 1)[0] + "/api/event",
        data={
            "kind": "comment",
            "revision": 1,
            "text": "Check the refreshed piece",
        },
    )
    assert response.ok, response.text()
    told(page)
    expect(page.locator("#zone-b > #piece")).to_have_count(1)
    expect(page.locator("#piece")).to_have_attribute("pinned", "yes")


def test_a_page_at_rest_is_read_across_a_widgets_own_root(
    browser, serve, tmp_path, monkeypatch
):
    """Whether the page is still moving is asked of every tree the page is in.

    A document answers for its own tree alone: `document.getAnimations()` returns
    nothing for an element inside a widget's shadow root, and `{subtree: true}` on
    the root element returns nothing either. A widget drawing itself into place in
    there grows the host box the gate's own readings measure, so a reading that
    asked the document would call that page still and read it mid-move — the fault
    the wait exists to prevent, surviving inside the one place a widget is most
    likely to draw."""
    url = serve(
        drifting_widget(tmp_path, monkeypatch, deep=True),
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = open_page(browser, url)
    page.wait_for_function("() => document.body.dataset.lfUpgraded === '1'")

    # The status dot pulses forever and is deliberately not the page moving, so the
    # control asks after a finite end rather than after an empty list.
    assert (
        page.evaluate(
            "() => document.getAnimations().filter(a => Number.isFinite("
            "  a.effect?.getComputedTiming().endTime)).length"
        )
        == 0
    ), "the document tree already answers for this one, so the reading proves nothing"
    # The mover is the widget's own box inside its root, and the reading names it
    # under the nearest element the author can address it by (`render-checks/locate.js`).
    assert render_checks_model.evaluate_probe(page, "moving") == [
        "<div> in <lf-drift id=drift-note>"
    ]


def test_a_module_that_stages_bare_text_is_refused_in_its_own_name(
    browser, serve, tmp_path, monkeypatch
):
    """The one text these walks reach with no element over it, and the page says whose.

    A widget may render the page's words into its own shadow root, and the passage walk
    crosses in after them. What it cannot take is a text node put straight on the root:
    `parentElement` is null there, so those words have no block to sit in, no cell to be
    fenced by and nothing for a mark to hang on, and admitting them would split the
    page's reading from the file's. The page refuses to present at all, which is the
    loud direction — but a refusal arriving as `Cannot read properties of null
    (reading 'closest')` over a blank page names neither the widget nor the mistake,
    which is a bug report against leaf rather than against the module that caused it.

    The refusal is also final. Raised again by every later reader of the page's words,
    it would be thrown by each repaint frame, key and selection, while the notice waited
    for a server update that cannot fix a module's mistake. The first refusal declares
    the page failed: its widgets fall back at once, the notice says the page itself has
    a problem, and later readers read past the refused words, so the agent and the
    console hear it once."""
    url = serve(
        drifting_widget(tmp_path, monkeypatch, bare=True),
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
    )
    page = browser.new_page(
        viewport=render_checks_model.RENDER_VIEWPORT, color_scheme="light"
    )
    # The first thing the page says in anger, whatever that turns out to be: waiting
    # for the wording under test would make a page that says something else read as a
    # page that says nothing, and the message is the whole subject here.
    with page.expect_console_message(lambda message: message.type == "error") as caught:
        page.goto(url, wait_until="commit")
    refusal = caught.value.text

    assert '<lf-drift id="drift-note">' in refusal, refusal
    assert "They came over the fence" in refusal, refusal
    assert "closest" not in refusal, (
        "the refusal is still a property name, which reads as leaf being broken: "
        + refusal
    )
    notice = page.get_by_role("status").filter(has_text="Leaf couldn't start")
    expect(notice).to_have_text(
        "Leaf couldn't start: this page has a problem its author needs to fix."
    )
    assert not page.evaluate(
        "() => document.documentElement.hasAttribute('data-lf-interactive')"
    ), "the page kept its widgets' upgraded boxes rather than its readable fallback"

    page.mouse.wheel(0, 300)
    page.set_viewport_size({"width": 900, "height": 700})
    page.keyboard.press("j")
    page.mouse.click(200, 200)
    page.keyboard.press("k")
    # A selection is read by the composing surface rather than a frame or a key, and
    # reads across the widget into the paragraphs after it.
    start = page.locator("#drift-title").bounding_box()
    end = page.locator("#drift-week").bounding_box()
    page.mouse.move(start["x"] + 2, start["y"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(end["x"] + 40, end["y"] + end["height"] / 2, steps=5)
    page.mouse.up()
    page.locator("#drift-four").dblclick()
    rendered(page)
    assert page.evaluate("() => document.body.dataset.lfPresented") is None, (
        "the page presented anyway, so the words with nothing over them are in it"
    )
    errors = consume_browser_errors(page, '<lf-drift id="drift-note">')
    assert len(errors) == 1, errors
    reports = wait_for(
        lambda: [
            event["text"].splitlines()[0]
            for event in events_model.read_events(serve.page_dir)
            if event["kind"] == "error"
        ],
        bool,
        failure="the agent never heard the refusal",
    )
    assert errors[0].code == "console-error", errors
    assert reports == [
        errors[0].values["text"].splitlines()[0].removeprefix("leaf: ")
    ], reports


def test_replay_signatures_exclude_settlement_and_other_runtime_paint(browser, serve):
    """A rendered settlement cannot become authored state through a DOM signature.

    The application snapshot owns the outcome; data-lf-state and the other runtime
    attributes only make that publication visible and must not replace a retained node.
    """
    url = serve(SUGGESTION_PAGE)
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-refill")).to_have_attribute("data-lf-state", "accept")

    signatures = page.evaluate("""async () => {
        const { shallowSigs } = await window.__lfCheckApi();
        const widget = document.getElementById("sug-refill");
        const read = () => shallowSigs(document.body).get(widget.id);
        const decided = read();
        widget.setAttribute("data-lf-user-override", "probe");
        const painted = read();
        widget.setAttribute("data-lf-space", "wide");
        const marked = read();
        widget.removeAttribute("data-lf-state");
        const undecided = read();
        return { decided, painted, marked, undecided };
    }""")
    assert signatures["decided"] == signatures["painted"], (
        "runtime-owned pending paint became authored state in the replay signature"
    )
    assert signatures["decided"] == signatures["marked"], (
        "a declared mark's paint became authored state in the replay signature"
    )
    assert signatures["decided"] == signatures["undecided"], (
        "rendered settlement paint became authored state in the replay signature"
    )
    positions = page.evaluate("""async () => {
        const { shallowSigs } = await window.__lfCheckApi();
        const root = document.createElement("div");
        root.id = "signature-root";
        root.innerHTML = '<i></i><div id="first"><b id="nested"></b></div>' +
            '<div class="lf-ui" id="runtime-control"></div>' +
            '<div class="lf-ui" id="runtime-parent">' +
                '<lf-options id="thread-widget"></lf-options></div>' +
            '<i></i><div id="second"></div>';
        const before = Object.fromEntries(shallowSigs(root));
        root.insertBefore(document.createElement("i"), root.firstElementChild);
        root.querySelector("#runtime-parent").id = "replacement-runtime-parent";
        root.querySelector("#runtime-control").replaceWith(
            Object.assign(document.createElement("div"), {
                className: "lf-ui",
                id: "replacement-runtime-control",
            }),
        );
        const painted = Object.fromEntries(shallowSigs(root));
        root.prepend(root.lastElementChild);
        const moved = Object.fromEntries(shallowSigs(root));
        return { before, painted, moved };
    }""")
    assert positions["before"] == positions["painted"]
    assert set(positions["before"]) == {
        "signature-root",
        "first",
        "nested",
        "thread-widget",
        "second",
    }
    assert {
        identity
        for identity, signature in positions["before"].items()
        if positions["moved"][identity] != signature
    } == {"first", "second"}
    assert json.loads(positions["before"]["nested"])["parent"] == "first"
    assert json.loads(positions["before"]["thread-widget"])["parent"] == ""


def test_a_decision_detaches_the_threads_on_what_it_took_off_the_page(browser, serve):
    """A decision detaches the thread on what it removed, by element or by passage.

    An element anchor asks whether its section is still on the user's page, and for a
    suggestion that settles to nothing — an insertion refused — the markup's presence is
    the wrong answer: the thread would read as attached while its outline drew nothing.
    Pending, the wrapper is a thing to point at; refused, the thread detaches like any
    passage the decision removed.

    ✓ and ✗ are the visible affordances, but a proposal a user half-agrees with wants a
    sentence, not a verdict: the proposed words are ordinary page text, so selecting them
    and commenting works like anywhere else. Then the decision they eventually take has
    to reach the thread — rejecting retires the text the comment was made on, and a
    comment pointing into markup nobody can see has to read as detached rather than as a
    live mark that jumps nowhere."""
    url = serve(SUGGESTION_PAGE)
    on_element = append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "user",
            "revision": 1,
            "text": "Is thistle worth a feeder?",
            "anchor": {"section": "sug-thistle"},
        },
    )
    page = open_page(browser, url)
    resized(page, 1920, 900)
    expect(thread_head(page, serve.page_dir)).not_to_have_attribute(
        "data-lf-detached", ""
    )
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    # Pending, the outline hangs on a box the user can see, and it is read as a box
    # rather than as a class: a class on a wrapper that was display: contents would
    # paint no outline, so the half of this docstring about drawing nothing would be
    # true of the attached case too. The wrapper draws its own box, so the mark is the
    # wrapper itself rather than the slot.
    shown = page.locator("#sug-thistle.lf-mark-el")
    expect(shown).to_have_count(1)
    box = shown.evaluate("el => el.getBoundingClientRect().toJSON()")
    assert box["width"] > 0 and box["height"] > 0, (
        f"the attached thread's outline hangs on a box of no size: {box}"
    )
    unfolded_button(
        suggestion_control(page, "sug-thistle", "reject", visible=False)
    ).click()
    expect(thread_head(page, serve.page_dir)).to_have_attribute("data-lf-detached", "")
    expect(page.locator("#sug-thistle.lf-mark-el")).to_have_count(0)
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    # Beside its passage again, where the comment's box becomes its card on Send.
    choose_threads_in_panel(page, on=False)

    page.evaluate("""() => {
        const range = document.createRange();
        range.selectNodeContents(document.querySelector('#sug-refill lf-new'));
        getSelection().removeAllRanges();
        getSelection().addRange(range);
    }""")
    page.keyboard.press("c")
    page.wait_for_selector(".lf-fab-input", state="visible")
    page.locator(".lf-fab-input").click()
    page.wait_for_selector(".lf-composer", state="visible")
    quoted = composer_quote(page)["text"]
    assert quoted.strip("“”") == "Refill a feeder when its camera shows it half-empty."
    write(page.locator(".lf-composer leaf-text"), "Half-empty by whose reading?")
    page.keyboard.press("ControlOrMeta+Enter")

    inline = page.locator(".lf-margin-thread")
    expect(inline.locator(".lf-msg-body")).to_have_text("Half-empty by whose reading?")
    thread = thread_head(page, serve.page_dir, skipping=on_element["id"])
    expect(thread).to_be_visible()
    expect(thread).not_to_have_attribute("data-lf-detached", "")
    page.locator(".lf-fp-close").click()
    panel_settled(page, open=False)
    assert (
        painted(page, "lf-mark")
        == "Refill a feeder when its camera shows it half-empty."
    )

    unfolded_button(
        suggestion_control(page, "sug-refill", "reject", visible=False)
    ).click()
    expect(
        thread_head(page, serve.page_dir, skipping=on_element["id"])
    ).to_have_attribute("data-lf-detached", "")
    assert painted(page, "lf-mark") == "", (
        "a mark stayed painted on text the user's own decision removed"
    )


def test_a_decision_already_in_the_log_retires_its_slot_at_load(browser, serve):
    """The test above takes its decisions in front of the user, on a page that has
    been up long enough for everything to have arrived. Here the log holds it before
    the page opens, which is what puts the anchor pass's skip list on the clock: the
    registry names the slot a decision retires (`retired-when`), and the registry
    arrives over the network, after the module that reads it has evaluated. Replay
    settles the suggestion on the first poll, so the pass that runs with it has to be
    skipping lf-old already — or the page opens with a live mark on words the user
    accepted away."""
    url = serve(
        SUGGESTION_PAGE, anchored=[("replace", "Refill every feeder each morning.")]
    )
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-refill",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-refill lf-old")).to_be_hidden()
    expect(thread_head(page, serve.page_dir)).to_have_attribute("data-lf-detached", "")
    assert painted(page, "lf-mark") == "", (
        "the first pass anchored inside a slot the user's decision had retired"
    )


def test_a_throwing_settlement_still_reaches_the_layers_terminal_state(
    browser, serve, tmp_path, monkeypatch
):
    """A module failure is terminal rather than an endless replay retry, and the
    layer's generic settlement contract still applies: readiness, the holder mark,
    and the visible fail-soft box must agree on that one consumed action."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    (tmp_path / ".leaf" / "widgets" / "lf-trial.js").write_text(
        """\
import {LeafElement} from "/runtime/lib/leaf-element.js";
customElements.define("lf-trial", class extends LeafElement {
  render() { throw new Error("trial replay broke"); }
});
"""
    )
    url = serve(TWO_HOLDER_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "th-cache",
            "action": "decide",
            "detail": {"outcome": "shelve"},
        },
    )

    page = open_page(browser, url)
    expect(page.locator("#th-cache")).to_have_attribute("data-lf-state", "shelve")
    expect(page.locator("#th-cache .lf-error")).to_contain_text("trial replay broke")
    expect(page.locator("body")).to_have_attribute("data-lf-applied", "1")
    consume_browser_errors(page, '<lf-trial id="th-cache"> failed: trial replay broke')


def test_a_label_in_a_retired_slot_leaves_the_page_with_the_slot(browser, serve):
    """A decided suggestion's losing slot is off the page, and a label inside it goes
    too. The label is the one thing that reads back over chrome — a settled group's
    summary says "Settled: …" and declares those words the page's, which is what lets a
    user point at it anywhere else — so the rule has to stop at the slot: a marker that
    outranks a look must not outrank a decision, or a quote lands in the half the user
    removed."""
    url = serve(RETIRED_WIDGET_PAGE, anchored=[("sug-swap", "Settled: Lax cookie")])
    append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "sug-swap",
            "action": "decide",
            "detail": {"outcome": "accept"},
        },
    )
    page = open_page(browser, url)
    expect(page.locator("#sug-swap lf-old")).to_be_hidden()
    assert (
        page.locator("#old-group .lf-settled [data-lf-said]").evaluate(
            "el => el.textContent"
        )
        == "Settled: Lax cookie"
    ), "fixture is not exercising the case — the label the slot hides never rendered"
    expect(thread_head(page, serve.page_dir)).to_have_attribute("data-lf-detached", "")
    assert painted(page, "lf-mark") == "", (
        "a quote matched inside the half the user accepted away, because the "
        "label there declared itself the page speaking"
    )


def test_undo_takes_back_a_decision_carried_into_a_later_revision(browser, serve):
    """A decision the next revision keeps in force is still the user's newest gesture
    there, so ⌘Z takes it back as the widget's own Undo would."""
    first = leaf_page(
        "Carried decision",
        """<h1>Plan</h1>
<lf-group id="cz-ask" label="Which comes first?"><h2 id="cz-ask-h">Which comes first?</h2>
  <lf-options id="cz-options">
    <lf-option id="cz-flag">Flag</lf-option>
    <lf-option id="cz-backfill">Backfill</lf-option>
  </lf-options>
</lf-group>""",
    )
    page = open_page(browser, live_url(serve(first)))
    page.locator("#cz-flag .lf-pick").click()
    round_trip(page)
    expect(page.locator("#cz-flag")).to_have_attribute("selected", "")

    stamp_page(
        serve.page_dir,
        first.replace("<h1>Plan</h1>", "<h1>Plan</h1><p>Context added.</p>"),
        "add context",
    )
    wait_for_revision(page, 2)
    expect(page.locator("#cz-flag")).to_have_attribute("selected", "")

    undo(page)
    assert events_model.read_events(serve.page_dir)[-1]["kind"] == "undo"
    expect(page.locator("#cz-options lf-option[selected]")).to_have_count(0)
