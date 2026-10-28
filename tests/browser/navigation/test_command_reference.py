"""The command reference opened with `?`: its search, the commands it runs, and its
keyboard layer."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATIONS_PAGE
from render_cases_navigation import CONTROL_LABEL_PAGE, NOTED_PAGE
from render_harness import (
    LONG_PAGE,
    PANEL_THREAD,
    open_page,
    panel_control,
    panel_field,
    panel_view,
    resized,
    round_trip,
    show_resolved,
)

from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_only_controls_and_boxes_with_something_out_of_sight_take_a_tab_stop(
    browser, serve
):
    """Anything a mouse can scroll a keyboard has to reach, and the reference is a list
    long enough to scroll — but its rows carry no control, so nothing put the user in it
    and they could read the first screenful of the key reference and no more.

    The sweep that fixes that asks the box whether it may scroll, and the theme says every
    table may (`table { display: block; overflow-x: auto }`). So pointing it at the
    reference tagged all fourteen of its tables, none of which overflows: leaving the
    reference by Tab went from its native controls to fifteen extra stops, each wearing
    the browser's own ring rather than the layer's. A rule saying a box *could* scroll is
    not the same fact as a box that *has* something out of sight, and only the second is
    somewhere a user needs to be able to stand.

    Asserted as the whole set rather than a count, because the count was right before and
    the members were wrong: every stop in the overlay has to be a control the reference
    offers or a box that really scrolls."""
    page = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()

    stops = page.evaluate(
        """() => [...document.querySelector('.lf-command-reference').querySelectorAll('*')]
                 .filter(e => e.tabIndex >= 0)
                 .map(e => ({
                    tag: e.tagName,
                    scrolls: e.scrollWidth > e.clientWidth
                          || e.scrollHeight > e.clientHeight,
                 }))"""
    )
    assert stops, "the reference offers no tab stop at all, not even its search box"
    controls = {"BUTTON", "INPUT", "WA-INPUT"}
    dead = [s for s in stops if s["tag"] not in controls and not s["scrolls"]]
    assert dead == [], f"tab stops on boxes with nothing out of sight: {dead}"
    # The preference checkbox and the command search host each keep one stop.
    assert [s["tag"] for s in stops if s["tag"] in controls] == [
        "BUTTON",
        "INPUT",
        "WA-INPUT",
        "BUTTON",
    ]

    # And the box that does have something out of sight is one of those stops, which is
    # the whole point of the sweep. Its reachability is what is asserted here and not the
    # scroll itself: the headless shell does not move a focused div for an arrow or a
    # PageDown where Chrome does, so a motion assertion would be measuring the harness.
    # What this can say, and what the defect was, is that the box overflows and that a
    # user can be put on it.
    results = page.locator(".lf-command-reference-results")
    assert page.evaluate(
        "() => { const r = document.querySelector('.lf-command-reference-results');"
        "        return r.scrollHeight > r.clientHeight; }"
    ), (
        "this reference fits its box, so it proves nothing about reaching one that does not"
    )
    results.focus()
    expect(results).to_be_focused()
    page.keyboard.press("Escape")


def test_a_first_keyboard_opening_wires_the_references_close_control(browser, serve):
    """A first render's retained Close invokes the command its Escape key names."""
    page = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_have_attribute("open", "")
    expect(reference).to_be_visible()
    # The catalog is captured before the native dialog opens and takes focus. Its
    # own instructions must still appear on that first opening.
    for command in ["next", "previous", "activate"]:
        expect(
            reference.locator(
                f'[data-lf-command="command.reference.command.{command}"].lf-command-reference-row'
            )
        ).to_have_count(1)
    expect(
        reference.locator(
            '[data-lf-command="command.reference.close"].lf-command-reference-row'
        )
    ).to_have_count(1)
    page.get_by_role("combobox", name="Search commands").fill("comment")
    page.get_by_role("button", name="Close the command reference").click()
    expect(reference).to_be_hidden()


def test_the_reference_keeps_its_complete_keyboard_layer(browser, serve):
    """The reference has a visible close control and keeps Tab off the page behind it.

    It claims the keyboard while open, so Tab falling through to the page behind it
    would make the visible scope and the focus scope disagree. As a native modal it
    leaves Tab to the browser, which walks the reference and its own interface, while
    Escape closes and restores the opener."""
    page = open_page(browser, serve(CONTROL_LABEL_PAGE))
    page.evaluate(
        """async () => {
          const {commandScope, contributionEntry, presentContributionEntry} =
            await window.__lfWidgetApi();
          const control = document.createElement('button');
          control.id = 'projected-only-command';
          document.querySelector('main').append(control);
          const scope = commandScope('On a projected-only control', [{
            id: 'test.projected-only',
            keys: ['Mod+Alt+0'],
            title: 'Exercise the generated command scope',
            line: 'exercise projected command',
            run: () => {},
          }]);
          presentContributionEntry(control, contributionEntry({
            key: 'projected-only',
            icon: 'question',
            label: 'Projected command',
            scope,
          }));
        }"""
    )
    panel_control(page, "keyboard").click()
    # The leaf's menu goes away as its row opens the reference, so the leaf is the door
    # the reference returns to.
    opener = page.locator(".lf-fp-leaf")
    help_el = page.locator(".lf-command-reference")
    close = page.get_by_role("button", name="Close the command reference")
    expect(close).to_be_visible()
    expect(close.locator('svg[data-lf-icon="cross"]')).to_have_count(1)
    search = page.get_by_role("combobox", name="Search commands")
    expect(search).to_be_focused()
    # The editor's native focus is inside the shared control's shadow tree. Closing
    # directly from it must return to the same Help door as closing from a result.
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()
    panel_control(page, "keyboard").click()
    expect(search).to_be_focused()
    for command in [
        "test.projected-only",
        "response.reaction.choose",
        "response.move",
        "response.activate",
        "response.close",
    ]:
        expect(
            help_el.locator(
                f'.lf-command-reference-command[data-lf-command="{command}"]'
            )
        ).to_have_count(1)

    # The reference advertises the whole palette even while its controls are closed.
    expect(
        help_el.locator('[role=row][data-lf-command="response.reaction.choose"] kbd')
    ).to_have_text("1–6")

    # Tab is the browser's in the modal: it walks the reference and out to the browser's
    # own interface on its way round, never onto the page beneath.
    seen = set()
    for _ in range(6):
        page.keyboard.press("Tab")
        active = page.evaluate(
            """() => {
              const e = document.activeElement;
              return {inside: e === document.body
                        || document.querySelector('.lf-command-reference').contains(e),
                      name: e.getAttribute('aria-label') || e.className || e.tagName};
            }"""
        )
        assert active["inside"], f"Tab left the command reference for {active['name']}"
        seen.add(active["name"])
    assert "Close the command reference" in seen, seen

    page.keyboard.press("Shift+Tab")
    assert page.evaluate(
        "() => document.activeElement === document.body"
        "   || document.querySelector('.lf-command-reference').contains(document.activeElement)"
    )
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()

    # The native modal makes the page behind it inert. Its reachable light-dismiss gesture
    # is the backdrop, which closes the reference and returns to the door rather than
    # pretending a page control can be pressed through the modal layer.
    panel_control(page, "keyboard").click()
    page.mouse.click(2, 2)
    expect(help_el).to_be_hidden()
    expect(opener).to_be_focused()

    # A keyboard opening from an ordinary page control owes that control back too,
    # including when light dismissal closes the focused native search editor.
    page.keyboard.press("Escape")
    page_control = page.locator("#projected-only-command")
    page_control.click()
    page.keyboard.press("?")
    expect(search).to_be_focused()
    page.mouse.click(2, 2)
    expect(help_el).to_be_hidden()
    expect(page_control).to_be_focused()


def test_the_reference_runs_available_commands_and_explains_the_rest(browser, serve):
    """The reference is the command register made usable, not a second list of prose.

    Search narrows that register, arrows choose a result, and Enter runs it through the
    same scoped command route as its key. A command outside the user's current scope
    stays selectable, but explains the scope it needs instead of closing and doing
    nothing. Stable command IDs are exposed on the results so words can change without
    breaking this route or tooling built on it."""
    # Go-to's kind filters need a visible page target; the page's old skip button
    # used to supply one implicitly.
    page_with_target = NOTED_PAGE.replace(
        '<p id="p2">', '<a href="#p1">Jump to the first passage</a><p id="p2">'
    )
    page = open_page(browser, serve(page_with_target, comments=2))
    help_el = page.locator(".lf-command-reference")
    search = page.get_by_role("combobox", name="Search commands")

    page.keyboard.press("?")
    commands = help_el.locator(".lf-command-reference-command:visible")
    assert commands.count() > 1, "the command grid has no pair of rows to walk"
    # The head's hint and the rows share their verbs, "choose" and "activate".
    expect(help_el.locator(".lf-command-reference-meta")).to_have_text(
        re.compile(r"^\d+ commands · ↑↓ choose · ⏎ activate$")
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(commands.first).to_have_attribute("data-lf-selected", "true")
    # The walk says its position where the panel says what passes, in the empty
    # field's place.
    expect(panel_field(page)).to_have_attribute(
        "placeholder", f"Command 1 of {commands.count()}"
    )
    expect(help_el.locator(".lf-command-reference-meta")).to_have_text(
        re.compile(r" · ⏎ activate$")
    )
    first_row = commands.first.locator("xpath=ancestor::*[@role='row'][1]")
    assert search.evaluate(
        "input => input.ariaActiveDescendantElement?.id"
    ) == first_row.get_attribute("id")
    page.keyboard.press("ArrowUp")
    expect(commands.first).to_have_attribute("data-lf-selected", "true")

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    commands = help_el.locator(".lf-command-reference-command:visible")
    page.keyboard.press("ArrowUp")
    expect(search).to_be_focused()
    expect(commands.last).to_have_attribute("data-lf-selected", "true")
    last_row = commands.last.locator("xpath=ancestor::*[@role='row'][1]")
    assert search.evaluate(
        "input => input.ariaActiveDescendantElement?.id"
    ) == last_row.get_attribute("id")
    page.keyboard.press("ArrowDown")
    expect(commands.last).to_have_attribute("data-lf-selected", "true")

    # On a phone, every complete binding stays whole in its own cell, clear of its
    # command. Search adds a scope to each match; that context wraps to a second line
    # rather than squeezing the command's words or painting over them.
    resized(page, 390, 800)
    overlap = """(a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5
      && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5"""
    geometry = help_el.evaluate(
        f"""help => {{
          const overlap = {overlap};
          const results = help.querySelector('.lf-command-reference-results');
          return {{
            overflow: results.scrollWidth - results.clientWidth,
            keys: [...help.querySelectorAll('[role=row]:not([hidden]) .lf-binding-sequence')]
              .map(key => {{
                const box = key.getBoundingClientRect();
                const row = key.closest('[role=row]');
                return {{
                  command: row.dataset.lfCommand,
                  outside: box.right - key.closest('[role=gridcell]').getBoundingClientRect().right,
                  covers: overlap(box, row.querySelector('.lf-command-reference-action')
                    .getBoundingClientRect()),
                }};
              }}),
          }};
        }}"""
    )
    assert geometry["overflow"] <= 0, geometry
    assert not [
        key for key in geometry["keys"] if key["outside"] > 0.5 or key["covers"]
    ], geometry
    search.fill("space")
    matches = help_el.locator(
        ".lf-command-reference-binding-matches [role=row][data-lf-command]:visible"
    ).evaluate_all(
        f"""rows => rows.map(row => {{
          const overlap = {overlap};
          const command = row.querySelector('.lf-command-reference-command');
          const words = document.createRange();
          words.selectNodeContents(command);
          return {{
            command: row.dataset.lfCommand,
            lines: new Set([...words.getClientRects()].map(rect => Math.round(rect.top))).size,
            covered: overlap(command.getBoundingClientRect(),
              row.querySelector('.lf-command-reference-scope').getBoundingClientRect()),
          }};
        }})"""
    )
    assert matches
    assert all(item["lines"] == 1 and not item["covered"] for item in matches), matches
    resized(page, 1200, 800)

    # A key query may also occur in command ids and prose. Actual bindings lead the
    # filtered DOM, which is both the visual order and the Arrow-key command rail. A
    # trailing separator asks for continuations, and case puts the shifted face first.
    search.fill("g ")
    ranked = help_el.locator("[role=row][data-lf-command]:visible").evaluate_all(
        """rows => rows.map(row => ({
          command: row.dataset.lfCommand,
          binding: [...row.querySelectorAll('kbd')].map(key => key.textContent).join(' '),
        }))"""
    )
    assert ranked and ranked[0]["binding"].startswith("g "), ranked
    first_other = next(
        (
            index
            for index, row in enumerate(ranked)
            if not row["binding"].startswith("g ")
        ),
        len(ranked),
    )
    assert first_other > 0, ranked
    assert not any(row["binding"].startswith("g ") for row in ranked[first_other:]), (
        ranked
    )
    search.fill("g t")
    assert (
        help_el.locator("[role=row][data-lf-command]:visible").first.get_attribute(
            "data-lf-command"
        )
        == "navigation.target.filter.threads"
    )
    search.fill("g T")
    assert (
        help_el.locator("[role=row][data-lf-command]:visible").first.get_attribute(
            "data-lf-command"
        )
        == "navigation.panel.threads"
    )
    page.keyboard.press("ArrowDown")
    expect(
        help_el.locator(
            '.lf-command-reference-command[data-lf-command="navigation.panel.threads"]'
        )
    ).to_have_attribute("data-lf-selected", "true")
    expect(help_el.locator(".lf-command-reference-meta")).to_have_text(
        "Threads · g · ⏎ activate"
    )
    search.fill("Tab")
    tab_matches = help_el.locator(
        ".lf-command-reference-binding-matches [role=row][data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "panel.floating.menu.leave-forward" in tab_matches, tab_matches
    search.fill("w")
    w_results = help_el.locator("[role=row][data-lf-command]:visible").evaluate_all(
        "rows => rows.map(row => row.dataset.lfCommand)"
    )
    assert w_results.index("draw.mode.exit") < w_results.index("page.down"), w_results
    w_matches = help_el.locator(
        ".lf-command-reference-binding-matches [role=row][data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "draw.mode.exit" in w_matches, w_matches
    assert w_results.index("page.down") >= len(w_matches), w_results

    search.fill("r resolve")
    result = help_el.locator(
        '.lf-command-reference-command[data-lf-command="thread.resolution.toggle"]'
    )
    expect(result).to_have_count(1)
    expect(result).to_have_attribute("data-lf-command", "thread.resolution.toggle")
    expect(search).to_have_attribute("aria-haspopup", "grid")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result.locator("xpath=ancestor::*[@role='row'][1]")).to_have_attribute(
        "aria-selected", "true"
    )
    page.keyboard.type("!")
    expect(search).to_have_value("r resolve!")
    expect(help_el.locator(".lf-command-reference-empty")).to_be_visible()
    page.keyboard.press("Backspace")
    page.keyboard.press("ArrowDown")
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_visible()
    expect(help_el.locator(".lf-command-reference-meta")).to_have_text(
        "Available in a thread"
    )
    search.fill("reaction.cancel")
    cancel_reaction = help_el.locator(
        '.lf-command-reference-command[data-lf-command="reaction.cancel"]'
    )
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(cancel_reaction).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el.locator(".lf-command-reference-meta")).to_have_text(
        "Available with reactions open"
    )

    page.keyboard.press("Escape")
    page.keyboard.press("?")
    # The shared description names both directions, so its words match both rows.
    # Search the stable command id to run this exact direction through the reference.
    search.fill("thread.previous")
    previous = help_el.locator(
        '.lf-command-reference-command[data-lf-command="thread.previous"]'
    )
    expect(previous).to_have_count(1)
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(previous).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    # The last thread, which has no card on the page, opens in the panel.
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    page.keyboard.press("?")
    search.fill("r resolve")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    page.keyboard.press("Enter")
    expect(help_el).to_be_hidden()
    expect(show_resolved(page)).to_have_count(1)


# On me stands for the panel's views: its mark is the row's control, and Threads, a tab
# of On, shares its branch.
@pytest.mark.parametrize(
    ("command", "suffix", "surface"),
    [
        ("navigation.panel.queue", "M", panel_view("queue")),
        ("navigation.page-map", "P", ".lf-page-map-dialog"),
        ("version.open", "V", '.lf-fp-menu[data-level="versions"]'),
    ],
)
def test_the_reference_enters_named_go_to_destinations(
    browser, serve, command, suffix, surface
):
    """A named destination is one capability whether a keyboard sequence or the
    command reference reaches it; native controls keep their own activation."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE, comments=2))
    destination = page.locator(surface)
    if suffix in ("T", "M"):
        control = "threads" if suffix == "T" else "queue"
        panel_control(page, control).click()
        expect(destination).to_be_visible()
        page.keyboard.press("g")
        page.keyboard.press(f"Shift+{suffix.lower()}")
        expect(destination).to_be_hidden()
        panel_control(page, control).press("Enter")
        expect(destination).to_be_visible()
        page.wait_for_function(
            "selector => document.querySelector(selector).contains(document.activeElement)",
            arg=surface,
        )
        page.keyboard.press("g")
        page.keyboard.press(f"Shift+{suffix.lower()}")
        expect(destination).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press(f"Shift+{suffix.lower()}")
    expect(destination).to_be_visible()
    page.wait_for_function(
        "selector => document.querySelector(selector).contains(document.activeElement)",
        arg=surface,
    )
    if suffix in ("T", "M"):
        page.keyboard.press("g")
        page.keyboard.press(f"Shift+{suffix.lower()}")
    else:
        page.keyboard.press("Escape")
    expect(destination).to_be_hidden()

    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    page.get_by_role("combobox", name="Search commands").fill(command)
    row = reference.locator(f'[role=row][data-lf-command="{command}"]')
    expect(row.locator(".lf-binding-sequence > kbd")).to_have_text(["g", suffix])
    row.get_by_role("button").click()
    expect(reference).to_be_hidden()
    expect(destination).to_be_visible()
    page.wait_for_function(
        "selector => document.querySelector(selector).contains(document.activeElement)",
        arg=surface,
    )


def test_a_command_reference_versions_press_enters_the_menu_from_the_leaf(
    browser, serve
):
    """A command chosen in the reference enters its destination from the panel leaf."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE, comments=2))
    leaf = page.locator(".lf-fp-leaf")
    leaf.click()
    page.keyboard.press("Escape")
    expect(leaf).to_be_focused()
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    page.get_by_role("combobox", name="Search commands").fill("version.open")
    reference.locator('[role=row][data-lf-command="version.open"] button').click()
    versions = page.locator('.lf-fp-menu[data-level="versions"]')
    expect(versions).to_be_visible()
    expect(versions.locator(".lf-fp-item:focus")).to_have_count(1)


@pytest.mark.parametrize("viewport", [(1280, 800), (390, 800), (800, 320)])
def test_the_reference_keeps_its_top_and_search_still_when_filtering(
    browser, serve, viewport
):
    """Results shrink below the search field, including an empty result set."""
    page = open_page(browser, serve(NOTED_PAGE))
    resized(page, *viewport)
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    search = page.get_by_role("combobox", name="Search commands")
    expect(search).to_be_focused()
    initial_dialog = reference.bounding_box()
    search_field = reference.locator(".lf-command-reference-search")
    initial_search = search_field.bounding_box()
    commands = reference.locator(".lf-command-reference-command:visible")
    initial_count = commands.count()

    for query in ("page.search.open", "no command has these words", ""):
        if query:
            search.fill(query)
        else:
            search_field.get_by_role("button", name="Clear entry").click()
            expect(search).to_have_value("")
            expect(commands).to_have_count(initial_count)
        if query == "page.search.open":
            expect(
                reference.locator(".lf-command-reference-command:visible")
            ).to_have_count(1)
        if query == "no command has these words":
            expect(reference.locator(".lf-command-reference-empty")).to_be_visible()
            # At the shortest viewport both states can meet the same height limit.
            assert reference.bounding_box()["height"] <= initial_dialog["height"]
            if viewport[1] > 320:
                assert reference.bounding_box()["height"] < initial_dialog["height"]
        expect(search).to_be_focused()
        dialog = reference.bounding_box()
        field = search_field.bounding_box()
        assert dialog["y"] == pytest.approx(initial_dialog["y"], abs=0.5)
        for axis in ("x", "y", "width", "height"):
            assert field[axis] == pytest.approx(initial_search[axis], abs=0.5)
        assert dialog["y"] + dialog["height"] <= viewport[1] - 16


def test_the_reference_keeps_local_search_state_on_one_lit_surface(browser, serve):
    """Filtering and selection update one stable search surface through Lit.

    The input owns its native value and caret while the projected result model owns the
    selected command. Filtering a selection out clears it rather than retaining a hidden
    command, and filtering it back does not silently revive it.
    """
    page = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    search = page.get_by_role("combobox", name="Search commands")
    result = reference.locator(
        '.lf-command-reference-command[data-lf-command="thread.resolution.toggle"]'
    )
    page.evaluate(
        """() => {
          window.__commandReferenceSearch = document.querySelector(
            '.lf-command-reference-search');
          window.__commandReferenceResults = document.querySelector(
            '.lf-command-reference-results');
          window.__resolutionCommandKeys = document.querySelector(
            '[data-lf-command="thread.resolution.toggle"] .lf-binding-sequence');
          window.__resolutionCommandFirstKey = window.__resolutionCommandKeys.querySelector(
            'kbd');
        }"""
    )

    search.fill("rresolve")
    search.evaluate("input => input.setSelectionRange(1, 1)")
    page.keyboard.type(" ")
    expect(search).to_have_value("r resolve")
    assert search.evaluate("input => input.selectionStart") == 2
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")

    search.fill("r")
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result).to_have_attribute("tabindex", "0")
    row = result.locator("xpath=ancestor::*[@role='row'][1]")
    expect(row).to_have_attribute("aria-selected", "true")
    assert search.evaluate(
        "input => input.ariaActiveDescendantElement?.id"
    ) == row.get_attribute("id")
    assert page.evaluate(
        """() =>
          window.__commandReferenceSearch === document.querySelector(
            '.lf-command-reference-search') &&
          window.__commandReferenceResults === document.querySelector(
            '.lf-command-reference-results') &&
          window.__resolutionCommandKeys === document.querySelector(
            '[data-lf-command="thread.resolution.toggle"] .lf-binding-sequence') &&
          window.__resolutionCommandFirstKey === document.querySelector(
            '[data-lf-command="thread.resolution.toggle"] .lf-binding-sequence kbd')"""
    )

    search.fill("no command has these words")
    expect(reference.locator(".lf-command-reference-empty")).to_be_visible()
    assert search.evaluate("input => input.ariaActiveDescendantElement") is None
    search.fill("r resolve")
    expect(result).to_have_attribute("data-lf-selected", "false")
    assert page.evaluate(
        """() =>
          window.__resolutionCommandKeys === document.querySelector(
            '[data-lf-command="thread.resolution.toggle"] .lf-binding-sequence') &&
          window.__resolutionCommandFirstKey === document.querySelector(
            '[data-lf-command="thread.resolution.toggle"] .lf-binding-sequence kbd')"""
    )


def test_the_reference_revalidates_a_captured_command_before_running_it(browser, serve):
    """An opening-time catalog cannot execute a command whose live route changed.

    Search stays deterministic while the dialog stands. Activation closes the dialog,
    resolves the stable id against the live register, and reopens a fresh catalog with an
    explanation when that captured id is no longer available.
    """
    page = open_page(browser, serve(NOTED_PAGE))
    page.evaluate(
        """async () => {
          const { commands, paintKeys } = await window.__lfWidgetApi();
          const control = document.createElement('button');
          control.id = 'changing-command-scope';
          control.textContent = 'Changing command scope';
          control.dataset.phase = 'first';
          document.querySelector('main').append(control);
          commands(control, 'Changing commands', [
            {
              id: 'test.changing.first',
              keys: ['F8'],
              title: 'Run the first changing command',
              line: 'first changing command',
              when: () => control.dataset.phase === 'first',
              run: () => { control.dataset.ran = 'first'; },
            },
            {
              id: 'test.changing.second',
              keys: ['F8'],
              title: 'Run the second changing command',
              line: 'second changing command',
              when: () => control.dataset.phase === 'second',
              run: () => { control.dataset.ran = 'second'; },
            },
          ]);
          paintKeys();
          control.focus();
        }"""
    )
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    first = reference.locator(
        '.lf-command-reference-command[data-lf-command="test.changing.first"]'
    )
    second = reference.locator(
        '.lf-command-reference-command[data-lf-command="test.changing.second"]'
    )
    expect(first).to_be_visible()
    expect(second).to_have_count(0)

    page.locator("#changing-command-scope").evaluate(
        "control => { control.dataset.phase = 'second'; }"
    )
    first.click()
    expect(reference).to_be_visible()
    expect(reference.locator(".lf-command-reference-meta")).to_have_text(
        "That command is no longer available"
    )
    expect(first).to_have_count(0)
    expect(second).to_be_visible()
    expect(page.locator("#changing-command-scope")).not_to_have_attribute(
        "data-ran", re.compile(r".+")
    )


def test_the_reference_runs_the_exact_numbered_obligation_action(browser, serve):
    """Each obligation digit is a distinct command when invoked without a keydown."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))

    page.keyboard.press("m")
    page.keyboard.press("?")

    first = page.locator(
        '.lf-command-reference-command[data-lf-command="option.choose-lq-keep"]'
    )
    second = page.locator(
        '.lf-command-reference-command[data-lf-command="option.choose-lq-token"]'
    )
    expect(first).to_have_text("Keep the store")
    expect(second).to_have_text("Signed tokens")

    second.click()
    expect(page.locator("#lq-token")).to_have_attribute("chosen", "")
    expect(page.locator("#lq-keep")).not_to_have_attribute("chosen", "")
    round_trip(page)


def test_away_from_an_obligation_the_reference_names_widget_owned_options(
    browser, serve
):
    """The catalog keeps the widget's named commands and explicitly declared digits.

    Outside the widget those commands are unavailable; there is no synthetic page
    command claiming an undifferentiated digit range.
    """
    page = open_page(browser, serve(OBLIGATIONS_PAGE))
    page.keyboard.press("?")
    reference = page.locator(".lf-command-reference")
    expect(reference).to_be_visible()
    first = reference.locator('[role=row][data-lf-command="option.choose-lq-keep"]')
    second = reference.locator('[role=row][data-lf-command="option.choose-lq-token"]')
    expect(first.locator(".lf-command-reference-command")).to_have_attribute(
        "data-lf-available", "false"
    )
    expect(second.locator(".lf-command-reference-command")).to_have_attribute(
        "data-lf-available", "false"
    )
    expect(first.locator("kbd")).to_have_text("1")
    expect(second.locator("kbd")).to_have_text("2")
    expect(first).to_contain_text("Keep the store")
    expect(second).to_contain_text("Signed tokens")


def test_the_reference_reads_the_same_way_twice(browser, serve):
    """A widget registers its scope at upgrade, and the set the reference walks is
    insertion-ordered, so the sections came out in whatever order the modules happened to
    finish in. The same build read twice put "On a tab" above "On a card grip" once and
    below it the next time. A reference whose headings move between loads is one a user
    cannot learn the shape of, and any assertion on it flakes rather than fails — which is
    how it was found, a reviewer taking a reordering for fallout from an unrelated change.

    So the widgets' sections read in the order the page holds them. Asserted twice over:
    the same page loaded twice gives the same list, and that list is the document's own
    order rather than any order at all — a stable-but-wrong order would pass the first
    check alone."""
    url = serve(CONTROL_LABEL_PAGE)
    seen = []
    for _ in range(2):
        page = open_page(browser, url)
        page.keyboard.press("?")
        expect(page.locator(".lf-command-reference")).to_be_visible()
        seen.append(
            page.evaluate(
                "() => [...document.querySelectorAll('.lf-command-reference h3')].map(h => h.textContent)"
            )
        )
        page.close()

    assert seen[0] == seen[1], f"the reference reordered between loads: {seen}"
    assert "On a tab" in seen[0], seen[0]


def test_the_reference_lists_each_of_the_panel_s_keys_once(browser, serve):
    """The floating panel's section listed ↑ ↓ Home End twice, once for the leaf's menu
    and once for the open view, under the same words, and gave ← and → a row each with
    one description between them: twelve rows for seven keys' meanings. One walk over
    whichever list is open, and ← / → on one row as the margin's reads, list each key
    once."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    rows = page.evaluate(
        """() => {
          const listed = []; let inside = false;
          for (const row of document.querySelectorAll('.lf-command-reference [role=row]')) {
            const heading = row.querySelector('h3');
            if (heading) { inside = heading.textContent === 'In the floating panel'; continue; }
            if (!inside || !row.dataset.lfCommand) continue;
            listed.push([
              row.dataset.lfCommand,
              [...row.querySelectorAll('kbd')].map(key => key.textContent.trim()).join(' '),
              row.querySelector('.lf-command-reference-command').textContent,
            ]);
          }
          return listed;
        }"""
    )
    assert [(command, title) for command, _, title in rows] == [
        ("panel.floating.rows.previous", "Previous row"),
        ("panel.floating.rows.next", "Next row"),
        ("panel.floating.rows.first", "First row"),
        ("panel.floating.rows.last", "Last row"),
        ("panel.floating.menu.level", "Open or leave a list"),
        ("panel.floating.menu.leave-forward", "Leave forward"),
        ("panel.floating.menu.leave-backward", "Leave backward"),
    ], rows
    # The arrows' glyphs read the same on every platform; Tab's modifier does not.
    assert [keys for _, keys, _ in rows[:5]] == ["↑", "↓", "home", "end", "← / →"], rows


def test_the_reference_keeps_its_count_line_whole_above_the_results(browser, serve):
    """The reference is a column in a window-capped box, and only its results give up
    height to fit. Its count line was a shrinkable item too, squeezed to 13.8px under a
    16.7px line with the results starting on its last pixel, so a row scrolled up to the
    results' edge ran into the words above it. The line keeps a whole line, and the
    results start a step below it."""
    page = open_page(browser, serve(LONG_PAGE))
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_be_visible()
    reading = page.evaluate(
        """() => {
          const box = (selector) => document.querySelector(selector)
            .getBoundingClientRect();
          const meta = document.querySelector('.lf-command-reference-meta');
          const results = document.querySelector('.lf-command-reference-results');
          return {
            line: parseFloat(getComputedStyle(meta).lineHeight),
            meta: box('.lf-command-reference-meta').toJSON(),
            results: results.getBoundingClientRect().toJSON(),
            scrolls: results.scrollHeight > results.clientHeight,
          };
        }"""
    )
    assert reading["scrolls"], "the results fit, so nothing had to give up height"
    assert reading["meta"]["height"] >= reading["line"] - 0.5, reading
    assert reading["results"]["top"] - reading["meta"]["bottom"] >= 4, reading

    # Walking keeps the search field focused, so only the results' own scroll
    # region can make the selected command visible. The document stays put.
    search = page.get_by_role("combobox", name="Search commands")
    expect(search).to_be_focused()
    buttons = page.locator(".lf-command-reference-command")
    count = buttons.count()
    assert count > 10, "the command walk must extend beyond the visible results"
    last_command = buttons.last.evaluate(
        "button => button.closest('[role=row]').dataset.lfCommand"
    )
    before = page.evaluate("scrollY")
    search.press("ArrowUp")
    rendered(page)
    selected = page.locator('.lf-command-reference [role=row][aria-selected="true"]')
    expect(selected).to_have_attribute("data-lf-command", last_command)
    expect(search).to_be_focused()
    bounds = selected.evaluate("""row => {
      const results = row.closest('.lf-command-reference-results');
      const selected = row.getBoundingClientRect();
      const band = results.getBoundingClientRect();
      return {top:selected.top, bottom:selected.bottom, low:band.top,
        high:band.bottom, offset:results.scrollTop};
    }""")
    assert bounds["offset"] > 0, bounds
    assert bounds["top"] >= bounds["low"] - 1, bounds
    assert bounds["bottom"] <= bounds["high"] + 1, bounds
    assert page.evaluate("scrollY") == before
