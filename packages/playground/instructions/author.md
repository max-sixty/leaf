Give each design decision one place where the user selects. When the candidates are
fixed and visible, put them in `lf-options` inside an `lf-ask`, and draw each candidate
in its `lf-option`, so the user selects the example they want. When the decision changes
an existing interface, put a figure of today's interface between the question and the
options (`references/authoring-decisions.md`). A page-local control that steps every
candidate through the same states or cases goes in that `lf-ask` too.

Use `lf-playground` when the user needs to tune a configuration before choosing it, and
frame it with an `lf-ask` when the question's context lives outside the playground.
Behavior one page uses goes in that page's module, which can define custom elements, add
state to the playground and derive its output. Behavior several pages reuse belongs in a
package (`references/packages.md`, "Package reach").

Place each control next to the part of the preview it changes. A control that changes
the whole preview, as most do, is a direct child of `lf-playground` and stands in the
rail beside the preview. When the preview holds several items that each take their own
settings, such as alerts that each need a threshold, write each item's controls inside
`lf-playground-preview` beside that item, and leave only the settings every item shares
in the rail. A control in the preview is still submitted, and presets and Reset set it.

Give the `lf-playground` `data-width="available"` wherever it stands. Where the
playground is the page's subject, make the page a workspace (`<main
class="layout-workspace density-working">`) whose body is its `lf-ask`. When the page
also carries reading that supports the playground, make it a page of parts: the first
part is that workspace, `<div class="layout-workspace density-working">` holding the
`lf-ask`, and the reading goes in later parts, each a column
(`references/page-layout.md`, "A page of parts"). Where the playground is one exhibit in
a document, it breaks out of the document's column. Draw the candidates directly in the
preview, without a card around each.

An A/B comparison mounts both candidates in the preview with the same configuration and
starting content, applies each drag, scroll or edit once to the shared state, and draws
both candidates from it. When candidates stand side by side, align their names, notes
and drawings in rows, so each candidate's drawing starts level with the others' however
many lines its name or note wraps to. Each drawing keeps its own height.

## Decision fidelity

Start from the real artifact. Wrap the existing component, document or generated output
rather than redrawing it in page markup. A companion package can carry browser-ready
code and fixtures under `vendor/`, and page images go through `leaf page media`
(`references/authoring-evidence.md`), so the page loads them from its own origin.

Show each candidate as the interface being decided: its content, its controls where they
are proposed to go, the context around it, and the states that tell the candidates
apart. A sketch can be rough and unwired if it shows those things, but naming a control
in prose doesn't show it. Make an interaction work only when the user needs to try it to
decide. Use product copy for visible and accessible text, and keep commentary about the
prototype outside the candidates. Before asking which candidate the user prefers, check
that the views support the choice.

When the decision changes an existing interface, include its current state as a labeled
baseline, derive each candidate from it, and change only what is under review. Copy
everything else from the files that define the product: its controls and words, icons
and logos, theme tokens and interaction state. The user reads any difference from the
product as part of the proposal, so an emoji, Unicode symbol or plain dot standing in for
an icon or logo shows a change nobody proposed. Where a part can't be copied, leave a
plain blank of its size.

A copy of a component's DOM has none of its listeners, state or lifecycle. When behavior
is part of the comparison, mount the component through its production entry point, or
build and serve each candidate's source revision.

## Configuration, presets and output

Controls and presets describe what to build. Keep the cases used to inspect it apart:
give preview cases and inspection settings their own labeled controls, with page-local
state outside the playground's submitted values, and style them with Leaf's control
classes (`references/page-layout.md`, "Page CSS and Leaf's controls"). Changing the case
keeps the configuration, applying a preset keeps the case, and every candidate shows the
same case. When editing the data is itself the task, the data belongs in the
configuration.

Offer presets when combinations of several parameters make useful starting points. Design
each preset as one look whose parts read together on every surface it changes, rather
than each control's best value, and make the presets differ in several parameters. A
preset sets every control its look depends on, since a control it leaves out keeps the
user's last value. Before handoff, look at each preset in both themes and rework or drop
any you would not ship. Name a preset for its outcome: `Status strip`, not `Preset 2`.

In this comparison, `format` names which of the two candidates to build:

```html
<lf-ask id="notification-ask">
  <h2>Which deployment notification should we build?</h2>
  <lf-playground
    id="notification-playground"
    submit-label="Create notification"
    data-width="available"
  >
    <lf-playground-control name="format" label="Format" kind="choice" value="banner">
      <lf-playground-choice value="banner" label="Banner"></lf-playground-choice>
      <lf-playground-choice
        value="status strip"
        label="Status strip"
      ></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control
      name="radius"
      label="Corner radius"
      kind="range"
      value="10"
      min="0"
      max="24"
      step="1"
      unit="px"
    ></lf-playground-control>
    <lf-playground-control
      name="compact"
      label="Compact spacing"
      kind="toggle"
      value="false"
    ></lf-playground-control>

    <lf-playground-preset label="Status strip">
      <lf-playground-setting for="format" value="status strip"></lf-playground-setting>
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
    </lf-playground-preset>

    <lf-playground-preview>
      <section class="notification-candidates" aria-label="Notification candidates">
        <article data-candidate="banner">
          <h3>Banner</h3>
          <p>Checkout deployed. Review the deployment run.</p>
        </article>
        <article data-candidate="status strip">
          <h3>Status strip</h3>
          <p>Checkout · deployed · 18 checks passed</p>
        </article>
      </section>
    </lf-playground-preview>
    <lf-playground-output>
      Build the <lf-playground-value for="format"></lf-playground-value> notification
      with <lf-playground-value for="radius"></lf-playground-value> corners and compact
      spacing set to <lf-playground-value for="compact"></lf-playground-value>. Replace
      the notification component and show me its browser test.
    </lf-playground-output>
  </lf-playground>
</lf-ask>
```

Apply shared parameters with page CSS. From first paint, Leaf sets each control's value
on the `lf-playground` as a custom property, `--playground-NAME`, and an attribute,
`data-playground-NAME`:

```css
.notification-candidates > article {
  border-radius: var(--playground-radius);
}
#notification-playground[data-playground-compact="true"]
  .notification-candidates
  > article {
  padding: var(--sp-2);
}
#notification-playground[data-playground-format="status strip"]
  [data-candidate="status strip"] {
  outline: 2px solid var(--accent);
}
```

The output is the instruction the agent receives. Write a complete task that names the
object, where the change goes, and the evidence you want back. Use `lf-playground-value`
only where a selected value makes the task more precise; the action sends every control
in `detail.values` anyway.

To study Leaf's own live interface, embed each candidate in an `lf-sample window` inside
the preview (`references/live-samples.md`), and keep comparison labels and design
controls outside the samples. Comments on which design to build go on the outer page;
what the user tries inside a candidate stays in that sample. A candidate that restyles a
whole page or uses a global stylesheet needs a live sample too, while a static sketch
goes directly in the preview. Put each candidate's CSS in a `<style>` inside its
template, keyed on the child's root, such as `:root[data-playground-format="status
strip"]`: each sample's root carries the playground's properties and attributes from its
first paint, including after Reset.

## Stateful previews

Write a preview's script as an inline `<script type="module">`
(`references/module-authoring.md`, "What a behavior module owes"). The playground owns
working values, tab persistence, presets, Reset, instruction copying and submission;
views draw the values they receive, and a script reads them all from the immutable
`playground.values`.

During `PAGE_INTERFACE` (`references/module-authoring.md`, "Startup and presentation"),
register once per playground lifetime, joining the whole initialization with
`event.detail.present(Promise.resolve().then(initialize))`:

- Structured state, with `playground.registerContributor(name, defaults)`, whose name is
  unique and distinct from control names. Keep the returned handle rather than a second
  configuration object: `get()` reads its immutable current value, and `set(next)`
  replaces it. Set it on input, so a later control change or submission sees the edit;
  Reset and Undo replace the value it reads. Then redeclare the complete `lf-playground`
  entry in `page/registry.json` with an exact schema for `detail.values`.
- Optionally one `registerInstructionProvider(values => instruction)`, which describes
  the configuration as a task that makes sense without the preview.
- Each view, with `playground.subscribe(values => draw(values))`. Its callback paints
  synchronously and its return value isn't awaited. Hold the returned cleanup through
  `whileConnected`, so reconnection restores the view without declaring its data again.

Keep native editors mounted, and don't write their value when it already matches. Keep
dynamic rows, such as a query's filters, under stable ids; apply each add, remove,
reorder or edit once, and derive every candidate's rows and counts from that state.
Filtering and ordering change what is shown, never which items exist, and the
instruction lists items in an order that doesn't depend on the display. Store a map's
nodes and relations as ids and endpoints, never as positions or colors alone. A canvas
or SVG explorer uses one Pointer Events controller with pointer capture and a keyboard
route, converts input to model coordinates once, and calls `layoutChanged` after a
gesture changes geometry. To critique a document or source, use Leaf's comments,
suggestions, `lf-diff` or `lf-visual-review` rather than a playground.

Before handoff, operate every custom gesture, control and preset, then Reset, reload,
copy and submit. Check that the candidates reach the same state, measurements update,
focus lands where the user expects after adding or removing a row, and the copied
instruction can be acted on without the preview. Check wide, narrow and short windows,
and an exported file unless the page has live samples, which need a server. Capture any
real fixture when you build the page, so reopening and exporting it need no network.
