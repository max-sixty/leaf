## Research Questions

**Primary**: Can Leaf add MCP Apps as a delivery surface without adding a second interface or state authority?

**Secondary**:

- What is the smallest server-tool boundary that preserves the page directory and append-only log as Leaf's durable record?
- Can one current, option-shaped reader ask degrade into a useful disposable inline surface?
- Which host capabilities are prerequisites, conveniences, or policy-dependent enhancements?

## Current Status

### Latest Results: experiment 29

The complete page is green end to end in the official reference host. In
addition to the clean layout, accessibility, fullscreen, and options evidence,
an anchored comment appended through Leaf's ordinary event path and remained
resolved while the page traveled v2 → v1 → v2.

### Current Experiment: none

**Status**: Baseline complete
**Purpose**: The local reference-host primitive now covers the complete page,
durable actions, anchored comments, and immutable-version travel.

## Next Steps

1. Probe one shipped host and record whether HTTPS,
   private-network policy, or host CSP changes the result.
2. Probe `ui/message` turn behavior independently; neither page transport path
   should make a wake claim from an event append alone.

## Reference

- Reproduce experiment 29: `bash notes/mcp-apps/experiments/29/commands.sh`
- Read its result: `sed -n '1,380p' notes/mcp-apps/experiments/29/results/reference-host.json`
- Inspect the current project: `sed -n '1,240p' notes/mcp-apps/PROJECT.md`
