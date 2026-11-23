# Change Leaf's instructions

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
passage that has grown into a list is rewritten around its goals. The fix states the
goal the failing page missed and what an author weighs to meet it, and offers the form
that passed the eval as a default to depart from where the content calls for it, not
as a requirement. Where the author passed over a widget, as by drawing a chart by hand
that the vocabulary already draws, the fix names the form in the workflow and sharpens
the entry's `description`, rather than naming the tag in the workflow (root
`AGENTS.md`, "Keep the layer open").

## Score an instruction change

Root `AGENTS.md`, "Working on the repository", says which changes to score. Choose the
eval by what the instruction is for:

- Leaf's shipped workflows: Leaf's suite in `evals/`.
- The root `AGENTS.md` or `SOUL.md`: `pnpm run eval:root-guidance`, which scores the
  working tree's text beside the merge base's (`evals/root-guidance/README.md`).
- Other maintainer guidance, such as this skill or an area's `AGENTS.md`: a temporary
  A/B in scratch that gives each arm its version of the passage, with no committed
  case, unless the development contract needs the suite's staging, such as a served
  page or an installed arm.

For Leaf's suite, run the merge base beside the working tree with `--base`;
`evals/README.md` owns the commands, selection, arms, the case format and where results
go. Score
every case whose `metadata.tags` covers the passage, such as `asks` for decisions,
counting only runs whose native trace shows they opened the changed file, and read the
outputs as well as the pass counts.

Extend an existing case wherever one nearly fits, since every case costs time and
money on each later run, and keep only cases that cover distinct failures or necessary
controls. Give the subject the task, context, tools and handoff it would receive in
normal use, with only the fixture facts the case needs, and keep grading criteria and
harness bookkeeping out of its input. Let the installed instructions teach the
workflow and route the subject to their references, rather than telling it what to
read or repeating their procedure; a replay preserves what the recorded session had
read. Where an author reaches the rule through `leaf page instructions`, the case
gives the subject a page to run it on (`evals/README.md`, "Case format"). A case that states the situation plainly usually
passes on both arms, so paste in the earlier turns or competing instruction that
pulled the failing session the other way.
A rule that fails only late in a long session needs a replay of that session.
