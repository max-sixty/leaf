"""The surfaces that name keys, the command reference and ARIA, and the passing words
the panel says: every key a surface names is one that works, every key the runtime
binds is named somewhere, news keeps its order, and a page at rest repaints nothing."""

import re

import pytest
from interact_support import append_carried_log_record
from playwright.sync_api import expect
from render_cases_interaction import OBLIGATIONS_PAGE, live_url
from render_cases_navigation import NOTED_PAGE
from render_harness import (
    INLINE_PAGE,
    PANEL_THREAD,
    expect_open_threads,
    open_page,
    page_comment,
    panel_field,
    stamp_page,
    told,
    wait_for_revision,
)

from browser.navigation import expect_walk_position
from browser.threads import open_panel_thread
from leaf.render_checks import rendered

pytestmark = pytest.mark.shifts_unsurveyed


def test_overlapping_identical_live_announcements_are_fresh_changes(browser, serve):
    """Even overlapping identical words give the polite region two arrivals."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.locator(".lf-fp-on-user").focus()
    page.evaluate(
        """async () => {
          window.__lfLiveNode = document.querySelector('.lf-live');
          window.__lfLiveFocus = document.activeElement;
          window.__lfRepeatedAnnouncements = [];
          new MutationObserver(() => {
            const words = document.querySelector('.lf-live').textContent;
            if (words) window.__lfRepeatedAnnouncements.push(words);
          }).observe(document.querySelector('.lf-live'), {
            childList: true,
            subtree: true,
          });
          const {announce} = await window.__lfWidgetApi();
          announce('Same update');
          announce('Same update');
        }"""
    )
    page.wait_for_function(
        "() => window.__lfRepeatedAnnouncements.filter("
        "words => words === 'Same update').length === 2"
    )
    assert page.evaluate(
        """() => document.querySelector('.lf-live') === window.__lfLiveNode
          && document.activeElement === window.__lfLiveFocus"""
    )


def test_registered_shortcuts_are_exposed_to_assistive_technology(browser, serve):
    """The same declarations that paint help expose their active keys through ARIA."""
    page = open_page(browser, serve(OBLIGATIONS_PAGE))

    expect(page_comment(page)).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter"
    )
    page.keyboard.press("Escape")
    expect(page.locator("#live-question .lf-another leaf-text")).to_have_attribute(
        "aria-keyshortcuts", "Enter Meta+Enter Control+Enter"
    )

    page.keyboard.press("m")
    mark = page.locator("#live-question .lf-pick").first
    expect(mark).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space 1"
    )

    page.keyboard.press("?")
    expect(mark).to_have_attribute(
        "aria-keyshortcuts", "ArrowUp ArrowDown Home End Space"
    )
    expect(
        page.locator(
            ".lf-command-reference [role=row]",
            has_text="Next on me",
        ).locator("kbd")
    ).to_have_text("m")
    expect(
        page.locator(
            ".lf-command-reference [role=row]",
            has_text="Previous on me",
        ).locator("kbd")
    ).to_have_text("M")
    expect(
        page.get_by_role("button", name="Close the command reference")
    ).to_have_attribute("aria-keyshortcuts", "Escape")
    page.keyboard.press("Escape")


def test_a_key_the_runtime_binds_is_a_key_some_surface_names(browser, serve):
    """One declaration per binding, and every surface is a projection of it. The d/u
    reading-page pair is the case that named this: a runtime key must be visible wherever
    the keyboard vocabulary is projected.

    Where it is projected is the reference, which is read for the words — a key named on
    no surface at all is what this refuses.

    It is refused now, where a scope is declared, so the next binding written without a
    word fails on the page that introduces it rather than going quiet on every page after
    it. A row that presses nothing needs none — F7 is the browser's caret browsing, real
    and worth knowing and not what the next press does."""
    page = open_page(browser, serve(NOTED_PAGE))
    page.keyboard.press("?")
    expect(page.locator(".lf-command-reference")).to_contain_text("Page down")
    expect(page.locator(".lf-command-reference")).to_contain_text("Page up")
    expect(page.locator(".lf-command-reference")).to_contain_text("Caret browsing")
    page.keyboard.press("Escape")

    refused = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.no-line', keys: ['F2'],
                run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "title" in refused, refused

    # The other half of what this gate is for, and the quieter failure. `answers` asks
    # after Mod, Alt and Shift by name and reads every other prefix as absent, so a
    # binding written `Ctrl+k` is not a key that never fires — it is `k`, which fires on
    # a bare press while both surfaces spell the chip "Ctrl+k" and the press the chip
    # names does nothing. A declaration that means a different key than it says is the
    # one thing no surface can project, so it is refused where declarations enter.
    modified = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          try {
            commands(document.body, 'A project scope', [
              { id: 'test.bad-modifier', keys: ['Ctrl+k'],
                title: 'a modifier the matcher never asks about',
                line: 'a key that is really just k', run: () => {} },
            ]);
            return 'declared';
          } catch (e) {
            return e.message;
          }
        }"""
    )
    assert "Ctrl is no modifier" in modified, modified
    assert "Mod, Alt, Shift" in modified, modified

    # Routes split one compact row into separately addressable commands. Every declared
    # binding therefore needs exactly one route: otherwise dispatch can gain a press that
    # the reference omits from its presentation projection.
    routed = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          const declare = row => {
            try {
              commands(document.body, 'A routed project scope', [row]);
              return 'declared';
            } catch (e) {
              return e.message;
            }
          };
          return {
            missing: declare({
              id: 'test.missing-route', keys: ['F2', 'F3'],
              title: 'Move either way', line: 'move either way', run: () => {},
              routes: [{
                id: 'test.missing-route.first', binding: 'F2',
                title: 'Move one way', line: 'move one way',
              }],
            }),
            duplicate: declare({
              id: 'test.duplicate-route', keys: ['F4'],
              title: 'Move once', line: 'move once', run: () => {},
              routes: [
                {
                  id: 'test.duplicate-route.first', binding: 'F4',
                  title: 'Move first', line: 'move first',
                },
                {
                  id: 'test.duplicate-route.second', binding: 'F4',
                  title: 'Move second', line: 'move second',
                },
              ],
            }),
          };
        }"""
    )
    assert "has no route for F3" in routed["missing"], routed
    assert "routes F4 twice" in routed["duplicate"], routed

    # A registered result may deliberately precede the platform's own half of a press.
    # It still enters through the same register — and therefore the same surfaces and
    # scoping — but the dispatcher must not cancel that native result. The versions menu
    # uses this for the Tab that closes it before the browser moves focus past its door.
    native = page.evaluate(
        """async () => {
          const { commands } = await window.__lfWidgetApi();
          const owner = document.createElement('div');
          owner.tabIndex = -1;
          document.body.append(owner);
          owner.focus();
          let ran = 0;
          commands(owner, 'A native companion', [
            { id: 'test.native-companion', keys: ['F2'],
              title: 'Run before the browser', line: 'run first',
              native: true, run: () => ran++ },
          ]);
          const event = new KeyboardEvent(
            'keydown', {key: 'F2', bubbles: true, cancelable: true}
          );
          owner.dispatchEvent(event);
          owner.remove();
          return {ran, prevented: event.defaultPrevented};
        }"""
    )
    assert native == {"ran": 1, "prevented": False}, native


def test_a_coarse_pointer_keeps_useful_status_without_keyboard_hints(browser, serve):
    """A phone names no keys but keeps passing words and the walk's position, and the
    page's room stays whole: obligation hints still find what the page shows."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(OBLIGATIONS_PAGE), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches"), (
        "the touch fixture never reached Leaf's coarse-pointer rules"
    )
    expect(page.locator(".lf-fp-field .lf-key-badge")).to_have_count(0)

    page.evaluate(
        """async () => {
              (await window.__lfWidgetApi()).notice('Saved');
              dispatchEvent(new Event('resize'));
            }"""
    )
    expect(panel_field(page)).to_have_attribute("placeholder", "Saved")

    # And the page is still whole underneath. Everything that asks how far down the
    # page reaches asks it of the chrome's box, and one with no box answers 0 — the top
    # of the window — which reads as "all of it is covered". Obligation hints and the search's
    # own highlight are drawn for boxes above that answer, so a tablet got `s` naming
    # nothing and `/` painting no match, with the page itself intact and nothing on
    # screen saying why.
    page.keyboard.press("s")
    expect(page.locator(".lf-target-picker-hint").first).to_be_visible()
    page.keyboard.press("Escape")

    page.keyboard.press("m")
    expect_walk_position(page, "1 of 4 waiting on me · Options")


def test_a_page_at_rest_repaints_the_panel_only_when_the_state_moves(browser, serve):
    """A repaint that schedules the next one is a loop no surface reports.

    The banner's More once wrote `aria-expanded` inside the shared repaint, which the
    runtime watches over the whole document, so the paint delivered its own write back
    to itself and asked for another frame, and the page went on repainting for as long
    as it was open — every browser test on every page paying for it. The panel stands
    in the same repaint and writes the same kind of state.

    Nothing on screen says so, which is why the reading is the page's own frames at
    rest. A panel that keeps repainting while neither the user nor the application
    moves is repainting for a reason the page has not got."""
    page = open_page(browser, serve(NOTED_PAGE, comments=2))
    page.evaluate(
        """() => {
          const probe = { frames: 0, paints: 0 };
          window.__lfProbe = probe;
          new MutationObserver(() => { probe.paints += 1; }).observe(
            document.querySelector(".lf-floating-panel"),
            { attributes: true, childList: true, subtree: true },
          );
          const tick = () => { probe.frames += 1; requestAnimationFrame(tick); };
          requestAnimationFrame(tick);
        }"""
    )
    # The window is the page's own frames rather than a duration: a loop of this shape
    # repaints once per frame whatever the machine's speed, so counting frames is what
    # makes the contrast the same size on a loaded runner as on a desk.
    page.wait_for_function("() => window.__lfProbe.frames >= 90")
    probe = page.evaluate("() => window.__lfProbe")

    assert probe["paints"] <= 1, (
        "the panel repainted without the state moving over "
        f"{probe['frames']} frames: {probe}"
    )


def test_a_field_names_no_key_to_a_finger(browser, serve):
    """A touch screen names no keys because they are presses the user cannot make, and
    a text field's placeholder is the same advert: the page's box said "Comment on the
    page c" and a thread's box "Reply c" to a phone. Whether a surface advertises keys
    is one reading (`advertisesKeys`), asked for the key that enters a box as well as
    the one that sends it."""
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=True
    )
    page = open_page(browser, serve(INLINE_PAGE, comments=2), context=context)
    assert page.evaluate("() => matchMedia('(pointer: coarse)').matches")
    badge = page.locator(".lf-fp-field .lf-key-badge")
    general = page_comment(page)
    expect(general).not_to_have_attribute("placeholder", re.compile(r" c$"))
    expect(badge).to_have_count(0)
    thread = page.evaluate(
        "async () => (await window.__lfWidgetApi()).readThreads().threads[0].id"
    )
    open_panel_thread(page, thread)
    reply = panel_field(page)
    expect(reply).to_have_attribute("name", "reply")
    expect(reply).not_to_have_attribute("placeholder", re.compile(r" c$"))
    reply.focus()
    expect(reply).not_to_have_attribute("placeholder", re.compile(r" c$"))
    expect(badge).to_have_count(0)


# The register's own answer to which commands a press can run, read with focus on the
# page, since the command reference is a modal scope that shadows the page once open:
# `runs`, what the page's enabled keys run from here; `runs_any`, what the reference can
# run from here, a command whose shortcut the user turned off included; `dead`, the
# commands of a scope the reference filters by liveness (one the user is located in, or one
# that asks to be) that cannot run now, by the liveness each row declares for the
# reference (`commandReferenceWhen`, else `when`); and `absent`, the commands of scopes
# this page has not got. A command id another present scope also declares, where the
# reference lists it as available there, is neither dead nor absent.
KEYBOARD_REGISTER = """async () => {
    const {availableCommandRoutes, stack, allBindings, commandEntries,
      commandPresentations, live, pageScopes, commandDeclarationsWithin} =
        await window.__lfCheckApi();
    const scopeIdentity = scope => scope.identity ?? scope;
    const running = (options) => {
        const ids = new Set();
        for (const [row, keys] of availableCommandRoutes(options))
            for (const key of keys)
                for (const {id} of commandEntries(row, [key])) ids.add(id);
        return ids;
    };
    const declared = (rows) => rows.flatMap((row) => commandPresentations(
        row, allBindings(row), {includeUnavailable: true}).map(({id}) => id));
    const has = (scope) => !scope.when || scope.when();
    const scopes = [
        ...pageScopes().flat().filter((scope) => typeof scope === 'object'),
        ...commandDeclarationsWithin(document.body).map(({scope}) => scope),
    ];
    const open = stack();
    const filtered = new Set([...open, ...scopes.filter(
        (scope) => has(scope) && scope.liveInCommandReference)].map(scopeIdentity));
    const runs = running(), runsAny = running({commands: true});
    const elsewhere = new Set(declared(scopes.filter(
        (scope) => has(scope) && !filtered.has(scopeIdentity(scope))
    ).flatMap((scope) => scope.rows)));
    const present = new Set(declared(scopes.filter(has).flatMap((scope) => scope.rows)));
    const dead = declared([...open, ...scopes].filter(
        (scope) => filtered.has(scopeIdentity(scope))
    ).flatMap((scope) => scope.rows).filter((row) =>
        !(row.commandReferenceWhen ? row.commandReferenceWhen() : live(row))));
    const missing = declared(scopes.filter((scope) => !has(scope))
        .flatMap((scope) => scope.rows));
    return {
        runs: [...runs],
        runs_any: [...runsAny],
        dead: [...new Set(dead)].filter((id) => !runsAny.has(id) && !elsewhere.has(id)),
        absent: [...new Set(missing)].filter((id) => !present.has(id)),
    };
}"""


def shown_commands(page):
    """What the register says can run, and the command ids the command reference names,
    read in that order and through the reference's `?` route."""
    register = page.evaluate(KEYBOARD_REGISTER)
    help_el = page.locator(".lf-command-reference")
    page.keyboard.press("?")
    expect(help_el).to_be_visible()
    reference = help_el.locator("[role=row][data-lf-command]").evaluate_all(
        "rows => rows.map(r => r.dataset.lfCommand)"
    )
    runnable = help_el.locator(
        'button[data-lf-command][data-lf-available="true"]'
    ).evaluate_all("buttons => buttons.map(b => b.dataset.lfCommand)")
    page.keyboard.press("Escape")
    expect(help_el).to_be_hidden()
    return (
        {key: set(ids) for key, ids in register.items()},
        set(reference),
        set(runnable),
    )


def test_a_key_on_screen_is_a_key_that_works(browser, serve):
    """Every command a keyboard surface names is one the dispatcher will run.

    The command reference names no command of a scope this page has not got, and none
    that cannot run in a scope where it filters by liveness; a row it marks runnable
    runs. Liveness is one declaration the dispatcher and the reference ask, so the test
    holds the reference to the register by command id rather than by its words, in the
    states that change what is live: a thread walk only once there are threads, and
    still over resolved ones; a thread's own commands only once the page has one; and
    the versions open from the page."""
    url = serve(NOTED_PAGE)
    d = serve.page_dir
    page = open_page(browser, live_url(url))

    def surfaces_name_what_runs():
        register, reference, runnable = shown_commands(page)
        assert runnable <= register["runs_any"], (
            f"the command reference offers {runnable - register['runs_any']} "
            "as runnable, which would not run"
        )
        assert not reference & register["dead"], (
            f"the command reference names {reference & register['dead']}, "
            "which cannot run where it applies"
        )
        assert not reference & register["absent"], (
            f"the command reference names {reference & register['absent']}, "
            "from a scope this page has not got"
        )
        return register, reference

    # No threads and one version: there is nothing to walk, so the walks are dead
    # the current location, and the page has no thread scope and no link.
    register, reference = surfaces_name_what_runs()
    assert {"thread.next", "thread.previous"} <= register["dead"]
    assert {"thread.primary", "link.follow"} <= register["absent"]
    # The dispatcher asks the same declaration: neither half of the walk runs.
    page.keyboard.press("t")
    page.keyboard.press("Shift+t")
    rendered(page)
    expect(page.locator(PANEL_THREAD)).to_have_count(0)

    # Threads arrive, making the walk live and the thread scope the page's own.
    for text in ["A thread.", "Another."]:
        append_carried_log_record(
            d, {"kind": "comment", "author": "user", "revision": 1, "text": text}
        )
    told(page)
    expect_open_threads(page, 2)
    register, reference = surfaces_name_what_runs()
    assert {"thread.next", "thread.previous"} <= register["runs"]
    assert "thread.primary" in reference

    # The walk's key, pressed, stands the user on a thread open in the panel, where the
    # thread's own commands run.
    page.keyboard.press("t")
    expect(page.locator(PANEL_THREAD)).to_be_focused()
    register, reference = surfaces_name_what_runs()
    assert "thread.resolution.toggle" in register["runs"]

    # A second version gives the versions somewhere to go. Their walk is the Versions
    # list's own, declared while it stands in the menu, so no surface names it here.
    stamp_page(d, NOTED_PAGE, "two")
    wait_for_revision(page, 2)
    register, reference = surfaces_name_what_runs()
    assert "version.open" in register["runs"]
    assert not {"version.later", "version.earlier"} & reference

    # With every thread resolved and a resolved one open, the reference still names
    # only what runs.
    threads = page.evaluate(
        "async () => (await window.__lfWidgetApi()).readThreads().threads.map(t => t.id)"
    )
    for n, thread in enumerate(threads, start=1):
        open_panel_thread(page, thread)
        page.locator(".lf-fp-settle").click()
        expect_open_threads(page, 2 - n)
    open_panel_thread(page, threads[0]).focus()
    surfaces_name_what_runs()
