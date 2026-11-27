# The Python side

`leaf/` is the package a harness installs, and `leaf/commands/cli.py` declares its commands
(`leaf/__main__.py` says how they run). `cli.py` only parses and dispatches; domain
logic, and any branching across modules, belongs in the module that owns it.

Each module owns one concern and states its contract in its header, and each layer
package's `__init__.py` says what the package holds, so read the headers to find an
owner (`head -n 3 leaf/*/*.py leaf/*/*/*.py`). Callers import the owning module
directly; a package's `__init__.py` holds only its header, never a second API. The
packages stand in one order, a module imports only from its own package and the
packages below it, and the modules inside a package import each other without a cycle
(`../.config/importlinter.ini`, whose header says what to do when a change breaks
either rule).
A module imports what it uses at its top, so the top lists what it depends on. An
import goes inside a function only where loading it with its module would add
start-up work to a process a harness or agent starts often, such as a hook or a
`leaf` command, that loads the module without calling the function; would fail on a
platform Leaf supports; or would set off an effect, as importing `agents/codex.py`
registers an exit handler.
Domain code refuses by raising `refusals.Refused` or a subclass; only a process or
transport boundary exits, prints or answers HTTP. A command returns its result and
never prints it (`cli.py`'s header).

Some owners are the one way to do something anywhere in the package: every event is
appended through `event_contracts.append_admitted`, every finding a check reports or
note a command prints is a `findings` record, and every JSON record Leaf keeps outside a
page's log and document is a `state.Record`. Whether a session is live, and whether its
turn is open or closed, is asked of `state.session_live`, `state.turn_open` and
`state.turn_closed`, whether the caller holds the session record, a claim or the page's
served reading of it. A setting the user states once for every Leaf on the machine,
such as the host new pages are served on, is a key of the config file that
`machine.settings` reads, since each harness starts Leaf from an environment of its own.

## Protocol references

Each boundary shared across modules or runtimes has its reference beside the code:

- `leaf/page-storage.md`: page files and atomic state;
- `leaf/events.md`: what each event kind means, admission, threads, undo, edits and
  reactions;
- `leaf/layer-registry.md`: composition, the layer record and the page protocol;
- `leaf/session-lifetime.md`: claims, watchers and service lifetime;
- `leaf/validation.md`: where each input is validated, static and browser checks, and
  file-side passages.

`../skills/leaf/references/packages.md` owns the public package contract, and
`../browser/AGENTS.md` the browser's side.

A reference states what code on one side of its boundary may rely on from the other:
each shared record or event and what it means, who may write it, when a reader must
stop using it, and the orderings a change elsewhere must keep. How one module provides
that, such as its functions, constants, retries and the races it closes, goes in that
module's header.
