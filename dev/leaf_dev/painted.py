"""When a page first painted each goal a benchmark waits for, read in the page by
`painted.js`, which a command installs as an init script before the page loads.

`window.__leafBench.arm(goals)` starts sampling each frame after it paints for the
goals, each `{name, fact, arg}`, where `fact` names one of the script's `facts`, such
as `delivered`, the server's reading of the gesture's own event presented. `watch()`
then gives each goal's `at`, the epoch milliseconds of the first painted frame that
met it, and `input()` the gesture's input, which its time counts from. `disarm()`
stops the sampling, and `met(fact, arg)` reads one fact once. `leaf-dev bench` times
its inputs this way.
"""

from pathlib import Path

SCRIPT = Path(__file__).with_suffix(".js")
