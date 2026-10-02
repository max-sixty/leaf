"""Registry-declared markup instance validation."""

import re

from leaf.asks import asking, local_ask_entry, quoted_in
from leaf.passages import COLLAPSE_CHARS
from leaf.projection import enclosing_widgets
from leaf.registry.contract import json_validator, registry_path, visual_parts
from leaf.registry.state import retirement_slots
from leaf.structure import AUTHORED_ALLOCATIONS, SourceDocument

from .markup import at, structure_errors


def thread_markup_contract_errors(parser, registry: dict) -> list:
    """Registry-derived errors shared by admission and re-vendoring."""
    errors = fragment_errors(parser, registry)
    settled = retirement_slots(registry)
    errors.extend(
        f"<{rec['tag']}> is a settlement holder, but thread markup is frozen in "
        "the log and no version could ever settle it; put the change in the next "
        "version instead"
        for rec in parser.lf_elements
        if rec["tag"] in settled
    )
    return errors


def widget_errors(lf_elements: list, registry: dict) -> list:
    """Validate parsed lf-* elements against the registry: schema over the
    attribute instance, x-owners nesting, and the x-content model."""
    errors = []
    # Member containers admit exactly the tags that declare them as x-owners.
    members_of = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-"):
            continue
        for owner in entry.get("x-owners", []):
            members_of.setdefault(owner, set()).add(tag)

    for rec in lf_elements:
        tag, where = rec["tag"], at(rec)
        entry = registry.get(tag)
        if entry is None:
            errors.append(
                f"{where}: unknown widget — not in the vendored registry.json"
            )
            continue
        # The element validates as the instance built from its attributes:
        # values as strings, flag attributes as True. HTML's two flag spellings
        # (bare and ="") both mean true; a literal value on a flag stays a string
        # so it fails loudly rather than silently meaning true.
        props = entry.get("properties", {})
        instance = {}
        for name, value in rec["attrs"].items():
            if name in AUTHORED_ALLOCATIONS:
                continue
            prop = props.get(name)
            is_flag = isinstance(prop, dict) and prop.get("type") == "boolean"
            instance[name] = True if value in (None, "") and is_flag else (value or "")
        for err in sorted(json_validator(entry).iter_errors(instance), key=str):
            errors.append(f"{where}: {err.message}")
        if "data-height" in rec["attrs"] and "x-height" not in entry:
            errors.append(
                f"{where}: data-height states the height of a widget that draws into "
                f"its box, and <{tag}> takes the height of what it holds"
            )
        want_owners = entry.get("x-owners", [])
        if want_owners and rec["parent"] not in want_owners:
            actual = f", found <{rec['parent']}>" if rec["parent"] else ""
            wanted = " or ".join(f"<{owner}>" for owner in want_owners)
            errors.append(f"{where}: must be a direct member of {wanted}{actual}")
        # Tags that name this declaration in x-owners are its admissible members under
        # any content model. "data" takes one <pre>, "members" takes element members
        # only, and "empty" takes nothing at all.
        content = entry["x-content"]
        allowed = members_of.get(tag, set())
        stray = sorted({c for c in rec["children"] if c not in allowed})
        if content == "empty" and (rec["children"] or rec["text"]):
            errors.append(f"{where}: takes no content — write <{tag} …></{tag}>")
        elif content == "data":
            others = [c for c in stray if c != "pre"]
            if rec["children"].count("pre") != 1 or others:
                found = ", ".join(f"<{c}>" for c in rec["children"]) or "nothing"
                errors.append(
                    f"{where}: its body is one <pre> holding the text "
                    f"(escape < and >), found {found}"
                )
            if rec["text"]:
                errors.append(
                    f"{where}: text outside its <pre> — the whole body goes inside it"
                )
        elif content == "members":
            if stray:
                errors.append(
                    f"{where}: admits only {sorted(allowed)} members, found {stray}"
                )
            if rec["text"]:
                errors.append(f"{where}: loose text between its members isn't allowed")
        for member_tag, constraint in entry.get("x-required-members", {}).items():
            attribute = constraint["one-each"]
            values = registry[member_tag]["properties"][attribute]["enum"]
            direct = [
                member
                for member in lf_elements
                if member["holder"] is rec
                and member["parent"] == tag
                and member["tag"] == member_tag
            ]
            counts = {
                value: sum(member["attrs"].get(attribute) == value for member in direct)
                for value in values
            }
            missing = [value for value, count in counts.items() if count == 0]
            repeated = [value for value, count in counts.items() if count > 1]
            if missing or repeated:
                errors.append(
                    f"{where}: must contain exactly one direct <{member_tag}> for "
                    f"each `{attribute}` value; missing {missing}, repeated {repeated}"
                )
    return errors


def layout_errors(lf_elements: list, registry: dict) -> list:
    """Validate the direct grammar of registry-declared structural elements: a pane is an
    optional header, exactly one body element, and an optional footer."""
    errors = []
    for rec in lf_elements:
        role = registry.get(rec["tag"], {}).get("x-reading-role")
        if role is None:
            continue
        where = at(rec)
        direct = rec["direct"]
        headers = [i for i, child in enumerate(direct) if child == "header"]
        footers = [i for i, child in enumerate(direct) if child == "footer"]
        if len(headers) > 1 or len(footers) > 1:
            errors.append(
                f"{where}: x-reading-role {role} admits at most one direct <header> "
                "and one direct <footer>"
            )
        if headers and headers[0] != 0:
            errors.append(
                f"{where}: x-reading-role {role} direct <header> must be first"
            )
        if footers and footers[0] != len(direct) - 1:
            errors.append(
                f"{where}: x-reading-role {role} direct <footer> must be last"
            )
        body = [child for child in direct if child not in {"header", "footer"}]
        if len(body) != 1 or body[0] == "#text":
            errors.append(
                f"{where}: x-reading-role {role} must contain exactly one direct body "
                f"element between its header and footer, found {body or 'nothing'}; wrap "
                "several blocks in one <div> or <section>"
            )
    return errors


def visual_part_errors(lf_elements: list, registry: dict) -> list:
    """A visual's authored part tokens each name one stable generated target."""
    errors = []
    for rec in lf_elements:
        parts = visual_parts(rec, registry).tokens
        duplicates = sorted({part for part in parts if parts.count(part) > 1})
        if duplicates:
            errors.append(
                f"{at(rec)}: visual part ids must be unique, repeated {duplicates}"
            )
    return errors


def ask_surface_errors(lf_elements: list, registry: dict) -> list:
    """An x-ask-surface region frames exactly one nested local Ask source.

    One leading direct heading is the question's visible title and the region owns its
    reading and arrival, while the x-awaits widget owns the answer. Requiring
    both a title and one structural source makes that split unambiguous for the browser
    walk and for `page state`.
    Liveness still comes from the source's canonical Ask projection.
    """

    regions = [
        rec for rec in lf_elements if registry.get(rec["tag"], {}).get("x-ask-surface")
    ]
    sources = {id(region): [] for region in regions}
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        declared = local_ask_entry(entry)
        if not declared or quoted_in(rec, registry):
            continue
        holder = rec.get("holder")
        while holder and not registry.get(holder["tag"], {}).get("x-ask-surface"):
            holder = holder.get("holder")
        if holder:
            sources.setdefault(id(holder), []).append(rec)

    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        awaits = entry.get("x-awaits") or {}
        requires_region = awaits.get("region") and asking(
            rec["attrs"], awaits.get("when")
        )
        if not requires_region or quoted_in(rec, registry):
            continue
        holder = rec.get("holder")
        while holder and not registry.get(holder["tag"], {}).get("x-ask-surface"):
            holder = holder.get("holder")
        if not holder:
            errors.append(
                f"{at(rec)}: this declared Ask source must be inside an Ask "
                "with a heading"
            )
    for region in regions:
        headings = [
            child
            for child in region["children"]
            if child in {f"h{n}" for n in range(1, 7)}
        ]
        if len(headings) != 1:
            errors.append(
                f"{at(region)}: an Ask must have exactly one direct heading, "
                f"found {headings or 'none'}"
            )
        elif region["direct"][0] != headings[0]:
            first = (
                "text" if region["direct"][0] == "#text" else f"<{region['direct'][0]}>"
            )
            errors.append(
                f"{at(region)}: an Ask's direct heading must be its first content, "
                f"found {first} first"
            )
        nested = sources[id(region)]
        if len(nested) != 1:
            found = [
                f"<{rec['tag']}#{rec['attrs'].get('id') or '?'}>" for rec in nested
            ]
            errors.append(
                f"{at(region)}: an Ask must frame exactly one declared Ask source, "
                f"found {found or 'none'}"
            )
    return errors


def target_reference_contract_error(
    reference: dict, target_record: dict | None, registry: dict
) -> str | None:
    """Why one resolved target fails a package-declared relation, if it does."""
    via = reference.get("via")
    if via is None:
        return None
    relation = registry_path(registry, via)
    declaration = (
        relation.get(target_record["tag"])
        if isinstance(relation, dict) and target_record is not None
        else None
    )
    predicate = reference["where"]
    if isinstance(declaration, dict) and all(
        declaration.get(key) == value for key, value in predicate.items()
    ):
        return None
    expected = ", ".join(f"{key}={value!r}" for key, value in predicate.items())
    found = (
        ", ".join(f"{key}={declaration.get(key)!r}" for key in predicate)
        if isinstance(declaration, dict)
        else "no declaration"
    )
    actual = (
        f"<{target_record['tag']}> has {found}"
        if target_record is not None
        else "the target is not a registered widget"
    )
    return f"must name a {via} widget where {expected}; {actual}"


def reference_contract_error(
    record: dict, attribute: str, target_record: dict | None, registry: dict
) -> str | None:
    """Why one existing x-refers target fails its declared relation, if it does."""
    reference = registry[record["tag"]]["x-refers"][attribute]
    error = target_reference_contract_error(reference, target_record, registry)
    return (
        f'{at(record)}: {attribute}="{record["attrs"].get(attribute)}" {error}'
        if error
        else None
    )


def reference_errors(lf_elements: list, registry: dict, ids: set, by_id: dict) -> list:
    """An attribute the registry marks as naming another element (x-refers) that names
    nothing this version holds. The user follows it, so a typo is a reference to
    nowhere and the markup around it is perfectly well-formed — visible to them and to
    nobody else. Asked of the version rather than of a fragment: a reply's markup
    carries no page to check against, and one of its widgets pointing at the version
    beside it is exactly right.

    An `owns` reference is narrower, since its referrer fills the target and the
    browser looks for that target in the referrer's own document: each names an
    element of `lf_elements`' own document, and each element there that the
    contract's predicate selects is named by exactly one referrer, as each readings
    seat is filled by one command."""
    errors = []
    own = {rec["attrs"].get("id") for rec in lf_elements}
    owners = {}
    for rec in lf_elements:
        for attr, reference in registry.get(rec["tag"], {}).get("x-refers", {}).items():
            target = rec["attrs"].get(attr)
            if not target:
                continue
            if target not in ids:
                errors.append(
                    f'{at(rec)}: {attr}="{target}" names no element in this version'
                )
            elif error := reference_contract_error(
                rec, attr, by_id.get(target), registry
            ):
                errors.append(error)
            elif reference.get("owns") and target not in own:
                errors.append(
                    f'{at(rec)}: {attr}="{target}" names an element outside its own '
                    "document, which it fills"
                )
            elif reference.get("owns"):
                owners.setdefault((rec["tag"], attr, target), []).append(rec)
    owned = [
        (tag, attr, reference)
        for tag, entry in registry.items()
        if not tag.startswith("$")
        for attr, reference in entry.get("x-refers", {}).items()
        if reference.get("owns")
    ]
    for rec in lf_elements:
        for tag, attr, reference in owned:
            if target_reference_contract_error(reference, rec, registry):
                continue
            target = rec["attrs"].get("id")
            named = owners.get((tag, attr, target), [])
            if not named:
                errors.append(f"{at(rec)}: no <{tag}> names it in `{attr}`")
            if len(named) > 1:
                first = at(named[0], f"id={named[0]['attrs'].get('id')!r}")
                errors.extend(
                    f'{at(extra)}: {attr}="{target}" is already named by {first}; '
                    "only one element may name it"
                    for extra in named[1:]
                )
    return errors


def addressable_instance_errors(lf_elements: list, registry: dict) -> list:
    """Conditional Asks and thread seats need an id when they are live.

    Requiring every instance globally would outlaw inert option groups; checking the
    declared predicate here gives the runtime exactly the addressability it consumes.
    """
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        for role in ("x-awaits", "x-thread-seat"):
            declaration = entry.get(role)
            if (
                declaration is not None
                and asking(rec["attrs"], declaration.get("when"))
                and not rec["attrs"].get("id")
            ):
                errors.append(f"{at(rec)}: a matching {role} instance requires an id")
    return errors


# A word a widget declares that its layer has to know, as three things: the x- key
# naming the attribute that carries it, the layer-wide fact listing the words the layer
# has, and what the layer does with one that is on the list.
#
# One reader for both, because they are one failure — a misspelt language colors nothing
# and a misspelt tone paints nothing, and each renders as a page that otherwise looks
# perfectly well, so nobody downstream can see it: not the user, who never knew the chip
# was meant to be red. The one party who can still fix it is whoever wrote the word, and
# this is where they are told. A class would have been the same words with nobody
# checking them.
#
# The list is the layer's ($languages, $tones) rather than any widget's, and which
# attribute carries the word is the entry's to say — so nothing here knows which widget
# takes a language or a tone, and the thirteenth that colors something is covered the day
# it declares one. A third such word is a row in this table.
DECLARED_WORDS = (
    ("x-language", "$languages", "a language this page's layer speaks"),
    ("x-tone", "$tones", "a tone this page's layer paints"),
)


def declared_word_errors(lf_elements: list, registry: dict) -> list:
    """Every word the page declares that its layer has no entry for (DECLARED_WORDS)."""
    errors = []
    for key, fact, honored in DECLARED_WORDS:
        known = registry[fact]["names"]
        for rec in lf_elements:
            attr = (registry.get(rec["tag"]) or {}).get(key)
            word = rec["attrs"].get(attr) if attr else None
            if word is not None and word not in known:
                named = f'{attr}="{word}"'
                errors.append(f"{at(rec, named)}: not {honored} — known: {known}")
    return errors


LINE_RANGES = re.compile(r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*")


def _spans(value: str):
    for part in value.split(","):
        lo, _, hi = part.partition("-")
        yield part, int(lo), int(hi) if hi else int(lo)


# The whitespace a data body's trim removes: the browser's (JS trimEnd), spelled out
# because Python's own \s and isspace() disagree with it at U+FEFF, U+0085 and
# U+001C–001F, and a body ending in one would count a line more or fewer here than
# lf-code numbers.
_TRAILING = "".join(COLLAPSE_CHARS)


def _body_text(owner: dict) -> str:
    """A data body as its module reads it (`bodyText`, widget-upgrade.js): leading
    blank lines and trailing whitespace are the <pre>'s layout, not lines."""
    return owner.get("body", "").lstrip("\n").rstrip(_TRAILING)


def _body_lines(owner: dict) -> int:
    return _body_text(owner).count("\n") + 1


def _numbering(
    owner: dict, registry: dict
) -> tuple[str | None, list[tuple[int, int]] | None]:
    """The x-numbering attribute's reading on a data body's owner, and the ranges of
    numbers its lines carry: 1..N without one, None when its value is unreadable (the
    schema's error to report). Ranges rather than the numbers they hold, since an
    authored range can be as long as its digits allow."""
    attr = (registry.get(owner.get("tag")) or {}).get("x-numbering")
    value = owner.get("attrs", {}).get(attr) if attr else None
    if value is None:
        return None, [(1, _body_lines(owner))]
    if not LINE_RANGES.fullmatch(value):
        return value, None
    return value, [(lo, hi) for _, lo, hi in _spans(value)]


def line_ref_errors(lf_elements: list, registry: dict) -> list:
    """A body's x-numbering that does not number it, and a declared line reference
    outside the body it points into. x-numbering gives each line of a data body the
    number it has in the source it quotes, as ascending ranges; x-lines names the
    attributes holding line numbers or ranges of the nearest data body — the element's
    own, or its enclosing data element's (lf-note's `at` anchors in its lf-code) — by
    those numbers, a line the body leaves out included (it addresses the elided row
    standing for it). The modules miss silently in both directions — a reversed range
    paints nothing, a note past the end docks at the block's foot, a numbering one line
    short leaves the last line unnumbered — and version-to-version drift is exactly how
    one goes stale, so the door refuses what no user would ever see."""
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"]) or {}
        # Shape is the schema's question and already answered (widget_errors reports
        # a malformed value); this gate owns only the counts and bounds, so a value
        # it cannot read is one it stands aside from rather than a traceback that
        # eats every other error.
        value, ranges = _numbering(rec, registry)
        if value is not None and ranges is not None:
            where = at(rec, f'{entry["x-numbering"]}="{value}"')
            last = None
            for part, lo, hi in _spans(value):
                if hi < lo:
                    errors.append(f"{where}: range {part} runs backwards")
                elif last is not None and lo <= last:
                    errors.append(f"{where}: range {part} does not follow line {last}")
                last = hi
            numbered = sum(max(0, hi - lo + 1) for lo, hi in ranges)
            count = _body_lines(rec)
            if numbered != count:
                errors.append(
                    f"{where}: numbers {numbered} lines, but the body has {count}"
                )
        for attr in entry.get("x-lines", ()):
            ref = rec["attrs"].get(attr)
            if ref is None or not LINE_RANGES.fullmatch(ref):
                continue
            body_owner = rec if _body_text(rec) else rec.get("holder") or {}
            value, ranges = _numbering(body_owner, registry)
            if ranges is None:
                continue
            # A line the body leaves out still has a row: the elided one standing for
            # its stretch. So a reference may name any number from the first shown
            # line to the last, and only one past either end misses.
            first, last = min(lo for lo, _ in ranges), max(hi for _, hi in ranges)
            where = at(rec, f'{attr}="{ref}"')
            for part, lo, hi in _spans(ref):
                if hi < lo:
                    errors.append(f"{where}: range {part} runs backwards")
                elif lo < first or hi > last:
                    errors.append(
                        f"{where}: line {part} is outside the {ranges[0][1]}-line body"
                        if value is None
                        else f"{where}: line {part} is outside the body's "
                        f'{registry[body_owner["tag"]]["x-numbering"]}="{value}"'
                    )
    return errors


def suggestion_errors(lf_elements: list, registry: dict, thread_ids: set) -> list:
    """What the registry's schema can't say about a suggestion: it holds at most
    one of each slot and at least one of them, it doesn't nest, and `resolves`
    names a thread in the document's thread namespace. A family lint, named
    for its family — and it reads even its own slots out of the merged registry,
    so a layer that adds one to the family is linted for it rather than around it."""
    tags = {
        tag
        for slot_tags in retirement_slots(registry).get("lf-suggestion", {}).values()
        for tag in slot_tags
    }
    errors = []
    for rec in lf_elements:
        if rec["tag"] != "lf-suggestion":
            continue
        where = at(rec, f"id={rec['attrs'].get('id')!r}")
        if any(w["tag"] == "lf-suggestion" for w in enclosing_widgets(rec)):
            errors.append(f"{where}: suggestions don't nest")
        carried = [tag for tag in rec["children"] if tag in tags]
        if not carried:
            errors.append(
                f"{where}: needs a <lf-old> (what it replaces), a <lf-new> "
                f"(what it proposes), or both"
            )
        for tag in sorted(tags):
            if carried.count(tag) > 1:
                errors.append(
                    f"{where}: carries {carried.count(tag)} <{tag}> children, one at most"
                )
        resolves = rec["attrs"].get("resolves")
        if resolves and resolves not in thread_ids:
            errors.append(
                f"{where}: resolves={resolves!r} names no thread in this document"
            )
    return errors


def fragment_errors(parser: SourceDocument, registry: dict) -> list:
    """Structural + registry validation of a markup fragment (an agent reply
    carrying widgets): the discussion-side analog of `page check`. The declared-word
    checks come along because the schema stopped carrying the lists: a reply's
    <lf-code language=…> is colored by the same tokenizer a version's is, and its chips
    are tinted by the same theme, and nothing else would now refuse either a word its
    layer doesn't know."""
    return (
        structure_errors(parser)
        + widget_errors(parser.lf_elements, registry)
        + layout_errors(parser.lf_elements, registry)
        + visual_part_errors(parser.lf_elements, registry)
        + addressable_instance_errors(parser.lf_elements, registry)
        + ask_surface_errors(parser.lf_elements, registry)
        + declared_word_errors(parser.lf_elements, registry)
        + line_ref_errors(parser.lf_elements, registry)
    )
