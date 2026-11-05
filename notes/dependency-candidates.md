# Dependencies to consider

Maintained libraries that could replace or extend something in Leaf, recorded when a
prototype or close reading has shown what adopting each would cost. An entry is a lead
with its evidence, not a decision; adopting one is a change of its own, under root
`AGENTS.md`, "Use dependencies". Remove an entry once Leaf adopts the library or the
lead goes stale.

## DialKit

[DialKit](https://github.com/joshpuckett/dialkit) (MIT) generates a control panel from
a config, as `lf-playground` does. Its controls include spring, easing and XY-pad
editors Leaf can't draw with native inputs. Its `dialkit/vanilla` build has no runtime
dependencies.

A 2026-10-27 prototype (branch `agent-ab749e1dc55a3fa1a`) drew playground controls
with v2.1.0 and added a `kind="easing"` control. The playground kept owning the
values, and presets, Reset, Undo choice and submission all worked. Leaf's content
security policy didn't block it. What it cost:

- 26 KB gzipped (110 KB raw, about 65 KB of it its stylesheet), or 20 KB for the easing
  editor alone. It loads only on a playground that holds a DialKit control.
- 15–23 redundant DOM writes per page, which Leaf's write watch rejects. A fix that
  writes only changed values is ready on the fork
  [max-sixty/dialkit](https://github.com/max-sixty/dialkit/tree/skip-unchanged-dom-writes),
  not yet proposed upstream; with it, the watch reports 0.
- Drawing Leaf's existing range, toggle and choice kinds with it regressed: segments
  don't wrap, a range's unit disappears, vertical swipes over a slider don't scroll on
  phones, and its inline transitions ignore reduced motion.

For the existing kinds it is mostly a different way of drawing the same values, and
CSS on the native inputs can reach the same density. The case for adopting it is the
editors, once a page needs to decide motion. Firefox and WebKit were not probed.
