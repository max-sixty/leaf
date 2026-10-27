"""Expected watch faults keep their node identity across presentation state changes."""

import pytest
from render_harness import is_problem

from leaf.findings import Finding


@pytest.mark.parametrize(
    "place, expected",
    [
        (["leaf-text#field.lf-projected-mark.scroll"], True),
        (["leaf-text#field.scroll"], True),
        (["leaf-text#field.lf-projected-mark"], False),
        (["leaf-text#other.scroll.lf-projected-mark"], False),
        (["textarea#field.scroll.lf-projected-mark"], False),
        (["#text", "leaf-text#field.scroll.lf-projected-mark"], False),
        (
            ["leaf-text#field.scroll.lf-projected-mark", "#shadow-root", "div#host"],
            False,
        ),
    ],
)
def test_expected_fault_keeps_its_node_and_requested_classes(place, expected):
    problem = Finding("typing-moved", values={"node": place, "by": [0, 40]})
    assert (
        is_problem(
            problem,
            {"code": "typing-moved", "node": ["leaf-text#field.scroll"], "by": [0, 40]},
        )
        is expected
    )
    assert not is_problem(
        problem,
        {"code": "typing-moved", "node": ["leaf-text#field.scroll"], "by": [0, 20]},
    )
    assert not is_problem(problem, {"code": "moved-without-input"})


def test_expected_fault_keeps_its_shadow_host_and_field():
    path = ["div.cm-line.lf-face-p", "#shadow-root", "leaf-text#field.scroll"]
    problem = Finding(
        "typing-moved",
        values={"node": path, "field": ["leaf-text#field.scroll.lf-projected-mark"]},
    )
    expected = {
        "code": "typing-moved",
        "node": ["div.cm-line", "#shadow-root", "leaf-text#field"],
        "field": ["leaf-text#field"],
    }
    assert is_problem(problem, expected)
    assert not is_problem(problem, expected | {"field": ["leaf-text#other"]})
    assert not is_problem(
        problem,
        expected | {"node": ["div.cm-line", "#shadow-root", "leaf-text#other"]},
    )
