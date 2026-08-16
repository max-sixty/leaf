---
name: leaf
description:
  'Presents a concept, design, decisions, findings, or a run of work in progress as an
  HTML page the user comments on in the browser — the agent watches for comments, replies
  in-thread, and ships revised versions as the work moves. Use instead of a wall-of-text
  plan or a handed-over .md report. Triggers: "explain this in HTML", "write it up as a
  page", "write up the findings", "I want to see the options", a run of work whose items
  the user will want to watch go by, or an intricate design that needs review.'
allowed-tools:
  - Bash(leaf:*)
---

Present a concept, decision, findings, or work in progress as an HTML page the user opens
in a browser and works in place — a leaf: they select text and comment, decide and
edit through what the page offers, you reply in-thread and ship revised versions, and a
banner shows whether you're working or waiting on them. Reach for it instead of a
wall-of-text plan or a `.md` report handed over by path, when a complex change needs
shared understanding or a decision before code, when a diagnosis or review is itself the
deliverable, or when a run of work has items the user will want to watch go by. With
nothing named below, the subject is whatever the session is about — the plan you were
about to give, the design under discussion, the findings you just gathered, or the work
you are about to start.

$ARGUMENTS

## Soul

A page is the highest-bandwidth thing you can hand someone, so use it. Two habits carry
most of that.

**Shape follows the subject.** Ask what the subject *is* before writing about it. A set
of things renders as things — `lf-milestones` for work with stages, `lf-board` for work
the user re-orders, `lf-options` for a decision, `lf-metrics` for what was measured —
and the prose says what only prose can. Five paragraphs about five items hand the reader
the job of rebuilding the list you dissolved; the same five as items, each carrying its
own state, are read at a glance and commented on one at a time.

**A page that asks leaves somewhere to answer.** Anything you want a decision on ends in
a `lf-options … choose`, wherever on the page the question falls. Give each alternative a
`<strong>` title and its case — a sentence, or paragraphs with a `<dl class="facts">`
rail, and the evidence it turns on: a `lf-shot` pair, a diagram, a figure, written into
the option rather than into a section beside the group. The options stack as full-width
cards, so the reader reads the case and presses in the same place. Where the alternatives
are whole sections of the page rather than cards, let the group be bare labels naming
them (`for="<section id>"`), which renders as a compact list; `multiple` where more than
one can win. Every such group carries a box for words, so "none of these" and a pick's
why need no separate gesture. A page presenting five candidates in prose and offering
nothing to press has handed the reader a document where it meant to ask a question.

**The page keeps up with the work.** A page is not only a thing to approve before the
work starts. Where the work is yours to do and the page tracks it, publish a version each
time the state moves — an item to `active`, then `done`; a finding added as you find it —
and the user watches it happen instead of reading about it afterwards. Their browser
follows each new version by itself, deferring only while they are mid-comment or
mid-drag, so a version costs them nothing. Ship one when an item's state actually
changes rather than at every step it took, and let
`leaf status <page> working "<detail>"` carry the finer grain in between. Keep
`leaf wait <page>` running while you work, in the host-specific loop below: a comment
that lands mid-flight ("skip that one") then reaches you at the next step rather than at
the end, and the banner reads as working throughout.

Where other sessions do the work — workers reporting to a page one orchestrator
publishes — they move it with `leaf report <page> <widget> <verb> name=value…`
instead of a version: a declared state change (a `lf-task`'s `status`, per the widget's
x-report entry) that the page paints live as provisional news, marked as a report until
a version answers it. It wakes the page's watcher like a user event, and the next
version adjudicates it: write the reported state and publishing absorbs the report by
id; keep your own state by marking the element `overruled` (why in the note); leave the
markup unchanged and the report keeps painting. `version check` refuses a version that
contradicts a standing report it never names — `page catalog`'s `$report` has the rest.

## Setup

The page lives in its own directory, conventionally
`~/.local/state/leaf/pages/<slug>/`, where `<slug>` is a short kebab-case name
for the topic (`migration-options`, `auth-diagnosis`) — every leaf command takes the
page directory explicitly, so any location works. The directory survives the session
and is where every version, the event log, and the vendored widget layer live. It is
live state, not an archive: content with a life beyond the page leaves through
`version export` or a copied version, to wherever that content belongs.

The launcher is `${CLAUDE_SKILL_DIR}/../../bin/leaf`. Resolve
`${CLAUDE_SKILL_DIR}` to this skill's directory and use that launcher for every command
shown as `leaf` below. Claude Code also puts the same launcher on PATH.

```bash
leaf page init <page>                    # create layout, vendor the widget layer
leaf page catalog <page>                 # widgets and theme idioms
leaf page media <page> <file>…           # add images; print each page path
leaf page state <page>                   # where the page stands, as JSON
leaf version check <page> --render       # browser gate, once per page
leaf version publish <page> --version 1 --text "<changelog>"
leaf version export <page> -o <file>     # standalone HTML copy
leaf server run <page> [--host NAME]     # long-running; prints the URL
leaf status <page> working "<detail>"    # or: waiting "<what you want back>", idle
leaf report <page> <widget> <verb> name=value…  # a worker's state change, e.g.
                                             #   report <page> t-parser status status=review
leaf wait <page>                         # prints unacknowledged user events and reports
leaf ack <page> <seq>                    # complete, untruncated output reached context
leaf comment <page> --quote "<passage>" --text "…"
leaf reply <page> --to <id> --text "…"
leaf events <page>                       # full event log
leaf transcript <page>                   # the exchange as Markdown
```

If the resolved launcher does not exist, the plugin payload is incomplete; say so. In a
repository checkout it lives at `plugins/leaf/bin/leaf`.

1. Run `page init <page>`, then read `page catalog <page>`. It prints the vendored
   registry (widget schemas with examples) and the theme's class idioms, which vary per
   project.
2. Write the page as `<page>/versions/v1.html` (conventions below).
3. Start `server run <page>` as a long-running background command: a background task in
   Claude Code, or a unified-exec session in Codex. Hand over the URL it prints exactly
   as printed: the key in it is what opens the page. Address, key and port are all stable
   per directory, so the URL survives a restart.
4. Run `version publish <page> --version 1 --text "<changelog>"`. Publishing checks
   the version first and refuses a failure, so a half-written or broken file is never
   live in the user's browser. Before the URL first goes out, run the browser gate
   too: `version check <page> --render` (see "Before the URL goes out"). Then hand the
   user the URL with a one-line orientation (select text to comment; on a sign-off
   page, "✓ Looks good" approves) and enter the loop.

## When the deliverable is the file

`--export` in the argument asks for the file rather than the live page: steps 1, 2 and 4
as above, then `version export <page> -o <file>` and hand back the `file://` URL. No
`server run`, no `leaf wait`, no loop — the page directory is still built, so the
same page can be served later without being rewritten, and the Stop hook covers only
pages that were served or waited on, so it has nothing to say about this one. Write the
file wherever the project puts things for the user to open.

While a page is live the same command answers "give me a copy": `version export` writes
any published version, as many times as asked, and the page carries on around it. The
copy is the page as the browser drew it, with the user's decisions replayed onto it, the
comment layer left behind, and every control a handler answered gone with it — an
exported decision says what was picked and offers no pick, so a lede telling the reader
to click belongs on a page you are going to serve.

## Page conventions

- Pages are complete HTML documents. `version check` enforces the scaffold — exactly one
  stylesheet link (`/theme.css`) and one external script (the `/leaf.js` module);
  the rest of the head (title, charset, the `lf-*` metas below) is yours:

  ```html
  <!doctype html>
  <html lang="en">
  <head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>…</title>
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
<link rel="stylesheet" href="/theme.css">
  </head>
  <body>
  <main>
    …authored HTML and widgets…
  </main>
  <script type="module" src="/leaf.js"></script>
  </body>
  </html>
  ```

- **The theme owns the look.** Palette, type, spacing, headings, tables, code,
  `details`, and the class idioms all come from the vendored `theme.css` — write plain
  semantic HTML and it gets the voice for free. A page-local `<style>` is the escape
  hatch for genuinely page-specific presentation, not for re-declaring the palette.
- **Widgets are `lf-*` elements**, validated against the vendored registry: attributes
  carry scalars (enums, flags), children carry prose, an item's title is a leading
  `<strong>` child. Every `lf-*` element takes an explicit end tag — `<lf-diagram id="flow"/>` is
  rejected because HTML ignores the slash. A `data`-bodied widget (`lf-diagram`) holds
  its notation in a `<pre>`, HTML-escaped — `&` as `&amp;` first, then `<` and `>`,
  or a body carrying entity text is silently decoded — the whitespace is load-bearing,
  and `<pre>` is the only thing in HTML that says so to a tool with no stylesheet to
  read. The catalog is the authority; don't invent tags or attributes.
- Give every section, major block, and widget item a stable, meaningful `id`: comments
  anchor to the nearest `id`, and an anchor survives into a new version only where its
  id does. The reader's place on the page falls back to those same ids when the text
  around it was rewritten. Keep ids stable across versions so neither detaches, and out
  of the `lf-` prefix, which the runtime coins its own ARIA targets in.
- **Edits to already-seen content ship as suggestions.** Changing a passage the reader
  has already seen — a rewrite, a deletion, above all the fix a comment asked for —
  goes in a `lf-suggestion`: `lf-old` carries the current markup verbatim (its ids
  ride there), `lf-new` the proposal, and the user accepts or rejects it in the
  margin. Fresh content — the first version, a new section, a restructure — is
  written straight, and comments cover it as usual. Name the answered thread
  with `resolves="<comment id>"` so accepting the fix closes the thread too.
  Deciding isn't the only answer: the proposed words are ordinary page text, so the
  user can select them and comment instead — worth saying where the page
  introduces its first suggestion, since ✓ and ✗ are the only visible affordances.
- **Who writes the words picks the shape.** Three things change text once the page is
  in front of the user, and they differ by seat rather than by style. Prose you own, rewritten
  after the reader has seen it: a `lf-suggestion`, theirs to accept or reject. A
  passage that is theirs to word — a release note, a summary in their voice: a
  `lf-draft`, which nobody decides and the next version carries verbatim. Their
  wording for prose you own: a suggestion comment, which reaches the log for you to
  take or answer. So a draft never sits inside a suggestion — its words aren't yours
  to propose — and a suggestion carries markup, not a widget's own state: proposing a
  card's column or an option's pick has no form yet.
- The runtime injects the status banner, comment sidebar, version picker, keyboard
  shortcuts (`?` in the browser shows the reference), and a left panel listing the
  machine's live leaves with what each is doing or waiting for; don't build page UI
  for any of those. It also collects what the page is still waiting on the reader for —
  an undecided suggestion, a `choose` group with no pick, a task at `review` or `blocked`
  — into a banner count they can step through with `a`, from the vocabulary's own
  declarations (`x-awaits`). So write the asks as widgets and let the count find them;
  a hand-written "still open" list beside them is a second copy that goes stale the
  moment one is answered.
- **Sign-off is declared, not assumed.** A page that asks for the user's assent — a
  plan, a design, a proposed change, anything where approval unblocks work — declares
  `<meta name="lf-review" content="sign-off">` in the head, and the
  banner offers "✓ Looks good" — which approves and leaves the page live, so the
  work it unblocks goes on in front of the user. A page that only informs (a status
  report, an incident chronicle) omits it: it takes comments only, and the banner
  carries no terminal control at all, because there is nothing there for the reader
  to answer. `version check` rejects unknown `lf-*` metas and any other `lf-review`
  value.
- **Announce interactivity in prose.** Someone new to the page won't guess from a grip glyph
  or a hover cursor that a board takes drags or an options group takes clicks — the
  sentence introducing the widget says it ("drag cards to reprioritize; your edits
  reach me directly", "click an option to decide"). The widgets stay chrome-free on
  purpose; the page's own words carry the affordance.
- **Never lose user text.** A central tenet of the comment layer: drafts (the general
  box, each reply, the selection composer) survive navigation, reload, version switches,
  and server death; only a successful send clears them.
- **Diagrams are graphical, never ASCII.** Flow, sequence, and state diagrams go in a
  `lf-diagram` (mermaid source body); reach for hand-drawn inline `<svg>` only where
  layout must be bespoke, drawn from the theme's tokens, with labelled nodes and
  arrowheaded edges. Never box-drawing (`┌─┐ │ ▼`) in a `<pre>`.
- **Name a code block's language and it gets colored.** Two shapes, by what the block
  is for: `<pre><code class="language-python">` for a literal the user selects and
  quotes — a command, a config, a snippet of output — and `<lf-code language="python">` for
  a walkthrough, which adds line numbers, `hi` ranges, and `lf-note` remarks anchored at
  a line. The language names are the same set either way, `page catalog` lists them, and
  `version check` refuses one outside it. Nothing is inferred from the text, so a block
  whose body isn't source — a transcript, a stack trace, a log — simply says nothing
  and stays plain. A `lf-diff` needs no language and takes none: a unified diff spans
  files, so each file's own path says what it holds, and a path naming nothing leaves
  that file plain like any undeclared block.
- **Make references clickable.** Write source locations as ordinary semantic links,
  such as `<a href="https://host/repo/blob/main/path/to/file.py#L88"><code>path/to/file.py:88</code></a>`.
  Render ticket keys, MR/PR numbers, and URLs as real `<a>` links, not plain text.
  Inside a `<lf-specimen>` a fictional URL is fine.
- **Keep wide content inside the column** — 720px in the default theme. The comment
  layer anchors to on-screen text, so a page that scrolls sideways is hard to comment
  on.
  Give any element that can overflow (a `<pre>`, a `<table>`, an `<svg>`)
  `max-width: 100%` or `overflow-x: auto`, and size diagrams responsively rather than a
  fixed pixel width wider than the column. `version check` flags fixed widths that
  exceed it.
  Widgets whose width is their content's — a board's columns, a diagram's graph — stand
  wider than the column by themselves where the window has the room, because their
  registry entry declares it (`x-wide`, in `page catalog`). That is the whole of the
  mechanism: nothing is authored for it, no page states a width, and a page's shape
  follows what it holds. Write the widget and let it take the room.
- **Images come in by reference, never inline.**
  `leaf page media <page> <file>…` copies files into the page directory and prints
  the `src` to write; that path is the only form an image takes on a page, because a
  base64 `data:` URI is more bytes than you can usefully type and it would sit in every
  version forever. Each file is named by the hash of its bytes, so two versions showing
  one screenshot share one copy and a version the user approved cannot come to show
  them something else. `version check` refuses a `/media/` reference the directory
  can't answer.
  Where the deliverable is a change to a UI with a real *before* state, let the reader
  compare the renders rather than describing what moved: a `lf-shot` holds the pair and
  flips between them in place. Capture both states at the same viewport (the
  `/playwright-cli:playwright-cli` skill drives the browser; render the base commit in
  a second worktree rather than stashing). Say in prose what changed — a downscaled
  full-page shot shows that something moved and not what, and the column is 720px, so
  crop to the part that moved wherever the change is smaller than the page.
- **Show real content as evidence; quote invented content in a specimen.** Prefer
  putting the actual file contents, diff, or output behind `<details>` over
  paraphrasing it. An example that merely exhibits syntax or a widget goes in a
  `<lf-specimen>` — its gutter marks the region as quoted rather than spoken, and
  interactive widgets inside take no input — with visibly fictional content: real
  project content in an example gets read as a live proposal.
- **Show the destination, not the journey.** Explain the concept as it stands — total
  cut-over. Don't spend content on what was considered before or how you got here.

## Keeping the page current

A page shows where its topic stands now, with what came before still on it. That is
"Show the destination, not the journey" over time: the journey grows as the work does, so
v1's destination — four options laid out for a decision — is the journey by v4, once the
decision has been made and applied. Leaving it at full height in the order it was written
turns the page into the record of the investigation, and the user has to work the
present out of that.

Each version is therefore a rewrite toward the present. The body carries what is live —
the question in front of the user and what they need to answer it — and the lede says
what the page is asking now. A section the topic has moved past goes to a `Settled`
section at the foot: `<h2>Settled</h2>`, and under it one `<details>` per retirement, its
`<summary>` naming the question and what closed it (the option picked, or the section that
superseded it). Nothing is deleted. What retires moves intact, ids and all, so the anchors
hold and `version check` passes, and a user who wants the argument behind a settled
question opens it and finds what they read before.

A `lf-options` group has the same move built in. `settled` collapses it to one line naming
the pick, with every option behind a disclosure; the user can open it, disagree, and
pick again. Reach for it where a decision retires inside a section that stays live; a
section retiring whole takes its groups with it, marked the same way.

Retiring is not revising. The words don't change, so it is neither a `lf-suggestion` nor
grounds for `restated` — relocating a group the user picked in is a version agreeing
with them.

Time it by what is still moving rather than by what is finished. A decision stays live
while you are applying it and settles once nothing is revisiting it, usually a version or
two on, and a section the user is still commenting in stays in the body until that
thread closes.

## The loop

Whenever you hand over the URL or finish a round of work, run
`leaf status <page> waiting "<what you want back>"`, then enter the loop for the
current host:

Every handover message carries the page's URL again, so the user can open the page
from the turn in front of them.

- **Claude Code:** start `leaf wait <page>` as a background task and end the turn.
  Its completion returns as host input: an idle session starts a turn, while a working
  session receives it between tool calls. Restart the background wait after each batch.
- **Codex:** send the URL to the user in an intermediate update before waiting. Start
  `leaf wait <page>` in unified exec, retain the returned session id, and keep the
  current turn active. Where the user owns the next move, poll that exact session
  with empty `write_stdin` calls and long yields until it returns. Where you are working,
  leave the same waiter running, continue the work, and poll it between tool calls or
  milestones so a comment can change the next decision. Never detach the wait and never
  end the turn expecting its completion to start another one: Codex has no unprompted
  completion delivery. Start a fresh wait session after each batch and retain its new id.

While `leaf wait` runs, the banner reads "<agent> awaits" and puts the `waiting`
detail after it — the page's own line about what it needs from the reader. Write the
thing you want back, in one short clause ("pick a storage engine", "check the two
failure modes against what you saw"), rather than restating that you are waiting; the
line shares a row with the page's controls and ellipsizes when they need the room. A
page that asks nothing declares no detail, and the banner offers "select text to
comment" instead. The same clause is what a reader sees against this page's name in
every other leaf's panel, which is where they pick which of several pages to
come to — so name the ask, not the page's subject, which the title beside it already
gives them.

The wait can stay open as long as the user takes, and exits when they comment, reply,
resolve, approve the page or end the leaf, or edit an interactive widget (a drag on
a `lf-board` arrives as an `action` event) — or when a worker session posts a
`leaf report`, which joins the same batch — printing the unacknowledged events
as JSON lines. Printing is deliberately not receipt: a
detached process can finish without its output ever entering model context. As soon as
a complete wait result enters context, run `leaf ack <page> <highest-seq>` before
interpreting or handling it. If the wait output was truncated at all, acknowledge
nothing: run a new wait with enough output capacity to receive the whole batch. A scalar
cursor cannot represent a missing line in the middle. Acknowledgement is monotonic and
idempotent; an event posted between wait and ack has a higher sequence and remains
pending. Until ack, the next wait prints the batch again. Reading the full log with
`leaf events` does not acknowledge it. User comments exist only through the browser;
`leaf comment` posts as you, never as them.

A wait result while the page already says `working` leaves that status untouched;
`handoff` dates only a pickup from a non-working state.

For each acknowledged batch:

1. Run `leaf status <page> working "<what you're doing>"` and refresh the detail at
   each milestone. The banner shows it live, and reads a state left unrefreshed long
   enough as the agent having gone quiet.
2. Address every event `leaf wait` printed. Each is JSON carrying the server-minted
   `id` that `leaf reply --to` takes:
   - **A comment**: `leaf reply` in-thread, and change the page where the comment
     warrants it — usually both. A reply's `--text` is brief Markdown — lists, `code`,
     fenced blocks, a table, bare URLs arrive as links — and every raw tag in it
     renders as its characters: write `<T>`, `<div>`, or a `lf-` tag in prose and
     the user reads exactly those words. Point at the page with an ordinary
     Markdown fragment link — "pick [the channel decision](#d-channel)" — and the
     words carry the reader to that element, opening whatever tab or settled group
     hides it. Reach for one whenever a reply names a part of the page: telling
     them where to look costs a sentence they then have to act on, where a
     reference is the act. Nothing checks the id, so keep it right; one this
     version hasn't got renders detached, like a quote whose passage left the page.
     To put a widget in the thread (a small
     `lf-diagram` explaining a fix renders live there), pass its markup as `--markup`,
     which renders after the text. `leaf reply` validates it against the vendored
     registry and rejects what `version check` would, and a widget's ids must be
     fresh — it refuses ids the page or an earlier message already uses, and
     `version check` keeps later versions off a reply's.
   - **A suggestion** (a comment with `"suggestion": true`) proposes replacement text
     for its quoted passage: take it verbatim into the next version, or reply with
     why not — never silently rewrite it.
   - **A page-widget action** is the user editing the document through a widget — a
     board drag arrives as `{"kind": "action", "widget": "feeder-board", "action":
     "move", "detail": {"card": "card-baffle", "to": "col-doing", "index": 0}}`, an
     options pick with `"action": "choose"` and `"detail": {"options": ["st-s3"]}`
     (every option that now holds the pick, so an empty list is one cleared),
     a suggestion decided with `"action": "accept"` or `"reject"` — and they have
     already seen the change on screen. It stays on screen without your help: the
     page replays every recorded action onto every later version, so their edit
     survives a republish whether or not your markup mentions it. Write the next
     version as the document should now read and leave their widget alone. What
     the markup still owes them is the record — mark every picked option `chosen`,
     replace an accepted suggestion with its `lf-new` markup and a rejected one with
     its `lf-old`,
     keeping the old id where the passage survives — so the page reads right to
     someone who never saw the log. `version check` says where the record is behind
     ("record behind the log", advice on a passing run), and until a version
     carries a decision the page marks that widget as decided-and-unhonored.

     Declining means putting different words there — yours, or the originals
     back — and that takes `restated` on the element plus the reason in the note
     (`page catalog`'s `$restated` has the rest). Without it replay paints their words
     over yours, so `version check` refuses the version rather than let the two
     disagree in silence. It guards the other end too: a version may retire ids only
     where the log settled the suggestion holding them, so an undecided proposal is
     carried, withdrawn whole, or left alone, never quietly kept as settled content.
   - **A page error** (`"kind": "error"`, author `page`) is the page's own runtime
     reporting a failure in front of the user — a widget module that wouldn't
     load, an uncaught throw. It is your debt, not theirs: the reader was never
     asked to open a console. Fix the page (usually the widget module or the
     markup), publish the corrected version, and say nothing in-thread unless
     the reader asked — the event is diagnostics, not conversation.
   - **A worker's report** (`"kind": "report"`) is another session moving declared
     state — provisional until a version answers it, so the next version you publish
     adjudicates: carry the reported state into the markup (publishing then absorbs
     the report by id), or keep your own state with `overruled` on the element and
     the why in the note. Leaving the markup unchanged is legal silence — the report
     keeps painting — but a page shouldn't end on one (`version check` reports it as
     record debt).
   - **A thread-widget action**: a `lf-options choose` group in one of your messages
     is an inline question (announce it there too — "click an option to answer");
     the user's pick is the answer, so acknowledge it with a reply in the same
     thread. Thread markup is frozen in the log — versions neither carry nor revert
     it, and the picked state stays put on its own. A question opened this way
     counts among the page's asks (the banner, the `a` key) until answered: one
     pick answers a plain group, while a `multiple` group answers when the user
     presses its Done control, arriving as an `answer` action — act on the set
     then, though every toggle still reaches you live as it lands.
3. Page changes go in the next version: copy the last version to `versions/v2.html`
   (incrementing; never rewrite a version the user has seen — the picker is the
   history), edit the copy where the page moved, then run `version publish <page>
   --version 2 --text "<changelog>"`. Keep the changelog brief, though a decline's why
   can take a sentence or two. The browser follows the published version automatically.
4. Re-enter the host's loop above: start a new background wait in Claude Code, or a new
   unified-exec wait in Codex and retain its exact session. Use `leaf status <page>
   waiting "<what you want back>"` and long-poll where the next move is the user's.
   Where it is yours, use `working`, keep doing the work, and poll the running waiter
   between milestones.

A `done` event is sign-off — it arrives only from a page declaring it (see the
conventions). It approves the work rather than ending the page: carry the approval back
into the main task, and where the approved work is yours to do, the page keeps up with
it from here. So the page stays `working` under a live `leaf wait` — "skip that one"
then reaches you mid-flight rather than at the end.

Ending a page is yours, and the browser has no control for it: a reader who has stopped
commenting has said nothing about whether the work is done. If wait output
is truncated, acknowledge nothing and retrieve the whole batch. After the complete,
untruncated batch enters context, acknowledge through its highest sequence, handle every
earlier event in that batch, then run `leaf status <page> idle`. That explicit status
command is the act that ends the agent side of a page — on a comments-only page and on
a sign-off page whose approved work is finished alike. A server you
started needs no stopping; it goes down with the session (a standing one is the
exception, below, and stays up). A page ending with record debt publishes
one final honoring version first, because the final version is the page that has to read
right without the log; `leaf transcript` lists what still lags on stderr, and prints
the whole exchange as Markdown when a PR description wants it. `version export` writes
the page itself as one file when that is what outlives it.

The `Stop` hook applies the same invariant differently by host. In Claude Code, a fresh
wait heartbeat means the background watcher can safely carry the next comment into a
later turn. In Codex, that heartbeat only proves a command is running, so Stop continues
to block until the page is idle and directs you to poll the exact unified-exec session
inside the current turn. With no waiter it directs you to start one; with pending events
it directs you to retrieve a complete, untruncated wait batch (acknowledging nothing and
retrying if output is truncated), then acknowledge and handle it. The hook's one-shot
recursion escape
still lets a turn it has already blocked proceed once.

The invariant is what the user is owed — from the browser, a page nobody is listening
to looks exactly like a page whose user simply has not commented yet, so without it
they find out by asking. It covers the pages you run `server run` or `leaf wait`
on, the two acts that put a user on the other end, so a directory you only built or
linted is outside it. `leaf status <page> idle` refuses while events remain
unacknowledged: run `leaf wait`, which returns at once when they are already there.
If its output is truncated, acknowledge nothing and rerun with enough output capacity
for the whole batch. After a complete batch enters context, run `leaf ack` through
its highest sequence.
`leaf wait` also restarts a server that died under it and reports the restart on
stderr; exit 2 means it couldn't, and the page stays down until `server run`.

## Pointing at a passage yourself

`leaf comment` opens a thread the way the user's selection does — same anchor,
same Markdown, same reply box, labelled with the current agent instead of You. Reach for it when what you have to say is
about one passage and you can't settle it yourself: a sentence that reads two ways, an
assumption the paragraph rests on, a line only they have the fact to fix. Anything you
can settle, settle — ship the fix. In chat, the reader has to find the passage again;
in the margin it is already beside them. With neither `--quote` nor `--section` it
opens a general thread — the shape the browser's own general box posts — which is
where a question about the work rather than a passage belongs.

```bash
leaf comment <page> --quote "<passage from the version file>" --text "…"
leaf comment <page> --section <element-id> --text "…"  # diagram or image
leaf comment <page> --text "…"                         # the page as a whole
```

A question with alternatives takes them as `--markup` — the AskUserQuestion shape,
answered in the panel by click or by keys (`a` reaches it, digits pick):

```bash
leaf comment <page> --text "Auth for the sync endpoint — which way?" \
  --markup '<lf-options id="q-auth" choose>
  <lf-option id="qa-jwt">JWT, verified per request</lf-option>
  <lf-option id="qa-cookie">Session cookie, server-side store</lf-option>
</lf-options>'
```

`multiple` makes the pick a set, and only the reader can say a set is whole: the
group carries a Done press in a thread, and the ask stands until its `answer`
action arrives. Ask on the page instead when the answer belongs in the record —
a reader of the final page needs the question and its answer, honored `chosen`
and later `settled`; a thread question is scaffolding for the work, and ends
with the conversation.

It anchors in the newest published version, deriving the section the way the browser
does, and reads the version the way the user sees it: a slot their decision retired
(an accepted suggestion's `lf-old`, a rejected one's `lf-new`) is off the page, however
much the file still holds it, and a `lf-draft` they have edited says their words — quote
the text their edit sent, not the body you authored. Quote the words the file holds, not
what the page renders, and stay inside one part of a widget — a module writes words of
its own between an element's children (a column's heading or a milestone's chips), and
a quote spanning that join names nothing. A quote the version
doesn't hold, holds twice, runs across such a join, sits in a retired slot, or names
words an edit replaced is refused with what to do about it, rather than posted as a
comment that lands nowhere — as is a `--section` naming an element their decision left
empty (a deletion accepted, an insertion refused): present in the file, absent from
their screen.

A comment's `--text` is the same Markdown a reply's is, fragment links included:
`[the group](#d-channel)` carries the reader to that element.

A comment asks; a `lf-suggestion` proposes. Where you have the better sentence, ship it
as a suggestion in the next version and let them accept it — a comment is for the
question you can't answer yourself. The user resolves either. There is no CLI that
resolves a thread: a note's purpose is discharged by being read, and only the reader
knows that happened.

## Customizing the widget layer

`page init` vendors the layer into the page directory from leaf's integrated
layer, then its bundled widgets (the shipped content families ride this same overlay),
then the user's `~/.config/leaf/`, then the project's `.leaf/`. Each
mirrors the same layout (`theme.css`, `registry.json`, `icon.svg`, `widgets/`,
`vendor/`). Theme
files concatenate in that order, so a short later file can override tokens or rules
without copying the defaults. Runtime, icon, widget, and vendor files replace by path;
registry files merge at the unit of the contract: a later layer replaces a tag's
complete entry, and one member inside a `$` entry. A custom widget therefore adds
its entry without copying the shipped registry, overriding a tag supplies its whole
schema, and an idiom declared under `$idioms` joins the shipped catalog beside the
theme rules that style it. `leaf customize theme` and
`leaf customize widget lf-name [--upgrade]` scaffold those files in the project
layer; pass `--user` for the user layer. The merged vocabulary is validated before
vendoring, and its `x-state.detail` schema validates every action at
`POST /api/event`. `page catalog` reflects the result.

The page directory is self-contained: a version the user approved can't change under
them. Re-running `page init` on a live page is the explicit re-vendor; note it in
the next version's changelog. It refuses when the incoming layer no longer accepts a
logged event kind or action contract (tag, verb, and detail), since that event would
stop replaying.

## Where the page is served

`server run` serves a page on the address its session arrived on: for an SSH session, the
one the client reached this machine on; otherwise loopback. The URL therefore opens as
printed whether the user's browser is here or on the machine they SSH'd from.

That address is a route the session demonstrated, which the user's browser may not
share: a jump host or NAT between them and this machine leaves it unroutable from where
they sit. Only their browser can see that, so the report comes from them. Silence on
this side looks the same whether they haven't looked yet or can't reach the page at all.
When they say the URL doesn't load, `leaf server stop` and re-run with
`--host NAME`, where NAME is a hostname they reach this machine by — it goes in the URL
as given, and the server binds every interface so the name need not resolve to a local
address. A machine on an overlay
network (a tailnet) has that network as an interface, so its name there reaches a
user with no route otherwise; failing everything, `version export` hands over the
page as a file.

Reaching past loopback opens the port to that network, and `POST /api/event` appends to a
log that outranks the document, so the URL carries a key. The browser keeps it in a cookie
from the first request, and a reader without it gets 403 on the document, the assets, the
state reads and the event writes alike. That key is the boundary, and leaf serves only
networks this machine is already on: there is no public tunnel — a tunnel would put the
log's one door on the open internet, and a fresh tunnel hostname each restart would strand
the URL an open page is polling.

Address and bind are recorded once in `<page>/access.json` — `--host` goes there too —
because a restart has to reproduce the URL an open browser is still polling. Deleting that
file derives the address again from the session running now. The key is the machine's
rather than the page's, minted on the first serve and kept in the state home: handing out
one page's URL hands out every page on this machine.

## A page that outlives the session

`server run` from your session claims the page, and the server goes down when the
session ends. Two launches decline that claim and stay up instead:
`server run --standing`, and a run from a shell of the user's own — a terminal, a login
item. Either is a **standing page**, the arrangement for a command hub or a dashboard
they keep open for weeks. `server run` says which lifetime it started on the line after
the URL. Nothing revives a standing server and no session's end reaches it;
`leaf server stop <page>` is the only thing that ends one. Start one with
`--standing` when the page is meant to outlive your session — and say so when you do,
since the user inherits a process only that command stops.

A lifetime belongs to the process, so a crash ends it along with the server. The one
restart in leaf is `leaf wait`'s, and it starts a server of the session running
the wait — so a standing server that died and came back that way now goes down with that
session. Say so when it happens, and re-establish it with `server run --standing` (a
`server stop` first, if the wait's revival is still up).

Working on a standing page changes nothing in the loop, and adds one step before it:
the page carries weeks of decisions your session never saw, so read
`leaf page state <page>` first — the standing state the log has folded onto the page,
the asks still open, and where the markup lags a decision, as one JSON object. Then
pick it up with `leaf wait` as usual, publish versions as usual, and expect the same
loop while your session lasts — a
`server run` of your own finds the standing server already up, prints its URL, and
leaves it running. What changes is the ending: don't stop the server, and use
`leaf status <page> idle` only when the *page* is finished, not when your work on it
is. A session that just ends leaves the page up and unheld, which is what the user sees
between sessions and what the banner says; an idled one reads "Leaf closed" to
someone who was expecting it tomorrow.

## Before the URL goes out

Three passes stand between a version and its user.

**The lint.** `version publish` runs `version check` on every version and refuses a
failure, so the workflow needs no separate static check and a failing version never
reaches the user. It is deterministic and needs no browser, and a failure names
what to fix — the markup's structure, the registry's rules, and the id-survival rule
above.

**The render gate**, once, before the page's URL first reaches the user:

```bash
leaf version check <page> --render
```

It loads the version in the machine's installed Chrome (a couple of seconds, and works
before the version is published) and fails, in both color schemes, on what a static lint
cannot see: a console error, a widget upgraded into a box of no size, a page that
scrolls sideways, a `lf-diagram` whose mermaid source doesn't parse, words on screen
that no selection can reach, code set in an ink the reader can't tell from the block it
is on, words the screen shows and a printout drops, a version
that authors widget state the log replays over
(a different option `chosen`, a card in a column the user dragged it out of — the
decision stands, so carry it in the markup or rewrite the passage and declare
`restated`). The lint validates a diagram element but never the notation
in its body, so a typo there would otherwise reach the reader as an error box; and it
can't see a heading rendered as CSS generated content, or left under `.lf-ui` with
nothing said about whose words these are, which leaves the reader looking at text they can't
comment on. When Chrome isn't installed, the gate fails and says so on stderr. It is
the page's whole browser budget; a screenshot after it reads neither the console nor
the second scheme.

**Then read the page yourself.** Neither pass above has an opinion about any of what
follows. A page stands in for what you would otherwise have written in chat, so the
user's own skills for that hold here too — anything on writing prose, anything on how
they want to be addressed — and beyond those:

- **Claims backed.** Every assertion the reader would question is traceable to real
  evidence on the page — a command, a diff, a linked source, output behind `<details>` —
  not asserted bare.
- **Excess pruned.** No paragraph restates another; nothing explains what the reader
  already knows. If a version has been patched several times, rewrite the section clean
  rather than layering another note. Anything the topic has moved past is excess at full
  height — "Keeping the page current" says where it goes.
- **Diagrams read.** Each diagram earns its place and says something the prose doesn't.
- **References clickable.** Tickets, PRs, and URLs are real links.
