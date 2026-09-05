"""Registry-declared readings of the event vocabulary: what a reaction token
means, and what each event kind asks of the agent that receives it."""


def reaction_tokens(registry: dict | None) -> dict:
    """The merged reaction vocabulary, token → entry, in declared order."""
    return (registry or {}).get("$reactions", {}).get("tokens", {})


def described(event: dict, registry: dict | None) -> dict:
    """A reaction event with its token's `means` beside it, so whoever reads the
    line — `leaf wait`'s consumer, `page state`'s — meets a custom token
    already explained. A token the vendored layer no longer declares keeps its
    word and says nothing more. Any other event passes through as it is."""
    token = event.get("token")
    if not token:
        return event
    entry = reaction_tokens(registry).get(token)
    return {**event, "means": entry["means"]} if entry else event


def handling(batch: list[dict], registry: dict | None) -> dict:
    """What the layer asks of the agent for each event kind in a batch, keyed by
    kind, read off the vendored `$events.handling`. A project layer restates a
    kind's sentence merge-patch style, so the batch carries the rule the page
    was vendored with. A kind the layer does not describe is absent rather than
    empty."""
    declared = (registry or {}).get("$events", {}).get("handling", {})
    kinds = dict.fromkeys(event.get("kind") for event in batch)
    return {kind: declared[kind] for kind in kinds if kind in declared}
