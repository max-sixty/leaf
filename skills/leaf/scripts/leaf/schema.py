"""Layer schema and page-directory vocabulary."""

import re
from pathlib import Path

from .session_cleanup import EVENTS_FILE

# A session-managed server gives a replacement session one short poll window to
# claim the page before it closes. The external claim record is the ownership
# source; a standing lifetime ignores it and remains enabled until `server stop`.
ORPHAN_GRACE_SECS = 1
# Activity-backed claims must survive time in a background tab, which stops
# renewing viewed.json. Four hours permits those gaps while retiring abandoned
# session pages. Claim renewal and service lifetime: session-lifetime.md.
ACTIVITY_GRACE_SECS = 4 * 60 * 60
# The harness-neutral name of an agent nothing names: a page's when no claimant
# supplies one, and an agent-authored event's that carries no `agent` (`agent_name`).
UNNAMED_AGENT = "Agent"
# Non-message gesture kinds eligible for withdrawal; events.undo_error handles
# reactions. The complete eligibility contract is events.md, "Undo".
UNDOABLE_KINDS = {"resolve", "unresolve", "action", "done"}
MESSAGE_KINDS = {"comment", "reply"}
# The kinds a widget owns, admitted against the page's registry before they append.
WIDGET_KINDS = {"action", "report"}
# The operations that settle a user move the agent owes, as `workflows` and
# `activity` address them and `$events.answering` explains them. A `turn` answer is
# a thread reply the claimant's turn writes with its own opening and final messages.
ANSWER_KINDS = ("reply", "turn", "markup")
# The answer kinds that post a message in a thread.
THREAD_ANSWER_KINDS = frozenset({"reply", "turn"})
ANSWER_ASK_INSTRUCTION = (
    "Each move takes the answer named for it. Read current obligations with "
    "`leaf page state <page>` and thread history with `leaf page state <page> <id>`."
)
WAIT_BATCH_OUTPUT_INSTRUCTION = (
    "Print one page's complete ordered batch, thread context, and response "
    "requirements as an immutable delivery, whose `acknowledge` says how to confirm "
    "it. `leaf delivery read <id>` reads that same delivery. Where the host's hook "
    "carries input into the turn, as in Claude Code, print one line naming the page "
    "with new input instead, and end."
)

HTML_NAME = r"[a-z][a-z0-9-]*"
WIDGET_NAME = r"lf-[a-z0-9]+(?:-[a-z0-9]+)*"
# What a refused element name is told, so the author need not read WIDGET_NAME.
WIDGET_NAME_RULE = (
    "an element name is `lf-` followed by hyphen-separated words of lowercase "
    f"letters and digits, such as `lf-merge-film` ({WIDGET_NAME})"
)
ELEMENT_ID = r"[a-z0-9][a-z0-9-]*"
# An id the log mints for an event. Page ids and event ids are one address space:
# a command's ID is a widget or a message, whichever the page holds, so an authored
# id may not take this shape (`validation.markup.id_errors`).
EVENT_ID = r"[0-9a-f]{8}"
DATA_SOURCE_NAME = HTML_NAME
DATA_CONTRACT_NAME = r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*"
# The record forms one vocabulary of declared state draws on ($state in the
# registry): how a unit's state reads in markup, each dispatched on by the gate,
# the runtime, and the diff without any of them knowing a widget by name.
_RECORD_ATTRIBUTE = {
    "type": "object",
    "properties": {
        "kind": {"const": "attribute"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "attr", "value"],
    "additionalProperties": False,
}
_RECORD_POSITION = {
    "type": "object",
    "properties": {
        "kind": {"const": "position"},
        "within": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
        "value": {"type": "string", "minLength": 1},
        # The detail field holding the unit's rank among its container's siblings.
        # Comparison stays at the container's granularity (see $state), but a
        # reader that has to *state* a position needs both halves: a record naming
        # only the column would put a card back on the right list in the wrong place.
        "rank": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "within", "value", "rank"],
    "additionalProperties": False,
}
_RECORD_BODY = {
    "type": "object",
    "properties": {
        "kind": {"const": "body"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "value"],
    "additionalProperties": False,
}
_RECORD_VALUE = {
    "type": "object",
    "properties": {
        "kind": {"const": "value"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "value": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "attr", "value"],
    "additionalProperties": False,
}


# A `when` predicate selects instances by attribute values (or by a flag's being
# present or absent). One condition shape serves Asks and threads because they
# ask the same question of the same authored attributes.
AWAITING_CONDITION = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "array",
        "items": {"type": ["string", "boolean"]},
        "minItems": 1,
    },
}

# When a local Ask is answered: a map from each answering x-state verb to the
# condition its standing state meets. An empty condition means the verb's state stands
# (a non-empty attribute or value record, otherwise a standing action). `when` narrows
# the verb to instances whose attributes match; `empty` holds when the one member
# container it names inside the widget is left with no members by the standing
# positions. One map, so every answer is a reading of state the fold already keeps.
ANSWERED_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "when": AWAITING_CONDITION,
            "empty": {
                "type": "object",
                "properties": {
                    "within": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
                    "when": AWAITING_CONDITION,
                },
                "required": ["within", "when"],
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
}

ACTION_CREATES = {
    "type": "object",
    "properties": {
        "child": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
        "words": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["child", "words"],
    "additionalProperties": False,
}

# One package-neutral relation shape for authored attributes. An empty object accepts
# any authored element. A typed relation selects a package registry map
# and an equality predicate within that map; the names and values remain vocabulary.
# `owns` makes the relation one-to-one within a document: the referrer fills its
# target (`validation.instances.reference_errors`).
REFERENCE_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "via": {
                "type": "string",
                "pattern": r"^\$[a-z][a-z0-9-]*(?:\.[a-z][A-Za-z0-9-]*)*$",
            },
            "where": {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": {
                    "type": ["string", "number", "boolean", "null"]
                },
            },
            "owns": {"const": True},
        },
        "dependentRequired": {"via": ["where"], "where": ["via"], "owns": ["via"]},
        "additionalProperties": False,
    },
}


# Each verb is {detail, unit, record}. `writer: "agent"` makes it a verb the agent
# reports through `leaf page report` rather than one the user acts on;
# absent, the user writes it. The two writers differ in what their state may be, not in its shape.
STATE_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "detail": {"type": "object"},
            "unit": {"type": "string", "minLength": 1},
            "record": {
                "oneOf": [
                    _RECORD_ATTRIBUTE,
                    _RECORD_POSITION,
                    _RECORD_BODY,
                    _RECORD_VALUE,
                ]
            },
            "writer": {"const": "agent"},
            "creates": ACTION_CREATES,
            # A report may carry one short prose update beside the structured state it
            # records. Naming the detail field is what lets the common update feed
            # expose those words without guessing from a widget, verb, or field name.
            "update": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        },
        "required": ["detail", "unit"],
        "additionalProperties": False,
        # An agent's verb moves declared state only, never body words — so the
        # passage reading never has to model one — and never a part's place, which
        # the stamped version owns and a rank reads between the neighbours a widget
        # shows the user. Its record is required: the gate compares record forms,
        # and a recordless report would be a claim nothing could check a version
        # against. Only the user adds children, and only a report carries update
        # prose.
        "if": {"required": ["writer"]},
        "then": {
            "required": ["record"],
            "properties": {
                "record": {"properties": {"kind": {"enum": ["attribute", "value"]}}},
                "creates": False,
            },
        },
        "else": {"properties": {"update": False}},
    },
}
AWAITS_SCHEMA = {
    "type": "object",
    "properties": {
        "when": AWAITING_CONDITION,
        "answered": ANSWERED_SCHEMA,
        # This widget supplies the answer control but not its own question title.
        # A matching instance therefore stands inside an x-ask-surface region, whose direct
        # heading owns the reading and arrival.
        "region": {"const": True},
        "all": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "additionalProperties": False,
}
# Package and data-contract instructions address their declared audiences. Widget
# authoring instructions have one reader and therefore use a plain string below.
INSTRUCTIONS_SCHEMA = {
    "type": "object",
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {"type": "string", "pattern": r"\S"},
}
DATA_INPUTS_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "contract": {
                "type": "string",
                "pattern": f"^{DATA_CONTRACT_NAME}$",
            },
            "source": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        },
        "required": ["contract", "source"],
        "additionalProperties": False,
    },
}
MEASURED_SCHEMA = {
    "type": "object",
    "properties": {
        # The x-data input whose source timestamp says whether another run landed.
        "input": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        # The widget attribute holding the source value's recorded instant.
        "at": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["input", "at"],
    "additionalProperties": False,
}

_ATTRIBUTE_LIST = {
    "type": "array",
    "items": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    "minItems": 1,
}
_ATTRIBUTE_NAME = {"type": "string", "pattern": f"^{HTML_NAME}$"}
CHILDREN_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{WIDGET_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {"one-each": {"type": "string", "pattern": f"^{HTML_NAME}$"}},
        "required": ["one-each"],
        "additionalProperties": False,
    },
}
EXTENSION_SCHEMA = {
    "type": "object",
    "properties": {
        "x-ask-surface": {"const": True},
        "x-awaits": AWAITS_SCHEMA,
        "x-thread-seat": {
            "type": "object",
            "properties": {
                "when": AWAITING_CONDITION,
                "hold": {"type": "string", "minLength": 1},
            },
            "required": ["when"],
            "additionalProperties": False,
        },
        "x-required-members": CHILDREN_SCHEMA,
        "x-content": {"enum": ["markup", "members", "data", "empty"]},
        "x-text-format": {"const": "inline-markdown"},
        "x-data": DATA_INPUTS_SCHEMA,
        "x-example": {"type": "string"},
        "x-exhibit": {"type": "boolean"},
        "x-instructions": {"type": "string", "pattern": r"\S"},
        "x-inline": {"type": "boolean"},
        "x-language": _ATTRIBUTE_NAME,
        "x-reading-role": {"enum": ["pane"]},
        # Attributes holding line references into the nearest data body — the element's
        # own <pre>, or its enclosing data element's (lf-note's `at` names a line of its
        # lf-code) — by the numbers x-numbering gives that body, 1-based without it.
        # `page check` refuses one outside the body (line_ref_errors).
        "x-lines": _ATTRIBUTE_LIST,
        "x-numbering": _ATTRIBUTE_NAME,
        "x-measured": MEASURED_SCHEMA,
        # Attributes the theme renders as paint alone — a status marker's tint or an
        # event's kind. The runtime speaks each as a clipped word (renderQuiet), the
        # value or, where a flag carries no value, the attribute's own name.
        "x-paints": _ATTRIBUTE_LIST,
        "x-patch": {"enum": ["members"]},
        "x-owners": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
            "minItems": 1,
        },
        "x-refers": REFERENCE_SCHEMA,
        "x-retired-when": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-says": {
            "type": "object",
            "propertyNames": {"pattern": f"^{HTML_NAME}$"},
            "additionalProperties": {"enum": ["before", "after"]},
        },
        "x-shadow": {"type": "boolean"},
        "x-state": STATE_SCHEMA,
        "x-thread-surface": {"const": True},
        "x-tone": _ATTRIBUTE_NAME,
        "x-upgrade": {"type": "boolean"},
        "x-verbatim": {"type": "boolean"},
        "x-visual": {
            "oneOf": [
                {"const": "whole"},
                {
                    "type": "object",
                    "properties": {
                        "parts": _ATTRIBUTE_NAME,
                        "complete": {"const": True},
                    },
                    "required": ["parts"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "prefixes": {
                            "type": "array",
                            "items": {"type": "string", "pattern": "^\\S+$"},
                            "minItems": 1,
                            "uniqueItems": True,
                        }
                    },
                    "required": ["prefixes"],
                    "additionalProperties": False,
                },
            ]
        },
        "x-space": {"enum": ["wide", "available"]},
        "x-bound": {"enum": ["start", "end"]},
        # A default height in CSS pixels, or `true` for a widget that has none and
        # reserves only what an occurrence's data-height states.
        "x-height": {"oneOf": [{"const": True}, {"type": "integer", "minimum": 1}]},
        # Child selectors, each matched inside the element, for the painted boxes that
        # draw its own face: a margin pin whose target is the element may stand on them.
        # Only a light-DOM child by tag and classes, so a malformed selector is refused
        # here rather than throwing in the browser's layout pass.
        "x-face": {
            "type": "array",
            "items": {
                "type": "string",
                "pattern": r"^:scope > (?:[a-z][a-z0-9-]*(?:\.[A-Za-z_][\w-]*)*|(?:\.[A-Za-z_][\w-]*)+)$",
            },
            "minItems": 1,
            "uniqueItems": True,
        },
        "x-history": {"const": True},
        "x-views": {"const": True},
        "x-withdrawn-as": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-word": {"enum": ["module"]},
        "x-name": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-work": {"const": True},
    },
    "required": ["x-content", "x-upgrade"],
    "dependentRequired": {
        "x-retired-when": ["x-owners"],
        "x-measured": ["x-data"],
    },
    # Only an upgraded container has members its module could leave in place.
    "if": {"required": ["x-patch"]},
    "then": {
        "properties": {"x-content": {"const": "members"}, "x-upgrade": {"const": True}}
    },
    "additionalProperties": False,
}
# The keys whose value names attributes of the widget's own schema, in whichever shape
# each carries the names: a list, a mapping keyed by them, or one name. One rule for all
# of them, because the failure is one — the attribute is absent, so the pass reading the
# key finds nothing and does nothing, and the widget is simply missing from it with no
# error anywhere (validate_registry holds every key here to the entry's `properties`).
# The verb keys of the same shape (x-retired-when, x-withdrawn-as) are not in it: they
# name an outcome rather than an attribute, and sharing a spelling is no reason to share
# a check. x-awaits and x-data name attributes too and keep their own loops, having more
# to say about each than that it exists.
ATTRIBUTE_KEYS = (
    "x-language",
    "x-lines",
    "x-name",
    "x-numbering",
    "x-paints",
    "x-refers",
    "x-says",
    "x-tone",
)
# The declarations a stylesheet reads, each painted on the element as `paint`: the room
# it takes (x-space), whether it sets inline among words (x-inline), quotes what it holds
# (x-exhibit), holds its own height (x-bound), draws into a box of a stated height
# (x-height), the reading structure it supplies (x-reading-role), and whether it shows
# one member at a time (x-views). Neither a stylesheet nor the prepaint, which runs
# before the registry has loaded (`runtime/prepaint.js`), can read the registry, so
# each is painted where a selector can ask. `authored` is
# the attribute an occurrence writes to override its tag's declaration. `message` says
# whether the mark holds in a thread's message too:
# each is the element's own fact wherever it renders, except the room, which is the
# document's to hand out; a message renders in the panel, whose width bounds it.
#
# Delivery paints a page's document from this (`revision_delivery.mark_declared`).
# Composition stamps it into the vocabulary as `$marks` (`registry.layer.
# stamp_composition`), from which the runtime paints a message it renders and tells the
# paint from the author's attributes (`isPagePaint`). The paint names are also the
# theme's contract: the stylesheets that read them spell them out.
DECLARED_MARKS = {
    "x-space": {"paint": "data-lf-space", "authored": "data-width", "message": False},
    "x-inline": {"paint": "data-lf-inline", "message": True},
    "x-exhibit": {"paint": "data-lf-exhibit", "message": True},
    "x-bound": {"paint": "data-lf-bound", "authored": "data-bound", "message": True},
    "x-height": {"paint": "data-lf-height", "authored": "data-height", "message": True},
    "x-reading-role": {"paint": "data-lf-reading-role", "message": True},
    "x-views": {"paint": "data-lf-views", "message": True},
}

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = SKILL_ROOT.parent.parent
ASSETS = SKILL_ROOT / "assets"
BUNDLED_PACKAGES = SKILL_ROOT / "packages"
DEFAULT_PACKAGE = BUNDLED_PACKAGES / "default"
VENDORED_FILES = ("leaf.js", "theme.css", "shadow.css", "registry.json", "icon.svg")
BROWSER_DIRS = ("runtime", "widgets", "vendor")
INSTRUCTIONS_DIR = "instructions"
PACKAGE_DIRS = (*BROWSER_DIRS, INSTRUCTIONS_DIR)
# A package's own command-line tools, run by `leaf package run` from wherever the
# package is installed or bundled. A page never vendors them: they are the agent's.
SCRIPTS_DIR = "scripts"
INSTRUCTIONS_FILE = re.compile(rf"{HTML_NAME}\.md")
LAYER_PLACEHOLDER = b'"__LEAF_LAYER_GENERATION__"'
# Images the page shows, named by the hash of their bytes (`page media`). Not vendored
# — they are the page's content, not the layer's — but served like it, and the
# naming is what keeps the directory's promise: same name, same bytes, so a
# version the user approved cannot show them something else later.
MEDIA_DIR = "media"
MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
# A media file's name is the first MEDIA_DIGEST hex characters of its bytes' SHA-256
# and a lowercase MEDIA_TYPES suffix: `media.media_name` mints it, `DIR_FILES` serves
# it, and the agent's reference doors refuse any other name under `/media/`. The
# browser and the Worker know the directory and never the name.
MEDIA_DIGEST = 16
NO_KEY = "open the link leaf printed; it carries the key"
DATA_FILE = "data.json"
DATA_DIR = "data"
# The diagnostic request and interaction trace (`interaction_log.py`).
INTERACTIONS_FILE = "interactions.jsonl"
PREVIEW_FILE = "preview.json"
VIEWED_FILE = "viewed.json"
# One name, because there is one key (`host_key`). Cookies are scoped by host and
# blind to the port, so every page this machine serves shares a jar — on 127.0.0.1,
# with every other server the user has running, which is what the prefix is for.
KEY_COOKIE = "lf_key"
# How long a bare address stays authorized after the last handover link (`host_key`),
# the lifetime Jupyter gives its login cookie.
KEY_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
STATUS_FILE = "status.json"
CURSOR_FILE = "cursor.json"
SERVICE_FILE = "service.json"
SERVER_LOCK = "server.lock"
WAITER_LOCK = "waiter.lock"
# What a page records about who is working on it and how it is served, as against what
# its author wrote (the source) and what it has accumulated (the log and its revisions).
# Neither validation nor a revision's capture reads these, so a write to one is news to
# an open tab and never a candidate revision.
SESSION_FILES = (
    STATUS_FILE,
    WAITER_LOCK,
    CURSOR_FILE,
    VIEWED_FILE,
    SERVICE_FILE,
    SERVER_LOCK,
    PREVIEW_FILE,
)
# The files Leaf writes in a page directory as it runs. With the author's index.html,
# the vendored files, and PAGE_OWNED_DIRS, the whole of page-storage.md's "Files".
PAGE_STATE_FILES = (EVENTS_FILE, INTERACTIONS_FILE, DATA_FILE, *SESSION_FILES)
PAGE_OWNED_FILES = ("index.html", *VENDORED_FILES, *PAGE_STATE_FILES)
PAGE_OWNED_DIRS = ("revisions", *PACKAGE_DIRS, MEDIA_DIR, DATA_DIR, "page")
# A revision's and a version's file name, without `.html`.
REVISION_NAME = r"r(?P<revision>[1-9][0-9]*)-[a-f0-9]{16}"
VERSION_NAME = r"v(?P<version>[1-9][0-9]*)"
# The directories of a page's URL namespace beneath its root, beside its vendored
# files: its API, its browser layer, and what its session writes after a publish (the
# media it adds, the revisions it activates, the versions it stamps). The website
# adapter routes exactly these and those files to a page, and so does the Worker in
# front of it, which reads the layer and session kinds from the site manifest
# `leaf-dev site` writes: a static miss under a session directory is a file the
# page's container has. `api` is the page server's protocol prefix, which the Worker
# names with the endpoints under it.
SESSION_ROUTE_DIRS = (MEDIA_DIR, "revisions", "versions")
PAGE_ROUTE_DIRS = ("api", *BROWSER_DIRS, *SESSION_ROUTE_DIRS)
# What the server exposes from a page: the browser layer, media, immutable revisions,
# and event-backed version addresses. Agent-side instructions stay vendored but are read
# only through the CLI.
# The dir patterns are keyed by the public directories themselves, so growing
# that surface without saying what it may serve fails here, at import.
DIR_FILES = {
    "runtime": r"(?:[a-z0-9-]+/)*[a-z0-9-]+\.(?:js|css)",
    "widgets": r"(?:[a-z0-9-]+/)*[a-z0-9-]+\.js",
    "vendor": (r"(?:(?!\.{1,2}/)[A-Za-z0-9._-]+/)*" r"(?!\.{1,2}$)[A-Za-z0-9._-]+"),
    MEDIA_DIR: rf"[a-f0-9]{{{MEDIA_DIGEST}}}(?:"
    + "|".join(re.escape(e) for e in MEDIA_TYPES)
    + ")",
}
SERVED_PATH = re.compile(
    "/(?:"
    + "|".join(
        [re.escape(f) for f in VENDORED_FILES]
        + [f"{d}/{DIR_FILES[d]}" for d in (*BROWSER_DIRS, MEDIA_DIR)]
        + [rf"versions/{VERSION_NAME}\.html"]
        + [rf"revisions/{REVISION_NAME}\.html"]
    )
    + ")"
)
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".html": "text/html",
    **MEDIA_TYPES,
}
BINARY_TYPES = frozenset(MEDIA_TYPES.values()) - {"image/svg+xml"}


def agent_name(event: dict) -> str | None:
    """The name an agent-authored event is shown under, and None for any other
    author's: its posting session's `agent`, or `UNNAMED_AGENT` where it was written
    outside a host session and so carries none. The log stores no placeholder
    (`host.message_identity`); every reading that shows the event names it through
    here, so the browser, the margin, the activity feed and the transcript agree."""
    if event["author"] != "agent":
        return None
    return event.get("agent") or UNNAMED_AGENT
