# Live samples

Use `<lf-sample interactive>` to show working widgets inline, with a sample label
and gutter. Its contents belong to the surrounding page: choices and edits use that
page's event log and Undo, and comments reach the same agent. Its widgets demonstrate
rather than ask, so none of them goes on On me. Give every widget its own page-wide
id. This mode has no inner page, panel, Reset or Full view controls:

```html
<lf-sample id="delivery-sample" interactive label="Delivery choices">
  <lf-options id="delivery-choice" choose>
    <lf-option id="delivery-standard">Standard delivery</lf-option>
    <lf-option id="delivery-express">Express delivery</lf-option>
  </lf-options>
</lf-sample>
```

Without `interactive` or a template, the contents are quoted and take no input.
For an isolated live page, use `lf-sample` with one direct `template[data-sample]` child to let the user operate a
complete Leaf page inside the surrounding page. Give both the element and the template
stable ids, and put the sample page's content and styles directly in the template. The
sample is a column page unless the template's `class` names another Layout, such as
`class="layout-workspace density-working"`:

```html
<lf-sample id="practice" label="practice release note">
  <template id="practice-page" data-sample>
    <h1>Weekend service</h1>
    <p id="service-note">The sample shuttle runs every hour.</p>
  </template>
</lf-sample>
```

Put only the demonstrated page inside the template; labels, your own controls and
instructions for using the sample go outside it.

The sample uses the parent's layer and has its own event log, so its decisions and
comments never reach the parent's log or On me. When the sample is
about the window itself, such as Leaf's panel and its views, add the boolean `window`
attribute to show a whole Leaf window at a fixed height. The user can click or Tab into
the sample and use it fully; Escape returns to the parent, and Reset starts it fresh
from the template. A sample's
history is temporary, so use an ordinary Leaf page when the history must last. A page
with a live sample can't be exported (`serving-pages.md`, "Exported files").

To give the sample a page-wide setting such as `data-annotations="page"`, put it on the
template.

A thread message's `--markup` can carry a live sample too. It uses the layer of the
version showing the message and can load only that version's saved files, so keep its
code inline in the template. Its `data-sample-threads` can't name the thread the
message is in.

To start the sample with made-up conversations or decisions, write an inline JSON
script in the same markup as the template and name its id in `data-sample-events`:

```html
<script id="service-history" type="application/json">
  [
    {
      "id": "service-question",
      "kind": "comment",
      "author": "user",
      "anchor": { "section": "service-note" },
      "text": "Does Sunday keep the same timetable?"
    },
    {
      "kind": "reply",
      "author": "agent",
      "parent": "service-question",
      "text": "Yes, both weekend days use this timetable."
    }
  ]
</script>
<lf-sample id="service-window" label="weekend service" window>
  <template id="service-page" data-sample data-sample-events="service-history">
    <h1>Weekend service</h1>
    <p id="service-note">The shuttle runs every hour.</p>
  </template>
</lf-sample>
```

The array holds ordinary event commands, which `page check` checks against the sample.
Give an event an `id` when a later event refers to it; Leaf fills in other ids and
timestamps. Several samples can share one script, and Reset restores it. Keep the
anchors the events name inside the template, and don't post setup events from a page
module.

To start the sample with threads from the parent instead, set `data-sample-threads` on
the template to their space-separated ids. A thread the parent's log doesn't hold yet is
skipped, and the content the threads anchor to must exist in the sample. A template uses either `data-sample-events` or `data-sample-threads`, not
both.

The sample is a separate, sandboxed document: its styles and scripts apply only to it,
and neither page can read the other's DOM, storage or functions. A page module drives a
sample through the element's API:

- `await sample.ready` resolves once the sample is usable, and rejects if it can't load.
  The parent doesn't wait for samples off screen, so await `ready` rather than the
  page's presentation.
- `await sample.reset()` replaces the sample with a fresh copy.
- The bubbling `lf-sample-ready` event, with `detail.sample`, fires after every load,
  including Reset and reloads; reapply any view your controls chose there.
- `await sample.showThread(id)` shows a thread by its root event id, as its marker
  would; `{surface: "panel"}` shows it in the sample's Leaf panel, or with no id the
  panel's Threads. It returns false when a newer selection, Reset or a reload of the
  sample replaces it.

Use these rather than clicking the sample's controls or reading its DOM. Write the
sample's content in the template rather than copying rendered controls from the parent.
The child-page API applies only to samples with a template. A direct template selects
this isolated mode even when `interactive` is present.

An ordinary served Leaf page can also appear in a plain `<iframe src="…">`, with its own
lasting history, inside a page of the same origin or inside another Leaf page this
machine serves. Give the frame the page's address from `leaf page list` without its
`?t=` key, which the framing page's own address already carried.

## Generated samples

A page module can render newly generated Leaf source without changing the surrounding
page. Import `mountSample` from `/runtime/widget-api.js`, connect an iframe to the
document, then pass a complete HTML document as `source`:

```js
import { mountSample } from "/runtime/widget-api.js";

const host = await mountSample(frame, { source });
const fit = ({ height }) => {
  frame.style.height = `${height}px`;
};
host.on("height", fit);
fit(await host.ready);
```

The source uses the layer the parent's revision selects and its captured files. Leaf checks it as an ordinary
page before serving it, and its native controls use an independent, temporary event
log. The iframe has an opaque origin: it cannot read the surrounding page's DOM or
credentials. Generation happens in the parent; a sample cannot call `generate()`.

`source` and `template` are alternatives. Pass `{template: "authored-template-id"}` to
mount a declared template through the same API, or `{window: true}` alongside either
source to keep a fixed viewport. The returned host has `ready`, `reset()`, `destroy()`
and `on(type, callback)`; the latter returns an unsubscribe function. Reset starts a
fresh child from the same source, and removing the iframe destroys its child.

`ready` resolves after Leaf upgrades the interface and rejects if startup fails.
It does not establish that the generated widget meets the user's request.
