# Page behavior

Write page behavior as you would on any web page: in a `<script>`, inline or a file
under `page/` referenced as `/page/…`, or one from another server. Leaf runs every
script once the page has parsed, as `defer` does, so `document.write` does nothing. A
script that imports is a module (`type="module"`), and its relative imports stay within `page/`. A
module imports Leaf's helpers from `/runtime/widget-api.js`. For floating placement
that native layout cannot express, import the bundled Floating UI library from
`/vendor/floating-ui.esm.js`.
Each revision saves every file under `page/` with the markup, except hidden ones, so
page code can fetch any of them, such as JSON, CSV, text, images, fonts or wasm. Name a
file relative to the module that fetches it, `fetch(new URL("./data.json",
import.meta.url))`: a URL relative to the document reaches no page file, so fetch from a
module under `page/` rather than an inline script. An export doesn't serve page files
to fetch, so a page that fetches them works only while served.

When you change only content and style, the open page updates in place: unchanged
widgets keep their elements and the user's state, and changed widgets are replaced.
When you change the registry or JavaScript, the page reloads. Leaf restores reading
position, unsent drafts, and focus and control state for elements that keep their id and
tag, but module state is lost.

## A page script

A page script is ordinary JavaScript over the page's DOM: it queries elements, listens,
draws with the DOM, lit-html or a canvas, animates with CSS or the Web Animations API,
and builds plain elements that page CSS styles. Leaf asks four things of it:

- Send whatever the agent must hear through a widget: a playground's contributor or
  actions (the playground package's author instructions), `lf-options`, `lf-draft`, or
  a page widget whose controller records it (`module-state.md`, "The widget
  controller"). State the script keeps itself, in memory or `localStorage`, never
  reaches the log.
- Leaf takes printed letter keys before the page's listeners, for its own walks and
  commands, and handles other keys, such as Escape, on `document` once they bubble
  there. Give the interface keys of its own with `commands()` (`module-input.md`,
  "Commands and keyboard routes"), or handle arrows, Enter and Escape on the page's own
  elements, which hear them first.
- A revision that changes only content patches the page in place without running
  scripts again, so an element it adds or replaces has none of the listeners the script
  attached. Listen on `main` or another stable ancestor, or set up again when
  `PAGE_INTERFACE` fires (`module-authoring.md`, "Startup and presentation").
- Animate from JavaScript through `motion()`, which skips the animation for a user who
  asked for less motion. Leaf stops only its own CSS motion for that user, so stop or
  shorten the page's under `@media (prefers-reduced-motion: reduce)`.

A page script may define custom elements with shadow DOM of their own. Comments can't
quote the words only such a shadow root shows, and Leaf reads the element's own children
in its place, so put words the user should quote in the light DOM and slot them, or
write the element as a widget declaring `x-shadow` (`module-authoring.md`, "Shadow
stages and styles").

Reach a widget's methods with `whileInterfaceConnected` (`module-authoring.md`,
"Startup and presentation"). The rest of `/runtime/widget-api.js` is there where its
helpers save work; `module-authoring.md` is for writing widgets. For text that changes
during an interaction, read `page-layout.md`, "Space for changing text".

A page module that shows the obligations in each card or section of its own layout reads them
from Leaf (`module-reading.md`, "Reading obligations and the On lists").

`leaf page check` opens the page once in the host's browser when it has code of its own,
such as a script or a page widget, or places a widget whose module reads what no static
check opens: a data widget such as a chart, or a screenshot pair's images. It fails on any
uncaught exception or rejected promise, naming the source location, and on any widget
that couldn't draw. Code that runs only after a gesture or a timer isn't reached.
Operate those paths through their final result before handover. Compare the positions
and sizes of the controls and content the reader is using through those states,
including at a narrow width; a settled screenshot cannot show whether changing
feedback moved them.

`page/registry.json` adds declarations in the package registry format; an element entry
there replaces the layer's entry for that tag. `page/widgets/<tag>.js` replaces a
package's module for that tag, with or without a page declaration.

Use a package when behavior, styling or vocabulary is reused across pages; a one-page
explorer or playground keeps its code in `page/`.

A script, stylesheet, font, image or frame can also come from another server by its
absolute `http(s)://` URL, and page code can fetch from anywhere, but these load only
while the user is online. Save a file the page reads as it is under `page/`. Data you
will replace while the page stays open, such as a current status or query result, goes
in a `data/` source instead (`package-data.md`, "External or derived data"): it reaches
the open page without a new revision, is checked against its contract, and an export
keeps it.

Read typed data and media through their Leaf or browser APIs. Never turn their contents
into source code or markup.
