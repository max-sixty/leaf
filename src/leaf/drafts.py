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
cancelled an earlier write of its own that the store may already have taken. A send or
a Cancel settles a generation, which removes it (`{attempt, settled}` names the one to
remove), so the store holds only what the user is writing; words a tab types over a
generation settled elsewhere start the draft again, since they are the user's newer
words.

Only the log records which generations were sent, and the store asks it
(`admitted_attempts`): a generation whose attempt the log admitted is settled. The
first reading or write after a send drops that generation and moves the store's
version, so every tab and device hears its words were sent, and words typed after the
send, a new generation, stand. A tab's write of words it then sent can reach the store
after their event, and settles the generation rather than standing it up again,
whether or not the tab lives to settle it. Admission never touches the store, so no
stop between taking a send and settling its draft can leave the words standing.

Every record carries the store's `version` when it was written, so a tab ordering a
reading against a write's answer keeps the later of the two.
"""

from pathlib import Path

from leaf.event_log import admitted_attempts
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
                    "Each draft's latest generation, by its context, which a "
                    "generation the log admitted no longer is.",
                    {"type": "object", "additionalProperties": _STORED},
                ),
            },
        ),
    ),
    since=46,
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


def _settle_sent(page_dir: Path, stored: dict, *, check: bool = False) -> bool:
    """Drop from `stored` each generation the log admitted, moving its version so
    every tab hears the words were sent, and say whether any went; with `check`, only
    say whether any would."""
    drafts = stored["drafts"]
    admitted = admitted_attempts(
        page_dir, (record["attempt"] for record in drafts.values())
    )
    sent = [
        context for context, record in drafts.items() if record["attempt"] in admitted
    ]
    if sent and not check:
        for context in sent:
            del drafts[context]
        stored["version"] += 1
    return bool(sent)


def read_drafts(page_dir: Path) -> dict:
    """The drafts the user is writing, by context, with the store's version. A
    generation sent since the last reading or write is settled first."""
    stored = _stored(page_dir)
    if _settle_sent(page_dir, stored, check=True):
        with flocked(page_dir / DRAFTS_LOCK):
            stored = _stored(page_dir)
            if _settle_sent(page_dir, stored):
                DRAFTS.write(page_dir / DRAFTS_FILE, stored)
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
        changed = _settle_sent(page_dir, stored)
        if not record.get("settled") and admitted_attempts(
            page_dir, [record["attempt"]]
        ):
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
        if written or changed:
            DRAFTS.write(page_dir / DRAFTS_FILE, stored)
    return {"written": written, "version": stored["version"], "record": current}
