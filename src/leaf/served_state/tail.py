"""What a state answer leaves out for a browser that holds an earlier reading.

A browser adopts each state answer whole (`browser/AGENTS.md`, "One writer for each
fact"), and on a large page most of an answer is records the tab already holds: its
threads and their messages, workflows, obligations and On rows, its projection
entries and undo list. So the page server names each reading it serves by its
content, `browser.basis.key`, and remembers the most recent ones. A tab sends back the
key of the reading it adopted as `Leaf-Held-Basis`, and when this process still
remembers that reading the answer carries `since`, naming it, and in place of the
reading:

- `patch`: the changes from the held reading to this one;
- `events`: the events logged after the held reading's `through_seq`, since the log
  only grows;
- `data`: whole, since a tab names the data it holds by its version
  (`http.page_state`).

So an answer costs what changed since the tab's reading, however many records the
page holds and however long a thread runs: a reply sends its message and the fields
of its thread it changed. The browser applies the patch to the reading it named
(`completeState` in `layer-client.js`); what it assembles is the whole answer, and
whatever the patch leaves alone keeps the identity it had there, down to each
message, which is what lets every reader downstream skip it.

The patch is a list of changes, each at a path of keys from the root of what it
changes through its objects:

- `{"at": path, "value": v}`: the value at `path` is now `v`, whole;
- `{"at": path}`: the object at `path[:-1]` no longer holds `path[-1]`;
- `{"at": path, "by": ..., "items": [...], "changed": [...], "dropped": [...],
  "after": [...]}`: the list at `path`, whose items are each named by its `id` (`by`
  `"id"`), its event's `id` (`"event"`) or itself, a string (`"self"`), changed.
  `items` holds the new items whole; `changed` pairs the name of each item it held
  that is now otherwise with the patch, in this same form and from that item's root,
  that makes it so; `dropped` names the items it no longer holds; and `after` pairs
  each item that is new or moved, in the list's order, with the name of the item now
  before it, or null for the first. Every other item keeps its place. Each of the
  four is left out where empty.

A list whose items are not all named one of those ways, or whose names repeat, is a
value like any other.

#5271 sent only the history after the held reading and re-read it at the held
sequence, which keeps no record of what each tab holds and is exact, since it sent
everything else whole. Remembering readings, as this module does instead, reverses
that, and buys the rest: the threads and workflows also read the claim, the live
stream and the clock, so the same log sequence can read two ways and re-reading
can't give what the tab holds of them, while a content name can, so those records
travel as changes too. Readings are remembered in this process alone, each as the
JSON of its records and the values of its other fields (`_parts`), one copy shared by
every remembered reading that holds a part unchanged. A restarted server, or another
process, answers whole, as it does a key it never served or has forgotten.
"""

import hashlib
import json
import threading
from collections import OrderedDict

# The parts of a reading the patch leaves to their own mechanism.
_OWN = frozenset({"events", "data"})
# How many readings this process remembers of each page: a reading for each of a few
# tabs, and the answers each received but had not adopted yet when it next asked.
REMEMBERED = 16
# How many pages it remembers readings of: a multiplexed server's pages, and the live
# samples in them, so one page's answers never push out another's readings.
PAGES = 8

# Each page's remembered readings, by key, each its log position and parts (`_parts`);
# pages and their readings both oldest first.
_served: OrderedDict[str, OrderedDict[str, tuple[int, tuple]]] = OrderedDict()
_lock = threading.Lock()


def _json(value) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


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


_SCALARS = (str, int, float, bool, type(None))


def _token(part: tuple) -> bytes:
    """What a part contributes to the digest of the object holding it."""
    kind = part[0]
    if kind == "scalar":
        return b"s" + repr(part[1]).encode()
    if kind == "value":
        return b"v" + part[1]
    if kind == "names":
        return b"n" + "\x00".join(part[1]).encode()
    return part[1]


def _same(held: tuple, current: tuple) -> bool:
    """Whether two parts hold the same JSON: the one comparison this module makes, so a
    `false` and a `0`, or a `1` and a `1.0`, are never taken for each other."""
    return held is current or (
        held[0] == current[0] and _token(held) == _token(current)
    )


def _object(children: dict) -> tuple:
    hasher = hashlib.blake2b(digest_size=16)
    for key, child in children.items():
        encoded = key.encode()
        hasher.update(b"%d:" % len(encoded) + encoded)
        token = _token(child)
        hasher.update(b"%d:" % len(token) + token)
    return ("object", hasher.digest(), children)


def _parts(value, earlier: tuple | None) -> tuple:
    """`value` as this module remembers it: an object as its keys' parts, each with a
    digest of what it holds; a scalar as itself; a list named by its strings as those;
    a list of named records as their names and JSON, with a digest; and anything else
    as its JSON. A part the same as the one at its place in `earlier`, a remembered
    reading's, is that reading's own, so a part that didn't change is the very one the
    held reading has, and keeps the digest it had."""
    if isinstance(value, dict):
        same_kind = earlier is not None and earlier[0] == "object"
        children = earlier[2] if same_kind else {}
        parts = {key: _parts(child, children.get(key)) for key, child in value.items()}
        if (
            same_kind
            and parts.keys() == children.keys()
            and all(part is children[key] for key, part in parts.items())
        ):
            return earlier
        return _object(parts)
    if isinstance(value, _SCALARS):
        part = ("scalar", value)
        return earlier if earlier is not None and _same(earlier, part) else part
    named = _named(value) if isinstance(value, list) else None
    if named is None:
        encoded = _json(value)
        if earlier is not None and earlier[0] == "value" and earlier[1] == encoded:
            return earlier
        return ("value", encoded)
    by, names = named
    if by == "self":
        names = tuple(names)
        if earlier is not None and earlier[0] == "names" and earlier[1] == names:
            return earlier
        return ("names", names)
    before = (
        dict(zip(earlier[3], earlier[4], strict=True))
        if earlier is not None and earlier[0] == "list" and earlier[2] == by
        else {}
    )
    items = []
    for name, item in zip(names, value, strict=True):
        encoded = _json(item)
        kept = before.get(name)
        items.append(kept if kept == encoded else encoded)
    names, items = tuple(names), tuple(items)
    if earlier is not None and earlier[0] == "list" and earlier[3:] == (names, items):
        return earlier
    hasher = hashlib.blake2b(by.encode(), digest_size=16)
    for name, item in zip(names, items, strict=True):
        encoded = name.encode()
        hasher.update(b"%d:" % len(encoded) + encoded)
        hasher.update(b"%d:" % len(item) + item)
    return ("list", hasher.digest(), by, names, items)


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


def _list_change(path, by, held_names, names, items, changes) -> dict | None:
    """The change that makes the held list named `held_names` the list of `items`,
    named `names`, or None where there is none. `changes(before, at)` gives the changes
    from held item `before` to current item `at`, or None where they are the same."""
    held_at = {name: at for at, name in enumerate(held_names)}
    whole, changed = [], []
    for at, (name, item) in enumerate(zip(names, items, strict=True)):
        before = held_at.get(name)
        if before is None:
            whole.append(item)
        elif (inner := changes(before, at)) is not None:
            changed.append([name, inner])
    current = set(names)
    staying = _staying([name for name in names if name in held_at], held_at)
    after = []
    previous = None
    for name in names:
        if name not in staying:
            after.append([name, previous])
        previous = name
    change: dict = {"at": path, "by": by}
    for field, entries in (
        ("items", whole),
        ("changed", changed),
        ("dropped", [name for name in held_names if name not in current]),
        ("after", after),
    ):
        if entries:
            change[field] = entries
    return change if len(change) > 2 else None


def _changes(held: tuple, current: tuple, value, path: list, patch: list) -> None:
    """Append to `patch` the changes that make the held parts `value`, whose parts are
    `current`."""
    if _same(held, current):
        return
    kind = current[0]
    if (
        held[0] != kind
        or kind in ("scalar", "value")
        or (kind == "list" and held[2] != current[2])
    ):
        patch.append({"at": path, "value": value})
    elif kind == "object":
        for key, child in current[2].items():
            if key in held[2]:
                _changes(held[2][key], child, value[key], [*path, key], patch)
            else:
                patch.append({"at": [*path, key], "value": value[key]})
        patch.extend({"at": [*path, key]} for key in held[2] if key not in current[2])
    elif kind == "names":
        change = _list_change(
            path, "self", held[1], current[1], value, lambda _before, _at: None
        )
        if change is not None:
            patch.append(change)
    else:
        held_items, items = held[4], current[4]

        # A record the held list had, which is an object, changes from within.
        def changes(before: int, at: int) -> list | None:
            if held_items[before] == items[at]:
                return None
            inner: list = []
            _changes(
                _parts(json.loads(held_items[before]), None),
                _parts(value[at], None),
                value[at],
                [],
                inner,
            )
            return inner

        change = _list_change(path, current[2], held[3], current[3], value, changes)
        if change is not None:
            patch.append(change)


def answer(state: dict, held: str | None, page: str) -> dict:
    """Name `state`, a whole reading of `page`, in `browser.basis.key`, remember it, and
    return what a tab holding the reading `held` names is sent: the patch from that
    reading where this process remembers it, else `state` itself."""
    browser = state["browser"]
    if browser is None:
        return state
    basis = browser["basis"]
    basis.pop("key", None)
    patched = {key: value for key, value in state.items() if key not in _OWN}
    with _lock:
        readings = _served.setdefault(page, OrderedDict())
        _served.move_to_end(page)
        while len(_served) > PAGES:
            _served.popitem(last=False)
        before = readings.get(held) if held is not None else None
        latest = next(reversed(readings.values()), None)
    current = _parts(patched, (before or latest or (0, None))[1])
    key = basis["key"] = current[1].hex()
    with _lock:
        if held is not None and held in readings:
            readings.move_to_end(held)
        readings[key] = (basis["through_seq"], current)
        readings.move_to_end(key)
        while len(readings) > REMEMBERED:
            readings.popitem(last=False)
    if before is None:
        return state
    through, parts = before
    patch: list = []
    _changes(parts, current, patched, [], patch)
    # The key names the reading rather than being part of it, and moves when it does.
    if patch:
        patch.append({"at": ["browser", "basis", "key"], "value": key})
    return {
        "since": {"key": held},
        "patch": patch,
        "events": [event for event in state["events"] if event["seq"] > through],
        "data": state["data"],
    }
