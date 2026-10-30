"""CLI, plugin payload, layer, and customization tests."""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from interact_support import (
    COMMAND_HUB_PACKAGE,
    PAGE,
    ROOT,
    STATED_TIMEOUT,
    add_test_widget,
    check,
    fetch,
    install_payload,
    page_packages,
    publish,
    vendored_at_another_protocol,
)

from leaf import cli as cli_model
from leaf import delivery as delivery_model
from leaf import event_log as events_model
from leaf import files as interact_files
from leaf import layer as layer_model
from leaf import packages as packages_model
from leaf.registry.storage import (
    layer_record,
    layer_widgets,
    load_registry,
    selected,
)


def test_an_installed_payload_is_complete_and_launches_outside_the_checkout(
    tmp_path, monkeypatch
):
    # This test runs the copied install's launcher, not the browser-tier fixture's
    # prepared checkout launcher.
    monkeypatch.delenv("LEAF_HOST_LAUNCHER", raising=False)
    commit = "4cb17dc60870"
    installed = install_payload(
        tmp_path / "host" / ".claude" / "plugins" / "cache" / "leaf" / "leaf" / commit
    )

    conflicts = []
    for path in installed.rglob("*"):
        if not path.is_file() or "vendor" in path.parts:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.match(r"^(<{7}|={7}|>{7})(?: |$)", line):
                conflicts.append(f"{path.relative_to(installed)}:{line_no}")
    assert conflicts == []

    elsewhere = tmp_path / "unrelated-project"
    elsewhere.mkdir()
    work = elsewhere / "work"
    shutil.copytree(COMMAND_HUB_PACKAGE, work)
    selected = ("./work", *page_packages()[1:])
    launcher = installed / "bin" / "leaf"
    page = tmp_path / "state" / "page"

    help_result = subprocess.run(
        [launcher, "--help"],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert help_result.stderr == ""
    assert (
        "Build and run interactive pages a session shares with its user."
        in help_result.stdout
    )

    init_result = subprocess.run(
        [
            launcher,
            "page",
            "init",
            *(arg for name in selected for arg in ("--package", name)),
            page,
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_result.returncode == 0, init_result.stderr
    vocabulary = subprocess.run(
        [launcher, "page", "vocabulary", page],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert vocabulary.returncode == 0, vocabulary.stderr
    installed_registry = json.loads(vocabulary.stdout)
    assert "lf-test-plan" in installed_registry
    # The page holds its copy of the project package, so it reads the same anywhere.
    assert installed_registry["$layer"]["packages"] == [
        "./packages/work",
        *selected[1:],
    ]
    (page / "index.html").write_text(PAGE)
    publish_result = subprocess.run(
        [
            launcher,
            "page",
            "stamp",
            page,
            "--text",
            "installed-payload smoke",
        ],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert publish_result.returncode == 0, publish_result.stderr
    assert interact_files.published_versions(page, events_model.read_events(page)) == [
        1
    ]


@pytest.mark.network
def test_the_launcher_installs_quietly_with_an_empty_cache(tmp_path):
    """First-time installation really downloads the payload's dependencies.

    An empty cache exercises uv's install summary, which `bin/leaf` must silence
    on success. The ordinary installed-payload smoke test uses the setup cache;
    only this test requires an external package index.
    """
    installed = install_payload(tmp_path / "leaf")
    cold = subprocess.run(
        [installed / "bin" / "leaf", "--help"],
        cwd=tmp_path,
        env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "first-run-cache")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert cold.returncode == 0, cold.stderr
    assert cold.stderr == ""
    assert (
        "Build and run interactive pages a session shares with its user." in cold.stdout
    )


def test_the_resources_a_fixture_owns_are_taken_from_that_fixture():
    """Each of these has one owner in the suite, and the owner is what ends it.

    A process, a browser, and a directory short enough to hold a socket: what a test
    gets by asking for the fixture is a teardown, and what it gets by calling the
    primitive itself is a resource the run has no way to take back — a server still
    serving after the test that started it, a browser held for the rest of the
    worker, a directory under a root neither sweep walks. A fixture cannot stop a
    test making its own, so the call is read for here instead, which is the only
    place the rule can be enforced rather than written down.

    A new exception is a line in this list naming the file it belongs to and the
    reason, not a call that quietly joins the others.

    The end of the loan is read for too. A page or context the `browser` fixture
    made is closed by that fixture, after it has read what the page reported; a
    close where the test ends with it does the same work a step early, and the
    reading it cuts short is its own. The exception is a page that keeps making
    the fault its test is about, where the consume has to follow a close of its own
    (tests/AGENTS.md, "Browser errors").
    """
    closes_to_stop_a_repeating_fault = {
        "test_a_website_session_reference_survives_a_failed_first_read",
        "test_a_malformed_first_state_keeps_interaction_unresolved",
    }
    # What hands a test something the browser fixture will close: the fixtures built
    # on it, and `opened_tab`, whose tab is made readable and so reports into the
    # collector that fixture reads.
    lending = {"browser", "iphone", "held_events", "one_user", "opened_tab"}
    owners = {
        "Popen": ("spawn", {"conftest.py"}),
        "mkdtemp": ("socket_dir", {"interact_support.py"}),
        # The cached Codex schema helper in conftest.py closes its output
        # directory with a context manager before returning the schemas.
        "TemporaryDirectory": ("socket_dir", {"interact_support.py", "conftest.py"}),
        "launch": ("browser, iphone", {"conftest.py"}),
    }
    bypassed = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        named = path.relative_to(ROOT / "tests").as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            called = (
                node.func.attr
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                else None
            )
            if (
                isinstance(node, ast.Call)
                and called in owners
                and named not in owners[called][1]
            ):
                owner = owners[called][0]
                bypassed.append(f"{named}:{node.lineno} {called} — {owner} owns it")
        for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            if function.name in closes_to_stop_a_repeating_fault:
                continue
            # A fixture's own teardown is the owner ending what it lent. Read what
            # the decorator calls, not its whole text, which also carries a
            # `parametrize` whose ids can say "fixture".
            if any(
                ast.unparse(d).split("(")[0].endswith("fixture")
                for d in function.decorator_list
            ):
                continue
            # What the fixture owns is what came from it, however far the value
            # travelled and whatever the function was handed it as:
            # `host, app = open_snapshot_app(browser, page_dir)` hands back a page
            # as surely as `browser.new_page()` does, `browser, held = held_events`
            # hands over the browser itself, and `for tab in (first, second)` walks
            # pages. A list of the spellings that count would read some and miss
            # the next, so the names are followed until nothing new is reached.
            bindings = []
            for node in ast.walk(function):
                if isinstance(node, ast.Assign):
                    bindings.append((node.value, node.targets))
                elif isinstance(node, ast.For):
                    bindings.append((node.iter, [node.target]))
                elif isinstance(node, ast.With):
                    bindings += [
                        (item.context_expr, [item.optional_vars])
                        for item in node.items
                        if item.optional_vars is not None
                    ]
            lent = set(lending)
            while True:
                reached = {
                    name.id
                    for value, targets in bindings
                    if lent & {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
                    for target in targets
                    for name in ast.walk(target)
                    if isinstance(name, ast.Name)
                }
                if reached <= lent:
                    break
                lent |= reached
            # Only where the test is finished with the page: anywhere in a `finally`,
            # which is the end of the block the page was used in, and the function's
            # last line, followed down through a block it ends on. A close written
            # anywhere else is the gesture under test — a second tab shut to show
            # what the first one still holds — and the assertions after it are what
            # read it.
            endings = [
                statement
                for node in ast.walk(function)
                if isinstance(node, ast.Try)
                for final in node.finalbody
                for statement in ast.walk(final)
            ]
            last = function.body[-1]
            while isinstance(last, (ast.For, ast.If, ast.With)):
                last = last.body[-1]
            endings.append(last)
            for node in endings:
                if not isinstance(node, ast.Expr):
                    continue
                ending = ast.unparse(node)
                if ending.endswith(".close()") and ending[: -len(".close()")] in lent:
                    bypassed.append(
                        f"{named}:{node.lineno} {ending} — the browser fixture does"
                    )
    assert not bypassed, bypassed


def test_a_wait_takes_the_suites_deadline():
    """A wait in the suite bounds a hang; it does not time the work it waits for.

    A literal deadline is sized to how long the work took where it was written, and
    a busy runner takes many times that, so a correct product fails the test there
    (tests/AGENTS.md, "Functional results do not depend on execution speed").
    A Python-side wait takes `STATED_TIMEOUT`, or a constant derived from it. A
    browser wait takes `SERVED_TIMEOUT_MS`, which `render_harness` makes the default
    of every Playwright wait and `expect` that names none, or `HANDOVER_DEADLINE_MS`
    where it spans a page handover. So each bound is set in one place. A wait whose
    length is its subject names that value where it is defined, which keeps it out
    of this check without a list of exceptions here.

    Read are every `timeout` or `timeout_ms` a call passes or a helper defaults;
    the deadline a thread, future, event or socket takes first, and a page's
    default deadline; and a deadline a local loop computes from `monotonic()`. A
    zero timeout asks without waiting and is left alone. A sleep
    (`wait_for_timeout`) is a pause or an absence window, not a deadline.
    """
    deadline_names = {"timeout", "timeout_ms"}
    deadline_first = {
        "join",
        "result",
        "set_default_navigation_timeout",
        "set_default_timeout",
        "settimeout",
        "wait",
    }

    def literal(node) -> bool:
        if isinstance(node, ast.BinOp):
            return literal(node.left) and literal(node.right)
        return (
            isinstance(node, ast.Constant)
            and type(node.value) in (int, float)
            and node.value != 0
        )

    def called(func) -> str | None:
        return (
            func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        )

    def defaults(arguments):
        positional = arguments.posonlyargs + arguments.args
        yield from zip(
            positional[len(positional) - len(arguments.defaults) :], arguments.defaults
        )
        yield from zip(arguments.kwonlyargs, arguments.kw_defaults)

    fixed = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                computed = (
                    isinstance(node.left, ast.Call)
                    and called(node.left.func) == "monotonic"
                    and literal(node.right)
                )
            elif isinstance(node, ast.Call):
                computed = any(
                    keyword.arg in deadline_names and literal(keyword.value)
                    for keyword in node.keywords
                ) or (
                    called(node.func) in deadline_first
                    and isinstance(node.func, ast.Attribute)
                    and bool(node.args)
                    and literal(node.args[0])
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                computed = any(
                    argument.arg in deadline_names
                    and default is not None
                    and literal(default)
                    for argument, default in defaults(node.args)
                )
            else:
                continue
            if computed:
                fixed.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} "
                    + ast.unparse(node).split("\n", 1)[0]
                )
    assert not fixed, (
        "these waits fix their own deadline; bound them with STATED_TIMEOUT "
        "(interact_support.py), or in a browser with SERVED_TIMEOUT_MS or "
        f"HANDOVER_DEADLINE_MS (leaf.render_checks): {fixed}"
    )


def test_no_test_ends_a_process_with_sigkill():
    """SIGKILL gives a process no chance to end what it started, so a test ends one
    by closing the pipe it reads or with SIGTERM (tests/AGENTS.md, "Processes and servers"). The source is read for it, since no fixture
    sees which signal a test sends: `Popen.kill()`, `signal.SIGKILL`, signal 9
    passed to `kill`, `killpg` or `send_signal`, and a shell `kill` given signal 9
    or KILL in a command a test runs."""
    shell_kill = re.compile(r"\bkill\s+-(?:9|KILL|SIGKILL)\b")
    killed = []
    for path in sorted((ROOT / "tests").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                (isinstance(node, ast.Attribute) and node.attr == "SIGKILL")
                or (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "kill"
                    and not node.args
                )
                or (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"kill", "killpg", "send_signal"}
                    and node.args
                    and isinstance(node.args[-1], ast.Constant)
                    and node.args[-1].value == 9
                )
                or (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and shell_kill.search(node.value)
                )
            ):
                killed.append(
                    f"{path.relative_to(ROOT / 'tests')}:{node.lineno} "
                    + ast.unparse(node)[:80]
                )
    assert not killed, killed


def test_page_packages_are_explicit_and_survive_reinitialization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    runner = CliRunner()
    baseline = tmp_path / "baseline"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(baseline)])
    assert initialized.exit_code == 0, initialized.output
    user = home / ".config" / "leaf"
    project = tmp_path / ".leaf"
    for package, marker in (
        (user, "user"),
        (project, "project"),
        (config / "leaf", "xdg"),
    ):
        (package / "widgets").mkdir(parents=True)
        (package / "overrides.css").write_text(f":root {{ --{marker}-package: 1; }}\n")
        (package / "widgets" / f"{marker}.js").write_text(f"// {marker}\n")
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    def composed(page):
        layer_2 = layer_record(page)
        assert layer_2 is not None
        return selected(layer_2, page)

    assert composed(page) == composed(baseline)
    assert load_registry(page)["$layer"]["packages"] == []
    assert "user.js" not in composed(page).directory_files["widgets"]
    chosen = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "~/.config/leaf",
            "--package",
            "./.leaf",
            str(page),
        ],
    )
    assert chosen.exit_code == 0, chosen.output
    theme = composed(page).top_files["theme.css"].decode()
    # Selected packages follow the kernel in order, and the Layouts close the theme.
    assert (
        theme.index("--user-package")
        < theme.index("--project-package")
        < theme.index("@layer lf-layouts")
    )
    widgets = composed(page).directory_files["widgets"]
    assert "user.js" in widgets and "project.js" in widgets
    assert "xdg.js" not in widgets
    repeated = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert repeated.exit_code == 0, repeated.output
    registry = load_registry(page)
    # The record names the page's copies of the packages selected by path.
    assert registry["$layer"]["packages"] == ["./packages/leaf", "./packages/.leaf"]
    assert composed(page).top_files["theme.css"].decode() == theme
    cleared = runner.invoke(cli_model.cli, ["page", "init", "--no-packages", str(page)])
    assert cleared.exit_code == 0, cleared.output
    assert composed(page) == composed(baseline)


def test_an_idiom_declares_no_mark(tmp_path, monkeypatch):
    """An idiom carries author-facing words and no mark: delivery paints each mark from
    the element's tag, so a mark an idiom declared would paint nothing. A layer whose
    idiom declares one, or whose selector cannot be matched, is refused at init."""
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir()

    def init(selector, declaration, page):
        (layer / "registry.json").write_text(
            json.dumps(
                {
                    selector: {
                        "description": "d",
                        "x-example": '<p class="hazard">Warning</p>',
                        **declaration,
                    }
                }
            )
        )
        return CliRunner().invoke(
            cli_model.cli,
            ["page", "init", "--package", "./.leaf", str(tmp_path / page)],
        )

    for selector in (".hazard", "table", "lf-options.selected"):
        result = init(selector, {}, "plain")
        assert result.exit_code == 0, result.output
    for selector, declaration, page in (
        (".hazard", {"x-inline": True}, "inline"),
        (".hazard", {"x-space": "wide"}, "room"),
        (".hazard::before", {}, "pseudo"),
        (".hazard[", {}, "invalid-selector-without-marks"),
        (".hazard", {"x-example": ""}, "empty-example"),
        (".hazard", {"x-instructions": " "}, "empty-instructions"),
    ):
        result = init(selector, declaration, page)
        assert result.exit_code != 0
        assert f"idiom {selector!r}" in result.output


def test_package_continues_when_the_project_root_is_the_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", "."]
    )
    assert initialized.exit_code == 0, initialized.output
    record = layer_record(tmp_path)

    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-after-init", upgrade=True)
    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert checked.exit_code == 0, checked.output
    assert layer_record(tmp_path) == record
    assert (package / "widgets" / "lf-after-init.js").is_file()


@pytest.mark.parametrize("name", ["callout", "diagram", "default"])
def test_package_install_replaces_a_name_without_changing_held_readers(
    tmp_path, monkeypatch, name
):
    """Installation publishes one complete snapshot; invalid replacements preserve it.

    This holds for an existing installed name and an override of any bundled name,
    including an explicitly selected default overlay.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    source = tmp_path / "src" / name
    created = runner.invoke(cli_model.cli, ["package", "init", str(source)])
    assert created.exit_code == 0, created.output
    add_test_widget(source, "lf-installed", upgrade=True)
    (source / "overrides.css").write_text("lf-installed { color: teal; }\n")
    first = runner.invoke(cli_model.cli, ["package", "install", str(source)])
    assert first.exit_code == 0, first.output
    held = layer_model.named_package(name)
    assert held == Path(json.loads(first.output)["package"])
    first_registry = (held / "registry.json").read_bytes()
    (source / "overrides.css").write_text("lf-installed { color: purple; }\n")
    source_registry = source / "registry.json"
    updated = json.loads(source_registry.read_text())
    updated["lf-installed"]["description"] = "Replacement snapshot."
    source_registry.write_text(json.dumps(updated))
    replace = packages_model.os.replace
    observations = []

    def at_publication(staged, destination):
        if Path(staged).name == "selection":
            observations.append(layer_model.named_package(name))
            assert (
                held / "overrides.css"
            ).read_text() == "lf-installed { color: teal; }\n"
        replace(staged, destination)
        if Path(staged).name == "selection":
            observations.append(layer_model.named_package(name))

    with monkeypatch.context() as publication:
        publication.setattr(packages_model.os, "replace", at_publication)
        second = runner.invoke(cli_model.cli, ["package", "install", str(source)])
    assert second.exit_code == 0, second.output
    current = layer_model.named_package(name)
    assert observations == [held, current] and held != current
    assert (held / "registry.json").read_bytes() == first_registry
    assert (held / "overrides.css").read_text() == "lf-installed { color: teal; }\n"
    assert current is not None
    assert (
        json.loads((current / "registry.json").read_text())["lf-installed"][
            "description"
        ]
        == "Replacement snapshot."
    )
    assert (
        current / "overrides.css"
    ).read_text() == "lf-installed { color: purple; }\n"

    page = tmp_path / "page"
    vendored = runner.invoke(
        cli_model.cli, ["page", "init", "--package", name, str(page)]
    )
    assert vendored.exit_code == 0, vendored.output
    assert load_registry(page)["lf-installed"]["description"] == "Replacement snapshot."
    layer_3 = layer_record(page)
    assert layer_3 is not None
    theme = selected(layer_3, page).top_files["theme.css"].decode()
    assert "lf-installed { color: purple; }" in theme
    (source / "overrides.css").write_text(".bad { color red; }\n")
    refused = runner.invoke(cli_model.cli, ["package", "install", str(source)])
    assert refused.exit_code != 0 and "syntax error" in refused.output
    assert layer_model.named_package(name) == current
    assert (
        current / "overrides.css"
    ).read_text() == "lf-installed { color: purple; }\n"


def test_package_init_starts_one_checked_upgraded_widget(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = Path("packages/risk-notes")

    created = runner.invoke(
        cli_model.cli,
        ["package", "init", str(package), "--widget", "lf-risk-note"],
    )

    assert created.exit_code == 0, created.output
    package_root = tmp_path / package
    registry = json.loads((package_root / "registry.json").read_text())
    entry = registry["lf-risk-note"]
    assert entry["description"]
    assert entry["x-content"] == "markup"
    assert entry["x-upgrade"] is True
    assert entry["x-verbatim"] is True
    assert entry["x-example"] == (
        '<lf-risk-note id="risk-note"><strong>Risk note</strong> The retry budget '
        "is three attempts before manual review.</lf-risk-note>"
    )
    assert (package_root / "defaults.css").read_bytes() == b""
    module = (package_root / "widgets" / "lf-risk-note.js").read_text()
    checked = runner.invoke(cli_model.cli, ["package", "check", str(package)])
    assert checked.exit_code == 0, checked.output

    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "diagram",
            "--package",
            str(package),
            str(page),
        ],
    )
    assert initialized.exit_code == 0, initialized.output
    layer_4 = layer_record(page)
    assert layer_4 is not None
    widgets = selected(layer_4, page).directory_files["widgets"]
    assert widgets["lf-risk-note.js"].decode() == module
    (page / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-risk-note id="release-risk"><strong>Release risk'
            "</strong> The retry budget is three attempts before manual review."
            "</lf-risk-note>",
        )
    )
    result = check(page)
    assert result.exit_code == 0, result.output
    # Rendering owns a Playwright loop; a session browser may already own this
    # process's loop when the full suite reaches this CLI integration.
    rendered = subprocess.run(
        [*LEAF_COMMAND, "page", "check", str(page), "--render"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr


def test_package_writers_only_wait_for_contract_destinations_they_share(
    tmp_path, monkeypatch, spawn
):
    """An unrelated package proceeds while registry aliases and installs wait,
    even from environments with different state and temporary homes. Observe the
    real child lock's nonblocking refusal rather than infer waiting from a delay.
    """
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "package"
    packages_model.cmd_package_init(package)
    alias = tmp_path / "alias"
    alias.symlink_to(package, target_is_directory=True)
    registry_alias = tmp_path / "registry-alias"
    packages_model.cmd_package_init(registry_alias)
    (registry_alias / "registry.json").unlink()
    (registry_alias / "registry.json").symlink_to(package / "registry.json")
    (registry_alias / "widgets").rmdir()
    (registry_alias / "widgets").symlink_to(
        package / "widgets", target_is_directory=True
    )
    other_state = tmp_path / "other-state"
    other_tmp = tmp_path / "other-tmp"
    other_tmp.mkdir()
    environment = os.environ | {
        "XDG_STATE_HOME": str(other_state),
        "TMPDIR": str(other_tmp),
    }
    observe = """
import contextlib
import fcntl
import sys
from leaf import cli, packages
real_lock = packages.flocked
@contextlib.contextmanager
def observed(path):
    with open(path, "a+b") as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("waiting on shared destination", flush=True)
    with real_lock(path) as held:
        yield held
packages.flocked = observed
cli.cli.main(args=sys.argv[1:], standalone_mode=False)
"""
    routes = [package, alias, registry_alias]
    case_path = package.with_name(package.name.swapcase())
    if case_path.exists() and package.samefile(case_path):
        routes.append(case_path)
    for index, destination in enumerate(routes):
        widget = f"lf-parallel-{index}"
        with packages_model.package_write_lock(package):
            other = (
                package / "runtime" / "nested"
                if index == 0
                else tmp_path / f"other-{index}"
            )
            independent = subprocess.run(
                [*LEAF_COMMAND, "package", "init", str(other)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=STATED_TIMEOUT,
                check=False,
            )
            assert independent.returncode == 0, independent.stdout + independent.stderr
            child = spawn(
                [
                    sys.executable,
                    "-c",
                    observe,
                    "package",
                    "init",
                    str(destination),
                    "--widget",
                    widget,
                ],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert child.stdout.readline().strip() == "waiting on shared destination"
        out, err = child.communicate(timeout=STATED_TIMEOUT)
        assert child.returncode == 0, out + err
    assert set(json.loads((package / "registry.json").read_text())) == {
        f"lf-parallel-{index}" for index in range(len(routes))
    }

    for held_package in (
        package,
        other_state / "leaf" / "packages" / "locks" / package.name,
    ):
        with packages_model.package_write_lock(held_package):
            installing = spawn(
                [sys.executable, "-c", observe, "package", "install", str(package)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert (
                installing.stdout.readline().strip() == "waiting on shared destination"
            )
        out, err = installing.communicate(timeout=STATED_TIMEOUT)
        assert installing.returncode == 0, out + err


def test_package_is_the_unit_that_init_creates_checks_and_vendors(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output

    package = tmp_path / ".leaf"
    assert json.loads((package / "registry.json").read_text()) == {}
    assert (package / "overrides.css").is_file()
    assert list((package / "instructions").iterdir()) == []
    assert (package / "widgets").is_dir()
    assert (package / "vendor").is_dir()

    entry = add_test_widget(package, "lf-callout", upgrade=True)
    (package / "instructions" / "author.md").write_text(
        "# Callouts\n\nUse them for short notices.\n"
    )
    (package / "widgets" / "callout-format.js").write_text(
        'export const label = "Heads up";\n'
    )
    (package / "vendor" / "callout-schema.json").write_text('{"kind":"callout"}\n')

    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])
    assert checked.exit_code == 0, checked.output

    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
    )
    assert initialized.exit_code == 0, initialized.output
    layer_5 = layer_record(page)
    assert layer_5 is not None
    layer = selected(layer_5, page)
    # The package's widget rule reaches the page among its defaults, unscoped.
    theme = layer.top_files["theme.css"].decode()
    assert "lf-callout {\n  display: block;" in theme
    assert theme.index("lf-callout {") < theme.index("@layer lf-overrides")
    assert load_registry(page)["lf-callout"] == entry
    assert (
        "Use them for short notices."
        in layer.directory_files["instructions"]["author.md"].decode()
    )
    widgets = layer.directory_files["widgets"]
    assert "lf-callout.js" in widgets
    assert (
        widgets["callout-format.js"]
        == (package / "widgets" / "callout-format.js").read_bytes()
    )
    assert (
        layer.directory_files["vendor"]["callout-schema.json"]
        == (package / "vendor" / "callout-schema.json").read_bytes()
    )

    (page / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-callout id="custom-note">'
            "<strong>Heads up</strong> Custom project instructions."
            "</lf-callout>",
        )
    )
    result = check(page)
    assert result.exit_code == 0, result.output


def test_page_init_vendors_an_explicit_package_without_privileging_it(
    tmp_path, monkeypatch
):
    """A bundled vocabulary is selected and removed by the same ordinary layer path."""
    monkeypatch.chdir(tmp_path)
    plain = tmp_path / "plain"
    composed = tmp_path / "composed"
    runner = CliRunner()
    plain_result = runner.invoke(cli_model.cli, ["page", "init", str(plain)])
    packaged_result = runner.invoke(
        cli_model.cli,
        ["page", "init", "--package", "diagram", str(composed)],
    )
    assert plain_result.exit_code == 0, plain_result.output
    assert packaged_result.exit_code == 0, packaged_result.output
    plain_registry = load_registry(plain)
    packaged_registry = load_registry(composed)
    assert "lf-diagram" not in plain_registry
    assert "lf-activity" in plain_registry
    assert "lf-diagram" in packaged_registry
    assert plain_registry["$layer"]["packages"] == []
    assert packaged_registry["$layer"]["packages"] == ["diagram"]
    diagram = "widgets/lf-diagram.js"
    layer_6 = layer_record(plain)
    assert layer_6 is not None
    assert diagram not in layer_widgets(layer_6, plain)
    layer_7 = layer_record(composed)
    assert layer_7 is not None
    assert diagram in layer_widgets(layer_7, composed)
    revendor = runner.invoke(cli_model.cli, ["page", "init", str(composed)])
    assert revendor.exit_code == 0, revendor.output
    assert load_registry(composed)["$layer"]["packages"] == ["diagram"]
    layer_8 = layer_record(composed)
    assert layer_8 is not None
    assert diagram in layer_widgets(layer_8, composed)
    removed = runner.invoke(
        cli_model.cli, ["page", "init", "--no-packages", str(composed)]
    )
    assert removed.exit_code == 0, removed.output
    removed_registry = load_registry(composed)
    assert removed_registry["$layer"]["packages"] == []
    assert "lf-diagram" not in removed_registry
    layer_9 = layer_record(composed)
    assert layer_9 is not None
    assert diagram not in layer_widgets(layer_9, composed)


def _replying_after(page, server, edit):
    """Reply to a user comment after `edit` changes what the page's layer records,
    as a Leaf update leaves it, and return the command's result."""
    publish(page)
    code, response = fetch(
        f"{server}/api/event",
        data=json.dumps({"kind": "comment", "revision": 1, "text": "Hello"}).encode(),
    )
    assert code == 200, response
    woke = CliRunner().invoke(cli_model.cli, ["wait", str(page)])
    assert woke.exit_code == 0, woke.output
    envelope = json.loads(woke.output)
    delivery_model.receive(envelope, "s1")
    reference = envelope["batches"][0]["events"][0]["answer"]["ref"]
    edit(page)
    # A process of its own, as the agent's next command is, so it reads the page as
    # edited rather than as this one remembers it (`page_memory`).
    return subprocess.run(
        [*LEAF_COMMAND, "thread", "reply", reference, "--ephemeral", "--text", "Hi"],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )


def test_a_command_re_vendors_its_sessions_page_an_older_leaf_vendored(
    claimed, server, tmp_path
):
    """A reply through a reference names no page, so it is refused on a page an older
    Leaf vendored, naming the re-vendor. The session's next write naming the page
    makes that re-vendor itself (`vendoring.renew_layer`), restarting the server at
    its address, and the reply then goes."""
    replied = _replying_after(claimed, server, vendored_at_another_protocol)
    assert replied.returncode != 0, replied.stdout
    assert f"leaf page init {claimed}" in replied.stderr
    read = subprocess.run(
        [*LEAF_COMMAND, "page", "state", str(claimed)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert read.returncode == 0, read.stderr
    assert "page protocol" in json.loads(read.stdout)["source"]["error"]
    layer_10 = layer_record(claimed)
    assert layer_10 is not None
    before = layer_10["generation"]
    subprocess.run(
        [
            *LEAF_COMMAND,
            "page",
            "export",
            str(claimed),
            "--out",
            str(tmp_path / "export.html"),
        ],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    layer_11 = layer_record(claimed)
    assert layer_11 is not None
    assert layer_11["generation"] == before
    for command in (["page", "claim", str(claimed)], replied.args[len(LEAF_COMMAND) :]):
        ran = subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert ran.returncode == 0, ran.stderr
        assert "re-initialized" not in ran.stderr
        assert "older page protocol" not in ran.stderr
    assert fetch(f"{server}/api/state")[0] == 200
