# Page behavior

Read this before giving a page a script, a file under `page/`, a
`page/registry.json`, or anything loaded from another server.
`module-authoring.md` holds the helpers a script uses.

Write page-specific behavior in an inline `<script type="module">` or in browser-ready
modules below `page/`, referenced through `/page/…`. A library that ships only a classic
script loads with `<script defer src>`, from `page/` or any server; every script runs after
Leaf has read the page, so an inline classic, parser-blocking, or `async` script is
refused. Page stylesheets and their local dependencies may live below `page/` too.
Relative imports stay within `page/`; a module that integrates with Leaf may import the
public `/runtime/widget-api.js`. Leaf captures
the complete local dependency graph, effective registry, and selected layer bytes in the
same immutable revision as the markup they control.

Content and style changes update the open document when its registry and JavaScript
are unchanged. Unchanged widgets keep their elements and local interaction state;
changed widgets are replaced. An edit inside an element whose children a page module
moved or detached also replaces that element. Give elements stable ids when their
identity must survive a rewrite (`page-authoring.md`, "Stable anchors").

Changing the registry or JavaScript opens a fresh document. Leaf restores reading
position, recoverable drafts, and comparison state. It can also restore focus and
supported control state when an element keeps its authored id and tag. Element
instances and arbitrary module state do not survive the reload. Reloads wait while
the user is composing. An in-place revision can arrive during selection, commenting,
or editing when it preserves every selected passage or comment's complete authored
anchor scope and every active native editor. Thread replies keep their editing session
independently of the page's authored content. Otherwise the revision waits until
composition ends. Both update paths wait during dragging or undoing, while a gesture
awaits server admission, or while the version menu is open.

Page modules follow `references/module-authoring.md`, "What a behavior module owes". In
particular, its `once()`, `quoted()`, `offer()`, `layoutChanged()`, and durable-state
rules keep authored controls correct after reconnection and thread quoting.

A page module that shows the state of the asks in each card, section or item of its
own layout reads them from Leaf rather than keeping a copy: `readAsks()` in a
`watchProjection` paint with `asksIn(region)` selects each region's asks, answered or open, by the rule `lf-tabs`
rows and `lf-tally` read, and `askActions.next({within})` steps to the next one
waiting on the user (`references/module-authoring.md`, "Reading asks and obligation
queues").

`leaf page check` runs a page's own code, a script or a page widget the
document places, once in the host's browser, and a page with a data widget such as a
chart or a diagram, whose body only its module can read: through upgrade,
presentation, and one frame after it. It fails on every error the page would report to
you through the watcher, an uncaught exception or a rejected promise with the source
location it came from, or a widget that could not draw its body, so a module that
throws on its first paint or a chart that does not parse is found before the URL goes
out. Code that runs only after a gesture or a timer is
not reached; operate it in the pre-handover review. A page with neither is checked
without a browser. On a host with no browser the run is skipped with a note; the page
still reports those errors to you once a browser draws it.

`page/registry.json` may contribute declarations using the package registry language.
Its element entry replaces the selected layer's complete entry; shared `$` declarations
compose at their declared grain. Declaration and implementation ownership are separate:
a page declaration keeps the package widget unless `page/widgets/<tag>.js` exists, and a
page widget may replace the package implementation without restating its declaration.
Both choices are fixed in the revision manifest.

Use a package when behavior, styling, or vocabulary is reused across pages. A one-page
explorer or playground keeps its code in `page/`. Leaf captures the local files a
page's scripts and stylesheets name literally, so import a page file by a literal URL;
a computed `import()` reaches a module on another server, named by its full URL. Leaf
refuses unresolved imports, filesystem escapes, and anything declared about the whole
document (a `<base>`, an http-equiv `<meta>`, an import map), which would send the
runtime's requests elsewhere or leave its modules unresolved.

A script, stylesheet, font, image, or frame may also come from another server, named
by its absolute `http(s)://` URL, and a page's code may fetch from anywhere. The page
loads it as written, so it arrives only while the user is online. Data the page
presents belongs in a `data/` source instead (`references/packages.md`, "External or
derived data"), where the log and an export hold it.

Typed data and media remain inert inputs. Read them through their Leaf/browser APIs;
do not turn their contents into source code or markup.
