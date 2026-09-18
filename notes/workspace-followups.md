# Leaf next-work backlog

Research at merged commit `cb7915bb`, 8 September 2026. Research briefs for the workspace section of [TODO.md](../TODO.md#workspace-follow-ups).

I recommend keeping the current primitives and spending the next cycle on reliable shared contracts, convincing examples and a measured authoring advantage. The larger layout vocabulary should follow evidence from those tasks.

The shared-contract and example items this note opened with have landed; what remains is verification and the product questions the implementation cannot settle. Begin the authoring baseline #19 before improving the recipes, and run the reader-continuity items #11 and #14 against the examples they protect.

Items are ranked within each group. IDs are stable references, not a global priority score. Agent-owned work is distinguished from the repeated-use pilot, which needs Max’s purpose and participation. Evidence labels separate reproduced defects from code gaps and experiments.

## Keep the reader oriented

<a id="item-11"></a>

- **#11** **Let newer navigation win over revision restoration** — Use navigation intent to prevent an old reading capture from overwriting input made during revision activation.

  **Evidence / confidence:** One-frame race reproduced; human timing unmeasured. In a real browser, scrolling the new pane to 700 one animation frame after replacement was restored to 340. The same intervention two frames later stayed at 700. The probe injected a wheel event; a human-scale window under a slow real widget still needs demonstration.

  **Next task:** Build a deterministic delayed real-widget journey and extend the existing navigation-intent ownership rule to revision restore if the conflict remains reachable.

  **Done when:** A newer scroll/reveal/focus wins while a revision settles; an untouched revision still restores its semantic landmark. Hidden-tab restoration must preserve the active tab, which passed the current probe.

  **Owner / dependencies:** Astra sets lifecycle rule; Sol implements. Focused lifecycle work, separate from visual polish.

  **Sources:** [version.js:1254](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1254), [version.js:1479](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1479), [version.js:1505](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1505).

<a id="item-14"></a>

- **#14** **Verify the complete keyboard and accessibility route** — Exercise the workspace as one keyboard task, including reading, pane furniture, local comments and Threads.

  **Evidence / confidence:** Composition verification task. The visual-review journey now covers real Go-to controls and pane furniture, case-local comments, covering and nonmodal Threads, draft restoration, bounded/flow transitions, and shared reading keys. A general named two-pane journey still needs to walk authored landmarks plus header and footer controls together and verify every painted focus mark remains unobscured.

  **Next task:** Use a named two-pane example with header/footer controls; walk authored landmarks and controls, use reading keys, open Threads, return through Escape, then change posture. Check focus against actual modal/nonmodal behavior.

  **Done when:** Every action is reachable with a comprehensible accessible name and visible focus. Covered content does not leave the reader lost. Avoid imposing a modal focus trap on a nonmodal panel.

  **Owner / dependencies:** Sol. Run against the adaptive Threads placement [PR #520](https://github.com/max-sixty/leaf/pull/520) settled.

  **Sources:** [lf-pane.js:29](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-pane.js#L29), [test_render_navigation.py:106](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/tests/test_render_navigation.py#L106), [panel.js:75](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/conversation/panel.js#L75).

## Measure the product boundary

<a id="item-19"></a>

- **#19** **Measure what Leaf saves an authoring agent** — Run a small blind authoring comparison against plain HTML, including the cost of the subsequent feedback cycle.

  **Evidence / confidence:** Unanswered positioning question. This session established implementation correctness and found composition flaws. It did not measure whether widgets and package guidance make agents faster or their outputs more useful than arbitrary HTML.

  **Next task:** Give comparable agents document-review, configuration and queue/detail tasks with the same content and acceptance criteria. Compare usable output, time/tokens, custom CSS and repair iterations; then require a comment and revision on each result. Counterbalance task order.

  **Done when:** Produce the artifacts and an independently assessed task-level result, including failures. Use the findings to decide which guidance or primitive earns investment; avoid reducing quality to lines of code.

  **Owner / dependencies:** Astra designs comparison; Sol agents execute. Extend the [existing agent-usability evaluation plan](agent-usability-evals.md#first-executable-slice) with this baseline before further recipe polishing; repeat relevant cases after #20.

  **Sources:** [page-authoring.md:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/page-authoring.md#L78), [notification-playground.html:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L1), [review-queue.html:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L1).

<a id="item-20"></a>

- **#20** **Teach the few compositions that earn their place** — Put tested document, configuration and queue/detail recipes into the existing package guidance.

  **Evidence / confidence:** Guidance experiment after observed authoring failures. The current authoring reference explains the primitives and links examples. We have not tested whether an unfamiliar agent chooses the right shape, state owner or fallback order from that guidance.

  **Next task:** Use failures from #19 to write short compositional recipes with one state owner, meaningful pane labels, purposeful furniture and authored-order flow. Validate with an agent that has not seen this design discussion.

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

  **Next task:** Use configuration, review and monitoring on recurring work. Observe whether readers reopen the same page, need saved navigation/selection, or prefer a fresh artifact; compare the full feedback cycle with the tools they already use.

  **Done when:** A short record of actual returns, abandoned flows and completed tasks supports a decision about saved layouts, project navigation and the target user. My recommendation is to begin with task-scoped workspaces.

  **Owner / dependencies:** Max chooses real work; Astra studies usage. Max’s participation and choice of real work are required; the notification playground supplies a useful starting workflow.

  **Sources:** [README.md:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/README.md#L1).

## Suggested work packages

The IDs describe work to retain, not separate agents to launch. The contract and example packages have landed; the verification items travel with the behavior they protect.

| Package | Lead | Scope |
| --- | --- | --- |
| Reader continuity | Astra scopes; Sol verifies and implements | #11, with #14 as its acceptance journey |
| Agent authoring | Astra designs; Sol agents execute | #19 baseline before #20 guidance changes |
| Product boundary | Astra with Max’s real tasks | #23; run #22 when inline hosting is part of a selected task |

## Reproduction record

The scratch probes used the repository's real browser/render harness. Four of them —
failed admission changing DOM, duplicate arrangements disagreeing about posture,
dark-only prose replacement producing no render-gate finding, and a custom root
retaining narrow/intrinsic geometry — belonged to briefs that have since landed. The
revision probe behind #11 injected a wheel event one animation frame after
replacement; its human-scale reachability remains unproven. Recreate that case as a
failing regression in its owning suite before implementing the fix.

## Positioning research

VS Code contributes views within host-owned containers. Its guidance recommends restraint in view count and using custom webviews when the native surfaces cannot do the job. I infer a useful Leaf boundary: packages contribute content and guidance while the host owns collaboration and placement. [VS Code views](https://code.visualstudio.com/api/ux-guidelines/views), [VS Code webviews](https://code.visualstudio.com/api/ux-guidelines/webviews), [VS Code layout](https://code.visualstudio.com/docs/configure/custom-layout).

Herdr puts tabs and terminal panes inside project workspaces, with a persistent server owning processes. This supports investigating continuity and task identity; it does not establish that Leaf should own terminals or process lifetimes. [Herdr concepts](https://herdr.dev/docs/concepts/).

MCP Apps provides interactive HTML in a host iframe; A2UI describes a client-owned component catalog and declarative UI updates. My inference is that rendering flexibility alone is a weak distinction. Leaf should measure whether its authored content, anchored feedback, decisions and revisions improve the whole task. [MCP Apps overview](https://modelcontextprotocol.io/extensions/apps/overview), [A2UI introduction](https://a2ui.org/introduction/what-is-a2ui/).

A movable splitter introduces keyboard, naming and value semantics beyond a static split. If repeated use later demands resizing, treat it as an interaction feature with those obligations. The W3C pattern itself notes that its example review is unfinished. [W3C window splitter pattern](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/).

## Boundaries and existing work

Already owned elsewhere: [real website agents, PR #460](https://github.com/max-sixty/leaf/pull/460), [navigation status, PR #461](https://github.com/max-sixty/leaf/pull/461), [screenshot caption controls, PR #464](https://github.com/max-sixty/leaf/pull/464), and the separately dispatched example-comment pickup investigation. Those are dependencies, not new backlog items.

Equal splits, whole-workspace fallback and native header/footer slots remain deliberate first-slice choices. Resizable splits, docking, saved layout presets and a separate layout registry are not missing acceptance work. Revisit them only when a completed task demonstrates the need. The hidden-tab revision probe preserved the active tab, so it is not listed as a bug.

## Browser evidence

Isolated previews used installed Chrome on macOS. At 1100×520, notification furniture
consumed about 190px below the banner and left a 165px controls body for 432px of
content. The review queue repeated eight worklist entries in a three-row, 122px tab
strip. Both examples hid their overlay scrollbars at rest despite remaining content.
These observations motivated the example and overflow items, which have landed; they
never established frequency across users or cross-browser compatibility.
