"""Shared fixtures and assertions for the Leaf integration modules.

Run from the repo root:

    uv run pytest tests
"""

import errno
import fcntl
import http.client
import http.cookiejar
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import anyio
import pytest
from click.testing import CliRunner
from conftest import LEAF_COMMAND
from leaf import cli as cli_model
from leaf import event_log as events_model
from leaf import events as event_folds_model
from leaf import files as files_model
from leaf import host as host_model
from leaf import hosting as hosting_model
from leaf import layer as layer_model
from leaf import passages as passages_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import structure as structure_model
from leaf import vendoring as vendoring_model
from leaf.registry import storage as registry_storage_model
from leaf.served_state import page as served_page
from leaf.validation import instances as validation_model

ROOT = Path(__file__).parent.parent
# The checkout and the payload a host installs are one tree now; PLUGIN_ROOT still
# names the role a path plays — "what a host runs" — for the tests built on that.
PLUGIN_ROOT = ROOT
# The payload's manifests, hooks and launcher hang off PLUGIN_ROOT; the six product parts
# sit one skill directory below it. Both are wanted often enough to be worth naming, and
# spelled by hand the two are one plausible typo apart — a glob a level short matches
# nothing and reports nothing.
SKILL_ROOT = PLUGIN_ROOT / "skills" / "leaf"
COMMAND_HUB_PACKAGE = SKILL_ROOT / "packages" / "command-hub"
# The complete shipped vocabulary, in the order `page init` composes it for an example.
# Read from examples/layer.json rather than listed here, because a floor that names its
# own packages stops covering the next one: lf-diagram and lf-diff left the default
# package for `diagram` and `diff` and would have dropped out of every sweep silently,
# and pr-review's two widgets had never been in one.
SHIPPED_PACKAGES = [
    schema_model.ASSETS,
    schema_model.DEFAULT_PACKAGE,
    *(
        SKILL_ROOT / "packages" / name
        for name in json.loads(
            (ROOT / "examples" / "layer.json").read_text(encoding="utf-8")
        )
    ),
]
COMMAND_SUBJECTS = (
    '<lf-agent id="worker" state="waiting" on="goal"><strong>Worker</strong>'
    '<lf-worktree id="tree" source="project-worktrees"></lf-worktree>'
    "</lf-agent>"
)

# No path work: `leaf` is installed into the environment this interpreter runs
# in, so a child of it imports the same modules the tests do.
PROBE_BOOTSTRAP = """\
import contextlib
import os
from pathlib import Path
import sys

from leaf import cli as cli_model
"""


def append_command(page_dir, command):
    """Seed a widget command through the real transaction's admission step.

    A test of raw storage or retired vocabulary passes an explicitly admitted
    event, including meaning, to event_log.append_event instead.
    """
    with service_model.PageTransaction(page_dir) as page:
        return page.append_event(
            command, registry_storage_model.require_registry(page_dir)
        )


def run_async(entry):
    """Run an async entry point on a thread of this test's own.

    Playwright's sync API drives an asyncio loop and holds it running in the thread that
    opened a browser for the whole life of `sync_playwright()`, and the `browser` fixture
    is session-scoped per xdist worker. So `anyio.run` in a worker that has already run a
    browser test raises "Already running asyncio in this thread", and the same call in a
    worker that has not passes — leaving the scheduler to decide whether an MCP test can
    start a loop at all. A thread with no loop on it answers for every schedule.
    """
    with ThreadPoolExecutor(max_workers=1) as loop_thread:
        return loop_thread.submit(lambda: anyio.run(entry)).result()


def spawn_probe(spawn, page_dir, body, **environment):
    """Run a deterministic race seam in an isolated Leaf application process."""
    env = {name: str(value) for name, value in environment.items()}
    return spawn(
        [sys.executable, "-c", PROBE_BOOTSTRAP + body],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ | {"PAGE": str(page_dir)} | env,
    )


STATED_TIMEOUT = 10
"""How long a pure-Python wait gives another thread or process to state its fact.

The deadline separates a product that never states the fact from a machine that
has not reached it yet, so it is generous rather than tight. Two workers share
one runner's cores with a browser, and a stretch of ordinary work there runs
many times slower than it does on an unloaded host: a wait sized as a small
multiple of the unloaded duration reddens `main` on the runs where the other
worker happens to be driving Chrome. `SERVED_TIMEOUT_MS` is the browser side's
counterpart, more generous again for the work a page does."""


def wait_for(read, accepts, *, failure: str, timeout: float = STATED_TIMEOUT):
    """Return the first accepted reading, or fail with the last one observed."""
    deadline = time.monotonic() + timeout
    while True:
        reading = read()
        if accepts(reading):
            return reading
        if time.monotonic() >= deadline:
            pytest.fail(f"{failure}; last reading was {reading!r}")
        time.sleep(0.05)


@contextmanager
def running_http_server(httpd):
    """Serve an HTTP fixture and close every thread and socket it creates."""
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive(), "the fixture HTTP server did not stop"


def pytest_configure(config):
    """Keep a nonignored basetemp out of the candidate plugin payload."""
    given = config.option.basetemp
    if given is None:
        return
    given = Path(given).resolve()
    if not given.is_relative_to(PLUGIN_ROOT.resolve()):
        return
    ignored = subprocess.run(
        ["git", "-C", str(PLUGIN_ROOT), "check-ignore", "-q", str(given)],
        check=False,
    )
    if ignored.returncode != 0:
        raise pytest.UsageError(
            f"--basetemp={given} is inside the checkout and git does not ignore "
            "it, so this run's temporary files would count as shipped payload. "
            "Drop the flag — pytest puts the basetemp under $TMPDIR already — or "
            "name a path outside the checkout."
        )


def shipped_payload():
    """Tracked and unignored candidate files a completed change would ship."""
    listed = subprocess.run(
        [
            "git",
            "-C",
            str(PLUGIN_ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        path
        for relative in listed.splitlines()
        if (path := PLUGIN_ROOT / relative).exists()
    ]


def install_payload(destination):
    """Copy the candidate payload the way a host installs the committed tree."""
    for path in shipped_payload():
        target = destination / path.relative_to(PLUGIN_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            target.symlink_to(os.readlink(path))
        else:
            shutil.copy2(path, target)
    return destination


PAGE = """<!doctype html>
<html lang="en">
<head>
<title>t</title>
</head>
<body>
<main>
<section id="plan">
  <h2>Plan</h2>
  <p>The cutoff lives in <a href="https://example.test/jobs/backfill.py#L88"><code>jobs/backfill.py:88</code></a>.</p>
  <lf-ask id="plan-choice-decision">
    <h3>Which plan should lead?</h3>
    <lf-options>
      <lf-option id="flag-first"><lf-chip>effort: low</lf-chip><lf-chip>risk: med</lf-chip>
        <strong>Flag first</strong> Ship dark.
      </lf-option>
      <lf-option id="backfill-first"><lf-chip>effort: med</lf-chip><lf-chip>risk: low</lf-chip>
        <strong>Backfill first</strong> Verify, then flip. <em>My take: do this first.</em>
      </lf-option>
    </lf-options>
  </lf-ask>
  <lf-diagram id="flow"><pre>
graph LR
  A --> B
  </pre></lf-diagram>
</section>
</main>
</body>
</html>
"""


# The fixture's own layer. PAGE holds an lf-diagram, and the interact suite borrows
# lf-diagram and lf-diff declarations out of the vendored registry, so the selection
# names the packages those three now travel in. The template cache is keyed by this
# same list, so a page built for one selection is never handed to another.
PAGE_PACKAGES = ("command-hub", "diagram", "diff")


@pytest.fixture
def page_dir(tmp_path, monkeypatch, initialized_page):
    """A mutable page with the default, Command Hub, diagram and diff vocabularies."""
    monkeypatch.chdir(tmp_path)  # resolve fixture package paths
    d = tmp_path / "page"

    def initialize(template):
        result = CliRunner().invoke(
            cli_model.cli,
            [
                "page",
                "init",
                *(arg for name in PAGE_PACKAGES for arg in ("--package", name)),
                str(template),
            ],
        )
        assert result.exit_code == 0, result.output
        (template / "index.html").write_text(PAGE)

    initialized_page("-".join(PAGE_PACKAGES), d, initialize)
    return d


def check(d):
    return CliRunner().invoke(cli_model.cli, ["version", "check", str(d)])


def declare_data_input(
    page_dir,
    source,
    schema,
    *,
    contract="test-data",
    tag="lf-test-data",
    input_name="data",
    guidance=None,
    snapshot=False,
    activate=True,
):
    """Add one typed widget input and bind it in the mutable source."""
    registry_path = page_dir / "registry.json"
    registry = json.loads(registry_path.read_text())
    declaration = {"description": "Test data contract.", "schema": schema}
    if guidance:
        declaration["guidance"] = guidance
    registry["$data"]["contracts"][contract] = declaration
    registry[tag] = {
        "description": "A test widget with one external-data input.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
            "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
            **(
                {"snapshot": {"type": "string", "pattern": "^[1-9][0-9]*$"}}
                if snapshot
                else {}
            ),
        },
        "required": ["id", "source"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {
            input_name: {
                "contract": contract,
                "source": "source",
                **({"snapshot": "snapshot"} if snapshot else {}),
            }
        },
        "x-upgrade": False,
    }
    registry_path.write_text(json.dumps(registry))
    source_path = page_dir / "index.html"
    html = source_path.read_text()
    source_path.write_text(
        html.replace(
            "</main>",
            f'<{tag} id="test-data" source="{source}"></{tag}>\n</main>',
        )
    )
    if activate:
        activated = revisioning_model.activate_source(
            page_dir, events_model.read_events(page_dir)
        )
        assert activated.error is None


def publish(d, version=1):
    """Append the note event that makes a version the user-seen baseline:
    `version check` compares against the last *published* version, and an action
    can only ever be made against one the server exposed."""
    activated = revisioning_model.activate_source(
        d, events_model.read_events(d), allow_transition=True
    )
    assert activated.error is None and activated.revision is not None
    events_model.append_event(
        d,
        {
            "kind": "note",
            "author": "agent",
            "version": version,
            "revision": activated.revision,
            "text": "published",
        },
    )


def stamp(d, text="stamped", completes=()):
    """Stamp the fixture's canonical authored source through the CLI."""
    return CliRunner().invoke(
        cli_model.cli,
        [
            "version",
            "stamp",
            str(d),
            "--text",
            text,
            *(arg for widget in completes for arg in ("--completes", widget)),
        ],
    )


def page_state(d):
    events = events_model.read_events(d)
    return served_page.full_state(d, events)


def record_claim(page, harness="claude-code", **fields):
    """Write the canonical claim shape for lifecycle fixtures.

    `harness` is checked against Leaf's own table, so a fixture cannot record a
    name `take_claim` would never write."""
    record = {
        "page": str(page.resolve()),
        "id": "s1",
        "harness": host_model.HARNESSES[harness].name,
        "pid": os.getpid(),
        "agent": "Claude",
        "cwd": str(Path.cwd()),
        "ts": "t",
        "released": None,
        "turn": "turn-1",
        "turn_closed": None,
        **fields,
    }
    # A lifetime is one key, the way `take_claim` spreads it: a claim naming a job
    # record or resting on activity states no pid, and a reader that saw one there
    # would be reading a fixture rather than a shape leaf writes.
    if fields.keys() & {"job", "activity"}:
        record.pop("pid", None)
    path = service_model.claim_path(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    files_model.write_json(path, record)
    return record


def live_versions(d):
    events = events_model.read_events(d)
    return files_model.published_versions(d, events)


def fragment_errors(html, registry):
    parser = structure_model.SourceDocument(html)
    return validation_model.fragment_errors(parser, registry)


def case_alias(path):
    alias = path.with_name(path.name.swapcase())
    if not alias.exists() or not path.samefile(alias):
        pytest.skip("requires a case-insensitive filesystem")
    return alias


SUGGESTION = """<lf-suggestion id="sug-refill">
  <lf-old><p id="refill-rule">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="refill-camera">Refill when the camera shows it half-empty.</p></lf-new>
</lf-suggestion>
"""


def before_choice(page, markup):
    """Insert a fixture before the base page's titled choice Ask."""
    start = '<lf-ask id="plan-choice-decision">'
    return page.replace(start, markup + start)


def suggest(page_dir, markup=SUGGESTION):
    """Write and publish v1 carrying a suggestion to check against."""
    (page_dir / "index.html").write_text(before_choice(PAGE, markup))
    publish(page_dir)


def decide(page_dir, outcome, widget="sug-refill"):
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": widget,
            "action": outcome,
            "detail": {},
        },
    )


def _decided(page_dir, words):
    """v1 carrying a draft the user has since rewritten, and the log that
    says so. Whatever v2 does about it, `version check` is what has to notice."""
    (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            f'<h2>Plan</h2><lf-draft id="d1"><pre>{words}</pre></lf-draft>',
        )
    )
    publish(page_dir)
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": files_model.latest_revision(page_dir),
            "widget": "d1",
            "action": "edit",
            "detail": {"text": "Cut the flag; backfill first."},
        },
    )
    return lambda words, attrs="": (page_dir / "index.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            f'<h2>Plan</h2><lf-draft id="d1"{attrs}><pre>{words}</pre></lf-draft>',
        )
    )


def _tasks(status, extra=""):
    """A one-task tree whose task carries the given status and extra attributes."""
    return (
        '<lf-tasks id="tree">'
        f'<lf-task id="t-parser" status="{status}"{extra}><strong>Parser</strong></lf-task>'
        "</lf-tasks>"
    )


def _tasks_version(page_dir, status, extra=""):
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _tasks(status, extra))
    )


def _report(page_dir, *args):
    return CliRunner().invoke(cli_model.cli, ["report", str(page_dir), *args])


def _board(todo, done):
    """A two-column board, each column given its cards as (id, attrs, title)."""

    def card(c):
        return f'<lf-card id="{c[0]}"{c[1]}><strong>{c[2]}</strong></lf-card>'

    return (
        '<lf-board id="b1">'
        f'<lf-column id="c-todo" label="Todo">{"".join(map(card, todo))}</lf-column>'
        f'<lf-column id="c-done" label="Done">{"".join(map(card, done))}</lf-column>'
        "</lf-board>"
    )


X = ("card-x", "", "Guard the delete")
Y = ("card-y", "", "Wire the importer")
OPTIONS = """<lf-ask id="g1-decision">
  <h3>Which migration should lead?</h3>
  <lf-options id="g1" choose>
    <lf-option id="o-shim"{a}>{chip}<strong>Shim it</strong> {shim}</lf-option>
    <lf-option id="o-stage"{b}><strong>Migrate in stages</strong> {stage}</lf-option>
  </lf-options>
</lf-ask>"""


def state_json(d):
    result = CliRunner().invoke(cli_model.cli, ["page", "state", str(d)])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


# One comment and two decisions on one suggestion — the whole vocabulary these
# threads are read out of. `REJECT` is spelt off `ACCEPT` because the two answering
# the same widget is the entire premise: a decision supersedes the one before it on
# the widget that sent it, the way a second `move` supersedes the first on one card.
COMMENT = {"kind": "comment", "id": "c1", "author": "user", "text": "cameras are flaky"}
ACCEPT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "sug-a",
    "action": "accept",
    "detail": {"resolves": "c1"},
    "meaning": {
        "document": {"kind": "page", "revision": 1},
        "coordinate": ["sug-a", "sug-a", "settlement"],
        "depends": ["sug-a"],
        "answer": "c1",
    },
}
REJECT = {
    **ACCEPT,
    "action": "reject",
    "detail": {},
    "meaning": {**ACCEPT["meaning"], "answer": None},
}
RESOLVE = {"kind": "resolve", "author": "user", "parent": "c1"}


def logged(page_dir, *events):
    """Append these events, then read the threads back the way the CLI does — off
    the whole log and the page the decisions were folded over. Copied in, because
    `append_event` stamps an id onto what it is handed and these are constants."""
    activated = revisioning_model.activate_source(page_dir, [])
    assert activated.error is None and activated.revision == 1
    for event in events:
        event = dict(event)
        if event["kind"] == "action":
            event["meaning"] = {
                **event["meaning"],
                "coordinate": [event["widget"], event["widget"], "settlement"],
                "depends": [event["widget"]],
            }
        events_model.append_event(page_dir, event)
    return event_folds_model.build_threads(
        events_model.read_events(page_dir),
        passages_model.enclosing_ids(structure_model.parse_revision(page_dir, 1)),
    )


def assert_revendor_serializes_writer(page_dir, monkeypatch, kind, write):
    """Hold one admitted writer at append and prove re-vendor cannot pass it."""
    entering = threading.Event()
    resume = threading.Event()
    checked_without_writer = threading.Event()
    finish_vendoring = threading.Event()
    original_append_event = service_model.PageTransaction.append_event
    original_composed_sheets = layer_model.composed_sheets

    def held_append_event(page, event, registry=None):
        if event.get("kind") == kind:
            entering.set()
            assert resume.wait(timeout=10), "re-vendor never observed the writer"
        return original_append_event(page, event, registry)

    def held_composed_sheets(sources):
        checked_without_writer.set()
        assert finish_vendoring.wait(timeout=10), "the writer never resumed"
        return original_composed_sheets(sources)

    def init_result():
        try:
            vendoring_model.cmd_init(page_dir, selected=(*PAGE_PACKAGES, "./.leaf"))
        except SystemExit as error:
            return str(error)
        return None

    monkeypatch.setattr(
        service_model.PageTransaction, "append_event", held_append_event
    )
    monkeypatch.setattr(layer_model, "composed_sheets", held_composed_sheets)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writing = executor.submit(write)
        assert entering.wait(timeout=10), f"{kind} never passed old-layer validation"
        vendoring = executor.submit(init_result)
        passed_check = checked_without_writer.wait(timeout=2)
        # Release either acquisition order without relying on a scheduler: a
        # broken re-vendor may already own the page lease at composed_sheets.
        finish_vendoring.set()
        resume.set()
        written = writing.result(timeout=10)
        refusal = vendoring.result(timeout=10)

    assert not passed_check, f"re-vendor passed a validated {kind} writer"
    assert refusal is not None
    return written, refusal


def _mutated_registry_check(page_dir, mutate):
    registry = json.loads((page_dir / "registry.json").read_text())
    mutate(registry)
    (page_dir / "registry.json").write_text(json.dumps(registry))
    return check(page_dir)


def _report_body_record(registry):
    registry["lf-task"]["x-report"]["status"]["record"] = {
        "kind": "body",
        "value": "status",
    }


def _report_no_record(registry):
    del registry["lf-task"]["x-report"]["status"]["record"]


def _report_undeclared_attr(registry):
    registry["lf-task"]["x-report"]["status"]["record"]["attr"] = "phase"


def _report_says_attr(registry):
    task = registry["lf-task"]
    task["required"].append("owner")
    task["x-says"] = {"owner": "before"}
    task["x-report"]["status"] = {
        "detail": {
            "type": "object",
            "properties": {"owner": {"type": "string"}},
            "required": ["owner"],
            "additionalProperties": False,
        },
        "facet": "status",
        "unit": "widget",
        "record": {"kind": "value", "attr": "owner", "value": "owner"},
    }


def _report_detail_drift(registry):
    registry["lf-task"]["x-report"]["status"]["detail"]["properties"]["status"] = {
        "type": "string"
    }


def _report_without_overruled(registry):
    del registry["lf-task"]["properties"]["overruled"]


def _report_without_upgrade(registry):
    registry["lf-task"]["x-upgrade"] = False


def _body_record_with_prose(registry):
    registry["lf-draft"]["x-content"] = "markup"


def _body_record_with_nested_widget(registry):
    registry["lf-option"]["x-owners"].append("lf-draft")


# A holder/slot family core has never heard of. <lf-trial> is decided by `adopt`
# or `shelve`: `adopt` retires the <lf-current> it would replace, `shelve` the
# <lf-proposed> it offers, and taking an undecided one back leaves the page where
# a `shelve` would. <lf-pilot> holds the same <lf-proposed> under the same verb and
# declares no withdrawal at all — the pair, not the slot, is what the licensing is
# keyed on. Three instances, because a page needs one to decide, one to withdraw
# and one that can't be, and a decision is in the log for good once it is made.
TRIAL_CACHE = """<lf-trial id="trial-cache">
  <lf-current id="cache-now"><p id="cache-daily">The cache is rebuilt nightly.</p></lf-current>
  <lf-proposed><p id="cache-hourly">Rebuild the cache each hour.</p></lf-proposed>
</lf-trial>"""
TRIAL_LOG = """<lf-trial id="trial-log">
  <lf-current><p id="log-daily">Logs roll over at midnight.</p></lf-current>
  <lf-proposed><p id="log-hourly">Roll logs over each hour.</p></lf-proposed>
</lf-trial>"""
PILOT_PURGE = """<lf-pilot id="pilot-purge">
  <lf-proposed><p id="purge-weekly">Purge the dead-letter queue weekly.</p></lf-proposed>
</lf-pilot>"""
ADOPTED = '<p id="cache-hourly">Rebuild the cache each hour.</p>'
SHELVED = '<p id="log-daily">Logs roll over at midnight.</p>'


def trial_version(*markup):
    return PAGE.replace("<lf-options>", "\n".join([*markup, "<lf-options>"]))


@pytest.fixture
def trial_page(tmp_path, monkeypatch):
    """A page whose vocabulary a project layer widened with holder/slot families
    of its own. Declared in `.leaf/` and vendored by `page init` — the door the
    shipped suggestion comes through too, so what the licensing does here is what
    a project gets rather than what a fixture arranged."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    created = runner.invoke(cli_model.cli, ["package", "init", ".leaf"])
    assert created.exit_code == 0, created.output
    widgets = (
        ("lf-trial", True),
        ("lf-pilot", True),
        ("lf-current", False),
        ("lf-proposed", False),
    )
    for tag, upgrade in widgets:
        add_test_widget(tmp_path / ".leaf", tag, upgrade)

    source = tmp_path / ".leaf" / "registry.json"
    declarations = json.loads(source.read_text())
    verb = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "settlement",
        "unit": "widget",
    }
    for tag, state, example in (
        ("lf-trial", ("adopt", "shelve"), TRIAL_CACHE),
        ("lf-pilot", ("run", "shelve"), PILOT_PURGE),
    ):
        declarations[tag] |= {
            "x-content": "members",
            "x-state": {name: dict(verb) for name in state},
            "x-example": example,
        }
        declarations[tag]["properties"]["restated"] = {"type": "boolean"}
        del declarations[tag]["x-verbatim"]  # a module renders the slots
    # Only the trial says what taking it back would mean.
    declarations["lf-trial"]["x-withdrawn-as"] = "shelve"
    for tag, owners, outcome in (
        ("lf-current", ["lf-trial"], "adopt"),
        ("lf-proposed", ["lf-trial", "lf-pilot"], "shelve"),
    ):
        declarations[tag] |= {"x-owners": owners, "x-retired-when": outcome}
        del declarations[tag]["x-example"]  # a slot has no standing of its own
        del declarations[tag]["required"]  # nor an id it must carry
    source.write_text(json.dumps(declarations))

    page = tmp_path / "page"
    # The version is built out of PAGE, which holds an lf-diagram; the project package
    # under test is explicitly selected beside it.
    initialized = runner.invoke(
        cli_model.cli,
        ["page", "init", "--package", "diagram", "--package", "./.leaf", str(page)],
    )
    assert initialized.exit_code == 0, initialized.output
    (page / "index.html").write_text(trial_version(TRIAL_CACHE, TRIAL_LOG, PILOT_PURGE))
    assert check(page).exit_code == 0, check(page).output
    publish(page)
    return page


def styled(css, body='<svg width="10" height="10"></svg>'):
    """PAGE with `css` as its own stylesheet and `body` after the first heading."""
    return PAGE.replace("</head>", f"<style>{css}</style></head>").replace(
        "<h2>Plan</h2>", f"<h2>Plan</h2>{body}"
    )


# The key is the machine's and minted on the first serve; fixed here so a test
# can build a URL for a server it did not start.
TOKEN = "test-page-key"


@pytest.fixture
def server(page_dir):
    """A real HTTP server over the page directory, on an ephemeral port."""
    temporary = hosting_model.TemporaryPageServer(page_dir, token=TOKEN).start()
    yield temporary.origin
    temporary.close()


@pytest.fixture
def socket_dir():
    """A directory short enough to hold a Unix socket, gone when the test ends.

    `sun_path` is 104 bytes, and pytest spends most of them before the test's own
    files begin: a socket under `tmp_path` is refused outright, with `AF_UNIX path
    too long` naming the length rather than the directory that made it. So the
    sockets go under a short root — and, because that root is outside every sweep
    the run makes, they are this fixture's to remove rather than the test's.
    """
    directory = Path(tempfile.mkdtemp(prefix="lf", dir="/tmp"))
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


def fetch(url, data=None, token=TOKEN, layer=None, headers=None):
    """A request arriving the way a user's does: the key in the query, and a
    cookie jar to carry it onward. The live root and the runtime's later query-less
    requests are authorized by the cookie that first keyed arrival set. Pass token=None
    for the reader who never had the link; headers carry route-specific metadata."""
    if token:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"t": token})
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        request_headers = dict(headers or {})
        if data is not None and (
            token or urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("t")
        ):
            if layer is None:
                state_url = (
                    urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
                )
                with opener.open(state_url) as state:
                    layer = json.loads(state.read())["layer"]["generation"]
            request_headers["Leaf-Layer"] = layer
        request = urllib.request.Request(url, data=data, headers=request_headers)
        with opener.open(request) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


HELD_LEASES = []


def serving(directory, port: int, lifetime: str = "standing") -> None:
    """Hold the same contentless lease as a live `server run`."""
    directory.mkdir(parents=True, exist_ok=True)
    service = {
        "host": "127.0.0.1",
        "bind": "127.0.0.1",
        "port": port,
        "enabled": True,
        "lifetime": lifetime,
    }
    files_model.write_json(directory / "service.json", service)
    handle = open(directory / "server.lock", "a+b")  # noqa: SIM115 - test lease
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    HELD_LEASES.append(handle)


def available_loopback_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def fifo_writer(path: Path, failure: str) -> int:
    """Open a nonblocking writer once a child is waiting on this FIFO."""
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            return os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as error:
            if error.errno != errno.ENXIO:
                raise
            time.sleep(0.05)
    path.unlink()
    pytest.fail(failure)


@pytest.fixture(autouse=True)
def _no_page_outlives_its_test(tmp_path, isolated_session):
    """Nothing the suite put up is still up when the test that put it there ends.

    The suite's own pretend servers go first. They do not run the cooperative
    service watcher, so their leases are released before the real-server sweep.

    Then every page under the directories a test can write to. A server `server
    start` or a revival puts up is spawned into a session of its own, so no Popen
    handle reaches it and `leaf server stop` is the door; and the sweep walks for
    them rather than reading a list the tests append to, since the serve nobody
    remembered is the one this is here for.

    Both roots are the run's own: `tmp_path`, and the state home as
    `isolated_session`'s value. Read from the environment here instead, at setup
    or after the yield, the root is the developer's `~/.local/state/leaf`, and
    this sweep stopped every server standing there (tests/CLAUDE.md, "A process
    the suite starts ends with the run")."""
    yield
    while HELD_LEASES:
        HELD_LEASES.pop().close()
    for root in (tmp_path, isolated_session):
        for lease in root.rglob("server.lock"):
            if server_model.running_server(lease.parent):
                hosting_model.cmd_stop(lease.parent)


def neighbour_page(directory, title=None, dead=False, published=True):
    """A page with desired service state and, unless dead, a live lease."""
    directory.mkdir(parents=True)
    (directory / "revisions").mkdir()
    head = f"<title>{title}</title>" if title else ""
    html = (
        f"<!doctype html><html><head>{head}</head>"
        "<body><main><p>words</p></main></body></html>"
    )
    (directory / "index.html").write_text(html)
    initialized = CliRunner().invoke(cli_model.cli, ["page", "init", str(directory)])
    assert initialized.exit_code == 0, initialized.output
    files_model.write_revision(directory, 1, html.encode())
    # What `page init` writes: a page always has a status record.
    files_model.write_json(
        directory / "status.json",
        {"state": "idle", "detail": "", "ts": None, "after": 0},
    )
    if published:
        events_model.append_event(
            directory,
            {
                "kind": "note",
                "author": "agent",
                "version": 1,
                "revision": 1,
                "text": "t",
            },
        )
    record = {"port": 59999}
    if dead:
        files_model.write_json(
            directory / "service.json",
            {
                "host": "127.0.0.1",
                "bind": "127.0.0.1",
                "port": 59999,
                "enabled": True,
                "lifetime": "standing",
            },
        )
    else:
        serving(directory, record["port"])
    return server_model.page_url("127.0.0.1", 59999, server_model.host_key())


def _status(page_dir, *args):
    return CliRunner().invoke(cli_model.cli, ["status", str(page_dir), *args])


@pytest.fixture
def comment_once_served():
    """Post a user comment as soon as a server answers for the page, so a wait
    that had to revive one has something to return on: the revival is the fact
    under test and the comment is only what ends the wait.

    A wait ends on someone speaking or on the leaf ending, and this owes the test
    one of the two. With neither, `cmd_wait` holds forever and the run has to be
    killed — which is how a revived server got stranded, the kill reaching
    neither the wait's own stop nor a page that had declined the claim."""
    stopped = threading.Event()
    posting = []

    def watch(page_dir):
        deadline = time.monotonic() + 30

        def post():
            while not stopped.wait(0.1):
                if server_model.running_server(page_dir):
                    events_model.append_event(
                        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
                    )
                    return
                if time.monotonic() > deadline:
                    session_model.cmd_status(page_dir, "idle", "no server came up")
                    return

        thread = threading.Thread(target=post, daemon=True)
        thread.start()
        posting.append(thread)

    yield watch
    stopped.set()
    for thread in posting:
        thread.join(timeout=5)


@pytest.fixture
def claimed(page_dir, monkeypatch):
    """A page claimed by session s1, the way Claude Code's environment claims one:
    it puts the session id and its pid into every Bash tool call."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    return page_dir


@pytest.fixture(scope="session")
def codex_program(tmp_path_factory):
    """A program named `codex` to run a session under, which is the whole of what
    `CodexHarness.lifetime` looks for above a leaf: a copy of this interpreter wearing that
    name. The name has to be the executable's own, because what a process reports
    is what the kernel loaded — a `#!` script and a symlink both wear the
    interpreter's, and a copy of /bin/sh is killed on sight on macOS, where that
    binary's signature is the system's."""
    program = tmp_path_factory.mktemp("codex-program") / "codex"
    shutil.copy(sys.executable, program)
    return program


@pytest.fixture
def under_codex(spawn, codex_program):
    """A command run the way Codex runs one: a session process that stays for the
    thread, and between it and the command a shell of the moment — which is what
    a pipeline leaves there, and what Leaf once mistook for the session.

    `; exit` is what puts that shell there: a lone command is exec'd in place by
    the shell wrapping it, which is why some command shapes recorded the right
    pid by accident. It also keeps the command's own status, where the `| cat`
    that produced the shape in the wild would report the pipeline's last exit.
    PYTHONHOME because a copied interpreter has no prefix beside it to find its
    own standard library in."""
    runner = (
        "import subprocess, sys; "
        "sys.exit(subprocess.run(['/bin/sh', '-c', sys.argv[-1]]).returncode)"
    )

    def start(command, env, *, app_server=False, **kwargs) -> subprocess.Popen:
        # `app-server` is the whole difference between the app's shared host and
        # one session's own process — same program, same ancestry, one word in
        # the argv — so it is the one factor this varies. The runner reads the
        # last word either way, which is what keeps that the only difference.
        hosting = ["app-server"] if app_server else []
        return spawn(
            [str(codex_program), "-c", runner, *hosting, f"{command}; exit"],
            env={**env, "PYTHONHOME": sys.base_prefix},
            **kwargs,
        )

    return start


@pytest.fixture
def codex_claimed_page(tmp_path, under_codex, codex_env):
    page = tmp_path / "codex-page"
    env = codex_env | {"CODEX_THREAD_ID": "codex-thread"}

    # Uncaptured, so `check=True` reports something: a CalledProcessError over
    # captured streams names the command and the exit status and takes leaf's
    # own message down with it, and nothing here reads either stream. Left to
    # pytest, the message is in the failure it belongs to.
    subprocess.run([*LEAF_COMMAND, "page", "init", page], env=env, check=True)
    # Under the fake codex so the service child's claim walk finds it. The chain
    # from that claim up to the codex program is therefore intact.
    # Captured because the URL is read back; the status is asserted here with
    # both streams in the message, rather than left to a CalledProcessError
    # that would take leaf's own account down with it.
    started = under_codex(
        shlex.join([*LEAF_COMMAND, "server", "start", str(page)]),
        env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = started.communicate(timeout=60)
    assert started.returncode == 0, f"{out}{err}"
    assert out.startswith("http://127.0.0.1:")
    # The fake codex wrapper exits with this one command; a real Codex session
    # stays above later hook calls. Keep that session lifetime true for tests
    # using this fixture after the launch itself has been verified.
    claim = service_model.page_claim(page)
    files_model.write_json(
        service_model.claim_path(page), {**claim, "pid": os.getpid()}
    )
    return page


@pytest.fixture
def session_process(spawn):
    """A process for a session to be, so a test can end that session on purpose
    without ending its own.

    It reads a pipe this worker holds, and so ends when the worker does however
    the worker ends: the write end closing is EOF, and a killed run would
    otherwise leave both this and the server watching it running."""
    return lambda: spawn(
        [sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE
    )


@pytest.fixture
def managed_server(spawn):
    """A server whose lifetime is a session the test can end on purpose. Claude
    Code's door, because that host states its session's pid outright and the
    test wants a process of its own in that role; which host claimed the page is
    nothing to the watcher that reads the claim."""

    def start(page_dir, session_id, session_pid):
        record_claim(page_dir, id=session_id, pid=session_pid)
        process = spawn(
            [
                *LEAF_COMMAND,
                "server",
                "run",
                str(page_dir),
            ],
            env=os.environ
            | {
                "CLAUDE_CODE_SESSION_ID": session_id,
                "CLAUDE_PID": str(session_pid),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout.readline().startswith("http://127.0.0.1:")
        assert process.stderr.readline().strip() == (
            "server   session (stops with its agent session)"
        )
        return process

    return start


def start_server_command(page_dir, *flags, session_id="starter"):
    """Run `server start` from a host session and wait for the command to return."""
    return subprocess.run(
        [
            *LEAF_COMMAND,
            "server",
            "start",
            *flags,
            str(page_dir),
        ],
        env=os.environ
        | {"CLAUDE_CODE_SESSION_ID": session_id, "CLAUDE_PID": str(os.getpid())},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.fixture
def standing_server(spawn, sessionless):
    """`server run` from a bare shell — a terminal, a login item — held to the
    two lines it prints, the URL and the lifetime it recorded.

    Standing is the serve nothing reaps: it declines the claim, so no watcher
    starts, and a run killed while one is up leaves a process only a person can
    stop (tests/CLAUDE.md, "A process the suite starts ends with the run"). A
    child of the worker is as close as the suite gets."""

    def start(page_dir):
        process = spawn(
            [
                *LEAF_COMMAND,
                "server",
                "run",
                str(page_dir),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout.readline().startswith("http://127.0.0.1:")
        assert process.stderr.readline().strip() == "server   standing"
        return process

    return start


# ---------- comment: the anchor written without a browser ----------


def published(page_dir):
    result = stamp(page_dir, "first")
    assert result.exit_code == 0, result.output
    return page_dir


def comment(page_dir, *args):
    return CliRunner().invoke(cli_model.cli, ["comment", str(page_dir), *args])


DRAFTED = PAGE.replace(
    "<h2>Plan</h2>",
    '<h2>Plan</h2>\n  <lf-draft id="note"><pre>\nAdds --dry-run to every mutating command.\n  </pre></lf-draft>',
)


def drafted(page_dir):
    """A published v1 carrying the note draft, its body still Claude's."""
    (page_dir / "index.html").write_text(DRAFTED)
    return published(page_dir)


def edit(page_dir, text, widget="note", version=1):
    events = events_model.read_events(page_dir)
    revision = files_model.version_revisions(events).get(
        version, files_model.latest_revision(page_dir)
    )
    append_command(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "revision": revision,
            "widget": widget,
            "action": "edit",
            "detail": {"text": text},
        },
    )


SUGGESTED = before_choice(PAGE, SUGGESTION)


def suggested(page_dir):
    """A published v1 carrying the sug-refill suggestion, both slots pending."""
    (page_dir / "index.html").write_text(SUGGESTED)
    return published(page_dir)


def add_test_widget(package: Path, tag: str, upgrade: bool = False) -> dict:
    """Author one widget in an initialized package fixture."""
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    declaration = element_declaration(tag, upgrade)
    registry[tag] = declaration
    registry_path.write_text(json.dumps(registry))
    with (package / "theme.css").open("a") as theme:
        theme.write(f"\n{tag} {{ display: block; }}\n")
    if upgrade:
        (package / "widgets" / f"{tag}.js").write_text(
            f'customElements.define("{tag}", class extends HTMLElement {{}});\n'
        )
    return declaration


def element_declaration(tag: str, upgrade: bool = False) -> dict:
    """A minimal package widget declaration for composition fixtures."""
    declaration = {
        "description": f"A <{tag}> test block.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "markup",
        "x-upgrade": upgrade,
        "x-example": f'<{tag} id="example">Example</{tag}>',
    }
    if upgrade:
        declaration["x-verbatim"] = True
    return declaration
