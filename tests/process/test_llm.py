"""Widget inference uses the claimant's login over HTTP, without page writes."""

import json
import os
import sys

import pytest
from interact_support import PAGE, TOKEN, fetch, publish, read_page_data, record_claim

from leaf import event_log, inference
from leaf.hosting import TemporaryPageServer
from leaf.page_snapshot import capture_page_snapshot
from leaf.revision_artifact import read_revision

SCHEMA = {
    "type": "object",
    "properties": {"headline": {"type": "string"}},
    "required": ["headline"],
    "additionalProperties": False,
}
REQUEST = {"input": "Story context", "schema": SCHEMA}


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    """Replace only the logged-in CLI executable; keep HTTP and inference real."""
    programs = tmp_path / "programs"
    programs.mkdir()
    executable = programs / "claude"
    record = tmp_path / "claude-calls.jsonl"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['LLM_TEST_RECORD'], 'a') as record:\n"
        "    record.write(json.dumps({'argv': sys.argv[1:], 'input': sys.stdin.read()}) + '\\n')\n"
        "print(json.dumps({'structured_output': {'headline': 'Hello'}, "
        "'duration_api_ms': 90, 'usage': {'input_tokens': 30, 'output_tokens': 12}}))\n"
    )
    executable.chmod(0o755)
    monkeypatch.setenv("LLM_TEST_RECORD", str(record))
    monkeypatch.setenv("PATH", f"{programs}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("LEAF_LLM_MODEL", raising=False)
    return record


def infer(server, body=REQUEST, **kwargs):
    status, raw = fetch(
        server + "/api/llm",
        data=json.dumps(body).encode(),
        headers={"Origin": server},
        **kwargs,
    )
    return status, json.loads(raw)


def test_llm_uses_claimants_login_and_host_model_without_persisting(
    server, claimed, fake_claude, monkeypatch
):
    before = event_log.read_events(claimed), read_page_data(claimed)
    status, answer = infer(server, REQUEST | {"instructions": "Be concise"})
    assert status == 200, answer
    assert answer["value"] == {"headline": "Hello"}
    assert answer["model"] == "haiku"
    assert answer["usage"] == {"inputTokens": 30, "outputTokens": 12}
    assert isinstance(answer["durationMs"], int)
    [call] = [json.loads(line) for line in fake_claude.read_text().splitlines()]
    assert call["input"] == REQUEST["input"]
    argv = call["argv"]
    assert "--tools=" in argv
    assert "--safe-mode" in argv
    assert "--no-session-persistence" in argv
    assert "--model=haiku" in argv
    assert argv[argv.index("--system-prompt") + 1] == "Be concise"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    monkeypatch.setenv("LEAF_LLM_MODEL", "host-model")
    status, answer = infer(server)
    assert status == 200, answer
    assert answer["model"] == "host-model"
    calls = [json.loads(line) for line in fake_claude.read_text().splitlines()]
    assert len(calls) == 2
    assert "--model=host-model" in calls[-1]["argv"]
    status, answer = infer(server, REQUEST | {"schema": {"type": "array"}})
    assert status == 502, answer
    assert "not of type 'array'" in answer["error"]
    assert len(fake_claude.read_text().splitlines()) == 3
    assert (event_log.read_events(claimed), read_page_data(claimed)) == before


def test_llm_rejects_untrusted_requests_before_inference(
    server, claimed, fake_claude, subtests
):
    for body in (
        REQUEST | {"model": "costly-model"},
        REQUEST | {"tools": []},
        REQUEST | {"input": 12},
        REQUEST | {"input": "x" * 65536},
        {"input": "No schema"},
        REQUEST | {"schema": {"type": "invented"}},
        REQUEST | {"schema": {"$ref": "#/$defs/missing"}},
        REQUEST | {"schema": {"$ref": "https://untrusted.invalid/schema"}},
    ):
        with subtests.test(body=str(body)[:80]):
            assert infer(server, body)[0] == 400
    for origin in ({}, {"Origin": "https://other.invalid"}):
        with subtests.test(origin=origin):
            assert (
                fetch(
                    server + "/api/llm",
                    data=json.dumps(REQUEST).encode(),
                    headers=origin,
                )[0]
                == 403
            )
    assert infer(server, token=None)[0] == 401
    assert not fake_claude.exists()


def test_llm_failures_do_not_retry(server, claimed, monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("The login needs refreshing")

    monkeypatch.setattr(inference, "claude_code_generate", fail)
    status, answer = infer(server)
    assert status == 502, answer
    assert "login needs refreshing" in answer["error"]
    assert len(calls) == 1


def test_llm_requires_a_supported_active_claim(
    server, page_dir, fake_claude, monkeypatch
):
    status, answer = infer(server)
    assert status == 503, answer
    record_claim(page_dir, harness="pi", agent="Pi")
    assert infer(server)[0] == 503
    record_claim(page_dir, harness="codex", agent="Codex")
    calls = []

    def codex(request, target, **options):
        calls.append((request, target, options))
        return {
            "value": {"headline": "From Codex"},
            "model": "gpt-6-luna",
            "usage": {"inputTokens": 30, "outputTokens": 12},
            "durationMs": 1,
        }

    monkeypatch.setattr(inference, "codex_generate", codex)
    status, answer = infer(server)
    assert status == 200, answer
    assert answer["value"] == {"headline": "From Codex"}
    assert calls == [
        (
            REQUEST["input"],
            page_dir,
            {"schema": SCHEMA, "instructions": "", "model": None},
        )
    ]
    assert not fake_claude.exists()


def test_llm_is_unavailable_in_samples_and_read_only_previews(
    server, claimed, fake_claude
):
    template = '<template id="practice" data-sample><h1>Practice</h1></template>'
    (claimed / "index.html").write_text(PAGE.replace("</main>", template + "</main>"))
    publish(claimed)
    status, raw = fetch(server + "/api/samples", data=b'{"template":"practice"}')
    assert status == 200, raw
    child = server + json.loads(raw)["url"].rstrip("/")
    assert (
        fetch(
            child + "/api/llm",
            data=json.dumps(REQUEST).encode(),
            headers={"Origin": server},
        )[0]
        == 403
    )
    snapshot = capture_page_snapshot(
        claimed, read_revision(claimed, 1).document, 1, url="test"
    )
    with TemporaryPageServer(
        claimed, token=TOKEN, page_options={"page_snapshot": snapshot}
    ) as preview:
        assert infer(preview.origin)[0] == 403
    assert not fake_claude.exists()
