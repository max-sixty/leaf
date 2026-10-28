"""An attributed inventory of a page, without a quality score or a validation gate.

Source facts come from the same parsed document and captured resource graph as
delivery. CSS bytes are UTF-8 CSS text (HTML-decoded for style attributes); rules
count qualified and at-rules, including nested rules, and declarations include
custom properties. Files count
once, even when several documents or widgets use them. Inline CSS belongs to its
document, with sample children named separately. Selected-layer CSS stays separate
from page CSS. Page-owned widget implementations are listed from captured
provenance. JavaScript bytes include executable inline scripts and captured files,
including downloads; no byte count implies execution. JavaScript is not parsed for
strings that might become CSS.

This is a static source inventory, not network transfer or CSS coverage. Styles made
by JavaScript, including widget template strings, are outside it. Browser views
retain their own revision, viewport and freshness; only a matching artifact digest
lets one describe the inspected source. Inspection never activates the candidate,
opens a browser, alters a disclosure, or makes a measurement a pass/fail verdict.
Revision comparisons name changed captured sources and metric deltas. The revision
directories retain the files for an author who needs their full text diff.
"""

import json
from pathlib import Path

from .files import latest_revision, list_revisions
from .leases import page_locked
from .refusals import Refused
from .registry.storage import read_page_registry, selected
from .revision_artifact import (
    Resource,
    RevisionArtifact,
    capture_artifact,
    css_dependencies,
    css_syntax_errors,
    read_artifact,
    read_revision,
    resolve_dependency,
    resource_dependencies,
)
from .runtime_selection import executing
from .structure import SourceDocument, links_with_rel, script_kind
from .styles import css_block, css_stylesheet
from .user_views import read_user_views


def _css_counts(css: str, *, inline=False) -> dict:
    counts = {
        "bytes": len(css.encode("utf-8")),
        "rules": 0,
        "declarations": 0,
        "inline_styles": int(inline),
        "important": 0,
    }

    def walk(nodes):
        for node in nodes:
            if node.type == "declaration":
                counts["declarations"] += 1
                counts["important"] += int(node.important)
            elif node.type in {"qualified-rule", "at-rule"}:
                counts["rules"] += 1
                if node.content is not None:
                    walk(css_block(node.content))

    walk(css_block(css) if inline else css_stylesheet(css))
    return counts


def inspect_artifact(artifact: RevisionArtifact, revision: int | None) -> dict:
    """Read static source facts for the exact artifact a caller names."""
    document = SourceDocument(artifact.html.decode("utf-8"))
    sources = []
    scripts = []
    references = {}
    # The layer the revision selects is the serving Leaf's, not captured, but its
    # files are what the page runs beside its own.
    running = executing(artifact).resources
    resources = {
        **{
            path: running[path]
            for path in selected(
                json.loads(artifact.manifest)["layer"], artifact.page_dir
            ).files
        },
        **artifact.resources,
    }

    def add_source(css, path, line, kind, owner, documents):
        sources.append(
            {
                "path": path,
                "line": line,
                "kind": kind,
                "owner": owner,
                "documents": documents,
                **_css_counts(css, inline=kind == "inline"),
                "syntax_errors": [
                    finding.json()
                    for finding in css_syntax_errors(
                        css, f"{path}:{line}", kind == "inline"
                    )
                ],
            }
        )

    def refer(path, *, document):
        pending = [path]
        visited = set()
        while pending:
            target = pending.pop()
            if target in visited or target not in resources:
                continue
            visited.add(target)
            resource = resources[target]
            if resource.mime != "text/css":
                continue
            references.setdefault(target, set()).add(document)
            pending.extend(resource_dependencies(target, resource.data, resource.mime))

    documents = [("index.html", document)]
    for name, authored in documents:
        documents.extend(
            (f"{name}#{sample['attrs']['id']}", sample["document"])
            for sample in authored.samples
        )
        authoring = authored.authoring
        for script in authoring.inline_scripts:
            if script_kind(script["attrs"]) not in {"module", "classic"}:
                continue
            body = script["body"].encode("utf-8")
            scripts.append(
                {
                    "path": "index.html",
                    "line": script["line"],
                    "kind": "script",
                    "owner": "page",
                    "documents": [name],
                    "bytes": len(body),
                }
            )
        for sheet in authoring.style_blocks:
            add_source(
                sheet["css"], "index.html", sheet["line"], "style", "page", [name]
            )
            for specifier in css_dependencies(sheet["css"], "/index.html"):
                refer(resolve_dependency(specifier, "/index.html"), document=name)
        for inline in authoring.inline_styles:
            add_source(
                inline["style"], "index.html", inline["line"], "inline", "page", [name]
            )
            for specifier in css_dependencies(
                inline["style"], "/index.html", declarations=True
            ):
                refer(resolve_dependency(specifier, "/index.html"), document=name)
        for link in links_with_rel(authoring.links, "stylesheet"):
            refer(
                resolve_dependency(link["attrs"].get("href", ""), "/index.html"),
                document=name,
            )

    page_widgets = []
    for tag, implementation in artifact.implementations.items():
        if implementation["owner"] == "page":
            page_widgets.append(
                {"tag": tag, "path": implementation["path"].lstrip("/")}
            )

    for path, resource in sorted(resources.items()):
        owner = "page" if path.startswith("/page/") else "layer"
        if resource.mime == "application/javascript":
            scripts.append(
                {
                    "path": path.lstrip("/"),
                    "line": 1,
                    "kind": "file",
                    "owner": owner,
                    "bytes": len(resource.data),
                }
            )
        if resource.mime != "text/css":
            continue
        add_source(
            resource.data.decode("utf-8"),
            path.lstrip("/"),
            1,
            "stylesheet",
            owner,
            sorted(references.get(path, ())),
        )

    def total(owner):
        return {
            key: sum(source[key] for source in sources if source["owner"] == owner)
            for key in _css_counts("")
        }

    def script_total(owner):
        owned = [script for script in scripts if script["owner"] == owner]
        return {
            "bytes": sum(script["bytes"] for script in owned),
            "inline_scripts": sum(script["kind"] == "script" for script in owned),
            "files": sum(script["kind"] == "file" for script in owned),
        }

    return {
        "basis": {
            "revision": revision,
            "source_digest": document.digest,
            "artifact_digest": artifact.digest,
        },
        "css": {
            "page": total("page"),
            "layer": total("layer"),
            "sources": sources,
            "coverage": [
                "Static authored CSS and captured stylesheet files; each file counts once.",
                "JavaScript-generated styles and remote stylesheets are not counted.",
                "Layer totals describe the selected layer's stylesheet files, not bytes loaded by this view.",
                *(
                    [
                        "CSS syntax errors are listed with their sources; counts include only parsed rules and declarations."
                    ]
                    if any(source["syntax_errors"] for source in sources)
                    else []
                ),
            ],
        },
        "page_widgets": page_widgets,
        "javascript": {
            "page": script_total("page"),
            "layer": script_total("layer"),
            "sources": scripts,
            "coverage": [
                "Executable inline scripts and captured JavaScript files; each file counts once.",
                "These are source bytes, not transferred or executed bytes. The serving runtime and remote modules are not counted.",
                "JavaScript is not searched for strings that may become CSS.",
            ],
        },
    }


def inspection_views(page_dir: Path, artifact_digest: str) -> dict:
    """Retained browser readings with exact source matching, independent of recency."""
    views = read_user_views(page_dir, latest_revision(page_dir))
    revisions = set(list_revisions(page_dir))

    def matches(revision):
        return (
            revision in revisions
            and read_revision(page_dir, revision).digest == artifact_digest
        )

    for view in views["sessions"]:
        view["matches_source"] = matches(view["revision"])
        if view["checks"] is not None:
            view["checks"]["matches_source"] = matches(view["checks"]["revision"])
    return views


def compare_artifacts(before: RevisionArtifact, after: RevisionArtifact) -> list[dict]:
    """Changed captured sources and their byte counts and digests.

    This compares source inputs only. Browser geometry has an independent runtime,
    event position and interaction state and is deliberately not subtracted here.
    """

    def files(artifact):
        return {
            "/index.html": Resource(artifact.html, "text/html"),
            **artifact.resources,
        }

    old, new = files(before), files(after)
    changes = []
    for path in sorted(old.keys() | new.keys()):
        left, right = old.get(path), new.get(path)
        if left and right and left.digest == right.digest:
            continue
        change = {
            "path": path.lstrip("/"),
            "status": "added"
            if left is None
            else "removed"
            if right is None
            else "changed",
            "before": {"bytes": len(left.data), "digest": left.digest}
            if left
            else None,
            "after": {"bytes": len(right.data), "digest": right.digest}
            if right
            else None,
        }
        changes.append(change)
    return changes


def cmd_inspect(
    page_dir: Path, revision: int | None = None, compare_to: int | None = None
) -> dict:
    """Inspect mutable candidate inputs, or an explicitly named captured revision."""
    with page_locked(page_dir):
        if revision is not None:
            if revision not in list_revisions(page_dir):
                raise Refused(f"unknown revision r{revision}")
            artifact = read_artifact(page_dir, revision)
        else:
            document = SourceDocument(
                (page_dir / "index.html").read_bytes().decode("utf-8")
            )
            vocabulary = read_page_registry(page_dir)
            if vocabulary is None:
                raise Refused("page has no layer; run `leaf page init` first")
            artifact = capture_artifact(
                page_dir,
                document,
                vocabulary.registry,
                declaration_sources=vocabulary.declaration_sources,
                widget_sources=vocabulary.widget_sources,
            )
        report = inspect_artifact(artifact, revision)
        report["views"] = inspection_views(page_dir, artifact.digest)
        if compare_to is not None:
            if compare_to not in list_revisions(page_dir):
                raise Refused(f"unknown revision r{compare_to}")
            previous = read_artifact(page_dir, compare_to)
            baseline = inspect_artifact(previous, compare_to)
            changes = compare_artifacts(previous, artifact)
            for change in changes:
                old_css = [
                    source
                    for source in baseline["css"]["sources"]
                    if source["path"] == change["path"]
                ]
                new_css = [
                    source
                    for source in report["css"]["sources"]
                    if source["path"] == change["path"]
                ]
                if old_css or new_css:
                    change["css_delta"] = {
                        key: sum(source[key] for source in new_css)
                        - sum(source[key] for source in old_css)
                        for key in _css_counts("")
                    }
            report["comparison"] = {
                "basis": baseline["basis"],
                "sources": changes,
                "css": {
                    owner: {
                        key: value - baseline["css"][owner][key]
                        for key, value in report["css"][owner].items()
                    }
                    for owner in ("page", "layer")
                },
                "javascript": {
                    owner: {
                        key: value - baseline["javascript"][owner][key]
                        for key, value in report["javascript"][owner].items()
                    }
                    for owner in ("page", "layer")
                },
                "coverage": "Source changes only. Browser observations are not subtracted across rendering environments or interaction states.",
            }
        return report
