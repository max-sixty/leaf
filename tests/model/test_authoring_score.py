"""Fixed authoring evidence separates observed defects, gaps and judge failures."""

import json

import pytest
import yaml
from click.testing import CliRunner
from leaf_dev import authoring_score
from leaf_dev.eval_judge import validate_reads


def test_promptfoo_adapter_retains_gap_and_scores_only_observed_criteria(
    tmp_path, monkeypatch
):
    from leaf_dev import authoring_assertion

    work = tmp_path / "samples" / "sample"
    work.mkdir(parents=True)
    grade = {
        "status": "observation_gap",
        "named_scores": {"legibility": 1},
        "criteria": {
            "content": {
                "status": "observation_gap",
                "explanation": "Required evidence remains unobserved.",
            }
        },
    }
    monkeypatch.setattr(authoring_assertion, "score_sample", lambda *a, **kw: grade)
    result = authoring_assertion.get_assert(
        "authored reply", {"providerResponse": {"metadata": {"work": str(work)}}}
    )
    assert result["pass"] is False
    assert result["metadata"]["authoring_grade"]["status"] == "observation_gap"
    assert result["namedScores"] == {"legibility": 1}
    assert "Required evidence remains unobserved" in result["reason"]


def test_authoring_summary_retains_provider_failure_as_unscored(tmp_path):
    from leaf_dev.authoring_assertion import summarize_run

    rows = [
        {
            "testCase": {"metadata": {"executor": "leaf_dev.arrangement_eval"}},
            "gradingResult": {
                "componentResults": [
                    {
                        "metadata": {
                            "authoring_grade": {
                                "scored": True,
                                "status": "observation_gap",
                            }
                        }
                    }
                ]
            },
        },
        {
            "testCase": {"metadata": {"executor": "leaf_dev.arrangement_eval"}},
            "error": "Author provider failed before producing evidence",
        },
    ]
    (tmp_path / "results.json").write_text(json.dumps({"results": {"results": rows}}))
    summary = summarize_run(tmp_path)
    assert summary["samples"] == 2
    assert summary["observation_gap"] == summary["unscored"] == 1
    assert summary["defect"] == summary["pass"] == 0


def staged(tmp_path, **kwargs):
    image = tmp_path / "capture.png"
    # The model boundary below is scripted. This test checks evidence delivery and
    # score semantics, not image decoding or a model's visual judgment.
    image.write_bytes(b"recorded image bytes")
    return authoring_score.stage_packet(
        tmp_path / "packet",
        request="Read the evidence and choose an option.",
        messages=[],
        captures={"narrow": [str(image)]},
        provenance={"authoring": "author-rev", "runtime": "runtime-rev"},
        **kwargs,
    )


def model(
    monkeypatch, packet, *, statuses=None, skip_image=False, invalid=None, evidence=None
):
    """Replace only the remote model; record its native result/tool-call shape."""
    criteria = yaml.safe_load((packet / "rubric.yaml").read_text())["criteria"]
    images = authoring_score.read_packet(packet)["images"]
    grade = {
        name: {
            "status": (statuses or {}).get(
                name, "pass" if name in ("content", "legibility") else "not_applicable"
            ),
            "explanation": "Supported by the supplied task and captured state.",
            "evidence": evidence
            if evidence is not None
            else [images[0]["id"] if images else "request"],
        }
        for name in criteria
    }
    if invalid == "reference":
        grade["content"]["evidence"] = ["invented-image"]
    if invalid == "criterion":
        grade.pop("content")
    if invalid == "missing":
        grade = None
    if invalid == "inapplicable":
        grade["content"]["status"] = "not_applicable"

    def run(cwd, prompt, *args, out, err, **kwargs):
        assert kwargs["model"] == authoring_score.MODELS["judge"]
        schema = json.loads(args[args.index("--json-schema") + 1])
        assert set(schema["required"]) == set(criteria)
        files = (
            []
            if invalid == "unread-inputs"
            else ["packet.json", "rubric.yaml", "observations.json"]
        )
        if not skip_image:
            files.extend(image["file"] for image in images)
        if invalid == "private-read":
            files.append("provenance.json")
        trace = []
        for number, name in enumerate(files):
            identity = f"read-{number}"
            trace.extend(
                [
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": identity,
                                    "name": "Read",
                                    "input": {"file_path": str(packet / name)},
                                }
                            ]
                        },
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": identity,
                                    "is_error": invalid == "read-denied"
                                    and name.endswith("png"),
                                    "content": "recorded file",
                                }
                            ]
                        },
                    },
                ]
            )
        trace += [
            {
                "type": "result",
                "is_error": invalid == "transport",
                "structured_output": grade,
            },
        ]
        out.write_text("".join(json.dumps(row) + "\n" for row in trace))
        err.write_text("")
        return trace

    monkeypatch.setattr(authoring_score, "run_agent", run)


def test_fixed_packet_retains_inputs_and_refuses_changed_evidence(
    tmp_path, monkeypatch
):
    observation = {
        "widths": {
            "narrow": {
                "states": [
                    {
                        "id": "narrow-state-0",
                        "label": "opened evidence",
                        "images": [str(tmp_path / "capture.png")],
                    }
                ]
            }
        },
    }
    packet = staged(tmp_path, observations=observation)
    frozen = authoring_score.read_packet(packet)
    assert frozen["provenance"]["authoring"] == "author-rev"
    assert frozen["provenance"]["runtime"] == "runtime-rev"
    assert frozen["provenance"]["evaluator"]["files"]
    public = json.loads((packet / "packet.json").read_text())
    assert "provenance" not in public and "judge" not in public
    assert json.loads((packet / "observations.json").read_text())["widths"]["narrow"][
        "states"
    ][0]["images"] == ["image-001"]
    assert (packet / "evaluator.py").is_file()
    # A changed calibration artifact cannot be silently rejudged as its old input.
    (packet / "image-001.png").write_bytes(b"changed image bytes")
    monkeypatch.setattr(
        authoring_score,
        "run_agent",
        lambda *args, **kwargs: pytest.fail("changed evidence reached judge"),
    )
    result = authoring_score.evaluate(packet)
    assert not result["scored"] and result["status"] == "unscored"
    assert "Frozen authoring evidence changed" in result["error"]


def test_supported_defect_survives_observation_gap_and_scores_exclude_unknown(
    tmp_path, monkeypatch
):
    packet = staged(tmp_path)
    model(
        monkeypatch,
        packet,
        statuses={
            "content": "defect",
            "legibility": "pass",
            "navigation": "observation_gap",
        },
    )
    result = authoring_score.evaluate(packet)
    assert result["scored"] and result["status"] == "defect"
    assert result["named_scores"] == {"content": 0, "legibility": 1}
    assert result["criteria"]["navigation"]["status"] == "observation_gap"
    assert result["opened_images"] == ["image-001"]
    assert result["judgment"] == "model"


@pytest.mark.parametrize(
    "invalid",
    [
        "missing",
        "reference",
        "criterion",
        "transport",
        "unread",
        "read-denied",
        "inapplicable",
        "unread-inputs",
        "private-read",
    ],
)
def test_judge_failure_cannot_become_page_failure_or_pass(
    tmp_path, monkeypatch, invalid
):
    packet = staged(tmp_path)
    model(monkeypatch, packet, invalid=invalid, skip_image=invalid == "unread")
    result = authoring_score.evaluate(packet)
    assert not result["scored"] and result["status"] == "unscored"
    assert "named_scores" not in result


def test_missing_observation_is_retained_and_not_renamed_a_defect(
    tmp_path, monkeypatch
):
    packet = staged(tmp_path)
    inputs = authoring_score.read_packet(packet)
    assert "No browser observation record" in inputs["limitations"][0]
    model(
        monkeypatch,
        packet,
        statuses={"content": "observation_gap", "legibility": "pass"},
    )
    result = authoring_score.evaluate(packet)
    assert result["status"] == "observation_gap"
    assert result["named_scores"] == {"legibility": 1}


def test_replay_uses_historical_phases_and_saved_inputs_without_future_messages(
    tmp_path, monkeypatch
):
    run = tmp_path / "run"
    work = run / "samples" / "queue-sample"
    work.mkdir(parents=True)
    image = run / "old-shot.png"
    image.write_bytes(b"frozen")
    (work / "prompt-1.txt").write_text(
        "Historical request, with facts current request lacks."
    )
    (work / "prompt-2.txt").write_text("Historical standing preference.")
    (work / "prompt-3.txt").write_text("Historical comment.")
    (work / "prompt-4.txt").write_text("Future decision must not leak.")
    (run / "results.json").write_text(
        json.dumps(
            {
                "results": {
                    "results": [
                        {
                            "response": {
                                "metadata": {
                                    "work": str(work),
                                    "diagnostics": {
                                        "subject": "queue",
                                        "phases": {
                                            str(n): {
                                                "captures": {"narrow": [str(image)]}
                                            }
                                            for n in (1, 2, 3)
                                        },
                                    },
                                }
                            }
                        }
                    ]
                }
            }
        )
    )

    def grade(packet):
        inputs = authoring_score.read_packet(packet)
        assert inputs["phase"] == 3
        assert inputs["request"].startswith("Historical request")
        assert inputs["messages"] == [
            "Historical standing preference.",
            "Historical comment.",
        ]
        assert "Future" not in json.dumps(inputs)
        assert inputs["provenance"]["runtime"] is None
        return {"scored": True, "status": "observation_gap"}

    monkeypatch.setattr(authoring_score, "evaluate", grade)
    output = tmp_path / "score"
    response = CliRunner().invoke(
        authoring_score.eval_score, [str(run), "--output", str(output)]
    )
    assert response.exit_code == 0, response.output
    assert json.loads((output / "scores.json").read_text())[0]["phase"] == 3
    refused = CliRunner().invoke(
        authoring_score.eval_score, [str(run), "--output", str(output)]
    )
    assert refused.exit_code != 0 and "already exists" in refused.output


def test_partial_recorded_inputs_keep_known_messages_and_mark_unknown_phases(tmp_path):
    (tmp_path / "stream.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"type": "eval_phase", "phase": 1},
                {"type": "eval_phase", "phase": 2},
                {"type": "eval_send", "text": "Known width preference."},
                {"type": "eval_phase", "phase": 3},
                {"type": "eval_phase", "phase": 4},
                {"type": "eval_send", "text": "Future decision."},
            ]
        )
    )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 3)
    assert messages == ["Known width preference."]
    assert limitations and "[3]" in limitations[0]


def test_page_decisions_recover_values_instead_of_scaffold(tmp_path):
    for number in (2, 3, 4):
        (tmp_path / f"prompt-{number}.txt").write_text("Handle the saved input.")
    decision = tmp_path / "decision.json"
    decision.write_text(
        json.dumps(
            {
                "route": "page",
                "gestures": [
                    {"widget": "option", "action": "pick", "detail": "Postgres"}
                ],
            }
        )
    )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 4)
    assert "Postgres" in messages[-1]
    assert limitations == []
    decision.write_text(json.dumps({"route": "page", "gestures": []}))
    messages, limitations = authoring_score.recorded_messages(tmp_path, 4)
    assert len(messages) == 2
    assert limitations and "[4]" in limitations[0]


@pytest.mark.parametrize(
    "state_id,valid", [("narrow-state-0", True), ("invented-state", False)]
)
def test_judge_state_citations_resolve_only_to_actual_observation_records(
    tmp_path, monkeypatch, state_id, valid
):
    observations = {
        "widths": {
            "narrow": {
                "states": [
                    {
                        "id": "narrow-state-0",
                        "label": "Arrival",
                        "images": [str(tmp_path / "capture.png")],
                    }
                ]
            }
        }
    }
    packet = staged(tmp_path, observations=observations)
    inputs = authoring_score.read_packet(packet)
    assert "narrow-state-0" in inputs["evidence_ids"]
    assert "invented-state" not in inputs["evidence_ids"]
    model(monkeypatch, packet, evidence=[state_id])
    result = authoring_score.evaluate(packet)
    assert result["scored"] is valid
    assert result["status"] == ("pass" if valid else "unscored")
    if valid:
        raw = json.loads((packet / "judgment/raw-grade.json").read_text())
        schema = json.loads((packet / "schema.json").read_text())
        supplied_observations = json.loads((packet / "observations.json").read_text())
        # Revalidation retains the exact model conclusion; a claimed ID added to
        # a cached registry cannot manufacture a real supplied observation.
        assert (
            authoring_score.validate_grade(raw, inputs, supplied_observations, schema)
            is raw
        )
        inputs["evidence_ids"].append("invented-state")
        raw["content"]["evidence"] = ["invented-state"]
        with pytest.raises(ValueError, match="unknown evidence IDs"):
            authoring_score.validate_grade(raw, inputs, supplied_observations, schema)


def test_absent_page_decision_record_retains_chat_without_claiming_complete_inputs(
    tmp_path,
):
    for number in (2, 3, 4):
        (tmp_path / f"prompt-{number}.txt").write_text(
            "Apply my decisions from the page."
        )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 4)
    assert len(messages) == 3
    assert (
        limitations
        and "choices it refers to without naming remain unknown" in limitations[0]
    )
    page = tmp_path / "page-phase4"
    page.mkdir()
    log = page / "events.jsonl"
    receipt = {"id": "receipt", "author": "user", "kind": "read", "attention": False}
    log.write_text(json.dumps(receipt) + "\n")
    _, limitations = authoring_score.recorded_messages(tmp_path, 4)
    assert limitations
    pick = {
        "id": "choice",
        "author": "user",
        "kind": "choose",
        "attention": True,
        "detail": "Postgres",
    }
    log.write_text(json.dumps(receipt) + "\n" + json.dumps(pick) + "\n")
    messages, limitations = authoring_score.recorded_messages(tmp_path, 4)
    assert "Postgres" in messages[-1] and "receipt" not in messages[-1]
    assert limitations == []


def test_shared_sample_grader_prefers_canonical_phase_input_manifest(
    tmp_path, monkeypatch
):
    work = tmp_path / "sample"
    work.mkdir()
    (work / "prompt-1.txt").write_text(
        "Old setup wrapper must not override canonical inputs."
    )
    (work / "authoring-inputs.json").write_text(
        json.dumps(
            {
                "request": "Actual user task.",
                "phases": {
                    "2": {"messages": ["Actual width preference."]},
                    "3": {"messages": ["Future comment."]},
                },
            }
        )
    )
    metadata = {
        "work": str(work),
        "diagnostics": {"phases": {"2": {"captures": {"narrow": []}}}},
    }

    def grade(packet):
        public = json.loads((packet / "packet.json").read_text())
        assert public["request"] == "Actual user task."
        assert public["messages"] == ["Actual width preference."]
        return {"scored": True, "status": "observation_gap"}

    monkeypatch.setattr(authoring_score, "evaluate", grade)
    result = authoring_score.score_sample(metadata, tmp_path, tmp_path / "packet")
    assert result["phase"] == 2 and result["sample"] == work.name


@pytest.mark.parametrize("changed", [{"files": {}}, {"model": "different-model"}])
def test_changed_evaluator_requires_new_packet_from_same_artifact(
    tmp_path, monkeypatch, changed
):
    packet = staged(tmp_path)
    identity = authoring_score.evaluator_identity()
    monkeypatch.setattr(
        authoring_score,
        "evaluator_identity",
        lambda: {**identity, **changed},
    )
    monkeypatch.setattr(
        authoring_score,
        "run_agent",
        lambda *args, **kwargs: pytest.fail(
            "different evaluator ran against frozen packet"
        ),
    )
    result = authoring_score.evaluate(packet)
    assert not result["scored"] and "Evaluator changed" in result["error"]


def test_git_context_alone_does_not_change_the_frozen_evaluator(tmp_path, monkeypatch):
    packet = staged(tmp_path)
    identity = authoring_score.evaluator_identity()
    monkeypatch.setattr(
        authoring_score,
        "evaluator_identity",
        lambda: {**identity, "commit": "documentation-only-context"},
    )
    model(monkeypatch, packet)
    result = authoring_score.evaluate(packet)
    assert result["scored"] and result["status"] == "pass"
    assert result["provenance"]["evaluator"]["commit"] == identity["commit"]


def test_leaf_revision_recovers_admitted_comment_and_keeps_missing_input_unknown(
    tmp_path,
):
    (tmp_path / "prompt-2.txt").write_text("Width preference.")
    (tmp_path / "prompt-3.txt").write_text(
        "A comment is waiting on the page; handle it."
    )
    (tmp_path / "comment.json").write_text(json.dumps({"event": "comment-id"}))
    page = tmp_path / "page-phase3"
    page.mkdir()
    log = page / "events.jsonl"
    log.write_text(
        json.dumps(
            {
                "id": "comment-id",
                "author": "user",
                "kind": "comment",
                "text": "Name Mei Tanaka here.",
            }
        )
        + "\n"
    )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 3)
    assert messages[-1] == "Name Mei Tanaka here."
    assert limitations == []
    # A scaffold is not the user's missing requirement, and an agent's claim
    # cannot substitute for the absent admitted user comment.
    log.write_text(
        json.dumps(
            {
                "id": "comment-id",
                "author": "agent",
                "kind": "comment",
                "text": "I handled the comment.",
            }
        )
        + "\n"
    )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 3)
    assert messages == ["Width preference."]
    assert limitations and "[3]" in limitations[0]


def test_historical_comment_uses_saved_phase_difference_without_comment_record(
    tmp_path,
):
    (tmp_path / "prompt-2.txt").write_text("Width preference.")
    (tmp_path / "prompt-3.txt").write_text("Handle the comment on the page.")
    earlier = {
        "id": "earlier",
        "author": "user",
        "kind": "comment",
        "text": "Earlier input.",
    }
    added = {
        "id": "new",
        "author": "user",
        "kind": "comment",
        "text": "Name Mei Tanaka here.",
    }
    for number, events in ((2, [earlier]), (3, [earlier, added])):
        page = tmp_path / f"page-phase{number}"
        page.mkdir()
        (page / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in events)
        )
    messages, limitations = authoring_score.recorded_messages(tmp_path, 3)
    assert messages == [
        "Width preference.",
        "Handle the comment on the page.",
        "Name Mei Tanaka here.",
    ]
    assert limitations == []


def test_shared_native_integrity_allows_only_declared_optional_public_evidence(
    tmp_path,
):
    required, optional = tmp_path / "brief.md", tmp_path / "public-reading.json"
    trace = []
    for number, path in enumerate((required, optional)):
        trace.extend(
            [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": str(number),
                                "name": "Read",
                                "input": {"file_path": str(path)},
                            }
                        ]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": str(number),
                                "is_error": False,
                            }
                        ]
                    },
                },
            ]
        )
    trace.append({"type": "result", "is_error": False})
    assert validate_reads(trace, [required], [required, optional]) == {
        str(required),
        str(optional),
    }
    with pytest.raises(ValueError, match="outside the public evidence manifest"):
        validate_reads(trace, [required])
    with pytest.raises(ValueError, match="Required judge evidence is outside"):
        validate_reads(trace, [required], [optional])


def test_no_images_cannot_support_legibility_even_when_judge_reads_all_inputs(
    tmp_path, monkeypatch
):
    packet = authoring_score.stage_packet(
        tmp_path / "packet",
        request="Read the page.",
        messages=[],
        captures={"narrow": []},
    )
    model(
        monkeypatch,
        packet,
        statuses={"content": "observation_gap", "legibility": "pass"},
        evidence=["request"],
    )
    result = authoring_score.evaluate(packet)
    assert result["status"] == "unscored"
    assert (
        "legibility: a scored conclusion requires a supplied image" in result["error"]
    )
    assert result["opened_inputs"] == [
        "packet.json",
        "rubric.yaml",
        "observations.json",
    ]


@pytest.mark.parametrize(
    "reference", ["request", "messages", "observations", "empty-state"]
)
def test_requirements_and_empty_metadata_cannot_substitute_for_artifact_evidence(
    tmp_path, monkeypatch, reference
):
    observations = {
        "widths": {
            "narrow": {
                "states": [{"id": "empty-state", "label": "Unobserved", "images": []}]
            }
        }
    }
    packet = staged(tmp_path, observations=observations)
    model(
        monkeypatch,
        packet,
        statuses={"content": "pass", "legibility": "observation_gap"},
        evidence=[reference],
    )
    result = authoring_score.evaluate(packet)
    assert result["status"] == "unscored"
    assert (
        "content: a scored conclusion requires supplied artifact evidence"
        in result["error"]
    )
