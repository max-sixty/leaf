"""Layer schema and page-directory vocabulary."""

import re
from pathlib import Path

# A session-managed server gives a replacement session one short poll window to
# claim the page before it closes. The external claim record is the ownership
# source; a standing lifetime ignores it and remains enabled until `server stop`.
ORPHAN_GRACE_SECS = 1
# Activity-backed claims must survive time in a background tab, which stops
# renewing viewed.json. Four hours permits those gaps while retiring abandoned
# session pages. Claim renewal and service lifetime: session-lifetime.md.
ACTIVITY_GRACE_SECS = 4 * 60 * 60
# Harness-neutral label when no claimant supplies a name. context.js uses the
# same label before a browser has an authoritative state, including exports.
UNCLAIMED_AGENT = "Agent"
# Non-message gesture kinds eligible for withdrawal; events.undo_error handles
# reactions. The complete eligibility contract is events.md, "Undo".
UNDOABLE_KINDS = {"resolve", "unresolve", "action", "done"}
MESSAGE_KINDS = {"comment", "reply"}
# The kinds a widget owns, admitted against the page's registry before they append.
WIDGET_KINDS = {"action", "report", "request"}
# The operations that settle a user move the agent owes, as `workflows` and
# `activity` address them and `$events.answering` explains them. A `turn` answer is
# a thread reply the claimant's turn writes with its own opening and final messages.
ANSWER_KINDS = ("reply", "turn", "markup", "receipt")
# The answer kinds that post a message in a thread.
THREAD_ANSWER_KINDS = frozenset({"reply", "turn"})
ANSWER_ASK_INSTRUCTION = (
    "Each move takes the answer named for it. Read current obligations with `leaf page state <page>` and thread history with "
    "`leaf thread read <page> <id>`."
)
WAIT_BATCH_OUTPUT_INSTRUCTION = (
    "Print one page's complete ordered batch, thread context, and response "
    "requirements as an immutable delivery, whose `acknowledge` says how to confirm "
    "it. `leaf delivery read <id>` reads that same delivery."
)

HTML_NAME = r"[a-z][a-z0-9-]*"
WIDGET_NAME = r"lf-[a-z0-9]+(?:-[a-z0-9]+)*"
# What a refused element name is told, so the author need not read WIDGET_NAME.
WIDGET_NAME_RULE = (
    "an element name is `lf-` followed by hyphen-separated words of lowercase "
    f"letters and digits, such as `lf-merge-film` ({WIDGET_NAME})"
)
ELEMENT_ID = r"[a-z0-9][a-z0-9-]*"
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
        },
        "dependentRequired": {"via": ["where"], "where": ["via"]},
        "additionalProperties": False,
    },
}


# Each verb is {detail, unit, record}. `writer: "agent"` makes it a verb the agent
# reports through `leaf experimental report` rather than one the user acts on;
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
# A request is a one-shot instruction for the host, not state the browser can replay.
# Its declaration owns the offered verbs and typed payload, but no replay form.
# Authored holders name child offers; projected holders offer their verbs directly.
# The linked receipt carries the closed, layer-wide outcome envelope;
# host-specific evidence belongs in external data.
REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "ask": {"type": "boolean"},
        # This request supplies the commands but not its own question title.
        # A matching holder therefore stands inside an x-ask-surface region, whose direct
        # heading owns the reading and arrival.
        "region": {"const": True},
        "records": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "offers": {
            "type": "object",
            "minProperties": 1,
            "propertyNames": {"pattern": f"^{WIDGET_NAME}$"},
            "additionalProperties": {
                "type": "string",
                "pattern": f"^{HTML_NAME}$",
            },
        },
        "verbs": {
            "type": "object",
            "minProperties": 1,
            "propertyNames": {"pattern": f"^{HTML_NAME}$"},
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "detail": {"type": "object"},
                    "unit": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                    "bind": {
                        "type": "object",
                        "minProperties": 1,
                        "propertyNames": {"pattern": f"^{HTML_NAME}$"},
                        "additionalProperties": {
                            "type": "string",
                            "pattern": f"^{HTML_NAME}$",
                        },
                    },
                },
                "required": ["detail"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verbs"],
    "additionalProperties": False,
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
# A list of the widget's own attribute names. One shape for the three keys that hold
# one, since the shape is a consequence of what they name rather than three decisions.
GUIDANCE_SCHEMA = {
    "type": "object",
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {"type": "string", "minLength": 1},
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
        "x-guidance": GUIDANCE_SCHEMA,
        "x-inline": {"type": "boolean"},
        "x-language": _ATTRIBUTE_NAME,
        "x-reading-role": {"enum": ["workspace", "pane", "grid"]},
        # Attributes holding line references into the nearest data body — the element's
        # own <pre>, or its enclosing data element's (lf-note's `at` names a line of its
        # lf-code) — by the numbers x-numbering gives that body, 1-based without it.
        # `version check` refuses one outside the body (line_ref_errors).
        "x-lines": _ATTRIBUTE_LIST,
        "x-numbering": _ATTRIBUTE_NAME,
        "x-measured": MEASURED_SCHEMA,
        # Whole-page view navigation when the element is the last root after no more
        # than one native header. The outline advice recognizes this authored shape.
        "x-page-navigation": {"const": True},
        # The element that lists the page's own headings. `version check` advises a
        # page with two or more headings and no such element (missing_outline).
        "x-outline": {"const": True},
        # Attributes the theme renders as paint alone — a status marker's tint or an
        # event's kind. The runtime speaks each as a clipped word (renderQuiet), the
        # value or, where a flag carries no value, the attribute's own name.
        "x-paints": _ATTRIBUTE_LIST,
        "x-owners": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
            "minItems": 1,
        },
        "x-refers": REFERENCE_SCHEMA,
        "x-request": REQUEST_SCHEMA,
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
                    "properties": {"parts": _ATTRIBUTE_NAME},
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
        "x-measure": {"enum": ["surface", "group"]},
        "x-bound": {"enum": ["start", "end"]},
        "x-history": {"const": True},
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

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = SKILL_ROOT.parent.parent
ASSETS = SKILL_ROOT / "assets"
BUNDLED_PACKAGES = SKILL_ROOT / "packages"
DEFAULT_PACKAGE = BUNDLED_PACKAGES / "default"
# Outside the layer roots: an MCP host reads a resource here from the install over
# the tool transport, so `page init` never copies one into a page directory.
MCP_APP = SKILL_ROOT / "mcp-app"
VENDORED_FILES = ("leaf.js", "theme.css", "shadow.css", "registry.json", "icon.svg")
BROWSER_DIRS = ("runtime", "widgets", "vendor")
GUIDANCE_DIR = "guidance"
PACKAGE_DIRS = (*BROWSER_DIRS, GUIDANCE_DIR)
# A package's own command-line tools, run by `leaf package run` from wherever the
# package is installed or bundled. A page never vendors them: they are the agent's.
SCRIPTS_DIR = "scripts"
GUIDANCE_FILE = re.compile(rf"{HTML_NAME}\.md")
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
NO_KEY = "open the link leaf printed; it carries the key"
DATA_FILE = "data.json"
DATA_DIR = "data"
EVENTS_FILE = "events.jsonl"
PREVIEW_FILE = "preview.json"
VIEWED_FILE = "viewed.json"
# One name, because there is one key (`host_key`). Cookies are scoped by host and
# blind to the port, so every page this machine serves shares a jar — on 127.0.0.1,
# with every other server the user has running, which is what the prefix is for.
KEY_COOKIE = "lf_key"
STATUS_FILE = "status.json"
CURSOR_FILE = "cursor.json"
SERVICE_FILE = "service.json"
SERVER_LOCK = "server.lock"
RESTART_LOCK = "restart.lock"
WAITER_LOCK = "waiter.lock"
PAGE_STATE_FILES = (
    EVENTS_FILE,
    STATUS_FILE,
    DATA_FILE,
    WAITER_LOCK,
    CURSOR_FILE,
    VIEWED_FILE,
    SERVICE_FILE,
    SERVER_LOCK,
    RESTART_LOCK,
    PREVIEW_FILE,
)
PAGE_OWNED_FILES = ("index.html", *VENDORED_FILES, *PAGE_STATE_FILES)
PAGE_OWNED_DIRS = ("revisions", *PACKAGE_DIRS, MEDIA_DIR, DATA_DIR, "page")
# What the server exposes from a page: the browser layer, media, immutable revisions,
# and event-backed version addresses. Agent-side guidance stays vendored but is read
# only through the CLI.
# The dir patterns are keyed by the public directories themselves, so growing
# that surface without saying what it may serve fails here, at import.
DIR_FILES = {
    "runtime": r"(?:[a-z0-9-]+/)*[a-z0-9-]+\.(?:js|css)",
    "widgets": r"(?:[a-z0-9-]+/)*[a-z0-9-]+\.js",
    "vendor": (r"(?:(?!\.{1,2}/)[A-Za-z0-9._-]+/)*" r"(?!\.{1,2}$)[A-Za-z0-9._-]+"),
    MEDIA_DIR: r"[a-f0-9]{16}(?:" + "|".join(re.escape(e) for e in MEDIA_TYPES) + ")",
}
SERVED_PATH = re.compile(
    "/(?:"
    + "|".join(
        [re.escape(f) for f in VENDORED_FILES]
        + [f"{d}/{DIR_FILES[d]}" for d in (*BROWSER_DIRS, MEDIA_DIR)]
        + [r"versions/v[1-9][0-9]*\.html"]
        + [r"revisions/r[1-9][0-9]*-[a-f0-9]{16}\.html"]
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
