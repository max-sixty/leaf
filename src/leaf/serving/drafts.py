"""The user's unsent words on a page, kept by its server for every tab and device.

A draft is what the user typed or drew into a message box and hasn't sent: a comment,
a reply, a rewrite or a widget's edit (`browser/runtime/records/drafts.js` names each by its
context). The page's server keeps one record of each, so a draft written in one tab
or on one device stands in every other, which they hear through the same freshness
look that tells them of the log (`/api/news`'s `drafts`, then `/api/drafts`). Drafts
are neither events nor state: nothing here enters the log, a reading of the page or
what the agent reads, because sending is when the user says them.

A record is a generation, `{attempt, text, payload?, held?}`, which the edit that made
it minted, and a send carries its attempt into the log. Each write names the
generations it may replace (`expect`), and the store takes it only over one of those or
over none: a tab whose words another tab or device has since replaced hears the current
record back rather than overwriting it, and writes over it a generation holding its
words and the tab's (`browser/runtime/records/drafts.js`, `adopt`). A write names more than one
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

The store names itself (`store`), an identity minted when its file is created, and
every reading and write answer carries it beside the store's `version`, which counts
its writes. Within one store the version never goes back: every write replaces the
file under its lock. A host that keeps the page outside this machine holds the store
of record (`transaction.commit_provider`), and the file is this machine's copy of it: the
host takes a write only over the store the file held, before Leaf replaces the file
or answers, so a tab never hears a write the host could lose, and a save that reaches
the host late finds a newer store there and changes nothing. Where the host holds
another store than the file, as after a save it took whose answer never came back,
the file takes the host's store and the write runs once more against it (`_change`).
Every record carries the version of its own write, so a tab ordering a reading
against a write's answer keeps the later of the two. A page directory replaced, or a leaf.page session started at a new page protocol,
starts another store with another identity, whose versions say nothing of the one a
tab heard before.
"""

import secrets
from collections.abc import Callable
from pathlib import Path

from leaf.base.schema import DRAFTS_FILE, DRAFTS_LOCK
from leaf.base.state import Record, described, flocked, object_schema
from leaf.log.event_log import admitted_attempts
from leaf.records.transaction import commit_provider
from leaf.source.registry.schema import schema_error

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
                "store": described(
                    "The store's identity, minted when its file is created.",
                    {"type": "string", "minLength": 1},
                ),
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
    since=51,
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
    """A new store, under an identity of its own: version 0 holds no drafts."""
    return {"store": secrets.token_hex(16), "version": 0, "drafts": {}}


def _change[T](
    page_dir: Path, change: Callable[[dict], tuple[bool, T]]
) -> tuple[dict, T]:
    """Run `change` on the store under its lock, and save the store where `change` says
    it changed it or the page had none: the store and what `change` returned. A host
    that keeps the page elsewhere takes the save only over the store the file held, and
    answers with the store it holds; where that is another, the file takes it and
    `change` runs once more against it. RuntimeError where the host turns that away
    too."""
    path = page_dir / DRAFTS_FILE
    provider = commit_provider()
    with flocked(page_dir / DRAFTS_LOCK):
        for _ in range(2):
            stored = DRAFTS.read(path)
            replaces = stored and {
                "store": stored["store"],
                "version": stored["version"],
            }
            stored = stored or no_drafts()
            changed, result = change(stored)
            if not changed and replaces is not None:
                return stored, result
            held = (
                provider.publish_drafts(page_dir, stored, replaces)
                if provider
                else stored
            )
            if held == stored:
                DRAFTS.write(path, stored)
                return stored, result
            if held is None:
                DRAFTS.remove(path)
            else:
                DRAFTS.write(path, held)
    raise RuntimeError("the page's host holds another drafts store")


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
    """The drafts the user is writing, by context, with the store's identity and
    version. A generation sent since the last reading or write is settled first, and
    a page with no store yet starts one, so every reading names the store it read."""
    stored = DRAFTS.read(page_dir / DRAFTS_FILE)
    if stored is None or _settle_sent(page_dir, stored, check=True):
        stored, _ = _change(
            page_dir, lambda stored: (_settle_sent(page_dir, stored), None)
        )
    return {
        "store": stored["store"],
        "version": stored["version"],
        "drafts": stored["drafts"],
    }


def write_draft(page_dir: Path, payload: dict) -> dict:
    """Take a tab's generation where it replaces one it names, and answer with
    the context's record as the store now holds it: `written` says whether that is
    the tab's. ValueError for a write of the wrong shape."""
    if error := schema_error(_WRITE, payload):
        raise ValueError(f"invalid draft: {error}")
    context, expect, record = payload["context"], payload["expect"], payload["record"]
    if not record.get("settled") and admitted_attempts(page_dir, [record["attempt"]]):
        record = {"attempt": record["attempt"], "settled": True}

    def change(stored: dict) -> tuple[bool, tuple[bool, dict | None]]:
        changed = _settle_sent(page_dir, stored)
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
        return written or changed, (written, current)

    stored, (written, current) = _change(page_dir, change)
    return {
        "written": written,
        "store": stored["store"],
        "version": stored["version"],
        "record": current,
    }
