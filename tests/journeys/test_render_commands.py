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


def test_a_failing_render_check_saves_screens(serve, headless_shell):
    """Findings leave the author pictures of the page that needs fixing."""
    serve(LONG_PAGE.replace("</main>", "<div style='width:150vw'>wide</div></main>"))
    ran = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(serve.page_dir), "--render"],
        capture_output=True,
        text=True,
        check=False,
        env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": headless_shell},
    )
    assert ran.returncode == 1, ran.stdout + ran.stderr
    report = json.loads(ran.stdout)
    assert any(f["code"] == "page-scrolls" for f in report["findings"]), report
    screens = report["browser"]["screens"]
    into = Path(screens["directory"])
    names = {screen["file"] for screen in screens["files"]}
    assert {"1280px-1.png", "1920px-1.png", "390px-1.png"} <= names
    assert all((into / name).is_file() for name in names)


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


from browser.test_render_commands import stage_reach_cases
from browser.threads import open_panel_thread
from interact_support import (
    add_test_widget,
    wait_for,
)
from render_cases_layout import (
    BADGE_CHROME,
)
from render_harness import (
    CARRIED_PAGE,
    EXAMPLE_PACKAGES,
    REPLY_HOST_PAGE,
    SAMPLE_MARKUP,
    SAMPLE_TEXT,
    consume_browser_errors,
    open_page,
    primed,
)

from leaf import event_log as events_model
from leaf.render_gate import version as render_gate_model


@pytest.mark.shifts_unsurveyed
def test_render_reads_widget_chrome_where_it_stands(
    browser, serve, tmp_path, monkeypatch
):
    """The user's reading of a page, on one page.

    The words a widget puts out of reach. A user selected a draft's heading, tried to
    comment on it, and got nothing back — twice, months apart, on the same page. The
    heading was the page's word in a row its author had marked as the runtime's, and
    `.lf-ui` is a look rather than a permission, so the class alone can't be the answer:
    the declaration goes on the label (relabel), and an undeclared word under chrome is
    reported. It is about a word the user was shown, so the check asks that first: a
    word the browser reads out and the page never paints is hidden with [hidden], the
    silence available in every root, and the same word shown is still reported. A
    visible control and an otherwise identical one below an unscrollable clip keep the
    control-reachability reading non-vacuous.

    The chrome half, asked where the nesting turns over. A widget's chrome is a
    `.lf-ui` the widget put inside itself. A widget in a message is the other way up:
    the runtime's own layer is above it and the widget has none of its own, so every
    word it holds sits under a `.lf-ui` with nothing wrong. Asking whether the *words*
    stand in a widget cannot tell those apart and accuses the second; asking whose the
    `.lf-ui` is can. One reply carries three widgets: a question, an exhibit beside it,
    and a badge whose module injects unmarked words under the chrome face. The panel
    around all three says nothing; the badge's own chrome is read exactly as it would
    be on a page. Nothing here had ever been rendered until a fixture asked the gate
    rather than the panel.

    Beside them, a pair shot captured at two widths: both frames render at the frame's
    width, so the pair is scaled by two different factors and every line lands somewhere
    new, and the flip would report that the whole page changed with nothing on screen
    to say otherwise. That is the one shot failure worth an error box rather than a
    caveat, and the gate has to hear about it, since nobody else will. The same shot
    with both frames at one width passes."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-badge", upgrade=True)
    module = package / "widgets" / "lf-badge.js"
    source = module.read_text()
    starter = "class extends LeafElement {},"
    assert source.count(starter) == 1
    module.write_text(
        source.replace(
            starter,
            "class extends LeafElement {\n    setup() {\n"
            + BADGE_CHROME
            + "\n    }\n  },",
        )
    )
    narrow = solid_png(400, 300, (235, 215, 205))
    narrow_src = f"/media/{hashlib.sha256(narrow).hexdigest()[:16]}.png"
    pair = (
        f'<lf-shot id="shot-pair" alt="the navigation rail" before="{SHOT_SRC["before"]}"'
        f' after="{narrow_src}"></lf-shot>'
        f'<lf-shot id="shot-nav" alt="the navigation rail" before="{SHOT_SRC["before"]}"'
        f' after="{SHOT_SRC["after"]}"></lf-shot>'
    )
    start = CARRIED_PAGE.index('<lf-options id="carried">')
    carried = CARRIED_PAGE[start : CARRIED_PAGE.index("</lf-options>") + 13]
    source = REPLY_HOST_PAGE.replace("</main>", carried + pair + "</main>")
    url = serve(
        source,
        packages=(*EXAMPLE_PACKAGES, "./.leaf"),
        media={
            **{SHOT_SRC[name]: data for name, data in SHOTS.items()},
            narrow_src: narrow,
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "comment",
            "id": "c-decision",
            "author": "user",
            "revision": 1,
            "text": "What would the alternative look like?",
        },
    )
    append_carried_log_record(
        serve.page_dir,
        {
            "kind": "reply",
            "author": "agent",
            "parent": "c-decision",
            "revision": 1,
            "text": SAMPLE_TEXT,
            "markup": SAMPLE_MARKUP + '<lf-badge id="rp-badge">Weighed.</lf-badge>',
        },
    )
    page = open_page(primed(browser, stage_reach_cases), url)
    assert (
        page.locator(
            "#native-link, #hidden-note, #shown-note, #unreachable-row, "
            "#unreachable-button"
        ).count()
        == 5
    )
    assert page.locator("#hidden-note").is_hidden()
    assert page.locator("#shown-offer, #clipped-offer").count() == 2
    assert page.locator("#shown-offer").is_visible()
    # A label inside a form control no marker can reach is the suite's question of
    # Leaf's own modules (`test_page_fixture_renders`), not the gate's.
    assert [
        said
        for said in render_checks_model.evaluate_probe(page, "wordsInFormControls")
        if said["at"] == "<lf-option id=c-lax>"
    ] == [
        {
            "code": "form-control-words",
            "at": "<lf-option id=c-lax>",
            "words": "Lax, host-only",
        }
    ]
    # The two-width pair fails soft, as the gate below is to hear.
    consume_browser_errors(page, '<lf-shot id="shot-pair"> failed')
    page.close()

    failures = render_gate_model.render_version(
        primed(browser.unwatched, stage_reach_cases), url
    ).failures
    pair = [f for f in failures if f.code == "console-error"]
    assert pair and all(
        "shot-pair" in f.values["text"]
        and "600px" in f.values["text"]
        and "400px" in f.values["text"]
        for f in pair
    ), failures
    clipped = [f for f in failures if f.code == "clipped-control"]
    assert [(f.values["id"], f.widths) for f in clipped] == [
        ("clipped-offer", (360, 1920))
    ], failures
    assert all(f.values["by"] == "<div id=clipped-holder>" for f in clipped), clipped
    words = sorted(
        {(f.code, f.at, f.values["words"]) for f in failures if f not in pair + clipped}
    )
    assert words == [
        ("chrome-words", "<lf-badge id=rp-badge>", "Sent by the reviewer"),
        ("chrome-words", "<lf-option id=c-lax>", "Session cookies"),
        ("chrome-words", "<lf-option id=c-lax>", "opens in a new tab"),
    ], failures


@pytest.mark.shifts_unsurveyed
def test_a_widget_that_fails_in_a_message_is_refused_where_a_browser_draws_it(
    browser, serve, tmp_path, headless_shell
):
    """Nothing draws a message's widgets before the user opens its thread, and the
    log freezes the message, so a thread command runs markup holding a widget only a
    browser can judge once before it posts, and refuses it with the widget's own
    error, as plain `page check` refuses a page. A host with no browser posts it
    unrun; the body its module cannot draw then reports to the author when the user
    opens its thread, naming the widget, and the author answers with a corrected
    reply."""
    url = serve(LONG_PAGE)
    d = serve.page_dir

    def post(executable):
        return subprocess.run(
            [*LEAF_COMMAND, "thread", "create", str(d), "--text", "See this."]
            + [
                "--markup",
                '<lf-chart id="t-bad"><pre>\n{ marks: [ }\n</pre></lf-chart>',
            ],
            capture_output=True,
            text=True,
            check=False,
            env=unnamed_browser() | {"LEAF_BROWSER_EXECUTABLE": executable},
        )

    refused = post(headless_shell)
    assert refused.returncode != 0, refused.stdout + refused.stderr
    refusal = json.loads(refused.stderr)["error"]
    assert refusal.startswith("comment markup doesn't draw:"), refusal
    assert '<lf-chart id="t-bad"> failed: ' in refusal
    assert not [e for e in events_model.read_events(d) if e["kind"] == "comment"]

    posted = post(str(tmp_path / "none"))
    assert posted.returncode == 0, posted.stdout + posted.stderr

    [root] = [e["id"] for e in events_model.read_events(d) if e["kind"] == "comment"]
    page = open_page(browser, url)
    view = open_panel_thread(page, root)
    expect(view.locator("#t-bad .lf-error")).to_contain_text("Unexpected token")
    report = '<lf-chart id="t-bad"> failed: '
    consume_browser_errors(page, report)
    reported = wait_for(
        lambda: [
            event["text"]
            for event in events_model.read_events(d)
            if event["kind"] == "error"
        ],
        bool,
        failure="the page never reported the chart",
    )
    assert len(reported) == 1 and reported[0].startswith(report), reported
