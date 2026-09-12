# Playground capability plan

Leaf should have one reusable Playground package and many page-instance playgrounds.
The package owns mechanics that recur across examples. A page instance selects that
package, then owns its particular artifact, state model, controls, output, and
page-specific JavaScript. It does not become a package merely because it is interactive.

This plan closes the useful gaps left by the retired standalone playground skill without
rebuilding a second, weaker page system inside Leaf. It uses Leaf's existing
[page-owned behavior and declarations](../skills/leaf/references/page-authoring.md#page-behavior),
[captured revision](../skills/leaf/scripts/leaf/page-storage.md),
[public widget behavior](../skills/leaf/references/packages.md#a-widget), and
[static and interactive exports](../skills/leaf/references/serving-pages.md#exported-files).
Those contracts supply the one semantic publisher, stable Targeting references, rendering
lifecycle, and presentation barrier; this plan owns only the Playground capability built
with them.

## Ownership

| Owner | Owns |
|---|---|
| Playground package | Control and preset mechanics, one working-configuration loop, tab persistence, reset, copy, submit, projection, accessible layout, and public integration points |
| Other packages | Reusable capabilities such as Targeting, Diff, Diagram, Visual Review, comments, and suggestions |
| Page instance | The real artifact, task-specific state and schema, page module, derived output, chosen package composition, and instance-specific tests |
| Core Leaf | Revision-correct assets and declarations, typed event admission, stable identity, browser lifecycle, static export, and interactive export |

Promote page code into the Playground package only when separate page instances need the
same mechanics. Promote a specialized capability into its own package only when it has
an independent vocabulary and lifecycle. Worked examples remain page instances.

## Package contract

### #2 and #6 — One configuration drives every path

Replace the present split between declarative control values and page-module preview
state with one JSON-safe working configuration. Built-in controls contribute ordinary
fields. A page module may register one or more named contributors for structured state
such as filter rows, graph edges, target roles, canvas positions, reorderings, or custom
gestures.

One public registration call takes a stable contributor name, its default snapshot, and
the operations needed to read and apply a snapshot. It returns the notifier the page
module calls after a gesture changes that source. Contributor names are unique and do not
collide with control names. `lf-playground` remains the coordinator: restore, preset,
reset, projection, copy, and submit all consume the same aggregate configuration, and
every change event contains a fresh clone of it. Contributors do not keep a second
durable history or submit their own competing action. This editable aggregate is local
draft or reader-session state; only `Submit` enters the reactive semantic publisher and
Leaf's shared event path.

The final action keeps the existing `values` plus `instruction` shape; `values` becomes
the aggregate configuration rather than renaming the action contract. The page instance
declares the exact schema for its task-specific values in `page/registry.json`, and Leaf
admits them through the normal event path. The package must not replace precise page
schemas with an unvalidated arbitrary object.

Simple scalar playgrounds keep the declarative path. They should not need a page module
or registration call.

### #6 — Output is derived, not interpolated only

Keep authored `lf-playground-output` with `lf-playground-value` as the zero-JavaScript
default. Add one public instruction provider for page modules whose result depends on
conditions or structured state. The package still owns copy feedback and sends exactly
the instruction it displays.

Guidance for an instruction provider requires it to:

- name the object, destination, and evidence needed to act;
- omit settings that remain at their defaults unless their presence is material;
- translate numeric choices into qualitative intent where that helps implementation;
- include structured additions, removals, ordering, and relationships in readable prose;
  and
- remain sufficient when read without the playground.

Do not add a declarative condition language. Page-authored JavaScript is the simpler
expression mechanism for task-specific output.

### #6 — Comparisons preserve controlled differences

One gesture drives every candidate from the same input snapshot. A page may keep
candidate-specific values under explicit candidate keys and offer a copy-to-other
operation, so the reader can hold all but one variable equal. Measurements use the same
gesture snapshot as the candidates they compare.

This is initially a recipe over the shared configuration API. Extract another package
primitive only after two worked examples need identical comparison mechanics.

## Authoring and discovery

### #3 — “Playground” should discover Leaf

The Leaf skill description names playgrounds, explorers, simulators, and interactive
tools as triggers. Its first routing step says that bespoke behavior belongs in a page
module and does not require a new package. Package guidance explains the three cases:

| Need | Owner |
|---|---|
| One page's behavior or state model | Page instance |
| Mechanics reused by several pages | Existing or new package |
| Revision, identity, event, or export guarantee | Core Leaf |

### #4 — Restore task-shaped recipes

Expand Playground author guidance with recipes for:

- data and query explorers with dynamic rows, ordering, and nested configuration;
- concept and code maps with semantic nodes, relations, direct manipulation, and
  comments;
- real-artifact A/B comparisons with controlled differences and live measurements; and
- multi-change decision sweeps with stable ids and a retained decision set.

Each recipe specifies the state shape, interaction loop, output strategy, accessibility
route, and verification journey. It routes document critique and code-diff review to
Leaf's existing suggestion, comment, Diff, and Visual Review capabilities instead of
recreating the retired templates.

“Use the real artifact” becomes operational guidance:

- start from the built output or captured runtime DOM, not an empty application shell;
- alter or wrap the real nodes rather than recreating their appearance;
- preserve the artifact's tokens, typography, states, and viewport assumptions;
- seed fixtures at build time so reopening does not depend on a network fetch; and
- when compiled variants differ, build both from their source revisions and serve them
  from the same captured page-instance graph.

## Targeting

### #7 — Compose reusable identity with page-chosen editor semantics

The Targeting package already supplies the composed candidate walk, stable id and
structural references, multiple named selections with their resolution states, and a
public controller for arm, disarm, reset, and current draft state. A playground composes
that capability instead of rebuilding target identity or resolution.

Core Leaf owns identity and resolution. Labels, colors, and prose are presentation,
never identity. The page instance or a reusable controller still chooses semantic
boundaries, editable properties, value grammar, and the live edit appropriate to the
artifact.

## Website examples

The examples catalog should prove the general model, not only list the package.

1. Repair `notification-playground.html` so event pressure participates in the same
   configuration, reset, persistence, copied instruction, and submitted result as its
   declarative controls.
2. Add a structured data explorer with dynamic filter rows and ordering. It uses one
   page module, a page-owned schema, a derived preview, and a natural-language result;
   it does not add a package.
3. Add a controlled A/B example around actual built output from the repository. One
   direct gesture reaches both candidates, candidate-specific configuration can be
   copied across, and a live measurement exposes the consequence. A hand-built visual
   replica does not satisfy this example.

The catalog and package page link these as examples of one Playground package applied to
different page instances. At least one example also composes the shipped Targeting
capability.

## #5 — Interactive standalone delivery

Use the static export for a readable, script-free record and the explicit interactive
export when the artifact needs local controls, presets, custom gestures, derived output,
reset, or copy. The interactive form runs the captured revision without host chrome or
networking and disables submission with an honest “no agent or server is available”
state.

The Playground package contains no export-only parallel runtime. It operates against the
same offline mode and captured dependencies as every other interactive page.

## #8 — Verify the page-specific loop

Package tests cover reusable mechanics. Every worked or user-facing playground also gets
a browser journey that:

- waits for `data-lf-presented`;
- directly operates every control, preset, custom gesture, reset, copy, and submit path;
- checks the preview, aggregate configuration, displayed instruction, and recorded
  action after each relevant transition;
- uses the real gesture rather than injecting the expected state;
- checks wide, narrow, and short viewports; and
- exercises both static and interactive exports.

For an A/B example, the test proves both candidates received the same input snapshot and
that copying candidate-specific configuration changes only the intended difference.

## Implementation slices

1. Land #3, the #4 recipes, and the stronger #8 author checklist. Repair the notification
   example by making pressure a normal scalar control in its one existing configuration.
2. Use page-owned declarations and the public widget behavior contract to add the
   aggregate configuration and instruction-provider contracts, then build the structured
   data explorer (#2 and #6). Reuse the existing page/runtime validation fixture rather
   than creating a second integration shape.
3. Build the real-artifact A/B example and extract only the comparison mechanics it and
   an existing example actually share (#6).
4. Compose the shipped Targeting capability into a playground example (#7), and verify
   every worked example through both existing export modes (#5).

Each slice updates package declarations, guidance, generated references, website copy,
and browser tests together. Future-tense rules move from this note into the owning
contracts as they ship; the final slice deletes this note and its `TODO.md` entry.

## Acceptance

The plan is complete when an agent asked for a playground discovers Leaf, initializes a
single page with the existing Playground package, and builds all three website shapes
without creating a task-specific package. Structured gestures survive reset and restore,
the copied instruction and submitted action describe the same configuration, relational
targets resolve after revision, and the page exports as both a static record and an
offline interactive artifact. Existing declarative scalar playgrounds continue to work
without page JavaScript.

## Retired-skill reference

The removed local skill is design evidence, not a Leaf dependency. On the development
machine it remains in Mackup history at commit `21299bba`:

```bash
git -C ~/Mackup show 21299bba^:.claude/skills/playground/SKILL.md
git -C ~/Mackup show 21299bba^:.claude/skills/playground/upstream/SKILL.md
git -C ~/Mackup ls-tree -r --name-only 21299bba^ .claude/skills/playground
```

The useful source material is the single-state and output discipline, the data/concept/
code-map recipes, real-artifact comparison guidance, per-page verification checklist,
and Targeting design. Its standalone shell, duplicated review tools, visual styling, and
runtime-generated identity are not contracts to port.
