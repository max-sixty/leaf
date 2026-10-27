"""Shared fixtures and assertions for the Leaf integration modules.

Run from the repo root:

    uv run pytest tests
"""

import difflib
import fcntl
import http.client
import http.cookiejar
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from functools import cache
from pathlib import Path

import psutil
import pytest
import yaml
from click.testing import CliRunner
from conftest import CLAUDE_IDENTITY, LEAF_COMMAND, collect_app_server_error
from pytest_regtest.snapshot_handler import (
    BaseSnapshotHandler,
    SnapshotHandlerRegistry,
)
from websockets.sync.server import serve as serve_websocket
from websockets.sync.server import unix_serve as serve_unix_websocket

from leaf import cli as cli_model
from leaf import codex as codex_model
from leaf import codex_adapter as codex_adapter_model
from leaf import codex_state as codex_state_model
from leaf import data as data_model
from leaf import delivery as delivery_model
from leaf import event_contracts as event_contracts_model
from leaf import event_log as events_model
from leaf import files as files_model
from leaf import harness as harness_model
from leaf import hosting as hosting_model
from leaf import layer as layer_model
from leaf import leases as leases_model
from leaf import packages as packages_model
from leaf import page_memory as page_memory_model
from leaf import passages as passages_model
from leaf import revisioning as revisioning_model
from leaf import schema as schema_model
from leaf import server as server_model
from leaf import server_rows as server_rows_model
from leaf import service as service_model
from leaf import session as session_model
from leaf import state as cleanup_model
from leaf import structure as structure_model
from leaf import thread_context as thread_context_model
from leaf import vendoring as vendoring_model
from leaf.findings import Finding
from leaf.obligations import collection
from leaf.refusals import Refused
from leaf.registry.contract import RegistryError
from leaf.registry.storage import load_registry, require_registry
from leaf.revision_artifact import active_enclosing
from leaf.served_state import page as served_page
from leaf.validation import composition as composition_model
from leaf.validation import instances as validation_model

ROOT = Path(__file__).parent.parent
# The checkout and the payload a harness installs are one tree now; PLUGIN_ROOT still
# names the role a path plays — "what a harness runs" — for the tests built on that.
PLUGIN_ROOT = ROOT
# The skill contains agent instructions; application resources belong to the plugin.
SKILL_ROOT = PLUGIN_ROOT / "skills" / "leaf"
COMMAND_HUB_PACKAGE = ROOT / "tests" / "fixtures" / "packages" / "work"
# The complete shipped vocabulary, in the order `page init` composes it for an example.
# Read from examples/layer.json rather than listed here, because a floor that names its
# own packages stops covering the next one: lf-diagram and lf-diff left the default
# package for `diagram` and `diff` and would have dropped out of every sweep silently,
# and pr-review's two widgets had never been in one.
SHIPPED_PACKAGES = [
    schema_model.ASSETS,
    schema_model.DEFAULT_PACKAGE,
    *(
        schema_model.BUNDLED_PACKAGES / name
        for name in json.loads(
            (ROOT / "examples" / "layer.json").read_text(encoding="utf-8")
        )
    ),
]
COMMAND_SUBJECTS = (
    '<lf-test-worker id="worker" state="waiting" on="goal"><strong>Worker</strong>'
    '<lf-test-tree id="tree" source="project-worktrees"></lf-test-tree>'
    "</lf-test-worker>"
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
    """Seed a widget command through the real append door.

    A test of raw storage or retired vocabulary passes an explicitly admitted
    event, including meaning and attention, to event_log.append_event instead.
    """
    with service_model.PageTransaction(page_dir) as page:
        return event_contracts_model.append_admitted(page, command)[0]


def response_reference(page_dir, event):
    """Read the exact address emitted by the real delivery producer for an input."""
    from leaf.delivery import batch_data, freeze_delivery

    event_id = event["id"] if isinstance(event, dict) else event
    with service_model.PageTransaction(page_dir) as page:
        captured = next(item for item in page.events if item["id"] == event_id)
        batch = batch_data(page_dir, page, [captured])
    return freeze_delivery([batch])["batches"][0]["events"][0]["answer"]["ref"]


def append_carried_log_record(page_dir, event):
    """Seed already-interpreted input for a storage or transport test.

    These tests declare input the transport must deliver, without a document that
    could decide its meaning, so user input that admission would weigh against the
    page's obligations is taken to change them. Semantic attention cases use
    `append_command`.
    A raw fixture can explicitly declare `attention=False` for quiet input. A kind
    whose record requires the `revision` it was made on is placed on the first.
    """
    from leaf.registry.kernel import kernel_event_kinds

    contract = kernel_event_kinds().get(event["kind"], {})
    attention = event_contracts_model.settled_attention(event, contract)
    record = {"attention": attention is not False, **event}
    if "revision" in contract["record"]["required"]:
        record.setdefault("revision", 1)
    return events_model.append_event(page_dir, record)


def write_revision(page_dir: Path, revision: int, data: bytes) -> Path:
    """Write revision `revision` of `data` under the page's current registry.

    A shortcut past `page stamp` for a test that stages history directly: it
    runs no gate and no activation, and refuses a revision number already taken."""
    from leaf.passages import SourceReading
    from leaf.registry.storage import read_page_registry
    from leaf.revision_artifact import capture_artifact, write_artifact
    from leaf.structure import SourceDocument

    candidate = read_page_registry(page_dir)
    reading = SourceReading(SourceDocument(data.decode("utf-8")), candidate.registry)
    artifact = capture_artifact(
        page_dir,
        reading.document,
        candidate.registry,
        declaration_sources=candidate.declaration_sources,
        widget_sources=candidate.widget_sources,
    )
    return write_artifact(page_dir, revision, artifact, reading)


@cache
def model_layer(*packages: str) -> dict:
    """The vocabulary `page init` vendors for one package selection.

    Composed from the bundled packages rather than read back out of a page, and
    cached per selection, because every stated page asking for the same packages
    is asking for the same registry. Nothing may mutate what this returns.
    """
    return composition_model.incoming_registry(layer_model.layer_inputs(packages))


def queue_board_registry(registry: dict) -> dict:
    """A page-owned queue stays an obligation until all cards leave its Queued column.

    Extend the board's position verb with a completion condition to exercise
    answers spanning units without a presentation-specific package.
    """
    registry = deepcopy(registry)
    registry["lf-board"]["x-awaits"] = {
        "value": "move",
        "answered": {
            "move": {"empty": {"within": "lf-column", "when": {"label": ["Queued"]}}}
        },
    }
    return registry


class ModelPage:
    """A page stated rather than stored, for a rule its markup decides.

    `event_contracts.admitted_event` reads a page through the answers below and
    nothing else, so a refusal that follows from authored markup and the current
    log can be put to the real door with no page directory, server or browser
    underneath it. Each revision here is its markup, in the order given.
    `packages` names the optional vocabularies the markup speaks, as `page init`
    would be told them; the default layer alone is the default.

    Typed external data can be supplied as the same validated reading the server
    receives. File publication behavior and response delivery belong on `page_dir`.
    """

    def __init__(
        self,
        *revisions: str,
        packages: tuple[str, ...] = (),
        documents: dict | None = None,
        registry: dict | None = None,
        data: dict | None = None,
    ):
        """`documents` and `registry` are for a caller that has already parsed and
        composed them — `model_folds.reading` has, and states the same page to the
        door through this class rather than answering the door's readings itself."""
        self.documents = documents or {
            number: structure_model.SourceDocument(html)
            for number, html in enumerate(revisions, 1)
        }
        self._packages = packages
        self._registry = registry
        self._data = data or {"version": "", "sources": {}}

    @property
    def revisions(self) -> list[int]:
        return sorted(self.documents)

    def document(self, revision: int):
        return self.documents[revision]

    def reading(self, revision: int, registry: dict):
        return passages_model.SourceReading(self.documents[revision], registry)

    def registry(self, revision: int | None) -> dict:
        """One layer for every revision: a stated page never re-vendors, so no
        revision of it captured a vocabulary different from the rest."""
        return self._registry or model_layer(*self._packages)

    @property
    def contracts(self) -> dict:
        """The contracts of the supplied data publications."""
        return {
            source: value["contract"] for source, value in self._data["sources"].items()
        }

    def data(self, registry: dict) -> dict:
        """The supplied validated data readings, empty unless a test names them."""
        return self._data

    @property
    def within(self) -> dict:
        return passages_model.enclosing_ids(self.documents[max(self.documents)])

    def responses(self, events: list) -> dict:
        raise NotImplementedError(
            "what a page still owes is read from its claims and its deliveries, "
            "which a stated page has none of: put that refusal on `page_dir`"
        )

    @property
    def claims(self) -> list:
        return []


def spawn_probe(spawn, page_dir, body, *, stdin=None, **environment):
    """Run a deterministic race seam in an isolated Leaf application process."""
    env = {name: str(value) for name, value in environment.items()}
    return spawn(
        [sys.executable, "-c", PROBE_BOOTSTRAP + body],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=stdin,
        text=True,
        env=os.environ | {"PAGE": str(page_dir)} | env,
    )


STATED_TIMEOUT = 120
"""How long a pure-Python wait gives another thread or process to state its fact.

The deadline separates a product that never states the fact from a machine that
has not reached it yet, so it is generous rather than tight. Several workers
share one runner's cores with their browsers, and a stretch of ordinary work there
runs many times slower than it does on an unloaded host: a wait sized as a small
multiple of the unloaded duration reddens `main` on the runs where another worker
happens to be driving Chrome. On a local host at load 230 over 18 cores,
two concurrent `page init`s took up to 25s and three `leaf codex start`
commands 20s. `SERVED_TIMEOUT_MS` is the browser side's counterpart.

Every Python-side wait in the suite takes its deadline from here, so a slow machine
is answered in one place (`test_a_wait_takes_the_suites_deadline`). A
wait whose length is its subject, such as a product's own timeout passed in to be
exercised, names that value where it is defined instead."""

COMPOSITE_TIMEOUT = 2 * STATED_TIMEOUT
"""The hang bound on a subprocess that does several stated waits' worth of work
before it says anything: a nested pytest run, a preview that builds and serves a
page before printing its address, a hook launched through uv."""

POLL_INTERVAL = 0.05
"""How often a pure-Python poll re-reads its fact. It sets how soon a fact is seen
once stated, never whether it is."""


def wait_for(
    read,
    accepts,
    *,
    failure: str | Callable[[], str],
    timeout: float = STATED_TIMEOUT,
):
    """Return the first accepted reading, or fail with the last one observed.

    `failure` is the message, or a function that composes it at the timeout, for a
    poll whose diagnosis needs state read only once it has failed (a log, a record).

    For pure-Python state polls. Keep a local loop where process exit, cancellation,
    or a deadline shared across several transitions is the contract."""
    deadline = time.monotonic() + timeout
    while True:
        reading = read()
        if accepts(reading):
            return reading
        if time.monotonic() >= deadline:
            said = failure() if callable(failure) else failure
            pytest.fail(f"{said}; last reading was {reading!r}")
        time.sleep(POLL_INTERVAL)


def lock_contention(
    monkeypatch, *paths: Path, by: str | None = None
) -> threading.Event:
    """Return an event set once an exclusive lock on one of `paths` finds it held.

    A taker blocked in the kernel states nothing, so neither a sleep nor a short
    wait can tell one held behind the lock from one that never reached it, or from
    one let through. This intercepts `flock`: a blocking exclusive request on the
    file one of `paths` names is first tried without blocking, and when that is
    refused the event is set before the request waits as its caller asked. An
    uncontended acquisition passes through and sets nothing.

    `by` names the thread whose waiting is the claim, where another thread could
    take the same lock in passing; leave it out where only the taker under test
    can."""
    native_flock = fcntl.flock
    contended = threading.Event()

    def names(fd) -> bool:
        held = os.fstat(fd if isinstance(fd, int) else fd.fileno())
        for path in paths:
            try:
                if os.path.samestat(held, os.stat(path)):
                    return True
            except FileNotFoundError:
                continue
        return False

    def observed_flock(fd, operation):
        taker = threading.current_thread().name
        if operation == fcntl.LOCK_EX and by in (None, taker) and names(fd):
            try:
                return native_flock(fd, operation | fcntl.LOCK_NB)
            except BlockingIOError:
                contended.set()
        return native_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", observed_flock)
    return contended


def take_stream_activity(monkeypatch, updates: list, clears: list) -> None:
    """Collect every activity reading a turn writes, instead of a page taking it.

    Every App Server client and harness calls the writers through `leaf.codex`, so that one binding
    takes them all. Pass empty lists for a test that wants them to touch nothing.
    """
    monkeypatch.setattr(
        codex_model,
        "set_stream_activity",
        lambda session, turn, detail, **_scope: updates.append((session, turn, detail)),
    )
    monkeypatch.setattr(
        codex_model,
        "clear_stream_activity",
        lambda session, turn=None, **_scope: clears.append((session, turn)),
    )


@contextmanager
def running_http_server(httpd):
    """Serve an HTTP fixture and close every thread and socket it creates."""
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=STATED_TIMEOUT)
        assert not thread.is_alive(), "the fixture HTTP server did not stop"
        httpd.server_close()


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


def js_facts(command: str, files) -> str:
    """What `tests/js_facts.mjs` reads with `command` out of the parsed modules `files`:
    JSON for every command but `keydown`, whose lines are returned as printed."""
    return subprocess.run(
        ["node", str(ROOT / "tests" / "js_facts.mjs"), command, *map(str, files)],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    ).stdout


def shipped_core_registry() -> dict:
    """The kernel registry with the core layer's declarations beside it, the layer
    facts `page init` starts every composition from, unstamped."""
    return {
        **cleanup_model.kernel_registry(),
        **json.loads((schema_model.ASSETS / "registry.json").read_text()),
    }


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
    """Copy the candidate payload the way a harness installs the committed tree."""
    for path in shipped_payload():
        target = destination / path.relative_to(PLUGIN_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            target.symlink_to(os.readlink(path))
        else:
            shutil.copy2(path, target)
    return destination


def vendored_at_another_protocol(page_dir: Path, *, newer: bool = False) -> int:
    """Record another page protocol in the page's layer record, and return it.

    The state a breaking Leaf update leaves a page in: an earlier `page init`
    recorded an older number this Leaf no longer speaks, or with `newer`, a later
    Leaf recorded a higher one. The file is replaced rather than written through,
    as every file a lent page may share with its template has to be.
    """
    from leaf.registry.storage import LAYER, layer_record

    path = page_dir / schema_model.LAYER_FILE
    record = layer_record(page_dir)
    foreign = record["protocol"] + (1 if newer else -1)
    path.unlink()
    LAYER.write(path, {**record, "protocol": foreign})
    return foreign


def declare_on_page(page_dir: Path, mutate) -> None:
    """Apply `mutate` to the page's vocabulary as the page's own declarations.

    A page's layer is the Leaf's own (`layer.selected_layer`), so a test that needs
    a vocabulary the shipped layer lacks declares it where an author would, in
    `page/registry.json`: each entry `mutate` changes or adds, whole, and each `$`
    fact by the members it changes, which merge over the layer's, a map member by
    merge-patch (`registry.layer.merge_layer_declarations`). `mutate` sees the
    declarations the page already makes."""
    from copy import deepcopy

    from leaf.registry.layer import merge_layer_declarations

    path = page_dir / "page" / "registry.json"
    declarations = json.loads(path.read_text()) if path.is_file() else {}
    before = deepcopy(
        {
            key: value
            for key, value in load_registry(page_dir).items()
            if key != "$layer"
        }
    )
    merge_layer_declarations(before, deepcopy(declarations))
    after = deepcopy(before)
    mutate(after)
    for key, value in after.items():
        if value == before.get(key):
            continue
        if key.startswith("$") and isinstance(before.get(key), dict):
            members = declarations.setdefault(key, {})
            for member, item in value.items():
                earlier = before[key].get(member)
                if item == earlier:
                    continue
                if isinstance(item, dict) and isinstance(earlier, dict):
                    patch = members.get(member)
                    members[member] = {
                        **(patch if isinstance(patch, dict) else {}),
                        **{k: v for k, v in item.items() if earlier.get(k) != v},
                        **{k: None for k in earlier.keys() - item.keys()},
                    }
                else:
                    members[member] = item
        else:
            declarations[key] = value
    path.parent.mkdir(exist_ok=True)
    if path.is_file():
        path.unlink()
    path.write_text(json.dumps(declarations))


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
  <div id="plan-choice-decision">
    <h3>Which plan should lead?</h3>
    <lf-options>
      <lf-option id="flag-first"><small class="tag">effort: low</small><small class="tag">risk: med</small>
        <strong>Flag first</strong> Ship dark.
      </lf-option>
      <lf-option id="backfill-first"><small class="tag">effort: med</small><small class="tag">risk: low</small>
        <strong>Backfill first</strong> Verify, then flip. <em>My take: do this first.</em>
      </lf-option>
    </lf-options>
  </div>
</section>
</main>
</body>
</html>
"""
# PAGE places no widget whose module only a browser can judge, so `page check` on it
# and on the versions built from it never starts one (`needs_browser`). A test about a
# data widget's body, its visual parts, or the section one supplies starts from
# FLOW_PAGE, which closes the Plan section with a diagram.
FLOW_PAGE = PAGE.replace(
    "</section>",
    """  <lf-diagram id="flow"><pre>
graph LR
  A --> B
  </pre></lf-diagram>
</section>""",
)


def package_path(path: Path) -> str:
    """Select a checkout fixture from the caller's cwd, wherever HOME lives."""
    return "./" + os.path.relpath(path)


def page_packages() -> tuple[str, ...]:
    """The integration page's package selection, resolved where it is initialized.

    FLOW_PAGE holds an lf-diagram, and the interact suite borrows lf-diagram and
    lf-diff declarations from the vendored registry.
    """
    return (package_path(COMMAND_HUB_PACKAGE), "diagram", "diff")


@pytest.fixture
def page_dir(tmp_path, monkeypatch, initialized_page):
    """A mutable page with the default, Command Hub, diagram and diff vocabularies."""
    monkeypatch.chdir(tmp_path)  # resolve fixture package paths
    return initialized_page(
        tmp_path / "page",
        page_packages(),
        ("PAGE", lambda template: (template / "index.html").write_text(PAGE)),
    )


def check(d):
    """`page check`, in-process."""
    return CliRunner().invoke(cli_model.cli, ["page", "check", str(d)])


def refused_on(answer) -> Finding:
    """The one finding a refusal rests on: an exception's (`Refused.findings`), or the
    one an event door's answer carries, as a dict or its raw JSON body."""
    if isinstance(answer, Exception):
        (finding,) = answer.findings
        return finding
    if isinstance(answer, (str, bytes)):
        answer = json.loads(answer)
    (finding,) = answer["findings"]
    return Finding.loads(finding)


def check_findings(d) -> tuple[int, list[Finding]]:
    """`page check`, in-process: its exit status and what it found, as records."""
    report = json.loads(
        CliRunner().invoke(cli_model.cli, ["page", "check", str(d)]).stdout
    )
    return report["status"], [Finding.loads(found) for found in report["findings"]]


def package_findings(package) -> tuple[int, list[Finding]]:
    """`package check`, in-process: its exit status and what it found, as records."""
    report = json.loads(
        CliRunner().invoke(cli_model.cli, ["package", "check", str(package)]).stdout
    )
    return report["status"], [Finding.loads(found) for found in report["findings"]]


def found(findings, code: str, at: str | None = None, **values) -> list[Finding]:
    """The findings of `code`, about the element `at` names where given, whose values
    include each of `values`."""
    return [
        finding
        for finding in findings
        if finding.code == code
        and at in (None, finding.at)
        and all(finding.values.get(key) == value for key, value in values.items())
    ]


def registry_refusal(read: Callable) -> Finding:
    """The one finding the registry refusal raised by calling `read` carries."""
    with pytest.raises(RegistryError) as refused:
        read()
    [finding] = refused.value.findings
    return finding


def command_findings(*args) -> list[Finding]:
    """The findings the refusal of the leaf command `args`, run in process, carries:
    none where the command succeeds."""
    result = CliRunner().invoke(cli_model.cli, [*map(str, args)], standalone_mode=False)
    return [] if result.exception is None else result.exception.__cause__.findings


def read_page_data(page_dir) -> dict:
    """Every source the page records, judged against the vocabulary its live
    document is read in."""
    return data_model.read_data(page_dir, require_registry(page_dir))


def declare_data_input(
    page_dir,
    source,
    schema,
    *,
    contract="test-data",
    tag="lf-test-data",
    input_name="data",
    instructions=None,
    activate=True,
):
    """Add one typed widget input and bind it in the mutable source."""
    declaration = {"description": "Test data contract.", "schema": schema}
    if instructions:
        declaration["instructions"] = instructions
    entry = {
        "description": "A test widget with one external-data input.",
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": f"^{schema_model.ELEMENT_ID}$"},
            "source": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
        },
        "required": ["id", "source"],
        "additionalProperties": False,
        "x-content": "empty",
        "x-data": {input_name: {"contract": contract, "source": "source"}},
        "x-upgrade": False,
    }

    def declare(registry):
        registry["$data"]["contracts"][contract] = declaration
        registry[tag] = entry

    declare_on_page(page_dir, declare)
    source_path = page_dir / "index.html"
    html = source_path.read_text()
    source_path.write_text(
        html.replace(
            "</main>",
            f'<{tag} id="test-data" source="{source}"></{tag}>\n</main>',
        )
    )
    if activate:
        activated = revisioning_model.activate_source(page_dir)
        assert activated.error is None


def publish(d, text="published"):
    """Stamp the source as the next version, through `page stamp`'s own path.

    The stamped version is the user-seen baseline: `page check` compares against
    the last one, and an action can only ever be made against one the server
    exposed. Returns the stamp's note."""
    from leaf.publishing import cmd_stamp

    return cmd_stamp(d, text)


def let_a_pick_settle_a_thread(page_dir, thread):
    """Declare `resolves` on `lf-options` and point the page's `picks` group at
    `thread`, before the page publishes.

    A settling answer rests on its widget and on the ids that widget's detail
    names inside itself, so a version rewriting one of those takes the answer
    back. Nothing shipped exercises both halves: only `lf-suggestion` declares
    `resolves`, and its answer rests on the widget alone. A test of the two
    together declares the attribute it needs on the page it is about to publish,
    which is where the append door reads the vocabulary and the markup that
    admit an action.
    """
    declare_on_page(
        page_dir,
        lambda registry: registry["lf-options"]["properties"].update(
            resolves={"type": "string"}
        ),
    )
    # An obligation, so a pick answers it; the markup already records that pick, so the
    # answer owes no version of its own and only the thread is left to settle.
    source = page_dir / "index.html"
    source.write_text(
        source.read_text()
        .replace(
            '<lf-options id="picks">',
            f'<lf-options id="picks" choose resolves="{thread}">',
        )
        .replace('<lf-option id="flag-first">', '<lf-option id="flag-first" chosen>')
    )


def stamp(d, text="stamped", completes=()):
    """Stamp the fixture's canonical authored source through the CLI."""
    return CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "stamp",
            str(d),
            "--text",
            text,
            *(arg for widget in completes for arg in ("--completes", widget)),
        ],
    )


@cache
def _served_state_validator(against: tuple[str, ...]):
    """`served_state/state.schema.json`, with the `leaf:` schemas it refers to
    (`registry.schema.leaf_resources`), taking any of `against`: `answer`, a
    complete `/api/state` answer, `null`, or one of its definitions by name."""
    from leaf.registry.schema import json_validator, with_leaf_resources

    schema = with_leaf_resources(
        json.loads(
            Path(served_page.__file__).with_name("state.schema.json").read_text()
        )
    )

    def target(name: str) -> dict:
        if name == "null":
            return {"type": "null"}
        pointer = "" if name == "answer" else f"#/$defs/{name}"
        return {"$ref": schema["$id"] + pointer}

    return json_validator(
        {
            "anyOf": [target(name) for name in against],
            "unevaluatedProperties": False,
            "$defs": {"served": schema},
        }
    )


def served_state_error(value, against: str | tuple[str, ...] = "Reading") -> str | None:
    """Where `value` breaks the served state's schema, or None: against a fold's
    `Reading`, a complete `/api/state` answer (`answer`), or any definition or
    definitions named. A channel only Leaf writes, so the tests hold its shape here
    rather than anything validating it in flight."""
    from jsonschema.exceptions import best_match

    names = (against,) if isinstance(against, str) else against
    error = best_match(_served_state_validator(names).iter_errors(value))
    if error is None:
        return None
    return f"{error.json_path}: {error.message[:400]}"


# What each route a test requests through `fetch` may answer, by the end of its path
# (`http.PageEndpoint.POST_ROUTES` and its gates), so every answer a test reads holds
# the schema the browser and the Worker are typed from.
ROUTE_ANSWERS = {
    r"/api/event": ("EventAnswer", "Refusal", "LayerAnswer"),
    r"/api/samples": ("SampleAnswer", "Refusal", "LayerAnswer"),
    r"/api/media": ("MediaAnswer", "Refusal", "LayerAnswer"),
    r"/api/files/[^/]+": (
        "FileSnapshot",
        "null",
        "StaleFile",
        "Refusal",
        "LayerAnswer",
    ),
}


def route_answer_error(url: str, body: bytes) -> str | None:
    """Where the answer `body` a route under `url` gave breaks its schema, or None
    for a route `ROUTE_ANSWERS` doesn't name."""
    path = urllib.parse.urlsplit(url).path
    for route, against in ROUTE_ANSWERS.items():
        if re.search(route + "$", path):
            return served_state_error(json.loads(body), against)
    return None


def page_state(d):
    events = events_model.read_events(d)
    return served_page.full_state(d, events)


def served_thread(browser: dict) -> dict:
    """The frozen threads as the one view `browser` serves reads them."""
    [view] = browser["views"].values()
    return view["thread"]


def served_obligations(browser: dict, *, page: bool = False) -> dict:
    """The obligation records the one view `browser` serves for what the page asks, by
    the selections `obligations.collection` makes: the frozen threads' obligations, or
    with `page` the document's obligations. The records the user's updates publish
    are `served_updates`."""
    [view] = browser["views"].values()
    return collection(
        [
            item
            for item in view["obligations"]
            if item["source"]["kind"] != "update" and (item["thread"] is None) == page
        ]
    )


def served_updates(browser: dict) -> list[dict]:
    """The records the user's updates publish (`workflows.handed_over`), in the one view
    `browser` serves."""
    [view] = browser["views"].values()
    return [item for item in view["obligations"] if item["source"]["kind"] == "update"]


@pytest.fixture
def native_codex_chat(tmp_path):
    """Publish a native chat's validated source through its ordinary prompt hook."""
    from leaf.hooks import cmd_hook

    def create(session_id):
        source = tmp_path / "sessions" / f"{session_id}.jsonl"
        source.parent.mkdir(exist_ok=True)
        source.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": session_id}}) + "\n"
        )
        cmd_hook(
            "codex",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session_id,
                "transcript_path": str(source),
            },
        )
        assert cleanup_model.session_record(session_id)["transcript_path"] == str(
            source
        )
        return source

    return create


def _page_record(path):
    """The `state.Record` a page file's name declares."""
    from leaf.user_views import USER_VIEWS

    return {
        schema_model.STREAM_FILE: service_model.STREAM,
        schema_model.SERVICE_FILE: server_model.SERVICE,
        schema_model.PREVIEW_FILE: server_model.PREVIEW,
        schema_model.USER_VIEWS_FILE: USER_VIEWS,
    }[path.name]


def acknowledged_through(page_dir):
    """The page's acknowledgement cursor (`service.acknowledged`), read off its log."""
    return service_model.acknowledged(events_model.read_events(page_dir))


def acknowledge_through(page_dir, seq):
    """Confirm receipt of the page's input through `seq`, as a receipt does."""
    with service_model.PageTransaction(page_dir) as page:
        delivery_model.record_receipt(page, seq)


def read_record(path):
    """A page's record as Leaf reads it, or None where Leaf reads none."""
    return _page_record(path).read(path)


def write_record(path, value):
    """Write a page's record as its writer in Leaf would, through the `state.Record`
    its file name declares. A stream observes nothing `value` doesn't name, and a
    service no runtime and an incarnation no server holds unless it names them."""
    record = _page_record(path)
    if record is service_model.STREAM:
        value = {**service_model.no_stream(), **value}
    if record is server_model.SERVICE:
        value = {"runtime": {}, "server_id": "gone", **value}
    record.write(path, value)


def write_row(path, page):
    """Publish a neighbor row for `page` at `path` with every field a serving
    page's producer writes, none of them saying anything."""
    activity = dict.fromkeys(server_rows_model.ACTIVITY_FIELDS)
    activity["counts"] = dict.fromkeys(server_rows_model.COUNT_FIELDS, 0)
    server_rows_model.ROW.write(
        path,
        {
            "page": str(page),
            "page_key": cleanup_model.page_key(page),
            "server_id": "fixture-server",
            "row": {
                "title": page.name,
                "session_cwd": None,
                "activity": activity,
                "on_user": 0,
                "threads": {"open": 0, "unread": 0},
            },
        },
    )


def record_claim(page, /, harness="claude-code", **fields):
    """Write the canonical claim shape for lifecycle fixtures.

    `harness` is checked against Leaf's own table, so a fixture cannot record a
    name `take_claim` would never write."""
    observed = cleanup_model.session_record(fields.get("id", "s1"))
    if observed and not observed["provider"]:
        observed = None
    record = {
        "page": str(page.resolve()),
        "id": "s1",
        "harness": harness_model.HARNESSES[harness].name,
        "pid": os.getpid(),
        "agent": "Claude",
        "cwd": str(Path.cwd()),
        "ts": cleanup_model.now_iso(),
        "turn": observed["turn"] if observed else "turn-1",
        "turn_opened": observed["turn_opened"] if observed else cleanup_model.now_iso(),
        "turn_closed": observed["turn_closed"] if observed else None,
        **fields,
    }
    lifetime = {key: record[key] for key in ("job", "chat") if key in record}
    if not lifetime:
        lifetime = {"pid": record["pid"]}
    turn = {key: record[key] for key in ("turn", "turn_opened", "turn_closed")}
    session = cleanup_model.ensure_session(record["id"], lifetime)
    session = cleanup_model.write_session({**session, **turn})
    record = {
        key: value
        for key, value in record.items()
        if key not in {"job", "chat", "pid", "turn", "turn_opened", "turn_closed"}
    }
    record["generation"] = session["generation"]
    record["acquisition"] = fields.get("acquisition", secrets.token_hex(16))
    service_model.publish_claim(page, record)
    return service_model.page_claim(page)


def bind_task_lifetime_to_worker(page):
    """Keep a synthetic task running after its one-command harness exits.

    The worker stands for the real harness process that survives tool calls. This
    changes only that existing task's lifetime provenance, under its session
    lock: its generation, turn, provider observation, and page acquisition stay
    intact. Recording another claim would create a replacement generation and
    briefly leave the already-running adapter with no pages to own.
    """
    claim = service_model.page_claim(page)
    with cleanup_model.flocked(cleanup_model.session_lock_path(claim["id"])):
        record = cleanup_model.session_record(claim["id"])
        assert record["generation"] == claim["generation"]
        assert record["ended"] is None
        cleanup_model.write_session({**record, "lifetime": {"pid": os.getpid()}})


def release_codex_command(page, host, finished):
    """Complete a held command before its synthetic Codex harness can exit.

    The command must finish its claim transaction while its ancestor is alive.
    The canonical lifetime handoff then keeps that same task running for later
    delivery, before the fixture releases the one-command harness.
    """
    wait_for(
        finished.exists,
        bool,
        failure="the held Codex command did not finish",
    )
    bind_task_lifetime_to_worker(page)
    release_held(host)


def release_held(host):
    """Let an `under_codex` harness held with `finished` exit, by giving its
    shell the line it waits for. The pipe stays open for `communicate`."""
    os.write(host.stdin.fileno(), b"\n")


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
    """Insert a fixture before the base page's titled choice."""
    start = '<div id="plan-choice-decision">'
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
            "action": "decide",
            "detail": {"outcome": outcome},
        },
    )


def _decided(page_dir, words):
    """v1 carrying a draft the user has since rewritten, and the log that
    says so. Whatever v2 does about it, `page check` is what has to notice."""
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
            "detail": {"value": "Cut the flag; backfill first."},
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
        '<lf-test-tasks id="tree">'
        f'<lf-test-task id="t-parser" status="{status}"{extra}><strong>Parser</strong></lf-test-task>'
        "</lf-test-tasks>"
    )


def _tasks_version(page_dir, status, extra=""):
    (page_dir / "index.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _tasks(status, extra))
    )


def _report(page_dir, *args):
    """Report as a worker, with the posted event on stdout for the caller to read."""
    return CliRunner().invoke(cli_model.cli, ["page", "report", str(page_dir), *args])


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


def thread_records(page_dir, name: str) -> list[str]:
    """The logged records that change the history of the thread `name` reaches, in
    log order: the join a delivery reads to say which threads an event lands in
    (`thread_context.thread_memberships`)."""
    events = events_model.read_events(page_dir)
    names = thread_context_model.thread_names(events)
    memberships = thread_context_model.thread_memberships(
        events,
        names,
        thread_context_model.thread_widgets(
            thread_context_model.thread_structure(events), names
        ),
        active_enclosing(page_dir),
    )
    thread = names[name]
    return [event["id"] for event in events if thread in memberships[event["id"]]]


def state_json(d):
    result = CliRunner().invoke(cli_model.cli, ["page", "state", str(d)])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def obligations_on_user(state):
    """Widget obligations on the user's list, On me, retaining source and prompt identity:
    each row joined to the record in `obligations` it names."""
    records = {item["id"]: item for item in state["obligations"]}
    return [
        {
            "id": row["id"],
            "tag": records[row["id"]]["source"]["tag"],
            "widget": records[row["id"]]["source"]["id"],
            "widget_tag": records[row["id"]]["source"]["tag"],
            "thread": row["thread"],
        }
        for row in state["queues"]["on_user"]
        if row["kind"] == "widget"
    ]


def owed(state):
    """The answers one agent-facing state still owes, each the workflow of the input
    its record names, with the record's id as `obligation` and the owed `answer`.

    `activity.obligations` names each by its record's id beside its answer, so this
    is the join an agent makes to reach a move's stage or subject.
    """
    records = {item["id"]: item for item in state["obligations"]}
    by_input = {item["input"]: item for item in state["workflows"]}
    return [
        {
            **by_input[records[entry["id"]]["source"]["id"]],
            "obligation": entry["id"],
            "answer": entry["answer"],
        }
        for entry in state["activity"]["obligations"]
    ]


def activity_reading(page_dir, now: str | None = None) -> dict:
    """The page's activity as the server folds it (`activity.canonical_activity`), each
    owed answer (`obligations`) whole: the workflow of its update with the record's id
    and the answer, where the served state lists the record ids alone and `page state`
    prints each id beside its answer."""
    from leaf.served_state.context import read_page

    events = events_model.read_events(page_dir)
    return read_page(page_dir, events, now=now).work.activity


def owed_answers(page_dir):
    """The answers the page's agent owes (`activity.obligations`), as the hooks and
    `leaf page close` read them: each the workflow of the input its record names, with
    the record's id as `obligation` and the owed `answer`."""
    from leaf.served_state.context import read_page

    return read_page(page_dir, events_model.read_events(page_dir)).work.obligations


# A question and the accept that answers it, written as a stored log holds them:
# ids of their own and the `meaning` admission stamped on the action. For a test
# that needs an answered thread in a page directory and is about something else —
# what a floored widget retracts, what a second verb joins — so the pair is
# premise rather than subject. A test whose subject is the settlement states its
# page and its log instead, and lets the door derive the meaning.
COMMENT = {"kind": "comment", "id": "c1", "author": "user", "text": "cameras are flaky"}
ACCEPT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "sug-a",
    "action": "decide",
    "detail": {"outcome": "accept"},
    "meaning": {
        "scope": "page",
        "unit": "sug-a",
        "depends": ["sug-a"],
        "answer": "c1",
    },
}


def assert_revendor_serializes_writer(page_dir, monkeypatch, kind, write):
    """Hold one admitted writer at append and prove re-vendor cannot pass it.

    Re-vendoring waits for the admitted writer, then commits the incoming
    vocabulary while retaining that event. Release the writer before
    joining either worker, including when an assertion fails."""
    entering = threading.Event()
    resume = threading.Event()
    original_append_record = service_model.PageTransaction._append_record

    def held_append_record(page, event):
        if event.get("kind") == kind:
            entering.set()
            assert resume.wait(timeout=STATED_TIMEOUT), (
                "re-vendor never observed the writer"
            )
        return original_append_record(page, event)

    def init_result():
        try:
            vendoring_model.cmd_init(page_dir, selected=(*page_packages(), "./.leaf"))
        except Refused as error:
            return str(error)
        return None

    monkeypatch.setattr(
        service_model.PageTransaction, "_append_record", held_append_record
    )
    # The held writer keeps whichever page locks it took until it resumes, so a
    # re-vendor found waiting on one of them is waiting on the writer.
    waiting = lock_contention(
        monkeypatch, page_dir, page_dir / cleanup_model.EVENTS_FILE, by="re-vendor_0"
    )
    with (
        ThreadPoolExecutor(max_workers=1) as writer,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="re-vendor") as init,
    ):
        try:
            writing = writer.submit(write)
            wait_for(
                entering.is_set,
                bool,
                failure=f"{kind} never passed old-layer validation",
            )
            vendoring = init.submit(init_result)
            # Either the re-vendor waits on the writer's lock, or, written without
            # serialization, it finishes with the writer still held.
            wait_for(
                lambda: waiting.is_set() or vendoring.done(),
                bool,
                failure="re-vendor neither waited on the writer nor finished",
            )
            passed_writer = not waiting.is_set()
        finally:
            resume.set()
        written = writing.result(timeout=STATED_TIMEOUT)
        refusal = vendoring.result(timeout=STATED_TIMEOUT)

    assert not passed_writer, f"re-vendor passed a validated {kind} writer"
    assert refusal is None
    return written, refusal


def _mutated_registry_check(page_dir, mutate):
    registry = json.loads((page_dir / "registry.json").read_text())
    mutate(registry)
    (page_dir / "registry.json").write_text(json.dumps(registry))
    return check_findings(page_dir)


def _report_body_record(registry):
    registry["lf-test-task"]["x-state"]["status"]["record"] = {"kind": "body"}


def _report_position_record(registry):
    registry["lf-test-task"]["x-state"]["status"]["record"] = {
        "kind": "position",
        "within": "lf-column",
    }


def _report_no_record(registry):
    del registry["lf-test-task"]["x-state"]["status"]["record"]


def _report_undeclared_attr(registry):
    registry["lf-test-task"]["x-state"]["status"]["record"]["attr"] = "phase"


def _report_says_attr(registry):
    task = registry["lf-test-task"]
    task["required"].append("owner")
    task["x-says"] = {"owner": "before"}
    task["x-state"]["status"] = {
        "writer": "agent",
        "unit": "widget",
        "record": {"kind": "value", "attr": "owner"},
    }


def _report_authored_detail(registry):
    registry["lf-test-task"]["x-state"]["status"]["detail"] = {
        "type": "object",
        "additionalProperties": False,
    }


def _report_without_overruled(registry):
    del registry["lf-test-task"]["properties"]["overruled"]


def _report_without_upgrade(registry):
    registry["lf-test-task"]["x-upgrade"] = False


def _user_verb_text(registry):
    registry["lf-options"]["x-state"]["choose"]["text"] = True


def _agent_verb_answers(registry):
    registry["lf-options"]["x-state"]["choose"]["writer"] = "agent"
    registry["lf-options"]["properties"]["overruled"] = {"type": "boolean"}


def _body_record_with_prose(registry):
    # Isolate the body-record contract from the Markdown/data-content contract.
    del registry["lf-draft"]["x-text-format"]
    registry["lf-draft"]["x-content"] = "markup"


def _body_record_with_nested_widget(registry):
    registry["lf-option"]["x-owners"].append("lf-draft")


# A holder/slot family core has never heard of. <lf-trial> is decided by `adopt`,
# `shelve` or `pause`: `adopt` retires the <lf-current> it would replace, `shelve` the
# <lf-proposed> it offers, `pause` nothing, and taking an undecided one back leaves the
# page where a `shelve` would. <lf-pilot> holds the same <lf-proposed> under the same
# verb and declares no withdrawal at all — the pair, not the slot, is what the
# licensing is keyed on. Three instances, because a page needs one to decide, one to
# withdraw and one that can't be, and a decision is in the log for good once it is made.
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


def deciding_verb(outcomes):
    """The one verb whose `outcome` settles which of a holder's slots retire."""
    return {
        "decides": True,
        "detail": {
            "type": "object",
            "properties": {"outcome": {"enum": outcomes}},
            "required": ["outcome"],
            "additionalProperties": False,
        },
        "unit": "widget",
    }


def trial_version(*markup):
    return PAGE.replace("<lf-options>", "\n".join([*markup, "<lf-options>"]))


def trial_family(root: Path) -> None:
    """Declare the trial family in the project package at `root / ".leaf"`.

    Registry declarations relate its owners and slots, and each owner's module is the
    product's starter, which renders nothing of its own: anything a test sees settle is
    the layer's doing, and the holders' bodies are the authored words (`x-verbatim`).
    Only <lf-proposed> names two owners, for the selector case that needs one."""
    package = root / ".leaf"
    for tag, upgrade in (
        ("lf-trial", True),
        ("lf-pilot", True),
        ("lf-current", False),
        ("lf-proposed", False),
    ):
        add_test_widget(package, tag, upgrade=upgrade)
    source = package / "registry.json"
    declarations = json.loads(source.read_text())
    for tag, outcomes, example in (
        ("lf-trial", ["adopt", "shelve", "pause"], TRIAL_CACHE),
        ("lf-pilot", ["run", "shelve"], PILOT_PURGE),
    ):
        declarations[tag] |= {
            "x-content": "members",
            "x-state": {"decide": deciding_verb(outcomes)},
            "x-example": example,
        }
        declarations[tag]["properties"]["restated"] = {"type": "boolean"}
    # Only the trial says what taking it back would mean.
    declarations["lf-trial"]["x-withdrawn-as"] = "shelve"
    for tag, owners, outcome in (
        ("lf-current", ["lf-trial"], "adopt"),
        ("lf-proposed", ["lf-trial", "lf-pilot"], "shelve"),
    ):
        declarations[tag] |= {"x-owners": owners, "x-retired-when": outcome}
        del declarations[tag]["x-example"]  # a slot does not stand alone
        del declarations[tag]["required"]  # nor an id it must carry
    source.write_text(json.dumps(declarations))
    # add_test_widget frames every tag as a card. The slots draw no box of their own;
    # clearing their paragraph margins keeps a retired sibling from leaving a margin
    # trapped against the holder's frame. Geometry is not this family's subject.
    with (package / "widgets.css").open("a") as theme:
        theme.write(
            "\nlf-current, lf-proposed "
            "{ display: block; margin: 0; padding: 0; border: none; "
            "--lf-block-frame: initial; }\n"
            "lf-current p, lf-proposed p { margin-block: 0; }\n"
        )


@pytest.fixture
def trial_page(tmp_path, monkeypatch):
    """A published page whose vocabulary a project layer widened with the trial
    family. Declared in `.leaf/` and vendored by `page init` — the door the shipped
    suggestion comes through too, so what the licensing does here is what a project
    gets rather than what a fixture arranged."""
    monkeypatch.chdir(tmp_path)
    trial_family(tmp_path)
    page = tmp_path / "page"
    initialized = CliRunner().invoke(
        cli_model.cli, ["page", "init", "--package", "./.leaf", str(page)]
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
    for the user who never had the link; headers carry route-specific metadata."""
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
            status, body = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    if error := route_answer_error(url, body):
        raise AssertionError(f"{url} answered {status} outside its schema: {error}")
    return status, body


def fetch_hanging_up(url, data=None):
    """`fetch(url, data, token=None)` that closes the connection from the client.

    Whichever side closes a TCP connection first holds its address in TIME_WAIT, and
    a server rebinding its recorded port waits that out (`hosting.listening_socket`):
    a minute on Linux. urllib asks the server to close, so a test that fetches and
    then restarts the server at the same URL waits that minute at every restart. This
    keeps the connection alive and hangs up itself, leaving the cooldown on its own
    ephemeral port. The URL carries the page's key, as an announced URL does.
    """
    parts = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(
        parts.hostname, parts.port, timeout=STATED_TIMEOUT
    )

    def request(method, path, body=None, headers=None):
        connection.request(
            method, f"{path}?{parts.query}", body=body, headers=headers or {}
        )
        response = connection.getresponse()
        return response.status, response.read()

    try:
        if data is None:
            return request("GET", parts.path or "/")
        _, state = request("GET", "/api/state")
        layer = json.loads(state)["layer"]["generation"]
        return request("POST", parts.path, data, {"Leaf-Layer": layer})
    finally:
        connection.close()


HELD_LEASES = []


def fixture_service(directory, port: int, lifetime: str = "persistent") -> dict:
    """Record the desired service of a `server run` on `port`, as it records its own."""
    service = {
        "host": "127.0.0.1",
        "bind": "127.0.0.1",
        "port": port,
        "enabled": True,
        "lifetime": lifetime,
        "server_id": "fixture-server",
    }
    write_record(directory / "service.json", service)
    return service


def serving(directory, port: int, lifetime: str = "persistent") -> None:
    """Hold the serving incarnation lease of a live `server run`, taken as it takes it."""
    directory.mkdir(parents=True, exist_ok=True)
    service = fixture_service(directory, port, lifetime)
    lease = hosting_model._take_server_lease(directory)
    lease.write(service["server_id"].encode())
    lease.flush()
    HELD_LEASES.append(lease)


def available_loopback_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


_HELD_SELECTION = """
import sys
from pathlib import Path

from leaf import session
from leaf.__main__ import main

transaction = session.PageTransaction
marker, page = Path(sys.argv[1]), Path(sys.argv[2]).resolve()


def selected(page_dir, *args, **options):
    if Path(page_dir).resolve() == page:
        session.PageTransaction = transaction
        marker.write_text("selected", encoding="utf-8")
        sys.stdin.readline()
    return transaction(page_dir, *args, **options)


session.PageTransaction = selected
sys.argv = ["leaf", *sys.argv[3:]]
main()
"""


def held_selection(marker: Path, page: Path, *args: str) -> list[str]:
    """`leaf ARGS` as a child whose watch holds after it selects `page` and before
    it reads that page under its lease: it writes `marker` there, and goes on once a
    line reaches its stdin. A watch's first transaction on a page is that read
    (`session.Watch.tick`), so whatever the test does meanwhile, such as
    transferring the claim, wins the race the lease must then decline."""
    return [sys.executable, "-c", _HELD_SELECTION, str(marker), str(page), *args]


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
    this sweep stopped every server running there (tests/AGENTS.md, "Processes and
    servers")."""
    yield
    retire_test_services(tmp_path, isolated_session)


def retire_bridge(lock):
    """End the bridge holding `lock` once it has published its address."""
    record = wait_for(
        lambda: files_model.read_json(lock.with_suffix(".json")),
        bool,
        failure="a started bridge never published its address",
    )
    os.kill(record["pid"], signal.SIGTERM)
    wait_for(
        lambda: leases_model.lock_is_held(lock),
        lambda held: not held,
        failure="a bridge outlived its test",
    )


def retire_test_services(tmp_path, isolated_session):
    """End the test's harnesses before removing their coordination files.

    Detached adapters hold session leases outside any subprocess group. Their
    lifecycle must end while its state directory still exists, so they can
    retire normally rather than retry a deleted startup lock forever.
    In-process title workers also finish before page loans or state disappear.
    """
    while HELD_LEASES:
        leases_model.release_lease(HELD_LEASES.pop())
    for path in (isolated_session / "sessions").glob(
        f"*.{cleanup_model.SESSION_SUFFIX}"
    ):
        record = files_model.read_json(path)
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            cleanup_model.end_session(record["id"])
    # A Claude Code hook leaves Leaf's bridge running while its session lives.
    for lock in (isolated_session / "bridge").glob("*.lock"):
        if leases_model.lock_is_held(lock):
            retire_bridge(lock)
    for root in (tmp_path, isolated_session):
        for lease in root.rglob("server.lock"):
            if server_model.running_server(lease.parent):
                hosting_model.cmd_stop(lease.parent)
    wait_for(
        lambda: [
            path.name
            for path in (isolated_session / "sessions").glob("*.adapter")
            if leases_model.lock_is_held(path)
        ],
        lambda held: not held,
        failure="a detached adapter outlived its test's ended sessions",
    )
    # Servers have stopped accepting input, so no new title request can start.
    # The worker reports under the page lock even when its generator fails.
    for worker in threading.enumerate():
        if worker.name == "leaf-thread-title":
            worker.join(timeout=STATED_TIMEOUT)
            assert not worker.is_alive(), "a title worker outlived its test's page"


@contextmanager
def fresh_process():
    """What a newly started process holds of every page: nothing (`page_memory`)."""
    kept = page_memory_model._memories
    page_memory_model._memories = page_memory_model.PageMemories()
    try:
        yield
    finally:
        page_memory_model._memories = kept


def neighbour_page(directory, title=None, dead=False, published=True, port=59999):
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
    write_revision(directory, 1, html.encode())
    # A neighbour waiting on its user: a closed one is not listed (`other_leaves`).
    declare(directory)
    if published:
        append_carried_log_record(
            directory,
            {
                "kind": "note",
                "author": "agent",
                "version": 1,
                "revision": 1,
                "text": "t",
            },
        )
    if dead:
        fixture_service(directory, port)
    else:
        serving(directory, port)
    server_rows_model.RowPublisher(directory, "fixture-server").refresh()
    return server_model.page_url("127.0.0.1", port, server_model.host_key())


def declare_idle(page_dir):
    """Write the page's `idle` declaration directly, past `leaf page close`'s refusal
    over unanswered moves, for a test whose subject is what an idle page does."""
    with service_model.PageTransaction(page_dir) as page:
        return page.set_status("idle")


def declared(page_dir):
    """The agent's declaration as the page's log holds it (`activity.declaration`)."""
    from leaf.activity import declaration

    return declaration(events_model.read_events(page_dir))


def status_and_stream(page_dir):
    """The agent's declaration beside what the harness streams, for a test that
    asserts a write moved neither."""
    return declared(page_dir), service_model.read_stream(page_dir)


def declare(page_dir, state="waiting", *, ts=None, **voice):
    """Seed the agent's declaration as the log holds it, a `status` event, for a test
    of how a page reads it: `state`, dated `ts` (now by default) and
    spoken in `voice` (`agent`, `session`). Raw, so a test can date it in the past;
    `leaf page open` is the command an agent runs."""
    return append_carried_log_record(
        page_dir,
        {
            "kind": "status",
            "author": "agent",
            "state": state,
            **({"ts": ts} if ts else {}),
            **voice,
        },
    )


def declare_work(page_dir, line, *, item=None, ts=None, **voice):
    """Seed the agent's work in hand as the log holds it, for a test of how a page
    reads it: a `start` on `item`, or on the page's own task, which this opens when
    the page has none, dated `ts` (now by default) and spoken in `voice` (`agent`,
    `session`, `turn`). Raw, so a test can date it in the past; `working` is the
    command an agent runs."""
    from leaf.todos import TodoReading

    if item is None:
        item = (
            next(
                (
                    task["id"]
                    for task in TodoReading(events_model.read_events(page_dir)).owed
                    if task["subject"] == {"kind": "page"}
                ),
                None,
            )
            or append_carried_log_record(
                page_dir,
                {
                    "kind": "todo",
                    "author": "agent",
                    "owner": "agent",
                    "subject": {"kind": "page"},
                    "title": "Work on the page",
                    **({"ts": ts} if ts else {}),
                },
            )["id"]
        )
    return append_carried_log_record(
        page_dir,
        {
            "kind": "start",
            "author": "agent",
            "item": item,
            "text": line,
            **({"ts": ts} if ts else {}),
            **voice,
        },
    )


def end_work(page_dir):
    """End every open task on the page as a whole, `declare_work`'s and `working`'s,
    so nothing the agent opened for itself is in hand any more."""
    from leaf.todos import TodoReading

    for task in TodoReading(events_model.read_events(page_dir)).owed:
        if task["subject"] == {"kind": "page"}:
            append_carried_log_record(
                page_dir,
                {
                    "kind": "todo_end",
                    "author": "agent",
                    "todo": task["id"],
                    "outcome": "done",
                },
            )


def end_work_on(page_dir, subject):
    """End the open tasks on the thread or widget `subject` names, done."""
    from leaf.todos import TodoReading
    from leaf.work import page_subject

    named = page_subject(page_dir, events_model.read_events(page_dir), subject)
    for task in TodoReading(events_model.read_events(page_dir)).owed:
        if task["subject"] == named:
            ended = CliRunner().invoke(
                cli_model.cli, ["task", "end", str(page_dir), task["id"], "done"]
            )
            assert ended.exit_code == 0, ended.output


def newest_move(page_dir, widget):
    """The id of the user's newest move on `widget`, the item a start on it names."""
    return next(
        event["id"]
        for event in reversed(events_model.read_events(page_dir))
        if event["kind"] == "action"
        and event["author"] == "user"
        and event["widget"] == widget
    )


def _start(page_dir, item, line):
    """`leaf task start`: take a move or task in hand with the status's line."""
    return CliRunner().invoke(
        cli_model.cli, ["task", "start", str(page_dir), str(item), "--text", line]
    )


def working(page_dir, line, subject="page"):
    """Show work no move asked for: open a task on `subject` (the page, unless a
    thread or widget is named) and start it with `line`, as an agent does. Reuses the
    page's open task on that subject, so a test can say what it does next. Returns the
    start's record."""
    from leaf import event_log as log_model
    from leaf.todos import TodoReading
    from leaf.work import page_subject

    named = (
        {"kind": "page"}
        if subject == "page"
        else page_subject(page_dir, log_model.read_events(page_dir), subject)
    )
    task = next(
        (
            task
            for task in TodoReading(log_model.read_events(page_dir)).owed
            if task["subject"] == named
        ),
        None,
    )
    if task is None:
        opened = CliRunner().invoke(
            cli_model.cli,
            ["task", "create", str(page_dir), subject, "--title", line[:80]],
        )
        assert opened.exit_code == 0, opened.output
        task = json.loads(opened.output.splitlines()[-1])
    started = _start(page_dir, task["id"], line)
    assert started.exit_code == 0, started.output
    return json.loads(started.output.splitlines()[-1])


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
        deadline = time.monotonic() + STATED_TIMEOUT

        def post():
            while not stopped.wait(POLL_INTERVAL):
                if server_model.running_server(page_dir):
                    append_carried_log_record(
                        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
                    )
                    return
                if time.monotonic() > deadline:
                    declare_idle(page_dir)
                    return

        thread = threading.Thread(target=post, daemon=True)
        thread.start()
        posting.append(thread)

    yield watch
    stopped.set()
    for thread in posting:
        thread.join(timeout=STATED_TIMEOUT)


class ContextRecord:
    """Claude Code's transcript, as tests stand it in (`Harness.entered_context`):
    every inline handover a hook printed reached the model's context, except those
    into the turns a test has `dropped`, as Escape during a prompt hook drops them."""

    def __init__(self):
        self.dropped: set[str] = set()

    def entered(self, harness) -> set[str]:
        from leaf.delivery import pickup_receipts
        from leaf.event_log import read_events

        return {
            event_id
            for page in service_model.owned_pages(harness.session)
            for pickup in pickup_receipts(read_events(page), phase="opened")
            if pickup["session"] == harness.session
            for event_id in pickup["events"]
            if pickup["turn"] not in self.dropped
        }


@pytest.fixture
def context_record(monkeypatch):
    record = ContextRecord()
    monkeypatch.setattr(
        harness_model.ClaudeCodeHarness,
        "entered_context",
        lambda harness, payload: record.entered(harness),
    )
    return record


@pytest.fixture
def claimed(page_dir, monkeypatch, context_record):
    """A page claimed by session s1, the way Claude Code's environment claims one:
    it puts the session id and its pid into every Bash tool call."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", str(os.getpid()))
    service_model.claim_page(page_dir)
    return page_dir


def _launched_as(monkeypatch, argv: list[str]) -> None:
    """Read this process, the CLAUDE_PID `claimed` names, as a Claude Code launched
    with `argv`, which is what says whether a watch follows its turns
    (`ClaudeCodeHarness.watches_between_turns`). Other processes read as they run."""
    launched = harness_model.process_argv
    monkeypatch.setattr(
        harness_model,
        "process_argv",
        lambda pid: argv if pid == os.getpid() else launched(pid),
    )


@pytest.fixture
def interactive(monkeypatch):
    """Claude Code at its terminal, where a watch follows each turn and gives input
    that arrives as the turn ends a turn of its own."""
    _launched_as(monkeypatch, ["claude"])


@pytest.fixture
def printing(monkeypatch):
    """Claude Code under plain `--print`, where no watch follows the run, so its Stop
    hook hands over the input pending as the turn ends."""
    _launched_as(monkeypatch, ["claude", "-p", "review the page"])


@pytest.fixture(scope="session")
def codex_program(tmp_path_factory):
    """A program named `codex` to run a session under, which is the whole of what
    `CodexHarness.lifetime` looks for above a leaf: a copy of this interpreter wearing that
    name. The name has to be the executable's own, because what a process reports
    is what the kernel loaded — a `#!` script and a symlink both wear the
    interpreter's. A framework Python's sys.executable is a launcher that re-execs
    Python.app, so copy the running binary itself.

    macOS kills a copy on exec, silently and with SIGKILL, when its signature no
    longer holds at the new path. A framework build's Python.app binary is signed
    as part of its bundle, so a copy without the bundle's Info.plist fails that
    check. Signing the copy ad hoc makes it valid wherever it lies, whichever
    Python runs the suite."""
    program = tmp_path_factory.mktemp("codex-program") / "codex"
    shutil.copy(psutil.Process().exe(), program)
    if sys.platform == "darwin":
        subprocess.run(["codesign", "--force", "--sign", "-", program], check=True)
    return program


@pytest.fixture
def codex_queue(tmp_path):
    """Replace the external queue CLI while exercising real preview delivery.

    The executable acknowledges help and records submitted arguments. Tests may
    set PREVIEW_QUEUE_AVAILABLE=False to exercise an unsupported installation.
    This is separate from codex_program, which models kernel process ancestry.
    A recorded queue call appears only once its complete JSON is readable.
    """
    executable = tmp_path / "queue-bin" / "codex"
    executable.parent.mkdir()
    queued = tmp_path / "queued.json"
    executable.write_text(
        f"""#!{sys.executable}
import os
import sys
from pathlib import Path
from leaf.state import write_json

# The queue command is all this models; the App Server a page server starts to
# name a thread is not here.
if sys.argv[1] == "app-server":
    sys.exit(1)
if os.environ.get("PREVIEW_QUEUE_AVAILABLE", "True") == "False":
    print("queue unsupported", file=sys.stderr)
    sys.exit(1)
if sys.argv[1:] != ["queue", "--help"]:
    write_json(Path(os.environ["PREVIEW_QUEUE_RECORD"]), sys.argv[1:])
print("queued")
"""
    )
    executable.chmod(0o755)
    return {
        "PATH": f"{executable.parent}{os.pathsep}{os.environ['PATH']}",
        "PREVIEW_QUEUE_RECORD": str(queued),
    }


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
    own standard library in. It is the copy's alone: the runner drops it before
    the shell, so the command gets the environment the test gave it, and a
    Python below it on another base, such as a prepared installation's, still
    finds its own."""
    runner = (
        "import os, subprocess, sys; "
        "os.environ.pop('PYTHONHOME'); "
        "sys.exit(subprocess.run(['/bin/sh', '-c', sys.argv[-1]]).returncode)"
    )

    def start(
        command, env, *, app_server=False, finished=None, **kwargs
    ) -> subprocess.Popen:
        # `app-server` is the whole difference between the app's shared harness and
        # one session's own process — same program, same ancestry, one word in
        # the argv — so it is the one factor this varies. The runner reads the
        # last word either way, which is what keeps that the only difference.
        hosting = ["app-server"] if app_server else []
        shell_command = f"{command}; exit"
        if finished is not None:
            # Create `finished` once the command has, and keep the fake harness
            # alive until a line or the end of its stdin. A test can then hand
            # its lifetime to the worker before release (`release_held`); unlike
            # a real task, this harness would otherwise die with its command. The
            # worker holds the pipe's other end, so the harness also ends when the
            # worker does, however it ends.
            shell_command = (
                f"{command}; result=$?; "
                f"touch {shlex.quote(str(finished))}; "
                "read -r released; "
                "exit $result"
            )
            kwargs["stdin"] = subprocess.PIPE
        return spawn(
            [str(codex_program), "-c", runner, *hosting, shell_command],
            env={**env, "PYTHONHOME": sys.base_prefix},
            **kwargs,
        )

    return start


@pytest.fixture
def codex_claimed_page(tmp_path, under_codex, codex_env):
    """A Codex-owned server before delivery starts, for adapter lifecycle tests.

    Public handoff connects delivery too. These tests choose their own transport
    or exercise a direct wait, so setup takes the lower-level claim and serve.
    """
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
    program = """
import json, sys
from pathlib import Path
from leaf.harness import session_harness
from leaf.hosting import start_server
from leaf.service import claim_page
page = Path(sys.argv[1])
claim_page(page)
started = start_server(page, harness=session_harness())
print(json.dumps({"url": started.url}))
"""
    finished = tmp_path / "page-host-finished"
    started = under_codex(
        shlex.join([sys.executable, "-c", program, str(page)]),
        env,
        finished=finished,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    release_codex_command(page, started, finished)
    out, err = started.communicate(timeout=STATED_TIMEOUT)
    assert started.returncode == 0, f"{out}{err}"
    assert json.loads(out)["url"].startswith("http://127.0.0.1:")
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
    Code's door, because that harness states its session's pid outright and the
    test wants a process of its own in that role; which harness claimed the page is
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
        started = json.loads(process.stdout.readline())
        assert started["url"].startswith("http://127.0.0.1:")
        assert started["lifetime"] == "session"
        return process

    return start


def start_server_command(page_dir, *flags, session_id="starter"):
    """Run `server start` from a harness session and wait for the command to return."""
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
        timeout=STATED_TIMEOUT,
        check=False,
    )


@pytest.fixture
def persistent_server(spawn, sessionless):
    """`server run` from a bare shell — a terminal, a login item — held to what it
    prints, the URL and the lifetime it recorded.

    A persistent serve is one nothing reaps: it declines the claim, so no watcher
    starts, and a run killed while one is up leaves a process only a person can
    stop (tests/AGENTS.md, "Processes and servers"). A
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
        started = json.loads(process.stdout.readline())
        assert started["url"].startswith("http://127.0.0.1:")
        assert started["lifetime"] == "persistent"
        return process

    return start


# ---------- comment: the anchor written without a browser ----------


def published(page_dir):
    result = stamp(page_dir, "first")
    assert result.exit_code == 0, result.output
    return page_dir


def comment(page_dir, *args):
    """Open a thread, with the posted event on stdout for the caller to read."""
    return CliRunner().invoke(cli_model.cli, ["thread", "create", str(page_dir), *args])


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
            "detail": {"value": text},
        },
    )


SUGGESTED = before_choice(PAGE, SUGGESTION)


def suggested(page_dir):
    """A published v1 carrying the sug-refill suggestion, both slots pending."""
    (page_dir / "index.html").write_text(SUGGESTED)
    return published(page_dir)


def add_test_widget(package: Path, tag: str, *, upgrade: bool = False) -> dict:
    """Author one widget in a package, creating the package first if it is missing.

    What a package author gets from `package init --widget`: the product's starter
    declaration and, for an upgraded widget, its starter module, plus a framed block in
    the theme. A test specializes the declaration in `registry.json` and rewrites the
    module where its subject needs behavior of its own."""
    created = CliRunner().invoke(cli_model.cli, ["package", "init", str(package)])
    assert created.exit_code == 0, created.output
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    declaration = element_declaration(tag, upgrade=upgrade)
    registry[tag] = declaration
    registry_path.write_text(json.dumps(registry, indent=2))
    with (package / "widgets.css").open("a") as theme:
        theme.write(
            f"\n{tag} {{\n"
            "  display: block;\n"
            "  margin: var(--sp-3) 0;\n"
            "  padding: var(--sp-3);\n"
            "  border: 1px solid var(--rule);\n"
            "  border-radius: var(--r);\n"
            "  background: var(--card);\n"
            "  --lf-block-frame: 1;\n"
            "}\n"
        )
    if upgrade:
        (package / "widgets" / f"{tag}.js").write_bytes(
            packages_model.starter_widget_module(tag)
        )
    return declaration


@pytest.fixture
def declared_reading_package(tmp_path, monkeypatch):
    """A module-free vocabulary for the shared said-word contract."""
    monkeypatch.chdir(tmp_path)
    package = tmp_path / ".leaf"
    add_test_widget(package, "lf-reading")
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    reading = registry["lf-reading"]
    reading["properties"].update({"label": {"type": "string"}})
    reading["x-says"] = {"label": "before"}
    registry_path.write_text(json.dumps(registry))
    return "./.leaf"


def element_declaration(tag: str, *, upgrade: bool = False) -> dict:
    """The product's starter declaration for `tag`, or, without `upgrade`, the same
    markup block with no module behind it."""
    declaration = packages_model.starter_element_declaration(tag)
    if not upgrade:
        declaration["x-upgrade"] = False
        del declaration["x-verbatim"]
    return declaration


class YamlDocument(str):
    """Text that `snapshot.check` records as `snapshot.yaml` in the test's folder
    under `_regtest_outputs/`, so an editor reads it as YAML: its `#` header says
    what the file is, and everything under the header is the recorded data."""


class Prose(str):
    """A string a YAML snapshot writes as a folded `>-` block wrapped to the line,
    or a literal block when it already has line breaks."""


class Json(dict):
    """A mapping a YAML snapshot writes as JSON, which YAML reads back as the same
    mapping, so it reads character for character like the JSON file it came from."""


class _SnapshotDumper(yaml.SafeDumper):
    # Prose folds at the width; a JSON value stays on one line, as its own file has
    # it. The emitter reads this width on every break it considers.
    @property
    def best_width(self):
        return sys.maxsize if self.flow_level else self._best_width

    @best_width.setter
    def best_width(self, width):
        self._best_width = width

    def increase_indent(self, flow=False, **_indentless):
        # A list sits indented under its key, as a person writes one.
        return super().increase_indent(flow, False)


_SnapshotDumper.add_representer(
    Prose,
    lambda dumper, text: dumper.represent_scalar(
        "tag:yaml.org,2002:str", text, style="|" if "\n" in text else ">"
    ),
)


def _json_node(dumper, value):
    if isinstance(value, dict):
        return yaml.MappingNode(
            "tag:yaml.org,2002:map",
            [(_json_node(dumper, k), _json_node(dumper, v)) for k, v in value.items()],
            flow_style=True,
        )
    if isinstance(value, list):
        return yaml.SequenceNode(
            "tag:yaml.org,2002:seq",
            [_json_node(dumper, item) for item in value],
            flow_style=True,
        )
    if isinstance(value, str):
        return yaml.ScalarNode("tag:yaml.org,2002:str", value, style='"')
    # true, false, null and numbers are spelled the same in both.
    return dumper.represent_data(value)


_SnapshotDumper.add_representer(Json, _json_node)
# A list of values stays on one line, as `[0, 0]`; a list of records goes one to a
# line.
_SnapshotDumper.add_representer(
    list,
    lambda dumper, items: dumper.represent_sequence(
        "tag:yaml.org,2002:seq",
        items,
        flow_style=not any(isinstance(item, dict) for item in items),
    ),
)


def words(output: str) -> str:
    """The words in what a command printed (`cli`): each JSON value's `error` and
    every `text` within it, one to a line."""
    found = []

    def collect(value):
        if isinstance(value, dict):
            found.extend(value[key] for key in ("error", "text") if key in value)
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    decoder, at = json.JSONDecoder(), 0
    while at < len(output.rstrip()):
        value, at = decoder.raw_decode(output, at)
        collect(value)
        at = len(output) - len(output[at:].lstrip())
    return "\n".join(found)


def said(stderr: str) -> list[dict]:
    """What a command said beside its result: each JSON object it printed on stderr
    (`cli`), its words as `Prose`."""
    return [
        {
            key: Prose(value) if key in ("text", "error") else value
            for key, value in json.loads(line).items()
        }
        for line in stderr.splitlines()
    ]


def yaml_block(data: dict) -> str:
    """`data` as a YAML snapshot writes it."""
    return yaml.dump(
        data,
        Dumper=_SnapshotDumper,
        sort_keys=False,
        allow_unicode=True,
        # PyYAML breaks at the first space past this column, so a line runs a word
        # longer.
        width=78,
    )


def yaml_document(header: str, cases: dict) -> YamlDocument:
    """`cases` as YAML, a blank line between top-level keys, under `header` as a
    comment block."""
    comment = "\n".join(f"# {line}".rstrip() for line in header.splitlines())
    body = "\n".join(yaml_block({name: case}) for name, case in cases.items())
    return YamlDocument(f"{comment}\n\n{body}")


class _YamlSnapshotHandler(BaseSnapshotHandler):
    FILE = "snapshot.yaml"

    def __init__(self, *_configuration):
        pass

    def save(self, folder, obj):
        Path(folder, self.FILE).write_text(obj, encoding="utf-8")

    def load(self, folder):
        return YamlDocument(Path(folder, self.FILE).read_text(encoding="utf-8"))

    def show(self, obj):
        return obj.splitlines()

    def compare(self, current_obj, recorded_obj):
        return current_obj == recorded_obj

    def show_differences(self, current_obj, recorded_obj, *_presentation):
        return list(
            difflib.unified_diff(
                recorded_obj.splitlines(),
                current_obj.splitlines(),
                "recorded",
                "current",
                lineterm="",
            )
        )


# In front of the plugin's own handler, which takes every str.
SnapshotHandlerRegistry.add_handler(
    lambda obj: isinstance(obj, YamlDocument), _YamlSnapshotHandler, insert_front=True
)


def consume_pending_input(session_id):
    """Hand the session its pending input as a hook does inline: one complete
    envelope, confirmed as it is handed over."""
    from leaf import delivery, hook_transport, state

    batches = [
        plan.batch
        for plan in hook_transport.read_plans(session_id)
        if plan.batch and plan.harness.hooks_carry()
    ]
    if not batches:
        return None
    payload = delivery.freeze_delivery(batches)
    delivery.receive_held(payload, session_id, state.session_record(session_id))
    return payload


def claim_and_wait_command(page: Path) -> str:
    """Explicit ownership handoff followed by its ordinary observing wait."""
    return (
        shlex.join([*LEAF_COMMAND, "page", "claim", str(page), "--manual-delivery"])
        + " >/dev/null && "
        + shlex.join([*LEAF_COMMAND, "wait", str(page)])
    )


def last_deliverable_seq(page_dir: Path) -> int:
    """The last event a wait can print, excluding page-owned pickup records."""
    return service_model.unacknowledged(events_model.read_events(page_dir), 0)[-1][
        "seq"
    ]


def delivered(capsys) -> tuple[dict, dict, list[dict]]:
    """Read and confirm the complete input a direct wait printed."""
    return woken(capsys.readouterr().out)


def woken(output: str, session: str | None = None) -> tuple[dict, dict, list[dict]]:
    """Receive an explicit wait's envelope or a native hook watch's wake.

    Explicit waits confirm their own captured input; a native watch hands its
    pending input through the hook transport.
    """
    lines = output.splitlines()
    decoder = json.JSONDecoder()
    payload = None
    # A served page can print a JSON restart diagnostic before the wait envelope.
    for i, line in enumerate(lines):
        if not line.startswith("{"):
            continue
        candidate, _ = decoder.raw_decode("\n".join(lines[i:]))
        if (
            isinstance(candidate, dict)
            and candidate.get("format") == delivery_model.DELIVERY.format
        ):
            payload = candidate
            break
    if payload is not None:
        assert payload["acknowledge"] is not None
        delivery_model.receive(
            payload, session or session_model.session_harness().session
        )
    else:
        assert "has new input" in output, output
        payload = consume_pending_input(
            session or session_model.session_harness().session
        )
        assert payload["acknowledge"] is None
    assert payload["format"] == delivery_model.DELIVERY.format
    [batch] = payload["batches"]
    return payload, batch, batch["events"]


def continued(output: str | dict) -> str:
    """What a Claude Code session's Stop hook continues the turn with. It speaks
    through the harness's non-error channel, so the user reads "Stop hook additional
    context" rather than "Stop hook error"."""
    answer = json.loads(output) if isinstance(output, str) else output
    assert "decision" not in answer, answer
    assert answer["hookSpecificOutput"]["hookEventName"] == "Stop"
    return answer["hookSpecificOutput"]["additionalContext"]


def printed(output: str) -> tuple[dict, dict, list[dict]]:
    """Read the one delivery a wait printed, for a harness whose wait is its watcher
    (a bare shell, a Codex watcher): its reader confirms it with `delivery ack`."""
    payload = json.loads(output)
    assert payload["format"] == delivery_model.DELIVERY.format
    assert payload["acknowledge"] is not None
    [batch] = payload["batches"]
    return payload, batch, batch["events"]


@pytest.fixture
def codex_loop(monkeypatch):
    """A Codex task running its own `leaf wait` loop, the harness
    session whose wait prints each delivery for its reader to confirm. This process,
    and every command it spawns, carries the task's identity in place of Claude
    Code's. Call the value with a page to record the task's claim on it: a claim
    taken from here would look for a codex process above the suite and find none."""
    for name in CLAUDE_IDENTITY:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "codex-thread")
    return lambda page: record_claim(
        page, id="codex-thread", harness="codex", agent="Codex"
    )


def freeze_events(page_dir: Path, events: list[dict]) -> dict:
    """Freeze selected page events through the harness-neutral delivery boundary."""
    with service_model.PageTransaction(page_dir) as transaction:
        stored = {event["id"]: event for event in transaction.events}
        batch = delivery_model.batch_data(
            page_dir,
            transaction,
            [stored[event["id"]] for event in events],
        )
    return delivery_model.freeze_delivery(
        [batch], acknowledge=session_model.wait_acknowledgement(None, page_dir)
    )


def delivery_through(page_dir: Path, seq: int) -> str:
    """Freeze the complete deliverable prefix used to arrange a received fixture."""
    events = service_model.unacknowledged(events_model.read_events(page_dir), 0)
    return freeze_events(
        page_dir, [event for event in events if event["seq"] <= int(seq)]
    )["id"]


def receive_through(page_dir: Path, seq: int) -> None:
    harness = session_model.session_harness()
    with service_model.PageTransaction(page_dir) as page:
        held = harness is not None and page.claim_of(harness.session) is not None
    if not held:
        service_model.claim_page(page_dir)
    delivery_model.receive_delivery(delivery_through(page_dir, seq))


def delivered_ref(page_dir: Path, input_id: str) -> str:
    """The `answer.ref` the page's log recorded for a received input, checked to
    resolve to that input in its delivery's envelope."""
    events = events_model.read_events(page_dir)
    ref = delivery_model.current_responses(page_dir, events)[input_id]["ref"]
    assert delivery_model.response_address(ref)["input"]["id"] == input_id
    return ref


class _CheckedAppServerSocket:
    """The stand-in's end of an App Server connection, which holds each message to
    Codex's schema for its sender: what Leaf sends it, and what it sends Leaf."""

    def __init__(self, socket, found: list):
        self._socket = socket
        self._found = found

    def _check(self, raw, sender: str):
        message = json.loads(raw)
        if isinstance(message, dict):
            collect_app_server_error(self._found, message, sender)

    def recv(self, *args, **kwargs):
        raw = self._socket.recv(*args, **kwargs)
        self._check(raw, "Client")
        return raw

    def __iter__(self):
        for raw in self._socket:
            self._check(raw, "Client")
            yield raw

    def send(self, raw):
        self._check(raw, "Server")
        return self._socket.send(raw)

    def __getattr__(self, name):
        return getattr(self._socket, name)


@pytest.fixture(name="app_server")
def app_server_fixture(app_server_messages):
    """Serve an App Server stand-in for one handler, until the test ends. The
    handler's socket holds every message either side sends to Codex's schema
    (`app_server_messages`).

    The observer under test connects over a real websocket, so a test that made its
    own server owned three things: the server, the thread serving it, and the stop
    that ends both. One of them ran that stop on the last line of the test body,
    which is the line a failing assertion never reaches — the thread then served on
    for the rest of the worker, holding its socket, under later tests that had
    nothing to do with it.

    Returns the endpoint to connect to: a loopback port, or the Unix socket path the
    caller names.
    """
    serving = []

    def serve(handle, socket_path=None) -> str:
        def checked(socket):
            return handle(_CheckedAppServerSocket(socket, app_server_messages))

        server = (
            serve_unix_websocket(checked, str(socket_path))
            if socket_path
            else serve_websocket(checked, "127.0.0.1", 0)
        )
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        serving.append((server, worker))
        return (
            f"unix://{socket_path}"
            if socket_path
            else f"ws://127.0.0.1:{server.socket.getsockname()[1]}"
        )

    yield serve
    for server, worker in reversed(serving):
        server.shutdown()
        worker.join(timeout=STATED_TIMEOUT)


def codex_records(session_id: str) -> list[tuple[Path, dict]]:
    directory = codex_state_model.delivery_dir(session_id)
    return [
        (path, files_model.read_json(path)) for path in sorted(directory.glob("*.json"))
    ]


def _observer() -> codex_adapter_model.TaskConnection:
    """An observer that has not connected, so a test feeds it notifications itself."""
    connection = codex_adapter_model.TaskConnection("ws://127.0.0.1:1", "codex-thread")
    connection.connected.set()
    return connection


def _delivery_item(payload: dict) -> dict:
    """The transcript item a turn carrying one App Server delivery holds."""
    return {
        "id": "delivery",
        "type": "functionCallOutput",
        "name": "leaf_delivery",
        "output": json.dumps(payload),
    }


def _codex_delivery(page_dir, text="Answer this"):
    append_carried_log_record(
        page_dir, {"kind": "comment", "author": "user", "text": text}
    )
    return codex_model.prepare_codex_delivery(
        page_dir,
        harness_model.EmbeddedHarness("codex-thread", "Codex", os.getpid()),
    )


# A page whose suggestion answers c1, which is the one shipped shape where the
# gesture that settles a thread is made on a widget standing outside it.
SETTLING_PAGE = PAGE.replace(
    '<div id="plan-choice-decision">',
    '<lf-suggestion id="sug-refill" resolves="c1">\n'
    "  <lf-old><p>The manual sightings log.</p></lf-old>\n"
    "  <lf-new><p>Switch the north feeder to thistle.</p></lf-new>\n"
    '</lf-suggestion>\n<div id="plan-choice-decision">',
)


SETTLING_DECISION = {
    "kind": "comment",
    "id": "c1",
    "author": "user",
    "revision": 1,
    "anchor": {"section": "plan-choice-decision"},
    "drawing": {
        "strokes": [[[-20, 74], [50, 10], [120, 74]]],
        "box": [640.5, 96],
        "viewport": [1200, 900],
        "scheme": "light",
    },
}


SETTLING_ACCEPT = {
    "kind": "action",
    "author": "user",
    "revision": 1,
    "widget": "sug-refill",
    "action": "decide",
    "detail": {"outcome": "accept"},
}


def _settling_page(page_dir):
    (page_dir / "index.html").write_text(SETTLING_PAGE)
    append_carried_log_record(page_dir, dict(SETTLING_DECISION))
    result = check(page_dir)
    assert result.exit_code == 0, result.output
    publish(page_dir)
    serving(page_dir, 1)


# One authored id for the group, so an action can name it. Its options already
# carry ids, which is what lets a floor land inside the widget rather than on it.
PICKS_PAGE = PAGE.replace("<lf-options>", '<lf-options id="picks">')


def _interaction_prompt_evidence(page, value):
    """Keep complete output, replacing only run-specific identities and times."""
    events = events_model.read_events(page)
    identities = {event["id"]: f"event-{event['seq']}" for event in events}

    def stable(item):
        if isinstance(item, dict):
            return {
                key: "<time>"
                if key in {"ts", "created_at"}
                else "<attempt>"
                if key == "attempt"
                else "<claim-session>"
                if key == "claim" and child is not None
                else stable(child)
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [stable(child) for child in item]
        if isinstance(item, str):
            item = item.replace(str(page), "<page>")
            item = re.sub(
                r'(<leaf-delivery id=")[0-9a-f]{8}(" operation="delivery read" />)',
                r"\1<delivery>\2",
                item,
            )
            for source, replacement in identities.items():
                item = item.replace(source, replacement)
            return Prose(item) if " " in item or "\n" in item else item
        return item

    return stable(value)


def _watched(page_dir):
    """A claimed page this session watches, so only its debts reach the hooks."""
    session_model.cmd_waiting(page_dir)
    session = service_model.page_claim(page_dir)
    lease = leases_model.take_lease(
        leases_model.waiter_lease_path(page_dir, session["id"])
    )
    assert lease
    return lease


def adapter_lease(session_id, app_server):
    """Hold `session_id`'s adapter lease as a running adapter does, naming the App
    Server it starts turns over, or None for one that queues them
    (`codex_adapter.run_adapter`)."""
    lease = leases_model.take_lease(leases_model.adapter_lease_path(session_id))
    assert lease
    lease.write(codex_adapter_model.ADAPTER.encode({"app_server": app_server}))
    lease.flush()
    return lease
