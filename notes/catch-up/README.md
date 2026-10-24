# Catch up as a widget

Slack's Catch up for Leaf is `lf-deck` in the `deck` package: a widget the agent writes
around the questions it is waiting on, which the user works through one card at a time.
Its contract is the header of `packages/deck/widgets/lf-deck.js`. The page beside this
note (`page.html`) holds a live sample and puts one decision to the user: whether the
deck moves into the default package, so every page has it. Serve it with
`uv run leaf-dev preview --source notes/catch-up/page.html --user`, and delete this note
once that is decided.

An earlier design put a Catch up button at the panel's foot and a deck over the whole
window, built from the On me list. The user turned it down: Catch up should be a widget
agents show on the page, and the prototype was slow, waiting a fixed 700 ms after each
answer's reading before a 240 ms flight.
