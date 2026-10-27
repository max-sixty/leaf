# Page behavior

Write page behavior in an inline `<script type="module">` or in modules under `page/`,
referenced as `/page/…`. Load a library that ships only as a classic script with
`<script defer src>`. Relative imports stay within `page/`. A module imports Leaf's helpers
from `/runtime/widget-api.js`. For floating placement that native layout cannot
express, import the bundled Floating UI library from `/vendor/floating-ui.esm.js`.
Leaf saves the local files that scripts and stylesheets name
by a literal path in the same revision as the markup, so import page files by literal
URL.

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
  commands. Give the interface keys of its own with `commands()` (`module-input.md`,
  "Commands and keyboard routes"); arrows, Enter and Escape reach the page first.
- A revision that changes only content patches the page in place without running
  scripts again, so an element it adds or replaces has none of the listeners the script
  attached. Listen on `document` or a stable ancestor, or set up again when
  `PAGE_INTERFACE` fires (`module-authoring.md`, "Startup and presentation").
- Animate from JavaScript through `motion()`, which skips the animation for a user who
  asked for less motion; CSS motion already stops for them.

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
while the user is online. Put data the page presents in a `data/` source instead
(`package-data.md`, "External or derived data"), where the log and an export keep it.

Read typed data and media through their Leaf or browser APIs. Never turn their contents
into source code or markup.
