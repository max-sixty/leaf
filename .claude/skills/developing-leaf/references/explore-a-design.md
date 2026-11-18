# Explore an open design

When the user is to choose among designs for a visual or interaction question, show
the candidates side by side in one decision, where the user can compare them, try the
interactions, comment, and pick the one to build. Their pick, or the configuration a
playground submits, is the one implementation the change keeps. First look in the
shipped examples and `notes/` for an exploration of the same surface, and extend it
when it covers the same decision.

The exploration is one HTML file under `.tmp/`, served with
`uv run leaf-dev preview --source <file> --user` (`previews.md`); its CSS reads the
live theme's tokens. Follow `<root>/packages/playground/instructions/author.md`
to choose the elements, present the candidates, and say what to build.

To change an existing interface, take this checkout's rendered interface as the
baseline, covering the controls and states the requested property affects. Build
runtime candidates in the runtime and theme that own the surface. A separate sketch
copies Leaf's mark from `browser/icon.svg` and each icon's path from
`browser/runtime/icon-paths.js`. Drive the baseline and every candidate through
the same journey before handoff.
