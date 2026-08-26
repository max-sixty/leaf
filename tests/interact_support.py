"""Shared fixtures and assertions for the interact.py integration modules.

Run from the repo root:

    uv run pytest tests
"""

import errno
import fcntl
import http.client
import http.cookiejar
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import interact
from leaf_interact import http as http_model
from leaf_interact import layer as layer_model

ROOT = Path(__file__).parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "leaf"
COMMAND_HUB_PACKAGE = ROOT / "examples" / "packages" / "command-hub"

PROBE_BOOTSTRAP = """\
import contextlib
import importlib.util
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(os.environ["INTERACT"]).resolve().parent))
spec = importlib.util.spec_from_file_location("interact", os.environ["INTERACT"])
interact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interact)
"""


def spawn_probe(spawn, page_dir, body, **environment):
    """Run a deterministic race seam in an isolated interact.py process."""
    env = {name: str(value) for name, value in environment.items()}
    return spawn(
        [sys.executable, "-c", PROBE_BOOTSTRAP + body],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ
        | {"INTERACT": str(interact.__file__), "PAGE": str(page_dir)}
        | env,
    )


def wait_for_path(path, failure):
    deadline = time.monotonic() + 10
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert path.exists(), failure


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>t</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
<script type="module" src="/leaf.js"></script>
</head>
<body>
<main>
<section id="plan">
  <h2>Plan</h2>
  <p>The cutoff lives in <a href="https://example.test/jobs/backfill.py#L88"><code>jobs/backfill.py:88</code></a>.</p>
  <lf-options>
    <lf-option id="flag-first"><lf-chip>effort: low</lf-chip><lf-chip>risk: med</lf-chip>
      <strong>Flag first</strong> Ship dark.
    </lf-option>
    <lf-option id="backfill-first" recommended><lf-chip>effort: med</lf-chip><lf-chip>risk: low</lf-chip>
      <strong>Backfill first</strong> Verify, then flip.
    </lf-option>
  </lf-options>
  <lf-diagram id="flow"><pre>
graph LR
  A --> B
  </pre></lf-diagram>
</section>
</main>
</body>
</html>
"""


@pytest.fixture
def page_dir(tmp_path, monkeypatch):
    """A page with the default and Command Hub package vocabularies and a valid v1."""
    monkeypatch.chdir(tmp_path)  # keep the project layer out of the overlay
    package = link_command_hub_package(tmp_path)
    d = tmp_path / "page"
    result = CliRunner().invoke(
        interact.cli, ["page", "init", "--package", package, str(d)]
    )
    assert result.exit_code == 0, result.output
    (d / "versions" / "v1.html").write_text(PAGE)
    return d


def check(d, version=None):
    args = ["version", "check", str(d)] + (
        ["--version", str(version)] if version else []
    )
    return CliRunner().invoke(interact.cli, args)


def publish(d, version=1):
    """Append the note event that makes a version the user-seen baseline:
    `version check` compares against the last *published* version, and an action
    can only ever be made against one the server exposed."""
    interact.append_event(
        d, {"kind": "note", "author": "claude", "version": version, "text": "published"}
    )


def page_state(d):
    events = interact.read_events(d)
    return interact.full_state(d, events, interact.published_versions(d, events))


def record_claim(page, **fields):
    """Write the canonical claim shape for lifecycle fixtures."""
    record = {
        "page": str(page.resolve()),
        "id": "s1",
        "host": "claude-code",
        "pid": os.getpid(),
        "agent": "Claude",
        "cwd": str(Path.cwd()),
        "ts": "t",
        "released": None,
        "turn_closed": None,
        **fields,
    }
    path = interact.claim_path(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    interact.write_json(path, record)
    return record


def live_versions(d):
    events = interact.read_events(d)
    return interact.published_versions(d, events)


def fragment_errors(html, registry):
    parser = interact._StructParser()
    parser.feed(html)
    parser.close()
    return interact.fragment_errors(parser, registry)


def case_alias(path):
    alias = path.with_name(path.name.swapcase())
    if not alias.exists() or not path.samefile(alias):
        pytest.skip("requires a case-insensitive filesystem")
    return alias


# HTML's phrasing content, quoted whole from the standard's own list. The theme
# inverts it to decide what makes a slot a block, and this is the only place the set
# is stated rather than derived: `link` and `meta` are in it because the standard has
# them there, not because a slot will ever hold one. A set edited down to what looked
# worth keeping could only be checked against another copy of itself.
PHRASING_CONTENT = frozenset(
    [
        "a",
        "abbr",
        "area",
        "audio",
        "b",
        "bdi",
        "bdo",
        "br",
        "button",
        "canvas",
        "cite",
        "code",
        "data",
        "datalist",
        "del",
        "dfn",
        "em",
        "embed",
        "i",
        "iframe",
        "img",
        "input",
        "ins",
        "kbd",
        "label",
        "link",
        "map",
        "mark",
        "math",
        "meta",
        "meter",
        "noscript",
        "object",
        "output",
        "picture",
        "progress",
        "q",
        "ruby",
        "s",
        "samp",
        "script",
        "select",
        "slot",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "svg",
        "template",
        "textarea",
        "time",
        "u",
        "var",
        "video",
        "wbr",
    ]
)


def _balanced(css, start):
    """What is inside a parenthesis already open at `start`, nesting included.

    A selector list carrying a :where() no longer ends at the first `)`, and reading
    it with one is how a marker arrives here missing its last bracket and passes for
    a name the list never held."""
    depth, at = 1, start
    while depth:
        depth += {"(": 1, ")": -1}.get(css[at], 0)
        at += 1
    return css[start : at - 1]


def _marker_for(declaration):
    """The attribute leaf.js paints for an `x-` declaration, or None if it paints
    none.

    Two facts, and the second is the one a stylesheet's exclusion rests on.
    PAGE_PAINT_ATTRIBUTE is the spelling every writer in the runtime shares and the
    set of names no version file may assert; a name in it says only that the runtime
    is allowed to paint it. What actually puts a mark on a page is a declaration's
    entry in one of markDeclared's tables, and a selector naming an attribute with no
    such entry excludes nothing anywhere. Both tables are read, because which of the
    two a declaration sits in is a question about where the fact holds, and the
    browser is what answers that."""
    js = (interact.ASSETS / "leaf.js").read_text()
    table = re.search(
        r"const PAGE_PAINT_ATTRIBUTE = Object\.freeze\(\{(.*?)\}\);", js, re.DOTALL
    )
    assert table, "leaf.js lost the list of attributes the runtime may paint"
    names = dict(re.findall(r'(\w+): "(data-lf-[a-z-]+)",', table.group(1)))
    assert names, "that list holds no data-lf-* name"
    tables = re.findall(
        r"const MARKED_(?:ANYWHERE|IN_PAGE) = Object\.freeze\(\{(.*?)\}\);",
        js,
        re.DOTALL,
    )
    assert len(tables) == 2, "leaf.js lost one of markDeclared's tables"
    for key in re.findall(
        rf'"{re.escape(declaration)}": PAGE_PAINT_ATTRIBUTE\.(\w+)', "".join(tables)
    ):
        assert key in names, (
            f"markDeclared paints {declaration} as PAGE_PAINT_ATTRIBUTE.{key}, which "
            "that table has no member for — the runtime writes an attribute with no "
            "name and every selector reading it matches nothing"
        )
        return names[key]
    return None


SUGGESTION = """<lf-suggestion id="sug-refill">
  <lf-old><p id="refill-rule">Refill every feeder each morning.</p></lf-old>
  <lf-new><p id="refill-camera">Refill when the camera shows it half-empty.</p></lf-new>
</lf-suggestion>
<lf-options>"""


def suggest(page_dir, version=2, markup=SUGGESTION):
    """Write and publish v1 carrying a suggestion, and an unchanged v2 to
    check against."""
    (page_dir / "versions" / "v1.html").write_text(PAGE.replace("<lf-options>", markup))
    publish(page_dir)
    (page_dir / "versions" / f"v{version}.html").write_text(
        PAGE.replace("<lf-options>", markup)
    )


def decide(page_dir, outcome, widget="sug-refill"):
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": widget,
            "action": outcome,
            "detail": {},
        },
    )


def _decided(page_dir, words):
    """v1 carrying a draft the user has since rewritten, and the log that
    says so. Whatever v2 does about it, `version check` is what has to notice."""
    (page_dir / "versions" / "v1.html").write_text(
        PAGE.replace(
            "<h2>Plan</h2>",
            f'<h2>Plan</h2><lf-draft id="d1"><pre>{words}</pre></lf-draft>',
        )
    )
    publish(page_dir)
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": 1,
            "widget": "d1",
            "action": "edit",
            "detail": {"text": "Cut the flag; backfill first."},
        },
    )
    return lambda words, attrs="": (page_dir / "versions" / "v2.html").write_text(
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


def _tasks_version(page_dir, version, status, extra=""):
    (page_dir / "versions" / f"v{version}.html").write_text(
        PAGE.replace("<h2>Plan</h2>", "<h2>Plan</h2>" + _tasks(status, extra))
    )


def _report(page_dir, *args):
    return CliRunner().invoke(interact.cli, ["report", str(page_dir), *args])


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
OPTIONS = """<lf-options id="g1" choose>
  <lf-option id="o-shim"{a}>{chip}<strong>Shim it</strong> {shim}</lf-option>
  <lf-option id="o-stage"{b}><strong>Migrate in stages</strong> {stage}</lf-option>
</lf-options>"""


def state_json(d):
    result = CliRunner().invoke(interact.cli, ["page", "state", str(d)])
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
    "version": 1,
    "widget": "sug-a",
    "action": "accept",
    "detail": {"resolves": "c1"},
}
REJECT = {**ACCEPT, "action": "reject", "detail": {}}
RESOLVE = {"kind": "resolve", "author": "user", "parent": "c1"}


def logged(page_dir, *events):
    """Append these events, then read the threads back the way the CLI does — off
    the whole log and the page the decisions were folded over. Copied in, because
    `append_event` stamps an id onto what it is handed and these are constants."""
    for event in events:
        interact.append_event(page_dir, dict(event))
    return interact.build_threads(
        interact.read_events(page_dir),
        interact.spoken(
            (page_dir / "versions" / "v1.html").read_text(encoding="utf-8"),
            interact.require_registry(page_dir),
        ),
    )


def assert_revendor_serializes_writer(page_dir, monkeypatch, kind, write):
    """Hold one admitted writer at append and prove re-vendor cannot pass it."""
    entering = threading.Event()
    resume = threading.Event()
    checked_without_writer = threading.Event()
    finish_vendoring = threading.Event()
    original_append_event = interact.append_event
    original_composed_theme = layer_model.composed_theme

    def held_append_event(directory, event):
        if event.get("kind") == kind:
            entering.set()
            assert resume.wait(timeout=10), "re-vendor never observed the writer"
        return original_append_event(directory, event)

    def held_composed_theme(sources):
        checked_without_writer.set()
        assert finish_vendoring.wait(timeout=10), "the writer never resumed"
        return original_composed_theme(sources)

    def init_result():
        try:
            interact.cmd_init(page_dir)
        except SystemExit as error:
            return str(error)
        return None

    monkeypatch.setattr(interact, "append_event", held_append_event)
    monkeypatch.setattr(http_model, "append_event", held_append_event)
    monkeypatch.setattr(layer_model, "composed_theme", held_composed_theme)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writing = executor.submit(write)
        assert entering.wait(timeout=10), f"{kind} never passed old-layer validation"
        vendoring = executor.submit(init_result)
        passed_check = checked_without_writer.wait(timeout=2)
        # Release either acquisition order without relying on a scheduler: a
        # broken re-vendor may already own the page lease at composed_theme.
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


def _state_with_optional_value_record(registry):
    task = registry["lf-task"]
    task["properties"]["restated"] = {"type": "boolean"}
    task["x-state"] = {
        "assign": {
            "detail": {
                "type": "object",
                "properties": {"owner": task["properties"]["owner"]},
                "required": ["owner"],
                "additionalProperties": False,
            },
            "facet": "owner",
            "unit": "widget",
            "record": {"kind": "value", "attr": "owner", "value": "owner"},
        }
    }


def _body_record_with_prose(registry):
    registry["lf-draft"]["x-content"] = "prose"


def _body_record_with_nested_widget(registry):
    registry["lf-option"]["x-parent"].append("lf-draft")


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
    created = runner.invoke(interact.cli, ["package", "init", ".leaf"])
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
    entries = json.loads(source.read_text())
    verb = {
        "detail": {"type": "object", "additionalProperties": False},
        "facet": "settlement",
        "unit": "widget",
    }
    for tag, state, example in (
        ("lf-trial", ("adopt", "shelve"), TRIAL_CACHE),
        ("lf-pilot", ("run", "shelve"), PILOT_PURGE),
    ):
        entries[tag] |= {
            "x-content": "items",
            "x-state": {name: dict(verb) for name in state},
            "x-example": example,
        }
        entries[tag]["properties"]["restated"] = {"type": "boolean"}
        del entries[tag]["x-verbatim"]  # a module renders the slots
    # Only the trial says what taking it back would mean.
    entries["lf-trial"]["x-withdrawn-as"] = "shelve"
    for tag, holders, outcome in (
        ("lf-current", ["lf-trial"], "adopt"),
        ("lf-proposed", ["lf-trial", "lf-pilot"], "shelve"),
    ):
        entries[tag] |= {"x-parent": holders, "x-retired-when": outcome}
        del entries[tag]["x-example"]  # a slot has no standing of its own
        del entries[tag]["required"]  # nor an id it must carry
    source.write_text(json.dumps(entries))

    page = tmp_path / "page"
    initialized = runner.invoke(interact.cli, ["page", "init", str(page)])
    assert initialized.exit_code == 0, initialized.output
    (page / "versions" / "v1.html").write_text(
        trial_version(TRIAL_CACHE, TRIAL_LOG, PILOT_PURGE)
    )
    assert check(page, version=1).exit_code == 0, check(page, version=1).output
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
    httpd = interact.LeafHTTPServer(
        ("127.0.0.1", 0), interact.handler_for(page_dir, TOKEN)
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def fetch(url, data=None, token=TOKEN, layer=None):
    """A request arriving the way a user's does: the key in the query, and a
    cookie jar to carry it onward. The live root and the runtime's later query-less
    requests are authorized by the cookie that first keyed arrival set. Pass token=None
    for the reader who never had the link."""
    if token:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode({"t": token})
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    try:
        headers = {}
        if data is not None and (
            token or urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("t")
        ):
            if layer is None:
                state_url = (
                    urllib.parse.urlsplit(url)._replace(path="/api/state").geturl()
                )
                with opener.open(state_url) as state:
                    layer = json.loads(state.read())["layer"]
            headers["Leaf-Layer"] = layer
        request = urllib.request.Request(url, data=data, headers=headers)
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
    interact.write_json(directory / "service.json", service)
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
            if interact.running_server(lease.parent):
                interact.cmd_stop(lease.parent)


def neighbour_page(directory, title=None, dead=False, published=True):
    """A page with desired service state and, unless dead, a live lease."""
    (directory / "versions").mkdir(parents=True)
    head = f"<title>{title}</title>" if title else ""
    (directory / "versions" / "v1.html").write_text(
        f"<!doctype html><html><head>{head}</head>"
        "<body><main><p>words</p></main></body></html>"
    )
    if published:
        interact.append_event(
            directory, {"kind": "note", "author": "claude", "version": 1, "text": "t"}
        )
    record = {"port": 59999}
    if dead:
        interact.write_json(
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
    return interact.page_url("127.0.0.1", 59999, interact.host_key())


@pytest.fixture
def wildcard_server(page_dir):
    """The stated-host bind: a real server on "::", the network-facing socket."""
    httpd = interact.DualStackHTTPServer(
        ("::", 0), interact.handler_for(page_dir, TOKEN)
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _status(page_dir, *args):
    return CliRunner().invoke(interact.cli, ["status", str(page_dir), *args])


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
                if interact.running_server(page_dir):
                    interact.append_event(
                        page_dir, {"kind": "comment", "author": "user", "text": "hi"}
                    )
                    return
                if time.monotonic() > deadline:
                    interact.cmd_status(page_dir, "idle", "no server came up")
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
    interact.claim_page(page_dir)
    return page_dir


@pytest.fixture(scope="session")
def codex_program(tmp_path_factory):
    """A program named `codex` to run a session under, which is the whole of what
    `session_lifetime` looks for above a leaf: a copy of this interpreter wearing that
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
    a pipeline leaves there, and what the launcher's `$PPID` used to record.

    `; exit` is what puts that shell there: a lone command is exec'd in place by
    the shell wrapping it, which is why some command shapes recorded the right
    pid by accident. It also keeps the command's own status, where the `| cat`
    that produced the shape in the wild would report the pipeline's last exit.
    PYTHONHOME because a copied interpreter has no prefix beside it to find its
    own standard library in."""
    runner = (
        "import subprocess, sys; "
        "sys.exit(subprocess.run(['/bin/sh', '-c', sys.argv[1]]).returncode)"
    )

    def start(command, env, **kwargs) -> subprocess.Popen:
        return spawn(
            [str(codex_program), "-c", runner, f"{command}; exit"],
            env={**env, "PYTHONHOME": sys.base_prefix},
            **kwargs,
        )

    return start


@pytest.fixture
def codex_claimed_page(tmp_path, under_codex, codex_env):
    page = tmp_path / "codex-page"
    launcher = PLUGIN_ROOT / "bin" / "leaf"
    env = codex_env | {"CODEX_THREAD_ID": "codex-thread"}

    # Uncaptured, so `check=True` reports something: a CalledProcessError over
    # captured streams names the command and the exit status and takes leaf's
    # own message down with it, and nothing here reads either stream. Left to
    # pytest, the message is in the failure it belongs to.
    subprocess.run([launcher, "page", "init", page], env=env, check=True)
    # Under the fake codex so the service child's claim walk finds it. The chain
    # from that claim up to the codex program is therefore intact.
    # Captured because the URL is read back; the status is asserted here with
    # both streams in the message, rather than left to a CalledProcessError
    # that would take leaf's own account down with it.
    started = under_codex(
        shlex.join([str(launcher), "server", "start", str(page)]),
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
    claim = interact.page_claim(page)
    interact.write_json(interact.claim_path(page), {**claim, "pid": os.getpid()})
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
                sys.executable,
                str(interact.__file__),
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
        assert "session server" in process.stderr.readline()
        return process

    return start


def start_through_the_launcher(page_dir, *flags, session_id="starter"):
    """`server start` the way an agent runs it: from a host session, as a command
    that returns."""
    return subprocess.run(
        [
            sys.executable,
            str(interact.__file__),
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
                sys.executable,
                str(interact.__file__),
                "server",
                "run",
                str(page_dir),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdout.readline().startswith("http://127.0.0.1:")
        assert "standing server" in process.stderr.readline()
        return process

    return start


# ---------- comment: the anchor written without a browser ----------


def published(page_dir):
    assert (
        CliRunner()
        .invoke(
            interact.cli,
            ["version", "publish", str(page_dir), "--version", "1", "--text", "first"],
        )
        .exit_code
        == 0
    )
    return page_dir


def comment(page_dir, *args):
    return CliRunner().invoke(interact.cli, ["comment", str(page_dir), *args])


DRAFTED = PAGE.replace(
    "<h2>Plan</h2>",
    '<h2>Plan</h2>\n  <lf-draft id="note"><pre>\nAdds --dry-run to every mutating command.\n  </pre></lf-draft>',
)


def drafted(page_dir):
    """A published v1 carrying the note draft, its body still Claude's."""
    (page_dir / "versions" / "v1.html").write_text(DRAFTED)
    return published(page_dir)


def edit(page_dir, text, widget="note", version=1):
    interact.append_event(
        page_dir,
        {
            "kind": "action",
            "author": "user",
            "version": version,
            "widget": widget,
            "action": "edit",
            "detail": {"text": text},
        },
    )


SUGGESTED = PAGE.replace("<lf-options>", SUGGESTION)


def suggested(page_dir):
    """A published v1 carrying the sug-refill suggestion, both slots pending."""
    (page_dir / "versions" / "v1.html").write_text(SUGGESTED)
    return published(page_dir)


def add_test_widget(package: Path, tag: str, upgrade: bool = False) -> dict:
    """Author one widget in an initialized package fixture."""
    registry_path = package / "registry.json"
    registry = json.loads(registry_path.read_text())
    entry = widget_entry(tag, upgrade)
    registry[tag] = entry
    registry_path.write_text(json.dumps(registry))
    with (package / "theme.css").open("a") as theme:
        theme.write(f"\n{tag} {{ display: block; }}\n")
    if upgrade:
        (package / "widgets" / f"{tag}.js").write_text(
            f'customElements.define("{tag}", class extends HTMLElement {{}});\n'
        )
    return entry


def link_command_hub_package(root: Path) -> str:
    """Expose the repository package at its recorded project-relative path."""
    relative = Path("examples/packages/command-hub")
    package = root / relative
    package.parent.mkdir(parents=True, exist_ok=True)
    if not package.exists():
        package.symlink_to(COMMAND_HUB_PACKAGE, target_is_directory=True)
    return str(relative)


def widget_entry(tag: str, upgrade: bool = False) -> dict:
    """A minimal package widget declaration for composition fixtures."""
    entry = {
        "description": f"A <{tag}> test block.",
        "type": "object",
        "properties": {"id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"}},
        "required": ["id"],
        "additionalProperties": False,
        "x-content": "prose",
        "x-upgrade": upgrade,
        "x-example": f'<{tag} id="example">Example</{tag}>',
    }
    if upgrade:
        entry["x-verbatim"] = True
    return entry
