# How far back `z` reaches

This note hands over an open design question: how far back the page's undo key
should reach, and whether Leaf should add redo or an undo panel. The design waits
on the user's pick in the playground beside this note (`playground.html`). Delete
the note once the chosen design lands and `events.md`'s Undo section states it.

## The question

The user asked this in a comment on the ui-sweep decision page, on its Ask
`ask-undo` ("How far back should z reach?"):

> Vim's persistent undo is very nice, would be great to avoid arbitrary limits.
> But OTOH, it's too easy to undo too much without realizing it atm. /dispatch --
> what are some things along the spectrum of effort vs closeness that we can
> build? we could have an "activity" panel that people can undo & redo over, for
> example. or we could just limit undo more... let's move this question there

So the goal has two parts that pull against each other: no arbitrary limit on how
far back undo reaches, as in Vim's persistent undo, and no undo that changes
something the user didn't realize it would.

## What main does today

`z` takes back the user's newest gesture, however old, or nothing (#1410). The
server's `browser_undo_candidates`
(`skills/leaf/scripts/leaf/served_state/document.py:30`) lists the user's
undoable gestures newest first and marks the head `newest` only when it is the
user's newest event that isn't bookkeeping, an undo, or already withdrawn. So a
reply sent since then ends the walk. `undoable()` in
`skills/leaf/assets/runtime/projection/commands.js:58` takes the head only when it
carries `newest`. A widget's own Undo control can still withdraw an older gesture
it names. #1407 puts the view back where a thread settlement moved it when that
settlement is undone, in the same tab only.

The remaining problem: on a page the user left three weeks ago, the first `z`
reopens a thread they resolved then, possibly below the fold, and the shortcut
bar and notice name only the gesture's kind (`undoSentence` and the per-kind words
in `commands.js`), not which thread or how old.

Undo is one-way. Nothing puts back what an undo took:

- An `undo` event names one gesture in `undoes`; nothing leaves the log
  (`skills/leaf/scripts/leaf/events.md`, "Undo").
- `taken_back` (`skills/leaf/scripts/leaf/events.py:6`) returns the flat set of
  every id any undo names, and every Python fold reads it.
- The append door's `UndoReading.error` (`events.py:71`) refuses an undo whose
  target isn't an unwithdrawn gesture of the user's own, so an undo can't name an
  undo. `UNDOABLE_KINDS` (`skills/leaf/scripts/leaf/schema.py:19`) is resolve,
  unresolve, action, and done; an unanswered reaction is also undoable.
- `events.md` states "An undo cannot itself be undone."

## The candidates

The playground lays these out, cheapest first, with a table, an operable
simulation, and a section per cost. A reach rule decides which gesture `z` may
take back; an add-on combines with any rule.

| Reach rule | How far back `z` reaches | Can `z` change what the user can't see? | Build |
| --- | --- | --- | --- |
| Main before #1410 | No limit, walking past sent replies | Yes | Shipped, then replaced |
| Newest only (main) | The newest gesture, however old | Yes | Shipped |
| Last 7 days | A fixed age | Yes, within the week | Small |
| This visit only | Since the page loaded; a tab open for weeks is one visit | Yes, for this visit's gestures out of view | Small |
| Show, then take | No limit | No: a target out of view, or one the agent has already picked up, is shown on the first press and taken on the second | Medium |
| Only what's in view | The edge of the viewport, so it moves as the user scrolls | No, though it still reaches an old gesture in view | Medium |

| Add-on | What it adds | Build |
| --- | --- | --- |
| Say what `z` takes | The bar and the notice name the gesture and its age | Small |
| Redo on `Z` | Puts back what an undo took, as Vim's Ctrl-R does, until the user's next change and while it would still show | Large |
| Changes panel | Every gesture the user made, newest first, each with Undo, and Redo once redo exists | Large |

The recommendation on the page, which the user has not yet answered: build
**Show, then take** with **Say what `z` takes** now, since it sets no limit and
never acts where the user isn't looking; build redo second; build the Changes
panel on top of both. The page's presets are "This visit only", "Vim's u and
Ctrl-R" (newest + name + redo), "Show, then take, with redo", and "Changes panel"
(show-then-take + name + redo + panel); each sets every control.

## What each design changes

- **Last 7 days.** `commands.js` compares the head's `ts` with the clock. The 7 is
  the arbitrary limit the user wants to avoid.
- **This visit only.** `commands.js` records the undo candidates present at the
  first reading, and `undoable()` refuses a head among them. Browser only.
- **Say what `z` takes.** `document.py` adds each candidate's words from
  `GestureWords` (`skills/leaf/scripts/leaf/gesture_words.py:86`, `says` at
  line 161). Today `served_state/browser.py` builds those words only for a page
  that shows history, so every state read would pay for them. `undoSentence` and
  the notice read them in place of the per-kind words.
- **Show, then take.** `document.py` marks each candidate the agent has picked up,
  from the delivery evidence the workflows already read. `commands.js` holds an
  armed state that the next gesture or key clears, and so does a scroll that takes
  the target out of view. The first press reveals the target the way an
  `lf-activity` row's link does: a thread opens, a widget scrolls into view and is
  outlined. It needs the words above too. A target needs the reveal when it is out
  of view or the agent has already picked it up; that second condition is what
  covers a tab left open for weeks, where "This visit" fails.
- **Only what's in view.** Every press reads each candidate's geometry, and a
  thread open in the panel counts as in view. `z` then means something different
  after every scroll.
- **Redo on `Z`.** See the next section.
- **Changes panel.** A third tray beside Asks and Leaves, with its glossary entry
  (`.claude/skills/developing-leaf/references/glossary.md`) and keyboard and touch
  routes. It is served the `history` reading on demand, which today reaches only a
  page placing `lf-activity`, filtered to the user's own gestures. That reading
  stops at 50 rows (`LIMIT` in `skills/leaf/scripts/leaf/history.py:28`), another
  arbitrary limit the panel would need to page past. Its Undo and Redo go through
  the one `withdraw` door.

## Redo in the event model

Redo is an `undo` naming the user's own standing `undo`. Nothing leaves the log
and no counter-event is invented, so the root `AGENTS.md` invariant ("An `undo`
event names the gesture withdrawn; it never deletes or invents a counter-event")
holds as written. `taken_back` changes so that an undo counts only while no
standing undo names it, which makes it a parity fold over the chain rather than a
flat set.

It has three costs:

1. **A restored gesture reads at its original log position.** Every fold reads
   effects in log order, so a restored gesture shows nothing once a later event on
   the same target stands. Any spoken reply, the agent's included, reopens a
   thread (`build_threads`, `events.py:203`), and a later pick on the same widget
   supersedes an earlier one. A redo that would paint nothing must be refused at
   the door, and the one general check is to fold the log with and without the
   redo and compare what the page shows. Re-sending the gesture as a new event
   avoids this but loses its identity: the agent reads a fresh pick, and history
   can't pair the undo with what it undid.
2. **Readers that follow `undoes` one level must follow the chain.** These are
   `GestureWords.says` (`gesture_words.py:161`), the coverage lookup in
   `served_state/browser.py:206`, `projection/presentation.js:157`, and the undo
   case in `delivery.py:159`.
3. **A redo restores an answer obligation.** An undo owes the agent no answer, but
   a redo brings back the restored gesture's obligation, which the stop hook
   enforces. The delivery must carry it, and the undo handling text in
   `skills/leaf/assets/registry.json` ("Treat the two as cancelling out", line
   374) needs a clause for a redo.

The rest of the redo change: `UndoReading.error` admits an undo naming the user's
own standing undo when folding without it changes the page; `document.py` serves a
redo list; `projection/model.js` lets a local redo override the server's reading
that the target is withdrawn, as a pending forward action does; `commands.js`
binds `Z`; `lf-activity.js`'s "undone" label
(`skills/leaf/packages/default/widgets/lf-activity.js:189`), `events.md`, and
`skills/leaf/references/event-batches.md` learn the redo.

Vim's undo tree is a different thing: `g-` and `g+` restore any past state,
superseded branches included, where this redo restores only what would still
show. The Changes panel offers selective undo instead, any standing gesture in any
order.

## The playground

`playground.html` is one Leaf page: the tables above, an Ask whose
`lf-playground` (submit label "Build this undo") holds the controls `reach`
(walk, newest, age, visit, confirm, here), `name`, `redo`, and `panel`, the
presets, and an `<undo-sim>` preview. Its output is the instruction the user
submits; `registerInstructionProvider` builds it from the controls and ends by
asking for the build on this branch, an updated `events.md` Undo section and
notice words, and a live preview of `review-a-plan`.

`<undo-sim>` is a page-local custom element: a simulated review page three weeks
in (an Ask, threads, and the user's newest move, resolving *Scope of the
migration* 21 days ago below the fold), its event log, and a toolbar (Reload the
page, Agent picks up your moves, A week passes, Start over). Its `fold(log)`
withdraws by parity newest first, so an undo naming an undo is a redo, and reads
each effect (choose, resolve, unresolve, reply) at its own log position, so a
later reply reopens its thread and makes Redo unavailable, as cost 1 says. The
simulation's reach rules, words, and notices are page-local; today's notice words
come from `commands.js`.

Serve it to the user with:

```sh
uv run leaf-dev preview --source notes/undo-reach/playground.html --slot undo-reach --user
```

Start the preview as a long-running command from the chat that will receive
feedback, then open the keyed URL it prints. Follow `/developing-leaf`,
“Preview a page”, for the host's feedback route and handoff. A restart builds a
fresh page and log; answer pending feedback before restarting.

`bin/leaf page check --render` on the page passes on main's runtime as of
e2fdf6ee2. It still advises against the `.sim-page` scroller; that scroller is the
simulated viewport the "What's in view" rule depends on, so it stays.

## Next steps

1. The user picks a reach rule and add-ons in the playground and presses "Build
   this undo". Their submitted instruction is the spec.
2. Merge main into `undo-reach` before building, and check whether main has moved
   the undo code above.
3. Build the pick in the runtime and Python owners named above, with the door's
   rule in `events.md`'s Undo section and the shortcut words in `commands.js`.
   Every new action gets a keyboard and a touch route (root `AGENTS.md`).
4. Hand the user a live `--user` preview of `review-a-plan` showing the new
   behavior, then delete this note and the playground.
