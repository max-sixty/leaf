# The Python side

`leaf/` is the package a host installs. `leaf/cli.py` declares the commands, and
`leaf/__main__.py` runs them as `python -m leaf`, the form `bin/leaf` and every leaf
subprocess use. `cli.py` stays a facade: domain logic, and any branching across the
owners below, belongs in the owning module.

Each module owns one concern and states its contract in its header. Callers import
the owning module directly; a subpackage's initializer is only a marker, never a
second API.

## Owners

- page files and revisions: `files`, `revisioning`, `revision_artifact`,
  `revision_delivery`, `locations`, `page`, `samples`, `data`, `data_contracts`,
  `media`, `publishing`, `live_shell`, `exporting`;
- the event log and its one append door: `event_log`, `event_contracts`, `page_view`,
  `event_endpoint`, `event_meaning`, `interaction_log`;
- readings over the log: `events`, `projection`, `document_reading`, `construction`,
  `page_snapshot`, `agent_state`, `read_state`, `gesture_words`, `history`,
  `transcript`, `asks`, `work`, `workflows`, `activity`;
- threads: `thread_context`, `thread`, `thread_titles`;
- delivery and hosts: `delivery`, `session`, `hooks`, `hook_carrier`, `host`, `codex`,
  `codex_adapter`;
- processes and servers: `state_paths`, `machine`, `leases`, `service`, `server`,
  `hosting`, `detached`, `presence`, `http`;
- layers and source: `layer`, `packages`, `vendoring`, `schema`, `structure`,
  `styles`, `passages`, `anchor_capture`, `render_checks` (its page-side code is
  `render-checks/`).

Within `registry/`: `contract`, `kernel`, `layer`, `widgets`, `state`, `validation`,
`page`, `storage`, and `reactions`.

Within `served_state/`: `wire`, `thread`, `document`, `browser`, `page`, `reading`, and
`service`, which owns the page transaction every route reads through.

Within `render_gate/`: `command`, `browser`, `scheme`, `readings`, `version`,
`page_code`, `preview`, `screens`, and `widget_quality`, the report `package check
--render` gives a widget's author, which refuses nothing.

Within `validation/`: `markup`, `instances`, `admission`, `compatibility`,
`source_history`, `transitions`, `source`, and `command`.

## Protocol references

Each boundary shared across modules or runtimes has its reference beside the code:

- `leaf/page-storage.md`: page files and atomic state;
- `leaf/events.md`: what each event kind means, admission, threads, undo, edits, and
  reactions;
- `leaf/layer-registry.md`: composition, vendoring, and layer generations;
- `leaf/session-lifetime.md`: claims, watchers, and service lifetime;
- `leaf/validation.md`: where each input is validated, static and browser checks,
  parsed source, and file-side passages.

`../references/packages.md` owns the public package contract, and
`../assets/AGENTS.md` the browser's side of projection, passages, the registry,
and rendering.
