"""Event, markup, and authored-page validation boundaries."""

import re
import sys
from pathlib import Path

from leaf.asks import (
    asking,
    page_awaiting_values,
    projected_action_holders,
    quoted_in,
    thread_ask_projection,
)
from leaf.data import data_binding_errors, read_data_store
from leaf.events import build_threads, thread_roots, thread_structure, thread_widgets
from leaf.files import list_revisions, revision_path
from leaf.passages import (
    EMPTY,
    collapse,
    enclosing_ids,
    enclosing_of,
    spoken,
)
from leaf.projection import (
    NO_RECORD,
    StateProjection,
    action_subjects,
    enclosing_widgets,
    folded_facet,
    markup_facet,
    page_projection,
    state_projection,
)
from leaf.registry import (
    RegistryError,
    json_validator,
    merge_layer_entries,
    read_registry_entries,
    require_registry,
    retirement_slots,
    validate_registry,
    visual_parts,
)
from leaf.structure import (
    OPTIONAL_END,
    SECTIONING_TAGS,
    _StructParser,
    parse_revision,
    parse_structure,
)
from leaf.styles import inline_presentation_override_errors


def thread_universe(events: list, registry: dict):
    """Every widget the log's frozen markup holds, read as one document.

    id → record and id → spoken words, which is the panel's answer to a version's
    `parser.by_id`/`spoken` pair, plus the thread each widget was sent in. A
    version's element universe is one file; the panel's is every fragment the log
    carries, and the two are separate documents that happen to share a page."""
    structure = thread_structure(events)
    byid, spk = {}, {}
    for e in events:
        if markup := e.get("markup"):
            byid.update(structure.fragments[e["id"]].by_id)
            spk.update(spoken(markup, registry))
    return byid, spk, thread_widgets(structure, thread_roots(events))


def thread_state(events: list, registry: dict):
    """What the reader's gestures leave standing on the widgets an agent sent.

    Thread markup is frozen in its event: no version window bounds it and no
    retraction floor reaches it, so every action on it reads the whole
    conversation window. Both doors that must answer for such a widget read it
    here — the action gate, deciding whether a fresh press is allowed, and
    `page state`, telling a session picking the page up what the reader has
    already settled — so a decision made in the panel cannot stand at one door
    and be missing at the other."""
    byid, spk, thread_of = thread_universe(events, registry)
    projection = state_projection(events, byid, spk, registry, None, floors={})
    return projection, byid, thread_of


def read_text_arg(text) -> str:
    body = text if text is not None else sys.stdin.read()
    if not body.strip():
        sys.exit("empty text (pass --text or pipe via stdin)")
    return body.strip()


def detail_error(schema: dict, detail: dict):
    """The first schema complaint about an event's detail payload, or None —
    ordered so which one speaks doesn't depend on validator iteration order."""
    error = min(json_validator(schema).iter_errors(detail), key=str, default=None)
    return error.message if error else None


def event_record_error(contract: dict, event: dict, browser: bool = False):
    """The first complaint from one event kind's stored-record contract."""
    schema = contract["record"]
    instance = event
    if browser:
        # Supply the fields the server and reader add so the full record schema
        # can validate the unstamped request beside its browser assertions.
        schema = {"allOf": [schema, contract["browser"]]}
        instance = {
            **event,
            "id": "browser",
            "ts": "browser",
            "author": "page" if event.get("kind") == "error" else "user",
            "seq": 1,
        }
    return detail_error(schema, instance)


def declared_event_error(
    event: dict, tag: str, registry: dict, kind: str, channel: str
):
    """Why a known widget's verb or detail violates one declared channel."""
    entry = registry.get(tag)
    if entry is None:
        return (
            f"registry no longer declares <{tag}> for {kind} widget {event['widget']!r}"
        )
    declared = entry.get(channel, {})
    spec = declared.get(event["action"])
    if spec is None:
        return f"<{tag}> does not declare {kind} verb {event['action']!r}" + (
            f"; it declares {sorted(declared)}" if kind == "report" and declared else ""
        )
    if message := detail_error(spec["detail"], event["detail"]):
        return f"<{tag}> {kind} {event['action']!r} detail is invalid: {message}"
    return None


def declared_action_error(
    event: dict, page_by_id: dict, thread_by_id: dict, registry: dict
):
    """Why a stored action violates its sending widget's durable declaration."""
    # Page widgets come from the action's own immutable revision. Thread widgets
    # inhabit the panel's other live document. Either record answers both which
    # tag sent the action and whether it stands inside an exhibit.
    rec = page_by_id.get(event["widget"]) or thread_by_id.get(event["widget"])
    if rec is None:
        return (
            f"unknown action widget {event['widget']!r} in revision "
            f"r{event['revision']} "
            "or agent-authored thread markup"
        )
    tag = rec["tag"]
    if error := declared_event_error(event, tag, registry, "action", "x-state"):
        return error
    # The exhibit rule at the door, not only in the shipped runtime's
    # sendAction: an exhibited widget is a mention, and the log outranks the
    # document — an action taken here would replay as a decision the reader
    # made on quoted material. Any sender the key admits reaches this door.
    if quoted_in(rec, registry):
        return (
            f"<{tag}> {event['widget']!r} stands inside an exhibit (x-exhibit); "
            "quoted material takes no input"
        )
    return None


def held_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why one comment cannot hold the exact command goal it names."""
    target = event.get("holds")
    if not target:
        return None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or not conversation.get("hold")
        or not asking(rec["attrs"], conversation.get("when"))
        or event.get("anchor") != {"section": target}
    ):
        return (
            "comment holds must name its exact-section anchor on a matching "
            "x-conversation hold target"
        )
    return None


def version_response_comment_error(event: dict, page_by_id: dict, registry: dict):
    """Why a comment cannot require the authored response it names."""
    response = event.get("response")
    if not response:
        return None
    anchor = event.get("anchor")
    target = anchor.get("section") if isinstance(anchor, dict) else None
    rec = page_by_id.get(target)
    conversation = (
        (registry.get(rec["tag"]) or {}).get("x-conversation") if rec else None
    )
    if (
        rec is None
        or not conversation
        or conversation.get("response") != response
        or not asking(rec["attrs"], conversation.get("when"))
        or anchor != {"section": target}
    ):
        return (
            "comment response must match its exact-section x-conversation "
            "response target"
        )
    return None


def visual_anchor_error(event: dict, page_by_id: dict, registry: dict):
    """Why a semantic visual coordinate is not authored on its section."""
    anchor = event.get("anchor") or {}
    visual = anchor.get("visual")
    if not visual:
        return None
    if anchor.get("quote") or anchor.get("datum"):
        return (
            f"visual anchor {visual!r} names a box rather than a passage, "
            "so it cannot also carry a quote or a datum"
        )
    section = anchor["section"]
    available = visual_parts(page_by_id.get(section) or {}, registry)
    if visual not in available:
        return (
            f"visual anchor {visual!r} is not declared on section {section!r}; "
            f"known: {list(available)}"
        )
    return None


def action_contract_error(page_dir: Path, event: dict, events: list, registry: dict):
    """Why a fresh action violates its declaration or current applicability.

    Eligibility is derived inside the append transaction from the action's
    authored document and the standing log. A browser evaluates the same
    declaration for honest controls, but its possibly stale reading never
    authorizes this boundary.
    """
    revision = event["revision"]
    page = parse_revision(page_dir, revision)
    # One reading of the panel's document for the whole door: the id universe the
    # declaration is looked up in and the projection the requirement is judged
    # against are the same frozen fragments, and parsing them twice was two
    # readings that could only ever agree.
    thread_projection, thread_by_id, _threads = thread_state(events, registry)
    if error := declared_action_error(event, page.by_id, thread_by_id, registry):
        return error
    page_rec = page.by_id.get(event["widget"])
    rec = page_rec or thread_by_id[event["widget"]]
    tag = rec["tag"]
    spec = registry[tag]["x-state"][event["action"]]
    requirement = spec.get("requires")
    if not requirement:
        return None

    if page_rec:
        html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        projection, parser, spk = page_projection(html, events, registry, revision)
        byid = parser.by_id
        current = parser.by_id[event["widget"]]
        # This door asks whether the request is answered, not whether it is the
        # reader's to deal with: a conversation standing in the widget's seat
        # takes it off their list without answering it, and refusing their pick
        # over their own remark would refuse them the answer they were asked for.
        awaiting_values = page_awaiting_values(html, parser, projection, spk, registry)
    else:
        # Thread markup is frozen in the log: it has no version retraction floor
        # and its actions read the whole conversation window.
        projection, byid = thread_projection, thread_by_id
        current = byid[event["widget"]]
        page_html = revision_path(page_dir, revision).read_text(encoding="utf-8")
        threads = build_threads(events, enclosing_ids(page_html))
        settled = {root for root, value in threads.items() if value["resolved"]}
        _, awaiting_values = thread_ask_projection(events, registry, settled)

    holders = projected_action_holders(projection, byid, registry)
    target = (
        current
        if requirement["target"] == "self"
        else holders.get(current["attrs"]["id"], current["holder"])
    )
    target_id = target["attrs"]["id"]
    awaiting = awaiting_values.get(target_id, False)
    if awaiting != requirement["awaiting"]:
        return (
            f"<{tag}> {event['widget']!r} action {event['action']!r} is "
            f"unavailable: {requirement['target']} {target_id!r} is "
            f"{'still ' if awaiting else 'no longer '}awaiting the reader"
        )
    return None


def report_contract_error(event: dict, page_by_id: dict, registry: dict):
    """Why a structurally complete report violates its widget's declaration —
    the CLI door's mirror of the POST door's action_contract_error. Page markup
    only, never a reply's: a report has to be answerable, and thread markup is
    frozen in the log, so no version could ever absorb or overrule one made
    there."""
    rec = page_by_id.get(event["widget"])
    tag = rec["tag"] if rec else None
    if tag is None:
        return (
            f"unknown report widget {event['widget']!r} in revision "
            f"r{event['revision']} — "
            "reports name page widgets only; thread markup is frozen, so no "
            "version could ever answer a report made there"
        )
    return declared_event_error(event, tag, registry, "report", "x-report")


def version_ids(page_dir: Path) -> set:
    ids = set()
    for revision in list_revisions(page_dir):
        ids |= parse_revision(page_dir, revision).ids
    return ids


def reserved_ids_error(ids: list) -> str:
    """The one sentence for an authored id in the runtime's own namespace, shared by the
    version lint and the thread-markup one — page ids and a reply's are one universe, so
    what keeps both clear of the runtime's is one rule. leaf.js coins document ids
    under `lf-` (`lf-composer-quote`) and points ARIA at them, so an authored id there
    redirects the reference to the page."""
    return (
        "ids in the runtime's own lf- namespace (it coins lf-composer-quote there, "
        f"and points ARIA at them): {ids}"
    )


def reserved_marker_errors(parser) -> list:
    """The same trespass as a reserved id, and reserved the same way one is: the
    runtime writes data-lf-* attributes and lf- classes as its own record and
    reads them back, so an authored copy makes it misread the page — words
    inside .lf-chrome leave every reading, .lf-quiet clips them to a point, and
    data-lf-gen words become cells the file-side reading has no fence for."""
    return [
        f"<{tag}> at line {line} wears the runtime's own markers "
        f"({', '.join(markers)}); the lf- and data-lf- namespaces are the "
        "runtime's to write, whether or not it writes this name today"
        for tag, line, markers in parser.reserved_markers
    ]


def id_errors(parser) -> list:
    """What a parsed page's own names must not do: repeat, or trespass on the runtime's
    own namespace — its ids, and its markers. One reader, because the two gates that ask
    are asking the same thing of the same parser: a version, and a catalog example, which
    is markup an author writes from. Written twice, the second gate is the one that goes
    on not asking whatever the first one learns to."""
    errors = []
    if parser.duplicate_ids:
        errors.append(
            f"duplicate ids (anchors need unique targets): {parser.duplicate_ids}"
        )
    if parser.reserved_ids:
        errors.append(reserved_ids_error(parser.reserved_ids))
    return errors + reserved_marker_errors(parser)


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


def check_markup(page_dir: Path, kind: str, markup: str, events: list) -> _StructParser:
    """A message's widget markup, validated against the vendored registry at post
    time — the discussion-side `version check`, and the field's one gate: the browser
    door refuses `markup` outright, so nothing reaches the log under that name
    unvalidated. Text needs no gate at all — the runtime renders it with every tag
    escaped, so it cannot claim a widget. Exits with what's wrong."""
    registry = require_registry(page_dir)
    frag = parse_structure(markup)
    # Two gates beside the vocabulary contract rather than inside it. That contract is
    # what re-vendoring asks of every fragment already in the log — can this layer still
    # speak it — and neither a presentation rule nor the presence of a file is any part
    # of the answer. Put there, a page whose log held a <style> from before the rule
    # existed could never be re-vendored again: the log is append-only, so it would have
    # failed `page init` for good, with a message about replay that had nothing to do
    # with what was wrong. Here they are asked of what is arriving, at the one moment
    # anything can still be done about it.
    errs = (
        thread_markup_contract_errors(frag, registry)
        + fragment_style_errors(frag)
        + media_errors(frag, page_dir)
        + data_binding_errors(
            page_dir,
            registry,
            read_data_store(page_dir),
            events,
            [(frag.lf_elements, f"incoming {kind} markup")],
        )
    )
    if errs:
        sys.exit(
            f"{kind} markup doesn't validate:\n" + "\n".join(f"  - {e}" for e in errs)
        )
    if not frag.lf_elements:
        sys.exit("--markup carries no widget; put prose in --text")
    if frag.duplicate_ids:
        sys.exit(
            f"{kind} widget markup reuses an id within itself: {frag.duplicate_ids}"
        )
    if frag.reserved_ids:
        sys.exit(f"{kind} widget markup takes " + reserved_ids_error(frag.reserved_ids))
    if marker_errors := reserved_marker_errors(frag):
        sys.exit(f"{kind} widget markup: " + "; ".join(marker_errors))
    clash = sorted(frag.ids & (version_ids(page_dir) | thread_structure(events).ids))
    if clash:
        sys.exit(
            f"{kind} widget ids already taken by the page or an earlier message: {clash}"
        )
    return frag


def validate_registry_examples(registry: dict, source) -> dict:
    """Validate each independent catalog example where registry layers become one."""
    for tag, entry in registry.items():
        if not tag.startswith("lf-") or (example := entry.get("x-example")) is None:
            continue
        parser = parse_structure(example)
        errors = fragment_errors(parser, registry) + id_errors(parser)
        if errors:
            raise RegistryError(f"{source}: <{tag}> x-example is invalid: {errors[0]}")
    return registry


def incoming_registry(packages: list) -> dict:
    """The merged registry `page init` will vendor.

    Packages are additive at the top level; merge_layer_entries holds the grain.
    """
    merged = {}
    paths = []
    for package in packages:
        path = package / "registry.json"
        if not path.is_file():
            continue
        paths.append(path)
        merge_layer_entries(merged, read_registry_entries(path))
    if not paths:
        raise RegistryError("the incoming layer has no registry.json")
    source = "merged registry (" + ", ".join(str(path) for path in paths) + ")"
    return validate_registry_examples(validate_registry(merged, source), source)


# ---------- the vocabulary stamp ----------
# The registry vendored into a page is also that page's statement of what its
# runtime speaks: $events names the event kinds and the fields each carries,
# x-state (per widget) each tag's verbs and detail schemas. Nothing else on disk
# says so. `page init` refuses a re-vendor that would retire or reshape a contract
# still present in the log.
#
# That refusal is the third door a decision can be lost through, after version-scoping
# and hand-copying: the log is append-only and its verbs are a forever-contract, so
# fifteen of one page's own `decide` events fell silent when the verb was retired under
# them. Only the stamp makes that a refusal rather than a quiet no-op.


def vocabulary_gaps(page_dir: Path, events: list, incoming: dict) -> list:
    """What the page's log says that the *incoming* layer no longer speaks:
    events its $events record schemas reject; reactions on a token its
    $reactions drops; comments whose conversation contract changed; or
    actions and reports whose sending tag, verb, or detail the incoming x-state
    or x-report contract rejects. Empty for a fresh page.
    Counted, because the number is the cost — each is a recorded event that
    would never replay again."""
    if not events:
        return []
    contracts = incoming["$events"]["kinds"]
    tokens = incoming.get("$reactions", {}).get("tokens", {})
    thread = thread_structure(events)
    revisions = {}

    def page_by_id(revision):
        if revision not in revisions:
            revisions[revision] = parse_revision(page_dir, revision).by_id
        return revisions[revision]

    missing = {}
    for e in events:
        kind = e["kind"]
        if kind not in contracts:
            key = f"kind `{kind}`"
        elif error := event_record_error(contracts[kind], e):
            key = f"kind `{kind}` record: {error}"
        elif e.get("token") and e["token"] not in tokens:
            # A token the layer drops has no glyph to paint and no pill to withdraw
            # it by, so a standing reaction on it would fall silent — the verb rule
            # (`declared_action_error`) read for the reaction vocabulary.
            key = f"reaction token `{e['token']}` no longer declared by $reactions"
        elif (
            (
                kind == "comment"
                and e.get("holds")
                and (
                    error := held_comment_error(e, page_by_id(e["revision"]), incoming)
                )
            )
            or (
                kind == "comment"
                and e.get("response")
                and (
                    error := version_response_comment_error(
                        e, page_by_id(e["revision"]), incoming
                    )
                )
            )
            or kind == "comment"
            and (error := visual_anchor_error(e, page_by_id(e["revision"]), incoming))
        ):
            key = f"comment contract: {error}"
        elif kind == "action" and (
            error := declared_action_error(
                e, page_by_id(e["revision"]), thread.by_id, incoming
            )
        ):
            key = f"action contract: {error}"
        elif kind == "report" and (
            error := report_contract_error(e, page_by_id(e["revision"]), incoming)
        ):
            key = f"report contract: {error}"
        elif e.get("markup") and (
            errors := thread_markup_contract_errors(thread.fragments[e["id"]], incoming)
        ):
            key = "thread markup contract: " + "; ".join(errors)
        else:
            continue
        missing[key] = missing.get(key, 0) + 1
    return [
        f"{n} event{'s' if n != 1 else ''} of {key}"
        for key, n in sorted(missing.items())
    ]


def at(rec: dict, named: str = "") -> str:
    """Where a lint finding is, in the terms the author reads their own file in: the
    tag, whatever identifies the one meant — an id, or the attribute the rule is
    about — and the line the markup opens on. Every gate below opens its findings this
    way, so the shape is stated here rather than re-spelled at each of them; a reader
    scanning a page of them reads one shape, and a change to it is one edit."""
    return f"<{rec['tag']}{' ' + named if named else ''}> (line {rec['line']})"


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
    """An x-ask region frames exactly one nested standing request.

    The region owns the question's reading and arrival while the x-awaits widget owns
    its answer. Requiring one structural source makes that split unambiguous for the
    browser walk and for `page state`; liveness still comes from the ordinary projected
    x-awaits value.
    """

    regions = [rec for rec in lf_elements if registry.get(rec["tag"], {}).get("x-ask")]
    sources = {id(region): [] for region in regions}
    for rec in lf_elements:
        if registry.get(rec["tag"], {}).get("x-awaits") is None or quoted_in(
            rec, registry
        ):
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
                f"{at(region)}: an Ask must frame exactly one x-awaits widget, "
                f"found {found or 'none'}"
            )
    return errors


def reference_errors(lf_elements: list, registry: dict, ids: set) -> list:
    """An attribute the registry marks as naming another element (x-refers) that names
    nothing this version holds. The reader follows it, so a typo is a reference to
    nowhere and the markup around it is perfectly well-formed — visible to them and to
    nobody else. Asked of the version rather than of a fragment: a reply's markup
    carries no page to check against, and one of its widgets pointing at the version
    beside it is exactly right."""
    return [
        f'{at(rec)}: {attr}="{target}" names no element in this version'
        for rec in lf_elements
        for attr in registry.get(rec["tag"], {}).get("x-refers", [])
        if (target := rec["attrs"].get(attr)) and target not in ids
    ]


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


# A verb with no declared record form (accept/reject — the honoring version
# retires the wrapper, so there is no markup value to compare) has no record.


def unpointable_blocks(parser: _StructParser) -> list:
    """Blocks a user will aim at whole that no anchor can name. Advice, never a
    gate, in the same register as record_lag:
    references/page-authoring.md's "Stable anchors" states the id rule, and this
    is its feedback loop. The page that introduced item anchoring hit this
    failure itself — its code blocks carried no ids, so a comment aimed at one fell
    through to the enclosing section and read as the gesture being broken rather
    than the page being bare, and nothing anywhere said so.

    A section or article is named outright; a block below one only where its aim
    escapes to a sectioning element. The ancestor's tag stands in for tightness —
    a figure around a table, a card around a pre — which no static read can
    measure, so a page-wide <div id> also passes for aim enough and the advice
    stays quiet. Undercounting is the right error for advice: a miss costs one
    aim landing wide, noise costs the register its authority."""
    lines = []
    for block in parser.bare_blocks:
        where = at(block)
        under = block["under"]
        if block["tag"] in ("section", "article"):
            lines.append(
                f"unpointable — {where} has no id, so no comment or reading "
                f"position can hold to it"
            )
        elif under is None:
            lines.append(
                f"unpointable — {where} has no id, nor anything enclosing it, "
                f"so no comment can name it"
            )
        elif under[0] in SECTIONING_TAGS:
            lines.append(
                f"unpointable — {where} has no id, so a comment aimed at it "
                f"lands on the whole of #{under[1]}"
            )
    return lines


def restatement_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    prev_num: int,
    registry: dict,
    projection: StateProjection,
    floors: dict,
) -> list:
    """The other half of the id-survival rule. That one keeps a revision from
    dropping the anchors a user hung on the page; this one keeps it from
    dropping the decisions they recorded on it. CLAUDE.md carries why the log
    outranks the markup and what that cost.

    The runtime reconciles every standing action onto every later version, so a
    version cannot revise what a user acted on: reconciliation would paint their
    recorded state back over the revision and the new words would reach nobody. A
    version that means to revise says so — `restated` on what it rewrote — and one that
    changes those words in silence is refused here. An unearned `restated` is an
    error too: a decision thrown away for nothing, and, left unchecked, the
    one-word ritual that would make this gate meaningless.

    The comparison is the words each version says (`spoken`), because words are
    what a decision is about. Re-indenting a draft, marking the picked option
    `chosen`, or relocating a card the user already moved is not a revision,
    and neither is writing their own edit back — a version that says what they
    said is agreeing with them.

    Words are one divergence kind; declared state is the other. For each verb
    the registry declares (x-state), the fold gives the user's standing
    state per owner, unit, and facet, and a version whose markup actively changes that unit's
    record away from both the previous version's and the fold is refused the
    same way a silent rewrite of words is. Writing the folded state is the
    state-level echo (honoring); re-emitting the previous version's state is
    blessed silence, which reconciliation resolves; a unit with no surviving folded
    action is exempt — never decided, or retracted back to the author. And
    `restated` is earned by either divergence kind: a words-unchanged
    relocation earns it at the unit even though no subject's words moved."""
    errors = []
    declared = cur.restated
    # Retractions up to prev — never this version's own, which is what it is
    # here to declare, so re-checking a stamped revision reaches the same
    # verdict as checking it did.
    byid = cur.by_id

    decided = {}  # subject id → the actions resting on it
    within = enclosing_of(now)
    for e, _spec in projection.actions.values():
        for subject in action_subjects(e, byid, within, registry):
            if subject in was:
                decided.setdefault(subject, []).append(e)

    # The state gate, beside the words gate: one gate, two divergence kinds.
    prev_byid = prev.by_id
    facet_earned = set()
    for coordinate in sorted(projection.actions):
        _widget, unit, _facet = coordinate
        e, spec = projection.actions[coordinate]
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_prev = markup_facet(unit, spec, prev_byid, was, registry)
        if f_cur is NO_RECORD or f_cur == f_prev:
            continue  # no record form, or no active change — replay resolves silence
        f_fold = folded_facet(e, spec)
        if f_cur == f_fold:
            continue  # writing the folded state is honoring: the state-level echo
        if unit in declared:
            facet_earned.add(unit)
            continue
        where = at(rec, f"id={unit!r}")
        errors.append(
            f"{where}: its state changed under the user's decision — the markup "
            f"shows {f_cur!r} where their {e['action']} (on r{e['revision']}) "
            f"left {f_fold!r}. Their decision is what the page shows, so this state "
            f"would never reach them — add `restated` to retract it and ask again, "
            f"or leave it as r{prev_num} had it."
        )

    for sid, rec in sorted(byid.items()):
        live, restated = decided.get(sid, []), sid in declared
        # A version that writes back what the user themselves recorded is
        # agreeing with them, not overruling them — an honored `edit` is the
        # commonest and most correct thing an author does with a draft, and the
        # gate has to stay quiet for it or it fires on nearly every version and
        # teaches authors to reach for `restated` by reflex. No verb is special-
        # cased: it is enough that the words on the page are words the user
        # sent.
        # `resolves` is not among them: the registry reserves it for the thread
        # an action answers, so its value is a comment id rather than words
        # anybody sent. `action_rests_on` reads past it for the same reason.
        echoed = {
            collapse(str(v))
            for e in live
            for field, v in e["detail"].items()
            if field != "resolves" and isinstance(v, str)
        }
        said = now.get(sid, EMPTY).words
        changed = sid in was and said != was[sid].words and said not in echoed
        where = at(rec, f"id={sid!r}")
        # `restated` is earned by either divergence kind — words on the leaf, or
        # declared state at the unit — else a words-unchanged relocation would
        # be refused both with the attribute and without it.
        if restated and not ((live and changed) or sid in facet_earned):
            # An already-retracted widget is the case an author lands on by being
            # careful — carrying the attribute forward the way state used to have
            # to be carried — so it gets its own answer rather than the
            # never-decided one, which would read as if the user had done
            # nothing.
            if sid in floors:
                errors.append(
                    f"{where}: restated, but r{floors[sid]} already took that "
                    f"back — a retraction is recorded when it is stamped and holds "
                    f"without being repeated. Drop the attribute."
                )
            else:
                why = (
                    f"its words are unchanged since r{prev_num}"
                    if live
                    else "the user has recorded nothing on it"
                )
                errors.append(
                    f"{where}: restated, but there is nothing to retract — {why}. "
                    f"Drop the attribute; `restated` discards their decision."
                )
        elif changed and live and not restated:
            did = ", ".join(f"{e['action']} on r{e['revision']}" for e in live[-3:])
            errors.append(
                f"{where}: its words changed, and the user has already acted "
                f"on it ({did}). Their decision is what the page shows, so these "
                f"words would never reach them — add `restated` to retract it and "
                f"ask again, or leave the text as r{prev_num} had it."
            )
    return errors


def report_errors(
    cur,
    prev,
    was: dict,
    now: dict,
    registry: dict,
    projection: StateProjection,
) -> list:
    """The report gate, beside the reviewer one — the same shape with the
    precedence reversed. A report is a worker's provisional news: the runtime
    paints it onto every revision activated before it, and it stands only until
    a version settles its typed id on the note (the agent-side counterpart to
    `restated`). Three outcomes are legal. Writing the reported state is
    honoring — stamping records it as absorption. Leaving the markup as the
    previous version had it is blessed silence — the report keeps painting.
    Marking the element `overruled` keeps this version's own state and retires
    the report, with the why in the note's text. What is refused is the fourth
    thing, markup that contradicts a standing report it never names: the drop
    must be the publisher's to adjudicate, never silent. And an unearned
    `overruled` is refused like an unearned `restated` — spent where nothing
    stands or where the markup agrees with the report, it is the reflex that
    would make the gate meaningless.

    Standing is read up to prev — never this version's own note, which is what
    stamping is about to record — so re-checking a stamped version reaches
    the same verdict as checking it did."""
    errors = []
    declared = cur.overruled
    byid = cur.by_id
    prev_byid = prev.by_id
    effective_standing = {
        coordinate: reports
        for coordinate, reports in projection.reports.items()
        if coordinate not in projection.actions
    }
    earned = set()
    for coordinate in sorted(effective_standing):
        _widget, unit, _facet = coordinate
        e, spec = effective_standing[coordinate][-1]
        f_cur = markup_facet(unit, spec, byid, now, registry)
        f_rep = folded_facet(e, spec)
        # Whether an `overruled` is earned is this version's markup against the
        # report, so it is settled ahead of the skip below: a unit the gate declines
        # to adjudicate would otherwise land in `unearned` and be told it writes the
        # reported state it in fact contradicts.
        if unit in declared and f_cur != f_rep:
            earned.add(unit)  # a named disagreement, whatever state it keeps
            continue
        rec = byid.get(unit)
        # A unit either version lacks is id-survival's business, not this gate's.
        if rec is None or unit not in prev_byid:
            continue
        if f_cur == f_rep:
            continue  # honoring: stamping absorbs the report by id
        if f_cur == markup_facet(unit, spec, prev_byid, was, registry):
            continue  # blessed silence: the report keeps painting
        where = at(rec, f"id={unit!r}")
        who = e.get("agent", "a worker")
        errors.append(
            f"{where}: its markup contradicts a standing report — it shows "
            f"{f_cur!r} where {who}'s {e['action']} (report {e['id']}, on "
            f"r{e['revision']}) left {f_rep!r}. Adjudicate it: write the reported "
            f"state to absorb the report, or add `overruled` to keep this state "
            f"and retire it (say why in the note)."
        )
    unearned = declared - earned
    # Where an attribute is spent past its revision: which revision already
    # answered the unit's reports, for the message that says to drop it.
    answered_at = {}
    if unearned:
        for (_widget, unit, _facet), revision in projection.report_settlements.items():
            answered_at[unit] = max(answered_at.get(unit, 0), revision)
    for sid in sorted(unearned):
        rec = byid.get(sid)
        if rec is None:
            continue
        where = at(rec, f"id={sid!r}")
        if any(unit == sid for _widget, unit, _facet in effective_standing):
            errors.append(
                f"{where}: overruled, but this version writes the reported state — "
                f"that is absorption, which stamping records on its own. "
                f"Drop the attribute."
            )
        elif sid in answered_at:
            errors.append(
                f"{where}: overruled, but r{answered_at[sid]} already answered the "
                f"reports on it — an answer is recorded when it is stamped and "
                f"holds without being repeated. Drop the attribute."
            )
        else:
            errors.append(
                f"{where}: overruled, but no report is standing on it — there is "
                f"nothing to overrule. Drop the attribute."
            )
    return errors


def structure_errors(parser: _StructParser) -> list:
    """A fed parser's structural complaints, plus the tags it was left holding
    open at the end of its input."""
    errors = list(parser.errors)
    leftover = [(t, ln) for t, ln, *_ in parser.stack if t not in OPTIONAL_END]
    if leftover:
        errors.append(
            "unclosed tags: " + ", ".join(f"<{t}> (line {ln})" for t, ln in leftover)
        )
    return errors


def page_boundary_errors(parser: _StructParser) -> list:
    """Authored content lies under the same element the presentation gate owns."""
    errors = []
    direct = [line for line, is_direct in parser.main_elements if is_direct]
    if (
        len(parser.body_lines) != 1
        or len(parser.main_elements) != 1
        or len(direct) != 1
    ):
        errors.append(
            "the page must have one <main> directly under <body>; "
            f"found {len(parser.body_lines)} bodies, {len(parser.main_elements)} mains, "
            f"and {len(direct)} direct body mains"
        )
    if parser.outside_main:
        errors.append(
            "paintable authored content must stay inside the one <main> directly "
            "under <body>; found " + str(parser.outside_main)
        )
    return errors


def fragment_style_errors(parser: _StructParser) -> list:
    """A message may not dress the document it is put into.

    A version's <style> is the page's own, and the gates a version answers to read
    it as such — syntax, the column it may not overflow, the presentation
    properties the theme keeps. A fragment has no page of its own: the runtime
    parses an agent's reply markup into a template and moves those nodes into the
    message body, where a <style> among them becomes a document stylesheet like
    any other. `<style>main h1 { color: red !important }</style>` in a reply was
    accepted here and repainted the version's own heading, past every gate the
    same rule in a version answers to; an inline `!important` on a protected
    property outranked the theme's first cascade layer the same way.

    Nothing is lost by refusing them. The layer already dresses a widget an agent
    sends — that is what a registry entry and its theme rules are for — and a rule
    of a message's own has nowhere honest to sit, because the message is not the
    page and its markup is frozen in the log where no version can revise it."""
    errors = []
    if parser.css.strip():
        errors.append(
            "<style> in message markup becomes a stylesheet of the whole document it "
            "is put into; a widget's look belongs in the layer's theme, beside its "
            "registry entry"
        )
    if parser.stylesheets:
        errors.append(
            "<link rel=stylesheet> in message markup dresses the whole document it is "
            "put into; the page serves the one vendored theme it was reviewed with"
        )
    return errors + inline_presentation_override_errors(parser)


def media_errors(parser: _StructParser, page_dir: Path) -> list:
    """A /media/ reference the page directory can't answer, which renders as a broken
    image. The render gate would catch it as a 404, but that runs once a page; this
    runs at every door markup comes through, and a missing file is as deterministic as
    a missing id.

    Both doors, because a widget carrying pictures is exactly the shape an agent sends
    in a reply — here is what it looks like now, and after — and the fragment door was
    the one that didn't ask. A version can be rewritten; a reply is frozen in an
    append-only log the moment it is accepted, so an unanswerable reference posted
    there is two broken images for as long as the page exists, and no later check
    would ever mention them.

    Asked at each door rather than in the vocabulary contract, for the reason
    `check_markup` gives where that choice is made."""
    return [
        f"{ref} isn't in the page directory; `leaf page media` puts it there"
        for ref in sorted(parser.media_refs)
        if not (page_dir / ref.lstrip("/")).is_file()
    ]


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
        + language_class_errors(parser.language_blocks, registry)
        + declared_word_errors(parser.lf_elements, registry)
        + line_ref_errors(parser.lf_elements, registry)
    )
