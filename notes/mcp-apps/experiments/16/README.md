# Experiment 16: Hydrated reference-host full-page probe

## Purpose

Wait for the reference host's asynchronous tool controls to become stable,
then run the original complete-page frame and interaction measurement.

**Changes from experiment 15:**

- Wait for both visible tool options before selecting `leaf_open_page`.
- Assert the stable `{}` default before writing the page argument.
- Keep the app resource, frame CSP, Leaf server, fixture, and browser readings
  unchanged.

**Expected outcomes:**

- The rendered Tool Input panel preserves the exact page directory submitted by
  the harness.
- The nested loopback page either reaches Leaf's readiness stamps or leaves a
  concrete frame/CSP failure in the preserved diagnostics.
- On success, inline and fullscreen dimensions, accessibility, console output,
  and a keyboard-authored Leaf event establish the first full-interface result.

## Findings

The host shell appeared immediately, but the MCP tool options did not hydrate
within the 20-second barrier. The failure snapshot taken immediately afterward
showed both options rendered, so the selected tool was still never called and
the loopback frame remained untested. Experiment 17 raises only this discovery
barrier to 60 seconds.
