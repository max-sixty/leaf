# Reading the page from a module

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers reading the page's words, elements and declarations, the content helpers that render Markdown, code, images and icons, and the page readings: asks, work hierarchies, history, and version changes.

## Reading the page

Read an element's words with `says(element)`, which returns them as passages and
comments read them. `textContent` also returns lines Leaf writes into the page. To name
one of the widget's own parts, use `wrote(element)`, which returns only the words the
author wrote. Read a widget's `<pre>` body with `bodyText(this)`, which trims leading
blank lines and trailing whitespace, or with `dataBody(this)` where whitespace matters, as in
a diff.

An agent's message can carry markup that repeats ids on the page. To find a partner
element, such as the widget a seat serves, search `authoredScope(element)`: the page's
`main`, or the body of the message holding the element. `elementById(id, root)` finds an
id within `root`, or the whole document, including widgets' shadow trees, which
`getElementById` misses. `under(node, root)` says whether `node` is in `root` across
shadow boundaries, and `inChrome(node)` whether it is in Leaf's own interface, as a
widget in a Thread reply is.

### Naming elements

To name an element elsewhere, such as in a feed row, use the name Leaf's chrome gives
it: `addressableLabel(element)`. That is its title, from the attribute its entry
declares with `x-name` or a leading heading or `<summary>`, else its caption,
`aria-label`, `<label>` or `alt`. Failing those, a paragraph or list item is named by
its first words, and another element by the nearest named element around it, so a
question's options take the question's name. A registered widget with no name gets an
empty label; `addressableWord(element)` gives the word for its kind instead. A widget
whose title is an attribute, as a column's `label` is, declares it with `x-name`.

`anchorLabel(anchor, about)` names a comment's anchor as Threads does, and
`excerptWords(text, cap)` cuts text to at most `cap` characters at a word boundary.

### Reading declarations

Read the registry rather than repeating it. `declarationFor(element, key)` returns one
key of the element's entry. `elementsDeclaring(root, key, {direct})` lists the elements
under `root`, or only its children, whose entries declare `key`.
`matchesWhen(element, when)` says whether the element's attributes satisfy a `when`,
such as an `x-thread-seat`'s. `layerFact(name)` returns a copy of a layer-wide `$`
declaration, such as `$reactions`.

### Following a reference

Reach another widget through an attribute declared in `x-refers`
([package-data.md, "References between widgets"](package-data.md#references-between-widgets)),
not by looking up the id yourself. For a widget in an agent's message, Leaf looks in that
message's markup first and then in the page, as the server does; a keyed contract looks
inside the widget's enclosing owner. Both helpers below throw for an undeclared
attribute.

`navigateToDatum(this, attribute, key, {success, missing})` takes the user to the first
element `key` names in the referenced widget. The key is a visual part's id, a projected
datum's key, or whatever the target's `lfElementsFor(key)` maps it to; `lf-code` takes
line ranges, so `"3-5,8"` names those lines. Leaf has the target load or draw the datum,
opens any disclosure around it, focuses it, updates the fragment, and announces
`success` or `missing`. A lazy target can implement `lfRevealDatum(key)`, returning a
promise that resolves once the datum is loaded, `lfDataDatum(key)` to map a key to its
projected element, and `lfDatumLabel(key)` to name a datum not yet drawn. Where your key
is a source location rather than the datum's lasting identity, translate it and read
`projectedDatum(widget, key)`, which returns the one matching element or `null`.

#### Indicating (experimental)

`indicate(this, attribute, key)` marks the elements `key` names in the referenced
widget with `data-lf-indicated`, replacing this widget's previous mark through that
attribute, and returns whether it marked anything. Pass `null` to clear it, including in
your cleanup. It doesn't scroll, focus, load or announce, so a widget may move the mark
every frame, and it says in its own words what the mark means. The log doesn't record a
mark. The default style is an accent outline; a target whose parts have their own look
styles `[data-lf-indicated]`, and calls `layoutChanged(this)` after redrawing what a key
names. The signature and `lfElementsFor` may change.

## Content helpers

### Markdown

A widget whose entry declares `x-text-format: inline-markdown` has its direct authored
text formatted as inline Markdown. With `markdown`, its data body arrives rendered as
block Markdown; the recorded body stays the source. Adopt the rendered
`.lf-markdown-body` and repaint changing prose with `paintMarkdown(body, source)`.
`markdownSourceOffset(body, node, offset)` maps a caret in the rendered body back to the
source. Text set with `textContent` is never formatted.

`inlineMarkdownFragment(text)` returns a fragment, `renderMarkdown(text)` a safe HTML
string for `unsafeHTML`, and `markdownWords(text)` the words Markdown renders to. The
renderer loads lazily, and until it has, they return the escaped source; `loadMarkdown()`
resolves once it has loaded, so a widget showing changing prose repaints then.

### Code

`syntax(source, lang)` resolves to the code's tokens, `[{text, style}]`, coloured by the
page's syntax theme. `synNodes(tokens)` turns them into nodes, and `tokenLines(tokens)`
splits them by line for a widget that numbers lines. `lang` is a registry `$languages`
name; `langForPath(path)` derives one from a file name, and
`ensureSyntaxLanguage(lang)` loads one ahead of time. `highlightBlocks(root)` colours
each `pre > code` in `root` whose `language-…` class names a language.

Leaf adds a Copy button to each `pre > code` in the page. For other source text a widget
draws, such as code in its shadow stage, `copyBlock(block, source, noun)` returns a Copy
button for the block's top right that copies `source()`; `noun`, such as `"code"`, names
what it copies. Call it once the block is connected and append the button to the
widget.

### Text alignment

`alignText(before, after)` aligns two texts by words and returns runs `{kind, text}`,
with `kind` `same`, `delete` or `insert`. A large rewritten middle comes back as one
delete and one insert. To align by sentences, pass an `Intl.Segmenter` with
`granularity: "sentence"` as the third argument.

### Image comparison

`compareImages(a, b)` compares two decoded images at natural size that don't taint a
canvas. It resolves to `{width, height, changed, throughout, regions}`: the compared
size, the number of differing pixels, whether they differ almost everywhere, and
outlines `{x, y, width, height, side, kind}` around content that `changed` or `moved`,
on the before image (`a`) or the after (`b`). `differenceKind(reading)`,
`describeDifference(reading)` and `countAreas(regions)` classify, word and count the
result. `compareImagePixels(a, b)` returns masks `{width, height, before, after, both}`
that are more opaque where a pixel changed more: `before` where only the before image
has content, `after` where only the after does, `both` otherwise. The comparison is
experimental; `lf-shot` is the worked example.

### Media URLs

Pass a `/media/…` path from typed data through `scopedMediaUrl(path)` before putting it
on a generated image or link, so it resolves on published pages too.
`isCanonicalMediaUrl(href)` says whether a path is such a `/media/…` path.

### Icons

`iconElement(name, className)` and `iconTemplate(name, className)` draw Leaf's icons.
For a thread control, put `iconElement("comment", "lf-action-icon")` in an
`lf-icon-action` button, which gives the label.

## Page readings

A widget that draws from the readings below registers its drawing once with
`watchProjection(owner, paint)`. Leaf calls `paint()` straight away, again when the page
first presents, and again whenever a reader it called, such as `readAsks()` or a
controller's `read()`, returns something new. So a paint never lists its inputs. Only
reads before the first `await` count, and reads of DOM nodes don't; watch those
yourself. The watcher pauses while the owner is out of the page. Call the returned
function to end it, or its `refresh()` to repaint after a change Leaf can't see, such as
revealing held news. An optional third argument, `ready()`, holds every paint until it
returns true.

### Reading asks and obligation queues

`readAsks()` returns `{phase, all, user, unanswered}`. `all` holds every ask whose
source is still there, answered and withdrawn ones included; `user` the open asks
waiting on the user; and `unanswered` every open ask, including those with the agent.
Each record looks like this:

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

A widget ask's answer is the state of the verb its entry's `x-awaits.value` names, and
`x-awaits.answered` decides when it is complete
([package-data.md, "User state"](package-data.md#user-state)). So a partial answer can
show while `status` is `open`, and an empty selection can be complete. `answer.event` is
`null` for authored state. An `lf-ask` or other `x-ask-context` wrapper supplies the
prompt and where the user lands.

A prose ask is a question in an agent's message, with `source.kind === "reply"`. The
user's reply or reaction answers it. When the agent ends it with `leaf task end`
instead, `status` is `answered_elsewhere` or `withdrawn` and `end.detail` says why.

An approval ask, `source.kind === "approval"`, asks the user to approve the stamped
version `source.version`. Approving sets `answer.value` to `true`, and Undo reopens it.

`thread` and `message` name the Thread and message of a prose ask or of a widget inside
a Thread. `prompt.target` is where the user goes to answer. A user's answer shows in
`answer` at once; which asks exist changes when the server's reading arrives.

`askWords(ask)` words an answer for display, using a widget's `answerWords`
(`module-state.md`, "Declared widget state"). `asksIn(region, asks)` returns the widget
asks, not withdrawn, inside `region`; `lf-tabs` and `lf-tally` count with it, so a module
marking asks per card or section should too, passing `readAsks().user` for the asks
waiting on the user.

`askActions.open(id)` takes the user to an ask, resolving to `false` if it is gone.
`askActions.next({within, dir})` steps to the next ask waiting on the user inside
`within`, or the previous with `dir: -1`, as `m` does in On me, and resolves to whether
it arrived. A control that calls it should prevent `mousedown`'s default so focus stays
put and a second press steps on. Asks have no answer API; answer through the widget's
own command.

`readQueues()` returns the `{phase, on_user, on_agent, done}` lists the On panel shows.
Each row has a `kind` (`ask`, `todo`, `answer` for the agent's sent replies, and others)
and an `owner`, `user` or `agent`. Rows not done carry `offers: {open, done}`.
`queueItemKey(row)` names a row across moves between lists, and `queueTitle(row)` gives
its title. `queueActions.open(key)` goes to a row. `queueActions.done(key)` ends a to-do
the agent opened on the user, returning its admission promise, and returns `null` for
any other row; asks end through their own widget, reply or approval. Act on a collection
only when its `phase` is `ready`.

### Work hierarchies

`readWork(scope)` reads a work hierarchy the page declares, such as goals and the
workers on them, so a widget that counts its children's work reads it here rather than
from their reports. The page's `$work.widgets` gives tags roles: `scope` bounds a
hierarchy, `goal` and `worker` name the recorded `state` attribute and the values that
mean done, stopped, running or retired, and `evidence` marks a seat for observed data.
The result lists `goals`, `workers`, `leaves`, `stopped` goals, `liveWorkers`, and
`running` and `quiet` workers, each with its authored `element`, and `done` counts
finished leaves. `workRole`, `workElements`, `directWorkElements` and `workAncestor` read
the same declaration. Atlas in `examples/command-hub.page/` is the worked example.

### Page history and reports

A widget that shows the page's history declares `x-history` and reads
`readHistory()`: `{phase, events}`, the server's rows, newest first, each already
carrying its thread, whether it was undone, the agent's name as `agent`, and a gesture's
words. The widget only words these. A widget restoring something from `tabStore` compares
it with the history once `phase` is `ready`.

A widget an agent reports on reads the reports with `reportSequence(this)`, in a paint
registered as `watchProjection(this, paint, () => reportsPresented(this))`. A
`LeafElement` checks `reportsReady(this)` in `render()` instead and returns `noChange`
while it is false. Each entry has `id`, `target`, `source`, `action`, `detail`, `text`,
`ts` and `disposition`: `effective`, `outranked` by a newer report on the same unit and
verb, or
`settled` by a stamped version. Pass `{kind: "thread", id}` for a Thread's reports, or
nothing for all of them. `saidAt(element)` is when the message holding `element` was
sent, or the page published, for showing how long a worker has been quiet.

### Reading version changes

`comparisonChanges(owner)` returns the changed elements inside `owner` in the current
version comparison, or every changed element with no owner, and an empty array with no
comparison active. `watchComparison(owner, callback)` calls back at once and on each
change to the comparison; its returned function ends the watch.

`revisionLabel(event.revision)` is the page's name for the version an event was
recorded in.
