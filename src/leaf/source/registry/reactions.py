"""Registry-declared reactions."""


def reaction_emoji(registry: dict | None) -> dict:
    """The merged reactions, each emoji → its facts, in declared order."""
    return (registry or {}).get("$reactions", {}).get("emoji", {})
