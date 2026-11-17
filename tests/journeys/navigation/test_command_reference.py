"""Tests scheduled by the measured cost of their boundary."""

import re

import pytest
from playwright.sync_api import expect
from render_cases_navigation import NOTED_PAGE
from render_harness import open_page, panel_field, resized, show_resolved

from leaf_dev.browser import PANEL_THREAD

pytestmark = pytest.mark.shifts_unsurveyed


def test_the_reference_runs_available_commands_and_explains_the_rest(browser, serve):
    """The reference is the command register made usable, not a second list of prose.

    Search narrows that register, arrows choose a result, and Enter runs it through the
    same scoped command route as its key. A command outside the user's current scope
    stays selectable, but explains the scope it needs instead of closing and doing
    nothing. Stable command IDs are exposed on the results so words can change without
    breaking this route or tooling built on it."""
    # Go-to's kind filters need a visible page target.
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
    first_row = commands.first
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
    last_row = commands.last
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
            keys: [...help.querySelectorAll('[role=option]:not([hidden]) .lf-binding-sequence')]
              .map(key => {{
                const box = key.getBoundingClientRect();
                const row = key.closest('[role=option]');
                return {{
                  command: row.dataset.lfCommand,
                  outside: box.right - key.closest('.lf-command-reference-key').getBoundingClientRect().right,
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
        ".lf-command-reference-binding-matches [role=option][data-lf-command]:visible"
    ).evaluate_all(
        f"""rows => rows.map(row => {{
          const overlap = {overlap};
          const command = row.querySelector('.lf-command-reference-title-words');
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
    ranked = help_el.locator("[role=option][data-lf-command]:visible").evaluate_all(
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
        help_el.locator("[role=option][data-lf-command]:visible").first.get_attribute(
            "data-lf-command"
        )
        == "navigation.target.filter.threads"
    )
    search.fill("g T")
    assert (
        help_el.locator("[role=option][data-lf-command]:visible").first.get_attribute(
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
        ".lf-command-reference-binding-matches [role=option][data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "page.search.match.next" in tab_matches, tab_matches
    search.fill("w")
    w_results = help_el.locator("[role=option][data-lf-command]:visible").evaluate_all(
        "rows => rows.map(row => row.dataset.lfCommand)"
    )
    assert w_results.index("draw.mode.exit") < w_results.index("page.down"), w_results
    w_matches = help_el.locator(
        ".lf-command-reference-binding-matches [role=option][data-lf-command]:visible"
    ).evaluate_all("rows => rows.map(row => row.dataset.lfCommand)")
    assert "draw.mode.exit" in w_matches, w_matches
    assert w_results.index("page.down") >= len(w_matches), w_results

    search.fill("r resolve")
    result = help_el.locator(
        '.lf-command-reference-command[data-lf-command="thread.resolution.toggle"]'
    )
    expect(result).to_have_count(1)
    expect(result).to_have_attribute("data-lf-command", "thread.resolution.toggle")
    expect(search).to_have_attribute("aria-haspopup", "listbox")
    page.keyboard.press("ArrowDown")
    expect(search).to_be_focused()
    expect(result).to_have_attribute("data-lf-selected", "true")
    expect(result).to_have_attribute("aria-selected", "true")
    page.keyboard.type("!")
    expect(search).to_have_value("r resolve!")
    expect(help_el.locator(".lf-rows-empty")).to_be_visible()
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
