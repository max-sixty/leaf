"""Whether a revision runs what only a browser can judge (`needs_browser`), read from
its document and captured artifact alone.

A page can carry code of its own: module scripts, and page widgets below `/page/`,
with whatever each imports. It can also place a widget whose module reads content the
static check only proves exists: a body of data (`content: data`), such as a chart's
Plot expression, a diagram's Mermaid source or a diff, in a notation only the widget's
module reads, or page media an attribute names, such as a screenshot pair whose two
widths have to match. No static reading can say whether that code throws or whether
the module can read that content, and a quick page never reaches `--render`. Without a
browser run, a module that breaks on its first paint, or a chart whose body fails,
would pass the check and reach the user, and its author would hear about it only from
the watcher's `error` event. So plain `page check` runs in a browser each revision
that carries any of these (`pages/render_gate/page_code.py`), and a thread message's
markup is run the same way before it posts wherever it places such a widget
(`places_judged_widget`).

This module imports nothing of the browser run, so a check whose page needs no
browser loads none of it."""

from leaf.base.schema import MEDIA_DIR
from leaf.source.registry.contract import body_is_data
from leaf.source.revision_artifact import RevisionArtifact
from leaf.source.structure import SourceDocument, script_kind


def needs_browser(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether this revision runs what only a browser can judge: a script, or a
    placed widget whose module reads what no static check has, a page widget's own
    code, a data widget's body in a notation only its module parses, or the page
    media its attributes name. A module a script imports is reached through that
    script, and a widget the document never places never loads."""
    scripts = [
        *document.authoring.inline_scripts,
        *document.authoring.external_scripts,
    ]
    if any(script_kind(script["attrs"]) in {"module", "classic"} for script in scripts):
        return True
    return places_judged_widget(document, artifact)


def places_judged_widget(document: SourceDocument, artifact: RevisionArtifact) -> bool:
    """Whether the document places a widget whose module reads what no static check
    has: a page widget's own code, a data widget's body, or the page media its
    attributes name. A widget the document never places never loads."""
    registry = artifact.registry
    implementations = artifact.implementations
    return any(
        implementations[record["tag"]]["owner"] == "page"
        or body_is_data(registry[record["tag"]])
        or any(
            isinstance(value, str) and value.startswith(f"/{MEDIA_DIR}/")
            for value in record["attrs"].values()
        )
        for record in document.lf_elements
        if record["tag"] in implementations
    )
