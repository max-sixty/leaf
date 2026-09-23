# Dependency survey

The September 2026 survey compared Leaf's browser runtime, Python services, tooling,
and authoring model with established libraries and browser primitives. Active
implementation candidates live in `TODO.md`; completed cutovers and rejected
alternatives live in git history.

## Result

Leaf uses dependencies where they own one complete, established mechanism. Lit renders
components; TurboHTML parses HTML; jsdiff aligns text; unidiff parses patches; Starlette
and uvicorn serve pages; psutil reads processes; watchfiles watches development previews;
dependency-cruiser checks imports; Floating UI places response surfaces; and Web Awesome
supplies ordinary form controls. Where a dependency replaced a mechanism, the old path
was deleted rather than retained as a compatibility path.

The remaining large modules mostly implement Leaf's product model: page and event
lifecycle, exact anchors, live revision activation, the keyboard grammar, margin
projection, and delivery into the user's existing agent task. Libraries can supply the
mechanics those systems use, but replacing the systems would change the product rather
than simplify its implementation.

The standing architectural choices are:

- Agents author semantic HTML and registered Leaf elements.
- Comments match rendered text exactly or detach.
- A page directory remains the durable record and deployment unit.
- Live revisions preserve user focus, selection, drafts, disclosures, and position.
- Leaf accompanies the user's existing Codex task through App Server.
- Package declarations remain the shared JSON Schema vocabulary read by Python,
  JavaScript, package authors, and generated documentation.
- Leaf's keyboard scopes, layer ordering, and focus restoration remain domain behavior;
  native elements and component libraries own only their local interaction mechanics.

## Platform cutovers

Three candidates remain conditional:

- **CSS cascade layers:** an earlier trial put Leaf's sheets in layers while page styles
  remained unlayered. Unlayered rules then outranked every Leaf layer and moved 53 chrome
  boxes. Establish an isolation boundary between page styles and chrome before trying
  layers again.
- **Invoker commands:** `command` and `commandfor` can replace imperative dialog and
  popover invocation once Leaf's Chromium floor is at least 135. They do not replace
  Leaf's layer stack, semantic state, or focus-restoration rules.
- **MCP page ports:** replace `/p/<capability>` multiplexing only after a host proves that
  wildcard-port `frame_domains` admit the per-page server model.
