"""Render, shot, and browser-gate command tests."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import LEAF_COMMAND
from interact_support import (
    append_carried_log_record,
    append_command,
    install_payload,
    state_json,
)
from playwright.sync_api import expect
from render_cases_layout import (
    SHOT_PAGE,
    SHOT_SRC,
    SHOTS,
    UNPARSABLE_DIAGRAM,
    shown_frames,
    solid_png,
)
from render_harness import (
    LONG_PAGE,
    example_media,
    leaf_page,
)

from leaf import render_checks as render_checks_model
from leaf import user_views
from leaf.render_gate.command import PIN_VARIABLE
from leaf.render_gate.page_code import run_page_code

pytestmark = pytest.mark.shifts_unsurveyed

from browser.test_render_commands import FILM_DECLARATION, FILM_PAGE, unnamed_browser
from model.test_user_views import report as user_view_report


def test_check_render_refuses_what_only_a_browser_can_see(serve):
    """`page check --render` end to end, as the agent runs it: the static lint
    passes both sources, and only one renders clean. The broken source is deliberately
    unstamped — refusing it before `page stamp` names it is the gate's whole job,
    so the preview server has to expose the exact candidate without activating it.

    The clean source goes through the installed Chrome the default channel finds; the
    executable leaf's browser variable names is
    `test_an_installed_payload_passes_its_real_browser_gate`'s. This arm states every
    variable empty rather than inheriting whatever the developer or the job
    exported, since a set one would otherwise turn the channel this arm exists to
    cover into a run of the named one. A runner image really does export
    CHROME_BIN, so unnaming leaf's alone is not unnaming. A clean result has to name
    the browser that drew the page: a clean gate telling a Chromium host that Chrome
    drew it is the same false claim on the way out that the failure messages stopped
    making."""
    serve(LONG_PAGE)
    d = serve.page_dir

    def gate(*flags):
        return subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d), "--render", *flags],
            capture_output=True,
            text=True,
            check=False,  # both exit codes are the subject
            env=unnamed_browser(),
        )

    ok = gate()
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["browser"]["browser"] == "Chrome"

    # A vw width slips the static lint (which counts only px) and overflows only
    # in a layout engine.
    (d / "index.html").write_text(
        LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div>\n</main>")
    )
    broken = gate()
    assert broken.returncode == 1, broken.stderr
    report = json.loads(broken.stdout)
    assert report["status"] == 1
    assert report["browser"]["asked"] == report["browser"]["ran"] == ["render check"]
    assert report["browser"]["browser"] == "Chrome"
    [scrolls] = [f for f in report["findings"] if f["code"] == "page-scrolls"]
    assert scrolls["widths"] == [360, 1920], report
    assert scrolls["severity"] == "error" and scrolls["values"]["past"] > 0, scrolls


def test_a_passing_render_check_saves_the_screens_the_author_reads(
    serve, headless_shell
):
    """A clean `page check --render` saves screens and names them: the page top to
    bottom at the desktop viewport and on a phone, and one screen at each width where
    the page's own arrangement is at its tightest before it changes. A sidebar page with
    four tiles in its body changes twice there: its tiles wrap before its track stacks.
    Each open obligation, a suggestion as much as an lf-ask, gets the window `m` brings it
    into, as the user working the page meets it, including those `m` reaches past a
    page widget move handed back to the user, which is a stop of its own and no obligation."""
    tiles = "".join(
        f"<dl id='m{i}'><dt>metric {i}</dt><dd>{i}</dd></dl>" for i in range(4)
    )
    serve(
        leaf_page(
            "a sidebar page",
            "<header><h1>Rollout</h1></header>"
            "<div id='body'><lf-ask id='ship-ask'><h2>Ship now?</h2>"
            "<lf-options id='ship' choose><lf-option id='ship-now'>Now</lf-option>"
            "<lf-option id='ship-later'>Later</lf-option></lf-options></lf-ask>"
            f"<div class='layout-tiles' id='2026-numbers'>{tiles}</div>"
            + "".join(
                f"<p id='para-{i}'>{'Body paragraph. ' * 30}</p>" for i in range(60)
            )
            + "".join(
                f"<lf-ask id='ask-{i}'><h2>Ship part {i}?</h2>"
                f"<lf-options id='o-{i}' choose><lf-option id='o-{i}-y'>Yes</lf-option>"
                f"<lf-option id='o-{i}-n'>No</lf-option></lf-options></lf-ask>"
                for i in range(2)
            )
            + "<p id='note'>Keep this line.<lf-suggestion id='sug'><lf-old>"
            "Drop this one.</lf-old></lf-suggestion></p>"
            + "</div><aside id='checks'><p>Checks beside the body.</p></aside>",
            layout="sidebar",
        )
    )
    # The first obligation is answered, and the host gave up on picking the answer up, which
    # hands the move back: the walk's first stop is that widget, ahead of every obligation.
    moved = append_command(
        serve.page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": 1,
            "widget": "ship",
            "action": "choose",
            "detail": {"value": ["ship-now"]},
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "pickup",
            "author": "page",
            "attention": False,
            "events": [moved["id"]],
            "phase": "failed",
            "failure": "turn_failed",
            "session": "screens",
            "turn": "turn-1",
        },
    )
    on_user = state_json(serve.page_dir)["queues"]["on_user"]
    assert {"kind": "widget", "id": "ship"} in [item["subject"] for item in on_user]

    ran = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(serve.page_dir), "--render"],
        check=False,
        capture_output=True,
        text=True,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    screens = json.loads(ran.stdout)["browser"]["screens"]
    into = Path(screens["directory"])
    shows = {screen["file"]: screen["shows"] for screen in screens["files"]}
    names = sorted(path.name for path in into.iterdir())
    assert set(shows) <= set(names)
    assert {"1280px-1.png", "1920px-1.png", "390px-1.png"} <= set(names)
    assert {
        "1280px-obligation-1.png",
        "1280px-obligation-2.png",
        "1280px-obligation-3.png",
    } <= set(names)
    assert "1280px-obligation-4.png" not in names
    assert any("each press of `m`" in label for label in shows.values())
    assert '"Pre-handover review"' in screens["next"]
    assert any("<main> 1+2 → 1+1+1" in label for label in shows.values())
    assert any("<div id=2026-numbers> 4 → " in label for label in shows.values())
    # A page longer than its first screens says so rather than passing for read whole.
    assert "390px-9.png" not in names
    assert any("phone, the first 8 of the page's" in label for label in shows.values())


def test_a_render_check_reads_the_desktop_in_the_users_window(
    serve, headless_shell, monkeypatch
):
    """With a browser's report of its window on the page, `page check --render`
    reads the desktop, its screens included, at that window and says so; pinned, as
    the suite and evals pin it, it reads the fixed laptop window."""
    serve(LONG_PAGE)
    d = serve.page_dir
    window = user_view_report()
    window["viewport"] = {"width": 1000, "height": 640}
    user_views.observe_user_view(d, window)

    def desktop(**pin):
        ran = subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d), "--render"],
            capture_output=True,
            text=True,
            check=True,
            env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell} | pin,
        )
        browser = json.loads(ran.stdout)["browser"]
        names = {screen["file"] for screen in browser["screens"]["files"]}
        return browser["desktop"], names

    monkeypatch.delenv(PIN_VARIABLE)
    read, names = desktop()
    assert read == {"width": 1000, "height": 640, "from": "the user's window"}
    assert "1000px-1.png" in names, names
    read, names = desktop(**{PIN_VARIABLE: "fixed"})
    assert (read["width"], read["height"]) == (1280, 720), read
    assert "1280px-1.png" in names, names


def test_a_named_browser_that_is_not_one_names_the_variable(serve, tmp_path):
    """A browser variable is the whole of what a host says about its browser, so a
    value naming no browser has to come back as that variable and that value rather
    than as Chrome, which the host never asked for.

    Whichever variable the host set is the one the message names. Reporting a
    CHROME_PATH browser as LEAF_BROWSER_EXECUTABLE's would be a false statement about
    the host's own configuration, and it points the reader at a variable they never
    set — so the second half checks the other two by their own names."""
    serve(LONG_PAGE)
    d = serve.page_dir
    missing = tmp_path / "not-a-browser"
    named = unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": str(missing)}

    checked = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(d), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=named,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    unavailable = json.loads(checked.stdout)["browser"]["unavailable"]
    assert unavailable.startswith("no browser launched: ")
    assert "LEAF_BROWSER_EXECUTABLE" in unavailable and str(missing) in unavailable
    assert "Chrome did not launch" not in unavailable

    for variable in ("CHROME_PATH", "CHROME_BIN"):
        answered = subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d), "--render"],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {variable: str(missing)},
        )
        assert answered.returncode == 0, answered.stdout + answered.stderr
        unavailable = json.loads(answered.stdout)["browser"]["unavailable"]
        assert variable in unavailable and str(missing) in unavailable
        assert "LEAF_BROWSER_EXECUTABLE" not in unavailable


def test_an_installed_payload_passes_its_real_browser_gate(tmp_path, headless_shell):
    """Exercise the copied artifact a harness installs, never an import from this checkout.

    Its browser gate runs on a named Chromium, since the install is where a host with
    a Chromium and no Chrome meets it, and its result names that executable rather
    than Chrome; the default channel's Chrome is
    `test_check_render_refuses_what_only_a_browser_can_see`'s."""
    root = Path(__file__).parents[2]
    installed = install_payload(tmp_path / "host" / "leaf")
    launcher = installed / "bin" / "leaf"
    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    page_dir = tmp_path / "state" / "page"

    init = subprocess.run(
        [launcher, "page", "init", "--package", "diagram", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    vocabulary = subprocess.run(
        [launcher, "page", "vocabulary", page_dir],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert vocabulary.returncode == 0, vocabulary.stderr
    installed_registry = json.loads(vocabulary.stdout)
    assert "lf-diagram" in installed_registry
    assert installed_registry["$layer"]["packages"] == ["diagram"]
    (page_dir / "index.html").write_text(
        (root / "examples" / "release-notes.html").read_text()
    )
    shutil.copytree(example_media(), page_dir / "media", dirs_exist_ok=True)
    stamp = subprocess.run(
        [
            launcher,
            "page",
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

    rendered = subprocess.run(
        [launcher, "page", "check", page_dir, "--render"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert json.loads(rendered.stdout)["browser"]["browser"] == headless_shell


def test_a_shot_compares_its_frames_with_a_direct_divider(browser, serve):
    """The live pair is continuously comparable through its native divider.

    Image clicks, pointer drag and the complete keyboard pattern move one divider,
    while print keeps the two complete frames and their order. The gate's pass is
    `test_render_reads_widget_chrome_where_it_stands`'s."""
    url = serve(
        SHOT_PAGE,
        media={SHOT_SRC[name]: data for name, data in SHOTS.items()},
    )

    page = browser.new_page(viewport={"width": 1200, "height": 900})
    page.add_init_script(
        """new MutationObserver(() => {
          if (document.body?.hasAttribute('data-lf-presented') &&
              window.__lfPresentedAt === undefined)
            window.__lfPresentedAt = performance.now();
        }).observe(document, {attributes: true, subtree: true});
        new PerformanceObserver(list => {
          for (const entry of list.getEntries())
            if (entry.name.endsWith('/vendor/webawesome.esm.js'))
              window.__lfComparisonRequestedAt = entry.startTime;
        }).observe({type: 'resource', buffered: true});"""
    )
    page.goto(url)
    render_checks_model.wait_until_ready(page)
    page.locator("lf-shot").get_by_role("button", name="Slider", exact=True).click()
    comparison = page.locator("lf-shot wa-comparison")
    handle = comparison.get_by_role("scrollbar")
    expect(handle).to_be_visible()
    page.wait_for_function("window.__lfComparisonRequestedAt !== undefined")
    timing = page.evaluate(
        """() => ({
          presented: window.__lfPresentedAt,
          requested: window.__lfComparisonRequestedAt,
        })"""
    )
    assert timing["requested"] >= timing["presented"]
    rail = page.locator("lf-shot .lf-shot-toolbar")
    expect(rail).to_have_count(1)
    expect(rail.locator(".lf-shotcap")).to_have_text(["Before", "After"])
    before_bounds = rail.locator('[data-lf-state="before"]').bounding_box()
    after_bounds = rail.locator('[data-lf-state="after"]').bounding_box()
    assert before_bounds is not None and after_bounds is not None
    expect(comparison).to_have_attribute("position", "50")
    glyph = comparison.locator('[slot="handle"].lf-shot-handle')
    expect(glyph).to_have_count(1)
    assert glyph.evaluate(
        "node => [getComputedStyle(node).borderStyle, "
        "getComputedStyle(node).borderRadius]"
    ) == ["solid", "50%"]
    expect(handle).to_have_accessible_name("Before and after — the navigation rail")
    expect(handle).to_have_attribute("aria-valuetext", "Before 50%, after 50%")
    # Labels keep source order across the viewport-wide header, while fitted images
    # can be narrower. Each image half must show that source. Web Awesome's `after`
    # slot is the inline-start side, so wiring same-named slots reverses the evidence.
    comparison.scroll_into_view_if_needed()
    visible_halves = page.evaluate(
        """() => {
          const box = document.querySelector('lf-shot wa-comparison')
            .getBoundingClientRect();
          return [...document.querySelectorAll('lf-shot .lf-shot-toolbar .lf-shotcap')].map((cap, index) => {
            const x = box.left + box.width * (index === 0 ? 0.25 : 0.75);
            const hit = document.elementFromPoint(x, box.top + box.height / 2);
            return [cap.dataset.lfState, hit?.closest('.lf-shotframe')?.dataset.lfState];
          });
        }"""
    )
    assert before_bounds["x"] < after_bounds["x"]
    assert visible_halves == [["before", "before"], ["after", "after"]]
    page.emulate_media(media="print")
    assert shown_frames(page) == ["before", "after"]
    printed_tops = [
        page.locator(f'lf-shot .lf-shotframe[data-lf-state="{state}"]').bounding_box()[
            "y"
        ]
        for state in ("before", "after")
    ]
    assert printed_tops[0] < printed_tops[1], "paper put the after frame on top"
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
          };
        }"""
    )
    assert divider_face["divider"] != divider_face["handle"]

    comparison.scroll_into_view_if_needed()
    bounds = comparison.bounding_box()
    assert bounds is not None
    image_point = (bounds["x"] + bounds["width"] / 4, bounds["y"] + 80)
    page.mouse.click(*image_point)
    expect(comparison).to_have_attribute("position", "100")
    expect(handle).to_have_attribute("aria-valuetext", "Before 100%, after 0%")
    page.mouse.click(*image_point)
    expect(comparison).to_have_attribute("position", "0")
    page.keyboard.down("Shift")
    page.mouse.click(*image_point)
    page.keyboard.up("Shift")
    expect(comparison).to_have_attribute("position", "0")
    comparison.evaluate("node => { node.position = 50; }")
    view = page.locator("lf-shot").get_by_role("button", name="Slider", exact=True)
    # A second finger does not replace the primary contact's input destination.
    view.focus()
    handle.evaluate("""handle => handle.dispatchEvent(new PointerEvent('pointerdown', {
      bubbles: true, composed: true, pointerId: 98, pointerType: 'touch',
      isPrimary: false, button: 0
    }))""")
    expect(view).to_be_focused()
    handle.click()
    expect(handle).to_be_focused()
    expect(comparison).to_have_attribute("position", "50")
    page.keyboard.press("ArrowRight")
    expect(comparison).to_have_attribute("position", "51")
    page.keyboard.press("End")
    expect(comparison).to_have_attribute("position", "100")

    handle.focus()
    expect(handle).to_be_focused()
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
    handle.focus()
    page.keyboard.press("End")
    expect(handle).to_be_focused()
    width = handle.evaluate(
        "node => getComputedStyle(node).outlineStyle === 'none' ? 0 :"
        " parseFloat(getComputedStyle(node).outlineWidth)"
    )
    assert width > 0


def test_the_shim_runs_the_gate_from_anywhere(serve, tmp_path, headless_shell):
    """`leaf` is what the skill hands an agent, so the shim's own resolution
    is load-bearing: it names the payload project from its own location rather
    than letting uv find whatever project the cwd sits in. Running it from an
    unrelated directory exercises that.

    The version under it carries a diagram body the renderer refuses — a shape the
    static lint cannot reach, since it validates the element and never the
    notation inside it. The widget fails soft and reports it, and a data body is
    what sends plain `page check` to the browser to hear that report, which is why
    the check is worth its couple of seconds."""
    serve(UNPARSABLE_DIAGRAM)
    d = serve.page_dir

    shim = Path(__file__).parents[2] / "bin" / "leaf"
    for executable in ("", headless_shell):
        run = subprocess.run(
            [str(shim), "page", "check", str(d)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | {"LEAF_BROWSER_EXECUTABLE": executable},
        )
        assert run.returncode == 1, run.stdout + run.stderr
        # "needs Playwright" here would mean the shim dispatched the plain `uv run`.
        # The report names the widget, gives Pele's reason and locates its call site.
        report = json.loads(run.stdout)
        assert report["browser"]["ran"] == ["page code"]
        [error] = [f["text"] for f in report["findings"] if f["severity"] == "error"]
        assert '<lf-diagram id="d-broken"> failed:' in error
        assert "No diagram type detected" in error
        assert "/widgets/lf-diagram.js:" in error
        assert "leaf-unsupported" not in error
        assert "Ada,Review,3" not in error


def test_plain_check_runs_a_page_whose_widget_reads_media(serve, headless_shell):
    """A screenshot pair shot at two viewports is refused only by lf-shot's module, once
    it has decoded both images; the static check proves the files exist and never
    opens them. A page with no code of its own and no data widget otherwise takes
    plain `page check` without a browser, so the refusal first reached the user, as an
    error box where the pair should have been. Media an upgraded widget names sends
    the check to the browser, and the same page passes once the pair shares a width."""
    narrow = solid_png(500, 300, (235, 215, 205))
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    serve(
        SHOT_PAGE.replace(SHOT_SRC["after"], narrow_src),
        media={SHOT_SRC["before"]: SHOTS["before"], narrow_src: narrow},
    )
    d = serve.page_dir

    def check(status):
        ran = subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d)],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
        )
        assert ran.returncode == status, ran.stdout + ran.stderr
        report = json.loads(ran.stdout)
        assert report["browser"]["ran"] == ["page code"], report
        return [f["text"] for f in report["findings"] if f["severity"] == "error"]

    [error] = check(1)
    refusal = '<lf-shot id="shot-nav"> failed: before is 600px wide and after is 500px'
    assert refusal in error

    (d / "index.html").write_text(SHOT_PAGE)
    for name, data in SHOTS.items():
        (d / SHOT_SRC[name].lstrip("/")).write_bytes(data)
    assert check(0) == []


def test_plain_check_reports_page_request_failures_but_ignores_optional_assets(
    browser, serve
):
    url = serve(
        FILM_PAGE.replace("</main>", '<img src="/page/missing-image.png"></main>'),
        page_files={
            "registry.json": json.dumps(FILM_DECLARATION),
            "film.js": 'import { label } from "./helper.js";\n'
            "export const paint = el => (el.textContent = label);\n",
            "helper.js": 'export const label = "loaded";\n',
            "widgets/lf-film.js": 'import { paint } from "../film.js";\n'
            "customElements.define('lf-film', class extends HTMLElement {\n"
            "  connectedCallback() { paint(this); }\n"
            "});\n",
            "widgets/lf-loader.js": "customElements.define('lf-loader', class extends HTMLElement {\n"
            "  connectedCallback() { this.textContent = 'loaded'; }\n"
            "});\n",
        },
        media={"page/missing-image.png": solid_png(1, 1, (0, 0, 0))},
    )

    class RoutedBrowser:
        def __init__(self, *, fail_helper):
            self.fail_helper = fail_helper

        def new_page(self, **kwargs):
            page = browser.unwatched.new_page(**kwargs)
            page.route(
                "**/page/helper.js",
                lambda route: (
                    route.abort("failed") if self.fail_helper else route.continue_()
                ),
            )
            page.route(
                "**/page/missing-image.png", lambda route: route.fulfill(status=404)
            )
            return page

    failed = run_page_code(RoutedBrowser(fail_helper=True), url)
    # The runtime's own report carries the error's stack; the check's refusal quotes
    # only the reason the page shows.
    by_code = {}
    for report in failed:
        by_code.setdefault(report.code, []).append(report.values)
    assert any(
        report["text"].startswith("page failed to start:")
        and "TypeError" in report["text"]
        for report in by_code["page-report"]
    ), failed
    assert by_code["not-ready"][0]["stage"] == "refused", failed
    assert by_code["not-ready"][0]["error"].startswith("the runtime could not start:")
    assert any(
        report["kind"] == "Script"
        and report["error"] == "net::ERR_FAILED"
        and report["frame"] == url
        and report["url"].endswith("/page/helper.js")
        for report in by_code["request-failed"]
    ), failed
    assert any(
        report["status"] == 404
        and report["kind"] == "Image"
        and report["url"].endswith("/page/missing-image.png")
        for report in by_code["request-status"]
    ), failed

    assert run_page_code(RoutedBrowser(fail_helper=False), url) == []


def test_plain_check_runs_the_code_a_page_authored(serve, tmp_path, headless_shell):
    """A quick page takes plain `page check` and nothing else, so that is the check
    that has to run the page's own code: a widget that throws on its first paint, or
    a load that rejects, is otherwise heard of only once the user's browser reports
    it to the watcher. The check fails on those reports, worded as the watcher gets
    them — the painter's throw names the module under `page/` that threw, not the
    widget that called it — and passes the same page once its modules run clean.

    A page without code of its own is still checked without a browser: the missing
    executable named below is never launched. A host with no browser at all, as
    leaf.page's container is, skips the run with a note rather than refusing the page,
    since the same errors reach the author as `error` events once a browser draws it."""
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

    def check(status, **env):
        ran = subprocess.run(
            [*LEAF_COMMAND, "page", "check", str(d)],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | env,
        )
        assert ran.returncode == status, ran.stdout + ran.stderr
        return json.loads(ran.stdout)

    no_browser = check(0, LEAF_BROWSER_EXECUTABLE=str(tmp_path / "not-a-browser"))
    assert no_browser["browser"] is None

    (d / "index.html").write_text(FILM_PAGE)
    broken = check(1, LEAF_BROWSER_EXECUTABLE=headless_shell)
    errors = [f["text"] for f in broken["findings"] if f["severity"] == "error"]
    assert len(errors) == 2, broken
    errors = "\n".join(errors)
    assert "map is not a function" in errors
    assert "at paint (" in errors
    assert "/page/film.js:2:" in errors
    assert "Error: the trace never loaded" in errors
    assert "/page/widgets/lf-loader.js:3" in errors

    unrun = check(0, LEAF_BROWSER_EXECUTABLE=str(tmp_path / "not-a-browser"))
    assert (unrun["browser"]["asked"], unrun["browser"]["ran"]) == (["page code"], [])
    assert unrun["browser"]["unavailable"].startswith("no browser launched: ")

    (d / "page" / "film.js").write_text(
        "export const paint = (el, step) =>\n"
        "  (el.textContent = [step.cmp].flat().map(String).join());\n"
    )
    (d / "page" / "widgets" / "lf-loader.js").write_text(
        "customElements.define('lf-loader', class extends HTMLElement {\n"
        "  connectedCallback() { this.textContent = 'loaded'; }\n"
        "});\n"
    )
    clean = check(0, LEAF_BROWSER_EXECUTABLE=headless_shell)
    assert clean["browser"]["ran"] == ["page code"]
    assert clean["browser"]["browser"] == headless_shell
