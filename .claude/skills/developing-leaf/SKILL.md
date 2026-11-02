---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, check that
`<root>/bin/leaf --root` prints that root, and run every `leaf` command through that
absolute launcher; a bare `leaf` may run the installed plugin instead.

Before writing words the user sees, such as a label, status line or placeholder, or
naming anything they operate or an identifier for one, read `references/glossary.md`,
Leaf's canonical vocabulary and guidance for visible text. A control may
need no words at all (`<root>/browser/AGENTS.md`, "Controls are few and quiet"). Before
changing anything Leaf draws, read that file's "Leaf's interface".

## Take a backlog item

Pick an issue labelled `backlog`, not `waits-on-user`, that no pull request links
(`TODO.md` has the query), and open its pull request early, as a draft if need be,
with `Closes #N` in the body, so the next session sees the item taken.

## Read the owning contract

A contract shared across modules or runtimes lives in a reference beside the Python
code that owns it; `<root>/src/AGENTS.md` lists them under "Protocol
references". To check what the code does, call it: `leaf` and `leaf_dev` are installed
editable, so `uv run python -c 'from leaf... import ...'` works as is. A tag's schema
is in the registry of the package that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  browser/registry.json packages/*/registry.json
```

A fact both runtimes use has one home (`browser/AGENTS.md`, "Facts both
runtimes know"). When a change adds a parity fixture, or a test that scans one
language's source for the other's names, ask why the fact isn't generated.

Before adding tests for developer tooling or benchmarks, or selecting checks for
them, read `dev/AGENTS.md`, "Tests"; `tests/` holds product behavior.

## Review a UI change

Record browser API and rendering support gaps in
[`notes/browser-support.md`](../../../notes/browser-support.md), as its "Recording and
assessing a gap" section says.

The user judges a UI change by using it and by looking at it, so review both before
handing it over. Whoever reviews it, you or an independent reviewer, first uses the
live candidate cold for the user's task, before reading its code or the author's
account, reaching each result by every route Leaf gives to it and capturing each state
those routes leave. A reviewer's brief gives the task and the candidate and asks for
that pass before any code review. An agent that has driven, measured or read the
change sees the screen through that work and misses flaws a first look catches; a
fresh agent given only the captures and the user's request, and asked what looks
wrong, is one way to get that look. For a theme or shared-control change, also run
`/ui-sweep` (`../ui-sweep/SKILL.md`), whose "Review a design system" section covers it
and whose "External review" section says when to use the skills below.

### External UI skills

These optional skills are installed separately from Leaf; check the harness's
available skills before invoking one.

- [Impeccable](https://github.com/pbakaus/impeccable#installation):
  `/impeccable critique` for hierarchy, grouping and clarity, `audit` for technical UI
  quality, and focused workflows such as `layout` and `typeset`.
- [Web Design Guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines):
  `/web-design-guidelines` for interface conventions, accessibility, navigation, forms
  and motion.
- [Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design):
  `/frontend-design` for new compositions or an intentional redesign.
- [Emil Kowalski's skills](https://github.com/emilkowalski/skills): `review-animations`
  for motion, which refuses model invocation, so read its `SKILL.md` and
  `STANDARDS.md`; `/break-ui` for worst-case content, keeping the demo-data toggle it
  adds out of a shipped page.
- [Mblode UI skills](https://github.com/mblode/agent-skills): `/ui-animation` for
  motion and interruption, `/ui-design` Audit for visual quality and Break for extreme
  content, `/ui-verification` for browser reproduction, and `/product-design` for
  action scope, recovery and consistency across input routes.

## Leave taste to the authoring agent

Code enforces only what Leaf needs to work: a contract between modules, or a guarantee
the user relies on, such as a gesture being recorded or a pressed control staying where
it was (`browser/AGENTS.md`, "The page holds still under the user's aim"). Taste goes
in the shipped instructions as a
goal with its reason, so the authoring agent weighs it against its own page. A CSS
rule, validator or Layout that fixes how many tiles share a row overrides every page
that needs another number. A check may report what it sees, as the render check names
where a tile row wraps, and leave the decision to the agent.

`page check` and its render checks enforce Leaf's page contracts: they report widget
initialization failures and unintended clipping of content or controls.
A rare authoring mistake costs one fix, or a clearer line in the instruction the agent
misread, so prefer widening a general check to adding one for a particular mistake.
Add a narrow check, or a note a command prints, only where agents get something wrong
on real pages and fix it when told. Before adding one, estimate its precision (the
share of firings that were needed) and recall (the share of the failure's occurrences
it catches) on real pages and sessions, not only on the failure that prompted it, and
weigh them with what a missed failure costs.

## When to pass guidance back to the authoring agent

Pass guidance back when it helps the author improve the user's result, weighed against
the interruption and the cost of another rule (root `AGENTS.md`, "Leaf's role"). First
ask whether Leaf should provide the behavior itself, so the author needn't work around
incidental markup restrictions.

Refuse input only when proceeding would break a guarantee, and say how to fix it where
the author can act. Use the owning parser or validator rather than repeating its rules,
and let its message reach the author: `patch_manifest.py` stores a patch as given, and
`lf-diff` reports a file it can't draw with `reportFailure`. A reader's current
limitation alone doesn't justify a restriction. Where the author must judge the
evidence, report the observation without making it a requirement, and say what was
checked and what was not. When a markup contract changes, update its reader,
validation, dependent layout rules and instructions together.

Data passed between Leaf modules over a channel only Leaf can write needs no input
validation. This includes the server's answer to the browser and the build manifest
the Worker reads. The reader uses that data directly, and the producer's tests verify
its shape. Data a person or agent can modify is input, even when Leaf code sent it:
a request the browser posts, a file an agent edits, or the answer from leaf.page's
container, where a visitor directs the agent.

## Explore an open design

When the user is to choose among designs for a visual or interaction question, show
the candidates side by side in one decision, where the user can compare them, try the
interactions, comment, and pick the one to build. Their pick, or the configuration a
playground submits, is the one implementation the change keeps. First look in the
shipped examples and `notes/` for an exploration of the same surface, and extend it
when it covers the same decision.

The exploration is one HTML file under `.tmp/`, served with
`uv run leaf-dev preview --source <file> --user` ("Preview a page"); its CSS reads the
live theme's tokens. Follow `<root>/packages/playground/instructions/author.md`
to choose the elements, present the candidates, and say what to build.

To change an existing interface, take this checkout's rendered interface as the
baseline, covering the controls and states the requested property affects. Build
runtime candidates in the runtime and theme that own the surface. A separate sketch
copies Leaf's mark from `browser/icon.svg` and each icon's path from
`browser/runtime/icon-paths.js`. Drive the baseline and every candidate through
the same journey before handoff.

## Choose what the user reviews

Prefer outputs the user can review quickly. Do the reviews you can do as well as the
user, and report the results. Choose the decisions the page puts to the user from
their request, and show visible and interaction changes with the proof below.

A choice about how something looks or moves can't be judged from a description, so
every UI option you leave to the user carries a picture of its result: a still pair, a
sketch, a diagram or a live sample. That includes the calls a PR body leaves to the
user, and the decisions a page relays from it.

## Prove and hand off a visible change

Define the user's task and each step's expected visible outcome before choosing
controls or checks. A reader should be able to tell which labels, symbols and
destinations belong together before activating them. Exercise each route from the
states that change its effect, such as when its destination is already open or another
item is selected; finishing the task by one route proves only that route.

Open the exact preview URL in a fresh browser context and check those outcomes on
arrival and through ordinary input; setup the user can't repeat belongs in the fixture.
Judge legibility and layout in the states ordinary input produces, in every affected
color scheme, at a representative desktop viewport, including the hovered or
keyboard-targeted item inside an open surface. Capture the viewport when fixed chrome
should appear: a Playwright screenshot of an element taller than the viewport draws
fixed overlays in the wrong place.

Derive the required visual relationships from the reader's task, not from the checks
that pass. For each ordinary input, state which content and controls the reader needs
to keep in view or reach next, then check before and after the input, in the delivered
page, embedded views included, that each stands where the task needs it and that the
user can see and reach it. A control's box and opacity can be right while something
paints over it, so reach it as the user does, with a Playwright hover or click, whose
actionability check refuses a covered control. Make those relationships hold as content
and sizes change, through layout constraints or positions derived from one shared
dimension, and check the constraints in the source too, since a screenshot can hide a
small misalignment. A server keeps the runtime and layer it started with, so judge a
runtime, theme, registry or widget change on a server started after it.

To ask a page where an element sits, what style it computes, or what holds focus after
a key, run `uv run leaf-dev probe` rather than writing a Playwright script or a scratch
test. It builds the page from this working tree, with `--log` adding threads and
messages to its log, runs your input steps, and prints what a JavaScript expression
returns, with `--base` for the merge base beside it (`leaf-dev probe --help`).

When an interaction depends on a sequence of inputs or changes over time, record it
with `leaf-dev probe --record .tmp/recordings/NAME` (its `--help` covers journeys and
serving the trace), review the frames at their recorded times, and show
the trace on the Leaf page in `lf-trace` (`skills/leaf/references/authoring-evidence.md`,
"Source files and media"). For an important result, assert the outcome from the user's
task with a Playwright expectation: disclosure and focus prove only themselves, and
returning from the input doesn't prove an asynchronous update finished.

`uv run leaf-dev stills` crops each changed catalogue state into a before/after pair
and lists the computed styles that differ in it, shadow trees included, with the
declarations behind them (its module header covers committing first and
`--authored`). For a change to where a rule sits,
such as its sheet, layer or selector, read those lists, with the corpus states
covering every composed page, rather than writing a computed-style sweep. Cover states
reached by interaction, including focus states where layout can cover a focus ring,
and add a missing state to `STATES` rather than driving it by hand.

Hand off every difference a still can show as a Leaf page with an `lf-shot` of the
crops and a sentence saying what changed, and link the page in the reply; a live
preview may accompany the pairs but doesn't replace them. Show a difference once, in
the state where it reads most clearly, naming the states that repeat it, and add a
dark-scheme or phone pair only where the change looks different there. For an
interaction-only change, compare the same journey on both versions ("Compare checkout
versions"). A live preview handed to the user carries the fragment of the section it
is about and stays running.

## Preview a page

`uv run leaf-dev preview <example>` serves a live page that follows source and browser-runtime
edits at one URL; `--source <file>` serves any HTML file. Its module header
(`dev/leaf_dev/commands/preview.py`) covers slots, restarts and which previews detach.
Start one that stays in the foreground as a long-running command (`run_in_background`
in Claude Code).

Python, schema and dependency edits require restarting the preview; its log says when.
For a user preview, stop its page server and rerun the same preview command to keep its
URL and comments. A plain preview starts fresh on restart.

Drive only plain previews, since every click this session drives on a `--user`
preview arrives as an unanswered update, and start a `--user` preview only from the
session the user talks to. Don't close a preview to quiet the loop; `page close` ends
the agent's side of the page, which the panel shows as Page closed.

For finite checks, prefer `leaf-dev probe` or `stills`, which close their servers when
they finish, and serve the smallest fixture that keeps the journey and its
surroundings. Separate page directories keep reviewers' comments apart, and fresh
browser contexts keep browser storage apart, without another browser or Python
process. Close a browser session you opened when you finish with it; a custom runner
closes its servers and browsers on success, failure and cancellation. Previews and
trace viewers handed to the user keep running for their review.

In Codex, start the preview with `--user` from the current chat, which connects the
page to this chat before printing the URL. Open the printed URL with the section's
fragment through `mcp__codex_app__open_in_codex` as a browser target with
`placement: "right"`, and tell the user to comment on the page to steer this chat.
Comments inside a live sample stay in that sample.

## Run the agent journey

`uv run --project <root> leaf-dev journey TARGET` runs one user's journey against a
real agent and times each step on the page server's clock. Its `--help` lists the
targets and options, and each target's module header lists its steps and the promises
it checks. A run spends the target's login. Add `--browser` when what the page shows
is part of the change.

The suite only stands in for each harness, so run the journey on the harness a change
touches:

- `claude-code` (`journey_claude_code.py`): after a change to `hooks/hooks.json`,
  `hooks/claude-code.ts`, `ClaudeCodeHarness`, `hooks.py`, or the watch between turns
  in `session.py`. Add `--sandbox` after a change to `bridge.py`, the README's "Agent
  sandboxes" settings, or what a `leaf` command needs from outside its page directory,
  and `--forks` after a change to `forks.py` or the module's `forkReply`.
- `codex-app-server` and `codex-queue` (`journey_codex.py`), both: after a change to
  `codex.py`, `codex_adapter.py`, `hooks.py`, `hook_transport.py`, or the claim's turn
  in `service.py`. Add `--preview` for a change to preview startup or lifetime, and
  `--sandbox` for a change to `codex_tool.py`, the MCP server in
  `.codex-plugin/plugin.json`, or what a `leaf` command needs from outside its page
  directory.
- `pi` (`journey_pi.py`): after a change to `hooks/pi.ts`, `PiHarness`, `hooks.py`, or
  the watch between turns in `session.py`.

For the website, `tests/AGENTS.md`, "Run what the change needs", says which delivery
checks CI runs, and `worker/README.md`, "Local development", how to reproduce a Worker
or container failure. Only the `publish-site` workflow's journey against the deployed
release reads production.

To benchmark replies, run each harness's journey a few times, with and without
`--case working`, and tabulate the samples with `leaf-dev journey-chart --replies`;
`leaf-dev response-times` measures retained pages and sorts each pickup's wait
by what ended it, which shows the waits only long real sessions have
(`dev/leaf_dev/commands/response_times.py`). The benchmark is the whole reply's time,
which `dev/leaf_dev/reply_phases.py` attributes to Leaf's delivery, commands and hooks,
the harness, the model's wait and generation, and the agent's other tools. Model time
varies widely from run to run, so compare a phase Leaf owns directly, and the whole
reply over enough runs to see past that spread.

## Compare checkout versions

`uv run leaf-dev compare <example>` serves the merge-base runtime beside this checkout,
in the foreground as a preview runs ("Preview a page"); `--help` lists the flags. Keep
the default shared source for a runtime change, pass `--authored` when the authored
content changed, and pass `--user` only when the URLs go to the user.

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped example or
fixture, a playground, or a page for this conversation. Before writing its content,
read `<root>/skills/leaf/SKILL.md` completely and follow its authoring, validation,
handoff and conversation-loop routes, using the checkout launcher and resolving its
references from `<root>/skills/leaf/`. Read it again after a compaction, before the
page's next revision or handoff. A brief for a subagent that writes the page names the
content and the decisions to put to the user, and leaves how to pose them to those
instructions.

To make an existing page use the current checkout, serve it with the checkout
launcher, and run that launcher's `page init` on a page at another protocol
(`<root>/skills/leaf/references/serving-pages.md`, "Leaf updates"); fix or report a
compatibility refusal rather than falling back to the installed plugin.

A page that explains how a Leaf widget, verb or event flow behaves lets the user try it
in a live sample (`<root>/skills/leaf/references/live-samples.md`) holding only the
demonstrated page and an `lf-activity` feed of its own log. Make the next gesture and
its visible result clear as the user tries the sample, including Undo. Guidance beside
the relevant step lets the user learn by operating the page. Before handoff, operate
the sample using only its visible guidance and read each line the feed prints, so the
review checks whether the user can work it without the author's knowledge.

## Keep authoring a page fast

Leaf is often a developer tool, used by one person waiting on the page in the middle
of their own work, so the time an agent takes to produce a page is usually part of
its quality. Shipped instructions keep that path short: write the page, run
`page check`, look it over and hand it over. Keep a reviewer subagent, render pass or
critique round off the path most pages take, and put it in the reference for a page
that has to be especially well made, such as one that will be published.

When pages keep failing the same way, improve the guidance the author reads while
writing, and measure it in `evals/`. That guidance is usually the workflow's reference
rather than a registry entry (`skills/leaf/references/packages.md`, "A widget"), and a
passage that has grown into a list is rewritten around its goals
(`/improving-instructions`, "Authoring the change"). The fix states the goal the
failing page missed and what an author weighs to meet it, and offers the form that
passed the eval as a default to depart from where the content calls for it, not as a
requirement.

## Score an instruction change

Score an instruction change when you can't be sure how an agent will read it: a new or
reworded rule, a goal that competes with another, or a cut that may have carried a
behavior. Deleting a description of an input that can no longer arrive, or correcting
a fact, needs no score.

Choose the eval by what the instruction is for:

- General agent behavior: personal-skill evals (`/improving-instructions`, "Validate
  with evals").
- Leaf's shipped workflows: Leaf's suite in `evals/`.
- Maintainer guidance, such as this skill or an `AGENTS.md`: a temporary A/B in scratch
  that gives each arm its version of the passage, with no committed case, unless the
  development contract needs the suite's staging, such as a served page or an
  installed arm.

For Leaf's suite, run the merge base beside the working tree with `--base`;
`evals/README.md` owns the commands, selection, arms, the case format and where results
go. Score
every case whose `metadata.tags` covers the passage, such as `asks` for decisions,
counting only runs that opened the changed file (`/improving-instructions`,
"Confirming each arm loaded what you edited"), and read the outputs as well as the
pass counts.

Extend an existing case wherever one nearly fits, since every case costs time and
money on each later run, and keep only cases that cover distinct failures or necessary
controls. Give the subject the task, context, tools and handoff it would receive in
normal use, with only the fixture facts the case needs, and keep grading criteria and
harness bookkeeping out of its input. Let the installed instructions teach the
workflow rather than repeating their procedure or directing the subject to the rule
being measured; a replay preserves what the recorded session had read. A diagnostic
that deliberately supplies a skill or rule measures behavior with that context, not
whether ordinary use discovers it, so name that limit when reading its result. A
case that states the situation plainly usually passes on both arms, so paste in the
earlier turns or competing instruction that pulled the failing session the other way.
A rule that fails only late in a long session needs a replay of that session.

## Refresh the public catalog stills

When a change adds or removes an example or changes its first screen, run
`wt refresh-previews` from the repository root on macOS once the examples are ready,
and again after merging `main` or any later fix that changes a first screen.
`uv run leaf-dev record-demo` does the same for the README's recording and the site's
card (`dev/AGENTS.md`, "Commands with consequences outside `.tmp/`"). Run `wt setup` first in a new checkout; if
Worktrunk asks to approve the project commands, ask the user to run
`wt config approvals add`.

## Weigh what a change adds

Whoever writes or reviews a change asks whether what it adds is worth what later
changes and users pay for it, by the bar "Regular maintenance" sets for code already
there. Size says little: a two-line selector can reach every page.

- **What it adds**: a mode, branch or special case; one more member of a set,
  allowlist or tolerance; a wait, retry or timer; a public option; room reserved for a
  state that may not come; a second statement of a rule with an owner; a reliance on a
  dependency's internals.
- **What it buys**: a behavior a user sees, a request the maintainer made, or a
  measured cost. A green test buys what the test protects, so name that.
- **Where its cost lands**: read the change's reach rather than its claim, such as a
  selector's or guard's scope against the condition it names, what else inherits from
  or sits in the box it changes, and how often a guard fires on a correct setup. Then
  compare who pays with who gains: a cost paid in every state or on every page to fix
  one transition usually outweighs it.
- **The cheaper change**: a platform or dependency primitive, the fix in the owner
  rather than a caller, the stale copy deleted, or the gap left open with an issue.
  When `git log -L` shows earlier changes compensating for the same gap, ask whether
  the mechanism is the wrong primitive and the cheaper change its general form.

Keep an addition whose benefit is concrete when no cheaper change buys it, as with a
fix in a primitive every caller gains from; otherwise make the cheaper change, or ask
for it in review. When the fix for a finding would add another branch, flag or
condition, first ask whether the finding is about the approach.

## Regular maintenance

Whenever a survey, a review or the nightly sweep reads a file, look for code that
makes Leaf harder to develop than it is worth:

- **A mechanism users wouldn't miss.** Ask who would notice it gone and what it costs
  the changes around it. Code woven into the core runtime, the server or a shared
  contract costs every nearby change, so it must clear a much higher bar. Signs it
  doesn't: a hold, carry or special case for one widget or gesture spread across
  several owners; a public API whose only callers are tests or a single example; a
  mechanism `git log --follow` shows patched again and again (without `--follow`, a file's
  history stops at its last move). Code in its own module, such as a
  package, a widget or a `leaf-dev` command, costs little beyond its own files; remove
  it only when it is large and unused. Keep anything users would notice losing,
  including Leaf's interface guarantees. Taking a feature away is the maintainer's
  call, so propose the removal with what users lose and what it deletes.
- **Several implementations of one capability.** Consolidate them into one home and
  move every caller to it (root `AGENTS.md`, "Fix the underlying issue").
- **A mechanism a dependency or the platform already provides.** Delegate it (root
  `AGENTS.md`, "Use dependencies").

Measure a candidate by making the change in a scratch worktree: `git diff --numstat`
gives what it deletes, and a probe or capture of the affected journey shows what users
lose. A count read off the code overstates the saving.

## Land a change

Before handing over a change that adds to an area `AGENTS.md`, ask of each addition
whether one module owns it; if one does, the rule goes in that module's header (root
`AGENTS.md`, "Where instructions live").

The thread appearance gate, `tests/*/test_render_thread_snapshots.py`, is paused
(issue #4046, "Resume the thread appearance gate"), so a thread appearance change needs
no snapshot run before landing. `tests/AGENTS.md`, "Selecting checks", says what the
landing gates run and what a failure there means. `wt merge` checks the rebased tree
and lands it; `✗ Can't push to local main branch` means a fast-forward failed.

Installed sessions load harness caches, not the checkout, and follow `main`: Claude
Code picks up a push on its marketplace sweep, and Codex refreshes at startup. To
refresh Codex in a running session, run `codex plugin marketplace upgrade leaf`.
