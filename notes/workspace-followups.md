# Leaf next-work backlog

Research at merged commit `cb7915bb`, 8 September 2026. Research briefs for the workspace section of [TODO.md](../TODO.md#workspace-follow-ups).

I recommend keeping the current primitives and spending the next cycle on reliable shared contracts, convincing examples and a measured authoring advantage. The larger layout vocabulary should follow evidence from those tasks.

Start #2, #3 and #4 as one coordinated contract batch; run the example simplifications #6 and #8 alongside it. Begin the authoring baseline #19 before improving the recipes. Follow with #9 and #17 so the examples complete useful work, then compare Threads placement in #12.

Items are ranked within each group. IDs are stable references, not a global priority score. Agent-owned work is distinguished from the repeated-use pilot, which needs Max’s purpose and participation. Evidence labels separate reproduced defects from code gaps and experiments.

## Close the shared-contract gaps

<a id="item-2"></a>

- **#2** **Make arrangement admission one transaction** — Admit a single live arrangement before changing its DOM, so failed registration cannot leave a half-arranged widget.

  **Evidence / confidence:** Browser reproduced. A duplicate region ID throws after the helper has moved authored children and added generated classes. Separately, two arrangements for the same owner/content can leave the DOM reporting flow while the effective reading posture reports bounded.

  **Next task:** Define ownership and validation once, then construct and commit the arrangement. Cover cancellation, cleanup and re-registration through that lifecycle; avoid rollback patches around each mutation.

  **Done when:** Rejected admission leaves children, order, classes and registries unchanged. One owner has one effective posture. Disconnect/reconnect and pending completion do not retain conflicting owners.

  **Owner / dependencies:** Sol; Astra reviews lifecycle contract. Independent first-wave fix; settle the API before #21.

  **Sources:** [reading-layout.js:26](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/reading-layout.js#L26), [reading-regions.js:166](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/reading-regions.js#L166).

<a id="item-3"></a>

- **#3** **Check text honesty in dark mode** — Run the scheme-sensitive text check in both color schemes.

  **Evidence / confidence:** Browser reproduced. A custom preserving widget replaces its authored prose only in dark mode; render_version returns no findings. The honesty check runs inside the light-only branch.

  **Next task:** Move scheme-dependent reading checks to the per-scheme path. Keep checks whose meaning is independent of the scheme at their existing single owner.

  **Done when:** The dark-only dishonest widget produces a dark finding; honest nested widgets pass in both schemes without duplicated unrelated diagnostics.

  **Owner / dependencies:** Sol. Small first-wave fix; coordinate file ownership with #1 and #5.

  **Sources:** [readings.py:77](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/scripts/leaf/render_gate/readings.py#L77).

<a id="item-4"></a>

- **#4** **Size custom workspace roots by their declared role** — Remove the remaining default-tag dependency from root workspace sizing.

  **Evidence / confidence:** Browser reproduced. A valid lf-studio using the public workspace arrangement helper reports bounded at 1200×900, but main stays 768px wide and the root only about 123px tall. Root sizing rules still select lf-workspace literally.

  **Next task:** Use the canonical arrangement/root markers in shared sizing CSS. Preserve the rule that only the sole page root fills the available viewport.

  **Done when:** A differently named package root receives the same available width/height as the default root; embedded instances stay contained and flow remains reachable.

  **Owner / dependencies:** Sol. Independent first-wave fix; does not require the fit-policy experiment #21.

  **Sources:** [theme.css:84](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/theme.css#L84), [packages.md:202](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/packages.md#L202).

<a id="item-1"></a>

- **#1** **Check anonymous preserving widgets** — Extend the text-preservation check to widgets without an authored ID, retaining the existing compositional contract.

  **Evidence / confidence:** Known checker gap. The checker filters preserving owners by el.id. A TODO explicitly leaves anonymous owners unchecked, while the registry permits them. This is the existing follow-up #1.

  **Next task:** Carry pre-upgrade source identity into the checker for anonymous owners and frozen replies. Reuse provenance captured for nested ownership; requiring every widget to acquire an ID would narrow the authoring model.

  **Done when:** Changing anonymous owner prose fails; legitimate generated descendant text passes; multiple anonymous instances stay distinct through revision and frozen reply rendering.

  **Owner / dependencies:** Sol; Astra reviews source identity. Coordinate with #3 and #5 because they change the same checking boundary.

  **Sources:** [words.js:39](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/scripts/leaf/render-checks/words.js#L39), [schema.py:454](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/scripts/leaf/schema.py#L454).

<a id="item-5"></a>

- **#5** **Check projected prose after actions and reports** — Replace whole-owner exemptions with the narrower changes that the projected state actually permits.

  **Evidence / confidence:** Code-confirmed exemption; runtime consequence unmeasured. The render gate collects every action/report owner into a touched set and omits those owners from verbatim checking. This is broader than checking only rewritten or retired content; a dishonest post-action wrapper has not yet been reproduced.

  **Next task:** First demonstrate unrelated owner prose escaping after a real action. Then derive allowed text changes from canonical projected rewrites/retirement rather than treating any action as permission to rewrite the whole owner.

  **Done when:** A legitimate draft rewrite passes; unrelated owner prose mutation fails after an action; a child action does not exempt its parent. If reproduction disproves the concern, close it with that evidence.

  **Owner / dependencies:** Astra defines projection boundary; Sol implements. Coordinate with #1 and #3; design review before changing projection semantics.

  **Sources:** [scheme.py:176](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/scripts/leaf/render_gate/scheme.py#L176), [words.js:46](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/scripts/leaf/render-checks/words.js#L46).

## Make the examples worth using

<a id="item-6"></a>

- **#6** **Compact the notification example** — Consolidate the title, explanation and question so the actual controls and preview have useful height.

  **Evidence / confidence:** Measured in browser. At 1100×520, the title/lede, Ask heading and frame consume about 190px below the banner before the playground begins. Its controls and preview bodies are only 165px high.

  **Next task:** Simplify the example’s heading and prose hierarchy, retain one clear title and Ask meaning, and remove redundant spacing in the surrounding frame and notification card. Compare a second bounded Ask before changing package-wide styling.

  **Done when:** Recover at least one control row at 1100×520, with no overlap and a coherent authored-order document at 540px wide. The deployment notification itself should look intentional in both viewports.

  **Owner / dependencies:** Sol. Good independent first-wave UI task; #7 touches the package composition separately.

  **Sources:** [notification-playground.html:19](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L19), [notification-playground.html:48](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L48).

<a id="item-7"></a>

- **#7** **Keep playground presets within reach** — Try placing the compact preset controls in the controls pane’s header, outside its scrolling body.

  **Evidence / confidence:** Measured in browser. At 1100×520 the controls body is 165px high for 432px of content. Reaching Tone, Accent and Heading scrolls both presets out of view.

  **Next task:** Move the preset group through the existing pane furniture mechanism, then check the cost of the fixed group at short heights. If that leaves too little controls space, simplify the preset presentation before adding another layout policy.

  **Done when:** Presets remain reachable while controls scroll, without adding a scrollbar or reducing the body below a useful control row. Flow, copy and print preserve the intended reading order.

  **Owner / dependencies:** Sol. Evaluate together with the simpler example #6; use shared arrangement registration.

  **Sources:** [lf-playground.js:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/playground/widgets/lf-playground.js#L1), [notification-playground.html:60](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L60).

<a id="item-8"></a>

- **#8** **Give the review queue one navigator** — Remove the repeated worklist and tab-strip selection surfaces while preserving independent queue and detail reading.

  **Evidence / confidence:** Measured in browser; composition decision remains. Every item is named in the left list and again in the right tab strip. The strip consumes 122px in three rows at 1100×520; clicking a worklist item focuses its duplicate tab.

  **Next task:** Start with a native worklist whose links reveal ordinary detail sections in the adjacent scrolling pane. If showing only one detail is necessary, establish that need before extending the existing tabs/view-state owner. Board moves and option decisions must not stand in for browsing.

  **Done when:** Each item has one navigation control; keyboard/fragment/comment reveal reaches its detail without resetting the worklist. Narrow flow stays understandable. Browsing emits no durable decision action.

  **Owner / dependencies:** Sol prototypes; Astra reviews if a new primitive is needed. Do before #9; extract a reusable master/detail widget only if this simpler composition fails a real task.

  **Sources:** [review-queue.html:26](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L26), [review-queue.html:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L78), [lf-tabs.js:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-tabs.js#L1).

<a id="item-9"></a>

- **#9** **Make the queue’s blockers answerable** — Turn the stated cache and billing blockers into real decisions and show the revision that incorporates the answers.

  **Evidence / confidence:** Browser and source confirmed. The footer says the review closes when cache rollback and billing sample are resolved, but the details contain no decision widget. Current interaction is navigation and disclosure.

  **Next task:** Use existing Ask/options semantics at the two blockers and add a companion revision through the established fixture/event-log flow. Replace passive footer prose with compact actual status where useful.

  **Done when:** Both decisions are keyboard-answerable; unanswered choices appear in the Ask projection; accepted decisions survive the next revision and the queue visibly closes or explains what remains.

  **Owner / dependencies:** Sol. After #8; no bespoke queue state machine.

  **Sources:** [review-queue.html:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L78), [review-queue.html:209](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/review-queue.html#L209), [registry.json:152](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/registry.json#L152).

## Keep the reader oriented

<a id="item-10"></a>

- **#10** **Make pane overflow discoverable** — Test a subtle continuation cue for bounded panes with more content below the visible edge.

  **Evidence / confidence:** Observed usability problem; proposed cue needs comparison. In both short-height examples, content ends exactly at the pane/footer edge while macOS overlay scrollbars are invisible at rest. The screenshots do not expose whether more content remains.

  **Next task:** Compare the current view with a shared overflow-edge cue. Prefer the smallest producer of remaining-scroll state; use the same behavior for public and compound panes.

  **Done when:** The cue appears only with remaining overflow, clears at the bottom and in flow/copy/print, and does not cover text or controls. Retain it only if the paired example is easier to read.

  **Owner / dependencies:** Sol prototypes; Astra reviews the shared behavior. After #6–#8 reduce avoidable crowding; this should signal real overflow rather than conceal poor composition.

  **Sources:** [reading-regions.js:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/reading-regions.js#L1), [theme.css:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/theme.css#L1).

<a id="item-11"></a>

- **#11** **Let newer navigation win over revision restoration** — Use navigation intent to prevent an old reading capture from overwriting input made during revision activation.

  **Evidence / confidence:** One-frame race reproduced; human timing unmeasured. In a real browser, scrolling the new pane to 700 one animation frame after replacement was restored to 340. The same intervention two frames later stayed at 700. The probe injected a wheel event; a human-scale window under a slow real widget still needs demonstration.

  **Next task:** Build a deterministic delayed real-widget journey and extend the existing navigation-intent ownership rule to revision restore if the conflict remains reachable.

  **Done when:** A newer scroll/reveal/focus wins while a revision settles; an untouched revision still restores its semantic landmark. Hidden-tab restoration must preserve the active tab, which passed the current probe.

  **Owner / dependencies:** Astra sets lifecycle rule; Sol implements. Focused lifecycle work, separate from visual polish.

  **Sources:** [version.js:1254](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1254), [version.js:1479](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1479), [version.js:1505](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/version.js#L1505).

<a id="item-12"></a>

- **#12** **Compare Threads overlay with Keep beside** — Try overlay as the quick-access default, with an explicit Keep beside choice for sustained conversation.

  **Evidence / confidence:** Acknowledged product experiment. Threads currently uses a 420px panel and covers at widths at or below 840px. Beside mode reduces the workspace allocation and can cause it to switch to flow. The original implementation deliberately retained this behavior pending a focused experiment.

  **Next task:** Compare current adaptive placement against overlay plus Keep beside on the queue and configuration examples. Follow a comment in the rightmost pane and return to the work.

  **Done when:** Both the conversation and its referenced content stay reachable; subject, draft and reading landmarks survive opening/closing. Decide the default from the complete task, including the cost of content obscured by overlay.

  **Owner / dependencies:** Astra leads; Sol builds comparison. Use #6 and #8 after composition cleanup; coordinate geometry with PR #461. No general docking system is required.

  **Sources:** [chrome-layout.js:62](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/chrome-layout.js#L62), [chrome-layout.js:94](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/chrome-layout.js#L94).

<a id="item-13"></a>

- **#13** **Automate long local-comment journeys** — Protect draft and focus continuity when a long composer meets a short pane, a tall footer and a posture change.

  **Evidence / confidence:** Regression-coverage gap. The previous review manually exercised a 20-line composer successfully. The new automated pane journey primarily covers the long read-only thread preview; the composed editing sequence remains unprotected.

  **Next task:** Add one real journey selecting near a pane’s foot, growing a multiline draft, changing bounded/flow posture, and reopening it. Reuse existing events and composer behavior.

  **Done when:** All draft text and actions stay reachable, sibling panes stay still, and draft text plus intended focus survive the transitions.

  **Owner / dependencies:** Sol. Independent regression task; incorporate fixes only if this journey finds one.

  **Sources:** [surface.js:116](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/composing/surface.js#L116), [test_render_navigation.py:205](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/tests/test_render_navigation.py#L205).

<a id="item-14"></a>

- **#14** **Verify the complete keyboard and accessibility route** — Exercise the workspace as one keyboard task, including reading, pane furniture, local comments and Threads.

  **Evidence / confidence:** Composition verification task. The suite has reading-region keyboard tests and menu/accessibility coverage. Those components do not by themselves prove the composed split-plus-Threads journey, especially when content is covered.

  **Next task:** Use a named two-pane example with header/footer controls; walk landmarks and controls, use reading keys, open Threads, return through Escape, then change posture. Check focus against actual modal/nonmodal behavior.

  **Done when:** Every action is reachable with a comprehensible accessible name and visible focus. Covered content does not leave the reader lost. Avoid imposing a modal focus trap on a nonmodal panel.

  **Owner / dependencies:** Sol. Run against both candidates in #12 if that experiment is active.

  **Sources:** [lf-pane.js:29](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-pane.js#L29), [test_render_navigation.py:106](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/tests/test_render_navigation.py#L106), [panel.js:75](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/conversation/panel.js#L75).

<a id="item-15"></a>

- **#15** **Name the region in ambiguous page-map entries** — Test whether the compact page map can distinguish identical subjects in different panes.

  **Evidence / confidence:** Code-confirmed omission; usability reproduction first. Pane entries intentionally lack a global scroll percentage. The marker naming path does not add the region label, leaving a plausible ambiguity when two panes have the same heading.

  **Next task:** Build duplicate subjects in named panes, inspect visual and spoken map entries, and add the nearest useful region label only if needed. Keep regional orientation rather than inventing a page-wide percentage.

  **Done when:** The reader can distinguish and reveal either subject without guessing or resetting the other pane; unique entries do not acquire redundant labels.

  **Owner / dependencies:** Sol. Coordinate with navigation presentation in PR #461; this is a separate naming case, not that PR’s work.

  **Sources:** [living-margin.js:1764](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/living-margin.js#L1764), [living-margin.js:2811](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/assets/runtime/living-margin.js#L2811).

## Prove complete work

<a id="item-16"></a>

- **#16** **Prove a current-versus-proposed comparison** — Show two real alternatives simultaneously and let the reader discuss each before committing one choice.

  **Evidence / confidence:** Missing acceptance example. The notification example contains a single simulated preview. It does not yet prove the original current/alternative comparison case that motivated flexible layouts.

  **Next task:** Build a bounded comparison with truthful baseline and candidate content, one configuration/decision owner, and independently anchored comments. Reuse existing panes and comparison vocabulary where their behavior fits.

  **Done when:** A reader can compare the same state in both alternatives, comment on either, choose once, and inspect the choice after a revision. Flow/export expose both alternatives clearly.

  **Owner / dependencies:** Sol; Astra evaluates the composition. After #6; distinct from PR #464, which handles clicking screenshot captions.

  **Sources:** [notification-playground.html:60](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L60), [registry.json:418](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/registry.json#L418).

<a id="item-17"></a>

- **#17** **Complete a real configure-to-agent-to-revision loop** — Make a committed playground configuration produce an inspectable local artifact, then refine it through an anchored comment.

  **Evidence / confidence:** Current example is explicitly simulated. The current example previews a fictional notification and produces a descriptive instruction. It demonstrates interaction and one commit, but not useful work completed by the agent.

  **Next task:** Use a local output file as the real result. Carry the committed configuration through the existing host delivery and receipt loop, revise the page with the result, then apply a reader comment. Preserve uncommitted exploration separately.

  **Done when:** The output matches the submitted configuration/version; the reader sees pickup and completion; a follow-on comment changes the intended result and survives the next revision.

  **Owner / dependencies:** Sol implements; Astra judges the complete task. Reuse existing delivery; do not build another runner. The hosted demonstration can use PR #460 when it lands.

  **Sources:** [notification-playground.html:135](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/notification-playground.html#L135), [README.md:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/README.md#L1).

<a id="item-18"></a>

- **#18** **Try an exception-driven monitoring workspace** — Use the existing live-progress example to test a stable overview beside changing evidence and an exception that needs a decision.

  **Evidence / confidence:** Unproven original use case. The shipped live-progress page is a document of metrics, roster and tabs. It supplies a real contrast to configuration and review, but has not demonstrated this bounded monitoring workflow.

  **Next task:** Feed typed data through the existing data/event boundary, keep a readable log/evidence pane, and expose one exception through an existing decision widget.

  **Done when:** Updates do not steal the reader’s position, completed decisions stay completed, and the reader can find and resolve the exception without manually inspecting every log line.

  **Owner / dependencies:** Sol builds a bounded experiment; Astra evaluates. Reuse current primitives. If the task demands long-lived process ownership, record that as a product boundary rather than adding a process manager.

  **Sources:** [live-progress.html:18](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/live-progress.html#L18), [live-progress.html:41](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/examples/live-progress.html#L41).

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

  **Owner / dependencies:** Sol drafts; Astra reviews the public model. After #8, #17 and #19. This extends packages; it does not create a named-layout registry.

  **Sources:** [page-authoring.md:78](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/page-authoring.md#L78), [packages.md:202](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/packages.md#L202).

<a id="item-21"></a>

- **#21** **Test whether custom roots need shared fitting policy** — Use one genuinely different package root to decide whether responsive fit ownership belongs in the shared API.

  **Evidence / confidence:** Architecture experiment. The public arrangement API is reusable, but recursive minimum-size calculation and fit observation live in the default workspace widget. A second root can register regions yet may need to duplicate that policy.

  **Next task:** Build the second root through public APIs after the concrete fixes. If useful behavior requires copying the default root’s fit algorithm, extract that single policy; otherwise document the narrower default-root composition.

  **Done when:** Two concrete compositions either share one fit owner or demonstrate why only the default root needs it. No new breakpoint matrix or general layout framework is introduced.

  **Owner / dependencies:** Astra sets boundary; Sol builds second real root. After #2 and #4. Gate extraction on actual duplicated need.

  **Sources:** [lf-workspace.js:60](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-workspace.js#L60), [lf-workspace.js:132](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/packages/default/widgets/lf-workspace.js#L132), [packages.md:212](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/skills/leaf/references/packages.md#L212).

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

  **Owner / dependencies:** Max chooses real work; Astra studies usage. Max’s participation and choice of real work are required; #17 supplies a useful starting workflow.

  **Sources:** [README.md:1](https://github.com/max-sixty/leaf/blob/cb7915bb924aa78fcbcf83439110794982bb3b86/README.md#L1).

## Suggested work packages

The IDs describe work to retain, not separate agents to launch. Start the contract and example packages first; the verification items travel with the behavior they protect.

| Package | Lead | Scope |
| --- | --- | --- |
| Arrangement contracts | Sol; Astra reviews ownership | #2 and #4, then the bounded experiment #21 |
| Passage honesty | One Sol owner; Astra reviews projection | #3, #1 and #5 share the checker; land separate verified fixes |
| Example composition | Sol | #6 and #7 together; #8 followed by #9 |
| Reader continuity | Astra scopes; Sol verifies and implements | #11 and #12 are separate changes; attach #13 and #14 as acceptance journeys. Evaluate #10 and #15 on those same examples |
| Complete workflows | Sol; Astra evaluates task outcome | #16 and #17, then #18 if the monitoring contrast is useful |
| Agent authoring | Astra designs; Sol agents execute | #19 baseline before #20 guidance changes |
| Product boundary | Astra with Max’s real tasks | #23; run #22 when inline hosting is part of a selected task |

## Reproduction record

The scratch probes used the repository's real browser/render harness. Their observed
results are recorded in the corresponding briefs: failed admission changed DOM,
duplicate arrangements disagreed about posture, dark-only prose replacement produced
no render-gate finding, and a custom root retained narrow/intrinsic geometry. The
revision probe injected a wheel event one animation frame after replacement; its
human-scale reachability remains unproven. Recreate each case as a failing regression
in its owning suite before implementing the fix.

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
These observations motivate the example and overflow items; they do not establish
frequency across users or cross-browser compatibility.
