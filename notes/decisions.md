# Approaches considered and not taken

Maintainer notes rather than a published page, and nothing here is checked by CI, so each
entry dates from the day it names. What an entry is for is the arguments that turned out not
to hold, since those are the ones a later reader reaches for again.

## htmx

Considered on 2026-08-28 against htmx 2.0.10, read from
[htmx.org/docs](https://htmx.org/docs/).

htmx serves markup where leaf serves JSON: an element declares a request and a target, the
server answers with HTML, and the swap installs it. The question it puts to leaf is whether
the browser runtime does work a server could do by returning fragments.

Much of it could. The comment path already has that shape — `stageOutboxAction` stages an
optimistic value only for an `action` whose verb declares a `record`, so a comment paints
nothing early: the composer disables Send, the POST answers with the whole state, and the
thread appears out of that answer. Several objections that sound structural are not. Python
holding no template engine is a choice about language. The single-script rule and the page
CSP are leaf's own, and leaf could widen them. `version export` drives headless Chrome and
bakes whatever DOM it finds, so it would survive a server that rendered.

A server answering gestures with markup would need a rendering implementation of every
widget. AGENTS.md keeps a new widget family down to a registry entry, a module and theme
rules, and that module already renders every state the widget can hold. Writing it a second
time in the serving process doubles what a package author ships and moves half of it out of
the browser's sandbox and into the process the agent runs.

Two smaller costs sit under that. A record-bearing action has already moved the DOM before
its request leaves — a drag, an edit — so those verbs cannot wait for a swap, and they carry
most of the behaviour. And a stamped version renders the same forever because everything
deciding its appearance is vendored into the page directory under one layer generation,
where a rendered fragment would come from code outside it; leaf already vendors per-page
browser code, so vendoring a renderer beside it answers that, and the objection folds back
into the sandbox.

Version activation is where htmx would fit. `version.js` fetches the next
immutable revision and replaces `body > main`, which is a hypermedia navigation and nothing
more; htmx would do it, `transition:true` included. The reason not to is that the lines
around the swap carry the contract — the layer-generation check, the head and root attribute
reconciliation, the upgrade passes, serialising behind an activation already in flight — and
htmx would own the boundary they rest on.
