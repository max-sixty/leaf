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
operates each, comments on it, and submits a choice. The submitted configuration
or feedback chooses the one implementation the change keeps. First look in the
shipped examples and `notes/` for an exploration of the same surface, and extend
its playground when it owns the same decision.

A playground is one HTML file, like a standalone sketch. Write it under `.tmp/`
and serve it with `uv run leaf-dev preview --source <file> --user` ("Preview a
page"), which builds the page from that file alone. Its CSS reads the live
theme's tokens. Follow
`<root>/skills/leaf/packages/playground/instructions/author.md` to choose the
selection and exploration elements, present the candidates, and submit a task
saying what to build.

When the subject already exists and the candidates are to be implemented,
implement each in the runtime and theme that own the surface and present it
through a shipped example or fixture. A sketch without implementation is
page-local markup derived from the current surface's controls, copy, and
styling, shown beside that surface as the baseline. For a live Leaf interface,
embed the baseline and candidates as `lf-sample window` children in the playground.
The outer page carries the configuration and feedback; the children carry practice
interactions. Start their fictional histories with `data-sample-events`, sharing
one parent-local JSON fixture when the candidates need the same conversation
(`skills/leaf/references/page-authoring.md`, "Live samples").

## Prove and hand off a visible change

Review at a representative desktop viewport (`skills/leaf/assets/AGENTS.md`,
"Layout and motion"), and capture the viewport when fixed chrome should
appear. A Playwright screenshot of an element taller than the viewport draws
fixed overlays in the wrong place; crop a viewport capture instead.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. A green suite does not judge visual quality; run `/ui-sweep` or
look at a composed page.

To ask a page a question, such as where an element sits, what style it computes, or
what holds focus after a key, run `uv run leaf-dev probe` rather than writing a
Playwright script: it builds the page from this working tree, runs the input steps
you give it, and prints what a JavaScript expression returns, with `--base` for the
merge base beside it (`dev/AGENTS.md`).

When a complex interaction depends on a sequence of inputs or changes over time,
show a recorded journey with a timeline so the user can inspect intermediate
states and motion. Use that same probe with `--record .tmp/recordings/NAME`.
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
Playwright cannot save screencast video after its page closes. Serve the trace in
a browser tab with:

```bash
uv run playwright show-trace --host 127.0.0.1 --port 0 \
  .tmp/recordings/NAME/worktree/trace.zip
```

When showing a timeline in Leaf, place a direct link to the same recording in the
running Trace Viewer beside its controls. The viewer supplies action details,
Before/Action/After DOM snapshots, source, console and network inspection; Leaf
supplies the anchored discussion. Keep both previews running and verify that the
viewer URL reaches the user's browser before handing it over.

`uv run leaf-dev stills` compares HEAD with the merge base with `main` and crops
each changed catalogue state into a before/after pair. Commit first, since it
compares commits. Include pages at rest and states reached by interaction,
including focus states where layout can cover a focus ring. Add missing states
to `STATES` rather than driving them by hand.

For every difference a still can show, the handoff carries one sentence and
matched before/after screenshots, embedded in the reply or as one `lf-shot`; a
live preview may accompany the pair but does not replace it. For an
interaction-only change, serve both versions ("Compare checkout versions" below),
keep both previews live, and hand off the labeled URL pair with the action that
reveals the difference. Exercise the same journey in both at the same fragment,
viewport, theme, and interaction state. A live preview handed to the user
carries the fragment of the semantic block it is about (a titled section's own
id) and stays running.

## Preview a page

`uv run leaf-dev preview <example> --export` writes one file that opens offline.
`uv run leaf-dev preview <example>` serves a live page at `.tmp/previews/<example>`
in the foreground, like a dev server, so run it as a long-running command
(`run_in_background` in Claude Code). `--source <file>` serves any authored HTML
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

1. Start the preview with `--user` as a long-running command from the current
   chat. It connects Leaf feedback to this Codex chat before printing the URL;
   each restart reconnects the rebuilt page automatically.
2. Call `mcp__codex_app__open_in_codex` with the printed keyed URL and the semantic
   block's fragment, as a browser target with `placement: "right"`.
3. Tell the user to comment on the surrounding review page to steer this chat.
   Comments inside a live sample are practice interactions in that child. Codex
   Annotation mode sends visual comments with the next chat message; Leaf's text
   selection and comment affordance send an anchored thread directly.

## Test the hosted website agent

`uv run --project <root> leaf-dev verify-site local` builds the site, starts the
website adapter against the host's Codex login, asks for one heading edit, and
verifies the publication, reply, and changed page in Chrome. It bypasses the
Cloudflare Worker, container limits, and credential proxy, and needs no Docker.

Use CI for Linux-specific evidence and the complete Worker/container boundary:
pull requests run the site build, dry-run deploy, and `verify-site wrangler`, and
`publish-site` verifies that boundary before deployment. Start Docker locally
only to reproduce a concrete failure at that boundary. When debugging hosted-agent
delivery through it and `OPENAI_API_KEY` is exported, run:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
uv run --project <root> leaf-dev verify-site wrangler --agent
```

The `publish-site` workflow's run against the deployed release is the only
production reading.

## Test a terminal Codex task

`uv run --project <root> leaf-dev verify-codex-task` runs real Codex tasks, with
this working tree installed as their plugin, through both transports of automatic
server handoff. It checks each comment is answered once, a comment during queue-backed
work is picked up and answered in that same turn, and each turn is closed under
App Server's id. Run it after a change to `codex.py`,
`codex_adapter.py`, `hooks.py`, `hook_carrier.py`, or the claim's turn in
`service.py`; the suite scripts App Server, and only this run shows what Codex
itself sends. It spends a few turns on the host's Codex login, and CI has none.

For a change to preview startup or lifetime, add `--preview`. It starts the
canonical user preview in each task, checks the keyed URL across those turns,
and interrupts its isolated server between turns to prove that the preview
restores both the address and working feedback without a source edit.

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
as separate long-running commands, adding `--user` to both when their URLs go to
the user:

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
(`references/sample-explainers.md`).

## Score an instruction change

Each `evals/<case>/case.yaml` is a native Promptfoo test. The runner gives Claude
Code and Codex the same task, the same assertions, and a staged copy of Leaf's
instructions. Install the separate eval dependencies once, then select the cases
that bear on an instruction change:

```bash
npm ci --prefix evals
uv run leaf-dev eval [CASE]... [--base REF] [--harness cc|codex|both] [--runs N]
```

The defaults are both harnesses, one run, and the merge base with `main`. Each sample
has a fresh workspace and home with the harness's account login. Promptfoo owns the
assertions, judgments, traces, and HTML report under `.tmp/eval/`;
the runner prints passes separately for each harness and base/candidate arm. Read
`evals/README.md` for the provider models and case format.

A reference-read assertion requires successful tool output, rather than counting
a denied attempt. Claude exposes Read/Skill results; Codex shell evidence requires
a completed successful command naming the file and returning text. Shell matching
is a heuristic, so inspect traces before treating a reference-read pass as proof.
These static cases test instruction use, while `leaf-dev verify-codex-task` owns
plugin installation, discovery, and hooks.

The suite is a library that grows with the instructions, so a later edit, whether a fix
or a cut, is scored against the behaviors earlier edits had to produce. Add to it
where a change's behavior gives the library breadth, a behavior or kind of situation
no case yet covers. First try to extend an existing case, with an assertion, a
criterion, or context in its prompt, so coverage grows without the cases
proliferating; add a new case only where no existing one can carry the behavior.
Keep a case small: one prompt carrying only the context the behavior needs, and a
few assertions. Measure with whatever scenarios and guardrails the change needs, and
keep what you add whether or not it separated the arms. The leading comment says where the case came from and what it measured, so a
reader can tell a case that told two wordings apart from one that has only guarded;
`metadata.purpose` names the clause it pins, and `metadata.tags` its area.

A prompt ends by asking for the HTML in the reply, since the child has no page
directory. It can read the staged skill and its references. A prompt pointing at
a file beyond the references names that file from the skill's base directory. The
prompt never states the behavior under test. Grade a fixed form with a `regex`
assertion, and a judgment with an `llm-rubric` assertion whose `value` states the
passing reading without requiring particular wording.

Run cold, a case that states the situation plainly usually passes on both arms: the
failing session had its own earlier turns or a competing instruction pulling the
other way, so paste those into the prompt. A rule that loses only to a long
session's context needs a replay of that session instead.
Complete workflows use the same catalog and command. `leaf-dev eval document`
authors and revises a document; `document/resume`
selects a controlled state-reading context. `--condition both` compares the authored example with
ordinary HTML. `evals/README.md` owns selection, conditions and evidence limits.
Keep focused contexts until a combined workflow detects their original failures.
No grader has been calibrated against human judgments, so a pass is weak evidence.

## Refresh the public catalog stills

When a change adds or removes a worked example or changes its first viewport,
run `wt refresh-previews` from the repository root on macOS once the examples
are ready, and again after integrating `main` or any later fix that changes a
first viewport. It pushes the stills to `max-sixty/leaf-assets` and moves the pin
in `leaf-assets.json` and the README's image URLs; that push is part of the
authorized change. `uv run leaf-dev record-demo` does the same for the README's
recording and stills and the site's card. Run `wt setup` first in a new checkout;
if Worktrunk asks to approve the project commands, ask the user to run
`wt config approvals add`.

## Land a change

Thread appearance changes run `tests/test_render_thread_snapshots.py` through the
ordinary gate. Review the failure's captured images before accepting an intentional
change; `dev/leaf_dev/thread_snapshots.py` owns the pinned-image capture and acceptance workflow.

A red gate is the branch's to fix. A pull request's `test` job and the local
pre-merge `tests` run the broad selection and the nightly tests the branch edits;
the rest of the nightly-marked tests run once main moves, and `tend-ci-fix` answers
them when they fail (`tests/AGENTS.md`, "Run the narrowest useful surface").
`wt merge` checks the rebased tree and lands it; `✗ Can't push to local main branch`
is a fast-forward failure.

Installed sessions load harness caches, not the checkout. Claude Code picks up a
push on its marketplace sweep; the post-merge hook refreshes an installed Codex
plugin, and after a merge that skipped hooks, run
`codex plugin marketplace upgrade leaf`.
