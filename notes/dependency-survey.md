# Dependency survey, 2026-09-16

What Leaf could hand to a dependency or a browser feature, and why the rest stays. The
chosen candidates are scored in `TODO.md` under "Platform and dependency cutover"; this
note keeps what that section leaves out: the evidence, the candidates considered and not
added, and the Leaf choices worth reconsidering. Delete it once those are decided.

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

## Considered and not added

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
| Chrome library | Web Awesome, Spectrum, Lion, Zag | Not chosen over the platform-first direction; still open |
| Chrome framework | React, Radix, Base UI, shadcn, Preact + htm | A framework migration for the smallest defect bucket |
| Build | Vite, Rollup | One entry, no dev server; esbuild suffices |
| HTML parsing | lxml, selectolax, BeautifulSoup, html5lib | Lose source offsets and browser-parity recovery |
| Events | pydantic or msgspec for event shapes | Shapes are jsonschema; semantics are code |
| Events | an event-sourcing library | None fits a CLI-appendable file |
| Locks | filelock | Wrong lock semantics; the daemon item removes the locks |
| Supervision | supervisor-style libraries | The reaper is the session semantics |
| File watching | watchfiles for the server | Presence is pids and locks, not files |
| JS parsing | esprima, acorn | Pre-ES2020; needs node; per-revision copies are the reason it exists |
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
- **The keyboard system is vim-like.** Letter chords, per-area scopes, an Escape that
  unwinds one level; 6,100 lines and the largest fix bucket. Proposal: prototype in a
  playground page a flatter model of global shortcuts from a settled library, a command
  palette listing every action, and native Tab and arrow movement; estimated 3 to 4k
  lines deleted if it wins.
- **Comments float in the margin in clusters, and the reply box sits inside the page.**
  6,600 lines and the second-largest bucket. Proposal: add a stacked side-column layout
  with the reply box in the panel as one arm of the "Now" item on annotation placement.
- **The page body is the scroll container.** Behind 30 scroll and layout fixes, and every
  library assumes the normal setup. Now a row in the TODO tables (spike it).
- **Every revision keeps its own copy of the runtime.** 3.2 MB per revision plus the
  import-path rewriting that tree-sitter exists for. The stated purpose is that an old
  revision renders after a plugin update replaces the install. Open question: do old
  revisions need their own runtime, or only their HTML rendered by the current one? If
  the latter, serve from the install and delete the copies and the parser; if the former,
  the "share by digest" item under Later keeps the guarantee.
- **Leaf joins the conversation the user has open in Codex.** Excludes the official SDK,
  which starts its own Codex (and bundles a 113 to 138 MB binary per platform). Open
  question: is the shared conversation a product requirement? If not, 758 lines of
  hand-written protocol code go.
- **Package authors describe widgets in JSON Schema.** 474 lines of meta-schema check
  those descriptions. Proposal: typed declarations (pydantic is installed through `mcp`)
  when packages are next revisited.
- **Agents write HTML.** The JSON-description alternative was not compared. Proposal:
  keep HTML; the evidence favours it.

One incidental finding: the locked turbohtml build ships no macOS x86_64 wheel, so an
Intel Mac install compiles it from source.
