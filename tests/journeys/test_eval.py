"""Tool-capable eval samples preserve real authored pages and independently validate them."""

import json
import socket
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from interact_support import STATED_TIMEOUT
from leaf_dev import ROOT, authoring_eval
from leaf_dev.arms import run_leaf
from leaf_dev.leaf_assets import pinned_copy
from model_folds import leaf_page


def test_authoring_repetitions_isolate_tools_and_grade_the_saved_page(
    tmp_path, monkeypatch
):
    """Only the model is replaced: media registration and the final render gate are real."""
    case = "shot-pair-outlined"
    pinned = pinned_copy(ROOT / "evals" / case)
    before = pinned / "captures/before.png"
    assert before.is_file(), "wt setup must fetch the pinned eval captures"
    observed = []
    servers = []
    fail_model = False

    def run_agent(cwd, request, *args, out, err, dirs, env, harness):
        page = cwd / "page"
        state = Path(env["XDG_STATE_HOME"])
        assert state == cwd / "state"
        assert env["LEAF"] == str(ROOT / "bin/leaf")
        assert dirs == [ROOT]
        assert harness == "claude-code"
        if len(observed) < 2:
            source = ROOT / sources[len(observed)]
            injected = args[args.index("--append-system-prompt") + 1]
            assert injected == f"Instructions from {source}:\n\n" + source.read_text()
            assert (out.parent / "instructions.txt").read_text() == injected
        else:
            assert "--append-system-prompt" not in args
        assert "Use the provided capture" in request
        assert str(page / "index.html") in request
        assert json.loads((page / "registry.json").read_text())["lf-shot"]["required"]
        assert not (cwd / "sample-marker").exists()
        (cwd / "sample-marker").write_text("one repetition")
        capture = cwd / "evals" / case / "captures/before.png"
        assert capture.read_bytes() == before.read_bytes()
        registration = run_leaf(
            ROOT, state, "page", "media", str(page), str(capture), check=True
        )
        url = json.loads(registration.stdout)["path"]
        if len(observed) == 1:
            # The historical failure: nested images instead of the required attributes.
            shot = f'<lf-shot id="pair" alt="Header"><img src="{url}"></lf-shot>'
        else:
            shot = f'<lf-shot id="pair" before="{url}" after="{url}" alt="Header"></lf-shot>'
        (page / "index.html").write_text(
            leaf_page("Header change", f"<h1>Header change</h1>{shot}")
        )
        observed.append((cwd, state, url))
        if len(observed) == 1:
            started = run_leaf(
                ROOT, state, "server", "start", str(page), "--standing", check=True
            )
            servers.append(urlsplit(json.loads(started.stdout)["url"]))
        if fail_model:
            out.write_text('{"type":"assistant","message":{"content":[]}}\n')
            err.write_text("model transport unavailable\n")
            raise RuntimeError("model transport unavailable")
        trace = [
            {
                "type": "result",
                "is_error": False,
                "result": "Page complete.",
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        ]
        out.write_text("\n".join(json.dumps(record) for record in trace) + "\n")
        err.write_text("")
        return trace

    monkeypatch.setattr(authoring_eval, "run_agent", run_agent)
    evidence_dirs = [tmp_path / name for name in ("first", "second")]
    responses = []
    sources = [
        ".claude/skills/developing-leaf/SKILL.md",
        ".claude/skills/ui-sweep/SKILL.md",
    ]
    for evidence, source in zip(evidence_dirs, sources, strict=True):
        evidence.mkdir()
        responses.append(
            authoring_eval.execute(
                "Use the provided capture",
                ROOT,
                evidence,
                {"case": case, "instructions": source},
                harness="claude-code",
                shots=tmp_path / "screenshots" / evidence.name,
            )
        )
    assert observed[0][0] != observed[1][0]
    assert observed[0][1] != observed[1][1]
    assert all(not cwd.exists() for cwd, _, _ in observed)
    assert json.loads((evidence_dirs[0] / "stop.txt").read_text()) == {"stopped": True}
    for address in servers:
        with (
            pytest.raises(OSError),
            socket.create_connection(
                (address.hostname, address.port), timeout=STATED_TIMEOUT
            ),
        ):
            pass
    assert [response["metadata"]["checks"] for response in responses] == [
        {"completed": True, "page-valid": True},
        {"completed": True, "page-valid": False},
    ]
    for evidence, response, (_, _, url) in zip(
        evidence_dirs, responses, observed, strict=True
    ):
        assert response["output"] == (evidence / "page/index.html").read_text()
        assert response["output"] != "Page complete."
        assert (
            evidence / "page" / url.removeprefix("/")
        ).read_bytes() == before.read_bytes()
        assert (evidence / "prompt.txt").is_file()
        assert json.loads((evidence / "stream.jsonl").read_text())["is_error"] is False
        assert json.loads((evidence / "result.json").read_text()) == response
        assert response["tokenUsage"] == {"prompt": 11, "completion": 7}
        assert (
            response["metadata"]["input_media"][f"evals/{case}/captures/before.png"]
            == url
        )
        captures = response["metadata"]["capture_evidence"]
        assert (
            Path(captures["inputs"]["captures/before.png"]).read_bytes()
            == before.read_bytes()
        )
        assert Path(captures["media"][url]).read_bytes() == before.read_bytes()
        assert captures["exact_inputs"][url] == ["captures/before.png"]
        shots = tmp_path / "screenshots" / evidence.name
        assert {path.name for path in shots.iterdir()} == {"inputs", "media"}
        assert not list(shots.rglob("*.jsonl"))
        assert not list(shots.rglob("*.txt"))
    refused = (evidence_dirs[1] / "check.txt").read_text()
    assert "lf-shot" in refused and "before" in refused and "after" in refused

    fail_model = True
    failed_evidence = tmp_path / "failed"
    failed_evidence.mkdir()
    with pytest.raises(RuntimeError, match="model transport unavailable"):
        authoring_eval.execute(
            "Use the provided capture",
            ROOT,
            failed_evidence,
            {"case": case},
            harness="claude-code",
        )
    failed_cwd, _, url = observed[-1]
    assert not failed_cwd.exists()
    assert "Header change" in (failed_evidence / "page/index.html").read_text()
    assert (
        failed_evidence / "page" / url.removeprefix("/")
    ).read_bytes() == before.read_bytes()
    assert (failed_evidence / "err.txt").read_text() == "model transport unavailable\n"
    assert not (failed_evidence / "result.json").exists()
