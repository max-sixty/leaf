# leaf

A page Claude hands the user, and the loop that carries their comments back. The
README covers what it does; this covers how it is built, and the rules that keep it
buildable.

## Soul

Everything here serves a high-fidelity connection between the agent and the person it is
working with. That is why the handover is a page. A terminal has one channel and one
width; a page has as many as the subject needs — a diagram, a board the user drags,
two screenshots that flip in place — and it carries the reply back on the words that
prompted it. The vocabulary is something to build with rather than a form to fill in: a
shape leaf hasn't got is one a project can add, since theme, registry and widget
modules all overlay from the user's own config.

Bandwidth is one axis; the other is time. A page that keeps up with the work — a list of
things ticking over as each is done — says more than the same list written afterwards,
and keeping it true costs a version rather than a paragraph. Build toward pages that are
the work itself.

## Stage

Early, and nothing owes the past anything. Nobody uses it, so there is no deployment,
no database, no command, flag, or name anyone has learned, and no page or log on disk
with a claim on new code, whichever version of the layer minted it. Stale state is
deleted and made again, which is the whole of the migration, so no code reads the old
shape and a page a change breaks is neither a caveat to raise nor a follow-up to file.
Backward compatibility carries zero weight: rename and reshape whenever the better
form is clear, and treat a name being the current one as no argument for keeping it.
So the trade between simplicity and robustness is already settled — take the simpler
code. A guard earns its place only where the state it defends against is reachable and
there is something to do about it; the rest is complexity paid for a case that never
arrives, and it reads as if the impossible were expected.

That settles your own hesitation too: an improvement you can see is one to make. A
change is the user's to call when it turns on what only they know — what the work is
for, what they meant by it, what they will do with it next. Not because it takes
judgement, not because it changes what a page says, and not because the present form
was chosen deliberately once; that is the ordinary substance of the work. The tell is a
change worked out and then reported rather than made — "your call rather than a defect"
— which spends a round trip being told to do what you had already decided on.

Where data enters, check it once and completely: browser events at `POST /api/event`,
authored markup at `version check`, a replayed action's detail in the widget's own
`applyAction`, since only it knows that shape. Everything downstream then indexes the
field rather than asking a second time whether it arrived.

## Shape

Claude Code and Codex both resolve `plugins/leaf/` as the plugin payload:
`.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` are the two
repo-root pointers, and the payload carries one manifest for each host. Seven things make
the product, and nothing sits between them. Six are the skill's, under
`plugins/leaf/skills/leaf/`:

- `scripts/interact.py` — a `uv` script: the server, the event log, the lint
  (`version check`), vendoring, export. No daemon, no
  database. Reached as `leaf`, through the payload's `bin/` shim: Claude Code puts
  it on PATH and Codex resolves it from the active skill directory.
- `assets/leaf.js` — the runtime the page loads. One ES module owning the widget
  layer and the comment layer, with its stylesheet in a `<style>` block inside it. No
  build step.
- `assets/registry.json` — the machine's own vocabulary: the suggestion family and
  the layer-wide `$` keys. The renderer, the linter, and the agent's documentation
  all read the merged registry, so none of them can drift from the others.
- `assets/theme.css` — the tokens, elements and idioms every page links, the
  suggestion family's rules, and what the runtime styles its own chrome from, so a
  page themes as one thing.
- `assets/icon.svg` — the mark, worn by the tab of every served page and by the
  published site alike, so there is one of it. Its `lf-tone` element is what the runtime
  paints the page's status onto.
- `bundled/` — the content widget families, an overlay layer in the integrated
  layer's own layout: their registry entries, one module per upgraded widget, their
  theme rules, mermaid and sortable beside them. `page init` merges it exactly as it
  merges a user's `~/.config/leaf/` or a project's `.leaf/`, so the shipped
  widgets reach a page through the same door a customization's do — every vendoring
  is the proof the door works.

The seventh is `examples/` at the repo root — complete pages that are also the render
suite's corpus, plus `gallery.html`, all on one page (generated; edit the examples, not
it).

`plugins/leaf/hooks/hooks.json` is shared too: both hosts speak its three events,
and Codex supplies `CLAUDE_PLUGIN_ROOT` as a compatibility alias. The launcher maps
Codex's thread identity into the session record that Claude Code supplies directly.

The whole layer is vendored into each page directory by `page init`. A page you approved
can't change under you when the defaults do. What a page directory holds, and why each
thing is in it, is `interact.py`'s module docstring.

## Norms

Each of these was learned by getting it wrong, and the failure is named with the rule
because the rule alone is just a preference. They live next to the code they bind, so
opening that code is how you meet them:

- the page in the browser — the runtime, the widget modules, the theme, in the
  integrated and bundled layers both: `plugins/leaf/skills/leaf/CLAUDE.md`
- the server, the log, and the lint: `interact.py`, in its
  module docstring and beside the code each one binds
- the tests: `tests/CLAUDE.md`
- the examples, and what the corpus owes the vocabulary: `examples/CLAUDE.md`

Four bind both runtimes at once, and no one directory owns them.

### The document is the state, and the log outranks it

A user's edit (a dragged card, a pick) posts an `action`, and every action replays
onto every version after the one it was made on. Nothing is stored as "the current
board"; the log plus the version is the whole truth. Keep it that way — a second store
is a second thing to reconcile.

There was a second store once, unnamed: recorded state in the log and authored state in
the markup, with the page's author expected to copy each decision from one to the other
by hand. `version check` guaranteed ids survived a republish and nothing guaranteed the
state on them did, so a forgotten copy silently un-made a decision. The user
re-approved the same drafts version after version, and no part of the system said a
word.

One writer, then: markup states the initial condition, the log every transition after
it. A version that says nothing about a decision leaves it standing. The cost lands
where the old design hid it — a version can't quietly revise what the user acted on,
because replay would paint their state back over the revision — so `restated` on the
rewritten element retracts what rested on it, and `version check` refuses a bare rewrite
and an unearned `restated` alike (`restatement_errors`).

Both failures are invisible to the user, so the question was never which is worse
but who can see each. A dropped decision is visible to nobody. A stale decision standing
over rewritten content is visible to the author as they rewrite it, and only they know
whether the rewrite invalidates it. Route a failure to whoever can adjudicate it: the
runtime preserves by default, and discarding costs the author a word.

### One representation per concept

A passage is `{node, start, end}` segments — for the quote search, the quote capture, the
reading-position landmark, and the version diff's block keys alike. When there were four
answers to "what text is in this region", every one of them was some other one's bug: a
selection's `toString()` returns what `text-transform` rendered, so a quote captured that
way could never be found again. `page_passages` is that one answer on the Python side, so
anything asking what a version says slices it (`spoken`) rather than walking the markup
again.

A second representation earns its place only when the two things are genuinely different
(an element anchor has no text to paint, so it wears an outline). Not when they are the
same thing reached by different code.

One representation means one budget too, and the budget belongs to whatever is actually
scarce. A quote was capped at four hundred characters, which read as an economy over a
log line and was a claim about the page: the stored quote is the passage, so the mark
paints it and the comment is on it, and a reader who selected a paragraph past the cap
got a comment on its opening with a highlight that shrank to match — silently, on most
of the paragraphs a leaf page holds. What could not afford the passage was never the
log; it was the search's pattern, one regular expression with a term per character, which
V8 refuses to compile at all past some length between five and twelve thousand of them.
So the bound sits on the pattern (`LEAD_CAP`), which finds the candidates, and the rest
of the quote is walked against the text from each. A cap on the wrong side of a
representation reads as thrift and spends what the representation was for.

Two readings of one element's words are the case that does earn it, because they answer
different questions. `says` is what is on the screen for the user to point at, so a
label a widget declared as the page's words is in it; `wrote` is what the author put
there, so everything an upgrade generated is out. The version diff wants the second (the
base version it compares against has no generated nodes at all) and so does a widget
naming one of its own parts — a picked row's mark is the page speaking, which belongs in
what the user can quote and not in the row's name, or a question answered reads its own
answer back as part of what was asked. One reading with a flag would have been the same
two answers with nothing saying which is which.

### The file's reading never claims more than the page's

An anchor is captured in two places and resolved in one. `selectionAnchor` captures from
the DOM, `leaf comment` captures from the version file, and `resolveAnchor` is still
the only thing that searches. Two captures are not two answers to "what does the page say
here": both write the same collapsed text under the same rules, so what the file's reading
holds the page holds too — where a module replaces what the file holds, the reading skips
it, and everywhere else a module only adds.

The file alone is not enough, because the user moves the page too: a decision retires a
settled suggestion's losing slot, and an edit puts their words where the authored body was.
So both readings follow the log rather than the markup, and each refuses a quote into what
it dropped by naming the act that dropped it. The keys that carry this and the shape of
each reading are `_PassageParser`'s.

Keeping that true is not free, and the first draft wasn't. A board's module prepends each
column's heading, so a quote running from the lede into the first card matched a file the
page no longer resembled and anchored on nothing; a milestone's chips do the same
mid-element, where no edge keyword can reach. And a prefix captured one character wider
than the DOM's — a leading space the runtime's own collapse trims — is context no
occurrence can ever confirm, which silently costs the comment its copy.

So where the file can't model what a module writes, the reading stops rather than guesses.
The registry declares what it can and a fence covers the rest, and a quote across a fence
is refused when it is written instead of detaching later in front of the user. The
browser indexes those same fences before upgrades run and clips captured context to them
afterward, so neither capture claims neighbours the other cannot confirm. A widget that
writes words of its own declares them or stays fenced.

Context identifies an occurrence only when exactly one candidate confirms it in full.
If no candidate does, a quote that occurs once can still identify itself; a repeated quote
cannot. It detaches instead of falling back to document order, because an offset or ordinal
is not evidence that a revised copy is the one the user meant.

### The widget list is never closed

The vocabulary grows by an entry in `registry.json` and a module beside it, and nothing
may assume it has seen the whole of it. A consumer that works from which widget it is
looking at is a consumer that stops at the ones it was taught, and it fails quietly
rather than loudly: it keeps working perfectly on those while silently doing nothing for
the next one, so the bug surfaces as a feature that was never wired up rather than as an
error. So a consumer works from what an entry declares — where a behaviour is wanted by
some widgets and not others, it becomes an `x-` key they declare and the consumer
dispatches on, and no branch anywhere reads `lf-diagram` and does something particular.
That binds the runtime, the lint, `version check --render`, `version export`, and the
skill's own prose alike; the test is whether a twelfth widget touches anything but its
module and its entry, and where it would, the thing missing is a declaration.

Most widgets are things a page contains, and those are anonymous outside their own
module. A few are part of the machine the list is defined against, and core names those
outright. The suggestion is the one today: the log settles it, `retirable_ids` is written
in terms of its slots, and thread markup refuses one. That name is a mechanism's, not a
member's, so it isn't a special case waiting for a declaration to replace it. Which kind a
widget is has one question behind it — is this one of the ways leaf works, or one of
the things a page can hold? Convenience is not an answer to it; a widget joins the first
set by having the loop written in terms of it.

The banner's `✓ Accept all` used to be a fourth item in that list and was never one. It
counted `lf-suggestion:not([data-lf-state])`, which is the shape of a mechanism and the
substance of a member: what the page is waiting on the reader for is not a suggestion's
question but the whole page's, so the count that named one tag was perfect for that tag
and silently zero for every question, pick and blocked task beside it. `x-awaits` is what
it became — the entry says an instance of this tag stands as a request to the reader, and
one list then feeds the banner's count, the key that steps them and the `?` overlay. So
the question above has a second edge: a name core can only defend because that widget got
there first is a declaration waiting to be written, and the way to tell is to ask what the
sentence would mean for the twelfth widget. "The log settles a suggestion" stays true of
the mechanism; "the banner counts suggestions" was already the wrong sentence.

Declare the general property, not the particular widget, or the special case has only
moved into the registry: `x-upgrade` says a module enhances this tag, not that mermaid
needs loading. The bar is real — an `x-` key the log records is a forever-contract the
vendored-layer stamp then carries (`$events`) — which is an argument for finding the
general shape, not for reaching past the registry.

A fact the whole layer shares belongs to the layer, under a `$` key, rather than to
whichever widget first needed it. The vendored tokenizer's language list lived in
`lf-code`'s `language` enum, and from there the only way for the lint to read it was to name
`lf-code`: the wrong home was the cause and the reach by name only the symptom, which is
why moving the list (`$languages`) is what let the widgets declare instead (`x-language`
names the attribute carrying one). The tell is a consumer indexing past the entry it was
handed — and the second tell is what such a consumer does when the reach comes up empty,
because a list read from the wrong place is a list that can move, and a check standing
down on `if not known` retires itself the day it does.

Layers compose a `$` key member by member, where a tag's entry replaces whole, because
the two are different kinds: a schema is one contract whose halves cannot mix, and a
shared fact is a namespace whose members stand alone. Under replace-whole, a project
declaring its one idiom vendored a `$idioms` holding exactly that idiom — every shipped
idiom kept styling, theme.css concatenating where the registry did not, while
`page catalog` silently dropped the other ten — so the natural act of declaring a shape
cost the agent the catalog it authors from. The stamp is indifferent to the grain: its
gates read the merged result (`merge_layer_entries`).

An `applyAction` implementation states an absolute placement, never a relative mutation,
because the poll replays it and the sender's own action must be a no-op. The verb, its
detail schema, its fold unit, and its record form are declared in the registry
(`x-state`), not known privately to the module: absoluteness is what makes the
user's standing state a fold over the log, and the declaration drives every consumer
of it without teaching any of them a widget by name.

## Working on it

- **Tests are integration tests in a real browser.** `test_render.py` drives the shipped
  examples through the Chrome already on the machine. What a test must assert, and the
  ways one passes vacuously, are in `tests/CLAUDE.md`.
- **Measure before optimising and before assuming.** The cost claims in this codebase came
  from timing the real thing on `examples/gallery.html`, not from reasoning.
- **Merge locally.** The project isn't at the stage of PRs: landing is `wt merge`, a
  direct squash merge to main, never a PR — background jobs, whose harness default is a
  draft PR, included. That settles the form of a landing, not whether one was asked for:
  a job once read "merge locally" as standing permission, and unreviewed work landed on
  the strength of it. A finished branch waits for the user's go-ahead unless the task
  said to land.
- **A session loads each host's cached copy, not the checkout.** Both repo-root
  marketplaces point at `plugins/leaf/`, and both hosts install from GitHub main, so a
  payload change reaches a session only once pushed, and reaches the next session rather
  than the one that pushed it. Neither manifest declares a version, because that string is
  Claude Code's cache key: an unchanged one leaves the old copy in place and the update
  reports it as the latest. Without one the key is the commit, so Claude Code's periodic
  marketplace sweep installs each pushed commit on its own and nothing needs running.
  Codex installs from a marketplace snapshot it fetches separately and does not sweep, so
  a change reaches it through `codex plugin marketplace upgrade leaf` and then
  `codex plugin add leaf@leaf`.
