"""Compose the parts of the product documents that other sources own.

Every page under `docs/` is a Leaf source, authored for what only it decides: its
prose, which examples the catalog shows and under which headings, and where each part
below sits. A part whose facts another source owns is authored as an empty slot, and
every builder of a product document, the site build and a local preview alike, fills
it here from that owner as it reads the source (`page_fixtures.authored_markup`):

- `nav.sitenav`: the site's routes (`SITE_NAV`), the page's own marked current;
- an `<img>` inside a link to `/examples/<name>/`: that example's
  catalog preview, at the address `leaf page media` gives the bytes of the asset tree
  the build reads, the pinned one unless a draft's is handed in;
- `.example-description` inside a catalog link (`a.example-link`): the example's
  `<meta name="description">`;
- `table#all-verbs`'s body: every `x-state` verb the kernel and the bundled packages
  declare, in registry order;
- `nav.reference-index` and `div.reference-list`: the core layer's `$keys`
  (`browser/registry.json`);
- `div.schema-list`: each declared schema in the group its `data-schemas` names
  (`SCHEMA_LISTS`), as a table of its fields.

A slot that already holds content is refused, since a copy there would go stale
silently. The edits splice into the authored source at the parser's own spans, so every
byte outside a slot is published as written.
"""

import html
import json
import re
from pathlib import Path

from leaf.media import media_name
from leaf.schema import MEDIA_DIR
from leaf.state import KERNEL_REGISTRY
from leaf.structure import SourceDocument
from leaf_dev import ROOT, declared_records
from leaf_dev.example_data import document_metadata
from leaf_dev.leaf_assets import pinned_assets

DOCS = ROOT / "docs"
EXAMPLES = ROOT / "examples"
ASSETS = ROOT / "browser"
PACKAGES = ROOT / "packages"
SCRIPTS = ROOT / "src" / "leaf"
SERVED_SCHEMA = SCRIPTS / "served_state" / "state.schema.json"
INTERACTION_SCHEMA = SCRIPTS / "interaction-batch.schema.json"
# Where each event kind's meaning is written: its row of the kinds table that opens
# the file, at the anchor `kind-<kind>`.
EVENTS_REFERENCE = "https://github.com/max-sixty/leaf/blob/main/src/leaf/events.md"

# The site's route bar, the brand first.
SITE_NAV = (
    ("/", "leaf"),
    ("/examples/", "Examples"),
    ("/how-it-works/", "How it works"),
    ("/ui/", "UI"),
    ("/extending/", "Extending"),
    ("https://github.com/max-sixty/leaf", "GitHub"),
)
# A $keys entry longer than its first sentence by this many words keeps the rest
# behind a disclosure.
COLLAPSED_DETAIL_WORDS = 30


def product_sources() -> list[Path]:
    """The top-level product documents, each published at its filename's route."""
    return sorted(DOCS.glob("*.html"))


def product_route(source: Path) -> str:
    """The site's index is `/`; every other document uses `/<stem>/`."""
    return "/" if source.stem == "index" else f"/{source.stem}/"


def media_url(source: Path) -> str:
    """The page path an image takes once `leaf page media` has stored it."""
    return f"/{MEDIA_DIR}/{media_name(source.read_bytes(), source.suffix)}"


def catalog_preview(assets: Path, name: str) -> Path:
    """Where an asset tree holds one example's catalog preview
    (`leaf_dev.commands.refresh_previews`)."""
    return assets / "examples" / f"example-{name}.jpg"


def example_name(link) -> str | None:
    """The example a link opens, or None for any other destination."""
    found = re.fullmatch(r"/examples/([^/]+)/", link.attrs.get("href", ""))
    return found.group(1) if found else None


def site_nav(current: str) -> list[str]:
    links = []
    for index, (href, label) in enumerate(SITE_NAV):
        attrs = ' class="brand"' if index == 0 else ""
        attrs += f' href="{href}"'
        if href == current:
            attrs += ' aria-current="page"'
        links.append(f"<a{attrs}>{label}</a>")
    return links


def markup_record(verb_state: dict) -> str:
    """What a verb's current state reads as in markup."""
    if "creates" in verb_state:
        return f"creates an <code>{verb_state['creates']['child']}</code>"
    shape = verb_state.get("record")
    if shape is None:
        return "none"
    if shape["kind"] == "position":
        return f"position in an <code>{shape['within']}</code>"
    if shape["kind"] == "body":
        return "body"
    written = ", written by the agent" if verb_state.get("writer") == "agent" else ""
    return f"<code>{shape['attr']}</code> attribute{written}"


def registries() -> list[Path]:
    """The core layer's registry, then each bundled package's."""
    return [ASSETS / "registry.json", *sorted(PACKAGES.glob("*/registry.json"))]


def verb_rows() -> list[str]:
    rows = []
    for path in registries():
        for tag, element in json.loads(path.read_text(encoding="utf-8")).items():
            if not tag.startswith("lf-"):
                continue
            for verb, verb_state in element.get("x-state", {}).items():
                cells = (
                    f"<code>{tag}</code>",
                    f"<code>{verb}</code>",
                    verb_state["unit"],
                    markup_record(verb_state),
                )
                rows.append(
                    "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"
                )
    return rows


def registry_keys() -> dict[str, str]:
    keys = json.loads((ASSETS / "registry.json").read_text(encoding="utf-8"))["$keys"]
    return {key: keys[key] for key in sorted(keys) if key != "description"}


def key_prose(text: str) -> str:
    """A $keys paragraph as HTML: escaped, with `code` spans marked up."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text, quote=False))


def key_summary(text: str) -> tuple[str, str]:
    """The visible summary and any substantial detail to disclose."""
    first, separator, detail = text.partition(". ")
    if not separator or len(detail.split()) < COLLAPSED_DETAIL_WORDS:
        return text, ""
    return first + ".", detail


def key_index() -> list[str]:
    return [f'<a href="#{key}"><code>{key}</code></a>' for key in registry_keys()]


def key_entries() -> list[str]:
    entries = []
    for key, text in registry_keys().items():
        lead, detail = key_summary(text)
        contract = ""
        if detail:
            contract = (
                '<details class="reference-more">'
                f'<summary aria-label="Full {key} contract">Full contract</summary>'
                f"<p>{key_prose(detail)}</p>"
                "</details>"
            )
        entries.append(
            f'<section class="reference-entry" id="{key}">'
            f"<h3><code>{key}</code></h3>"
            f'<div class="reference-copy"><p>{key_prose(lead)}</p>{contract}</div>'
            "</section>"
        )
    return entries


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_reference(ref: str) -> str:
    """A `$ref` as a link to the entry that declares its target: a served-state
    definition, an event kind, or the registry's `x-state`."""
    uri, _, pointer = ref.partition("#")
    if not uri:
        name = pointer.removeprefix("/$defs/")
        return f'<a href="#served-{name or "state"}">{name or "served state"}</a>'
    if uri == "leaf:verb":
        return '<a href="/registry/#x-state">x-state verb</a>'
    if uri == "leaf:event":
        return '<a href="#events">event</a>'
    kind = uri.removeprefix("leaf:event/")
    field = pointer.removeprefix("/properties/")
    named = (
        f"<code>{kind}</code>'s <code>{field}</code>"
        if field
        else f"<code>{kind}</code>"
    )
    return f'<a href="#event-{kind}">{named}</a>'


def type_label(schema) -> str:
    """What one schema admits, in a few words."""
    if schema is True or schema == {}:
        return "any"
    if schema is False:
        return "nothing"
    if "$ref" in schema:
        return schema_reference(schema["$ref"])
    if "const" in schema:
        return f"<code>{html.escape(json.dumps(schema['const']))}</code>"
    if "enum" in schema:
        return " | ".join(
            f"<code>{html.escape(json.dumps(value))}</code>" for value in schema["enum"]
        )
    union = schema.get("anyOf") or schema.get("oneOf")
    if union and "type" not in schema:
        return " or ".join(dict.fromkeys(type_label(branch) for branch in union))
    kinds = schema.get("type", "object" if "properties" in schema else "any")
    return " or ".join(
        kind_label(schema, kind)
        for kind in ([kinds] if isinstance(kinds, str) else kinds)
    )


def kind_label(schema: dict, kind: str) -> str:
    """One JSON type `schema` admits, with what its arrays and maps hold."""
    values = schema.get("additionalProperties")
    if kind == "array" and "prefixItems" in schema:
        return "[" + ", ".join(map(type_label, schema["prefixItems"])) + "]"
    if kind == "array":
        return f"array of {type_label(schema.get('items', True))}"
    if kind == "object" and isinstance(values, dict) and not schema.get("properties"):
        return f"map of {type_label(values)}"
    if kind == "string" and "format" in schema:
        return f"string ({schema['format']})"
    return kind


def variant_label(branch: dict) -> str:
    """What picks one branch of a union: the constants its fields hold."""
    held = [
        f"<code>{name}</code> is {type_label(field)}"
        for name, field in branch.get("properties", {}).items()
        if isinstance(field, dict) and ("const" in field or "enum" in field)
    ]
    return " and ".join(held)


def field_rows(schema, path: str = "", skip: frozenset = frozenset()) -> list[tuple]:
    """A row `(path, type, required, description)` for each field `schema` declares,
    at any depth. A branch of a union or conditional clause that declares fields of
    its own adds a one-cell row introducing them; one that only requires fields
    declared beside it adds a row saying which."""
    if not isinstance(schema, dict):
        return []
    rows = []
    required = set(schema.get("required", ()))
    for name, field in schema.get("properties", {}).items():
        if name in skip:
            continue
        at = f"{path}.{name}" if path else name
        description = field.get("description", "") if isinstance(field, dict) else ""
        rows.append((at, type_label(field), name in required, description))
        rows.extend(field_rows(field, at))
    if isinstance(values := schema.get("additionalProperties"), dict):
        rows.extend(field_rows(values, f"{path}.*" if path else "*"))
    if isinstance(items := schema.get("items"), dict):
        rows.extend(field_rows(items, f"{path}[]"))
    where = f"<code>{path}</code> " if path else ""
    declared = {row[0] for row in rows}
    # Each clause and the condition it holds under: a union's branch is picked by
    # the constants it holds, a conditional by its `if`, and an `allOf` conjunct
    # always holds.
    clauses = [
        (branch, when(variant_label(branch)), True)
        for branch in [*schema.get("anyOf", []), *schema.get("oneOf", [])]
    ]
    conditionals = [schema, *schema.get("allOf", [])]
    for clause in conditionals:
        if "if" in clause:
            condition = when(variant_label(clause["if"]))
            clauses.append((clause.get("then", {}), condition, False))
            if "else" in clause:
                clauses.append((clause["else"], "otherwise", False))
        elif clause is not schema:
            clauses.append((clause, "", False))
    # Each clause's own fields, less those it restates from beside it.
    adding = [
        [row for row in field_rows(branch, path) if row[0] not in declared]
        for branch, _, _ in clauses
    ]
    alternatives = []
    for index, ((branch, condition, alternative), nested) in enumerate(
        zip(clauses, adding, strict=True), 1
    ):
        if nested:
            label = condition or f"variant {index}"
            description = key_prose(branch.get("description", ""))
            # A union with one branch of fields, such as an object or null, needs no
            # row telling its branches apart.
            if condition or description or sum(map(bool, adding)) > 1:
                rows.append((f"{where}{label}. {description}".strip(),))
            rows.extend(nested)
        elif rule := requirement(branch):
            if condition:
                rows.append((f"{where}{condition}, {rule}.",))
            elif alternative:
                alternatives.append(rule)
            else:
                rows.append((f"{where}{rule}.",))
    if alternatives:
        rows.append((f"{where}one of: {'; '.join(alternatives)}.",))
    return rows


def when(label: str) -> str:
    return f"when {label}" if label else ""


def code_list(names) -> str:
    return ", ".join(f"<code>{name}</code>" for name in names)


def requirement(clause) -> str:
    """The fields a clause requires and forbids, in words."""
    if not isinstance(clause, dict):
        return ""
    parts = []
    if clause.get("required"):
        parts.append(f"requires {code_list(clause['required'])}")
    excluded = clause.get("not", {})
    forbidden = [
        group["required"][0]
        for group in [excluded, *excluded.get("anyOf", [])]
        if len(group.get("required", ())) == 1
    ]
    if forbidden:
        parts.append(f"forbids {code_list(forbidden)}")
    return " and ".join(parts)


def table_row(row: tuple) -> str:
    if len(row) == 1:
        return f'<tr class="schema-variant"><td colspan="4">{row[0]}</td></tr>'
    path, label, required, description = row
    # A break opportunity after each dot, so a long path wraps between its fields.
    shown = path.replace(".", ".<wbr>")
    cells = (
        f"<code>{shown}</code>",
        label,
        "yes" if required else "",
        key_prose(description),
    )
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def schema_entry(
    entry_id: str,
    heading: str,
    schema: dict,
    notes: list[str] | tuple[str, ...] = (),
    *,
    skip: frozenset = frozenset(),
) -> str:
    """One declared schema: its heading, what it is, and a table of its fields."""
    parts = [f"<h3>{heading}</h3>"]
    if text := schema.get("description"):
        parts.append(f"<p>{key_prose(text)}</p>")
    label = type_label(schema)
    if label != "object":
        notes = [f"Type: {label}.", *notes]
    if notes:
        parts.append(f'<p class="schema-notes">{" ".join(notes)}</p>')
    rows = field_rows(schema, skip=skip)
    if rows:
        parts.append(
            '<table class="schema-fields"><thead><tr><th>Field</th><th>Type</th>'
            "<th>Required</th><th>Description</th></tr></thead>"
            f"<tbody>{''.join(map(table_row, rows))}</tbody></table>"
        )
    return f'<section class="schema-entry" id="{entry_id}">{"".join(parts)}</section>'


def served_entries() -> list[str]:
    """The state `GET /api/state` serves, then each definition it names, POST answers
    included."""
    schema = read_json(SERVED_SCHEMA)
    definitions = schema.pop("$defs")
    schema.pop("$schema", None)
    return [
        schema_entry("served-state", "<code>GET /api/state</code>", schema),
        *(
            schema_entry(f"served-{name}", f"<code>{name}</code>", definition)
            for name, definition in definitions.items()
        ),
    ]


def event_entries() -> list[str]:
    """The fields every event record shares, then each kind's own, with the meaning
    left to `events.md`."""
    kinds = read_json(KERNEL_REGISTRY)["$events"]["kinds"]
    records = [contract["record"] for contract in kinds.values()]
    shared = tuple(
        name
        for name, field in records[0]["properties"].items()
        if all(
            record["properties"].get(name) == field
            and (name in record["required"]) == (name in records[0]["required"])
            for record in records
        )
    )
    envelope = {
        "type": "object",
        "properties": {name: records[0]["properties"][name] for name in shared},
        "required": [name for name in records[0]["required"] if name in shared],
    }
    entries = [schema_entry("event-envelope", "Every event", envelope)]
    for kind, contract in kinds.items():
        notes = [f'<a href="{EVENTS_REFERENCE}#kind-{kind}">What it means</a>.']
        if "browser" in contract:
            notes.append("The browser may post it to <code>POST /api/event</code>.")
        for member in ("message", "bookkeeping", "undoable"):
            if contract.get(member):
                notes.append(f"A <code>{member}</code> kind.")
        if writer := contract.get("verb_writer"):
            notes.append(f"Carries an x-state verb the {writer} writes.")
        entries.append(
            schema_entry(
                f"event-{kind}",
                f"<code>{kind}</code>",
                contract["record"],
                notes,
                skip=frozenset(shared),
            )
        )
    return entries


def record_entries() -> list[str]:
    """Each record Leaf keeps outside a page's log and document, the composer's draft
    among them, with the `format` it is stored at."""
    draft = read_json(KERNEL_REGISTRY)["$events"]["draft"]
    records = {
        kind: (record.since, record.schema)
        for kind, record in declared_records().items()
    } | {
        "draft": (
            draft["since"],
            {"description": draft["description"], **draft["schema"]},
        )
    }
    return [
        schema_entry(
            f"record-{kind}",
            f"<code>{kind}</code>",
            schema,
            [f"Stored with <code>format</code> <code>leaf-{kind}/{since}</code>."],
        )
        for kind, (since, schema) in sorted(records.items())
    ]


def interaction_entries() -> list[str]:
    return [
        schema_entry(
            "interaction-batch",
            "<code>POST /api/interaction</code>",
            read_json(INTERACTION_SCHEMA),
        )
    ]


SCHEMA_LISTS = {
    "served": served_entries,
    "events": event_entries,
    "records": record_entries,
    "interactions": interaction_entries,
}


def inputs(source: Path) -> list[Path]:
    """The files `compose` reads for one product document, besides the asset pin, so a
    preview follows an edit to an owner."""
    tree = SourceDocument(source.read_text(encoding="utf-8")).tree
    examples = [
        EXAMPLES / f"{name}.html"
        for link in tree.select("a.example-link")
        if (name := example_name(link))
    ]
    composed = tree.select("table#all-verbs, nav.reference-index, div.reference-list")
    schemas = tree.select("div.schema-list")
    return [
        *examples,
        *(registries() if composed else []),
        *([SERVED_SCHEMA, INTERACTION_SCHEMA, KERNEL_REGISTRY] if schemas else []),
    ]


def compose(source: Path, markup: str, *, assets: Path | None = None) -> str:
    """Fill the slots of one product document from their owners."""
    document = SourceDocument(markup)
    edits: list[tuple[int, int, str]] = []

    def fill(element, children: list[str] | str) -> None:
        location = element.source_location
        _, start = document.offsets(location.start_tag)
        end, _ = document.offsets(location.end_tag)
        if markup[start:end].strip():
            raise ValueError(
                f"{source.name}:{location.start_tag.start_line}: "
                f"<{element.tag}> is composed from its owner (leaf_dev.docs); "
                "leave it empty"
            )
        if isinstance(children, str):
            edits.append((start, end, children))
            return
        line_start = markup.rfind("\n", 0, start) + 1
        indent = markup[line_start:]
        indent = indent[: len(indent) - len(indent.lstrip(" \t"))]
        inner = "".join(f"\n{indent}  {child}" for child in children)
        edits.append((start, end, f"{inner}\n{indent}"))

    for nav in document.tree.select("nav.sitenav"):
        fill(nav, site_nav(product_route(source)))
    previews = None
    for link in document.tree.select("a[href]"):
        name = example_name(link)
        if name is None:
            continue
        for image in link.select("img"):
            if "src" in image.attrs:
                assert image.source_location is not None
                raise ValueError(
                    f"{source.name}:{image.source_location.start_tag.start_line}: "
                    "an example link's image is its preview, composed from its owner "
                    "(leaf_dev.docs); leave out its src"
                )
            if previews is None:
                previews = assets or pinned_assets()
            assert image.source_location is not None
            at = document.offsets(image.source_location.start_tag)[0] + len("<img")
            address = media_url(catalog_preview(previews, name))
            edits.append((at, at, f' src="{address}"'))
        if link.has_class("example-link"):
            _, description = document_metadata(EXAMPLES / f"{name}.html")
            for caption in link.select(".example-description"):
                fill(caption, html.escape(description, quote=False))
    for body in document.tree.select("table#all-verbs > tbody"):
        fill(body, verb_rows())
    for nav in document.tree.select("nav.reference-index"):
        fill(nav, key_index())
    for listing in document.tree.select("div.reference-list"):
        fill(listing, key_entries())
    for listing in document.tree.select("div.schema-list"):
        name = listing.attrs["data-schemas"]
        assert isinstance(name, str)
        fill(listing, SCHEMA_LISTS[name]())
    for start, end, text in sorted(edits, reverse=True):
        markup = markup[:start] + text + markup[end:]
    return markup
