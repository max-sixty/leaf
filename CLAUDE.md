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
module. A few are part of the machine the list is defined against, and core would name
those outright. None is today, and the suggestion is where the temptation kept landing:
the log settles it, a version honoring that decision may drop the ids it retired, and
thread markup refuses one, no version being able to reach a widget frozen in the log. All
three read as sentences about the suggestion and every one of them is about a relation
the registry states — `x-retired-when` names the outcome a slot leaves the page under and
`x-parent` the widgets whose decision reaches it, so a holder/slot pair is the whole of
what a settlement is (`retirement_slots`). All three are written from that pair now, and
a family a project declares gets them the day it declares it.

The licensing was the one still written in terms of `lf-old` and `lf-new`, and the
registry door had to be held shut on the key to cover for it: a third-party slot could be
declared, painted, decided and read, and then the version honoring the decision failed
with "ids dropped", three versions from the declaration and with nothing to connect the
two. Refusing the declaration gave that failure somewhere to be reported and left the
wrong shape standing. What the pair genuinely could not say is what an *unanswered* one
means when the author takes it back: a withdrawn suggestion leaves the page where a
`reject` would, and "which outcome retires this slot" never says which outcome that is.
So the widget says it (`x-withdrawn-as`) and the two halves are one rule — the outcome
the log recorded, or the one the entry says a withdrawal stands as, hedged because there
the author is asserting a state the user never gave.

One name is left in core and it is a member's. `suggestion_errors` holds the family's
markup to one slot of each kind, at least one of them, and no nesting; it reads which
tags those are off the registry, and the rules themselves are the family's, cardinality
being the thing no key states. Ask what those sentences mean for the twelfth widget and
the answer is nothing, which is what makes them a member's lint rather than a mechanism
reaching for a name. The day a second family wants them is the day the registry grows a
way to say them.

Which kind a widget is has one question behind it — is this one of the ways leaf works,
or one of the things a page can hold? Convenience is not an answer to it; a widget joins
the first set by having the loop written in terms of it.

The banner's `✓ Accept all` used to be a fourth item in that list and was never one. It
counted `lf-suggestion:not([data-lf-state])`, which is the shape of a mechanism and the
substance of a member: what the page is waiting on the reader for is not a suggestion's
question but the whole page's, so the count that named one tag was perfect for that tag
and silently zero for every question, pick and blocked task beside it. `x-awaits` is what
it became — the entry says an instance of this tag stands as a request to the reader, and
one list then feeds the banner's count, the key that steps them and the `?` overlay. So
the question above has a second edge: a name core can only defend because that widget got
there first is a declaration waiting to be written, and the way to tell is to ask what the
sentence would mean for the twelfth widget. "The log settles what a version then has to
honor" is a mechanism's sentence, which is why it survived being rewritten without the
name; "the banner counts suggestions" was already the wrong sentence.

Declare the general property, not the particular widget, or the special case has only
moved into the registry: `x-upgrade` says a module enhances this tag, not that mermaid
needs loading. The bar is real — an `x-` key the log records is a forever-contract the
vendored-layer stamp then carries (`$events`) — which is an argument for finding the
general shape, not for reaching past the registry.

A boolean key is an enumeration whose second value has already been chosen, and it was
chosen by whichever widget declared first. `x-wide: true` read as *may stand wider than
the column* and meant *and fills whatever box it is given*, which is a board's answer to
a question the key never asked: what the theme has to decide is how far the box may
reach, and with nothing to read it decided once, at the one width the vocabulary shares.
A diagram's graph is drawn at a size its source decides, so held to that width a 1533px
sequence diagram was cut off at 1080 on a window with room for all of it, behind an
overlay scrollbar this platform hides until it is used. Nothing named a widget and
nothing reached past the registry, so every gate that catches those had nothing to see,
and it surfaced three widgets later as the page's reader saying a diagram was cut off.
The kinds are values now (`box`, `drawing`). Where a key's `true` carries a claim the
entry never states, that claim is the value the key should have had.

The stylesheet is under the same rule and answers it in its own vocabulary, since a
selector is a consumer too and a list of tags is the closed list wearing CSS. A box
declares that it frames what it holds (`--lf-frame`) in the rule where it draws the frame,
and one style query trims what every such box would otherwise paint as its own inset — so
a project's card is covered by saying the same thing, where a list in leaf's theme could
never have named it. The norm is `plugins/leaf/skills/leaf/CLAUDE.md`'s.

Which is not to say one declaration answers every question about the same boxes. The room
a wide exhibit may take reads as the same question — the boxes it must stay inside are
the boxes that frame what they hold — and `--lf-frame` cannot carry it: the declaration
says the box has an inset a child's margin would double, so `main` makes it, the column
being a padded box like any other, and read that way the room is withheld from every
exhibit on every page. A shared declaration is worth reaching for and worth measuring
before it is spent; the tell is that the two questions have different answers for one
box.

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

For a long time nothing checked it and every gate passed a relative one, because there
is nothing to see: it renders perfectly, and what it costs arrives later, on the poll
that replays the sender's own action over the state their gesture already painted — the
reader drags a card once and watches it walk. So the render gate asks the page rather
than the code (`RELATIVE_REPLAYS`): it re-applies the standing state and reports what
moved, at the widget, with the fix. Replaying the log again would prove nothing, since
every action carries its seq and replay retires each exactly once, so a second pass is a
no-op whatever the widgets do. It reads the result twice, one reading being blind where
the other sees — `shallowSigs` for the markup state, which excludes text on purpose, and
the unit's declared record form for the words.

The set is re-applied whole and in the log's order, which is not the same check as
asking each action on its own. Absoluteness is a claim about a unit, not about the
page: two cards dragged to the head of one column fold to two standing moves, and
replaying the earlier one alone is *meant* to lift it back over the later one. Measured
per action that called lf-board relative and refused a page with nothing wrong with
it — at the one gate a handover cannot get past, which is the expensive place to be
wrong. What it still cannot reach is a verb nobody has used: the actions are the log's,
so a widget shipped with no decision recorded on it yet is checked by its first user
rather than at handover.

A verb's record form is also the whole of what a module may write in the author's namespace.
An entry's `additionalProperties: false` closes that namespace, and the file's lint holds
a version to it — but a widget has a second writer the file cannot see, and a module can
leave anything it likes on the element it upgrades. So it writes there only where a record
declares the attribute (`chosen`, `status`), and everything else it needs to mark goes on
the chrome it built, in the platform's vocabulary or under `data-`. `lf-options` had two of
the other kind and both were silent: `answered` recorded a verb only a thread can post,
where no version can carry the markup to honor a record of it, and `open` recorded which
way this tab last left a disclosure, which no version carries at all. Each was a second
copy of a fact the module already stated on the control that carries it, and the one
reader that saw them believed them — `shallowSigs` excludes exactly the attributes no
version can assert, and its exclusion list is the runtime's own paint, so a widget writing
beside it is counted as state the author wrote. `version check --render` asks the rendered
page for the rest (`UNDECLARED_ATTRS`), which is the only side the second writer shows on.

## Working on it

- **Tests are integration tests in a real browser.** `test_render.py` drives the shipped
  examples through the Chrome already on the machine. What a test must assert, and the
  ways one passes vacuously, are in `tests/CLAUDE.md`.
- **A cloud container has none of that, so set it up first.** No system Chrome, so every
  browser test fails at launch — the Chromium preinstalled there is a different build than
  the locked Playwright expects, and the suite asks for `channel="chrome"`. No
  `pre-commit` either, so the lint cannot run at all.

  ```sh
  uv sync --frozen
  uv run playwright install chrome
  uv tool install pre-commit
  ```

  Two tests fail there whatever the setup does, the container having no IPv6 stack at all:
  the pair binding the stated-host wildcard `::` cannot run, and they are its answer rather
  than the change's — landing is from a workstation, where they do.
- **Measure before optimising and before assuming.** The cost claims in this codebase came
  from timing the real thing on `examples/gallery.html`, not from reasoning.
- **A page directory holds a copy of the layer, so re-vendor before believing it.**
  `page init` is what vendors, and it re-vendors an existing directory. Until it is run
  again a page serves the assets it was created with, so `version check --render` reads a
  runtime the checkout no longer has — and reports it clean, which is the whole trouble:
  the green is about the copy, and says nothing either way about the edit being checked.
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
