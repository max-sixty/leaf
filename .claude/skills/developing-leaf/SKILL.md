---
name: developing-leaf
description: Develops changes to what Leaf readers see and do from the current checkout, including UI exploration, page previews, browser testing, and before-and-after proof.
---

# Develop Leaf from this checkout

Resolve the repository root three directories above this `SKILL.md`, then resolve
`<root>/bin/leaf` to an absolute path. Run that launcher with `--version` and
continue only when it prints the same repository root. Use the absolute launcher
throughout; a bare `leaf` command may resolve to the installed plugin instead.

## Explore an open design

When a new interface leaves a material visual or interaction choice unsettled,
first follow `Author or revise a page` below. Initialize the page with the
`playground` package and follow
`<root>/skills/leaf/packages/playground/guidance/author.md`. Put several coherent
options in named presets. Build each option far enough that the reader can operate it
in the shared preview. Controls select the option and its parameters; the reader
performs the interaction being judged inside the preview. Use the reader's submitted
configuration or feedback to choose the one implementation the finished change keeps.

When the subject already exists, implement each proposed behavior in the code that
owns that surface and preview its real output and styling. A Leaf interface therefore
implements candidates in its owning runtime and theme and presents them through a
shipped example or fixture. Page-local HTML and CSS may frame it; a page-local
recreation is a sketch.

## Prove and hand off a visible change

Re-vendor before trusting a browser result after a runtime, theme, registry, or
widget change. An `/ui-sweep` and a look at a composed page are worth the time;
a green suite does not judge visual quality.

Reproduce the baseline from a clean checkout of `git merge-base HEAD main`, then
compare it with the candidate through the workflow below. Every difference that
a still can show requires one sentence and matched before/after screenshots,
embedded in the session or presented as one `lf-shot`. A live preview may
accompany the pair, but does not replace it. For an interaction-only change, keep
both previews live and hand off the labeled URL pair with the action that reveals
the difference. Add another state or width only when the first comparison cannot
show the behavior.

Before presenting a served page or visible runtime change as finished, inspect
the exact candidate URL. Exercise the same journey in the baseline and candidate,
matching the URL fragment, viewport, theme, and interaction state, and check both
browser consoles. Confirm the expected content and review the changed surface at a
representative viewport. When handing off a live preview, use the exact URL including
the semantic block's fragment and keep the process alive. A titled section uses the
section's stable id, so its eyebrow and heading arrive together. Add an id to the
tight semantic container when it has none.

## Preview a shipped example

From the repository root, run `scripts/preview.py <example> --export` for a
standalone static rendering. Start `scripts/preview.py <example>` in a
long-running command or terminal session for an interactive preview. Keep it
alive and retain the exact served URL. The script watches source and runtime
edits and preserves feedback at `.tmp/previews/<example>`. Repeating the command
reuses that preview; use `--slot <name>` for another copy. A refused update
appears in the terminal or the background log named at startup. Fix the input
and the watcher retries.

Browser automation runs `scripts/preview.py <example> --automation` in a
long-running process. The command uses the browser suite's temporary server: the
real HTTP and event log, with no task claim or durable service. Its default page
is `.tmp/previews/<example>-automation`; use the reader preview's distinct page
when presenting a URL for feedback. An explicit slot cannot change interaction
mode.

When finished with a preview, run the matching preview command with `--stop` (and
`--automation` for its automation slot); it waits for the watcher and server to
stop. Ctrl-C stops a foreground preview. A slot refuses a different source or seeded
history so it keeps the existing page and feedback. Use `--reset` to discard the
selected slot and rebuild it from the current fixture.

### In Codex

1. Call `mcp__codex_app__open_in_codex` with the destination's fragment URL as a
   browser target and `placement: "right"`.
2. Run `<root>/bin/leaf codex start <root>/.tmp/previews/<example>` so Leaf
   comments return to the current task.
3. Tell the user to select page text or use Leaf's comment affordance for a Leaf
   thread. Codex Annotation mode creates visual comments that the user sends with
   their next chat message. Use the Codex review pane when feedback belongs to a
   source line.

## Test the hosted website agent

Run `<root>/scripts/verify-site-agent-local.sh` for the development loop. It builds
the current site, starts the canonical website adapter, uses the host's logged-in Codex
App Server, asks for one heading edit, and verifies the publication, reply, and changed
page in Chrome. Its profile reports request acknowledgement, agent activity,
publication, reply, HTML, first contentful paint, JavaScript, state, upgrade, and
presentation timings. It stops every process and removes the disposable reader page
when it finishes.

This fast loop bypasses the Cloudflare Worker, Queue, container allocation and
resource limits, and outbound credential proxy. When a change touches one of those
boundaries and `OPENAI_API_KEY` is exported, build the Worker and run the same check
through Wrangler's local Queue and Docker container:

```bash
npm ci --prefix <root>/worker
npm run build --prefix <root>/worker
LEAF_VERIFY_AGENT=1 <root>/scripts/verify-site-local.sh
```

Local infrastructure is emulated, so neither loop proves edge rollout or production
latency. The `publish-site` workflow runs `scripts/verify-site.py` against the exact
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
by an earlier run.

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
