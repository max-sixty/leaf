"""Leaf's fixed kernel event contract, read off the kernel's own registry.

`$events.kinds` is the transport contract no layer can change
(`layer.validate_event_contracts`), so its facts are read from the shipped
`registry.json` rather than from a page's composed vocabulary. Reading them needs
no schema validator, and this module imports none: the page service sorts every
event by these kinds, including in a harness hook that validates nothing."""

from functools import cache

from leaf.files import read_json
from leaf.schema import ASSETS


def kernel_event_kinds() -> dict:
    """The fixed event records produced and consumed by Leaf's kernel."""
    return read_json(ASSETS / "registry.json")["$events"]["kinds"]


@cache
def bookkeeping_kinds() -> frozenset[str]:
    """The kinds `$events` declares `bookkeeping`: facts about the user's view of
    the page, kept for the page's own readings and never a move the agent answers."""
    return frozenset(
        kind
        for kind, contract in kernel_event_kinds().items()
        if contract.get("bookkeeping")
    )
