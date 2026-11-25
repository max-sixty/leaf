# Reading the page from a module

Read with [module-authoring.md](module-authoring.md).

## Reading the page

Read an element's words with the platform's: `innerText` for text to copy or send,
which keeps rendered block boundaries, explicit line breaks and preformatted
whitespace, and `textContent` for the words in the source. Both return words the author
didn't write too: a generated control's, and the words Leaf writes into an element the
author wrote, such as the quiet word on a part the user changed
(`module-scroll-and-motion.md`, "Notices and spoken words"), each in an element marked
`data-lf-gen`. To name one of the widget's own parts, use the `authoredWords` of the
library's [`authored-words.js`](../../../browser/runtime/lib/authored-words.js), which reads only the
words the author wrote, less a popover's, such as a gloss's explanation. Read a widget's
`<pre>` body with the library's
[`data-body.js`](../../../browser/runtime/lib/data-body.js), never the element's
`textContent`. A widget that also declares an input (`inputs`) reads that input's
property instead, which Leaf sets to the `<pre>`'s text when the markup binds nothing
(`package-data.md`, "External or derived data").

Find the element an attribute names by its id with the platform's `getElementById`, on
the root the widget stands in: `this.getRootNode().getElementById(id)`. That finds the
first element in the tree with the id, the page's before a reply's where an agent's
message repeats an id the page holds, and none inside another widget's shadow tree.

Leaf's floating panel, its dialogs and the margin's rows stand inside an element of
class `lf-chrome`, and so does a widget in a reply the panel shows. The library's
[`shadow-tree.js`](../../../browser/runtime/lib/shadow-tree.js) answers whether a node
stands inside such an element across shadow boundaries. A widget that acts on the
document around it, as a contents list does, reads it with
`node.closest('[role="tabpanel"], main')`: the tab panel holding the node, else the
`main` holding it, else null.

### Naming

To name something elsewhere, such as in a feed row, use `nameOf(thing)`, the name Leaf
gives it in words. It names an element, the page (`document`), a thread from
`threads.read()` and a row from `queues.read()`, and returns "" where Leaf gives no name.
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

### Reading declarations

Read the registry rather than repeating it. `layerFact(name)` returns the registry's
entry under a name, as the package's `registry.json` spells it: a widget's declaration
under its tag, each fact under its own name, as `layerFact(element.localName)?.awaits`
reads a widget's `awaits`, or a frozen layer-wide `$` declaration, such as
`$reactions`. A plain HTML tag, such as `table`, can have an entry of authoring
guidance, so read the fact you need rather than whether an entry exists.

### Taking the user somewhere

`go(place, options)` takes the user where Leaf's own travel would, and resolves to
whether they arrived. Where it moves focus or the page, Back returns the user to where
they were, as after a followed link. `place` is one of:

- an element, or with `{key}` the first element `key` names in it: a visual part's id,
  a projected datum's key, or whatever the element's `lfElementsFor(key)` maps it to
  (`lf-code` takes line ranges such as `"3-5,8"`). Leaf loads the datum, opens what
  holds it, reveals and focuses it, sets the URL's fragment to the element's id and the
  key, and announces `success`. An absent destination keeps the reader's place and
  history and shows `missing` in Leaf's notice seat. Pass `focus: false` when the
  source stays the user's input surface, as a file navigator does beside the evidence
  it selects. Find another widget through an attribute declared in `refers`
  ([package-data.md, "References between widgets"](package-data.md#references-between-widgets)),
  so `page check` holds the id;
- a thread, or anything with its `key` ("Reading and opening Threads from a widget" in
  [module-annotations.md](module-annotations.md)), opened where a margin mark would
  open it: the page's primary reader, which is the Leaf panel unless a package
  registers one. `part` is `"thread"` for the card, `"reply"` for the reply editor, or
  `"message"` with `message: message.key` for one message; with none it lands as
  opening a thread does. `travel: false` keeps the page where it is, and `focus: false`
  leaves focus alone;
- an obligation or a row of the On lists, or anything with its `id` ("Reading
  obligations and the On lists"), where On Me's arrival would land;
- `{within, dir}`: the next obligation waiting on the user inside the element
  `within`, or the previous with `dir: -1`, from where the user is, as `m` steps in
  On Me. A control that does this prevents `mousedown`'s default, so focus stays put
  and a second press steps on.

A lazy target can implement
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
key names nothing. A widget that answers `go` with a key needs nothing more for links
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

The library's [`language-paths.js`](../../../browser/runtime/lib/language-paths.js)
names, by its `langForPath`, the registry `$languages` language a file name means, or
undefined where the page's table has none. Leaf colours each `pre > code` a widget
draws as it arrives, whose `language-…` class names a language and that wears the
reading face, and typesets each formula, a `<code class="language-math">`
(`page-authoring.md`, "Markup"), leaving a widget's data body to its module
(`package-themes.md`, "A page's theme"); a block in a shadow tree wears it where the
widget sets `--lf-reading-face: 1` on a box around it. Inline annotations keep their
elements and text while tokens are added inside them; use literal newlines rather than
`<br>`, whose blocks remain uncoloured. A block keeps its colouring while its language
stands, so draw a new `<code>` to show other words. A block with its own colouring
turns off the reading face as other content with its own design does.

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
over a block, such as in a popover's header, is the UI library's `wa-copy-button`,
which the widget builds and gives its `value`.

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

`obligations`, `queues`, `threads` and `history` are the page's readings. Each one's
`read()` returns its current value, which a `LeafElement`'s `render()` that reads it
synchronously follows, drawing again as it moves (`module-plain-elements.md`,
"`LeafElement`"); a read after an `await` is not followed. Each also dispatches `change`
after its value moves, so any element follows it with
`obligations.addEventListener("change", draw)`. `comparisonChanges` below is followed
the first way only.

### Reading obligations and the On lists

An obligation is what a widget waits on the user for, what an update the user
handed over is owed, or a to-do the agent opened; the On lists show each one under its
next actor. `obligations.read()` returns `{phase, all, user, unanswered, byId}`: `all`
holds every obligation whose source is still there, answered and withdrawn ones
included, `user` the open obligations waiting on the user, `unanswered` every open
obligation, including those with the agent, and `byId` a `Map` from each one's `id` to
its record.

`obligations.read(region)` returns the three lists holding only what a region of the
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

To show an answer in the words On Me gives it, the library's `answer-words.js` reads
a reply's words or a widget's `static answerWords` (`module-state.md`, "Declared widget
state").

A module that counts items per heading as the reader moves through them, as `lf-toc`
does, gives each heading the stretch of the page from the element it opens, such as
its `section`, to the next heading's, and counts each item in the stretch holding its
first word, comparing positions with `compareDocumentPosition`.

`queues.read()` returns the `{phase, on_user, on_agent, done}` lists Leaf's panel shows
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

### Page history and reports

A widget that shows the page's history reads
`history.read()`: `{phase, events}`, the server's rows, newest first, each carrying its
thread, whether it was undone, the agent's name as `agent`, and a gesture's words. A
widget restoring something from the tab's memory compares it with the history once `phase` is
`ready`.

The report in force on a widget an agent reports on is its own `state`: the
agent-written verb's `value`, with the words a `text` verb carries in its `detail`.
When it last reported, and what it said before, are `history.read()` rows of `kind`
`report`, naming the `widget`, with its words as `excerpt` and the time as `ts`. The
history holds the newest rows only, so a report older than them is not there.

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
