"""What a state answer leaves out for a browser that holds an earlier reading.

A browser adopts each state answer whole (`browser/AGENTS.md`, "One writer for each
fact"), and on a large page most of an answer is records the tab already holds: its
threads, workflows, obligations and On rows, its projection entries and undo list.
So the page server names each reading it serves by its content, `browser.basis.key`,
and remembers the most recent ones by that name. A tab sends back the key of the
reading it adopted as `Leaf-Held-Basis`, and when this process still remembers that
reading the answer carries `since`, naming it, and in place of the reading:

- `patch`: the changes from the held reading to this one;
- `events`: the events logged after the held reading's `through_seq`, since the log
  only grows;
- `data`: whole, since a tab names the data it holds by its version
  (`http.page_state`).

So an answer costs what changed since the tab's reading, however many records the
page holds. The browser applies the patch to the reading it named (`completeState` in
`layer-client.js`); what it assembles is the whole answer, and the records the patch
leaves alone keep the identity they had there, which is what lets every reader
downstream skip them.

The patch is a list of changes, each at a path of keys from the reading's root
through its objects:

- `{"at": path, "value": v}`: the value at `path` is now `v`, whole;
- `{"at": path}`: the object at `path[:-1]` no longer holds `path[-1]`;
- `{"at": path, "by": ..., "items": [...], "dropped": [...], "after": [...]}`: the
  list at `path`, whose items are each named by its `id` (`by` `"id"`), its event's
  `id` (`"event"`) or itself, a string (`"self"`), changed. `items` holds the new and
  changed items whole, `dropped` names the items it no longer holds, and `after`
  pairs each item that is new or moved, in the list's order, with the name of the
  item now before it, or null for the first. Every other item keeps its place. Each
  of the three is left out where empty.

A list whose items are not all named one of those ways, or whose names repeat, is a
value like any other. An item is never patched inside: a thread with one new message
comes whole.

Readings are remembered in this process alone, so a restarted server, or another
process, answers whole, as it does a key it never served or has forgotten. Naming by
content rather than by log position is what makes the patch exact: a reading depends
on the claim, the live stream and the clock as well as the log, so the same log
sequence can read two ways, while the same key cannot.
"""

import hashlib
import json
import threading
from collections import OrderedDict

# The parts of a reading the patch leaves to their own mechanism.
_OWN = frozenset({"events", "data"})
# How many readings this process remembers: a reading for each of a few tabs, and
# the answers each received but had not adopted yet when it next asked.
REMEMBERED = 16

# Each remembered reading's log position and fingerprint, oldest first.
_served: OrderedDict[str, tuple[int, tuple]] = OrderedDict()
_lock = threading.Lock()


def _digest(*parts: bytes) -> bytes:
    hasher = hashlib.blake2b(digest_size=16)
    for part in parts:
        hasher.update(part)
    return hasher.digest()


def _value_digest(value) -> bytes:
    return _digest(b"v", json.dumps(value, separators=(",", ":")).encode())


def _named(items: list) -> tuple[str, list[str]] | None:
    """How each item of `items` is named, and the names, where every one has its own."""
    if all(isinstance(item, str) for item in items):
        by, names = "self", items
    elif all(
        isinstance(item, dict) and isinstance(item.get("id"), str) for item in items
    ):
        by, names = "id", [item["id"] for item in items]
    elif all(
        isinstance(item, dict)
        and isinstance(item.get("event"), dict)
        and isinstance(item["event"].get("id"), str)
        for item in items
    ):
        by, names = "event", [item["event"]["id"] for item in items]
    else:
        return None
    return (by, names) if len(set(names)) == len(names) else None


def _fingerprint(value) -> tuple:
    """A digest of `value`, beside those of its keys where it is an object, and of its
    items where it is a named list."""
    if isinstance(value, dict):
        children = {key: _fingerprint(child) for key, child in value.items()}
        return (
            "object",
            _digest(
                b"o", *(json.dumps(key).encode() + c[1] for key, c in children.items())
            ),
            children,
        )
    named = _named(value) if isinstance(value, list) else None
    if named is None:
        return ("value", _value_digest(value))
    by, names = named
    digests = tuple(_value_digest(item) for item in value)
    return (
        "list",
        _digest(
            b"l",
            by.encode(),
            *(
                json.dumps(name).encode() + d
                for name, d in zip(names, digests, strict=True)
            ),
        ),
        by,
        tuple(names),
        digests,
    )


def _staying(names: list[str], held_at: dict[str, int]) -> set[str]:
    """The most of `names`, each a name the held list had, that stand in the order
    they stood there: a longest increasing run of their held positions."""
    tails: list[int] = []  # the index into `names` ending the best run of each length
    before: list[int | None] = []
    for index, name in enumerate(names):
        position = held_at[name]
        low, high = 0, len(tails)
        while low < high:
            middle = (low + high) // 2
            if held_at[names[tails[middle]]] < position:
                low = middle + 1
            else:
                high = middle
        before.append(tails[low - 1] if low else None)
        if low == len(tails):
            tails.append(index)
        else:
            tails[low] = index
    staying = set()
    at = tails[-1] if tails else None
    while at is not None:
        staying.add(names[at])
        at = before[at]
    return staying


def _list_change(held: tuple, current: tuple, items: list, path: list) -> dict:
    _, _, by, held_names, held_digests = held
    _, _, _, names, digests = current
    held_digest = dict(zip(held_names, held_digests, strict=True))
    held_at = {name: at for at, name in enumerate(held_names)}
    kept = set(names)
    change: dict = {"at": path, "by": by}
    if sent := [
        item
        for name, digest, item in zip(names, digests, items, strict=True)
        if held_digest.get(name) != digest
    ]:
        change["items"] = sent
    if dropped := [name for name in held_names if name not in kept]:
        change["dropped"] = dropped
    staying = _staying([name for name in names if name in held_at], held_at)
    after = []
    previous = None
    for name in names:
        if name not in staying:
            after.append([name, previous])
        previous = name
    if after:
        change["after"] = after
    return change


def _changes(held: tuple, current: tuple, value, path: list, patch: list) -> None:
    """Append to `patch` the changes that make the held fingerprint's value `value`."""
    if held[1] == current[1]:
        return
    if held[0] == current[0] == "object":
        for key, child in current[2].items():
            if key in held[2]:
                _changes(held[2][key], child, value[key], [*path, key], patch)
            else:
                patch.append({"at": [*path, key], "value": value[key]})
        patch.extend({"at": [*path, key]} for key in held[2] if key not in current[2])
    elif held[0] == current[0] == "list" and held[2] == current[2]:
        patch.append(_list_change(held, current, value, path))
    else:
        patch.append({"at": path, "value": value})


def answer(state: dict, held: str | None) -> dict:
    """Name `state`, a whole reading, in `browser.basis.key`, remember it, and return
    what a tab holding the reading `held` names is sent: the patch from that reading
    where this process remembers it, else `state` itself."""
    browser = state["browser"]
    if browser is None:
        return state
    basis = browser["basis"]
    basis.pop("key", None)
    patched = {key: value for key, value in state.items() if key not in _OWN}
    current = _fingerprint(patched)
    key = basis["key"] = current[1].hex()
    with _lock:
        before = None
        if held is not None and held in _served:
            _served.move_to_end(held)
            before = _served[held]
        _served[key] = (basis["through_seq"], current)
        _served.move_to_end(key)
        while len(_served) > REMEMBERED:
            _served.popitem(last=False)
    if before is None:
        return state
    through, fingerprint = before
    patch: list = []
    _changes(fingerprint, current, patched, [], patch)
    # The key names the reading rather than being part of it, and moves when it does.
    if patch:
        patch.append({"at": ["browser", "basis", "key"], "value": key})
    return {
        "since": {"key": held},
        "patch": patch,
        "events": [event for event in state["events"] if event["seq"] > through],
        "data": state["data"],
    }
