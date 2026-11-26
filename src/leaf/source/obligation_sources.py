"""The widgets a document declares that can ask the user, read from its markup and
vocabulary alone.

A widget asks by declaring `awaits` (`local_obligation_entry`), unless it stands in an
exhibit, where it is shown rather than asked (`structure.shown_in`). Its prompt is the
name of the group the author declares round it, or else its own (`widget_groups`). Every
reading of a document's obligations against the log starts from its asking widgets and
their prompts (`ObligationSources`, `obligations.page_obligation_readings`), and a
revision's history keeps a compact registration of each (`ObligationRegistration`).
Nothing here reads the log."""

from typing import NamedTuple

from leaf.source.passages import element_name
from leaf.source.registry.contract import matches_when
from leaf.source.structure import shown_in


def local_obligation_entry(entry: dict) -> bool:
    """Whether a widget can originate an obligation when its predicate holds."""
    return entry.get("awaits") is not None


def group_tags(registry: dict) -> list[str]:
    """The tags the vocabulary declares a named group (`reading-role: group`), such as
    the default package's `lf-group`."""
    return sorted(
        tag
        for tag, entry in registry.items()
        if isinstance(entry, dict) and entry.get("reading-role") == "group"
    )


def widget_groups(content: list, registry: dict):
    """Each widget in `content` that can ask, as its authoring node and its question:
    the innermost named group round it (`group_tags`), or None. The group's `label`
    (`passages.element_name`) is the widget's prompt, and the group is where the
    obligation stands and going to it starts while it holds no other
    (`records/obligations/place.js` in the browser); the registry requires both its id and its
    label. Python reads only the authored source, so a group the runtime draws holds no
    question. A widget set among words (`inline`), such as a suggestion, has none: its
    sentence and its own words name it.

    The author declares the question's region and name on an element of Leaf's own,
    and Leaf reads no heading and no ARIA to find them: the user chose one Leaf element
    whose `label` names any group of things, questions among them, over HTML's group
    named by `aria-labelledby` or a fieldset's legend, which gave a question several
    ways to be written and leaned on accessibility attributes for one of Leaf's own
    facts. Finding the section a heading opens round the widget is the alternative a
    later change might reach for; it fails because it infers a region the author never
    marked, so a section of prose round several questions would become their region."""
    groups = set(group_tags(registry))

    def walk(nodes: list, group: dict | None):
        for node in nodes:
            if isinstance(node, str):
                continue
            entry = registry.get(node["tag"]) or {}
            if local_obligation_entry(entry):
                yield node, None if entry.get("inline") else group
            yield from walk(node["content"], node if node["tag"] in groups else group)

    yield from walk(content, None)


class ObligationSources(NamedTuple):
    """The widgets one document declares that can ask the user, read under one
    vocabulary.

    `asking` holds each declared widget, with whether it stands inside an exhibit
    (`structure.shown_in`).
    `prompts` maps each one's id to its prompt: `text`, the words naming it, its group's
    name (`widget_groups`) or else its own, and `target`, the id of the element going
    to it starts at, its group or else itself.

    These depend on the document and the vocabulary alone, and finding them is most
    of the cost of reading a page's obligations. A stored revision's reading
    therefore holds them across requests (`reading.SourceReading`), and each reading
    against the log, such as admission's before and after an event, reads only what
    the log decides."""

    asking: tuple[tuple[dict, bool], ...]
    prompts: dict[str, dict]


def obligation_sources(source, registry: dict) -> ObligationSources:
    """Read `ObligationSources` from a page document or a thread structure,
    whose fragments each hold one message's markup."""
    documents = (
        list(source.fragments.values()) if hasattr(source, "fragments") else [source]
    )

    declared = [
        record
        for document in documents
        for record in document.lf_elements
        if local_obligation_entry(registry.get(record["tag"]) or {})
    ]
    prompts = {}
    for document in documents:
        for node, group in widget_groups(document.authoring.content, registry):
            if not (identity := node["attrs"].get("id")):
                continue
            prompts[identity] = {
                "text": element_name(group or node, registry),
                "target": (group["attrs"].get("id") if group else None) or identity,
            }
    return ObligationSources(
        tuple((record, shown_in(record, registry)) for record in declared), prompts
    )


class ObligationRegistration(NamedTuple):
    """Compact registration inputs: no parser records or holder chains survive here.
    Whether a widget whose `triggers` were written asked in its revision is the log
    fold's to read (`obligations.previously_requested`)."""

    tag: str
    asking: bool
    restated: bool
    triggers: frozenset[str]


def obligation_registrations(
    document, registry: dict
) -> dict[str, ObligationRegistration]:
    """Compact immutable registration inputs, separate from a revision's parse. A
    widget an exhibit shows (`structure.shown_in`) registers as one that neither asks
    nor is asked by a write, as the current version's fold reads it: it asked nothing
    there, and a write to it there was a demonstration."""
    registrations = {}
    for unit, record in document.by_id.items():
        declaration = registry.get(record["tag"], {}).get("awaits")
        if declaration is None:
            continue
        eligible = not shown_in(record, registry)
        registrations[unit] = ObligationRegistration(
            record["tag"],
            eligible and matches_when(record["attrs"], declaration.get("when")),
            "restated" in record["attrs"],
            frozenset(
                verb
                for verb, spec in registry[record["tag"]].get("verbs", {}).items()
                if eligible
                and (spec.get("record") or {}).get("kind") == "value"
                and spec["record"]["attr"] in declaration.get("when", {})
            ),
        )
    return registrations
