"""Leaf's fixed kernel facts, read off the kernel's own registry.

Every `$events` member but `handling` and `answering` is the transport contract no
layer can change (`layer.merge_layer_declarations`), and `$passages` is how a page reads
as text, which the browser's generated copy (`runtime/passage-facts.js`) shares. Both
are read from the running Leaf's shipped `registry.json` rather than from a page's
composed vocabulary, which may be another Leaf's at the same `protocol`
(`kernel_protocol`). Reading them needs no schema validator, and this module imports
none: the page service sorts every event by these kinds, including in a harness hook
that validates nothing."""

from functools import cache

from leaf.files import read_json
from leaf.schema import ASSETS


@cache
def _kernel() -> dict:
    return read_json(ASSETS / "registry.json")


def _kernel_events() -> dict:
    return _kernel()["$events"]


def kernel_passages() -> dict:
    """How both readings turn a page into text: the characters a whitespace run is
    made of (`collapse`), the tags whose text is one block (`blocks`), and the context
    an anchor starts with on each side of its quote (`context`)."""
    return _kernel()["$passages"]


def kernel_event_kinds() -> dict:
    """The fixed event records produced and consumed by Leaf's kernel."""
    return _kernel_events()["kinds"]


def kernel_protocol() -> int:
    """The number of the contract between a page and the Leaf serving it, which a
    page records by carrying the `$events` it was vendored with
    (`layer.incompatible_layer`)."""
    return _kernel_events()["protocol"]


def record_format(kind: str) -> str:
    """The `format` a record that each installed Leaf may read carries: its kind and the
    protocol of the Leaf that wrote it. A Leaf at another protocol leaves the record
    alone, as it refuses a page vendored at one, so one number versions pages and
    records alike (`AGENTS.md`, "Pages across Leaf updates")."""
    return f"leaf-{kind}/{kernel_protocol()}"


def kernel_event_ownership() -> dict:
    """Fields derived at admission or discarded at browser ingress."""
    return _kernel_events()["ownership"]


@cache
def bookkeeping_kinds() -> frozenset[str]:
    """The kinds `$events` declares `bookkeeping`: facts about the user's view of
    the page, kept for the page's own readings and never an update the agent answers."""
    return frozenset(
        kind
        for kind, contract in kernel_event_kinds().items()
        if contract.get("bookkeeping")
    )
