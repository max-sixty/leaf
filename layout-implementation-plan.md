# Leaf layout primitives: implementation plan

Status: approved for implementation on 2026-09-08. Implementation starts from `51ddc7e3` on `codex/workspace-primitives`.

## Outcome

An agent can compose a bounded workspace from a small structural widget family, using the same packages, semantic widgets, comments, actions, and revisions as a document. A document needs no new boilerplate. The implementation must support a configuration playground, queue with detail, and nested comparison without a separate layout engine for each.

The first feature includes the collaboration behavior that makes these useful. A layout that renders correctly but loses a comment, moves the wrong scroller, resets a draft, or hides a footer is unfinished.

## Public contract

Ship the structural family in the default package. Packages remain the distribution unit and can supply compositions, themes, compound widgets, and guidance. There is no new layout manifest or package category.

| Widget | Meaning | Initial surface |
| --- | --- | --- |
| `lf-workspace` | A bounded task surface with optional header/footer | Stable `id`; native direct header/footer; content body |
| `lf-pane` | A named reading and interaction region | Stable `id`, required `label`; native direct header/footer; ordinary prose/widgets in its body |
| `lf-split` | Divide an allocation between two regions | Stable `id`; `direction="columns\|rows"`; two pane/split children |

Only the outer workspace establishes viewport sizing. A split divides its parent's allocation, and a pane gives its body what remains after its header and footer. A footer is a slot containing existing action widgets, not a new action type or an independently managed panel.

Use equal split proportions initially. Package theme CSS may tune a composition through the structural family's documented sizing tokens; do not add a ratio parser, dragging, docking, or a persisted split-size model for this first feature. If equal proportions make an acceptance example unusable, add one authored sizing axis to the shared split contract before handoff, not a per-example positioning patch.

Only direct native `header` and `footer` children are slots, at most one each, in that order around the body. Headers nested inside an article remain article content. Pane bodies may contain multiple ordinary blocks. A split has exactly two region children and no loose prose; additional content belongs inside a pane. A workspace may contain a semantic compound owner such as the playground; it is not restricted to a direct split if that would split the widget's state ownership.

The target authoring syntax is:

```html
<main>
  <lf-workspace id="review-workspace">
    <header><h1>Review the proposed change</h1></header>
    <lf-split id="review-regions" direction="columns">
      <lf-pane id="queue" label="Items">
        <nav>…links to stable detail subjects…</nav>
      </lf-pane>
      <lf-pane id="detail" label="Selected item">
        …existing prose and widgets…
        <footer>…existing decision widget…</footer>
      </lf-pane>
    </lf-split>
  </lf-workspace>
</main>
```

### Declaration and validation

Introduce one registry declaration identifying structural behavior (`x-layout` with workspace, pane, or split kinds), with its definition under the existing `$keys` documentation. Generic consumers inspect that declaration, never a list of tag names. This is a widget capability, not a new installable primitive category.

Keep these widgets under the existing prose content model and add the role-derived structure checks at the shared instance-validation boundary. The current `x-parent` and `x-children` contracts cannot express this grammar: `x-parent` would overconstrain legal nesting, while `x-children` only describes required enum-indexed widget children. Do not widen those unrelated contracts or add three widget-specific Python validators.

Validation covers slot cardinality/order, split arity and child roles, required identities/labels, and malformed attributes. Both authored revisions and frozen message markup use the same checks. Include a package-defined differently named structural widget in a contract test to establish that support follows the declaration rather than built-in names.

The exact `x-layout` spelling can be refined once in the foundation assignment; its roles, ownership, and generic consumers are the frozen contract before parallel implementation starts.

## Layout, containment, and media

Preserve the single `body > main` authored boundary. The viewport behavior applies only when the workspace is the sole authored content root directly inside that `main`. Put the page title inside its header. Do not infer global mode from a descendant `:has(lf-workspace)` anywhere in the document.

The same workspace embedded in a corpus tab, an ordinary document, another pane, or frozen message content remains contained. Without an explicitly bounded parent it uses intrinsic document flow; it never claims the global viewport. This lets the corpus and quoted content use the same vocabulary without exceptions in their builders.

The root allocation comes from Leaf's shell, after its banner, shortcut controls, and any beside-panel reservations. One owner exposes that allocation; packages do not independently subtract panel widths. Avoid a viewport workspace plus a second root scrollbar caused by the document's existing padding and chrome spacers.

Use CSS Grid/Flexbox for the actual layout. Keep rendered pane content in light DOM. Preserve existing authored nodes and IDs when wrapping a scrolling body; do not clone content for another arrangement.

Use one compact fallback: when the bounded arrangement cannot fit its shared minimums, flatten it into authored-order document flow. Header/body/footer retain order and all content remains reachable. Do not automatically turn panes into another tabs interface. The minimum-size policy belongs to the structural family, with CSS tokens and computed measurements where needed; start without per-package breakpoint programs. Width, short windows, zoomed text, and a tall footer all belong in this check. The same fit reading must determine posture throughout the runtime; avoid a layout/measurement loop in which switching posture changes its own threshold.

In standalone copies and print, always expose content in authored-order flow: no viewport heights, hidden pane overflow, fixed footers, or dead layout controls. Use the existing `html.lf-copy`/print paths. Do not add tag-name exceptions to generic export or exempt pane contents from overflow checks.

## One reading-region mechanism

Add a small runtime owner (proposed `runtime/reading-regions.js`) exposed through `widget-api.js`. The region's stable identity, host element, and content body are its inputs. Its narrow capabilities are registration/cleanup, lookup from a node, enumeration for continuity, visible bounds through the existing geometry helpers, and a shared reading of the currently effective scroller and layout posture.

Stable region identity is not the same as an active scrollport. In bounded mode the pane body is its reading scroller. In flow mode it inherits the containing active region, normally the document for a root workspace but potentially an outer pane or Threads for embedded content. Consumers must not infer this independently from overflow CSS. Publish posture transitions through the existing layout invalidation path so capture occurs before a transition and restoration after settled geometry. Hidden regions retain saved readings without capturing empty geometry. Disconnection unregisters live DOM bindings; a replacement with the same identity can reclaim its stored reading.

Freeze allocation propagation alongside region registration. One shared arrangement entry point receives an owner, its content/body slots, and its pane/split arrangement; it exposes the effective allocation and posture to readers. Both public layout widgets and a compound semantic owner call it. A compound owner between a workspace and generated regions receives the same bounded allocation; direct ancestry of the public custom-element tags must not be the only supported path. The foundation proves this with a tiny compound-owner fixture before layout and navigation agents work independently.

A compound widget may register its internally generated Controls and Preview regions under stable identities derived from its owning widget. It uses the same arrangement and region helpers as the public widgets, not a second implementation. Internal names are stable local keys qualified by the semantic owner; they must not collide with authored or chrome regions.

Distinguish two operations:

- Reading keys select the region containing the current focus. Focus in a pane header/footer still identifies that pane's body as its reading area.
- Revealing a target scrolls only actual ancestors of that target. Revealing a footer must not scroll a body that does not contain it.

The document remains the default reading region. Bring the Threads list onto this contract in place of the current document-versus-chrome shortcut. Ordinary overflow inside a code block or board is not automatically a new reading region; existing nested-scroll reveal still handles it.

Reuse `lf-reveal`, disclosure opening, composed-tree lookup, `shownBand`/clipping, captured light-DOM scroll events, `layoutChanged`, and the existing keyboard register. Do not create a second focus manager or new page-level key scheme.

### Continuity and state

Extend the existing version transition to capture a semantic landmark and fallback offset for each identified authored reading region, plus its existing focus identity. Capture only content visible within that region's clipped bounds; hidden tabs retain saved state rather than replacing it with a meaningless measurement.

Restore in this order: authored root and widget upgrades; existing tab selections and widget working values; final shell/region geometry; surviving landmarks; focus with `preventScroll`; final anchor paint. Where a focused subject is deliberately removed, fall back to its surviving region. An explicit navigation request wins over restoration.

On bounded-to-flow transitions retain the bounded region readings, and preserve the active semantic subject in the document. Returning to bounded mode restores the inactive panes while keeping the current subject in its owning region. Do not write the flow document's offset into every inactive pane's saved position.

Region working position is browser-tab view state through existing storage, not an event or new file authority. Playground values remain playground state; drafts use the existing draft machinery. This feature does not promise to preserve arbitrary third-party form state whose widget never supplies a persistence contract.

## Comments, Asks, and Leaf controls

Local comments must work in every pane. Reuse the canonical conversation renderer and widget-owned outlets. Target marks and local conversation placement must track the relevant scroller, clip at pane boundaries, and avoid the pane's header/footer. Navigating from Threads or Asks must reveal the required tab/disclosure and scroll the correct region without moving unrelated panes.

A workspace has no meaningful single percentage-down-the-document for independent panes. Use the existing compact map and locally docked contributions, with placement bounded to their owning region. Do not create a rail per pane. Authored document sidebars/sidenotes inside a constrained pane fall into their in-flow form. The full Threads/Asks indexes stay runtime-owned and canonical.

Retain today's adaptive beside/covering Threads policy for this feature. Ensure its opening, resizing, and covering behavior coordinates with the root allocation and never leaves a footer or keyboard destination inaccessible. The proposed overlay-by-default plus explicit Keep-beside interaction is a subsequent product change; do not make it an incidental consequence of the pane implementation.

## Examples and acceptance evidence

Use the smallest corpus that exercises different requirements. A synthetic gallery specimen supplies awkward combinations; it does not replace working examples.

| Case | Proof required |
| --- | --- |
| Existing document review | Native root scrolling, local comments, Ask travel, and revision continuity remain usable without pane markup. |
| Notification/configuration playground | Persistent Controls and Preview plus a task action footer; one typed working-value set, one commit; local changes survive reflow and a content revision. |
| Queue with detail | Left-side item navigation and independently scrolling detail using existing links/tabs/content widgets; following an item reveals its subject without resetting the list. No new generic selection framework. |
| Recursive gallery specimen | Columns with a rows split in one child; inactive tabs, disclosure, internal code/board overflow, footer, and projected-datum comment; native header inside an article is not stolen as a pane slot. |
| Contained and frozen use | The specimen under a corpus tab and a fragment admitted through the real reply door; neither changes the outer page's viewport mode. |
| Copy and print | Export after scrolling and editing, reopen at another width, and expose content below every previous fold with the chosen configuration intact. |

For the playground, preserve its existing direct-child authoring grammar. Its module already collects controls, presets, preview, and output before moving them into generated wrappers. Replace its arrangement mechanism with the shared one at that point; keep one value owner and existing projection/action semantics. Both embedded and root-workspace uses must use that path.

Source the notification demonstration from its original artifact if available; otherwise author an honest example using the shipped playground vocabulary. Simulated receipt states are clearly examples, not a fork of Leaf's actual receipt renderer. Use `lf-tabs`/ordinary anchor navigation for queue detail where they fit; the purpose is exercising the layout, not building a second queue product.

Extend existing owning tests. Assertions must establish actual pane overflow/independent positions before asserting correct movement. Inspect the real event log for unchanged working-state semantics and exactly one committed configuration. Use real keyboard gestures for focus/rings. Include the rightmost preview while Threads is open, reduced-motion behavior through existing helpers, dark/light rendering, a narrow window, and a short window. Cover these as journeys, not a combinatorial set of screenshot snapshots.

## Scope decisions during implementation

When an acceptance case exposes a structural problem, consider reducing scope before adding exceptions, fallback paths, or per-example patches. Stop and escalate a consequential tradeoff to the user with the observed failure and the smallest coherent scope reduction. Preserve local comments and the ordinary document contract.

## Sol assignments and dependency order

The primary agent owns integration and final acceptance. Use `gpt-5.6-sol` explicitly for implementation agents, with bounded context and this plan. Revalidate file locations against the implementation base before dispatch.

**A — Foundation, one Sol agent.** Registry declaration and family schemas; shared boundary validation; region registration/lookup API and lifecycle; effective-scroller/posture transitions; allocation propagation through a semantic owner and the shared arrangement entry point; documentation of the public seam; focused contract tests. Agree the exact DOM/registration/allocation shape with the primary before B starts. Owning files include `schema.py`, `registry/widgets.py`, `validation/instances.py`, both registry layers, `reading-regions.js`, and its public reexport. Establish cleanup and minimal exercised document/registered-region/compound-owner cases, not stubs that callers invent independently. A need not implement polished layout, but its effective-scroller transition must actually run in a bounded/flow fixture.

**B — Two Sol agents in parallel after A.**

- Layout owner: structural widget modules, shared arrangement helpers, theme and shell sizing, direct slots, compact/copy/print behavior, and corresponding layout/render-gate tests. Own `chrome.css`/`chrome-layout.js` changes for available area. It must honor the frozen region API and send any necessary seam change to the primary before modifying it.
- Navigation owner: region-aware reading keys, anchor/Ask travel, version/focus continuity, local comments and compact map geometry, with tests in the existing navigation/anchor/margin owners. Own `navigation.js`, `anchors.js`, `version.js`, `asks/view.js`, and relevant local-conversation/margin changes. Consume A's frozen region/allocation/posture API while the layout owner implements its full presentation.

Keep shared entry points and broad test files assigned to one writer at a time. The primary applies small reexport/boot edits or coordinates ownership transfers. Agents add behavior tests with their work; tests are not deferred to the end.

**C — Integration, one Sol agent after B.** Playground cutover, worked example(s), gallery specimen, export/contained-message journeys, package/authoring guidance, corpus generation, and running previews. This agent owns `test_render_widgets.py` while integrating, after layout contributions there have completed. Other tests stay beside their owning behavior. The primary runs the combined gate and resolves cross-boundary failures with the owning agents.

**D — Review and correction.** The primary reviews the complete diff, and an independent reviewer examines the public contract, declaration-driven integration, and state/continuity guarantees. A separate browser-use pass exercises the three actual work patterns and local comments. Return defects to their owners, rerun affected checks, and re-review the changed boundary. Do not settle for three independently green components.

## Code seams established by investigation

Paths below are relative to the Leaf checkout; verify them on the implementation base.

| Concern | Existing owner and constraint |
| --- | --- |
| Widget grammar | `scripts/leaf/schema.py`, `registry/widgets.py`, `validation/instances.py` beneath `skills/leaf`; existing child schemas are not optional slot schemas. |
| Shell | `assets/runtime/chrome-layout.js`, `chrome.css`, and `assets/theme.css`; document width, margin claims, and top/bottom reservations are currently coordinated here. |
| Travel | `runtime/navigation.js`, `anchors.js`, `asks/view.js`; several paths still choose only document or Threads. |
| Continuity | `runtime/version.js`; capture and restore currently model one page reading position. |
| Local comments | `runtime/living-margin.js`, `margin-layout.js`, `conversation/surfaces.js`, `geometry.js`; reuse canonical rendering and clipping. |
| Compound owner | `packages/playground/widgets/lf-playground.js` and its registry/theme; direct-child grammar and one value map. |
| Browser gate | `scripts/leaf/render-checks/layout.js` and `render_gate/`; use a pane's true bounds, never skip its subtree. |
| Export | `render-checks/standalone.js` and family CSS; reset live geometry through copy/print presentation. |
| Corpus | `scripts/corpus.py` embeds main content under tabs and currently extracts literal `<main>`; keep that authored boundary rather than adding a mode attribute there. |

## Integration gates and handoff

Implementation starts from refreshed main at `51ddc7e3`, including startup, bundling, and UI changes since the planning investigation. Recheck the identified seams before editing; do not reintroduce removed receipt or visual behavior from the planning base.

Run focused boundary tests during each assignment. Before final handoff run the complete owning browser files and the everyday suite:

```sh
uv run pytest tests
```

Also run the project's pre-commit checks and regenerate `examples/corpus.html` and its data through `scripts/corpus.py`. Re-vendor the page layer before inspecting a browser result. The new main includes published runtime bundling; read the current owning generator and rebuild affected committed outputs rather than editing bundles. Run the complete browser gate on the worked examples and use the UI-sweep workflow for local comments, placement, clipping, crowding, and keyboard access. Run the website-worker gates only if implementation touches that boundary.

Hand over running previews of the current code, the acceptance results, and the reviewed diff. Publishing catalog images, pushing, merging, deploying, and refreshing installations are separate authorized actions; local generation and validation come first. The catalog refresh command pushes immediately, so do not run it as if it were a local screenshot command.

The feature is complete only when the examples work through the same primitives and the ordinary document remains simpler to author. New layout names, package-specific navigation, or schema exceptions needed to make an example pass are reasons to revise the shared contract before handoff.
