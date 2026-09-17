# Dependency survey, 2026-09-16

What Leaf could hand to a dependency or a browser feature, and why the rest stays. The
chosen candidates are scored in `TODO.md` under "Platform and dependency cutover"; this
note keeps what that section leaves out: the evidence, the rejected candidates, and the
Leaf choices worth reconsidering. Delete it once those are decided.

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
| Scroll settle | `scrollend` only | `keyboard/go-to-sequence.js` documents a case that never fires it |
| Positioning | Floating UI for the CSS-anchored menus | Tried: +80 lines of JS and async placement for what 10 CSS lines do synchronously |
| Focus | tabbable for the covering surface's Tab wrap | Tried: a vendored startup module in place of a 7-line local filter |
| Motion | `@starting-style` for the thread card and agent-arrival listeners | It replays whenever an ancestor leaves `display: none`, so the reopened panel needs the end listener anyway; the pulse is not an entrance |
| Motion | Same-document View Transitions for the folds, trays, board moves, and column carry in `runtime/motion.js` | The update runs after the old state is captured, later than the gesture's turn; pointer input misses the page while it animates; a fold collapses height so later content slides, which a root cross-fade does not draw; board cards move inside their own scroller, whose clip a snapshot escapes under the Chrome 125 floor. #666 removed the paint-boundary transition version travel used |
| Version patch | idiomorph with exclusion callbacks in place of `runtime/dom-children.js` | A live-tree diff keeps only the reader state an exclusion names; the source-to-source patch keeps all of it and has needed no fix since #514 split it out |
| Typecheck | `tsc --checkJs` over the runtime | It runs in under a second, but a bug-back over six runtime fixes (#404, #448, #625, #660, #676, #757) found no error the fix removed; the 272 errors outside vendored bundles are inference artifacts, and the typed `scripts/browser` core arrives through a bundle with no declarations |
| Keyboard | TanStack Hotkeys (alpha), `@github/hotkey`, tinykeys | They own key parsing, which has had no fix since 2026-08-29; the scope stack, Escape order, and go-to grammar stay in Leaf either way |
| Focus walks | `focusgroup`, Tabster | `focusgroup` is Chrome 150 with no WebKit, so the published site would carry the 19 KB polyfill; Tabster's Groupper returns focus to a group rather than closing a surface and restoring the reader's place |
| History | Navigation API for version travel | Three `history` and `popstate` sites; the gain needs intercept to replace the activation choreography |
| Server | One user-level daemon on SQLite, starlette, and asyncio | Measured about 750 gross and -300 to +500 net: the browser already receives pushes over `EventSource`, the 70 µs stat loop serves CLI writers in other processes, pid probing and the wait, adapter, and delivery locks stay, Windows is not a goal, and a user-level database stops the page directory being the deployment unit |
| Server | The server rewritten in TypeScript | Not incremental; forfeits the pytest suite and render harness, and node is not guaranteed on Codex hosts |
| Chrome library | Web Awesome, Spectrum, Lion, Zag | Not chosen over the platform-first direction; still open |
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

Each excluded a library or a simpler model. The proposal is what to do if the choice is
reopened.

- **Comments match text exactly or detach.** Excludes tolerant re-anchoring. Saves no
  complexity (the exact search is ~150 lines); a UX question about fewer detached
  comments. Proposal: leave it.
- **The keyboard system is vim-like.** Letter chords, per-area scopes, go-to hints, and
  an Escape that closes one layer; 6,085 lines and the largest fix bucket. The reader
  keeps this behaviour, and no library owns the scope stack, the Escape order, or the
  go-to grammar; the ones that came closest are in Rejected above. Ten of the 24 keyboard
  fixes since 2026-08-29 landed in the code that infers the open layers: `stack()` in
  `keyboard/dispatch.js`, `keyboard/return-stack.js`, and `native-layers.js`. Proposal:
  an explicit layer stack that openers push and closes pop, so Escape closes the top
  layer and bindings come from it; about 600 to 900 lines deleted est. First step: fold
  `native-layers.js` into the return stack and drop the popover and modal branches of
  `stack()`.
- **Comments float in the margin in clusters, and the reply box sits inside the page.**
  6,600 lines and the second-largest bucket. Proposal: add a stacked side-column layout
  with the reply box in the panel as one arm of the "Now" item on annotation placement.
- **Every revision keeps its own copy of the layer.** Two versions of a new page measured
  about 3.27 MB in 189 files each, with all 187 resource digests identical, beside a
  3.24 MB page-level copy. The copy arrived with #666 so that activating a revision reads
  no mutable file, and it lets `page init` skip checking old revisions' HTML against a new
  layer. tree-sitter stays either way: it reads authored `page/` modules and builds
  interactive exports. Open question: must a stamped version keep the exact JS, CSS, and
  look it was approved with? If so, the "share by digest" item under Later keeps that at
  one stored copy per digest. If not, serve one page-level layer and have `page init`
  refuse a layer that an old revision's HTML cannot render under.
- **Leaf joins the conversation the user has open in Codex.** Excludes the official SDK,
  which starts its own Codex (and bundles a 113 to 138 MB binary per platform). Open
  question: is the shared conversation a product requirement? If not, 758 lines of
  hand-written protocol code go. The website host in `worker/server.py` already spawns
  its own app-server, so the SDK's limit does not reach it; adopting the SDK there alone
  would run two clients for one protocol beside `codex.py`.
- **Package authors describe widgets in JSON Schema.** 474 lines of meta-schema check
  those descriptions. Proposal: typed declarations (pydantic is installed through `mcp`)
  when packages are next revisited.
- **Agents write HTML.** The JSON-description alternative was not compared. Proposal:
  keep HTML; the evidence favours it.

One incidental finding: the locked turbohtml build ships no macOS x86_64 wheel, so an
Intel Mac install compiles it from source.
