---
name: developing-leaf
description: Develops Leaf itself from the current checkout, including its runtime, protocol, packages, UI exploration, page previews, and browser proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, then resolve
`<root>/bin/leaf` to an absolute path. Run that launcher with `--root` and
continue only when it prints the same repository root. Use the absolute launcher
throughout; a bare `leaf` command may resolve to the installed plugin instead.

Read this skill's `references/glossary.md` before naming or revising user-facing elements,
interaction contexts, navigation, chrome, view state, or an identifier governed by
those concepts. It is Leaf's canonical implementation vocabulary.

## Read the owning contract

Read the scoped `AGENTS.md` for every implementation area the change reaches and the
module header for each module changed. For a contract shared across modules or runtimes,
read the sidecar beside the Python code that owns the boundary;
`<root>/skills/leaf/scripts/AGENTS.md` lists them under "Protocol references".

This skill is maintainer workflow, not a second home for product specifications. Agents
using Leaf read `<root>/skills/leaf/SKILL.md`. Package authors read the public contract
at `<root>/skills/leaf/references/packages.md`.

## Leave old state out of the handoff

Leaf owes nothing to state an earlier version wrote (`AGENTS.md`, "Stage"). A
handoff therefore doesn't tell the user that an existing page, log, or claim
predates the change, needs re-vendoring, or won't show it, and doesn't list
reviving that state as follow-up work.

## Explore an open design

When a new interface leaves a material visual or interaction choice unsettled,
first search the shipped examples and active notes for an exploration of the same
surface; extend its playground when it owns the same decision. Then follow `Author or
revise a page` below. Initialize a new page with the
`playground` package and follow
`<root>/skills/leaf/packages/playground/guidance/author.md`. Put several coherent
options in named presets. Build each option far enough that the user can operate it
in the shared preview. Controls select the option and its parameters; the user
performs the interaction being judged inside the preview. Use the user's submitted
configuration or feedback to choose the one implementation the finished change keeps.

When the subject already exists, implement each proposed behavior in the code that
owns that surface and preview its real output and styling. A Leaf interface therefore
implements candidates in its owning runtime and theme and presents them through a
shipped example or fixture. When the user asks for sketches without implementation,
keep the current surface as a baseline and derive each sketch from its actual controls,
copy, and styling. Embed an operable current surface with a live `lf-specimen`,
following `skills/leaf/references/page-authoring.md`: it hosts a complete Leaf page
with independent state, laid out as a block of the containing page. The developer gallery's
choreographed replays use the same host in passive mode; they demonstrate a sequence
rather than accept user gestures. Page-local HTML and CSS may frame the comparison
and build proposed sketches.

## Prove and hand off a visible change

Leaf's current product focus is desktop. Use a representative desktop viewport for
the primary screenshots, preview inspection, and visual review. Capture the viewport
when fixed chrome should appear in the result. A Playwright screenshot of an element
taller than the viewport composites fixed overlays into the element's page-space bounds
and misrepresents their position; crop the viewport image afterward when a smaller region
is needed.

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. An `/ui-sweep` and a look at a composed page are worth the time;
a green suite does not judge visual quality.

Reproduce the baseline from a clean checkout of `git merge-base HEAD main`, then
compare it with the candidate through the workflow below. For every difference a still
can show, include one sentence and matched before/after screenshots in the final
handoff, embedded in the reply or presented as one `lf-shot`. A live preview may
accompany the pair, but does not replace it. For an interaction-only change, keep
both previews live and hand off the labeled URL pair with the action that reveals
the difference. Add another state or width only when the first comparison cannot
show the behavior.

Before presenting a served page or visible runtime change as finished, inspect
the exact candidate URL. Exercise the same journey in the baseline and candidate,
matching the URL fragment, viewport, theme, and interaction state, and check both
browser consoles. Confirm the expected content and review the changed surface at the
primary viewport. When handing off a live preview, use the exact URL including
the semantic block's fragment and keep the process alive. A titled section uses the
section's stable id, so its eyebrow and heading arrive together. Add an id to the
tight semantic container when it has none.

## Preview a shipped example

From the repository root, run `scripts/preview.py <example> --export` for a
standalone static rendering. Start `scripts/preview.py <example>` for an
interactive preview: `--background` detaches the watcher and prints its URL,
and a foreground run holds the terminal. The script watches source and runtime
edits and preserves feedback at `.tmp/previews/<example>`. Repeating the command
reuses that preview and prints where it answers now; use `--slot <name>` for
another copy. A refused update appears in the terminal or the background log named at
startup. Fix the input and the watcher retries.

A preview takes no task claim: it serves through the browser suite's process-owned
server, with the real HTTP and event log, and its presses go nowhere but the page's
log. That is what every screenshot and browser check needs. Add `--user` for a
preview whose URL goes to the user, at `.tmp/previews/<example>-user`: the claim
carries their comments to `leaf wait`. It carries the agent's own gestures just as
readily, so a preview this session drives under `--user` reports each screenshot
click as an unanswered user move, and the Stop hook holds the turn open for it. A
preview of either kind owes no watcher, so the per-turn reminder to start one skips
it. Do not idle a preview to quiet the loop: `idle` closes the page in the browser
and changes the banner a visual check may be reading.
`--user` also fixes the address: the durable service records it, so the URL
survives a stop, while an unclaimed preview's server is its watcher's and a new
watcher answers somewhere else. A slot keeps the mode it was built in; `--reset`
rebuilds it in the other one. `--reset` discards the slot's `service.json` with the
rest of the page, and `--slot` names a different page, so after either, hand over
the URL the command prints. Any other address question about a `--user` preview is
a served page's, which `<root>/skills/leaf/references/serving-pages.md`, "Address
and authentication", answers. A subagent's previews stay claimless, and the session
the user talks to starts any `--user` preview: a subagent's claim is that session's
claim, so that session's Stop hook would answer for the preview's moves either way.

When finished with a preview, run the matching preview command with `--stop` (and
`--user` for a user slot); it waits for the watcher and server to stop. Ctrl-C
stops a foreground preview. A slot refuses a different source or seeded history so
it keeps the existing page and feedback. Use `--reset` to discard the selected slot
and rebuild it from the current fixture.

### In Codex

1. Start the preview with `--user`, which serves it at
   `.tmp/previews/<example>-user`. `codex start` claims the page, and the
   durable service `--user` puts up is what keeps that URL answering for as
   long as the task lasts.
2. Call `mcp__codex_app__open_in_codex` with the destination's fragment URL as a
   browser target and `placement: "right"`.
3. Run `<root>/bin/leaf codex start <root>/.tmp/previews/<example>-user` so
   Leaf comments return to the current task.
4. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode creates visual comments that the user sends with
   their next chat message. Use the Codex review pane when feedback belongs to a
   source line.

## Test the hosted website agent

Run `uv run <root>/scripts/verify_site.py local` for the development loop. It builds
the current site, starts the canonical website adapter, uses the host's logged-in Codex
App Server, asks for one heading edit, and verifies the publication, reply, and changed
page in Chrome. Its profile reports request acknowledgement, agent activity,
publication, reply, HTML, first contentful paint, JavaScript, state, upgrade, and
presentation timings. It stops every process and removes the disposable user page
when it finishes.

This fast loop bypasses the Cloudflare Worker, container allocation and
resource limits, and outbound credential proxy. When a change touches one of those
boundaries and `OPENAI_API_KEY` is exported, build the Worker and run the same check
through Wrangler's local Docker container:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
<root>/scripts/verify-site-local.sh --agent
```

Local infrastructure is emulated, so neither loop proves edge rollout or production
latency. The `publish-site` workflow runs `scripts/verify_site.py` against the exact
deployed release and is the authoritative production reading.

## Compare checkout versions

Create the baseline when the comparison is ready. Use a detached worktree so its
contents come from the merge-base commit rather than another worktree's state:

```bash
candidate_root=$(git rev-parse --show-toplevel)
baseline_commit=$(git merge-base HEAD main)
baseline_parent=$(mktemp -d "${TMPDIR:-/tmp}/leaf-baseline.XXXXXX")
baseline_parent=$(cd "$baseline_parent" && pwd -P)
baseline_root="$baseline_parent/checkout"
git worktree add --detach "$baseline_root" "$baseline_commit"
```

Use `$baseline_root` as the baseline and `$candidate_root` as the candidate.
Choose the sources that isolate the change: one shared authored source for a
runtime change, or each checkout's copy when the authored content changed. Give
the pair a comparison-specific `<slot>` name; `--reset` removes any state left
by an earlier run. Add `--user` to both when the pair's URLs go to the user,
or a comment they leave on either page reaches nobody.

```bash
"$candidate_root/scripts/preview.py" --source <baseline-source.html> \
  --runtime "$baseline_root" \
  --slot <slot>-baseline --reset --background
"$candidate_root/scripts/preview.py" --source <candidate-source.html> \
  --runtime "$candidate_root" \
  --slot <slot>-candidate --reset --background
```

Each command verifies the checkout launcher, prepares its independent page,
watches that runtime and source, and prints its exact URL. After stopping both
previews, remove the temporary checkout:

```bash
git worktree remove "$baseline_root"
rmdir "$baseline_parent"
```

## Author or revise a page

Read `<root>/skills/leaf/SKILL.md` completely and follow its authoring,
validation, handoff, and conversation-loop routes. Use the checkout launcher's
absolute path for every command written there as `leaf`, and resolve its
references from `<root>/skills/leaf/`.

`page init` vendors the checkout's runtime, theme, registry, widgets, and assets
into the page. For an existing page that must exercise the current checkout,
read `<root>/skills/leaf/references/serving-pages.md` and re-vendor it with the
checkout launcher. A served page follows that reference's stop, init, start
sequence. Fix or report a compatibility refusal without falling back to the
installed plugin.

A page that explains how a Leaf interface behaves lets the reader operate it;
`references/specimen-explainers.md` covers that pattern.

## Refresh the public catalog stills

When a change adds or removes a worked example, or changes its first viewport, run
`wt refresh-previews` from the repository root on macOS. Run `wt setup` first in a
new checkout. If Worktrunk requests approval for the project commands, ask the user
to run `wt config approvals add`. The refresh command captures every worked example,
validates the rebuilt site, pushes the complete JPEG set to
`max-sixty/leaf-assets`, and updates `example-previews.json` and the catalog links in
this checkout. Run it after the example changes are ready, and rerun it after
integrating `main` or making later fixes that change a first viewport. Those refreshes
are part of the authorized change and need no separate authorization. The generator
checks the required Charter and San Francisco fonts and fails rather than publishing
images rendered with fallback fonts.
