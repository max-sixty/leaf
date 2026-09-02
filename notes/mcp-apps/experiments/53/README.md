# Experiment 53: Inline browser-managed icon assets

## Purpose

Repeat experiment 52 after inlining the vendored icon in the banner's favicon
and injected CSS mask. Those loads bypass fetch, so they must be bundled too.
The network assertion allows embedded data resources and still rejects every
external resource request. No change to the host CSP or Leaf state authority.

Expected outcome: the complete fixture interaction and message tests pass with
zero external resource requests. Keep the successful host as a live preview.

## Findings

Passed. `results/reference-host.json` records the complete automated result:

- The shipped design-decision page and canonical runtime presented inside the
  MCP resource; 15 widget modules were bundled, not 15 widget families tested.
- No nested Leaf iframe, no external resource requests, and empty declared
  connect/resource/frame domain lists.
- A keyboard choice and uniquely marked anchored comment reached the existing
  PageStateService/EventEndpoint log; the comment appeared in the real Threads
  panel. The initial inline reply received focus before the panel was opened.
- The probe button's Enter route sent ui/message, accepted by the reference host.
- Browser error log was empty. Python Ruff and JavaScript syntax checks passed.

The MCP server and official reference host remain live at
http://localhost:8080/?tool=leaf_direct_present&server=leaf-direct-probe&call=true
for inspection. The original Leaf page and its detached adapter are separate.

## Limits

This is the official reference host, also opened inside Codex's browser pane;
it is not Codex's built-in inline MCP renderer. No idle Codex wake was tested.
The page directory is still the durable record, but version navigation, typed
data, all-pages navigation, new packages/layer refresh, and Mermaid's dynamic
script load are not implemented by this fixed-resource transport. The narrow
inline card captured in experiment 50 and tall-frame probe-button positioning
show that compact-layout parity remains unproven. No production route changed.
