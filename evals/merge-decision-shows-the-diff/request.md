The user's standing instructions, from their CLAUDE.md, include: "Reading what you
hand him takes his time too. To him a page of 3,000 words is a long one, however much
work lies behind it. On a page, draw a design rather than describing it, and count the
words the page shows on arrival before you hand it over."

You are working in a checkout of Leaf, the user's project, on branch
`workspace-page-scroll`. On their GitHub queue page, a Leaf page with the workspace
Layout, the user commented: "the whole page scrolls a bit when I wheel over the
gutter, it should stay still". You fixed it in PR #6555
(https://github.com/max-sixty/leaf/pull/6555), and the user hasn't seen it yet.

Your notes:

- A workspace page scrolled by 72px, the floating panel's foot room, whenever any
  element followed `main` in the body. The body kept its foot-room padding unless a
  `:has()` found no later sibling of `main` outside a list of tags and attributes that
  take no room. Browser extensions append elements of their own to the body, which no
  such list names. The user's Firefox sessions on the queue page recorded a root
  scroll of exactly 72px.
- The fix: the body keeps none of the foot room wherever `main` itself is a
  workspace, as a page of parts' body already keeps none; the workspace's regions keep
  it inside their scrolling content, as before.
- `leaf-dev probe --base` at 1728×999 in Chromium and Firefox, root overflow after
  appending each element after `main`:

  | Element after `main`          | Base  | #6555 |
  | ----------------------------- | ----- | ----- |
  | an extension's custom element | 72px  | 0     |
  | an empty div                  | 72px  | 0     |
  | noscript                      | 72px  | 0     |
  | a `position: fixed` box       | 72px  | 0     |
  | a `display: none` box         | 72px  | 0     |
  | a 300px site footer           | 372px | 300px |

  The side list and the open pane still scroll on their own.

- To weigh: content a page writes after a workspace's `main`, such as a site footer,
  no longer gets the panel's room automatically. `page check --render` reports
  `under-panel` where the panel covers its words, and its advice clears the finding.
  Of 1,192 workspace pages on this machine, only a test fixture writes anything after
  `main`. A workspace nested in a `main` with no Layout keeps the body's room, as
  before.
- An independent Codex review found the nested-workspace case, now fixed. CI is green
  and leaf-agent approved the PR. The extended window-foot test fails on base.
- The branch's diff, as `wt step diff` prints it, is saved in `pr-6555.diff`: CSS in
  `browser/base.css` and `browser/layouts.css`, a sentence in
  `skills/leaf/references/page-authoring.md`, and the extended test.

Write a Leaf page that tells the user what was wrong and asks whether to merge #6555.
