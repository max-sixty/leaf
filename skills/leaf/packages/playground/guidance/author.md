# Playgrounds

Use `lf-playground` when several values or behaviors need to be explored together before
the reader chooses one configuration. Put it inside `lf-ask`, declare controls and
optional presets, then include exactly one preview and one output. The preview is the
surface the reader operates. Controls and presets select a candidate and set its
parameters; the reader performs the interaction being judged inside the preview.

When you have recommendations, offer two to four presets as coherent starting points.
Name the outcome—`Trail alert`, not `Preset 2`—and let the reader tune it afterward.

Controls support `range`, `toggle`, `choice`, `color`, and `text`. Their `name` becomes
the key in the final typed value map. A range's `unit` is appended in its CSS custom
property and in `lf-playground-value`; its data attribute and public `values` entry stay
numeric. A range requires `max`; `min` defaults to zero and `step` defaults to one.

```html
<lf-ask id="card-design-ask">
  <h2>How should the card feel?</h2>
  <lf-playground id="card-design">
    <lf-playground-control
      name="radius" label="Corner radius" kind="range"
      value="12" min="0" max="24" step="1" unit="px"
    ></lf-playground-control>
    <lf-playground-control
      name="compact" label="Compact spacing" kind="toggle" value="false"
    ></lf-playground-control>
    <lf-playground-control
      name="title" label="Title" kind="text" value="Preview card"
    ></lf-playground-control>
    <lf-playground-control name="tone" label="Tone" kind="choice" value="quiet">
      <lf-playground-choice value="quiet" label="Quiet"></lf-playground-choice>
      <lf-playground-choice value="bold" label="Bold"></lf-playground-choice>
    </lf-playground-control>
    <lf-playground-preset label="Soft">
      <lf-playground-setting for="radius" value="18"></lf-playground-setting>
      <lf-playground-setting for="tone" value="quiet"></lf-playground-setting>
    </lf-playground-preset>

    <lf-playground-preview>
      <article id="sample-card"><strong>Preview card</strong></article>
    </lf-playground-preview>
    <lf-playground-output>
      Use a <lf-playground-value for="radius"></lf-playground-value> corner radius and
      a <lf-playground-value for="tone"></lf-playground-value> tone. Title the
      instruction “<lf-playground-value for="title"></lf-playground-value>.”
    </lf-playground-output>
  </lf-playground>
</lf-ask>
```

Bind simple parameter changes with page CSS. Each value is reflected on the playground
in both forms. A text control's custom property is a quoted CSS string, so it can be used
by `content`; its data attribute contains the unquoted text:

```css
#sample-card { border-radius: var(--playground-radius); }
#card-design[data-playground-tone="quiet"] #sample-card { border-color: var(--rule); }
#sample-card::before { content: var(--playground-title); }
```

A preview that needs JavaScript behavior or computation uses a companion package widget.
Create it with `leaf package init ./PACKAGE --widget TAG`, then include both packages with
`leaf page init --package playground --package ./PACKAGE PAGE`.
Follow `references/packages.md` for the behavior-module contract. Inside its own element,
the widget uses ordinary browser APIs and imports Leaf helpers only from
`/runtime/widget-api.js`. Wait for `customElements.whenDefined("lf-playground")` before
reading `closest("lf-playground").values`; later snapshots arrive in the bubbling
`lf-playground-change` event's `detail.values`. The widget owns the preview's gestures and
resulting state. Page authors do not add scripts to the document.
