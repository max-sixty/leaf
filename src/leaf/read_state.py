"""Whether the page's one user has taken in each piece of agent content.

The log owns the fact, and this module is its one reading. A message's original id and
each later edit id name distinct content versions. Content needs evidence the user
took it in unless it is progress. Two kinds of read evidence count:

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

A progress message (`ephemeral`) is never unread. The thread draws its run as one
dim line, the working message while its update is in hand, not as a reply, and once
the next ordinary agent reply supersedes it (`events.progress_completions`) it disappears
from the transcript. The answer itself needs read evidence.
Neither is something the user reads in order to keep up, so neither pulls them back
to the thread. An edit to other content
is a new version needing fresh evidence. An explicit summary
does not mark read what it covers. Unread is independent of turn-taking and of the
user's outstanding work: reading never answers an obligation, and answering one does
mark it read.

The page itself is agent content too, one revision at a time. A `seen` event names the
live revision a tab showed the user in a visible document, posted as they leave it, and
`seen_revision` is the newest one any tab named: the revision the browser compares the
page against to mark what changed since (`browser/runtime/since-seen.js`). It needs no
exposure of each passage, as a message's read does: a reader comes back to a page to
see what moved, and the marks it then shows are the evidence's whole use. A page has
one user, so like `read` it names no account and holds across tabs and browsers.
"""

from .events import taken_back
from .findings import Finding
from .registry.kernel import kinds_declaring
from .thread_context import event_threads


def user_message_content(event: dict) -> bool:
    """Whether an admitted message contains agent content the user can encounter.

    Failure replies are content too: they tell the user why a response failed,
    even though they are not substantive answers. Token reactions and unadmitted
    stream placeholders are not content versions in the page log.
    """
    return (
        event["kind"] in kinds_declaring("message")
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
        unread[thread_id] = [
            {"message": message["id"], "version": version}
            for message in thread["msgs"]
            if user_message_content(message)
            and not message.get("ephemeral")
            and message.get("edited", {}).get("seq", message["seq"]) > moved
            and (message["id"], version := content_version(message)) not in marked
        ]
    return unread


def seen_revision(events: list[dict]) -> int | None:
    """The newest revision a `seen` event names, or None before any tab showed one."""
    return max(
        (event["revision"] for event in events if event["kind"] == "seen"),
        default=None,
    )
