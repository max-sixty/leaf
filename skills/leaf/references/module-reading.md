# Reading the page from a module

Read with [module-authoring.md](module-authoring.md).

## Reading the page

Read an element's words with `says(element)`, which returns them as passages and
comments read them. `textContent` also returns words passages leave out, among them a
generated control's words and the words Leaf writes into an element the author wrote,
such as the quiet word on a part the user changed (`module-scroll-and-motion.md`,
"Notices and spoken words"). For text to copy or send,
`says(element, {format: "lines"})` keeps rendered block boundaries, explicit line
breaks and preformatted whitespace. Read a connected element so its computed styles
supply these boundaries; a closed popover is supported.
Inline values stay in their sentence, and ordinary HTML source indentation collapses.
`{drawn: true}` keeps only the words the page draws now, and `until` names an element
to stop at.
`phrasing(element)` says whether an element stands within a line of words, as HTML's
phrasing content and a widget declaring `inline` do, rather than starting a block.
To name one of the widget's own parts, use `named(element)`, which returns only the words
the author wrote, less a popover's, such as a gloss's explanation. Read a widget's
`<pre>` body with the library's
[`data-body.js`](../../../browser/runtime/lib/data-body.js), never the element's
`textContent`. A widget that also declares an input (`inputs`) reads that input's
property instead, which Leaf sets to the `<pre>`'s text when the markup binds nothing
(`package-data.md`, "External or derived data").

`elementById(address, from)` returns the element an address names, or null. An
address is an element's id, or a widget's id and a key (`id:key`), which names the part
the widget has drawn for that key, else the widget. A link's fragment (`#…`) holds
either form URL-encoded, and `elementById` decodes it; any other address is read as
written.

Pass the element that holds the address as `from`, as in
`elementById(this.getAttribute("for"), this)`. An agent's message can repeat ids the
page holds, so an address written in a message names that message's element first and
the page's after it. An id neither holds can still name an element Leaf draws, such as
a widget in a reply a Thread shows. The lookup reaches into widgets' shadow trees,
which `getElementById` misses, and names nothing inside a member a decision has
retired (`retired-when`, `package-data.md`).

Leaf's floating panel, its dialogs and the margin's rows stand inside an element of
class `lf-chrome`, and so does a widget in a reply the panel shows. The library's
[`shadow-tree.js`](../../../browser/runtime/lib/shadow-tree.js) answers whether a node
stands inside such an element across shadow boundaries. A widget that acts on the
document around it, as a contents list does, reads it with
`node.closest("[data-lf-views] > *, main")`: the view member holding the node
(`views`, `module-authoring.md`), whose holder Leaf marks `data-lf-views`, else the
`main` holding it, else null.

### Naming

To name something elsewhere, such as in a feed row, use `nameOf(thing)`, the name Leaf
gives it in words. It names an element, the page (`document`), a thread from
`readThreads()` and a row from `readQueues()`, and returns "" where Leaf gives no name.
An element's name is its title, caption or label; failing those, a paragraph or list
item is named by its first words, and another element by the nearest named element
around it. A registered widget with no name gets an empty name: say the
word for its kind instead, which the library's
[`element-word.js`](../../../browser/runtime/lib/element-word.js) gives. That word is the element's `aria-roledescription`, which the module that
builds the element writes along with a role for it, since ARIA ignores the attribute
on an element with no role, as `lf-playground` makes each preset a `group` it calls
"preset". Without one, it is what the element answers from an `lfWord()`
method, for a word that depends on the element, as `lf-suggestion` says "insertion"
or "rewrite"; else its tag without `lf-`. Where a widget's words alone don't convey
its structure, as a rewrite's old and new text don't, its `lfSays()` returns the
words that describe it. A widget's name is its `label` attribute, as an option
card's, a board card's or a column's is, which names its element on every widget
that takes it (the registry's `$attributes`), whether or not the widget draws it.
The page's name is its own `<title>`, which `document.title` doesn't give while the
tab's title counts what waits on the user in front of it.

`titledElement(heading)` is the element a heading titles: its `hgroup`, the `section`
or `article` that opens with it, alone or in that `hgroup`, and a heading inside a
widget titles only itself. A heading after other content, or opening any other
element, titles only itself. `lf-toc` links each heading to one of them, and a heading's
link preview counts a thread about any of them.

`anchorLabel(anchor, about)` names a comment's anchor as Threads does.

### Reading declarations

Read the registry rather than repeating it. `layerFact(name)` returns the registry's
entry under a name, as the package's `registry.json` spells it: a widget's declaration
under its tag, each fact under its own name, as `layerFact(element.localName)?.awaits`
reads a widget's `awaits`, or a frozen layer-wide `$` declaration, such as
`$reactions`. A plain HTML tag, such as `table`, can have an entry of authoring
guidance, so read the fact you need rather than whether an entry exists.

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

A widget that draws each line of source in a box of its own, as an editor does, marks
the box `data-lf-pre-line`. Leaf then indents the rows a long line wraps onto two
columns past the line's own indent and draws a mark before each. The box states the
line's indent, a count of its leading columns, as `--lf-code-indent`, and its own
inline padding as `--lf-pre-line-inset`.

Leaf adds a Copy button to each `pre > code` in the page. A widget block holding other
source text, such as numbered code lines, declares its own: give the block
`data-lf-copy`, naming what it holds, such as `"code"`, and an `lfCopy()` method that
returns the text to copy. Leaf stands the button right after the block while both are in
the page, and a page without Leaf shows none. A widget that draws marks of its own over
the block, as `lf-code` draws its notes mark and a draft its editing marks, sets the
block's `lfBar` to the `.lf-mark-bar` it places and shows over the block, and Leaf
stands Copy last in it. Place the bar in the seat a lone Copy has: inside the block's
top-right corner, `--lf-block-control-inset` from both of the block's outer edges. A copy that stands among a widget's own controls rather than
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

Each function here returns a page reading. A `LeafElement`'s `render()` that reads one
synchronously runs again when the reading changes (`module-plain-elements.md`,
"`LeafElement`"); a read after an `await` is not followed.

### Reading obligations and the On lists

An obligation is what a widget waits on the user for, what an update the user
handed over is owed, or a to-do the agent opened; the On lists show each one under its
next actor. `readObligations()` returns `{phase, all, user, unanswered, byId}`: `all`
holds every obligation whose source is still there, answered and withdrawn ones
included, `user` the open obligations waiting on the user, `unanswered` every open
obligation, including those with the agent, and `byId` a `Map` from each one's `id` to
its record.

`readObligations(region)` returns the three lists holding only what a region of the
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
  next message in its thread is its `answer.value` (`{text}`, or `{emoji}` for a
  settling reaction). Once its
  thread is resolved after it, it stays `waiting` with no `next_actor`, even when the
  thread reopens, until a message asks it again.
- An `update` is what a message the user sent, or an action in an answered widget's
  obligation, is owed. `source.id` names the event and `source.subject` the thread or
  widget the update concerns. Its next actor is the agent while it owes a reply or a version,
  the user when it was handed back to send again, and `null` once a reply, named by
  `answer.event`, answered it. Where the user sends several of these in one Thread
  before an answer, only the newest has one. No region holds an update.

`answerWords(obligation)` words an answer for display, using a widget's `answerWords`
(`module-state.md`, "Declared widget state").

A module that counts items per heading as the reader moves through them, as `lf-toc`
does, gives each heading the stretch of the page from the element it titles
(`titledElement`, "Naming") to the next heading's, and counts each item in the stretch
holding its first word, comparing positions with `compareDocumentPosition`.

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
`nameOf(row)` gives a row's name ("Naming"). An obligation is
answered only through its widget or thread. Act on a collection only when its `phase`
is `ready`.

### Work hierarchies

`readWork(element)` reads the work hierarchy of the scope `element` is or stands in,
such as its goals and the workers on them, so a widget that counts its children's work
reads it here rather than from their reports. An element outside every scope reads
the work on its page, or in its message, that stands in no scope. Leaf owns the work
roles, and a package maps its tags onto them in `$work.widgets`
([package-data.md, "Work roles"](package-data.md#work-roles)), which composition
checks. The result lists `goals`, `workers`, `leaves`, `stopped` goals, `liveWorkers`,
and `running` and `quiet` workers, each with its authored `element`, and `done` counts
finished leaves; a goal or worker finds its own row by that `element`. Atlas in
`examples/command-hub.page/` is the worked example.

### Page history and reports

A widget that shows the page's history declares `history` and reads
`readHistory()`: `{phase, events}`, the server's rows, newest first, each carrying its
thread, whether it was undone, the agent's name as `agent`, and a gesture's words. A
widget restoring something from `tabStore` compares it with the history once `phase` is
`ready`.

A widget an agent reports on reads `readReports(this)` as it draws its `state`, in a
`LeafElement`'s `render()` or a plain element's `state` setter: `{phase, reports}`.
`phase` turns `ready` once the server's reading has arrived and the state the reports
describe is drawn. Until then the widget draws no report: a `render()` returns
`noChange`. Leaf sets the widget's `state` again as `phase` turns `ready`, so it draws
its reports then. Each report has `id`, `target`, `source`, `action`,
`detail`, `text`, `ts` and `disposition`: `effective`, `outranked` by a newer report
on the same unit and verb, or `settled` by a stamped version. The element form is for
the widget's own drawing: its `phase` waits on that element's drawing, and Leaf sets
only that element's `state` again. Pass `{kind: "widget", id}` for another widget's
reports, `{kind: "thread", id}` for a Thread's, or nothing for all of them. Their
`phase` is the page's, and only a `LeafElement`'s `render()` follows them: nothing
sets a plain element's `state` when they move.

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
The result's length counts changes as the reader does. It is a page reading ("Page
readings").
