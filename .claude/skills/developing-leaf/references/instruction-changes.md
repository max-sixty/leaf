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
