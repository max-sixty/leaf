# Reading the page from a module

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Reading the page

Read an element's words with `says(element)`, which returns them as passages and
comments read them; `textContent` also returns words a widget generated that passages
leave out. For text to copy or send, `says(element, {format: "lines"})` keeps rendered
block boundaries, explicit line breaks and preformatted whitespace. Read a connected
element so its computed styles supply these boundaries; a closed popover is supported.
Inline values stay in their sentence, and ordinary HTML source indentation collapses.
To name one of the widget's own parts, use `wrote(element)`, which returns only the words the
author wrote. Read a widget's `<pre>` body with `bodyText(this)`, which trims leading
blank lines and trailing whitespace, or with `dataBody(this)` where whitespace matters.
A widget that also declares an `x-data` input reads that input's property instead,
which Leaf sets to the `<pre>`'s text when the markup binds nothing
(`package-data.md`, "External or derived data").

An agent's message can carry markup that repeats ids on the page, so look up an id
another element gives within `authoredScope(element)`: the page's `body`, or the body
of the message holding the element. `elementById(id, root)` finds an id within `root`,
or the whole document, including the shadow trees `getElementById` misses.
`under(node, root)` says whether `node` is in `root` across shadow boundaries, and
`inChrome(node)` whether it is in Leaf's own interface, as a widget in a Thread reply
is.

### Naming elements

To name an element elsewhere, such as in a feed row, use `addressableLabel(element)`,
the name Leaf's chrome gives it: its title, caption or label; failing those, a
paragraph or list item is named by its first words, and another element by the nearest
named element around it. A registered widget with no name gets
an empty label, and `addressableWord(element)` gives the word for its kind instead. A
widget whose title is an attribute, as a column's `label` is, declares it with
`x-name`.

`anchorLabel(anchor, about)` names a comment's anchor as Threads does, and
`excerptWords(text, cap)` cuts text to at most `cap` characters at a word boundary.

### Reading declarations

Read the registry rather than repeating it. `declarationFor(element, key)` returns one
key of the element's entry, and `elementsDeclaring(root, key, {direct})` lists the
elements under `root`, or only its children, whose entries declare `key`.
`matchesWhen(element, when)` says whether the element's attributes satisfy a `when`,
such as an `x-thread-seat`'s. `layerFact(name)` returns a frozen layer-wide `$`
declaration, such as `$reactions`.

### Following a reference

Reach another widget through an attribute declared in `x-refers`
([package-data.md, "References between widgets"](package-data.md#references-between-widgets)),
not by looking up the id yourself.

`navigateToDatum(this, attribute, key, {success, missing, focus})` takes the user to
the first element `key` names in the referenced widget: a visual part's id, a projected
datum's key, or whatever the target's `lfElementsFor(key)` maps it to (`lf-code` takes
line ranges such as `"3-5,8"`). Leaf loads the datum, opens what holds it, reveals and
focuses it, updates the fragment, and announces `success`. An absent destination
keeps the reader's place and history and shows `missing` in Leaf's notice seat. Pass
`focus: false` when the source stays the user's input surface, as a file navigator does
beside the evidence it selects. A lazy target can implement
`lfRevealDatum(key)`, returning a promise that resolves once the datum is loaded,
`lfDataDatum(key)` to map a key to its projected element, and `lfDatumLabel(key)` to
name a datum not yet drawn. Where your key is a source location rather than the datum's
lasting identity, translate it and read `projectedDatum(widget, key)`, the one matching
element or `null`.

## Content helpers

### Markdown

A widget whose entry declares `x-text-format: inline-markdown` has its direct authored
text formatted as inline Markdown. With `markdown`, its data body arrives rendered as
block Markdown while the recorded body stays the source. It reads as a Markdown file,
whose soft line breaks are spaces. Adopt the rendered `.lf-markdown-body` and repaint
changing prose with `paintMarkdown(body, source)`.
`markdownSourceOffset(body, node, offset)` maps a caret in the rendered body back to the
source.

`inlineMarkdownFragment(text)` returns a fragment, `renderMarkdown(text)` a safe HTML
string for `unsafeHTML`, and `markdownWords(text)` the words Markdown renders to. They
keep each line break as typed words do; `renderMarkdown(text, false)` renders a Markdown
file, whose soft line breaks are spaces, so its paragraphs wrap to the box. Until
the renderer has loaded, they return the escaped source; `loadMarkdown()` resolves once
it has, and `markdownReady()` says whether it has, so a widget showing changing prose
repaints then.

### Code

`syntax(source, lang)` resolves to the code's tokens, `[{text, style}]`, coloured by the
page's syntax theme. `synNodes(tokens)` turns them into nodes, and `tokenLines(tokens)`
splits them by line. `lang` is a registry `$languages` name; `langForPath(path)` derives
one from a file name, and `ensureSyntaxLanguage(lang)` loads one ahead of time.
`highlightBlocks(root)` colours each `pre > code` in `root` whose `language-…` class
names a language.

Leaf adds a Copy button to each `pre > code` in the page. A widget block holding other
source text, such as numbered code lines, declares its own: give the block
`data-lf-copy`, naming what it holds, such as `"code"`, and an `lfCopy()` method that
returns the text to copy. Leaf stands the button right after the block while both are in
the page, and a page without Leaf shows none. Where the button belongs among the
widget's own controls, as in a draft's toolbar, place the one `copyBlock(block, source,
noun)` returns once the block is connected; it copies `source()`. A copy that stands
among a widget's own controls rather than over a block, such as in a popover's header,
is `copyControl(className, {label, success, error})`: set its `value` before it copies,
and it reports `success` or `error` as a code block's does.

### Text alignment

`alignText(before, after)` aligns two texts by words and returns runs `{kind, text}`,
with `kind` `same`, `delete` or `insert`. To align by sentences, pass an
`Intl.Segmenter` with `granularity: "sentence"` as the third argument.

### Media URLs

Pass a `/media/…` path from typed data through `scopedMediaUrl(path)` before putting it
on a generated image or link, so it resolves on published pages too.
`isCanonicalMediaUrl(href)` says whether a path is such a `/media/…` path.

`canvas2D(canvas, options)` returns the native 2D context of a canvas or offscreen
canvas, and throws if the browser cannot create it. Pass native context options when
the drawing needs them.

### Icons

`iconElement(name, className)` and `iconTemplate(name, className)` draw Leaf's icons,
for what something is or holds, such as a kind or a state. A press shows an action's
symbol instead, so each action looks the same wherever it is offered. `ACTIONS` in
`runtime/icon-paths.js` lists Leaf's actions with their symbol and name, and
`offerAction("symbol", className, label, {action: "comment"})` draws one
(`module-authoring.md`, "Generated controls"). Where your widget gives the press its
face itself, `nameAction(control, action, {label, title, className})`, or
`namedAction(action, {…})` in a template's element part, gives it the action's symbol
and says the action's name as its tooltip and accessible name, unless `label` or
`title` says more. Call it again with another action for a press whose action follows
its state, such as Expand all turning to Collapse all; it swaps only the symbol.
`actionTemplate(action, className)` draws an action's symbol that isn't a press's whole
face, such as the second of two symbols a press swaps by CSS.

For a Lit control, `actionClass(role, className)` supplies the same face classes as
`offerAction`; `actionName(action)` supplies the action's accessible name.

## Page readings

A widget reads these values in its `LeafElement.render()`, which redraws when they
change (`module-authoring.md`, "Drawing what a widget reads").

### Reading obligations and the On lists

An obligation is what a widget waits on the user for, or what an update the user
handed over is owed; the On lists show each one under its next actor.
`readObligations()` returns `{phase, all, user, unanswered}`: `all` holds every
obligation whose source is still there, answered and withdrawn ones included, `user`
the open obligations waiting on the user, and `unanswered` every open obligation,
including those with the agent. Each record looks like this:

```js
{
  id: "widget:release-disposition",
  source: {kind: "widget", id: "release-disposition", tag: "lf-options"},
  thread: null,
  message: null,
  prompt: {text: "When should this ship?", target: "release-context"},
  answer: {value: ["release-later"], event: null},
  status: "answered", // open | answered | answered_elsewhere | withdrawn
  end: null,          // a question the agent ended unanswered: {detail, event}
  next_actor: null,   // user | agent | null
}
```

A widget's obligation takes its answer and completion from its `x-awaits`
([package-data.md, "User state"](package-data.md#user-state)), so a partial answer can
show while `status` is `open`. `answer` is `null` until there is one, and `answer.event`
is `null` for authored state. `prompt.target` is where the user goes to answer;
`prompt.text` is `null` for a widget with no heading and for an update. `thread`
and `message` name the Thread and message of a widget inside a Thread. A user's answer
shows in `answer` at once; which obligations exist changes when the server's reading
arrives. Each `source.kind` adds its own facts:

- A bound-data record's obligation names the owning widget in `source.id` and the
  record key in `source.unit`.
- For a `message` obligation, an agent message sent with `--obligation`, the user's
  next message in its thread is its `answer.value` (`{text}`, or `{token}` for a
  settling reaction); `answeredInWords(obligation)` says whether an obligation is one. When the agent ends it with `leaf task end`, `status` is
  `answered_elsewhere` or `withdrawn` and `end.detail` says why.
- An `update` is what a message the user sent, or an action in an answered widget's
  obligation, is owed. `source.id` names the event and `source.subject` the thread or
  widget the update concerns. Its next actor is the agent while it owes a reply or a version,
  the user when it was handed back to send again, and `null` once a reply, named by
  `answer.event`, answered it. Of several messages the user sent in a row, only the
  newest has one. `obligationsIn` never counts an update.

`answerWords(obligation)` words an answer for display, using a widget's `answerWords`
(`module-state.md`, "Declared widget state"). `obligationsIn(region, obligations)`
returns the widgets' obligations, not withdrawn, inside `region`; `lf-tabs` and
`lf-tally` count with it, so a module marking obligations per card or section should
too, passing `readObligations().user` for those waiting on the user.
`tally(obligations)` counts such a set as `{onUser, onAgent, open, total}`, splitting the
open ones by next actor, and `tallyWords(count, agentName())` words it as `lf-tally`
does, such as "2 left to answer · 1 on Claude", so every count of a queue reads alike.

`obligationActions.open(id)` takes the user to an obligation, resolving to `false` if
it is gone. `obligationActions.next({within, dir})` steps to the next obligation
waiting on the user inside `within`, or the previous with `dir: -1`, as `m` does in On
me, and resolves to whether it arrived. A control that calls it prevents `mousedown`'s
default, so focus stays put and a second press steps on. The user answers an obligation
through the widget's own command.

An element declaring `x-shows`, such as a board card, is a view of another widget's
answer ([package-data.md, "Views of an answer"](package-data.md#views-of-an-answer)).
`shownAnswer(element)` reads it in `render()`, which then redraws with every change to
that widget's state, and returns `null` where the element shows no answer. Otherwise
it returns `{owner, value, available, takes, answer}`: the widget, the value its
answer names now (`null` for none), whether the user can change it, `takes(value)`,
whether the widget can answer `value` (`null` clears it), and `answer(value, says)`,
which sends the widget's own command and returns what `dispatch` returns, or `null`
where the widget can't take `value`. Place the view by `value`, and change it only
through `answer`, so the view records nothing of its own.

`readQueues()` returns the `{phase, on_user, on_agent, done}` lists Leaf's panel shows
under On me and On <agent>. Each row has a `kind`, which is its obligation's
`source.kind` (with the obligation as `obligation`) or `todo` (with the to-do as
`todo`), and an `owner`, `user` or `agent`. An obligation's row lists in `also` the ids
of the other obligations the user answers at the same place, such as the agent's answer
in a thread about it. Rows not done carry `offers: {open, done}`.
`queueItemKey(row)` names a row across moves between lists, and `queueTitle(row)` gives
its title. `queueActions.open(key)` goes to a row. `queueActions.done(key)` ends a to-do
the agent opened on the user, returning its admission promise, and returns `null` for
any other row. Act on a collection only when its `phase` is `ready`.

### Work hierarchies

`readWork(scope)` reads a work hierarchy the page declares within `scope`, such as
goals and the workers on them, so a widget that counts its children's work reads it here
rather than from their reports. The page's `$work.widgets` gives tags roles. A `goal`
names its recorded `state` attribute and lists the values under `done` and `stopped`; a
`worker` does the same under `running` and `retired`, and may name its assignment
attribute in `on`. `evidence` marks the element that shows observed data. The result
lists `goals`, `workers`, `leaves`, `stopped` goals, `liveWorkers`, and `running` and
`quiet` workers, each with its authored `element`, and `done` counts finished leaves.
`workRole`, `workElements`, `directWorkElements` and `workAncestor` read the same
declaration. Atlas in `examples/command-hub.page/` is the worked example.

### Page history and reports

A widget that shows the page's history declares `x-history` and reads
`readHistory()`: `{phase, events}`, the server's rows, newest first, each carrying its
thread, whether it was undone, the agent's name as `agent`, and a gesture's words. A
widget restoring something from `tabStore` compares it with the history once `phase` is
`ready`.

A widget an agent reports on reads reports with `reportSequence(this)`, after checking
`reportsReady(this)` and returning `noChange` while it is false; outside `render()`,
`reportsPresented(target)` answers the same question. Each entry has `id`, `target`,
`source`, `action`, `detail`, `text`, `ts` and `disposition`: `effective`, `outranked`
by a newer report on the same unit and verb, or `settled` by a stamped version. Pass
`{kind: "thread", id}` for a Thread's reports, or nothing for all of them.
`saidAt(element)` is when the message holding `element` was sent, or the page
published, for showing how long a worker has been quiet.

### Reading version changes

`comparisonChanges(owner)` returns the changed elements inside `owner` in the current
version comparison, or every changed element with no owner, and an empty array with no
comparison active. Reading it during a `LeafElement` render subscribes that render
to comparison changes.

`revisionLabel(event.revision)` is the page's name for the version an event was
recorded in.
