# Prose review

Status: in progress. Phase 0 landed as #1476. Phase 1 is written and unlanded. Phases
2–6 are planned here, and four of them wait on a decision. Delete this note when the
last phase lands, after moving any standing rule into `/developing-leaf`, the glossary,
or the guidance it governs.

## Goal

Leaf's prose was written quickly, mostly by models, and much of it reads that way:
mannered, over-compressed, padded with facts the reader does not need, and organised
around Leaf's subsystems rather than around anyone reading it. The review rewrites it in
Worktrunk's register: no second person, descriptive rather than normative, topic
headings, and each page written for one reader.

The respect each body of text gets depends on how much was invested in it:

- Agent guidance (`skills/leaf/SKILL.md`, `skills/leaf/references/`, package guidance)
  and maintainer guidance (`AGENTS.md` files, protocol sidecars, `/developing-leaf`) get
  the most care. That means no change that alters what an agent does unless the text
  is wrong. It does not mean leaving verbosity in place: phase 1's first pass only
  reworded these files, and it grew them by 444 words. Max's verdict was "I would expect much
  more /descartes such that we're removing lots of verbosity". The second pass cut 26%.
- The front page is kept as it is.
- The rest of the website gets the least deference: pages can be merged, split, or
  dropped.

## Patterns to remove

The review found these habits across every area. A reviewer applies `/writing-prose`
as well as this list.

| Habit | Example | Plain form |
| --- | --- | --- |
| Heading as a thesis | "The page directory is the record" | "Page directory" |
| Narrative or dramatic heading | "From X to Y" | The topic's name |
| Abstract noun doing a concrete verb | "markers stand in room the page left free" | "markers sit in the rail beside the text" |
| Colon reveal | "The rail claims none of it: its markers stand beside…" | "The rail sits beside the column and never narrows it." |
| Over-compression | "crosses into the column only by what the rail lacks" | Separate sentences, conjunctions kept |
| Free relative | "what it is about" | Name the thing |
| Conditional "where" on an elided noun | "the kind where it is known" | "the kind of X that is known when…" |
| Coined term never introduced | "each [widget, unit, verb] coordinate" | Gloss it once; the explicit tuple itself is fine |
| Second person | "What you see after you send" | "Delivery status" |
| Detail meant for another reader | "believed while something renewed it within a quarter hour" | What the user sees, and what it means |
| One concept under many names | comment, update, change, gesture, input, item, move | One word per concept (phase 5) |
| Counts in durable prose | "Three stores hold…" | Name the property; the list carries the count |
| A fix's history written as behaviour | "shows it as context from the Stop hook, not as an error" | State the behaviour |
| The same fact in several places | the fold three times on the site, host selection four times in the guidance | One home; others point at it by section name |

## Phases

Each phase starts from `main` on its own branch. A prose phase is a
`/iteration:descartes` rewrite: recover what the reader needs, write the text afresh,
then check every dropped detail against the code. Each phase reports words before and
after for every file. A file that grows needs a reason, such as a table completed
against the code.

### Phase 0: Layout tab and factual corrections (landed, #1476)

The How it works Layout tab became a reference to the layouts. Prose the code had
outgrown was corrected across the site.

### Phase 1: Maintainer guidance (written, not landed)

Branch `agent-a7d03ea41654f534b` at `5c7based6f` (local). Against main it takes the 17
maintainer-guidance files from 33,267 to 24,750 words:

- `scripts/AGENTS.md` −58%, `dev/AGENTS.md` −56%, `session-lifetime.md` −38%;
- `validation.md` −34%, `layer-registry.md` −31%, `page-storage.md` −30%;
- `events.md` −27%, `assets/AGENTS.md` −23%, `tests/AGENTS.md` −19%;
- the root `AGENTS.md` from "Repository map" down −7%. The text above that heading is
  untouched.

What went: restatements of module headers, which the text now points at; how rules were
found; justification beyond the one reason a reader needs; and per-command catalogs that
`--help` gives. Stale claims were corrected against the code, among them pin placement,
the `--render` viewports, the `service.json` restart mark, and the `$events` registry
description of what `page init` checks. The aphorism headings in `tests/AGENTS.md` and
`keyboard/AGENTS.md` became topic names, and every citer was updated. The suite passes on
the branch.

Before landing: read `session-lifetime.md` and `tests/AGENTS.md`, the files most cut and
most cited. The last round of cuts to the `scripts`, `keyboard`, `tests`, `examples` and
root `AGENTS.md` files has had no independent review.

### Phase 2: Agent guidance (no decision needed)

The same descartes brief, applied to `skills/leaf/SKILL.md`, `skills/leaf/references/`,
and each package's `guidance/`. Score the change with `uv run leaf-dev guidance-eval`
before and after (`/developing-leaf`, "Score a guidance change"). Known work:

- `packages.md` (11k words): a contents list; the optional packages as a table; the
  25-line "What a behavior module owes" sentence as a checklist; "A theme change" split
  by topic.
- One home each for the host-selection rule (four copies), "say what you are doing
  first" (five), and the URL-in-every-message rule (two). Host contracts stop pointing
  at each other.
- `event-batches.md`: the instruction comes before the transport details. It and
  `conversation-loop.md` tell the agent to follow an event's `answering` clauses, but a
  delivery carries them merged into `handling`, so the agent never sees the name it is
  told to look for.
- `authoring-revisions.md` "Honor user state": its two "exceptions" are one rule, a
  widget's declared record form.
- `page-authoring.md` "The rail and the margin": keep only what an author acts on.
- `SKILL.md`: drop one residue of a removed feature, compress "Operate" step 3, and fix
  one garbled sentence.
- `host-claude-code.md` "Session list": keep the rule and cut the mechanism.
  `serving-pages.md`: move maintainer and harness material aside.
  `host-codex-app-server.md` "Start the terminal" is user setup (lower confidence).
- Errors:
  - `page-authoring.md` says "`version check` advises against one", but no `version`
    command exists; the advisory comes from `page check`. The same stale name is in
    `assets/runtime/bounds.js` and `reading-regions.js`.
  - `packages.md` "`data set` is the one write" contradicts the same file, which says
    any process may rewrite its file.
  - `command-hub/guidance/coordinator.md` says "one leaf" for a leaf of the goal tree;
    it should say "one leaf goal".

### Phases 3 and 4: How it works and site structure (decisions A and B)

These run together, because the site structure decides where each rewritten tab lands.

Today's site follows Leaf's subsystems. No page is written for a person using a Leaf
page; that material is spread over five How it works tabs, and the fold is explained
three times. The proposed site gives each page one reader:

- `/` unchanged.
- `/examples/` without the developer galleries; each card names its package.
- `/using/` (new): operating a page and reading its status.
- `/how-it-works/`: the mechanism only, with the event log (`/event-log/`) folded in
  and the fold stated once.
- `/pages/` (new): what a page contains, and its layouts.
- `/extending/`: where a change belongs, the packages as a table, and one worked package.
- `/registry/` removed from the public site.

The site never mentions these topics, and should:
- Leaf's experimental status;
- its requirements (`uv`, `jq` ≥ 1.6, a reachable browser);
- trust: what a page may load, that Leaf opens no public tunnel, and what the access
  key grants;
- `leaf page export`.

The How it works tabs, rewritten:

- **Loop** becomes the path of one comment to its answer. It absorbs the Updates
  timeline and replaces the four-route delivery paragraph with a table by host. The
  acknowledgement list and "A command never edits the document" go.
- **Updates** is renamed **Status** and organised by surface: the banner as a table of
  readings, the label beside a comment, threads and Asks, notices. "Update" today names
  three things: the user's input, a new revision, and the agent's status.
- **Revisions** gains the missing section on comparing versions, takes the "New page
  available" chip from Updates, and gives reactions to Loop.
- **Pages**: page source; widgets, saying plainly that the samples are inert; page code;
  packages. "Kernel" and "layer" get a plain introduction or go.
- **Data** and **Serving**: topic headings. One table of the page directory's contents,
  including the vendored runtime. The fold reduced to a paragraph. Serving rebuilt
  around the address and access key, the stable URL, and restart by `leaf wait`.
  Possibly one tab.

**Decision A, banner and delivery depth.** Loop and Updates spend about 900 words on
how the server decides what the banner says (the "believed" rules and an 11-node
flowchart), on the acknowledgement protocol, and on a 13-node map from commands to
surfaces. The references own all of it, and #1433 added a Stop-hook flowchart in the
same vein. The options:
- *User level only* (recommended): the banner table and one paragraph on how the
  reading is computed, linking to the references.
- *User level with the flowchart under a closed disclosure*: a second copy of the
  references' material.
- *Keep the derivation*: fix the register and the naming only.

**Decision B, how far to restructure.** The restructure touches the route table, the
nav copied into every page, three product-page tests, and the Worker's route fixtures.
The prose rewrite is the same work either way. The options:
- *Reorganise by reader* (recommended): the map above.
- *Keep the pages and regroup the tabs*: fold the event log in, drop `/registry/`, and
  keep How it works as one tabbed page with tabs by topic.
- *Rewrite in place*: keep every page and tab.

### Phase 5: UI and CLI copy (decisions C and D)

About 45 browser strings and 6 CLI strings address the reader as "you", and one speaks
as the reader: "Done: my picks here are complete". Three banner readings are wrong:
- "Claude waiting for you" means the agent is blocked on a prompt in its own terminal;
- "Leaf closed" means the agent declared itself finished;
- one offline state has two wordings.

The CLI has three error formats, "issue(s)" plurals, Python lists in messages, and
success lines that recite every check.

The fix is a short table of user-visible words in the glossary, with every surface cut
over to it (about 120 strings). For example: "Undo" rather than "take back", "page"
rather than "leaf", "Threads" for the panel, "comment box" for the composer, and one
word each for "needs a reply" and "with the agent". The CLI also gets:
- one error presentation;
- a minimal success line;
- self-contained hints;
- one grammar for command-reference rows;
- no code vocabulary in reader-facing copy.

**Decision C, the word for the user's input.** Today the user's input is a comment,
update, change, gesture, input, item or move, depending on the surface. The banner and
the Leaves drawer count a mix of comments, picks and drags, and the activity payload
holds one number per stage, not per kind. The options:
- *"Update" for mixed input, the specific word otherwise* (recommended): "3 updates
  picked up", "Reply to this comment". "Updated to v4" becomes "Showing v4", so
  "update" means only the user's input. This is a string change.
- *Always name the kind*: "2 comments and a pick picked up". Needs per-kind counts in
  the activity payload and a user-facing noun declared per event kind.
- *"Move" for a mix*: matches the guidance's game framing but reads oddly to a user.

**Decision D, `layout-sidebar`.** "Sidebar" names two unrelated things:
`main.layout-sidebar`, a wide page's side column, and `aside.sidebar`, navigation in a
column page's margin. Either rename touches about 19 files, including
`validation/markup.py`, two packages' registries and guidance, the glossary, and three
eval cases, which then need scoring before and after. The options:
- rename the Layout `layout-aside`;
- rename the margin idiom;
- keep both names, distinguished in words, which is what the Layout tab does now.

### Phase 6: Example pages (decision E)

Alert review, the triage board, heat loss, plan review and the Rust sort read as a
capable engineer's handoff, and their numbers check out. The command hub, code
comparison, data explorer and notification playground are demos written for the demo,
and several pages narrate Leaf's controls ("Alt-click a file header…") where one clause
naming the move would do. The work:

- **Gallery cards:** generate them from each page's `<meta name="description">`. Today
  they are a hand-written second description and have drifted ("Move four defects" on
  a seven-card board).
- **Fact slips:**
  - log retention's survivorship argument does not hold at 400 days;
  - ship review shows release notes' runs table as a vendor build list;
  - release notes' suggestion repeats the line above it.
- **Command hub:** rebuild it around the importer rewrite it coordinates rather than the
  orchestration vocabulary it teaches ("remit", "cargo", "receipt").
- **PR walkthrough**, the catalog's flagship review: replace its invented labels and
  invented Rust assertions with real ones.
- **Seeded user comments** read like a user wrote them. Log retention's "The two
  write-ups is the number, not the story" is written in the agent's voice.

**Decision E, the playground-shaped examples.** The code comparison, data explorer and
notification playground share one shape: controls, a preview, and a generated
instruction. None says whose problem it solves, and the code comparison's instruction
edits Leaf's own `lf-code.js`. The options:
- *Keep one in the catalog* (recommended): the notification playground, given a real
  product. The other two move to the Playground entry on Extending.
- *Give each a real subject*: a docs site choosing how code behaves on a phone; a
  weekly release-risk report.
- *Leave them*, fixing their prose only.
