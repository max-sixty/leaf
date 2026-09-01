# Ask placement eval

Scores a wording of the authoring guidance on where it makes an author put each
ask: after the passage that makes it answerable, or gathered after the
explanation. Three subjects, each a page an agent would write from working
notes whose decisions are listed after the findings:

- `list-items.md`: a code review whose two asks each turn on one item of a
  six-item list. The wording under test has to put each ask after its item
  rather than after the list and its evidence.
- `sections.md`: a capacity report whose two asks turn on whole sections. Both
  wordings place these in their section; it shows the rule does not disturb what
  already worked.
- `whole-page.md`: a review packet whose one ask turns on everything before it.
  A guardrail: the ask belongs last, and a wording that pulls it earlier fires
  where it should stay quiet.

## Running

Each arm is a directory holding that arm's `SKILL.md` and
`authoring-decisions.md`; `run.sh` pastes the skill's Page contract, the
reference's opening, and page-authoring.md's Reading cost from the working tree
into one prompt with the subject, so only the two files under test differ.
Stage the old arm from git and the new one from the working tree:

```sh
d=$(mktemp -d)
mkdir "$d/old" "$d/new"
git show main:skills/leaf/SKILL.md > "$d/old/SKILL.md"
git show main:skills/leaf/references/authoring-decisions.md > "$d/old/authoring-decisions.md"
cp skills/leaf/SKILL.md skills/leaf/references/authoring-decisions.md "$d/new/"
for s in list-items sections whole-page; do
  for n in 1 2; do
    notes/ask-placement-eval/run.sh "$d/old" $s $n &
    notes/ask-placement-eval/run.sh "$d/new" $s $n &
  done
  wait
done
python3 notes/ask-placement-eval/outline.py .tmp/ask-placement-eval/*.html
```

The arms of one subject run together so drift over the session lands on both.
Count a run only when its `is_error` is false. `outline.py` prints each page's
headings, list items, and decisions in document order; read where each
`DECISION` falls against the item or section it turns on.

## Baseline

Old and new wording at the change that introduced the placement rule, two runs
per arm, all runs complete:

| Subject | Old wording | New wording |
|---|---|---|
| `list-items` | both asks stacked after the list and its evidence, 2/2 | each ask after its item, 2/2 |
| `sections` | each ask in its section, 2/2 | each ask in its section, 2/2 |
| `whole-page` | last, 2/2 | last, 2/2 |
