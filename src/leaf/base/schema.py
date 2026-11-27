"""Layer schema, browser/package resource paths, and page-directory vocabulary.

Resources belong to the installed plugin; the skill directory holds instructions.
"""

import re

from leaf.base.state import EVENTS_FILE, PLUGIN_ROOT, kernel_registry

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
# An element property Leaf sets on an element it drives: a record's (`property`) and a
# bound input's. It is never `state`, the widget's reading, which Leaf also sets on a
# widget's element (host/element-integration.js), so the two would overwrite each
# other.
_SET_PROPERTY = {
    "type": "string",
    "pattern": "^[a-z][A-Za-z0-9]*$",
    "not": {"const": "state"},
}
# The members of a value or attribute record that bind it to the page's elements: the
# `property` that holds the state in the browser, and the `event` that says the user
# changed it, `change` unless named (host/element-integration.js "Recorded
# properties"). A value record names the widget's own property, which holds the
# value; an attribute record names each member's, which reads true while the member is
# in the set.
_RECORD_BINDING = {
    "property": _SET_PROPERTY,
    "event": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9:._-]*$"},
}
# The record forms one vocabulary of declared state draws on ($verbs in the
# registry): how a unit's state reads in markup, each dispatched on by the gate,
# the runtime, and the diff without any of them knowing a widget by name.
_RECORD_ATTRIBUTE = {
    "type": "object",
    "properties": {
        "kind": {"const": "attribute"},
        "attr": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        **_RECORD_BINDING,
    },
    "required": ["kind", "attr"],
    "dependentRequired": {"event": ["property"]},
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
        **_RECORD_BINDING,
    },
    "required": ["kind", "attr"],
    "dependentRequired": {"event": ["property"]},
    "additionalProperties": False,
}
# The binding's members say how the page's elements hold the state, not what the state
# is or where it reads in markup, so no fold reads them (`registry.contract.recorded`).
RECORD_BINDING = frozenset(_RECORD_BINDING)

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

ACTION_CREATES = {
    "type": "object",
    "properties": {
        "child": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
        "words": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["child", "words"],
    "additionalProperties": False,
}

# The relation an authored attribute names: an empty object, which accepts any element
# id.
REFERENCE_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {"type": "object", "additionalProperties": False},
}


# A custom detail carries exactly the keys its declaration spells. Field meanings
# such as `resolves` read those declarations, so patternProperties and combinators
# cannot admit unnamed keys. `registry.schema.check_schema` validates the nested
# schemas and the standard keywords left unrestricted here. A declaration may leave
# out `type` and `additionalProperties`: composition writes them in
# (`registry.contract.complete_declarations`), so every composed detail has both, and
# one that writes another value for either is refused.
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
# A declaration may leave out `unit` and a record's `kind`: composition writes each
# default in (`registry.contract.complete_declarations`), so this schema requires both
# and every reader finds them.
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
        # The deciding verb's outcome that declines the proposal (`$verbs`).
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
VERBS_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": VERB_SCHEMA,
}
# A widget's obligation: the attributes that make it ask (`when`), the verb whose state
# is its typed answer (`value`), and how it ends. Whether it is answered is the
# widget's own word, carried on its gestures (`obligations.gesture_answers`).
AWAITS_SCHEMA = {
    "type": "object",
    "properties": {
        "when": AWAITING_CONDITION,
        "value": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "all": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        "retired": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    },
    "required": ["value"],
    "additionalProperties": False,
}
# Package and data-contract instructions address their declared audiences. Widget
# authoring instructions have one reader and therefore use a plain string below.
INSTRUCTIONS_SCHEMA = {
    "type": "object",
    "propertyNames": {"pattern": f"^{HTML_NAME}$"},
    "additionalProperties": {"type": "string", "pattern": r"\S"},
}
_ATTRIBUTE_NAME = {"type": "string", "pattern": f"^{HTML_NAME}$"}
# The keys of an input (`inputs`) that bind it. Each names the attribute whose value
# binds the input on an element: `source` names the attribute holding a page source's
# id, and `reference` the `refers` attribute naming a widget, whose one output of the
# input's contract the input reads. An input declares at least one of them, and
# composition writes each attribute it names into the element's attribute schema
# (`registry.contract.complete_declarations`). The browser's copy is `bindingAttributes`
# (runtime/state/registry.js), and the input type the build generates from this schema checks
# the key names it reads.
INPUT_BINDINGS = ("source", "reference")
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
            **dict.fromkeys(INPUT_BINDINGS, _ATTRIBUTE_NAME),
            # The element property the runtime sets to the delivered value
            # (host/element-data.js, "Bound values").
            "property": _SET_PROPERTY,
            # The widget attribute holding the receipt of the source's run that
            # produced the value written in the element's content.
            "measured": {"type": "string", "pattern": f"^{HTML_NAME}$"},
        },
        "required": ["contract"],
        "anyOf": [{"required": [key]} for key in INPUT_BINDINGS],
        "additionalProperties": False,
    },
}

_TAGS = {
    "type": "array",
    "items": {"type": "string", "pattern": f"^{WIDGET_NAME}$"},
    "minItems": 1,
}


# The form of a fact declared to hold only for the occurrences whose authored
# attributes match its `when` (`registry.contract.holds_for`).
_WHEN_FORM = {
    "type": "object",
    "properties": {"when": AWAITING_CONDITION},
    "required": ["when"],
    "additionalProperties": False,
}


def _conditional(schema: dict) -> dict:
    """The schema of a fact a declaration may state outright, as `schema` admits, or
    in the `{when: {attribute: [values]}}` form. Only a mark (`$marks`) may take it,
    and importing this module fails for any other fact (below). Delivery and the
    browser paint each mark on the occurrences where it holds, and `registry.widgets`
    holds each mark's `when` to the declared attributes, so no code names the fact. A
    reader asking of one occurrence reads the fact through
    `registry.contract.holds_for`, and one asking whether the tag declares it at all
    reads the declaration, condition or not; `$keys` says which of `exhibit`'s
    readers asks which."""
    return {"oneOf": [schema, _WHEN_FORM]}


# How an author writes an element: a widget's declaration holds these with its other
# facts, and a selector idiom holds only these and its description (`IDIOM_SCHEMA`).
_AUTHORING = {
    "example": {"type": "string", "pattern": r"\S"},
    "instructions": {"type": "string", "pattern": r"\S"},
}
# The facts a declaration may hold beside its description, attributes and content,
# each declared because some reader can't run the widget's module to learn it; `$keys`
# in the kernel package's registry says which.
FACTS: dict[str, dict] = {
    "verbs": VERBS_SCHEMA,
    "awaits": AWAITS_SCHEMA,
    "retired-when": {"type": "string", "pattern": f"^{HTML_NAME}$"},
    "exhibit": _conditional({"const": True}),
    "history": {"const": True},
    "owners": _TAGS,
    "refers": REFERENCE_SCHEMA,
    "reading-role": {"enum": ["pane", "group"]},
    "verbatim": {"const": True},
    "shadow": {"const": True},
    "inline": {"const": True},
    "visual": {
        "oneOf": [
            {"const": "whole"},
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
    "height": {"oneOf": [{"const": True}, {"type": "integer", "minimum": 1}]},
    "bound": {"enum": ["start", "end"]},
    "spine": {"const": True},
    "flow": _conditional({"const": True}),
    "inputs": DATA_INPUTS_SCHEMA,
    # Each output's name is the element property holding it (host/data.js).
    "outputs": {
        "type": "object",
        "minProperties": 1,
        "propertyNames": {"pattern": "^[a-z][A-Za-z0-9]*$"},
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
    **_AUTHORING,
}
# An element declaration: the JSON Schema of its attributes, and its facts.
DECLARATION_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string", "pattern": r"\S"},
        # A JSON Schema, held to Draft 2020-12 apart (`registry.widgets`). The keywords
        # Leaf's readers read are named, so the browser's types know them: an
        # attribute's own schema (`properties`), its presence (`required`), and whether
        # the schema admits attributes it doesn't name (`additionalProperties`). A
        # declaration may leave the schema out, or `type` and `additionalProperties`
        # out of it. Composition writes them in
        # (`registry.contract.complete_declarations`), so this schema, which reads a
        # composed declaration, still requires `attributes`.
        "attributes": {
            "type": "object",
            "properties": {
                "properties": {"type": "object"},
                "required": {"type": "array", "items": {"type": "string"}},
                "additionalProperties": {},
            },
        },
        "content": {"enum": ["markup", "members", "data", "markdown", "empty"]},
        **FACTS,
    },
    "required": ["description", "attributes"],
    # A fact read through others needs them declared too: a member that leaves under
    # its owner's decision reads its owners.
    "dependentRequired": {"retired-when": ["owners"]},
    "additionalProperties": False,
}
# Every key `$keys` documents: each a declaration may hold but its `description`.
DECLARATION_KEYS = frozenset(DECLARATION_SCHEMA["properties"]) - {"description"}
# A fact no mark paints would reach its readers in the `{when}` form as an object, which
# reads as true, with nothing holding its condition to the declared attributes.
if stray := sorted(
    name
    for name, schema in FACTS.items()
    if _WHEN_FORM in schema.get("oneOf", ()) and name not in kernel_registry()["$marks"]
):
    raise ValueError(f"only a mark ($marks) may take the {{when}} form: {stray}")
# A selector idiom names authored HTML the theme dresses, so it says only how an
# author writes it, and declares no widget behavior or marks
# (`revision_delivery.mark_declared`).
IDIOM_SCHEMA = {
    "type": "object",
    "properties": {
        "description": DECLARATION_SCHEMA["properties"]["description"],
        **_AUTHORING,
    },
    "required": ["description", "example"],
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
# check's membership test by substring, and a reaction the picker offers that is no
# emoji is one admission refuses. A `leaf:` reference names a kernel record's field
# (`registry.schema.leaf_resources`).
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
            "emoji": {
                "type": "array",
                # One emoji, by the form a reaction's record holds it to.
                "items": {"$ref": "leaf:event/comment#/properties/emoji"},
                "uniqueItems": True,
            }
        },
        "required": ["emoji"],
    },
}
# The work roles, which Leaf owns and `runtime/host/work.js` reads: what each role's
# `$work.widgets` entry holds beside `role`, then which of those it must hold. A goal
# or worker names its recorded state attribute and the values of it that mean done or
# stopped, running or retired, and may name the attribute saying when it stopped or
# which goal it works on; a scope or evidence holds nothing more.
_WORK_VALUES = {"type": "array", "items": {"type": "string"}}
_WORK_ROLES = {
    "scope": ({}, []),
    "evidence": ({}, []),
    "goal": (
        {
            "state": _ATTRIBUTE_NAME,
            "done": _WORK_VALUES,
            "stopped": _WORK_VALUES,
            "stoppedAt": _ATTRIBUTE_NAME,
        },
        ["state", "done", "stopped"],
    ),
    "worker": (
        {
            "state": _ATTRIBUTE_NAME,
            "running": _WORK_VALUES,
            "retired": _WORK_VALUES,
            "on": _ATTRIBUTE_NAME,
        },
        ["state", "running", "retired"],
    ),
}
# The shared layer facts a vocabulary may leave out, each held to its schema where a
# layer declares it (`registry.validation.check_layer_facts`). A package maps its tags
# onto the work roles in `$work.widgets`, and `registry.validation.validate_work_roles`
# holds each entry to its tag's declaration.
OPTIONAL_LAYER_FACTS = {
    "$work": {
        "type": "object",
        "properties": {
            "description": _NONEMPTY,
            "widgets": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {"role": {"enum": list(_WORK_ROLES)}},
                    "required": ["role"],
                    # A clause per role, so a refusal names the key its role refused.
                    "allOf": [
                        {
                            "if": {
                                "properties": {"role": {"const": role}},
                                "required": ["role"],
                            },
                            "then": {
                                "properties": {"role": True, **keys},
                                "required": required,
                                "additionalProperties": False,
                            },
                        }
                        for role, (keys, required) in _WORK_ROLES.items()
                    ],
                },
            },
        },
        "required": ["widgets"],
        "additionalProperties": False,
    },
}
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
# The kernel's sheets that `layer.composed_sheets` reads, and every file of the
# kernel's a layer names (`layer.input_paths`).
KERNEL_STYLES = (
    "shadow.css",
    "base.css",
    "elements.css",
    "layouts.css",
    "state.css",
    "styles/control-face.css",
    "styles/page-control-face.css",
    "styles/markup.css",
    "styles/parts.css",
    "styles/shadow-leading.css",
)
KERNEL_FILES = (*KERNEL_STYLES, "registry.json", "icon.svg")
# A package's source contributions are composed into the page files above. Their
# roles depend on their filenames, not on whether the package declares widgets.
PACKAGE_STYLES = (
    "theme.css",
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
# The lock serializing re-initializations of an initialized page (`vendoring._reinit`).
INIT_LOCK = "init.lock"
# What a page records about who is working on it and how it is served, as against what
# its author wrote (the source) and what it has accumulated (the log and its revisions).
# Neither validation nor a revision's capture reads these, so a write to one is news to
# an open tab and never a candidate revision.
SESSION_FILES = (
    STREAM_FILE,
    WAITER_LOCK,
    INIT_LOCK,
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
    # (`drafts.py`), though no reading of the page counts them (`page_inputs.UNWATCHED`).
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
