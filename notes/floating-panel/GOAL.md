# Goal: the floating Leaf panel

> **Status (2026-10-13): rebuilt and opt-in (TODO #28).** Checkpoints 1–3 landed
> on `main` behind the preference, off by default. The user disliked their look, so
> a second round redesigned it from a sketch they tried and configured (below, "The
> overhaul"). The rebuilt panel remains non-default while its remaining work is done.
>
> On 13 October the user retired the Codex reference: the panel is judged by Leaf's
> own aesthetic and the user's eye, not against the Codex app. The phone waits until
> the desktop design is firm, and gets no work before then.

## The overhaul

On 12 October the user reviewed the build as landed ("it doesn't seem elegant
generally, nor that consistent with our aesthetic. The menus are quite bad, very
large spacing. Things like 'layout' should not need to be selectable in a menu;
they should be embedded into the design"), then tried a sketch of a redesign and
chose its configuration: the page's own ground (Paper), 12px corners, the compact
width, a sans status line, the folded leaf in the window's corner, no folding on
scroll, a badge on the folded leaf for what waits plus a dot for news, and opened
views that close on a press on the page. The sketch's page is kept at
`~/.tmp/leaf.floating-panel/overhaul/source/playground.html`. What it changed, and
what the module header of `runtime/floating-panel.js` now states:

- **Three sizes, chosen by what the user does.** Folded (the leaf in the corner),
  the row, and a view opened above the row. The Layout row, the Minimal and Moderate
  displays and the Classic choice are gone from the panel; the preference keeps only
  where the panel was left (`rest`).
- **The field holds the status**, a thread's turn in a thread, and passing notices,
  which no longer stand at the window's head (`--lf-notice-seat: panel`).
- **Marks with counts in the row**: the question mark and the thread mark with a
  dot for news. Send stands in their place while the user types. (The pen that
  opened Annotations left the row on 13 October: "remove the pen, keep
  annotations".) Annotations leaves out Select element, which the user starts on
  the page by selecting words or pressing `s` ("I don't think we need the select
  mode").
- **The leaf's menu is a small menu** of one-line rows with each row's shortcut
  (the toolbar row contract's `shortcut`), the agent's state at its head. A row that
  opens a list of its own ends in a chevron. Navigate holds All pages and Search
  page; Page Map, Resume writing, Restore selection and Align current item at top
  keep their keys and leave the menu (the row group `keys`); where no keyboard is
  there to reach them, a finger finds them under Navigate.
- **Where the user is sits at a view's top edge**, with its filters, search,
  Resolve and Close beside it; the destination line and the thread-actions row went.
- **Motion moves no layout**: every change of size takes effect in one step and a
  separate surface layer follows by a clip, so the shift watch sees no tween.

The sketch's breathing leaf was left out: `skills/leaf/assets/AGENTS.md`,
"Motion", allows one continuous animation. On 13 October the user had the working
status carry that one sheen instead, asked for the resting status to read dimmer
than body text ("currently it's too 'normal text'"), and for the focused field's
placeholder to say where the words go.

Build an opt-in alternative to Leaf's chrome: one panel that hovers over the
bottom of the page, like the Codex app's floating chat panel, and replaces both
the banner and the bottom bar. Classic chrome stays the default. Build it on
current `main` in the Leaf repository, behind a user preference, and land it
there in steps, so the user can keep developing it from `main` without
changing what anyone else sees.

The bar is high. The user wants something excellent, and a previous attempt
failed on looks, not function: it worked, and it looked like a form. So treat
the appearance and feel below as requirements, on a par with the behavior.

Commit this file as `notes/floating-panel/GOAL.md` in your first commit. Re-read
it after every context compaction and before every review round. It is the
spec. Your memory of it is not.

## The design you are building

The user approved a prototype on 10 October: the **Leaf** arrangement of the
playground in commit `446de2cb2`, `notes/hierarchical-controls/`, in both its
Minimal and Moderate displays. Its appearance and behavior are the spec, apart
from the departures listed under "Intended departures". Its fixture data and
browser-local model are throwaway. The user called it "good; not perfect", so
improve on it where you can. Add each improvement to "Intended departures"
with its reason, and show it beside the prototype at the next checkpoint.

An unchanged export of that commit sits at
`~/.tmp/leaf/approved-prototype-446de2cb2/`, already built. Serve it live with:

```sh
env LEAF_PREVIEWS_ROOT=$HOME/.tmp/leaf/approved-prototype-446de2cb2/.tmp/previews \
  uv --directory $HOME/.tmp/leaf/approved-prototype-446de2cb2 run leaf-dev preview \
  --source .tmp/hierarchical-controls/playground.html --slot approved-leaf-446de2cb2
```

Choose **Leaf** in the tabs at the sample's top, and Minimal or Moderate beside
them. **Full view** fits the sample to the window. The prototype runs on its own
2026-10-10 runtime, which is why it is served from that tree rather than this one.


Reference images are in `~/.tmp/leaf/floating-controls-reference/`:

- `prototype/`: stills of the approved Leaf arrangement, Minimal and Moderate:
  at rest, menu open, Threads, Threads filtered to Unread, a thread with its
  reply field, Questions and writing, at 1440×900, plus rest and writing at
  390×844 touch. `scripts/stills.py` beside it regenerates them.
- `codex-floating-panel.png`: the Codex app's panel, the user's inspiration.
- `codex-app-study.md`: how Codex builds that panel. It covers the states, the
  motion, the geometry and dragging, read from the app's own source. Study it
  for the mechanics behind its polish. Don't copy its code.
- `questions-panel-liked.png`: the Questions panel as it was. The user liked
  it, because questions are answered right there in the panel.
- `rejected-production-composer.png`: what the previous attempt shipped. It is
  the failure to avoid (see "What went wrong last time").

## What the user asked for

These are in the user's own words, from the sessions that produced the
prototype. Each stays a requirement unless the user changes it.

**One panel replacing both bars.** "Turning this into something like the codex
floating panel … as part of removing the top and bottom bars." It needs a way to
reach everything the banner and bottom bar offer today: threads, Questions,
Versions, the agent's status, approval, page comments, modes, the page's other
controls, and keyboard shortcuts. These "pop out a panel above"; letting the
user move the panel, and pop it out downward, is welcome but optional.

**A resting box.** "The 'resting' mode would have a box that we could click in
to start a new page thread, and also in the box is the current status." Later:
"Have the most minimalist just be the comment box, maybe with only a questions
button + annotation." And after the last attempt dropped it: "what happened to
our resting comment box?" At rest the panel is one compact row. It holds the
leaf mark, a one-line comment field, the Questions count, the count of new
replies, and, on a desk, a door to annotating. "If it's not possible to glance
and see how many unread there are, then we need to resolve that." The empty
field shows the agent's status where a placeholder would say "Comment…": the
line the banner shows today, such as what the agent is working on or what it
wants back. "The 'Comment...' could instead show the Agent status that is
currently in the top bar." Clicking in it starts a page comment. Minimizing to
the mark alone is a deliberate gesture, and the panel then stays minimized
until the user restores it. The user may later want to switch the resting
form, as Codex lets you switch between compact, expanded and minimized and
choose where the panel sits. That isn't needed now, but keep the resting form
one setting rather than a fixed layout, so it can become a choice.

**Hierarchical, not a cockpit.** "They look like a cockpit — there are so many
symbols. Our interface should be hierarchical — extremely simple in its most
basic, and then extensible."

- "The leaf logo's color determine[s] the current state of the agent, no words,
  and then allow hover or clicking for more."
- "All the other things like modes appear in a small menu upon clicking the leaf
  logo … you gotta stop putting things on multiple lines." Each menu row is one
  line: a label and a terse value, such as `Threads 12 · 3 new` or `Versions v3`.
- "Fairly terse … numbers next to icons rather than saying whole words."
- A **Moderate** display adds keyboard shortcuts and position notices such as
  `Thread 3 of 12`. It is still much less than a side panel. The menu's Layout
  row offers Minimal, Moderate and Classic, and the choice persists (see "The
  preference").

**Threads and Questions inside the panel.** The user asked to "think about the
full lifecycle of threads: creating them, resolving them; being able to find
them."

- Threads: "a title (which is already an agent-generated summary!) and a status
  can be on a single line." The inventory has search and All / Unread / Drafts /
  Resolved filters. A thread opens inside the panel, where it can be answered,
  resolved and reopened.
- Questions are answered inline, as in the liked image: "there are things there
  we can actually answer inline (whereas threads need to be clicked into)."
- Threads anchored to a passage keep their markers and thread cards beside the
  text, as today. The panel's inventory lists every thread, anchored or not.

**One box for writing.** "If I click on Comment, we then shift to a different
box. Why can't we use that same box for the comment itself?" Within the panel,
the field you click in is the field you write in, both for a new page thread
and for a reply in a thread open in the panel. The panel says plainly who the
words go to. A thread card beside the text keeps its own reply field.

**Nothing moves under the pointer.** "If I click 'Unread', then there are fewer
messages, so the whole thing shrinks, including the thing I just clicked." A
control the user just pressed stays where it was. Inventories keep their size
when filtered.

**You always know where you are.** "It can be a bit difficult to know where we're
at." The prototype's header row (`‹ Threads   Rollout safety   Close`) is one
answer.

**Finesse.** "Compare to the nice animations in the Codex one; ours seems to lack
that finesse / polish." The panel grows and shrinks from a fixed edge, its
content cross-fades instead of jumping, and every state change reads as one
continuous movement. `codex-app-study.md` has the mechanics. Codex keeps one
element through its compact, expanded and minimized states, so each transition
resizes the same box. That design also meets the one-box requirement. Codex
animates with Motion, which has a framework-free build; weigh it against the
Web Animations API under root `AGENTS.md`'s "Use dependencies".

**Aesthetic.** "Minimal, elegant, transparent, hierarchical, 'new aesthetic',
John Pawson, Puritan, Work."

**Leave alone.** Don't touch the page's typography, other global CSS, or how
users select text to comment on it: "let's just focus on this specific feature."
Full-page dialogs were liked but are not this project.

## Intended departures from the prototype

Reviewers get this list, so that a departure on it is not reported as a
shortfall. Add each improvement you make, with its reason. Where an item here and
"The overhaul" above disagree, the overhaul holds; the items it replaced say so.

- **The resting row holds the comment field.** The Leaf arrangement rests as the
  mark with counts and opens the field on the first click. The user asked for
  the field at rest (see "A resting box"). The prototype's **Line** arrangement
  shows a resting field, with Questions and annotating beside it; use it as the
  reference for this row. The user chose Leaf over Line on 10 October and asked
  for the box back on 11 October. So everything except the resting row follows
  the Leaf arrangement: the mark, its menu, and how everything opens above the
  row.
- **The box resizes from its foot, in one step, and its surface follows.** The row
  stays put; the leaving view fades out (80 ms) before the arriving one fades in, and
  the surface layer follows the box's outline by a clip on the Codex panel's 300 ms
  `cubic-bezier(.23,1,.32,1)`. (The first build tweened the card's height; a layout
  tween's last frame landed outside CI's input window as a shift.)
- **The focused field shows no frame and no ground**: the line naming where the words
  go opens above it. A dark frame around the field was the previous attempt's "form"
  look.
- **While the user types, Send stands in the counts' place;** the counts come back
  when the caret leaves, and the line naming where the words go stays while the field
  holds words. (Replaces the first build's counts on the destination line.)
- **In a thread the destination line reads "Reply in {thread} · to {agent}",** since
  the thread's name now heads the view rather than standing just above the field.
- **A short thread reserves its "New reply · Show" slot,** so arriving news moves
  nothing.
- **Answers are the widget's own choices** (a multiple-choice ask shows its options and
  Done), recorded exactly as on the page; Questions has On you / On {agent} / Done.
- **Messages draw with Leaf's own reader** (the panel is a registered thread
  presentation), so asks, reactions and HTML replies work in the panel.
- **The menu carries the banner's inventory,** drawn from each contributor's declared
  row, less what the row and its views already hold (Threads, Questions, the page
  comment, approval); Navigate, Annotations and About open as views of their rows.
- **On a phone, a count at rest is its number beside an icon,** so the agent's status
  keeps the field ("numbers next to icons rather than saying whole words").
- **Passing notices are said in the empty field** (the overhaul); a walk's position
  still stands centred at the window's head.

## What went wrong last time

Commit `7e5083ab5` on the local branch `codex/floating-controls` is a 10-hour
Codex build of this feature. It works, but blind reviewers ranked every build
it produced below the prototype. It is not your starting point, and it sits
190+ commits behind `main`. Its commit message lists edge cases it handled,
such as draft retention, refused sends and resuming writing. Use it as a
checklist, and port none of its code without re-deriving the change on current
`main`.

Its visible failures, all present from its first hour:

- The composer became a stacked form. "Comment on the page" appeared twice,
  once as a label and again as the placeholder. A strip of shortcuts sat flush
  against the field with no gap.
- The Comment button disappeared the moment it was pressed.
- The leaf menu was the old control list, Versions sat three clicks deep, and
  Questions opened the old side panel. Thread rows kept a second summary line.
- Resume threw `TypeError: Cannot read properties of null (reading 'key')`.

These had two causes. The prototype dropped out of the run's goal at the first
step, so no build was ever compared with it. And the build reused the classic
composer and panels, whose structure produced the stacked form. Its reviewers
were given tasks, never the prototype, so they passed screenshots that showed
the defects.

## How to build it

**Same state and commands, new presentation.** The floating panel is another
presentation of what Leaf already owns. Threads, Questions, Tasks, status and
versions come from the application publication. The panel's controls come from
the banner toolbar's contributor inventory (`banner-toolbar.js`) and the command
registry behind the shortcut bar. A control that a package contributes appears
in the panel without the panel naming it.

The toolbar's contributors hand over their own DOM nodes, which can't become
one-line menu rows. Extend the contributor contract so that each contributor
also declares its label and a terse value, and render the rows from that. Don't
scrape the nodes. When an existing component's markup can't produce the spec's
appearance, as the classic composer can't, write the panel's own presentation.
You may refactor a shared component as long as classic chrome still renders and
behaves exactly as before. Never bend the design to fit a component. Root
`AGENTS.md`'s cross-runtime invariants still hold; read them before you design
the state flow.

**The preference.** The user turns the panel on once, and it applies to every
page they open on that origin. Store it in the user-scoped store that
`prepaint.js` reads before the page paints, as the Quick keyboard shortcuts
preference does, so a page never paints the classic bars and then swaps them
out. A URL parameter sets and stores it, on or off, which is how the user turns
the panel on from classic chrome; previews and tests set it in their own
browser contexts. The panel's Layout row can switch back to Classic. Classic
chrome gains no new control. With the preference off, every page looks and
behaves exactly as it does today.

**Samples.** An `lf-sample window` child follows the same preference, or takes
it from an attribute. That lets a review page show classic and floating side by
side.

## How to work

**The prototype stays beside you.** Before writing production code, serve the
prototype and use it in every state you will build. Add any state that
`prototype/` lacks, dark schemes included, by extending `scripts/stills.py`.
Every state you build gets compared side by side with the same state in the
prototype.

**Show the user early, then often.** Within about 90 minutes, hand the user a
Leaf review page. It shows the resting panel and the open menu on a real page,
next to the prototype. Then keep working without waiting, and take their
comments as they arrive. Give them a new checkpoint at each milestone:

- the resting panel, the leaf mark's status, and the menu;
- Threads, opening, answering and resolving a thread, and writing in the one box;
- Questions answered inline, Versions, approval, modes, and the Moderate display;
- motion and polish.

Budget about eight hours of work. If the user hasn't answered a checkpoint
after two more milestones, stop adding scope. Polish what they have seen, and
wait.

**Reviewers hold the reference.** Each review round sends fresh reviewer
subagents, running Opus or Fable, the following:

- this file, including "Intended departures";
- the prototype, live and in stills;
- your build.

Each reviewer uses the prototype and the build through the same journeys, at
1440×900 and 390×844 and normal zoom. Ask them where the build falls short of the
prototype or of a requirement above, quoting the requirement. A round passes
only when every shortfall it names is fixed, or you have put it to the user with
your reason for keeping it. A blind usability pass that never sees the reference
does not count as a review round.

**Spend the time where the user will look.** The user judges this by eye, at
ordinary window sizes. Edge cases nobody asked about, such as pinch zoom, unusual
viewports and exotic input, go to the open-items list unless they break the
requested experience. Fix the main path's look and feel first.

**Tests.** Cover each journey with the preference on: comment, reply, resolve
and reopen, filter, open a thread, answer a question, switch versions, minimize,
and restore. Check that the existing chrome tests pass with it off. Follow
`tests/AGENTS.md`'s "Run what the change needs", and don't run the whole suite
locally.

## Landing

When the user accepts a checkpoint, open a pull request that lands that work on
`main` behind the preference. Merging it is the user's call; merge only when
they tell you to. Do the same for each later checkpoint they accept, so their
development continues from `main`. The work is done when the user accepts the
build as a whole.
