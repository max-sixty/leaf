"""CLI, plugin payload, layer, and customization tests."""

import json
import os
import re
import shutil
import subprocess

import pytest
from click.testing import CliRunner
from interact_support import (
    PAGE,
    PLUGIN_ROOT,
    ROOT,
    case_alias,
    check,
    interact,
    record_claim,
)


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
  customize   Create theme and widget customizations.
  events      Print the event log as JSON lines.
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
            ["customize", "--help"],
            """Usage: leaf customize [OPTIONS] COMMAND [ARGS]...

  Create theme and widget customizations.

Options:
  --help  Show this message and exit.

Commands:
  theme   Create the theme override file.
  widget  Add a widget scaffold.
""",
            id="customize",
        ),
        pytest.param(
            ["page", "--help"],
            """Usage: leaf page [OPTIONS] COMMAND [ARGS]...

  Create pages and add media.

Options:
  --help  Show this message and exit.

Commands:
  catalog  Print the widget and theme vocabulary.
  init     Create or re-vendor a page directory.
  media    Add images and print their page paths.
  state    Print where the page stands, as JSON.
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
        interact.cli,
        args,
        prog_name="leaf",
        terminal_width=80,
    )

    assert result.exit_code == 0
    assert result.output == expected


@pytest.mark.parametrize("command", ["wait", "ack"])
def test_wait_and_ack_help_require_a_complete_batch(command):
    result = CliRunner().invoke(
        interact.cli,
        [command, "--help"],
        terminal_width=200,
    )

    assert result.exit_code == 0
    assert "--forward" not in result.output
    assert " ".join(interact.ACK_BATCH_INSTRUCTION.split()) in " ".join(
        result.output.split()
    )


def test_ack_batch_instruction_preserves_scalar_cursor_safety():
    assert interact.ACK_BATCH_INSTRUCTION == (
        "If wait output is truncated, acknowledge nothing and rerun with enough output "
        "capacity for the whole batch. After the complete batch reaches its next durable "
        "consumer, the wait owner runs `leaf ack <page> <highest-seq>` for the page the "
        "batch's first line names."
    )


def test_skill_assigns_acknowledgement_to_the_wait_owner():
    root = PLUGIN_ROOT / "skills" / "leaf"
    conversation = (root / "references" / "conversation-loop.md").read_text()
    watcher = (root / "references" / "codex-watcher.md").read_text()

    assert " ".join(interact.ACK_BATCH_INSTRUCTION.split()) in " ".join(
        conversation.split()
    )
    assert "Process every event" in conversation
    assert "`send_message_to_thread` is available" in watcher
    assert "Run `leaf wait <page>`" in watcher
    assert "do not run\n   `leaf wait` or `leaf ack`" in watcher
    assert "page and event seq already handled is a retry" in watcher
    assert "After the host accepts the follow-up" in watcher


def test_the_reply_guidance_shows_the_shape_a_long_answer_takes():
    """A reply is written into a shell argument and never read where it lands.

    The panel renders a reply through `marked` and the theme dresses its lists,
    code, quotes and tables for a column that is narrow by default, so the shape
    is available and nothing in the loop shows the author what they chose. The
    guidance said "brief Markdown" over a single-line `--text "<answer>"`, and
    brevity read as one paragraph: an answer carrying three independent reasons
    arrived as four sentences of prose with the reasons buried in clauses.

    So the rule states the short case as complete and the example carries the
    long one, because a documented call is copied where a description is not.
    The two assertions hold each half: brevity first, and a worked long answer
    to copy from when brevity does not fit.
    """
    root = PLUGIN_ROOT / "skills" / "leaf" / "references"
    conversation = (root / "conversation-loop.md").read_text()

    assert "one sentence is a complete reply" in " ".join(conversation.split())
    reply_block = conversation.split("leaf reply <page> --to <thread-id>")
    assert any(part.startswith(" <<'EOF'") for part in reply_block[1:])
    assert any(part.startswith(' --text "') for part in reply_block[1:])

    # A worker reads its own file and nothing routes it here, so its reply
    # example is the only shape that reaches it.
    worker = (root / "worker-orchestration.md").read_text()
    assert 'reply "$PAGE" --to "$THREAD" <<' in worker


def test_leaf_skill_routes_its_complete_reference_set():
    root = PLUGIN_ROOT / "skills" / "leaf"
    skill = (root / "SKILL.md").read_text()
    references = sorted((root / "references").glob("*.md"))
    expected = {
        "codex-watcher.md",
        "conversation-loop.md",
        "customizing.md",
        "page-authoring.md",
        "serving-pages.md",
        "worker-orchestration.md",
    }

    assert len(skill.splitlines()) < 500
    assert {path.name for path in references} == expected
    assert "--forward" not in "\n".join(
        [skill, *(path.read_text() for path in references)]
    )
    authoring = " ".join((root / "references/page-authoring.md").read_text().split())
    conversation = " ".join(
        (root / "references/conversation-loop.md").read_text().split()
    )
    assert "Escape `&` first, then `<` and `>`" in authoring
    assert "status banner, comment sidebar, version picker" in authoring
    assert "live-leaves tray, and open-asks tray" in authoring
    assert "informational page with no concrete ask" in " ".join(skill.split())
    assert "informational page with no concrete ask" in conversation
    for path in references:
        assert f"references/{path.name}" in skill


def test_a_correction_is_written_straight_rather_than_offered_as_a_choice():
    """A suggestion asks the reader to decide, so it needs a live alternative.

    The revision rule keys on who owns the words and whether the reader has already
    seen them, and had no test for whether there was anything to decide. So a page
    that reported a latency in the wrong unit put the corrected sentence in an
    `lf-suggestion`, and the reader got a check and a cross over a fact whose only
    other answer restores the error — counted, until pressed, among the things the
    banner and the ask walk say the page is waiting on them for.

    The carve-out is asserted inside its own section because that paragraph is what
    an author reads before writing the revision; stated anywhere else it is guidance
    nobody reaches at the moment it applies. Both halves are pinned, so dropping the
    suggestion rule to satisfy the carve-out fails here too."""
    authoring = " ".join(
        (PLUGIN_ROOT / "skills/leaf/references/page-authoring.md").read_text().split()
    )
    start = authoring.index("## Revisions and reader-owned words")
    revisions = authoring[start : authoring.index("## Honoring reader state", start)]

    assert (
        "Rewrite prose the reader has already seen as an `lf-suggestion`" in revisions
    )
    assert "A correction is not a proposal" in revisions
    assert "write the true thing straight" in revisions
    assert "wording the reader could reasonably prefer as it stands" in revisions


def test_the_page_is_named_by_its_findings_and_collapsed_around_them():
    """What a page costs to review is stated where it is composed and checked
    where it is handed over.

    A version can pass every gate and still be unreadable: the finding three
    paragraphs down, the section called "What we learned", the transcript that
    supports it standing open in the column. Neither the markup check nor the
    render gate can see any of that — both answer whether a page renders, not
    whether it is worth the reading — so this is prose or it is nothing.

    Two places, because they answer at different moments. "Reading cost" is what
    an author reads while deciding what goes on the page. The pre-handover review
    is the last point it can still change, and a heading that withholds its own
    finding is invisible to whoever just wrote it and plain to anyone who reads
    the headings alone. Pinned in one place only, the rule would be stated and
    never asked after."""
    root = PLUGIN_ROOT / "skills" / "leaf"
    authoring = " ".join((root / "references/page-authoring.md").read_text().split())
    start = authoring.index("## Reading cost")
    cost = authoring[start : authoring.index("## Interactivity", start)]

    assert "what the reader has to take from the page" in cost
    assert "its backing goes under `<details>`" in cost
    assert "A section that reaches a finding says it in the heading" in cost
    # The other half of the same rule. Without it the sentence above reads as a
    # demand that every section name be a claim, which turns an honest label over
    # a list or a control into a sentence; with it alone, every label is excused.
    assert "where there is no finding to state" in cost
    # The one thing a reading-cost rule must never license. A collapsed ask still
    # counts in the banner and the asks tray, and `checkVisibility()` is false
    # inside a closed disclosure, so no gate refuses the page whose decision is
    # behind a click.
    assert "An ask never collapses" in cost

    review = authoring[authoring.index("## Pre-handover review") :]
    assert "Take the headings on their own first" in review

    contract = " ".join((root / "SKILL.md").read_text().split())
    assert "its backing sits under `<details>`" in contract


def test_hidden_hook_remains_callable():
    result = CliRunner().invoke(interact.cli, ["hook"], input="{}")

    assert result.exit_code == 0
    assert result.output == ""


def test_init_help_names_the_version_file_layout():
    result = CliRunner().invoke(
        interact.cli,
        ["page", "init", "--help"],
        prog_name="leaf",
        terminal_width=80,
    )

    assert result.exit_code == 0
    assert "Creates PAGE/versions/ for authored vN.html files" in result.output


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

    assert result.returncode == 0, result.stderr
    assert (dispatched[1:3] == ["--with", "playwright"]) is needs_playwright


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
        "skills/leaf/references/customizing.md",
        "skills/leaf/references/page-authoring.md",
        "skills/leaf/references/serving-pages.md",
        "skills/leaf/references/worker-orchestration.md",
        "skills/leaf/scripts/interact.py",
        # The lock only pins what it ships beside; an install that loses it
        # resolves fresh and looks identical from the outside.
        "skills/leaf/scripts/interact.py.lock",
    ]:
        assert (PLUGIN_ROOT / relative).is_file()
    assert not [path for path in PLUGIN_ROOT.rglob("*") if path.is_symlink()]


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
    assert interact.published_versions(page, interact.read_events(page)) == [1]


@pytest.mark.nightly  # the resolve behind the lock asks the index for the header
def test_the_launcher_starts_where_the_locks_own_urls_cannot_be_served(tmp_path):
    """The lock records an absolute URL per wheel and uv fetches exactly those, so an
    index the host configures is never consulted while the lock can be satisfied. On a
    host whose index is a private mirror rather than pypi.org that fetch fails, and it
    fails before the script runs — `page init`, `version check` and `server run` alike.

    The mirror is stood up from the other side, because that is the half this repro
    needs: the lock's recorded URLs are pointed at a closed port, which leaves the
    configured index as the only thing that can serve the three dependencies. The cache
    gets a directory of its own for the same reason — a wheel already in the developer's
    cache answers whatever the lock says, and the run proves nothing."""
    installed = tmp_path / "plugins" / "leaf"
    shutil.copytree(PLUGIN_ROOT, installed)
    lock = installed / "skills" / "leaf" / "scripts" / "interact.py.lock"
    lock.write_text(
        lock.read_text().replace(
            "https://files.pythonhosted.org/", "http://127.0.0.1:1/"
        )
    )

    result = subprocess.run(
        [installed / "bin" / "leaf", "--help"],
        cwd=tmp_path,
        env={**os.environ, "UV_CACHE_DIR": str(tmp_path / "uv-cache")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        "Build and run interactive pages a session shares with its user."
        in result.stdout
    )
    # The fallback re-resolves a header with no upper bounds and writes the result
    # over the pins, and the run behind it succeeds — so it says so on stderr,
    # which is the only account anyone gets of a moved pin.
    assert "resolving the header against this host's index" in result.stderr
    # Which failure it was is the ask's to say and not the announcement's — an
    # unservable lock reads nothing like a 503 or a host with no `uv` at all — so
    # the ask's own words come with it rather than dying with its exit status.
    assert "127.0.0.1:1" in result.stderr
    # The resolve is paid once: it rewrites the lock to what this host's index
    # served, so the next run is pinned again rather than resolving afresh.
    assert "127.0.0.1:1" not in lock.read_text()


def test_init_vendors_the_layer(page_dir):
    for name in ["leaf.js", "theme.css", "registry.json"]:
        assert (page_dir / name).is_file()
    assert (page_dir / "widgets" / "lf-tabs.js").is_file()
    assert (page_dir / "widgets" / "lf-diagram.js").is_file()
    assert (page_dir / "vendor" / "mermaid.min.js").is_file()


def test_every_test_runs_against_a_throwaway_config_and_state(tmp_path_factory):
    """What `isolated_session` promises, asserted where a break would show. The
    two homes are the only thing leaf reads from the developer's own, and a
    suite that reached theirs fails silently in both directions: it would vendor
    their overlay into fixtures that never say what a theme should contain, and
    register a dozen throwaway pages a run in the state home the loop guard reads,
    for pages nobody has. Every other test here sets whichever home it is about,
    so none of them would notice."""
    root = tmp_path_factory.getbasetemp()
    assert interact.config_home().is_relative_to(root)
    assert interact.state_home().is_relative_to(root)


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
    result = CliRunner().invoke(interact.cli, ["page", "init", str(d)])
    assert result.exit_code == 0, result.output
    vendored_theme = (d / "theme.css").read_text()
    assert vendored_theme.startswith((interact.ASSETS / "theme.css").read_text())
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
    result = CliRunner().invoke(interact.cli, ["page", "init", str(d)])
    assert result.exit_code == 0, result.output
    theme = (d / "theme.css").read_text()
    assert theme.startswith((interact.ASSETS / "theme.css").read_text())
    assert theme.endswith(custom_theme)
    # Files the project layer doesn't override still come from the shipped defaults.
    assert (d / "registry.json").is_file()


def test_init_refuses_a_layer_theme_that_leaves_a_block_open(tmp_path, monkeypatch):
    """The CSS parser auto-closes a block left open at end of file, so tinycss2
    reports nothing — but layer stylesheets concatenate, and an unclosed block
    swallows every later layer's rules into its own scope. The shipped split hit
    exactly this: a cut that dropped one closing brace nested the whole bundled
    layer inside a min-width media query, and the only symptom was print styles
    quietly not applying. The gate names the file while the author is still in
    front of it."""
    project = tmp_path / "proj"
    (project / ".leaf").mkdir(parents=True)
    (project / ".leaf" / "theme.css").write_text(
        "@media screen and (min-width: 900px) {\n  :root { --accent: red }\n"
    )
    monkeypatch.chdir(project)
    result = CliRunner().invoke(interact.cli, ["page", "init", str(tmp_path / "page")])
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
    result = CliRunner().invoke(interact.cli, ["page", "init", str(page)])

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
    result = CliRunner().invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    idioms = json.loads((page / "registry.json").read_text())["$idioms"]
    shipped = json.loads((interact.ASSETS / "registry.json").read_text())["$idioms"]
    assert idioms[".hazard"] == hazard
    assert idioms[".lede"] == lede
    assert idioms["description"] == shipped["description"]
    assert set(shipped) <= set(idioms)
    languages = json.loads((page / "registry.json").read_text())["$languages"]
    shipped_langs = json.loads((interact.ASSETS / "registry.json").read_text())[
        "$languages"
    ]
    assert languages["paths"]["svelte"] == "javascript"
    assert set(shipped_langs["paths"]) <= set(languages["paths"])
    assert languages["names"] == shipped_langs["names"]


def test_customize_scaffolds_a_project_widget_that_init_can_vendor(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    theme = runner.invoke(interact.cli, ["customize", "theme"])
    assert theme.exit_code == 0, theme.output

    widget = runner.invoke(
        interact.cli, ["customize", "widget", "lf-callout", "--upgrade"]
    )
    assert widget.exit_code == 0, widget.output

    layer = tmp_path / ".leaf"
    registry = json.loads((layer / "registry.json").read_text())
    entry = registry["lf-callout"]
    assert entry["x-content"] == "prose"
    assert entry["x-upgrade"] is True
    assert entry["x-verbatim"] is True
    assert "<lf-callout" in entry["x-example"]
    assert "lf-callout {" in (layer / "theme.css").read_text()
    assert "customElements.define(" in (layer / "widgets" / "lf-callout.js").read_text()

    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    assert "lf-callout {" in (page / "theme.css").read_text()
    assert json.loads((page / "registry.json").read_text())["lf-callout"] == entry
    assert (page / "widgets" / "lf-callout.js").is_file()

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


def test_customize_scaffolds_a_long_widget_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tag = "lf-" + "a" * 237
    module_name = f"{tag}.js"
    try:
        name_max = os.pathconf(tmp_path, "PC_NAME_MAX")
    except (AttributeError, OSError, ValueError):
        name_max = 255
    if len(os.fsencode(module_name)) > name_max:
        pytest.skip("the final module name does not fit this filesystem")

    result = CliRunner().invoke(interact.cli, ["customize", "widget", tag, "--upgrade"])

    assert result.exit_code == 0, result.output
    layer = tmp_path / ".leaf"
    assert (layer / "widgets" / module_name).is_file()
    assert tag in json.loads((layer / "registry.json").read_text())


def test_customize_never_overwrites_an_existing_layer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(":root { --accent: rebeccapurple; }\n")

    result = runner.invoke(interact.cli, ["customize", "theme"])
    assert result.exit_code == 0, result.output
    assert theme.read_text() == ":root { --accent: rebeccapurple; }\n"

    assert (
        runner.invoke(interact.cli, ["customize", "widget", "lf-note-card"]).exit_code
        == 0
    )
    registry_before = (layer / "registry.json").read_text()
    theme_before = theme.read_text()

    duplicate = runner.invoke(interact.cli, ["customize", "widget", "lf-note-card"])
    assert duplicate.exit_code != 0
    assert "already exists" in duplicate.output
    assert (layer / "registry.json").read_text() == registry_before
    assert theme.read_text() == theme_before

    shipped = runner.invoke(interact.cli, ["customize", "widget", "lf-options"])
    assert shipped.exit_code != 0
    assert "already exists" in shipped.output
    assert (layer / "registry.json").read_text() == registry_before
    assert theme.read_text() == theme_before


def test_customize_can_target_the_user_layer(tmp_path, monkeypatch):
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-personal-note", "--user"]
    )

    assert result.exit_code == 0, result.output
    layer = config / "leaf"
    assert "lf-personal-note" in json.loads((layer / "registry.json").read_text())
    assert (layer / "theme.css").is_file()
    assert not (tmp_path / ".leaf").exists()


def test_customize_preserves_a_symlinked_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    shared_registry = tmp_path / "shared-registry.json"
    shared_registry.write_text("{}\n")
    registry = layer / "registry.json"
    registry.symlink_to(shared_registry)

    result = CliRunner().invoke(interact.cli, ["customize", "widget", "lf-shared-note"])

    assert result.exit_code == 0, result.output
    assert registry.is_symlink()
    assert "lf-shared-note" in json.loads(shared_registry.read_text())


@pytest.mark.skipif(os.name == "nt", reason="POSIX umask and mode semantics")
def test_staged_writes_honor_umask_without_copying_a_replaced_symlink_mode(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    old_umask = os.umask(0o077)
    try:
        customized = runner.invoke(interact.cli, ["customize", "theme"])
    finally:
        os.umask(old_umask)
    assert customized.exit_code == 0, customized.output
    custom_theme = tmp_path / ".leaf" / "theme.css"
    assert custom_theme.stat().st_mode & 0o777 == 0o600

    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    external = tmp_path / "external-theme.css"
    external.write_text("external")
    external.chmod(0o600)
    (page / "theme.css").unlink()
    (page / "theme.css").symlink_to(external)
    old_umask = os.umask(0o022)
    try:
        revendored = runner.invoke(interact.cli, ["page", "init", str(page)])
    finally:
        os.umask(old_umask)

    assert revendored.exit_code == 0, revendored.output
    assert not (page / "theme.css").is_symlink()
    assert (page / "theme.css").stat().st_mode & 0o777 == 0o644
    assert external.read_text() == "external"


@pytest.mark.parametrize("alias", ["root", "theme.css", "registry.json", "widgets"])
def test_customize_refuses_targets_aliased_to_another_layer(
    tmp_path, monkeypatch, alias
):
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

    args = ["customize", "widget", "lf-no-scope-alias"]
    if alias in {"root", "widgets"}:
        args.append("--upgrade")
    result = CliRunner().invoke(interact.cli, args)

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    after = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    "args",
    [
        ["customize", "theme"],
        ["customize", "widget", "lf-future-alias"],
        ["customize", "theme", "--user"],
        ["customize", "widget", "lf-future-alias", "--user"],
    ],
    ids=["project-theme", "project-widget", "user-theme", "user-widget"],
)
def test_customize_protects_another_layers_future_root(tmp_path, monkeypatch, args):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    (project / ".leaf").symlink_to(config / "leaf", target_is_directory=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(interact.cli, args)

    assert result.exit_code != 0
    if "--user" in args:
        assert "overlaps another layer source" in result.output
    else:
        assert "must be a directory" in result.output
    assert not (config / "leaf").exists()


def test_path_case_policy_matches_the_filesystem(tmp_path):
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    alias_resolves = (tmp_path / "cASEpROBE").exists()

    assert interact._filesystem_case_sensitive(tmp_path) is not alias_resolves


def test_path_overlap_respects_case_sensitive_future_names(tmp_path, monkeypatch):
    upper = tmp_path / "FutureScope"
    lower = tmp_path / "fUTUREsCOPE"
    monkeypatch.setattr(interact, "_filesystem_case_sensitive", lambda path: True)
    assert not interact.locations_overlap(
        interact._path_location(upper), interact._path_location(lower)
    )

    monkeypatch.setattr(interact, "_filesystem_case_sensitive", lambda path: False)
    assert interact.paths_same(upper, lower)


def test_customize_refuses_case_aliased_future_roots(tmp_path, monkeypatch):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(alias / ".LEAF"))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(interact.cli, ["customize", "theme"])

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    assert not (project / ".leaf").exists()


def test_customize_refuses_a_broken_case_alias_to_its_future_target(
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

    result = CliRunner().invoke(interact.cli, ["customize", "theme"])

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    assert user_theme.is_symlink() and not user_theme.exists()
    assert not (project / ".leaf" / "theme.css").exists()


def test_customize_refuses_an_existing_member_case_alias(tmp_path, monkeypatch):
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

    result = CliRunner().invoke(interact.cli, ["customize", "widget", "lf-case-member"])

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    assert user_theme.read_bytes() == before
    assert not (project_theme.parent / "registry.json").exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_customize_refuses_an_initialized_page_as_a_layer(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = config / "leaf" if user else project / ".leaf"
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.symlink_to(page, target_is_directory=True)
    args = ["customize", "widget", "lf-page-alias", "--upgrade"]
    if user:
        args.append("--user")

    result = runner.invoke(interact.cli, args)

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize(
    "relative",
    ["theme.css", "registry.json", "widgets", "widgets/lf-tabs.js"],
)
def test_customize_refuses_members_aliased_into_an_initialized_page(
    tmp_path, monkeypatch, relative
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
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

    result = runner.invoke(
        interact.cli,
        ["customize", "widget", "lf-page-member-alias", "--upgrade"],
    )

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


def test_customize_recognizes_a_page_without_runtime_status(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    (page / "status.json").unlink()
    before = (page / "theme.css").read_bytes()

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").symlink_to(page / "theme.css")

    result = runner.invoke(
        interact.cli,
        ["customize", "widget", "lf-page-without-status", "--upgrade"],
    )

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    assert (page / "theme.css").read_bytes() == before
    assert not (layer / "registry.json").exists()


@pytest.mark.parametrize(
    ("source_name", "page_name"),
    [
        ("theme.css", "status.json"),
        ("widgets", interact.MEDIA_DIR),
        ("vendor", "versions"),
    ],
)
def test_customize_refuses_sources_aliased_to_page_owned_state(
    tmp_path, monkeypatch, source_name, page_name
):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    target = page / page_name
    if source_name in interact.VENDORED_DIRS:
        target.mkdir(exist_ok=True)
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = project / ".leaf"
    layer.mkdir(parents=True)
    (layer / source_name).symlink_to(target, target_is_directory=target.is_dir())

    result = runner.invoke(
        interact.cli,
        ["customize", "widget", "lf-page-owned-alias", "--upgrade"],
    )

    assert result.exit_code != 0
    assert "owned by initialized page" in result.output
    after = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (layer / "registry.json").exists()


def test_customize_continues_when_the_project_root_is_the_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    themed = runner.invoke(interact.cli, ["customize", "theme"])
    assert themed.exit_code == 0, themed.output
    initialized = runner.invoke(interact.cli, ["page", "init", "."])
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

    scaffold = runner.invoke(
        interact.cli,
        ["customize", "widget", "lf-after-init", "--upgrade"],
    )

    assert scaffold.exit_code == 0, scaffold.output
    assert page_theme.read_bytes() == before_theme
    assert page_registry.read_bytes() == before_registry
    assert {
        path.name: path.read_bytes()
        for path in (tmp_path / "widgets").iterdir()
        if path.is_file()
    } == before_widgets
    source = tmp_path / ".leaf"
    assert (source / "widgets" / "lf-after-init.js").is_file()

    revendored = runner.invoke(interact.cli, ["page", "init", "."])

    assert revendored.exit_code == 0, revendored.output
    assert "lf-after-init" in json.loads(page_registry.read_text())
    assert (tmp_path / "widgets" / "lf-after-init.js").is_file()


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
    initialized = CliRunner().invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    assert interact.initialized_page_owning(page / name) == page
    assert interact.initialized_page_owning(page / ".leaf" / name) is None


@pytest.mark.parametrize(
    "directory", ("versions", "runtime", "widgets", "vendor", "media")
)
def test_initialized_page_owns_declared_directory_trees(
    tmp_path, monkeypatch, directory
):
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output

    assert interact.initialized_page_owning(page / directory / "future") == page


def test_customize_allows_a_symlink_managed_external_layer(tmp_path, monkeypatch):
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

    result = CliRunner().invoke(
        interact.cli,
        ["customize", "widget", "lf-managed", "--upgrade"],
    )

    assert result.exit_code == 0, result.output
    assert (layer / "theme.css").is_symlink()
    assert (layer / "registry.json").is_symlink()
    assert (layer / "widgets").is_symlink()
    assert "lf-managed {" in theme.read_text()
    assert "lf-managed" in json.loads(registry.read_text())
    assert (widgets / "lf-managed.js").is_file()


def test_replace_files_rejects_case_aliased_future_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(interact, "_filesystem_case_sensitive", lambda path: False)
    first = tmp_path / "Result.css"
    second = tmp_path / "rESULT.CSS"

    with pytest.raises(SystemExit, match="resolve to the same target"):
        interact.replace_files([(first, b"first", False), (second, b"second", False)])

    assert not first.exists() and not second.exists()


def test_customize_widget_names_a_wrong_kind_lower_layer(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    user_layer = config / "leaf"
    user_layer.write_text("not a directory")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)

    result = CliRunner().invoke(interact.cli, ["customize", "widget", "lf-clear-error"])

    assert result.exit_code != 0
    assert f"{user_layer} must be a directory" in result.output
    assert user_layer.read_text() == "not a directory"
    assert not (project / ".leaf").exists()


@pytest.mark.parametrize(
    ("relative", "directory"),
    [("vendor", False), ("leaf.js", True)],
)
def test_customize_widget_validates_the_complete_selected_layer(
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

    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-complete-layer", "--upgrade"]
    )

    assert result.exit_code != 0
    assert str(malformed) in result.output
    assert not (layer / "theme.css").exists()
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_customize_refuses_a_broken_lower_alias_to_its_planned_target(
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

    result = CliRunner().invoke(interact.cli, ["customize", "theme"])

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    assert user_theme.is_symlink() and not user_theme.exists()
    assert not project_theme.exists()


def test_customize_refuses_an_existing_member_aliased_to_another_scope(
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

    result = CliRunner().invoke(interact.cli, ["customize", "theme"])

    assert result.exit_code != 0
    assert "overlaps another layer source" in result.output
    assert project_module.is_symlink()
    assert user_module.read_text() == "// shared source\n"
    assert not (project / ".leaf" / "theme.css").exists()


@pytest.mark.parametrize("user", [False, True], ids=["project", "user"])
def test_init_refuses_to_overwrite_a_customization_source(tmp_path, monkeypatch, user):
    project = tmp_path / "project"
    project.mkdir()
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.chdir(project)
    runner = CliRunner()
    args = ["customize", "widget", "lf-safe-source", "--upgrade"]
    if user:
        args.append("--user")
    scaffold = runner.invoke(interact.cli, args)
    assert scaffold.exit_code == 0, scaffold.output

    layer = config / "leaf" if user else project / ".leaf"
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert before

    result = runner.invoke(interact.cli, ["page", "init", str(layer)])

    assert result.exit_code != 0
    assert "customization source" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_overlapping_customization_scopes(tmp_path, monkeypatch):
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

    result = CliRunner().invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "layer scopes must be separate" in result.output
    after = {
        path.relative_to(user): path.read_bytes()
        for path in user.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not page.exists()


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

    result = CliRunner().invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "layer scopes must be separate" in result.output
    assert theme.read_bytes() == before
    assert not page.exists()


def test_init_refuses_to_write_inside_a_customization_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    scaffold = runner.invoke(
        interact.cli, ["customize", "widget", "lf-safe-source", "--upgrade"]
    )
    assert scaffold.exit_code == 0, scaffold.output
    layer = tmp_path / ".leaf"
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(interact.cli, ["page", "init", str(layer / "widgets")])

    assert result.exit_code != 0
    assert "inside the widget-layer customization source" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_init_refuses_a_case_aliased_page_inside_a_customization_source(
    tmp_path, monkeypatch
):
    project = tmp_path / "Project"
    project.mkdir()
    alias = case_alias(project)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.chdir(project)
    runner = CliRunner()
    scaffold = runner.invoke(
        interact.cli,
        ["customize", "widget", "lf-case-source", "--upgrade"],
    )
    assert scaffold.exit_code == 0, scaffold.output
    layer = project / ".leaf"
    page = alias / ".LEAF" / "WIDGETS"
    assert page.samefile(layer / "widgets")
    before = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "inside the widget-layer customization source" in result.output
    after = {
        path.relative_to(layer): path.read_bytes()
        for path in layer.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_customize_widget_validates_every_target_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    theme = layer / "theme.css"
    theme.mkdir(parents=True)
    sentinel = theme / "keep.txt"
    sentinel.write_text("keep")

    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-no-partial", "--upgrade"]
    )

    assert result.exit_code != 0
    assert "theme.css must be a file" in result.output
    assert sentinel.read_text() == "keep"
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_customize_widget_refuses_malformed_css_before_writing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    theme = layer / "theme.css"
    theme.write_text(".bad { color red; }\n")

    result = CliRunner().invoke(
        interact.cli, ["customize", "widget", "lf-no-broken-css", "--upgrade"]
    )

    assert result.exit_code != 0
    assert f"{theme} syntax error" in result.output
    assert theme.read_text() == ".bad { color red; }\n"
    assert not (layer / "registry.json").exists()
    assert not (layer / "widgets").exists()


def test_init_reads_the_complete_layer_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "registry.json").write_text(
        json.dumps(
            {"lf-bad-theme": interact.custom_widget_entry("lf-bad-theme", False)}
        )
    )
    (layer / "theme.css").write_bytes(b"\xff")

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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

    result = CliRunner().invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code != 0
    assert "theme.css syntax error" in result.output
    assert list(page.iterdir()) == []


def test_page_commands_do_not_mint_the_successful_init_marker(tmp_path):
    """An existing directory becomes a page only through a completed page init."""
    page = tmp_path / "prepared-page"
    page.mkdir()

    result = CliRunner().invoke(interact.cli, ["server", "stop", str(page)])

    assert result.exit_code != 0
    assert "page init" in result.output
    assert list(page.iterdir()) == []


def test_hooks_do_not_mint_the_successful_init_marker_for_a_deleted_page(page_dir):
    """An external claim does not turn a deleted page back into initialized state."""
    record_claim(page_dir, id="stale-session")
    shutil.rmtree(page_dir)
    page_dir.mkdir()

    interact.cmd_hook({"hook_event_name": "Stop", "session_id": "stale-session"})

    assert list(page_dir.iterdir()) == []


def test_a_failed_fresh_commit_does_not_mark_the_page_initialized(
    tmp_path, monkeypatch
):
    """The stable log marks a completed init, not one that failed while committing."""
    monkeypatch.chdir(tmp_path)
    page = tmp_path / "interrupted-page"
    original_replace_files = interact.replace_files

    def fail_layer_commit(files):
        if any(path.name == "registry.json" for path, _, _ in files):
            raise OSError("layer commit failed")
        return original_replace_files(files)

    monkeypatch.setattr(interact, "replace_files", fail_layer_commit)

    with pytest.raises(OSError, match="layer commit failed"):
        interact.cmd_init(page)

    assert not (page / "comments.jsonl").exists()


def test_init_refuses_malformed_layer_css_before_revendoring(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }
    theme = tmp_path / ".leaf" / "theme.css"
    theme.parent.mkdir(parents=True)
    theme.write_text(".bad { color red; }\n")

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
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
        json.dumps(
            {"lf-new-shape": interact.custom_widget_entry("lf-new-shape", False)}
        )
    )

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    original = tmp_path / f"original-{sub}"
    (page / sub).rename(original)
    outside = tmp_path / f"outside-{sub}"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("do not prune or replace files outside the page")
    (page / sub).symlink_to(outside, target_is_directory=True)

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    destination = page / destination_relative
    if destination.is_dir():
        (destination / "keep-source.txt").write_text(
            "stale pruning must not delete a customization source"
        )

    source = tmp_path / ".leaf" / source_relative
    source.parent.mkdir(parents=True)
    source.symlink_to(destination, target_is_directory=destination.is_dir())
    before = {
        path.relative_to(page): path.read_bytes()
        for path in page.rglob("*")
        if path.is_file()
    }

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
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

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

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
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    source = page / f"theme.css.{os.getpid()}.0.tmp"
    source.write_text(":root { --accent: rebeccapurple; }\n")
    layer = tmp_path / ".leaf"
    layer.mkdir(parents=True)
    (layer / "theme.css").symlink_to(source)

    result = runner.invoke(interact.cli, ["page", "init", str(page)])

    assert result.exit_code == 0, result.output
    assert source.read_text() == ":root { --accent: rebeccapurple; }\n"
    assert (layer / "theme.css").is_symlink()


@pytest.mark.parametrize(
    ("relative", "directory"),
    [
        ("theme.css", True),
        ("registry.json", True),
        ("widgets", False),
        ("vendor", False),
    ],
)
def test_init_refuses_wrong_kind_customization_paths(
    tmp_path, monkeypatch, relative, directory
):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".leaf" / relative
    path.parent.mkdir(parents=True)
    if directory:
        path.mkdir()
    else:
        path.write_text("not a directory")

    result = CliRunner().invoke(interact.cli, ["page", "init", str(tmp_path / "page")])

    assert result.exit_code != 0
    assert str(path) in result.output


def test_init_refuses_an_upgraded_custom_widget_without_its_module(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    scaffold = runner.invoke(interact.cli, ["customize", "widget", "lf-unfinished"])
    assert scaffold.exit_code == 0, scaffold.output

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-unfinished"]["x-upgrade"] = True
    registry["lf-unfinished"]["x-verbatim"] = True
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(interact.cli, ["page", "init", str(tmp_path / "page")])
    assert result.exit_code != 0
    assert "widgets/lf-unfinished.js" in result.output


def test_init_refuses_a_registry_example_that_violates_its_schema(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    scaffold = runner.invoke(interact.cli, ["customize", "widget", "lf-toned-note"])
    assert scaffold.exit_code == 0, scaffold.output

    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    entry = registry["lf-toned-note"]
    entry["properties"]["tone"] = {"enum": ["quiet", "loud"]}
    entry["required"].append("tone")
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(interact.cli, ["page", "init", str(tmp_path / "page")])

    assert result.exit_code != 0
    assert "<lf-toned-note> x-example is invalid" in result.output
    assert "'tone' is a required property" in result.output


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
    scaffold = runner.invoke(interact.cli, ["customize", "widget", "lf-toned-note"])
    assert scaffold.exit_code == 0, scaffold.output
    registry_path = tmp_path / ".leaf" / "registry.json"
    registry = json.loads(registry_path.read_text())
    registry["lf-toned-note"]["x-example"] = example
    registry_path.write_text(json.dumps(registry))

    result = runner.invoke(interact.cli, ["page", "init", str(tmp_path / "page")])

    assert result.exit_code != 0
    assert "<lf-toned-note> x-example is invalid" in result.output
    assert message in result.output


def test_revendoring_removes_files_the_layer_retired(page_dir):
    stale = page_dir / "widgets" / "lf-retired.js"
    stale.write_text("// no longer in any layer")
    result = CliRunner().invoke(interact.cli, ["page", "init", str(page_dir)])
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

    retired = CliRunner().invoke(interact.cli, ["page", "init", str(page_dir)])

    assert retired.exit_code == 0, retired.output
    assert not stale.is_symlink()

    source = page_dir.parent / ".leaf" / sub / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("// returned\n")
    returned = CliRunner().invoke(interact.cli, ["page", "init", str(page_dir)])

    assert returned.exit_code == 0, returned.output
    assert stale.is_file() and not stale.is_symlink()
    assert stale.read_text() == "// returned\n"
    assert source.read_text() == "// returned\n"
