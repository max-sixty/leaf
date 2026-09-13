# Playgrounds

Use `lf-playground` when several values or behaviors need to be explored together before
the reader chooses one configuration. Put it inside `lf-ask`, declare controls and
optional presets, then include exactly one preview and one output.

Keep ownership at its natural boundary:

| Need | Owner |
| --- | --- |
| One page's behavior, artifact, schema, or state model | The page instance |
| Mechanics reused by several pages | An existing or new package |
| Revision, identity, event admission, or export guarantees | Leaf core |

Interactive page behavior does not by itself justify a package. A page module can define
custom elements, register structured state with its playground, and derive the output.

The preview is the surface the reader operates. An A/B comparison keeps both candidates
mounted in that preview and applies each control edit or custom gesture to both. The
reader should not have to reproduce a drag, scroll, reorder, or input sequence in two
separate previews. Put measurements that affect the decision beside their candidates and
update them from the same gesture snapshot.

Start from the real artifact. Wrap the existing component, document, or generated output
instead of rebuilding its appearance in page-local markup. A companion package may carry
browser-ready code and fixtures under `vendor/`; page images go through `leaf page media`.
Load those assets from the page's same origin, retain its CSP, and keep imports from
Leaf's runtime to `/runtime/widget-api.js`.

Controls support `range`, `toggle`, `choice`, `color`, and `text`. Their `name` becomes
the key in the complete typed value map sent by the final `choose` action. A range's
`unit` is appended in its CSS custom property and in `lf-playground-value`; its data
attribute and public `values` entry stay numeric. A range requires `max`; `min` defaults
to zero and `step` defaults to one.

When you have recommendations, offer two to four presets as coherent starting points.
Name the outcome—`Status strip`, not `Preset 2`—and let the reader tune it afterward.

This comparison keeps two operable candidates in one preview. One edit updates both,
while `format` identifies the candidate to build:

```html
<lf-ask id="notification-ask">
  <h2>Which deployment notification should we build?</h2>
  <lf-playground id="notification-playground" submit-label="Create notification">
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

Bind shared parameter changes with page CSS. For every control value the preview reads
through `--playground-NAME`, author that property on the playground with the control's
initial value. Base rules carry the initial attribute-selected state. This gives the
preview the same first paint before Leaf upgrades it. Each value is then reflected on
the playground as both `--playground-NAME` and `data-playground-NAME`. A text control's
custom property is a quoted CSS string; its data attribute contains the unquoted text:

```css
#notification-playground { --playground-radius: 10px; }
.notification-candidates > article { border-radius: var(--playground-radius); }
#notification-playground[data-playground-compact="true"]
  .notification-candidates > article { padding: var(--sp-2); }
[data-candidate="banner"] { outline: 2px solid var(--accent); }
#notification-playground[data-playground-format="status strip"]
  [data-candidate="banner"] { outline: 0; }
#notification-playground[data-playground-format="status strip"]
  [data-candidate="status strip"] { outline: 2px solid var(--accent); }
```

The output is the instruction the reader copies and the host receives. Write a complete
task with an object, destination, and requested evidence. Use `lf-playground-value` only
where a selected value makes that task more precise. The action still includes every
control in `detail.values`, including controls the prose does not repeat.

## Stateful previews

A preview that needs JavaScript keeps its page-specific behavior in an inline
`<script type="module">` block. Put the real candidates in an ordinary element or a
page-specific custom element. Use a package widget only when that behavior or
vocabulary is reused across pages. Follow `references/packages.md`'s behavior-module
contract in either case.

Wait for `customElements.whenDefined("lf-playground")` before reading
`closest("lf-playground").values`. Later snapshots arrive in the bubbling
`lf-playground-change` event's `detail.values`.

A custom state model joins the same configuration with
`playground.registerContributor(name, defaultSnapshot, {read, apply})`. The returned
notifier is called after a direct gesture changes that source. Names are stable, unique,
and distinct from control names. `read` returns a JSON-safe snapshot; `apply` replaces
the page module's complete state from a restored, reset, preset, or projected snapshot.
The playground then owns the aggregate persistence, reset, copy, and submit path.

When structured state changes the instruction, one
`playground.registerInstructionProvider(values => instruction)` provider derives the
displayed output. The instruction names the object, destination, and requested evidence;
it includes additions, removals, ordering, and relations in readable prose and stands
alone without the preview. Default settings may be omitted unless they affect the task.
The page's `page/registry.json` replaces the complete `lf-playground` declaration with an
exact schema for its aggregate `detail.values`.

Keep one interaction state and render both candidates from it. Dynamic-row explorers
keep stable row keys, apply add, remove, reorder, and edit operations once, then derive
both row renderings and their counts from that state. Canvas and SVG explorers use one
Pointer Events controller with pointer capture and a keyboard route; translate the input
to model coordinates once, then render both candidates and their measurements from the
same coordinates. Call `layoutChanged` after a gesture changes geometry.

Before handoff, manually operate every custom gesture the page claims. Check that both
candidates reach the same input state, the measurements update, the complete typed value
map is still present, and the copied instruction can be acted on without the preview.
Operate every control and preset, then reset, restore, copy, and submit. Check wide,
narrow, and short viewports plus both the static and offline-interactive exports.

## Task-shaped recipes

### Data and query explorer

Keep dynamic filter rows under one contributor such as
`filters: {rows: [{id, field, operator, value}], order: [id]}`. Add, remove, edit, and
reorder stable row ids through labeled native controls and buttons, call the notifier
once per gesture, and derive the result table from that snapshot. The instruction
translates the rows and their order into a query task. Verify each row operation,
keyboard focus after addition or removal, reset, restore, copy, and submission.

### Concept or code map

Keep semantic nodes and relations as ids and endpoints, never positions or colors alone.
Pointer manipulation uses capture and has an equivalent keyboard route. The page may
compose Targeting for stable element references and comments while it owns which node
types, relation grammar, and edits make sense. The instruction lists changed nodes and
relations. For document critique or source review, use Leaf comments, suggestions,
Diff, or Visual Review instead of rebuilding those review loops in a map.

### Real-artifact A/B comparison

Mount the built variants or captured runtime DOM together, preserve their tokens,
typography, states, and viewport assumptions, and drive both from one gesture snapshot.
Candidate-specific values live under explicit keys; a copy-to-other action changes only
the intended candidate. Measurements are derived from the same snapshot and appear
beside each variant. When variants differ by compilation, build both source revisions
and serve both from the captured page graph rather than drawing a visual replica.

### Multi-change decision sweep

Keep proposed changes under stable ids and retain one decision value per id. Filtering or
ordering changes what is shown, not which decisions exist. Each offered decision remains
keyboard reachable and the output summarizes accepted, rejected, and undecided changes
without depending on display order. Verify a decision survives filter, reorder, restore,
and reset before the final submission.

Any real fixture the playground needs is captured at build time so reopening and export
do not depend on a network fetch. Static export is the readable script-free record;
interactive export retains local controls, gestures, derived output, reset, and copy but
honestly disables submission because no agent or server is present.
