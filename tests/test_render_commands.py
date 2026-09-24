"""Render, shot, and browser-gate command tests."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import install_payload
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import render_checks as render_checks_model
from leaf.render_gate import browser as browser_model
from leaf.render_gate import version as render_gate_model
from playwright.sync_api import expect
from render_cases_layout import (
    BADGE_CHROME,
    PAINTED_IN_SILENCE_PAGE,
    PRINT_LOSS_PAGE,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    UNPARSABLE_DIAGRAM,
    flip_point,
    shown_frames,
    solid_png,
)
from render_harness import (
    CARRIED_PAGE,
    EXAMPLE_MEDIA,
    EXAMPLE_PACKAGES,
    INLINE_PAGE,
    LONG_PAGE,
    REPLY_HOST_PAGE,
    SETTLED_PAGE,
    SPECIMEN_MARKUP,
    SPECIMEN_TEXT,
    author_test_widget,
    open_page,
    page_registry,
    primed,
    resized,
    scroll_settled,
    shortcut_bar_text,
)

pytestmark = pytest.mark.nightly


def unnamed_browser():
    """This process's environment with every browser variable cleared, for a child
    whose subject is the launch a host that named none gets.

    Unnaming means clearing all of them, not leaf's alone: `named_executable` reads
    three, and empty is none in each. The GitHub runner image really does export
    CHROME_BIN, so a test that cleared one and inherited the rest would run the named
    arm twice and never reach the channel it meant to check."""
    return os.environ | dict.fromkeys(browser_model.VARIABLES, "")


def test_the_gate_passes_a_page_that_carries_a_comment(browser, serve):
    """The gate refuses words under `.lf-ui` inside a widget, because a widget reaching for
    that marker is how a user ends up unable to comment on a heading they can see. The
    line saying how many comments are on a passage wears the same marker and sits wherever
    the passage does — inside the widget, when that is where the comment was made. Unless
    the gate knows the difference, one comment on an option is a page nobody can hand over,
    and every page the sweep above renders is a page with no comments on it.

    The pass hunting words drawn on other words has to know the same difference, and
    knows it as a float the runtime hangs over the page. The resting control is drawn
    nowhere twice over — transparent, and clipped to the pixel it is parked on — and the
    paint check correctly omits it for either reason. This test takes both away to plant
    the fault it is about: its characters then fall down the document through the
    paragraphs under the passage, painted. Holding the runtime float out is the only
    thing keeping the reading clean, so it is taken twice: once as the gate runs it, and
    once with the hold defeated, where it has to report.

    The hold is the float predicate rather than a class named in the skip list, which is
    what the second reading has to reach for now: the line is out-of-flow chrome like a
    suggestion's controls, so one rule answers for both and a name beside it would be the
    same guarantee kept twice."""
    # The last option, because the unheld half below needs the line to land on words:
    # the note is the holder's last child, so its characters fall from the end of the
    # option's own prose, and from a mid-group option they fall through the whitespace
    # tails of the shorter cells below and are spent before any paragraph. From the
    # group's last option they cross straight into #p, whose full-width lines have a
    # word at any x the option's prose can end on.
    url = serve(INLINE_PAGE, anchored=[("opt-b", "quietly puts one back")])
    page = open_page(browser, url)
    # Vacuous otherwise: the gate has to be looking at a page that has the line on it.
    page.wait_for_function(
        "() => document.querySelectorAll('.lf-mark-note').length === 1"
    )
    # Give the real runtime control paint so this tests the floating exemption rather
    # than passing because the ordinary resting state is not drawn. Both halves of "not
    # drawn": the transparency, and the one-pixel box whose hidden overflow keeps the
    # characters off the screen however opaque they are.
    # The one-pixel box stays: it is what turns the label into a column of characters
    # falling through the paragraphs, which is the shape of the fault.
    page.locator(".lf-mark-note").evaluate(
        "note => Object.assign(note.style, {opacity: '1', overflow: 'visible'})"
    )
    held = render_checks_model.evaluate_probe(page, "coveredWords")
    reported = render_checks_model.evaluate_probe(
        page, "coveredWords", {"holdFloating": False}
    )
    page.close()
    assert render_gate_model.render_version(browser, url).failures == []
    assert held == []
    assert any("1 comment" in found for found in reported), (
        "the line falls on nobody, so a gate that never looked would pass this too"
    )


def test_the_gate_passes_a_page_whose_collapsed_cards_lie_on_each_other(browser, serve):
    """Words drawn on other words is a question about the screen, and a collapse is the
    page being asked to take words off it. The cards behind a settled row wear
    hidden="until-found" so find-in-page still reaches them, which is content-visibility
    rather than display, and checkVisibility answers for neither: they read as drawn, and
    each reports the box it last laid out in, so all three land on one another. That is
    the collapse working, and COVERED_WORDS says why it is held out.

    On a fresh load whether they report at all is a coin, which is no basis for a test.
    Opening the row and closing it again settles it: the cards lay out for real, and the
    boxes they keep afterwards are that layout."""
    url = serve(SETTLED_PAGE)
    page = open_page(browser, url)
    row = page.locator("#transport .lf-settled")
    card = page.locator("#transport #opt-lax")

    row.click()
    expect(card).to_be_visible()
    row.click()
    expect(card).to_be_hidden()

    # The gate's own reading, taken here rather than left to render_version: that opens a
    # fresh page, which is the coin again, and this page is the one holding the layout the
    # cards kept. Then the same named reading with its collapsed-content hold disabled.
    held, reported = (
        render_checks_model.evaluate_probe(page, "coveredWords"),
        render_checks_model.evaluate_probe(page, "coveredWords", {"holdHidden": False}),
    )
    assert held == []
    assert any("opt-" in found for found in reported), (
        "the cards fell on nobody, so a gate that never looked would pass this too"
    )
    page.close()
    assert render_gate_model.render_version(browser, url).failures == []


def test_the_gate_measures_an_inline_widget_by_its_words(browser, serve):
    """A chip is set among the words around it, so its box is the words in it and there is
    no width it was ever going to reach. Held to the floor written for a widget that lays
    out a region, a chip saying `£9` reads as a collapse, and the gate refuses a page with
    nothing wrong with it — for a price, which is the shortest thing an author is likely to
    put in one. A suggestion swapping one short word is the same case in a second tag,
    there because the gate dispatches on the declaration: the day the wrapper took a box
    it stood in front of this floor, and only x-inline says whose floor is whose.

    The floor a chip does keep is the height, since a line of words is a line tall under
    any layout. Both halves are asserted, because a floor deleted outright passes the
    first on its own."""
    url = serve(SHORT_CHIP_PAGE)
    page = open_page(browser, url)
    widths = page.locator("lf-chip").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert widths and max(widths) < 40, (
        f"these chips are {widths}px, so they clear the floor and prove nothing"
    )
    sug_width = page.locator("#sug-flag").evaluate(
        "el => Math.round(el.getBoundingClientRect().width)"
    )
    assert sug_width < 40, (
        f"the suggestion is {sug_width}px, so it clears the floor and proves nothing"
    )

    # Asked without the declaration, the same floor flags it — so what passes the page
    # is the declaration, not a floor gone missing.
    undeclared = json.loads(json.dumps(page_registry(page)))
    del undeclared["lf-suggestion"]["x-inline"]
    assert [
        box
        for box in render_checks_model.evaluate_probe(page, "tinyBoxes", undeclared)
        if box["tag"] == "lf-suggestion"
    ], (
        "with x-inline stripped the gate stays quiet, so the floor is gone rather than declared"
    )

    # Flattened, the same chips are a collapse and the gate says so — the reading the
    # declaration narrows rather than switches off.
    page.add_style_tag(
        content="lf-chip { display: block; height: 2px; overflow: hidden; }"
    )
    flattened = render_checks_model.evaluate_probe(
        page, "tinyBoxes", page_registry(page)
    )
    page.close()
    assert [box for box in flattened if box["tag"] == "lf-chip"], (
        "a chip with no height left reports nothing, so the floor is gone rather than declared"
    )
    assert render_gate_model.render_version(browser, url).failures == []


def test_check_render_refuses_what_only_a_browser_can_see(serve, headless_shell):
    """`version check --render` end to end, as the agent runs it: the static lint
    passes both sources, and only one renders clean. The broken source is deliberately
    unstamped — refusing it before `version stamp` names it is the gate's whole job,
    so the preview server has to expose the exact candidate without activating it.

    Over the clean source once through each browser a host can supply: the installed
    Chrome the default channel finds, and the executable a browser variable names —
    leaf's own and one of the two that predate it, since a host that set CHROME_PATH
    for another tool has named this browser too. The default arm states every
    variable empty rather than inheriting whatever the developer or the job
    exported, since a set one would otherwise turn the channel this arm exists to
    cover into a second run of the other. A runner image really does export
    CHROME_BIN, so unnaming leaf's alone is not unnaming. Each arm's success line
    has to name the browser that drew the page: a clean gate telling a Chromium host
    that Chrome drew it is the same false claim on the way out that the failure
    messages stopped making."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*args, variable=None, executable=""):
        return subprocess.run(
            [
                *LEAF_COMMAND,
                "version",
                "check",
                str(d),
                "--render",
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
            env=unnamed_browser() | ({variable: executable} if variable else {}),
        )

    ok = gate()
    assert ok.returncode == 0, ok.stderr
    assert "renders clean in Chrome" in ok.stdout

    for variable in ("LEAF_BROWSER_EXECUTABLE", "CHROME_PATH"):
        named = gate(variable=variable, executable=headless_shell)
        assert named.returncode == 0, named.stderr
        assert f"renders clean in {headless_shell}" in named.stdout

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "index.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate()
    assert broken.returncode == 1
    assert "scrolls sideways" in broken.stderr


def test_a_named_browser_that_is_not_one_names_the_variable(serve, tmp_path):
    """A browser variable is the whole of what a host says about its browser, so a
    value naming no browser has to come back as that variable and that value rather
    than as Chrome, which the host never asked for. Both user-path launches answer for
    it, and they have to move together: `serving-pages.md` names export as the fallback
    for when no network route reaches the page, so a host whose browser cannot launch
    loses the page twice over.

    Whichever variable the host set is the one the message names. Reporting a
    CHROME_PATH browser as LEAF_BROWSER_EXECUTABLE's would be a false statement about
    the host's own configuration, and it points the reader at a variable they never
    set — so the second half checks the other two by their own names, through the
    check alone, both launches having already been shown to move together."""
    serve(LONG_PAGE)
    d = serve.page_dir
    missing = tmp_path / "not-a-browser"
    named = unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": str(missing)}

    checked = subprocess.run(
        [*LEAF_COMMAND, "version", "check", str(d), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=named,
    )
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert (
        "LEAF_BROWSER_EXECUTABLE" in checked.stderr and str(missing) in checked.stderr
    )
    assert "Chrome did not launch" not in checked.stderr

    exported = subprocess.run(
        [
            *LEAF_COMMAND,
            "version",
            "export",
            str(d),
            "--out",
            str(tmp_path / "standalone.html"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=named,
    )
    assert exported.returncode == 1, exported.stdout + exported.stderr
    assert (
        "LEAF_BROWSER_EXECUTABLE" in exported.stderr and str(missing) in exported.stderr
    )
    assert "export needs Chrome" not in exported.stderr

    for variable in ("CHROME_PATH", "CHROME_BIN"):
        answered = subprocess.run(
            [*LEAF_COMMAND, "version", "check", str(d), "--render"],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {variable: str(missing)},
        )
        assert answered.returncode == 1, answered.stdout + answered.stderr
        assert variable in answered.stderr and str(missing) in answered.stderr
        assert "LEAF_BROWSER_EXECUTABLE" not in answered.stderr


def test_a_driver_that_never_starts_is_reported_rather_than_raised(serve, tmp_path):
    """Under the browser both gates launch sits Playwright's driver, a Node process
    leaf never names. Where it ends at startup, no launch is reached, so the guard
    that answers for a browser cannot: `sync_playwright()`'s context entry dies on an
    AttributeError naming a Playwright private, and the connection's own reason
    arrives afterwards, out of order, as asyncio's unretrieved task. A page author
    reading that has been handed a leaf bug where the host has an old Node.

    Two hosts reach it — a glibc older than the bundled Node needs, and a
    PLAYWRIGHT_NODEJS_PATH naming a Node older than the driver bundle needs — and
    both end at the same observable point, which a stub that exits without answering
    stands in for. What each gate owes is its own one line: the connection's reason,
    the Node that ran, and the variable that chooses one, since neither real failure
    names that variable and it is the whole of what settles them. Both gates answer,
    for the reason the named-browser case gives: export is the fallback when no
    network route reaches the page, so a host losing one loses the page twice over.

    A third host names a Node it does not have, so the driver never runs at all and
    the spawn fails a step earlier than the silence above. It owes the same line,
    and it is where cleaning up after a failed start goes wrong: Playwright's stop
    asserts a transport handle that spawn never assigned, so a manager exited after
    a failed entry answers with a private of its own instead of the missing file.

    No traceback is half the subject. The four shapes asserted away are the ones the
    reader sees where a gate raises instead of answering: either private, the
    out-of-order asyncio block, and any traceback at all."""
    serve(LONG_PAGE)
    d = serve.page_dir
    silent = tmp_path / "not-a-node"
    silent.write_text("#!/bin/sh\nexit 1\n")
    silent.chmod(0o755)
    missing = tmp_path / "no-node-here"

    def answered(result, node, reason):
        assert result.returncode == 1, result.stdout + result.stderr
        assert browser_model.DRIVER_VARIABLE in result.stderr
        assert str(node) in result.stderr
        assert reason in result.stderr
        assert "Traceback" not in result.stderr
        assert "_playwright" not in result.stderr
        assert "_output" not in result.stderr
        assert "Task exception was never retrieved" not in result.stderr

    def ran(node, *command):
        return subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {browser_model.DRIVER_VARIABLE: str(node)},
        )

    ended = "Connection closed while reading from the driver"
    answered(ran(silent, "version", "check", str(d), "--render"), silent, ended)
    answered(
        ran(
            silent,
            "version",
            "export",
            str(d),
            "--out",
            str(tmp_path / "standalone.html"),
        ),
        silent,
        ended,
    )
    answered(
        ran(missing, "version", "check", str(d), "--render"),
        missing,
        "No such file or directory",
    )


def test_an_installed_payload_passes_its_real_browser_gate(tmp_path, headless_shell):
    """Exercise the copied artifact a host installs, never an import from this checkout.

    Its browser gate runs on both of the browsers a host can supply, since the install
    is where a host with a Chromium and no Chrome meets it."""
    root = Path(__file__).parent.parent
    installed = install_payload(tmp_path / "host" / "leaf")
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", "--package", "command-hub", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    installed_registry = json.loads((page_dir / "registry.json").read_text())
    assert "lf-command" in installed_registry
    assert installed_registry["$layer"]["packages"] == ["command-hub"]
    (page_dir / "index.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(EXAMPLE_MEDIA, page_dir / "media", dirs_exist_ok=True)
    stamp = subprocess.run(
        [
            launcher,
            "version",
            "stamp",
            page_dir,
            "--text",
            "installed-payload smoke",
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert stamp.returncode == 0, stamp.stderr

    for executable in ("", headless_shell):
        rendered = subprocess.run(
            [launcher, "version", "check", page_dir, "--render"],
            cwd=elsewhere,
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": executable},
        )
        assert rendered.returncode == 0, rendered.stderr
        assert "renders clean" in rendered.stdout


def test_render_reports_a_word_the_printed_page_loses(browser, serve):
    """A user prints the page, or saves it to PDF for someone who wasn't in the
    loop, and whatever the screen said had better still be there. Ways it isn't, all
    silent: a control that is a statement as well as a thing to press (the pick mark,
    which is the only place a group says which option it carries) and a rule that
    hides page content in print, inside a widget or in plain prose. The gate reads
    the page in both media and reports what the second one drops.

    A control declared an offer is exempt, since paper has nothing to press: the same
    page's pick mark reads "chosen" and goes unreported either way."""
    lost = render_gate_model.render_version(browser, serve(PRINT_LOSS_PAGE)).failures
    assert lost == [
        (
            '[print] <p id=lede> drops "Where the decision stands, for the recor", '
            "which it says on screen"
        ),
        (
            '[print] <strong> in <lf-option id=c-bearer> drops "Bearer header", '
            "which it says on screen"
        ),
        (
            '[print] <lf-option id=c-bearer> drops "Suits the mobile client;\\n  '
            'puts the id w", which it says on screen'
        ),
    ], lost


def test_a_shot_compares_its_frames_with_a_direct_divider(browser, serve):
    """The live pair is continuously comparable, with direct endpoint alternatives.

    Pointer drag and the component's complete keyboard pattern move one divider. The
    rail and the stable margin entry still jump to the named endpoints, while print
    keeps the two complete frames and their order."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    assert render_gate_model.render_version(browser, url).failures == []

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """new MutationObserver(() => {
          if (document.body?.hasAttribute('data-lf-presented') &&
              window.__lfPresentedAt === undefined)
            window.__lfPresentedAt = performance.now();
        }).observe(document, {attributes: true, subtree: true});"""
    )
    page.goto(url)
    page.wait_for_function(
        "document.body.hasAttribute('data-lf-presented') && "
        "document.querySelector('lf-shot wa-comparison')"
    )
    timing = page.evaluate(
        """() => ({
          presented: window.__lfPresentedAt,
          loaded: performance.getEntriesByType('resource')
            .find(entry => entry.name.endsWith('/vendor/webawesome.esm.js'))?.startTime,
        })"""
    )
    assert timing["loaded"] >= timing["presented"]
    rail = page.locator("lf-shot .lf-shotrail")
    expect(rail).to_have_count(1)
    expect(rail.locator(".lf-shotcap")).to_have_text(["before", "after"])
    before_bounds = rail.locator('[data-lf-state="before"]').bounding_box()
    after_bounds = rail.locator('[data-lf-state="after"]').bounding_box()
    assert before_bounds is not None and after_bounds is not None
    comparison = page.locator("lf-shot wa-comparison")
    expect(comparison).to_have_attribute("position", "50")
    glyph = comparison.locator('[slot="handle"].lf-shot-handle')
    expect(glyph).to_have_count(1)
    assert glyph.evaluate(
        "node => [getComputedStyle(node).borderStyle, "
        "getComputedStyle(node).borderRadius]"
    ) == ["solid", "50%"]
    handle = comparison.get_by_role("scrollbar")
    expect(handle).to_have_accessible_name("Before and after — the navigation rail")
    expect(handle).to_have_attribute("aria-valuetext", "Before 50%, after 50%")
    # Each half of the split shows the frame its rail caption names: the image the
    # user hits below a caption is that caption's own. Web Awesome's `after` slot is
    # the inline-start side, so wiring the frames to their same-named slots put the
    # after image under BEFORE.
    comparison.scroll_into_view_if_needed()
    under_captions = page.evaluate(
        """() => {
          const box = document.querySelector('lf-shot wa-comparison')
            .getBoundingClientRect();
          return [...document.querySelectorAll('lf-shot .lf-shotcap')].map(cap => {
            const x = cap.getBoundingClientRect().left + cap.offsetWidth / 2;
            const hit = document.elementFromPoint(x, box.top + box.height / 2);
            return [cap.dataset.lfState, hit?.closest('.lf-shotframe')?.dataset.lfState];
          });
        }"""
    )
    assert under_captions == [["before", "before"], ["after", "after"]]
    page.emulate_media(media="print")
    assert shown_frames(page) == ["before", "after"]
    printed_tops = [
        page.locator(f'lf-shot .lf-shotframe[data-lf-state="{state}"]').bounding_box()[
            "y"
        ]
        for state in ("before", "after")
    ]
    assert printed_tops[0] < printed_tops[1], "paper put the after frame on top"
    assert (
        rail.locator('[data-lf-state="before"]').evaluate(
            "cap => getComputedStyle(cap, '::after').content"
        )
        == '" · top"'
    )
    assert (
        rail.locator('[data-lf-state="after"]').evaluate(
            "cap => getComputedStyle(cap, '::after').content"
        )
        == '" · bottom"'
    )
    page.emulate_media(media="screen")
    expect(comparison).to_be_visible()
    page.mouse.move(0, 0)
    divider_face = comparison.evaluate(
        """async node => {
          const divider = node.shadowRoot.querySelector('[part~="divider"]');
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return {
            divider: getComputedStyle(divider).backgroundColor,
            handle: getComputedStyle(handle).backgroundColor,
            opacity: parseFloat(getComputedStyle(handle).opacity),
          };
        }"""
    )
    assert divider_face["divider"] != divider_face["handle"]
    assert 0.45 < divider_face["opacity"] < 0.6

    comparison.scroll_into_view_if_needed()
    bounds = comparison.bounding_box()
    assert bounds is not None
    image_point = (bounds["x"] + bounds["width"] / 4, bounds["y"] + 80)
    page.mouse.move(*image_point)
    active_midpoint = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert active_midpoint == 1
    page.mouse.down()
    page.mouse.up()
    expect(comparison).to_have_attribute("position", "0")
    page.mouse.move(0, 0)
    quiet_handle = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert quiet_handle < 0.25
    handle.focus()
    active_handle = comparison.evaluate(
        """async node => {
          const handle = node.shadowRoot.querySelector('[part~="handle"]');
          await Promise.all(handle.getAnimations().map(animation => animation.finished));
          return parseFloat(getComputedStyle(handle).opacity);
        }"""
    )
    assert active_handle == 1
    page.mouse.click(*image_point)
    expect(comparison).to_have_attribute("position", "100")
    comparison.evaluate("node => { node.position = 50; }")
    handle.click()
    expect(comparison).to_have_attribute("position", "50")

    before_caption = page.get_by_role(
        "button", name="before — the navigation rail", exact=True
    )
    after_caption = page.get_by_role(
        "button", name="after — the navigation rail", exact=True
    )
    expect(before_caption).to_have_attribute("aria-pressed", "false")
    expect(after_caption).to_have_attribute("aria-pressed", "false")
    before_caption.focus()
    assert "show before" in shortcut_bar_text(page)
    after_caption.focus()
    assert "show after" in shortcut_bar_text(page)
    after_caption.click()
    expect(comparison).to_have_attribute("position", "0")
    expect(before_caption).to_have_attribute("aria-pressed", "false")
    expect(after_caption).to_have_attribute("aria-pressed", "true")
    page.mouse.move(0, 0)
    assert after_caption.evaluate("node => getComputedStyle(node).backgroundColor") != (
        before_caption.evaluate("node => getComputedStyle(node).backgroundColor")
    )
    assert "show after" not in shortcut_bar_text(page)
    after_caption.click()
    expect(comparison).to_have_attribute("position", "0")
    before_caption.click()
    expect(comparison).to_have_attribute("position", "100")
    after_caption.focus()
    page.keyboard.press("Enter")
    expect(comparison).to_have_attribute("position", "0")
    before_caption.focus()
    page.keyboard.press("Space")
    expect(comparison).to_have_attribute("position", "100")
    for locator, bounds in (
        (rail.locator('[data-lf-state="before"]'), before_bounds),
        (rail.locator('[data-lf-state="after"]'), after_bounds),
    ):
        flipped_bounds = locator.bounding_box()
        assert flipped_bounds is not None
        assert {key: flipped_bounds[key] for key in ("x", "width", "height")} == {
            key: bounds[key] for key in ("x", "width", "height")
        }

    handle.focus()
    expect(handle).to_be_focused()
    assert "adjust the comparison" in shortcut_bar_text(page)
    page.keyboard.press("ArrowLeft")
    expect(comparison).to_have_attribute("position", "99")
    expect(handle).to_have_attribute("aria-valuetext", "Before 99%, after 1%")
    page.keyboard.press("Shift+ArrowLeft")
    expect(comparison).to_have_attribute("position", "89")
    page.keyboard.press("End")
    expect(comparison).to_have_attribute("position", "100")
    page.keyboard.press("Home")
    expect(comparison).to_have_attribute("position", "0")

    comparison.evaluate("node => { node.position = 50; }")
    expect(comparison).to_have_attribute("position", "50")
    bounds = comparison.bounding_box()
    handle_bounds = handle.bounding_box()
    assert bounds is not None and handle_bounds is not None
    at = (
        handle_bounds["x"] + handle_bounds["width"] / 2,
        handle_bounds["y"] + handle_bounds["height"] / 2,
    )
    page.mouse.move(*at)
    page.mouse.down()
    page.mouse.move(at[0] + bounds["width"] / 4, at[1], steps=4)
    page.mouse.up()
    dragged = float(comparison.get_attribute("position"))
    assert 70 <= dragged <= 80
    expect(handle).to_have_attribute(
        "aria-valuetext", f"Before {dragged:g}%, after {100 - dragged:g}%"
    )

    comparison.evaluate("node => { node.position = 100; }")
    expect(comparison).to_have_attribute("position", "100")
    button = page.get_by_role("button", name="Show after — the navigation rail")
    expect(page.locator(".lf-margin-cluster").filter(has=button)).to_be_visible()
    expect(button.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "compare-before"
    )
    button_bounds = button.bounding_box()
    assert button_bounds is not None
    button_at = (
        button_bounds["x"] + button_bounds["width"] / 2,
        button_bounds["y"] + button_bounds["height"] / 2,
    )
    page.mouse.click(*button_at)
    expect(comparison).to_have_attribute("position", "0")
    button = page.get_by_role("button", name="Show before — the navigation rail")
    expect(button).to_be_focused()
    assert "show before" in shortcut_bar_text(page)
    expect(button.locator(".lf-margin-entry-icon")).to_have_attribute(
        "data-lf-icon", "compare-after"
    )
    assert button.bounding_box() == button_bounds
    page.mouse.down()
    expect(button).to_be_focused()
    page.mouse.up()
    expect(comparison).to_have_attribute("position", "100")
    page.keyboard.press("Enter")
    expect(comparison).to_have_attribute("position", "0")
    page.keyboard.press("Space")
    expect(comparison).to_have_attribute("position", "100")

    handle.focus()
    ring = handle.evaluate(
        """node => { const cs = getComputedStyle(node); return {
          name: cs.getPropertyValue('--lf-here-ring').trim(),
          width: cs.outlineStyle === 'none' ? 0 : parseFloat(cs.outlineWidth),
        }}"""
    )
    assert ring["name"] == "shot" and ring["width"] > 0


def test_a_tall_shot_drags_where_it_was_grabbed_without_moving_the_page(browser, serve):
    """Dragging a tall comparison stays under the pointer on a desk and phone."""
    before = solid_png(390, 700, (232, 226, 213))
    after = solid_png(390, 844, (214, 226, 235))
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after},
    )
    page = open_page(browser, url)
    comparison = page.locator("lf-shot wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    expect(handle).to_have_accessible_name("Before and after — the navigation rail")

    for width in (1200, 390):
        resized(page, width, 900)
        comparison.evaluate("node => { node.position = 50; }")
        page.evaluate(
            """() => { const r = document.querySelector('lf-shot .lf-shotframe')
                                  .getBoundingClientRect();
                       document.scrollingElement.scrollBy(0, r.top - 140); }"""
        )
        box = comparison.bounding_box()
        handle_box = handle.bounding_box()
        image_heights = comparison.locator("img").evaluate_all(
            "nodes => nodes.map(node => node.getBoundingClientRect().height)"
        )
        assert box is not None and handle_box is not None
        assert box["height"] >= max(image_heights) - 1
        divider = (
            handle_box["x"] + handle_box["width"] / 2,
            box["y"] + 80,
        )
        scroll_before = page.evaluate("document.scrollingElement.scrollTop")
        page.mouse.move(*divider)
        page.mouse.down()
        page.mouse.move(divider[0] + 24, divider[1], steps=3)
        page.mouse.up()
        scroll_settled(page)
        assert float(comparison.get_attribute("position")) > 50
        assert (
            abs(page.evaluate("document.scrollingElement.scrollTop") - scroll_before)
            <= 1
        )


def test_a_shot_adopts_a_fallback_choice_when_the_divider_arrives(browser, serve):
    """A user's before → after → before choice survives the deferred import."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """new MutationObserver(() => {
          if (!document.body?.hasAttribute('data-lf-presented') || window.__lfFlipped)
            return;
          const box = document.querySelector('lf-shot input.lf-shotflip');
          if (!box) return;
          window.__lfFlipped = true;
          window.__lfHadComparison = !!document.querySelector('lf-shot wa-comparison');
          box.click();
          box.click();
          window.__lfFallbackShown = [...document.querySelectorAll('.lf-shotframe')]
            .filter(frame => getComputedStyle(frame).visibility === 'visible')
            .map(frame => frame.dataset.lfState);
        }).observe(document, {attributes: true, subtree: true});"""
    )
    page.goto(url)
    comparison = page.locator("lf-shot wa-comparison")
    expect(comparison).to_have_attribute("position", "100")
    assert page.evaluate(
        "() => [window.__lfHadComparison, window.__lfFallbackShown]"
    ) == [False, ["before"]]


def test_a_shot_still_flips_with_every_script_removed(
    browser, serve, tmp_path, headless_shell
):
    """Which is the whole reason the target is a native checkbox. A copy is the
    rendered DOM with the scripts dropped and every press a handler answered taken out
    with them — the upgrade has already run, so the frames are there, and this switch
    survives that pass because the browser is what works it. A slider would have
    frozen at whatever the user left it on; `:has(:checked)` is CSS, and the browser
    owns a checkbox's state, so its transparent box over the image goes on being the
    target in a file with nothing running.

    Through `version export` rather than a copy the test makes itself, which is what
    puts the widget's bargain in front of the code that could break it: a hand-rolled
    one dropped the script tags and nothing else, so it went on passing however the
    real export treated a control.

    What it pins is no longer that a state serializes. Setting `checked` as a property
    left no attribute behind, so the copy opened with neither frame chosen and both of
    them stacked in the one cell — a fault the frames' own default has since made
    unrepresentable, the after frame being hidden until something checks the box rather
    than until something checks the other box. So the state needs nothing serialized at
    all, and what is left to lose is the gesture: the direct native checkbox and its CSS
    target must survive. A copy that dropped either would keep every frame and every word
    and answer no click on the image."""
    serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )

    def export(out, executable=""):
        return subprocess.run(
            [
                *LEAF_COMMAND,
                "version",
                "export",
                str(serve.page_dir),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"LEAF_BROWSER_EXECUTABLE": executable},
        )

    standalone = tmp_path / "standalone.html"
    exported = export(standalone)
    assert exported.returncode == 0, exported.stdout + exported.stderr

    # The same copy through the browser a host names instead. A file is all this arm
    # needs from it: what a copy has to keep is the subject below, on the Chrome arm.
    named = tmp_path / "named.html"
    from_named = export(named, executable=headless_shell)
    assert from_named.returncode == 0, from_named.stdout + from_named.stderr
    assert named.stat().st_size > 0
    loose = browser.new_page(viewport={"width": 1200, "height": 900})
    loose.goto(standalone.as_uri(), wait_until="load")
    assert loose.evaluate("document.querySelectorAll('script').length") == 0
    assert loose.locator("wa-comparison, [slot=handle]").count() == 0
    assert loose.locator("lf-shot > .lf-shotframe").count() == 2
    expect(loose.locator("lf-shot [aria-keyshortcuts]")).to_have_attribute(
        "aria-keyshortcuts", "Space"
    )
    assert shown_frames(loose) == ["before"]
    loose.mouse.click(*flip_point(loose))
    assert shown_frames(loose) == ["after"]
    before_caption = loose.locator('lf-shot .lf-shotcap[data-lf-state="before"]')
    after_caption = loose.locator('lf-shot .lf-shotcap[data-lf-state="after"]')
    before_caption.hover()
    assert before_caption.evaluate(
        "node => getComputedStyle(node).backgroundColor"
    ) != (after_caption.evaluate("node => getComputedStyle(node).backgroundColor"))
    loose.keyboard.press("Space")
    assert shown_frames(loose) == ["before"]
    loose.emulate_media(media="print")
    printed_tops = loose.locator("lf-shot .lf-shotframe").evaluate_all(
        "nodes => nodes.map(node => node.getBoundingClientRect().top)"
    )
    assert printed_tops[0] != printed_tops[1]


def test_a_shot_refuses_a_pair_shot_at_two_widths(browser, serve):
    """Both frames render at the frame's width, so a pair captured at two viewports is
    scaled by two different factors and every line in it lands somewhere new — the flip
    then reports that the whole page changed, convincingly and with nothing on screen
    to say otherwise. The one failure worth an error box rather than a caveat."""
    narrow = solid_png(400, 300, (235, 215, 205))
    page_html = SHOT_PAGE.replace(
        SHOT_SRC["after"], f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    )
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    url = serve(
        page_html,
        media={SHOT_SRC["before"]: SHOTS["before"], narrow_src: narrow},
    )

    assert [
        f
        for f in render_gate_model.render_version(browser, url).failures
        if "600px" in f and "400px" in f
    ], "the gate has to hear about a mismatch, since nobody else will"


def test_render_reports_words_a_widget_puts_out_of_reach(browser, serve):
    """The user's half of the gate. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported here.

    The second one no marker can fix, which is why it reads differently: a word inside a
    form control is unselectable in every engine, so a widget that reaches for <button>
    has put its label somewhere the user cannot go. `selectableOffer` is the explicit
    exception for such page words, and this says when a widget needed it.

    Both are about a word the user was shown, so the check asks that first. The
    runtime's external-link note is the case that made it say so: an aria-describedby
    target the browser reads out and the page never paints, put inside whatever root
    its link stands in — a shadow tree included, where .lf-quiet's clip does not
    reach. [hidden] is the silence available in every root, and the same note shown is
    still reported."""

    def stage_reach_cases(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const control = document.getElementById('c-bearer');
              const link = document.createElement('a');
              link.id = 'native-link';
              link.className = 'lf-ui';
              link.href = '#h';
              link.textContent = 'Read context';
              const hidden = document.createElement('span');
              hidden.id = 'hidden-note';
              hidden.className = 'lf-ui';
              hidden.hidden = true;
              hidden.textContent = 'opens in a new tab';
              control.prepend(link, hidden);

              const option = document.getElementById('c-lax');
              const shown = document.createElement('span');
              shown.id = 'shown-note';
              shown.className = 'lf-ui';
              shown.textContent = 'opens in a new tab';
              const row = document.createElement('div');
              row.id = 'unreachable-row';
              row.className = 'lf-ui';
              row.innerHTML = '<strong>Session cookies</strong>';
              const button = document.createElement('button');
              button.id = 'unreachable-button';
              button.setAttribute('data-lf-said', '');
              button.textContent = 'Lax, host-only';
              option.prepend(shown, row, button);
            }, {once: true});"""
        )

    primed_browser = primed(browser, stage_reach_cases)
    page = open_page(primed_browser, serve(CARRIED_PAGE))
    assert (
        page.locator(
            "#native-link, #hidden-note, #shown-note, #unreachable-row, "
            "#unreachable-button"
        ).count()
        == 5
    )
    assert page.locator("#hidden-note").is_hidden()
    page.close()

    found = render_gate_model.render_version(
        primed_browser, serve(CARRIED_PAGE)
    ).failures
    assert len(found) == 6, found
    assert sorted({f.split("] ", 1)[1] for f in found}) == [
        (
            '<lf-option id=c-lax> puts "Session cookies" under .lf-ui, where no comment '
            "can reach it"
        ),
        (
            '<lf-option id=c-lax> puts "opens in a new tab" under .lf-ui, where no '
            "comment can reach it"
        ),
        (
            '<lf-option id=c-lax> says "Lax, host-only" inside a form control, where no '
            "selection can reach it"
        ),
    ], found


def test_render_reports_a_painted_fact_whose_word_was_drawn_nowhere(browser, serve):
    """The x-paints half of the same gate, and the line it draws between two silences.

    A widget may paint a fact — `kind="failure"` is a visual state and no text node —
    and it owes a user who is listening the same fact in words. The runtime
    writes that word, so what is left to check is whether anything drew it. Asking
    is asking for a box, and only an element that is being laid out has one to give:
    a disclosure nobody opened, a tab nobody switched to and a shut thread panel
    all lay out nothing, and their emptiness is the ancestor's answer rather than
    the widget's.

    So the two silences part here, and this holds one of them: a word drawn nowhere
    on a page that is on screen is reported, and the same widget behind a fold is
    not, there being nothing to measure and the fold being the user's to open.
    That exemption is what lets a widget riding a message out, in
    `test_render_leaves_a_widget_riding_a_reply_out_of_that_reading`.

    The other silence — a word the runtime never wrote, which is a fault wherever
    the element stands — no fixture can stage: `quietFacts` returns the attribute's
    own value or its name, so a declared paint always gets its word, and the branch
    is reachable only by a regression in `renderQuiet` itself. What holds it is the
    corpus with that regression put back: silence `renderQuiet` and every painted
    option in the examples is reported, an option in a tab nobody opened among them.
    Skipping the unrendered element before asking whether
    a word exists is what drops that one, so the order of the two questions here is
    the contract, and this test does not pin it."""
    found = [
        f.split("] ", 1)[1]
        for f in render_gate_model.render_version(
            browser, serve(PAINTED_IN_SILENCE_PAGE)
        ).failures
    ]
    assert sorted(set(found)) == [
        (
            '<lf-chronology-entry id=p-seen> paints kind="failure" and says nothing a user '
            "listening can hear"
        )
    ], found


def test_render_reads_a_reply_widgets_own_chrome_and_not_the_panel_around_it(
    browser, serve, tmp_path, monkeypatch
):
    """The same reading, asked where the nesting turns over.

    A widget's chrome is a `.lf-ui` the widget put inside itself. A widget in a
    message is the other way up: the runtime's own layer is above it and the
    widget has none of its own, so every word it holds sits under a `.lf-ui`
    with nothing wrong. Asking whether the *words* stand in a widget cannot tell
    those apart and accuses the second. Asking whose the `.lf-ui` is can.

    Both halves, because either alone is half a claim. One reply carries three
    widgets: a question, an exhibit beside it, and a badge whose module injects
    unmarked words under the chrome face. The panel around all three says
    nothing; the badge's own chrome is read exactly as it would be on a page.

    Nothing here had ever been rendered. No example shipped a widget in its log
    until one did, and every fixture that put one in a reply asked about the
    panel rather than about the gate — while the gate walks text nodes rather
    than boxes, so it had been reading the panel all along with the panel shut.
    It would have refused the first page that carried a question in a reply,
    which is a shape the vocabulary describes and `leaf reply --markup` posts."""
    monkeypatch.chdir(tmp_path)
    package = author_test_widget(tmp_path, "lf-badge", upgrade=True)
    module = package / "widgets" / "lf-badge.js"
    module.write_text(
        module.read_text().replace(
            "      once(this);",
            "      once(this);\n" + BADGE_CHROME,
        )
    )

    url = serve(REPLY_HOST_PAGE, packages=(*EXAMPLE_PACKAGES, "./.leaf"))
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    events_model.append_event(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    found = sorted(
        {
            f.split("] ", 1)[1]
            for f in render_gate_model.render_version(browser, url).failures
        }
    )
    assert found == [
        (
            '<lf-badge id=rp-badge> puts "Sent by the reviewer" under .lf-ui, where no '
            "comment can reach it"
        )
    ], found


def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path, headless_shell):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it names the payload project from its own location rather
    than letting uv find whatever project the cwd sits in. Running it from an
    unrelated directory exercises that.

    The version under it carries a diagram body the renderer refuses — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and the browser half is what sees
    the error box, which is why the gate is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir
    assert (
        CliRunner().invoke(cli_model.cli, ["version", "check", str(d)]).exit_code == 0
    )

    shim = Path(__file__).parent.parent / "bin" / "leaf"
    for executable in ("", headless_shell):
        run = subprocess.run(
            [str(shim), "version", "check", str(d), "--render"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"LEAF_BROWSER_EXECUTABLE": executable},
        )
        assert run.returncode == 1, run.stdout + run.stderr
        # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
        # The report names the widget and gives the renderer's reason, not the source.
        assert "<lf-diagram id='d-broken'> failed soft:" in run.stderr
        assert "is unsupported" in run.stderr
        assert "Ada,Review,3" not in run.stderr


FILM_DECLARATION = {
    tag: {
        "description": f"A <{tag}> page widget.",
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-upgrade": True,
    }
    for tag in ("lf-film", "lf-loader")
}
FILM_PAGE = LONG_PAGE.replace(
    "</main>", '<lf-film id="film"></lf-film><lf-loader id="loader"></lf-loader></main>'
)


def test_plain_check_runs_the_code_a_page_authored(serve, tmp_path, headless_shell):
    """A quick page takes plain `version check` and nothing else, so that is the check
    that has to run the page's own code: a widget that throws on its first paint, or
    a load that rejects, is otherwise heard of only once the user's browser reports
    it to the watcher. The check fails on those reports, worded as the watcher gets
    them — the painter's throw names the module under `page/` that threw, not the
    widget that called it — and passes the same page once its modules run clean.

    A page without code of its own is still checked without a browser: the missing
    executable named below is never launched."""
    serve(
        LONG_PAGE,
        page_files={
            "registry.json": json.dumps(FILM_DECLARATION),
            "film.js": "export const paint = (el, step) =>\n"
            "  (el.textContent = (step.cmp ?? []).map(String).join());\n",
            "widgets/lf-film.js": 'import { paint } from "../film.js";\n'
            "customElements.define('lf-film', class extends HTMLElement {\n"
            "  connectedCallback() { paint(this, { cmp: 3 }); }\n"
            "});\n",
            "widgets/lf-loader.js": "customElements.define('lf-loader', class extends HTMLElement {\n"
            "  connectedCallback() { this.load(); }\n"
            "  async load() { await null; throw new Error('the trace never loaded'); }\n"
            "});\n",
        },
    )
    d = serve.page_dir

    def check(**env):
        return subprocess.run(
            [*LEAF_COMMAND, "version", "check", str(d)],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | env,
        )

    no_browser = check(LEAF_BROWSER_EXECUTABLE=str(tmp_path / "not-a-browser"))
    assert no_browser.returncode == 0, no_browser.stdout + no_browser.stderr
    assert "page code" not in no_browser.stdout + no_browser.stderr

    (d / "index.html").write_text(FILM_PAGE)
    broken = check(LEAF_BROWSER_EXECUTABLE=headless_shell)
    assert broken.returncode == 1, broken.stdout + broken.stderr
    assert "✗ page code: 2 error(s)" in broken.stderr
    assert "map is not a function" in broken.stderr
    assert "/page/film.js:2)" in broken.stderr
    assert "Error: the trace never loaded" in broken.stderr
    assert "/page/widgets/lf-loader.js:3" in broken.stderr

    (d / "page" / "film.js").write_text(
        "export const paint = (el, step) =>\n"
        "  (el.textContent = [step.cmp].flat().map(String).join());\n"
    )
    (d / "page" / "widgets" / "lf-loader.js").write_text(
        "customElements.define('lf-loader', class extends HTMLElement {\n"
        "  connectedCallback() { this.textContent = 'loaded'; }\n"
        "});\n"
    )
    clean = check(LEAF_BROWSER_EXECUTABLE=headless_shell)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert f"✓ page code: runs through upgrade and first paint in {headless_shell}" in (
        clean.stdout
    )
