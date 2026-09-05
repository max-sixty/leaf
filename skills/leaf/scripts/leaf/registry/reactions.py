"""Registry-declared reaction readings."""


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
