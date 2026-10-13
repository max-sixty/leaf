# Workspace scrolling and chrome

The sticky-header foundation landed in [PR #1472](https://github.com/max-sixty/leaf/pull/1472).
The banner has a stated height, sticky headers stack through `--lf-top`, and the
workspace row rule applies to pane grids without squeezing a widget's own rows.
These contracts live in [layouts.css](../skills/leaf/assets/layouts.css),
[theme.css](../skills/leaf/assets/theme.css), and the
[module reading-region contract](../skills/leaf/references/module-authoring.md#reading-regions).

## Decided: a workspace is a screen

A full-height workspace stays a screen whose regions hold their own overflow. Some
pages behave like a TUI or a dashboard rather than a document, and the workspace
Layout exists for them; a long read beside a panel kept in view is a `layout-sidebar`
document whose aside sticks (`page-authoring.md`, A workspace).

Option E, a workspace whose main region flows with the root while its other regions
stick, is rejected. It kept native page scrolling at the cost of reworking the
full-height widgets, footers, margin lanes and phone stacking, all to make workspaces
scroll better, which is not what they are for.

The aim is pages that need little scrolling, composed simply, rather than better
scrolling inside regions. page-authoring.md asks an author to trim or split a pane
whose body runs past its region, and no check enforces it.

A branch that made a side list (`lf-tabs list="side"`) a screen was built and
abandoned (`screen-workspace-review`, October 2026): it gave the list and the open
item separate scrollers, routed the reading keys to the item, and stacked queue and
item on a phone. It bound the workspace's behavior to one widget and spent its
weight on scrolling, so none of it shipped except the instructions above.

## Still open

- **The desktop bottom bar** leaves with the classic chrome (TODO #28): the floating
  panel, the default, hides it. Its status already stands elsewhere (notices in the
  panel's field, the walk position at the window's head), but its key hints for the
  current context have no home in the panel; a desktop user meets keys only on the
  leaf's menu rows and in `?`. Decide whether the panel shows them.

## Evidence

The original review ran on 29 September 2026 at `5ed41df4b`. On a plain Chrome page
it found:

| Gesture | Root scroller | Inner page box |
|---|---|---|
| PageDown or Space before a click | Scrolled | Stayed still |
| PageDown after clicking body text | Scrolled | Scrolled |
| PageDown after clicking the header | Scrolled | Stayed still |
| Back after `pushState` | Restored position | Kept the later position |
| Back from another document, or reload | Restored position | Returned to top |

Use `leaf-dev stills` against the merge base for changed first viewports and banner
states, on a phone too.
