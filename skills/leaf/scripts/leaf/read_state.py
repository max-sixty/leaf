"""One reader's acknowledgement of exact conversation content on a page.

The log owns the fact. A message's original id and each later edit id name distinct
content versions; acknowledging one never acknowledges another. This is independent
of conversation turn-taking and of the reader's outstanding work.
"""

from .schema import MESSAGE_KINDS


def reader_message_content(event: dict) -> bool:
    """Whether an admitted message contains agent content the reader can encounter.

    Failure replies are content too: they tell the reader why a response failed,
    even though they are not substantive answers. Token reactions and unadmitted
    stream placeholders are not content versions in the page log.
    """
    return (
        event["kind"] in MESSAGE_KINDS
        and event["author"] == "agent"
        and not event.get("token")
    )


def content_versions(events: list[dict]) -> dict[str, set[str]]:
    """Every exact version that may be acknowledged, including superseded edits."""
    versions = {
        event["id"]: {event["id"]}
        for event in events
        if reader_message_content(event)
    }
    for event in events:
        if event["kind"] == "edit" and event["message"] in versions:
            versions[event["message"]].add(event["id"])
    return versions


def read_contract_error(event: dict, events: list[dict]) -> str | None:
    """Reject an acknowledgement that names no admitted content version."""
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


def read_versions(events: list[dict]) -> set[tuple[str, str]]:
    """The monotone set of exact message versions this page's reader acknowledged."""
    return {
        (item["message"], item["version"])
        for event in events
        if event["kind"] == "read"
        for item in event["messages"]
    }
