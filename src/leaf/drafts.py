"""The user's unsent words on a page, kept by its server for every tab and device.

A draft is what the user typed or drew into a message box and hasn't sent: a comment,
a reply, a rewrite or a widget's edit (`browser/runtime/drafts.js` names each by its
context). The page's server keeps one record of each, so a draft written in one tab
or on one device stands in every other, which they hear through the same freshness
look that tells them of the log (`/api/news`'s `drafts`, then `/api/drafts`). Drafts
are neither events nor state: nothing here enters the log, a reading of the page or
what the agent reads, because sending is when the user says them.

A record is a generation, `{attempt, text, payload?, held?}`, which the edit that made
it minted, and a send carries its attempt into the log. Each write names the
generations it may replace (`expect`), and the store takes it only over one of those or
over none: a tab whose words another tab or device has since replaced hears the current
record back and adopts it, rather than overwriting it. A write names more than one
where it can't know which the store holds, as a page going away does after leaving
cancelled an earlier write of its own that the store may already have taken. A send or a Cancel settles a generation, which
removes it (`{attempt, settled}` names the one to remove), so the store holds only what
the user is writing; words a tab types over a generation settled elsewhere start the
draft again, since they are the user's newer words. Admission settles the generation an
accepted event was sent from (`settle_sent`), so a send in flight never leaves its words
standing as a draft, and words typed after it, a new generation, stand. It also keeps
the attempts it admitted most recently (`sent`), and a write of one of them, which
reached the store after its event, settles that generation rather than standing it up
again, whether or not the tab that sent it lives to settle it.

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
# How many admitted attempts the store remembers: far more than can be sent while one
# tab's write is on its way.
SENT_KEPT = 64
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
            },
            {
                "sent": described(
                    "The attempts admission settled most recently, oldest first.",
                    {"type": "array", "items": _ATTEMPT},
                )
            },
        ),
    ),
    since=44,
)
_WRITE = {
    "type": "object",
    "properties": {
        "context": {"type": "string", "minLength": 1},
        "expect": {"type": "array", "items": _ATTEMPT},
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


def no_drafts() -> dict:
    """The store before its first write: version 0 holds no drafts."""
    return {"version": 0, "drafts": {}}


def _stored(page_dir: Path) -> dict:
    return DRAFTS.read(page_dir / DRAFTS_FILE) or no_drafts()


def read_drafts(page_dir: Path) -> dict:
    """The drafts the user is writing, by context, with the store's version."""
    stored = _stored(page_dir)
    return {"version": stored["version"], "drafts": stored["drafts"]}


def write_draft(page_dir: Path, payload: dict) -> dict:
    """Take a tab's generation where it replaces one it names, and answer with
    the context's record as the store now holds it: `written` says whether that is
    the tab's. ValueError for a write of the wrong shape."""
    if error := schema_error(_WRITE, payload):
        raise ValueError(f"invalid draft: {error}")
    context, expect, record = payload["context"], payload["expect"], payload["record"]
    with flocked(page_dir / DRAFTS_LOCK):
        stored = _stored(page_dir)
        if record["attempt"] in stored.get("sent", []):
            record = {"attempt": record["attempt"], "settled": True}
        current = stored["drafts"].get(context)
        written = current is None or current["attempt"] in expect
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
    """Settle the generation an accepted event was sent from, wherever it stands, and
    remember its attempt for a write of it still on its way (`sent`)."""
    with flocked(page_dir / DRAFTS_LOCK):
        stored = _stored(page_dir)
        kept = stored.get("sent", [])
        if attempt in kept:
            return
        stored["sent"] = [*kept, attempt][-SENT_KEPT:]
        settled = [
            context
            for context, record in stored["drafts"].items()
            if record["attempt"] == attempt
        ]
        if settled:
            stored["version"] += 1
        for context in settled:
            del stored["drafts"][context]
        DRAFTS.write(page_dir / DRAFTS_FILE, stored)
