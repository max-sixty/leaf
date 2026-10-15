# Page behavior

Read this before giving a page a script, a file under `page/`, a `page/registry.json`,
or anything loaded from another server. `module-authoring.md` holds the helpers a
script uses.

Write page behavior in an inline `<script type="module">` or in modules under `page/`,
referenced as `/page/…`. Load a library that ships only as a classic script with
`<script defer src>`; Leaf refuses an inline classic script, a parser-blocking one, or an
`async` one. Relative imports stay within `page/`, and a module may also import
`/runtime/widget-api.js`. Leaf saves the local files that scripts and stylesheets name
by a literal path in the same revision as the markup, so import page files by literal
URL. Leaf refuses unresolved imports, paths outside the page directory, and any
declaration about the whole document, such as a `<base>`, an http-equiv `<meta>` or an
import map.

When you change only content and style, the open page updates in place: unchanged
widgets keep their elements and the user's state, and changed widgets are replaced.
When you change the registry or JavaScript, the page reloads. Leaf restores reading
position, unsent drafts, and focus and control state for elements that keep their id and
tag, but module state is lost. Give an element a stable id when its identity must
survive a rewrite (`page-authoring.md`, "Stable anchors").

Page modules follow `module-authoring.md`, "What a behavior module owes", whose rules
keep page controls working after a reconnect and inside quoted threads.

A page module that shows the asks in each card or section of its own layout reads them
from Leaf: `readAsks()` in a `watchProjection` paint, with `asksIn(region)` selecting
each region's asks and `askActions.next({within})` moving to the next one waiting on the
user (`module-reading.md`, "Reading asks and obligation queues").

`leaf page check` opens the page once in the host's browser when it has code of its own,
such as a script or a page widget, or a data widget such as a chart. It fails on any
uncaught exception or rejected promise, naming the source location, and on any widget
that couldn't draw. A module that throws on first paint, or a chart whose data doesn't
parse, therefore fails before you hand over the URL. Code that runs only after a gesture
or a timer isn't reached, so operate it in your review before handover. On a host
without a browser, the check skips this step with a note.

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
