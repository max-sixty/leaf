---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Each section below gives the steps for one task that work on Leaf can include,
in the order a change meets them, from running `leaf` to landing. Follow the
sections for the tasks your work includes, and skip the rest. A fix to the server's
Python may need only "Read the owning contract" and "Land a change", while a theme
change also needs the sections on proving, handing off and reviewing it. Where root
`AGENTS.md` requires a task, it names the task's section. The last section lists
the tasks whose steps are in a file of their own.

## Run `leaf`

A command goes to the Leaf that owns what it acts on (`src/leaf/session-lifetime.md`,
"Which Leaf runs a session"):

- **A page the session holds**, such as the page it talks to the user on: the
  session's own `leaf`, the copy its hooks run, which is the bare `leaf` on `PATH`
  in a session started normally.
- **This checkout's runtime**: `<root>/bin/leaf` for a preview, a fixture or another
  page the session doesn't hold, and `uv run` from `<root>` for the tests and
  `leaf-dev`. `<root>` is the repository root three directories above this
  `SKILL.md`, which `<root>/bin/leaf --root` prints. The checkout acts for no
  session, as a dev server of any project would: it serves a page unclaimed,
  `leaf-dev preview --user` included, and `<root>/bin/leaf wait PAGE` hears it.

So serve the user the page you talk to them on as a session in any other project
would, through the session's own `leaf`, even when its subject is a change to Leaf.
A checkout preview reaches the user as a link from that page, for trying a runtime
change, as a dev server's URL would. Only the session's own pages reach its hooks,
such as Leaf's line above Claude Code's prompt.

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

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped example or
fixture, a playground, or a page for this conversation. Before writing its content,
read completely the leaf skill of the Leaf that runs the page ("Run `leaf`"): the
session's own for a page the session holds, `<root>/skills/leaf/SKILL.md` for this
checkout's. Follow its authoring, validation, handoff and conversation-loop routes
through that Leaf's `leaf`, resolving its references beside the skill. Read it again
after a compaction, before the page's next revision or handoff. A brief for a
subagent that writes the page names the content and the decisions to put to the user,
and leaves how to pose them to those instructions.

A page runs the runtime of the Leaf serving it, so a page the checkout serves shows
the checkout's runtime. The session's hooks, its pages follower and the hooks module
run the session's own copy whichever launcher you use; to try a change to them, run
the agent journey ("Run the agent journey") or `uv run leaf-dev journey session`,
whose Claude Code loads this checkout as its plugin. A page built in another
checkout, such as a subagent's worktree, was checked against that checkout's Leaf,
and markup and layout contracts change between commits with no protocol change.
Serve it with that checkout's launcher, and judge it against that checkout's
instructions.

A page that explains how a Leaf widget, verb or event flow behaves lets the user try it
in a live sample (`<root>/skills/leaf/references/live-samples.md`) holding only the
demonstrated page and an `lf-activity` feed of its own log. Make the next gesture and
its visible result clear as the user tries the sample, including Undo. Guidance beside
the relevant step lets the user learn by operating the page. Before handoff, operate
the sample using only its visible guidance and read each line the feed prints, so the
review checks whether the user can work it without the author's knowledge.

## Choose what the user reviews

Prefer outputs the user can review quickly. Do the reviews you can do as well as the
user, and report the results. Choose the decisions the page puts to the user from
their request, and show visible and interaction changes with the proof below,
including the picture root `AGENTS.md` asks for with each UI option you leave to them.

## Prove and hand off a visible change

The user judges a visible change by using it, so before handoff, use it for their task
yourself, in the page and states they will see. Name the task, each step's visible
outcome, and the content and controls the reader must keep in view or reach next,
before choosing controls or checks. A check proves only what it observes: a disclosure
that opens or focus that lands proves only that, finishing the task by one route
proves only that route, and an input call returning doesn't prove the update it
started has finished. For an important result, assert the outcome the task needs with
a Playwright expectation in a `leaf-dev probe --journey` file. Check:

- **What the user receives.** Open the exact preview URL in a fresh browser context and
  check the outcomes on arrival and through ordinary input; setup the user can't repeat
  belongs in the fixture. A server keeps the runtime and layer it started with, so
  judge a runtime, theme, registry or widget change on a server started after it.
  Before handing over a recording, step through its frames and confirm they show the
  motion you describe.
- **Each route, from the states that change its effect**, such as its destination
  already open or another item selected. Before activating anything, the reader should
  be able to tell which labels, symbols and destinations belong together.
- **Every state the reader sees**, transient ones included: a hovered or
  keyboard-targeted item in an open surface, a focus ring that layout might cover, a
  drag or resize before release. Judge legibility and layout in every affected color
  scheme at a representative desktop viewport.
- **The relationships the task depends on.** Before and after each input, check that
  what the reader needs stands where the task needs it, embedded views included. Reach
  each control as the user does, with a Playwright hover or click: its actionability
  check refuses a control that something paints over, even when the control's box and
  opacity look right. Derive aligned positions from layout constraints or one shared
  dimension, so the alignment holds as content and sizes change, and check the
  constraints in the source too, since a screenshot can hide a half-pixel
  misalignment.

To ask a page where an element sits, what style it computes, or what holds focus after
a key, run `uv run leaf-dev probe` rather than writing a Playwright script or a scratch
test. It builds the page from this working tree, runs your input steps and prints what
a JavaScript expression returns. `leaf-dev probe --help` covers `--log` for threads and
messages, `--base` for the merge base's page beside this one, `--browser` for other
engines, and `--frames` for a reading after every frame a scroll or animation draws. To
reach a surface that one of the `leaf-dev stills` states reaches, open that
state with `--state NAME` rather than repeating its input as steps.

`uv run leaf-dev stills` crops each changed catalogue state into a before/after pair
and lists the computed styles that differ in it, shadow trees included, with the
declarations behind them (its module header covers `--base`, `--authored` and
`--browser`). For a change to where a rule sits, such as its sheet, layer or selector,
read those lists, with the corpus states covering every composed page, rather than
writing a computed-style sweep. It also lists each geometry fault the change adds,
such as a box nearly touching its frame's edge or a focus ring a clip cuts
(`leaf_dev.geometry`); hand over none the change can fix.
Where no state reaches a surface the change touches,
add one to `STATES` as the `dev/leaf_dev/states.py` header says, rather than driving
the surface by hand. In a screenshot you take yourself, capture the viewport where fixed
chrome should appear: a Playwright screenshot of an element taller than the viewport
draws fixed overlays in the wrong place.

Some `leaf-dev` commands run one surface through every case in a list they keep, such
as `placement cards` for where thread cards stand; `leaf-dev --help` gives each
command's subject. For a change to such a surface, run its command with `--base` and
read its module header for how to judge the output.

Hand off every difference a still can show as a Leaf page with an `lf-shot` of the
stills crops and a sentence saying what changed, and link the page in the reply; a
live preview may accompany the pairs but doesn't replace them. Show a difference once,
in the state where it reads most clearly, naming the states that repeat it, and add a
dark-scheme or phone pair only where the change looks different there. For an
interaction-only change, compare the same journey on both versions ("Compare checkout
versions"). A live preview handed to the user carries the fragment of the section it
is about and stays running.

## Review a UI change

Whoever reviews a UI change, you or an independent reviewer, first uses the
live candidate cold for the user's task, before reading its code or the author's
account, reaching each result by every route Leaf gives to it and capturing each state
those routes leave. A reviewer's brief gives the task and the candidate and asks for
that pass before any code review. An agent that has driven, measured or read the
change sees the screen through that work and misses flaws a first look catches; a
fresh agent given only the captures and the user's request, and asked what looks
wrong, is one way to get that look. A theme or shared-control change also gets a
`/ui-sweep` pass (`../ui-sweep/SKILL.md`), which follows that skill's "Review a design
system" section. This skill's `references/external-ui-skills.md` lists optional review
skills from outside Leaf, such as visual critique and motion review, and `/ui-sweep`'s
"External review" section says how to choose among them.

## Land a change

`tests/AGENTS.md`, "Selecting checks", says what the landing gates run and what a
failure there means. `wt merge` checks the rebased tree and lands it; `✗ Can't push to
local main branch` means a fast-forward failed.

Installed sessions load harness caches, not the checkout, and follow `main`: Claude
Code installs a push on its marketplace sweep, which a running session loads at
`/reload-plugins`, and Codex refreshes at startup. To refresh Codex in a running
session, run `codex plugin marketplace upgrade leaf`.

## Tasks with their own reference

Each of these tasks has its steps in a file under this skill's `references/`. Read
the file when the task arises.

- **Preview a page**: `references/previews.md`, before you start, restart, drive or
  hand over a `uv run leaf-dev preview` of an example or an HTML file, or serve a
  scratch page.
- **Compare checkout versions**: `references/previews.md`, "Compare checkout
  versions", to serve this checkout beside its merge base for an interaction-only
  change or one that can alter browser startup.
- **Run the agent journey**: `uv run --project <root> leaf-dev journey run TARGET`
  runs one user's journey against a real agent. `references/agent-journey.md` names
  the target for each file a harness change touches, and covers benchmarking replies
  and tracing one message.
- **Score an instruction change**: `references/instruction-changes.md`, before
  changing the instructions an authoring agent follows, or scoring a change as root
  `AGENTS.md` asks.
- **Record an interaction**: `references/recordings.md`, when an interaction depends on
  a sequence of inputs or changes over time.
- **Measure a removal**: `references/removals.md`, before proposing to remove or
  consolidate what root `AGENTS.md`'s "Regular maintenance" finds.
- **Explore an open design**: `references/explore-a-design.md`, to build the
  side-by-side choice root `AGENTS.md` asks for when the user is to choose among
  designs.
- **Add a check or guidance for the authoring agent**:
  `references/checks-and-guidance.md`, before adding or changing a rule, check,
  refusal or message that constrains or answers an authoring agent.
