# MCP Apps research

## Research Questions

**Primary**: Can Leaf add MCP Apps as a delivery surface without adding a second interface or state authority?

**Secondary**:

- What is the smallest server-tool boundary that preserves the page directory and append-only log as Leaf's durable record?
- Can one current, option-shaped user ask degrade into a useful disposable inline surface?
- Which host capabilities are prerequisites, conveniences, or policy-dependent enhancements?

## Current Status

### Latest Results: experiment 56

The real Leaf design-decision page travels directly in a `ui://` resource in the
official MCP Apps reference host. Its canonical theme/runtime render; a keyboard
choice and anchored comment append through the existing event endpoint, and the
comment appears in Leaf's normal Threads panel. The resource has no nested Leaf
iframe, makes no external resource requests, and declares no connect, resource,
or frame domains. The reference host accepts ui/message. Its acceptance is not
evidence of an idle Codex turn.

The reviewed runner reproduced this result from a fresh pinned reference-host
checkout and passed 21 HTTP host/origin checks. It resolves temporary paths to
their physical location and keeps that host outside hidden parent directories,
as required by npm workspace resolution and the host's Express file policy.

The prototype bundles the existing vendored runtime and widgets, substituting
MCP tools only for state reads and event writes. It owns no parallel projection
or durable log. The experiment demonstrates this fixture, not every widget or
version/data/package operation. A narrow inline comment card and the tall-frame
probe control expose remaining layout questions.

This was also viewed in Codex's browser pane, but not in Codex's built-in inline
MCP renderer. The earlier blocked HTTP iframe was a limitation of our wrapper,
not evidence that direct Leaf resources cannot work. The separate browser-pane
route rendered the canonical page in Codex and returned a keyboard choice and
anchored comment through the detached adapter. Those deliveries reached later turns
of the originating task; a reply, revisions, reload, and version travel preserved
the standing state. Its actions began while the task was active, so the run did not
isolate idle wake-up.

### Latest experiment: 56

**Status**: Complete. Direct
rendering, durable gestures, visible comment UI, accepted ui/message, no-network,
and HTTP boundary checks pass. Source hashes identify the reviewed code.

## Next Steps

1. Register this direct-resource probe in Codex and inspect its actual inline
   renderer, not a reference host in a browser tab. A fresh probe connection/task
   is required; the installed production MCP route has not been replaced.
2. Test ui/message after that task is idle, with no detached watcher, active goal,
   or diagnostic tool calls before or after the message. Preserve exact event
   timing so acceptance and wake are separate observations.
3. If Codex accepts the direct resource, extend the transport to version/data and
   dynamic assets and test compact comment layout before choosing a production
   cutover. These are missing prototype coverage, not MCP protocol prohibitions.

## Reference

- Read the direct-resource result: `cat notes/mcp-apps/experiments/56/README.md`
- Read its machine result: `jq . notes/mcp-apps/experiments/56/results/reference-host.json`
- Run the current reference-host probe: `bash scripts/mcp-app/run-direct-probe.sh 57`
