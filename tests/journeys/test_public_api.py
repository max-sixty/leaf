"""Tests scheduled by the measured cost of their boundary."""

import pytest
from browser.test_public_api import output_package
from model_folds import leaf_page

from leaf.pages.render_gate.version import _render_page
from leaf.pages.render_gate.widget_quality import widget_findings
from leaf.source.render_checks import RENDER_VIEWPORT, SERVED_TIMEOUT_MS
from leaf.source.revision_artifact import read_artifact


@pytest.mark.parametrize("ending", ["removed", "navigated"])
def test_render_check_keeps_departed_samples_invalid_outputs(
    tmp_path, browser, serve, ending
):
    package = tmp_path / "sample-output-package"
    output_package(package, {"count": "wrong"})
    url = serve(
        leaf_page(
            "Sample output",
            "<h1>Example producers</h1>"
            + "".join(
                f"""<lf-sample id="example-{n}" label="producer example {n}">
  <template id="example-page-{n}" data-sample>
    <lf-output-proof id="proof">Output example.</lf-output-proof>
  </template>
</lf-sample>"""
                for n in range(3)
            ),
        ),
        packages=(package,),
    )
    artifact = read_artifact(serve.page_dir, 1)
    pages = []

    def leave_samples(page, registry):
        assert len(page.frames) == 4
        if ending == "removed":
            page.locator("lf-sample").evaluate_all(
                "els => els.forEach(el => el.remove())"
            )
        else:
            for frame in page.frames[1:]:
                frame.goto("about:blank")

    findings, _, complete = _render_page(
        browser.unwatched,
        url,
        RENDER_VIEWPORT,
        SERVED_TIMEOUT_MS,
        pages,
        then=leave_samples,
        implementations=artifact.implementations,
        declaration_sources=artifact.declaration_sources,
    )
    assert complete
    failures = [f for f in findings if f.code == "invalid-output"]
    assert len(failures) == 3
    for failure in failures:
        assert failure.values["owner"] == "package"
        assert "/api/samples/" in failure.values["document"]
        assert "$.count" in failure.values["error"]


@pytest.mark.parametrize("value", [{"count": 3}, {"count": "wrong"}])
def test_package_render_checks_every_exercised_output_before_withdrawal(
    tmp_path, browser, value
):
    package = tmp_path / "output-package"
    output_package(package, value)
    failures = [
        f for f in widget_findings(browser.unwatched, package) if f.severity == "error"
    ]
    if isinstance(value["count"], int):
        assert failures == []
    else:
        assert failures
        assert all(f.code == "invalid-output" for f in failures)
        failure = failures[0]
        assert failure.at == "<lf-output-proof id=proof>"
        assert failure.values["owner"] == "package"
        assert failure.values["output"] == "count"
        assert failure.values["contract"] == "count"
        assert "$.count" in failure.values["error"]
        assert "<lf-output-proof id=proof> (package producer)" in str(failure)
