"""Per-call wall-clock spans of named functions, for `bench_render_check.py`.

The benchmark puts this directory on a child's `PYTHONPATH`, so Python imports this
file at startup inside whichever arm's environment the child runs, and the arm's own
code is measured as it stands. It does nothing unless `LEAF_BENCH_TRACE` names an
output file, and it removes that variable so a subprocess never writes over it.

`LEAF_BENCH_FUNCTIONS` is a JSON object from `<path suffix>:<qualname>` to the names
of the locals to record when that function starts, e.g.
`{"render_gate/scheme.py:_render_scheme": ["scheme", "viewport"]}`. Every other code
object is disabled on first sight through `sys.monitoring` (Python 3.12+), so the
process runs at full speed outside the named functions. A generator records one span
per run between a resume and the next yield or return, which splits a
`@contextmanager` into its enter and its exit.

At exit it writes `{"imported": t, "exited": t, "cpu": {...}, "spans": [...]}`. Times
are epoch seconds. `cpu` is the CPU seconds of this process (`self`) and of the
children it has reaped (`children`: the Playwright driver and, through it, the
browser). Each span is `{"fn", "args", "part", "main", "start", "end"}`: `part` counts
the generator runs of that frame from 0, and `main` says whether the span ran on the
main thread rather than, say, a server thread. A span still open at exit is dropped.
"""

import _thread
import atexit
import json
import os
import sys
import time


def _plain(value):
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value


def _install(out: str, functions: dict[str, list[str]]) -> None:
    monitoring = sys.monitoring
    events = monitoring.events
    tool = monitoring.PROFILER_ID
    imported = time.time()
    main = _thread.get_ident()
    targets = {}
    frames = {}
    spans = []

    def target(code):
        if code not in targets:
            targets[code] = next(
                (
                    (key, names)
                    for key, names in functions.items()
                    if code.co_qualname == key.rsplit(":", 1)[1]
                    and code.co_filename.endswith(key.rsplit(":", 1)[0])
                ),
                None,
            )
        return targets[code]

    def open_span(code, frame):
        key, names = targets[code]
        entry = frames.get(id(frame))
        if entry is None or entry["frame"] is not frame:
            args = {name: _plain(frame.f_locals.get(name)) for name in names}
            entry = frames[id(frame)] = {"frame": frame, "args": args, "part": 0}
        entry["span"] = {
            "fn": key,
            "args": entry["args"],
            "part": entry["part"],
            "main": _thread.get_ident() == main,
            "start": time.time(),
        }

    def close_span(frame, last):
        entry = frames.get(id(frame))
        if entry is None or entry["frame"] is not frame:
            return
        if span := entry.pop("span", None):
            span["end"] = time.time()
            spans.append(span)
            entry["part"] += 1
        if last:
            del frames[id(frame)]

    # The callbacks for local events disable every code object that is not a target.
    # PY_THROW and PY_UNWIND are global events, which cannot be disabled per code
    # object, but a target has passed PY_START before either can reach it.
    def started(code, _offset):
        if target(code) is None:
            return monitoring.DISABLE
        open_span(code, sys._getframe(1))
        return None

    def yielded(code, _offset, _value):
        if target(code) is None:
            return monitoring.DISABLE
        close_span(sys._getframe(1), last=False)
        return None

    def returned(code, _offset, _value):
        if target(code) is None:
            return monitoring.DISABLE
        close_span(sys._getframe(1), last=True)
        return None

    def thrown(code, _offset, _exception):
        if targets.get(code):
            open_span(code, sys._getframe(1))

    def unwound(code, _offset, _exception):
        if targets.get(code):
            close_span(sys._getframe(1), last=True)

    callbacks = {
        events.PY_START: started,
        events.PY_RESUME: started,
        events.PY_THROW: thrown,
        events.PY_YIELD: yielded,
        events.PY_RETURN: returned,
        events.PY_UNWIND: unwound,
    }
    monitoring.use_tool_id(tool, "leaf-bench")
    for event, callback in callbacks.items():
        monitoring.register_callback(tool, event, callback)
    monitoring.set_events(tool, sum(callbacks))

    def write():
        monitoring.set_events(tool, 0)
        cpu = os.times()
        reading = {
            "imported": imported,
            "exited": time.time(),
            "cpu": {
                "self": cpu.user + cpu.system,
                "children": cpu.children_user + cpu.children_system,
            },
            "spans": spans,
        }
        with open(out, "w", encoding="utf-8") as file:
            json.dump(reading, file)

    atexit.register(write)


if out := os.environ.pop("LEAF_BENCH_TRACE", None):
    _install(out, json.loads(os.environ.get("LEAF_BENCH_FUNCTIONS", "{}")))
