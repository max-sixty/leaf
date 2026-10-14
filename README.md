# leaf

[![maintained with tend](https://img.shields.io/badge/maintained_with-tend-bba580?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMCwxNikgc2NhbGUoMC4wMTI1LC0wLjAxMjUpIiBmaWxsPSIjZmZmIiBzdHJva2U9Im5vbmUiPjxwYXRoIGQ9Ik02ODAgMTEyOCBjNjIgLTk2IDY5IC0xNzggMjAgLTI0MSAtMTcgLTIyIC0yMCAtNDAgLTIwIC0xMzQgbDEgLTEwOCAyMSAyOCBjMTEgMTYgMzAgNDcgNDIgNzAgMTIgMjIgMzIgNDkgNDYgNTkgMzcgMjcgMTE0IDM4IDE4NCAyNyA5MyAtMTUgOTQgLTE4IDQ0IC03OSAtNzIgLTg4IC0xMDkgLTExMyAtMTc2IC0xMTcgLTMxIC0yIC02NCAxIC03MiA2IC0yMyAxNSAyMSA1NiAxMDcgOTggNDAgMjAgNzEgMzggNjkgNDAgLTYgNyAtODggLTE3IC0xMjYgLTM3IC00OSAtMjUgLTEwMCAtNzggLTEyMSAtMTI1IC0xNSAtMzMgLTE5IC02NiAtMTkgLTE4OCAwIC0xNTcgOCAtMTk1IDUwIC0yMzIgMTcgLTE2IDM2IC0yMCA4NSAtMTkgNjIgMSA2MyAxIDczIC0zMiA5IC0zMiA5IC0zMyAtMjIgLTQwIC01MCAtMTIgLTEzMiAtNyAtMTY0IDEwIC00MCAyMSAtNzkgNjkgLTkyIDExNCAtNSAyMCAtMTAgMTAyIC0xMCAxODIgMCA4MCAtNSAxNjIgLTExIDE4NCAtMjIgNzkgLTEzNSAxNjYgLTIzNCAxODEgLTM3IDYgLTM1IDMgMzAgLTI4IDc4IC0zOSAxNDQgLTkxIDEzMiAtMTA0IC01IC00IC0zNyAtOCAtNzEgLTggLTc3IDAgLTExNyAyNCAtMTgyIDEwOSAtNTIgNjggLTUxIDcwIDQyIDg1IDcxIDExIDE0MyAwIDE4MyAtMjkgMTYgLTExIDQwIC00MyA1NCAtNzMgMTMgLTI5IDMyIC01OSA0MSAtNjYgMTQgLTEyIDE2IC03IDE2IDU4IDAgNTkgNCA3NyAyMyAxMDIgMTkgMjYgMjMgNDYgMjUgMTMwIDMgNjcgMCA5OSAtNyA5OSAtNyAwIC0xMSAtMjMgLTEyIC01NyAwIC0zMiAtNiAtNzYgLTEyIC05NyBsLTEyIC00MCAtMjcgMzIgYy0zNCA0MSAtNDMgOTYgLTI0IDE1MSAxNCA0MSA3NSAxNDEgODYgMTQxIDMgMCAyMSAtMjQgNDAgLTUyeiIvPjwvZz48L3N2Zz4K)](https://github.com/max-sixty/tend)

> **Experimental software; not ready for general use.**

Leaf is generative UI for Claude Code and Codex. Review a plan, make a decision,
or follow live work in a page you can comment on and change. The agent responds by
revising the page.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/max-sixty/leaf-assets/40dc7c4e2078357b89ec0b5f1be59f7a6235761d/demo/session-dark.png">
  <img alt="A Leaf page with an anchored comment, the agent's reply, and a revised plan" src="https://raw.githubusercontent.com/max-sixty/leaf-assets/40dc7c4e2078357b89ec0b5f1be59f7a6235761d/demo/session-light.png">
</picture>

<details>
<summary>Watch the comment-and-revision loop</summary>

![A Leaf page receiving a comment, revising the work, and preserving a moved card](https://raw.githubusercontent.com/max-sixty/leaf-assets/40dc7c4e2078357b89ec0b5f1be59f7a6235761d/demo/demo.gif)

</details>

[Try Leaf on the home page](https://leaf.page/), where a small demo agent responds in your
private copy, or [explore the examples](https://leaf.page/examples/).

## Install

You need [`uv`](https://docs.astral.sh/uv/),
[`jq`](https://jqlang.github.io/jq/download/) 1.6 or newer on `PATH`, and a
browser that can reach the machine the agent runs on. No Leaf account or
configuration is required.
Users and package authors never need to build Leaf or run a package manager;
custom widgets are ordinary browser JavaScript.

Claude Code:

```
/plugin marketplace add max-sixty/leaf
/plugin install leaf@leaf
```

Codex:

```
codex plugin marketplace add max-sixty/leaf
codex plugin add leaf@leaf
```

Pi (a highly experimental trial, which the rest of these docs don't cover yet):

```
pi install git:github.com/max-sixty/leaf
```

Then ask: “Use Leaf to write up the options for this change.” The explicit skill is
`/leaf [topic]` in Claude Code, `$leaf [topic]` in Codex, and
`/skill:leaf [topic]` in Pi; without a topic, it
presents the work already under discussion.
The result opens in a browser page; its comments return to the same agent task.

<details>
<summary>Browser and environment requirements</summary>

Known functional limitations and accepted visual differences in current browsers
are recorded in [Browser support gaps](notes/browser-support.md).

The first run syncs the plugin's uv environment through your configured package
index. Render checks use the executable named by
`LEAF_BROWSER_EXECUTABLE`, `CHROME_PATH`, or `CHROME_BIN`, then installed Google
Chrome, then the first `google-chrome`, `google-chrome-stable`, `chrome`,
`chromium`, or `chromium-browser` on `PATH`.

In Claude Code, a page messages its session when input arrives while nothing watches
it, as after a turn you interrupted. A session that bypasses permissions holds that message for
your approval unless Claude Code's `crossSessionInbound` setting is `"accept"`.

Leaf's "Watch pages with a hooks module" option, in `/config`, moves that watch into a
Claude Code hooks module, an early-access Claude Code feature, which goes on watching
after a turn you interrupt. A Claude Code that doesn't load hooks modules keeps the
default watch.

</details>

<details>
<summary>Agent sandboxes</summary>

Leaf's hooks run outside an agent's sandbox, but `leaf` commands run wherever the
agent's shell commands do. The sandboxes of Claude Code and Codex refuse those
commands what they need: writes to Leaf's state in `~/.local/state/leaf`, a port on
localhost for the page server, and a browser for render checks. On Linux, Claude
Code's sandbox also hides the session's process from them and ends the server when
the command returns. The agent can rerun each refused command outside the
sandbox, asking you first.

To have `leaf` commands run outside the sandbox without asking, add this to Claude
Code's settings, such as `~/.claude/settings.json`:

```json
{
  "sandbox": { "excludedCommands": ["leaf *"] },
  "permissions": { "allow": ["Bash(leaf *)"] }
}
```

For Codex, add a rules file, such as `~/.codex/rules/leaf.rules`, and restart Codex:

```
prefix_rule(pattern = ["leaf"], decision = "allow")
```

Either one runs `leaf` with your own access, as Leaf's hooks already run, while the
agent chooses its arguments, such as the directory `page init` writes to. Both
apply only where the whole command line is `leaf` commands, so one chained after
`cd` or piped into another program stays in the sandbox.

</details>

## Explore and extend

- [How it works](https://leaf.page/how-it-works/): comments, decisions, live
  revisions, and the widgets a page can use.
- [Examples](https://leaf.page/examples/): proposals, editable drafts, release
  workspaces, and code reviews.
- [Extending](https://leaf.page/extending/): choose between page-local changes,
  reusable packages, and Leaf's shared kernel. Your agent can build a widget a
  task needs and use it in later pages.
- [Public contracts](skills/leaf/SKILL.md): authoring, serving, and continuing a
  Leaf page.
