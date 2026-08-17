# The page in the browser

The norms the runtime, the widget modules and the theme are built to. Each was learned
by getting it wrong, and the failure is named because the rule without the failure is
just a preference. The four that bind this layer and the Python side at once — the log
outranking the document, one representation per concept, the file's reading never
claiming more than the page's, and the widget list never being closed — are in the
repo's own CLAUDE.md.

## One writer per thing

If two functions can write the same page state, they have to agree about who owns what
and who runs first — and that agreement lives nowhere the compiler or the tests can see
it. `paintAnchors` is the only thing that marks the page: threads' marks and the open
composer's draft mark are decided in one loop, so ownership is an `if` rather than a
protocol. Before that it was three functions, an ordering constraint stated only in a
comment, and a guard in one function reading a `data-` attribute the other wrote. Every
bug in that arrangement was the two drifting apart.

When you find yourself writing a guard that reads state another function wrote, the fix
is to merge the writers, not to add the guard.

## A gesture the log has not taken outranks everything the page has read

A widget paints the user's gesture before the log has taken it, so from that paint until
the poll that reads the action back, the page holds state no log it can read accounts
for. Replay leaves the widget alone for exactly that long. Every `applyAction` states the
widget whole, so an action from before the gesture — this tab's own previous one, most of
the time — hands the reader their older state back, and the gesture after that computes
from what it painted: a `multiple` group two picks in, repainted holding one, sends the
next toggle as a set the reader never chose. Applying each action exactly once is what
makes replay converge, and it says nothing about *when* — an action recorded before a
click can still be applied after it, which is what a loaded machine does to a page's own
polls.

All of that rests on the log holding the gestures in the order they were made, which the
page owes and the wire does not give: the server answers each request on a thread of its
own, so two sends in flight are appended in whichever order they arrive, and a pick
overtaken by the one after it is a decision the reader never made standing as their
state. So `post` sends one at a time — every event goes through that one door — and the
page having already painted is what makes the wait free. CI found it twice on the same
test, and neither this machine nor the dockerised Linux suite reproduced it in two dozen
tries, so the gate that holds it states the race rather than running for it: the first
send is stopped in the wire and the second click made while it is still there.

The hold is the layer's, in `sendAction`'s record of what is in flight, and no module
writes one. `lf-draft` did, privately (`#sending`), and was the only widget that had it:
right for drafts, and missing from every pick and every drag, because it was written at
the level of the widget in front of it rather than the level the problem is general at.
What a module still owes is the state the layer cannot see — an open editor is a live
gesture no send accounts for, so `applyAction` returns `false` for that.

## The page finishes twice, and the second time is the log's

`lf-upgraded` is the document's word for being done: widgets upgraded, the async ones
settled, the geometry and the drawn SVG final. The runtime writes it in the same breath
as it *starts* the first poll and never awaits that poll, so the stamp is no statement
about the log at all. `lf-applied` is the other half, written at the end of every replay
pass, and its presence is the page saying it has heard the log and rendered what the log
holds — which version is newest, what the reader has decided, what has been asked.

Anything meaning "the page is ready" wants both, and the gap between them is one fetch
wide, which is why it keeps being missed. `version export` missed it on a log holding a
single report and copied the page blank; the suite missed it at its own front door until a
loaded Linux runner dropped three keypresses into pages that had nothing yet to answer
them.

Nothing collapses the two, because they answer to different things. The document's stamp
owes nothing to the network — a page whose server never answers has still finished
becoming itself, and says so.

## A pinned version scopes the document, never the conversation

Two readings of the same log run on every page, and they take different windows of it on
purpose. Replay asks what the document held at this version, so it stops at `VNUM`: an
action recorded later is not yet part of the page the reader pinned, and a retraction
floor declared later cannot reach back to undo a decision this version still stands on.
The panel asks what has been said, so it takes the whole log
(`retractionFloors(Infinity)`, and `upto=None` from `interact.py`'s callers): a
conversation is not a property of a version, and a thread opened on v3 is the same thread
on v7.

The two windows disagree on screen, and the disagreement reads as a contradiction. A
reader pinned to v3, with a v5 note that `restated` the passage an accept rested on, sees
the thread reopened in the panel and the suggestion still painted accepted in the document
beside it. Both are right. The document is v3's, and at v3 the accept had not been taken
back; the thread is the conversation's, and the retraction is something that has been said.

The temptation is to pick one window and give it to both readings, which loses whichever
question the other was answering. Scope the panel, and a retraction is not news until the
reader steps forward to the version that declared it — so the older page keeps from them
the one thing they most need to hear, that a decision of theirs no longer stands. Unscope
replay, and an older version stops being a historical view: decisions made after it are
painted onto the markup it had before them, which is a page that never existed.

So a reading's window follows from the question it answers. What the document holds is
the version's; what has been said is the log's.

## Derive rendering from state; never read it back

`composerOpen`, `fabAnchor`, `diffBase` are the state. `style.display` is a rendering of
it. Nothing reads `style.display` to find out what is going on, because the rendering has
values the state doesn't: `display` is `""` before an element is first shown, which is
neither `"block"` nor `"none"`, and a guard testing for one of them ran on every mousedown
in the document and swallowed the click.

A setter owns the pair (`showComposer`, `showFab`) and states the whole outcome, so it can
be called from anywhere without first asking what the current state is. It is not free —
`showComposer` repaints — so a caller firing on every mousedown says what it means
(`if (composerOpen && !composerInput.value)`) rather than the setter guessing which of its
callers was the noisy one. That guess was wrong once already: an early return meant for the
mousedown also skipped the repaint when the composer reopened on a new passage, stranding
the mark on the old one.

## Paint; don't wrap

Marking text by wrapping it in an element splits text nodes, and a redraw that lands
between a mousedown and its mouseup swaps the node under the pointer — so the browser
dispatches no click at all, and a link inside a marked passage silently stops working.
The CSS custom highlight registry paints a `Range` and touches no nodes, so a redraw is
safe whenever it lands. That is what lets the same pass run from a mousedown handler and
from a poll.

What wrapping gave for free — knowing which thread the pointer is over, and the pointer
cursor — comes back as a geometric hit-test (`markAt`) over the pass's own record of what
it drew.

A painted range builds no accessibility node either, where a `<mark>` was a `mark` node,
and no ARIA relation puts one back: on a block that isn't focusable, NVDA ignores
`aria-describedby` in browse mode and reports none of the labelling attributes on a bare
`<p>` at all, VoiceOver reads it only on an interactive, image or landmark role, and
`aria-details` is supported unevenly and says only that details exist. What every screen
reader announces in every mode is text, so the same pass writes one hidden, unselectable
button per block that holds a mark, saying how many comments are on it. Focus reveals it
like a skip link; activating it enters the first matching thread, and j/k continues from
there. It names the block rather than the words, because naming the words is wrapping them
again.

State the cost anyway: a norm that hides what it costs gets applied where it shouldn't be.
Writing text into the author's document is a thing to do carefully rather than freely —
the line has to stay out of a selection, out of the next quote, out of what a widget reads
back as its own, and out of the mutation stream a screen reader rebuilds its buffer on.
Each of those is a rule the pass keeps rather than a property it gets for free.

## The runtime's line lands inside widgets

A comment can land anywhere the user can select, so the hidden line announcing one
lands inside widgets — and a widget reading its own light DOM back gets the runtime's
words along with the author's. `.lf-ui` is no help there: it keeps chrome out of
everything *the runtime* reads (the quote search, the capture, the version diff), and
`textContent` honours no markers.

Two rules, because there are two failures. The line goes on a text block or on the element
an anchor names, never on the inline run or body div between them: `lf-draft` seeds the
editor the user types into from its body div, and a line left there arrived in the
textarea and posted with their edit. And a widget asking what its own slot holds calls
`says`, not `textContent` — a block inside a widget is still a block, so the line lands in
it legitimately, and `lf-suggestion` labelled itself from the raw text and offered to
accept "Retry three times. 1 comment". The first rule keeps the line out of a widget's
content; the second is for where it belongs there anyway.

## The page holds still under the user's aim

The user works by pointing, and the gestures this product is made of are the long ones:
a double-click that opens an editor, a drag across three lines, a press on a row hanging
in the margin. Anything that moves between deciding where to point and arriving there is
aim thrown away. So a state change may repaint whatever it likes and must move nothing,
and where something has to move it moves as motion rather than as a jump, which is the
form the eye can follow to where the sentence went.

Two of the three ways a page moves are layout, and any geometry read catches them. An
element that resizes pushes its neighbours. A control that shows its state in metrics does
the same thing smaller — a selected tab set in 600 weight is a wider tab, so the strip
reshuffled under the pointer that had just pressed it — which is why the state a control
wears is paint (ink, rule, fill) and never weight or size. Metrics are shared with the
neighbours; paint is not.

The third moves nothing and is the one no measurement reaches. The draft's editor wore an
outset focus ring, so a double-click aimed at one word was answered by the frame around it
growing 2px on every side, corners rounding wider to match. Every rect was identical,
because in layout nothing had happened; what found it was a screenshot diff of the pixels
outside the box, which is the check to reach for whenever the fix is a border, a ring, or
a shadow. Emphasis paints inside the box it belongs to.

Said positively, room is reserved before it is needed rather than taken when it is: the
draft's control row exists in both its views, so opening the editor adds no height; a
`choose` group holds the pick mark's strip on every card, because the pick can land on any
of them; a control that will rewrite its own label holds the widest word it may say. Each
spends something on a case that may not arrive, and that is the trade — the alternative is
paid at the moment the user had something to say.

The rule has an edge, and it is the pressed control's own line. Below that line the page
is content and may move, since a tab showing another panel is what the press was for. On
it nothing may move, because it is where the next gesture is already aimed. That edge is
what makes the rule checkable rather than a thing to remember: the press sweep walks every
control on every shipped example, holds the ones beside it still, and reads the single
property a widget hasn't got a say in — that a thing can be pressed. It found two more the
day it was written. The sign-off button's "✓ Approved" is 12px narrower than "✓ Looks
good", so signing off slid the version chooser and the Comments button right; a row-form
pick mark took the room for the word it says at the moment it was pressed, dragging that
row's § reference 54px out from under the pointer.

News arriving has no gesture behind it, so there is no press to draw a line around and the
edge falls around the whole of the chrome instead: its controls are addresses the user
is holding whether or not they are looking at them, while the document below may still
change, because a fact arriving is what they are here to see. The banner takes all of it,
packed to the right against a spacer, and that decides who pays — a control that grows
moves itself and everything to its left, while everything to its right keeps its place. A
comment posted from the terminal took `Comments (9)` to `Comments (10)` and the version
chooser 6px with it; a second tab deciding the last pending suggestion took the ✓ Accept
all away and slid the New-version chip 148px right, under whoever was reaching for it.

Room is reserved from the words themselves wherever the words are enumerable: a control
that will rewrite its own label lists what it may say and `reserve` floors it at the
widest, measured in the control's own box and live face at load — so the reservation
re-measures itself when the type moves, instead of standing as a number somebody once
read out of a browser. Three numbers stood in the banner that way and all three quietly
stopped covering the day `--t-5` grew half a pixel. A number is stated only where there
is no widest word to measure: the pick column's dot room, which is a fact about a shape
and stays true when the type moves. The banner had the other kind — the version chooser
capped its width against notes nothing bounds, a fact about one font and free to stop
covering silently — and the way that number left was the control changing rather than the
number being re-measured: the chooser says the version and the menu says the note, so
there is no unbounded word on the row to hold a cap against. The two sweeps
are what check both kinds, and between them they work every one: a press, and the poll,
which is the half no gesture can reach. For the measured kind they check the words listed
are the words the writers write; for the stated kind they are the only thing standing
between the number and its going stale.

A stylesheet lint was the first attempt at that check, and the shape is wrong. It reads
the selector, and the state a control shows is not reliably in one: a class the module
adds, a label the runtime rewrites, a count that gains a digit. It caught one of the four
real cases, missed the ring that prompted all this, and objected to every deliberate hover
lift. What a control does to its neighbours is a fact about a rendered page, so the page is
where to ask.

The poll then asks two things of reserving that a press never did. A control that comes and
goes claims its room the first time it appears and keeps it for the rest of the page's
life: reserving from the start would hold room on every row for news that page will never
get, and reserving nothing is the movement, so this spends only where the alternative is a
control moving and only on the pages that got the news. And a row out of room takes it from
whatever will give, so which control that is has to be chosen rather than left to the
stylesheet: the chooser was the one that could, so it did, dropping under the width it
stated and putting every arrival back in play on any window narrow enough. What gives now
is the status text and the chip, both of them left of everything else on the row, where
what they give up moves nothing — and nothing else on the row can give, every control on
it now being floored at its own words.

The room a control takes is also a fact about the row it has to fit in, which the width
question above kept separate from and shouldn't have. The chooser was the widest thing on
the bar at 190px, spending it on a note it then ellipsized to about nine characters, and
that was 142px the row did not have: under about 990px the bar overflowed the window
outright, with no wrap and no scroll to reach what had gone past the edge. The reason it
could not simply be made narrow is the control it was — a `select`'s closed label is its
selected option's whole text, so the note was on the bar or it was nowhere. A press and a
menu separates the two questions, and the row fits a 900px window because of it.

A shift before the first paint is not jerk, since nothing was on screen to move, and nearly
every widget upgrade measured on the shipped examples lands there, ahead of its own page's
first paint — so hiding them behind `:not(:defined)` would buy nothing and cost every
rendering of the vocabulary that carries no script. The one that doesn't is where the
rule's lower edge is. A diagram arrives at 163ms against a 52ms first paint and grows its
element 93px, so the page does move with something on it; it is still not jerk, because aim
needs a target and a moment to reach it and at a tenth of a second the user has
neither. What would make it jerk is that number growing, and the number is a fact about the
vendored bundle rather than about the widget: mermaid's fetch completes 12ms *before* first
paint, and the 123ms after it is parsing and drawing 2.75MB, so nothing about when the load
is started reaches it.

Holding the first paint until the page is done becoming itself is the fix that suggests
itself, and the trade is bad. It buys that tenth of a second with a permanently blank page
whenever anything between the hide and the reveal throws or hangs — for a product whose
whole deliverable is the page, where the failure today is a readable page with broken
chrome. The one arrival that does have aim behind it needs none of it: a version switch is
a load the user asked for, and the reading position is restored after the same
`settling` the SVG lands in, so it is re-found in the page that grew rather than in the one
that was about to.

And a change the user asked for may change the page: accepting a suggestion replaces
the words, and the paragraph below moves because the content did. What is forbidden is
movement they did not ask for, and movement that answers a small gesture with a large
rearrangement.

Deciding a suggestion was both of those and cleared its own control besides. A block
change is a struck old paragraph stacked over a tinted new one, so accepting dropped 179
measured pixels out of the middle of the shipped design page in the frame of the press,
and everything below arrived somewhere else with no path between the two; and the row
the user had just pressed took itself off the page in that same frame, leaving a corner
toast as the only evidence anything had happened. Both halves are answered by rules
above rather than by new ones. The retired slot folds over a fifth of a second, which is
the form the eye can follow — measured before the decision, played after it, so what the
log and a second tab read is true from the first frame while the pixels catch up. And
the pressed control's own line holds still: the control states the outcome where it
stood ("✓ Accepted"), its pair gives up its ink and not its room, and the room the past
tense needs was reserved from the decided word itself as the row was built (`reserve`),
so the word can change without the box doing the same.

An acknowledgement is worth more than the room it costs. The rail is reserved for the
page's life once any change is on it, so a decided row is standing in space that was
never going to be reclaimed — and a user who scrolls back can see which changes they
took, which nothing on the page said before.

Resolving a thread was the same pair in the panel, and one difference decides its
shape: the control cannot stay. A resolved thread belongs in the disclosure at the
foot of the list, so the row the press was made on is leaving whatever else happens
and there is no rail to keep it standing in. What can be held is its place. The node
stays where it stood, says on the pressed control what was done to it, and folds over
the same fifth of a second, so the threads under it rise where the eye can follow
rather than arriving somewhere else in the frame of the press; the disclosure gets the
thread when the fold is over, which is what keeps one node per thread the whole way
through. The log is true from the first frame either way — Comments counts down,
Resolved counts up, and a second tab reads both.

The fold is the reconcile's and not the press's, because the log is what resolves a
thread. A second tab's resolve takes the same room out of the same list with no
gesture behind it, which is the case that needs the motion more: a reader who did
nothing has nothing to account for the gap. One writer covers both, and the pressed
path is the reconcile its own trip brought back.

What is left standing must then not still be a thread. Everything that walks the list
asks for `.lf-thread`, so renaming the node once takes it out of j/k, out of the g
addresses, out of r's press and out of the panel's repaint in a stroke — and it was
that last repaint the departing box turned out to need, since it went on offering
`g 1` while the thread that had just taken the address offered it too. A key on screen
is a key that works, so the address goes the frame the log settles the thread and the
box says "Reply" on its way out.

## Assume the browser it already assumes

The runtime requires ES modules, custom elements, `field-sizing`, `color-mix`, `:has()`,
`@scope`, anchor positioning, `caretPositionFromPoint`, `Intl.Segmenter`, `scrollend`,
scroll anchoring, and the highlight registry. Guarding one of those while assuming the rest
buys nothing and reads as if the others were checked. Add a feature guard only where there
is a real fallback to take.

Scroll anchoring is the one nothing in the code names, so it is the one a reader can't find
by grepping. The panel reconciles rather than rebuilds, so a message arriving above the fold
grows the list over the reader's head and the browser's own anchoring is what holds the
thread in front of them still. That is why the test pins that thread's box and not the
scroll offset: the offset is the browser's to adjust, and asking it to stay put would be
asserting the implementation rather than the fact the user cares about.

A stale entry is the same mistake as a stray guard, so cut one the moment nothing uses it.
And the list promises support, not uniform rendering: `::highlight()` takes a narrow,
deliberately layout-free property set that engines implement unevenly, so a mark's tint
carries its meaning and the underline is a bonus.

## Everything the page says, the user can point at

The user selected a draft's text and commented on it, then tried the same on the label
naming that draft and got nothing back. They read the asymmetry as a bug, and it is one: a
label saying which draft you are looking at is exactly the thing to hang "this one's
wrong" on. It was a `<strong>` in a row marked `.lf-ui`, which the anchor pass skips. Its
author reached for that class meaning "this is chrome". What it means is "these are the
runtime's words, not the page's".

Chrome is a look, not a permission, and the user has no such category — so the class
cannot be the whole of anchoring's answer. Whose words these are is declared where they
are written (`relabel`'s `says`, the same word paper reads), and the anchor pass takes the
nearest answer: the class where nothing nearer speaks, the declaration where one does, so
a label is the page's inside the chrome that holds it. Without that there is nowhere left
to put the words a control is the only place for.

`.lf-ui` still marks the runtime's own layer and the controls a widget injects — a
control is a thing to work rather than a thing to say, which is why its label is usually
the name of an action ("Save", "choose", the drag grip) — and still carries the face that
says "this is not the document". It just no longer decides. The line counting the comments
on a passage is the runtime's one word inside the page's own blocks: about the document
rather than of it, which is why it wears the class there and why the gate names it beside
the controls rather than as a heading someone hid. A widget's own label, note, heading or
badge outside a control declares nothing at all — `data-lf-gen` alone keeps it out of the
version diff and in reach of the anchor pass, and those two questions were never the same
question.

The rule has a second edge, and that one had every shipped widget: `content: attr(label)`
paints glyphs into no text node, so a metric's headline number, a column's heading and an
option's chip band could be read and not selected — no `.lf-ui` anywhere near them. Hence
`x-says` in the registry, and one runtime pass rendering what it names. Leaving it to each
widget would be leaving it to be forgotten, which is how it was forgotten the first time.
A widget writes its own only where the pass can't reach: one run of words at the element's
first or last child is all a pseudo-element could ever have been, so a chip row placed
after a title (`lf-milestone`) or a heading that doubles as a list's accessible name
(`lf-column`) is a module's job. Where the pass writes is the same question as what it
writes, and appending got it wrong: a pseudo-element's box is the element's first or last,
which on a page carrying no script is the edge of the element's own words and stops being
so the moment a module injects chrome. An option's risk chip landed past the pick mark
that ends its row — outside the apparatus, on a side the file's reading of that same
version has nothing on. The page's words go at the edge of the page's words. Same contract either way — generated, so the diff looks
away; no chrome marker, so the anchor pass doesn't — and `data-lf-said` beyond that only
where something else reads it: the theme keys the column heading's look on it, the chip
row has a class of its own.

The rule has a third edge, where the page states a fact in no words at all. A task's
status marker, a milestone's dot, an event's kind band, the ring around the recommended
option: each is a sentence to the eye and silence to whoever is listening, who gets every
word around the fact and never the fact — `done` sounded exactly like `blocked`, and the
page's own recommendation, which is most of what a decision page is for, reached the
reader with the least other way to find it not at all. Two widgets had answered it
privately and identically, lf-task and lf-milestone each hand-copying a clipped status
word, which is the shape that says the decision belongs in the registry rather than in a
module: `x-paints` names the attributes a widget renders in paint alone and one pass
speaks them (`renderQuiet`), so the two widgets here that have no module at all are
covered, and so is whichever the twelfth turns out to be. The word is the value, or a
flag attribute's own name, which is the whole of what its ring says. The runtime's own
restatement outline goes through the same door, being the same failure under a different
owner: a decision undone looks exactly like one never made, and the mark that exists to
state the difference stated it in ink only.

Where the fact is the element rather than one of its attributes, the declaration has
nothing to name and the module says it, the way a module writes the words a pseudo-element
could not have reached. A suggestion's two slots are told apart by a strike and two tints
and by nothing else, so a screen reader read the sentence twice and contradicted itself
— worst on an insert- or delete-only change, where the emphasis stands down and the tint
is the whole story, and a listener hears one perfectly ordinary sentence. `lf-suggestion`
writes `deletion` and `insertion`, and retires them with the marks when a decision
settles, because a settled slot is prose and there is no longer a change to announce.

Said, and therefore clipped to nothing, out of the flow, and out of the selection. This
is not the page's words but a reading of the page's paint, so the anchor pass must not
offer it — a quote resolved into a clipped box paints a mark nobody can see — and the
clipboard must not carry it, which the clip does not do on its own: a word standing among
the page's words is inside any selection drawn across them, so a copied task line came
away carrying `done` long after the runtime's own reading had learned to skip it. Both
readings being silent is what keeps the file's reading and the page's in agreement
without a fence.

A control that says one of those words is never a `<button>`. Chrome starts no pointer
selection inside a form control — not with `user-select: text`, and not on a span nested
inside one, which is what the plan this replaced assumed would work — so the words are on
screen and out of reach whatever they are marked. `offer` builds every press as a span wearing
`role="button"`, and one listener supplies the keys the UA would have — on the bubble, so
a control that handles Enter itself has already said so by preventing the default and the
runtime doesn't overrule the focused control. That is one place rather than each widget
remembering, and it costs nothing these controls used: no forms, and no `disabled`, which
a widget's press therefore cannot have. What the platform gives back has to be given back too — the press refuses a
drag exactly where nothing under it is said, since `user-select: none` on the control
takes the whole subtree with it and no descendant can win it back.

Then a drag that ends on a control is that selection's mouseup and not a press, which is
`offer`'s to know. Two guards around it each asked a question next to the right one and
paid differently. Where the *pointer* stopped is not it: a tab's name runs to within a few
pixels of its own padding, so the mouseup lands on chrome while the selection is the
page's, and the Comment button never came up. Whether the selection *contains* the control
is not it either, and that one cost more — containment is a fact about the DOM, and a
suggestion's row stands in the column between the block holding the change and the next
one, so a user who read across the change and then reached for Accept pressed a
control that did nothing, and kept doing nothing, since a press that refuses a drag never
collapses the selection deadening it. The question is whether this click's own mouseup is
where the selection stopped, and the selection's focus end is that answer.

The button raised by that same drag is the other way a press goes missing, and it needs no
wrong question to do it: a selection fills the lines it covers, so the button placed beside
it lands in the margin, on the line a change's row hangs. Nothing was deadened — the
user pressed the 💬 they could see and got a composer, because a press on it is not the
outside click that dismisses it. Floating chrome steps aside from what stands on the page
(`placeClear`), asked of `data-lf-offer` so it holds for any control any widget hangs.

Paper asks its own question and reads its own pair of markers. Print's question is "is
this a thing to work, and nothing else?", because nothing on paper can be pressed; the
class's answer is "these are the runtime's words". Keying print on the class cost a
printed decision the only words that stated it: a pick mark is a control and a statement
at once, and the settled row naming the chosen card is chrome too, so a printed group
said which option won only in a border colour greyscale drops, and a settled one said it
nowhere at all. So a control says which it is where its label is written — `offer`
marks the chrome a widget injects, `relabel` marks a label that turns out to be the page
speaking — print hides the declaration rather than the class, and the runtime's own layer
hides as one thing at its `@scope` root. No print rule anywhere has to remember a
control's label now: what `lf-tabs` still restores on paper is each panel's own authored
label, painted back on the panel because the strip that carried it is gone.

Each marker gets one writer, and the arrangement where one of them had two cost
something. `relabel` used to *clear* `offer`'s mark instead of adding its own, which made
that mark read "paper drops this" rather than "a widget injected this control" — so the
two other passes that ask it went blind on exactly the controls this norm is about. A
drag across a picked card's mark was a press again, and nothing but `lf-options`' own
guard on the card stood between the user selecting the word and losing their pick.

`render_version` reads the page in both media and reports what the second drops — the
whole page, not the widgets in it, because a printout losing a paragraph is no better
than losing a widget's word. A label written without saying which kind it is throws
where the widget upgrades, and the console error is a finding of that same gate. What no
pass can catch is a wrong answer, since a statement declared an offer is exempt by
construction; that mistake is now made where the label is written, in front of whoever
wrote the word, rather than in a print rule three files away that nobody thought to
write.

## A gesture a container takes on its whole box stops at what it holds

A `choose` group takes the pick on the whole option, and an option's case is argued
inside the option — a screenshot pair to flip, a disclosure to open, tabs to walk.
Reading the evidence then cast a vote. A click on a tab chose that option; one on a
shot's switch chose it and cleared it again, so the log carried two decisions nobody made
and the page showed neither of them. What stood there was an exemption for `<a>`, which is
one item off a list the platform had already closed. The shot has since made the whole
image its target, so what the container declines is now most of the option's area rather
than a control in the corner of it — the same rule, carrying far more.

`worksInside` is the question asked once: the nearest thing between the click and the
container that has a use for it, or nothing, where the container itself is the aim. Two
vocabularies, because a container holds two kinds of thing — a widget it merely contains
is the registry's answer (`x-parent` says which widgets a container is *made* of, and
everything else it holds is its own world), and authored HTML has the interactive
elements the platform defines. Declared rather than listed, so a widget whose gesture
lands on its own words rather than on chrome is covered by its entry; inert widgets go in
with the rest, because a diagram is evidence the reader studies with the pointer on it,
and which evidence happens to carry a control is nothing they can see.

It fails closed, and that is the trade rather than an accident of the implementation: a
pick is sent the moment it is made, so a gesture the container declines costs a reader
one more click on the words, and one it takes wrongly is a decision Claude has already
read. The container's own apparatus is the one thing no rule out here can tell from the
rest — `lf-options`' pick mark is a control and the aim at once — so a container excludes
its own by name, being the only thing that can.

## A shadow tree carries the page's words, and its ids

`x-shadow` made a widget's rendered text part of the page. The passage walk crosses the
boundary (`textNodesUnder`), the capture asks `getComposedRanges` for exactly the roots
the registry declares, and `upFrom`, `containsAcross` and `closestAcross` climb out of a
tree the way `parentElement` and `closest` climb inside one — so a reader selects a line
of a diff, comments on it, and the mark paints where they drew it.

Element identity is the same boundary, and it did not follow at first. `getElementById`
searches the document tree alone, so an id inside a shadow tree was invisible to every
question the runtime asks by id: which element an anchor names (`sectionOf`), what an
action rests on (`restsOn`), which unit a fold paints, which ask the `a` key steps to.
Each answers null and then quietly does nothing — the anchor stored, the mark never
painted, no error anywhere to find it by. `elementById` is the document first and the
declared roots after, and every one of those questions goes through it.

Two things follow from that rather than sit beside it. A pass that clears its own marks
before repainting has to sweep everywhere it can now write (`pageQueryAll`), or a mark on
a staged element outlives its reason. And `elementFromPoint` retargets to the host, which
is the right answer where the question is which *item* the pointer is aimed at — aiming
at a diff means the diff, whose rows are nothing to anchor on — and the wrong one where
it is which of several marks it touched, since a host contains them all. So `markAt`
takes the tree's own answer and `aimedItem` keeps the document's.

Where the reader is *standing* is the third crossing of the same kind, and the comment
over the scope walk promised it before anything did it. `document.activeElement`
retargets to the host, so a control a widget staged in a tree answered as the widget: no
scope of its own found, no control scope matched, and a press would have been aimed at
the host. The climb out was written (`upFrom`) and the descent in was not, so `focused`
is that half, and the register's questions go through it — the stack, the control and
typing scopes' `at`, the leader's Escape check. `lf-diff` declared its per-file
disclosure's keys and no surface said a word about them, which is the shape of this
failure: the declaration is right, the reader is somewhere the runtime cannot see, and
nothing errors.

Which widgets the page holds stays the document's question. A widget staged inside
another's tree is a nesting `x-parent` does not model, and settling it in a sweep would be
writing that contract where nobody would look for it. The line is that an id names one
element wherever it was staged, and what a page *contains* is declared rather than
discovered. Nothing shipped crosses it either way — `lf-diff` stages a tree built out of
parsed data and mints no ids — so the render suite stages one by hand, that move being the
whole of what the next such widget does differently.

Holding that line costs a staged element its declarations, and the two word passes owe
an account of it. `renderSaid` and `renderQuiet` ask the document which widgets it
holds, so an `lf-event` staged into a tree keeps `x-says` and `x-paints` and gets
neither — and the failure is silence: no error, no missing box, an attribute that
reaches nobody looking exactly like one with nothing to say. Crossing is what the
paragraph above refuses, since it would settle the nesting contract in a sweep. So the
gate says it instead (`SILENT_WORDS`, in `interact.py`), reading every open root and
asking each declaration for its word. The same finding covers the route that needs no
shadow tree: both passes run once at the upgrade, so a module that rebuilds its body
from a `settle()` promise takes the words out after them. Route the failure to whoever
can adjudicate it — here, the module's author, at handover.

The host is the other side of that, and it is where a reading of the markup lies outright.
Both passes *do* find a host — it is in the document — and write into a light DOM the
shadow root hides, so the markup holds every word the entry promised and the reader gets
none of them: `textContent` returns the span, `querySelector` finds it, and only the
rendered page knows. So the gate asks the rendered page for both — `says()` for the words
and a box for the clipped one, a span rendered nowhere having no rects. `says()` has an
edge worth knowing before reaching for it here: `textNodesUnder` substitutes a declared
root for a *child* and never for the element it was handed, so `says(host)` reads the
hidden light DOM. Nothing in the product passes a host, which is why the substitution has
never had to be uniform; anything that starts to must ask the root, as the gate does.

## Three voices, because the page has three kinds of words

What the page *says* is prose the user reads closely and points at. What it *labels* —
an eyebrow, a column heading, a chip, the headings across a table, a metric's caption —
is apparatus, the page pointing at its own content. What it *shows* is evidence: code, diffs, trees,
timestamps. The norms here already turn on that distinction; until the theme had more
than one face, nothing on screen carried it. Document and chrome were the same system
sans, so "this is not the document" rested on size and colour alone — and those are the
two things that go first, colour being what a project theme overrides and size what a
dense page compresses.

So the page's own prose is a text serif, apparatus is the UI sans small and tracked, and
evidence is mono. `.lf-ui` reads `--sans` rather than naming a stack, which makes the
chrome's face a consequence of that one decision instead of a second one to keep in step;
a diagram reads the same token, because mermaid paints its own labels and would otherwise
carry a palette and a face from nowhere. Which voice a widget's words take is decided in
one rule in `theme.css` listing the apparatus, and that is the point of it: what counts
as a label is a judgement, and a judgement made in twenty rules is twenty chances to
answer it differently. It is a look and not a permission — the line the norm directly
above draws. A chip a widget says is set in the sans because it reads as machinery, and is
still the page's words, still something to select and quote. Nothing built through
`offer` belongs in that rule: those wear `.lf-ui`, which already answers in the same
face, so listing one is inert and reads as a claim that the runtime's chrome is the page.

The class answering for the face is not the same as the face arriving, and five controls
sat in the gap. Clearing the UA's form-control font is asked for by inheriting
(`font: inherit`), and inheriting finds the chrome's face only where a `.lf-ui` float
*encloses* the control. Where the control wears the class itself, a clearing rule that
outranked `.lf-ui` sent the walk straight past it into the document: the 💬 button came
out in the page's serif at 17px, alone in the chrome and three points larger than
everything beside it; a picked option's mark and a settled group's disclosure said their
one word each in Charter.

Clearing a face and choosing one are different kinds of declaration, so the clearing
lives in a cascade layer (`lf-reset`, in the runtime's stylesheet), which any unlayered
choice outranks whatever its specificity. That makes the collision unrepresentable
rather than re-fixed per control: `.lf-ui` states the chrome face and wins it on any
control wearing the class, the one control whose face is deliberately the document's —
`lf-draft`'s editor, which must match the body it replaces — says so unlayered in the
theme and wins that, and the chrome's container still states the face once for anything
inside it that misses the class. A mark whose shapes straddle the line — `lf-option`'s
is a press wearing `.lf-ui` where the group takes picks and a bare span where it
doesn't — keeps its face in the one rule both shapes share, since only one of them has
the class to read from. The room the mark's word needs moves with that face — "your pick"
is 3px wider in the sans than in the serif — and the group takes it off its own mark at
load rather than holding a number, so the face and the reservation cannot come apart.

The serif is stacked, not shipped, and the reason is the copy. `theme.css` is inlined
whole into every `version export` and parsed by `version check` on every version, so a
webfont has to arrive as a base64 blob in both — and referenced by URL instead it falls
back silently in exactly the medium that has no server to ask. Charter and Iowan Old
Style ship on macOS, Georgia everywhere else; each is a screen serif with a large
x-height, which is what matters at 17px.

Changing any of this moves every reserved width. The ones taken from the words
(`reserve`) re-measure themselves on the next load; the ones stated as numbers are what
the press sweep above answers for — it named the sign-off button the day `--t-5` went
from 13.5px to 14px and 110px stopped covering "✓ Looks good", and the row form's pick
column the day the suite first ran on Linux, where DejaVu sets "your pick" 2px wider than
the face the 68px had been read in. A stated number is caught a release late and a
platform late, and the second one is only caught at all where there is a second platform
to run on. So where there are words to measure, measure them — the pick column takes its
own room now. Where there are none, re-measure and restate the number; don't derive it.

## The page may break a word, so anything that must not come apart says so

The subject here is code, so the prose carries paths, identifiers and shas, and there is no
column width at which one of them cannot be longer. Text that cannot wrap does not stop at
the edge of its box — it paints straight on over whatever the layout put beside it, and
every rect stays exactly where it should be, so nothing about the boxes says a word. A
twelve-character metric value ran 287px out of a 138px card. `overflow-wrap: break-word` on
`body` is the answer, and it is inherited, which is what makes it one decision rather than
a thing each new widget has to remember.

What it costs is that the browser will also break a run that was never meant to come apart,
so those say `white-space: nowrap`. `lf-tree` writes its name and badges with no whitespace
between them at all — a line is one word to the breaker, which split a two-character badge
down the middle and drew half the pill on each line.

A box clipped to nothing takes no part in this. One pixel wide, it overflows on every
word — the line announcing a passage's comments lays itself out a character to the row,
down the document and through the paragraphs under it — and nothing comes of that. The
clip holds, so nothing shows, and a reader is handed the words from the document rather
than from the lines they fell into, which is what the aria snapshot in
`test_a_commented_block_says_so_to_a_screen_reader` reads back. What those characters did
reach was a reading of the page that took them for the page's own words, and that is
answered where the question is asked — whose words are these, in `COVERED_WORDS`.

## The inset a box shows is the inset it stated

A box that draws an inset shows it twice, above what it holds and below it, and by default
only one of the two is the stylesheet's to decide. A child's outer margin collapses through
its parent and is spent between blocks; where the parent draws something at that edge, or
holds a formatting context of its own, the margin cannot get out and is painted as the
parent's inset instead. So the number in the rule is not the number on screen, and which of
the two a reader gets depends on what the author wrote inside: an option card stating 16px
came out 16 above its title and 29 under its last paragraph, and the same card ending in a
run of words came out even. A block change's tinted field stated 2px and showed 15 at each
end. It was on every option card, every variant, every block change and every quotation the
corpus has, and what finally surfaced it was a reader looking at a specimen's gutter running
sixteen pixels past the exhibit at both ends and asking why the marking was longer than the
thing it marked.

None of those numbers was chosen, which is what makes it a defect rather than a taste. An
inset that moves with the content is the box saying one thing and the page showing another,
and it fails silently in both directions — it renders perfectly, and it reads as a number
somebody picked.

`margin-trim` is the property for this and Chrome has not got it (checked at 151), so the
trim is written out in `theme.css`. The half worth reading twice is who writes it. A list of
the boxes that frame what they hold is the closed list the norms forbid: a layer's
stylesheet can name only that layer's own boxes, so a project's card is outside it and the
failure is a silent 13px rather than an error. A box says so itself instead, in the same
declaration where it draws the frame (`--lf-frame: 1`), and one style query finds every one
of them in any layer, the one nobody has written yet included. The box `leaf customize
widget` scaffolds says it, so a project's first widget is right by construction.

Which child is at that edge is a question about the page's own blocks, and `:first-child` is
the DOM's answer to it. The two agree only where no module has written anything. A pick mark
is appended and positioned out of the flow; a quiet word is clipped and inserted after the
title — and each takes the trim off the block the reader can actually see, in exactly the
widgets that build the most chrome. So the trim asks for the first and last child that is
not generated, by the same pair of markers the anchor pass reads (`GENERATED`), because it
is the same question: which of these words are the page's. That also dissolves the
specimen's two arrangements into one, its "quoted ·" note being a generated child on a live
page and a pseudo-element on a page carrying no script.

What no selector reaches is a child that hands its own children's margins on rather than
reserving room itself. A suggestion generates no box, so its slots are the flow's boxes and
the frame's rule lands on an element with nothing to trim; a bare wrapper has a box and no
margin of its own, so a grandchild's margin collapses through it to the frame's edge
unchanged. The rail is that second one, and it is why `.facts` declares the frame too: a
`dt`'s 6px between terms is the first term's as well, and it reached the option's padding
through a `dl` that had reserved nothing, leaving the rail's first line 6px below the case
docked beside it. The answer is the same sentence one level in — which is also why the
block slot asks for its room above rather than around itself.
Reaching a level further from the frame is the fix that suggests itself and trades a silent
failure for a worse one, since the same selector over a padded child closes up that box's
own first line. The gate reads the same level the trim does, so what it reports is what a
declaration can fix.

The check is a reading of the rendered page, because nothing else can be: the trim is a
style query, the frame is a declaration in whichever layer drew the box, and a project
overlays its own theme over leaf's, so which rule won is a fact only the browser holds.
`version check --render` re-reads every drawn box and names the one showing more than it
declared (`TRAPPED_MARGINS`, in `interact.py`), which is the same shape as the press sweep
replacing a stylesheet lint: what a rule does to a page is a fact about a rendered page. It
excludes two things on purpose. A flex or grid container collapses no margin anywhere, so a
margin on an item at its edge is a placement rather than room that could not get out — the
switch under a screenshot pair carries 3px of exactly that, the UA's own on a checkbox. And
an edge whose box is generated is the layer's own paint, stated in the same rule as the
frame.

## A widget's form follows its content, and each form states its own rules

`lf-options` renders as stacked cards or as a list of rows, and nothing declares which:
an option leading with a `<strong>` title argues its own case, so a group holding one is
full-width cards read down the page — with a `.facts` rail when an option carries one —
and a group whose options are bare labels is a question about the page and reads as a
list. An attribute saying `layout="rows"` would have been the same fact written twice,
free to disagree with the markup under it. There was a grid once, for groups whose every
option was terse, and its geometry moved with the count: four options came out three
across with the fourth orphaned under them, each cell as tall as the row's longest
argument. A list holds one shape at three options or six.

What that costs is paid in the stylesheet, and paying it the cheap way doesn't work. The
first draft left every card rule general and added row overrides after them, which is the
same shape as a guard reading state another function wrote: `lf-option[recommended]` is an
attribute selector and `lf-options:not(:has(…)) > lf-option` is not, so the card's accent
ring outranked the row's own look and a row wore a ring it had no border to hang on.
Chips pinned to a card's corners reached a row with no corners to pin to. So the rules
that only make sense for one form say which form — the reset never fires, because there is
nothing to reset — and a rule stays general only where it is true of both, which is most
of them.

"True of both" is a claim about what the declaration does in each form, and a general
selector is no evidence for it. `.lf-ref` set `margin-left: auto`, which is nothing at
all inside a card laid out in flow and was the whole of the row form's alignment while
rows were flex — so a rule that read as the reference's look was the row's placement of
its mark, and the marks' column rested on an attribute (`for`) the form does not require.
Rows naming no block hung each mark wherever their label happened to end.

Flex was the wrong layout to be reasoning about, and the auto margin only the first thing
it cost. A row is a run of the author's prose with the module's apparatus after it, and
flex lays out items: every stretch of the label became one, so an inline `<code>`
mid-label wore the row's own gap either side of it and lost the space that was written
there, since a flex item's edge whitespace is trimmed. The words get a box of their own,
and the markup stays the author's, which between them leave one candidate — the anonymous
cell a table puts around them. The layout is then stated around that box rather than
through it, and the fix to the mark's column falls out: the apparatus takes the cells
after it and claims none of the row's width.

What the forms don't get to answer differently is whether the group can be answered at
all. Under `choose` it draws as one control — a border with its options as cells sharing
hairlines — because that is a fact about the group and not about the layout, and the
shape appearing at all is the offer. The list form was exempted from it at first, on the
reading that a bare-label row is a quiet thing and a border around it would be shouting;
what shipped was a question with no visible answer to "which of these can I press",
since a row draws no border, no fill and no rule between it and the next. The only thing
that ever drew a row's own box was the hover wash, which arrives after the reader has
committed the pointer, and a reader asked why. A form may decide how it looks; it may
not decide whether it says it takes an answer.

The module is where this stops. It sees the difference exactly once (`for` renders a
reference) and never asks which form it is in, because a second reading of "am I rows?"
in a second language is two predicates to keep in step.

## A widget module takes the helper surface, and no more

A widget module gets the helper surface `leaf.js` exports, and no more until one
genuinely needs it.

Keys are the one place that surface grew rather than held. A widget used to declare its
keys three times — `keyHelp` for the reference, `keyHint` for the line, and its own
`keydown` listener for the behaviour — on the reasoning that focus-scoped keys belong to
the focused control and only the global table needed to feed a surface. The scoping was
right and the count was wrong: three objects for one binding is three chances to disagree,
and every widget took at least one. `lf-board`'s grip answered Space in both its states
while both its lists said Enter, and re-declared the line's rows by hand at three separate
state changes; `lf-options` declared one pair of arrows twice and spelled them two ways;
`lf-tabs`' rows named neither the wrap its handler does nor the four keys it tests.

So a widget calls `keys(el, title, rows)`, one declaration the register reads for all
three. Focus scoping is still the DOM's — the scope holds while focus is inside `el` — and
what changed is that the word and the press are one object. The register is now the only
way a key enters the runtime, which is what lets a press be promised at all.

## The key line promises exactly one press

The key line renders what a key will do right now, and a promise about the next press is
only worth making if the press does that and nothing else. The failure that named this:
the draft editor's Escape called its own close without consuming the event, so the
runtime's ladder ran behind it — the edit closed *and* the panel did, two actions under a
line that promised one.

That was a contract each control kept by hand: declare an Esc row, and remember to
`preventDefault`. Escape is a binding like any other now, so the rung is whichever scope
in reach binds it first and one dispatcher runs that one and no other. A control declaring
its own Escape gets the press because its scope is innermost rather than because it
consumed the event, and nothing runs behind it because nothing else was reached. The suite
still presses Escape on each declaring control and asserts exactly the declared effect —
the check is worth keeping; what went is the rule it was checking.

The same shape covers the rest of the keyboard. The line walks the stack outward and skips
a row sharing any binding with one already named, so two scopes cannot put two words over
one press: an armed `g` over an option's pick mark would otherwise have offered "reply to
thread" and "toggle the nth" side by side, and `lf-options` asked `leaderArmed()` privately
to stop half of it.

## A scope names what it takes, and takes no more

The walk above shadows an outer row wherever a nearer one names the binding, which covers
every key the register runs. It cannot cover the keys the *platform* runs where the reader
is standing — a text box's letters have no row here, and an outer row naming one would be
promising a press it will never get. So a scope states them (`claims`), and everything it
does not claim goes on standing behind it.

That was a blanket first (`only: true`, the scope suspending the page whole), and the
blanket is the more natural thing to reach for, because for the two scopes that wanted it
the claim really is everything: an armed chord and the open reference are modes, and a mode
takes the keyboard. A text box is not a mode. It takes the keys that put a character in
it — which is most of the page's, so the blanket read as right — and it has no use for the
Escape, the Enter or the send chord it was also taking. One of those was noticed and
rescued by hand, in a branch inside the box's own Escape row that reimplemented the panels'
rung and said that other scope's word on the line. Every other key it took — `c`, the
walks, the versions, the reference itself — nobody rescued, and they stayed swallowed.

The bill for that arrived somewhere the blanket's author never looked. `at` asked whether
focus was in a form control, which is a different question from whether a letter is a
keystroke, and every `<input>` answered yes. A radio, a checkbox and a slider are handed no
letter by any platform, so a reader standing on a screenshot's before/after toggle had the
page's whole keyboard taken from them — `c`, the walks, the versions, the reference — to
protect typing that could not happen. The line went blank rather than wrong, which is the
version of this that reaches its author as "the keyboard stopped working" with nothing to
point at.

Two rules fall out, and the second is the general one. A predicate is named for the
question it answers, so `takesLetters` is the whole of what the typing scope turns on and
there is nowhere left to put a wider one. And a scope that has to hand back a key it took
is a scope claiming the wrong set: reach for what it uses, not for what stands near it,
because the keys it over-claims are invisible until a reader is standing on one.

## A key on screen is a key that works

Every surface that names a key promises the press does something now. One table kept the
words from drifting and did nothing to keep the surfaces from drifting from each other:
the key line asked `when` and the `?` overlay didn't, so a page with no open thread offered
`g 1–9` to reply to one, and a first version offered the diff with nothing to diff. Two
shortcuts had no `when` at all — the diff's liveness sat inside its own `run` and the
version pair's inside `stepVersion`, where no surface could ask. So whether a key is live
is declared once (`when`), `live` is the one question the dispatcher, the line and the
overlay all put to it, and a label that names a range is a function (`g ${digits()}`) so it
counts the threads that are there rather than promising nine. A liveness guard inside `run`
is the tell, because it makes the key refuse a press some surface is still advertising.

One `when` was still one answer to two questions, and `r` is where that showed. Its
sentence said "On a focused thread" while its liveness said "the page has threads", so a
reader who had focused nothing was offered a press that silently no-opped — `d / u`'s bug
from the other side, a word and a binding disagreeing about where the key applies. The two
readings cannot be reconciled by picking one: the reference wants the capability, since a
reader learning the keyboard needs to know `r` resolves before they have focused anything,
and the line wants the press, since offering one that would refuse is the whole of what
this norm forbids. So the scope carries the capability and the row carries the press. The
reference lists a scope's rows wherever the page has that scope; the line filters by each
row's own liveness, which it may do because the reader standing in the scope can see which
state they are in. `Enter` and `r` moved into the thread's own scope on the strength of it,
and the page's line stopped naming them at all.

Live means the capability exists, not that every press moves. A stepper at its end — j on
the last thread, `]` on the newest version — is a clamp on a live key: the promise is
that there are threads or versions to walk, not that this edge press lands. What
`stepVersion` used to hold alone was the other kind, deadness — one version, or a viewed
version the server no longer lists, so nothing to step between at all — and that is what
`when` now owns; the clamp stays in the stepper.

A binding says which key it is in two halves, and only one of them was ever read. `answers`
asks after `Mod`, `Alt` and `Shift` by name and takes every other prefix to be absent, so
`Ctrl+k` is not a binding that never fires — it is `k`, firing on a bare press, while both
surfaces spell the chip "Ctrl+k" and the press the chip names does nothing. That is the one
mistake a projection cannot catch, because every surface projects the declaration faithfully
and the declaration is what lies. So the modifiers are refused where declarations enter
(`checked`), from a list read off the matcher rather than chosen beside it. The keys
themselves are not checkable the same way — `F7` and `Backspace` are as real as `Escape`,
and an enumeration of what a keyboard has is a menu that goes stale — but the modifiers are
closed by the code that implements them.

What a control answers is the platform's fact, so it is stated once and read, never spelled
per row. Five rows spelled `["Enter", " "]` by hand — the control scope, a card grip in each
of its two states, an option's pick mark, and the version menu's row — and the fifth spelled
it short, naming `⏎` over a real `<button>` that Space activates too. Nothing failed: the
key worked and the page under-promised it, which is this norm's inversion and just as much
a lie about the keyboard. `PRESS` is that fact now. The bound of it is a link, which is why
this is not "a control answers two keys": Enter follows an `<a>` and Space scrolls the page,
so the leaves board binds Enter alone and is right to. A shared fact that grew to cover the
link would have put Space on a row where the press scrolls the page out from under the
reader — the exact failure, reached from the other side.

A control the widget takes from the platform rather than building is the other side of
`PRESS` again. `offer` writes a tab stop of its own making and the control scope matches
one, so a `<summary>` or a checkbox a widget injects matched nothing and no surface named
the press the reader could plainly make — the register's own inversion, the same size as
the under-promise above and quieter, since the key works. The widget declares it, because
the keys are the platform's fact about *that* control and differ between them: a
`<summary>` is button-like and takes `PRESS`, while a checkbox takes Space alone, Enter
being a form's submit and a leaf page having no form. The row binds no `run` — the
dispatcher skips a run-less row, so the press stays the platform's, where binding one
would work a control the browser has already worked.

A key that acts at large takes the Shift as well as the letter, and the binding is where
that is said: `Shift+a`, matched on the letter's lowercase with the modifier asked for
exactly. Reading the uppercase key instead is wrong twice over, because caps lock writes
one out of an unshifted press — a reader with it on who reached for `a`, the walk through
the page's asks one at a time, got `A` under the first rule, which answers every one of
them and ends the matter, and matched nothing at all under the rule that fixed it, while
the line went on offering the walk. So the pair is a relation rather than two letters that
happened to be free: `a` steps the page's asks and `Shift+a` gives every blanket answer it
offers, the shifted half acting on the whole of what the lowercase one walks through. The
chip still reads `A`, because that is the key the reader presses; the binding reads
`Shift+a`, because that is what the dispatcher must ask for.

A move that merely sits beside a key, rather than acting on the whole of what it walks,
is spelled in the scope that key opens, where the letter is free again: `v` opens the
version chooser, and a second `v` inside it takes the newest version — the inner scope's,
so it shadows the page's `v` by standing nearer the reader rather than by consuming the
press first. The shifted twin is the tempting shape here and the wrong one, since a `V`
that opened the newest version would act on one of them rather than on all of them, and
Shift would then mean two things.

The overlay renders at open and can go stale while it stands, and the two directions cost
differently, both acceptably. A row going dead under it can't be pressed — the overlay is
`only`, so the page stands down beneath it — and a key going live under it is merely
unlisted until the next open, one press away; neither is a false promise. A widget's
section holds the rule only if the module declares its scope at *upgrade*
(`connectedCallback`), never at module load: every x-upgrade module loads on every page,
presence or not, so a top-level declaration is help for a widget the page hasn't got.
lf-options carried exactly that phantom section until the loader's contract was written
down here.

## A key's word says what this press does

The two rules above make a press real and singular; this one is about the word over it.
`c` opens a box on the selection, on the item a click raised the 💬 on, or on the page,
and all three read "comment" — a word true of the key and silent about the press. A
reader who had just selected a paragraph and one who had selected nothing were told the
same thing about two different boxes, and the reader who reported it had already seen the
difference on screen.

The tell is a word wide enough to cover every branch of its own `run`: "comment", "show
or hide", "toggle". Such a word reads as accurate because it is never wrong, and it is
never wrong because it says nothing. Where the branch is a fact about the page rather
than about the key — what is selected, what stands open — the reader can already see
which branch they are in, so the word has to agree with them. A row's cells are therefore
read where they are painted (`word`), the way a label naming a range already was, and
both surfaces get the same answer: `c` names what it would comment on, `o` says whether
the press shows or hides.

Passable for both is the argument to refuse. A word kept because it survives a change of
meaning is a word nobody reads, and a legend read that way is chrome the page is paying
screen for.

Keeping it true costs a repaint wherever the state a word reads changes, which is the
rule the runtime already follows for everything it renders: `showFab` writes the anchor
`c` names, so it paints the line, as `showOthers` does for the board. `paintLine`
coalesces to a frame, so painting from each writer costs nothing and saves reasoning
about which one is last.

## A widget's chrome outlives its handlers

`lf-shot` flips between two screenshots with a checkbox, a label over the image driving
it, and one `:has(:checked)` rule, where a dragged wipe divider would have read more
naturally. The reason is what a leaf page becomes once it leaves the server: rendered DOM,
script tags dropped. The upgrade has already run, so everything a module built is still on
the page — and nothing it bound is. A slider would freeze wherever the last reader left it.
A checkbox's state belongs to the browser, and CSS can see it.

Which gesture drives it is a separate question from what holds the state, and the first
answer conflated them. Two radios under the frame put the switch 83px off the change and
20px tall — a fiftieth of the image's area — so every alternation cost a look away and a
re-aim, on a widget whose whole worth is that the eye can hold still. The label over the
image is the target now; the checkbox stays under it for the keyboard, where it covers
nothing. Browser-owned state was never what made the control small.

That cuts both ways, and the first draft got the other half wrong: `checked` set as a
property leaves no attribute to serialize, so the standalone copy opened with neither
frame chosen and both of them stacked in the one cell. What a widget wants to survive
goes in an attribute, and the test that proves it strips every `<script>` before asking.

Print is the same question asked by a medium that has always been script-less, which is
why the answers coincide: paper drops the switch and stacks both frames, and the captions
naming them are `data-lf-gen` rather than `.lf-ui` — a frame's caption is the widget's own
word, like a column's heading, not a control's like "Save".

A copy is the third medium, and `version export` marks it as one: `.lf-copy` on the root.
The theme reads it as a guard rather than a case — a widget writes its affordance once,
inside `@media screen { html:not(.lf-copy) { … } }`, and everything outside that block is
the page the markup already describes, which is what a copy and paper both get by never
being handed the affordance rather than by undoing it. Where a control's state is the
browser's the widget has no such block and keeps working; where it needed a handler,
withholding the block is what stacks `lf-tabs`' panels and drops a strip that switches
nothing. The theme's `@media print` is then only what paper needs beyond a copy, and
paper needs two things: it can press nothing, so `lf-shot` stacks both frames there while
a copy still flips them, and it cannot edit the document, so it undoes the
content-visibility that `version export` removes outright by dropping
`hidden="until-found"` — a promise nothing in the file can keep, and one that takes the
collapsed element's layout with it, since the theme zeroes a hidden card's padding and
that padding is the room its chips are positioned into.

Withholding the block covers what a widget draws and not what it built, and for a long
while nothing covered the second: a `choose` group's pick mark is a press with a tab stop
and a role on it, and both outlived the handler that answered them. The first Tab into an
exported decision page landed on one, which drew the keyboard address for a key that
answers nothing — into a row whose 30px column for it is held on the live page alone, so
the digit came down over the option's own first word. Ten grips in a copied board opened a
grab cursor each; a suggestion offered ✓ Accept to a file with no way to accept anything.

So `version export` takes the control out, which is the bargain paper had struck first
(`@media print` on `[data-lf-offer]:not([data-lf-said])`). The word a control says is kept
where the page speaks through it — a mark reading "chosen" states which option won — and
the control around that word goes, along with the box it hung in once nothing is left in
it. A suggestion's row is nothing but its two controls, and standing empty it went on
claiming the rail the page reserves for it. What survives is disarmed: the mark gives up
its role and its tab stop.

Read off the marker `offer` writes, so a widget nobody has written yet is answered for,
and off the tab stop rather than a role by name — `offer` writes `role="button"` and a
widget with an ARIA pattern to keep writes over it, so every press in `lf-tabs`' strip says
`role="tab"` and a hunt for buttons walks past all of them. The tab stop is also what tells
a copy from paper. A control the browser works has no tab stop of the runtime's making, so
it keeps both the role that names it and its place on the page: `lf-shot`'s checkbox and
the label over its frames still flip them in a file with no script behind it, where paper,
which can press nothing either way, stacks both.

That leaves the theme less to key than it looks. An affordance on a press that goes needs
no qualifier at all — a grip's grab cursor stands plain, since no medium shows a grip with
no handler behind it. The role is worth keying on where the copy keeps the control: a pick
mark reading "chosen" is still on the page and must not go on offering a hand. An
affordance for a gesture the **widget** takes goes in the guard, there being nothing on
those elements to strip — a click lands anywhere in an option, and `choose` is the author's
word and stands in every copy of the page. All of it is checked in one place
(`test_an_exported_example_stands_on_its_own`), which asks the copy what it still offers
rather than asking any widget what it drew.

How a guard is spelled follows from what it is doing. A guard that **grants**
a layout — the strip's `display: flex` over the `display: none` that withholds it — has to
outrank the rule it overrides, so it is written plainly. A guard that **withholds an
affordance** is the only statement its declarations get, so it needs to outrank nothing and
is written `:where(html:not(.lf-copy))`, because the plain form hands every rule inside it a
class and an element it did not have. `lf-specimen` unkeys the choose group's hand and lift
selector by selector, and a guard carrying that extra weight outranked the lot — putting
the hand back on an exhibit quoted precisely so as not to offer one.

The guard is the medium's and not the widgets', so the runtime's own furniture goes
inside it too. The document scrolls body rather than the viewport because the panel needs
the room beside it, and the copy — which has no panel, and no session to change in —
carried the whole arrangement out with it: a stable gutter reserved against a growth that
can no longer happen, and scroll padding held under a banner the file hasn't got. It
showed as this norm's own subject in a place no widget could be blamed for: the column of
every exported page sitting 7.5px off the centre of a page it had all of. A Linux runner
is what said so, macOS drawing overlay scrollbars that reserve nothing — which is the
second half of it. A live-page rule whose cost is a no-op on this machine goes under the
guard when it is written, because the platform that can see the cost is CI.

## The chrome's rules stay inside the chrome

Tags, attributes, nesting, and ids are registry-driven, so the renderer, the linter,
and the catalog can't drift apart. Class names have no registry entry; their owner is
the stylesheet's shape. The runtime's private rules sit in one `@scope` block rooted
at its own container, where no class a widget or a page coins can match them —
`lf-tabs` once marked itself `lf-live`, the chrome's name for its visually-hidden
live region, and every tabbed page clipped to a pixel. What is styled at document
level is the shared vocabulary, and only that: `lf-ui`, `lf-btn`, `lf-pill` and
`lf-address`, which a widget's controls wear on purpose, and the marks the runtime
paints onto the page's own elements. A global rule is a widening of that vocabulary;
the render suite pins the list so widening is a decision rather than a leak.

A word joins it when one look is worn on both sides of the scope line, which is a
reason the container can't answer: the margin's press is the runtime's 💬 and a
suggestion's ✓ Accept sharing a line, and the keyboard address is a thread's reply
box and an option's corner saying the same digit. Stated twice, each pair was a dozen
declarations kept level by hand — so the shared half moves here and each wearer keeps
only what is its own.

What a wearer keeps is where the thing sits and when it shows, and the split earns its
keep the moment those differ. A reply box has padding to hang a chip over and an option
had none: its group is a control whose box is spent on its cells, and it clips itself so
their hairlines stop at its edge, so a chip on a cell's corner came out cut in half
everywhere it ever appeared. Every fix that borrowed room from somewhere else showed —
the page margin beside the group is the next cell's words as soon as the group has two
columns — so the option reserves a column for its digit and holds it whether or not one
is showing, which is the same answer the pick mark's room already is. A shared rule that
had placed as well as dressed would have had to grow a case for that; dressing only, it
didn't notice.

The container answers in script too, and the class had been answering for it. Whether
a widget's state has a version to contradict, and which block the reader's eye rests
on, are questions about *which document* an element is in; the layer is one container,
so they ask `.lf-chrome`. Asking `.lf-ui` was the same substitution the anchoring norm
above is about, and it worked for the same reason — the layer wears that face — right
up until a widget's own chrome, out on the page, wraps something of the page's. Where a
marker does own the question it still answers it: the class for the composer's quote,
the class on any injected element carrying an id (`[id]:not(.lf-ui)`), and `data-lf-offer` for a
thing to work, which is what a draft's double-click asks before it swallows the
browser's word selection.

## Never lose user text

Every draft persists to tab-local `sessionStorage` on input; absence and an empty value
are different, because deleting all of a `lf-draft` is still an edit. It survives reload
and version navigation, while another tab's successful send or Cancel cannot erase it;
submitted actions converge through the log instead. Only a successful send (or finding
the same value already authored) clears one. A send owns that input until its response,
so an earlier response can never clear or overtake newer text. Escape and outside clicks
hide, they don't discard. Cancel is the only discard.

## Working on it

`node --check` proves syntax, not bindings: a deleted `const` with six live callers
passes it. Run the suite.

It does not reliably prove syntax either, and the runtime's stylesheet is where that
bites. Those rules live in a template literal, so a backtick written inside one of
their comments — quoting a token name the way prose does everywhere else in this
repo — closes the literal, and the CSS after it is parsed as code. A pair of them
leaves the file's backticks balanced, which is enough for `node --check` to pass a
file Chrome refuses outright: the module never loads, and every page is a bare
document with no chrome on it. `version check --render` is what says so, in one line.

Its cost is worth knowing before you spend it. A runtime that doesn't load doesn't
fail the suite quickly — it makes every browser test wait out its own timeout, at no
CPU, so the run stops looking broken and starts looking slow. Ninety minutes of that
reads exactly like a loaded machine. If the suite is somehow still going, render one
example before assuming it is contention.
