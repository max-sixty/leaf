"""CLI, plugin payload, layer, and customization tests."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    PLUGIN_ROOT,
    ROOT,
    add_test_widget,
    case_alias,
    check,
    link_command_hub_package,
    record_claim,
    widget_entry,
)
from leaf import cli as cli_model
from leaf import events as events_model
from leaf import files as interact_files
from leaf import hooks as hooks_model
from leaf import layer as layer_model
from leaf import schema as schema_model
from leaf import service as service_model


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(
            ["--help"],
            """Usage: leaf [OPTIONS] COMMAND [ARGS]...

  Build and run interactive pages a session shares with its user.

Options:
  --help  Show this message and exit.

Commands:
  ack         Acknowledge one complete, untruncated wait batch.
  comment     Open an agent thread — on a passage, or on the page whole.
  data        Set or clear page-bound external data.
  edit        Edit one of this agent session's messages.
  events      Print the event log as JSON lines.
  package     Create and check packages.
  page        Create pages and add media.
  reply       Reply to a thread as the agent.
  report      Report a state change onto a page widget, as a worker.
  resolve     Close a thread as the agent.
  server      Start, run, or stop the local server.
  status      Set the agent's banner state.
  transcript  Print the page's exchange as Markdown.
  version     Check, publish, and export versions.
  wait        Print one page's unacknowledged events and reports, then exit.
""",
            id="root",
        ),
        pytest.param(
            ["data", "--help"],
            """Usage: leaf data [OPTIONS] COMMAND [ARGS]...

  Manage replaceable external or derived page data.

Options:
  --help  Show this message and exit.

Commands:
  clear  Remove one source snapshot.
  set    Replace one bound source value.
""",
            id="data",
        ),
        pytest.param(
            ["package", "--help"],
            """Usage: leaf package [OPTIONS] COMMAND [ARGS]...

  Create and check packages.

Options:
  --help  Show this message and exit.

Commands:
  check  Check a package as one unit.
  init   Create a package directory.
""",
            id="package",
        ),
        pytest.param(
            ["page", "--help"],
            """Usage: leaf page [OPTIONS] COMMAND [ARGS]...

  Create pages and add media.

Options:
  --help  Show this message and exit.

Commands:
  catalog   Print the widget and theme vocabulary.
  guidance  List or print composed guidance by audience.
  init      Create or re-vendor a page directory.
  media     Add images and print their page paths.
  state     Print where the page stands, as JSON.
""",
            id="page",
        ),
        pytest.param(
            ["version", "--help"],
            """Usage: leaf version [OPTIONS] COMMAND [ARGS]...

  Check, publish, and export versions.

Options:
  --help  Show this message and exit.

Commands:
  check    Check a page version.
  export   Export a published version to one HTML file.
  publish  Publish a checked version with a changelog.
""",
            id="version",
        ),
        pytest.param(
            ["server", "--help"],
            """Usage: leaf server [OPTIONS] COMMAND [ARGS]...

  Start, run, or stop the local server.

Options:
  --help  Show this message and exit.

Commands:
  run    Serve a page in the foreground until stopped.
  start  Start a page's server and print its URL.
  stop   Stop a page's server.
""",
            id="server",
        ),
    ],
)
def test_cli_help_groups_commands_with_complete_summaries(args, expected):
    result = CliRunner().invoke(
        cli_model.cli,
        args,
        prog_name="leaf",
        terminal_width=80,
    )

    assert result.exit_code == 0
    assert result.output == expected


@pytest.mark.parametrize("command", ["wait", "ack"])
def test_wait_and_ack_help_require_a_complete_batch(command):
    result = CliRunner().invoke(
        cli_model.cli,
        [command, "--help"],
        terminal_width=200,
    )

    assert result.exit_code == 0
    assert "--forward" not in result.output
    assert " ".join(schema_model.ACK_BATCH_INSTRUCTION.split()) in " ".join(
        result.output.split()
    )


def test_the_skill_routes_every_reference_it_ships():
    """A reference SKILL.md never links is a file no session opens.

    The set comes from the directory rather than a list here, because a list is the
    second copy: adding a reference and forgetting to route it would leave it green.
    """
    root = PLUGIN_ROOT / "skills" / "leaf"
    skill = (root / "SKILL.md").read_text()
    references = sorted((root / "references").rglob("*.md"))

    assert references, "no references read — an empty set routes itself"
    for path in references:
        relative = path.relative_to(root).as_posix()
        assert relative in skill, relative


def test_hidden_hook_remains_callable():
    result = CliRunner().invoke(cli_model.cli, ["hook"], input="{}")

    assert result.exit_code == 0
    assert result.output == ""


def test_init_help_names_the_version_file_layout():
    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--help"],
        prog_name="leaf",
        terminal_width=80,
    )

    assert result.exit_code == 0
    assert "Creates PAGE/versions/ for authored vN.html files" in result.output
    assert "--package" in result.output


@pytest.mark.parametrize(
    ("args", "needs_playwright"),
    [
        (["version", "check", "page", "--render"], True),
        (["version", "export", "page", "-o", "export"], True),
        (["version", "check", "export"], False),
        (["reply", "page", "--to", "c1", "--text", "export"], False),
    ],
)
def test_shim_adds_playwright_only_for_browser_commands(
    tmp_path, monkeypatch, args, needs_playwright
):
    fake_uv = tmp_path / "uv"
    fake_uv.write_text(
        '#!/bin/sh\nfor cli_arg in "$@"; do\n  printf "%s\\n" "$cli_arg"\ndone\n'
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    shim = PLUGIN_ROOT / "bin" / "leaf"

    result = subprocess.run(
        [shim, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    dispatched = result.stdout.splitlines()
    script_at = next(
        i for i, arg in enumerate(dispatched) if arg.endswith("interact.py")
    )

    assert result.returncode == 0, result.stderr
    # Everything before the script path is uv's, and this states the whole of it
    # rather than that some flag appears somewhere in it: an index named here
    # would take back the host's say as surely as a lock would.
    assert dispatched[1:script_at] == (
        ["--with", "playwright>=1.49"] if needs_playwright else ["-q"]
    )


def test_claude_and_codex_load_the_same_plugin_payload():
    claude_marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text()
    )
    codex_marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    claude_manifest = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
    )
    codex_manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text()
    )

    assert claude_marketplace["plugins"][0]["source"] == "./plugins/leaf"
    assert codex_marketplace["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/leaf",
    }
    assert codex_marketplace["plugins"][0]["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert claude_manifest["name"] == codex_manifest["name"] == "leaf"
    assert "version" not in claude_manifest
    assert "version" not in codex_manifest
    for relative in [
        "bin/leaf",
        "hooks/hooks.json",
        "hooks/scripts/loop-guard.py",
        "skills/leaf/SKILL.md",
        "skills/leaf/references/codex-watcher.md",
        "skills/leaf/references/conversation-loop.md",
        "skills/leaf/references/packages.md",
        "skills/leaf/references/page-authoring.md",
        "skills/leaf/references/serving-pages.md",
        "skills/leaf/packages/default/registry.json",
        "skills/leaf/scripts/interact.py",
    ]:
        assert (PLUGIN_ROOT / relative).is_file()
    assert not [path for path in PLUGIN_ROOT.rglob("*") if path.is_symlink()]
    # Shipping a lock would take the client's own index out of the loop, per the
    # root `CLAUDE.md`. The nightly test below proves that against a real index;
    # this is the half every run sees.
    assert not list(PLUGIN_ROOT.rglob("*.lock"))


def test_an_installed_payload_is_complete_and_launches_outside_the_checkout(tmp_path):
    installed = tmp_path / "host" / "plugins" / "leaf"
    shutil.copytree(PLUGIN_ROOT, installed)

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
        [launcher, "page", "init", page],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_result.returncode == 0, init_result.stderr
    (page / "versions" / "v1.html").write_text(PAGE)
    publish_result = subprocess.run(
        [
            launcher,
            "version",
            "publish",
            page,
            "--version",
            "1",
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


@pytest.mark.nightly  # the resolve asks the host's index for the header
def test_the_launcher_resolves_through_the_hosts_own_index(tmp_path):
    """The index a host configures is the only place leaf may look for its
    dependencies, and resolving the PEP 723 header is the only way it gets a
    wheel.

    Both halves need a cache directory of their own, because a wheel already in
    the developer's cache answers before any index is consulted and the run would
    prove nothing. A cold resolve is also the one moment uv has an install summary
    to print, so it is where `bin/leaf`'s `-q` can be held to the silent stderr an
    agent reads back.

    The second half stands a closed port in for a private mirror, which is enough
    to say which index was asked: the run must fail naming that port, and a
    pypi.org URL anywhere in the output would mean something still had a way
    around it. It declines the developer's own index settings, in their
    environment and in their `uv.toml` alike, since either would serve the run and
    read as leaf ignoring the port it was pointed at."""
    installed = tmp_path / "plugins" / "leaf"
    shutil.copytree(PLUGIN_ROOT, installed)

    unconfigured = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("UV_INDEX")
        and name not in {"UV_DEFAULT_INDEX", "UV_FIND_LINKS", "UV_NO_INDEX"}
    }

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

    mirrored = subprocess.run(
        [installed / "bin" / "leaf", "--help"],
        cwd=tmp_path,
        env={
            **unconfigured,
            "UV_CACHE_DIR": str(tmp_path / "mirror-cache"),
            "UV_DEFAULT_INDEX": "http://127.0.0.1:1/simple",
            "UV_NO_CONFIG": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    output = mirrored.stdout + mirrored.stderr
    assert mirrored.returncode != 0, output
    assert "127.0.0.1:1" in output, output
    assert "pypi.org" not in output and "pythonhosted.org" not in output, output


def test_init_vendors_the_layer(page_dir):
    for name in ["leaf.js", "theme.css", "registry.json"]:
        assert (page_dir / name).is_file()
    assert (page_dir / "runtime" / "widget-api.js").is_file()
    assert (page_dir / "widgets" / "lf-tabs.js").is_file()
    assert (page_dir / "widgets" / "lf-chart.js").is_file()
    assert (page_dir / "widgets" / "lf-diagram.js").is_file()
    assert (page_dir / "vendor" / "mermaid.min.js").is_file()
    assert (page_dir / "vendor" / "plot.esm.js").is_file()


def test_init_composes_and_prunes_nested_browser_modules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "package"
    module = package / "runtime" / "nested-package" / "fold" / "model.js"
    module.parent.mkdir(parents=True)
    module.write_text("export const model = 'package';\n")
    page = tmp_path / "page"
    runner = CliRunner()

    initialized = runner.invoke(
        cli_model.cli, ["page", "init", "--package", "package", str(page)]
    )

    assert initialized.exit_code == 0, initialized.output
    assert (page / "runtime" / "nested-package" / "fold" / "model.js").read_text() == (
        "export const model = 'package';\n"
    )
    assert schema_model.SERVED_PATH.fullmatch("/runtime/nested-package/fold/model.js")
    assert not schema_model.SERVED_PATH.fullmatch("/vendor/../../status.json")
    assert not schema_model.SERVED_PATH.fullmatch("/vendor/../leaf.js")

    module.unlink()
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert initialized.exit_code == 0, initialized.output
    assert not (page / "runtime" / "nested-package").exists()


@pytest.mark.parametrize("nested_first", [False, True])
def test_init_refuses_composed_file_directory_collisions_before_writing(
    tmp_path, monkeypatch, nested_first
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    flat = tmp_path / "flat" / "vendor" / "cache"
    flat.parent.mkdir(parents=True)
    flat.write_text("flat")
    nested = tmp_path / "nested" / "vendor" / "cache" / "chunk.js"
    nested.parent.mkdir(parents=True)
    nested.write_text("nested")
    packages = ["nested", "flat"] if nested_first else ["flat", "nested"]

    result = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            *(arg for package in packages for arg in ("--package", package)),
            str(page),
        ],
    )

    assert result.exit_code != 0
    assert "as a file and" in result.output
    assert "vendor/cache" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_an_intermediate_symlink_before_writing_nested_modules(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    package_module = (
        tmp_path / "package" / "runtime" / "nested-package" / "fold" / "model.js"
    )
    package_module.parent.mkdir(parents=True)
    package_module.write_text("export const model = true;\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (page / "runtime" / "nested-package").symlink_to(outside, target_is_directory=True)

    result = runner.invoke(
        cli_model.cli,
        ["page", "init", "--package", "package", str(page)],
    )

    assert result.exit_code != 0
    assert "must be a real directory, not a symlink" in result.output
    assert list(outside.iterdir()) == []


def test_init_refuses_case_aliased_file_directory_collisions_before_writing(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    flat = tmp_path / "flat" / "vendor" / "Cache"
    flat.parent.mkdir(parents=True)
    flat.write_text("flat")
    nested = tmp_path / "nested" / "vendor" / "cache" / "chunk.js"
    nested.parent.mkdir(parents=True)
    nested.write_text("nested")
    location = layer_model._path_location

    def case_insensitive(path):
        found = location(path)
        return found._replace(tail=tuple(part.casefold() for part in found.tail))

    monkeypatch.setattr(layer_model, "_path_location", case_insensitive)

    result = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "flat",
            "--package",
            "nested",
            str(page),
        ],
    )

    assert result.exit_code != 0
    assert "as a file and" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_behavior_modules_use_the_widget_api_boundary():
    modules = [
        *(PLUGIN_ROOT / "assets" / "widgets").glob("*.js"),
        *(PLUGIN_ROOT / "packages").glob("*/widgets/*.js"),
        *(ROOT / "examples" / "packages").glob("*/widgets/*.js"),
    ]
    assert modules
    for module in modules:
        source = module.read_text()
        specifiers = [
            match[1]
            for match in re.findall(
                r"""(?:from\s+|import\s*(?:\(\s*)?)(["'])(/[^"']+)\1""",
                source,
            )
        ]
        assert "/leaf.js" not in specifiers, module
        private_imports = [
            specifier
            for specifier in specifiers
            if specifier.startswith("/runtime/")
            and specifier != "/runtime/widget-api.js"
        ]
        assert private_imports == [], (
            f"{module} imports private runtime owners: {private_imports}"
        )


def test_every_test_runs_against_a_throwaway_config_and_state(tmp_path_factory):
    """What `isolated_session` promises, asserted where a test would see a break.
    The two homes are the only thing leaf reads from the developer's own, and a
    suite that reached theirs fails silently in both directions: it would vendor
    their overlay into fixtures that never say what a theme should contain, and
    register a dozen throwaway pages a run in the state home the loop guard reads,
    for pages nobody has. Every other test here sets whichever home it is about,
    so none of them would notice. What a fixture sees before the isolation is up
    is a different question; `test_a_run_ends_only_the_servers_it_started` asks
    it."""
    root = tmp_path_factory.getbasetemp()
    assert service_model.config_home().is_relative_to(root)
    assert service_model.state_home().is_relative_to(root)


def test_init_user_layer_applies(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".config" / "leaf" / "widgets").mkdir(parents=True)
    custom_theme = ":root { --accent: teal }\n"
    (home / ".config" / "leaf" / "theme.css").write_text(custom_theme)
    (home / ".config" / "leaf" / "widgets" / "lf-foo.js").write_text("// user widget")
    # The ~/.config fallback, which is the path a machine with no XDG_CONFIG_HOME
    # set takes — so the variable the fixtures isolate with has to come back off.
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "page"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(d)])
    assert result.exit_code == 0, result.output
    vendored_theme = (d / "theme.css").read_text()
    assert vendored_theme.startswith((schema_model.ASSETS / "theme.css").read_text())
    assert vendored_theme.endswith(custom_theme)
    assert (d / "widgets" / "lf-foo.js").read_text() == "// user widget"
    assert (d / "widgets" / "lf-tabs.js").is_file()  # shipped modules still vendored
    assert (d / "runtime" / "chrome-style.js").is_file()


def test_init_project_layer_wins(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    (project / ".leaf").mkdir(parents=True)
    custom_theme = ":root { --accent: red }\n"
    (project / ".leaf" / "theme.css").write_text(custom_theme)
    monkeypatch.chdir(project)
    d = tmp_path / "page"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(d)])
    assert result.exit_code == 0, result.output
    theme = (d / "theme.css").read_text()
    assert theme.startswith((schema_model.ASSETS / "theme.css").read_text())
    assert theme.endswith(custom_theme)
    # Files the project layer doesn't override still come from the shipped defaults.
    assert (d / "registry.json").is_file()


def test_init_refuses_a_layer_theme_that_leaves_a_block_open(tmp_path, monkeypatch):
    """The CSS parser auto-closes a block left open at end of file, so tinycss2
    reports nothing — but layer stylesheets concatenate, and an unclosed block
    swallows every later layer's rules into its own scope. The shipped split hit
    exactly this: a cut that dropped one closing brace nested the whole standard
    layer inside a min-width media query, and the only symptom was print styles
    quietly not applying. The gate names the file while the author is still in
    front of it."""
    project = tmp_path / "proj"
    (project / ".leaf").mkdir(parents=True)
    (project / ".leaf" / "theme.css").write_text(
        "@media screen and (min-width: 900px) {\n  :root { --accent: red }\n"
    )
    monkeypatch.chdir(project)
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(tmp_path / "page")])
    assert result.exit_code == 1
    assert "block(s) left open at end of file" in result.output
    assert "theme.css" in result.output


def test_init_merges_registry_layers_by_complete_entry(tmp_path, monkeypatch):
    """A custom widget adds one entry; it need not fork the shipped vocabulary.

    Precedence still belongs to the later layer, but at the entry boundary: the
    project entry replaces the user's whole schema rather than inheriting stale
    fields from it.
    """
    user = tmp_path / "config" / "leaf"
    project = tmp_path / "project"
    project_layer = project / ".leaf"
    user.mkdir(parents=True)
    project_layer.mkdir(parents=True)
    user_entry = {
        "description": "user shape",
        "type": "object",
        "properties": {"user-only": {"type": "string"}},
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": False,
    }
    project_entry = {
        "description": "project shape",
        "type": "object",
        "properties": {"project-only": {"type": "string"}},
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": False,
    }
    project_only = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "x-content": "none",
        "x-upgrade": False,
    }
    (user / "registry.json").write_text(json.dumps({"lf-local": user_entry}))
    (project_layer / "registry.json").write_text(
        json.dumps({"lf-local": project_entry, "lf-project-only": project_only})
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)

    page = tmp_path / "page"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    registry = json.loads((page / "registry.json").read_text())
    assert registry["lf-local"] == project_entry
    assert registry["lf-project-only"] == project_only
    assert "lf-options" in registry and "$events" in registry


def test_init_merges_dollar_entries_by_member(tmp_path, monkeypatch):
    """A project idiom joins the shipped catalog; a restated one replaces its member.

    $ entries merge one level deep. Under replace-whole, the first project layer
    to declare an idiom vendored a $idioms holding only its own: the shipped
    idioms' CSS kept styling (theme files concatenate), while `page catalog`
    stopped documenting them — a silent wipe of everything the layer didn't
    restate.
    """
    project = tmp_path / "proj"
    layer = project / ".leaf"
    layer.mkdir(parents=True)
    hazard = {
        "description": "A tinted aside for operational hazards.",
        "example": '<aside class="hazard">Deploys freeze Friday.</aside>',
    }
    lede = {"description": "project lede", "example": '<p class="lede">…</p>'}
    (layer / "registry.json").write_text(
        json.dumps(
            {
                "$idioms": {".hazard": hazard, ".lede": lede},
                # A map member merges by its own keys — the same wipe one level
                # down: declaring one extension must not drop the shipped map.
                "$languages": {"paths": {"svelte": "javascript"}},
            }
        )
    )
    monkeypatch.chdir(project)

    page = tmp_path / "page"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    idioms = json.loads((page / "registry.json").read_text())["$idioms"]
    shipped = json.loads((schema_model.ASSETS / "registry.json").read_text())["$idioms"]
    assert idioms[".hazard"] == hazard
    assert idioms[".lede"] == lede
    assert idioms["description"] == shipped["description"]
    assert set(shipped) <= set(idioms)
    languages = json.loads((page / "registry.json").read_text())["$languages"]
    shipped_langs = json.loads((schema_model.ASSETS / "registry.json").read_text())[
        "$languages"
    ]
    assert languages["paths"]["svelte"] == "javascript"
    assert set(shipped_langs["paths"]) <= set(languages["paths"])
    assert languages["names"] == shipped_langs["names"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX umask and mode semantics")
def test_staged_writes_honor_umask_without_copying_a_replaced_symlink_mode(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    old_umask = os.umask(0o077)
    try:
        customized = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    finally:
        os.umask(old_umask)
    assert customized.exit_code == 0, customized.output
    custom_theme = tmp_path / ".leaf" / "theme.css"
    assert custom_theme.stat().st_mode & 0o777 == 0o600

    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    external = tmp_path / "external-theme.css"
    external.write_text("external")
    external.chmod(0o600)
    (page / "theme.css").unlink()
    (page / "theme.css").symlink_to(external)
    old_umask = os.umask(0o022)
    try:
        revendored = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    finally:
        os.umask(old_umask)

    assert revendored.exit_code == 0, revendored.output
    assert not (page / "theme.css").is_symlink()
    assert (page / "theme.css").stat().st_mode & 0o777 == 0o644
    assert external.read_text() == "external"


def test_path_case_policy_matches_the_filesystem(tmp_path):
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    alias_resolves = (tmp_path / "cASEpROBE").exists()

    assert interact_files._filesystem_case_sensitive(tmp_path) is not alias_resolves


def test_path_overlap_respects_case_sensitive_future_names(tmp_path, monkeypatch):
    upper = tmp_path / "FutureScope"
    lower = tmp_path / "fUTUREsCOPE"
    monkeypatch.setattr(interact_files, "_filesystem_case_sensitive", lambda path: True)
    assert not interact_files.locations_overlap(
        interact_files._path_location(upper), interact_files._path_location(lower)
    )

    monkeypatch.setattr(
        interact_files, "_filesystem_case_sensitive", lambda path: False
    )
    assert interact_files.paths_same(upper, lower)


@pytest.mark.parametrize(
    "name",
    (
        "comments.jsonl",
        "status.json",
        "waiter.lock",
        "cursor.json",
        "service.json",
        "server.lock",
    ),
)
def test_initialized_page_owns_runtime_state_paths(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    assert layer_model.initialized_page_owning(page / name) == page
    assert layer_model.initialized_page_owning(page / ".leaf" / name) is None


@pytest.mark.parametrize(
    "directory", ("versions", "runtime", "widgets", "vendor", "media")
)
def test_initialized_page_owns_declared_directory_trees(
    tmp_path, monkeypatch, directory
):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    assert layer_model.initialized_page_owning(page / directory / "future") == page


def test_replace_files_rejects_case_aliased_future_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        interact_files, "_filesystem_case_sensitive", lambda path: False
    )
    first = tmp_path / "Result.css"
    second = tmp_path / "rESULT.CSS"

    with pytest.raises(SystemExit, match="resolve to the same target"):
        interact_files.replace_files(
            [(first, b"first", False), (second, b"second", False)]
        )

    assert not first.exists() and not second.exists()


def test_init_refuses_case_aliased_layer_scopes(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(alias / ".LEAF"))
    monkeypatch.chdir(project)
    user_layer = alias / ".LEAF" / "leaf"
    user_layer.mkdir(parents=True)
    theme = user_layer / "theme.css"
    theme.write_text(":root { --accent: teal; }\n")
    before = theme.read_bytes()
    page = tmp_path / "page"

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "package scopes must be separate" in result.output
    assert theme.read_bytes() == before
    assert not page.exists()


def test_init_reads_the_complete_layer_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "registry.json").write_text(
        json.dumps({"lf-bad-theme": widget_entry("lf-bad-theme")})
    )
    (layer / "theme.css").write_bytes(b"\xff")

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "theme.css must be UTF-8" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_a_rejected_init_leaves_a_precreated_directory_empty(tmp_path, monkeypatch):
    """A directory the caller prepared is not page state until init succeeds."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "prepared-page"
    page.mkdir()
    layer = tmp_path / ".leaf"
    layer.mkdir()
    (layer / "theme.css").write_text(".bad { color red; }\n")

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "theme.css syntax error" in result.output
    assert list(page.iterdir()) == []


def test_page_commands_do_not_mint_the_successful_init_marker(tmp_path):
    """An existing directory becomes a page only through a completed page init."""
    page = tmp_path / "prepared-page"
    page.mkdir()

    result = CliRunner().invoke(cli_model.cli, ["server", "stop", str(page)])

    assert result.exit_code != 0
    assert "page init" in result.output
    assert list(page.iterdir()) == []


def test_hooks_do_not_mint_the_successful_init_marker_for_a_deleted_page(page_dir):
    """An external claim does not turn a deleted page back into initialized state."""
    record_claim(page_dir, id="stale-session")
    shutil.rmtree(page_dir)
    page_dir.mkdir()

    hooks_model.cmd_hook({"hook_event_name": "Stop", "session_id": "stale-session"})

    assert list(page_dir.iterdir()) == []


def test_a_failed_fresh_commit_does_not_mark_the_page_initialized(
    tmp_path, monkeypatch
):
    """The stable log marks a completed init, not one that failed while committing."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "interrupted-page"
    original_replace_files = layer_model.replace_files

    def fail_layer_commit(files):
        if any(path.name == "registry.json" for path, _, _ in files):
            raise OSError("layer commit failed")
        return original_replace_files(files)

    monkeypatch.setattr(layer_model, "replace_files", fail_layer_commit)

    with pytest.raises(OSError, match="layer commit failed"):
        layer_model.cmd_init(page)

    assert not (page / "comments.jsonl").exists()


def test_init_refuses_malformed_layer_css_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    theme = tmp_path / ".leaf" / "theme.css"
    theme.parent.mkdir(parents=True)
    theme.write_text(".bad { color red; }\n")

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert f"{theme} syntax error" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_does_not_partially_revendor_on_a_destination_conflict(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    theme_before = (page / "theme.css").read_bytes()
    registry_before = (page / "registry.json").read_bytes()

    conflict = page / "widgets" / "lf-tabs.js"
    conflict.unlink()
    conflict.mkdir()
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").write_text(":root { --accent: rebeccapurple; }\n")
    (layer / "registry.json").write_text(
        json.dumps({"lf-new-shape": widget_entry("lf-new-shape")})
    )

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    # Named, not merely refused. `page init` has a dozen ways to stop, and the layer
    # staged above is enough to trip several of them, so an exit code alone says only
    # that something went wrong — delete the destination check and one of the others
    # fails the command in its place, leaving this green with its subject gone. The tail
    # of the message rather than the whole path: the CLI resolves the directory, and on
    # a mac that is the /private prefix the fixture's own path doesn't carry.
    assert "lf-tabs.js must be a file" in result.output
    assert (page / "theme.css").read_bytes() == theme_before
    assert (page / "registry.json").read_bytes() == registry_before


@pytest.mark.parametrize("sub", ["versions", "runtime", "widgets", "vendor"])
def test_init_refuses_a_symlinked_page_directory(tmp_path, monkeypatch, sub):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    original = tmp_path / f"original-{sub}"
    (page / sub).rename(original)
    outside = tmp_path / f"outside-{sub}"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("do not prune or replace files outside the page")
    (page / sub).symlink_to(outside, target_is_directory=True)

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "must be a real directory, not a symlink" in result.output
    assert sentinel.read_text() == "do not prune or replace files outside the page"
    assert list(outside.iterdir()) == [sentinel]


@pytest.mark.parametrize(
    ("source_relative", "destination_relative"),
    [("vendor", "widgets"), ("theme.css", "registry.json")],
)
def test_init_refuses_a_layer_source_aliased_to_a_page_destination(
    tmp_path, monkeypatch, source_relative, destination_relative
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    destination = page / destination_relative
    if destination.is_dir():
        (destination / "keep-source.txt").write_text(
            "stale pruning must not delete a package"
        )

    source = tmp_path / ".leaf" / source_relative
    source.parent.mkdir(parents=True)
    source.symlink_to(destination, target_is_directory=destination.is_dir())
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "overlaps page destination" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_a_case_aliased_source_at_a_page_destination(
    tmp_path, monkeypatch
):
    project = tmp_path / "Project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "MixedCasePage"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    alias = case_alias(page)
    target = alias / "THEME.CSS"
    assert target.samefile(page / "theme.css")
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    layer_theme = project / ".leaf" / "theme.css"
    layer_theme.parent.mkdir(parents=True)
    layer_theme.symlink_to(target)

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "overlaps page destination" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_preserves_tmp_files_even_when_a_layer_reads_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    source = page / f"theme.css.{os.getpid()}.0.tmp"
    source.write_text(":root { --accent: rebeccapurple; }\n")
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").symlink_to(source)

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    assert source.read_text() == ":root { --accent: rebeccapurple; }\n"
    assert (layer / "theme.css").is_symlink()


@pytest.mark.parametrize(
    ("example", "message"),
    [
        (
            '<lf-toned-note id="repeat"><p id="repeat">Two</p></lf-toned-note>',
            "duplicate ids",
        ),
        (
            '<lf-toned-note id="lf-example">One</lf-toned-note>',
            "lf- namespace",
        ),
    ],
    ids=["duplicate", "reserved"],
)
def test_init_refuses_invalid_ids_in_a_registry_example(
    tmp_path, monkeypatch, example, message
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-toned-note")
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-toned-note"]["x-example"] = example
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(cli_model.cli, ["page", "init", str(tmp_path / "page")])

    assert result.exit_code != 0
    assert "<lf-toned-note> x-example is invalid" in result.output
    assert message in result.output


def test_revendoring_removes_files_the_layer_retired(page_dir):
    stale = page_dir / "widgets" / "lf-retired.js"
    stale.write_text("// no longer in any layer")
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])
    assert result.exit_code == 0, result.output
    assert not stale.exists()


@pytest.mark.parametrize(
    ("sub", "name"),
    [("widgets", "lf-returned.js"), ("vendor", "returned.js")],
)
def test_revendoring_removes_stale_broken_links_before_a_file_returns(
    page_dir, sub, name
):
    stale = page_dir / sub / name
    stale.symlink_to(page_dir.parent / "missing-target")

    retired = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert retired.exit_code == 0, retired.output
    assert not stale.is_symlink()

    source = page_dir.parent / ".leaf" / sub / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("// returned\n")
    returned = CliRunner().invoke(cli_model.cli, ["page", "init", str(page_dir)])

    assert returned.exit_code == 0, returned.output
    assert stale.is_file() and not stale.is_symlink()
    assert stale.read_text() == "// returned\n"
    assert source.read_text() == "// returned\n"


def test_explicit_package_order_is_registry_file_and_theme_precedence(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    for name in ("first", "second"):
        package = tmp_path / name
        (package / "widgets").mkdir(parents=True)
        entry = widget_entry("lf-shared")
        entry["description"] = name
        (package / "registry.json").write_text(json.dumps({"lf-shared": entry}))
        (package / "theme.css").write_text(f"/* package {name} */\n")
        (package / "widgets" / "shared.js").write_text(f"// {name}\n")

    page = tmp_path / "page"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "first",
            "--package",
            "second",
            str(page),
        ],
    )

    assert result.exit_code == 0, result.output
    registry = json.loads((page / "registry.json").read_text())
    assert registry["$layer"]["packages"] == ["first", "second"]
    assert registry["lf-shared"]["description"] == "second"
    assert (page / "widgets" / "shared.js").read_text() == "// second\n"
    theme = (page / "theme.css").read_text()
    assert theme.index("package first") < theme.index("package second")


def test_init_refuses_a_case_aliased_page_inside_a_package(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    layer = project / ".leaf"
    page = alias / ".LEAF" / "WIDGETS"
    assert page.samefile(layer / "widgets")
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_non_utf8_package_guidance_before_revendoring(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    package = tmp_path / ".leaf" / "guidance"
    package.mkdir(parents=True)
    source = package / "author.md"
    source.write_text("# Project author\n")
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = (page / "guidance" / "author.md").read_bytes()

    source.write_bytes(b"\xff")

    result = runner.invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "guidance/author.md must be UTF-8" in result.output
    assert (page / "guidance" / "author.md").read_bytes() == before


def test_init_refuses_a_noncanonical_guidance_audience(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    guidance = tmp_path / ".leaf" / "guidance"
    guidance.mkdir(parents=True)
    malformed = guidance / "Project Lead.md"
    malformed.write_text("Use the project package.\n")
    page = tmp_path / "page"

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert f"{malformed} must be named <audience>.md" in result.output
    assert not page.exists()


def test_init_refuses_overlapping_package_scopes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    user = config / "leaf"
    user.mkdir(parents=True)
    (user / "theme.css").write_text(":root { --accent: teal; }\n")
    project_layer = project / ".leaf"
    project_layer.symlink_to(user, target_is_directory=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    before = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    page = tmp_path / "page"

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "package scopes must be separate" in result.output
    after = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not page.exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_init_refuses_to_overwrite_a_package(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    runner = CliRunner()
    package = config / "leaf" if user else project / ".leaf"
    created = runner.invoke(cli_model.cli, ["package", "init", str(package)])
    assert created.exit_code == 0, created.output

    layer = package
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert before

    result = runner.invoke(cli_model.cli, ["page", "init", str(layer)])

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_to_write_inside_a_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    layer = tmp_path / ".leaf"
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(cli_model.cli, ["page", "init", str(layer / "widgets")])

    assert result.exit_code != 0
    assert "inside package" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    ("relative", "directory"),
    [
        ("theme.css", True),
        ("registry.json", True),
        ("guidance", False),
        ("widgets", False),
        ("vendor", False),
    ],
)
def test_init_refuses_wrong_kind_package_paths(
    tmp_path, monkeypatch, relative, directory
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".leaf" / relative
    path.parent.mkdir(parents=True)
    if directory:
        path.mkdir()
    else:
        path.write_text("not a directory")

    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(tmp_path / "page")])

    assert result.exit_code != 0
    assert str(path) in result.output


def test_package_allows_a_symlink_managed_external_layer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    managed = tmp_path / "managed"
    widgets = managed / "widgets"
    widgets.mkdir(parents=True)
    theme = managed / "theme.css"
    theme.write_text(":root { --accent: teal; }\n")
    registry = managed / "registry.json"
    registry.write_text("{}\n")
    (layer / "theme.css").symlink_to(theme)
    (layer / "registry.json").symlink_to(registry)
    (layer / "widgets").symlink_to(widgets, target_is_directory=True)

    runner = CliRunner()
    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code == 0, result.output
    assert (layer / "theme.css").is_symlink()
    assert (layer / "registry.json").is_symlink()
    assert (layer / "widgets").is_symlink()
    assert theme.read_text() == ":root { --accent: teal; }\n"
    assert json.loads(registry.read_text()) == {}
    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])
    assert checked.exit_code == 0, checked.output


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
    registry["lf-unfinished"]["x-upgrade"] = True
    registry["lf-unfinished"]["x-verbatim"] = True
    registry_path.write_text(json.dumps(registry))

    for args in (
        ["package", "check", ".leaf"],
        ["page", "init", str(tmp_path / "page")],
    ):
        result = runner.invoke(cli_model.cli, args)
        assert result.exit_code != 0
        assert "widgets/lf-unfinished.js" in result.output


def test_package_check_refuses_a_registry_example_that_violates_its_schema(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    add_test_widget(tmp_path / ".leaf", "lf-toned-note")

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    entry = registry["lf-toned-note"]
    entry["properties"]["tone"] = {"enum": ["quiet", "loud"]}
    entry["required"].append("tone")
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert result.exit_code != 0
    assert "<lf-toned-note> x-example is invalid" in result.output
    assert "'tone' is a required property" in result.output


def test_package_check_refuses_malformed_css_without_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(".bad { color red; }\n")

    before = theme.read_bytes()
    result = CliRunner().invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert result.exit_code != 0
    assert f"{theme} syntax error" in result.output
    assert theme.read_bytes() == before
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_package_check_requires_an_existing_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_model.cli, ["package", "check", "packages/missing"])

    assert result.exit_code != 0
    assert "is not a package directory" in result.output
    assert not (tmp_path / "packages").exists()


def test_package_command_accepts_the_root_of_a_standalone_package_repo(
    tmp_path, monkeypatch
):
    package = tmp_path / "callout-package"
    package.mkdir()
    monkeypatch.chdir(package)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", "."])

    assert result.exit_code == 0, result.output
    assert (package / "registry.json").is_file()
    assert (package / "theme.css").is_file()
    assert (package / "guidance").is_dir()
    assert (package / "widgets").is_dir()
    assert (package / "vendor").is_dir()


def test_package_command_can_target_the_user_package(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        cli_model.cli, ["package", "init", str(config / "leaf")]
    )

    assert result.exit_code == 0, result.output
    package = config / "leaf"
    assert json.loads((package / "registry.json").read_text()) == {}
    assert (package / "theme.css").is_file()
    assert not (tmp_path / ".leaf").exists()


def test_package_continues_when_the_project_root_is_the_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    initialized = runner.invoke(cli_model.cli, ["page", "init", "."])
    assert initialized.exit_code == 0, initialized.output
    page_theme = tmp_path / "theme.css"
    page_registry = tmp_path / "registry.json"
    before_theme = page_theme.read_bytes()
    before_registry = page_registry.read_bytes()
    before_widgets = {
        path.name: path.read_bytes()
        for path in (tmp_path / "widgets").iterdir()
        if path.is_file()
    }

    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-after-init", upgrade=True)
    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert checked.exit_code == 0, checked.output
    assert page_theme.read_bytes() == before_theme
    assert page_registry.read_bytes() == before_registry
    assert {
        path.name: path.read_bytes()
        for path in (tmp_path / "widgets").iterdir()
        if path.is_file()
    } == before_widgets
    assert (package / "widgets" / "lf-after-init.js").is_file()

    revendored = runner.invoke(cli_model.cli, ["page", "init", "."])

    assert revendored.exit_code == 0, revendored.output
    assert "lf-after-init" in json.loads(page_registry.read_text())
    assert (tmp_path / "widgets" / "lf-after-init.js").is_file()


def test_package_init_creates_independently_selectable_packages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    callout = Path("packages/callout")
    accent = Path("packages/accent")

    for path in (callout, accent):
        result = runner.invoke(cli_model.cli, ["package", "init", str(path)])
        assert result.exit_code == 0, result.output
    add_test_widget(tmp_path / callout, "lf-callout", upgrade=True)
    with (tmp_path / accent / "theme.css").open("a") as theme:
        theme.write("\n:root { --accent: teal; }\n")

    page = tmp_path / "page"
    initialized = runner.invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            str(callout),
            "--package",
            str(accent),
            str(page),
        ],
    )
    assert initialized.exit_code == 0, initialized.output
    registry = json.loads((page / "registry.json").read_text())
    assert registry["$layer"]["packages"] == [str(callout), str(accent)]
    assert "lf-callout" in registry
    assert (page / "widgets" / "lf-callout.js").is_file()


def test_package_init_names_a_wrong_kind_lower_package(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    user_layer = config / "leaf"
    user_layer.write_text("not a directory")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert f"{user_layer} must be a directory" in result.output
    assert user_layer.read_text() == "not a directory"
    assert not (project / ".leaf").exists()


def test_package_init_never_overwrites_existing_contents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(":root { --accent: rebeccapurple; }\n")

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert result.exit_code == 0, result.output
    assert theme.read_text() == ":root { --accent: rebeccapurple; }\n"
    (layer / "registry.json").write_text('{"$local": {"value": 1}}\n')
    (layer / "guidance" / "author.md").write_text("Keep me.\n")
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    repeated = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert repeated.exit_code == 0, repeated.output
    assert {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("role", ["project", "user"])
def test_package_init_protects_another_package_future_root(tmp_path, monkeypatch, role):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    (project / ".leaf").symlink_to(config / "leaf", target_is_directory=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    package = project / ".leaf" if role == "project" else config / "leaf"
    result = CliRunner().invoke(cli_model.cli, ["package", "init", str(package)])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert not (config / "leaf").exists()


def test_package_init_validates_every_target_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    theme = layer / "theme.css"
    theme.mkdir(parents=True)
    sentinel = theme / "keep.txt"
    sentinel.write_text("keep")

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "theme.css must be a file" in result.output
    assert sentinel.read_text() == "keep"
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


@pytest.mark.parametrize(
    ("relative", "directory"),
    [("vendor", False), ("leaf.js", True)],
)
def test_package_init_validates_the_complete_package(
    tmp_path, monkeypatch, relative, directory
):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    malformed = layer / relative
    if directory:
        malformed.mkdir()
    else:
        malformed.write_text("not a directory")

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert str(malformed) in result.output
    assert not (layer / "theme.css").exists()
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_package_is_the_unit_that_init_creates_checks_and_vendors(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output

    package = tmp_path / ".leaf"
    assert json.loads((package / "registry.json").read_text()) == {}
    assert (package / "theme.css").is_file()
    assert list((package / "guidance").iterdir()) == []
    assert (package / "widgets").is_dir()
    assert (package / "vendor").is_dir()

    entry = add_test_widget(package, "lf-callout", upgrade=True)
    (package / "guidance" / "author.md").write_text(
        "# Callouts\n\nUse them for short notices.\n"
    )
    (package / "widgets" / "callout-format.js").write_text(
        'export const label = "Heads up";\n'
    )
    (package / "vendor" / "callout-schema.json").write_text('{"kind":"callout"}\n')

    checked = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])
    assert checked.exit_code == 0, checked.output

    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    assert "lf-callout {" in (page / "theme.css").read_text()
    assert json.loads((page / "registry.json").read_text())["lf-callout"] == entry
    assert (
        "Use them for short notices." in (page / "guidance" / "author.md").read_text()
    )
    assert (page / "widgets" / "lf-callout.js").is_file()
    assert (page / "widgets" / "callout-format.js").read_text() == (
        package / "widgets" / "callout-format.js"
    ).read_text()
    assert (page / "vendor" / "callout-schema.json").read_text() == (
        package / "vendor" / "callout-schema.json"
    ).read_text()

    (page / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            '<h2>Plan</h2><lf-callout id="custom-note">'
            "<strong>Heads up</strong> Custom project guidance."
            "</lf-callout>",
        )
    )
    result = check(page)
    assert result.exit_code == 0, result.output


def test_package_preserves_a_symlinked_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    shared_registry = tmp_path / "shared-registry.json"
    shared_registry.write_text("{}\n")
    registry = layer / "registry.json"
    registry.symlink_to(shared_registry)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code == 0, result.output
    assert registry.is_symlink()
    assert json.loads(shared_registry.read_text()) == {}


def test_package_recognizes_a_page_without_runtime_status(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    (page / "status.json").unlink()
    before = (page / "theme.css").read_bytes()

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").symlink_to(page / "theme.css")

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    assert (page / "theme.css").read_bytes() == before
    assert not (layer / "registry.json").exists()


def test_package_refuses_a_broken_case_alias_to_its_future_target(
    tmp_path, monkeypatch
):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    config = tmp_path / "Config"
    user_theme = config / "leaf" / "theme.css"
    user_theme.parent.mkdir(parents=True)
    user_theme.symlink_to(alias / ".LEAF" / "THEME.CSS")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert user_theme.is_symlink() and not user_theme.exists()
    assert not (project / ".leaf" / "theme.css").exists()


def test_package_refuses_a_broken_lower_alias_to_its_planned_target(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    user_layer = config / "leaf"
    user_layer.mkdir(parents=True)
    project_theme = project / ".leaf" / "theme.css"
    user_theme = user_layer / "theme.css"
    user_theme.symlink_to(project_theme)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert user_theme.is_symlink() and not user_theme.exists()
    assert not project_theme.exists()


def test_package_refuses_an_existing_member_aliased_to_another_scope(
    tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    user_module = config / "leaf" / "widgets" / "lf-shared.js"
    user_module.parent.mkdir(parents=True)
    user_module.write_text("// shared source\n")
    project_module = project / ".leaf" / "widgets" / "lf-shared.js"
    project_module.parent.mkdir(parents=True)
    project_module.symlink_to(user_module)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert project_module.is_symlink()
    assert user_module.read_text() == "// shared source\n"
    assert not (project / ".leaf" / "theme.css").exists()


def test_package_refuses_an_existing_member_case_alias(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    config = tmp_path / "Config"
    user_theme = config / "leaf" / "theme.css"
    user_theme.parent.mkdir(parents=True)
    user_theme.write_text(":root { --accent: teal; }\n")
    config_alias = case_alias(config)
    project_theme = project / ".leaf" / "theme.css"
    project_theme.parent.mkdir(parents=True)
    project_theme.symlink_to(config_alias / "LEAF" / "THEME.CSS")
    before = user_theme.read_bytes()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert user_theme.read_bytes() == before
    assert not (project_theme.parent / "registry.json").exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_package_refuses_an_initialized_page_as_a_layer(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = config / "leaf" if user else project / ".leaf"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.symlink_to(page, target_is_directory=True)
    result = runner.invoke(cli_model.cli, ["package", "init", str(layer)])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_package_refuses_case_aliased_future_roots(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(alias / ".LEAF"))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    assert not (project / ".leaf").exists()


@pytest.mark.parametrize(
    "relative",
    ["theme.css", "registry.json", "widgets", "widgets/lf-tabs.js"],
)
def test_package_refuses_members_aliased_into_an_initialized_page(
    tmp_path, monkeypatch, relative
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = project / ".leaf"
    alias = layer / relative
    alias.parent.mkdir(parents=True, exist_ok=True)
    target = page / relative
    alias.symlink_to(target, target_is_directory=target.is_dir())

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (layer / "theme.css").exists() or relative == "theme.css"
    assert not (layer / "registry.json").exists() or relative == "registry.json"


@pytest.mark.parametrize(
    ("source_name", "page_name"),
    [
        ("theme.css", "status.json"),
        ("widgets", schema_model.MEDIA_DIR),
        ("vendor", "versions"),
    ],
)
def test_package_refuses_sources_aliased_to_page_owned_state(
    tmp_path, monkeypatch, source_name, page_name
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(cli_model.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    target = page / page_name
    if source_name in schema_model.BROWSER_DIRS:
        target.mkdir(exist_ok=True)
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / source_name).symlink_to(target, target_is_directory=target.is_dir())

    result = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (layer / "registry.json").exists()


@pytest.mark.parametrize("alias", ["root", "theme.css", "registry.json", "widgets"])
def test_package_refuses_targets_aliased_to_another_layer(tmp_path, monkeypatch, alias):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    user = config / "leaf"
    user.mkdir(parents=True)
    (user / "theme.css").write_text(":root { --accent: teal; }\n")
    (user / "registry.json").write_text("{}\n")
    (user / "widgets").mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    layer = project / ".leaf"
    if alias == "root":
        layer.symlink_to(user, target_is_directory=True)
    else:
        layer.mkdir()
        (layer / alias).symlink_to(user / alias, target_is_directory=alias == "widgets")
    before = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }

    result = CliRunner().invoke(cli_model.cli, ["package", "init", ".leaf"])

    assert result.exit_code != 0
    assert "overlaps another package" in result.output
    after = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_page_init_refuses_a_duplicate_package_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "solo"
    package.mkdir()

    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "solo",
            "--package",
            "solo",
            str(tmp_path / "page"),
        ],
    )

    assert result.exit_code == 2
    assert "each --package path may appear only once" in result.output


def test_page_init_refuses_an_empty_package_path_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", "", str(page)],
    )

    assert result.exit_code == 2
    assert "--package paths cannot be empty" in result.output
    assert not page.exists()


def test_page_init_refuses_to_publish_an_absolute_package_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "solo"
    source.mkdir()
    page = tmp_path / "page"

    result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", str(source), str(page)],
    )

    assert result.exit_code == 1
    assert "use a project-relative or ~ path" in result.output
    assert "does not publish a machine path" in result.output
    assert not page.exists()


def test_page_init_selects_the_same_directory_contract_at_any_cardinality(
    tmp_path, monkeypatch
):
    """A package is not a multi-widget subtype.

    One root below carries exactly one widget plus its private helper and vendor
    data; the other carries only theme rules. Both enter the same ordered merger
    as a many-widget package, and a plain re-vendor resolves their recorded
    project-relative paths again.
    """
    monkeypatch.chdir(tmp_path)
    widget_package = tmp_path / "solo"
    (widget_package / "widgets").mkdir(parents=True)
    (widget_package / "vendor").mkdir()
    (widget_package / "registry.json").write_text(
        json.dumps({"lf-solo": widget_entry("lf-solo", True)})
    )
    (widget_package / "theme.css").write_text("lf-solo { --lf-frame: 1; }\n")
    (widget_package / "widgets" / "lf-solo.js").write_text(
        'import { ready } from "./ready.js";\n'
        'customElements.define("lf-solo", class extends HTMLElement {\n'
        "  connectedCallback() { ready(this); }\n"
        "});\n"
    )
    (widget_package / "widgets" / "ready.js").write_text(
        "export const ready = (el) => { el.dataset.ready = '1'; };\n"
    )
    (widget_package / "vendor" / "solo.json").write_text('{"accent":"plum"}\n')
    (widget_package / "guidance").mkdir()
    (widget_package / "guidance" / "author.md").write_text(
        "# Solo widget\n\nUse one solo.\n"
    )
    (widget_package / "guidance" / "worker.md").write_text(
        "# Solo worker\n\nReport the result.\n"
    )

    theme_package = tmp_path / "night"
    theme_package.mkdir()
    (theme_package / "theme.css").write_text(":root { --solo-night: 1; }\n")
    (theme_package / "guidance").mkdir()
    (theme_package / "guidance" / "author.md").write_text(
        "# Night theme\n\nUse after dusk.\n"
    )
    (theme_package / "guidance" / "reviewer.md").write_text(
        "# Night reviewer\n\nCheck the contrast.\n"
    )

    page = tmp_path / "page"
    initialized = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "init",
            "--package",
            "solo",
            "--package",
            "night",
            str(page),
        ],
    )

    assert initialized.exit_code == 0, initialized.output
    registry = json.loads((page / "registry.json").read_text())
    assert registry["$layer"]["packages"] == ["solo", "night"]
    assert "lf-solo" in registry
    assert (page / "widgets" / "lf-solo.js").is_file()
    assert (page / "widgets" / "ready.js").is_file()
    assert (page / "vendor" / "solo.json").is_file()
    theme = (page / "theme.css").read_text()
    assert theme.index("lf-solo { --lf-frame: 1; }") < theme.index("--solo-night: 1")
    guidance = (page / "guidance" / "author.md").read_text()
    assert guidance.index("# Solo widget") < guidance.index("# Night theme")
    assert "Report the result." in (page / "guidance" / "worker.md").read_text()
    assert "Check the contrast." in (page / "guidance" / "reviewer.md").read_text()

    audiences = CliRunner().invoke(cli_model.cli, ["page", "guidance", str(page)])
    worker = CliRunner().invoke(
        cli_model.cli, ["page", "guidance", str(page), "worker"]
    )
    assert audiences.exit_code == 0, audiences.output
    assert audiences.output.splitlines() == ["author", "reviewer", "worker"]
    assert worker.exit_code == 0, worker.output
    assert worker.output == "# Solo worker\n\nReport the result.\n"

    revendored = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])
    assert revendored.exit_code == 0, revendored.output
    assert json.loads((page / "registry.json").read_text())["$layer"]["packages"] == [
        "solo",
        "night",
    ]


def test_page_init_vendors_an_explicit_package_without_privileging_it(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    package = link_command_hub_package(tmp_path)
    plain = tmp_path / "plain"
    command = tmp_path / "command"

    plain_result = CliRunner().invoke(cli_model.cli, ["page", "init", str(plain)])
    packaged_result = CliRunner().invoke(
        cli_model.cli,
        ["page", "init", "--package", package, str(command)],
    )

    assert plain_result.exit_code == 0, plain_result.output
    assert packaged_result.exit_code == 0, packaged_result.output
    plain_registry = json.loads((plain / "registry.json").read_text())
    packaged_registry = json.loads((command / "registry.json").read_text())
    orchestration = {
        "lf-roster",
        "lf-agent",
        "lf-tasks",
        "lf-task",
        "lf-command",
        "lf-worktree",
        "lf-record",
    }
    assert orchestration.isdisjoint(plain_registry)
    assert orchestration <= packaged_registry.keys()
    assert "$command" not in plain_registry
    assert "$command" in packaged_registry
    assert plain_registry["$layer"]["packages"] == []
    assert packaged_registry["$layer"]["packages"] == [package]
    assert not (plain / "widgets" / "lf-command.js").exists()
    assert (command / "widgets" / "lf-command.js").is_file()
    assert list((plain / "guidance").iterdir()) == []
    assert "# Command Hub package" in (command / "guidance" / "author.md").read_text()
    plain_audiences = CliRunner().invoke(
        cli_model.cli, ["page", "guidance", str(plain)]
    )
    plain_catalog = CliRunner().invoke(cli_model.cli, ["page", "catalog", str(plain)])
    packaged_catalog = CliRunner().invoke(
        cli_model.cli, ["page", "catalog", str(command)]
    )
    assert plain_audiences.exit_code == 0, plain_audiences.output
    assert plain_audiences.output == ""
    assert plain_catalog.exit_code == 0, plain_catalog.output
    assert packaged_catalog.exit_code == 0, packaged_catalog.output
    assert '"lf-worktree"' not in plain_catalog.output
    assert '"lf-worktree"' in packaged_catalog.output
    assert "# Widget `<lf-worktree>`" in packaged_catalog.output
    assert (
        packaged_registry["lf-worktree"]["x-guidance"]["author"]
        in packaged_catalog.output
    )
    assert "# Guidance for authors" not in plain_catalog.output
    assert "# $command, declared by this layer." in packaged_catalog.output
    assert "# Guidance for authors" in packaged_catalog.output
    assert "# Command Hub package" in packaged_catalog.output
    audiences = CliRunner().invoke(cli_model.cli, ["page", "guidance", str(command)])
    coordinator = CliRunner().invoke(
        cli_model.cli, ["page", "guidance", str(command), "coordinator"]
    )
    assert audiences.exit_code == 0, audiences.output
    assert audiences.output.splitlines() == ["author", "coordinator", "worker"]
    assert coordinator.exit_code == 0, coordinator.output
    assert "# Command Hub coordinator" in coordinator.output
    assert "# Data contract `lf-worktree`" in coordinator.output
    assert (
        packaged_registry["$data"]["contracts"]["lf-worktree"]["guidance"][
            "coordinator"
        ]
        in coordinator.output
    )

    revendor = CliRunner().invoke(cli_model.cli, ["page", "init", str(command)])
    assert revendor.exit_code == 0, revendor.output
    assert json.loads((command / "registry.json").read_text())["$layer"][
        "packages"
    ] == [package]
    assert (command / "widgets" / "lf-command.js").is_file()

    removed = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--no-packages", str(command)]
    )
    assert removed.exit_code == 0, removed.output
    removed_registry = json.loads((command / "registry.json").read_text())
    assert removed_registry["$layer"]["packages"] == []
    assert "lf-command" not in removed_registry
    assert not (command / "widgets" / "lf-command.js").exists()
    assert list((command / "guidance").iterdir()) == []


def test_init_merges_reaction_tokens_merge_patch_style(tmp_path, monkeypatch):
    """The shipped tokens are the default layer's statement, not core's. A project's
    entry under a token's name replaces that token whole, a new name joins after
    the shipped ones, and `null` removes one — which is the only way a layer can take
    a token off the bar without restating the whole set. The order the page numbers
    the armed digits by is the merged map's."""
    project = tmp_path / "proj"
    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / "registry.json").write_text(
        json.dumps(
            {
                "$reactions": {
                    "tokens": {
                        "ok": {"glyph": "👍", "means": "ship it", "settles": True},
                        "cut": None,
                        "meh": {"glyph": "~", "means": "neither here nor there"},
                    }
                }
            }
        )
    )
    monkeypatch.chdir(project)

    page = tmp_path / "page"
    result = CliRunner().invoke(cli_model.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    tokens = json.loads((page / "registry.json").read_text())["$reactions"]["tokens"]
    assert list(tokens) == ["ok", "no", "lost", "more", "this", "meh"]
    assert tokens["ok"] == {"glyph": "👍", "means": "ship it", "settles": True}
    assert tokens["meh"] == {"glyph": "~", "means": "neither here nor there"}
    assert "settles" not in tokens["no"]


@pytest.mark.parametrize(
    "entry",
    [
        {"glyph": "✓"},  # no meaning for `leaf wait` to print
        {"glyph": "", "means": "x"},
        {"glyph": "✓", "means": "x", "settle": True},  # a flag nothing reads
        {"glyph": "✓", "means": "x", "settles": "yes"},
    ],
)
def test_package_check_refuses_a_malformed_reaction_token(tmp_path, monkeypatch, entry):
    """Every consumer reads a token's entry directly — the bar paints `glyph`,
    `leaf wait` prints `means`, the panel reads `settles` — so a member missing or
    misspelled is a token that paints nothing or a flag that settles nothing, and
    nothing else would say so."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli_model.cli, ["package", "init", ".leaf"]).exit_code == 0
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["$reactions"] = {"tokens": {"nod": entry}}
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(cli_model.cli, ["package", "check", ".leaf"])

    assert result.exit_code != 0
    assert "$reactions.tokens must map lowercase token names" in result.output
