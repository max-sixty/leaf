The user commented on a long thread they were reading in a margin card:
"particularly in times like this, it would be useful to have a way of opening the
thread in the expanded floating panel; so we can see it all; can we think about
how to do that?"

You investigated and prototyped. Your notes:

- Today a margin card is 444px wide. A thread reaches the floating panel's thread
  view only by closing the card, pressing the Threads mark and then the thread's
  row: three presses. That view opens 540px wide. The panel also has a 760px
  width, More room to write, for long drafts.
- Measured on this thread in a 1640x1010 window: the margin card shows 864 of
  1245px of it (69%), the panel's thread view 778 of 1007px (77%), and the panel
  at 760px all 839px.
- The routes, from today's behavior to the largest change:
  - today, "Keep Threads as the only way in": three presses, 540px.
  - panel, "Add Open in panel to the card": an expand icon in the card's head,
    beside Resolve and Close. One press closes the card and opens the thread in
    the panel's view at today's 540px.
  - reading, "Open in panel at reading size": the same icon, and the view opens
    760px wide and may rise to 24px from the window's top. The whole thread fits.
    You recommend it.
- The captures below come from a prototype. Its implementation is not included in
  this workspace.
- Captures, each a 1640x1010 window with the thread open beside the column:
  - evals/decision-options-fit-the-window/captures/start-card.png: today's margin
    card, where every route starts.
  - evals/decision-options-fit-the-window/captures/card-with-button.png: the card
    with the Open in panel icon in its head, at about x 1180 to 1640, y 10 to 80.
  - evals/decision-options-fit-the-window/captures/today-panel.png: after Threads,
    then the thread's row: the panel's view at 540px.
  - evals/decision-options-fit-the-window/captures/panel-panel.png: after Open in
    panel at today's size.
  - evals/decision-options-fit-the-window/captures/reading-panel.png: after Open
    in panel at reading size, the whole thread.
- Once a route is chosen, you'll build it from the prototype into the runtime with
  a keyboard route, carry a reply being written into the panel, and show the user
  a before/after still and the journey in Firefox.

Write the Leaf page that puts the choice of route to the user.
