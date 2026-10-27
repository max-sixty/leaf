Use `lf-playground` when the user compares candidates, tunes a configuration, or does
both. A playground can have just one choice: the candidate to build. Put each candidate
inside an `lf-playground-choice` in the preview, so the user selects the actual example
rather than a second selector elsewhere. `lf-options` remains useful for a fixed choice
that needs no playground controls or composed preview.

Frame the question with `lf-ask` when its context lives outside the playground. Keep
behavior that one page uses in that page's module, which can define custom elements, add
state to the playground and derive its output. Behavior several pages reuse belongs in a
package (`references/packages.md`, "Package reach").

Place each control next to the part of the preview it changes. A control that changes
the whole preview, as most do, is a direct child of `lf-playground` and appears in the
rail beside the preview, above the playground's actions. When the preview holds several items
that each take their own settings, such as alerts that each need a threshold, write each
item's controls inside `lf-playground-preview` beside that item, and leave only the
settings every item shares in the rail. A control in the preview still belongs to the
playground. Its value is submitted, and presets and Reset set it.

Choose the playground's space by what the user needs to see and operate together
(`references/page-authoring.md`, "Composing a page"). `data-width="available"` lets it
break out of a reading column; a workspace gives it the window. Candidates the user
compares fit the window together, each picture sized as
`references/authoring-on-me.md` says. Shared controls stay in their rail on wide
layouts and above the preview on narrow layouts, where their own contents scroll if
needed to leave room for the candidates. Controls authored beside an individual
candidate stay beside it.

Keep the premise focused on what the user is setting and why, so the preview, controls
and submission remain easy to reach. Leave facts already visible in the preview there.
Supporting qualifications can go behind a disclosure when they interrupt the task;
`lf-gloss` opens on hover, focus or a tap without moving the page.

An A/B comparison mounts both candidates in the preview with the same configuration and
starting content. When candidates appear side by side, align their names, notes and
drawings in rows, so each candidate's name starts level with the others' however many
lines it wraps to. Each drawing keeps its own height.

## Decision fidelity

Start from the real artifact. Wrap the existing component, document or generated output
rather than redrawing it in page markup. A companion package can carry browser-ready
code and fixtures under `vendor/`, and page images go through `leaf page media`
(`references/authoring-evidence.md`). Load these assets from the page's own origin.

Show each candidate as the interface being decided, so the user can judge it as they
would use it: its content, its controls where they are proposed to go, the context
around it, and the states that tell the candidates apart. A sketch, wireframe or diagram
can be rough and unwired if it shows those things; naming a control in prose does not
show it. Make an interaction work inside a candidate only when the user needs to try it
to decide. Before asking which candidate the user prefers, check that the views support
the choice, and add what is missing. Use product copy for visible and accessible text,
and put commentary about the prototype in the surrounding playground only where needed.

When the decision changes an existing interface, include its current state as a labeled
baseline. Derive each candidate from the baseline and change only what is under review.
Draw everything else as the product shows it, copied from the files that define it: its
controls and words, its icons and logos, theme tokens and interaction state. The user
reads any difference from the product as part of the proposal, so a lookalike, such as
an emoji, a Unicode symbol or a plain dot standing in for an icon or logo, shows a change
nobody proposed. Where a part can't be copied, leave a plain blank of its size.

A copy of a component's DOM has its appearance but none of its listeners, state or
lifecycle. When behavior is part of the comparison, mount the component through its
production entry point, or build and serve each candidate's source revision, rather than
wiring substitute handlers onto copied DOM.

## Controls, samples, and output

A choice control shows radio buttons by default, so alternatives and their labels can
be compared directly. `appearance="select"` favors scanning current settings across
many items, at the cost of opening menus to compare alternatives. Choose by whether
the alternatives or the current values carry the decision. The same
`lf-playground-choice` children provide the select's values and labels; presets, Reset
and the submitted values work the same.

Keep the configuration the user is choosing apart from the cases used to inspect it.
Controls and presets describe what to build. Give preview cases and inspection settings
their own labeled controls, with page-local state outside the playground's submitted
values, and style them with Leaf's control classes (`references/page-layout.md`, "Page
CSS and Leaf's controls"). Changing the case keeps the configuration, applying a preset
keeps the case, and every candidate shows the same case. When editing the data is itself
the task, the data belongs in the configuration.

Offer presets when combinations of several parameters make useful starting points for
further tuning. Choose each preset's values together so they produce a consistent appearance on every
surface they change, rather than optimizing each control separately. A preset sets every
control its look depends on, since a control it leaves out keeps the user's last value.
Before handoff, look at each preset in both themes on every surface it changes, and
rework or drop any you would not ship.
Name a preset for its outcome: `Status strip`, not `Preset 2`.

In this comparison, `format` names which candidate to build. Each choice contains its
preview. Pressing its label or noninteractive body selects it; buttons, editors and media remain
operable without selecting it. Do not put a second `format` control in the rail.
Rich choices form a responsive grid, and plain label choices run in a row that wraps
between whole labels. When the comparison needs a particular arrangement of either, set
`--playground-choice-columns` on the authored choice control or its parent to a grid's
columns, such as `repeat(2, minmax(0, 1fr))`, and use a media query to stack them on
narrow screens.

```html
<lf-ask id="notification-ask">
  <h2>Which deployment notification should we build?</h2>
  <lf-playground
    id="notification-playground"
    submit-label="Create notification"
    data-width="available"
  >
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
    <lf-playground-preset label="Compact">
      <lf-playground-setting for="radius" value="4"></lf-playground-setting>
      <lf-playground-setting for="compact" value="true"></lf-playground-setting>
    </lf-playground-preset>
    <lf-playground-preview>
      <lf-playground-control
        name="format"
        label="Notification"
        kind="choice"
        value="banner"
      >
        <lf-playground-choice value="banner" label="Banner">
          <article class="notification-candidate">
            <h3>Checkout deployed</h3>
            <p>Review the deployment run.</p>
          </article>
        </lf-playground-choice>
        <lf-playground-choice value="status strip" label="Status strip">
          <article class="notification-candidate">
            Checkout · deployed · 18 checks passed
          </article>
        </lf-playground-choice>
      </lf-playground-control>
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

For animation comparisons, compose an `lf-motion` inside `lf-playground-preview` and
put the choice control in its body. Motion supplies the optional shared
playback, speed and timeline; its toolbar stays visible while the candidates scroll.
The motion package's author instructions describe recorded video and authored animation
sources. Playback is inspection state, so it never enters the submitted configuration.
Keep duration or easing in playground controls only when the user is choosing those
parameters for the implementation. Show the current interface as a labeled baseline
beside the selectable alternatives when the decision changes an existing interface.

Apply shared parameters with page CSS. From first paint, Leaf sets each control's value
on the `lf-playground` as a custom property, `--playground-NAME`, and an attribute,
`data-playground-NAME`:

```css
.notification-candidate {
  border-radius: var(--playground-radius);
}
#notification-playground[data-playground-compact="true"] .notification-candidate {
  padding: var(--sp-2);
}
```

To study Leaf's own live interface, embed each candidate in an `lf-sample window` inside
the preview, and keep comparison labels and design controls outside the samples.
Comments on which design to build go on the outer page and reach you. Comments and
decisions the user tries inside a candidate stay in that sample's own log, and Reset
returns it to its starting history. Start fictional threads or decisions inside the
samples, as `references/live-samples.md` describes, never in the outer page's log.

A candidate that restyles a whole page or uses a global stylesheet also needs a live
sample; a static sketch or snippet can go directly in the preview. Put each candidate's
CSS in a `<style>` inside its template, keyed on the child's root, such as
`:root[data-playground-format="status strip"]`: each sample's root carries the
playground's properties and attributes from its first paint, including after Reset.

The output is the instruction the agent receives. Write a complete task that names the
object, where the change goes, and the evidence you want back. Unless the page draws the actions, the user reads it only on
request, from a button beside the playground's Reset and submit, so show in the preview
or the controls whatever the user needs to see before submitting. Use
`lf-playground-value` only where a selected value makes the task more precise; the
action sends every control in `detail.values` anyway. After submission, the button reads **Undo choice** while the
working values and instruction match the saved choice. Editing either restores the
submit action; Undo withdraws the choice and keeps the working values.

## Stateful previews

Write a preview's script as an inline `<script type="module">`, and put the candidates
in ordinary or custom elements (`references/module-authoring.md`, "What a behavior
module owes").

The playground owns working values. Read its immutable `values` aggregate, or declare
one named structured slice with `playground.registerContributor(name, defaults)`.
The returned handle's `get()` reads its immutable current value; `set(next)` replaces
that slice. Update it on input, so a later control change or submission sees the edit.
Names are unique and distinct from control names. Retain the handle rather than a
second configuration object. Reset restores the authored defaults, and a new choice
loads its configuration. Undo withdraws a submitted decision while keeping the current
working values, including edits made since submission, so the user can adjust and
resubmit them.

A page script that draws what the values decide, such as each alert's firings at the
chosen threshold, and writes the instruction itself, is complete as below; adapt
`paint` and `instruction` and keep the rest. `whileInterfaceConnected` reaches the
playground once it has upgraded, and holds the page's first presentation until the view
has painted (`references/module-authoring.md`, "Startup and presentation"). `declare`
runs once per playground lifetime, so slices and the instruction provider are declared
there; `connect` runs on each connection, so a reconnected playground restores the view
without declaring its data again. `subscribe` calls `paint` at once and on every
change; it paints synchronously, and its return value is not awaited. A preview without
structured data only subscribes; one without its own instruction keeps
`lf-playground-output`'s markup and has no `declare`.

```html
<script type="module">
  import { keepsText, whileInterfaceConnected } from "/runtime/widget-api.js";

  const FIRED = { 0.5: 31, 1: 12, 2: 4 };
  const playground = document.getElementById("alert-playground");

  function paint(values) {
    const fired = FIRED[values["5xx-threshold"]];
    keepsText(
      document.getElementById("alert-5xx-outcome"),
      `Would have fired ${fired} times`,
    );
  }

  const instruction = (values) =>
    `Set payments-5xx-rate to over ${values["5xx-threshold"]}% and show me the config diff.`;

  whileInterfaceConnected(playground, {
    declare: () => playground.registerInstructionProvider(instruction),
    connect: () => playground.subscribe(paint),
  });
</script>
```

A preview that declares its configuration as contributor slices needs no
`lf-playground-control`. Where the preview draws its own instrument, it can draw the
submission and Reset too: set `actions="page"` on the playground, build two ordinary
buttons, and pass them in `declare` with
`playground.registerActions({submit, reset})`. Leaf then draws no rail or bar of
actions, and the page's CSS styles the buttons. The playground answers their presses and its keys,
writes the submission's words (`submit-label`, then **Undo choice**), and records the
choice. The instruction stays where `lf-playground-output` is written, so place or
style it as the page needs.

Keep native editors mounted and avoid writing their value when it already matches.
The playground owns tab persistence, presets, Reset, instruction copying and submission;
views draw the values they receive. For a structured configuration, set that
playground's `contract` attribute to a named `$data.contracts` entry in
`page/registry.json`. Its `schema` describes the complete `values` object: scalar
controls and contributor slices, required names and any bounds. Each instance can
select a different contract. Admission validates that schema before recording a
submission; an unbound playground uses the package's open values schema.
The `data-explorer` example shows a scalar limit beside structured filter rows.
An instruction provider describes the configuration as a task that makes sense
without the preview.

When both candidates draw from shared state, keep dynamic rows under stable keys, apply
each add, remove, reorder or edit once, and derive both candidates' rows and counts from
that state. Rows the user is choosing, such as a query's filters, are one contributor in
the submitted configuration. Give each node or item a stable element id, so the user can
point at it in Design mode, and keep one decision per id. Filtering and ordering change
what is shown, never which items or decisions exist, and the instruction reports each
item's decision (accepted, rejected or undecided) in an order that doesn't depend on the
display. Store a map's nodes and relations as ids and endpoints, never as positions or
colors alone. To critique a document or source, use Leaf's comments, suggestions,
`lf-diff` or `lf-visual-review` rather than a playground. A canvas or SVG explorer uses
one Pointer Events controller with pointer capture and a keyboard route; it converts the
input to model coordinates once and draws both candidates and their measurements from
them. Call `layoutChanged` after a gesture changes geometry.

Before handoff, exercise the user's comparison and submission journey through the states
that change its result. Check that the preview and measurements reflect the chosen
values, the copied or submitted instruction stands alone, and the controls remain
reachable where the layout changes. Check that focus lands where the user expects after
adding or removing a row, and that a decision survives filtering, reordering, Reset and
reload. Verify Reset, reload and export for state or behavior the page adds to them;
live samples need a server. Capture any real fixture the playground needs when you build
the page, so reopening and exporting it need no network.
