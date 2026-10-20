"""Leaf's fixed kernel facts, read off the kernel's own registry.

Every `$events` member but `handling` and `answering` is the transport contract no
layer can change (`layer.merge_layer_declarations`), `$passages` is how a page reads
as text, which the browser's generated copy (`runtime/passage-facts.js`) shares, and
`$marks` the declarations painted for stylesheets, which composition stamps over any a
layer declares. All three are read from the running Leaf's shipped `registry.json`
rather than from a page's composed vocabulary, which may be another Leaf's at the same
`protocol` (`kernel_protocol`). Reading them needs no schema validator, and this module
imports none: the page service sorts every event by these kinds, including in a harness
hook that validates nothing."""

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
def kinds_declaring(flag: str) -> frozenset[str]:
    """The kinds whose `$events.kinds` contract sets `flag`: `bookkeeping`, a fact
    about the user's view of the page that is never an update the agent answers;
    `message`, words said in a thread; `undoable`, a gesture of the user's own an
    `undo` may withdraw. `$events.description` owns what each means."""
    return frozenset(
        kind for kind, contract in kernel_event_kinds().items() if contract.get(flag)
    )


@cache
def verb_writers() -> dict[str, str]:
    """Each widget kind, one that carries an x-state verb, with the side that writes
    that verb (`verb_writer`): the user's `action`, the agent's `report`."""
    return {
        kind: contract["verb_writer"]
        for kind, contract in kernel_event_kinds().items()
        if "verb_writer" in contract
    }


def answer_kinds() -> list[str]:
    """The answers an update may owe (`reply`, `markup`), each of which
    `$events.answering` instructs; a layer restates only these."""
    return list(_kernel_events()["answering"])


@cache
def kernel_marks() -> dict:
    """The declarations a stylesheet reads, each with the attribute it is painted as
    (`$marks`, whose description owns the table's meaning)."""
    return {
        key: mark for key, mark in _kernel()["$marks"].items() if key != "description"
    }
