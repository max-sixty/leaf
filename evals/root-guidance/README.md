# Root guidance

Given only Leaf's root text, does a fresh agent make the calls the maintainer has
made? The root text is the root `AGENTS.md` with the `skills/leaf/SOUL.md` it imports,
which together hold the maintainer's principles. This experiment gives a model that
text and nothing else about Leaf, puts to it a situation in which the maintainer made
a call, and has a judge compare what the model says it does with the call. Run it
when the root text changes, to score the changed text beside the text it replaces.

## Run

```sh
pnpm run eval:root-guidance --repeat 3
pnpm run eval:view
```

Each arm is a version of the root text. `head` is the text in this working tree,
uncommitted edits included, and `base` is the text at the merge base with the local
`main`. Where the two are the same text, only `head` runs. Three samples of each
situation is the usual run. Each sample makes two calls on the host's Claude login:
the subject's, which carries the root text, and the judge's.

Promptfoo's options select part of a run, such as one situation on one arm, or the
situations of one kind:

```sh
pnpm run eval:root-guidance --filter-pattern '^rare-hold$' --filter-providers head
pnpm run eval:root-guidance --filter-metadata kind=holds --repeat 3
```

## Reading the results

A sample passes when the judge finds that its answer makes the call. Samples of one
situation differ, so read a cell, one situation on one arm, by how many of its samples
passed. Promptfoo exits with 100 when any sample fails, so the script's exit code
reports failed samples, not a broken run. It writes the run to
`.tmp/root-guidance/results.json` and counts each cell of a repeated run there:

```sh
jq -r '.results.repeatStability.groups | group_by(.description)[]
  | [.[0].description] + (sort_by(.provider.label)
    | map("\(.provider.label) \(.passed)/\(.repetitions)")) | @tsv' \
  .tmp/root-guidance/results.json
```

Each situation has a kind, and Promptfoo totals each arm's passes by kind, as a metric
of the kind's name:

- `call`: a call the maintainer made. A cell that fails is a call the root text
  doesn't decide. Its rule may belong in the root, or in the area's `AGENTS.md` or
  the module header an agent reads when the case comes up.
- `holds`: a rule the root text already settles. A cell that passes on `base` and
  fails on `head` is a rule the change lost.

The subject ends its answer with a `PASSAGE` line, the words of the root text that it
says decided the answer. For a failed sample, read that line beside the judge's
reason. It shows whether the text said nothing about the call or said something that
led the answer away from it:

```sh
jq -r '.results.results[] | select(.success | not)
  | "\(.testCase.description) on \(.provider.label)\n\(.response.output)\n\(.gradingResult.reason)\n"' \
  .tmp/root-guidance/results.json
```

## Parts

- `situations.json` holds the situations. Each has an `id`, its `kind`, the `text`
  and `ask` put to the subject, and the `rubric` the judge grades by, which the
  subject never sees. A `text` describes Leaf as it stood when the call was made, so
  it can differ from the tree. Where a public record exists, `source` names it: the
  pull request or issue that records a call, or for `holds` the section of the root
  `AGENTS.md` that states the rule.
- `promptfooconfig.mjs` composes each arm's text, `AGENTS.md` with its import of
  `SOUL.md` replaced by that file's text, and declares an arm per distinct text.
- `provider.mjs` is the subject, whose system prompt is the arm's text, and
  `grade.mjs` is the judge, which reads the situation, the answer and the rubric.
  Both ask through `dev/leaf_dev/claude_ask.mjs`, which gives the model no tools and
  nothing of the host's settings. `MODELS` and `JUDGE_MODELS` in
  `dev/leaf_dev/arms.py` pin their models.

## Adding a situation

A change that writes one of the maintainer's calls into the root text adds that
call's situation, so the run shows `base` missing the call and `head` making it.
Write the `text` as the choice stood before the call, with the pull the other way
that made it a call: the option that looked reasonable, in the words its advocate
would use. A situation that states the choice plainly passes on every arm and
measures nothing. The `rubric` says what the maintainer did and which other answers
fail, in terms a judge can apply to an answer that never mentions the root text.

A situation whose call the maintainer has since reversed is rewritten or removed,
with the rule the root text states for it.

## Limits

- Three samples a cell is a coarse instrument. For a cell that passed two of its
  three samples, Promptfoo's 95% interval (`passRateConfidenceInterval`) is 21% to
  94%, so a cell that differs by one sample between arms may not differ.
- The subject and the judge are the same model family, so a misreading of a rubric
  that both share passes unseen.
- A `call` situation was written by someone who knew the call. Its text may lead
  toward the call, or away from it, more than the case it came from did.
- The subject sees only the root text. A pass says the text decides the call when the
  text is what the agent reads. It doesn't say a working session, which also holds a
  task, an area's guidance and a long context, will reach the passage.
