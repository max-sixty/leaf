# External UI skills

These optional reviews come from outside Leaf. The skills are installed separately,
so check the harness's available skills before invoking one.

- [Impeccable](https://github.com/pbakaus/impeccable#installation):
  `/impeccable critique` for hierarchy, grouping and clarity, `audit` for technical UI
  quality, and focused workflows such as `layout` and `typeset`.
- [Web Design Guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines):
  `/web-design-guidelines` for interface conventions, accessibility, navigation, forms
  and motion.
- [Frontend Design](https://github.com/anthropics/skills/tree/main/skills/frontend-design):
  `/frontend-design` for new compositions or an intentional redesign.
- [Emil Kowalski's skills](https://github.com/emilkowalski/skills): `review-animations`
  for motion, which refuses model invocation, so read its `SKILL.md` and
  `STANDARDS.md`; `/break-ui` for worst-case content, keeping the demo-data toggle it
  adds out of a shipped page.
- [Mblode UI skills](https://github.com/mblode/agent-skills): `/ui-animation` for
  motion and interruption, `/ui-design` Audit for visual quality and Break for extreme
  content, `/ui-verification` for browser reproduction, and `/product-design` for
  action scope, recovery and consistency across input routes.
- [Gridlines](https://github.com/pritamux/gridlines): `/gridlines` for alignment. Its
  probe finds the edges each container's items share and lists each item 2px or more
  off its container's edge. As published it skips every `aria-hidden` element, which
  covers every Leaf icon, and measures an icon by its box rather than its glyph
  ([pritamux/gridlines#1](https://github.com/pritamux/gridlines/issues/1)), so fix both
  in your copy first. Run it on a state by passing the probe, with a loop over the
  containers to check, to `uv run leaf-dev probe --state NAME --js`, and append its
  guides to `.lf-chrome` or the open dialog, since guides on the body paint under
  both. Most of what it lists on Leaf is ragged text or a centred column, so confirm
  each miss in a crop before fixing it.
- [renderlint](https://github.com/ngocanhnckh/renderlint) for rendered defects at 13
  widths: clipped and overlapping text, controls of unequal height side by side,
  covered content and focus, small targets, and contrast read from pixels. Run it on the
  URL `uv run leaf-dev preview <example>` prints rather than on an export, which has no
  chrome and draws its widgets at one width:

  ```bash
  npx @yitec/renderlint "$URL" --no-crawl --no-scan --no-routes --dark
  ```

  `--dark` is needed because it doesn't detect a scheme set with `light-dark()`. A
  `states` config of Playwright steps reaches the panel, Threads or a dialog, without
  the width sweep. Most of what it lists on Leaf follows Leaf's own rules (text on the type
  scale's 10px to 11.5px steps, the floating panel standing over the page, a diff's
  line numbers as targets), so confirm each miss in a crop.

- [OpenDesigner's review probe](https://github.com/ckryptickunal/OpenDesigner/blob/main/skills/opendesigner-review/scripts/probe.js),
  for its inventories rather than its flags. Load its `probe.js` into a state through
  `uv run leaf-dev probe --state NAME --js` with its walk (`all()`) scoped to one chrome
  surface and its cap of 15 items a list raised, and read the text colours, font sizes,
  radii and spacings `probe()` lists, in both schemes, against
  `browser/styles/tokens.css`. A value no token gives, such as pure black or white
  text, is a miss to confirm in a crop.
- [UI SDK](https://github.com/vercel-labs/ui)'s `checkPattern`, for keyboard and ARIA
  structure. This journey checks each composite the page shows, such as tabs, trees,
  toolbars and radio groups, against its WAI-ARIA Authoring Practices pattern;
  `--state NAME` in place of the example opens a surface such as the command reference
  first:

  ```bash
  uv run leaf-dev probe <example> --journey .claude/skills/developing-leaf/scripts/check_patterns.py
  ```

  It needs the network, and it reports some problems that aren't there
  (`notes/dependency-candidates.md`, "UI SDK"), so press the keys yourself before
  fixing one.
