# The page in the browser

The norms the runtime, the widget modules and the theme are built to. Each was
learned by getting it wrong, and each names its failure, because the rule without
the failure would read as a preference. Four norms bind this layer and the Python
side at once — the log outranks the document, one representation per concept, the
file's reading never claims more than the page's, and the widget list is never
closed — and those live in the repo's own CLAUDE.md.

## One writer per thing

If two functions can write the same page state, they have to agree about who owns
what and who runs first — and that agreement lives nowhere the compiler or the
tests can see. `paintAnchors` is the only thing that marks the page: the threads'
marks and the open composer's draft mark are decided in one loop, so ownership is
an `if` rather than a protocol. Before that it was three functions, an ordering
constraint stated only in a comment, and a guard in one function reading a
`data-` attribute the other wrote — and every bug in that arrangement was the two
drifting apart.

When you find yourself writing a guard that reads state another function wrote,
the fix is to merge the writers, not to add the guard.

## The one writer may not write the box the layout is measured from

The room a wide widget spends is measured off `document.body`: the window, less
the strip an open comment panel holds, less every margin a widget has claimed. So
body is the one box the layout has to be able to watch, and watching is the only
answer that survives the widget list being open. The room used to be recomputed
from a list of the ways the box was known to move, and a widget that moved it any
other way got no recomputation at all.

Watching was impossible while the layout's own writer wrote that box. Body is a
border-box scroller of the window's height, so when `syncLayout` wrote body's
`padding-bottom` to hold the key line's room, the write was a resize of the very
box it had just been called about. Chrome will not re-deliver an observation
broken from inside the round it was already answered in, and reports that as
"ResizeObserver loop completed with undelivered notifications" on the window's
`error` channel — which nothing was reading (`tests/CLAUDE.md`). Three observers
watch body, so a single change in the key line's height would have put that
report on the console of a page that had done nothing wrong.

So the chrome's reservations are boxes in the document's flow: `body::before`
holds the banner's room at the head, and the chrome container's own padding holds
the foot's. Nothing measures either box, so the writer is clear of the box it
reads. That fixed paper as well, because a box goes where the chrome goes, while
a padding on the scroll container stays behind: 42px of blank had stood over the
first line of every printed page, reserving room for a bar that was not on the
paper.

Two more writes were hiding behind that one. `syncLayout` also set body's
`margin-right` to the strip an open panel holds, and it toggled
`data-lf-cramped`, which is body's own padding on the theme's side
(`theme.css`). Neither write was ever punished, and for two different reasons.
The margin transitions, so its used value did not move until the frame after the
write, and the round the write landed in closed intact. And the veto — the
cramped toggle — was reached from a `resize` listener that ran ahead of the
observation, so its resize was never inside a round at all. Correctness resting
on an easing curve is not correctness, and a second trigger for one writer is
what the other kind looks like from the outside.

The strip belongs to a media query now, keyed on an attribute `setPanel` states
on body, and the veto is a function of its own, called on the two occasions that
decide it — the window and the panel — neither of which is a reading of the box.
What is left in `syncLayout` writes only chrome, and the `resize` listener went
with the writes: body is the window's own height and width, so the window is one
more way that box moves.

The general form is that a fact derived from a box is not derived by a writer of
that box. Where one function has to be both reader and writer, the write moves
to a box nobody is measuring — or to the cascade, which is not that function.

## A gesture the log has not taken outranks everything the page has read

A widget paints the user's gesture before the log has taken it, so until the poll
reads the action back, the page holds state no log accounts for. Replay leaves
the widget alone for exactly that long. Every `applyAction` states the widget
whole, so replaying an action from before the gesture hands the reader their
older state back — and the next gesture then computes from what that replay
painted. A `multiple` group two picks in, repainted holding one, sends the next
toggle as a set the reader never chose. Applying each action exactly once is what
makes replay converge, and "exactly once" says nothing about *when*.

All of that rests on the log holding the gestures in the order they were made,
and the wire does not give that order: the server answers each request on a
thread of its own, so a pick overtaken by the pick after it leaves a decision the
reader never made standing as their state. So `post` sends one action at a
time — and the wait costs nothing, because the page has already painted. No
machine here reproduced the race in two dozen tries, so the gate states the
condition rather than running for it: the first send is stopped in the wire, and
the second click is made while it is still there.

The hold belongs to the layer, in `sendAction`'s record of what is in flight, and
no module writes one of its own. `lf-draft` once did, privately (`#sending`), and
was the only widget that had a hold — written at the level of the one widget in
front of its author rather than at the level the problem is general at. What a
module still owes is the state the layer cannot see: an open editor is a live
gesture no send accounts for, so its `applyAction` returns `false` while one
stands.

## The page finishes twice, and the second time is the log's

`lf-upgraded` is the document's word for being done: widgets upgraded, the async
ones settled, the geometry and the drawn SVG final. The runtime writes it in the
same breath as it *starts* the first poll, and never awaits that poll, so the
stamp says nothing about the log at all. `lf-applied` is the other half, written
at the end of every replay pass: the page saying it has heard the log and
rendered what the log holds.

Anything that means "the page is ready" wants both stamps, and the gap between
them is one fetch wide — which is why it keeps being missed. `version export`
copied a page blank, and the suite lost three keypresses into pages that had
nothing yet to answer them. Nothing collapses the two stamps into one: the
document's stamp owes nothing to the network, and a page whose server never
answers has still finished becoming itself.

## A pinned version scopes the document, never the conversation

Two readings of the same log run on every page, and they take different windows
of it on purpose. Replay asks what the document held at this version, so it stops
at `VNUM`. The panel asks what has been said, so it takes the whole log
(`retractionFloors(Infinity)` in the runtime, and `upto=None` from
`interact.py`'s callers): a thread opened on v3 is the same thread on v7.

The two readings disagree on screen, and it reads as a contradiction: a reader
pinned to v3, with a v5 note that `restated` the passage an accept rested on,
sees the thread reopened in the panel and the suggestion still painted accepted
beside it. Both are right. Giving one window to both readings loses whichever
question the other was answering. Scope the panel to the version and a retraction
is not news until the reader steps forward, so the older page keeps from them the
one thing they most need to hear. Unscope replay and decisions made after a
version are painted onto the markup the page had before them — a page that never
existed.

A registry-declared widget conversation is the same whole-log reading in a second place, not a
third reading or a store: while the current document holds its owner, the runtime projects the
owner's exact-section threads textually inside it. Pinning a version that still holds the owner
therefore shows the current conversation; a version that drops the owner drops only this page
view, while Comments keeps the thread. Interactive reply markup stays in Comments, so one event's
widget ids are instantiated once even while both places show its words.

## Derive rendering from state; never read it back

`composerOpen`, `fabAnchor` and `diffBase` are the state; `style.display` is a
rendering of it. Nothing reads `style.display` to find out what is going on,
because the rendering has values the state doesn't: `display` is `""` before an
element is first shown, and a guard testing for `"block"` or `"none"` ran on
every mousedown in the document and swallowed the click.

A setter owns each state/rendering pair (`showComposer`, `showFab`) and states
the whole outcome, so it can be called from anywhere without first asking what
the current state is. Calling one is not free — `showComposer` repaints — so a
caller firing on every mousedown says what it means
(`if (composerOpen && !composerInput.value)`) rather than the setter guessing
which of its callers was the noisy one.

## Paint; don't wrap

Marking text by wrapping it in elements splits text nodes, and a redraw that
lands between a mousedown and its mouseup swaps the node under the pointer — the
browser then dispatches no click at all, and a link inside a marked passage
silently stops working. The CSS custom highlight registry paints a `Range` and
touches no nodes, so a redraw is safe whenever it lands, and that is what lets
the same pass run from a mousedown handler and from a poll. What wrapping gave
for free — knowing which thread the pointer is over, and the pointer cursor —
comes back as a geometric hit-test (`markAt`) over the pass's own record of what
it drew.

A painted range builds no accessibility node either, and no ARIA relation puts
one back: on a block that isn't focusable, screen readers variously ignore
`aria-describedby`, report none of the labelling attributes on a bare `<p>`, or
say only that details exist. What every screen reader announces in every mode is
text. So the same pass writes one hidden, unselectable button per block that
holds a mark, saying how many comments are on that block. It names the block
rather than the marked words, because naming the words would be wrapping them
again.

The cost is worth stating anyway: writing text into the author's document is a
thing to do carefully. The injected line has to stay out of a selection, out of
the next quote, out of what a widget reads back as its own, and out of the
mutation stream a screen reader rebuilds its buffer on.

## The runtime's line lands inside widgets

A comment can land anywhere the user can select, so the hidden line announcing
one lands inside widgets too — and a widget reading its own light DOM back gets
the runtime's words along with the author's. `.lf-ui` is no help here: that class
keeps chrome out of everything *the runtime* reads, and `textContent` honours no
markers.

Two rules follow, because there are two failures. The line goes on a text block
or on the element an anchor names, never on the inline run or body div between
them: `lf-draft` seeds its editor from its body div, and a line left there
arrived in the textarea and posted with the user's edit. And a widget asking what
its own slot holds calls `says`, not `textContent` — a block inside a widget is
still a block, so the line lands in it legitimately, and `lf-suggestion` once
labelled itself from the raw text and offered to accept "Retry three times.
1 comment".

## The page holds still under the user's aim

The gestures this product is made of are the long ones: a double-click that opens
an editor, a drag across three lines, a press on a row hanging in the margin.
Anything that moves between the reader deciding where to point and their pointer
arriving is aim thrown away. So a state change may repaint whatever it likes and
must move nothing — and where something has to move, it moves as motion rather
than as a jump, because motion is the form the eye can follow.

Two of the three ways a page moves are layout, and any geometry read catches
them: an element that resizes pushes its neighbours, and a control that shows its
state in font metrics does the same thing smaller — a selected tab set in 600
weight is a wider tab, so the strip reshuffled under the pointer that had just
pressed it. That is why the state a control wears is paint (ink, rule, fill) and
never weight or size. The third way moves nothing, and no measurement reaches it:
the draft's editor wore an outset focus ring, so a double-click was answered by
the frame around the editor growing 2px on every side while every rect stayed
identical. What found that was a screenshot diff of the pixels outside the box,
which is the check to reach for whenever the fix under review is a border, a
ring, or a shadow. Emphasis paints inside the box it belongs to.

Said positively, room is reserved before it is needed, not taken when it is. The
draft's control row exists in both of its views, a `choose` group holds the pick
mark's strip on every card, and a control that will rewrite its own label holds
room for the widest word it may say. Reserve that room from the words themselves
wherever the words are enumerable: a control lists what it may say, and `reserve`
floors the control at the widest of them, measured in the control's own box and
live typeface at load, so the reservation re-measures itself when the type moves.
Three numbers stood in the banner as constants instead, and all three quietly
stopped covering the day `--t-5` grew half a pixel.

The rule has an edge, and the edge is the pressed control's own line. Below that
line the page is content and may move — a tab showing another panel is what the
press was for. On the line itself nothing may move, because the line is where the
next gesture is already aimed. News arriving on its own has no gesture behind it,
so for news the edge falls around the whole of the chrome, whose controls are
addresses the user is holding whether or not they are looking at them. The banner
is packed to the right against a spacer, and the spacer decides who pays: a
control that grows moves itself and everything to its left, while everything to
its right keeps its place.

That edge is what makes the rule checkable rather than a thing to remember, and
the check is a reading of the rendered page. A stylesheet lint was the first
attempt, and that shape is wrong: the state a control shows is not reliably in a
selector. So two sweeps ask the page instead — a press, and the poll, the poll
being the half no gesture can reach. The poll asks two things of reserving that a
press never did. A control that comes and goes claims its room the first time it
appears and keeps that room for the page's life. And a row out of room takes room
from whatever will give it up, so which control gives is chosen rather than left
to the stylesheet: the status text and the chip, both of which sit left of
everything else on the row, where what they give up moves nothing.

A shift before the first paint is not jerk, since nothing was on screen to move,
and nearly every widget upgrade lands there — so hiding widgets behind
`:not(:defined)` would buy nothing, and it would cost every rendering of the
vocabulary that carries no script. The slow tail lands after that edge: a diagram
arrives at 163ms against a 52ms first paint and grows its element 93px. Still not
jerk, because aim needs a target and a moment to reach it. What would make it
jerk is that number growing — and the number is a fact about the vendored bundle
rather than about the widget, since mermaid's fetch completes 12ms *before*
first paint and the rest is parsing and drawing 2.75MB. Holding the first paint
until the page is done becoming itself would buy that tenth of a second at the
price of a permanently blank page whenever anything between the hide and the
reveal throws.

A change the user asked for may change the page: accepting a suggestion replaces
the words, and the paragraph below moves because the content did. What is
forbidden is movement they did not ask for, and movement that answers a small
gesture with a large rearrangement. Accepting once dropped 179 measured pixels
out of the middle of the shipped design page in the frame of the press, and the
row the reader had just pressed took itself off the page in that same frame. Both
halves are answered by rules above. The retired slot folds away over a fifth of a
second — measured before the decision, played after it — so what the log and a
second tab read is true from the first frame while the pixels catch up. And the
pressed control's own line holds still: it states the outcome where it stood
("✓ Accepted"), its paired control gives up its ink and not its room, and the
room the past tense needs was reserved from the decided word itself (`reserve`).

Resolving a thread is the same pair of rules in the panel, with one difference
deciding its shape: the control cannot stay, because a resolved thread belongs in
the disclosure at the foot of the list. What can be held is its place. The node
stays where it stood, says on the pressed control what was done to it, and folds
away over the same fifth of a second, with the disclosure taking the thread once
the fold is over. The fold belongs to the reconcile and not to the press, because
the log is what resolves a thread, and a resolve with no gesture behind it — a
second tab's, or the agent's — is the case that needs the motion more. What is
left standing must then not still be a thread: everything that walks the list
asks for `.lf-thread`, so renaming the node once takes it out of j/k, out of the
g addresses, out of r's press, and out of the panel's repaint in one stroke.

## Assume the browser it already assumes

The runtime requires ES modules, custom elements, `field-sizing`, `color-mix`,
`:has()`, `@scope`, anchor positioning, `caretPositionFromPoint`,
`Intl.Segmenter`, scroll anchoring, and the highlight registry.
Guarding one of those while assuming the rest buys nothing, and it reads as if
the others were checked. Add a feature guard only where there is a real fallback
to take, and cut a stale entry the moment nothing uses it.

Nothing in the code names scroll anchoring, so it is the one entry a reader can't
find by grepping — which is why it is worth spelling out. The panel reconciles
rather than rebuilds, so a message arriving above the fold grows the list over
the reader's head, and the browser's own anchoring is what holds the thread in
front of them still. That is why the test pins that thread's box and not the
scroll offset: the offset is the browser's to adjust. The list promises support,
not uniform rendering — `::highlight()` takes a narrow, deliberately layout-free
property set that engines implement unevenly, so a mark's tint carries its
meaning and the underline is a bonus.

## Everything the page says, the user can point at

The user selected a draft's text and commented on it, then tried the same on the
label naming that draft and got nothing back. The label was a `<strong>` in a row
marked `.lf-ui`, which the anchor pass skips. Its author had reached for that
class to mean "this is chrome"; what the class means is "these are the runtime's
words, not the page's".

Chrome is a look, not a permission, and the user has no such category in their
head — so the class cannot be the whole of anchoring's answer. Whose words these
are is declared where the words are written (`relabel`'s `says`, the same word
paper reads), and the anchor pass takes the nearest answer: the class where
nothing nearer speaks, the declaration where one does. So a label is the page's
even inside the chrome that holds it. A widget's own label, note, heading or
badge outside a control declares nothing at all — it wears `data-lf-gen` alone,
which keeps it out of the version diff while leaving it in reach of the anchor
pass, because those two questions were never the same question.

The rule has three edges, and each is a way the page says something the anchor
pass could not otherwise reach. The first is text a pseudo-element paints
(`content: attr(label)`): it lives in no text node, so a metric's headline number
could be read and not selected. `x-says` declares such an attribute, and one
runtime pass renders the words it names as real text — leaving that to each
widget is how it was forgotten the first time. A widget writes its own words only
where that pass can't reach — a chip row after a title (`lf-milestone`), a
heading doubling as a list's accessible name (`lf-column`) — and it writes them
at the edge of the page's own words; an option's risk chip once landed past the
pick mark that ends its row. The second edge is a fact stated in paint alone: a
task's status marker and the ring around a recommended option are sentences to
the eye and silence to a listener, so `done` sounded exactly like `blocked`.
`x-paints` names those attributes and one pass speaks them (`renderQuiet`), the
spoken word being the attribute's value or, for a flag, its own name. The third
edge is a fact carried by the element itself rather than by an attribute, which a
declaration cannot name, so the module says it: `lf-suggestion` writes `deletion`
and `insertion`, and retires them along with the marks when a decision settles.

Spoken words of that kind are clipped to nothing, out of the flow, and out of the
selection. They are a reading of the page's paint rather than of the page's
words, so the anchor pass must not offer them and the clipboard must not carry
them — and the clip does not keep them out of the clipboard on its own: a copied
task line once came away carrying `done`. Keeping both readings silent is what
keeps the file's reading and the page's in agreement without a fence.

A control that says one of those words is never a `<button>`, because Chrome
starts no pointer selection inside a form control, so the words would be on
screen and out of reach. `offer` builds every press as a span wearing
`role="button"`, and one listener, on the bubble, supplies the keys the UA would
have supplied — so a control that handles Enter itself has already said so by
preventing the default. What that costs is nothing these controls used: no forms,
and no `disabled`, which a widget's press therefore cannot have. What the
platform gives back has to be given back deliberately too: the press refuses a
drag exactly where nothing under it is said, since `user-select: none` on the
control takes the whole subtree with it.

A drag that ends on a control is that selection's mouseup, not a press, and
telling the two apart is `offer`'s job. Two guards around it each asked a
question next to the right one. Where the *pointer* stopped is not the question:
a tab's name runs to within a few pixels of its own padding, so a mouseup can
land on chrome while the selection is the page's. Whether the selection
*contains* the control is not the question either: a suggestion's row stands in
the column between the block holding the change and the next block, so a user who
read across the change and then reached for Accept pressed a control that did
nothing — and kept doing nothing, since a press that refuses a drag never
collapses the selection that is deadening it. The right question is whether this
click's own mouseup is where the selection stopped, and the selection's focus end
answers it. The button raised by that same drag goes missing the other way round:
a selection fills the lines it covers, so the button beside it lands in the
margin, where a change's row hangs. Floating chrome steps aside from whatever
stands on the page (`placeClear`), and it asks `data-lf-offer` to find those
things, so the stepping-aside holds for any control any widget hangs there.

Paper asks its own question and reads its own pair of markers. Print's question
is "is this a thing to work, and nothing else?" — nothing on paper can be
pressed. The class answers a different question, "these are the runtime's words".
Keying print on the class cost a printed decision the only words that stated it:
a pick mark is a control and a statement at once, so a printed group said which
option won only in a border colour that greyscale drops. So a control says which
kind it is where its label is written (`offer` for injected chrome, `relabel` for
the page speaking through a control), print hides the declaration rather than the
class, and the runtime's own layer hides as one thing at its `@scope` root. Each
marker gets one writer: `relabel` used to *clear* `offer`'s mark instead of
adding its own, so the two other passes that ask for the mark went blind on
exactly the controls this norm is about.

`render_version` reads the page in both media and reports what the second medium
drops — over the whole page, not per widget. What no pass can catch is a wrong
declaration, since a statement declared as an offer is exempt by construction.
That mistake is now made where the label is written, in front of whoever wrote
the word, rather than in a print rule three files away.

## A gesture a container takes on its whole box stops at what it holds

A `choose` group takes the pick on the whole option, and an option's case is
argued inside the option — a screenshot pair to flip, a disclosure to open, tabs
to walk. So reading the evidence used to cast a vote: a click on a shot's switch
chose the option and then cleared it again, and the log carried two decisions
nobody made. What stood in the code was an exemption for `<a>` — one item off a
list the platform had already closed.

`worksInside` is that question asked once: it finds the nearest thing between the
click and the container that has a use for the click, or nothing, in which case
the container itself is the aim. It reads two vocabularies, because a container
holds two kinds of thing. For widgets, the registry answers: `x-parent` says
which widgets a container is *made* of, and every other widget it holds is its
own world. For authored HTML, the platform defines the interactive elements. The
widget vocabulary is declared rather than listed, so a widget whose gesture lands
on its own words is covered by its registry entry — and inert widgets go in with
the rest, because a diagram is evidence the reader studies with the pointer on
it.

It fails closed, and that is the trade rather than an accident: a gesture the
container declines costs the reader one more click, while a gesture it takes
wrongly is a decision Claude has already read. The container's own apparatus is
the one thing no rule out here can tell from the rest — `lf-options`' pick mark
is a control and the aim at once — so a container excludes its own apparatus by
name, being the only thing that can.

## A shadow tree carries the page's words, and its ids

`x-shadow` made a widget's rendered text part of the page. The passage walk
crosses the shadow boundary (`textNodesUnder`), the capture asks
`getComposedRanges` for exactly the roots the registry declares, and `upFrom`,
`containsAcross` and `closestAcross` climb out of a tree the way `parentElement`
and `closest` climb inside one.

Element identity crosses the same boundary, and it did not follow at first.
`getElementById` searches the document tree alone, so an id inside a shadow tree
was invisible to every question the runtime asks by id: which element an anchor
names (`sectionOf`), what an action rests on (`restsOn`), which unit a fold
paints, which ask the n/p walk steps to. Each of those answers null and then
quietly does nothing — there is no error to find the gap by. `elementById`
searches the document first and the declared roots after it. Two consequences
follow rather than sitting beside it: a pass that clears its own marks before
repainting has to sweep everywhere it can now write (`pageQueryAll`), and
`elementFromPoint` retargets to the host — which is right where the question is
which *item* the pointer is aimed at, and wrong where the question is which of
several marks it touched. So `markAt` takes the tree's own answer and `aimedItem`
keeps the document's. Where the reader is *standing* is the third crossing:
`document.activeElement` retargets to the host, so a control a widget staged in a
tree answered as the widget itself. `focused` is the descent that the climb out
(`upFrom`) never had.

Which widgets the page holds stays the document's question. A widget staged
inside another widget's tree is a nesting `x-parent` does not model, and settling
that in a sweep would write the contract somewhere nobody would look for it. The
line is that an id names one element wherever it was staged, and what a page
*contains* is declared rather than discovered.

Holding that line costs a staged element its declarations. `renderSaid` and
`renderQuiet` ask the document which widgets it holds, so an `lf-event` staged
into a tree keeps its `x-says` and `x-paints` declarations and gets neither
rendered — and the failure is silence. Crossing into the trees is what the
paragraph above refuses, so the gate says it instead (`SILENT_WORDS`, in
`interact.py`), reading every open root and asking each declaration for its word.
The same finding covers a route that needs no shadow tree at all: both passes run
once, at the upgrade, so a module that rebuilds its body from a `settle()`
promise takes the rendered words out after they ran. The host is the other side,
and there a reading of the markup lies outright: both passes *do* find a host and
write into a light DOM the shadow root hides, so `querySelector` finds every word
the entry promised while the reader gets none of them. So the gate asks the
rendered page for both halves: `says()` for the words, and a box for the clipped
one.

## Three voices, because the page has three kinds of words

What the page *says* is prose the user reads closely and points at. What it
*labels* — an eyebrow, a column heading, a chip, a metric's caption — is
apparatus: the page pointing at its own content. What it *shows* is evidence:
code, diffs, trees, timestamps. Until the theme had more than one typeface,
nothing on screen carried that distinction, so "this is not the document" rested
on size and colour alone — the two things that go first, colour being what a
project theme overrides and size being what a dense page compresses.

So the page's own prose is set in a text serif, apparatus in the UI sans, small
and tracked, and evidence in mono. `.lf-ui` reads `--sans` rather than naming a
font stack, which makes the chrome's face a consequence of that one decision
instead of a second decision to keep in step. Which voice a widget's words take
is decided in one rule in `theme.css` that lists the apparatus: what counts as a
label is a judgement, and a judgement made in twenty rules is twenty chances to
answer it differently. The voice is a look and not a permission — a chip a widget
says is set in the sans because it reads as machinery, and it is still the page's
words, still something to select and quote.

The class answering for the face is not the same as the face arriving, and five
controls sat in that gap. Clearing the UA's form-control font is done by
inheriting (`font: inherit`), and inheriting finds the chrome's face only where a
`.lf-ui` float *encloses* the control. Where the control wears the class itself,
a clearing rule that outranked `.lf-ui` sent the inheritance walk straight past
it into the document, and the 💬 button came out in the page's serif at 17px.
Clearing a face and choosing one are different kinds of declaration, so the
clearing lives in a cascade layer (`lf-reset`, in the runtime's stylesheet),
which any unlayered choice outranks whatever its specificity. That makes the
collision unrepresentable rather than re-fixed per control: `.lf-ui` wins the
chrome face on any control wearing the class, and the one control whose face is
deliberately the document's — `lf-draft`'s editor — says so unlayered in the
theme, and wins that.

The serif is a system font stack, not a shipped file, and the reason is the copy.
`theme.css` is inlined whole into every `version export`, so a webfont would have
to arrive as a base64 blob — and referenced by URL instead, it falls back
silently in exactly the medium that has no server to ask. Charter and Iowan Old
Style ship on macOS, Georgia everywhere else; each is a screen serif with a large
x-height, which is what matters at 17px.

Changing any of this moves every reserved width. The reservations taken from the
words (`reserve`) re-measure themselves on the next load. The ones stated as
numbers are what the press sweep above answers for — a release late and a
platform late: it named the row form's pick column the day the suite first ran on
Linux, where DejaVu sets "your pick" 2px wider. So where there are words to
measure, measure them; where there are none, re-measure and restate the number
rather than deriving it.

## The page may break a word, so anything that must not come apart says so

The subject of these pages is code, so the prose carries paths, identifiers and
shas, and there is no column width at which one of them cannot be longer. Text
that cannot wrap does not stop at the edge of its box: it paints straight on over
whatever the layout put beside it, and every rect stays exactly where it should
be, so nothing about the boxes says a word about it. A twelve-character metric
value once ran 287px out of a 138px card. `overflow-wrap: break-word` on `body`
is the answer, and it is inherited, which makes it one decision rather than a
thing each new widget has to remember.

What it costs is that the browser will also break a run that was never meant to
come apart, so those runs say `white-space: nowrap`. `lf-tree` writes its name
and badges with no whitespace between them at all — the whole line is one word to
the breaker, which split a two-character badge down the middle.

A box clipped to nothing takes no part in any of this: it overflows on every word
and nothing comes of it, so a screen reader is handed the words from the document
rather than from the lines they fell into
(`test_a_commented_block_says_so_to_a_screen_reader`). What those clipped
characters did once reach was a reading of the page that took them for the page's
own words; that is answered where the question is asked — whose words are these,
in `COVERED_WORDS`.

## The inset a box shows is the inset it stated

A box that draws an inset shows it twice, above what it holds and below it, and
by default only one of the two is the stylesheet's to decide. A child's outer
margin collapses through its parent and is spent between blocks; where the parent
draws something at that edge, or holds a formatting context of its own, the
margin cannot get out, and it is painted as the parent's inset instead. So the
number in the rule is not the number on screen: an option card stating 16px came
out 16 above its title and 29 under its last paragraph. That stood on every
option card, every block change and every quotation the corpus has, and none of
those numbers was chosen — which is what makes it a defect rather than a taste.

`margin-trim` is the property for this, and Chrome has not got it (checked at
151), so the trim is written out in `theme.css`. The half worth reading twice is
who writes it. A list of the boxes that frame what they hold would be the closed
list the norms forbid: a layer's stylesheet can name only that layer's own boxes,
so a project's card would sit outside the list and the failure would be a silent
13px rather than an error. So a box says it itself, in the same declaration where
it draws the frame (`--lf-frame: 1`), and one style query finds every such box in
any layer. The layer reads the same declaration for the other question about the
same box: a wide widget inside a box that frames what it holds takes the box's
width rather than the page's room (`--lf-room`, theme.css). One word answers both
questions, so a project's card is covered either way. The box that
`leaf customize widget` scaffolds declares it, so a project's first widget is
right by construction.

The declaration goes where the frame is drawn, and that is not always a tag's own
rule. A task draws its rail in `lf-task > lf-task`, so it frames what it holds
only where it is nested; a code note's box is `.lf-code-note`, built by the
module and worn by no tag at all. Neither declared the frame, and a diagram
inside either stood ~245px over the column. What found them was the gate, put to
a page that stood an exhibit in each — going down the stylesheet tag by tag is
what had missed them.

Which boxes owe the declaration is a line the registry already draws. The
declaration is for the page's own flow, and an entry says whether flow can land
in a widget: `x-content: prose` or `items` admits it, `data` and `none` do not,
and `x-inline` stands a widget among the words around it, where there is no block
flow to frame. So a chip's tint declares nothing — a pill over a run of the
author's words is not a frame, and `x-inline` is the chip saying so — and the
boxes a data widget builds inside its own rendering (a highlighted code line, a
tree's guides, a shot's frame) are the module's own inset, spaced by the module
that draws them. What holds those honest is not a list but the gates: a drawn box
that reserves a child's margin reports as a trapped margin, and content across a
clip reports as a cut, so a missing declaration is caught on the page, where it
costs.

A declaration cannot hold room inside a box whose own sizing answers to its
content. A row-form option is a table hugging its words, and legacy table sizing
takes a drawing at its drawn width where every modern layout clamps a scroll
container. So with the frame declared all along, a diagram in a row option grew
the row past its joined group, and the group's clip cut the evidence off at the
border. A separated table also adds its padding outside the width it is given, so
every row on every joined group stood 30px past it with no diagram anywhere, the
clip spending the overhang out of the pick's word-room. Both failures were
invisible, because the gate excused whatever stood inside any container that took
its own overflow — and that excuse is worth only what the reader can tell from
the container. So a wide widget's box states that its width is the room's and
never its content's (`contain: inline-size`, theme.css); the row keeps its
reservation inside the width it states (`box-sizing: border-box`,
bundled/theme.css); and the gate asks what kind of container it is looking at
(`PAST_THE_COLUMN`): a scroller reaches what ran out on the side it scrolls
toward, a marked cut (`text-overflow`) says there is a rest, and a box that only
clips shows nothing past its edge — so a box drawn outside one is reported.

Which child is at the frame's edge is a question about the page's own blocks, and
`:first-child` is the DOM's answer to it. The two agree only where no module has
written anything: a pick mark is appended and positioned out of the flow, a quiet
word is clipped and inserted after the title, and each takes the trim off the
block the reader can actually see. So the trim asks for the first and last child
that is not generated, using the same pair of markers the anchor pass reads
(`GENERATED`), because it is the same question. What no selector reaches is a
child that hands its own children's margins on rather than reserving room itself:
a bare wrapper has a box and no margin of its own, so a grandchild's margin
collapses through it to the frame's edge unchanged. That is why `.facts` declares
the frame too — the answer is the same sentence, one level in. Reaching a level
further would trade a silent failure for a worse one, since the same selector
applied over a padded child closes up that box's own first line.

The check is a reading of the rendered page, because nothing else can be: the
trim is a style query, the frame is a declaration in whichever layer drew the
box, and a project overlays its own theme, so which rule won is a fact only the
browser holds. `version check --render` re-reads every drawn box and names any
box showing more inset than it declared (`TRAPPED_MARGINS`, in `interact.py`). It
excludes two things on purpose: a flex or grid container collapses no margin
anywhere, so a margin on an item at its edge is a placement; and an edge whose
box is generated is the layer's own paint.

## A widget's form follows its content, and each form states its own rules

`lf-options` renders as stacked cards or as a list of rows, and nothing declares
which. An option leading with a `<strong>` title argues its own case, so a group
holding one renders as full-width cards read down the page — with a `.facts` rail
when an option carries one — while a group whose options are bare labels is a
question about the page, and reads as a list. An attribute saying
`layout="rows"` would have been the same fact written twice, free to disagree
with the markup under it. There was a grid once, and its geometry moved with the
count: four options came out three across with the fourth orphaned under them. A
list holds one shape at three options or six.

What that costs is paid in the stylesheet, and paying it the cheap way doesn't
work. The first draft left every card rule general and added row overrides after
them — the same shape as a guard reading state another function wrote.
`lf-option[recommended]` is an attribute selector and
`lf-options:not(:has(…)) > lf-option` is not, so the card's accent ring outranked
the row's own look, and a row wore a ring it had no border to hang on. So the
rules that only make sense for one form say which form they are for — the reset
never fires, because there is nothing to reset — and a rule stays general only
where it is true of both forms.

"True of both" is a claim about what the declaration does in each form, and a
general selector is no evidence for it. `.lf-ref` set `margin-left: auto`, which
does nothing at all inside a card laid out in flow — and was the whole of the row
form's alignment while rows were flex. So a rule that read as the reference's
look was in fact the row's placement of its mark, and rows naming no block hung
each mark wherever their label happened to end. Flex was also the wrong layout to
be reasoning about: a row is a run of the author's prose with the module's
apparatus after it, and flex lays out items, so an inline `<code>` mid-label wore
the row's own gap on either side of it and lost the space written there. The
words need a box of their own while the markup stays the author's, which leaves
one candidate — the anonymous cell a table puts around them — and the layout is
then stated around that box rather than through it.

What the forms don't get to answer differently is whether the group can be
answered at all. Under `choose` the group draws as one control — a border with
its options as cells sharing hairlines — because being answerable is a fact about
the group and not about the layout, and the shape appearing at all is the offer.
The list form was exempted at first, on the reading that a bare-label row is a
quiet thing; what shipped was a question with no visible answer to "which of
these can I press". A form may decide how it looks; it may not decide whether it
says it takes an answer.

The module is where this stops. It sees the difference exactly once (`for`
renders a reference) and never asks which form it is in, because a second reading
of "am I rows?" in a second language would be two predicates to keep in step.

## A widget module takes the helper surface, and no more

A widget module gets the helper surface `leaf.js` exports, and no more until one
genuinely needs more.

Keys are the one place that surface grew rather than held. A widget used to
declare its keys three times: `keyHelp` for the reference, `keyHint` for the key
line, and its own `keydown` listener for the behaviour. The scoping was right and
the count was wrong — three objects for one binding is three chances to disagree,
and every widget took at least one. `lf-board`'s grip answered Space in both its
states while both of its lists said Enter.

So a widget calls `keys(el, title, rows)`: one declaration the register reads for
all three purposes. Focus scoping is still the DOM's — the scope holds while
focus is inside `el` — and what changed is that the word and the press are one
object. The register is now the only way a key enters the runtime, and that is
what lets a press be promised at all.

## The key line promises exactly one press

The key line renders what a key will do right now, and a promise about the next
press is only worth making if the press does that and nothing else. The failure
that named this norm: the draft editor's Escape called its own close without
consuming the event, so the runtime's ladder ran behind it — the edit closed
*and* the panel closed, two actions under a line that promised one.

That was a contract each control kept by hand: declare an Esc row, and remember
to `preventDefault`. Escape is a binding like any other now, so the rung that
runs is whichever scope in reach binds Escape first, and one dispatcher runs that
rung and no other. A control declaring its own Escape gets the press because its
scope is innermost, not because it consumed the event. The same shape covers the
rest of the keyboard: the line walks the scope stack outward and skips any row
sharing a binding with one already named, so two scopes cannot put two words over
one press.

What there is to walk is one list (`SCOPES`, with the element scopes spliced in
where they stand), and every reader takes its order from that list: the
dispatcher and the line walk it forwards, the reference backwards. Three lists
said it before, the third being the reference's own — and a mode left out of that
one was a mode the reference never names. Gathering the rows into sections is one
function (`merge`) for the same reason.

## The reader has to be standing somewhere

Escape unwinds what the chrome opened, and for a long time it stopped there: with
the composer, the menu, the board and the panel all closed, Escape had nothing to
say and the line said nothing. That reads as complete and isn't, because closing
the panel does not put the reader back on the page. It puts them on the control
that closed it — deliberately, since dropping focus on `<body>` loses a keyboard
reader's place in silence. The press that closed the panel is a keypress, so the
browser then draws a focus ring on a button that a reader who came by pointer
never chose, and `Comments` sits there looking selected.

Looking selected is the small half. Standing there, the reader's next Space is
that button's press rather than the page's scroll, so the panel they just
dismissed comes back and nothing says why. That is a page-level key silently
answered by a control — the failure the whole scope stack exists to prevent —
arriving through focus instead of through a binding. So the last rung leaves the
chrome (`panelsRung`), on the same key as every rung above it: a reader pressing
Escape until nothing happens ends up on the page. Losing a place is a fault only
when the reader did not ask for it, and the rung is the asking.

The rung lands focus on `body` rather than blurring, and the difference is a
browser fact worth having before writing either. `html` is `overflow: hidden`
here, so the document scrolls in `body`, the panel beside it is the other scroll
region, and Space scrolls whichever box the browser last saw the reader put
themselves in. A blur names no box. `document.activeElement` reads as `body`
either way, so from the page the two look identical — but after a blur, Space
goes on doing nothing until the next click in the document. Only the focus hands
the scroll back, which is what makes "back to the page" the whole sentence.

Which leaves the beginning of the page, where the same browser fact was doing the
same damage — and this section had already written that down, as a remark about
the rung's test pressing Space from a click in the document rather than from a
fresh load, "where there would have been nothing to hand back". That is not a
property of the test. A page nobody has clicked in is a page the browser has put
in no box, so Space, PageDown and the arrow keys scrolled nothing whatever until
the reader's first click landed somewhere in the document. `d` and `u` are the
runtime's own rows and worked from the first frame, which is what kept the bug
standing: the keys leaf names were live while the keys every reader already knows
were dead, and that reads as a page with no keyboard scrolling rather than as a
page with a bug.

So the runtime makes the rung's move as it evaluates
(`test_a_page_nobody_has_touched_scrolls_from_the_keyboard`). That is a placement
rather than a guard: the start block below runs a mermaid render later than
module evaluation, with the chrome clickable throughout, so making the move any
later would take a control back off a reader who had taken one in the meantime. A
sentence explaining why a test sets something up is a claim about the product,
and this one turned out to be a bug report.

## A scope names what it takes, and takes no more

The walk above shadows an outer row wherever a nearer one names the same binding,
and that covers every key the register runs. It cannot cover the keys the
*platform* runs where the reader is standing: a text box's letters have no row
here, and an outer row naming one of them would promise a press it will never
get. So a scope states those keys (`claims`), and everything a scope does not
claim goes on standing behind it.

The claim was a blanket first (`only: true`, the scope suspending the page
whole), and the blanket is the more natural thing to reach for, because for the
two scopes that wanted it the claim really is everything: an armed chord and the
open reference are modes, and a mode takes the keyboard. A text box is not a
mode. It takes the keys that put a character in it — most of the page's keys, so
the blanket read as right — and it has no use for the Escape, the Enter or the
send chord it was also taking. The bill arrived somewhere the blanket's author
never looked: `at` asked whether focus was in a form control, which is a
different question from whether a letter would become a keystroke, and every
`<input>` answered yes. A radio, a checkbox and a slider are handed no letter by
any platform, so a reader standing on a screenshot's before/after toggle had the
page's whole keyboard taken from them to protect typing that could not happen.
The key line went blank rather than wrong, and that reaches its author as "the
keyboard stopped working", with nothing to point at.

Two rules fall out, and the second is the general one. A predicate is named for
the question it answers, so `takesLetters` is the whole of what the typing scope
turns on, and there is nowhere left to put a wider predicate. And a scope that
has to hand back a key it took is a scope claiming the wrong set: claim what the
scope uses, not what stands near it, because the keys it over-claims are
invisible until a reader is standing on one.

That cuts the other way for a mode, which does take the keyboard. The versions
menu claimed nothing, so a reader mid-walk could press `l` and lose focus to the
leaves board — each press doing what it promises, somewhere the reader was not.
What a mode keeps open is the reference (`allButTheReference`): the two older
modes can blanket even that, because neither outlives a keystroke, whereas a menu
stands until it is dismissed and a swallowed `?` stays swallowed. And a scope is
*where focus is*, so the overlay hands focus back on close (`helpFrom`).

## A key on screen is a key that works

Every surface that names a key promises that the press does something now. One
table kept the words from drifting and did nothing to keep the surfaces from
drifting from each other: the key line asked `when` and the `?` overlay didn't,
so a page with no open thread offered `g 1–9` to reply to one. So whether a key
is live is declared once (`when`); `live` is the one question the dispatcher, the
line and the overlay all put to that declaration; and a label that names a range
is a function (`g ${digits()}`), so it counts the threads that are there rather
than promising nine. A liveness guard inside `run` is the tell, because it makes
the key refuse a press some surface is still advertising.

One `when` was still one answer to two questions, and `r` is where that showed.
Its sentence said "On a focused thread" while its liveness said "the page has
threads", so a reader who had focused nothing was offered a press that silently
no-opped. Picking one reading loses the other: the reference wants the
capability, since a reader learning the keyboard needs to know `r` resolves
before they have focused anything, while the line wants the press. So the scope
carries the capability and the row carries the press, and the two are named apart
in the code (`pageHas`, `readerIn`). Live means the capability exists, not that
every press moves something: a stepper at its end is a clamp on a live key, where
having no second version at all is a `when`.

A binding says which key it is in two halves, and only one half was ever read.
`answers` asks after `Mod`, `Alt` and `Shift` by name and takes every other
prefix to be absent — so `Ctrl+k` is not a binding that never fires: it is `k`,
firing on a bare press, while both surfaces spell the chip "Ctrl+k". That is the
one mistake a projection cannot catch, because every surface projects the
declaration faithfully and the declaration is what lies. So unknown modifiers are
refused where declarations enter (`checked`), against a list read off the matcher
rather than chosen beside it. The keys themselves are not checkable the same way:
an enumeration of what a keyboard has is a menu that goes stale.

Which keys a control answers is the platform's fact, so it is stated once and
read (`PRESS`), never spelled per row: five rows spelled `["Enter", " "]` by
hand, and the fifth spelled it short, naming `⏎` over a real `<button>` that
Space activates too — the key worked and the page under-promised it. The bound of
that fact is a link, which is why this is not "a control answers two keys": Enter
follows an `<a>` while Space scrolls the page, so the leaves board binds Enter
alone. A control the widget takes from the platform rather than building is the
other side of the same fact. `offer` writes a tab stop of its own making, and the
control scope matches that, so a `<summary>` or a checkbox a widget injects
matched nothing, and no surface named a press the reader could plainly make. The
widget declares such a control, since the keys differ between them, and the row
binds no `run`: the dispatcher skips a run-less row, so the press stays the
platform's.

A walk's keys name the direction, never the thing walked, and every walk here is
a pair a reader arrives already knowing: `j`/`k` is vim's list, `d`/`u` is less's
half page, `n`/`p` is next and previous through the things waiting on the reader.
The noun is the tempting name, and it strands the second half: the ask walk was
`a`, and there is no letter meaning "the previous ask", so whatever went beside
it was chosen rather than known. A borrowed pair costs nothing to learn, and it
leaves the noun's own letter free for the key that acts at large — which takes
the Shift as well: `Shift+a`, matched on the letter's lowercase with the modifier
asked for exactly, because caps lock writes an uppercase key out of an unshifted
press and a lowercase key out of a shifted press. The chip reads `A`, because
that is the key the reader presses. A move that merely sits beside a key is
spelled in the scope that key opens, where the letter is free again: `v` opens
the version chooser, and a second `v` inside it takes the newest version,
shadowing the page's `v` by standing nearer the reader.

The overlay renders at open and can go stale while it stands, and both directions
are acceptable: a row going dead under it can't be pressed, the overlay being
`only`, and a key going live under it is merely unlisted until the next open. A
widget's section holds this rule only if the module declares its scope at
*upgrade* (`connectedCallback`), never at module load — every x-upgrade module
loads on every page, present or not, so a top-level declaration is help for a
widget the page hasn't got.

## A key's word says what this press does

The two rules above make a press real and singular; this one is about the word
over it. `c` opens a box on the selection, or on the item a click raised the 💬
on, or on the page, and all three read "comment" — a word true of the key and
silent about the press. A reader who had just selected a paragraph and one who
had selected nothing were told the same thing about two different boxes.

The tell is a word wide enough to cover every branch of its own `run`:
"comment", "show or hide", "toggle". Such a word reads as accurate because it is
never wrong, and it is never wrong because it says nothing. Where the branch
turns on a fact about the page rather than about the key, the reader can already
see which branch they are in, so the word has to agree with them. A row's cells
are therefore computed where they are painted (`word`): `c` names what it would
comment on, `l` says whether the press shows or hides. Keeping the words true
costs a repaint wherever the state a word reads changes — and `paintLine`
coalesces to a frame, so painting from each writer costs nothing.

## One door to a place, and it is the one that shows it

`[` and `]` stepped versions older and newer — the menu's walk with the list
taken away, at a page load per press — so a reader holding `[` travelled back
through the work straight past the notes saying what each version changed. A
second key to a place the page already reaches is worth its binding only if it
carries what the door carries, and choosing a version is reading the list, so an
older/newer step fails that test.

`=` looked like the one key that passed the test. It named no version, and "what
changed since the last one I saw" is a question a reader has without opening
anything — so the key seemed to carry the whole door in one press. What it
actually compared against was the version before this one, and those are the same
thing only for a reader who was here for exactly that version. On a page that
ships a version whenever the work moves, a reader back after a week got marks
against v(n-1) and had no way to notice, because naming no version is also naming
nothing to check. The virtue and the defect were one property read twice. A key
that answers a question the reader cannot see it answering is worse than the walk
it saves — and the walk says which version it is standing on at every step.

Inside the menu, the row focus stands on *is* the comparison base, so the marks
follow the walk, and the row that ends the walk downward is the version being
read — comparable with nothing, so arriving there is the way off a comparison.
Where an open lands has to agree with that, and the agreement is what broke
quietly: opening on the version being read while a comparison stood elsewhere
moved the base on the reader's first arrow press, with the marks redrawn to match
and nothing saying so. So an open lands on the standing base, which puts the
reader at one end of the span the rail draws, with the way off at the other end.

## A walk starts where the reader is standing

A key that steps through the page answers "from here, what is next", and the
reader decides where "here" is. `d`/`u` measure from the scroll position, `j`/`k`
from the focused thread. The ask walk measured from an id of its own instead, and
so answered a question nobody asked — where its own last press had put them. A
reader who scrolled halfway down and pressed it for the first time was taken to
the top of the page, past everything they had just read.

Where the reader is, is read from what they have done, most direct first — focus,
then the selection, then the walk's own mark, then the block they are reading —
because each of those is a thing they did, and the later ones are older news. A
caret counts here even where a quote wouldn't: this reading asks where the reader
is, not what they meant to quote, which is why it is its own reading and not
`pageSelection`. The banner is the one place that is no place: its controls are
addresses held from wherever the reader stands, and the Asks button focuses
itself on the way to running the walk.

Then the walk steps over places in the document rather than over indices into its
own list (`askStep`), which is what makes a direction mean anything from a
standing start — and an ask holding the reader's place is the one they step off,
not the one they step to. The panel's threads are in the log's order, so `j`/`k`
have no page position to measure from, and the head of the list is the right
answer there. The tell is not "does this walk carry state" but "is where the
reader is a position in what this walk walks".

A version arriving is a navigation, and it takes the three most direct of those
readings with it: focus, the selection and the walk's mark are all paint on a
document that has just been replaced. Only the reading position rode across (view
continuity), so the reader kept their place on the page and lost their place in
the walk, and nothing said so. Standing on the third of four asks when the version
landed, they pressed `n` and were handed the third again — the block at the top of
the window is above an ask the walk had centred, so the walk measured from
somewhere they had already walked past. The mark travels in the same record as the
passage now: one place, both readings of it. Focus and the selection get no such
record and are not owed one. A focus put back would leave the reader's next Space
pressing a control rather than scrolling the page, which is what "the reader has
to be standing somewhere" is about, and the words a selection covered are not
promised to survive the revision.

## A widget's chrome outlives its handlers

`lf-shot` flips between two screenshots with a checkbox, a label over the image
driving it, and one `:has(:checked)` rule — where a dragged wipe divider would
have read more naturally. The reason is what a leaf page becomes once it leaves
the server: rendered DOM, script tags dropped. The upgrade has already run, so
everything a module built is still on the page, and nothing it bound is. A slider
would freeze wherever the last reader left it; a checkbox's state belongs to the
browser, and CSS can see it. What holds the state is a separate question from
which gesture drives it, and the first answer conflated the two: two radios under
the frame put the switch 83px off the change, so every alternation cost a look
away and a re-aim, on a widget whose whole worth is that the eye can hold still.
That cuts both ways, and the first draft got the other half wrong too: `checked`
set as a property leaves no attribute to serialize, so the standalone copy opened
with neither frame chosen. What a widget wants to survive goes in an attribute —
and the test that proves it strips every `<script>` before asking.

A copy is the third medium, and `version export` marks it as one: `.lf-copy` on
the root. The theme reads that as a guard rather than as a case. A widget writes
its affordance once, inside `@media screen { html:not(.lf-copy) { … } }`, and
everything outside that block is the page the markup already describes — which is
what a copy and paper both get, by never being handed the affordance rather than
by undoing it. Where a control's state is the browser's, the widget has no such
block and keeps working; where it needed a handler, withholding the block is what
stacks `lf-tabs`' panels. The theme's `@media print` is then only what paper
needs beyond a copy: paper can press nothing, so `lf-shot` stacks both frames
there while a copy still flips them, and paper cannot edit the document, so print
undoes the content-visibility that `version export` removes outright by dropping
`hidden="until-found"`.

Withholding the block covers what a widget draws, not what it built, and for a
long while nothing covered the second: a `choose` group's pick mark is a press
with a tab stop and a role on it, both of which outlived the handler that
answered them — so the first Tab into an exported decision page drew a keyboard
address for a key that answers nothing. So `version export` takes the control
out, which is the bargain paper had struck first (`@media print` on
`[data-lf-offer]:not([data-lf-said])`). The word a control says is kept where the
page speaks through it — a mark reading "chosen" states which option won — while
the control around that word goes, along with the box it hung in once nothing is
left inside; what survives is disarmed, the mark giving up its role and its tab
stop. All of that is read off the marker `offer` writes, so a widget nobody has
written yet is answered for — and off the tab stop rather than a role by name,
since a widget with an ARIA pattern to keep writes over `role="button"`, and
every press in `lf-tabs`' strip says `role="tab"`. The tab stop is also what
tells a copy from paper: a control the browser itself works has no tab stop of
the runtime's making, so `lf-shot`'s checkbox still flips its frames in a file
with no script behind it, where paper stacks both.

That leaves the theme less to key on than it looks. An affordance on a press that
gets stripped needs no qualifier at all, since no medium shows a grip with no
handler behind it. The role is worth keying on where the copy keeps the control —
a pick mark reading "chosen" is still on the page and must not go on offering a
hand. And an affordance for a gesture the **widget** takes goes in the guard,
there being nothing on those elements to strip. All of it is checked in one place
(`test_an_exported_example_stands_on_its_own`), which asks the copy what it still
offers rather than asking any widget what it drew.

How a guard is spelled follows from what it is doing. A guard that **grants** a
layout — the strip's `display: flex` over the `display: none` that withholds it —
has to outrank the rule it overrides, so it is written plainly. A guard that
**withholds an affordance** is the only statement its declarations get, so it
needs to outrank nothing, and it is written `:where(html:not(.lf-copy))`. The
plain form hands every rule inside it a class and an element it did not have, and
`lf-specimen` — which unkeys the choose group's hand cursor selector by
selector — was outranked by exactly that extra weight.

The guard is the medium's and not the widgets', so the runtime's own furniture
goes inside it too. The document scrolls body rather than the viewport because
the panel needs the room beside it, and the copy — which has no panel — carried
that whole arrangement out with it, showing as the column of every exported page
sitting 7.5px off the centre of a page it had all of. A Linux runner is what said
so, macOS drawing overlay scrollbars that reserve nothing. So a live-page rule
whose cost is a no-op on this machine goes under the guard at the moment it is
written: the platform that can see the cost is CI.

## The chrome's rules stay inside the chrome

Tags, attributes, nesting and ids are registry-driven, so the renderer, the
linter and the catalog can't drift apart. Class names have no registry entry;
their owner is the stylesheet's shape. The runtime's private rules sit in one
`@scope` block rooted at its own container, where no class a widget or a page
coins can match them — `lf-tabs` once marked itself `lf-live`, which is the
chrome's name for its visually-hidden live region, and every tabbed page clipped
to a pixel. What is styled at document level is the shared vocabulary, and only
that: `lf-ui`, `lf-btn`, `lf-pill` and `lf-address`, which a widget's controls
wear on purpose, plus the marks the runtime paints onto the page's own elements.
A global rule is a widening of that vocabulary, and the render suite pins the
list, so widening is a decision rather than a leak.

A word joins that vocabulary when one look is worn on both sides of the scope
line, which is a reason the container can't answer: the margin's press is the
runtime's 💬 and a suggestion's ✓ Accept sharing a line. Stated twice, each such
pair was a dozen declarations kept level by hand. So the shared half moves into
the vocabulary, and each wearer keeps only what is its own — where the thing sits
and when it shows. The split earns its keep the moment those differ: a reply box
has padding to hang a chip over, and an option had none, its group being a
control whose box is spent on its cells and clipped so their fills stop at its
rounded corners — so a chip on a cell's corner came out cut in half. The option reserves
a column for its digit and holds it whether or not one is showing; a shared rule
that had placed as well as dressed would have had to grow a case for that.

The container answers in script too, and the class had been answering for it.
Whether a widget's state has a version to contradict, and which block the
reader's eye rests on, are questions about *which document* an element is in; the
layer is one container, so those questions ask `.lf-chrome`. Asking `.lf-ui` was
the same substitution the anchoring norm above is about, and it worked for the
same reason — right up until a widget's own chrome, out on the page, wrapped
something of the page's. Where a marker does own the question, it still answers
it: the class for the composer's quote, the class on any injected element
carrying an id (`[id]:not(.lf-ui)`), and `data-lf-offer` for a thing to work.

## Never lose user text

Every draft persists on input: the general box, each thread's reply, the
selection composer, a widget conversation's first message and reply, and an
`lf-draft` edit. Only a successful send (or finding the same value already
authored) clears one; Escape and outside clicks hide rather than discard, and
Cancel is the only discard. A send owns its input until its response arrives, so
an earlier response can never clear or overtake newer text.

That ownership is the reader's, not the tab's. Each edit stores one active
generation, `{text, attempt, base}`; even the same words typed later mint a fresh
attempt. `base` names the durable shared generation the edit supersedes, or
absence. A chain of failed local writes keeps that base. It may therefore replace
its predecessor or the predecessor's settlement, but never an unrelated attempt
another tab durably wrote later. Without the provenance, an old failed-write
cache that missed storage news could become writable after its held POST and
tombstone the newer shared words.

Two tabs can press Send or Save on that generation before either sees the
other's result, and both may POST it. Every sendable draft context uses the same
protocol: the general and selection composers, question first messages and
replies, and `lf-draft` edits. Under the log's append lock, an exact retry
returns the event already accepted, the same attempt with a different payload
is refused, and a new attempt with identical words is a new event. This also
covers a sender that dies after the append.

The browser rechecks the attempt and exact untrimmed text immediately before
POST. A successful send replaces that exact active generation with
`{attempt, settled: true}`; it never removes the key.
Words or spaces typed while the request was in flight have a fresh attempt and
therefore survive its response. Send, Cancel, and log reconciliation all refresh
the shared generation before writing a tombstone, so a stale tab cannot settle a
newer durable edit.

Storage failures still cost recovery, never the live Send action. Every edit
updates a document cache and then attempts the single record write. A failed
write leaves a nondurable branch which news from its base cannot erase; unrelated
shared news retires it. A failed tombstone keeps the same lineage for the next
local edit, while a successful write makes that attempt the next base. A
successful write followed by a refused read remains sendable from the cache. A
readable shared generation still outranks a stale durable cache. The event log
outranks both: an accepted attempt is treated as settled even if stale storage
returns its active record after reload.

The store is the reader's (`localStorage`), because the ordinary end of a tab
here is being closed. Each round's reply hands the URL over again and the user
opens the page from the turn in front of them, so a page's tabs accumulate, and
the tab holding a half-written sentence is as likely to be shut as any other.
Tab-local storage carried a draft through reload, version navigation and a server
restart — and lost it to the one gesture nobody thinks of as destructive.

What that costs is that one draft now has a box in several places at once, and
the answer is that there is only one draft: every box is a view of the store,
mirrored live (`watchDraft`), so two tabs cannot end up holding two halves of one
thought. The index that mirroring needs — from a draft's context to the box
showing it — is the document's own listener list rather than a map of ours, and
that is what keeps it in step with the panel: a box that has left the document, a
reply box gone with its resolved thread, renders nothing and drops its view at
the next word it would have shown. Nothing tells the box that it went, because
the alternative is the panel keeping this design's index up to date on the side.

Active and settled are different records, and the difference is what says *why*
a draft cleared. A box the reader emptied stores an active generation whose text
is `""`; Send or Cancel stores a tombstone for that generation. The storage event
therefore tells an edit from a settlement without key removal — important because
`removeItem` can fail independently of `setItem` and otherwise resurrect sent
words on reload. No channel beside the store has to carry the reason. Which
settlement it was, nothing asks: both leave the same box for the other tab to
render, and what was sent arrives there through the log. What a settlement does
is each box's own business — a reply box and the general box empty themselves,
the composer on that anchor closes, a draft editor closes and lets replay paint
the body — while a mirrored *edit* moves nothing that was not already showing,
news arriving having no gesture behind it.

The composer's draft is keyed by the passage it is on. One key was enough while a
draft died with its tab; shared, one key is two tabs on two passages overwriting
each other. The record carries the anchor, the mode, and when it was last
touched, and the load reopens the most recent one.

## Working on it

`node --check` proves syntax, not bindings: a deleted `const` with six live
callers passes it. Run the suite.

It does not reliably prove syntax either, and the runtime's stylesheet is where
that bites. Those rules live in a template literal, so a backtick written inside
one of their comments closes the literal, and the CSS after it is parsed as code.
A pair of such backticks leaves the file's backticks balanced, which is enough
for `node --check` to pass a file Chrome refuses outright: the module never
loads, and every page is a bare document with no chrome on it.
`version check --render` is what says so, in one line.

The cost of that failure is worth knowing before you spend it. A runtime that
doesn't load doesn't fail the suite quickly — it makes every browser test wait
out its own timeout, at no CPU, so the run stops looking broken and starts
looking slow. Ninety minutes of that reads exactly like a loaded machine. If the
suite is somehow still going, render one example before assuming it is
contention.
