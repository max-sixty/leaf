"""Layer schema, browser/package resource paths, and page-directory vocabulary.

Resources belong to the installed plugin; the skill directory holds instructions.
"""

import re

from .state import EVENTS_FILE, PLUGIN_ROOT, kernel_registry

ASSETS = PLUGIN_ROOT / "browser"
SKILL_FILE = PLUGIN_ROOT / "skills" / "leaf" / "SKILL.md"

# A session-managed server gives a replacement session one short poll window to
# claim the page before it closes. The external claim record is the ownership
# source; a persistent lifetime ignores it and remains enabled until `server stop`.
ORPHAN_GRACE_SECS = 1
# The harness-neutral name of an agent nothing names: a page's when no claimant
# supplies one, and an agent-authored event's that carries no `agent` (`agent_name`).
UNNAMED_AGENT = "Agent"
ANSWER_INSTRUCTION = (
    "`leaf page state <page>` lists what is owed, and "
    "`leaf page state <page> <message>` reads a thread's history."
)
WAIT_BATCH_OUTPUT_INSTRUCTION = (
    "Print one page's complete ordered batch, thread context, and response "
    "requirements as an immutable delivery, whose `acknowledge` says how to confirm "
    "it. `leaf delivery read <id>` reads that same delivery. Where the harness's hook "
    "carries input into the turn, as in Claude Code, print one line naming the page "
    "with new input instead, and end."
)

# The name grammars, declared in the kernel registry's `$names`, which the browser
# reads too.
_NAMES = kernel_registry()["$names"]
HTML_NAME = _NAMES["html"]
WIDGET_NAME = _NAMES["widget"]
# What a refused element name is told, so the author need not read WIDGET_NAME.
WIDGET_NAME_RULE = (
    "an element name is `lf-` followed by hyphen-separated words of lowercase "
    f"letters and digits, such as `lf-merge-film` ({WIDGET_NAME})"
)
# The grammars of the names Leaf looks up from a widget's attributes: an element id, a
# data source and a data contract. Composition writes each into the attributes that
# hold one (`registry.contract.stamp_grammars`), so no package declaration restates
# one. The browser checks none of them.
ELEMENT_ID = r"[a-z0-9][a-z0-9-]*"
DATA_SOURCE_NAME = HTML_NAME
DATA_CONTRACT_NAME = r"[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)*"
# An id the log mints for an event. Page ids and event ids are one address space:
# a command's ID is a widget or a message, whichever the page holds, so an authored
# id may not take this shape (`validation.markup.id_errors`).
EVENT_ID = r"[0-9a-f]{8}"
# The record forms one vocabulary of declared state draws on ($state in the
# registry): how a unit's state reads in markup, each dispatched on by the gate,
# the runtime, and the diff without any of them knowing a widget by name.
_RECORD_ATTRIBUTE = {
    "type": "object",
    "properties": {
        "kind": {"const": "attribute"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["kind", "attr"],
    "additionalProperties": False,
}
_RECORD_POSITION = {
    "type": "object",
    "properties": {
        "kind": {"const": "position"},
        "within": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
    },
    "required": ["kind", "within"],
    "additionalProperties": False,
}
_RECORD_BODY = {
    "type": "object",
    "properties": {"kind": {"const": "body"}},
    "required": ["kind"],
    "additionalProperties": False,
}
_RECORD_VALUE = {
    "type": "object",
    "properties": {
        "kind": {"const": "value"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["kind", "attr"],
    "additionalProperties": False,
}

# A `when` predicate selects instances by string attribute values or, with a
# boolean, by an attribute's presence or absence. One condition shape serves
# obligations and threads because they ask the same question of authored attributes.
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

# When a local obligation is answered: a map from each answering `server.state` verb to
# the condition its current state meets. An empty condition means the verb's state
# stands (a non-empty attribute or value record, otherwise an action in force). `when`
# narrows the verb to instances whose attributes match; `empty` holds when the one
# member container it names inside the widget is left with no members by the current
# positions. One map, so every answer is a reading of state the fold already keeps.
ANSWERED_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {
        "type": "object",
        "properties": {
            "when": AWAITING_CONDITION,
            "detail": {"type": "object", "minProperties": 1},
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
        "dependentRequired": {
            "via": ["where"],
            "where": ["via"],
            "owns": ["via"],
        },
        "additionalProperties": False,
    },
}


# A custom detail carries exactly the keys its declaration spells. Field meanings
# such as `resolves` read those declarations, so patternProperties and combinators
# cannot admit unnamed keys. `registry.schema.check_schema` validates the nested
# schemas and the standard keywords left unrestricted here.
_VERB_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"const": "object"},
        "properties": {},
        "required": {},
        "additionalProperties": {"const": False},
    },
    "required": ["type", "additionalProperties"],
    "additionalProperties": False,
}

# Each verb declares its coordinate and a recorded effect or custom detail schema.
# `writer: "agent"` makes it a report through `leaf page report`; otherwise the
# user writes it. The writers differ in what their state may be, not its shape. The
# served state hands the browser each admitted event's verb in this shape, and the
# browser build generates its type from this schema (`build/browser/contract-types.mjs`).
VERB_SCHEMA = {
    "type": "object",
    "properties": {
        "detail": _VERB_DETAIL_SCHEMA,
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
        "attention": {"const": True},
        "unsent": {"const": True},
        "creates": ACTION_CREATES,
        "decides": {"const": True},
        # The deciding verb's outcome that declines the proposal (`$state`).
        "withdraws": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "contract": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "minLength": 1},
                "attribute": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            },
            "required": ["field", "attribute"],
            "additionalProperties": False,
        },
        # The effect owns the payload; `text` adds a required non-empty detail.text.
        "text": {"const": True},
    },
    "required": ["unit"],
    "dependentRequired": {"withdraws": ["decides"]},
    "allOf": [
        {
            "if": {"required": ["record"]},
            "then": {
                "properties": {
                    "detail": False,
                    "creates": False,
                    "contract": False,
                    "decides": False,
                }
            },
            "else": {"required": ["detail"]},
        },
        # Unsent work asks for nothing, so it can't also be a request.
        {"not": {"required": ["attention", "unsent"]}},
    ],
    "additionalProperties": False,
    # An agent's verb moves declared state only, never body words — so the
    # passage reading never has to model one — and never a part's place, which
    # the stamped version owns and a rank reads between the neighbours a widget
    # shows the user. Its record is required: the gate compares record forms,
    # and a recordless report would be a claim nothing could check a version
    # against. Only the user adds children, and only an agent verb
    # declares `text`.
    "if": {"required": ["writer"]},
    "then": {
        "required": ["record"],
        "properties": {
            "record": {"properties": {"kind": {"enum": ["attribute", "value"]}}},
            "creates": False,
        },
    },
    "else": {"properties": {"text": False}},
}
STATE_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": VERB_SCHEMA,
}
# A widget's obligation is answered by its own state (`value` and `answered`).
AWAITS_SCHEMA = {
    "type": "object",
    "properties": {
        "when": AWAITING_CONDITION,
        "value": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "answered": ANSWERED_SCHEMA,
        "records": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                "label": {"type": "string", "minLength": 1},
            },
            "required": ["input", "label"],
            "additionalProperties": False,
        },
        "all": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "retired": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "key": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["value", "answered"],
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
            "reference": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            "output": {"type": "string", "pattern": f"^{HTML_NAME}$"},
            # The element property the runtime sets to the delivered value
            # (element-data.js, "Bound values").
            "property": {"type": "string", "pattern": "^[a-z][A-Za-z0-9]*$"},
            # The widget attribute holding the receipt of the source's run that
            # produced the value written in the element's content.
            "measured": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        },
        "dependentRequired": {"reference": ["output"], "output": ["reference"]},
        "required": ["contract"],
        "anyOf": [{"required": ["source"]}, {"required": ["reference", "output"]}],
        "additionalProperties": False,
    },
}

_ATTRIBUTE_NAME = {"type": "string", "pattern": f"^{HTML_NAME}$"}
_TAGS = {
    "type": "array",
    "items": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
    "minItems": 1,
}


def _declares(group: str, *names: str) -> dict:
    """A declaration that declares each of `names` in `group`."""
    return {"required": [group], "properties": {group: {"required": list(names)}}}


def _facts(properties: dict, **schema) -> dict:
    """One group of a declaration's facts: the facts one reader needs."""
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
        **schema,
    }


# The author's half of a declaration: how an author writes the element. A selector
# idiom declares only this and its description (`IDIOM_SCHEMA`).
_AUTHOR = _facts(
    {
        "example": {"type": "string", "pattern": r"\S"},
        "instructions": {"type": "string", "pattern": r"\S"},
    }
)
# An element declaration: the JSON Schema of its attributes, and each fact about the
# element that a part of Leaf which never runs its module needs, grouped by that
# reader. `$keys` in the kernel package's registry says what each means.
DECLARATION_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string", "pattern": r"\S"},
        # A JSON Schema, held to Draft 2020-12 apart (`registry.widgets`). The two
        # keywords Leaf's readers take an attribute's own schema and presence from are
        # named, so the browser's types know them.
        "attributes": {
            "type": "object",
            "properties": {
                "properties": {"type": "object"},
                "required": {"type": "array", "items": {"type": "string"}},
            },
        },
        "content": {"enum": ["markup", "members", "data", "empty"]},
        "data": _facts(
            {
                "inputs": DATA_INPUTS_SCHEMA,
                "outputs": {
                    "type": "object",
                    "minProperties": 1,
                    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "contract": {
                                "type": "string",
                                "pattern": f"^{DATA_CONTRACT_NAME}$",
                            }
                        },
                        "required": ["contract"],
                        "additionalProperties": False,
                    },
                },
            }
        ),
        "markup": _facts(
            {
                "owners": _TAGS,
                "unique": {
                    "type": "object",
                    "minProperties": 1,
                    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
                    "additionalProperties": {
                        "type": "string",
                        "pattern": f"^{WIDGET_NAME}$",
                    },
                },
                "refers": REFERENCE_SCHEMA,
                "reading-role": {"enum": ["pane"]},
            }
        ),
        "words": _facts(
            {
                "says": {
                    "type": "object",
                    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
                    "additionalProperties": {"enum": ["before", "after"]},
                },
                "verbatim": {"type": "boolean"},
                "shadow": {"type": "boolean"},
                "inline": {"type": "boolean"},
                "visual": {
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
                "text-format": {"const": "markdown"},
            }
        ),
        "paint": _facts(
            {
                "views": {
                    "type": "object",
                    "properties": {
                        "members": {"type": "string", "minLength": 1},
                        "parts": {"const": True},
                    },
                    "required": ["members"],
                    "additionalProperties": False,
                },
                "space": {"enum": ["wide", "available"]},
                # A default height in CSS pixels, or `true` for a widget that has none
                # and reserves only what an occurrence's data-height states.
                "height": {
                    "oneOf": [{"const": True}, {"type": "integer", "minimum": 1}]
                },
                "bound": {"enum": ["start", "end"]},
                "spine": {"const": True},
                "flow": {"const": True},
                "prepaint": _ATTRIBUTE_NAME,
            }
        ),
        "server": _facts(
            {
                "state": STATE_SCHEMA,
                "awaits": AWAITS_SCHEMA,
                "retired-when": {"type": "string", "pattern": f"^{HTML_NAME}$"},
                "encloses": {"const": True},
                "exhibit": {
                    "oneOf": [
                        {"type": "boolean"},
                        {
                            "type": "object",
                            "properties": {"when": AWAITING_CONDITION},
                            "required": ["when"],
                            "additionalProperties": False,
                        },
                    ]
                },
                # A view of another widget's answer (`shown_answers.py`): `attr` names
                # that widget, and `value` the attribute of the view's compound owner
                # that names the answer it holds.
                "shows": {
                    "type": "object",
                    "properties": {"attr": _ATTRIBUTE_NAME, "value": _ATTRIBUTE_NAME},
                    "required": ["attr", "value"],
                    "additionalProperties": False,
                },
                "work": {"const": True},
                "history": {"const": True},
            }
        ),
        "author": _AUTHOR,
    },
    "required": ["description"],
    # A member that leaves under its owner's decision, or a view of another widget's
    # answer, is read through the owners it names, and a view through its reference.
    "allOf": [
        {
            "if": _declares("server", "retired-when"),
            "then": _declares("markup", "owners"),
        },
        {
            "if": _declares("server", "shows"),
            "then": _declares("markup", "owners", "refers"),
        },
    ],
    "additionalProperties": False,
}
# A selector idiom names authored HTML the theme dresses, so it says only how an
# author writes it, and declares no widget behavior or marks
# (`revision_delivery.mark_declared`).
IDIOM_SCHEMA = {
    "type": "object",
    "properties": {
        "description": DECLARATION_SCHEMA["properties"]["description"],
        "author": {**_AUTHOR, "required": ["example"]},
    },
    "required": ["description", "author"],
    "additionalProperties": False,
}
_NONEMPTY = {"type": "string", "minLength": 1}
_UNIQUE_NAMES = {"type": "array", "items": {"type": "string"}, "uniqueItems": True}
# A delivered event's handling or answering instructions: what every batch carries.
_CLAUSES = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "properties": {"text": {"type": "string", "pattern": r"\S"}, "when": {}},
        "required": ["text"],
        "additionalProperties": False,
    },
}
# The shape of each shared layer fact a complete vocabulary carries, every one
# required and each held to its schema on its own (`registry.validation.check_layer_facts`).
# Its consumers read each directly: a string `$tones.names` would answer the tone
# check's membership test by substring, and a token without a `glyph` paints nothing.
# What names another fact, or needs more than a shape (a clause's `when` and a
# contract's `schema` are JSON Schemas, `resources` are JMESPath), the same module's
# `validate_layer_declarations` checks.
LAYER_FACTS = {
    "$events": {
        "type": "object",
        "properties": {
            "kinds": {"type": "object"},
            "handling": {"type": "object", "additionalProperties": _CLAUSES},
            "answering": {"type": "object", "additionalProperties": _CLAUSES},
        },
        "required": ["kinds", "handling", "answering"],
    },
    "$languages": {
        "type": "object",
        "properties": {
            "names": _UNIQUE_NAMES,
            "paths": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": ["names", "paths"],
    },
    "$tones": {
        "type": "object",
        "properties": {"names": _UNIQUE_NAMES},
        "required": ["names"],
    },
    "$data": {
        "type": "object",
        "properties": {
            "description": _NONEMPTY,
            "contracts": {
                "type": "object",
                "propertyNames": {"pattern": f"^(?:{DATA_CONTRACT_NAME})$"},
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "description": _NONEMPTY,
                        "schema": {"type": "object"},
                        "instructions": INSTRUCTIONS_SCHEMA,
                        # Null reads as absent (`data_contracts.payload_error`).
                        "records": {
                            "type": ["object", "null"],
                            "properties": {
                                "items": _NONEMPTY,
                                "key": _NONEMPTY,
                            },
                            "required": ["items", "key"],
                            "additionalProperties": False,
                        },
                        "resources": {"type": "array", "items": _NONEMPTY},
                    },
                    "required": ["description", "schema"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["description", "contracts"],
        "additionalProperties": False,
    },
    "$reactions": {
        "type": "object",
        "properties": {
            "tokens": {
                "type": "object",
                "propertyNames": {"pattern": f"^(?:{HTML_NAME})$"},
                "additionalProperties": {
                    "type": "object",
                    # A glyph is a mark: at most four code points.
                    "properties": {
                        "glyph": {
                            "type": "string",
                            "pattern": r"\S",
                            "maxLength": 4,
                        },
                        "settles": {"type": "boolean"},
                    },
                    "required": ["glyph"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["tokens"],
    },
}
# The facts whose value names attributes of the widget's own schema, in whichever shape
# each carries the names: a list, a mapping keyed by them, or one name. One rule for all
# of them, because the failure is one — the attribute is absent, so the pass reading the
# fact finds nothing and does nothing, and the widget is simply missing from it with no
# error anywhere (validate_registry holds every fact here to the entry's attributes).
# server.retired-when, of the same shape, is not in it: it names an outcome rather than
# an attribute, and sharing a spelling is no reason to share a check. server.awaits and
# data.inputs name attributes too and keep their own loops, having more to say about
# each than that it exists.
ATTRIBUTE_FACTS = (
    "paint.prepaint",
    "markup.refers",
    "words.says",
    "markup.unique",
)

# The kernel compiled from ASSETS's modules (`runtime_selection.read_runtime`).
KERNEL = PLUGIN_ROOT / "dist" / "kernel"
BUNDLED_PACKAGES = PLUGIN_ROOT / "packages"
DEFAULT_PACKAGE = BUNDLED_PACKAGES / "default"
# A page's layer record (`registry.storage.LAYER`): the packages it selects.
LAYER_FILE = "layer.json"
# The top-level files a composed layer serves beside the page (`layer.compose_layer`).
LAYER_TOP_FILES = (
    "theme.css",
    "shadow.css",
    "chrome.css",
    "portable.css",
    "registry.json",
    "icon.svg",
)
# The kernel's sheets, each composed into its own cascade tier
# (`layer.composed_sheets`), and every file of the kernel's a layer reads.
KERNEL_STYLES = ("shadow.css", "base.css", "layouts.css", "state.css")
KERNEL_FILES = (*KERNEL_STYLES, "registry.json", "icon.svg")
# A package's source contributions are composed into the page files above. Their
# roles depend on their filenames, not on whether the package declares widgets.
PACKAGE_STYLES = (
    "widget-shadow.css",
    "defaults.css",
    "overrides.css",
    "chrome.css",
)
PACKAGE_FILES = (*PACKAGE_STYLES, "registry.json", "icon.svg")
# The layer's browser directories, which packages add to.
BROWSER_DIRS = ("runtime", "widgets", "vendor")
# What the Leaf serving a page supplies beside the layer it composes: the runtime's
# entry and ASSETS's files under these directories (`runtime_selection`).
RUNTIME_ENTRY = "leaf.js"
RUNTIME_DIRS = ("runtime", "vendor")
INSTRUCTIONS_DIR = "instructions"
PACKAGE_DIRS = (*BROWSER_DIRS, INSTRUCTIONS_DIR)
# A package's own command-line tools, run by `leaf package run` from wherever the
# package is installed or bundled. A page never copies them: they are the agent's.
SCRIPTS_DIR = "scripts"
INSTRUCTIONS_FILE = re.compile(rf"{HTML_NAME}\.md")
# Media the page shows, named by the hash of their bytes (`page media`). They are the
# page's content, not the layer's, but served like it, and the
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
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
}
# A media file's name is the first MEDIA_DIGEST hex characters of its bytes' SHA-256
# and a lowercase MEDIA_TYPES suffix: `media.media_name` mints it, `DIR_FILES` serves
# it, and the agent's reference doors refuse any other name under `/media/`. The
# browser and the Worker know the directory and never the name.
MEDIA_DIGEST = 16
NO_KEY = "open the link leaf printed; it carries the key"
FILE_BINDINGS_FILE = "files.json"
DATA_DIR = "data"
# The page's copies of the packages it selects by path (`vendoring`), which every
# Leaf reading the page composes in place of a directory only `page init` could see.
PACKAGES_DIR = "packages"
# The diagnostic request and interaction trace (`interaction_log.py`).
INTERACTIONS_FILE = "observations.jsonl"
PREVIEW_FILE = "preview.json"
USER_VIEWS_FILE = "user-views.json"
USER_VIEWS_LOCK = "user-views.lock"
DRAFTS_FILE = "drafts.json"
DRAFTS_LOCK = "drafts.lock"
RENDER_CHECKS_DIR = "checks"
# How long a bare address stays authorized after the last handover link (`host_key`),
# the lifetime Jupyter gives its login cookie.
KEY_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
STREAM_FILE = "stream.json"
SERVICE_FILE = "service.json"
SERVER_LOCK = "server.lock"
WAITER_LOCK = "waiter.lock"
# What a page records about who is working on it and how it is served, as against what
# its author wrote (the source) and what it has accumulated (the log and its revisions).
# Neither validation nor a revision's capture reads these, so a write to one is news to
# an open tab and never a candidate revision.
SESSION_FILES = (
    STREAM_FILE,
    WAITER_LOCK,
    USER_VIEWS_FILE,
    USER_VIEWS_LOCK,
    DRAFTS_LOCK,
    SERVICE_FILE,
    SERVER_LOCK,
    PREVIEW_FILE,
)
# Process declarations, leases, browser observations and diagnostics are disposable.
PAGE_PROCESS_FILES = (*SESSION_FILES, INTERACTIONS_FILE)
# The files Leaf writes in a page directory as it runs. With the author's index.html
# and PAGE_OWNED_DIRS, the whole of page-storage.md's "Files".
PAGE_STATE_FILES = (
    LAYER_FILE,
    EVENTS_FILE,
    INTERACTIONS_FILE,
    FILE_BINDINGS_FILE,
    # The user's unsent words, which outlive the process serving them as the log does
    # (`drafts.py`), though no reading of the page counts them (`reading.UNWATCHED`).
    DRAFTS_FILE,
    *SESSION_FILES,
)
PAGE_OWNED_FILES = ("index.html", *PAGE_STATE_FILES)
PAGE_OWNED_DIRS = ("revisions", MEDIA_DIR, DATA_DIR, "page", PACKAGES_DIR)
# A revision's and a version's file name, without `.html`.
REVISION_NAME = r"r(?P<revision>[1-9][0-9]*)-[a-f0-9]{16}"
VERSION_NAME = r"v(?P<version>[1-9][0-9]*)"
# The directories of a page's URL namespace beneath its root, beside its layer's top
# files: its API, its browser layer, and what its session writes after a publish (the
# media it adds, the revisions it activates, the versions it stamps). The website
# adapter routes exactly these and those files to a page, and so does the Worker in
# front of it, which reads the layer and session kinds from the site manifest
# `leaf-dev site build` writes: a static miss under a session directory is a file the
# page's container has. `api` is the page server's protocol prefix, which the Worker
# names with the endpoints under it.
SESSION_ROUTE_DIRS = (MEDIA_DIR, "revisions", "versions", RENDER_CHECKS_DIR)
PAGE_ROUTE_DIRS = ("api", *BROWSER_DIRS, *SESSION_ROUTE_DIRS)
CONTENT_TYPES = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".html": "text/html",
    **MEDIA_TYPES,
}
JAVASCRIPT_SUFFIXES = frozenset(
    suffix for suffix, mime in CONTENT_TYPES.items() if mime == "application/javascript"
)
MODULE_EXTENSION = (
    "(?:" + "|".join(re.escape(suffix) for suffix in sorted(JAVASCRIPT_SUFFIXES)) + ")"
)
# Helper modules have package-owned names; only widget entry names follow tag syntax.
# Share safe path segments with vendor files, excluding traversal segments.
BROWSER_FILE = r"(?:(?!\.{1,2}/)[^/\\\x00-\x1f]+/)*(?!\.{1,2}$)[^/\\\x00-\x1f]+"
# What the server exposes from a page: the browser layer, media, immutable revisions,
# and event-backed version addresses. A layer's agent-side instructions are read only
# through the CLI.
# The dir patterns are keyed by the public directories themselves, so growing
# that surface without saying what it may serve fails here, at import.
DIR_FILES = {
    "runtime": rf"{BROWSER_FILE}(?:{MODULE_EXTENSION}|\.css)",
    "widgets": rf"{BROWSER_FILE}{MODULE_EXTENSION}",
    "vendor": BROWSER_FILE,
    MEDIA_DIR: rf"[a-f0-9]{{{MEDIA_DIGEST}}}(?:"
    + "|".join(re.escape(e) for e in MEDIA_TYPES)
    + ")",
}
SERVED_PATH = re.compile(
    "/(?:"
    + "|".join(
        [re.escape(f) for f in LAYER_TOP_FILES]
        + [f"{d}/{DIR_FILES[d]}" for d in (*BROWSER_DIRS, MEDIA_DIR)]
        + [rf"versions/{VERSION_NAME}\.html"]
        + [rf"revisions/{REVISION_NAME}\.html"]
    )
    + ")"
)
BINARY_TYPES = frozenset(MEDIA_TYPES.values()) - {"image/svg+xml"}


def agent_name(event: dict) -> str | None:
    """The name an agent-authored event is shown under, and None for any other
    author's: its posting session's `agent`, or `UNNAMED_AGENT` where it was written
    outside a harness session and so carries none. The log stores no placeholder
    (`harness.message_identity`); every reading that shows the event names it through
    here, so the browser, the margin, the activity feed and the transcript agree."""
    if event["author"] != "agent":
        return None
    return event.get("agent") or UNNAMED_AGENT
