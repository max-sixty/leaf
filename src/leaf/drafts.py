"""The user's unsent words on a page, kept by its server for every tab and device.

A draft is what the user typed or drew into a message box and hasn't sent: a comment,
a reply, a rewrite or a widget's edit (`browser/runtime/drafts.js` names each by its
context). The page's server keeps one record of each, so a draft written in one tab
or on one device stands in every other, which they hear through the same freshness
look that tells them of the log (`/api/news`'s `drafts`, then `/api/drafts`). Drafts
are neither events nor state: nothing here enters the log, a reading of the page or
what the agent reads, because sending is when the user says them.

A record is a generation, `{attempt, text, payload?, held?}`, which the edit that made
it minted, and a send carries its attempt into the log. Each write names the generation
it replaces (`expect`), and the store takes it only over that one or over none: a tab
whose words another tab or device has since replaced hears the current record back and
adopts it, rather than overwriting it. A send or a Cancel settles a generation, which
removes it (`{attempt, settled}` names the one to remove), so the store holds only what
the user is writing; words a tab types over a generation settled elsewhere start the
draft again, since they are the user's newer words. Admission settles the generation an
accepted event was sent from (`settle_sent`), so a send in flight never leaves its words
standing as a draft, and words typed after it, a new generation, stand.

Every record carries the store's `version` when it was written, so a tab ordering a
reading against a write's answer keeps the later of the two.
"""

from pathlib import Path

from leaf.registry.schema import schema_error
from leaf.schema import DRAFTS_FILE, DRAFTS_LOCK
from leaf.state import Record, described, flocked, object_schema

_ATTEMPT = described(
    "The generation's attempt, which its send carries into the log.",
    {"type": "string", "minLength": 1, "maxLength": 128},
)
_ACTIVE = object_schema(
    {
        "attempt": _ATTEMPT,
        "text": described("The words, untrimmed.", {"type": "string"}),
    },
    {
        "payload": described(
            "What the generation's send depends on beside its words, such as a "
            "comment's anchor (`$events.draft`).",
            {"type": "object"},
        ),
        "held": described(
            "A reply a refusal handed back to the draft whose message opens its "
            "thread.",
            {"type": "string"},
        ),
    },
)
_SETTLED = object_schema(
    {"attempt": _ATTEMPT, "settled": described("Sent or put away.", {"const": True})}
)
_VERSION = {"type": "integer", "minimum": 0}
_STORED = {**_ACTIVE, "properties": {**_ACTIVE["properties"], "version": _VERSION}}
DRAFTS = Record(
    "drafts",
    described(
        "The user's unsent message drafts on a page, in the page directory's "
        "`drafts.json`.",
        object_schema(
            {
                "version": described(
                    "Counts the store's writes; each record holds the count at its "
                    "own.",
                    _VERSION,
                ),
                "drafts": described(
                    "Each draft's latest generation, by its context.",
                    {"type": "object", "additionalProperties": _STORED},
                ),
            }
        ),
    ),
    since=44,
)
_WRITE = {
    "type": "object",
    "properties": {
        "context": {"type": "string", "minLength": 1, "maxLength": 1024},
        "expect": {"anyOf": [{"type": "null"}, _ATTEMPT]},
        "record": {
            "anyOf": [
                {**_ACTIVE, "additionalProperties": False},
                {**_SETTLED, "additionalProperties": False},
            ]
        },
    },
    "required": ["context", "expect", "record"],
    "additionalProperties": False,
}


def _stored(page_dir: Path) -> dict:
    return DRAFTS.read(page_dir / DRAFTS_FILE) or {"version": 0, "drafts": {}}


def read_drafts(page_dir: Path) -> dict:
    """The drafts the user is writing, by context, with the store's version."""
    return _stored(page_dir)


def write_draft(page_dir: Path, payload: dict) -> dict:
    """Take a tab's generation where it replaces the one it names, and answer with
    the context's record as the store now holds it: `written` says whether that is
    the tab's. ValueError for a write of the wrong shape."""
    if error := schema_error(_WRITE, payload):
        raise ValueError(f"invalid draft: {error}")
    context, expect, record = payload["context"], payload["expect"], payload["record"]
    with flocked(page_dir / DRAFTS_LOCK):
        stored = _stored(page_dir)
        current = stored["drafts"].get(context)
        written = current is None or current["attempt"] == expect
        if written:
            stored["version"] += 1
            if record.get("settled"):
                stored["drafts"].pop(context, None)
                current = None
            else:
                current = stored["drafts"][context] = {
                    **record,
                    "version": stored["version"],
                }
            DRAFTS.write(page_dir / DRAFTS_FILE, stored)
    return {"written": written, "version": stored["version"], "record": current}


def settle_sent(page_dir: Path, attempt: str) -> None:
    """Settle the generation an accepted event was sent from, wherever it stands. A
    generation whose write reaches the store after its event does is the sending tab's
    to settle, as it settles every generation it sends."""
    if not (page_dir / DRAFTS_FILE).exists():
        return
    with flocked(page_dir / DRAFTS_LOCK):
        stored = _stored(page_dir)
        sent = [
            context
            for context, record in stored["drafts"].items()
            if record["attempt"] == attempt
        ]
        if not sent:
            return
        stored["version"] += 1
        for context in sent:
            del stored["drafts"][context]
        DRAFTS.write(page_dir / DRAFTS_FILE, stored)
