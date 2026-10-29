"""The Page Map dialog and sheet, g hints, and the walk between margin locations,
including across live versions."""

import re

import pytest
from axe_playwright_python.sync_playwright import Axe
from click.testing import CliRunner
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATION_PAGE, PANEL_PAGE, REPORT_PAGE, live_url
from render_cases_navigation import CHIPS, _publish, address_code, go_to_address
from render_harness import (
    PANEL,
    RELEASE_FOCUS,
    compare_with,
    draft_control,
    expect_panel_offers,
    held_frames,
    leaf_page,
    margins_laid_out,
    open_page,
    panel_control,
    panel_settled,
    panel_view,
    press_visible,
    regions_side_by_side,
    resized,
    scroll_settled,
    sending,
    told,
)

from browser.margin import (
    ACTION_ON_OBLIGATION,
    COMMENT_ON_OBLIGATION,
    DENSE_SUGGESTIONS_PAGE,
)
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


DUPLICATE_REGION_PAGE = leaf_page(
    "duplicate Page Map subjects",
    """
  <div id="duplicate-map-split">
    <lf-pane id="current-pane" label="Current">
      <div>
        <h2 id="current-deployment">Deployment</h2>
        <p>The current release remains available to users.</p>
        <h2 id="current-summary">Summary</h2>
        <p>The current result has one unique subject.</p>
      </div>
    </lf-pane>
    <lf-pane id="proposed-pane" label="Proposed">
      <div>
        <h2 id="proposed-deployment">Deployment</h2>
        <p>The proposed release remains available to users.</p>
      </div>
    </lf-pane>
  </div>
""",
    head=regions_side_by_side("duplicate-map-split"),
    layout="workspace",
)


DUPLICATE_REGION_COMMENTS = [
    {
        "kind": "comment",
        "id": f"comment-{section}",
        "author": "user",
        "revision": 1,
        "text": "Check this subject.",
        "anchor": {"section": section},
    }
    for section in ("current-deployment", "current-summary", "proposed-deployment")
]


def test_page_map_qualifies_only_duplicate_subjects_with_their_reading_region(
    browser, serve
):
    page = open_page(
        browser, serve(DUPLICATE_REGION_PAGE, events=DUPLICATE_REGION_COMMENTS)
    )
    resized(page, 390, 760)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)

    headings = dialog.get_by_role("heading", level=3)
    expect(headings).to_have_count(3)
    assert headings.all_inner_texts() == [
        "Current · heading · Deployment",
        "heading · Summary",
        "Proposed · heading · Deployment",
    ]
    expect(
        dialog.get_by_role("heading", name="Current · heading · Deployment", exact=True)
    ).to_be_visible()
    expect(
        dialog.get_by_role(
            "heading", name="Proposed · heading · Deployment", exact=True
        )
    ).to_be_visible()
    expect(
        dialog.get_by_role("heading", name="heading · Summary", exact=True)
    ).to_be_visible()

    proposed = dialog.locator(".lf-page-map-group").nth(2)
    proposed.get_by_role(
        "button", name="Open thread: Check this subject.", exact=True
    ).click()
    expect(dialog).to_be_hidden()
    thread = page.locator(
        '.lf-margin-preview .lf-page-thread[data-thread="comment-proposed-deployment"]'
    )
    expect(thread).to_be_focused()
    expect(thread).to_contain_text("Check this subject.")
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()


PAGE_MAP_PAGE = leaf_page(
    "Twelve Page Map locations",
    "".join(
        f'<section id="map-{n}" style="min-height: 420px">'
        f"<h2>Location {n}</h2><p>Body {n}</p></section>"
        for n in range(1, 13)
    ),
)


PAGE_MAP_EVENTS = [
    {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": f"Map note {n}",
        "anchor": {"section": f"map-{n}"},
    }
    for n in range(1, 13)
]


def test_the_current_obligation_marks_its_selected_margin_reading(browser, serve):
    """The page and margin projections identify the same selected obligation."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    resized(page, 1440, 900)

    page.keyboard.press("m")
    first = page.locator("#jobs-decision")
    expect(first).to_be_focused()
    first_marker = page.locator(
        '[data-lf-margin-for="jobs-decision"] > .lf-margin-marker'
    )
    expect(first).to_have_attribute("data-lf-obligation", "1")
    expect(first_marker).to_have_attribute("data-lf-target-selected", "")
    assert first_marker.evaluate(
        "marker => getComputedStyle(marker).borderTopColor"
    ) == first.evaluate("ask => getComputedStyle(ask, '::after').outlineColor")
    page.keyboard.press("m")
    expect(page.locator("#bracket-decision")).to_be_focused()
    expect(first_marker).not_to_have_attribute(
        "data-lf-target-selected", re.compile(".*")
    )
    expect(
        page.locator('[data-lf-margin-for="bracket-decision"] > .lf-margin-marker')
    ).to_have_attribute("data-lf-target-selected", "")


def test_open_page_map_uses_the_canonical_margin_entry_record_and_live_state(
    browser, serve
):
    """Frozen replacement records retain one keyed view and one activation command."""
    page = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let state = {state: 'engaged', expanded: true, popup: 'dialog',
            pressed: true, disabled: false, behavior: 'disclosure'};
          const read = () => ({entries: [contributionEntry({
            key: 'inspect', icon: 'question', label: 'Inspect source',
            context: 'Patch ready', behavior: state.behavior, tone: 'negative',
            rank: 'reading', state: state.state, disabled: state.disabled,
            pressed: state.pressed,
            relation: state.behavior === 'disclosure'
              ? {kind: 'element', id: 'how-cap', expanded: state.expanded,
                  popup: state.popup}
              : null,
            activation: 'inspect-source'
          })]});
          window.lfCanonicalActivations = [];
          const registration = registerContribution({
            key: 'fixture', target: document.querySelector('#how-cap'), read,
            activate: token => window.lfCanonicalActivations.push(token)
          });
          const initial = registration.entry('inspect');
          window.lfCanonicalMarginEntry = {
            registration,
            update() {
              state = {...state, state: 'busy', expanded: false, popup: 'menu',
                pressed: null};
              registration.update({immediate: true});
            },
            disable(disabled) {
              state = {...state, disabled};
              registration.update({immediate: true});
            },
            behavior(behavior) {
              state = {...state, behavior, state: 'idle', disabled: false,
                pressed: null};
              registration.update({immediate: true});
            },
            recordProof() {
              const current = registration.entry('inspect');
              return {initialFrozen: Object.isFrozen(initial)
                  && Object.isFrozen(initial.relation),
                currentFrozen: Object.isFrozen(current)
                  && Object.isFrozen(current.relation),
                replaced: current !== initial};
            }
          };
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    proxy = dialog.get_by_role("button", name="Inspect source, Patch ready", exact=True)
    expect(proxy).to_be_visible()
    assert proxy.evaluate(
        """button => ({
          behavior: button.dataset.lfBehavior,
          tone: button.dataset.lfTone,
          rank: button.dataset.lfRank,
          state: button.dataset.lfState,
          label: button.querySelector('.lf-page-map-action-label-word').textContent,
          context: button.querySelector('.lf-page-map-action-context')?.textContent ?? null,
          expanded: button.getAttribute('aria-expanded'),
          pressed: button.getAttribute('aria-pressed'),
          popup: button.getAttribute('aria-haspopup'),
          controls: button.getAttribute('aria-controls'),
        })"""
    ) == {
        "behavior": "disclosure",
        "tone": "negative",
        "rank": "reading",
        "state": "engaged",
        "label": "Inspect source…",
        "context": "Patch ready",
        "expanded": "true",
        "pressed": "true",
        "popup": "dialog",
        "controls": "how-cap",
    }

    proxy.evaluate("button => button.dataset.stableProof = 'same-proxy'")
    proxy.focus()
    focused_key = proxy.get_attribute("data-lf-map-margin-entry")
    page.evaluate("() => window.lfCanonicalMarginEntry.update()")
    expect(proxy).to_be_focused()
    expect(proxy).to_have_attribute("data-stable-proof", "same-proxy")
    expect(proxy).to_have_attribute("data-lf-map-margin-entry", focused_key)
    assert page.evaluate("() => window.lfCanonicalMarginEntry.recordProof()") == {
        "initialFrozen": True,
        "currentFrozen": True,
        "replaced": True,
    }
    expect(proxy).to_have_attribute("data-lf-state", "busy")
    expect(proxy).to_have_attribute("aria-busy", "true")
    expect(proxy).to_have_attribute("aria-expanded", "false")
    expect(proxy).to_have_attribute("aria-haspopup", "menu")
    expect(proxy).not_to_have_attribute("aria-pressed", re.compile(".+"))
    page.evaluate("() => window.lfCanonicalMarginEntry.disable(true)")
    expect(proxy).to_be_disabled()
    page.evaluate("() => window.lfCanonicalMarginEntry.disable(false)")
    expect(proxy).to_be_enabled()
    assert (
        page.locator(
            '[data-lf-margin-entry-key="inspect"]:not(.lf-margin-entry):not(.lf-page-map-action)'
        ).count()
        == 0
    ), "the contribution left a hidden source control beside its projections"
    proxy.evaluate("button => window.lfPriorMapControl = button")
    page.evaluate("() => window.lfCanonicalMarginEntry.behavior('status')")
    status = dialog.locator(
        '[data-lf-margin-entry-owner="fixture"][data-lf-margin-entry-key="inspect"]'
    )
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_attribute("tabindex", "-1")
    expect(status).not_to_have_attribute("aria-disabled", re.compile(".+"))
    expect(status).not_to_have_attribute("aria-expanded", re.compile(".+"))
    expect(status).not_to_have_attribute("aria-controls", re.compile(".+"))
    expect(status).not_to_have_attribute("aria-haspopup", re.compile(".+"))
    expect(status).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    assert status.evaluate("node => node.tagName") == "SPAN"
    assert page.evaluate("() => !window.lfPriorMapControl.isConnected")
    expect(dialog.get_by_role("searchbox")).to_be_focused()
    page.keyboard.press("Enter")
    page.keyboard.press(" ")
    expect(dialog).to_be_visible()
    assert page.evaluate("() => window.lfCanonicalActivations") == []
    status.focus()
    page.keyboard.press("?")
    reference = page.get_by_role("dialog", name="Command reference", exact=True)
    reference.get_by_role("combobox", name="Search commands").fill("margin.press")
    press = reference.locator(
        '.lf-command-reference-command[data-lf-command="margin.press"]'
    )
    expect(press).to_have_attribute("data-lf-available", "false")
    page.keyboard.press("Escape")
    expect(status).to_be_focused()

    page.evaluate("() => window.lfCanonicalMarginEntry.behavior('action')")
    action = dialog.get_by_role(
        "button", name="Inspect source, Patch ready", exact=True
    )
    assert action.evaluate("node => node.tagName") == "BUTTON"
    expect(action).not_to_have_attribute("role", re.compile(".+"))
    expect(action).not_to_have_attribute("aria-keyshortcuts", re.compile(".+"))
    icon = action.locator(":scope > .lf-row-lead > .lf-margin-kind")
    box = icon.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.evaluate("() => window.lfCanonicalMarginEntry.update()")
    page.mouse.up()
    expect(dialog).to_be_hidden()
    assert page.evaluate("() => window.lfCanonicalActivations") == ["inspect-source"]


def test_page_map_preserves_opaque_contribution_identity_and_relation_targets(
    browser, serve
):
    """Composite keys retain both controls and relations target unique stable hosts."""
    page = open_page(browser, serve(PANEL_PAGE))
    page.evaluate(
        """async () => {
          const {contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          const target = document.querySelector('#how-cap');
          window.lfIdentityActivations = [];
          const register = (owner, key, label) => registerContribution({
            key: owner, target,
            read: () => ({entries: [contributionEntry({key, icon: 'dot', label})]}),
            activate: activation => window.lfIdentityActivations.push(activation),
          });
          const first = register('a:b', 'c', 'First opaque action');
          const second = register('a', 'b:c', 'Second opaque action');
          const related = registerContribution({
            key: 'relations', target,
            read: () => ({entries: [
              contributionEntry({key: 'open-colon', icon: 'more', label: 'Open colon',
                behavior: 'disclosure',
                relation: {kind: 'entries', keys: ['a:b'], expanded: true}}),
              contributionEntry({key: 'a:b', icon: 'dot', label: 'Colon target'}),
              contributionEntry({key: 'open-slash', icon: 'more', label: 'Open slash',
                behavior: 'disclosure',
                relation: {kind: 'entries', keys: ['a/b'], expanded: true}}),
              contributionEntry({key: 'a/b', icon: 'dot', label: 'Slash target'}),
            ]}), activate: () => {},
          });
          window.lfIdentityMargins = {first, second, related};
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    first = dialog.get_by_role("button", name="First opaque action", exact=True)
    second = dialog.get_by_role("button", name="Second opaque action", exact=True)
    expect(first).to_have_count(1)
    expect(second).to_have_count(1)
    first.evaluate("node => { node.dataset.identityProbe = 'first'; }")
    second.evaluate("node => { node.dataset.identityProbe = 'second'; }")

    page.evaluate(
        """() => Object.values(window.lfIdentityMargins)
          .forEach(registration => registration.update({immediate: true}))"""
    )
    expect(first).to_have_attribute("data-identity-probe", "first")
    expect(second).to_have_attribute("data-identity-probe", "second")
    assert first.get_attribute("data-lf-map-margin-entry") != second.get_attribute(
        "data-lf-map-margin-entry"
    )

    colon_target = dialog.get_by_role("button", name="Colon target", exact=True)
    slash_target = dialog.get_by_role("button", name="Slash target", exact=True)
    colon_relation = dialog.get_by_role("button", name="Open colon", exact=True)
    slash_relation = dialog.get_by_role("button", name="Open slash", exact=True)
    assert colon_target.get_attribute("id") != slash_target.get_attribute("id")
    assert colon_relation.get_attribute("aria-controls") == colon_target.get_attribute(
        "id"
    )
    assert slash_relation.get_attribute("aria-controls") == slash_target.get_attribute(
        "id"
    )
    colon_relation.click()
    expect(dialog).to_be_visible()
    expect(colon_target).to_be_focused()

    first.click()
    expect(dialog).to_be_hidden()
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    second.click()
    expect(dialog).to_be_hidden()
    assert page.evaluate("() => window.lfIdentityActivations") == ["c", "b:c"]


def test_page_map_keyed_reconciliation_preserves_user_current_location(browser, serve):
    """A synchronous inventory reorder retains its control, query, scroll, and scope."""
    fixture = leaf_page(
        "Keyed Page Map",
        "".join(f'<p id="keyed-{index}">Target {index}</p>' for index in range(15)),
    )
    page = open_page(browser, serve(fixture))
    page.evaluate(
        """async () => {
          const {commandScope, contributionEntry, registerContribution} =
            await window.__lfWidgetApi();
          let swapped = false;
          window.lfKeyedCommandRuns = 0;
          const scope = commandScope('On the retained Page Map action', [{
            id: 'fixture.retained', keys: ['x'],
            title: 'Run the retained action', line: 'run retained',
            run: () => window.lfKeyedCommandRuns += 1,
          }]);
          const ordinary = index => registerContribution({
            key: `keyed-${index}`,
            target: document.querySelector(`#keyed-${index}`),
            read: () => ({entries: [contributionEntry({
              key: 'action', icon: 'dot', label: `Action ${index}`,
            })]}),
            activate: () => {},
          });
          const registrations = Array.from({length: 13}, (_, offset) =>
            ordinary(offset + 1));
          const retained = registrations[11];
          retained.unregister();
          const reordered = registerContribution({
            key: 'keyed-12', target: document.querySelector('#keyed-12'),
            read: () => ({entries: [
              {key: 'keep', icon: 'dot', label: 'Action 12',
                rank: swapped ? 'secondary' : 'primary', scope},
              contributionEntry({key: 'peer', icon: 'dot', label: 'Action 12 peer',
                rank: swapped ? 'primary' : 'secondary'}),
            ]}), activate: () => {},
          });
          let movingTarget = 14;
          registerContribution({
            key: 'moving-group',
            target: () => document.querySelector(`#keyed-${movingTarget}`),
            read: () => ({entries: [contributionEntry({
              key: 'action', icon: 'dot', label: 'Moving action',
            })]}), activate: () => {},
          });
          window.lfKeyedMap = {
            reordered,
            change() {
              movingTarget = 0;
              swapped = true;
              reordered.update({immediate: true});
            },
          };
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    search.fill("Action")
    retained = dialog.get_by_role("button", name="Action 12", exact=True)
    retained.focus()
    retained.evaluate("node => window.lfRetainedMapNode = node")
    dialog.locator(".lf-page-map-list").evaluate(
        "list => { list.scrollTop = list.scrollHeight - list.clientHeight; "
        "window.lfRetainedMapScroll = list.scrollTop; }"
    )

    result = page.evaluate(
        """() => {
          window.lfKeyedMap.change();
          const current = window.lfKeyedMap.reordered.control('keep', 'map', true);
          const actions = [...current.parentElement.children]
            .map(node => node.dataset.lfMarginEntryKey);
          const words = [...document.querySelectorAll(
            '.lf-page-map-list .lf-page-map-action-label-word')]
            .map(node => node.textContent);
          return {
            sameNode: current === window.lfRetainedMapNode,
            focused: document.activeElement === current,
            connected: current.isConnected,
            actions,
            firstWord: words[0],
            query: document.querySelector('.lf-page-map-search').value,
            scroll: document.querySelector('.lf-page-map-list').scrollTop,
            expectedScroll: window.lfRetainedMapScroll,
          };
        }"""
    )
    assert result == {
        "sameNode": True,
        "focused": True,
        "connected": True,
        "actions": ["peer", "keep"],
        "firstWord": "Moving action",
        "query": "Action",
        "scroll": result["expectedScroll"],
        "expectedScroll": result["expectedScroll"],
    }
    assert result["expectedScroll"] > 0
    page.keyboard.press("x")
    assert page.evaluate("() => window.lfKeyedCommandRuns") == 1


def test_g_hints_address_the_visible_window_and_g_shift_m_opens_the_complete_page_map(
    browser, serve
):
    """Visible locations get local hints while the complete Map keeps every location."""
    page = open_page(browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS))
    resized(page, 1440, 300)

    page.keyboard.press("g")
    expect(page.locator(".lf-page-map-dialog")).to_be_hidden()
    locations = page.locator(f'{CHIPS}[data-lf-go-to-kind="Margin entry"]')
    expect(locations).to_have_count(1)

    # When the motion settles, regenerate the map over the newly visible window.
    page.evaluate(
        """() => new Promise(resolve => {
          addEventListener('scrollend', resolve, {once: true});
          const target = document.querySelector('#map-11');
          document.scrollingElement.scrollTo(0, target.offsetTop - 100);
        })"""
    )
    expect(locations).to_have_count(1)
    page.keyboard.type(address_code(page, "Margin entry", "map-11"))
    preview = page.locator(".lf-margin-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("Map note 11")
    # Out of the thread onto what it is about, then letting go of that takes the card.
    page.keyboard.press("Escape")
    expect(page.locator("#map-11")).to_be_focused()
    expect(preview).to_be_visible()
    page.keyboard.press("Escape")
    expect(preview).to_be_hidden()

    # This test is arranging a second starting view, not exercising scroll motion.
    # An earlier scrollend can resolve a smooth return before that return is done,
    # leaving the next `g` press to race the old motion.
    page.evaluate(
        "() => document.scrollingElement.scrollTo({top: 0, behavior: 'instant'})"
    )
    scroll_settled(page)
    before_sheet = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.locator(".lf-page-map-group")).to_have_count(12)
    expect(dialog).to_contain_text("Map note 12")
    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    expect(search).to_be_focused()
    search.fill("Map note 12")
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(1)
    expect(dialog.locator(".lf-page-map-group:visible")).to_contain_text("Map note 12")
    search.fill("")
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(12)
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before_sheet


# The phone's sheet and a window too short for the full list.
@pytest.mark.parametrize("viewport", [(390, 844), (1440, 300)])
def test_page_map_filtering_keeps_search_and_close_in_place(browser, serve, viewport):
    """Filtering changes the list below the search, keeping the sheet's top and the
    controls the user is operating fixed. A full list still reaches its final row."""
    page = open_page(browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS))
    resized(page, *viewport)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    close = dialog.get_by_role("button", name="Close Page Map", exact=True)
    groups = dialog.locator(".lf-page-map-group:visible")
    expect(groups).to_have_count(12)
    expect(search).to_be_focused()
    search_field = dialog.locator(".lf-page-map-search")
    before = {"search": search_field.bounding_box(), "close": close.bounding_box()}
    top = dialog.bounding_box()["y"]

    for query, count in [("Map note 12", 1), ("No such map entry", 0), ("", 12)]:
        if query:
            search.fill(query)
        else:
            search_field.get_by_role("button", name="Clear entry").click()
            expect(search).to_have_value("")
            expect(search).to_be_focused()
        expect(groups).to_have_count(count)
        rendered(page)
        assert search.get_attribute("aria-keyshortcuts") == (
            "ArrowDown Enter" if count else None
        )
        assert search_field.bounding_box() == before["search"]
        assert close.bounding_box() == before["close"]
        assert dialog.bounding_box()["y"] == top
        assert (
            dialog.bounding_box()["y"] + dialog.bounding_box()["height"] <= viewport[1]
        )

    page.keyboard.press("ArrowDown")
    page.keyboard.press("End")
    rows = dialog.locator("button.lf-page-map-action")
    expect(rows.last).to_be_focused()
    rendered(page)
    list_box = dialog.locator(".lf-page-map-list").bounding_box()
    last = rows.last.bounding_box()
    assert last["y"] >= list_box["y"]
    assert last["y"] + last["height"] <= list_box["y"] + list_box["height"] + 1
    assert dialog.locator(".lf-page-map-list").evaluate("node => node.scrollTop") > 0
    assert close.bounding_box() == before["close"]


def test_the_page_map_dialog_walks_its_rows_from_the_search(browser, serve):
    """The dialog is a list under a search: Down leaves the search for the first row,
    Up and Down then step between rows rather than scrolling the page behind the modal,
    and Enter in the search opens the first row it matches."""
    page = open_page(browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS))
    resized(page, 1440, 600)
    before = page.evaluate("() => document.scrollingElement.scrollTop")
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    rows = dialog.locator("button.lf-page-map-action")
    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    expect(search).to_be_focused()

    page.keyboard.press("ArrowDown")
    expect(rows.nth(0)).to_be_focused()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    expect(rows.nth(2)).to_be_focused()
    page.keyboard.press("ArrowUp")
    expect(rows.nth(1)).to_be_focused()
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before

    search.fill("Map note 12")
    search.focus()
    page.keyboard.press("Enter")
    expect(dialog).to_be_hidden()
    # The destination owner opens the compact thread when Threads is closed;
    # its card is the reading stop and c explicitly enters its reply.
    thread_id = next(
        event["id"]
        for event in events_model.read_events(serve.page_dir)
        if event.get("text") == "Map note 12"
    )
    thread = page.locator(
        f'.lf-margin-preview .lf-page-thread[data-thread="{thread_id}"]'
    )
    expect(thread).to_be_focused()
    expect(thread).to_contain_text("Map note 12")
    page.keyboard.press("c")
    expect(thread.locator("leaf-text")).to_be_focused()


def test_the_chrome_names_an_obligation_by_its_question(browser, serve):
    """An obligation is named by its heading, not its heading run into its options and their
    chips: the card in the panel's On me view, and the Page Map group for it, whose one
    row says why the obligation is there rather than naming it a second time."""
    page = open_page(browser, serve(OBLIGATION_PAGE))
    page.keyboard.press("g")
    page.keyboard.press("Shift+m")
    panel_settled(page, view="queue")
    row = page.locator(f"{panel_view('queue')} .lf-fp-on-item").first
    # The card names the Ask by its question; its options stand below as answers.
    expect(row.locator(".lf-fp-on-title, .lf-fp-prompt").first).to_have_text(
        "Which jobs are worth starting?"
    )
    page.keyboard.press("Escape")

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    group = dialog.locator(".lf-page-map-group").filter(
        has=page.get_by_role(
            "heading", name="question · Which jobs are worth starting?"
        )
    )
    expect(group).to_have_count(1)
    expect(group.locator(".lf-page-map-action")).to_have_text(["Waiting on me"])


def test_a_finger_opens_the_page_map_on_its_first_row(browser, serve):
    """Focusing the search on a phone raises the soft keyboard over the list the finger
    came to tap, so a coarse pointer opens the map on its first row instead."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True
    )
    page = open_page(
        browser, serve(PAGE_MAP_PAGE, events=PAGE_MAP_EVENTS), context=context
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog.locator("button.lf-page-map-action").first).to_be_focused()


def test_g_hints_reach_a_late_visible_action_only_location(browser, serve):
    """A late action-only location is reachable while it is visible."""
    fixture = leaf_page(
        "Late action location",
        "".join(
            f'<p id="action-{index}" style="min-height: 90px">Capture {index}</p>'
            for index in range(30)
        ),
    )
    page = open_page(browser, serve(fixture))
    resized(page, 1440, 900)
    page.evaluate("""async () => {
      const {contributionEntry, registerContribution} =
        await window.__lfWidgetApi();
      for (let index = 0; index < 30; index++) {
        registerContribution({key: `capture-${index}`,
          target: document.querySelector(`#action-${index}`),
          read: () => ({entries: [contributionEntry({key: 'review', glyph: 'R',
            label: 'Review capture'})]}), activate: () => {},
        });
      }
    }""")
    page.locator("#action-29").scroll_into_view_if_needed()
    margins_laid_out(page)
    page.evaluate(RELEASE_FOCUS)
    review = page.locator('[data-lf-margin-for="action-29"]').get_by_role(
        "button", name="Review capture", exact=True
    )
    # The hint layer offers on-screen locations, including entries late in the
    # inventory when their earlier peers have scrolled out of view.
    expect(review).to_be_in_viewport()

    page.keyboard.press("g")
    target = review.evaluate(
        "button => button.closest('[data-lf-margin-for]').dataset.lfMarginFor"
    )
    page.keyboard.type(address_code(page, "Margin entry", target))
    expect(review).to_be_focused()


def test_g_hints_press_each_visible_page_map_margin_entry(browser, serve):
    """Each margin entry has an exact route; local draft editing stays outside that map."""
    page = open_page(
        browser,
        serve(
            leaf_page(
                "Margin entry behavior",
                """
<p>Replace
  <lf-suggestion id="address-action">
    <lf-old>the first phrase</lf-old><lf-new>the second phrase</lf-new>
  </lf-suggestion>.</p>
<lf-draft id="address-disclosure"><pre>Keep this text editable.</pre></lf-draft>
""",
            )
        ),
    )
    resized(page, 1440, 900)
    action = page.get_by_role(
        "button", name="Accept the suggested change: the second phrase", exact=True
    )
    disclosure = draft_control(page, "edit", "address-disclosure")
    page.keyboard.press("g")
    suggestion_hints = page.locator(
        f'{CHIPS}[data-lf-go-to-kind="Margin entry"]'
        '[data-lf-go-to-target="address-action"]'
    )
    expect(suggestion_hints).to_have_count(2)
    with sending(page, "the addressed suggestion's acceptance"):
        page.keyboard.type(
            address_code(page, "Margin entry", "address-action", "accept")
        )
    expect(page.locator("#address-action lf-old")).to_be_hidden()
    expect(page.locator("#address-action lf-new")).to_be_visible()

    with sending(page, "the withdrawal of the addressed action"):
        page.keyboard.press("z")
    expect(action).to_be_visible()
    expect(page.locator("#address-action lf-old")).to_be_visible()

    with sending(page, "the addressed suggestion's rejection"):
        go_to_address(page, "Margin entry", "address-action", "reject")
    expect(page.locator("#address-action lf-old")).to_be_visible()
    expect(page.locator("#address-action lf-new")).to_be_hidden()

    with sending(page, "the withdrawal of the addressed rejection"):
        page.keyboard.press("z")
    expect(action).to_be_visible()

    page.keyboard.press("g")
    expect(
        page.locator(
            f'{CHIPS}[data-lf-go-to-kind="Margin entry"]'
            '[data-lf-go-to-target="address-disclosure"]'
        )
    ).to_have_count(0)
    page.keyboard.press("Escape")
    expect(page.locator("#address-disclosure leaf-text")).to_have_count(0)
    disclosure.click()
    expect(page.locator("#address-disclosure leaf-text")).to_be_focused()
    expect(disclosure).to_be_hidden()


def test_g_shift_m_exposes_dense_suggestion_verdicts_as_real_buttons(browser, serve):
    """Late action-only targets keep their verbs in the complete Page Map."""
    page = open_page(browser, serve(DENSE_SUGGESTIONS_PAGE))
    resized(page, 1440, 900)
    page.evaluate(
        """() => {
          const prefix = document.createElement('span');
          prefix.textContent = 'A deliberately long introduction places the remembered words later: ';
          document.querySelector('#bg-neighbors').prepend(prefix);
        }"""
    )

    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    expect(dialog).to_be_visible()
    for title, word in (
        ("rewrite · two → three", "three"),
        ("rewrite · red → blue", "blue"),
        ("rewrite · large → small", "small"),
    ):
        group = dialog.locator(".lf-page-map-group").filter(has_text=title)
        expect(
            group.get_by_role("button", name=f"Accept the suggested change: {word}")
        ).to_be_visible()
        expect(
            group.get_by_role("button", name=f"Reject the suggested change: {word}")
        ).to_be_visible()

    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    search.fill("Pack")
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(3)
    expect(dialog.locator(".lf-page-map-group:visible")).to_contain_text(
        ["two → three", "red → blue", "large → small"]
    )
    dialog.locator(".lf-page-map-group:visible").first.get_by_role(
        "button", name="Accept the suggested change: three"
    ).focus()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#bg-neighbors');
          const word = [...passage.childNodes].find(
            node => node.nodeType === Node.TEXT_NODE && node.textContent.includes('Pack')
          );
          word.textContent = word.textContent.replace('Pack', 'Carry');
          window.dispatchEvent(new Event('resize'));
        }"""
    )
    expect(search).to_be_focused()
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(0)
    expect(
        dialog.get_by_text("No matching actions, statuses, or locations")
    ).to_be_visible()
    page.evaluate(
        """() => {
          const passage = document.querySelector('#bg-neighbors');
          const word = [...passage.childNodes].find(
            node => node.nodeType === Node.TEXT_NODE && node.textContent.includes('Carry')
          );
          word.textContent = word.textContent.replace('Carry', 'Pack');
          window.dispatchEvent(new Event('resize'));
        }"""
    )
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(3)
    search.fill("red → blue")
    expect(dialog.locator(".lf-page-map-group:visible")).to_have_count(1)
    red = dialog.locator(".lf-page-map-group").filter(has_text="rewrite · red → blue")
    reject = red.get_by_role(
        "button", name="Reject the suggested change: blue", exact=True
    )
    reject.evaluate("button => button.dataset.testIdentity = 'held'")
    page.evaluate(
        """async () => {
          window.dispatchEvent(new Event('resize'));
          await new Promise(requestAnimationFrame);
          await new Promise(requestAnimationFrame);
        }"""
    )
    expect(reject).to_have_attribute("data-test-identity", "held")
    reject.focus()
    with sending(page, "the reject"):
        page.keyboard.press("Enter")
    sent = events_model.read_events(serve.page_dir)[-1]
    assert (sent["kind"], sent["widget"], sent["detail"]["outcome"]) == (
        "action",
        "bg-neighbor-b",
        "reject",
    )


def test_the_page_map_walk_stops_at_both_visible_edges(browser, serve):
    """The Page Map is a vertical list: its arrows stop at its first and last markers,
    while Home and End remain direct routes to those edges."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    markers = page.locator(".lf-margin-marker:visible")
    assert markers.count() > 1, "the Page Map has no pair of visible markers to walk"

    markers.first.focus()
    page.keyboard.press("Home")
    first = page.locator(":focus").get_attribute("aria-label")
    assert first and page.locator(":focus").evaluate(
        "node => node.matches('.lf-margin-marker')"
    )
    page.keyboard.press("ArrowUp")
    assert page.locator(":focus").get_attribute("aria-label") == first

    page.keyboard.press("End")
    last = page.locator(":focus").get_attribute("aria-label")
    assert last and last != first
    page.keyboard.press("ArrowDown")
    assert page.locator(":focus").get_attribute("aria-label") == last

    page.keyboard.press("Home")
    assert page.locator(":focus").get_attribute("aria-label") == first


def test_a_margin_entry_walk_position_stays_out_of_its_visible_word(browser, serve):
    """Which location of how many, and how far down, is how a user listening places a
    margin entry in the walk. Painted, the same words read as progress toward something, which
    is not what they say, so they belong to the accessible name alone."""
    subject = (
        "Which jobs should we start before the first frost reaches the garden, "
        "while keeping the bird bath available and leaving enough time to replace "
        "the mounts before the next storm arrives?"
    )
    source = OBLIGATION_PAGE.replace("Which jobs are worth starting?", subject)
    page = open_page(
        browser, serve(source, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION])
    )
    resized(page, 1440, 900)
    buttons = page.evaluate(
        """() => [...document.querySelectorAll('.lf-margin-entry')].map(control => ({
          name: control.getAttribute('aria-label'),
          word: control.querySelector(':scope > .lf-margin-entry-label').textContent,
        }))"""
    )
    placed = [button for button in buttons if re.search(r"\d+ of \d+", button["name"])]
    assert placed, "no margin entry announced where it stands in the walk"
    for button in placed:
        assert "percent down" in button["name"], button
    for button in buttons:
        assert not re.search(r"\d+ of \d+|percent down", button["word"]), button
    named = next(button["name"] for button in placed if "Which jobs" in button["name"])
    assert named.index("percent down") < named.index("Which jobs"), named
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    expect(page.locator(".lf-page-map-group h3", has_text=subject)).to_have_count(1)


def test_page_map_only_origins_do_not_count_as_margin_entries(browser, serve):
    """Page Map includes durable provenance even when the margin has no margin entry for it.

    A user listening to the margin walk hears only the margin entries they can visit. The
    Page Map count remains the count of every mapped target, including provenance-only
    locations.
    """
    comment = {
        "kind": "comment",
        "author": "user",
        "revision": 1,
        "text": "Check the squirrel baffle fit.",
        "anchor": {"section": "t-parser"},
    }
    url = serve(REPORT_PAGE, events=[comment])
    sent = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "report",
            str(serve.page_dir),
            "t-mounts",
            "status",
            "value=active",
        ],
    )
    assert sent.exit_code == 0, sent.output

    page = open_page(browser, url)
    resized(page, 1440, 900)
    marker = page.locator('[data-lf-margin-for="t-parser"] > .lf-margin-marker')
    expect(marker).to_have_attribute("aria-label", re.compile(r"^Thread, 1 of 1,"))
    expect(page.locator('[data-lf-margin-for="t-mounts"]')).to_have_count(0)
    expect(page.get_by_role("navigation", name="Page Map, 2 locations")).to_have_count(
        1
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    origin = page.get_by_role(
        "button", name=re.compile(r"^Open reported state: Reported state")
    )
    origin.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#t-mounts")).to_be_focused()
    expect(marker).not_to_be_focused()


def test_a_mouse_finds_page_map_under_navigate_only_where_the_rail_falls(
    browser, serve
):
    """A window too narrow for the margin's rail draws its markers as pins, so the
    leaf's Navigate offers the whole map to a mouse too, with its count and keys. Where
    the rail stands, the map stays a key's convenience the menu leaves out."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 760, 900)
    margins_laid_out(page)
    expect(
        page.locator('.lf-margin-cluster[data-lf-place="pin"]').first
    ).to_be_visible()
    row = panel_control(page, "map", at="navigate")
    expect(row.locator(".lf-fp-value")).to_have_text(re.compile(r"^\d+$"))
    expect(row.locator("kbd")).to_have_text(["g", "P"])
    row.click()
    expect(page.locator(".lf-page-map-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".lf-page-map-dialog")).to_be_hidden()

    resized(page, 1440, 900)
    margins_laid_out(page)
    expect(
        page.locator('.lf-margin-cluster[data-lf-place="rail"]').first
    ).to_be_visible()
    expect_panel_offers(page, "map", offered=False, at="navigate")


@pytest.mark.parametrize("opener", ["keyboard", "finger"])
def test_the_small_screen_map_is_a_complete_accessible_sheet(browser, serve, opener):
    """Where the rail falls the markers are pins, small targets over the content, and
    the whole map opens as a touch-sized index beside them: by `g Shift+P`, or for a
    finger, which has no keys, from the leaf's menu under Navigate."""
    context = (
        browser.new_context(
            viewport={"width": 390, "height": 760}, has_touch=True, is_mobile=True
        )
        if opener == "finger"
        else None
    )
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
        context=context,
    )
    resized(page, 390, 760)
    margins_laid_out(page)
    expect(
        page.locator('.lf-margin-cluster[data-lf-place="pin"]').first
    ).to_be_visible()

    before = page.evaluate("() => document.scrollingElement.scrollTop")
    if opener == "keyboard":
        page.keyboard.press("g")
        page.keyboard.press("Shift+p")
    else:
        press_visible(page, panel_control(page, "map", at="navigate"), touch=True)
    dialog = page.locator(".lf-page-map-dialog")
    expect(dialog).to_be_visible()
    # A finger arrives on the first row, where a soft keyboard would cover the list.
    expect(
        dialog.locator("button.lf-page-map-action").first
        if opener == "finger"
        else dialog.get_by_role(
            "searchbox", name="Find an action, status, or location in Page Map"
        )
    ).to_be_focused()
    expect(dialog.locator(".lf-page-map-action").first).to_have_css(
        "min-height", "44px"
    )
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    # Contrast is read on the sheet at rest, once its opening fade has ended.
    dialog.evaluate("d => Promise.all(d.getAnimations().map((a) => a.finished))")

    result = Axe().run(
        page,
        options={
            "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a"]},
            "resultTypes": ["violations"],
        },
    )
    assert [
        violation["id"]
        for violation in result.response["violations"]
        if violation["impact"] in {"serious", "critical"}
    ] == []

    # Escape hands the user back where they opened the dialog: the page for `g
    # Shift+P`, the leaf for its menu's row, which went with the menu. The menu the
    # finger went through folds with the dialog rather than standing open behind it,
    # promising a door the user has already been through.
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    if opener == "finger":
        expect(page.locator(".lf-fp-leaf")).to_be_focused()
    else:
        assert page.evaluate("() => document.activeElement === document.body")
    assert page.evaluate("() => document.scrollingElement.scrollTop") == before
    expect(page.locator(PANEL)).not_to_have_attribute("data-menu", "")


def test_the_complete_page_map_survives_a_crossing_to_the_wide_screen(browser, serve):
    """The Page Map is one destination while its compact rail changes posture."""
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 390, 760)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.locator(".lf-page-map-dialog")
    expect(dialog).to_be_visible()

    resized(page, 1200, 900)
    margins_laid_out(page)
    expect(
        page.locator('.lf-margin-cluster[data-lf-place="rail"]').first
    ).to_be_visible()
    expect(dialog).to_be_visible()
    # The obligation stands once, under the row saying where its answer has got to.
    expect(dialog.locator(".lf-page-map-action")).to_have_count(4)
    expect(
        dialog.locator(".lf-page-map-action").filter(
            has_text="options · choose · Which bracket should we use?"
        )
    ).to_have_count(1)
    expect(
        dialog.get_by_role("button", name=re.compile(r"^Open my change"))
    ).to_have_count(0)


def test_an_open_small_screen_map_reconciles_arriving_meanings(browser, serve):
    """The open dialog is a live projection, not a snapshot from its opening press."""
    height = 480
    page = open_page(
        browser,
        serve(OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]),
    )
    resized(page, 390, height)
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.locator(".lf-page-map-dialog")
    actions = dialog.locator(".lf-page-map-action")
    expect(actions).to_have_count(4)
    if height == 480:
        assert dialog.locator(".lf-page-map-list").evaluate(
            "list => list.scrollHeight > list.clientHeight"
        ), "the short dialog must exercise focus through an overflowing list"
    page.keyboard.press("Tab")
    expect(actions.first).to_be_focused()

    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "author": "agent",
            "agent": "Claude",
            "revision": 1,
            "text": "A second reading arrived while the map was open.",
            "anchor": {"section": "bracket"},
        },
    )
    told(page)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="comment"]').locator(
            ".lf-margin-count"
        )
    ).to_have_text("2")
    expect(actions).to_have_count(5)
    expect(actions.first).to_be_focused()


def test_a_live_version_keeps_the_user_on_the_same_margin_location(browser, serve):
    """Replacing authored main must not discard focus held by retained map chrome."""
    version_url = serve(
        OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]
    )
    page = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.focus()
    expect(marker).to_be_focused()

    (serve.page_dir / "index.html").write_text(
        OBLIGATION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(marker).to_be_focused()


def test_a_live_version_retargets_an_open_margin_preview(browser, serve):
    """A retained preview must mark the new document's matching destination."""
    version_url = serve(
        OBLIGATION_PAGE, events=[ACTION_ON_OBLIGATION, COMMENT_ON_OBLIGATION]
    )
    page = open_page(browser, live_url(version_url))
    resized(page, 1440, 900)
    marker = page.locator('.lf-margin-marker[data-lf-kinds~="comment"]')
    marker.click()
    close = page.locator(".lf-margin-preview-close")
    close.focus()
    expect(close).to_be_focused()
    # The card's thread, which the user is located in, marks its element.
    mark = page.locator('.lf-visual-mark-here[data-for="bracket"]')
    expect(mark).to_be_visible()

    (serve.page_dir / "index.html").write_text(
        OBLIGATION_PAGE.replace("Three jobs", "Four jobs")
    )
    told(page)
    expect(page.get_by_role("heading", name="Four jobs")).to_be_visible()
    expect(close).to_be_focused()
    expect(page.locator(".lf-margin-preview")).to_be_visible()
    expect(mark).to_be_visible()


def test_a_version_comparison_joins_the_same_map_and_leaves_with_it(browser, serve):
    """Comparison marks are another projection, not DOM scraped by the map."""
    url = serve(OBLIGATION_PAGE)
    _publish(
        serve.page_dir,
        2,
        OBLIGATION_PAGE.replace("Three jobs", "Four jobs"),
        "The heading now names four jobs.",
    )
    page = open_page(browser, url.replace("v1.html", "v2.html"))

    compare_with(page, 1)
    expect(
        page.locator('.lf-margin-marker[data-lf-kinds~="change"]')
    ).not_to_have_count(0)
    # Pressing the same Compare again ends the comparison.
    compare_with(page, 1)
    expect(page.locator('.lf-margin-marker[data-lf-kinds~="change"]')).to_have_count(0)


@pytest.mark.parametrize("search_again", [False, True], ids=["arrival", "newer-search"])
def test_page_map_disclosure_arrival_yields_to_newer_search(
    browser, serve, search_again
):
    """An expanded entry can reveal its child without reclaiming a newer search field."""
    page = open_page(
        browser, serve(leaf_page("Map disclosure", '<p id="target">Review.</p>'))
    )
    page.evaluate(
        """async () => {
          const {registerContribution, contributionEntry} =
            await window.__lfWidgetApi();
          let expanded = false;
          const registration = registerContribution({
            key: 'disclosure', target: document.querySelector('#target'),
            read: () => ({entries: [
              contributionEntry({key: 'open', label: 'Expand choices', icon: 'more',
                behavior: 'disclosure',
                relation: {kind: 'entries', keys: ['child'], expanded}}),
              contributionEntry({key: 'child', label: 'Revealed choice', icon: 'dot',
                visible: expanded}),
            ]}),
            activate: () => {
              expanded = true;
              registration.update({immediate: true});
            },
          });
        }"""
    )
    page.keyboard.press("g")
    page.keyboard.press("Shift+p")
    dialog = page.get_by_role("dialog", name="Page Map", exact=True)
    door = dialog.get_by_role("button", name="Expand choices", exact=True)
    child = dialog.get_by_role("button", name="Revealed choice", exact=True)
    search = dialog.get_by_role(
        "searchbox", name="Find an action, status, or location in Page Map"
    )
    expect(door).to_be_visible()
    with held_frames(page):
        box = door.bounding_box()
        assert box is not None
        page.mouse.click(box["x"] + 20, box["y"] + 10)
        expect(child).to_be_visible()
        if search_again:
            box = search.bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + 40, box["y"] + 10)
            expect(search).to_be_focused()
    rendered(page)
    expect(search if search_again else child).to_be_focused()


def test_a_crowded_outline_keeps_the_reading_position_when_it_fits_again(
    browser, serve
):
    """An automatic map measurement leaves an outline where its reader scrolled it."""
    source = leaf_page(
        "Crowded outline",
        '<h1 id="title">Crowded outline</h1>'
        '<aside class="sidebar"><lf-toc id="contents"></lf-toc></aside>'
        + "".join(
            f'<section id="row-{index}"><h2>Section {index:02}</h2>'
            '<div style="height:120px"></div></section>'
            for index in range(40)
        ),
    )
    page = open_page(browser, serve(source))
    resized(page, 1400, 700)
    outline = page.get_by_role("navigation", name="On this page")
    first = outline.get_by_role("link", name="Section 00", exact=True)
    expect(page.locator("#contents")).to_have_attribute("data-lf-outline", "")
    first.focus()
    box = outline.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 40, box["y"] + 80)
    page.mouse.wheel(0, 500)
    page.wait_for_function("document.querySelector('.lf-toc-nav').scrollTop > 300")
    scroll_settled(page)
    before = outline.evaluate("node => node.scrollTop")
    document_before = page.evaluate("scrollY")
    resized(page, 1401, 700)
    assert outline.evaluate("node => node.scrollTop") == before
    assert page.evaluate("scrollY") == document_before

    page.keyboard.press("Tab")
    next_link = outline.get_by_role("link", name="Section 01", exact=True)
    expect(next_link).to_be_focused()
    assert outline.evaluate("node => node.scrollTop") < before
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"#row-1$"))
    scroll_settled(page)
    assert (
        page.locator("#row-1").evaluate("node => node.getBoundingClientRect().top")
        < 150
    )
