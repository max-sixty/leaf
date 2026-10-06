"""Collect and prepare source-bound selector inputs; no CI outcomes are accepted."""

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from leaf_dev.test_select.css import literal_witnesses
from leaf_dev.test_select.direct import ChangePackets
from leaf_dev.test_select.evidence import EvidenceIndex, test_function_name
from leaf_dev.test_select.graph import (
    changed_python,
    graph,
    influence_paths,
    path_to_change,
    preload_python,
)
from leaf_dev.test_select.planning import unresolved
from leaf_dev.test_select.states import build_states
from leaf_dev.test_select.timing import cpu_time

POLICY = {
    "id": "source-context-lexical-owners-v7",
    "cutoff": 0.35,
    "model": "jev-1.13.0",
}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)


def commit(root: Path, ref: str) -> str:
    return git(root, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def require_checkout(root: Path, candidate: str) -> None:
    if commit(root, "HEAD") != candidate:
        raise ValueError("Collection requires the candidate as checkout HEAD")
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=False
    )
    if result.returncode:
        raise ValueError("Selection requires a clean candidate checkout")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", "tests")
    if untracked.strip():
        raise ValueError(
            "Untracked tests would make collection differ from the Git snapshot"
        )


def python_runtime(root: Path, *, env: dict[str, str] | None = None) -> dict:
    """Read the ordinary uv runner's interpreter, including its real binary path."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--all-groups",
            "python",
            "-c",
            (
                "import json, pathlib, sys; print(json.dumps({"
                "'executable': sys.executable, "
                "'interpreter': str(pathlib.Path(sys.executable).resolve()), "
                "'version': list(sys.version_info[:3]), "
                "'implementation': sys.implementation.name}))"
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"Cannot resolve the test runner's Python: {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def collect(root: Path, output: Path) -> Path:
    """Overlay only the canonical collector, preserving historical developer modules."""
    root, output = root.resolve(), output.resolve()
    candidate = commit(root, "HEAD")
    require_checkout(root, candidate)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    runtime = python_runtime(root)
    manifest = output / "manifest.json"
    # Overlaying leaf-dev wholesale changes modules historical tests import.
    # This derived distribution carries only the canonical collector's bytes.
    overlay = output / "collector-overlay"
    package = overlay / "leaf_test_select_collector"
    package.mkdir(parents=True, exist_ok=True)
    plugin_source = Path(__file__).with_name("collect.py").read_bytes()
    (package / "__init__.py").write_bytes(plugin_source)
    (overlay / "pyproject.toml").write_text(
        '[project]\nname = "leaf-test-select-collector"\nversion = "0"\nrequires-python = ">=3.10"\n[build-system]\nrequires = ["uv_build>=0.9"]\nbuild-backend = "uv_build"\n[tool.uv.build-backend]\nmodule-root = ""\n'
    )
    command = [
        "uv",
        "run",
        "--frozen",
        "--all-groups",
        "--python",
        runtime["executable"],
        "--with",
        str(overlay),
        "python",
        "-m",
        "pytest",
        "tests",
        "-o",
        "addopts=",
        "--collect-only",
        "-q",
        "-n0",
        "-p",
        "leaf_test_select_collector",
        "--jev-evidence-manifest",
        str(manifest),
    ]
    # The collection overlay cannot be removed by a historical test's --no-dev
    # child: collection never runs test bodies or fixtures.
    env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(output / "environment"))
    env.pop("PYTEST_ADDOPTS", None)
    with (output / "collection.log").open("w") as log:
        result = subprocess.run(
            command,
            cwd=root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode:
        raise ValueError(
            f"pytest collection failed ({result.returncode}); see {output / 'collection.log'}"
        )
    require_checkout(root, candidate)
    collected_runtime = python_runtime(root, env=env)
    if any(
        collected_runtime[key] != runtime[key]
        for key in ("interpreter", "version", "implementation")
    ):
        raise ValueError(
            "Collection used a different Python than the ordinary test runner"
        )
    tests = json.loads(manifest.read_text())
    sources = set(git(root, "ls-files", "--", "tests").splitlines())
    sources.update(d["path"] for t in tests for d in t["fixturedefs"])
    binding = {
        "schema": "jev-pytest-manifest-binding/v1",
        "candidate_sha": candidate,
        "root_head": candidate,
        "tracked_tree_clean": True,
        "runtime": runtime,
        "manifest_sha256": digest(manifest.read_bytes()),
        "tracked_test_source_sha256": {
            p: digest((root / p).read_bytes())
            for p in sorted(sources)
            if p.endswith(".py")
        },
        "uv_lock_sha256": digest((root / "uv.lock").read_bytes())
        if (root / "uv.lock").exists()
        else None,
        "collector": {
            "inventory": json.loads((output / "collection-summary.json").read_text()),
            "exit_code": 0,
            "collected_nodes": len(tests),
            "invocation": command,
            "wall_seconds": time.perf_counter() - started,
            "canonical_plugin_sha256": digest(
                Path(__file__).with_name("collect.py").read_bytes()
            ),
            "runtime": collected_runtime,
        },
    }
    write_json(output / "manifest-binding.json", binding)
    return manifest


def validate_manifest(
    root: Path, candidate: str, manifest: Path, binding_path: Path
) -> list[dict]:
    require_checkout(root, candidate)
    raw = manifest.read_bytes()
    tests = json.loads(raw)
    binding = json.loads(binding_path.read_text())
    if (
        binding["candidate_sha"] != candidate
        or binding["manifest_sha256"] != digest(raw)
        or binding["collector"]["exit_code"] != 0
        or binding["collector"]["collected_nodes"] != len(tests)
        or binding["collector"]["inventory"]
        != {
            "complete": True,
            "initial_nodes": len(tests),
            "final_nodes": len(tests),
        }
        or not binding["tracked_tree_clean"]
    ):
        raise ValueError("Collected inventory is not bound to the requested candidate")
    if not tests or len({t["nodeid"] for t in tests}) != len(tests):
        raise ValueError(
            "Inventory must be nonempty and contain unique collected node IDs"
        )
    if binding["runtime"] != python_runtime(root):
        raise ValueError(
            "Collected Python runtime differs from the test runner; collect again"
        )
    index = EvidenceIndex(root, candidate)
    for path, expected in binding["tracked_test_source_sha256"].items():
        if path not in index.paths or digest(index.source(path).encode()) != expected:
            raise ValueError(f"Collected source is stale: {path}")
    required = {t["file"] for t in tests} | {
        d["path"] for t in tests for d in t["fixturedefs"]
    }
    if not required <= set(binding["tracked_test_source_sha256"]):
        raise ValueError("Collected source binding omits tests or repository fixtures")
    if (
        binding.get("uv_lock_sha256") is not None
        and digest(index.source("uv.lock").encode()) != binding["uv_lock_sha256"]
    ):
        raise ValueError("Collected lockfile differs from the candidate")
    return tests


def prepare(
    root: Path,
    base: str,
    candidate: str,
    manifest: Path,
    binding: Path,
    output: Path,
    *,
    regeneration_proof: Path | None = None,
) -> Path:
    started, cpu = time.perf_counter(), cpu_time()
    root = root.resolve()
    base, candidate = commit(root, base), commit(root, candidate)
    tests = validate_manifest(root, candidate, manifest, binding)
    output.mkdir(parents=True, exist_ok=True)
    provenance = {
        "base": base,
        "candidate": candidate,
        "manifest_sha256": digest(manifest.read_bytes()),
    }
    indexes = [EvidenceIndex(root, ref) for ref in (base, candidate)]
    edges = {}
    for index in indexes:
        preload_python(index)
        _, dispatch, _, _ = graph(index)
        for owner, targets in dispatch.items():
            edges.setdefault(owner, set()).update(targets)
    changed = changed_python(indexes, base, candidate)
    paths = influence_paths(edges, changed)
    packets = ChangePackets(*indexes)
    cards = []
    mandatory = []
    for test in tests:
        card = packets.packet(test)
        if card["body"] is None:
            raise ValueError(
                f"Collected function has no candidate source: {test['nodeid']}"
            )
        roots = {(test["file"], test_function_name(test))} | {
            (
                fixture["path"],
                fixture.get("qualname", fixture["function"]).replace(".<locals>", ""),
            )
            for fixture in test["fixturedefs"]
        }
        graph_path = path_to_change(paths, roots)
        required = bool(graph_path or card["static_may_run"])
        if required:
            mandatory.append(test["nodeid"])
        cards.append(
            {
                "nodeid": test["nodeid"],
                "file": test["file"],
                "nightly": test["nightly"],
                "body": card["body"],
                "params": test["params"],
                "test_context": indexes[-1].test_context(test),
                "fixturenames": test["fixturenames"],
                "mandatory": required,
                "graph_path": graph_path,
                "change_witnesses": card["change_witnesses"],
                "provenance": provenance,
            }
        )
    css = literal_witnesses(
        *indexes,
        tests,
        contexts={card["nodeid"]: card["test_context"] for card in cards},
    )
    mandatory = set(mandatory) | css["witnesses"].keys()
    for card in cards:
        card["css_witnesses"] = css["witnesses"].get(card["nodeid"], [])
    proof = json.loads(regeneration_proof.read_text()) if regeneration_proof else None
    states = build_states(*indexes, tests, regeneration_proof=proof)
    mandatory = sorted(mandatory | set(states["auto_run_test_ids"]))
    unclassified = unresolved(cards, states["state_chunks"], mandatory)
    mandatory = sorted(set(mandatory) | {item["nodeid"] for item in unclassified})
    for card in cards:
        card["mandatory"] = card["nodeid"] in mandatory
    payload = {
        "schema": "leaf-test-select-inputs/v1",
        "root": str(root),
        **provenance,
        "manifest_file": str(manifest.resolve()),
        "manifest_binding_file": str(binding.resolve()),
        "binding_sha256": digest(binding.read_bytes()),
        "regeneration_proof_sha256": digest(regeneration_proof.read_bytes())
        if regeneration_proof
        else None,
        "policy": POLICY,
        "manifest": tests,
        "cards": cards,
        "states": states,
        "css_bridge": css,
        "unclassified_tests": unclassified,
        "mandatory_test_ids": mandatory,
        "preparation": {
            "wall_seconds": time.perf_counter() - started,
            "cpu_seconds": cpu_time() - cpu,
        },
    }
    path = output / "prepared.json"
    write_json(path, payload)
    write_json(
        output / "prepared-binding.json",
        {"sha256": digest(path.read_bytes()), **provenance},
    )
    return path
