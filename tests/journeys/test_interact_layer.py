"""CLI, plugin payload, layer, and customization tests."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND, hooks_run_this_tree
from interact_support import (
    COMMAND_HUB_PACKAGE,
    PAGE,
    STATED_TIMEOUT,
    add_test_widget,
    check,
    fetch,
    install_payload,
    page_packages,
    publish,
    vendored_at_another_protocol,
)
from model.test_interact_layer import PLAIN_PAGE, layer_files, layer_files_of_revision

from leaf.agents import delivery as delivery_model
from leaf.base import files as interact_files
from leaf.commands import cli as cli_model
from leaf.log import event_log as events_model
from leaf.pages import packages as packages_model
from leaf.records.revisioning import activate_source
from leaf.source import layer as layer_model
from leaf.source.layer import selected_layer
from leaf.source.registry.contract import stamp_grammars
from leaf.source.registry.storage import layer_record
from leaf.source.vocabulary import load_registry


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
        return selected_layer(layer_2, page)

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
                        "example": '<p class="hazard">Warning</p>',
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
        (
            ".hazard",
            {
                "inline": True,
            },
            "inline",
        ),
        (
            ".hazard",
            {
                "space": "wide",
            },
            "room",
        ),
        (".hazard::before", {}, "pseudo"),
        (".hazard[", {}, "invalid-selector-without-marks"),
        (
            ".hazard",
            {
                "example": "",
            },
            "empty-example",
        ),
        (
            ".hazard",
            {"example": '<p class="hazard">Warning</p>', "instructions": " "},
            "empty-instructions",
        ),
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
    theme = selected_layer(layer_3, page).top_files["theme.css"].decode()
    assert "lf-installed { color: purple; }" in theme
    (source / "overrides.css").write_text(".bad { color red; }\n")
    refused = runner.invoke(cli_model.cli, ["package", "install", str(source)])
    assert refused.exit_code != 0 and "syntax error" in refused.output
    assert layer_model.named_package(name) == current
    assert (
        current / "overrides.css"
    ).read_text() == "lf-installed { color: purple; }\n"


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
from leaf.commands import cli
from leaf.base import locations
real_lock = locations.flocked
@contextlib.contextmanager
def observed(path):
    with open(path, "a+b") as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("waiting on shared destination", flush=True)
    with real_lock(path) as held:
        yield held
locations.flocked = observed
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
    # Only the registry and the sheet a theme's or a widget's rules go in; the author
    # adds any other part of the layout when it has something to hold.
    assert sorted(path.name for path in package.iterdir()) == [
        "defaults.css",
        "registry.json",
    ]
    assert json.loads((package / "registry.json").read_text()) == {}

    entry = add_test_widget(package, "lf-callout", upgrade=True)
    (package / "overrides.css").write_text(".callout-note { font-weight: bold; }\n")
    (package / "instructions").mkdir()
    (package / "vendor").mkdir()
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
    layer = selected_layer(layer_5, page)
    # The package's widget rule reaches the page among its defaults, unscoped.
    theme = layer.top_files["theme.css"].decode()
    assert "lf-callout {\n  display: block;" in theme
    assert theme.index("lf-callout {") < theme.index("@layer lf-overrides")
    # The package's entry, as composition completes it.
    assert (
        load_registry(page)["lf-callout"]
        == stamp_grammars({"lf-callout": entry})["lf-callout"]
    )
    assert (
        "Use them for short notices."
        in layer.vocabulary.instructions["author.md"].decode()
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
        [
            *LEAF_COMMAND,
            "thread",
            "reply",
            reference,
            "--ephemeral",
            "--title",
            "Greeting",
            "--text",
            "Hi",
        ],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )


def test_a_command_re_vendors_its_sessions_page_an_older_leaf_vendored(
    claimed, server, tmp_path
):
    """A reply through a reference names no page, so it is refused on a page an older
    Leaf vendored, naming the re-vendor. Reads leave the layer as it was, `page
    state` refusing the page as at another page protocol. The session's next write
    naming the page makes that re-vendor itself (`vendoring.renew_layer`), restarting
    the server at its address, and the reply then goes."""
    replied = _replying_after(claimed, server, vendored_at_another_protocol)
    assert replied.returncode != 0, replied.stdout
    assert f"leaf page init {claimed}" in json.loads(replied.stdout)["error"]
    recorded = (claimed / schema_model.LAYER_FILE).read_bytes()
    read = subprocess.run(
        [*LEAF_COMMAND, "page", "state", str(claimed)],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert read.returncode != 0, read.stdout
    assert "page protocol" in read.stdout + read.stderr
    subprocess.run(
        [
            *LEAF_COMMAND,
            "page",
            "export",
            str(claimed),
            "--out",
            str(tmp_path / "export.html"),
            "--runtime",
        ],
        capture_output=True,
        text=True,
        timeout=STATED_TIMEOUT,
        check=False,
    )
    assert (claimed / schema_model.LAYER_FILE).read_bytes() == recorded
    for command in (["page", "claim", str(claimed)], replied.args[len(LEAF_COMMAND) :]):
        ran = subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
        )
        assert ran.returncode == 0, ran.stderr
        assert "re-initialized" not in ran.stdout + ran.stderr
        assert "older page protocol" not in ran.stdout + ran.stderr
    assert fetch(f"{server}/api/state")[0] == 200


import gc
import weakref

from leaf.base import page_memory
from leaf.base import schema as schema_model
from leaf.pages import vendoring as vendoring_model
from leaf.source import vocabulary as vocabulary_model
from leaf.source.registry import storage as registry_storage


def test_read_commands_leave_an_older_page_and_its_server_alone(claimed, server):
    """A read by another session cannot take a held page across a protocol bump."""
    publish(claimed)
    vendored_at_another_protocol(claimed)
    revisions = interact_files.list_revisions(claimed)
    recorded = (claimed / schema_model.LAYER_FILE).read_bytes()
    hooks_run_this_tree("s2")
    for command in (
        ["page", "state", str(claimed)],
        ["page", "events", str(claimed)],
        ["page", "instructions", str(claimed)],
        ["page", "check", str(claimed)],
    ):
        subprocess.run(
            [*LEAF_COMMAND, *command],
            capture_output=True,
            text=True,
            timeout=STATED_TIMEOUT,
            check=False,
            env={**os.environ, "CLAUDE_CODE_SESSION_ID": "s2"},
        )
        same_record = (claimed / schema_model.LAYER_FILE).read_bytes() == recorded
        assert same_record, command
        assert interact_files.list_revisions(claimed) == revisions
        assert fetch(f"{server}/api/state")[0] == 200
    assert vendoring_model.renew_layer(claimed, None) is None
    assert (claimed / schema_model.LAYER_FILE).read_bytes() == recorded


def test_package_check_and_page_init_refuse_an_upgraded_widget_without_its_module(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-unfinished")

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-unfinished"]["verbatim"] = True
    registry_path.write_text(json.dumps(registry))

    for args in (
        ["package", "check", ".leaf"],
        ["page", "init", "--package", "./.leaf", str(tmp_path / "page")],
    ):
        result = runner.invoke(cli_model.cli, args)
        assert result.exit_code != 0
        assert "widgets/lf-unfinished.js" in result.output


def test_package_install_makes_a_source_selectable_by_name(tmp_path, monkeypatch):
    """An installed package is a bundled one kept somewhere else.

    The store holds the package contract and none of the rest of the author's
    working directory, and the page reads the store rather than the source, which
    is gone by the time it is vendored.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    source = tmp_path / "src" / "callout"
    created = runner.invoke(cli_model.cli, ["package", "init", str(source)])
    assert created.exit_code == 0, created.output
    add_test_widget(source, "lf-callout", upgrade=True)
    (source / "README.md").write_text("How to work on this package.\n")
    (source / "spec").mkdir()
    (source / "spec" / "case.txt").write_text("the author's own test\n")

    installed = runner.invoke(cli_model.cli, ["package", "install", str(source)])

    assert installed.exit_code == 0, installed.output
    stored = Path(json.loads(installed.output)["package"])
    assert layer_model.named_package("callout") == stored
    assert sorted(path.name for path in stored.iterdir()) == [
        "defaults.css",
        "instructions",
        "registry.json",
        "runtime",
        "vendor",
        "widgets",
    ]

    shutil.rmtree(source)
    page = tmp_path / "page"
    vendored = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "callout", str(page)]
    )

    assert vendored.exit_code == 0, vendored.output
    registry = vocabulary_model.load_registry(page)
    assert registry["$layer"]["packages"] == ["callout"]
    assert "lf-callout" in registry
    assert "/widgets/lf-callout.js" in layer_files(page)


def test_package_init_widget_merges_an_existing_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf"
    initialized = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert initialized.exit_code == 0, initialized.output
    existing = add_test_widget(package, "lf-existing")
    instructions = package / "instructions" / "author.md"
    instructions.parent.mkdir()
    instructions.write_text("Keep this package instructions.\n")
    helper = package / "runtime" / "existing-helper.js"
    helper.parent.mkdir()
    helper.write_text("export const existing = true;\n")
    theme = (package / "defaults.css").read_bytes()

    result = runner.invoke(
        cli_model.cli,
        ["package", "init", ".leaf", "--widget", "lf-added-note"],
    )

    assert result.exit_code == 0, result.output
    registry = json.loads((package / "registry.json").read_text())
    assert registry["lf-existing"] == existing
    assert "lf-added-note" in registry
    # The package keeps the rules it had, and the starter's rule follows them.
    styles = (package / "defaults.css").read_bytes()
    assert styles.startswith(theme.rstrip())
    assert styles.endswith(packages_model.starter_widget_styles("lf-added-note"))
    assert instructions.read_text() == "Keep this package instructions.\n"
    assert helper.read_text() == "export const existing = true;\n"


def test_a_revision_reads_its_package_copy_after_the_selection_moves_on(
    tmp_path, monkeypatch
):
    """A saved version keeps the package it was written with: dropping the package
    from the selection leaves its copy for the revisions that name it, and an edit to
    the package reaches them at a new address, never under one a browser cached, and
    as a new generation, which an open document reloads on."""
    from leaf.source.revision_artifact import read_artifact
    from leaf.source.runtime_selection import execution_identity

    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom"
    (custom / "widgets").mkdir(parents=True)
    (custom / "widgets" / "helper.js").write_text("export const value = 1;\n")
    page = tmp_path / "page"
    init = ["page", "init", "--package", "./custom", str(page)]
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    (page / "index.html").write_text(PLAIN_PAGE)
    assert activate_source(page).error is None
    first = execution_identity(read_artifact(page, 1))
    layer_5 = registry_storage.layer_record(page)
    assert layer_5 is not None
    generation = layer_5["generation"]

    (custom / "widgets" / "helper.js").write_text("export const value = 2;\n")
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    assert execution_identity(read_artifact(page, 1)) != first
    layer_6 = registry_storage.layer_record(page)
    assert layer_6 is not None
    assert layer_6["generation"] != generation

    cleared = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--no-packages", str(page)]
    )
    assert cleared.exit_code == 0, cleared.output
    assert registry_storage.layer_packages(page) == []
    assert "/widgets/helper.js" in layer_files_of_revision(page, 1)


def test_package_instructions_do_not_change_a_revisions_browser_address(
    tmp_path, monkeypatch
):
    from leaf.source.revision_artifact import read_artifact
    from leaf.source.runtime_selection import executing

    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom"
    (custom / "instructions").mkdir(parents=True)
    (custom / "instructions" / "author.md").write_text("Initial instructions.\n")
    page = tmp_path / "page"
    init = ["page", "init", "--package", "./custom", str(page)]
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    (page / "index.html").write_text(PLAIN_PAGE)
    assert activate_source(page).error is None
    artifact = read_artifact(page, 1)
    record = json.loads(artifact.manifest)["layer"]
    first_layer = layer_model.selected_layer(record, page)
    first = executing(artifact)

    (custom / "instructions" / "author.md").write_text("Revised instructions.\n")
    assert CliRunner().invoke(cli_model.cli, init).exit_code == 0
    second_layer = layer_model.selected_layer(record, page)
    second = executing(artifact)

    assert second_layer.fingerprint != first_layer.fingerprint
    assert second.package_copies != first.package_copies
    assert second.resources == first.resources
    assert second.identity == first.identity


def test_a_layer_that_reads_a_pages_copy_lasts_as_long_as_the_pages_memory(
    tmp_path, monkeypatch
):
    """A layer that reads a page's own copy of a package is kept in the page's memory
    beside the copy's stamp (`layer._held`). Each `page init` that replaces the copy
    replaces that layer rather than keeping another beside it, so a process holds one
    layer for the page however often its package is edited, and none once it drops
    the page's memory. Forgetting the shared layers forgets it too."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "notes"
    package.mkdir()
    (package / "registry.json").write_text("{}")
    page = tmp_path / "page"
    kept = weakref.WeakSet()
    for edit in range(3):
        sheet = f".note {{ --edit: {edit}; }}"
        (package / "defaults.css").write_text(sheet + "\n")
        made = CliRunner().invoke(
            cli_model.cli, ["page", "init", "--package", "./notes", str(page)]
        )
        assert made.exit_code == 0, made.output
        record = registry_storage.layer_record(page)
        assert record is not None
        layer = layer_model.selected_layer(record, page)
        assert sheet in layer.files["/theme.css"].decode()
        kept.add(layer)
    del layer
    gc.collect()
    assert len(kept) == 1

    # A process that forgets the tree it read, as a preview does between servers
    # (`layer.forget_layers`), composes the page's layer again.
    [before] = kept
    layer_model.forget_layers()
    after = layer_model.selected_layer(record, page)
    assert after is not before
    kept.add(after)
    del before, after
    gc.collect()
    assert len(kept) == 1

    for n in range(page_memory.PageMemories.LIMIT):
        page_memory.memory_of(tmp_path / f"other-{n}")
    gc.collect()
    assert len(kept) == 0


def test_package_list_describes_each_selectable_package_in_its_own_words(tmp_path):
    """`package list` names what `page init --package NAME` selects: an installed
    package under a name of its own beside the bundled ones, described by the first
    paragraph of its author instructions and its entries' descriptions, and an
    installed package in place of the bundled one whose name it takes. `default`, on
    every page already, is not listed."""
    team = tmp_path / "src" / "team-charts"
    packages_model.cmd_package_init(team, ("lf-trend",))
    (team / "instructions").mkdir(exist_ok=True)
    (team / "instructions" / "author.md").write_text(
        "## When to select it\n\n"
        "Select this package for the analytics team's pages.\n"
        "It charts in their house style.\n\n"
        "Give every chart a label.\n"
    )
    diagram = tmp_path / "src" / "diagram"
    packages_model.cmd_package_init(diagram)
    for source in (team, diagram):
        installed = CliRunner().invoke(
            cli_model.cli, ["package", "install", str(source)]
        )
        assert installed.exit_code == 0, installed.output

    listed = CliRunner().invoke(cli_model.cli, ["package", "list"])

    assert listed.exit_code == 0, listed.output
    packages = {each["name"]: each for each in json.loads(listed.output)["packages"]}
    assert packages["team-charts"] == {
        "name": "team-charts",
        "installed": True,
        "description": "Select this package for the analytics team's pages. "
        "It charts in their house style.",
        "entries": {
            "lf-trend": packages_model.starter_element_declaration("lf-trend")[
                "description"
            ]
        },
    }
    assert packages["diagram"]["installed"] is True
    assert packages["diagram"]["entries"] == {}
    assert packages["playwright"]["installed"] is False
    assert "lf-trace" in packages["playwright"]["entries"]
    assert "default" not in packages
