# Experiment 32: Unified Codex App candidate

## Purpose

Submit the one-resource adaptive candidate to the real Codex host, verify that
tool annotations avoid read approvals, and test the complete-page frame only
after removing experiment 31's resource collision.

**Changes from experiment 31:**

- Every presentation and app-only tool binds one adaptive
  `ui://leaf/page/v1.html` resource.
- The app selects full-page or snapshot behavior from the result's explicit
  format and mode.
- Presentation and refresh tools are read-only; only snapshot event append is a
  write.

**Configuration:**

- Temporary MCP server name: `leaf_candidate` only; the installed `leaf` server
  was disabled for the probe.
- Codex `default_tools_approval_mode`: `writes`.
- A compatible freshly initialized `Codex MCP Apps probe` page.
- One task called both presentation tools; a separate task called only
  `leaf_present` to identify the full-mode card unambiguously.

**Expected outcomes:**

- No approval prompt means Codex honors the read-only tool annotations.
- Correct chrome on both cards means one adaptive resource removes the
  server-level cache collision.
- Authored content inside the primary frame means Codex permits the exact
  localhost frame domain; a frame error isolates the remaining host boundary.

## Findings

Both presentation calls completed with zero approval prompts under `writes`, so
Codex honored the read-only annotations. The snapshot selected the unified app's
snapshot mode and rendered the authored content and controls correctly.

The full-only task selected the right renderer too: its shell showed
`Complete page · Draft · event 0`, with no undefined fields or `replaceAll`
failure. The nested surface displayed Chromium's broken-frame document instead
of the Leaf page. Desktop log line 18919 identified the exact boundary:
`mcp_app_sandbox.guest_load_failed`, `errorCode=-30`,
`errorDescription=ERR_BLOCKED_BY_CSP`, `isMainFrame=false`, with a validated
`http://localhost:<port>/p/<capability>` URL. The browser error document was a
consequence of Codex's nested-frame CSP enforcement, not a connection refusal or
private-network-access failure.

The candidate shell also announced `Leaf page loaded.` because an iframe `load`
event fires for that error document. That is not a valid readiness signal. This
submission therefore proves snapshot success, permission success, and correct
adaptive dispatch, but not complete-page success. Codex blocks this localhost
nested frame despite the resource's exact `frameDomains` declaration. The
restriction is host-specific: experiment 30's official reference host accepted
the same exact-origin frame.

Review of Codex desktop 26.825.32147 made the policy mechanism decisive. Its
internal webview bundle normalizes `ui.csp.frameDomains` through a helper that
accepts only `https:` entries; `connectDomains` additionally permits `wss:`, and
`resourceDomains` does not authorize frames. The helper therefore removes Leaf's
exact `http://localhost:<port>` frame origin before the sandbox CSP is built,
which exactly predicts log line 18919's `ERR_BLOCKED_BY_CSP`. MCP Apps hosts may
apply stricter CSP policy than a resource requests, so this behavior is allowed
and does not contradict the official reference-host result.

The ext-apps host contract exposes that approved set as
`sandbox.csp.frameDomains`. A subsequent candidate can therefore skip the frame
without host-name sniffing when the exact Leaf origin is absent, while retaining
a readiness timeout for hosts that approve the origin or do not report the
field. That response belongs to the next submission, not this experiment.

Captured evidence was reviewed from `/tmp/leaf-unified-probe.IEKkq3/screen.png`
and `/tmp/leaf-unified-probe.IEKkq3/full-only.png`; it is not copied into the
repository.
