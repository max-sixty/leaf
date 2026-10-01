# The Python side

`leaf/` is the package a host installs. `leaf/cli.py` declares the commands, the
`leaf` console script exposes them, and `leaf/__main__.py` runs them as
`python -m leaf`, the form `bin/leaf` and every leaf subprocess use. `cli.py` stays
a facade: domain logic, and any branching across the owners below, belongs in the
owning module.

Each module owns one concern and states its contract in its header. Callers import
the owning module directly; a subpackage's initializer is only a marker, never a
second API.

## Owners

- `files`, `revisioning`, `revision_artifact`, `revision_delivery`: page files,
  immutable revisions with their captured inputs and held readings, and delivery;
- `locations`: filesystem path identity, containment, and overlap;
- `page`: vendored page guidance;
- `event_log`: append-only JSONL storage, locking, and attempt identity;
- `event_contracts`: the one append door every writer admits an event through;
- `page_view`: what that door may read about a page;
- `event_endpoint`: the browser's HTTP route onto the door;
- `event_meaning`: admitted widget-command meaning and layer compatibility;
- `interaction_log`: page-local diagnostics of browser gestures and requests;
- `events`, `projection`, `document_reading`, `construction`: folds over standing
  events and durable state, the shared document and decision reading, and a
  thread's frozen markup as effective content;
- `page_snapshot`: the transaction-consistent reading one browser preview serves;
- `agent_state`, `read_state`, `gesture_words`, `history`, `transcript`: the
  agent-facing page and thread readings, what the user has not read, what a
  gesture's ids say, `x-history` rows, and the Markdown export;
- `thread_context`, `thread`: thread identity, frozen markup, delivery context,
  thread writes, and the reply lifecycle;
- `workflows`, `activity`: unsettled user inputs with their evidence, and the
  page-level reading over workflows, status, claim, turn, and watcher;
- `asks`: page and thread Asks, which every surface reads from here;
- `work`: transient subject claims and widget work seats;
- `delivery`, `session`, `hooks`, `hook_carrier`, `host`: the delivery envelope and
  its receipt, status and the `leaf wait` watch, the host hooks' entry, the prompt
  and Stop hooks as a Claude Code session's carrier, and harness declarations;
- `codex`, `codex_adapter`: a Codex task's delivery records and turn folds, and the
  detached carrier behind `leaf codex start`;
- `thread_titles`: a new thread's title, asked of the host's model;
- `state_paths`, `machine`, `leases`, `service`, `server`, `hosting`, `detached`:
  state-home paths and cold session cleanup, process readings, process-backed
  leases (`take_lease`, `release_lease`), page claims and serialized transactions,
  server state, HTTP servers, and detached starts;
- `presence`: page, claim, and neighboring-leaf presence;
- `samples`: disposable child pages built from captured templates;
- `http`: HTTP transport and routes for one served page;
- `layer`, `packages`, `vendoring`: package discovery and composition, package
  authoring gates, and page init and layer transitions;
- `schema`, `structure`, `styles`: the layer schema and the parsed source with its
  structural and CSS readings;
- `passages`, `anchor_capture`: the file-side text reading and anchor capture;
- `render_checks`: the named browser probes, whose page-side code is
  `render-checks/`;
- `exporting`: a stamped version as one offline file;
- `data`, `data_contracts`: page-bound data storage, bindings, and contract checks;
- `media`, `publishing`, `live_shell`: page media, public version stamps, and the
  static files a host serves beside Leaf's API.

Within `registry/`, `contract` owns shared schema helpers, `kernel` the kernel
event contract, `layer`, `widgets`, and `state` their vocabulary contracts,
`validation` the composed gate, `page` page-owned declarations and provenance,
`storage` the vendored-file cache, and `reactions` reaction descriptions.

Within `served_state/`, `wire` serializes one declared fold, `thread` and `document`
own their scoped readings, `browser` assembles the requested views, `page` composes
the response, `reading` names the filesystem changes the news stream reports, and
`service` owns the page transaction every route reads through.

Within `render_gate/`, `command` owns the CLI boundary, `browser` the browser
launch, `scheme` one color scheme's lifecycle, `readings` the probe readings and
their findings, `version` retry policy, `page_code` the run of a page's own code,
`preview` ephemeral servers, `screens` the screens a passing check saves for the
author, and `widget_quality` the report `package check --render` gives a widget's
author, which refuses nothing.

Within `validation/`, `markup` owns shared document structure, `instances`
registry-declared instance rules, `admission` what an agent's writer hands in,
`compatibility` layer changes against the standing log, `source_history`
predecessor readings, `transitions` revisions against standing actions, `source`
the composed static gate, and `command` the CLI and render handoff.

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
