"""Whether the page's one user has taken in each piece of agent content.

The log owns the fact, and this module is its one reading. A message's original id and
each later edit id name distinct content versions. Content needs evidence the user
took it in unless it is superseded progress. Two kinds of read evidence count:

- a `read` event naming that exact version, which the browser posts when its visible
  body has been shown to the user;
- an update made in the version's thread and logged after the version, which is
  the thread the update names (`thread_context.event_threads`): a reply or reaction,
  a resolve or reopen, an action on a widget a message of that thread
  carries, and an action whose admitted answer closes the thread, such as accepting
  the page suggestion it asked for. Answering, resolving and replying are all things
  a user does with what the thread says, so each implies they have read it as it
  then stood.

Only the thread an update names counts. Delivery also files an update under threads it
changes without naming them (`thread_context.thread_memberships`): a later decision
on a suggestion that had answered a thread, or the `undo` of an answer. Neither
shows the user what the thread says, so neither is evidence here. An update the user
took back is no evidence either, as it is none for every other fold over the
current log.

The next ordinary agent reply supersedes preceding progress (`progress_completions`),
so completed progress leaves unread even when its body was never exposed. The reply
itself still needs read evidence. Edits to completed progress remain superseded; an
edit to other content is a new version needing fresh evidence. An explicit summary
does not mark read what it covers. Unread is independent of turn-taking and of the
user's outstanding work: reading never answers an ask, and answering one does
mark it read.
"""

from .events import progress_completions, taken_back
from .findings import Finding
from .schema import MESSAGE_KINDS
from .thread_context import event_threads


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


def read_contract_error(event: dict, events: list[dict]) -> Finding | None:
    """Reject a `read` event naming no admitted content version."""
    if event["kind"] != "read":
        return None
    versions = content_versions(events)
    for item in event["messages"]:
        if item["version"] not in versions.get(item["message"], ()):
            return Finding("unknown-content-version", values=dict(item))
    return None


def unread_content(
    events: list[dict], threads: dict, names: dict, widgets: dict
) -> dict[str, list[dict]]:
    """Each thread's agent content versions the user has not taken in, in log order.

    `threads` is the `build_threads` fold keyed by thread id; `names` and `widgets`
    are `thread_context.thread_names` and `thread_widgets` over the same log.
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
        if event["author"] != "user" or event["id"] in withdrawn:
            continue
        for thread_id in event_threads(event, names, widgets):
            latest_move[thread_id] = event["seq"]
    unread = {}
    for thread_id, thread in threads.items():
        moved = latest_move.get(thread_id, 0)
        completed = progress_completions(thread)
        unread[thread_id] = [
            {"message": message["id"], "version": version}
            for message in thread["msgs"]
            if user_message_content(message)
            and message["id"] not in completed
            and message.get("edited", {}).get("seq", message["seq"]) > moved
            and (message["id"], version := content_version(message)) not in marked
        ]
    return unread
