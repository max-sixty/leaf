---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, check that
`<root>/bin/leaf --root` prints that root, and run every `leaf` command through that
absolute launcher; a bare `leaf` may run the installed plugin instead.

Before naming or renaming anything the user sees or operates, or an identifier for one,
read `references/glossary.md`, Leaf's canonical vocabulary.

## Read the owning contract

A contract shared across modules or runtimes lives in a reference beside the Python
code that owns it; `<root>/skills/leaf/scripts/AGENTS.md` lists them under "Protocol
references". To check what the code does, call it: `leaf` and `leaf_dev` are installed
editable, so `uv run python -c 'from leaf... import ...'` works as is. A tag's schema
is in the registry of the package that ships it:

```bash
jq 'select(has("lf-shot"))."lf-shot"' \
  skills/leaf/assets/registry.json skills/leaf/packages/*/registry.json
```

A fact both runtimes use has one home (`skills/leaf/assets/AGENTS.md`, "Facts both
runtimes know"). When a change adds a parity fixture, or a test that scans one
language's source for the other's names, ask why the fact isn't generated.

## Review a UI change

Record browser API and rendering support gaps in
[`notes/browser-support.md`](../../../notes/browser-support.md), as its "Recording and
assessing a gap" section says.

Before handing over a change to browser controls, navigation, focus, motion, forms or
layout, run `/ui-sweep` (`../ui-sweep/SKILL.md`) on the changed surface and the
interactions that depend on it. Its "External review" section says when to use the
skills below, and its "Review a design system" section covers theme and shared-control
changes.

### External UI skills

These are optional installs, separate from Leaf's plugin. Check the harness's available
skills before invoking one; each link has installation instructions.

| Install | Use in a UI review |
| --- | --- |
| [Impeccable](https://github.com/pbakaus/impeccable#installation) | `/impeccable critique` for hierarchy, grouping and clarity; `audit` for technical UI quality; focused workflows such as `layout` and `typeset`. |
| [Web Design Guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines) | `/web-design-guidelines` for interface conventions, accessibility, navigation, forms and motion. |
| [Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | `/frontend-design` for new compositions or an intentional redesign. |
| [Emil Kowalski's skills](https://github.com/emilkowalski/skills) | `review-animations` for motion; it refuses model invocation, so read its `SKILL.md` and `STANDARDS.md`. `/break-ui` for worst-case content, such as long names or no items; keep the demo-data toggle it adds out of a shipped page. |

## Leave taste to the authoring agent

Code enforces only what Leaf needs to work: a contract between modules, or a guarantee
the user relies on, such as a gesture being recorded or nothing moving under the
pointer. Taste goes in the shipped instructions as a goal with its reason, so the
authoring agent weighs it against its own page. A CSS rule, validator or Layout that
fixes how many tiles share a row overrides every page that needs another number. A
check may report what it sees, as the render check names where a tile row wraps, and
leave the decision to the agent.

`page check` and its render checks hold Leaf's contracts on every page: each widget
upgrades, nothing a user needs is clipped out of reach, every control can be pressed.
Don't add a check for one particular authoring mistake, such as one attribute misused
on one tag; a rare mistake costs one fix, or a clearer line in the instruction it
misread. Add a narrow check, or a note a command prints, only where agents get
something wrong on real pages and fix it when told, and prefer widening a general check.

Before adding one, estimate its precision (the share of its firings that were needed)
and recall (the share of the failure's occurrences it catches) on real pages and
sessions, not only on the failure that prompted it, and say where the numbers are
estimates. Low precision spams the agent. Low recall makes the failure look handled
while it continues everywhere the check doesn't see. The rates inform the call
rather than gate it: weigh what a missed failure costs as well as how often it
happens, and whether agents improve the page after receiving the message.

## When to pass guidance back to the authoring agent

Pass guidance back when it helps the author improve the user's result, weighed against
the interruption and the cost of another rule (root `AGENTS.md`, "Leaf's role"). First
ask whether Leaf should provide the behavior itself: layout and runtime code should
carry out the author's intent without making them work around incidental markup
restrictions. Keep editorial choices with the author and preserve the user's state.

Refuse input only when proceeding would break a guarantee, and say how to fix it where
the author can act. Use the owning parser or validator rather than repeating its rules,
and let its message reach the author: `patch_manifest.py` stores a patch as given, and
`lf-diff` reports a file it can't draw with `reportFailure`. A reader's current
limitation alone doesn't justify a restriction.

Where Leaf has evidence but the author must judge it, report the observation without
making it a requirement: page findings in check results, a command's consequences in
its output. Say what was checked and what was not. Put reusable knowledge in the instructions the author reads when making the
relevant choice, with the reason it matters. Add no message when it would only
repeat known information or request a change the page does not need. When a
markup contract changes, update its
reader, validation, dependent layout rules and instructions together.

Data one Leaf module writes for another over a channel only Leaf writes is not input:
the browser reading the server's answer, the Worker reading the manifest its build
wrote. The reader uses it directly, and the producer's tests hold its shape. Data a
person or agent can write on the way is input, even when Leaf code sent it: a request
the browser posts, a file an agent edits, the answer of leaf.page's container, whose
agent a visitor steers. Delete code that recovers from a state no current Leaf writer
produces, such as a record an older Leaf left in the state home, along with the test
that creates that state.

## Explore an open design

When the user is to choose among designs for a visual or interaction question, show
the candidates side by side in one ask, where the user can compare them, try the
interactions, comment, and pick the one to build. Their pick, or the configuration a
playground submits, is the one implementation the change keeps. First look in the
shipped examples and `notes/` for an exploration of the same surface, and extend it
when it covers the same decision.

The exploration is one HTML file under `.tmp/`, served with
`uv run leaf-dev preview --source <file> --user` ("Preview a page"); its CSS reads the
live theme's tokens. Follow `<root>/skills/leaf/packages/playground/instructions/author.md`
to choose the elements, present the candidates, and say what to build.

To compare against an existing interface, cover the controls and states the named
property affects, with this checkout's rendered interface as the baseline and
candidates that differ from it only in the requested change. Build runtime candidates
in the runtime and theme that own the surface; a separate sketch follows "Decision
fidelity" in the playground author instructions. Drive the baseline and every candidate
through the same journey before handoff. For a live Leaf interface, embed each as an
`lf-sample window` child (`skills/leaf/references/live-samples.md`) and start their
histories with `data-sample-events`.

## Choose what the user reviews

Prefer outputs the user can review quickly. Do the reviews you can do as well as the
user, and report the results. Choose the decisions the page puts to the user from
their request, and show visible and interaction changes with the proof below.

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
fixed overlays in the wrong place. Close a browser session you opened when you finish
with it; the user's review preview and a borrowed browser keep their own lifetimes.

Derive the required visual relationships from the reader's task, not from the checks
that pass. For each ordinary input, state which content and controls the reader needs
to keep in view or reach next, then check their computed geometry before and after the
input in the delivered page, embedded views included. Make those relationships hold as
content and sizes change, through layout constraints or positions derived from one
shared dimension, and check those constraints in the source too: a screenshot can hide
a small misalignment. Re-vendor after a runtime, theme, registry or widget change, then
judge the composed page.

To ask a page a question, such as where an element sits, what style it computes, or
what holds focus after a key, run `uv run leaf-dev probe` rather than writing a
Playwright script. It builds the page from this working tree, runs your input steps,
and prints what a JavaScript expression returns, with `--base` for the merge base
beside it (`dev/AGENTS.md`).

When an interaction depends on a sequence of inputs or changes over time, record it
with `leaf-dev probe --record .tmp/recordings/NAME` (its `--help` covers journeys and
serving the trace), review the frames at their recorded times, and show the trace on
the Leaf page in `lf-trace` (`skills/leaf/references/authoring-evidence.md`, "Source
files and media"). For an important result, assert the outcome from the user's task
with a Playwright expectation: disclosure and focus prove only themselves, and
returning from the input doesn't prove an asynchronous update finished.

`uv run leaf-dev stills` compares HEAD with its merge base with `main` and crops each
changed catalogue state into a before/after pair. Commit first, since it compares
commits. For changes to the examples themselves, add `--authored` so each side reads
its own markup. Cover pages at rest and states reached by interaction, including focus
states where layout can cover a focus ring; add a missing state to `STATES` rather than
driving it by hand.

Hand off every difference a still can show as a Leaf page with an `lf-shot` of the
`stills` crops and a sentence saying what changed, and link the page in the reply. A
live preview may accompany the pairs but does not replace them.
Several states often show the same difference: show it once, in the state where it
reads most clearly, and name the states that repeat it. Add a dark-scheme or phone pair
only where the change looks different there. For an interaction-only change, compare
the same journey on both versions ("Compare checkout versions"). A live preview handed
to the user carries the fragment of the section it is about and stays running.

## Preview a page

`uv run leaf-dev preview <example>` serves a live page that follows source and runtime
edits at one URL. `--source <file>` serves any HTML file instead of a shipped example,
and `--export` writes one file that opens offline. A desktop Codex `--user` preview
detaches and returns its URL; every other preview runs in the foreground like a dev
server, so start it as a long-running command (`run_in_background` in Claude Code). The
`dev/leaf_dev/commands/preview.py` header covers slots and restarts; `--help` lists the flags.

A plain preview has no claim, so presses on it reach only the page's log; use it for
screenshots and browser checks. `--user` claims the page so the user's comments reach
this session, which also makes every click this session drives there arrive as an
unanswered update. So drive only plain previews, and start a `--user` preview only from
the session the user talks to. Don't idle a preview to quiet the loop; `idle` closes the
page in the browser.

### Temporary review resources

Keep a review's live resources in proportion to the work. Use the smallest fixture that
keeps the journey and its surroundings; `--source` avoids serving a whole gallery for
one interaction. Separate page directories keep reviewers' comments and data apart, and
fresh browser contexts keep browser storage apart; neither needs another browser or
Python process. For finite checks, prefer `leaf-dev probe` or `stills`, which close
their servers when they finish. A custom runner owns its servers and browsers through
success, failure and cancellation. Keep previews and trace viewers handed to the user
running for their review.

### In Codex

1. Start the preview with `--user` from the current chat. It connects the page's
   updates to this chat before printing the URL, and reconnects the page after each
   restart.
2. Call `mcp__codex_app__open_in_codex` with the printed URL and the section's
   fragment, as a browser target with `placement: "right"`.
3. Tell the user to comment on the review page to steer this chat. Comments inside a
   live sample are practice in that child. Codex Annotation mode sends visual comments
   with the next chat message; Leaf's own comments send an anchored thread directly.

## Run the agent journey

`uv run --project <root> leaf-dev journey TARGET` runs one user's journey against a real
agent. On the triage board, it tells the agent that a release passed its checks and
asks it to record that, then checks for a reply and a revision naming the release. It
prints how long each step took on the page server's clock, so the same journey
benchmarks every target. A run spends the target's login.

On a harness, the simulated user posts each comment over HTTP by default, as the page's
tab does, with no browser; use that for harness behavior and agent timing.
`--browser` runs the user in Chrome instead, typing each comment in Threads; use it when
what the page shows is part of the change. A website target always runs in Chrome.

The journey runs a session of the harness with this working tree as its plugin. The
suite only stands in for each harness, so run the journey on the harness a change
touches; each target's module header lists its steps and the promises it checks:

- `claude-code` (`journey_claude_code.py`): with and without `--hooks-module`, after a
  change to `hooks/hooks.json`, `hooks/claude-code.ts`, `ClaudeCodeHarness`,
  `hooks.py`, `background-watch.py`, or the watch between turns in `session.py`. Add
  `--sandbox` after a change to `bridge.py`, the README's "Agent sandboxes" settings,
  or what a `leaf` command needs from outside its page directory.
- `codex-app-server` and `codex-queue` (`journey_codex.py`): both, after a change to
  `codex.py`, `codex_adapter.py`, `hooks.py`, `hook_transport.py`, or the claim's turn
  in `service.py`; add `--preview` for a change to preview startup or lifetime.
- `pi` (`journey_pi.py`): after a change to `hooks/pi.ts`, `PiHarness`, `hooks.py`, or
  the watch between turns in `session.py`.

For the website, TARGET is `website-adapter` (its adapter against the host's Codex
login, with no Worker or container), `website-worker` (the built site through the local
Worker), or a website origin; there the journey is the release ask alone.
`tests/AGENTS.md`, "Run what the change needs", says which delivery checks CI runs, and
`worker/README.md`, "Local development", how to reproduce a Worker or container failure.
The `publish-site` workflow runs the journey against the deployed release, the only
production reading.

## Compare checkout versions

`uv run leaf-dev compare <example> --user` serves the merge-base runtime beside this
checkout. A desktop Codex `--user` comparison detaches and returns both URLs; every
other comparison runs in the foreground. Keep the default shared source for a runtime
change, pass `--authored` when the authored content changed, and omit `--user` for
tests with no claim. `--help` lists the other flags.

## Author or revise a page

Every authored Leaf source is a page: a site page under `docs/`, a shipped example or
fixture, a playground, or a page for this conversation. Before writing its content,
read `<root>/skills/leaf/SKILL.md` completely and follow its authoring, validation,
handoff and conversation-loop routes, using the checkout launcher and resolving its
references from `<root>/skills/leaf/`. Read it again after a compaction, before the
page's next revision or handoff. A brief for a subagent that writes the page names the
content and the decisions to put to the user, and leaves how to pose them to those
instructions.

To make an existing page use the current checkout, re-vendor it with the checkout
launcher (`<root>/skills/leaf/references/serving-pages.md`); fix or report a
compatibility refusal rather than falling back to the installed plugin.

A page that explains how a Leaf widget, verb or event flow behaves lets the user try it
in a live sample (`<root>/skills/leaf/references/live-samples.md`). The sample holds
only the demonstrated page and an `lf-activity` feed of its own log, so each gesture
shows the event it writes. The prose above the sample lists the gestures to try, in an
order that exercises each verb the page explains, undo included. Before handoff, drive
the sample using only what that prose says, and read each line the feed prints: a
probe that knows more than the prose shows that the sample works, not that a user can
work it.

## Score an instruction change

Score an instruction change when you can't be sure how an agent will read it: a new or
reworded rule, a goal that competes with another, or a cut that may have carried a
behavior. Deleting a description of an input that can no longer arrive, or correcting
a fact, needs no score.

Choose the eval by what the instruction is for:

- General agent behavior: personal-skill evals (`/improving-instructions`, "Validate
  with evals").
- Leaf's shipped workflows: the standard Leaf evals.
- Maintainer guidance, such as this skill or an `AGENTS.md`: a temporary A/B in scratch
  that gives each arm its version of the passage. Commit no case for it. Add a
  maintainer case to Leaf's suite only for a development contract that needs the
  suite's staging, such as a served page or an installed arm.

For cases in Leaf's suite, run both the merge base and the working tree:

```bash
pnpm install --frozen-lockfile
uv run leaf-dev eval [CASE]... --base --harness claude-code|codex [--repeat N]
pnpm run eval:view
```

`evals/README.md` owns selection, arms, the case format, where results go and how far
a pass can be trusted. Read the outputs as well as the pass counts.

Use an existing case wherever one fits, extending its assertions or prompt if it nearly
does, since every case costs time and money on each later run. Add a case only when no
existing one can carry the behavior, and keep it small: one prompt with only the
context the behavior needs, and a few assertions. Explore freely, but keep only cases
that cover distinct failures or necessary controls. The case's leading comment records
where it came from and whether it told the two versions apart.

The prompt never states the behavior under test. Grade what the agent wrote with an
`llm-rubric` assertion whose `value` describes the passing behavior without requiring
particular wording; use `regex` only for a literal such as a command or URL
(`evals/README.md`, "Case format").

A case that states the situation plainly usually passes on both arms, because the
failing session had earlier turns or a competing instruction pulling the other way:
paste those into the prompt. A rule that fails only late in a long session needs a
replay of that session; keep the smallest replay that shows the failure.

## Refresh the public catalog stills

When a change adds or removes an example or changes its first screen, run
`wt refresh-previews` from the repository root on macOS once the examples are ready,
and again after merging `main` or any later fix that changes a first screen. It pushes
the stills to `max-sixty/leaf-assets` and moves the pin in `leaf-assets.json` and the
README's image URLs; `uv run leaf-dev record-demo` does the same for the README's
recording and the site's card. Run `wt setup` first in a new checkout; if Worktrunk asks
to approve the project commands, ask the user to run `wt config approvals add`.

## Land a change

Before handing over a change that adds to an area `AGENTS.md`, ask of each addition
whether one module owns it. If one does, the rule goes in that module's header and the
area file keeps at most a pointer (root `AGENTS.md`, "Where instructions live").

The thread appearance gate, `tests/*/test_render_thread_snapshots.py`, is paused while
development moves fast (`TODO.md`, "Resume the thread appearance gate"), so a thread
appearance change needs no snapshot run before landing.

A pull request's `test` job and the local pre-merge run the broad selection and the
later-tier tests the branch edits; CI runs the rest after landing, and `tend-ci-fix`
answers what fails (`tests/AGENTS.md`, "Run what the change needs"). `wt merge` checks
the rebased tree and lands it; `✗ Can't push to local main branch` means a fast-forward
failed.

Installed sessions load harness caches, not the checkout. Claude Code picks up a push on
its marketplace sweep; Codex refreshes Git marketplaces and installed plugins at
startup. Both follow `main` by default. To refresh Codex in a running session, run
`codex plugin marketplace upgrade leaf`.
