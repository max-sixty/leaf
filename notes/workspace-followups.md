# Leaf next-work backlog

Research at merged commit `cb7915bb`, 8 September 2026. Research briefs for workspace items in [TODO.md](../TODO.md).

I recommend keeping the current primitives and spending the next cycle on reliable shared contracts, convincing examples and a measured authoring advantage. The larger layout vocabulary should follow evidence from those tasks.

The shared-contract and example items this note opened with have landed; what remains is verification and the product questions the implementation cannot settle. Use the arrangement baseline in #19 to choose which recipes to improve, and run the keyboard journey #14 against the examples it protects.

Items are ranked within each group. IDs are stable references, not a global priority score. Agent-owned work is distinguished from the repeated-use pilot, which needs Max’s purpose and participation. Evidence labels separate reproduced defects from code gaps and experiments.

## Keep the user oriented

<a id="item-14"></a>

- **#14** **Verify the complete keyboard and accessibility route** — Exercise the workspace as one keyboard task, including reading, pane furniture, local comments and Threads.

  **Evidence / confidence:** Composition verification task. The visual-review journey now covers real Go-to controls and pane furniture, case-local comments, covering and nonmodal Threads, draft restoration, bounded/flow transitions, and shared reading keys. A general named two-pane journey still needs to walk authored landmarks plus header and footer controls together and verify every painted focus mark remains unobscured.

  **Next task:** Use a named two-pane example with header/footer controls; walk authored landmarks and controls, use reading keys, open Threads, return through Escape, then change posture. Check focus against actual modal/nonmodal behavior.

  **Done when:** Every action is reachable with a comprehensible accessible name and visible focus. Covered content does not leave the user lost. Focus containment follows the shipped modality: held inside a workspace that covers the document, and never imposed on one that sits beside it.

  **Owner / dependencies:** Sol. The Threads placement this item waited on is settled: Threads stands over the document at every width and takes no room from it, and it takes the modal covering boundary ([PR #536](https://github.com/max-sixty/leaf/pull/536)) only where it leaves less than a usable page beside it. Verify the keyboard route against both: the live page beside an open panel, and the modal boundary where it covers.

  **Sources:** [lf-pane.js:29](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-pane.js#L29), [test_render_navigation.py:106](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/tests/test_render_navigation.py#L106), [panel.js:75](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/thread/panel.js#L75).

## Measure the product boundary

<a id="item-19"></a>

- **#19** **Measure what Leaf saves an authoring agent** — Run a small blind authoring comparison against plain HTML, including the cost of the subsequent feedback cycle.

  **Evidence / confidence:** First slice measured for arrangement with the [arrangement-eval harness](arrangement-eval/README.md): Leaf's arrangement vocabulary against plain page CSS on a document, a dashboard and a queue, plus a standing-preference revision. On the layout #1171 landed, a blind reviewer preferred the plain pages in 11 pairs, the leaf pages in 4, and split 3; the vocabulary cut page CSS about fourfold but not turns. The full write-up is [the harness README before its results moved out](https://github.com/max-sixty/leaf/blob/5e7fc3acf988d45649421a0b66483165cdefb57c/notes/arrangement-eval/README.md#results). Widgets beyond arrangement, and package guidance, are still unmeasured.

  **Follow-ups from the first run** (reproduced in the judge's defect lists and checked against the screenshots):

  - Drawn text: the theme scales a drawing to its box, so labels become unreadable at 900px and on a phone. The render check should measure each label's drawn height and flag a drawing whose smallest label is under about 10px; drawn size, not the percentage it shrank by, is what decides legibility.
  - Render check: it passed all 72 pages. On the settled 1200px page, flag a figure scrolled sideways out of view and an Ask below its pane's first screen; taking such readings across widths is a TODO.md item beside the mobile ones.
  - Render check: report the width at which each grid stacks, which no queue author could see.
  - Rail: it comes last on a phone and doesn't stick, and its 14rem floor cramps a table or log at 900px.

  **Next task:** Give comparable agents document-review, configuration and queue/detail tasks with the same content and acceptance criteria. Compare usable output, time/tokens, custom CSS and repair iterations; then require a comment and revision on each result. Counterbalance task order.

  **Done when:** Produce the artifacts and an independently assessed task-level result, including failures. Use the findings to decide which guidance or primitive earns investment; avoid reducing quality to lines of code.

  **Owner / dependencies:** Astra designs comparison; Sol agents execute. Extend the [existing agent-usability evaluation plan](agent-usability-evals.md#first-executable-slice) with this baseline before further recipe polishing; repeat relevant cases after #20.

  **Sources:** [page-authoring.md:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/page-authoring.md#L78), [notification-playground.html:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L1), [review-queue.html:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L1).

<a id="item-20"></a>

- **#20** **Teach the few compositions that earn their place** — Put useful composition suggestions in the owning widget or package guidance, with worked examples where they help authors choose.

  **Evidence / confidence:** Guidance experiment after observed authoring failures. The current authoring reference explains the primitives and links examples. We have not tested whether an unfamiliar agent chooses the right shape, state owner or fallback order from that guidance.

  The agent-loop review supplied current and proposed flowcharts in separate tabs; the user then asked for a diagram showing the change itself. Its author had read the diagram reference and selected the package. The `pr-walkthrough` example's “Behavior diff” already shows changes in place. The optional `code-review` package now trials task-level authoring suggestions, including behavior comparisons; whether a cold author discovers and uses it remains unmeasured.

  **Next task:** Use failures from #19 to test short suggestions for document, configuration, queue/detail and comparison tasks with an unfamiliar agent. Preserve one state owner, meaningful pane labels, purposeful furniture and authored-order flow. For comparisons, include process simplification, structural change, and an unchanged system as a control: judge whether the user can identify the differences, not whether every page contains a diagram.

  Check discovery both before package selection and through `page guidance PAGE author`. Keep widget-specific advice in `x-guidance`, cross-widget compositions in package guidance, and general selection principles in the authoring reference. Add a task-oriented discovery route only if authors miss relevant packages; compare it with the existing routes before building it.

  **Done when:** A fresh agent builds the task using the documented surfaces without copying runtime internals or inventing layout-specific state. Keep only guidance that changes the result.

  **Owner / dependencies:** Sol drafts; Astra reviews the public model. After #19. This extends packages; it does not create a named-layout registry.

  **Sources:** [page-authoring.md:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/page-authoring.md#L78), [packages.md:202](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/packages.md#L202).

<a id="item-22"></a>

- **#22** **Verify workspaces at the experimental MCP boundary** — Check the same workspace in a full iframe, a constrained host and the existing snapshot/browser handoff.

  **Evidence / confidence:** Documented host limitation; missing workspace journey. The README calls inline MCP rendering experimental and describes a comments-only snapshot when the nested live frame is blocked. Existing MCP render tests do not include the new workspace case.

  **Next task:** Exercise permitted full rendering and the declared fallback using the same authored workspace. Check the host’s available size, snapshot containment and the route to the full browser for real controls.

  **Done when:** Each mode accurately signals what is interactive; all content and actions are reachable in the full browser. Use the host’s supported boundary rather than duplicating workspace rendering or bypassing its sandbox.

  **Owner / dependencies:** Sol. Lower priority while full-browser Leaf remains canonical; no dependency on a new host API.

  **Sources:** [README.md:64](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/README.md#L64), [page-app.js:113](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/scripts/mcp-app/page-app.js#L113), [test_render_mcp.py:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/tests/test_render_mcp.py#L1).

<a id="item-23"></a>

- **#23** **Find out whether people return to a workspace** — Run repeated real tasks to decide how much persistence and workspace customization Leaf should own.

  **Evidence / confidence:** Purpose and audience experiment. The original positioning question remains unresolved: a page handed over for a decision and a persistent project workspace can use similar HTML but create different expectations. The implementation cannot settle that product choice.

  **Next task:** Use configuration, review and monitoring on recurring work. Observe whether users reopen the same page, need saved navigation/selection, or prefer a fresh artifact; compare the full feedback cycle with the tools they already use.

  **Done when:** A short record of actual returns, abandoned flows and completed tasks supports a decision about saved layouts, project navigation and the target user. My recommendation is to begin with task-scoped workspaces.

  **Owner / dependencies:** Max chooses real work; Astra studies usage. Max’s participation and choice of real work are required; the notification playground supplies a useful starting workflow.

  **Sources:** [README.md:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/README.md#L1).

## Suggested work packages

The IDs describe work to retain, not separate agents to launch. The contract and example packages have landed; the verification items travel with the behavior they protect.

| Package | Lead | Scope |
| --- | --- | --- |
| User continuity | Astra scopes; Sol verifies and implements | #14 keyboard and accessibility journey |
| Agent authoring | Astra designs; Sol agents execute | #19 baseline before #20 guidance changes |
| Product boundary | Astra with Max’s real tasks | #23; run #22 when inline hosting is part of a selected task |

## Positioning research

VS Code contributes views within host-owned containers. Its guidance recommends restraint in view count and using custom webviews when the native surfaces cannot do the job. I infer a useful Leaf boundary: packages contribute content and guidance while the host owns collaboration and placement. [VS Code views](https://code.visualstudio.com/api/ux-guidelines/views), [VS Code webviews](https://code.visualstudio.com/api/ux-guidelines/webviews), [VS Code layout](https://code.visualstudio.com/docs/configure/custom-layout).

Herdr puts tabs and terminal panes inside project workspaces, with a persistent server owning processes. This supports investigating continuity and task identity; it does not establish that Leaf should own terminals or process lifetimes. [Herdr concepts](https://herdr.dev/docs/concepts/).

MCP Apps provides interactive HTML in a host iframe; A2UI describes a client-owned component catalog and declarative UI updates. My inference is that rendering flexibility alone is a weak distinction. Leaf should measure whether its authored content, anchored feedback, decisions and revisions improve the whole task. [MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview), [A2UI introduction](https://a2ui.org/introduction/what-is-a2ui/).

A movable splitter introduces keyboard, naming and value semantics beyond a static split. If repeated use later demands resizing, treat it as an interaction feature with those obligations. The W3C pattern itself notes that its example review is unfinished. [W3C window splitter pattern](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/).

## Boundaries and existing work

Already owned elsewhere: [real website agents, PR #460](https://github.com/max-sixty/leaf/pull/460), [navigation status, PR #461](https://github.com/max-sixty/leaf/pull/461), [screenshot caption controls, PR #464](https://github.com/max-sixty/leaf/pull/464), and the separately dispatched example-comment pickup investigation. Those are dependencies, not new backlog items.

Equal splits, whole-workspace fallback and native header/footer slots remain deliberate first-slice choices. Resizable splits, docking, saved layout presets and a separate layout registry are not missing acceptance work. Revisit them only when a completed task demonstrates the need.

## Browser evidence

Isolated previews used installed Chrome on macOS. At 1100×520, notification furniture
consumed about 190px below the banner and left a 165px controls body for 432px of
content. The review queue repeated eight worklist entries in a three-row, 122px tab
strip. Both examples hid their overlay scrollbars at rest despite remaining content.
These observations motivated the example and overflow items, which have landed; they
never established frequency across users or cross-browser compatibility.
