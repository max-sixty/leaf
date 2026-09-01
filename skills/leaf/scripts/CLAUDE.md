# The Python side

This directory owns the CLI, page files, event log, service lifetime, validation,
projection, rendering, and publishing. It is the project's module root, so
`leaf/` is the package a host installs. `leaf/cli.py` composes the commands;
`leaf/__main__.py` is the CLI as `python -m leaf`, the form `bin/leaf` and every
leaf subprocess run it in, and the `leaf` console script is the same entry for
the hook guard and a developer's `uv run leaf`. Keep `cli.py` a facade over the
domain modules.

The main owners are:

- `files` and `revisioning`: atomic page files and immutable revisions;
- `locations`: filesystem path identity, containment, and overlap;
- `page`: vendored page guidance;
- `agent_state`: the agent-facing folded page-state reading;
- `transcript`: raw-event selection and the human-facing Markdown export;
- `event_log`: append-only JSONL storage, locking, and attempt identity;
- `event_endpoint` and `event_contracts`: browser-event admission, retry
  coordination and append, and shared browser/CLI event contracts;
- `events` and `projection`: standing event and durable state folds;
- `thread_context` and `conversation`: thread identity, frozen markup, bounded
  delivery context, and conversation writes;
- `acknowledgments` and `work`: growing delivery receipts, transient work
  claims, and widget work seats;
- `decisions`: declaration-driven page and thread decision projections;
- `requests`: declared request seats, their canonical lifecycle, and the
  terminal host receipts that close one;
- `host`: local paths, process readings, host identity, and session lifetime;
- `leases`: process-backed page, transition, and waiter leases;
- `service`: page claims, serialized transactions, and status;
- `server` and `hosting`: server address and lifetime state, and the HTTP process;
- `session` and `hooks`: direct wait delivery and host lifecycle;
- `codex`: detached Codex queue delivery and recovery;
- `mcp_server` and `mcp_app`: the bundled MCP transport, app resource, private
  page snapshot, and host handoff;
- `presence`: page, claim, and neighboring-leaf presence readings;
- `served_state/` and `http`: browser-facing projections and change readings,
  and HTTP transport;
- `registry/`: registry vocabulary contracts, composition validation, storage,
  and page-facing readings;
- `layer`: package discovery and layer composition;
- `packages`: package authoring commands and filesystem safety gates;
- `vendoring`: page initialization, layer transitions, and atomic installation;
- `schema`, `structure`, `styles`, and `validation/`: authored-page gates, the
  complete source reading, and the `version check` command;
- `passages` and `anchor_capture`: the file-side text reading and authored
  anchor construction;
- `render_checks`, `render_gate/`, and `exporting`: browser probes, validation,
  and standalone export;
- `data` and `data_contracts`: typed snapshot storage, commands, bindings, and
  registry-contract validation;
- `media` and `publishing`: page-bound media and deployment outputs.

Do not put domain logic into `cli.py` or branch across these owners there.

## Protocol references

Read the reference that owns the boundary before changing it:

- `../references/internals/page-storage.md` for page files and atomic state;
- `../references/internals/events.md` for event shapes, conversations, undo,
  edits, and reactions;
- `../references/internals/layer-registry.md` for composition, vendoring, and
  layer generations;
- `../references/internals/session-lifetime.md` for claims, watchers, and
  service lifetime;
- `../references/internals/validation.md` for static checks, browser checks,
  parsed source, and file-side passages.
- `../references/internals/mcp-app.md` for MCP tools, resource metadata, host
  messages, and delivery acknowledgement.

`../references/packages.md` owns the public package contract. The browser's
parallel projection, passage, registry, and render rules live in `../CLAUDE.md`.

## Boundaries

Validate once at the public door and pass trusted structures inward. Static
validation stays deterministic and browser-free; computed layout and module
writes belong to the render gate. Use the shared parser or projection for a
question it already answers instead of reconstructing it from source text,
events, CSS selectors, or tag names.

The page directory and append-only log are the authorities described in the
root instructions. A derived reading is not another store. Preserve atomic file
writes, immutable revision and version files, and the existing lock boundaries
when adding a command.

The registry is the common contract with the browser. Server-side event gates,
state folds, package checks, markup validation, and agent queries consume its
declarations without a widget-name list.

Within `registry/`, `contract` owns shared schema helpers and layer readings,
`layer`, `widgets`, and `state` own their complete vocabulary contracts,
`validation` composes those gates, `storage` owns the vendored-file cache and
page lookup, and `reactions` owns reaction descriptions. Import the owner
directly; the package initializer is only a marker.

Within `served_state/`, `wire` serializes one declared fold, `conversation` and
`document` own their scoped browser readings, `browser` assembles the requested
views, `page` composes the complete served response, and `reading` names
filesystem changes for the news stream. `service` owns the transport-neutral
transaction that HTTP and MCP share. Import the owner directly; the package
initializer is only a marker.

Within `render_gate/`, `models` owns the values passed between phases, `scheme`
owns one browser/color lifecycle, `readings` owns raw probe results, `reporting`
owns human findings, `version` owns retry policy, `preview` owns ephemeral
servers, and `command` owns the CLI boundary. Import the owner directly; the
package initializer is only a marker.

Within `validation/`, `markup` owns shared document structure rules, `instances`
owns registry-declared instance rules, `admission` owns incoming message markup,
`compatibility` owns layer changes against the standing log, `source_history`
owns predecessor readings and continuity, `transitions` compares authored
revisions with standing actions and reports, `source` composes those gates into
one reading, and `command` owns its CLI and render handoff. Import the owner
directly; the package initializer is only a marker, not a second API to maintain.
