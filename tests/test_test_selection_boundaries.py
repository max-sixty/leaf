"""Selection keeps runnable runtime identities and broadens on unreadable HTTP."""

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from interact_support import running_http_server
from leaf_dev.test_select.command import select
from leaf_dev.test_select.inputs import collect, prepare, python_runtime
from leaf_dev.test_select.model import Client


@pytest.fixture
def runtime_case(tmp_path, monkeypatch):
    """Use the actual uv project runner and the isolated canonical collector."""
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("UV_PYTHON", raising=False)
    root = tmp_path / "repository"
    root.mkdir()
    (root / ".gitignore").write_text(".venv/\n__pycache__/\n.pytest_cache/\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname="selection-boundary"\nversion="0"\nrequires-python=">=3.12"\n'
        '[dependency-groups]\ndev=["pytest>=9.1", "pytest-xdist>=3"]\n'
        "[tool.uv]\npackage=false\n"
    )
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_version.py").write_text(
        "import sys\nimport pytest\n\n"
        '@pytest.mark.parametrize("minor", [sys.version_info.minor])\n'
        "def test_version(minor):\n    assert minor == sys.version_info.minor\n"
    )
    env = {
        **os.environ,
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

    subprocess.run(
        ["uv", "sync", "--python", sys.executable],
        cwd=root,
        check=True,
        capture_output=True,
    )
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (root / "app.py").write_text("VALUE = 2\n")
    git("add", ".")
    git("commit", "-qm", "candidate")
    candidate = git("rev-parse", "HEAD")
    manifest = collect(root, tmp_path / "collection")
    prepared = prepare(
        root,
        base,
        candidate,
        manifest,
        manifest.with_name("manifest-binding.json"),
        tmp_path / "prepared",
    )
    return root, manifest, prepared


def test_isolated_collection_uses_the_ordinary_uv_runtime(runtime_case):
    root, manifest, _ = runtime_case
    binding = json.loads(manifest.with_name("manifest-binding.json").read_text())
    runtime = python_runtime(root)
    assert binding["runtime"] == runtime
    assert binding["collector"]["runtime"]["interpreter"] == runtime["interpreter"]
    nodeids = [test["nodeid"] for test in json.loads(manifest.read_text())]
    assert nodeids == [f"tests/test_version.py::test_version[{runtime['version'][1]}]"]
    result = subprocess.run(
        ["uv", "run", "--frozen", "pytest", "-n0", "-q", *nodeids],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_selection_rejects_a_changed_actual_uv_runtime(
    runtime_case, tmp_path, monkeypatch
):
    root, manifest, prepared = runtime_case
    # A different project environment is a real runner identity change, even
    # when both environments use the same Python release.
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(tmp_path / "other-runner"))
    assert (
        python_runtime(root)["executable"]
        != json.loads(manifest.with_name("manifest-binding.json").read_text())[
            "runtime"
        ]["executable"]
    )
    with pytest.raises(ValueError, match="Python runtime differs"):
        select(prepared, tmp_path / "selection")


@pytest.mark.parametrize("change", ["different-head", "dirty-checkout"])
def test_preparation_and_selection_reject_the_wrong_runner_checkout(
    runtime_case,
    tmp_path,
    change,
):
    root, manifest, prepared = runtime_case
    inputs = json.loads(prepared.read_text())
    if change == "different-head":
        subprocess.run(
            ["git", "-C", str(root), "checkout", "-q", inputs["base"]],
            check=True,
        )
    else:
        (root / "app.py").write_text("VALUE = 3\n")
    with pytest.raises(ValueError, match="candidate.*checkout|candidate as checkout"):
        prepare(
            root,
            inputs["base"],
            inputs["candidate"],
            manifest,
            manifest.with_name("manifest-binding.json"),
            tmp_path / "reprepared",
        )
    with pytest.raises(ValueError, match="candidate.*checkout|candidate as checkout"):
        select(prepared, tmp_path / "selection")
    assert not (tmp_path / "selection/nodeids.txt").exists()


@pytest.mark.parametrize("status", [200, 400])
def test_truncated_http_selects_full_inventory_and_counts_unknown_usage(
    runtime_case,
    tmp_path,
    monkeypatch,
    status,
):
    _, manifest, prepared = runtime_case

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            body = b'{"answers":'
            self.send_response(status)
            self.send_header("Content-Length", str(len(body) + 50))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        monkeypatch.setattr(
            "leaf_dev.test_select.command.api_key", lambda: "LOCAL-ONLY"
        )
        monkeypatch.setattr(
            "leaf_dev.test_select.command.Client",
            lambda key, output: Client(
                key,
                output,
                endpoint=f"http://127.0.0.1:{server.server_port}/",
            ),
        )
        output = tmp_path / "selection"
        result = select(prepared, output)
    assert "unreadable HTTP" in result["fallback"]
    assert result["selected"] == result["total"] == 1
    assert (output / "nodeids.txt").read_text().splitlines() == [
        test["nodeid"] for test in json.loads(manifest.read_text())
    ]
    assert result["spent"]["http_attempts"] == 1
    assert result["spent"]["http_200_responses"] == int(status == 200)
    assert result["spent"]["http_200_responses_without_usable_token_accounting"] == int(
        status == 200
    )
    assert result["spent"]["input_tokens"] == 0


def test_disconnect_before_http_headers_is_a_network_failure(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.close_connection = True

    with running_http_server(ThreadingHTTPServer(("127.0.0.1", 0), Handler)) as server:
        client = Client(
            "LOCAL-ONLY", tmp_path, endpoint=f"http://127.0.0.1:{server.server_port}/"
        )
        with pytest.raises(ValueError, match="network failure"):
            client.ask({"model": "jev-1.13.0", "state": {}, "questions": {"q": {}}})
    assert client.metrics()["http_attempts"] == 4
    assert client.metrics()["http_200_responses"] == 0


def commit_fixture(root):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "add", "."], cwd=root, env=env, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "collection control"],
        cwd=root,
        env=env,
        check=True,
    )


def test_complete_collection_neutralizes_environment_and_config_selection_filters(
    runtime_case, tmp_path, monkeypatch
):
    root, _, _ = runtime_case
    project = root / "pyproject.toml"
    project.write_text(
        project.read_text()
        + '[tool.pytest.ini_options]\naddopts="-m selected"\nmarkers=["selected"]\n'
    )
    (root / "tests/test_filter.py").write_text(
        "import pytest\n\n@pytest.mark.selected\ndef test_one():\n    pass\n\ndef test_two():\n    pass\n"
    )
    commit_fixture(root)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k one")
    manifest = collect(root, tmp_path / "unfiltered")
    nodeids = {t["nodeid"] for t in json.loads(manifest.read_text())}
    assert "tests/test_filter.py::test_one" in nodeids
    assert "tests/test_filter.py::test_two" in nodeids
    assert len(nodeids) == 3
    binding = json.loads(manifest.with_name("manifest-binding.json").read_text())
    assert binding["collector"]["inventory"] == {
        "complete": True,
        "initial_nodes": 3,
        "final_nodes": 3,
    }


def test_complete_collection_rejects_a_custom_deselection_hook(runtime_case, tmp_path):
    root, _, _ = runtime_case
    (root / "tests/test_extra.py").write_text("def test_extra():\n    pass\n")
    (root / "tests/conftest.py").write_text(
        "def pytest_collection_modifyitems(config, items):\n    items.pop()\n"
    )
    commit_fixture(root)
    with pytest.raises(ValueError, match="pytest collection failed"):
        collect(root, tmp_path / "filtered")
    assert (
        "complete, unfiltered collection"
        in (tmp_path / "filtered/collection.log").read_text()
    )
