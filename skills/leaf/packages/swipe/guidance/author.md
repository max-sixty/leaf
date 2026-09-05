# Swipe decks

Use a swipe deck when the reader can classify several independent technical proposals quickly; use ordinary options when the proposals need side-by-side comparison. One deck is one Ask: wrap it in `lf-decision` and lead with the heading that states the question. Pressing `a` then lands on that question and exposes the deck's ← Pass and → Keep actions inline. The final `finish` classification closes the Ask through the deck's declared empty-queue condition; the server tests it after the recorded move, so a stale rapid gesture cannot close a queue whose earlier card returned.

Give the deck exactly one pile for each verdict (`unseen`, `pass`, and `keep`), put new cards in `unseen` in review order, and keep every card self-contained enough to judge without opening another section. `pass` means remove the item from this design and `keep` means retain it for follow-up, so state that local meaning before the deck when it would otherwise be ambiguous.

Keep the authored starting placement stable after publication. Leaf replays recorded classifications by card id on later versions. Use `restated` on a rewritten card when the rewrite invalidates an intermediate classification; use `restated` on the deck when a rewrite invalidates its completed Ask.
