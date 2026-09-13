"""Layer schema and page-directory vocabulary."""

import re
from pathlib import Path

# A session-managed server gives a replacement session one short poll window to
# claim the page before it closes. The external claim record is the ownership
# source; a standing lifetime ignores it and remains enabled until `server stop`.
ORPHAN_GRACE_SECS = 1
# How long a page whose claim carries no liveness of its own (`activity`, for a
# host that multiplexes every session into one process) stays owned after the
# last thing touched it.
#
# Sized by the longest ordinary gap between touches, which is the reader's, not
# the agent's. A visible tab renews the page every thirty seconds, but only a
# visible one: `state-feed.js` closes the news stream on `visibilitychange`, so a
# reader who opens the handover link and switches away stops touching the page
# until they come back. The gap to survive is therefore however long a page sits
# in a background tab during a working session, and minutes is the wrong unit for
# that — half an hour would take the page down under the ordinary handover.
#
# Four hours covers that and still drains: the run of stale pages this was found
# on had gone 6 to 28 hours untouched, so the throwaway previews of an afternoon
# clear overnight rather than surviving to the next app restart. A page that does
# expire is re-served by the next command that reaches it, and one meant to
# outlive its session is `--standing`.
ACTIVITY_GRACE_SECS = 4 * 60 * 60
# The kinds a reader can take back. A message is not among them: a comment is
# speech, and the agent may already have read it — what a reader regrets there
# they say, rather than unsay. A reaction is the exception the message kinds
# carry (`undo_error`): a token is a mark rather than speech, and while nothing
# has answered it the mark is one press from off the page, which is what makes
# it cheap. Nor is an undo itself, which would be a redo.
#
# `done` joins them because approval is the one press on the page with no second
# step and the heaviest meaning: a reader who meant to press Threads and hit the
# button beside it had signed the work off, and nothing on the page or in the log
# would take it back. It is a mark rather than speech by the same reading a
# reaction is — the agent is told the version is approved, not told something,
# and the withdrawal is the whole of the correction. A request is still not
# undoable, and for the reason it never was: its effect may be out of the page
# before the receipt is.
UNDOABLE_KINDS = {"resolve", "unresolve", "action", "done"}
MESSAGE_KINDS = {"comment", "reply"}
# The kinds a widget owns, admitted against the page's registry before they append.
WIDGET_KINDS = {"action", "report", "request"}
ANSWER_ASK_INSTRUCTION = (
    "`leaf page state <page>` lists each conversation's current state, and "
    "`leaf conversation read <page> <id>` prints one exact bounded history. A "
    "conversation with "
    "`response.kind: version` is answered by revising the page and resolving it; open a "
    "separate `leaf comment --section <ask-id>` on the same Ask if that revision "
    "needs an answer first. With one reply in the current opened delivery, answer "
    "through the active host's reply interface; CLI hosts use `leaf reply <page> "
    "--text ...`. When several are pending, select an event with `--for <event-id>`. "
    "An explicit reply validates and activates a changed source, and leaves the "
    "conversation open for the reader."
)
WAIT_BATCH_OUTPUT_INSTRUCTION = (
    "A wait result prints one immutable Leaf delivery envelope containing one page's "
    "complete ordered batch, conversation context, and capture-time response "
    "requirements. First run `leaf delivery claim <id>` so the page shows the exact "
    "outstanding move as Working; the same envelope remains available with `leaf "
    "delivery read <id>`."
)
ACK_BATCH_INSTRUCTION = (
    "If wait output is truncated, acknowledge nothing and rerun with enough output "
    "capacity for the whole batch. After the complete batch reaches its next durable "
    "consumer, the wait owner runs `leaf ack <page> <through-seq>` for the page and "
    "sequence the batch names. Ack advances the cursor, then waits for the next batch "
    "while the page remains live."
)
HTML_NAME = r"[a-z][a-z0-9-]*"
WIDGET_NAME = r"lf-[a-z0-9]+(?:-[a-z0-9]+)*"
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
        # Where the unit sits among its siblings. Comparison stays at the
        # container's granularity (see $state) — but a reader that has to *state*
        # a position needs both halves, and taking a move back is one: the runtime
        # reads the authored placement off the page before replay touches it, and
        # a record naming only the column would put a card back on the right list
        # in the wrong place.
        "order": {"type": "string", "minLength": 1},
    },
    "required": ["kind", "within", "value", "order"],
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
# present or absent). One condition shape serves Asks and conversations because they
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

# Current action eligibility reuses Leaf's standing-Ask projection. `self` is the
# sending widget; `owner` is the direct ownership relation its x-owners declares.
ACTION_REQUIREMENT = {
    "type": "object",
    "properties": {
        "target": {"enum": ["self", "owner"]},
        "awaiting": {"type": "boolean"},
    },
    "required": ["target", "awaiting"],
    "additionalProperties": False,
}

# A completion verb may depend on the state its own record leaves behind. `empty`
# identifies a member container inside the answering widget by its authored attributes;
# after applying the candidate record, that container must hold no vocabulary members.
# This keeps completion authoritative without adding a second completion record beside
# the state the gesture actually changed.
ACTION_COMPLETION = {
    "type": "object",
    "properties": {
        "empty": {
            "type": "object",
            "properties": {
                "within": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
                "when": AWAITING_CONDITION,
            },
            "required": ["within", "when"],
            "additionalProperties": False,
        }
    },
    "required": ["empty"],
    "additionalProperties": False,
}

ACTION_CREATES = {
    "type": "object",
    "properties": {
        "field": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "child": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
    },
    "required": ["field", "child"],
    "additionalProperties": False,
}


def _verbs_schema(
    records: list,
    required: list,
    *,
    conditional: bool = False,
    updates: bool = False,
) -> dict:
    """The shape x-state and x-report share: verbs to
    {detail, facet, unit, record}, differing only in which record forms a
    channel admits, whether one is required at all, and whether the reader's
    channel may declare current applicability or the agent's may declare update
    prose."""
    properties = {
        "detail": {"type": "object"},
        "facet": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "unit": {"type": "string", "minLength": 1},
        "record": {"oneOf": records},
        "references": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            "uniqueItems": True,
        },
    }
    if conditional:
        properties["requires"] = ACTION_REQUIREMENT
        properties["creates"] = ACTION_CREATES
        properties["completion"] = ACTION_COMPLETION
    if updates:
        # A report may carry one short prose update beside the structured state it
        # records. Naming the detail field is what lets the common update feed expose
        # those words without guessing from a widget, verb, or field name.
        properties["update"] = {
            "type": "string",
            "pattern": f"^{HTML_NAME}$",
        }
    return {
        "type": "object",
        "minProperties": 1,
        "propertyNames": {"pattern": f"^{HTML_NAME}$"},
        "additionalProperties": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


STATE_SCHEMA = _verbs_schema(
    [_RECORD_ATTRIBUTE, _RECORD_POSITION, _RECORD_BODY, _RECORD_VALUE],
    ["detail", "facet", "unit"],
    conditional=True,
)
# A report moves declared state only, never body words — no body record, so the
# passage reading never has to model one — and the record itself is required:
# the gate compares record forms, and a recordless report would be a claim
# nothing could check a version against.
REPORT_SCHEMA = _verbs_schema(
    [_RECORD_ATTRIBUTE, _RECORD_POSITION, _RECORD_VALUE],
    ["detail", "facet", "unit", "record"],
    updates=True,
)
# A request is a one-shot instruction for the host, not state the browser can replay.
# Its declaration owns the authored offer relation and the typed payload, but no replay
# form. The linked receipt carries the closed, layer-wide outcome envelope;
# host-specific evidence belongs in external data.
REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "ask": {"type": "boolean"},
        # This request supplies the commands but not its own question title.
        # A matching holder therefore stands inside an x-ask-surface region, whose direct
        # heading owns the reading and arrival.
        "region": {"const": True},
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
    "required": ["offers", "verbs"],
    "additionalProperties": False,
}
AWAITS_SCHEMA = {
    "type": "object",
    "properties": {
        "when": AWAITING_CONDITION,
        "answers": {
            "type": "array",
            "items": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            "minItems": 1,
            "uniqueItems": True,
        },
        "rollup": {"const": True},
        # This widget supplies the answer control but not its own question title.
        # A matching instance therefore stands inside an x-ask-surface region, whose direct
        # heading owns the reading and arrival.
        "region": {"const": True},
        "all": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "until": {
            "type": "object",
            "properties": {
                "verb": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                "when": AWAITING_CONDITION,
            },
            "required": ["verb", "when"],
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
# A list of the widget's own attribute names. One shape for the three keys that hold
# one, since the shape is a consequence of what they name rather than three decisions.
WORK_SCHEMA = {
    "type": "object",
    "properties": {
        "seat": {"enum": ["content", "conversation"]},
        "when": AWAITING_CONDITION,
    },
    "required": ["seat"],
    "additionalProperties": False,
}

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
            "snapshot": {"type": "string", "pattern": f"^{HTML_NAME}$"},
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
        # The widget attribute holding the source snapshot's recorded instant.
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
REFERENCE_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            # A package-owned relation can constrain its target through any shared
            # registry map. Leaf understands only the path and equality predicate;
            # `$command.widgets` and its roles remain entirely package vocabulary.
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
        "x-conversation": {
            "type": "object",
            "properties": {
                "when": AWAITING_CONDITION,
                "hold": {"type": "string", "minLength": 1},
                "response": {
                    "type": "object",
                    "properties": {
                        "kind": {"const": "version"},
                        "verb": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                    },
                    "required": ["kind", "verb"],
                    "additionalProperties": False,
                },
            },
            "required": ["when"],
            "additionalProperties": False,
        },
        "x-required-members": CHILDREN_SCHEMA,
        "x-content": {"enum": ["markup", "members", "data", "empty"]},
        "x-data": DATA_INPUTS_SCHEMA,
        "x-example": {"type": "string"},
        "x-exhibit": {"type": "boolean"},
        "x-guidance": GUIDANCE_SCHEMA,
        "x-inline": {"type": "boolean"},
        "x-language": _ATTRIBUTE_NAME,
        "x-reading-role": {"enum": ["workspace", "pane", "partition"]},
        # Attributes holding 1-based line references into the nearest data body —
        # the element's own <pre>, or its enclosing data element's (lf-note's `at` names a line of
        # its lf-code). `version check` refuses one outside the body (line_ref_errors).
        "x-lines": _ATTRIBUTE_LIST,
        "x-measured": MEASURED_SCHEMA,
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
        "x-report": REPORT_SCHEMA,
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
            ]
        },
        "x-space": {"enum": ["wide", "available"]},
        "x-withdrawn-as": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "x-word": {"enum": ["module"]},
        "x-work": WORK_SCHEMA,
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
ATTRIBUTE_KEYS = ("x-language", "x-lines", "x-paints", "x-refers", "x-says", "x-tone")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = SKILL_ROOT.parent.parent
ASSETS = SKILL_ROOT / "assets"
BUNDLED_PACKAGES = SKILL_ROOT / "packages"
DEFAULT_PACKAGE = BUNDLED_PACKAGES / "default"
# Outside the layer roots: an MCP host reads a resource here from the install over
# the tool transport, so `page init` never copies one into a page directory.
MCP_APP = SKILL_ROOT / "mcp-app"
VENDORED_FILES = ("leaf.js", "theme.css", "registry.json", "icon.svg")
BROWSER_DIRS = ("runtime", "widgets", "vendor")
GUIDANCE_DIR = "guidance"
PACKAGE_DIRS = (*BROWSER_DIRS, GUIDANCE_DIR)
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
    PREVIEW_FILE,
)
PAGE_OWNED_FILES = ("index.html", *VENDORED_FILES, *PAGE_STATE_FILES)
PAGE_OWNED_DIRS = ("revisions", *PACKAGE_DIRS, MEDIA_DIR)
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
