# Starting Threads in datum outlets

Status: implemented

## Existing behavior

Leaf already has inline conversations in two forms:

- A widget that declares `x-conversation` can call `conversationBox`. This puts a
  persistent conversation seat in the widget, with its own first-message composer, and
  renders the resulting Threads there. The Command Hub uses it for every `lf-task talk`
  row.
- A widget that declares `x-thread-surface` can call `registerThreadSurface`. Core then
  renders established Threads in widget-provided outlets for exact projected data. The
  diff uses it to put full conversations beside individual lines, and the Feature
  Gallery includes a seeded example.

The missing case is narrower: a reader cannot start a new conversation in an exact
datum outlet. `conversationBox` is a persistent section seat and always constructs
`{section: owner.id}`. `registerThreadSurface` does nothing until a root comment exists.
An exact file or line therefore starts with the floating anchored response bar, even
though the resulting Thread can appear inline at that coordinate.

`commentOnTarget` previously tried to focus a widget's `conversationBox`. The current
runtime rejects that route because a section seat may be hidden, may contain several
Threads, and does not preserve the initiating gesture's focus and design-mode meaning.
This proposal does not restore that behavior. The canonical anchored composer still
opens first; only its presentation moves after the exact datum has resolved.

## Purpose

Extend the existing datum Thread surface so it may place Leaf's anchored composer as
well as established Threads beside the exact projected item being discussed. A diff can
therefore put a Comment control in a file or line gutter and open the composer below
that target. The comment still uses Leaf's ordinary anchor, draft, event, delivery, and
Thread lifecycle.

The outlet controls presentation only. The anchor remains the semantic location of the
conversation. Persistent `x-conversation` section seats keep their current contract.

## Result

An exact target inside a widget uses that widget's registered Thread outlet. A
target without an available outlet uses the floating response bar. The same composer
moves between those presentations; a widget never creates or owns an editor.

For `lf-diff`:

- Each file provides a visible Comment button. Hovering a changed line reveals its
  Comment button in the gutter.
- Activating the button opens the composer after that file or immediately below that
  line.
- Alt-click, item selection, and quoted text use the same inline outlet when their
  resolved anchor names that file or line.
- Sending the first comment closes the composer and the same Thread surface renders the
  resulting Thread in that outlet.

## Ownership

Core owns:

- the one anchored response composer node and whether it is open;
- draft keys, draft persistence, and explicit draft carrying when the reader retargets;
- Comment, Suggest, reactions, media, keyboard behavior, and accessible naming;
- event construction, delivery state, refusal, and the transition into a Thread;
- choosing inline or floating presentation and moving the composer between them;
- focus and selection continuity while the presentation changes.

The widget owns:

- the visible Comment triggers appropriate to its content;
- the layout location for an active inline composer;
- creating and removing its outlet as rows disclose, filter, load, or rerender;
- any grid rows or spans needed to make the composer occupy real layout space.

The Thread outlet is one layout location at an anchor; core decides whether it contains
established Threads, the active composer, or both. This avoids a separate composition
registration that would have to agree with the Thread surface about the same coordinate
and grid rows.

## Registration contract

The existing `x-thread-surface: true` declaration and adapter remain the contract:

```js
const threads = registerThreadSurface(this, {
  begin() {
    // Mark retained outlets inactive before one reconciliation.
  },
  outletFor({ anchor, placement }) {
    // Return the connected outlet for this exact target, or null.
  },
  end() {
    // Remove outlets that were not retained.
  },
});
```

The returned handle has three operations:

```js
threads.open(projectedElement, { origin });
threads.update();
threads.unregister();
```

`open` accepts a current projected element owned by the registering widget. Core captures
the canonical datum anchor from that element, including source and data revision when
the projection came from external data, and passes it through the same
`commentOnTarget` command used by Alt-click. `origin` is the control that receives focus
when the composer closes. The handle cannot name another widget, post an event, read a
draft, or alter response modes.

`update` schedules application invalidation. One Thread-surface reconciliation collects
the coordinates named by established Threads and the active composer, groups them by
owner and datum, calls `begin`, asks `outletFor` once for each exact coordinate, then
calls `end`. The adapter receives the canonical resolved placement, including the exact
datum element. It does not search the event log, inspect drafts, or interpret an anchor.

Core accepts an outlet only when all of these are true:

- the registration is still active and its owner is connected;
- the anchor's section is the owner id;
- anchor resolution reports an exact datum inside the owner;
- the returned outlet is connected and belongs to the owner;

The adapter returns a normal container in either light DOM or a declared shadow root.
Core reconciles its Thread views into that container and, when the anchor matches the
active composer, moves that composer there as the final child. The existing theme slice
for declared shadow roots carries the response control's rules beside the Thread rules;
no widget constructs or adopts another stylesheet. Removing inline presentation returns
the composer to Leaf's chrome root.

Composer focus checks use Leaf's composed-tree focus reading rather than
`document.activeElement` or a light-DOM `contains` test. Reparenting the composer must
not fire draft hiding, focus return, or outside-click behavior.

Invalid registration arguments throw before installing an adapter. A failure during
reconciliation or invalid adapter output reports a page error, clears that
registration's core-owned views, returns its Threads to the living margin, and uses
floating composition. It does not close the composer or discard the draft.

## Presentation lifecycle

1. A Comment gesture resolves a stable anchor and opens the canonical composer.
2. Core asks the matching registration for an exact outlet and mounts the composer
   before showing or measuring it.
3. When an outlet exists, core applies inline presentation. Inline presentation
   participates in widget layout and does not run Floating UI.
4. Otherwise, core mounts the composer in the chrome root and uses the existing
   floating placement against the best visible resolution of the anchor.
5. Widget updates, disclosure changes, filtering, fragment loading, revision changes,
   and disconnection reconcile the active presentation. The draft, textarea node, and
   response mode remain with the composer. Moving between available presentations
   preserves focus and its selection; when neither fits, Leaf uses its existing kept-draft
   route. An explicit retarget keeps the current `commentOnTarget` behavior.
6. A successful send uses the existing comment event. The composer closes through its
   current settlement path. Conversation projection then replaces it with the new
   Thread in the same registered outlet, and the existing guarded typing handoff lands
   in its reply field only when no later reader gesture has claimed focus.
7. A refused send leaves the same inline composer and draft available for correction.
8. Escape follows the existing response hierarchy. Closing an inline composer returns
   focus to its initiating control when that control still exists.

Only one outlet contains the active composer because Leaf has one anchored composer. An
explicit Comment gesture on another target carries a non-empty draft according to the
current `commentOnTarget` rule; passive rerendering never retargets the draft.

## Diff integration

`lf-diff` uses its projected file and line keys as the only coordinate. The Comment
control passes the key to `threads.open`; it does not assemble an event anchor.

The file outlet sits after the file and is available before a manifest fragment loads.
A line outlet adds one content row and its paired gutter row, using the
same span accounting as the current Thread-only implementation. A quoted range within a
rendered line resolves to that line's outlet.

The control is a real button with an accessible name such as `Comment on app.py · new
line 24`. Each line does not add another sequential Tab stop. Pointer hover reveals the
button, while the existing target-selection route supplies the keyboard path to the same
datum. The file-level button remains an ordinary keyboard control.

Closing, filtering, or unloading a file may remove the exact line outlet. Core retains
the draft and uses the ordinary floating or kept-draft behavior according to whether the
anchor still has a visible placement. Reopening the file restores inline presentation
once the exact line resolves again.

## Styling

Inline presentation uses the response control's existing typography, controls, media,
and state styles. Its layout rules differ from floating presentation:

- `position: static` and width constrained by the outlet;
- no Floating UI coordinates or float-size custom properties;
- textarea growth bounded by the widget's reading region;
- one full-width row that does not inherit the diff's code `white-space` or horizontal
  scrolling;
- print, copy, and exported markup omit generated Comment controls and the active
  composer; established Threads keep their current export behavior.

The widget theme owns only the outlet's placement in its grid. Core owns the
composer's shape in both presentations.

## Invariants

- One anchored response draft belongs to one anchor regardless of presentation.
- Moving the composer never clones its textarea or copies its value.
- Widget code cannot create comments, replies, or response modes.
- An outlet never changes the event anchor.
- Losing an outlet never loses a draft.
- A successful comment produces the same event with or without an outlet.
- Thread placement remains a projection of standing conversation state, not a side
  effect of the composer.
- Widget removal leaves no registered adapter, generated control, or outlet behind and
  does not strand the composer in the detached widget subtree.

## Acceptance tests

Browser coverage uses a bound manifest diff and proves:

1. A closed, unloaded file accepts a file comment without fetching its fragment.
2. A line Comment button opens one inline composer after the exact line and focuses its
   textarea.
3. Keyboard activation, Alt-click, item selection, and a quoted range reach the same
   outlet and accessible target label.
4. Retargeting with a non-empty draft carries the draft once. Passive reconciliation
   preserves the active textarea, caret, selection, and focus.
5. Filtering, closing, reopening, data refresh, and revision replacement retain draft
   text, media, and suggestion mode while the exact outlet appears or disappears. The
   same checks cover an outlet inside a shadow root.
6. A successful send replaces composition with an inline Thread in the same outlet and
   lands typing in that Thread's reply field. A refused send keeps the composer in
   place. Existing diff Threads still render, reply, react, resolve, and fall back to the
   living margin as they do before the cutover.
7. Returning an outlet outside the widget reports one error and falls back to floating
   presentation. Disconnecting the widget reports no error, restores floating
   presentation, and unregisters cleanly.
8. Ordinary prose and widgets without the capability retain today's floating response
   behavior.
9. Copy, print, and export contain neither Comment controls nor an open composer.

The focused browser suite also checks both narrow and wide reading regions, soft-wrapped
and horizontally scrolling diff lines, reduced motion, and keyboard-only operation.

## Non-goals

- No new event, anchor, draft, or conversation schema.
- No second registry declaration or outlet registration beside `x-thread-surface`.
- No widget-owned composer or diff-specific sending path.
- No replacement for persistent `x-conversation` section seats or the retained Threads
  panel.
- No simultaneous anchored response composers in datum outlets.
- No general editor API for package code.

## Implementation order

1. Let the existing Thread-surface reconciliation include the active anchored composer
   and expose `open` on its registration handle.
2. Separate the response bar's mount mode from its existing draft and send lifecycle.
3. Carry the composer presentation through the existing shadow-theme slice, make focus
   readings cross shadow boundaries, and support light- or shadow-root outlets with
   floating fallback.
4. Add diff file and line controls plus file outlets, reusing its current line-outlet
   grid accounting.
5. Add lifecycle, accessibility, export, and end-to-end delivery tests before changing
   another widget.
