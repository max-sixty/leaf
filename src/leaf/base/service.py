"""Page claims, and the page-directory records the claimant's watch reads.

A page's claim names the session that receives its updates (`page_claim`). Whether
that session still lives (`claim_is_active`, `session_lives`), and who holds the
page for a reader deciding whether it may act on it (`page_holder`), are read here.
The page's transaction (`transaction.PageTransaction`) takes, restores and marks
claims, and is the one writer of the stream. Cold harness hooks and the sandbox
bridge read claims, so this module stands below the event log and the page model.

What the harness observes of the claimant's task as it runs, its live activity, the
reply it drafts and the response addresses it has reserved, is `stream.json`
(`STREAM`). It stays out of the log: it changes several times a second while a turn
streams, means nothing once that turn has ended, and a reservation fences competing
writers of one answer. A developer preview's identity, `preview.json` (`PREVIEW`),
stands here too, since a page that carries one owes no watcher, which the hooks
ask beside the claim."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Protocol

from leaf.base.files import read_json
from leaf.base.machine import pid_alive, sandbox_remedy
from leaf.base.refusals import Refused
from leaf.base.schema import STREAM_FILE
from leaf.base.state import (
    CLAIM,
    SESSION,
    SESSION_SUFFIX,
    STRING,
    TIME,
    Record,
    chat_exists,
    claims_home,
    claims_lock,
    described,
    drop_locator,
    ensure_session,
    flocked,
    fsync_parents,
    held_claims,
    now_iso,
    object_schema,
    page_key,
    page_stands,
    session_claims,
    session_file,
    session_live,
    session_record,
    standing_claims,
)


class Claimant(Protocol):
    """The harness of a session that claims a page or asks who holds one
    (`harness.Harness`)."""

    @property
    def name(self) -> str: ...
    @property
    def session(self) -> str: ...
    @property
    def agent(self) -> str: ...

    def lifetime(self) -> dict: ...


def delivery_reply_attempt(delivery_id: str) -> str:
    """Return the stable idempotency key for one delivery-bound reply."""
    digest = hashlib.sha256(delivery_id.encode()).hexdigest()[:32]
    return f"leaf-delivery-{digest}"


def claim_path(page_dir: Path) -> Path:
    """The page's one canonical payload, also written by resident page servers."""
    return claims_home() / f"{page_key(page_dir)}.json"


def publish_claim(page_dir: Path, claim: dict) -> dict[Path, bytes]:
    """Prepare discovery, then commit ownership in the canonical payload: the one
    writer of a claim.

    Discovery validates the payload's owner against the partition. A transfer's
    old locator therefore stops being current at the canonical commit, which also
    admits the prepared new locator. Failed preparation leaves ownership intact.
    Resident writers retain the same flat payload path, so their atomic updates
    cannot destroy discovery. The claims lock keeps a retirement from removing
    what this publishes (`state.retire_claim`). A claim of another shape goes with
    the claim this replaces, since it would otherwise hold the page beside it
    (`page_holder`); its bytes, unread, are returned for a rollback to write back
    (`transaction.PageTransaction.restore_claim`).
    """
    path = claim_path(page_dir)
    name = CLAIM.file(path).name
    locator = session_claims(claim["id"]) / name
    with flocked(claims_lock()):
        locator.parent.mkdir(parents=True, exist_ok=True)
        previous = CLAIM.read(path)
        staged = locator.with_name(f".{secrets.token_hex(8)}.tmp")
        try:
            staged.symlink_to(Path("..") / name)
            os.replace(staged, locator)
            fsync_parents([locator])
        finally:
            staged.unlink(missing_ok=True)
        CLAIM.write(path, claim)
        displaced = {other: other.read_bytes() for other in CLAIM.others(path)}
        for other in displaced:
            other.unlink(missing_ok=True)
        if previous is not None and previous["id"] != claim["id"]:
            drop_locator(previous["id"], name)
    return displaced


def claim_reading(claim: dict | None) -> dict | None:
    """A claim as its readers take it: the record, with its session's lifetime and
    turn while the session is still in the generation the claim names.

    It reads a claim whatever harness it names, a later Leaf's included; only code
    that acts through the claimant's harness asks for one this Leaf knows
    (`harness.claim_harness`). Every reader goes through `page_claim` or
    `claim_records`."""
    if claim is None:
        return None
    record = session_record(claim["id"])
    if record is None or claim["generation"] != record["generation"]:
        return {**claim, "turn": None, "turn_opened": None, "turn_closed": None}
    return {
        **claim,
        **record["lifetime"],
        "turn": record["turn"],
        "turn_opened": record["turn_opened"],
        "turn_closed": record["turn_closed"],
    }


def page_claim(page_dir: Path) -> dict | None:
    """The page's last claim, including one whose session or lifetime ended."""
    return claim_reading(CLAIM.read(claim_path(page_dir)))


def claim_is_active(claim: dict | None) -> bool:
    """Whether a claim still names a live owner: its session's generation, not
    ended, with a lifetime that still lives (`session_lives`). Cold hooks and the
    CLI both call it."""
    if not claim:
        return False
    record = session_record(claim["id"])
    if record is None or record["generation"] != claim["generation"]:
        return False
    return session_lives({"id": claim["id"], **record["lifetime"]}, record)


def session_lives(lifetime: dict, record: dict | None) -> bool:
    """Whether a session lives: its lifecycle `record`, where it has one, hasn't
    recorded its end, and the owner its `lifetime` (`Harness.lifetime`) names still
    lives: the job record a background job's lifetime points at, the Claude desktop
    app's record an `app` lifetime points at while it is unarchived and still names
    the session, the native source a persisted `chat` stands on (`record`'s), or the
    process every other lifetime's pid names. The only reading of whether a session
    lives: a claim and the sandbox bridge's registrations both carry a lifetime
    beside the session's `id`.

    A lifetime that names nothing yet has no owner, so nothing lives by it. A kind
    this Leaf doesn't know reads as live until the record says the session ended,
    since this Leaf can't check it: the sandbox bridge's registrations don't declare
    their lifetime's keys, so a later Leaf's kind reaches an older bridge that shares
    their shape. So a harness that states its lifetime a new way adds its form to the
    session record's `lifetime` and its reading here."""
    if record is not None and record["ended"] is not None:
        return False
    if "job" in lifetime:
        return (Path(lifetime["job"]) / "state.json").is_file()
    if "app" in lifetime:
        app = read_json(Path(lifetime["app"]))
        return (
            app is not None
            and not app["isArchived"]
            and app["cliSessionId"] == lifetime["id"]
        )
    if lifetime.get("chat") is True:
        return chat_exists(record)
    if "pid" in lifetime:
        return pid_alive(lifetime["pid"])
    return bool(lifetime.keys() - {"id"})


def dead_session(claim: dict) -> str:
    """Why a claim just prepared has no live session. Its session can end between
    preparing and publishing, but where a sandbox runs the command in a process
    namespace of its own, as Claude Code's does on Linux, the session's process
    was never visible to it, and only a command run outside the sandbox can claim."""
    if "pid" in claim and not pid_alive(claim["pid"]) and (remedy := sandbox_remedy()):
        return f"the session's process ({claim['pid']}) is not visible here: {remedy}"
    return "the prepared acquisition no longer has a live session"


def claim_names_session(claim: dict | None, session_id: str) -> bool:
    """Whether the page is still `session_id`'s to record what its task took from
    the page and answered there: the claim names that session, and the session
    has not ended.

    Unlike `claim_is_active`, this survives the session's own restart. A new
    lifetime begins its generation before it publishes that generation's claim,
    and a task that holds several pages claims them back one at a time, so the
    claim may name an older generation, or a lifetime that has gone, of a session
    still running. What that session's task received and answered stays its own
    to record; only another session's claim takes the page from it."""
    if not claim or claim["id"] != session_id:
        return False
    return session_live(session_record(session_id))


def may_receive(page_dir: Path, claim: dict | None, session_id: str | None) -> bool:
    """Whether `session_id` may take receipt of `page_dir`'s input under `claim`
    (`delivery.receive_batch`): the claim names it, or, for a reader with no
    session, no one holds the page (`page_holder`)."""
    if session_id is None:
        return page_holder(page_dir, claim, None) is None
    return claim_names_session(claim, session_id)


def page_holder(
    page_dir: Path, claim: dict | None, session_id: str | None
) -> dict | str | None:
    """Who holds `page_dir`, as this Leaf sees it for a reader acting for the session
    `session_id`, or for no session: `claim`, the page's claim at this shape, while
    its session lives (`claim_is_active`); a holder this Leaf reads as holding the
    page without reading it (`state.Record`), as words naming it: `claim`'s session
    where a lifecycle of another shape of it stands that this Leaf's record doesn't
    match and hasn't seen end, unless that session is the reader's, which takes its
    page again (`reconnect`), or else a claim of another shape; or None where no one
    holds the page. Every reader that decides whether it may act on a page someone
    else holds asks this: `held_elsewhere`, `may_receive`,
    `transaction.PageTransaction.watch_state` and a server's retirement
    (`server_lifetime.stop_when_service_ends`)."""
    if claim is not None and claim_is_active(claim):
        return claim
    if claim is not None and claim["id"] != session_id:
        record = session_record(claim["id"])
        if (
            record is None
            or (record["generation"] != claim["generation"] and record["ended"] is None)
        ) and SESSION.others(session_file(claim["id"], SESSION_SUFFIX)):
            return f"session {claim['id']}, whose lifecycle another Leaf version keeps"
    if others := CLAIM.others(claim_path(page_dir)):
        return f"a session of another Leaf version, by the claim {others[0]}"
    return None


def claimant_matches(claim: dict | None, harness: Claimant | None) -> bool:
    """Whether the record names this harness, or neither names a claimant.

    Harness identity is independent of liveness: readers pass the active claim
    when asking which harness owns the page now. Resource retirement instead uses
    the exact acquisition reading (`same_claim`).
    """
    if harness is None:
        return claim is None
    return bool(
        claim and (claim["harness"], claim["id"]) == (harness.name, harness.session)
    )


def held_elsewhere(page_dir: Path, harness: Claimant | None) -> str | None:
    """Who holds `page_dir`, where a session other than `harness`'s does, or None
    (`page_holder`), whatever harness the holder names."""
    holder = page_holder(
        page_dir, CLAIM.read(claim_path(page_dir)), harness.session if harness else None
    )
    if isinstance(holder, dict):
        return None if claimant_matches(holder, harness) else f"session {holder['id']}"
    return holder


def refuse_held(page_dir: Path, harness: Claimant | None) -> None:
    """Refuse to serve `page_dir` or change its layer record for anyone but the
    session holding it (`held_elsewhere`). Another session takes the page over first
    by claiming it (`leaf server start`). Since only the Leaf a session's hooks run
    acts for it (`harness.session_harness`), no other Leaf, such as a checkout's or a
    terminal's, moves a held page to a protocol those hooks can't read, whatever the
    protocols are."""
    if (holder := held_elsewhere(page_dir, harness)) is None:
        return
    raise Refused(
        f"{page_dir} is held by {holder}, and only the Leaf that session's hooks run "
        "serves it or changes its layer. Work on the page through that session, or "
        f"take it over first by running `leaf server start {page_dir}` in an agent "
        "session"
    )


def same_claim(left: dict | None, right: dict | None) -> bool:
    """Whether two readings name the same acquisition, including no claimant.

    Lifecycle projection may change between readings; acquisition is the exact
    publication a resource owner may retire or a failed start may restore.
    """
    if left is None or right is None:
        return left is right
    return left["acquisition"] == right["acquisition"]


def claim_records(session_id: str | None = None) -> list:
    """Readable claims for pages still on this machine.

    Payloads are canonical by page. A named lookup reads only through the
    locators whose payloads name that session (`state.held_claims`), and opens no
    unrelated claim file; the unnamed scan reads every payload
    (`state.standing_claims`). Each retires the claims it finds on pages that are
    gone."""
    paths = held_claims(session_id) if session_id else standing_claims()
    claims = []
    for path in paths:
        claim = claim_reading(CLAIM.read(path))
        if (
            claim is not None
            and CLAIM.file(claim_path(Path(claim["page"])))
            == CLAIM.file(path).resolve()
            and (session_id is None or claim["id"] == session_id)
            and page_stands(Path(claim["page"]))
        ):
            claims.append(claim)
    return claims


def prepare_claim(harness: Claimant, page_dir: Path) -> dict:
    """Capture an unpublished acquisition in the claimant's process.

    Lifetime and cwd come from the launching harness, not a detached child. Preparing
    the canonical session is independent of any page ownership publication.
    """
    session = ensure_session(harness.session, harness.lifetime())
    return {
        "page": str(page_dir),
        "ts": now_iso(),
        "id": harness.session,
        "generation": session["generation"],
        "acquisition": secrets.token_hex(16),
        "harness": harness.name,
        "agent": harness.agent,
        "cwd": os.getcwd(),
    }


def no_stream() -> dict:
    """The stream while the harness observes nothing of the claimant's task: no live
    activity, no reply it is drafting, and no response address it has reserved
    (`delivery` header)."""
    return {"activity": None, "reply": None, "reply_reservations": {}}


_TURN = {
    "session": described("The claimant session the harness observed.", STRING),
    "turn": described("The turn it observed.", STRING),
}
# The page receives it whole, so its shape is the served state's `preview`.
PREVIEW = Record(
    "preview",
    described(
        "What a developer preview shows in browser chrome, as `leaf-dev preview` "
        "writes it to the page directory's `preview.json`.",
        read_json(
            Path(__file__).parents[1] / "serving" / "served_state" / "state.schema.json"
        )["$defs"]["Reading"]["properties"]["preview"],
    ),
    since=13,
)
STREAM = Record(
    "stream",
    described(
        "What the harness observes of the claimant's task as it runs, in the page "
        "directory's `stream.json`; `no_stream` while it observes nothing.",
        object_schema(
            {
                "activity": described(
                    "What the task is doing now (`set_stream_activity`), or null.",
                    {
                        **object_schema(
                            {
                                **_TURN,
                                "kind": described(
                                    "The step observed; the page reads one of "
                                    "`activity.WORK_KINDS`.",
                                    STRING,
                                ),
                                "ts": described("When it was last observed.", TIME),
                                "after": described(
                                    "The log's last `seq` when it was observed.",
                                    {"type": "integer"},
                                ),
                            },
                            {"detail": described("What the step names.", STRING)},
                        ),
                        "type": ["object", "null"],
                    },
                ),
                "reply": described(
                    "The reply it is drafting (`set_stream_reply`), or null.",
                    {
                        **object_schema(
                            {
                                **_TURN,
                                "attempt": described(
                                    "The delivery attempt it is drafted under.",
                                    STRING,
                                ),
                                "parent": described(
                                    "The thread it replies in.", STRING
                                ),
                                "responds": described("The input it answers.", STRING),
                                "item": described(
                                    "The harness's id for the message supplying the "
                                    "draft, or null while none is attached.",
                                    {"type": ["string", "null"]},
                                ),
                                "text": described("Its words so far.", STRING),
                                "state": STRING,
                                "settles": {"type": "boolean"},
                                "agent": described(
                                    "The name the claimant shows.", STRING
                                ),
                                "ts": described("When the draft began.", TIME),
                                "updated_at": described(
                                    "When the draft last changed.", TIME
                                ),
                            }
                        ),
                        "type": ["object", "null"],
                    },
                ),
                "reply_reservations": described(
                    "Each open reply reservation, by the response address it holds "
                    "(`thread.reserve_delivery_reply`).",
                    {
                        "type": "object",
                        "additionalProperties": object_schema(
                            {**_TURN, "attempt": STRING}
                        ),
                    },
                ),
            }
        ),
    ),
    since=16,
)


def read_stream(page_dir: Path) -> dict:
    """The page's stream, `stream.json`, as every reader takes it, or `no_stream`
    before the first write."""
    return STREAM.read(page_dir / STREAM_FILE) or no_stream()
