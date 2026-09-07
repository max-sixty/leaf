"""Registry-declared reaction readings."""


def reaction_tokens(registry: dict | None) -> dict:
    """The merged reaction vocabulary, token → entry, in declared order."""
    return (registry or {}).get("$reactions", {}).get("tokens", {})


def described(event: dict, registry: dict | None) -> dict:
    """Add a layer-supplied explanation to a reaction event when one exists.

    The token is the stable reading. Packages that define a specialized vocabulary
    may also explain it to off-page consumers; ordinary tokens need no prose. A token
    the vendored layer no longer declares keeps its word and says nothing more. Any
    other event passes through as it is.
    """
    # TODO(2026-09-06): Reconsider whether reaction prose belongs in Leaf's
    # contract at all; clear package-defined tokens may make `means` unnecessary.
    token = event.get("token")
    if not token:
        return event
    meaning = (reaction_tokens(registry).get(token) or {}).get("means")
    return {**event, "means": meaning} if meaning else event
