# The Python side

`leaf/` is the package a harness installs. `leaf/cli.py` declares the commands, and
`leaf/__main__.py` runs them as `python -m leaf`, the form `bin/leaf` and every leaf
subprocess use. `cli.py` only parses and dispatches; domain logic, and any branching
across the modules below, belongs in the module that owns it.

Each module owns one concern and states its contract in its header. Callers import the
owning module directly; a subpackage's `__init__.py` is only a marker, never a second
API. Domain code refuses by raising `refusals.Refused` or a subclass; only a process or
transport boundary exits, prints or answers HTTP.

## Owners

- `refusals`: the refusal exception and its reason;
- `files`, `revisioning`, `revision_artifact`, `revision_delivery`: atomic page
  files, immutable revisions, the inputs each captures, and delivery URLs;
- `locations`: path identity, containment and overlap;
- `file_changes`: native file-change subscriptions shared by pages, sessions and
  previews;
- `file_bindings`: local file grants, revision-checked writes and cross-page target
  locks, kept outside the page's event log;
- `page_memory`: how long a process caches a page: while it is among the eight read
  most recently;
- `page`: vendored page instructions;
- `event_log`: append-only JSONL storage;
- `event_contracts`: the one function every writer appends an event through;
- `page_view`: the page as that function reads it;
- `event_endpoint`: the browser's HTTP route to it;
- `event_meaning`: the meaning recorded for a widget command, and layer compatibility;
- `interaction_log`: page-local diagnostics of browser gestures and requests;
- `events`, `projection`, `document_reading`, `construction`: current state from the
  events still in force, the shared document and decision reading, and a thread's
  frozen markup with its origins;
- `page_snapshot`: the consistent state one browser preview serves;
- `agent_state`, `read_state`, `gesture_words`, `history`, `transcript`: what the
  agent reads of a page and thread, what the user hasn't read, what a gesture's ids
  say, newest events for `x-history`, and the Markdown export;
- `thread_context`, `thread`: thread identity, frozen markup, delivery context,
  thread writes and reply reservations;
- `work_reading`: the durable work state shared by admission, serving and delivery;
- `workflows`, `activity`: unfinished updates with their evidence, and the page-level
  summary over workflows, to-dos, status, claim, turn and watcher;
- `asks`: every widget and prose ask, with typed answers, completion and attention;
- `work`: what an id names, which widgets hold a to-do, and which widget to-dos a
  version would leave without a target;
- `todos` (experimental): committed work on either side until it ends, the `start`
  that takes an update or to-do in hand, and `leaf task`. Asks never become to-dos;
- `delivery`, `session`, `hooks`, `hook_transport`, `harness`: the delivery envelope
  and receipt, status and the `leaf wait` watch, the harness hooks' entry, the prompt
  and Stop hooks as a session's transport, and harness declarations;
- `reconnect`: which outages get a notice, once per outage;
- `codex_state`, `codex`, `codex_adapter`: Codex delivery eligibility and records, App
  Server reply lifecycles, and the detached adapter behind `leaf codex start`;
- `thread_titles`: the title Leaf asks the harness's model for when a user opens a
  thread;
- `state`: session lifetime and turn publication, cold SessionEnd, shared paths, page
  identity, locks and atomic replacement, with no dependencies on the rest;
- `machine`, `leases`, `service`, `server`, `hosting`, `detached`: process readings,
  process-backed leases (`take_lease`, `release_lease`), page claims and serialized
  transactions, server state, HTTP servers, and detached starts;
- `bridge`: the bridge Leaf's Claude Code hooks keep outside Claude Code's
  sandbox, which runs each `leaf` command the sandbox confines;
- `presence`: page, claim and neighboring-leaf presence;
- `server_rows`: the summary row each serving page publishes for its neighbors;
- `user_views`: disposable per-document browser observations;
- `samples`, `sample_content`: live samples' child pages and their starting histories;
- `http`: HTTP transport;
- `layer`, `packages`, `vendoring`: package discovery and composition, package
  checks, and page init and layer changes;
- `schema`: the layer's JSON schemas and the page-directory vocabulary;
- `structure`, `styles`: authored-page checks and the full source reading;
- `passages`, `anchor_capture`: the file-side text reading and anchor construction;
- `render_checks`: browser probes;
- `findings`: the record every `page check` finding and every command note uses, and
  their words;
- `exporting`: a stamped version as one offline file;
- `data`, `data_contracts`: typed snapshot storage, bindings and contract checks;
- `media`, `publishing`, `live_shell`: page media, public version stamps, and the
  static files a host serves beside Leaf's API.

Within `registry/`, `contract` reads vocabulary and derives declarations, `schema` is
the offline JSON Schema engine, `kernel` holds the fixed kernel event contract,
`layer`, `widgets` and `state` own their vocabulary contracts, `validation` composes
those checks, `page` composes page-owned declarations, `storage` caches vendored files,
and `reactions` describes reactions.

Within `served_state/`, `context` holds the live or captured inputs every reading uses,
`work` adds live activity and reply reservations to the durable work state, `wire`
serializes one reading, `thread` and `document` own their scoped readings, `queues`
selects the work queues each view serves and `page state` prints, `browser` assembles
the requested views, `page` composes the response, `reading` names file changes for
freshness reads, and `service` owns the page source every route reads (the live
directory or a `page_snapshot` capture) and its transaction.

Within `render_gate/`, `scheme` owns one browser and color-scheme run, `readings` the
probe readings and the findings they become, `version` retries, `page_code` the run
plain `page check` makes, `preview` temporary servers, `browser` the browser's launch and
exit, `screens` the screenshots a passing check saves, `picture` the image
`page picture` draws of a drawing comment, `command` the CLI, and `widget_quality` the
report `package check --render` gives a widget's author, which never fails a check.

Within `validation/`, `markup` owns shared document structure, `instances` the
registry-declared instance rules, `admission` what an agent's write hands in,
`composition` a composed registry's catalog examples and the registry `page init`
vendors, `source_history` predecessor readings and automatic anchor relocation,
`source` validation of the current document, and `command` the CLI and the handoff to
the render check.

## Protocol references

Each boundary shared across modules or runtimes has its reference beside the code:

- `leaf/page-storage.md`: page files and atomic state;
- `leaf/events.md`: what each event kind means, admission, threads, undo, edits and
  reactions;
- `leaf/layer-registry.md`: composition, vendoring and layer versions;
- `leaf/session-lifetime.md`: claims, watchers and service lifetime;
- `leaf/validation.md`: where each input is validated, static and browser checks, and
  file-side passages.

`../references/packages.md` owns the public package contract, and
`../assets/AGENTS.md` the browser's side.
