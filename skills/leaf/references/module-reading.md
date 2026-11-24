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
`phrasing(element)` says whether an element stands within a line of words, as HTML's
phrasing content and a widget declaring `inline` do, rather than starting a block.
To name one of the widget's own parts, use `named(element)`, which returns only the words
the author wrote, less a popover's, such as a gloss's explanation. Read a widget's
`<pre>` body with `bodyText(this)`, which trims leading blank lines and trailing
whitespace. A widget that also declares an input
(`inputs`) reads that input's property instead, which Leaf sets to the `<pre>`'s
text when the markup binds nothing (`package-data.md`, "External or derived data").

An agent's message can carry markup that repeats ids on the page, so look up an id
another element gives within `authoredScope(element)`: the page's `body`, or, for markup
in an agent's message, that message's own markup. `elementById(id, root)` finds an id
within `root`, or the whole document, including the shadow trees `getElementById`
misses. `inChrome(node)` says whether a node is in Leaf's own interface, as a widget in
a Thread reply is. The library answers whether one node is inside another across shadow
boundaries (`module-authoring.md`, "Shared web code"). A widget that acts on the
document around it, as a contents list does, reads it with
`node.closest("[data-lf-views] > *, main")`: the view member holding the node
(`views`, `module-authoring.md`), whose holder Leaf marks `data-lf-views`, else the
`main` holding it, else null.

### Naming elements

To name an element elsewhere, such as in a feed row, use `addressableLabel(element)`,
the name Leaf's chrome gives it: its title, caption or label; failing those, a
paragraph or list item is named by its first words, and another element by the nearest
named element around it. A registered widget with no name gets an empty label: say the
word for its kind instead, which the library gives (`module-authoring.md`, "Shared web
code"). That word is the element's `aria-roledescription`, which the module that
builds the element writes along with a role for it, since ARIA ignores the attribute
on an element with no role, as `lf-playground` makes each preset a `group` it calls
"preset". Without one, it is what the element answers from an `lfWord()`
method, for a word that depends on the element, as `lf-suggestion` says "insertion"
or "rewrite"; else its tag without `lf-`. Where a widget's words alone don't convey
its structure, as a rewrite's old and new text don't, its `lfSays()` returns the
words that describe it. A widget's name is its `label` attribute, as an option
card's, a board card's or a column's is, which names its element on every widget
that takes it (the registry's `$attributes`), whether or not the widget draws it.
`authoredTitle()` is the page's own `<title>`, which `document.title` doesn't give
while the tab's title counts what waits on the user in front of it.

`titledElement(heading)` is the element a heading titles: its `hgroup`, the `section`
or `article` that opens with it, alone or in that `hgroup`, and a heading inside a
widget titles only itself. A heading after other content, or opening any other
element, titles only itself. `lf-toc` links each heading to one of them, and a heading's
link preview counts a thread about any of them.

`anchorLabel(anchor, about)` names a comment's anchor as Threads does.

### Reading declarations

Read the registry rather than repeating it. `declarationFor(element)` returns the
widget's entry, each fact under its own name, as `declarationFor(element)?.awaits`
reads a widget's `awaits`. `matchesWhen(element, when)` says whether the element's attributes
satisfy a `when`, such as an `awaits`'s. `layerFact(name)` returns a frozen layer-wide `$`
declaration, such as `$reactions`.

### Following a reference

Reach another widget through an attribute declared in `refers`
([package-data.md, "References between widgets"](package-data.md#references-between-widgets)),
not by looking up the id yourself.

`navigateToDatum(this, attribute, key, {success, missing, focus})` takes the user to
the first element `key` names in the referenced widget: a visual part's id, a projected
datum's key, or whatever the target's `lfElementsFor(key)` maps it to (`lf-code` takes
line ranges such as `"3-5,8"`). Leaf loads the datum, opens what holds it, reveals and
focuses it, sets the URL's fragment to the widget's id and the key, and announces
`success`. Where it moves focus or the page, Back returns the user to where they were,
as after a followed link. An absent destination keeps the reader's place and history
and shows `missing` in Leaf's notice seat. Pass
`focus: false` when the source stays the user's input surface, as a file navigator does
beside the evidence it selects. A lazy target can implement
`lfRevealDatum(key)`, returning a promise that resolves once the datum is loaded,
`lfDataDatum(key)` to map a key to its projected element, and `lfDatumLabel(key)` to
name a datum not yet drawn. Leaf also asks `lfRevealDatum` for the key of a thread on
the widget as it takes the user to that thread on the page, including a thread made
on an earlier value of the data. Such a key can name a part that has since changed or gone,
so open what would hold it, as a diff opens the file an earlier line was in, or return
`null`. Leaf may ask again for a part that already shows, so leave such a part as it is
rather than selecting or redrawing it again.

A URL reaches the same parts, as `#<widget-id>:<key>`. Loading, following, reloading, or going Back or Forward to that URL draws the part
through the same hooks; a load or followed link lands on it, or on the widget where the
key names nothing. A widget that answers `navigateToDatum` needs nothing more for links
to its parts.

## Content helpers

### Markdown

Leaf reads Markdown in one dialect, the library's
[`markdown.js`](../../../browser/runtime/lib/markdown.js), whose header says how it
reads a message a person typed and a Markdown file. A widget that renders Markdown on
the page passes `pageLinks` to the dialect's renderers, so a picture of the page's
media answers at the page's address and opens in Leaf's viewer, and a link that leaves
the page opens in a new tab.

A widget whose entry declares `content: markdown` has its data body arrive
rendered as block Markdown, read as a Markdown file, while the recorded body stays the
source. Adopt the rendered `.lf-markdown-body` and repaint changing prose into it.

### Code

`langForPath(path)` names the registry `$languages` language a file name means, or
undefined where the page's table has none. `dressCode(root)` colours
each `pre > code` in `root` whose `language-…` class names a language and that wears
the reading face, and typesets each formula, a `<code class="language-math">`
(`page-authoring.md`, "Markup"), leaving a widget's data body to its module
(`package-themes.md`, "A page's theme"); a block in a shadow tree wears it where the
widget sets `--lf-reading-face: 1` on a box around it. Inline annotations keep their
elements and text while tokens are added inside them; use literal newlines rather than
`<br>`, whose blocks remain uncoloured. A block with its own colouring turns off the
reading face as other content with its own design does.

Leaf adds a Copy button to each `pre > code` in the page. A widget block holding other
source text, such as numbered code lines, declares its own: give the block
`data-lf-copy`, naming what it holds, such as `"code"`, and an `lfCopy()` method that
returns the text to copy. Leaf stands the button right after the block while both are in
the page, and a page without Leaf shows none. A widget that draws marks of its own over
the block, as `lf-code` draws its notes mark and a draft its editing marks, sets the
block's `lfBar` to the `.lf-mark-bar` it places and shows over the block, and Leaf
stands Copy last in it. A copy that stands among a widget's own controls rather than
over a block, such as in a popover's header, is `copyControl(className, {label,
success, error, role})`, a press of `role`, such as `"symbol"` for Copy's symbol; to
copy through a press of your own built by its role, pass it as `trigger` instead. Set
its `value` before it copies, and it reports `success` or `error` as a code block's
does.

### Media URLs

Pass a `/media/…` path from typed data through `scopedMediaUrl(path)` before putting it
on a generated image or link, so it resolves on published pages too. Any other address
goes on as written.

### Icons

A press shows its action's symbol, so each action looks the same wherever it is
offered: the library's control constructors draw a press from its action's name
(`module-controls.md`), and redraw it where the action follows the press's state, as
Expand all turns to Collapse all. The action names are the keys of `ACTIONS` in the
library's [`icon-paths.js`](../../../browser/runtime/lib/icon-paths.js), each with its
symbol and the words its press says.

## Page readings

A widget reads these values in its `LeafElement.render()`, which redraws when they
change (`module-authoring.md`, "Drawing what a widget reads").

### Reading obligations and the On lists

An obligation is what a widget waits on the user for, what an update the user
handed over is owed, or a to-do the agent opened; the On lists show each one under its
next actor. `readObligations()` returns `{phase, all, user, unanswered}`: `all` holds
every obligation whose source is still there, answered and withdrawn ones included,
`user` the open obligations waiting on the user, and `unanswered` every open obligation,
including those with the agent.

`readObligations(region)` returns the same lists holding only what a region of the
page holds, by the rule `lf-tabs` and `lf-tally` count with: the obligations whose
widget is `region` or stands inside it, shadow trees included, less those withdrawn.
It adds `asks`, whether the region's markup holds a widget declaring `awaits`, even one
whose obligation has yet to arrive or was withdrawn, as a side list keeps a row's room
for an answer through both. A module that marks every card or section reads each one
this way. Each record looks like this:

```js
{
  id: "widget:release-disposition",
  source: {kind: "widget", id: "release-disposition", tag: "lf-options"},
  thread: null,
  message: null,
  prompt: {text: "When should this ship?", target: "release-context"},
  answer: {value: ["release-later"], event: null},
  end: null,          // on a to-do, how the agent ended it: {detail, event}
  next_actor: null,   // whose move it is: user | agent | null
  state: "done",      // waiting | running | blocked | done
  reason: null,       // what the state leaves out, such as why it is blocked
  outcome: "done",    // how a done one ended: done | failed | dropped
  answered: true,     // whether its own answer stands on it
}
```

Every record says where it stands in `next_actor`, `state`, `reason` and `outcome`, the
same words a thread, a plan step and the page's status use. An open one is `waiting` on
its `next_actor`; one the agent has in hand is `running`; one that is owed while nothing
moves it is `blocked`, with the `reason`: `stopped` or `interrupted` (its turn ended
first), `quiet` (nothing has renewed it for a quarter of an hour), `undelivered` (no
turn has taken it in), `terminal` (the agent's turn waits on the user in its own window)
or `failed` (handed back to send again). A `done` one is `answered` when the answer its
source takes stands on it, and was withdrawn when `outcome` is `dropped`.

A widget's obligation takes its answer and completion from its `awaits`
([package-data.md, "User state"](package-data.md#user-state)), so a partial answer can
show while it is open. `answer` is `null` until there is one, and `answer.event`
is `null` for authored state. `prompt.target` is where the user goes to answer: the
innermost named group round the widget, an element whose registry entry declares
`reading-role: group` such as an `lf-group`, or else the widget itself; `prompt.text`
is that group's `label`, else the widget's own name, and `null` for an update. `thread` and `message` name the Thread and message of a widget inside a Thread. A user's answer
shows in `answer` at once; which obligations exist changes when the server's reading
arrives. Each `source.kind` adds its own facts:

- For a `message` obligation, an agent message sent with `--obligation`, the user's
  next message in its thread is its `answer.value` (`{text}`, or `{token}` for a
  settling reaction). Once its
  thread is resolved after it, it stays `waiting` with no `next_actor`, even when the
  thread reopens, until a message asks it again.
- An `update` is what a message the user sent, or an action in an answered widget's
  obligation, is owed. `source.id` names the event and `source.subject` the thread or
  widget the update concerns. Its next actor is the agent while it owes a reply or a version,
  the user when it was handed back to send again, and `null` once a reply, named by
  `answer.event`, answered it. Of several messages the user sent in a row, only the
  newest has one. No region holds an update.

`answerWords(obligation)` words an answer for display, using a widget's `answerWords`
(`module-state.md`, "Declared widget state").

`partOver(node)` is the part of the page `node` stands in: the heading over it, else
the nearest element holding it that its author named, such as a captioned figure, or
`null`. On Me groups its items by it and a link's preview names a place by it. A
question or section stands in the part around it, past its own heading. A module that
counts items per heading as the reader moves through them, as `lf-toc` does, gives
each heading the stretch of the page from the element it titles (`titledElement`,
"Naming elements") to the next heading's, and counts each item in the stretch holding
its first word, comparing positions with `compareDocumentPosition`.

`obligationActions.open(id)` takes the user to an obligation, resolving to `false` if
it is gone; a row of the On lists opens by its `id`.
`obligationActions.next({within, dir})` steps to the next obligation waiting on the
user inside `within`, or the previous with `dir: -1`, as `m` does in On Me, and
resolves to whether it arrived. A control that calls it prevents `mousedown`'s
default, so focus stays put and a second press steps on. The user answers an obligation
through the widget's own command.

`readQueues()` returns the `{phase, on_user, on_agent, done}` lists Leaf's panel shows
under On Me and On <agent>. Each row has its obligation's `id`, which names the row as
it moves between lists; a `kind`, which is its obligation's `source.kind`, `todo` for a
to-do of the agent's; the obligation itself as `obligation`; and an `owner`, `user` or
`agent`, naming its list. The record says where the row stands: the agent has it in
hand while its `state` is `running`, and a row in `done` ended as its `outcome` and
`end` say. An obligation's row lists in `also` the ids of the other obligations the
user answers at the same place, such as the agent's answer in a thread about it.
`queueTitle(row)` gives a row's title. An obligation is answered only through its
widget or thread. Act on a collection only when its `phase` is `ready`.

### Work hierarchies

`readWork(scope)` reads the work hierarchy within `scope`, such as goals and the
workers on them, so a widget that counts its children's work reads it here rather than
from their reports. Leaf owns the work roles, and a package maps its tags onto them in
`$work.widgets` ([package-data.md, "Work roles"](package-data.md#work-roles)), which
composition checks. The result lists `goals`, `workers`, `leaves`, `stopped` goals,
`liveWorkers`, and `running` and `quiet` workers, each with its authored `element`, and
`done` counts finished leaves. `workAncestor(element, role)` returns the nearest element
at or above `element` with that role. Atlas in `examples/command-hub.page/` is the
worked example.

### Page history and reports

A widget that shows the page's history declares `history` and reads
`readHistory()`: `{phase, events}`, the server's rows, newest first, each carrying its
thread, whether it was undone, the agent's name as `agent`, and a gesture's words. A
widget restoring something from `tabStore` compares it with the history once `phase` is
`ready`.

A widget an agent reports on reads reports with `reportSequence(this)`, after checking
`reportsReady(this)` and returning `noChange` while it is false. Each entry has `id`, `target`,
`source`, `action`, `detail`, `text`, `ts` and `disposition`: `effective`, `outranked`
by a newer report on the same unit and verb, or `settled` by a stamped version. Pass
`{kind: "thread", id}` for a Thread's reports, or nothing for all of them.

### Reading version changes

`comparisonChanges(owner)` returns the changes inside `owner` in the current version
comparison, or every change with no owner, and an empty array with no comparison
active. A change is one stretch of the comparison: a run of changed elements in one
view, such as a tab, a `details`, or the content a disclosure control
(`aria-expanded`) names in `aria-controls`, with no unchanged block between them, as a
rewritten section is, together with the blocks the earlier version had there. A
paragraph removed with nothing in its place is a change too, with no elements. Each
change is an object: `blocks`, its elements inside `owner` in page order; `removed`,
what the earlier version's blocks said (`{id, tag, word, words}`); and `at`, the
element it stands by: its first block, or for a removal the element beside its gap, or
the element the removal emptied of every block. A removal's `at` is in the part of the
page the blocks were taken from, so a paragraph removed from a tab counts in that tab.
The result's length counts changes as the reader does. Reading it during a
`LeafElement` render subscribes that render to comparison changes.
