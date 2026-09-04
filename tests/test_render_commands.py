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
from render_support import (
    BADGE_CHROME,
    CARRIED_PAGE,
    EXAMPLE_MEDIA,
    INLINE_PAGE,
    LONG_PAGE,
    PAINTED_IN_SILENCE_PAGE,
    PRINT_LOSS_PAGE,
    REPLY_HOST_PAGE,
    SCROLL_SETTLE_MS,
    SCROLL_STILL,
    SETTLED_PAGE,
    SHORT_CHIP_PAGE,
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    SPECIMEN_MARKUP,
    SPECIMEN_TEXT,
    UNPARSABLE_DIAGRAM,
    author_test_widget,
    flip_point,
    key_line,
    open_page,
    page_registry,
    primed,
    resized,
    shown_frames,
    solid_png,
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
    page, errors = open_page(browser, url)
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
    assert errors == []
    page.close()
    assert render_gate_model.render_version(browser, url) == []
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
    page, errors = open_page(browser, url)
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
    assert errors == []
    assert held == []
    assert any("opt-" in found for found in reported), (
        "the cards fell on nobody, so a gate that never looked would pass this too"
    )
    page.close()
    assert render_gate_model.render_version(browser, url) == []


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
    page, errors = open_page(browser, url)
    widths = page.locator("lf-chip").evaluate_all(
        "els => els.map(el => Math.round(el.getBoundingClientRect().width))"
    )
    assert errors == []
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
    assert render_gate_model.render_version(browser, url) == []


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


def test_a_host_that_names_nothing_is_asked_for_its_path_only_after_chrome(
    monkeypatch, tmp_path
):
    """With no variable set, PATH is the host's own statement of where its programs
    are, and a hardcoded candidate list is not: a list needs an entry per
    distribution and can never name a `/nix/store/<hash>-chromium-*/bin/chromium`.

    It is asked second, after the Chrome channel rather than before it, and that
    order is the whole of what keeps this from moving a host that works today: a box
    with both a Google Chrome and a distro Chromium goes on getting the Chrome the
    channel finds. So the launch is driven twice over one PATH holding one browser —
    once where the channel answers, once where it raises what Playwright raises on a
    host with no Chrome installed — and the assertion is the calls that were made,
    since a test reading only the browser back cannot see which of the two produced
    it."""
    from playwright.sync_api import Error as PlaywrightError

    chromium = tmp_path / "bin" / "chromium"
    chromium.parent.mkdir()
    chromium.write_text("#!/bin/sh\nexec true\n")
    chromium.chmod(0o755)
    for variable in browser_model.VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("PATH", str(chromium.parent))

    calls = []

    class Chromium:
        def __init__(self, channel_answers):
            self.channel_answers = channel_answers

        def launch(self, **kwargs):
            calls.append(kwargs)
            if "channel" in kwargs and not self.channel_answers:
                raise PlaywrightError(
                    "BrowserType.launch: Chromium distribution 'chrome' is not found "
                    "at /opt/google/chrome/chrome"
                )
            return "a browser"

    class Playwright:
        def __init__(self, channel_answers):
            self.chromium = Chromium(channel_answers)

    launched, name = browser_model.launch_browser(Playwright(True))
    assert (launched, name) == ("a browser", "Chrome")
    assert calls == [{"channel": "chrome"}], "the channel keeps the hosts it has"

    calls.clear()
    launched, name = browser_model.launch_browser(Playwright(False))
    assert (launched, name) == ("a browser", str(chromium))
    assert calls == [{"channel": "chrome"}, {"executable_path": str(chromium)}]

    # And the same reading is what the failed-launch line says, so a host with
    # neither is told what was looked for rather than named a variable twice.
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert browser_model.discovered_executable() is None
    hint = browser_model.browser_hint()
    assert "chromium" in hint and "LEAF_BROWSER_EXECUTABLE" in hint


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
    assert render_gate_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "a page whose print rendering keeps its words has nothing to report"
    )

    lost = render_gate_model.render_version(browser, serve(PRINT_LOSS_PAGE))
    assert [f for f in lost if f.startswith("[print]")] == [
        (
            '[print] <p id=lede> drops "Where the decision stands, for the recor", '
            "which it says on screen"
        ),
        '[print] <lf-option id=c-bearer> drops "Bearer header", which it says on screen',
        (
            '[print] <lf-option id=c-bearer> drops "Suits the mobile client;\\n  '
            'puts the id w", which it says on screen'
        ),
    ], lost


def test_a_shot_shows_one_frame_and_flips_between_them(browser, serve):
    """Image clicks and the target's Button flip the same fixed frame.

    Both state labels keep their corresponding sides while the active rule moves.
    Repeated presses keep their target and focus. The Button names the next frame
    after either route and answers both native activation keys. Arriving by Tab rings
    the whole card, rail included. The render gate also checks selectable captions and
    the two-frame print view."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )
    assert render_gate_model.render_version(browser, url) == []

    page, errors = open_page(browser, url)
    rail = page.locator("lf-shot .lf-shotrail")
    expect(rail).to_have_count(1)
    expect(rail.locator(".lf-shotcap")).to_have_text(["before", "after"])
    before_bounds = rail.locator('[data-lf-state="before"]').bounding_box()
    after_bounds = rail.locator('[data-lf-state="after"]').bounding_box()
    assert before_bounds is not None and after_bounds is not None
    before_face = rail.evaluate(
        """rail => [...rail.children].map(cap => ({
          state: cap.dataset.lfState,
          ink: getComputedStyle(cap).color,
          rule: getComputedStyle(cap).boxShadow,
        }))"""
    )
    assert before_face[0]["ink"] != before_face[1]["ink"]
    assert before_face[0]["rule"] != "none"
    assert before_face[1]["rule"] == "none"
    page.emulate_media(media="print")
    assert shown_frames(page) == ["before", "after"]
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
    assert shown_frames(page) == ["before"]
    at = flip_point(page)
    page.mouse.click(*at)
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    after_face = rail.evaluate(
        """rail => [...rail.children].map(cap => ({
          state: cap.dataset.lfState,
          ink: getComputedStyle(cap).color,
          rule: getComputedStyle(cap).boxShadow,
        }))"""
    )
    assert after_face[0]["ink"] == before_face[1]["ink"]
    assert after_face[1]["ink"] == before_face[0]["ink"]
    assert after_face[0]["rule"] == "none"
    assert after_face[1]["rule"] != "none"
    for locator, bounds in (
        (rail.locator('[data-lf-state="before"]'), before_bounds),
        (rail.locator('[data-lf-state="after"]'), after_bounds),
    ):
        flipped_bounds = locator.bounding_box()
        assert flipped_bounds is not None
        assert {key: flipped_bounds[key] for key in ("x", "width", "height")} == {
            key: bounds[key] for key in ("x", "width", "height")
        }
    box = page.locator("lf-shot input[type=checkbox]")
    expect(box).to_be_focused()
    assert "show before" in key_line(page)
    # The native checkbox is the overlay itself. Hold it across two frames: focus and the
    # screenshot key line must remain stable for the whole human press.
    page.mouse.down()
    expect(box).to_be_focused()
    assert "show before" in key_line(page)
    page.mouse.up()
    expect(page.locator('.lf-shotframe[data-lf-state="before"]')).to_be_visible()
    assert shown_frames(page) == ["before"]
    button = page.get_by_role("button", name="Show after — the navigation rail")
    expect(page.locator(".lf-margin-item").filter(has=button)).to_be_visible()
    expect(button.locator(".lf-margin-action-icon")).to_have_attribute(
        "data-lf-icon", "compare-before"
    )
    button_bounds = button.bounding_box()
    assert button_bounds is not None
    button_at = (
        button_bounds["x"] + button_bounds["width"] / 2,
        button_bounds["y"] + button_bounds["height"] / 2,
    )
    page.mouse.click(*button_at)
    expect(page.locator('.lf-shotframe[data-lf-state="after"]')).to_be_visible()
    assert shown_frames(page) == ["after"]
    button = page.get_by_role("button", name="Show before — the navigation rail")
    expect(button).to_be_focused()
    assert "show before" in key_line(page)
    expect(button.locator(".lf-margin-action-icon")).to_have_attribute(
        "data-lf-icon", "compare-after"
    )
    assert button.bounding_box() == button_bounds
    page.mouse.down()
    expect(button).to_be_focused()
    page.mouse.up()
    assert shown_frames(page) == ["before"]
    page.keyboard.press("Enter")
    assert shown_frames(page) == ["after"]
    page.keyboard.press("Space")
    assert shown_frames(page) == ["before"]

    # Image activation updates the Button too; Space still works at the image.
    page.mouse.click(*at)
    expect(
        page.get_by_role("button", name="Show before — the navigation rail")
    ).to_be_visible()
    box.focus()
    page.keyboard.press(" ")
    expect(page.locator('.lf-shotframe[data-lf-state="before"]')).to_be_visible()
    expect(
        page.get_by_role("button", name="Show after — the navigation rail")
    ).to_be_visible()

    # The rail and the frame are one card, so the ring a reader arriving by Tab leaves
    # goes round the card. Drawn on the frame alone it ran three pixels up inside the
    # rail, which is a rule across the card rather than a ring round the thing in hand,
    # and the rail's own surface stands where that run is. Asked here as well as in the
    # corpus ring walk because that walk is nightly and reports its first fault only.
    for _ in range(40):
        page.keyboard.press("Tab")
        if box.evaluate("flip => flip === document.activeElement"):
            break
    expect(box).to_be_focused()
    ring = page.locator("lf-shot").evaluate(
        """shot => {
          const cs = getComputedStyle(shot);
          const grow = parseFloat(cs.outlineWidth) + parseFloat(cs.outlineOffset);
          const b = shot.getBoundingClientRect();
          const card = [...shot.querySelectorAll('.lf-shotrail, .lf-shotframe')]
            .map((part) => part.getBoundingClientRect());
          return {
            name: cs.getPropertyValue('--lf-here-ring').trim(),
            width: cs.outlineStyle === 'none' ? 0 : parseFloat(cs.outlineWidth),
            top: b.top - grow,
            bottom: b.bottom + grow,
            card_top: Math.min(...card.map((part) => part.top)),
            card_bottom: Math.max(...card.map((part) => part.bottom)),
            corners: [cs.borderTopLeftRadius, cs.borderBottomRightRadius],
            card_corners: [
              getComputedStyle(shot.querySelector('.lf-shotrail')).borderTopLeftRadius,
              getComputedStyle(shot.querySelector('.lf-shotframe'))
                .borderBottomRightRadius,
            ],
          };
        }"""
    )
    assert ring["name"] == "shot" and ring["width"] > 0
    assert ring["top"] < ring["card_top"] and ring["bottom"] > ring["card_bottom"]
    # An outline follows its own box's corners, and lf-shot draws no border of its own
    # to have rounded them, so the ring's corners are asked against the rail's top and
    # the frame's foot — the card's own outer corners.
    assert ring["corners"] == ring["card_corners"] != ["0px", "0px"]
    assert errors == []
    page.close()


def test_a_tall_shot_flips_where_it_was_clicked_without_moving_the_page(browser, serve):
    """Clicking a tall comparison must not focus a remote control and scroll away
    from the image. The same causal gesture is checked on a desk and phone."""
    before = solid_png(390, 844, (232, 226, 213))
    after = solid_png(390, 844, (214, 226, 235))
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC["before"]: before, SHOT_SRC["after"]: after},
    )
    page, errors = open_page(browser, url)
    box = page.locator("lf-shot > input.lf-shotflip")
    expect(box).to_have_accessible_name(
        "Compare before and after — the navigation rail"
    )
    frame = page.locator('lf-shot .lf-shotframe[data-lf-state="before"]')

    for width in (1200, 390):
        resized(page, width, 900)
        page.evaluate(
            """() => { const r = document.querySelector('lf-shot .lf-shotframe')
                                  .getBoundingClientRect();
                       document.scrollingElement.scrollBy(0, r.top - 140); }"""
        )
        image_point = frame.evaluate(
            "el => { const r = el.getBoundingClientRect();"
            "        return [r.left + r.width / 2, r.top + 80]; }"
        )
        assert page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y) === "
            "document.querySelector('lf-shot > input.lf-shotflip')",
            image_point,
        )
        was_checked = box.is_checked()
        scroll_before = page.evaluate("document.scrollingElement.scrollTop")
        page.mouse.click(*image_point)
        page.wait_for_function(SCROLL_STILL, arg=SCROLL_SETTLE_MS)
        assert box.is_checked() is not was_checked
        assert (
            abs(page.evaluate("document.scrollingElement.scrollTop") - scroll_before)
            <= 1
        )

    assert errors == []
    page.close()


def test_a_shot_still_flips_with_every_script_removed(
    browser, serve, tmp_path, headless_shell
):
    """Which is the whole reason the target is a native checkbox. A copy is the
    rendered DOM with the scripts dropped and every press a handler answered taken out
    with them — the upgrade has already run, so the frames are there, and this switch
    survives that pass because the browser is what works it. A slider would have
    frozen at whatever the reader left it on; `:has(:checked)` is CSS, and the browser
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
    assert shown_frames(loose) == ["before"]
    loose.mouse.click(*flip_point(loose))
    assert shown_frames(loose) == ["after"]
    loose.keyboard.press("Space")
    assert shown_frames(loose) == ["before"]
    loose.close()


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
        for f in render_gate_model.render_version(browser, url)
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

    Both are about a word the reader was shown, so the check asks that first. The
    runtime's external-link note is the case that made it say so: an aria-describedby
    target the browser reads out and the page never paints, put inside whatever root
    its link stands in — a shadow tree included, where .lf-quiet's clip does not
    reach. [hidden] is the silence available in every root, and the same note shown is
    still reported."""
    assert render_gate_model.render_version(browser, serve(CARRIED_PAGE)) == [], (
        "the same page without the two mistakes has nothing to report"
    )

    def put_native_link(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const link = document.createElement('a');
              link.className = 'lf-ui';
              link.href = '#h';
              link.textContent = 'Read context';
              document.getElementById('c-lax').prepend(link);
            }, {once: true});"""
        )

    assert (
        render_gate_model.render_version(
            primed(browser, put_native_link), serve(CARRIED_PAGE)
        )
        == []
    ), "a native link's words label its browser-owned control rather than the page"

    def put_note(hidden):
        def go(page):
            page.add_init_script(
                """addEventListener('DOMContentLoaded', () => {
                  const note = document.createElement('span');
                  note.className = 'lf-ui';
                  note.hidden = HIDDEN;
                  note.textContent = 'opens in a new tab';
                  document.getElementById('c-lax').prepend(note);
                }, {once: true});""".replace("HIDDEN", "true" if hidden else "false")
            )

        return go

    assert (
        render_gate_model.render_version(
            primed(browser, put_note(True)), serve(CARRIED_PAGE)
        )
        == []
    ), "a word the page never shows is not a word the reader was shown and denied"
    assert sorted(
        {
            f.split("] ", 1)[1]
            for f in render_gate_model.render_version(
                primed(browser, put_note(False)), serve(CARRIED_PAGE)
            )
        }
    ) == [
        (
            '<lf-option id=c-lax> puts "opens in a new tab" under .lf-ui, where no '
            "comment can reach it"
        )
    ], "the same note shown is the failure this check exists for"

    def put_words_out_of_reach(page):
        page.add_init_script(
            """addEventListener('DOMContentLoaded', () => {
              const option = document.getElementById('c-lax');
              const row = document.createElement('div');
              row.className = 'lf-ui';
              row.innerHTML = '<strong>Session cookies</strong>';
              const button = document.createElement('button');
              button.setAttribute('data-lf-said', '');
              button.textContent = 'Lax, host-only';
              option.prepend(row, button);
            }, {once: true});"""
        )

    found = render_gate_model.render_version(
        primed(browser, put_words_out_of_reach), serve(CARRIED_PAGE)
    )
    assert sorted({f.split("] ", 1)[1] for f in found}) == [
        (
            '<lf-option id=c-lax> puts "Session cookies" under .lf-ui, where no comment '
            "can reach it"
        ),
        (
            '<lf-option id=c-lax> says "Lax, host-only" inside a form control, where no '
            "selection can reach it"
        ),
    ], found


def test_render_reports_a_painted_fact_whose_word_was_drawn_nowhere(browser, serve):
    """The x-paints half of the same gate, and the line it draws between two silences.

    A widget may paint a fact — `kind="failure"` is a visual state and no text node —
    and it owes a reader who is listening the same fact in words. The runtime
    writes that word, so what is left to check is whether anything drew it. Asking
    is asking for a box, and only an element that is being laid out has one to give:
    a disclosure nobody opened, a tab nobody switched to and a shut thread panel
    all lay out nothing, and their emptiness is the ancestor's answer rather than
    the widget's.

    So the two silences part here, and this holds one of them: a word drawn nowhere
    on a page that is on screen is reported, and the same widget behind a fold is
    not, there being nothing to measure and the fold being the reader's to open.
    That exemption is what lets a widget riding a message out, in
    `test_render_leaves_a_widget_riding_a_reply_out_of_that_reading`.

    The other silence — a word the runtime never wrote, which is a fault wherever
    the element stands — no fixture can stage: `quietFacts` returns the attribute's
    own value or its name, so a declared paint always gets its word, and the branch
    is reachable only by a regression in `renderQuiet` itself. What holds it is the
    corpus with that regression put back: silence `renderQuiet` and every painted
    option in the examples is reported, a `live-progress` option in a tab
    nobody opened among them. Skipping the unrendered element before asking whether
    a word exists is what drops that one, so the order of the two questions here is
    the contract, and this test does not pin it."""
    found = [
        f.split("] ", 1)[1]
        for f in render_gate_model.render_version(
            browser, serve(PAINTED_IN_SILENCE_PAGE)
        )
    ]
    assert sorted(set(found)) == [
        (
            '<lf-event id=p-seen> paints kind="failure" and says nothing a reader '
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
            "      if (!once(this)) return;",
            "      if (!once(this)) return;\n" + BADGE_CHROME,
        )
    )

    url = serve(REPLY_HOST_PAGE)
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
            "author": "claude",
            "parent": "c-decision",
            "revision": 1,
            "text": SPECIMEN_TEXT,
            "markup": SPECIMEN_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    found = sorted(
        {f.split("] ", 1)[1] for f in render_gate_model.render_version(browser, url)}
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

    The version under it carries a diagram body that doesn't parse — a shape the
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
        assert "failed soft" in run.stderr and "Parse error" in run.stderr
