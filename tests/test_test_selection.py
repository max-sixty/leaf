"""Source selection retains real collected identities and fails open on model uncertainty."""

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from click.testing import CliRunner
from interact_support import running_http_server
from leaf_dev.test_select.command import select
from leaf_dev.test_select.command import test_select as selector_command
from leaf_dev.test_select.evidence import EvidenceIndex
from leaf_dev.test_select.inputs import digest, prepare, python_runtime, write_json
from leaf_dev.test_select.javascript import javascript_records
from leaf_dev.test_select.model import Client
from leaf_dev.test_select.planning import CRITERIA, plan


@pytest.fixture
def git_case(tmp_path):
    """Collect real candidate tests and optionally prove a base-to-candidate regression."""

    def create(files, changes, *, prove_regression=False):
        root = tmp_path / "repository"
        root.mkdir()
        (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
        for name, source in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }

        def git(*args):
            return subprocess.check_output(
                ["git", "-c", "commit.gpgsign=false", *args],
                cwd=root,
                env=env,
                text=True,
            ).strip()

        def pytest_run(*args):
            return subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-q", *args],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        git("init", "-q")
        git("add", ".")
        git("commit", "-qm", "base")
        base = git("rev-parse", "HEAD")
        if prove_regression:
            result = pytest_run()
            assert result.returncode == 0, result.stdout + result.stderr
        for name, source in changes.items():
            target = root / name
            if source is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
        git("add", "-A")
        git("commit", "-qm", "candidate")
        candidate = git("rev-parse", "HEAD")
        if prove_regression:
            result = pytest_run()
            assert result.returncode == 1, result.stdout + result.stderr
        manifest = tmp_path / "manifest.json"
        result = pytest_run(
            "--collect-only",
            "-p",
            "leaf_dev.test_select.collect",
            "--jev-evidence-manifest",
            str(manifest),
        )
        assert result.returncode == 0, result.stdout + result.stderr
        tests = json.loads(manifest.read_text())
        sources = set(git("ls-files", "--", "tests").splitlines())
        sources.update(d["path"] for test in tests for d in test["fixturedefs"])
        binding = manifest.with_name("manifest-binding.json")
        write_json(
            binding,
            {
                "candidate_sha": candidate,
                "manifest_sha256": digest(manifest.read_bytes()),
                "tracked_tree_clean": True,
                "runtime": python_runtime(root),
                "tracked_test_source_sha256": {
                    name: digest((root / name).read_bytes())
                    for name in sources
                    if name.endswith(".py")
                },
                "collector": {
                    "exit_code": 0,
                    "collected_nodes": len(tests),
                    "inventory": {
                        "complete": True,
                        "initial_nodes": len(tests),
                        "final_nodes": len(tests),
                    },
                },
            },
        )
        prepared = prepare(
            root, base, candidate, manifest, binding, tmp_path / "prepared"
        )
        return prepared, manifest, candidate

    return create


@pytest.fixture
def selection_case(git_case):
    app = 'import click\n\n@click.group()\ndef cli():\n    pass\n\n@cli.group("page")\ndef page():\n    pass\n\n@page.command("state")\ndef state():\n    click.echo("before")\n'
    tests = 'import pytest\nfrom click.testing import CliRunner\nfrom app import cli\n\n@pytest.fixture\ndef marker():\n    return "value"\n\n@pytest.mark.parametrize("address", ["a::b"])\ndef test_state(address, marker):\n    assert CliRunner().invoke(cli, ["page", "state"]).exit_code == 0\n\n@pytest.mark.parametrize("number", [1, 2])\ndef test_independent(number):\n    assert number > 0\n'
    return git_case(
        {"app.py": app, "tests/test_app.py": tests},
        {"app.py": app.replace('"before"', '"after"')},
    )


def test_prepare_cli_exposes_a_complete_query_without_reading_credentials(
    selection_case, tmp_path, monkeypatch
):
    prepared, manifest, candidate = selection_case
    inputs = json.loads(prepared.read_text())
    output = tmp_path / "offline-preview"

    def unexpected_key_read():
        pytest.fail("Offline preparation must not read credentials")

    monkeypatch.setattr("leaf_dev.test_select.command.api_key", unexpected_key_read)
    result = CliRunner().invoke(
        selector_command,
        [
            "prepare",
            inputs["root"],
            inputs["base"],
            candidate,
            str(manifest),
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    preview = json.loads((output / "planned-single-query.json").read_text())
    first = plan(json.loads((output / "prepared.json").read_text()))[0]
    assert preview == {
        **first,
        "questions": dict(list(first["questions"].items())[:1]),
    }
    question = next(iter(preview["questions"].values()))
    assert (
        "def test_independent"
        in question["instructions"]["evidence"]["test_body"]["code"]
    )
    assert (
        json.loads((output / "plan-summary.json").read_text())["api_requests_sent"] == 0
    )


def test_source_preparation_retains_parameterized_click_dispatch_and_rejects_stale_collection(
    selection_case, tmp_path, monkeypatch
):
    prepared, manifest, _ = selection_case
    inputs = json.loads(prepared.read_text())
    assert len(inputs["cards"]) == 3
    state = next(c for c in inputs["cards"] if c["nodeid"].endswith("test_state[a::b]"))
    assert state["params"] == {"address": "a::b"}
    assert "marker" in state["fixturenames"]
    assert state["nodeid"] in inputs["mandatory_test_ids"]
    assert state["graph_path"][-1] == ["app.py", "state"]
    assert '"after"' in "".join(
        c["state"]["changes"][0]["patch"] for c in inputs["states"]["state_chunks"]
    )
    # Missing credentials and any API uncertainty must broaden the runnable list.
    monkeypatch.setattr(
        "leaf_dev.test_select.command.api_key",
        lambda: (_ for _ in ()).throw(ValueError("missing key")),
    )
    result = select(prepared, tmp_path / "selection")
    assert result["selected"] == 3
    assert result["fallback"] == "missing key"
    assert result["model_scored"] == 0
    manifest.write_text("[]\n")
    with pytest.raises(ValueError, match="not bound"):
        select(prepared, tmp_path / "stale")


@pytest.mark.parametrize(
    "criterion_names", [("relevant", "unrelated", "unknown"), ("relevant", "unrelated")]
)
def test_jev_cache_tracks_whole_payload_and_never_captures_credentials(
    tmp_path, criterion_names
):
    bodies = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            bodies.append(request)
            response = {
                "answers": {
                    name: {
                        "probabilities": {
                            criterion: 1 / len(question["criteria"])
                            for criterion in question["criteria"]
                        }
                    }
                    for name, question in request["questions"].items()
                },
                "usage": {"input_tokens": 10},
                "model": "jev-1.13.0",
            }
            if request["state"]["diff"] == "wrong-criteria":
                response["answers"]["q"]["probabilities"] = {"undeclared": 1}
            elif request["state"]["diff"] == "not-normalized":
                response["answers"]["q"]["probabilities"] = {
                    criterion: 0 for criterion in request["questions"]["q"]["criteria"]
                }
            encoded = json.dumps(response).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(encoded)

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        client = Client(
            "SECRET-KEY",
            tmp_path,
            endpoint=f"http://127.0.0.1:{server.server_port}/v1/systemone",
        )
        request = {
            "model": "jev-1.13.0",
            "state": {"diff": "A"},
            "questions": {
                "q": {
                    "type": "choice",
                    "criteria": {name: name for name in criterion_names},
                }
            },
        }
        answer = client.ask(request).answers["q"]["probabilities"]
        assert set(answer) == set(criterion_names)
        assert sum(answer.values()) == pytest.approx(1)
        client.ask({**request, "state": {"diff": "B"}})
        client.ask(request)
        with pytest.raises(ValueError, match="different selection criteria"):
            client.ask({**request, "state": {"diff": "wrong-criteria"}})
        with pytest.raises(ValueError, match="not normalized"):
            client.ask({**request, "state": {"diff": "not-normalized"}})
        assert len(bodies) == 4
        assert client.metrics()["cached_requests"] == 1
        captured = (tmp_path / "requests.jsonl").read_text()
        assert "SECRET-KEY" not in captured
        assert "Authorization" not in captured
        assert [
            json.loads(line)["state"]["diff"] for line in captured.splitlines()
        ] == ["A", "B", "wrong-criteria", "not-normalized"]


@pytest.mark.parametrize("binding", ["internal", "external"])
def test_changed_import_binding_reaches_its_reader_without_forcing_unrelated_functions(
    git_case, binding
):
    before_import, after_import = {
        "internal": ("from app.first import value", "from app.second import value"),
        "external": (
            "from math import floor as value",
            "from math import ceil as value",
        ),
    }[binding]
    reader = f"""{before_import}

def read(): return value(1.5)
def unrelated(value=5): return value
def lambda_shadow(): return (lambda value: value)(5)
def exception_shadow():
    try: raise ValueError(5)
    except ValueError as value: return value.args[0]
def comprehension():
    values = [value for value in range(2)]
    return value(1.5)
"""
    prepared, _, _ = git_case(
        {
            "app/__init__.py": "",
            "app/first.py": "def value(number):\n    return 1\n",
            "app/second.py": "def value(number):\n    return 2\n",
            "app/reader.py": reader,
            "tests/test_read.py": """from app.reader import read, unrelated, lambda_shadow, exception_shadow, comprehension

def test_read(): assert read() == 1
def test_unrelated(): assert unrelated() == 5
def test_lambda(): assert lambda_shadow() == 5
def test_exception(): assert exception_shadow() == 5
def test_comprehension(): assert comprehension() == 1
""",
        },
        {"app/reader.py": reader.replace(before_import, after_import)},
        prove_regression=True,
    )
    inputs = json.loads(prepared.read_text())
    assert set(inputs["mandatory_test_ids"]) == {
        "tests/test_read.py::test_read",
        "tests/test_read.py::test_comprehension",
    }


@pytest.mark.parametrize(
    "change", ["add", "format", "remove-unused", "rebind", "remove-used"]
)
def test_multiline_import_edits_retain_only_readers_of_changed_bindings(
    git_case, change
):
    before_import = (
        "from app.providers import (\n    stable,\n    value,\n    extra,\n)"
    )
    after_import = {
        "add": before_import.replace("    extra,", "    extra,\n    other,"),
        "format": "from app.providers import stable, value, extra",
        "remove-unused": before_import.replace("    extra,\n", ""),
        "rebind": before_import.replace("    value,", "    other as value,"),
        "remove-used": before_import.replace("    value,\n", ""),
    }[change]
    reader = f"""{before_import}

class Contract:
    field: stable

def read(): return value()
def independent(): return stable()
"""
    prepared, _, _ = git_case(
        {
            "app/__init__.py": "",
            "app/providers.py": """def stable(): return 5
def value(): return 1
def other(): return 2
extra = 0
""",
            "app/reader.py": reader,
            "tests/test_read.py": """from app.reader import Contract, read, independent
from app.providers import stable

def test_read(): assert read() == 1
def test_independent(): assert independent() == 5
def test_annotation(): assert Contract.__annotations__["field"] is stable
""",
        },
        {"app/reader.py": reader.replace(before_import, after_import)},
        prove_regression=change in {"rebind", "remove-used"},
    )
    inputs = json.loads(prepared.read_text())
    assert set(inputs["mandatory_test_ids"]) == (
        {"tests/test_read.py::test_read"}
        if change in {"rebind", "remove-used"}
        else set()
    )


def test_collected_dataclass_parameter_retains_the_actual_resource_dependency(git_case):
    prepared, _, _ = git_case(
        {
            "example.html": "before",
            "tests/test_page.py": """from dataclasses import dataclass
from pathlib import Path
import pytest

@dataclass(frozen=True)
class Page:
    source: Path
    packages: tuple[str, ...]

@pytest.mark.parametrize("page", [Page(Path("example.html"), ("diagram",))])
def test_page(page):
    assert page.source.read_text() == "before"
""",
        },
        {"example.html": "after"},
        prove_regression=True,
    )
    inputs = json.loads(prepared.read_text())
    card = inputs["cards"][0]
    assert card["params"]["page"] == {
        "type": "Page",
        "fields": {"source": {"path": "example.html"}, "packages": ["diagram"]},
    }
    assert inputs["mandatory_test_ids"] == [card["nodeid"]]
    assert any(w["path"] == "example.html" for w in card["change_witnesses"])


def test_model_question_contains_the_used_browser_constant_without_shared_fixture_code(
    git_case,
):
    probe = "() => getComputedStyle(document.body).getPropertyValue('--room')"
    prepared, _, _ = git_case(
        {
            "app.js": "export const value = 1;\n",
            "tests/cases.py": f"PROBE = {probe!r}\nUNUSED = 'unused context'\n",
            "tests/test_page.py": """import pytest
from cases import PROBE

@pytest.fixture
def shared_setup():
    return "shared fixture boilerplate"

def test_probe(shared_setup):
    assert "document.body" in PROBE
""",
        },
        {"app.js": "export const value = 2;\n"},
    )
    inputs = json.loads(prepared.read_text())
    requests = plan(inputs)
    assert len(requests) == 1
    query = next(iter(requests[0]["questions"].values()))
    definitions = query["instructions"]["evidence"]["direct_test_context"][
        "definitions"
    ]
    assert [(d["path"], d["symbol"]) for d in definitions] == [
        ("tests/cases.py", "PROBE")
    ]
    assert probe in definitions[0]["code"]
    assert "shared fixture boilerplate" not in json.dumps(query)
    assert "unused context" not in json.dumps(query)


def test_existing_javascript_parser_preserves_unicode_source_ranges_and_named_bindings():
    source = """import { measure as reading } from "./probe.js";
// 日本語 before a multi-line definition.
export function observer() {
  const text = "日本語";
  return reading(text);
}
"""
    # Repeated reads also exercise native parser/node lifetime, rather than
    # proving only a trivial one-line declaration.
    for _ in range(5):
        record = javascript_records(source, "observer.js")
        definition = record["definitions"]["observer"]
        assert definition["start"] == 3
        assert definition["end"] == 6
        assert definition["code"] == "\n".join(source.splitlines()[2:])
        assert "reading" in definition["refs"]
        assert record["imports"] == [
            {
                "source": "./probe.js",
                "names": [{"local": "reading", "remote": "measure"}],
            }
        ]


@pytest.mark.parametrize(
    "files,changes,nodeid",
    [
        (
            {
                "app/__init__.py": "",
                "app/values.py": "def value():\n    return 1\n",
                "app/reader.py": "from . import values\n\ndef read():\n    return values.value()\n",
                "tests/test_read.py": "from app.reader import read\n\ndef test_read():\n    assert read() == 1\n",
            },
            {"app/values.py": "def value():\n    return 2\n"},
            "tests/test_read.py::test_read",
        ),
        (
            {
                "app/__init__.py": "",
                "app/values.py": "def value():\n    return 1\n",
                "app/reader.py": "def read():\n    from . import values\n    return values.value()\n",
                "tests/test_read.py": "from app.reader import read\n\ndef test_read():\n    assert read() == 1\n",
            },
            {"app/values.py": "def value():\n    return 2\n"},
            "tests/test_read.py::test_read",
        ),
        (
            {
                "resource.json": "{}\n",
                "tests/test_resource.py": 'from pathlib import Path\n\ndef test_resource():\n    assert Path("resource.json").read_text() == "{}\\n"\n',
            },
            {"resource.json": None},
            "tests/test_resource.py::test_resource",
        ),
        (
            {
                "tests/test_calls.py": "def test_setup():\n    return 1\n\ndef test_uses_setup():\n    assert test_setup() == 1\n",
            },
            {
                "tests/test_calls.py": "def test_uses_setup():\n    assert test_setup() == 1\n",
            },
            "tests/test_calls.py::test_uses_setup",
        ),
    ],
    ids=[
        "relative-import",
        "local-relative-import",
        "deleted-resource",
        "deleted-test-helper",
    ],
)
def test_source_relationships_retain_tests_that_really_change_outcome(
    git_case, files, changes, nodeid
):
    prepared, _, _ = git_case(files, changes, prove_regression=True)
    inputs = json.loads(prepared.read_text())
    assert nodeid in inputs["mandatory_test_ids"]


def test_unreferenced_deleted_test_remains_in_the_complete_model_diff(git_case):
    source = "def test_unused():\n    assert True\n\ndef test_remaining():\n    assert True\n"
    prepared, _, _ = git_case(
        {"tests/test_calls.py": source},
        {
            "tests/test_calls.py": source.replace(
                "def test_unused():\n    assert True\n\n", ""
            )
        },
    )
    inputs = json.loads(prepared.read_text())
    states = inputs["states"]["state_chunks"]
    assert states, "A test-only deletion is still a code change for selection"
    patches = "".join(
        change["patch"] for chunk in states for change in chunk["state"]["changes"]
    )
    assert "-def test_unused():" in patches
    assert "-    assert True" in patches


@pytest.mark.parametrize(
    "variant", ["null", "answers-list", "probabilities-null", "invalid-json"]
)
def test_malformed_http_responses_select_the_full_inventory(
    selection_case, tmp_path, monkeypatch, variant
):
    prepared, _, _ = selection_case

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            responses = {
                "null": None,
                "answers-list": {
                    "answers": list(request["questions"]),
                    "usage": {"input_tokens": 7},
                },
                "probabilities-null": {
                    "answers": {
                        name: {"probabilities": None} for name in request["questions"]
                    },
                    "usage": {"input_tokens": 7},
                },
            }
            body = (
                b"{"
                if variant == "invalid-json"
                else json.dumps(responses[variant]).encode()
            )
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/systemone"
        monkeypatch.setattr(
            "leaf_dev.test_select.command.api_key", lambda: "LOCAL-ONLY"
        )
        monkeypatch.setattr(
            "leaf_dev.test_select.command.Client",
            lambda key, output: Client(key, output, endpoint=endpoint),
        )
        result = select(prepared, tmp_path / variant)
    assert result["fallback"]
    assert result["selected"] == result["total"] == 3
    assert result["model_scored"] == 0
    assert result["spent"]["http_attempts"] == 1
    assert result["spent"]["http_200_responses"] == 1
    unknown_usage = variant in {"null", "invalid-json"}
    assert result["spent"]["http_200_responses_without_usable_token_accounting"] == int(
        unknown_usage
    )
    assert result["spent"]["input_tokens"] == (0 if unknown_usage else 7)


def test_concurrent_success_usage_is_counted_even_when_one_answer_is_invalid(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            bad = "bad" in request["questions"]
            response = {
                "model": "jev-1.13.0",
                "answers": {}
                if bad
                else {
                    "good": {
                        "probabilities": {
                            "relevant": 0.7,
                            "unrelated": 0.2,
                            "unknown": 0.1,
                        }
                    }
                },
                "usage": {"input_tokens": 13 if bad else 20},
            }
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        client = Client(
            "LOCAL-ONLY",
            tmp_path,
            endpoint=f"http://127.0.0.1:{server.server_port}/v1/systemone",
        )
        requests = [
            {
                "model": "jev-1.13.0",
                "state": {"case": name},
                "questions": {name: {"type": "choice", "criteria": CRITERIA}},
            }
            for name in ("bad", "good")
        ]
        with pytest.raises(ValueError):
            client.run(requests)
    metrics = client.metrics()
    assert metrics["http_attempts"] == 2
    assert metrics["successful_calls"] == 1
    assert metrics["input_tokens"] == 33
    assert metrics["estimated_usd"] == pytest.approx(33 * 0.042 / 1_000_000)


@pytest.mark.parametrize("change_facade", [False, True])
def test_reexport_bindings_retain_origin_and_facade_regressions(
    git_case, change_facade
):
    first = "def value():\n    return 1\n"
    facade = "from app.first import value\n"
    prepared, _, _ = git_case(
        {
            "app/__init__.py": "",
            "app/first.py": first,
            "app/second.py": "def value():\n    return 2\n",
            "app/facade.py": facade,
            "tests/test_facade.py": "from app.facade import value\n\ndef test_value():\n    assert value() == 1\n",
        },
        {"app/facade.py": facade.replace("first", "second")}
        if change_facade
        else {"app/first.py": first.replace("return 1", "return 2")},
        prove_regression=True,
    )
    inputs = json.loads(prepared.read_text())
    assert inputs["mandatory_test_ids"] == ["tests/test_facade.py::test_value"]
    card = inputs["cards"][0]
    assert ["app/facade.py", "value"] in card["graph_path"]
    if not change_facade:
        assert card["graph_path"][-1] == ["app/first.py", "value"]


def test_reexported_browser_constant_and_callable_source_reach_actual_query(git_case):
    prepared, _, _ = git_case(
        {
            "runtime.js": "globalThis.layout = 'before';\n",
            "tests/support.py": "ROOM = \"() => document.querySelector('main').getBoundingClientRect()\"\n\ndef read_room(page):\n    return page.evaluate(ROOM)\n",
            "tests/facade.py": "from support import ROOM, read_room\n",
            "tests/test_room.py": "from facade import ROOM, read_room\n\ndef test_room():\n    assert callable(read_room)\n    assert 'main' in ROOM\n",
        },
        {"runtime.js": "globalThis.layout = 'after';\n"},
    )
    inputs = json.loads(prepared.read_text())
    context = inputs["cards"][0]["test_context"]
    assert {d["symbol"] for d in context["definitions"]} == {"ROOM", "read_room"}
    assert {d["path"] for d in context["definitions"]} == {"tests/support.py"}
    request = next(r for r in plan(inputs) if r["questions"])
    query = json.dumps(request)
    assert "getBoundingClientRect" in query
    assert "return page.evaluate(ROOM)" in query
    assert not context["omissions"]


def test_changed_production_callee_reached_by_active_fixture_is_mandatory(git_case):
    app = "def value():\n    return 1\n\ndef read():\n    return value()\n"
    prepared, _, _ = git_case(
        {
            "app.py": app,
            "tests/conftest.py": "import pytest\nfrom app import read\n\n@pytest.fixture\ndef answer():\n    return read()\n\n@pytest.fixture\ndef independent():\n    return 3\n",
            "tests/test_answer.py": "def test_answer(answer):\n    assert answer == 1\n\ndef test_independent(independent):\n    assert independent == 3\n",
        },
        {"app.py": app.replace("return 1", "return 2")},
        prove_regression=True,
    )
    inputs = json.loads(prepared.read_text())
    assert inputs["mandatory_test_ids"] == ["tests/test_answer.py::test_answer"]
    assert inputs["cards"][0]["graph_path"] == [
        ["tests/conftest.py", "answer"],
        ["app.py", "read"],
        ["app.py", "value"],
    ]


@pytest.mark.parametrize("delegate", [False, True])
def test_collected_fixture_override_uses_only_the_active_dependency_chain(
    git_case, delegate
):
    app = "def value():\n    return 1\n"
    override = (
        "def answer(answer):\n    return answer\n"
        if delegate
        else "def answer():\n    return 1\n"
    )
    prepared, manifest, _ = git_case(
        {
            "app.py": app,
            "conftest.py": "import pytest\nfrom app import value\n\n@pytest.fixture\ndef answer():\n    return value()\n",
            "tests/conftest.py": "import pytest\n\n@pytest.fixture\n" + override,
            "tests/test_answer.py": "def test_answer(answer):\n    assert answer == 1\n",
        },
        {"app.py": app.replace("return 1", "return 2")},
        prove_regression=delegate,
    )
    collected = json.loads(manifest.read_text())
    active = [d["path"] for d in collected[0]["fixturedefs"] if d["name"] == "answer"]
    assert (
        active == ["tests/conftest.py", "conftest.py"]
        if delegate
        else active == ["tests/conftest.py"]
    )
    inputs = json.loads(prepared.read_text())
    assert inputs["mandatory_test_ids"] == (
        ["tests/test_answer.py::test_answer"] if delegate else []
    )


def test_one_unsendable_test_runs_without_forcing_the_independent_inventory(
    git_case, tmp_path, monkeypatch
):
    large = "x" * 120_000
    prepared, _, _ = git_case(
        {
            "app.js": "export const value = 1;\n",
            "tests/test_app.py": f"def test_large():\n    assert len({large!r}) == 120000\n\ndef test_small():\n    assert 2 + 2 == 4\n",
        },
        {"app.js": "export const value = 2;\n"},
    )
    inputs = json.loads(prepared.read_text())
    assert inputs["mandatory_test_ids"] == ["tests/test_app.py::test_large"]
    assert inputs["unclassified_tests"][0]["max_bytes"] > 110_000
    queried = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            queried.extend(
                q["instructions"]["test_name"] for q in request["questions"].values()
            )
            response = {
                "model": "jev-1.13.0",
                "usage": {"input_tokens": 10},
                "answers": {
                    name: {
                        "probabilities": {"relevant": 0, "unrelated": 1, "unknown": 0}
                    }
                    for name in request["questions"]
                },
            }
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/systemone"
        monkeypatch.setattr(
            "leaf_dev.test_select.command.api_key", lambda: "LOCAL-ONLY"
        )
        monkeypatch.setattr(
            "leaf_dev.test_select.command.Client",
            lambda key, output: Client(key, output, endpoint=endpoint),
        )
        result = select(prepared, tmp_path / "selection")
    assert result["fallback"] is None
    assert result["selected"] == 1
    assert queried == ["test_small"]
    assert (tmp_path / "selection/nodeids.txt").read_text() == (
        "tests/test_app.py::test_large\n"
    )


def test_jev_token_refusal_retains_only_its_test_and_preserves_real_answers(
    git_case, tmp_path, monkeypatch
):
    """The service's token budget can reject a question below our byte estimate."""
    prepared, _, _ = git_case(
        {
            "app.js": "export const value = 1;\n",
            "tests/test_app.py": (
                "def test_large():\n    assert 1 == 1\n\n"
                "def test_small():\n    assert 2 + 2 == 4\n"
            ),
        },
        {"app.js": "export const value = 2;\n"},
    )
    assert not json.loads(prepared.read_text())["mandatory_test_ids"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            oversized = any(
                question["instructions"]["test_name"] == "test_large"
                for question in request["questions"].values()
            )
            if oversized:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"max_tokens_exceeded"}')
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "model": "jev-1.13.0",
                        "usage": {"input_tokens": 10},
                        "answers": {
                            name: {
                                "probabilities": {
                                    "relevant": 0,
                                    "unrelated": 1,
                                    "unknown": 0,
                                }
                            }
                            for name in request["questions"]
                        },
                    }
                ).encode()
            )

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        endpoint = f"http://127.0.0.1:{server.server_port}/v1/systemone"
        monkeypatch.setattr(
            "leaf_dev.test_select.command.api_key", lambda: "LOCAL-ONLY"
        )
        monkeypatch.setattr(
            "leaf_dev.test_select.command.Client",
            lambda key, output: Client(key, output, endpoint=endpoint),
        )
        result = select(prepared, tmp_path / "selection")
    assert result["fallback"] is None
    assert result["selected"] == 1
    large, small = result["tests"]
    assert large["selected"] and not large["model_scored"]
    assert large["relevance"] is None and large["raw"] == []
    assert large["context_refusals"][0]["error"] == "max_tokens_exceeded"
    assert not small["selected"] and small["model_scored"]
    assert small["relevance"] == 0 and not small["context_refusals"]
    assert result["spent"]["splits"] == 1
    assert result["spent"]["context_refused_questions"] == 1
    assert result["spent"]["input_tokens"] == 10
    cached = list((tmp_path / "selection/cache").glob("*.json"))
    assert len(cached) == 1
    assert all("max_tokens_exceeded" not in path.read_text() for path in cached)


@pytest.mark.parametrize("edit", ["method", "constructor", "declaration", "addition"])
def test_python_method_ownership_retains_actual_callers_without_forcing_sibling_bodies(
    git_case, edit
):
    app = """class Service:
    marker = 1
    def __init__(self): self.seed = 1
    def changed(self): return 1
    def stable(self): return self.seed
    def via(self): return self.changed()

def build(): return Service()
def uses_changed(): return Service.changed(build())
def uses_stable(): return Service.stable(build())
def uses_via(): return Service.via(build())
"""
    tests = """import pytest
from app import Service, build, uses_changed, uses_stable, uses_via

def test_changed(): assert uses_changed() in (1, 2)
def test_stable(): assert uses_stable() in (1, 2)
def test_via(): assert uses_via() in (1, 2)
def test_build(): assert isinstance(build(), Service)
def test_marker(): assert Service.marker in (1, 2)

class TestChanged:
    @pytest.fixture
    def value(self): return uses_changed()
    def test_value(self, value): assert value in (1, 2)

class TestStable:
    @pytest.fixture
    def value(self): return uses_stable()
    def test_value(self, value): assert value in (1, 2)
"""
    old, new = {
        "method": ("def changed(self): return 1", "def changed(self): return 2"),
        "constructor": ("self.seed = 1", "self.seed = 2"),
        "declaration": ("marker = 1", "marker = 2"),
        "addition": (
            "    def via(self): return self.changed()",
            "    def via(self): return self.changed()\n    def extra(self): return 9",
        ),
    }[edit]
    prepared, manifest, _ = git_case(
        {"app.py": app, "tests/test_app.py": tests}, {"app.py": app.replace(old, new)}
    )
    result = json.loads(prepared.read_text())
    collected = json.loads(manifest.read_text())
    expected = {
        "method": {"test_changed", "test_via", "TestChanged::test_value"},
        "constructor": {
            "test_changed",
            "test_stable",
            "test_via",
            "test_build",
            "TestChanged::test_value",
            "TestStable::test_value",
        },
        "declaration": {
            "test_changed",
            "test_stable",
            "test_via",
            "test_build",
            "test_marker",
            "TestChanged::test_value",
            "TestStable::test_value",
        },
        "addition": set(),
    }[edit]
    assert {n.split("::", 1)[1] for n in result["mandatory_test_ids"]} == expected
    for class_name in ("TestChanged", "TestStable"):
        item = next(t for t in collected if f"::{class_name}::" in t["nodeid"])
        card = next(c for c in result["cards"] if c["nodeid"] == item["nodeid"])
        assert card["body"]["symbol"] == f"{class_name}.test_value"
        assert "def test_value" in card["body"]["code"]
        evidence = EvidenceIndex(result["root"], result["candidate"]).extract(item)
        assert any(f["symbol"] == f"{class_name}.value" for f in evidence["fixtures"])


def test_lexical_source_ownership_retains_active_nested_calls_and_definition_defaults(
    git_case,
):
    app = """def changed(): return 1

def active():
    def inner(): return changed()
    return inner()

def dormant():
    def inner(): return changed()
    return 0

class Headers:
    def value(self, changed=changed()): return changed

def nested_class():
    class Value:
        value = changed()
    return 0
"""
    tests = """from app import active, dormant, Headers, nested_class

def test_active(): assert active() in (1, 2)
def test_dormant(): assert dormant() == 0
def test_header(): assert Headers().value() in (1, 2)
def test_nested_class(): assert nested_class() == 0
"""
    prepared, _, _ = git_case(
        {"app.py": app, "tests/test_app.py": tests},
        {"app.py": app.replace("def changed(): return 1", "def changed(): return 2")},
    )
    result = json.loads(prepared.read_text())
    assert {n.split("::", 1)[1] for n in result["mandatory_test_ids"]} == {
        "test_active",
        "test_header",
        "test_nested_class",
    }


def test_wrapped_fixture_source_identity_and_decorator_body_are_retained(git_case):
    helper = """from functools import wraps

def decorate(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper
"""
    test_source = """import pytest
from helper import decorate

@pytest.fixture
@decorate
def value(): return 10

def test_value(value): assert value == 10
"""
    prepared, manifest, _ = git_case(
        {"helper.py": helper, "tests/test_sample.py": test_source},
        {
            "helper.py": helper.replace(
                "return fn(*args, **kwargs)", "return fn(*args, **kwargs) + 1"
            )
        },
        prove_regression=True,
    )
    result = json.loads(prepared.read_text())
    item = json.loads(manifest.read_text())[0]
    fixture = next(f for f in item["fixturedefs"] if f["name"] == "value")
    assert fixture["path"] == "tests/test_sample.py"
    evidence = EvidenceIndex(result["root"], result["candidate"]).extract(item)
    assert [(f["path"], f["symbol"], f["code"]) for f in evidence["fixtures"]] == [
        (
            "tests/test_sample.py",
            "value",
            "@pytest.fixture\n@decorate\ndef value(): return 10",
        )
    ]
    assert result["mandatory_test_ids"] == [item["nodeid"]]
