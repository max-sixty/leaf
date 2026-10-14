# Reading the page from a module

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers reading the page's words, elements and declarations, the content helpers that render Markdown, code, images and icons, and the page readings: asks, work hierarchies, history, and version changes.

## Reading the page

`says(element)` is what an element says, read the way passages and comments read it.
Use it in place of `textContent`, which also returns lines Leaf writes into the page.
`wrote(element)` reads only the words the author wrote, leaving out what an upgrade
generated, for naming one of the widget's own parts. Read a widget's `<pre>` body with
`bodyText(this)`, which drops leading blank lines and trailing whitespace, or
`dataBody(this)` where whitespace is content, as in a diff; the element's own
`textContent` also holds the formatting around the `<pre>`.

A message's HTML markup is a document of its own, and it may repeat the shapes the page
holds. A module that finds a partner element by reference, as a seat names the widget it
serves, searches `authoredScope(element)`: the page's `main`, or the body of the message
whose markup holds the element. A search of the whole `document` lets quoted markup
answer for the page. `elementById(id, root)` finds an id in the document, or only within
`root` when one is given, such as `authoredScope(this)`, and searches the shadow trees
widgets declare too, where `getElementById` misses. `under(node, root)` says whether
`node` is `root` or inside it, across the shadow boundaries where `contains` stops.
`inChrome(node)` says whether a node stands in Leaf's own interface rather than on the
page, as a widget an agent sent in a Thread reply does.

### Naming elements

A module that names an element away from it, in a feed row or a summary, reads the
page's shared names rather than its own. `addressableLabel(element)` is what Leaf's
chrome calls it: first the name the authoring contract gives it (the attribute its entry
declares with `x-name`, else a leading `<summary>`, heading, or titled member's
`<strong>`, inside a leading `<header>` or `<hgroup>` too), else its caption, its
`aria-label`, its `<label>` or its `alt`. An element whose words are its own, such as a
paragraph or a list item, is otherwise named by those words cut short; any other element
takes the name of the nearest element holding it that has one, so a question's options
are named by the question. Past that, plain markup is named by its words cut short and
a registered widget by nothing: the label is empty, and `addressableWord(element)` is
the word for its kind. A widget whose title is an attribute, as a column's `label` is,
declares `x-name`.

`anchorLabel(anchor, about)` names a comment's anchor the way Threads does.
`excerptWords(text, cap)` cuts words to at most `cap` characters at a word boundary,
ending in an ellipsis.

### Reading declarations

A module reads its registry entries rather than repeating them.
`declarationFor(element, key)` is the value of one key in the entry for the element's
tag, or `undefined`. `elementsDeclaring(root, key, {direct})` lists the elements under
`root`, or only its children with `direct: true`, whose entries declare `key`.
`matchesWhen(element, when)` says whether the element's attributes satisfy a
declaration's `when`, as an `x-thread-seat` declaration's `when` selects its elements.
`layerFact(name)` returns a copy of a layer-wide `$` declaration, such as `$reactions`.

### Following a reference

A module reaches another widget through an attribute its entry declares in `x-refers`
([package-data.md, "References between widgets"](package-data.md#references-between-widgets))
rather than looking the id up itself. Leaf resolves the attribute in the owner's own
authored document first, so a widget in a reply finds its message's element before a
page element with the same id, as the server does, and then in the page, which a reply's
widget may name. A keyed contract resolves inside the owner's enclosing scope instead.
Both helpers below throw a `TypeError` for an attribute the owner's entry does not
declare.

A key addresses elements under the named widget in one key space: a registered visual
part's id, a projected datum's key, or, where the widget's parts have a private address,
whatever its `lfElementsFor(key)` maps to elements under itself. `lf-code` answers its
`hi` grammar, so `"3-5,8"` addresses those lines.

`navigateToDatum(widget, attribute, key, messages)` travels to the first element a key
addresses. Leaf resolves declared shadow trees, asks the target to hydrate lazy data or
draw a visual part it shows only in another state, opens its containing disclosure,
focuses the addressed element, updates the fragment, and announces the supplied
`success` or `missing` message. Commands at that focus use the datum's identity. A lazy
target may implement `lfRevealDatum(key)` to return its hydration promise,
`lfDataDatum(key)` to map a semantic key to the rendered projected element, and
`lfDatumLabel(key)` to name a datum it has not drawn, as its `projectData` label will
once it is. Where a key is a source location rather than the datum's durable identity,
translate it to the durable key and read `projectedDatum(widget, key)`: the unique
current projected element, or `null` when it is missing or ambiguous, including after a
reveal replaced its node.

#### Indicating (experimental)

The signature and the `lfElementsFor` hook may change. `indicate(widget, attribute, key)`
marks the elements a key addresses, in place of whatever the calling widget last
indicated through the same attribute, and returns whether anything is marked; a `null`
key clears it, which a driver owes in its cleanup. Leaf paints the marked elements with
`data-lf-indicated` and nothing else, leaving the target's own ARIA state alone, and
never scrolls, focuses, reveals, hydrates or announces for them, so a driver may move
its indication every animation frame; the driver's own narration says what the mark
means. An indication is browser state, like hover: the log never records it, and a new
revision does not carry it. A widget whose parts have a face of their own styles
`[data-lf-indicated]` on them; the default is an accent outline. A target that
re-renders what a key addresses calls `layoutChanged(this)`, and every current
indication resolves again.

## Content helpers

### Markdown

Registry `x-text-format: inline-markdown` formats direct authored text nodes; `markdown`
renders a data body's exact source as safe block Markdown. A block body is delivered
already formatted for first paint, and its canonical body record stays source, while
passages and comments read its visible words. A module adopts the prepared
`.lf-markdown-body` and uses `paintMarkdown(body, source)` for changing block prose.
`markdownSourceOffset(body, node, offset)` carries a rendered caret back to its offset in
the source. Inline formatting does not interpret strings a module assigns with
`textContent`.

The renderer loads lazily. `loadMarkdown()` loads it and resolves to whether it loaded.
Until it has, `inlineMarkdownFragment(text)`, `renderMarkdown(text)` and `paintMarkdown`
render the escaped source, so a module painting changing prose repaints once loading
completes, and `markdownReady()` says whether the renderer has loaded.
`inlineMarkdownFragment(text)` returns a fragment of inline Markdown, and
`renderMarkdown(text)` returns block Markdown as a safe HTML string for a template's
`unsafeHTML`. `markdownWords(text)` is the words a Markdown string renders to.

A changing numeric readout keeps surrounding text still with tabular numerals and a slot
wide enough for its largest value.

### Code

`syntax(source, lang)` colours code: it resolves to the code's tokens, `[{text, style}]` in
source order, where `style` holds CSS declarations from the page's syntax theme.
`synNodes(tokens)` turns tokens into nodes, and `tokenLines(tokens)` cuts them into one
array per line for a widget that numbers its lines. `lang` is one of the registry's
`$languages` names; `langForPath(path)` derives one from a file name, or returns
`undefined`, and `ensureSyntaxLanguage(lang)` loads a language before it is needed.
`highlightBlocks(root)` colours each `pre > code` block in `root`, `root` included, whose
`language-…` class names a language, as Leaf colours authored code.

Leaf adds a Copy button to each `pre > code` block in the page document itself. For any
other block of source text a widget draws, such as code in its shadow stage,
`copyBlock(block, source, noun)` returns a Copy button standing at the block's top right,
which copies `source()` when pressed; `noun`, such as `"code"`, names what it copies.
Call it once the styled block is connected, and append the button as a child of the
widget. The button shows while a pointer is over the widget or focus is inside it, which
a tap on the block gives a finger, and Enter on the block copies too.

### Text alignment

`alignText(before, after)` shows how one text became another: it returns runs
`{kind, text}`, where `kind` is `same`, `delete` or `insert`, aligned by words. The `same`
and `delete` runs join to `before`, and the `same` and `insert` runs to `after`; a very
large rewritten middle comes back as one delete and one insert. To align a rewritten
paragraph by sentences instead, pass an `Intl.Segmenter` with `granularity: "sentence"` as
the third argument.

### Image comparison

`compareImages(a, b)` compares two decoded images, such as an `HTMLImageElement` or an
`ImageBitmap` at natural size, which must not taint a canvas. It resolves to
`{width, height, changed, throughout, regions}`: the size compared, the larger of the two
images on each axis; the number of pixels that differ; whether they differ over most of
the image; and outlines `{x, y, width, height, side, kind}` drawn on the `before` image
(`a`) or the `after` image (`b`) around content that `changed` or `moved`.
`differenceKind(reading)` classifies a reading as `identical`, `throughout`, `slight` or
`areas`; `describeDifference(reading)` words it for the reader, and `countAreas(regions)`
counts the changed and moved areas, each once. `compareImagePixels(a, b)` reads the same
pair pixel by pixel and returns `{width, height, before, after, both}`, three black RGBA
masks, clear where a pixel did not change and otherwise rising with how far it changed,
from faint to opaque at twice the change an outline needs. A changed pixel is in `before` where only
the before image draws something there, unlike the ground around that run of changed
pixels, in `after` where only the after image does, and in `both` otherwise, as for a
recolour. The comparison is experimental; `lf-shot` is the
worked example.

### Media URLs

Resolve canonical `/media/…` paths from typed data with `scopedMediaUrl(path)` before
assigning them to generated images or links: it uses the page's public root across
ordinary and published pages, while the source keeps its canonical path.
`isCanonicalMediaUrl(href)` says whether a path is one of those canonical `/media/…`
paths.

### Icons

`iconElement(name, className)` and `iconTemplate(name, className)` draw Leaf's shared
icons, as an element and as a template. Use `"comment"` for a thread control, with
`lf-action-icon` inside an `lf-icon-action` button for the inherited stroke and hit area.
The icon is decorative; the button supplies its accessible label.

## Page readings

Each page reading below has a reader, and one watcher follows them all:
`watchProjection(owner, paint)` calls `paint()` on the microtask after subscribing, then
again, at most once per microtask, whenever anything `paint` read from the page's state
has changed, a drag starts or stops holding the page's projection back (`module-input.md`, "Pointer
presses"), or the page dispatches `PRESENTATION` (`module-authoring.md`, "Startup and presentation"). Register
it once for each owner. What the paint reads is tracked: every reader it calls
synchronously, such as `readAsks`, `readQueues`, `readThreads`, `readWork`,
`reportSequence`, `readHistory` or a widget controller's `read()`, so a paint never
lists its inputs, and one watcher serves a paint that reads several readings. A
publication that moves none of them calls nothing. Reads after an `await` and reads of
the document's nodes are not tracked; a paint that depends on them watches them itself.
Several of these in one task make one call. It pauses while the owner is away and reads
again on a return by the rule in `module-authoring.md`, "Connection lifetimes"; moving the owner within one
mutation batch keeps it. The returned function retires the subscription for good,
including queued reads and clock paints. Its `refresh()` reruns the same clock-tracked
reading synchronously, on the return when asked while the owner is away; use it when a
mechanical change, such as revealing held news or entering print, needs a repaint, since
calling the renderer directly would leave its new time readings outside the
subscription. An optional third argument, `ready()`, withholds every paint, clock paints
included, until it returns true; a withheld paint stays owed. Package semantic behavior
subscribes to its own widget's state through its controller.

### Reading asks and obligation queues

`readAsks()` returns the publisher's immutable `{phase, all, user, unanswered}`. `all`
holds widget, prose and stamped-version approval asks, including answered and withdrawn asks whose
sources remain. `user` selects open asks currently awaiting the user; `unanswered`
includes every open ask, even one held with the agent or hidden behind a later prompt.
Each record contains:

```js
{
  id: "widget:release-disposition", // or "reply:<agent-message-id>"
  source: {kind: "widget", id: "release-disposition", tag: "lf-options"},
  thread: null,
  message: null,
  prompt: {text: "When should this ship?", target: "release-context"},
  answer: {value: ["release-later"], event: null},
  status: "answered", // open | answered | answered_elsewhere | withdrawn
  end: null,          // a prose ask the agent ended: {detail, event}
  next_actor: null,   // user | agent | null
}
```

- A widget ask's `x-awaits.value` selects the state verb holding its typed answer, and
  `x-awaits.answered` independently decides completion. `answer` is `null` before answer
  content exists. Partial values can appear while `status` is `open`, and a completed
  empty selection has `answer.value === []`. `answer.event` names the admitted answering
  action, or is `null` for authored or carried state. An optional `x-ask-context`
  wrapper contributes the ask's heading and arrival target without changing its identity
  or answer owner; `lf-ask` is one such wrapper.
- A prose ask has `source.kind === "reply"` and its agent message's id as `source.id`. Its
  answer holds the settling user message or reaction and its event reference. When the
  agent ends it with `leaf task end` instead, `answer` stays `null`, `status` is
  `answered_elsewhere` for `done` and `withdrawn` for `dropped`, and `end.detail` says
  where the answer is or why it no longer applies. A message carrying a widget ask does
  not also pose a prose ask.
- An approval ask has `source.kind === "approval"`, `source.version` naming the stamped
  version, and id `approval:v<version>`. Its answer is `null` until that version's approval
  settles it with typed `answer.value === true`; Undo reopens it. Its arrival reaches the
  Approve control in the On view of Leaf's floating panel.

`thread` and `message` name a frozen widget ask's Thread and exact message, and a prose
ask's Thread and source message; both are null for page-widget and approval asks.
`prompt.text` can be `null` when a widget has no context heading; `prompt.target` names the
element or source the user can visit. Widget membership and completion change when an
authoritative reading is adopted, while pending widget input supplies its typed value at
once. A pending prose reply changes `next_actor` without inventing an admitted answer. A
required-version approval and its Undo update that ask at once, and a refusal restores the
admitted record. Page-widget asks follow the shown document version; frozen-thread asks are
page-wide.

`askWords(ask)` formats the answer of a widget, prose or approval ask, using the
widget family's `answerWords` (`module-state.md`, "Declared widget state"). It may return empty words and owns
no answer state. Display words are not canonical answer data.

`asksIn(region, asks = readAsks().all)` selects the asks a region of the page holds:
each widget ask, not withdrawn, whose source element is `region` or stands under it. It is
the rule a side-list `lf-tabs` row and `lf-tally` read, so a page module that marks or
counts asks per card, section or item reads the same set: filter what it returns by
`status` for answered and open, or pass `readAsks().user` for the asks waiting on the
user.

`askActions.open(id)` resolves the current ask and follows its arrival, including to
earlier prose prompts and completed asks, and resolves to `false` when that ask is
unavailable. `askActions.next({within, dir})` steps to the next ask waiting on the
user inside the element `within`, or the previous with `dir: -1`, as `m` steps through
On me: from the one the user stands on, else from their place in document order,
coming round at either end. From outside the region it counts from the ask the user last
went to when that ask is in the region, so Tab from an ask to a control above it and
Enter steps on; otherwise from the first of the region's asks in sight, the next if it
waits and the one after if it is answered; and with none in sight it enters at the
region's edge. It resolves to whether it arrived. A control that calls it keeps focus where the user stands on a press
(`mousedown` default prevented), so a second press steps on. Answering uses the source's
declared command; asks expose no separate answer API.

`readQueues()` returns the immutable `{phase, on_user, on_agent, done}` that the On
panel and `m` navigation use. Every row names the list it stands on, or left for `done`, in `owner` (`user` or `agent`); `done`
holds asks answered or withdrawn, ended to-dos, and the agent's sent replies, as
`kind === "answer"` rows, newest first. Ask rows
have `kind === "ask"` and their canonical `ask` record, whose `source.kind` is `widget`,
`reply` or `approval`. To-do rows have `kind === "todo"`; response obligations and delivery
retries keep their own kinds. An ask is not also a to-do. Live rows carry their workflow or
`null`, plus `offers: {open, done}` for current command availability. Keep local filters and
ordering separate. `queueItemKey(row)` names a row across a move between lists, and
`queueTitle(row)` names its subject with the same conversation or ask title the On
panel uses.

`queueActions.open(key)`, with a row's `queueItemKey`, resolves the current row and follows
Leaf's arrival, and resolves to `false` for an unavailable row. `queueActions.done(key)`
returns an admission promise only for a current to-do on `on_user`, one the agent opened
on the user, and `null` otherwise. A widget ask ends through its widget, a prose ask through
a reply, a settling reaction or the agent's `leaf task end`, and an approval ask through its version's approval.
Done removes its to-do optimistically, a duplicate cannot send again, and a refusal restores
the admitted reading; the server stays final. Collections keep their shape while `phase` is
`waiting`, `ready` or `offline`; activate only a ready collection.

### Work hierarchies

`readWork(scope)` reads a page-owned work hierarchy from the current publication; a
paint that calls it repaints whenever the widget states, threads, asks or reports it
reads change ("Page readings"), so a widget whose display counts its children's work
reads it there rather than reading their reports. The page
declares `$work.widgets` roles: `scope` bounds one hierarchy; `goal` names a recorded
`state` attribute and its `done` and `stopped` values; `worker` names its recorded `state`,
its `running` and `retired` values, and an optional assignment attribute `on`; `evidence`
declares an observed-data seat. The result's `goals`, `workers`, terminal `leaves`,
`stopped` goals, `liveWorkers`, `running` and `quiet` workers keep their authored `element`
identities, and `done` counts the finished leaves. A stopped goal includes held threads and
outstanding interventions; a worker keeps when it was last heard and the remit of its
closest scope or goal. No dashboard stores another copy. `workRole`, `workElements`,
`directWorkElements` and `workAncestor` read the same role declaration for page-owned
adapters. Atlas in `examples/command-hub.page/` demonstrates the composition, and its
domain tags belong to that page.

### Page history and reports

A widget that renders the page's history declares `x-history` and reads it with
`readHistory()`, which returns `{phase, events}`: the server's rows, newest first, each
already carrying its thread, whether it was undone, the name an agent's row is shown under
as `agent`, and a gesture's words as the document it was made in had them. The widget
words those facts; it does not fold the log. `phase` is `ready` once the authoritative
application is. A widget that restores a tab-local reading keeps it through preparation,
then compares it with the ready history; a preparation reading is no new baseline.

A widget an agent reports on reads the reports with `reportSequence(this)` in a paint
that waits for them to be drawn:
`watchProjection(this, paint, () => reportsPresented(this))` paints only once the widget
has painted every report it holds. Each entry is one report about the widget, in log order, carrying `id`, `target`,
`source`, `action`, `detail`, its words as `text`, `ts`, and `disposition`: `effective`,
`outranked` by a newer report on its coordinate, or `settled` by a stamped version. Pass
`{kind: "thread", id}` in place of the element to read a Thread's reports, or call
`reportSequence()` with nothing to read every report. `saidAt(element)` is when the message
holding `element` was sent, or when the page was published for an element on the page, for
a widget that shows how long a worker has gone unheard.

### Reading version changes

`comparisonChanges(owner)` returns the changed descendant elements in the current version
comparison, excluding the owner itself; omit the owner to read every changed element. It
reads the comparison's own record, not CSS markers, and returns an empty array with no
comparison active. `watchComparison(owner, callback)` calls the callback when the owner
first connects and on each change to the comparison; on a return it calls only when the
comparison changed while the owner was away. A callback that throws is reported, and the
next change calls it again. Its returned function ends the watch. Use `comparisonChanges`
in the callback to update counts or other local presentations.

`revisionLabel(event.revision)` is the name the page gives the version an event was
recorded in, for a widget that lists its own history.
