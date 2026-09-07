# Playgrounds

Use `lf-playground` when several values need to be explored together before the reader
chooses one configuration. Put it inside `lf-ask`, declare controls and optional presets,
then include exactly one preview and one output.

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

Bind a simple preview with page CSS. Each value is reflected on the playground in both
forms. A text control's custom property is a quoted CSS string, so it can be used by
`content`; its data attribute contains the unquoted text:

```css
#sample-card { border-radius: var(--playground-radius); }
#card-design[data-playground-tone="quiet"] #sample-card { border-color: var(--rule); }
#sample-card::before { content: var(--playground-title); }
```

A computed preview belongs to a companion package. Its widget reads
`closest("lf-playground").values` for the complete current snapshot and listens for the
bubbling `lf-playground-change` event; `event.detail.values` has the same shape. Page
authors do not add scripts to the document.
