---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, check that
`<root>/bin/leaf --root` prints that root, and run every `leaf` command through that
absolute launcher; a bare `leaf` may run the installed plugin instead.

## Take a backlog item

Pick an issue labelled `backlog`, assigned to nobody, that no pull request links
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

## Review a UI change

Record browser API and rendering support gaps in
[`notes/browser-support.md`](../../../notes/browser-support.md), as its "Recording and
assessing a gap" section says.

Whoever reviews a UI change, you or an independent reviewer, first uses the
live candidate cold for the user's task, before reading its code or the author's
account, reaching each result by every route Leaf gives to it and capturing each state
those routes leave. A reviewer's brief gives the task and the candidate and asks for
that pass before any code review. An agent that has driven, measured or read the
change sees the screen through that work and misses flaws a first look catches; a
fresh agent given only the captures and the user's request, and asked what looks
wrong, is one way to get that look. The `/ui-sweep` pass (`../ui-sweep/SKILL.md`) a
theme or shared-control change gets follows its "Review a design system" section, and
its "External review" section says when to use the skills below.

### External UI skills

Optional reviews from outside Leaf, installed separately, cover visual critique,
interface conventions, motion, worst-case content, and each composite control's
keyboard and ARIA structure. `references/external-ui-skills.md` names them and says
how to run each.

## Checks and guidance for the authoring agent

Code enforces only what Leaf needs to work, and taste goes in the shipped
instructions as a goal with its reason. Read `references/checks-and-guidance.md`
before adding or changing a rule, check, refusal or message that constrains or answers
an authoring agent.

## Explore an open design

To build the side-by-side choice root `AGENTS.md` asks for when the user is to choose
among designs, follow `references/explore-a-design.md`.

## Choose what the user reviews

Prefer outputs the user can review quickly. Do the reviews you can do as well as the
user, and report the results. Choose the decisions the page puts to the user from
their request, and show visible and interaction changes with the proof below,
including the picture root `AGENTS.md` asks for with each UI option you leave to them.

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
returns, with `--base` for the merge base beside it and `--browser` for another engine
(`leaf-dev probe --help`). To reach a surface a stills state reaches, open the state
with `--state NAME`, which brings its page there in its window, rather than repeating
its input as steps.

When an interaction depends on a sequence of inputs or changes over time, record it
with `leaf-dev probe --record .tmp/recordings/NAME` (its `--help` covers journeys and
serving the trace), review the frames at their recorded times, and show
the trace on the Leaf page in `lf-trace` (`skills/leaf/references/authoring-evidence.md`,
"Source files and media"). For an important result, assert the outcome from the user's
task with a Playwright expectation: disclosure and focus prove only themselves, and
returning from the input doesn't prove an asynchronous update finished.

`uv run leaf-dev stills` crops each changed catalogue state into a before/after pair
and lists the computed styles that differ in it, shadow trees included, with the
declarations behind them (its module header covers `--base`, `--authored` and
`--browser`). For a change to where a rule sits,
such as its sheet, layer or selector, read those lists, with the corpus states
covering every composed page, rather than writing a computed-style sweep. Cover states
reached by interaction, including focus states where layout can cover a focus ring.
Where no state reaches a surface the change touches, add one to `STATES`
(`dev/leaf_dev/states.py`) rather than driving it by hand: one state per surface,
never one per scheme, size or pointer, which a run chooses with `--scheme`,
`--viewport` and `--touch` (the `states.py` header says when a state keeps its own).

For a change to thread-card placement, also run `uv run leaf-dev placement cards --base`,
a gallery of cards across subjects, messages, routes, windows and page Layouts, and add
a case to its `CASES` for each new shape a reader meets.

For a change to what the panel says in passing, a notice, a walk's position or the
words standing in its field, run `uv run leaf-dev words --base`, a table of what the
seat says and a listener hears after each press on a set of pages, and read each
changed row beside its capture.

Hand off every difference a still can show as a Leaf page with an `lf-shot` of the
crops and a sentence saying what changed, and link the page in the reply; a live
preview may accompany the pairs but doesn't replace them. Show a difference once, in
the state where it reads most clearly, naming the states that repeat it, and add a
dark-scheme or phone pair only where the change looks different there. For an
interaction-only change, compare the same journey on both versions ("Compare checkout
versions"). A live preview handed to the user carries the fragment of the section it
is about and stays running.

## Preview a page

`uv run leaf-dev preview <example>` serves a live page that follows source and
browser-runtime edits at one URL; `--source <file>` serves any HTML file. Read
`references/previews.md` before you start, restart, drive or hand over a preview,
or serve a scratch page.

## Run the agent journey

`uv run --project <root> leaf-dev journey run TARGET` runs one user's journey against a
real agent. `references/agent-journey.md` names the target for each file a harness
change touches, and covers benchmarking replies and tracing one message.

## Compare checkout versions

`uv run leaf-dev preview <example> --base` serves the merge-base runtime beside this checkout,
in the foreground as a preview runs (`references/previews.md`); `--help` lists the flags. Keep
the default shared source for a runtime change, pass `--authored` when the authored
content changed, and pass `--user` only when the URLs go to the user.

For a change that can alter browser startup, compare served previews for a runtime
change, and `leaf-dev site verify website-worker` for site delivery, Worker routing or
containers. Read the comparison by phase (the document arriving, widgets upgrading,
the page first showing the server's state), and compare the requests and bytes loaded
before that last phase directly; elapsed time is only diagnostic.

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
compatibility refusal rather than falling back to the installed plugin. A page built
in another checkout, such as a subagent's worktree, was checked against that
checkout's Leaf, and markup and layout contracts change between commits with no
protocol change. Serve it with that checkout's launcher, and judge it against that
checkout's instructions.

A page that explains how a Leaf widget, verb or event flow behaves lets the user try it
in a live sample (`<root>/skills/leaf/references/live-samples.md`) holding only the
demonstrated page and an `lf-activity` feed of its own log. Make the next gesture and
its visible result clear as the user tries the sample, including Undo. Guidance beside
the relevant step lets the user learn by operating the page. Before handoff, operate
the sample using only its visible guidance and read each line the feed prints, so the
review checks whether the user can work it without the author's knowledge.

## Score an instruction change

Before changing the instructions an authoring agent follows, or scoring a change as
root `AGENTS.md` asks, read `references/instruction-changes.md`.

## Measure a removal

Measure a removal or consolidation that root `AGENTS.md`'s "Regular maintenance"
finds by making the change in a scratch worktree: `git diff --numstat` gives what it
deletes, and a probe or capture of the affected journey shows what users lose. A count
read off the code overstates the saving.

## Land a change

`tests/AGENTS.md`, "Selecting checks", says what the landing gates run and what a failure there means. `wt merge` checks the rebased tree
and lands it; `✗ Can't push to local main branch` means a fast-forward failed.

Installed sessions load harness caches, not the checkout, and follow `main`: Claude
Code picks up a push on its marketplace sweep, and Codex refreshes at startup. To
refresh Codex in a running session, run `codex plugin marketplace upgrade leaf`.
