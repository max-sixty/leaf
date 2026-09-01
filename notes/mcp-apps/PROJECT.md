# MCP Apps research

## Research Questions

**Primary**: Can Leaf add MCP Apps as a delivery surface without adding a second interface or state authority?

**Secondary**:

- What is the smallest server-tool boundary that preserves the page directory and append-only log as Leaf's durable record?
- Can one current, option-shaped reader ask degrade into a useful disposable inline surface?
- Which host capabilities are prerequisites, conveniences, or policy-dependent enhancements?

## Current Status

### Latest Results: experiment 32

The one-resource candidate removed experiment 31's Codex cache collision: both
cards selected the correct adaptive mode, the snapshot rendered, and four
read-only presentation/refresh calls needed no approval under `writes`. The
full-mode shell was correct, but Codex blocked its nested localhost page with
`ERR_BLOCKED_BY_CSP` despite the exact declared frame domain. The shell's iframe
`load` event then falsely announced success for Chromium's error document. Codex
desktop 26.825.32147 removes every `http:` frame domain while constructing the
sandbox CSP; the official reference host accepts this exact origin.

### Current Experiment: none

**Status**: Capability- and readiness-gated snapshot fallback complete locally
**Purpose**: Submit it as experiment 33 without rewriting experiment 32's failed
candidate result.

## Next Steps

1. Submit the readiness-gated candidate as experiment 33. The official host
   should reveal the full page only after its presentation marker; Codex should
   replace its hidden blocked frame with the read-only authored snapshot.
2. Keep the detached Codex adapter as the sole durable wake and acknowledgement
   carrier; no remaining implementation decision depends on `ui/message` policy.
3. If accessibility parity becomes the next question, compare Axe before and
   after the option action to isolate experiment 30's moderate `region` result.

## Reference

- Read the unified candidate result: `cat notes/mcp-apps/experiments/32/README.md`
- Read the installed-main baseline: `cat notes/mcp-apps/experiments/31/README.md`
- Reproduce the last reference-host run: `bash notes/mcp-apps/experiments/30/commands.sh`
- Inspect the current project: `sed -n '1,240p' notes/mcp-apps/PROJECT.md`
