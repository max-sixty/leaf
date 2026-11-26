"""Thread-scoped browser projection."""

from collections.abc import Callable

from leaf.base.schema import agent_name
from leaf.log.events import (
    active_summaries,
    is_answer,
    owed_turns,
    progress_completions,
    seat_root,
    spoken_turns,
)
from leaf.log.projection import ThreadMarkupReading
from leaf.records.read_state import content_version, unread_content
from leaf.serving.served_state.wire import browser_projection


def _answers_live_reply(event: dict, live_reply: dict) -> bool:
    """Whether one logged event is the durable answer a provisional reply stands in for.

    A provisional reply is reserved under a delivery attempt and addressed to a
    response, and the durable answer names itself by either. Reading only the response
    address would let an answer whose address has moved stand beside its own
    placeholder, and the panel draw the draft rather than the answer the log holds.
    """
    return any(
        event.get(named) == live_reply[named] for named in ("attempt", "responds")
    )


def _response_key(responds: str) -> dict:
    """The name an agent's answer to `responds` is drawn under, provisional or durable.

    A provisional reply and the answer that retires it are one message to the reader,
    but the answer's own attempt need not be the one the provisional reply was reserved
    under: an explicit `thread reply` takes an author's retry key from a namespace of
    its own, so it can never consume the provider final's append identity. The input
    they both answer is the identity they share. A failure receipt is no answer
    (`events.is_answer`), so it keeps its own name. The log can hold a second answer to
    an input though no writer gives one; a name stands for one message, so only the
    input's first answer in the log takes it."""
    return {"key": f"response:{responds}"}


def _named(event: dict) -> dict:
    """One served thread event, an agent's carrying the name it is shown under
    (`agent_name`). Any other author's carries no `agent`, so the event stays the record
    its kind declares."""
    name = agent_name(event)
    return {**event, "agent": name} if name is not None else event


def _answer_key(event: dict, first_answers: dict[str, str]) -> dict:
    """The name of an input's first answer (`_response_key`), by `first_answers`, each
    input's first answer's id in log order; nothing for any other event."""
    if not is_answer(event) or first_answers[event["responds"]] != event["id"]:
        return {}
    return _response_key(event["responds"])


def thread_counts(threads: list[dict]) -> dict:
    """What the Leaf panel's Threads tab counts of `browser_thread`'s threads
    (`threadCounts` in the runtime's `state/thread/model.js`): the ones still open, and
    of those the ones holding words the user hasn't read.
    `tests/thread_count_cases.json` holds both runtimes to the same cases."""
    open_threads = [thread for thread in threads if not thread["resolved"]]
    return {
        "open": len(open_threads),
        "unread": sum(bool(thread["unread"]) for thread in open_threads),
    }


def progress_ends(
    thread: dict, owed_since: int | None, runs: Callable[[dict], bool]
) -> dict[str, str | None]:
    """What ended each progress message `thread` no longer shows, by its id: the
    agent message that superseded it (`events.progress_completions`), or None where
    the turn that wrote it has ended (`runs`, `activity.turn_runs`) and no message of
    the user's said before it still waits on an answer (`owed_since`, the seq of the
    oldest one that does, or None). So a thread shows only its newest steps, and only
    while the work they belong to goes on.

    A step toward an answer still owed stands until the agent next speaks in its
    thread (`events.progress_completions`), whichever turn or session writes that, as
    the line a line fork writes for the session does (`forks.py`), which names no
    turn of its own. The user chose that a
    step otherwise goes with its turn, rather than standing as the thread's last word
    until the agent next speaks there, and that owed work keeps the rule before, under
    which every step stood until then, even past its session's end, when its On it
    goes."""
    superseded = progress_completions(thread)
    ends: dict[str, str | None] = {}
    for message in spoken_turns(thread):
        if not message.get("ephemeral"):
            continue
        if (by := superseded.get(message["id"])) is not None:
            ends[message["id"]] = by["id"]
        elif (owed_since is None or owed_since > message["seq"]) and not runs(message):
            ends[message["id"]] = None
    return ends


def browser_thread(
    work, live_reply: dict | None, runs: Callable[[dict], bool]
) -> tuple[dict, ThreadMarkupReading]:
    """Serialize the shared thread-markup work reading, adding presentation only.
    Messages and closing events carry their canonical display name; provisional
    replies and unread state never become durable work authority.

    A provisional reply joins its thread once it has words. Before then the input's
    workflow says the agent is replying, and an empty message would only reserve a
    bubble with nothing in it. An agent's message whose current Markdown holds HTML
    carries `html` (`thread_context.thread_structure`), which the browser draws as
    markup. A progress message the thread no longer shows carries `completed_by`
    (`progress_ends`), where `runs` says whether the turn that wrote an event still
    runs."""
    events, threads = work.events, work.threads
    reading = work.thread
    fragments = reading.structure.fragments
    unread = unread_content(
        events, threads, reading.thread_by_name, reading.thread_by_widget
    )
    summaries_for = active_summaries(events, threads)
    rendered_threads: list[dict] = []
    first_answers: dict[str, str] = {}
    for event in events:
        if is_answer(event):
            first_answers.setdefault(event["responds"], event["id"])
    owed_since: dict[str, int | None] = {}
    for thread_id, thread in threads.items():
        owed = owed_turns(thread)
        owed_since[thread_id] = owed[0]["seq"] if owed else None
        messages = [
            {
                **_named(message),
                **_answer_key(message, first_answers),
                **({"html": True} if message["id"] in fragments else {}),
                "content_version": content_version(message),
            }
            for message in thread["msgs"]
        ]
        rendered_threads.append(
            {
                # A thread's turn and closure histories are the server's to read
                # (`unanswered_turns`, `provenance.saved_after`, `obligations`).
                **{
                    key: value
                    for key, value in thread.items()
                    if key
                    not in (
                        "turns",
                        "closures",
                        "closings",
                        "answered_by",
                        "closed_by_user",
                    )
                },
                "msgs": messages,
                "root": next(
                    message
                    for message in messages
                    if message["id"] == thread["root"]["id"]
                ),
                "resolved": thread["resolved"] and _named(thread["resolved"]),
                "seat": seat_root(thread),
                "summaries": summaries_for[thread_id],
                "unread": unread[thread_id],
            }
        )
    if (
        live_reply is not None
        and live_reply["text"]
        and not any(_answers_live_reply(event, live_reply) for event in events)
    ):
        target = next(
            (
                thread
                for thread in rendered_threads
                if any(
                    message["id"] == live_reply["parent"] for message in thread["msgs"]
                )
            ),
            None,
        )
        if target is not None:
            target["msgs"] = [
                *target["msgs"],
                {
                    "id": f"stream:{live_reply['turn']}",
                    "content_version": f"stream:{live_reply['turn']}",
                    "attempt": live_reply["attempt"],
                    **_response_key(live_reply["responds"]),
                    "provisional": True,
                    "kind": "reply",
                    "addressable": False,
                    "author": "agent",
                    "agent": live_reply["agent"],
                    "parent": live_reply["parent"],
                    "text": live_reply["text"],
                    "ts": live_reply["ts"],
                    "pending": live_reply["state"] == "active",
                },
            ]
    # Presentation keeps the raw messages so a surface can retain progress while the
    # message that ended it is held. An answer already streaming here ends it too.
    for thread in rendered_threads:
        ends = progress_ends(thread, owed_since[thread["id"]], runs)
        for message in thread["msgs"]:
            if message["id"] in ends:
                message["completed_by"] = ends[message["id"]]
    return (
        {
            "projection": browser_projection(
                reading.projection, scope="thread", within={}, floors={}
            ),
            "threads": rendered_threads,
        },
        reading,
    )
