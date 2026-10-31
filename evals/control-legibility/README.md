# Control legibility

What does each item in a view do, to someone who has only seen it? Leaf's controls
show a symbol wherever a standard one exists (`browser/AGENTS.md`, "Controls are few
and quiet"),
so a reader must tell from the symbol alone what pressing it does. This eval shows a
model a view with every control numbered, asks what each one does, and has a judge
compare each reading with what the control does. A control read as another action is
what it exists to find, as Undo's old arrow, which is Lucide's and VS Code's reply
arrow, could read as Reply beside a message.

## Run

```sh
pnpm run eval:legibility --repeat 3
pnpm run eval:view
```

The first command captures the views from this working tree into
`.tmp/control-legibility/` (`views.py`, a `leaf-dev probe` journey), then runs
Promptfoo over them and writes `results.json` there. Each sample makes two calls on
the host's Claude login: the reader's, with the picture, and the judge's, in text.

## Reading the results

A view's score is the share of its controls read as one of their actions, and its
reason lists every other reading as `misread as …` or `unclear`. Readings vary from
run to run, so repeat and act on what recurs. A symbol drawn alone has no context:
the find bar's chevrons read as expand and collapse on the sheet, where the find bar
would settle them.

## Parts

- `views.py` draws each view and numbers its controls. Today's one view is every
  icon an action shows, drawn alone through the runtime's `offerAction`; an icon
  several actions share stands for all of them.
- `actions.json` says what pressing each action does, the truth the judge reads. It
  names exactly the actions `ACTIONS` in `browser/runtime/icon-paths.js` holds, and
  the capture refuses to run until a new action has its line.
- `provider.mjs` is the reader, given only the picture and a line about the app;
  `grade.mjs` is the judge. `promptfooconfig.yaml` names their models.

## Growing it

The question is general, and the parts above are built for more views than the sheet:

- **Controls in place.** Number a `leaf-dev stills` state, such as a thread card's
  head or the draft's toolbar, with the same `NUMBER`. A control there would stand for
  its own action, which the DOM doesn't record yet; `offerAction` marking each press
  with its action would give the truth without reading labels.
- **Every item, not only symbols.** The numbers work for word buttons, menu rows,
  margin marks and status chips, asking what each means or does. Items that aren't
  actions need a source of truth like `actions.json`.
- **Collisions within a view.** Two items read as the same action in one view.
- **More readers.** A Codex reader beside Claude (`ui-review-detection/provider.mjs`
  shows that transport), and a phone viewport.
- **A check on a change.** Run against the merge base when a change touches
  `icon-paths.js` or a control's face, and compare the readings.
