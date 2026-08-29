"""Registry-declared markup instance validation."""

import re

from leaf.asks import asking, quoted_in
from leaf.projection import enclosing_widgets
from leaf.registry.contract import json_validator, registry_path, visual_parts
from leaf.registry.state import retirement_slots
from leaf.structure import _StructParser

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
    attribute instance, x-parent nesting, and the x-content model."""
    errors = []
    # Containers ("items") admit exactly the tags that declare them as x-parent.
    children_of = {}
    for tag, entry in registry.items():
        if not tag.startswith("lf-"):
            continue
        for parent in entry.get("x-parent", []):
            children_of.setdefault(parent, set()).add(tag)

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
            prop = props.get(name)
            is_flag = isinstance(prop, dict) and prop.get("type") == "boolean"
            instance[name] = True if value in (None, "") and is_flag else (value or "")
        for err in sorted(json_validator(entry).iter_errors(instance), key=str):
            errors.append(f"{where}: {err.message}")

        want_parents = entry.get("x-parent", [])
        if want_parents and rec["parent"] not in want_parents:
            actual = f", found <{rec['parent']}>" if rec["parent"] else ""
            wanted = " or ".join(f"<{p}>" for p in want_parents)
            errors.append(f"{where}: must be a direct child of {wanted}{actual}")
        # Tags declaring this one as x-parent are admissible children under any
        # content model — that is what x-parent means. "data" takes one <pre> and
        # those, "items" element children only, "none" nothing at all.
        content = entry["x-content"]
        allowed = children_of.get(tag, set())
        stray = sorted({c for c in rec["children"] if c not in allowed})
        if content == "none" and (rec["children"] or rec["text"]):
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
        elif content == "items":
            if stray:
                errors.append(
                    f"{where}: admits only {sorted(allowed)} children, found {stray}"
                )
            if rec["text"]:
                errors.append(f"{where}: loose text between its items isn't allowed")
    return errors


def visual_part_errors(lf_elements: list, registry: dict) -> list:
    """A visual's authored part tokens each name one stable generated target."""
    errors = []
    for rec in lf_elements:
        parts = visual_parts(rec, registry)
        duplicates = sorted({part for part in parts if parts.count(part) > 1})
        if duplicates:
            errors.append(
                f"{at(rec)}: visual part ids must be unique, repeated {duplicates}"
            )
    return errors


def ask_region_errors(lf_elements: list, registry: dict) -> list:
    """An x-ask region frames exactly one nested declared ask source.

    The region owns the question's reading and arrival while the x-awaits or request
    widget owns its answer. Requiring one structural source makes that split
    unambiguous for the browser walk and for `page state`; liveness still comes from
    the source's canonical ask projection.
    """

    regions = [rec for rec in lf_elements if registry.get(rec["tag"], {}).get("x-ask")]
    sources = {id(region): [] for region in regions}
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        declared = (
            entry.get("x-awaits") is not None
            or entry.get("x-request", {}).get("ask") is True
        )
        if not declared or quoted_in(rec, registry):
            continue
        holder = rec.get("holder")
        while holder and not registry.get(holder["tag"], {}).get("x-ask"):
            holder = holder.get("holder")
        if holder:
            sources.setdefault(id(holder), []).append(rec)

    errors = []
    for region in regions:
        nested = sources[id(region)]
        if len(nested) != 1:
            found = [
                f"<{rec['tag']}#{rec['attrs'].get('id') or '?'}>" for rec in nested
            ]
            errors.append(
                f"{at(region)}: an Ask must frame exactly one declared ask source, "
                f"found {found or 'none'}"
            )
    return errors


def request_offer_errors(lf_elements: list, registry: dict) -> list:
    """Every authored request seat presents at least one command it can send.

    The registry declares a holder's complete verb vocabulary, while its direct
    children choose which verbs this particular seat offers. An empty holder would
    otherwise enter the Ask projection with no possible answer.
    """
    errors = []
    for holder in lf_elements:
        request = registry.get(holder["tag"], {}).get("x-request")
        if request is None or quoted_in(holder, registry):
            continue
        offered = [
            rec["attrs"][request["offers"][rec["tag"]]]
            for rec in lf_elements
            if rec.get("holder") is holder
            and rec.get("parent") == holder["tag"]
            and rec["tag"] in request["offers"]
            and request["offers"][rec["tag"]] in rec["attrs"]
        ]
        if not offered:
            errors.append(
                f"{at(holder)}: an x-request holder must offer at least one "
                "declared verb"
            )
            continue
        duplicates = sorted({verb for verb in offered if offered.count(verb) > 1})
        if duplicates:
            errors.append(
                f"{at(holder)}: an x-request holder must offer each verb once; "
                f"repeated {duplicates}"
            )
    return errors


def reference_contract_error(
    record: dict, attribute: str, target_record: dict | None, registry: dict
) -> str | None:
    """Why one existing target fails its package-declared relation, if it does."""
    reference = registry[record["tag"]]["x-refers"][attribute]
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
    return (
        f'{at(record)}: {attribute}="{record["attrs"].get(attribute)}" must '
        f"name a {via} widget where {expected}; {actual}"
    )


def reference_errors(lf_elements: list, registry: dict, ids: set, by_id: dict) -> list:
    """An attribute the registry marks as naming another element (x-refers) that names
    nothing this version holds. The reader follows it, so a typo is a reference to
    nowhere and the markup around it is perfectly well-formed — visible to them and to
    nobody else. Asked of the version rather than of a fragment: a reply's markup
    carries no page to check against, and one of its widgets pointing at the version
    beside it is exactly right."""
    errors = []
    for rec in lf_elements:
        for attr in registry.get(rec["tag"], {}).get("x-refers", {}):
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
    return errors


def addressable_instance_errors(lf_elements: list, registry: dict) -> list:
    """Conditional asks and conversation seats need an id when they are live.

    Requiring every instance globally would outlaw inert option groups; checking the
    declared predicate here gives the runtime exactly the addressability it consumes.
    """
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"], {})
        for role in ("x-awaits", "x-conversation"):
            declaration = entry.get(role)
            if (
                declaration is not None
                and asking(rec["attrs"], declaration.get("when"))
                and not rec["attrs"].get("id")
            ):
                errors.append(f"{at(rec)}: a matching {role} instance requires an id")
    return errors


def language_class_errors(blocks: list, registry: dict) -> list:
    """A `class="language-…"` the runtime won't honor: the class somewhere other than
    <pre><code>, or a word the layer doesn't speak. Neither is visible to the user — a
    class in the wrong place and a misspelt language both render as an ordinary
    uncolored block — so the failure is routed to the one party who can still fix it,
    which is whoever wrote the word. A widget declaring a language is held to the same
    list one attribute over (declared_word_errors); this half is the plain HTML block,
    which belongs to no widget at all.

    The list is indexed rather than tested: a layer naming none colors none, so a word
    declared to it is still one it can't honor, and the placement rule never depended on
    the list at all. A check whose two failures are both invisible on the page is the
    last one that should be able to pass by finding nothing to check against.

    The misplaced block is offered the other way to color one, read from the same
    declaration the check itself reads: whichever tags say an attribute of theirs names
    a language (x-language). Naming one here would be this lint knowing a widget, and
    the offer would go stale the moment a layer dropped it or added a second — so a
    layer whose tags declare none says only to move the block."""
    known = registry["$languages"]["names"]
    colored = " or ".join(
        f"<{tag} {attr}=…>"
        for tag, entry in sorted(registry.items())
        if tag.startswith("lf-") and (attr := entry.get("x-language"))
    )
    instead = f", or use {colored} for a walkthrough" if colored else ""
    errors = []
    for block in blocks:
        where = f'class="language-{block["lang"]}" (line {block["line"]})'
        if (block["tag"], block["parent"]) != ("code", "pre"):
            errors.append(
                f"{where}: only <pre><code> is colored, found <{block['tag']}> in "
                f"<{block['parent'] or 'nothing'}> — move it{instead}"
            )
        elif block["lang"] not in known:
            errors.append(
                f"{where}: not a language this page's layer speaks — known: {known}"
            )
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


def line_ref_errors(lf_elements: list, registry: dict) -> list:
    """A declared line reference outside the body it points into. x-lines names the
    attributes holding 1-based line numbers or ranges of the nearest data body — the
    element's own, or its holder's (lf-note's `at` anchors in its lf-code). The
    modules miss silently in both directions — a reversed range paints nothing, a
    note past the end docks at the block's foot — and version-to-version drift is
    exactly how one goes stale, so the door refuses what no reader would ever see."""
    errors = []
    for rec in lf_elements:
        entry = registry.get(rec["tag"]) or {}
        for attr in entry.get("x-lines", ()):
            value = rec["attrs"].get(attr)
            if value is None:
                continue
            # Shape is the schema's question and already answered (widget_errors
            # reports a malformed value); this gate owns only the bounds, so a
            # value it cannot read is one it stands aside from rather than a
            # traceback that eats every other error.
            if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*", value):
                continue
            holder = rec if rec["body"].strip() else rec.get("holder") or {}
            # The modules' own trim: leading blank lines and trailing whitespace
            # are the source's furniture, not lines.
            body = re.sub(r"\s+$", "", re.sub(r"^\n+", "", holder.get("body", "")))
            count = len(body.split("\n"))
            where = at(rec, f'{attr}="{value}"')
            for part in value.split(","):
                lo, _, hi = part.partition("-")
                lo, hi = int(lo), int(hi) if hi else int(lo)
                if hi < lo:
                    errors.append(f"{where}: range {part} runs backwards")
                elif not 1 <= lo <= count or hi > count:
                    errors.append(
                        f"{where}: line {part} is outside the {count}-line body"
                    )
    return errors


def suggestion_errors(lf_elements: list, registry: dict, comment_ids: set) -> list:
    """What the registry's schema can't say about a suggestion: it holds at most
    one of each slot and at least one of them, it doesn't nest, and `resolves`
    names a comment that exists. A family lint, named for its family — and it
    reads even its own slots out of the merged registry, so a layer that adds
    one to the family is linted for it rather than around it."""
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
        if resolves and resolves not in comment_ids:
            errors.append(f"{where}: resolves={resolves!r} names no comment in the log")
    return errors


def fragment_errors(parser: _StructParser, registry: dict) -> list:
    """Structural + registry validation of a markup fragment (an agent reply
    carrying widgets): the discussion-side analog of `version check`. The declared-word
    checks come along because the schema stopped carrying the lists: a reply's
    <lf-code language=…> is colored by the same tokenizer a version's is, and its chips
    are tinted by the same theme, and nothing else would now refuse either a word its
    layer doesn't know."""
    return (
        structure_errors(parser)
        + widget_errors(parser.lf_elements, registry)
        + visual_part_errors(parser.lf_elements, registry)
        + addressable_instance_errors(parser.lf_elements, registry)
        + ask_region_errors(parser.lf_elements, registry)
        + request_offer_errors(parser.lf_elements, registry)
        + language_class_errors(parser.language_blocks, registry)
        + declared_word_errors(parser.lf_elements, registry)
        + line_ref_errors(parser.lf_elements, registry)
    )
