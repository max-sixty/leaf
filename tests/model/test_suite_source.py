"""The rules the suite's own source keeps, which no fixture can see.

How a test spells a deadline, which signal it sends and where it gets a process or a
browser are read from each module's syntax. Each case reads one module under `tests/`,
so the rules fit the tier every pull request runs, and a change that breaks one is
refused before it lands rather than by the next nightly run. The suite's deadline
reaches Leaf's other code that drives a browser through the openers in
`leaf.source.render_checks`, so where that code opens its contexts and pages, and the
defaults it sets on them, are read here too, from `src/` and `dev/leaf_dev/`.
"""

import ast
import re

import pytest
from interact_support import ROOT

SOURCES = sorted((ROOT / "tests").rglob("*.py"))
by_module = pytest.mark.parametrize(
    "path", SOURCES, ids=lambda path: path.relative_to(ROOT / "tests").as_posix()
)


def _read(path):
    """The module's syntax, and its path as a finding names it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return tree, path.relative_to(ROOT / "tests").as_posix()


def _literal(node) -> bool:
    """Whether `node` is a deadline spelled as a number: a nonzero one, or sums and
    products of them. A zero timeout asks without waiting."""
    if isinstance(node, ast.BinOp):
        return _literal(node.left) and _literal(node.right)
    return (
        isinstance(node, ast.Constant)
        and type(node.value) in (int, float)
        and node.value != 0
    )


@by_module
def test_the_resources_a_fixture_owns_are_taken_from_that_fixture(path):
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
    tree, named = _read(path)
    bypassed = []
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
    assert not bypassed, "\n".join(bypassed)


@by_module
def test_a_wait_takes_the_suites_deadline(path):
    """A wait in the suite bounds a hang; it does not time the work it waits for.

    A literal deadline is sized to how long the work took where it was written, and
    a busy runner takes many times that, so a correct product fails the test there
    (tests/AGENTS.md, "Results do not depend on execution speed").
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
    (`wait_for_timeout`) bounds nothing, so this leaves it alone, and a test waits for
    an absence on an ordered event instead (tests/AGENTS.md, "Absences").
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

    def called(func) -> str | None:
        return (
            func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        )

    def defaults(arguments):
        positional = arguments.posonlyargs + arguments.args
        yield from zip(
            positional[len(positional) - len(arguments.defaults) :],
            arguments.defaults,
            strict=True,
        )
        yield from zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)

    tree, named = _read(path)
    fixed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            computed = (
                isinstance(node.left, ast.Call)
                and called(node.left.func) == "monotonic"
                and _literal(node.right)
            )
        elif isinstance(node, ast.Call):
            computed = any(
                keyword.arg in deadline_names and _literal(keyword.value)
                for keyword in node.keywords
            ) or (
                called(node.func) in deadline_first
                and isinstance(node.func, ast.Attribute)
                and bool(node.args)
                and _literal(node.args[0])
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            computed = any(
                argument.arg in deadline_names
                and default is not None
                and _literal(default)
                for argument, default in defaults(node.args)
            )
        else:
            continue
        if computed:
            fixed.append(
                f"{named}:{node.lineno} "
                + ast.unparse(node).split("\n", 1)[0]
                + " — STATED_TIMEOUT (interact_support.py), or in a browser"
                " SERVED_TIMEOUT_MS or HANDOVER_DEADLINE_MS (leaf.source.render_checks),"
                " bounds it"
            )
    assert not fixed, "\n".join(fixed)


def test_the_pages_leaf_opens_take_the_served_deadline():
    """Every context and page Leaf's code opens outside the suite, a developer tool's
    included, comes from `open_render_context` or `open_render_page`, which give each
    Playwright wait, request and `expect` that names no deadline `SERVED_TIMEOUT_MS`.
    A page opened any other way keeps Playwright's own 30s, and a probe or still that
    is right fails on a host busy with other sessions' suites (tests/AGENTS.md,
    "Results do not depend on execution speed"). A default set on the page or context
    afterwards wins over the opener's, so it names a constant, as a wait in the suite
    does where its length is its subject. The suite's own pages come from its
    fixtures, which `test_a_wait_takes_the_suites_deadline` reads."""
    openers = {"open_render_context", "open_render_page"}
    opens = {"new_context", "new_page"}
    defaults = {"set_default_timeout", "set_default_navigation_timeout"}
    found = []
    for path in sorted((ROOT / "src").rglob("*.py")) + sorted(
        (ROOT / "dev" / "leaf_dev").rglob("*.py")
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owned = {
            node
            for function in ast.walk(tree)
            if isinstance(function, ast.FunctionDef) and function.name in openers
            for node in ast.walk(function)
        }
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or node in owned
            ):
                continue
            where = f"{path.relative_to(ROOT)}:{node.lineno} {ast.unparse(node)}"
            if node.func.attr in opens:
                found.append(
                    f"{where} — an opener in leaf.source.render_checks opens it"
                )
            elif node.func.attr in defaults and node.args and _literal(node.args[0]):
                found.append(f"{where} — SERVED_TIMEOUT_MS or a named constant")
    assert not found, "\n".join(sorted(found))


@by_module
def test_no_assertion_rests_on_a_sleep(path):
    """A sleep says nothing about the work it waits out, so no assertion reads what a
    sleep left (tests/AGENTS.md, "Absences").

    On a slower machine the effect lands after the sleep: a check that it is absent
    passes with the bug present, and a check that it is there fails on a correct
    product. So a sleep (`time.sleep`, `wait_for_timeout`) is never followed, past
    assignments, by an `assert`, an `expect`, or a returned value in the same block. The
    test waits for the operation's own completion, or for a later event ordered after
    it, or runs the page's clock past the timer instead. A sleep that paces a poll, or
    spaces two gestures the browser tells apart by time, is followed by something else,
    and this leaves it alone. The check reads that one shape; a reviewer reads a sleep
    whose assertion comes later."""

    def sleeps(statement) -> bool:
        return (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, (ast.Attribute, ast.Name))
            and getattr(
                statement.value.func, "attr", getattr(statement.value.func, "id", None)
            )
            in {"sleep", "wait_for_timeout"}
        )

    def asserts(statement) -> bool:
        return (
            isinstance(statement, ast.Assert)
            or (isinstance(statement, ast.Return) and statement.value is not None)
            or (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and statement.value.func.attr.startswith(("to_", "not_to_"))
            )
        )

    tree, named = _read(path)
    rested = []
    for node in ast.walk(tree):
        for block in (
            getattr(node, field, None) for field in ("body", "orelse", "finalbody")
        ):
            if not isinstance(block, list):
                continue
            for index, statement in enumerate(block):
                if not sleeps(statement):
                    continue
                after = next(
                    (
                        s
                        for s in block[index + 1 :]
                        if not isinstance(s, (ast.Assign, ast.AnnAssign))
                    ),
                    None,
                )
                if after is not None and asserts(after):
                    rested.append(
                        f"{named}:{statement.lineno} {ast.unparse(statement)}, then "
                        + ast.unparse(after).split("\n", 1)[0][:80]
                    )
    assert not rested, "\n".join(rested)


@by_module
def test_no_test_ends_a_process_with_sigkill(path):
    """SIGKILL gives a process no chance to end what it started, so a test ends one
    by closing the pipe it reads or with SIGTERM (tests/AGENTS.md, "Processes and servers"). The source is read for it, since no fixture
    sees which signal a test sends: `Popen.kill()`, `signal.SIGKILL`, signal 9
    passed to `kill`, `killpg` or `send_signal`, and a shell `kill` given signal 9
    or KILL in a command a test runs."""
    shell_kill = re.compile(r"\bkill\s+-(?:9|KILL|SIGKILL)\b")
    tree, named = _read(path)
    killed = []
    for node in ast.walk(tree):
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
            killed.append(f"{named}:{node.lineno} " + ast.unparse(node)[:80])
    assert not killed, "\n".join(killed)
