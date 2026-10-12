---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, check that
`<root>/bin/leaf --root` prints that root, and run every `leaf` command through that
absolute launcher; a bare `leaf` may run the installed plugin instead.

Read `references/glossary.md` before naming or revising a user-facing element,
interaction, navigation, chrome, view state, or an identifier for one of them. It is
Leaf's canonical implementation vocabulary.

## Read the owning contract

A contract shared across modules or runtimes lives in the sidecar beside the Python
code that owns the boundary; `<root>/skills/leaf/scripts/AGENTS.md` lists them under
"Protocol references". To check what the code does, call it: `leaf` and `leaf_dev` are
installed editable, so `uv run python -c 'from leaf... import ...'` needs no
`sys.path` edit. A tag's schema is in the registry of the package that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  skills/leaf/assets/registry.json skills/leaf/packages/*/registry.json
```

A fact both runtimes use is owned by one language and consumed as data, or generated
from the registry (`skills/leaf/assets/AGENTS.md`, "Facts both runtimes know"). When
writing or reviewing a change that adds a parity fixture or a test that scans one
language's source for the other's names, ask why the fact is not generated.

## Review a UI change

For browser API and rendering support, maintain
[`notes/browser-support.md`](../../../notes/browser-support.md), following its
"Recording and assessing a gap" section.

Before handing over a change to browser controls, navigation, focus, motion,
forms or layout, read and follow `/ui-sweep` at `../ui-sweep/SKILL.md` on
the changed surface and its dependent interactions. Its "External review"
section owns selection and use of the tools below.

For theme or reusable-control changes, its "Review a design system" section owns
the review of foundations, component states, and their composition in a user task.

### External UI skills

These are optional external installs, separate from Leaf's plugin. Check the
harness's available skills before invoking one; each upstream link supplies its
installation instructions and complete references.

| Install | Use in a UI review |
| --- | --- |
| [Impeccable](https://github.com/pbakaus/impeccable#installation) | `/impeccable critique` for hierarchy, grouping and clarity; `audit` for technical UI quality. Its focused workflows include `layout`, `typeset`, `clarify`, `adapt`, `harden` and `distill`. |
| [Web Design Guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines) | `/web-design-guidelines` for interface conventions, accessibility, navigation, forms and motion. |
| [Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | `/frontend-design` for new compositions or an intentional redesign. |

## Leave taste to the authoring agent

Code enforces only what Leaf needs to work: a contract between modules, or a guarantee
the user relies on, such as a gesture being recorded or nothing moving under the
pointer. Taste goes in the shipped instructions as a goal and its reason, so the authoring
agent weighs it against its own page. A CSS rule, validator, or Layout that fixes how
many tiles share a row overrides every page that needs another number. A check may
report what it sees, as the render check names where a tile row wraps, and leave the
call to the agent.

Checks follow the same line. `page check` and its render checks hold Leaf's contracts
on every page: each widget upgrades, nothing a user needs is clipped out of reach, every
control can be pressed. Don't add a check that anticipates one particular authoring
mistake, such as one attribute misapplied to one tag. Each such check costs code, tests
and gate time on every page from then on, while a mistake agents rarely make costs one
fix on the page where it happened, or a clearer line in the instruction it misread. Add
a narrow check only where agents get what it reports wrong on real pages and fix it when
told. A check that fires mostly on pages that already work, because delivery or the
page's own CSS handles what it looks for, costs more than it catches. Prefer widening a
general reading to adding a narrow one beside it.

## Be a helpful linter, not a nanny or a partial checker

Leaf's checks exist to tell the agent about a mistake it would not otherwise hear of.
The agent that writes a page or sets its data reads what comes back: a `page check`
finding, a widget's failure box, a command's error. It fixes a mistake it can see, so
code handles the input its contract describes, such as a patch as `git diff` writes it,
and lets anything else fail through the parser or check already in its path.

Two kinds of check cost more than they return. A nanny refuses input that would work, or
detects, repairs or explains each malformed variant, which adds code to every reader of
that input and buys nothing the agent's next attempt would not. A partial checker judges
input that another component already judges exactly, with a second parser, a subset of a
grammar, or a refusal list kept in step with a widget's. It disagrees with the real
judge at the edges, and each disagreement found becomes another check. Leave the judging
to the component that consumes the input, and make sure its refusal reaches the agent:
`patch_manifest.py` stores a patch as given, and `lf-diff` refuses a file it cannot draw
and reports it with `reportFailure`.

Handle a malformed case only where nothing downstream would refuse it, so that it would
pass silently into state the user relies on, such as an admitted event or a stored
decision.

What one Leaf module writes for another, over a channel only Leaf code writes, is not
input: the browser reading the server's answer, the Worker reading the manifest its
build wrote, a caller reading what admission accepted. The reader uses it directly, and
the producer's own tests hold its shape. What a person or an agent can write on the way
is input even when Leaf code sent it: a request the browser posts, a file an agent
edits, the answer of leaf.page's container, whose agent a visitor steers (root
`AGENTS.md`, "Validate once and share readings"). The exception is a record an older
Leaf left in the state home, which root `AGENTS.md`, "Stage", has the reader tolerate.
Recovery from a state no Leaf writer produces goes the same way: delete it with the test
that manufactures the state to reach it.

## Explore an open design

Whenever the user is to choose among designs for a visual or interaction
question, whether options for a new interface, alternatives to a shipped one, or
sketches they asked for, put the candidates in one playground, where the user
compares them, tries the interactions needed to decide, comments, and submits a
choice. The submitted configuration or feedback chooses the one implementation
the change keeps. First look in the shipped examples and `notes/` for an
exploration of the same surface, and extend its playground when it owns the same
decision.

A playground is one HTML file, like a standalone sketch. Write it under `.tmp/`
and serve it with `uv run leaf-dev preview --source <file> --user` ("Preview a
page"), which builds the page from that file alone. Its CSS reads the live
theme's tokens. Follow
`<root>/skills/leaf/packages/playground/instructions/author.md` to choose the
selection and exploration elements, present the candidates, and submit a task
saying what to build.

For an existing-interface comparison, the property the user named defines which
controls and states the survey covers. Find it in its defining code; it can
cross owners or select part of one owner's interface. Candidates share the
current interface except for the requested change. Use this checkout's rendered
interface as the baseline in the review state. Implement runtime candidates in
the runtime and theme that own the surface; an appearance sketch can restyle
the live surface. A separate sketch follows "Decision fidelity" in the
playground author instructions. When a reviewer checks the comparison, give them
the user's question and the baseline and candidate views, and ask first whether
those views are enough to make that choice; ask for a preference only once they
are. Operate an interactive comparison's baseline and candidates through the
same journey before handoff. For a live Leaf interface, embed them as
`lf-sample window` children (`skills/leaf/references/page-authoring.md`, "Live
samples"). The outer page carries the configuration and feedback, and each child
carries practice interactions, which its Full view lets the user try at viewport
size. Start their fictional histories with `data-sample-events`, sharing one
parent-local JSON fixture when the candidates need the same conversation.

## Choose what the user reviews

Prefer outputs that are quick for the user to review. Perform reviews yourself
when you can do them as well as the user, and report the results.

Choose the review decisions from the user's request, then revise the page's
choices to match.

Present visible and interaction changes using the proof below.

## Prove and hand off a visible change

Define the user's task and each step's expected visible outcome before choosing
the controls or their checks. A reader should be able to associate related
labels, symbols and destinations before activating them. Exercise each route
from the reachable states that change its effect, including when its destination
is already open or a different selection is active. A reader completing the task
through one route proves only that route.

Open the exact preview URL in a fresh browser context and verify those outcomes
on arrival and through ordinary input. Setup from a private probe that the user
cannot repeat belongs in the fixture or a replay control.

Judge legibility and layout in the visible states ordinary input produces, in
the affected color schemes. Within an open surface, inspect the item under the
pointer or targeted by keyboard navigation against its current background;
focus can remain on the trigger.
Pause before the next input replaces or dismisses that state.
Every candidate and optional surface retained in the page belongs to that review.

Review at a representative desktop viewport (`skills/leaf/assets/AGENTS.md`,
"Layout and motion"), and capture the viewport when fixed chrome should
appear. A Playwright screenshot of an element taller than the viewport draws
fixed overlays in the wrong place; crop a viewport capture instead.

Close a browser session you created for a review when its final reading is
finished. The user's review preview and a browser borrowed from another owner
keep their own lifetimes.

Before declaring a visible change complete, derive its required visual relationships
from the reader's task, rather than treating the implementation's passing checks as
the complete target. For each ordinary input, state which content and controls the
reader needs to keep in view or reach next, then verify their computed geometry
before and after that input in the delivered page, including embedded views. Judge
reflow by whether it serves that task and keeps the reader oriented. Make the
relationships hold as content and sizes change through layout constraints or
positions derived from one shared coordinate or dimension. Check those constraints
in the source as well; a screenshot alone can hide a small alignment error.
Re-vendor after a runtime, theme, registry, or widget change, then judge the
composed page visually as well.

To ask a page a question, such as where an element sits, what style it computes, or
what holds focus after a key, run `uv run leaf-dev probe` rather than writing a
Playwright script: it builds the page from this working tree, runs the input steps
you give it, and prints what a JavaScript expression returns, with `--base` for the
merge base beside it (`dev/AGENTS.md`).

When a complex interaction depends on a sequence of inputs or changes over time,
show a recorded journey with a timeline so the user can inspect intermediate
states and motion. Use that same probe with `--record .tmp/recordings/NAME`, driving
the input from a `--journey` file where `--do` steps are not enough; its `--help`
owns the recording flags and how to serve the trace without opening a desktop
browser. Review the final exported recording through playback or decoded frames at
their recorded times, including its loop boundary; select the interval that shows
the behavior being reviewed. Link the trace viewer's URL in the review page; open a
desktop browser only when the user asks to watch.

Show the trace on the Leaf page in `lf-trace`, as
`skills/leaf/references/authoring-evidence.md`, "Source files and media", says,
importing it with that viewer URL. Keep both previews running and verify that the
viewer URL reaches the user's browser before handing it over.

For an important result, perform the input and use a Playwright expectation for
the outcome defined from the user's task. Disclosure and focus prove their own
effects; they do not prove a change to the content the user came to inspect.
Review the successful expectation's After checkpoint; returning from the input
alone does not prove an asynchronous update finished. Native tracing groups name
those operations without adding captures.
Add `--checkpoint-images` when the review needs native PNG images at those
checkpoints, and leave it off when ordinary motion and caret behavior are the
evidence.

`uv run leaf-dev stills` compares HEAD with the merge base with `main` and crops
each changed catalogue state into a before/after pair. Commit first, since it
compares commits. For changes to the examples themselves, add `--authored` so
each arm reads its own committed markup and companions; the default shares the
current source to isolate runtime changes. Include pages at rest and states reached by interaction,
including focus states where layout can cover a focus ring. Add missing states
to `STATES` rather than driving them by hand.

For every difference a still can show, the handoff is a Leaf page holding an
`lf-shot` of that difference, from the crops `leaf-dev stills` writes, with a
sentence saying what changed; the reply links the page. A live preview may
accompany the pairs but does not replace them. Several captured states often show
the same difference. Check them all, show the difference once, in the state where
it reads most clearly, and say in a line which other states repeat it, since the
user reads every pair and a repeat tells them nothing new. A dark-scheme or phone
pair belongs only where the change looks different there, as a change to a colour
or theme token does in the dark scheme.

For an interaction-only change, compare the same journey on both versions
("Compare checkout versions" below), at the same fragment, viewport, theme,
and interaction state. Choose the handoff materials using "Choose what the user
reviews" above, and use the recorded journey for motion evidence. A live preview
handed to the user carries the fragment of the semantic block it is about
(a titled section's own id) and stays running.

## Preview a page

`uv run leaf-dev preview <example>` serves a live page that follows source and
runtime edits at one URL. `--source <file>` serves any authored HTML file instead
of a shipped example, and `--export` writes one file that opens offline. A
desktop Codex `--user` preview detaches and returns its URL; every other preview
runs in the foreground like a dev server, so start it as a long-running command
(`run_in_background` in Claude Code). The
`dev/leaf_dev/preview.py` header owns slots, what a restart keeps, and the desktop
Codex detach; `--help` lists the flags.

A plain preview takes no claim, so its presses reach only the page's log; use it
for screenshots and browser checks. `--user` claims the page so the user's comments
reach this session's harness, which also makes every click this session drives
there read as an unanswered update. So drive only plain previews, and start any
`--user` preview from the session the user talks to. Don't idle a preview to quiet
the loop; `idle` closes the page in the browser.

### Temporary review resources

Keep a review's live resources proportional to the work being performed. Use the
smallest fixture that preserves the journey and its relevant surroundings; `--source`
can avoid serving an entire gallery for one interaction. Separate page directories
isolate reviewers' comments and data; fresh browser contexts isolate browser storage.
Neither alone requires another browser or Python process. Different historical server
runtimes still need their own environments.

For finite checks, prefer `leaf-dev probe` or `stills`, whose serving scopes
close their temporary servers when the journey exits. A live preview also watches source
and runtime edits, which an immutable revision does not need. Start comparison pages
as reviewers need them. Any custom runner owns its temporary servers and browsers
through completion, failure and cancellation, including waiting for its children to
exit. Keep previews and trace viewers handed to the user available for their review.

### In Codex

1. Start the preview with `--user` from the current
   chat. It connects the page's updates to this Codex chat before printing the URL;
   desktop Codex returns after the detached watcher subscribes to source edits.
   Each restart reconnects the existing page automatically.
2. Call `mcp__codex_app__open_in_codex` with the printed keyed URL and the semantic
   block's fragment, as a browser target with `placement: "right"`.
3. Tell the user to comment on the surrounding review page to steer this chat.
   Comments inside a live sample are practice interactions in that child. Codex
   Annotation mode sends visual comments with the next chat message; Leaf's text
   selection and comment affordance send an anchored thread directly.

## Run the agent journey

`uv run --project <root> leaf-dev journey TARGET` runs one user's journey against a
real agent: on the triage board, it tells the agent that a release passed its checks
and asks it to record that, leaving how to the agent, then checks a reply and a
revision naming the release. It prints how long each step took, the agent's steps on
the page server's clock, so the same journey benchmarks every target. A run spends
the target's login.

The simulated user reaches the page the same way on every step. On a harness it
posts each comment over HTTP by default, as the page's tab does, and starts no
browser; use that for harness behaviour and agent timing, which the page's log
carries whole. `--browser` runs the whole user journey in Chrome instead: each
comment typed in Threads, each reply's showing timed by the page, and the release
ask's reload checked. Use it when what the page shows is part of the change. A
website target always runs in Chrome, since delivery through the page is its subject.

On a harness the journey runs a session of it with this working tree as its plugin
and goes on as the user at its terminal. The suite stands in for each harness, and
only this run shows what the harness itself does. Run it on the harness a change
touches; each target's module header lists its steps and the harness promises it
checks:

- `claude-code` (`journey_claude_code.py`): run it, with and without
  `--hooks-module`, after a change to `hooks/hooks.json`, `hooks/claude-code.ts`,
  `ClaudeCodeHarness`, `hooks.py`, `background-watch.py`, or the watch between
  turns in `session.py`.
- `codex-app-server` and `codex-queue` (`journey_codex.py`): run both after a change
  to `codex.py`, `codex_adapter.py`, `hooks.py`, `hook_transport.py`, or the claim's
  turn in `service.py`, adding `--preview` for a change to preview startup or
  lifetime.
- `pi` (`journey_pi.py`): run it after a change to `hooks/pi.ts`, `PiHarness`,
  `hooks.py`, or the watch between turns in `session.py`.

For the website, TARGET is `website-adapter` for its adapter against the host's
Codex login (no Worker, container limits, credential proxy or Docker),
`website-worker` for the built site through the local Worker, or a website origin;
there the journey is the release ask alone. `tests/AGENTS.md`, "Run what the change
needs", owns the CI delivery checks and when to reproduce a Worker/container failure
locally. `worker/README.md`, "Local development", owns that reproduction setup. The
`publish-site` workflow verifies the complete boundary before deployment; its
journey against the deployed release is the only production reading.

## Compare checkout versions

`uv run leaf-dev compare <example> --user` serves the merge-base runtime beside
this checkout, and keeps running in the foreground. Keep the default shared source
for a runtime change and pass `--authored` when the authored content changed; omit
`--user` for claimless tests. Its `--help` lists the other flags.

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped
example or fixture, a playground, or a page made for this conversation. Before
writing its content, read `<root>/skills/leaf/SKILL.md` completely and follow
its authoring, validation, handoff, and conversation-loop routes, using the
checkout launcher for every `leaf` command and resolving its references from
`<root>/skills/leaf/`. A brief for a subagent that writes the page names the
content and the decisions the page puts to the user, and leaves how they are
posed to those instructions.
To make an existing page exercise the current checkout, re-vendor it with the
checkout launcher (`<root>/skills/leaf/references/serving-pages.md`); fix or
report a compatibility refusal rather than falling back to the installed plugin.
A page that explains how a Leaf widget, verb, or event flow behaves lets the user
operate it in a live sample (`<root>/skills/leaf/references/page-authoring.md`,
"Live samples"). The sample's template holds only the demonstrated page and an
`lf-activity` feed of the sample's own log, so each gesture shows the event it
writes; nothing in it mentions the sample. The parent's prose directly above the
sample lists the gestures to try, in an order that exercises each verb the page
explains, undo included. Before handing the page over, drive the sample using only
what that prose tells the user, and read each line the feed prints for those
gestures: a probe that knows more than the prose shows that the sample works, not
that a user can work it, and a badly worded line misleads the user about the log
the page explains.

## Score an instruction change

Score an instruction change when an agent could read it more than one way, so what
it will do under the new text is uncertain: a new or reworded rule, a goal that
competes with another, a cut that may have carried a behavior. A change whose reading
is plain needs no score, such as deleting the description of an input that can no
longer arrive or correcting a fact. Prefer personal-skill evals for general agent
behavior (`/improving-instructions`, "Validate with evals") and the standard Leaf
evals for consuming its shipped workflows. Score a change to Leaf's maintainer
guidance, such as this skill or an `AGENTS.md`, with a temporary A/B in scratch that
gives each arm its version of the passage, and commit no case for it. An internal
maintainer case in Leaf's suite is exceptional: add one only for a development
contract that needs the suite's own staging, such as a served page or an installed
arm, which a scratch prompt cannot reproduce. That the rule under test is Leaf's own
does not make it that exception. For cases in Leaf's suite, run both the merge base
and the working tree:

```bash
pnpm install --frozen-lockfile
uv run leaf-dev eval [CASE]... --base --harness claude-code|codex [--repeat N]
pnpm run eval:view
```

`evals/README.md` owns selection, arms, conditions, the case format, where the
results go and how far a pass can be trusted. Read the outputs as well as the pass
counts.

Score with the cases already there wherever one fits, and add to the suite sparingly:
every case costs time and money on each later run that selects it. Where an existing
case nearly fits, extend it with an assertion, a criterion, or context in its prompt.
Add a new case only where the change needs measuring and no existing case can carry
the behavior. What the suite holds then scores later edits, whether fixes or cuts,
against the behaviors earlier edits had to produce. Keep a case small: one prompt
carrying only the context the behavior needs, and a few assertions. Explore whatever
scenarios the change needs, then retain only cases that cover distinct failures or
necessary controls. Exploratory variants and their evidence stay in the run directory. Remove
contexts another retained case already covers. The leading comment records the
case's origin and whether it distinguished the instructions.

The prompt never states the behavior under test. A prompt pointing at a file beyond
the references names that file from the skill's base directory. Grade a fixed form
with a `regex` assertion, and a judgment with an `llm-rubric` assertion whose `value`
states the passing reading without requiring particular wording.

Run cold, a case that states the situation plainly usually passes on both arms: the
failing session had its own earlier turns or a competing instruction pulling the
other way, so paste those into the prompt. A rule that loses only to a long
session's context needs a replay of that session instead. Retain the smallest replay
that detects the failure; a diagnostic does not need a complete workflow to earn or
retire its place.

## Refresh the public catalog stills

When a change adds or removes a worked example or changes its first viewport,
run `wt refresh-previews` from the repository root on macOS once the examples
are ready, and again after integrating `main` or any later fix that changes a
first viewport. It pushes the stills to `max-sixty/leaf-assets` and moves the pin
in `leaf-assets.json` and the README's image URLs. `uv run leaf-dev record-demo` does the same for the README's
recording and stills and the site's card. Run `wt setup` first in a new checkout;
if Worktrunk asks to approve the project commands, ask the user to run
`wt config approvals add`.

## Land a change

Before handing over a change that adds to an area `AGENTS.md`, ask of each addition
whether one module owns it. If one does, the rule goes in that module's header and
the area file keeps at most a pointer (root `AGENTS.md`, "Where instructions live"),
so the area file holds only what spans its modules and trimmed text does not come back.

Thread appearance changes run `tests/*/test_render_thread_snapshots.py` on macOS
before landing. Linux CI runs the same delivery journey without comparing images.
Review captured Mac images before accepting an intentional change;
`dev/leaf_dev/thread_snapshots.py` owns capture and acceptance.

A pull request's `test` job and the local pre-merge `tests` run the broad selection
and the later-tier tests the branch edits; the rest of the `main` tier runs once main
moves, the `nightly` tier in the daily run, and `tend-ci-fix` answers them when they
fail (`tests/AGENTS.md`, "Run what the change needs").
`wt merge` checks the rebased tree and lands it; `✗ Can't push to local main branch`
is a fast-forward failure.

Installed sessions load harness caches, not the checkout. Claude Code picks up a
push on its marketplace sweep; Codex refreshes configured Git marketplaces and
installed plugins at startup. Both follow the configured ref, `main` by default.
For an immediate Codex refresh in a running session, run
`codex plugin marketplace upgrade leaf`.
