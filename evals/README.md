# Guidance evals

These cases score the shipped guidance in `skills/leaf/`: `SKILL.md`, its references,
and the registry entries they route to. Each case is a `case.yaml` that
`claude plugin eval` runs in a headless Claude Code, with this checkout as its only
plugin. The suite sits at the plugin root because `claude plugin eval` refuses one
inside `skills/`. The child loads the skill through the Skill tool and reads the
references it needs, as a real session does, so a case scores the guidance as it is
routed and not a passage pasted into the prompt. Run the suite before and after any
change to that guidance, and add the cases the change was made for.

The suite is early and needs a lot of work. It has three cases, all cold single-turn
prompts that ask for an HTML fragment in the reply. None writes a page, runs `leaf`, or
continues a long session, and the graders have not been checked against pages a person
has judged. The child cannot search the plugin, so it writes widget markup from the
references without reading the registry. Until that changes, a pass here is weak
evidence. Still, keeping each instruction fix's cases here is better than leaving them
in a worktree's scratch, so add them as you go, and improve the suite in the same change
when it gets in the way.

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
case also carries `reads-page-authoring`. A run where it fails did not read the guidance
it was meant to test.

## A/B

For an A/B, build the other arm from its revision and run both arms at once, since
batches an hour apart drift. The other arm goes outside this checkout: a run loads every
plugin and case below its target, so an arm under `.tmp/` would load as a second leaf.

```
base=$(mktemp -d)/leaf
git worktree add --detach "$base" <rev>
rm -rf "$base/evals" && cp -R evals "$base/evals"
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
| 09-25 | Having the delivered `leaf reply` clause put landed work on the page before the thread report, after session 78ca368e posted a finished fix and its screenshot paths in a thread (fix-instructions) | Cold: a finished visual fix, a finished measurement, and a thread-only question as a guardrail, with each arm's clause pasted in the envelope, ×2 per arm. Replay: the session resumed just before its report, ×3 per arm | Cold: both arms put captures and tables on the page and linked them from the reply (4 of 4), and neither edited the page for the question (4 of 4), so cold cases don't separate the wordings. Replay: with shell calls denied, every arm took the session for a restart and none reached the report, so it measured nothing, at about $25 a run. The change rests on the log: the session followed the old clause, in context from five deliveries, and only grepped `conversation-threads.md` for one unrelated line |
