# Live samples

Use `lf-sample` with one direct `template[data-sample]` to let the user
operate a complete Leaf page inside the surrounding document. Give both the
element and template stable ids. Put the child's content and styles directly in
the template; Leaf supplies the document and its `main`, a column page unless the
template's `class` names the child's Layout instead, such as
`class="layout-workspace density-working"` for a workspace:

```html
<lf-sample id="practice" label="practice release note">
  <template id="practice-page" data-sample>
    <h1>Weekend service</h1>
    <p id="service-note">The sample shuttle runs every hour.</p>
  </template>
</lf-sample>
```

The sample's gutter contains only the content being demonstrated. Keep labels,
host controls, and instructions about using the sample outside that gutter;
instructions that belong to the demonstrated page remain inside it.

The child uses the parent's selected layer and starts with its own event log. It
stands in the surrounding page as a block as tall as its content, with only the
Threads row of its chrome. When the window itself is what the sample shows, such as
Leaf's banner, bottom bar, or drawers, the boolean `window` attribute makes the child
a whole Leaf window instead, chrome included, at a fixed height that scrolls inside.
A click or Tab reaches the child directly; its normal widget controls, keyboard
routes, comments, and replies work there. Escape closes the child's open controls
before returning to the surrounding page. Every live sample supplies **Full view**,
which expands the same child to a whole Leaf window at viewport size. **Return to
page**, or Escape after closing the child's controls, restores the embedded view
with its choices, drafts, and history intact. Reset creates a fresh page from the template.
Child decisions and comments do not change the parent's log or ask inventory.
Set a page-wide body declaration, such as `data-annotations="page"`, on the sample
template when the child needs it. Leaf carries that declaration onto the child's
body; the surrounding page keeps its own choice.
Host-driven view changes preserve focus. Programmatic navigation inside a sample
scrolls only that child document.
The child is temporary: use an ordinary Leaf page when its history must outlive
the sample. A live sample needs a server, so a page declaring one cannot be
exported (`references/serving-pages.md`, "Exported files").

A thread message's `--markup` can carry a live sample too, and the user operates it
in the thread. Its child is checked as the message is posted and uses the layer of
the version showing the message; that version's captured files are the only page
files it can load, so keep its code inline in the template. Its
`data-sample-threads` cannot name the thread the message is in, since the copy would
hold the same sample again.

To start with fictional conversations or decisions, author an inert JSON script
in the parent and name its id in the template's `data-sample-events`:

```html
<script id="service-history" type="application/json">
[
  {"id":"service-question","kind":"comment","author":"user",
   "anchor":{"section":"service-note"},"text":"Does Sunday keep the same timetable?"},
  {"kind":"reply","author":"agent","parent":"service-question",
   "text":"Yes, both weekend days use this timetable."}
]
</script>
<lf-sample id="service-window" label="weekend service" window>
  <template id="service-page" data-sample data-sample-events="service-history">
    <h1>Weekend service</h1>
    <p id="service-note">The shuttle runs every hour.</p>
  </template>
</lf-sample>
```

The array contains ordinary event commands, checked against the child document
at `page check` and admitted before its first presentation. Give an event an explicit
`id` when a later command references it; omitted ids and timestamps are supplied,
and the history belongs to revision 1. Several samples can name the same script;
each gets an independent copy. Reset restores that authored history. The script
must be inline `application/json` in the markup declaring the template: the page, or
the message carrying it. Its events
never appear in the outer log: leave fictional fixture anchors inside the template,
and use this declaration rather than posting setup events from a page module.

To begin with threads from the parent, set `data-sample-threads` on the
template to their space-separated thread ids. The declaration selects from the
parent's current log rather than requiring it: a page whose log does not hold one
of those threads yet — a first version, or a copy made from the source alone — opens
the sample without that thread. Their anchored content must exist in the
child. Reset copies those threads again from the parent; subsequent child
replies remain independent. A template chooses either `data-sample-events` or
`data-sample-threads`, never both.

The child is a separate document in a sandbox. A `<style>` or module script in the
template applies only to the child, and the surrounding page's styles and scripts do
not reach it; neither page can read the other's DOM, browser storage, or runtime
functions. Scripts, embedded frames, forms, popups, and downloads work in the child,
and native resource loaders and module-relative URLs reach its own captured assets. A
page module can await the element's `ready` promise for the current child's
upgraded, usable interface. The child's banner can still say saved state is loading;
its comments already work, independently of the containing page.
Reset, and the child leaving its page, each replace that promise. The surrounding
page presents and takes keys without waiting for a sample whose arrival the reader
would not see, such as one below the first screen, so a module that needs the child
awaits `ready` rather than the page's presentation. `await
sample.reset()` replaces the child with a fresh copy of its initial state, and a
reload inside the child reconnects the same child. When the child cannot be loaded,
`ready` rejects and the sample shows the error with Reset available. The bubbling
`lf-sample-ready` event carries `detail.sample` after each upgrade, including
Reset and a reload, so host controls can reapply a selected view without inspecting
the Reset button. Once the child leaves its Leaf page, `ready` waits for the next one,
which a reload brings. The containing page cannot tell a reload from a link to another
document, so after such a link the wait lasts until Reset, which rejects it with
`AbortError`.
To select a conversation, call `await sample.showThread(id)` with its root event id;
this waits for the child's authoritative state reading, then shows the same page
destination as its marker. To inspect it in Threads,
call `await sample.showThread(id, {surface: "panel"})`. The panel view accepts
`status: "open" | "resolved" | "all"` and `waiting: "user" | "agent" | "all"`;
omitted values restore Open and unrestricted waiting. A panel view may omit the
id to show its list. Completion means the selected view has presented; it returns
false when a newer selection or Reset supersedes it. A selection the child leaves
before presenting waits for the next document, as `ready` does. Outer controls keep keyboard
focus. Use this method instead of clicking the child's private chrome or observing
its DOM. Reapply the selected view on `lf-sample-ready` after Reset or reload.
Author child content in the
template rather than copying rendered controls from the parent. Ordinary
`lf-sample` children, without a template, remain static quoted material.

An ordinary served Leaf page can appear in a plain `<iframe src="…">`, keeping
that page's durable history. Use its existing served URL. The parent and child
must share the browser origin: scheme, hostname, and port. Another local port
is a different origin. Leaf blocks cross-origin parents so another site cannot
place an authenticated Leaf control beneath a misleading interface. Framing
does not copy or reset the page.
