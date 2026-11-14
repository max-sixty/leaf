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
