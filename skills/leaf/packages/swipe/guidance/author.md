# Swipe decks

Use a swipe deck when the user can classify several independent technical proposals quickly; use ordinary options when the proposals need side-by-side comparison. One deck is one Ask inside `lf-ask`; pressing `a` lands on its question and also exposes the deck's ← Pass and → Keep actions inline. The final classification closes the Ask by emptying the queue.

Give the deck exactly one pile for each verdict (`unseen`, `pass`, and `keep`), put new cards in `unseen` in review order, and keep every card self-contained enough to judge without opening another section. `pass` means remove the item from this design and `keep` means retain it for follow-up, so state that local meaning before the deck when it would otherwise be ambiguous.

Keep the authored starting placement stable after publication; `lf-swipe-deck` says how classifications carry forward and where `restated` goes when a rewrite invalidates one.
