# The Python side

This directory owns the CLI, page files, event log, service lifetime, validation,
projection, rendering, and publishing. `interact.py` is the PEP 723 entrypoint;
`leaf/cli.py` composes the commands. Keep both as facades over the domain modules.

The main owners are:

- `files` and `revisioning`: atomic page files and immutable revisions;
- `page`: vendored page guidance and vocabulary catalog;
- `agent_state`: the agent-facing folded page-state reading;
- `event_log`: append-only JSONL storage, locking, and attempt identity;
- `event_endpoint`: browser-event admission, retry coordination, and append;
- `events`, `conversation`, `projection`, and `work`: event folds, durable state,
  and their standing readings;
- `asks`: declaration-driven page and thread request projections;
- `session`, `service`, `hosting`, and `hooks`: host identity, process lifetime,
  and leases;
- `served_state` and `http`: browser-facing state readings and HTTP transport;
- `registry` and `layer`: registry storage, layer composition, and package commands;
- `vendoring`: page initialization, layer transitions, and atomic installation;
- `registry_contract`, `schema`, `structure`, `styles`, and `validation`: the
  merged vocabulary contract and authored-page gates;
- `passages`: the file-side text reading and anchor capture;
- `render_checks`, `render_gate`, and `exporting`: browser probes, validation,
  and standalone export;
- `data`, `media`, and `publishing`: page-bound inputs and deployment outputs.

Do not put domain logic back into `interact.py` or branch across these owners in
the CLI.

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
state folds, catalog output, package checks, and markup validation must consume
its declarations without a widget-name list.
