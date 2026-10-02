"""A/B instruction cases refer to each payload's own package instruction files."""

import re
from copy import deepcopy

import click
import pytest
import yaml
from leaf_dev import ROOT
from leaf_dev.instructions_eval import resolve_case_instruction_paths


@pytest.mark.parametrize(
    ("directories", "selected"),
    [
        (("instructions",), "instructions"),
        (("guidance",), "guidance"),
        (("instructions", "guidance"), "instructions"),
    ],
)
def test_case_paths_resolve_per_payload_without_changing_the_task_or_scoring(
    tmp_path, directories, selected
):
    source = ROOT / "evals" / "playground-presets-are-whole-designs" / "case.yaml"
    case = tmp_path / "evals" / "case.yaml"
    case.parent.mkdir()
    case.write_text(source.read_text())
    original = yaml.safe_load(case.read_text())
    instruction_files = []
    for directory in directories:
        path = (
            tmp_path
            / "skills"
            / "leaf"
            / "packages"
            / "playground"
            / directory
            / "author.md"
        )
        path.parent.mkdir(parents=True)
        path.write_text(f"This payload's {directory} instructions.\n")
        instruction_files.append(path)

    resolve_case_instruction_paths(case, tmp_path)
    prepared = yaml.safe_load(case.read_text())
    assert (
        f"packages/playground/{selected}/author.md" in prepared["execution"]["prompt"]
    )
    read_grader = next(
        grader for grader in prepared["graders"] if grader.get("tool") == "Read"
    )
    target = (
        tmp_path
        / "skills"
        / "leaf"
        / "packages"
        / "playground"
        / selected
        / "author.md"
    )
    assert re.search(read_grader["input_match"], str(target))

    # Only resource addresses change. In particular the judge measures the same
    # composed-design behavior, and both arms demand the same successful file read.
    expected = deepcopy(original)
    if selected == "guidance":
        expected["execution"]["prompt"] = expected["execution"]["prompt"].replace(
            "/instructions/", "/guidance/"
        )
        for grader in expected["graders"]:
            if grader.get("tool") == "Read":
                grader["input_match"] = grader["input_match"].replace(
                    "/instructions/", "/guidance/"
                )
    assert prepared == expected
    for path in instruction_files:
        assert path.read_text() == f"This payload's {path.parent.name} instructions.\n"
    if selected == "guidance":
        assert not (
            tmp_path / "skills" / "leaf" / "packages" / "playground" / "instructions"
        ).exists()


def test_missing_instruction_reference_fails_preparation_without_rewriting_case(
    tmp_path,
):
    case = tmp_path / "case.yaml"
    source = (
        "execution:\n  prompt: Read `packages/playground/instructions/author.md`.\n"
    )
    case.write_text(source)
    with pytest.raises(
        click.ClickException, match="package instruction file .* is absent"
    ):
        resolve_case_instruction_paths(case, tmp_path)
    assert case.read_text() == source
