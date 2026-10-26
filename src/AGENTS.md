# The Python side

`leaf/` is the package a harness installs, and `leaf/cli.py` declares its commands
(`leaf/__main__.py` says how they run). `cli.py` only parses and dispatches; domain
logic, and any branching across modules, belongs in the module that owns it.

Each module owns one concern and states its contract in its header, so read the headers
to find an owner (`head -n 3 leaf/*.py leaf/*/*.py`). Callers import the
owning module directly; a subpackage's `__init__.py` is only a marker, never a second
API. Domain code refuses by raising `refusals.Refused` or a subclass; only a process or
transport boundary exits, prints or answers HTTP. A command returns its result and
never prints it (`cli.py`'s header).

Some owners are the one way to do something anywhere in the package: every event is
appended through `event_contracts.append_admitted`, every finding a check reports or
note a command prints is a `findings` record, and every JSON record Leaf keeps outside a
page's log and document is a `state.Record`.

## Protocol references

Each boundary shared across modules or runtimes has its reference beside the code:

- `leaf/page-storage.md`: page files and atomic state;
- `leaf/events.md`: what each event kind means, admission, threads, undo, edits and
  reactions;
- `leaf/layer-registry.md`: composition, vendoring and layer versions;
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
