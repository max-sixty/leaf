# Widget authoring formats

The controlled one-response HTML/JSON follow-up is documented in
[`controlled-README.md`](controlled-README.md). It holds components and behavior
fixed and separates first attempts from repair cost. The tool-assisted pilot below
measures the complete authoring workflow and cannot establish that contrast.

This retained eval tests whether direct Leaf HTML is easier for an agent to
author than JSON composition. `case.yaml` gives each arm the same user request
and independently checks the saved result. The first two arms keep Leaf's
runtime and widget behavior fixed; the third tests an established JSON card
system as a whole.

| Arm        | Agent writes                       | Reader                                           | What its comparison can show                                                              |
| ---------- | ---------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `leaf`     | Leaf `index.html`                  | Leaf                                             | Direct authoring baseline                                                                 |
| `json`     | A flat `root`/`elements` JSON tree | Deterministic compiler to Leaf HTML, then Leaf   | Effect of authoring syntax when the runtime and available HTML/Leaf elements are the same |
| `adaptive` | Adaptive Card JSON                 | Microsoft's pinned Adaptive Cards JavaScript SDK | Effect of a real JSON schema, component catalog, renderer, and action model together      |

The JSON tree borrows the flat keyed shape of [json-render's built-in
schema](https://github.com/vercel-labs/json-render/blob/main/apps/web/content/docs/schemas.mdx),
but is not json-render. Its elements carry HTML or Leaf tag names, an attribute
map and child IDs or text, so the compiled page uses the same Leaf runtime as
direct HTML. The Adaptive arm uses [Adaptive Cards' own JavaScript
renderer](https://learn.microsoft.com/en-us/adaptive-cards/sdk/rendering-cards/javascript/render-a-card)
and [card format](https://learn.microsoft.com/en-us/adaptive-cards/samples/input-form).
The SDK and its CSS are pinned by `package.json` and embedded in each output
page, so a retained sample opens without a CDN or a running build.

The tasks cover a read-heavy status board, one exclusive choice, and a short
form that returns submitted values. They use only capabilities all three arms
can express. No task names a format or asks for a particular widget. This is a
small pilot, selected before seeing author outputs; it is not a population
estimate for larger dashboards, agent collaboration, page updates, or custom
widgets.

Run the three conditions together with one harness and serial samples:

```sh
uv run leaf-dev eval widget-formats widget-formats/choice widget-formats/form \
  --harness codex --condition formats --model gpt-6.1-sol -j 1
pnpm run eval:view
```

Use `--repeat 3` when judging whether a pattern survives sampling variation.
The one-sample pilot is for finding harness errors and visible failures, not for
declaring a winner. Saved samples retain the agent prompt, native trace, source
file, compiled HTML, compile/check diagnostics, and rendered capture under
`.tmp/eval/<run>/samples/`. Compare the same task across the three provider
columns, and read the evidence before interpreting a pass count.

`completed` means the agent turn ended. `format-valid` means JSON parsed and its
compiler or SDK reported no diagnostics; direct HTML trivially passes this check. `page-valid`
means Leaf's render check passed for the Leaf arms, or Chromium rendered the
Adaptive Card. The `task-fit` rubric checks whether the content and offered
route address the user's request. The choice and form cases also run
`interaction.mjs` against the served page: `interaction-proven` means the browser
selected one choice at a time or received a newly visible receipt containing all
three entered form values after submission. The probe reports `defect` for an observed wrong result and
`insufficient_evidence` when it cannot identify the authored controls. A valid
document can still omit a fact, bury the blocker, or offer a broken control.
The interaction probe runs after a successful plain Leaf check even when the
render check finds a layout defect, so those outcomes remain separate.
An `interaction-proven: false` row includes both defects and unscored attempts;
read `metadata.interaction.status` and its reason before counting behavior failures.
Record failures by stage: parse/schema, compilation, page render, task meaning,
and operated interaction. The native trace shows repair attempts and tool calls;
Promptfoo reports tokens and elapsed time. Treat those costs as part of the
authoring outcome, with setup cost for the compiler or renderer reported
separately.

The Adaptive result cannot identify the effect of JSON syntax alone. Its SDK
supplies a fixed card vocabulary and host styling, while Leaf supplies a page
runtime and open widget layer. A format win on these tasks says which complete
authoring path served these tasks better. API-level strict JSON-schema decoding
is also a separate factor: these agents write files through their normal tools,
and post-generation validation is not constrained decoding.

The renderer and interaction probe can be checked without spending a model call:

```sh
node evals/widget-formats/adaptive-render.mjs CARD.json OUT.html
```

It rejects parse and SDK validation errors, then writes a self-contained page.
On an `Action.Submit`, the page shows a local receipt and records the action and
submitted values in `window.__evalActions`; it sends nothing. This verifies the
format arm's integration, not an agent-authored sample's quality.

```sh
node evals/widget-formats/interaction.mjs choice URL EVIDENCE_DIR
node evals/widget-formats/interaction.mjs form URL EVIDENCE_DIR
```

The URL must be a live served page. For Leaf, serve the sample with Leaf so its
widgets can record actions; for Adaptive Cards, a static server suffices. The
probe saves `interaction.json` and before/after screenshots in `EVIDENCE_DIR`.
