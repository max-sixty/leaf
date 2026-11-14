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

## UI SDK

[UI SDK](https://github.com/vercel-labs/ui) (Apache-2.0, `@ui-sdk/*` 0.1.0-beta.1,
first published 2026-11-12) is a library of interaction behaviors with no runtime
dependencies: roving focus, popups with layered dismissal, typeahead, drag and drop
and keyboard shortcuts, with adapters for React, Vue, Svelte, Solid and web
components. It also ships an agent bridge that reads and operates its components, and
`checkPattern`, which checks a rendered widget against its WAI-ARIA Authoring
Practices pattern. Read, and probed in Chromium, on 2026-11-12.

- **Leaf's runtime.** Leaf's popups use the platform (popover, `<dialog>`, CSS anchor
  positioning), and one keyboard register drives dispatch, menus, the command
  reference and `aria-keyshortcuts`. Adopting UI SDK there would add a second owner
  for keys, Escape, positioning and component state.
- **Page code.** A page can load its web components today with
  `<script type="module" src="https://ui-sdk.dev/web@0.1.0-beta.1.js">`, online only.
  Its select, tabs, menu and dialog worked inside Leaf, typeahead included, once
  Leaf's keyboard stopped acting on keys a page had already handled
  (`browser/runtime/keyboard/controller.js`). Escape on a tooltip's focused trigger
  still drops focus to the body, because UI SDK hears that Escape on `document`, after
  Leaf's listener there. Their values reach the event log only
  where page code passes them to a playground contributor or a widget controller.
  Each component's entry measures 13–53 KB gzipped on its own, by the repository's
  `size-budget.json`.
- **`checkPattern`** (`@ui-sdk/core/testing`, marked experimental). Run on eight
  examples through `leaf-dev probe --journey` (`/developing-leaf`'s
  `references/external-ui-skills.md` has the command), it found four defects in controls Leaf draws: `lf-tabs` gives its tablist no
  accessible name; the margin's `role="toolbar"` holds up to 15 tab stops, and
  ArrowRight, ArrowDown, Home and End from its first entry moved nothing; the
  playground's choice cards put Enlarge buttons inside a `radiogroup`; and Pierre's
  file tree puts its search field inside `role="tree"`. It also reported problems
  that weren't there. It presses keys with synthetic events, which don't move focus
  between native radios; it reads `aria-controls` as an attribute and misses a
  reference set through `ariaControlsElements`; and it reads focus from
  `document.activeElement`, which stops at a shadow host. Those false reports keep it
  out of `page check`.
