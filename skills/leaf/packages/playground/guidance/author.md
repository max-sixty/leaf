# Playgrounds

Use `lf-playground` when several values or behaviors need to be explored together before
the reader chooses one configuration. Put it inside `lf-ask`, declare controls and
optional presets, then include exactly one preview and one output.

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
`closest("lf-playground").values`. Later control snapshots arrive in the bubbling
`lf-playground-change` event's `detail.values`. The page module owns its preview
state and gestures; the playground owns the submitted configuration.

Keep one interaction state and render both candidates from it. Dynamic-row explorers
keep stable row keys, apply add, remove, reorder, and edit operations once, then derive
both row renderings and their counts from that state. Canvas and SVG explorers use one
Pointer Events controller with pointer capture and a keyboard route; translate the input
to model coordinates once, then render both candidates and their measurements from the
same coordinates. Call `layoutChanged` after a gesture changes geometry.

Before handoff, manually operate every custom gesture the page claims. Check that both
candidates reach the same input state, the measurements update, the complete typed value
map is still present, and the copied instruction can be acted on without the preview.
