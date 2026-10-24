# Catch up over On me

This note hands over an open design: Slack's Catch up for Leaf, a deck of cards over
the page with one card per item on the user's On me list. A card goes left for Later,
which keeps the item on On me and records nothing, and right once it is answered. It
generalizes the swipe deck retired in #2157 from pass-or-keep proposals to any
obligation. The page beside it (`page.html`) summarizes Slack's design, holds two
working prototypes and today's On view over the same eight items, and puts two
decisions to the user. Serve it with
`uv run leaf-dev preview --source notes/catch-up/page.html --user`. Delete the note
once Catch up lands, or once the user drops the idea.

## The design

The deck reads `readQueues().on_user` in the order the `m` walk uses and counts an
item answered when the server's reading drops it from On me. Within the deck `m` is
Later or Next, Shift+M is Back and Escape closes it; a drag or swipe sends a card
either way.

## The decisions

- **What a card holds.** The item itself: its authored region (the enclosing `lf-ask`
  or the widget), moved into the card with `move` while the card is in hand and put
  back after, answered with its own controls. Or a summary: its title and the answers
  its widget declares as Decision commands (`choicesOf` in
  `browser/runtime/obligations/view.js`), as the On view's cards show them. The page
  recommends the item itself.
- **Whether to hold unread replies too.** Slack's cards are unread conversations; a
  Keep unread for Leaf's threads needs an `unread` event and a protocol bump, since
  `read` events record exposure. The page recommends On me only for now.

## The prototypes

They are page scripts inside each sample's template, using only
`/runtime/widget-api.js` except where the real build would use internals: the summary
finds each widget's answer controls in its DOM as a stand-in for `choicesOf`, and a
question's Reply dispatches `c`. A real deck holding live regions has to stand in the
page's document as a modal dialog, not in the panel's shadow tree, so page styles
reach the item, and has to declare that it covers the page so the margin withholds
the rows of items behind it; in the prototype those rows still show.
