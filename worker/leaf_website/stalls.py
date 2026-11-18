"""Report a leaf.page container that stops running or stops answering.

When nothing in a container answers, a request the Workers runtime sends to it fails
with "Container is taking too long to accept the connection". That happens whether
the host stopped running the container or the container's own server stopped
serving, and the request's record can't say which. The first is Cloudflare's to
repair and the second Leaf's. A thread inside the container tells them apart more
often than not. Every second it wakes, sends the server a health check over
loopback, and looks at the one it sent a second earlier. It writes a record only when
something was late:

- `container_stalled`: the thread itself woke `stalledMs` late, so none of this
  process's Python threads ran meanwhile. `cpuMs` is the CPU the machine used over
  that tick. Near `stalledMs`, the container's own work held the CPU or the
  interpreter; near zero, nothing in the container ran, as when the host stops
  running its VM. `stealMs` is time the host gave the CPU to something else while
  the container waited for it, and `pressureMs` the time the kernel kept tasks
  waiting for CPU, memory or IO.
- `container_unresponsive`: the thread woke on time, but the server had not begun
  answering the previous health check. `stack` holds the frames the serving thread,
  which accepts every connection, is in. A Leaf frame there names the code holding
  the event loop; the event loop's own `select` means the delay is in the thread
  running the health route instead. A record comes once per health check, and the
  next check starts once this one is answered.

A health check in flight across a stall waited through the stall too, so the stall's
record covers it and the check is dropped. The counters are the kernel's, for the
whole machine. Cloudflare runs each container in a Firecracker VM of its own, so
there they are the container's. A record leaves out a counter the kernel doesn't
expose, and holds code locations and counts, never request or page content.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path

# The runtime waits several seconds before it gives up on a connection, so a stall
# shorter than a tick fails no request, and a longer one is rare enough to record.
TICK_SECONDS = 1.0
STACK_FRAMES = 8
HEALTH_REQUEST = b"GET /health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"


def watch_stalls(port: int, record: Callable[..., None]) -> threading.Thread:
    """Watch this container from a daemon thread, recording through `record`."""
    serving = threading.main_thread().ident
    assert serving is not None
    thread = threading.Thread(
        target=_watch,
        args=(port, serving, record),
        name="leaf-stall-watch",
        daemon=True,
    )
    thread.start()
    return thread


def _watch(port: int, serving: int, record: Callable[..., None]) -> None:
    before = counters()
    check: socket.socket | None = None
    reported = False
    tick = time.monotonic() + TICK_SECONDS
    while True:
        # Each tick is due a tick after the last one woke, so a stall anywhere in the
        # loop, the health check's connection included, makes the next one late.
        time.sleep(max(0.0, tick - time.monotonic()))
        late = time.monotonic() - tick
        tick = time.monotonic() + TICK_SECONDS
        after = counters()
        if late >= TICK_SECONDS:
            record("container_stalled", stalledMs=_ms(late), **spent(before, after))
            check = _drop(check)
        elif check is not None and answered(check):
            check = _drop(check)
        elif check is not None and not reported:
            record(
                "container_unresponsive",
                stack=thread_stack(serving),
                **spent(before, after),
            )
            reported = True
        before = after
        if check is None:
            reported = False
            try:
                check = send_health_check(port)
            except ConnectionRefusedError:
                return  # The server closed its listener: the container is stopping.
            except OSError:
                pass  # The next tick sends another, or reports the stall behind this.


def send_health_check(port: int) -> socket.socket:
    """Ask the server for `/health`, returning the socket its answer will arrive on."""
    check = socket.create_connection(("127.0.0.1", port), timeout=TICK_SECONDS)
    try:
        check.sendall(HEALTH_REQUEST)
    except OSError:
        check.close()
        raise
    check.setblocking(False)
    return check


def answered(check: socket.socket) -> bool:
    """Whether the server has begun answering, or closed, a health check."""
    try:
        check.recv(1, socket.MSG_PEEK)
    except BlockingIOError:
        return False
    except OSError:
        return True
    return True


def _drop(check: socket.socket | None) -> None:
    if check is not None:
        check.close()


def thread_stack(ident: int) -> list[str]:
    """The innermost frames of one thread, as `package/module.py:function:line`."""
    frame = sys._current_frames().get(ident)
    if frame is None:
        return []
    return [
        f"{'/'.join(Path(entry.filename).parts[-2:])}:{entry.name}:{entry.lineno}"
        for entry in traceback.extract_stack(frame)[-STACK_FRAMES:]
    ]


def counters() -> dict[str, float]:
    """The machine's cumulative busy CPU, steal and stall times in milliseconds, and
    the memory in use in MiB."""
    readings: dict[str, float] = {}
    if (stat := _read("/proc/stat")) is not None:
        # The aggregate line counts clock ticks: user nice system idle iowait irq
        # softirq steal, then guest time, which user already includes.
        ticks = [int(value) for value in stat.split("\n", 1)[0].split()[1:9]]
        tick_ms = 1000 / os.sysconf("SC_CLK_TCK")
        user, nice, system, _idle, _iowait, irq, softirq, steal = ticks
        readings["cpu"] = (user + nice + system + irq + softirq) * tick_ms
        readings["steal"] = steal * tick_ms
    for resource in ("cpu", "memory", "io"):
        if (pressure := _read(f"/proc/pressure/{resource}")) is not None:
            some = pressure.splitlines()[0]
            readings[f"pressure.{resource}"] = int(some.rsplit("total=", 1)[1]) / 1000
    if (meminfo := _read("/proc/meminfo")) is not None:
        kib = {
            line.split(":")[0]: int(line.split()[1]) for line in meminfo.splitlines()
        }
        readings["memory"] = (kib["MemTotal"] - kib["MemAvailable"]) / 1024
    return readings


def spent(before: dict[str, float], after: dict[str, float]) -> dict:
    """The record fields for what the machine did between two readings."""
    fields: dict = {}
    if "cpu" in after:
        fields["cpuMs"] = round(after["cpu"] - before["cpu"])
        fields["stealMs"] = round(after["steal"] - before["steal"])
    pressure = {
        key.removeprefix("pressure."): round(after[key] - before[key])
        for key in after
        if key.startswith("pressure.")
    }
    if pressure:
        fields["pressureMs"] = pressure
    if "memory" in after:
        fields["memoryMiB"] = round(after["memory"])
    return fields


def _read(path: str) -> str | None:
    """A kernel counter file's text, or None where this kernel doesn't provide it:
    the file is absent, or, for pressure with PSI disabled, refuses the read."""
    try:
        return Path(path).read_text()
    except OSError:
        return None


def _ms(seconds: float) -> int:
    return round(seconds * 1000)
