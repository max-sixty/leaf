# leaf

A page Claude hands the user, and the loop that carries their comments back. The
README covers what leaf does; this file covers how it is built and the rules that
keep it buildable.

## Soul

Everything here serves one goal: a high-fidelity connection between the agent and
the person it works with. That is why the handover is a page rather than terminal
text. A terminal has one channel and one width. A page can have as many channels as
the subject needs — a diagram, a board the user drags, two screenshots that flip in
place — and when the user comments, the reply comes back anchored to the exact
words that prompted it. The vocabulary is something to build with rather than a
form to fill in: if leaf lacks a shape a project needs, the project can add it,
because theme, registry, and widget modules all overlay from the user's own config.

Bandwidth is one axis; time is the other. A page that keeps up with the work — a
list of items ticking over as each one finishes — says more than the same list
written up afterwards, and keeping it true costs only publishing a new version.
Build toward pages that are the work itself, not reports about it.

## Stage

The project is early, and nothing owes the past anything. Nobody uses it yet, so
there is no deployment, no database, no command or flag or name anyone has learned,
and no page or log on disk with a claim on new code. Stale state is deleted and
regenerated; that is the entire migration story. Backward compatibility carries
zero weight: rename and reshape whenever the better form is clear, and treat a name
being the current one as no argument for keeping it.

That settles the trade between simplicity and robustness: take the simpler code. A
guard earns its place only where the state it defends against is actually reachable
and there is something useful to do about it. Any other guard is complexity paid
for a case that never arrives, and it misleads the reader into thinking the
impossible case was expected.

It settles your own hesitation the same way: if you can see an improvement, make
it. A change belongs to the user only when it turns on something only they know —
what the work is for, what they meant by it, what they will do with it next. A
change is not theirs merely because it takes judgement, changes what a page says,
or replaces something that was once chosen deliberately; that is the ordinary
substance of the work. The tell for this mistake is a change you worked out fully
and then reported instead of making — a round trip spent being told to do what you
had already decided.

Where data enters the system, check it once and completely: browser events at
`POST /api/event`, authored markup at `version check`, and a replayed action's
detail in the widget's own `applyAction`, because only the widget knows that shape.
Everything downstream then reads fields directly instead of asking a second time
whether they arrived.

## Shape

Claude Code and Codex both resolve `plugins/leaf/` as the plugin payload. The two
repo-root pointers are `.claude-plugin/marketplace.json` (Claude Code) and
`.agents/plugins/marketplace.json` (Codex), and the payload carries one manifest
for each host. Seven things make the product, and nothing sits between them. Six
belong to the skill, under `plugins/leaf/skills/leaf/`:

- `scripts/interact.py` — a `uv` script holding the server, the event log, the
  lint (`version check`), vendoring, and export. No daemon, no database. It is
  invoked as `leaf` through the payload's `bin/` shim: Claude Code puts the shim
  on PATH, and Codex resolves it from the active skill directory.
- `assets/leaf.js` — the runtime every page loads. One ES module owns both the
  widget layer and the comment layer, with its stylesheet in a `<style>` block
  inside the module. There is no build step.
- `assets/registry.json` — the machine's own vocabulary: the suggestion widget
  family and the layer-wide `$` keys. The renderer, the linter, and the agent's
  documentation all read the same merged registry, so none of them can drift from
  the others.
- `assets/theme.css` — the tokens, element styles, and class idioms every page
  links; the suggestion family's rules; and the source the runtime styles its own
  chrome from. One stylesheet is why a page themes as one thing.
- `assets/icon.svg` — the mark. Every served page wears it in the tab, and so
  does the published site. Its `lf-tone` element is the part the runtime paints
  the page's status onto.
- `bundled/` — the content widget families, shipped as an overlay layer with the
  same layout as the integrated layer: their registry entries, one module per
  upgraded widget, their theme rules, with mermaid and sortable vendored beside
  them. `page init` merges this layer exactly the way it merges a user's
  `~/.config/leaf/` or a project's `.leaf/`. The shipped widgets reach a page
  through the same door a user's customizations do, so every vendoring is a proof
  that the door works.

The seventh is `examples/` at the repo root — complete pages that double as the
render suite's corpus, plus `gallery.html`, which shows them all on one page
(generated; edit the examples, not the gallery).

`plugins/leaf/hooks/hooks.json` is shared too: both hosts speak its three events,
and Codex supplies `CLAUDE_PLUGIN_ROOT` as a compatibility alias. The launcher
maps Codex's thread identity into the session record that Claude Code supplies
directly. The other half of that record is the session's lifetime, and the
launcher cannot derive it from the shell: a shell tool's `$PPID` describes the
command, not the session — a pipeline leaves a shell there that exits with the
command, and the page's server would follow it down a second later. So
`session_pid` reads Claude Code's own `CLAUDE_PID`, and finds Codex's by walking
up to the ancestor process running `codex`.

`page init` vendors the whole layer into each page directory, deliberately: a page
you approved cannot change under you when the shipped defaults do. What a page
directory holds, and why each file is in it, is documented in `interact.py`'s
module docstring.

## Norms

Each of these was learned by getting it wrong, so each rule is stated with the
failure that taught it — the rule alone would read as a preference. The norms live
next to the code they bind, so opening that code is how you meet them:

- the page in the browser — the runtime, the widget modules, the theme, in both
  the integrated and bundled layers: `plugins/leaf/skills/leaf/CLAUDE.md`
- the server, the log, and the lint: `interact.py`, in its module docstring and
  beside the code each norm binds
- the tests: `tests/CLAUDE.md`
- the examples, and what the corpus owes the vocabulary: `examples/CLAUDE.md`

Four norms bind both runtimes at once, so no single directory owns them. They
follow here.

### The document is the state, and the log outranks it

When the user edits the page — drags a card, picks an option — the browser posts
an `action` to the event log, and every action replays onto every version
published after the one it was made on. Nothing anywhere stores "the current
board": the log plus the version is the whole truth. Keep it that way. A second
store would be a second thing to reconcile.

There was a second store once, and nothing named it: the log recorded the user's
state while the markup carried the author's, and the page's author was expected to
copy each user decision into the markup by hand. `version check` guaranteed that
ids survived a republish; nothing guaranteed that the state on them did. A
forgotten copy silently un-made a user's decision, and no part of the system said
a word.

So there is one writer per fact: the markup states the initial condition, and the
log records every transition after it. A version that says nothing about a
decision leaves that decision standing. The cost lands where the old design hid
it: a new version cannot quietly revise something the user acted on, because
replay would paint their state back over the revision. When a rewrite genuinely
invalidates a decision, the author says so with `restated` on the rewritten
element, which retracts what rested on it — and `version check` refuses both a
bare rewrite and an unearned `restated` (`restatement_errors`).

Taking a gesture back is the same sentence read from the reader's side. `z` posts
one event — `undo`, naming the gesture it takes back and nothing else — and every
fold and the thread reading drop the gesture it names, so the page is the version
plus what still stands. That is what a reload has always rendered, and what
`restated` already writes from the author's side; the reader now has the same word
for it. Nothing leaves the log, and nothing states a counter-gesture into it: a
card put back on the list it came from would read as a decision to move it there,
and there is no value "undecided" for any verb to carry, so a reader taking back
an accept could not have been recorded at all.

What the reader sees follows from that rather than being restated into it, and by
the cheapest faithful means. Where the log still leaves the unit a state that can
be stated — the detail a prior surviving action carried, or the placement this
version's markup arrived showing — the widget is told it, so the card travels back
under the reader's eye and the grip they were holding stays under their hand. That
is why a position record names the field carrying the order as well as the
container: a placement stated on the column alone puts a card back on the right
list in the wrong place. Where the verb records nothing there is no such state, so
the widget is rebuilt from the markup this version wrote and what survives is
replayed onto it — a reload, done to one widget. The clone that makes it possible
is taken beside the passage fences and for the same reason: the moment after the
registry lands and before the modules import is the only one at which the page
holds the author's markup and nothing else.

Both routes are chosen by a declaration and neither knows a widget's name, which
is the whole of why a settlement can be taken back at all. `accept` was final for
as long as an undo could only state a value — a fact about the mechanism, wearing
the clothes of a fact about suggestions, and written into that family's own entry
as though it were one.

One bound is real and stays: an action reaches only the version it was made
against, a later version being free to have been written around the decision. On
v2 the authored placement of a card moved on v1 is where the move put it, so the
press would be live and paint nothing. Threads are not scoped that way and must
not be, a conversation outliving the version it was opened on.

Both failure modes here are invisible to the user, so the question was never which
is worse but who can see each one. A dropped decision is visible to nobody. A
stale decision standing over rewritten content is visible to the author at the
moment they rewrite it, and only the author knows whether the rewrite invalidates
it. Route each failure to whoever can adjudicate it: the runtime preserves by
default, and discarding costs the author one word.

### One representation per concept

A passage of the page is represented as `{node, start, end}` segments, and that
one representation serves the quote search, the quote capture, the
reading-position landmark, and the version diff's block keys. When there were four
different answers to "what text is in this region", each was some other one's
bug — a selection's `toString()`, for example, returns whatever `text-transform`
rendered, so a quote captured that way could never be found again. On the Python
side, `page_passages` is the same single answer: anything that asks what a version
says slices its output (`spoken`) rather than walking the markup a second time. A
second representation earns its place only when two things are genuinely
different — an element anchor has no text to paint, so it wears an outline — never
when they are the same thing reached by different code.

One representation also means one budget, and the budget belongs to whatever is
actually scarce. Quotes were once capped at four hundred characters. That read as
economy on a log line, but it was a claim about the page, because the stored quote
*is* the passage: a reader who selected a paragraph longer than the cap got a
comment anchored on its opening words, with a highlight shrunk to match. The thing
that could not afford long passages was never the log — it was the search pattern,
one regular expression with a term per character, which V8 refuses to compile past
some length between five and twelve thousand terms. So the bound sits on the
pattern (`LEAD_CAP`), which finds candidate positions, and the rest of the quote
is walked against the text from each candidate. A cap on the wrong side of a
representation looks like thrift and spends exactly what the representation was
for.

Two readings of one element's words are the case that does earn a second
representation, because they answer different questions. `says` is what is on
screen for the user to point at, so a label a widget declared as the page's words
is included. `wrote` is what the author put in the file, so everything an upgrade
generated is excluded. The version diff wants `wrote`, and so does a widget naming
one of its own parts: a picked row's "chosen" mark is the page speaking, so it
belongs in what the user can quote but not in the row's own name — otherwise a
question that was answered reads its own answer back as part of what was asked.
Collapsing the two into one reading with a flag would have produced the same two
answers with nothing recording which is which.

### The file's reading never claims more than the page's

An anchor is captured in two places and resolved in one. `selectionAnchor`
captures from the DOM in the browser; `leaf comment` captures from the version
file; and `resolveAnchor` is the only thing that ever searches. The two captures
are not two answers to "what does the page say here": both write the same
collapsed text under the same rules, so whatever the file's reading holds, the
page's reading holds too.

The file alone is not enough, because the user moves the page as well as the
author: a decision retires a settled suggestion's losing slot, and an edit puts
the user's words where the authored body was. So both readings follow the log
rather than the raw markup, and each refuses to quote into content the log has
dropped, naming the act that dropped it. The keys that carry this, and the shape
of each reading, belong to `_PassageParser`.

Keeping this true is not free. A board's module prepends each column's heading to
the column's text, so a quote running from the lede above the board into its first
card matched a file the rendered page no longer resembled, and anchored on
nothing. A milestone's chips insert text mid-element, where no edge-of-element
keyword can describe the difference. So where the file cannot model what a module
writes, the reading stops rather than guesses: the registry declares what the file
can model, a fence covers the rest, and a quote across a fence is refused when the
comment is written, instead of detaching later in front of the user. The browser
indexes those same fences before upgrades run and clips captured context to them
afterward, so neither capture claims neighbouring text the other side cannot
confirm. A widget that writes words of its own either declares them or stays
fenced.

Context identifies an occurrence only when exactly one candidate confirms it in
full. When no candidate does, a quote whose text occurs once on the page can still
identify itself; a repeated quote cannot, and it detaches rather than falling back
to document order — an offset or an ordinal is not evidence that a revised copy is
the one the user meant.

### The widget list is never closed

The vocabulary grows by adding an entry in `registry.json` and a module beside
it, and no code may assume it has seen the whole list. A consumer that branches on *which
widget* it is looking at stops at the widgets it was taught, and it fails quietly
rather than loudly: it keeps working perfectly on those while silently doing
nothing for the next one, so the bug surfaces as a feature that was never wired
up rather than as an error. So every consumer works from what a registry entry
declares. Where some widgets want a behaviour and others don't, the behaviour
becomes an `x-` key those widgets declare and the consumer dispatches on; no
branch anywhere reads `lf-diagram` and does something particular. This binds the
runtime, the lint, `version check --render`, `version export`, and the skill's
own prose alike. The test is whether a twelfth widget would touch anything beyond
its own module and entry; wherever it would, the missing piece is a declaration.

Most widgets are things a page contains, and those stay anonymous outside their
own module. A few could be part of the machine itself, and core would name those
outright — today there are none. The suggestion is where the temptation kept
landing. Three facts read as sentences about the suggestion — the log settles it;
a version honoring the decision may drop the ids it retired; thread markup
refuses one — and every one turned out to be about a relation the registry can
state. `x-retired-when` names the outcome under which a slot leaves the page, and
`x-parent` names the widgets whose decision reaches it, so a holder/slot pair is
the entire definition of a settlement (`retirement_slots`), and a family a
project declares gets all of it the day it declares. What the pair cannot say is
what an *unanswered* suggestion means when the author takes it back, so the
widget says that itself (`x-withdrawn-as`). One name is left in core and it is a
member's, not the mechanism's: `suggestion_errors` holds the family's markup to
one slot of each kind, at least one, and no nesting — cardinality being the one
thing no key states, and those sentences meaning nothing for the twelfth widget.

Opening the pair to any family carried an obligation along with it. The
settlement mark (`data-lf-state`) was the suggestion module's own write, so
generalizing the relation turned it into a duty every holder module had to
remember — stated in the scaffold and the key table, enforced nowhere — and a
module that forgot would split the page's reading from the file's, with
`leaf comment`'s refusal as the only symptom, versions later and nowhere near
the mistake. Nothing about the mark ever needed a module: the relation and the
log both sit in the layer's hands, so replay paints it (`markSettled`,
leaf.js), and a scaffold module that does nothing on settle still yields a page
whose readings agree. The visible half followed once the same question was put
to it: hiding the retired slot needs only the relation too, so the layer marks
the slot (`renderRetired`) and one theme rule hides it, where the shipped
family's by-name rules had been the closed list wearing CSS's clothes. What is
left to a module is its own choreography, and the render gate reads the result
(`RETIRED_SLOTS`), comparing mark and shown words against the log's decision —
the check for what no default can see. Before gating an obligation every
adopter must remember, ask whether the declaration already states enough for
the layer to do it once.

Which kind a widget is has one question behind it: is this one of the ways leaf
works, or one of the things a page can hold? Convenience is not an answer; a
widget joins the first set only when the loop is written in terms of it. The
banner's "✓ Accept all" control was once a fourth name in core and never deserved
it: it counted `lf-suggestion:not([data-lf-state])`, a selector with the shape of
a mechanism and the substance of one member, so the count was perfect for that
tag and silently zero for every question, pick, and blocked task beside it. It
became `x-awaits`, which now feeds the banner's count, the key that steps through
open asks, and the `?` overlay. A name core can only defend because one widget
got there first is a declaration waiting to be written. And declare the general
property, not the particular widget — `x-upgrade` says "a module enhances this
tag", not "mermaid needs loading" — or the special case has merely moved into the
registry. The bar is real: an `x-` key the log records becomes a forever
contract, carried by the vendored layer's stamp (`$events`). That is an argument
for finding the general shape, never for reaching past the registry.

A boolean key is an enumeration whose second value was already chosen, by
whichever widget declared first. `x-wide: true` was read as "may stand wider than
the column" but in practice meant "and fills whatever box it is given" — the
board's answer to a question the key never asked. What the theme actually has to
decide is how far the box may reach, and with nothing to read, it decided once,
at the one width the whole vocabulary then shared. A diagram's graph is drawn at
a size its source determines, so held to that shared width, a 1533px sequence
diagram was cut off at 1080px in a window with room for all of it. Nothing had
named a widget and nothing had reached past the registry, so every gate that
catches those violations had nothing to see; the failure surfaced three widgets
later, as the page's reader saying a diagram was cut off. The kinds are explicit
values now (`box`, `drawing`). Where a key's `true` carries a claim the entry
never states, that claim is the value the key should have had.

The stylesheet is under the same rule, because a selector is a consumer too, and
a list of tags in CSS is the closed list wearing different clothes. A box that
frames what it holds declares so (`--lf-frame`) in the same rule where it draws
the frame, and the layer reads that one declaration for both things that follow
from it: the style query that trims what the box would otherwise paint as extra
inset, and the one that withholds the extra room a wide exhibit may take — since
inside a framed box, the box rather than the page is what holds the exhibit. A
project's own card gets both behaviours by making the same declaration. (The full
norm lives in `plugins/leaf/skills/leaf/CLAUDE.md`.) The room rule began as a
list of tags, because the second reading looks impossible: `main` declares the
frame too — the column is a padded box like any other — so read plainly, the
declaration would withhold wide-exhibit room from every exhibit on every page.
But the column is one box, and one line on it hands the room back to what it
holds — which is what the gate had been saying all along by walking up no
further than `main`. While the two lists stood, they cost what
lists cost: every tag in them declared the frame anyway; five boxes that declared
the frame were in neither list, so a diagram inside a metric stood 216px across
the metric beside it; and the one listed tag that declared nothing, `figure`, was
withholding room while drawing no box at all. When a declaration looks like it
can answer only one of two questions, measure it against the second before
writing the list.

A fact the whole layer shares belongs to the layer, under a `$` key, not to
whichever widget needed it first. The vendored tokenizer's language list lived in
`lf-code`'s `language` enum, and from there the only way the lint could read it
was to name `lf-code` explicitly: the wrong home was the cause, and the reach by
name only the symptom. Moving the list to `$languages` is what let the widgets
declare instead — `x-language` now names the attribute that carries a language.
The tell is a consumer indexing past the entry it was handed. The second tell is
what that consumer does when the reach comes up empty: a list read from the wrong
place is a list that can move, and a check that stands down on `if not known`
retires itself the day it does. Layers compose `$` keys member by member, while a
tag's entry replaces whole, because the two are different kinds of thing: a
schema is one contract whose halves cannot mix, and a shared fact is a namespace
whose members stand alone. Under replace-whole, a project that declared its one
idiom vendored a `$idioms` holding exactly that idiom, and `page catalog`
silently dropped the other ten — the natural act of declaring a shape cost the
agent the catalog it authors from. The stamp does not care about the grain: its
gates read the merged result (`merge_layer_entries`).

An `applyAction` implementation states an absolute placement, never a relative
mutation, because the poll replays every action — including the sender's own,
which must therefore be a no-op when reapplied. The verb, its detail schema, its
fold unit, and its record form are declared in the registry (`x-state`), not
known privately to the module: absoluteness is what makes the user's standing
state a fold over the log, and the declaration drives every consumer of it
without teaching any of them a widget by name. For a long time nothing checked
this, and every gate passed a relative implementation, because there is nothing
to see: it renders perfectly, and the cost arrives later, on the poll that
replays the sender's own action on top of the state their gesture already
painted. So the render gate asks the page rather than the code
(`RELATIVE_REPLAYS`): it re-applies the standing state, whole and in the log's
order, and reports what moved — at which widget, with the fix — reading the
result twice: `shallowSigs` for the markup state, which excludes text on purpose,
and the unit's declared record form for the words. Checking each action on its
own would be a different check and a wrong one, since two cards dragged to the
head of one column fold to two standing moves. What the gate cannot reach is a
verb nobody has used yet; the actions it replays are the log's.

A verb's record form is also the whole of what a module may write in the author's
namespace. An entry's `additionalProperties: false` closes that namespace, and
the file lint holds every version to it — but a widget is a second writer the
file lint cannot see. So a module writes an author-namespace attribute only where
a record form declares it (`chosen`, `status`); everything else goes on chrome
the module built itself, in the platform's vocabulary or under `data-`.
`lf-options` had two attributes of the other kind, and both were silent:
`answered` recorded a verb only a thread can post, and `open` recorded which way
this one tab last left a disclosure — a fact no version carries at all. Each was
a second copy of something the module already stated on the control that carries
it, and the one reader that saw them believed them: `shallowSigs` excludes
exactly the attributes no version can assert, so a widget writing beside that set
gets counted as state the author wrote. `version check --render` asks the
rendered page for the rest (`UNDECLARED_ATTRS`), the rendered page being the only
side the second writer shows on.

## Working on it

- **Tests are integration tests in a real browser.** What a test must assert, and
  the ways one can pass vacuously, are in `tests/CLAUDE.md`; what each file
  covers, and the commands, are under "The suite" below.
- **A cloud container has none of that, so set it up first.** The suite needs the
  Chromium headless shell that matches the Playwright version in `uv.lock`. Two
  end-to-end launcher tests also need installed Chrome. There is no `pre-commit`
  either, so the lint cannot run:

  ```sh
  uv sync --frozen
  uv run playwright install chromium --only-shell
  uv run playwright install chrome
  uv tool install pre-commit
  ```

  Two tests fail there whatever the setup does: the container has no IPv6 stack,
  so the pair that binds the stated-host wildcard `::` cannot run. Those failures
  are the container's answer, not the change's — land from a workstation, where
  they pass.
- **Measure before optimising, and before assuming.** The cost claims in this
  codebase came from timing the real thing on `examples/gallery.html`, not from
  reasoning about it.
- **A page directory holds a copy of the layer, so re-vendor before believing
  it.** `page init` is what vendors, and it re-vendors an existing directory.
  Until it runs again, a page serves the assets it was created with, so
  `version check --render` reads a runtime the checkout no longer has — and
  reports it clean. That green is a statement about the stale copy; it says
  nothing either way about the edit being checked.
- **Merge locally.** The project is not at the stage of PRs: landing is
  `wt merge`, a direct squash merge to main, never a PR — including for
  background jobs, whose harness default is a draft PR. This settles the *form*
  of a landing, not *whether* one was asked for: a job once read "merge locally"
  as standing permission, and unreviewed work landed on the strength of it. A
  finished branch waits for the user's go-ahead unless the task said to land.
- **A session loads each host's cached copy, not the checkout.** Both repo-root
  marketplaces point at `plugins/leaf/`, and both hosts install from GitHub main,
  so a payload change reaches a session only once it is pushed — and it reaches
  the *next* session, not the one that pushed it. Neither manifest declares a
  version, deliberately: that string is Claude Code's cache key, so an unchanged
  version leaves the old copy in place while the updater reports it as latest.
  With no version, the key is the commit, and Claude Code's periodic marketplace
  sweep installs each pushed commit on its own; nothing needs running. Codex
  installs from a marketplace snapshot it fetches separately and does not sweep,
  so a change reaches it through `codex plugin marketplace upgrade leaf` and then
  `codex plugin add leaf@leaf`.

### The suite

`test_interact.py` exercises the lint, vendoring, publishing, catalog, export,
thread-markup validation, and the anchors `leaf comment` writes by reading a
version file. `test_render.py` loads the shipped examples in a real browser, in
both color schemes, and asserts what a static lint cannot reach: every widget
upgrades into a box with usable size, the document and the comment panel scroll
in separate regions, the comment box grows without any script sizing it, and
neither pressing a control nor news arriving on its own moves the controls beside
it. One journey test drives the whole loop through the real UI — select a
passage, comment, drag a card, follow the next version, find the comment still
anchored — and pins the event log it leaves behind. `test_product_page.py` holds
the pages under `docs/` to the shipped theme and widget registry.
`test_site.py` builds the site and reads it back: the theme it serves is the
shipped file, each example stands up as a live page that takes a comment and
holds a decision through a reload, both palettes reach the site's own layer, and
no page scrolls sideways on a phone. Playwright drives the pinned Chromium headless
shell installed with the developer environment.

The suite runs in the environment `pyproject.toml` names and `uv.lock` pins, and
that environment is the developer's only. leaf itself declares its dependencies
in `interact.py`'s PEP 723 header — the header is what installs them, with no
build step — and the project file leaves that alone. The tests need the same
packages anyway, because they load `interact.py` by path.

```sh
uv run pytest tests
```

That everyday command needs no network after setup. It runs one shipped page through
the browser gate, so one of `pyproject.toml`'s eight workers launches Chromium; the
other tests cover the static lint, server, vendoring, and product pages. The fixtures
relocate the two XDG directories leaf reads (`config_home`, `state_home`) and leave the
rest of the home alone, so every `leaf` the suite shells out to finds the uv cache the
developer already has.

`test_render.py` and `test_site.py` are the browser integration suite. A browser change
runs its focused test with `--run-nightly`; CI and `wt merge` use the same flag for the
complete suite. The complete run has a network because the installed launcher's
browser path may resolve Playwright outside `uv.lock`:

```sh
uv run pytest tests --run-nightly
```

Ruff and prettier run from `.pre-commit-config.yaml`, which says what each covers
and why. `wt merge` runs that set and then the suite as pre-merge hooks
(`.config/wt.toml`), and refuses a tree that doesn't pass;
`.github/workflows/ci.yaml` runs both again on main and on every pull request.
Before then:

```sh
pre-commit run --all-files
```

CI is also the only place either gate meets a platform other than macOS, and the
platforms disagree about exactly the things a browser test measures: how wide a
system font sets a word, whether a scrollbar takes a gutter out of the window.
`scripts/linux-suite.sh` runs the suite the way CI runs it, in a container carrying
the pinned headless shell, installed Chrome, and the runner's fonts. It takes pytest's
arguments and needs a Docker daemon that can run linux/amd64:

```sh
scripts/linux-suite.sh
```

### Driving a page by hand

`scripts/preview.py [example]` serves a shipped example as a real page, vendoring
fresh each time; `examples/CLAUDE.md` covers what it lays in and why. For a page
of your own, run `page init` on the directory and serve it in-process from
`interact.handler_for(page_dir, token)`, the way the fixtures do, opening the
page with the key in the query string (`?t=…`). `server start` is different: it
puts a live page behind the session, and the loop's hooks then hold the session
to watching that page.

### The website

`scripts/site.py` assembles <https://leaf.page/> into `.tmp/site`, and
`.github/workflows/publish-site.yaml` runs it on every push to `main` that
touches the pages, the examples, or the layer. The docs pages are copied with
their checkout-relative paths substituted: the stylesheet and the icon a page
wears become the site's own copies, every other path into the payload becomes a
GitHub link, and a link to an example names the page directory it is published
as. The examples are published live: one vendored layer at the site's root, each
example at `examples/<name>/versions/v1.html`, and a `/leaf.js` that loads
`docs/session.js` in front of the vendored runtime. The event log then lives in
the reader's own tab, so the banner, the comment panel, and every widget work.
What a static host cannot supply is an agent reading that log, and the page says
so. The build resolves every local link it wrote and refuses a site holding one
that reaches nothing.

```sh
scripts/site.py
```

`docs/demo.gif`, which the README and the site both wear, is written by
`scripts/record-demo.sh` — it drives a session through the shipped server and
Chrome and records the result.

### The vendored bundles

Code blocks are colored in the browser from
`plugins/leaf/skills/leaf/assets/vendor/highlight.esm.js`, which upstream doesn't
ship in a form a page can import — so it is bundled here.
`scripts/vendor-highlight.sh` rebuilds it, reading the language list out of the
registry's `$languages.names` so the bundle cannot offer a language the lint
rejects. Add a language there, then rerun the script.

Thread messages render their Markdown in the browser too, from
`vendor/marked.esm.js`. Upstream ships that one as a single dependency-free ESM
file, so `scripts/vendor-marked.sh` is a copy at a pinned version, not a build.
