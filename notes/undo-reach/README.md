# How far back `z` reaches

This note hands over the build of the page's undo key's reach, which the user
chose on 21 October 2026 on the TODO decisions page: **Show, then take** with
**Say what `z` takes** (both described below). Redo and a Changes panel stay
candidates for later. Delete the note once the chosen design lands and
`events.md`'s Undo section states it.

## The question

The user asked this in a comment on the ui-sweep decision page, on its `lf-ask`
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
(`skills/leaf/scripts/leaf/served_state/document.py`) lists the user's
undoable gestures newest first and marks the head `newest` only when it is the
user's newest event that isn't bookkeeping, an undo, or already withdrawn. So a
reply sent since then ends the walk. `undoable()` in
`skills/leaf/assets/runtime/undo.js` takes the head only when it
carries `newest`. A widget's own Undo control can still withdraw an older gesture
it names. #1407 puts the view back where a thread settlement moved it when that
settlement is undone, in the same tab only.

The remaining problem: on a page the user left three weeks ago, the first `z`
reopens a thread they resolved then, possibly below the fold, and the command
reference and notice name only the gesture's kind (`undoSentence` and the per-kind words
in `undo.js`), not which thread or how old. Since #3271 a widget's gesture is announced
by the words its acknowledgement used ("Undid: Chose “Fast” — sent"), but only in the
tab that made it; after a reload the undo is announced by its kind again, and no undo
says its age.

Undo is one-way. Nothing puts back what an undo took:

- An `undo` event names one gesture in `undoes`; nothing leaves the log
  (`skills/leaf/scripts/leaf/events.md`, "Undo").
- `taken_back` (`skills/leaf/scripts/leaf/events.py`) returns the flat set of
  every id any undo names, and every Python fold reads it.
- The append door's `UndoReading.error` (`events.py`) refuses an undo whose
  target isn't an unwithdrawn gesture of the user's own, so an undo can't name an
  undo. The kinds `$events.kinds` marks `undoable`
  (`skills/leaf/assets/registry.json`) are resolve, unresolve, action, done, and
  todo_end; an unanswered reaction is also undoable.
- `events.md` states "An undo cannot itself be undone."

## The candidates

A reach rule decides which gesture `z` may take back; an add-on combines with any
rule. The playground that compared them operably is in history at `29966712b`
(`notes/undo-reach/playground.html`).

| Reach rule          | How far back `z` reaches                                  | Can `z` change what the user can't see?                                                                               | Build                  |
| ------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| Main before #1410   | No limit, walking past sent replies                       | Yes                                                                                                                   | Shipped, then replaced |
| Newest only (main)  | The newest gesture, however old                           | Yes                                                                                                                   | Shipped                |
| Last 7 days         | A fixed age                                               | Yes, within the week                                                                                                  | Small                  |
| This visit only     | Since the page loaded; a tab open for weeks is one visit  | Yes, for this visit's gestures out of view                                                                            | Small                  |
| Show, then take     | No limit                                                  | No: a target out of view, or one the agent has already picked up, is shown on the first press and taken on the second | Medium                 |
| Only what's in view | The edge of the viewport, so it moves as the user scrolls | No, though it still reaches an old gesture in view                                                                    | Medium                 |

| Add-on             | What it adds                                                                                                  | Build |
| ------------------ | ------------------------------------------------------------------------------------------------------------- | ----- |
| Say what `z` takes | Undo in the leaf's menu and the notice name the gesture and its age                                           | Small |
| Redo on `Z`        | Puts back what an undo took, as Vim's Ctrl-R does, until the user's next change and while it would still show | Large |
| Changes panel      | Every gesture the user made, newest first, each with Undo, and Redo once redo exists                          | Large |

The user's pick: **Show, then take** with **Say what `z` takes**, since it sets no
limit and never acts where the user isn't looking. On the decisions page it read:
"when the gesture's target is out of view, or the agent has already acted on it,
the first z scrolls to it and highlights it (“Press z again to undo”), and the
second press undoes it", with the notice and the panel menu naming the gesture and
its age after a reload too ("Undo: resolved ‘Rollout safety’ · 3 weeks ago").

## What each design changes

- **Last 7 days.** `undo.js` compares the head's `ts` with the clock. The 7 is
  the arbitrary limit the user wants to avoid.
- **This visit only.** `undo.js` records the undo candidates present at the
  first reading, and `undoable()` refuses a head among them. Browser only.
- **Say what `z` takes.** #3271 covers a widget's gesture in the tab that made it.
  The rest: `document.py` adds each candidate's words from
  `GestureWords.says` (`skills/leaf/scripts/leaf/gesture_words.py`). Today
  `served_state/browser.py` builds those words only for a page
  that shows history, so every state read would pay for them. `undoSentence` and
  the notice read them in place of the per-kind words.
- **Show, then take.** `document.py` marks each candidate the agent has picked up,
  from the delivery evidence the workflows already read. `undo.js` holds an
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
- **Changes panel.** A third panel beside On me and Threads, with its glossary entry
  (`.claude/skills/developing-leaf/references/glossary.md`) and keyboard and touch
  routes. It is served the `history` reading on demand, which today reaches only a
  page placing `lf-activity`, filtered to the user's own gestures. That reading
  stops at 50 rows (`LIMIT` in `skills/leaf/scripts/leaf/history.py`), another
  arbitrary limit the panel would need to page past. Its Undo and Redo go through
  the one `withdraw` door.

## Redo in the event model

Redo is an `undo` naming the user's own `undo` in force. Nothing leaves the log
and no counter-event is invented, so the root `AGENTS.md` invariant ("An `undo`
event names the gesture withdrawn; it never deletes or invents a counter-event")
holds as written. `taken_back` changes so that an undo counts only while no
undo in force names it, which makes it a parity fold over the chain rather than a
flat set.

It has three costs:

1. **A restored gesture reads at its original log position.** Every fold reads
   effects in log order, so a restored gesture shows nothing once a later event on
   the same target stands. Any spoken reply, the agent's included, reopens a
   thread (`build_threads`, `events.py`), and a later pick on the same widget
   supersedes an earlier one. A redo that would paint nothing must be refused at
   the door, and the one general check is to fold the log with and without the
   redo and compare what the page shows. Re-sending the gesture as a new event
   avoids this but loses its identity: the agent reads a fresh pick, and history
   can't pair the undo with what it undid.
2. **Readers that follow `undoes` one level must follow the chain.** These are
   `GestureWords.says` (`gesture_words.py`), the coverage lookup in
   `served_state/browser.py`, `projection/presentation.js`, and the undo
   case in `delivery.py`.
3. **A redo restores an answer obligation.** An undo owes the agent no answer, but
   a redo brings back the restored gesture's obligation, which the stop hook
   enforces. The delivery must carry it, and the undo handling text in
   `skills/leaf/assets/registry.json` (the Undo handling clause, "Treat the two as
   cancelling out") needs a clause for a redo.

The rest of the redo change: `UndoReading.error` admits an undo naming the user's
own undo in force when folding without it changes the page; `document.py` serves a
redo list; `projection/model.js` lets a local redo override the server's reading
that the target is withdrawn, as a pending forward action does; `undo.js`
binds `Z`; `lf-activity.js`'s "undone" label
(`skills/leaf/packages/default/widgets/lf-activity.js`), `events.md`, and
`skills/leaf/references/event-batches.md` learn the redo.

Vim's undo tree is a different thing: `g-` and `g+` restore any past state,
superseded branches included, where this redo restores only what would still
show. The Changes panel offers selective undo instead, any gesture in force in any
order.

## Next steps

1. Build in the task's current checkout, and read the current undo owners before
   editing them.
2. Build **Say what `z` takes**, then **Show, then take**, in the runtime and
   Python owners named above, with the door's rule in `events.md`'s Undo section
   and the shortcut words in `undo.js`. The reveal needs a keyboard and a touch
   route (root `AGENTS.md`).
3. Hand the user a live `--user` preview of `review-a-plan` showing the new
   behavior, then move what the redo section still holds into a TODO item and
   delete this note.
