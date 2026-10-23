# Catch-up over On me

This note hands over an open design: a catch-up pass that brings each item on the
user's On me list one at a time, with its own answers and a Later, in the spirit of
Slack's Catch-up and the swipe deck retired in #2157. The page beside it
(`page.html`) holds a live sample of today's On view and two working prototypes,
and puts two decisions to the user. Serve it with
`uv run leaf-dev preview --source notes/catch-up/page.html --user`. Delete the note
once catch-up lands, or once the user drops the idea.

## The design

A pass reads `readQueues().on_user` in the order the `m` walk uses, arrives at each
item through `queueActions.open`, and counts an item answered when the server's
reading drops it from On me. Every widget already declares its answers as Decision
commands (`decision: true`), which the On view turns into buttons through
`choicesOf` (`browser/runtime/obligations/view.js`), so catch-up needs no
per-widget code, no new widget and no event. Later records nothing; the item stays
on On me. Within a pass `m` steps on, Shift+M steps back and Escape ends it, and a
sideways swipe does the same on touch.

## The decisions

- **Where each item is shown.** In place (the page dims around the item and a bar
  holds the pass) or a card (one On card at a time above the panel, with the page
  travelling to the item behind it). The page recommends the card.
- **Whether to walk unread replies too.** Slack's "keep unread" maps to thread read
  state, which `read` events record on exposure, so walking unread agent replies
  needs an `unread` event and a protocol bump. The page recommends On me only.

## The prototypes

They are page scripts inside each sample's template, using only
`/runtime/widget-api.js`, except where the real build would use internals: they
find each widget's answer controls in its DOM as a stand-in for `choicesOf`, open
a question's comment box by dispatching `c`, and move to the window's top while a
panel view covers its foot. The real card would join Leaf's panel instead.
