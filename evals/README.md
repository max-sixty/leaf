# Guidance evals

These cases score the shipped guidance in `skills/leaf/`: `SKILL.md`, its references,
and the registry entries they route to. Each case is a `case.yaml` that
`claude plugin eval` runs in a headless Claude Code, with this checkout as its only
plugin. The suite sits at the plugin root because `claude plugin eval` refuses one
inside `skills/`. The child loads the skill through the Skill tool and reads the
references it needs, as a real session does, so a case scores the guidance as it is
routed and not a passage pasted into the prompt. Run the suite before and after any
change to that guidance, and add the cases the change was made for.

The suite is early and needs a lot of work. It has seven cases, all cold single-turn
prompts that ask for an HTML fragment, a JavaScript module, or the commands the agent
would run in the reply.
None writes a page, runs `leaf`, or continues a long session, and the graders have not
been checked against pages a person has judged. The child cannot search the plugin, so
it answers from the references without reading the registry. Until that changes, a pass
here is weak evidence. `notes/usability-eval/harness.py` runs the cases that need a page
directory and `leaf`: cold authoring, reading a page back, and resuming and revising one. Still, keeping each instruction fix's cases here is better than
leaving them in a worktree's scratch. Add them as you go, and improve the suite in the
same change when it gets in the way.

Run it from the repository root:

```
claude plugin eval . --no-publish --ablation none --trust-plugin \
    --judge-model opus --allow-tools Skill Read -j 8
```

`--case <glob>` picks one case and `--runs N` sets the runs per case (3 by default).
Results and the HTML report go to `results/`, which is gitignored. A run costs about
$0.27.

`--allow-tools Skill Read` is required. The child runs in `dontAsk` mode, which denied
its Skill call for `leaf:leaf` and its reads of the references, since they sit outside
its empty working directory. Without the grant, every run answers with no Leaf
guidance at all, and `loads-leaf` still passes, because it counts the attempt. So every
case also checks that the child read the relevant reference. A run where that check
fails did not read the guidance it was meant to test.

## A/B

For an A/B, build the other arm from its revision and run both arms at once, since
batches an hour apart drift. `scripts/eval_harness.py` builds an arm as the plugin
payload at a revision. The other arm goes outside this checkout: a run loads every
plugin and case below its target, so an arm under `.tmp/` would load as a second leaf.

```
base=$(mktemp -d)/leaf
uv run scripts/eval_harness.py <rev> "$base"
cp -R evals "$base/evals"
```

Then run the command above from each arm's root. Copying the cases puts both arms on
the same suite, even when `<rev>` predates a case.

## Cases

Each case pins one clause of the guidance, and its `description` names that clause. A
case earns a place only when no existing case pins its clause. The prompt is a
self-contained moment in a session: the agent's notes, the media already registered, and
the view to write. It ends by asking for the HTML in the reply, because the child has no
page directory. Grade a fixed form with a `regex` grader, and a judgment about the page
with an `llm` grader whose `criteria` states the passing reading exactly.

A case here is cold: one prompt, the guidance fresh in context. A rule that holds cold
and then loses to a long session's context passes here, and only a replay of the
recorded session measures it. One example is `SKILL.md` step 3's reading between the
render check and the stamp.

## Record

| Date | Tried | Measured | Result |
| --- | --- | --- | --- |
| 09-25 | Rewording "Draw the subject" and the Asks premise after a review page came back mostly prose (fix-instructions on session 78ca368e) | These cases' scenarios, pasted guidance, ×3 per arm | Main's wording already drew or showed every finding (3 of 3) and put a picture in every Ask (6 of 6). The rewording drew an SVG of the Save button beside its captures in 2 of 3 runs, so it was reverted. The failure came from skipping the reading, and step 3 changed instead (31373c873) |
| 09-25 | This suite, on main at 31373c873, with graders that require the registered captures (an `lf-shot` pair for the Save case) rather than any picture or a filename in prose | All cases ×3 | 9 of 9, $2.54 plus $0.66 for the Save case re-run after its regex was fixed for `lf-shot`'s `before`/`after` attributes |
| 09-25 | Having the delivered `leaf reply` clause put landed work on the page before the thread report, after session 78ca368e posted a finished fix and its screenshot paths in a thread (fix-instructions) | Cold: a finished visual fix, a finished measurement, and a thread-only question as a guardrail, with each arm's clause pasted in the envelope, ×2 per arm. Replay: the session resumed just before its report, ×3 per arm | Cold: both arms put captures and tables on the page and linked them from the reply (4 of 4), and neither edited the page for the question (4 of 4), so cold cases don't separate the wordings. Replay: with shell calls denied, every arm took the session for a restart and none reached the report, so it measured nothing, at about $25 a run. The change rests on the log: the session followed the old clause, in context from five deliveries, and only grepped `conversation-threads.md` for one unrelated line. `landed-work-goes-on-the-page` keeps the references' half as a regression case: 3 of 3 on the change, $0.97 |
| 09-26 | Teaching the Layout classes (`layout-wide`, `layout-sidebar`, `layout-tiles`, `layout-workspace`) in place of `lf-grid`, `lf-workspace` and `main[data-width]`, with `page-arrangement-uses-layouts` added for it | All cases ×3 per arm; the base arm built from aec3eea3d, the candidate from the working tree, about 15 minutes apart | The new case went from 0 of 3 to 3 of 3: the base arm wrote `lf-grid` and `main[data-width]`, the candidate a sidebar page with tiles. The other cases held (9 of 9 each arm), except `follow-up-asks-show-their-subject`, which failed its judgment in 2 of 3 base runs and 1 of 3 candidate runs with no change to its clause. $5.97 |
| 09-26 | Exposing typed Thread actions for package controls, with `thread-widget-actions` added | Base at a47182f22 and candidate working tree, ×3 per arm | Base used `watchThreads` but had no typed action calls (0 of 3); candidate used `watchThreads` and `threadActions` correctly (3 of 3). The mirror case passed 2 of 3 candidate runs; the other run's final answer was an unrelated background-task notice, so its last-message graders saw no JavaScript. |
| 09-27 | A workspace header as one row, the title and status chips, with its lede moved into a pane, and `workspace-header-is-one-row` added for it | The new case and `page-arrangement-uses-layouts` ×3 per arm; base at cd1d37b0d, candidate the working tree, both built outside the checkout and run together | The new case went from 0 of 3 to 3 of 3; one base run, read back, put a lede in the header. `page-arrangement-uses-layouts` held at 3 of 3 on both arms. $6.38 |
| 09-27 | Dropping `page state`'s construction tree, so an agent reads the active HTML beside `state`, after the paired check in `notes/agent-usability-evals.md` | `resume`, `constructs` and `board` from `notes/usability-eval/harness.py` ×3 per arm; base at 387dfed45, candidate the working tree, run together | Both arms passed all 90 checks: the current date over a rejected save, the user's rewritten draft kept and `restated`, a stale figure re-measured, moved cards written in their folded order. $12.55 |
| 09-27 | A sidebar page's track is its `aside`, written where the stacked page needs it (a review's summary and contents first), with `sidebar-track-is-its-aside` added | The new case and `page-arrangement-uses-layouts` ×3 per arm; base at ec9572b46, candidate at 4d8d08eca, both built outside the checkout and run together | The new case went from 0 of 3 to 2 of 3: base pages put the summary in a last `div`, candidate pages in an `aside` before the body. The third candidate page did too, but rebuilt `main` as a grid to keep the track beside the body at 900px, which the next row targets. The first judging failed every page for making the summary sticky, which the case now allows. `page-arrangement-uses-layouts` held (base 2 of 3, candidate 3 of 3). $8.12 |
| 09-27 | The guide saying where a sidebar page stacks (about 870px) and that a short track sticks at `var(--lf-top)`, with `sidebar-page-at-900px` added | The new case and `sidebar-track-is-its-aside` ×3 per arm; base at 4d8d08eca, candidate at 6bb7db722, run together | The new case went from 0 of 3 to 3 of 3: every base page rebuilt the sidebar as its own grid to keep the checklist beside the log at 900px, and two stuck it at `top: var(--sp-4)`, under the banner. `sidebar-track-is-its-aside` held at 3 of 3 on both arms. $6.06 |
