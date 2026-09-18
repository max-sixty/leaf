# Dependency survey, 2026-09-16

What Leaf could hand to a dependency or a browser feature, and why the rest stays. The
chosen candidates are scored in `TODO.md` under "Platform and dependency cutover"; this
note keeps what that section leaves out: the evidence, the rejected candidates, and the
two Leaf choices still open. A rejected row is one line and its deciding number, so that
asking again costs a glance rather than a survey.

## Method

Four read-only passes: the defect history under `skills/leaf/assets` and `packages`
since the 2026-08-29 rename (442 commits, about 175 classified as defect fixes, bodies
read for the ambiguous ones); the browser runtime module by module against library and
platform equivalents; the Python, tooling, and Worker code against libraries and the
standard library, first under Leaf's own constraints and then with every internal
constraint treated as negotiable; and an outside-in pass over what comparable products
(OpenAI Apps SDK, MCP Apps, Claude Code artifacts, Vercel AI SDK and v0, A2UI,
json-render, Hypothesis, Liveblocks) and the web-component libraries use. Fixed points:
Leaf is a generative UI library for agents, installs as a Claude Code and Codex plugin,
runs in Chrome 125+, and hosts on Cloudflare. Library adoption by mature projects is a
weight in the ranking, not a filter.

## What the defect record says

| Bucket (approx. fixes) | A Radix-style primitive set would have prevented |
|---|---|
| Focus and keyboard (38) | ~5; the rest is the vim-style command layer |
| Scroll, geometry, layout races (30) | ~3; the rest is page-shell timing |
| Margin and anchor placement (22) | 0 to 2; Floating UI landed 09-09 and three placement fixes followed |
| Visual and theme (~14 defects, ~45 design iterations) | none of the defects |
| State and render sync (17) | none; the Lit cutover is the answer |
| Overlay stacking and positioning (15) | ~8 |
| Widget-specific (19), other (20) | none |

So shadcn (React, Radix or Base UI, Tailwind) would have covered 15 to 20 of the fixes.
The 2026-08-30 cutover of chrome onto native `<dialog>` and popover (`335bf9a6`) was
followed by 12 to 15 overlay, focus, and Escape fixes in two weeks: assembling platform
primitives by hand is the same risk class as hand-rolled code, which is what a maintained
library removes. Agents write plain HTML with an id per block plus 67 `lf-*` tags, the
same camp as Claude Code artifacts and Google's generative UI; no benchmark compares
React and shadcn against HTML or a JSON page spec, so the authoring format is not a
reason to change frameworks.

## Rejected

| Area | Candidate | Why not |
|---|---|---|
| Anchoring | Hypothesis `dom-anchor-text-quote`, `approx-string-match` | Fuzzy; would replace ~150 lines of exact search |
| Anchoring | Resolving a typed quote through the rendered page instead of `passages.py` | Spiked `3132c9af`: anchors matched, but Python grew 168 lines, because the refusals and diagnostics read authored source, and a quoted `leaf comment` went from 0.2 s to 1.3 s and now needs Chrome |
| Keyboard parsing | tinykeys, hotkeys-js | The key normaliser is 15 lines; the rest is domain |
| Command palette | cmdk | React only |
| Composer | CodeMirror, ProseMirror, Lexical, Tiptap | The composer is a textarea |
| Markdown | markdown-it, micromark, DOMPurify | marked is vendored and escapes HTML itself |
| Live updates | reconnecting-eventsource | ~40 lines; the silence timer is Leaf's |
| Tokens | Open Props | 33 root tokens already |
| Styling | Tailwind | Needs a build and brings a look; only with a React chrome |
| Icons | lucide | 25 inline icons, 69 lines |
| Content widgets | Web Awesome or Spectrum tabs and boards | Different child vocabulary; under 400 lines each |
| Data widgets | TanStack Table, Virtual, Form | No widget sorts, filters, or virtualizes |
| Scroll settle | `scrollend` only | `keyboard/hints.js` documents a case that never fires it |
| Positioning | Floating UI for the CSS-anchored menus | Tried: +80 lines of JS and async placement for what 10 CSS lines do synchronously |
| Focus | tabbable for the covering surface's Tab wrap | Tried: a vendored startup module in place of a 7-line local filter |
| Motion | `@starting-style` for the thread card and agent-arrival listeners | It replays whenever an ancestor leaves `display: none`, so the reopened panel needs the end listener anyway; the pulse is not an entrance |
| Motion | Same-document View Transitions for `runtime/motion.js` | The update runs after the old state is captured, later than the gesture's turn, and a board card moves inside a scroller whose clip a snapshot escapes under the Chrome 125 floor |
| Version patch | idiomorph in place of `runtime/dom-children.js` | A live-tree diff reverts what the runtime built into the page — highlight spans, controller-owned widget children, lent tab stops — which a source-to-source diff never sees. `patchTree`'s nine domain callbacks survive any swap, leaving ~175 lines of diff loop |
| Version patch | Deleting the patch path so every revision arrives by reload | 600 to 900 lines, but a reload cannot claim the reader still stands on a control: caret, selection, focus and open disclosures go, and the page is away a measured median 595 ms |
| Storage | A page-local `objects/sha256/<digest>` store in place of a resource copy per revision | Disk only: 2 objects and 38 KB per save after the first in place of 189 files and 3.28 MB, about 930 MB down to 190 MB across the local state home, with no effect on save time (0.22 s against 0.19 s). A stamped version keeps its exact bytes either way, and the store is more mechanism than the directory of bytes it replaces. Revisit if disk is what hurts |
| Typecheck | `tsc --checkJs` over the runtime | A bug-back over six runtime fixes (#404, #448, #625, #660, #676, #757) found no error the fix removed; the 272 remaining errors are inference artifacts |
| Keyboard | TanStack Hotkeys (alpha), `@github/hotkey`, tinykeys | They own key parsing, which has had no fix since 2026-08-29; the scope stack, Escape order, and go-to grammar stay in Leaf either way |
| Focus walks | `focusgroup`, Tabster | `focusgroup` is Chrome 150 with no WebKit, so the published site would carry the 19 KB polyfill; Tabster's Groupper returns focus to a group rather than closing a surface and restoring the reader's place |
| History | Navigation API for version travel | Three `history` and `popstate` sites; the gain needs intercept to replace the activation choreography |
| Server | One user-level daemon on SQLite, starlette, and asyncio | The transport went to starlette and uvicorn in #774; what stays rejected is one daemon for every page. Measured ~750 gross and -300 to +500 net, and a user-level database stops the page directory being the deployment unit |
| Server | The server rewritten in TypeScript | Not incremental; forfeits the pytest suite and render harness, and node is not guaranteed on Codex hosts |
| Chrome library | Web Awesome, Spectrum, Lion, Zag | The churn is not in the ~500 lines of `<dialog>` and popover glue they would own: 12 commits there since the rename against 88 across the margin, the keyboard and the trays. Zag's menu also pulls in `@floating-ui/dom`, rejected above. Worth reaching for where the platform has no primitive — a combobox, a typeahead — not as a retrofit |
| Chrome framework | React, Radix, Base UI, shadcn, Preact + htm | A framework migration for the smallest defect bucket |
| Build | Vite, Rollup | One entry, no dev server; esbuild suffices |
| HTML parsing | lxml, selectolax, BeautifulSoup, html5lib | Lose source offsets and browser-parity recovery |
| Events | pydantic or msgspec for event shapes | Shapes are jsonschema; semantics are code |
| Events | an event-sourcing library | None fits a CLI-appendable file |
| Locks | filelock | Wrong lock semantics |
| Supervision | supervisor-style libraries | The reaper is the session semantics |
| File watching | watchfiles for the server | Presence is pids and locks; the one file loop re-stats the log at 70 µs a look |
| JS parsing | esprima, acorn | esprima is unmaintained and acorn needs node; tree-sitter parses authored `page/` modules in Python |
| Codex | official `openai-codex` SDK | Spawns its own CLI; cannot join a running conversation |
| Templating | jinja2 | No templating exists |
| Export | premailer-class inliners | Different job |
| Tests | pytest-playwright | Replaces 38 lines; the harness needs more |
| Worker | Hono | Manifest-driven roots do not fit its router |
| Site | static-site generators | Pages are Leaf page directories |
| Vendoring | `package.json` and one esbuild config for `vendor.py` | ~150 of 655 lines; the language-subset logic stays |
| Authoring format | JSON page catalogs (A2UI, json-render) | Not compared |

## Leaf choices worth reconsidering

Two are still open.

- **Leaf joins the conversation the user has open in Codex.** Excludes the official SDK,
  which starts its own Codex and bundles a 113 to 138 MB binary per platform. Is the
  shared conversation a product requirement? If not, 758 lines of hand-written protocol
  go. The website host in `worker/server.py` already spawns its own app-server, so
  adopting the SDK there alone would run two clients for one protocol.
- **Package authors describe widgets in JSON Schema.** 474 lines of meta-schema check
  those descriptions; typed declarations (pydantic arrives through `mcp`) when packages
  are next revisited.

The rest are decided. Comments match text exactly or detach, and agents write HTML: both
stay. The keyboard stays vim-like, and the layer inference behind ten of its 24 fixes went
in #780, which gave the keyboard an explicit layer stack. The margin's cluster layout is an arm of the region-aware
annotation placement item. Every revision keeps its own copy of the layer, and sharing
those copies by digest is in Rejected above with what it would have saved.

One incidental finding: the locked turbohtml build ships no macOS x86_64 wheel, so an
Intel Mac install compiles it from source.
