Use `lf-playground` when several values or behaviors need to be explored together before
the user chooses one configuration. Declare controls and optional presets, then include
exactly one preview and one output. Use `lf-ask` to frame the question and context
when they live outside the playground.

Interactive behavior does not by itself justify a package; `references/packages.md`
says where page-only and reused behavior belong. A page module can define custom
elements, register structured state with its playground, and derive the output.

The playground draws its own regions: the preview is a stage, and the controls and the
instruction to the agent stand in a rail beside it, on the same `2fr 1fr` tracks as a
wide page's body and rail, wherever it has 43.5rem; narrower, they stack. A preview that needs
width, such as two candidates side by side, belongs on a wide page (`<main
class="layout-wide">`), or on a workspace page (`<main class="layout-workspace">`) whose
body is the playground's Ask, where the stage grows to the window's height. Draw
candidates on the stage without a card of their own; the stage is their surface.

The preview is the surface the user operates. An A/B comparison keeps both candidates
mounted there with the same configuration and starting content. When the candidates
render one custom input model, apply each drag, scroll, reorder, or edit once and draw
both from that state; derive their measurements beside them. Live Leaf samples share
the configuration and authored starting history, while practice gestures belong to
each child's independent log. Reset brings a sample back to that starting history.

Start from the real artifact. Wrap the existing component, document, or generated output
instead of rebuilding its appearance in page-local markup. A companion package may carry
browser-ready code and fixtures under `vendor/`; page images go through `leaf page media`
(`references/authoring-evidence.md`). Load those assets from the page's same origin,
and keep imports from Leaf's runtime to `/runtime/widget-api.js`.

Keep candidates realistic so the user can judge the interface as they would use it.
Use product copy for their visible and accessible text. Describe them as prototypes
only in the surrounding playground, and only if necessary.

When exploring changes to an existing interface, include its current state as a labeled
baseline. Derive each candidate from that baseline and change only the behavior or
presentation under review; preserve its controls, words, tokens, and interaction state
unless the candidate explicitly proposes changing them.

Controls support `range`, `toggle`, `choice`, `color`, and `text`. Their `name` becomes
the key in the complete typed value map sent by the final `choose` action. A range's
`unit` is appended in its CSS custom property and in `lf-playground-value`; its data
attribute and public `values` entry stay numeric. A range requires `max`; `min` defaults
to zero and `step` defaults to one.

Separate the configuration the user is choosing from the cases used to inspect it.
Configuration controls and presets describe what to build. Give preview cases and
inspection settings their own labeled controls and page-local state, outside the
playground's submitted values. Changing a case preserves the configuration; applying
a preset preserves the case; all compared candidates use the same case. When editing
the data is itself the task, that data belongs in the configuration.

Controls and presets do different jobs. Controls span the configuration space: give
each part or parameter they might want to vary a control of its own, even when that
makes many, and put candidates that differ only as wholes in one `choice`. Presets are
the candidates you put forward: one for each proposal you would build, commonly three to
six, none a variant of another. Design each preset as one look, composing its parts so
they read together on every surface they change, rather than taking each control's best
value on its own. Free combinations of controls may clash; a preset may not, because the
user judges its idea by how it looks. Before handoff, look at each preset where the user
will see it, on every surface it changes and in both themes, and rework or drop any you
would not ship. A preset sets every control its look depends on, since a control it
leaves out keeps the user's last value. Name the outcome—`Status strip`, not `Preset 2`.

In this comparison, `format` identifies which of the two candidates to build:

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

When a playground studies Leaf's live interface, embed each candidate in an
`lf-sample window` inside the preview. The surrounding page owns the design controls,
the implementation request, and feedback to the author; each child owns its product
content and practice interactions. Comments and decisions inside a candidate stay
there, and Reset returns it to the same starting state. Keep comparison labels and
host controls outside the samples.

Start fictional threads or decisions with `data-sample-events`, naming one inert JSON
history in the parent; samples can share it without sharing subsequent gestures.
`references/page-authoring.md`, "Live samples", owns this declaration and its event
commands. Keep fixture anchors in the child template. Do not copy fictional history
into the outer page's log or post it with a setup script.

A candidate that restyles a whole page or uses a global stylesheet also needs a
live sample; `window` includes Leaf's chrome, while an ordinary live sample grows
with its content. Put each candidate's CSS in a `<style>` inside its template, keyed
on the child's root (`:root[data-playground-format="status strip"]`). Every child,
including after Reset, wears the playground's properties and attributes from its
first paint. The outer root and stylesheet belong to the review page. A static
sketch or snippet can stay directly in the preview.

The output is the instruction the user copies and the host receives. Write a complete
task with an object, destination, and requested evidence. Use `lf-playground-value` only
where a selected value makes that task more precise. The action still includes every
control in `detail.values`, including controls the prose does not repeat.

## Stateful previews

A preview that needs JavaScript keeps its page-specific behavior in an inline
`<script type="module">` block. Put the real candidates in an ordinary element or a
page-specific custom element, following `references/packages.md`, "What a behavior
module owes".

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

For the shared A/B state, dynamic-row explorers keep stable row keys, apply add, remove,
reorder, and edit operations once, then derive both row renderings and their counts
from that state. Canvas and SVG explorers use one Pointer Events controller with
pointer capture and a keyboard route; translate the input to model coordinates once,
then render both candidates and their measurements from the same coordinates. Call
`layoutChanged` after a gesture changes geometry.

Before handoff, manually operate every custom gesture the page claims. Check that both
candidates reach the same input state, the measurements update, the complete typed value
map is still present, and the copied instruction can be acted on without the preview.
Operate every control and preset, then reset, restore, copy, and submit. Check wide,
narrow, and short viewports. Check an exported file too when the page has no live
samples; live samples need a server.

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

Mount built variants together and preserve their tokens, typography, states, and
viewport assumptions. A runtime DOM capture is an appearance-only artifact: cloning it
does not carry the component's listeners, state source, or lifecycle. When behavior is
part of the comparison, mount a component through its production entry point or serve
a document as a complete captured revision. Do not add substitute page handlers to
captured DOM and present it as the current behavior. Candidate-specific values live
under explicit keys; a copy-to-other action changes only the intended candidate. When
variants differ by compilation, build and serve both source revisions rather than
drawing a visual replica.

### Multi-change decision sweep

Keep proposed changes under stable ids and retain one decision value per id. Filtering or
ordering changes what is shown, not which decisions exist. Each offered decision remains
keyboard reachable and the output summarizes accepted, rejected, and undecided changes
without depending on display order. Verify a decision survives filter, reorder, restore,
and reset before the final submission.

Any real fixture the playground needs is captured at build time so reopening and export
do not depend on a network fetch. The export keeps local controls, gestures, derived
output, reset, and copy, and disables submission because no agent or server is present.
