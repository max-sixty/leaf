# MCP Apps research

## Research Questions

**Primary**: Can Leaf add MCP Apps as a delivery surface without adding a second interface or state authority?

**Secondary**:

- What is the smallest server-tool boundary that preserves the page directory and append-only log as Leaf's durable record?
- Can one current, option-shaped reader ask degrade into a useful disposable inline surface?
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
not evidence that direct Leaf resources cannot work. Experiment 35 remains the
separate browser-pane/detached-adapter route; its automated actions happened while
the task was active, so its later delivered turns did not isolate idle wake-up.

### Current Experiment: 56

**Status**: Complete; the passing reference-host preview remains running. Direct
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
- Live reference host: http://localhost:8080/?tool=leaf_direct_present&server=leaf-direct-probe&call=true
- Read the full Codex browser-pane result: `cat notes/mcp-apps/experiments/35/README.md`
- Read the fresh-process Codex result: `cat notes/mcp-apps/experiments/34/README.md`
- Read the invalid reused-process attempt: `cat notes/mcp-apps/experiments/33/README.md`
- Read the unified candidate result: `cat notes/mcp-apps/experiments/32/README.md`
- Read the installed-main baseline: `cat notes/mcp-apps/experiments/31/README.md`
- Reproduce the last reference-host run: `bash notes/mcp-apps/experiments/30/commands.sh`
- Inspect the current project: `sed -n '1,240p' notes/mcp-apps/PROJECT.md`
