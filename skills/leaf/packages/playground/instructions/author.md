Give each design decision one place where the user selects. When the candidates are
fixed and visible, put them in `lf-options` inside an `lf-ask`, and draw each candidate
in its `lf-option`, so the user selects the example they want. When the decision changes
an existing interface, put a figure of today's interface between the question and the
options (`references/authoring-asks.md`). A page-local control that steps every
candidate through the same states or cases goes in that ask too.

Use `lf-playground` when the user needs to tune a configuration before choosing it. A
playground holds exactly one `lf-playground-preview` and one `lf-playground-output`.
Frame the question with `lf-ask` when its context lives outside the playground.
Interactive behavior alone is no reason to write a package: a page module can define
custom elements, add state to the playground and derive its output
(`references/packages.md`).

Place each control next to what it changes. A control that changes the whole preview, as
most do, is a direct child of `lf-playground` and appears in the rail beside the
preview, above the instruction. When the preview holds several items that each take
their own settings, such as alerts that each need a threshold, write each item's
controls inside `lf-playground-preview` beside that item, and leave only the settings
every item shares in the rail. A control in the preview still belongs to the playground:
its value is submitted, and presets and Reset set it.

When the preview needs width, such as for two candidates side by side, give the
`lf-playground` `data-width="available"`. The playground then widens past the column
while the question and premise in its `lf-ask` keep the prose width. On a workspace page
(`<main class="layout-workspace density-working">`) whose body is that `lf-ask`, the
playground fills the window. Draw the candidates directly in the preview, without a card
around each.

An A/B comparison mounts both candidates in the preview with the same configuration and
starting content. Candidates side by side start their names, notes and drawings on
shared lines across the row, however each wraps, so the user compares them straight
across; each drawing keeps its own height.

## Decision fidelity

Start from the real artifact. Wrap the existing component, document or generated output
rather than redrawing it in page markup. A companion package can carry browser-ready
code and fixtures under `vendor/`, and page images go through `leaf page media`
(`references/authoring-evidence.md`). Load these assets from the page's own origin, and
import from Leaf's runtime only `/runtime/widget-api.js`.

Show each candidate as the interface being decided, so the user can judge it as they
would use it: its content, its controls where they are proposed to go, the context
around it, and the states that tell the candidates apart. A sketch, wireframe or diagram
can be rough and unwired if it shows those things; naming a control in prose does not
show it. Make an interaction work inside a candidate only when the user needs to try it
to decide. Before asking which candidate the user prefers, check that the views support
the choice, and add what is missing. Use product copy for visible and accessible text,
and put commentary about the prototype in the surrounding playground only where needed.

When the decision changes an existing interface, include its current state as a labeled
baseline. Derive each candidate from the baseline and change only what is under review,
keeping its controls, words, tokens and interaction state unless the candidate proposes
changing them.

A copy of a component's DOM has its appearance but none of its listeners, state or
lifecycle. When behavior is part of the comparison, mount the component through its
production entry point, or serve both builds, rather than wiring substitute handlers
onto copied DOM.

## Controls, samples, and output

A control's `kind` is `range`, `toggle`, `choice`, `color` or `text`, and its `name` is
its key in the map of typed values the final `choose` action sends. A range needs `max`;
`min` defaults to 0 and `step` to 1. A range's `unit` is appended to its value in its
CSS custom property and in `lf-playground-value`, while its data attribute and its entry
in `values` stay plain numbers.

Keep the configuration the user is choosing apart from the cases used to inspect it.
Controls and presets describe what to build. Give preview cases and inspection settings
their own labeled controls, with page-local state outside the playground's submitted
values, and style them with Leaf's control classes (`references/page-layout.md`, "Page
CSS and Leaf's controls"). Changing the case keeps the configuration, applying a preset
keeps the case, and every candidate shows the same case. When editing the data is itself
the task, the data belongs in the configuration.

Offer presets when combinations of several parameters make useful starting points for
further tuning. Make the presets differ in several parameters, and design each as one
look whose parts read together on every surface they change, rather than taking each
control's best value separately. A preset sets every control its look depends on, since
a control it leaves out keeps the user's last value. Before handoff, look at each preset
in both themes on every surface it changes, and rework or drop any you would not ship.
Name a preset for its outcome: `Status strip`, not `Preset 2`.

In this comparison, `format` names which of the two candidates to build:

```html
<lf-ask id="notification-ask">
  <h2>Which deployment notification should we build?</h2>
  <lf-playground id="notification-playground" submit-label="Create notification"
    data-width="available">
    <lf-playground-control name="format" label="Format" kind="choice" value="banner">
      <lf-playground-choice value="banner" label="Banner"></lf-playground-choice>
      <lf-playground-choice
        value="status strip" label="Status strip"
      ></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-control
      name="radius" label="Corner radius" kind="range"
      value="10" min="0" max="24" step="1" unit="px"
    ></lf-playground-control>
    <lf-playground-control
      name="compact" label="Compact spacing" kind="toggle" value="false"
    ></lf-playground-control>

    <lf-playground-preset label="Status strip">
      <lf-playground-setting for="format" value="status strip"></lf-playground-setting>
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
    </lf-playground-preset>

    <lf-playground-preview>
      <section class="notification-candidates" aria-label="Notification candidates">
        <article data-candidate="banner">
          <h3>Banner</h3><p>Checkout deployed. Review the deployment run.</p>
        </article>
        <article data-candidate="status strip">
          <h3>Status strip</h3><p>Checkout · deployed · 18 checks passed</p>
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
`data-playground-NAME`. A text control's custom property is a quoted CSS string, and its
attribute holds the unquoted text:

```css
.notification-candidates > article { border-radius: var(--playground-radius); }
#notification-playground[data-playground-compact="true"]
  .notification-candidates > article { padding: var(--sp-2); }
#notification-playground[data-playground-format="status strip"]
  [data-candidate="status strip"] { outline: 2px solid var(--accent); }
```

To study Leaf's own live interface, embed each candidate in an `lf-sample window` inside
the preview, and keep comparison labels and design controls outside the samples.
Comments on which design to build go on the outer page and reach you. Comments and
decisions the user tries inside a candidate stay in that sample's own log, and Reset
returns it to its starting history.

Start fictional threads or decisions with `data-sample-events`, which names one inert
JSON history in the parent page; several samples can share it without sharing later
gestures (`references/live-samples.md`). Keep fixture anchors in the child's template.
Don't copy fictional history into the outer page's log or post it with a setup script.

A candidate that restyles a whole page or uses a global stylesheet also needs a live
sample; a static sketch or snippet can go directly in the preview. Put each candidate's
CSS in a `<style>` inside its template, keyed on the child's root, such as
`:root[data-playground-format="status strip"]`: each sample's root carries the
playground's properties and attributes from its first paint, including after Reset.

The output is the instruction the agent receives. Write a complete task that names the
object, where the change goes, and the evidence you want back. Use `lf-playground-value`
only where a selected value makes the task more precise; the action sends every control
in `detail.values` anyway, including those the prose leaves out.

## Stateful previews

Write a preview's script as an inline `<script type="module">`, and put the candidates
in ordinary or custom elements (`references/module-authoring.md`, "What a behavior
module owes").

Wait for `customElements.whenDefined("lf-playground")` before reading
`closest("lf-playground").values`. After each change, the playground dispatches a
bubbling `lf-playground-change` event carrying the values in `detail.values`.

To add state of your own to the configuration, call
`playground.registerContributor(name, defaultSnapshot, {read, apply})`, and call the
notifier it returns after each gesture that changes that state. The name must be stable,
unique, and different from every control's name. `read` returns a JSON-safe snapshot.
`apply` replaces the module's whole state with a snapshot the playground hands it on
restore, Reset, a preset or a recorded choice. The playground then stores, resets,
copies and submits that state along with the controls.

When structured state changes the instruction, register one
`playground.registerInstructionProvider(values => instruction)` to write the output. The
instruction it returns describes additions, removals, ordering and relations in readable
prose, and makes sense without the preview. To give `detail.values` an exact schema,
redeclare the complete `lf-playground` entry in the page's `page/registry.json`.

When both candidates draw from shared state, keep dynamic rows under stable keys, apply
each add, remove, reorder or edit once, and derive both candidates' rows and counts from
that state. A canvas or SVG explorer uses one Pointer Events controller with pointer
capture and a keyboard route; it converts the input to model coordinates once and draws
both candidates and their measurements from them. Call `layoutChanged` after a gesture
changes geometry.

Before handoff, operate every custom gesture, control and preset, then Reset, reload,
copy and submit. Check that both candidates reach the same state, the measurements
update, and the copied instruction can be acted on without the preview. Check wide,
narrow and short windows, and an exported file too unless the page has live samples,
which need a server.

## Task-shaped recipes

### Data and query explorer

Keep filter rows in one contributor, such as
`filters: {rows: [{id, field, operator, value}], order: [id]}`. Edit rows by stable id
through labeled native controls, and derive the result table from the snapshot. The
instruction turns the rows and their order into a query task. Check where keyboard focus
lands after adding or removing a row.

### Concept or code map

Store nodes and relations as ids and endpoints, never as positions or colors alone.
Dragging uses pointer capture and has a keyboard equivalent. Give elements stable ids so
the user can point at them in Leaf's Design mode. The instruction lists the changed
nodes and relations. To critique a document or source, use Leaf's comments, suggestions,
`lf-diff` or `lf-visual-review` rather than rebuilding that review in a map.

### Multi-change decision sweep

Keep proposed changes under stable ids, with one decision per id, each reachable by
keyboard. Filtering and ordering change what is shown, never which decisions exist, and
the output summarizes the accepted, rejected and undecided changes in an order that
doesn't depend on the display.

Capture any real fixture the playground needs when you build the page, so reopening and
exporting it need no network.
