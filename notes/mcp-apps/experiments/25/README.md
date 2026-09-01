# Experiment 25: Completed full-page evidence

## Purpose

Finish the full-page measurement with a valid read of the host's post-fullscreen
return control.

**Changes from experiment 24:**

- Read `Return inline` visibility from a role locator instead of calling a
  locator method through the frame locator.
- Change no implementation, host, fixture, or other measurement.

**Expected outcomes:**

- Fullscreen dimensions and the hidden return-control quirk are both recorded.
- Axe and console output characterize the composed app.
- A nested keyboard choice appends and replays as an ordinary durable Leaf
  action.

## Findings

The page again reached fullscreen, then Axe rejected the Playwright
`FrameLocator`; the wrapper requires a concrete `Frame`. Earlier successful MCP
App experiments already use `page.frames[-1]` for this exact nested boundary.
Experiment 26 adopts that proven call and persists fullscreen readings before
running Axe.
