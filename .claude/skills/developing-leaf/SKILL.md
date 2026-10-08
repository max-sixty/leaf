---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, then resolve
`<root>/bin/leaf` to an absolute path. Run that launcher with `--root` and
continue only when it prints the same repository root. Use the absolute launcher
throughout; a bare `leaf` may resolve to the installed plugin instead.

Read `references/glossary.md` before naming or revising user-facing elements,
interaction contexts, navigation, chrome, view state, or an identifier governed by
those concepts. It is Leaf's canonical implementation vocabulary.

## Read the owning contract

For a contract shared across modules or runtimes, read the sidecar beside the
Python code that owns the boundary;
`<root>/skills/leaf/scripts/AGENTS.md` lists them under "Protocol references".

To check what the code does, call it: the checkout's environment installs `leaf`
and `leaf_dev` editable, so `uv run python -c 'from leaf... import ...'` imports
either without a `sys.path` edit. A tag's schema is in the registry of the package
that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  skills/leaf/assets/registry.json skills/leaf/packages/*/registry.json
```

## Review a UI change

For browser API and rendering support, maintain
[`notes/browser-support.md`](../../../notes/browser-support.md), following its
"Recording and assessing a gap" section.

Before handing over a change to browser controls, navigation, focus, motion,
forms or layout, read and follow `/ui-sweep` at `../ui-sweep/SKILL.md` on
the changed surface and its dependent interactions. Its "External review"
section owns selection and use of the tools below.

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
pointer. Taste, formatting and aesthetics go in the shipped instructions, as a goal and
its reason, so the authoring agent weighs them against the page in front of it. How
many tiles share a row, where a heading breaks, which column is wider: a rule in CSS,
a validator or a Layout that fixes one of these for every page overrides the agent
where its page needs something else, and breaks on the next case it wasn't written
for. A check may report what it sees, as the render check names where a tile row
wraps, and leave the call to the agent.

## Leave old state out of the handoff

Leaf owes nothing to state an earlier version wrote (`AGENTS.md`, "Stage"). A
handoff doesn't say that an existing page, log, or claim predates the change or
needs re-vendoring, and doesn't list reviving it as follow-up work.

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
`lf-sample window` children.
The outer page carries the configuration and feedback; the children carry practice
interactions. Start their fictional histories with `data-sample-events`, sharing
one parent-local JSON fixture when the candidates need the same conversation
(`skills/leaf/references/page-authoring.md`, "Live samples").

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
states and motion. Review the final exported recording through playback or decoded
frames at their recorded times, including its loop boundary; select the interval
that shows the behavior being reviewed. Use that same probe with
`--record .tmp/recordings/NAME`.
Its Playwright trace has an action timeline, a screenshot
filmstrip, DOM snapshots, console and network; its WebM shows the actual frames.
Add `--gif` for a short shareable loop, or `--actions` to decorate clicks and keys.
`--journey FILE` runs a Python file's `run(page)` using Playwright's full API,
including assertions; it returns a JSON reading. Capture keeps the journey's
timing without adding pauses, and defaults to normal motion. `--actions` is for
demonstrations: Playwright waits 500 ms before each annotated input, so omit it
from timing-sensitive reproductions. Native video holds the final frame for at
least one second. `--motion reduce`
reproduces the reduced-motion preference. A failed journey keeps its recording
and exits unsuccessfully. The same command takes any HTTP(S) URL for general
browser work. Keep the page and context open until the recorder finalizes:
Playwright cannot save screencast video after its page closes. Serve the trace
without opening a desktop browser with:

```bash
uv run leaf-dev trace-server \
  .tmp/recordings/NAME/worktree/trace.zip
```

The command prints the viewer URL and stays running. Link that URL in the review
page; open a desktop browser only when the user asks to watch.

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
Add `--checkpoint-images` alongside `--record` when the review needs native PNG images
at those checkpoints. Taking them adds capture work and briefly hides the live
caret, so omit it when ordinary motion and caret behavior are the evidence.

`uv run leaf-dev stills` compares HEAD with the merge base with `main` and crops
each changed catalogue state into a before/after pair. Commit first, since it
compares commits. Include pages at rest and states reached by interaction,
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

`uv run leaf-dev preview <example> --export` writes one file that opens offline.
`uv run leaf-dev preview <example>` serves a live page at `.tmp/previews/<example>`
in the foreground, like a dev server, so run it as a long-running command
(`run_in_background` in Claude Code). A desktop Codex `--user` preview instead
detaches its watcher and returns its URL: the page and feedback stay available
when Codex unloads the chat's idle instance. `--source <file>` serves any authored HTML
file in place of a shipped example. It follows source and runtime edits at one
URL; each start rebuilds the page from the fixture, and `--slot <name>` runs another copy.

A plain preview takes no task claim, so its presses reach only the page's log;
use it for screenshots and browser checks. `--user` claims the page at
the directory printed at startup (`.tmp/previews/<example>-user` by default;
`--slot` chooses the directory name) so the user's comments reach the harness, which
also makes every click this session drives there read as an unanswered user
move. So drive only claimless previews, start any `--user` preview from the
session the user talks to, and answer the user's feedback before restarting
their preview, since a restart discards the claim and the moves it held. Don't
idle a preview to quiet the loop; `idle` closes the page in the browser.

### In Codex

1. Start the preview with `--user` from the current
   chat. It connects Leaf feedback to this Codex chat before printing the URL;
   desktop Codex returns after the detached watcher subscribes to source edits.
   Each restart reconnects the rebuilt page automatically.
2. Call `mcp__codex_app__open_in_codex` with the printed keyed URL and the semantic
   block's fragment, as a browser target with `placement: "right"`.
3. Tell the user to comment on the surrounding review page to steer this chat.
   Comments inside a live sample are practice interactions in that child. Codex
   Annotation mode sends visual comments with the next chat message; Leaf's text
   selection and comment affordance send an anchored thread directly.

## Run the agent journey

`uv run --project <root> leaf-dev journey TARGET` runs one user's journey in
Chrome: on the triage board, it tells the agent through Threads that a release
passed its checks and asks it to record that, leaving how to the agent, then checks
a reply shows and a reload presents a revision naming the release. It prints how long each step took, the agent's steps on the page
server's clock, so the same journey benchmarks every harness. TARGET is `claude-code`
or `codex` for an isolated session of that harness running this working tree's
plugin, `local` for the website's adapter against the host's Codex login (no
Worker, container limits, credential proxy or Docker), `wrangler` for the built
site through the local Worker, or a website origin. A run on this machine spends
the harness's login.

`tests/AGENTS.md`, "Run what the change needs", owns the CI delivery checks and
when to reproduce a Worker/container failure locally. `worker/README.md`, "Local
development", owns that reproduction setup. The `publish-site` workflow verifies
the complete boundary before deployment; its journey against the deployed release
is the only production reading.

## Test a terminal Codex task

`uv run --project <root> leaf-dev verify-codex-task` runs real Codex tasks, with
this working tree installed as their plugin, through both transports of automatic
server handoff. It checks each comment is answered once, a comment during queue-backed
work is picked up and answered in that same turn, and each turn is closed under
App Server's id. Run it after a change to `codex.py`,
`codex_adapter.py`, `hooks.py`, `hook_transport.py`, or the claim's turn in
`service.py`; the suite scripts App Server, and only this run shows what Codex
itself sends. It spends a few turns on the host's Codex login, and CI has none.

For a change to preview startup or lifetime, add `--preview`. It starts the
canonical user preview in each task, checks the keyed URL across those turns,
and interrupts its isolated server between turns to prove that the preview
restores both the address and working feedback without a source edit.

## Test a Claude Code session

`uv run --project <root> leaf-dev verify-claude-code-task` runs a real interactive
Claude Code session in a tmux pane, with this working tree as its plugin and the
host's login.
It checks each comment is answered once, a comment during a turn is picked up in
that turn, comments after an Escape are answered, and quitting ends the session's
claim; `--hooks-module` runs the same journey with the plugin's hooks module on,
and also checks that Escape closes the turn and leaves a watch running. Run it,
with and without the flag, after a change to `hooks/hooks.json`,
`hooks/claude-code.ts`, `ClaudeCodeHarness`, `hooks.py`, `loop-guard.py`, or the
watch between turns in `session.py`; the suite stands in for Claude Code, and only
this run shows what Claude Code itself does.

## Test a Pi session

`uv run --project <root> leaf-dev verify-pi-task` runs a real Pi session, the
version `dev/pi/` pins, with this working tree installed as its Pi package and the
host's Codex login as its only login. It checks each comment is answered once, a
comment during a run is answered in that run, Escape closes the turn without waking
Pi again, and quitting ends the session's claim. Run it after a change to
`hooks/pi.ts`, `PiHarness`, `hooks.py`, or the watch between turns in `session.py`;
the suite drives the extension with a stand-in for Pi, and only this run shows what
Pi itself does.

## Compare checkout versions

Build the baseline in a detached worktree at the merge base:

```bash
candidate_root=$(git rev-parse --show-toplevel)
baseline_commit=$(git merge-base HEAD main)
baseline_parent=$(mktemp -d "${TMPDIR:-/tmp}/leaf-baseline.XXXXXX")
baseline_parent=$(cd "$baseline_parent" && pwd -P)
baseline_root="$baseline_parent/checkout"
git worktree add --detach "$baseline_root" "$baseline_commit"
```

Choose sources that isolate the change: one shared source for a runtime change,
or each checkout's copy when the authored content changed. Run the two previews
as separate commands, adding `--user` to both when their URLs go to the user.
Keep foreground previews running; desktop Codex user previews return after
startup:

```bash
uv run --project "$candidate_root" leaf-dev preview --source <baseline-source.html> \
  --runtime "$baseline_root" \
  --slot <slot>-baseline
```

```bash
uv run --project "$candidate_root" leaf-dev preview --source <candidate-source.html> \
  --runtime "$candidate_root" \
  --slot <slot>-candidate
```

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped
example or fixture, a playground, or a page made for this conversation. Before
writing its content, read `<root>/skills/leaf/SKILL.md` completely and follow
its authoring, validation, handoff, and conversation-loop routes, using the
checkout launcher for every `leaf` command and resolving its references from
`<root>/skills/leaf/`.
To make an existing page exercise the current checkout, re-vendor it with the
checkout launcher (`<root>/skills/leaf/references/serving-pages.md`); fix or
report a compatibility refusal rather than falling back to the installed plugin.
A page that explains how a Leaf interface behaves lets the user operate it
(`references/page-authoring.md`, "Live samples").

## Score an instruction change

Score an instruction change when an agent could read it more than one way, so what
it will do under the new text is uncertain: a new or reworded rule, a goal that
competes with another, a cut that may have carried a behavior. A change whose reading
is plain needs no score, such as deleting the description of an input that can no
longer arrive or correcting a fact. Run the cases that bear on it on both the merge
base and the working tree:

```bash
npm ci --prefix evals
uv run leaf-dev eval [CASE]... --base --harness claude-code|codex [--repeat N]
npm run view --prefix evals
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
necessary controls. Internal maintainer evals stay small and
sparse; exploratory variants and their evidence stay in the run directory. Remove
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

Thread appearance changes run `tests/test_render_thread_snapshots.py` on macOS
before landing. Linux CI runs the same delivery journey without comparing images.
Review captured Mac images before accepting an intentional change;
`dev/leaf_dev/thread_snapshots.py` owns capture and acceptance.

A red gate is the branch's to fix. A pull request's `test` job and the local
pre-merge `tests` run the broad selection and the nightly tests the branch edits;
the rest of the nightly-marked tests run once main moves, and `tend-ci-fix` answers
them when they fail (`tests/AGENTS.md`, "Run what the change needs").
`wt merge` checks the rebased tree and lands it; `✗ Can't push to local main branch`
is a fast-forward failure.

Installed sessions load harness caches, not the checkout. Claude Code picks up a
push on its marketplace sweep; Codex refreshes configured Git marketplaces and
installed plugins at startup. Both follow the configured ref (`prepared` for
consumer installs). For an immediate Codex refresh in a running session, run
`codex plugin marketplace upgrade leaf`.
