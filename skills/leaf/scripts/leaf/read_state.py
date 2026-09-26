"""Whether the page's one user has taken in each piece of agent content.

The log owns the fact, and this module is its one reading. A message's original id and
each later edit id name distinct content versions; a version stands unread until the
log holds evidence the user took it in. Two kinds of evidence count:

- a `read` event naming that exact version, which the browser posts when the version
  has been shown to the user or when they mark its thread read;
- a user move in the version's thread logged after the version, where the thread
  an event belongs to is `thread_context.thread_memberships`: a reply or reaction,
  a resolve or reopen, an action or request on a widget a message of that thread
  carries, and an action that answers the thread, such as deciding the page
  suggestion it asked for. Answering, resolving and replying are all things a user
  does with what the thread says, so each implies they have read it as it then stood.

A move the user took back with `undo` is no evidence, as it is none for every other
fold over the standing log, and the `undo` itself is none either: it withdraws a
gesture, often from the page's undo walk with the thread closed, and counting it
would restore the evidence the withdrawn move just lost.

An edit is a new version logged after every earlier move, so it reads as unread again
until fresh evidence arrives. A summary does not mark read what it covers. Unread is
independent of turn-taking and of the user's outstanding work: reading never answers
an Ask, and answering one does mark it read.
"""

from .events import taken_back
from .schema import MESSAGE_KINDS


def user_message_content(event: dict) -> bool:
    """Whether an admitted message contains agent content the user can encounter.

    Failure replies are content too: they tell the user why a response failed,
    even though they are not substantive answers. Token reactions and unadmitted
    stream placeholders are not content versions in the page log.
    """
    return (
        event["kind"] in MESSAGE_KINDS
        and event["author"] == "agent"
        and not event.get("token")
    )


def content_version(message: dict) -> str:
    """The id naming a message's current content: its latest edit, else itself."""
    return message.get("edited", {}).get("id", message["id"])


def content_versions(events: list[dict]) -> dict[str, set[str]]:
    """Every exact version a `read` event may name, including superseded edits."""
    versions = {
        event["id"]: {event["id"]} for event in events if user_message_content(event)
    }
    for event in events:
        if event["kind"] == "edit" and event["message"] in versions:
            versions[event["message"]].add(event["id"])
    return versions


def read_contract_error(event: dict, events: list[dict]) -> str | None:
    """Reject a `read` event naming no admitted content version."""
    if event["kind"] != "read":
        return None
    versions = content_versions(events)
    for item in event["messages"]:
        if item["version"] not in versions.get(item["message"], ()):
            return (
                f"{item['version']!r} is not a content version of agent message "
                f"{item['message']!r}"
            )
    return None


def unread_content(
    events: list[dict], threads: dict, memberships: dict[str, list[str]]
) -> dict[str, list[dict]]:
    """Each thread's agent content versions the user has not taken in, in log order.

    `threads` is the `build_threads` fold keyed by root id; `memberships` is
    `thread_context.thread_memberships` over the same log.
    """
    marked = set()
    latest_move: dict[str, int] = {}
    withdrawn = taken_back(events)
    for event in events:
        if event["kind"] == "read":
            marked.update(
                (item["message"], item["version"]) for item in event["messages"]
            )
            continue
        if (
            event["author"] != "user"
            or event["kind"] == "undo"
            or event["id"] in withdrawn
        ):
            continue
        for root in memberships[event["id"]]:
            latest_move[root] = event["seq"]
    unread = {}
    for root, thread in threads.items():
        moved = latest_move.get(root, 0)
        unread[root] = [
            {"message": message["id"], "version": version}
            for message in thread["msgs"]
            if user_message_content(message)
            and message.get("edited", {}).get("seq", message["seq"]) > moved
            and (message["id"], version := content_version(message)) not in marked
        ]
    return unread
