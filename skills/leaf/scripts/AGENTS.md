# The Python side

This directory is the project's module root, and `leaf/` is the package a host
installs. `leaf/__main__.py` is the CLI as `python -m leaf`, which `bin/leaf` and
every leaf subprocess run; the `leaf` console script is the same entry. `leaf/cli.py`
composes the commands and stays a facade: domain logic, and any branching across the
owners below, belongs in the owning module.

Each module owns one concern, and callers import the owning module directly. Each
subpackage's initializer is only a marker, never a second API.

## Owners

- `files`, `revisioning`, `revision_artifact`, `revision_delivery`: atomic page
  files, immutable revisions, their captured inputs and held readings, and delivery
  URLs;
- `locations`: filesystem path identity, containment, and overlap;
- `page_memory`: how long a process keeps what it read of a page: while the page is
  among the eight it read most recently;
- `page`: vendored page instructions;
- `event_log`: append-only JSONL storage and attempt identity;
- `event_contracts`: the one append door every writer admits an event through;
- `page_view`: the page as that door reads it;
- `event_endpoint`: the browser's HTTP transport onto the door;
- `event_meaning`: admitted widget-command meaning and layer compatibility;
- `interaction_log`: page-local diagnostics of browser gestures and requests;
- `events`, `projection`, `document_reading`, `construction`: standing event and
  durable state folds, the shared document and decision reading, and a thread's
  frozen markup as effective content with its origins;
- `page_snapshot`: the transaction-consistent reading one browser preview serves;
- `agent_state`, `read_state`, `gesture_words`, `history`, `transcript`: agent-facing
  page and thread readings, what the user has not read, what a gesture's ids say,
  newest moves for `x-history`, and the Markdown export;
- `thread_context`, `thread`: thread identity, frozen markup, delivery context,
  thread writes, and the reply lifecycle;
- `workflows`, `activity`: unsettled user moves with their evidence, and the
  page-level fold over workflows, status, claim, turn, and watcher;
- `asks`: the one implementation of page and thread Asks, which every surface reads;
- `work`: transient subject claims and widget work seats;
- `delivery`, `session`, `hooks`, `hook_carrier`, `host`: the delivery envelope
  and its receipt, status and the `leaf wait` watch, the host hooks' entry, the
  prompt and Stop hooks as a session's carrier, and harness declarations;
- `codex_state`: Codex delivery eligibility and shared delivery serialization paths;
- `codex`, `codex_adapter`: Codex delivery records and App Server turn folds, and
  the detached carrier behind `leaf codex start`;
- `thread_titles`: the title Leaf asks the host's model for when a user opens a
  thread, before the agent's reply could name it;
- `state`: dependency-free session lifetime and turn publication, standalone cold
  SessionEnd, shared paths, page identity, locks and durable replacement;
- `machine`, `leases`, `service`, `server`, `hosting`, `detached`:
  process readings,
  process-backed leases taken through `take_lease` and `release_lease`, page
  claims and serialized transactions, server state, HTTP servers, and detached
  starts;
- `presence`: page, claim, and neighboring-leaf presence;
- `user_views`: disposable per-document browser observations and passive check context;
- `samples`, `sample_content`: disposable child pages built from captured templates,
  and their initial histories admitted from parent threads or authored fixture commands;
- `http`: HTTP transport;
- `layer`, `packages`, `vendoring`: package discovery and composition, package
  authoring gates, and page init and layer transitions;
- `schema`, `structure`, `styles`: authored-page gates and the complete source
  reading;
- `passages`, `anchor_capture`: the file-side text reading and anchor construction;
- `render_checks`: browser probes;
- `exporting`: a stamped version as one offline file;
- `data`, `data_contracts`: typed snapshot storage, bindings, and contract checks;
- `media`, `publishing`, `live_shell`: page-bound media, public version stamps, and
  the static files a host serves beside Leaf's API.

Within `registry/`, `contract` owns vocabulary readings and derived declarations,
`schema` the offline JSON Schema engine, and `kernel` the fixed
kernel event contract, `layer`, `widgets`, and `state` own their vocabulary
contracts, `validation` composes those gates, `page` composes page-owned
declarations and provenance, `storage` owns the vendored-file cache, and
`reactions` owns reaction descriptions.

Within `served_state/`, `context` owns the live or captured inputs every fold reads;
`wire` serializes one declared fold, `thread` and `document`
own their scoped readings, `browser` assembles the requested views, `page` composes
the served response, `reading` names filesystem changes for freshness reads, and
`service` owns the page transaction every route reads through.

Within `render_gate/`, `scheme` owns one browser and color lifecycle, `readings` owns
the probe readings and their findings, `version` owns retry policy, `page_code` owns
the run plain `page check` and message markup take, `preview` owns ephemeral servers, `browser` owns the
browser launch, `screens` owns the screens a passing check saves for the author, and
`command` owns the CLI boundary, and `widget_quality` owns the report `package check
--render` gives a widget's author, which refuses nothing.

Within `validation/`, `markup` owns shared document structure, `instances` owns
registry-declared instance rules, `admission` owns what an agent's writer hands in,
`compatibility` owns layer changes against the standing log, `source_history` owns
predecessor readings, `transitions` compares revisions with standing actions,
`source` composes those gates, and `command` owns the CLI and render handoff.

## Protocol references

The references that own each boundary:

- `leaf/page-storage.md` for page files and atomic state;
- `leaf/events.md` for event shapes, threads, undo, edits, and reactions;
- `leaf/layer-registry.md` for composition, vendoring, and layer generations;
- `leaf/session-lifetime.md` for claims, watchers, and service lifetime;
- `leaf/validation.md` for where each input is validated, static and browser checks,
  parsed source, and file-side passages.

`../references/packages.md` owns the public package contract, and
`../assets/AGENTS.md` owns the browser's parallel projection, passage, registry, and
render rules.
