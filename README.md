# leaf

[![maintained with tend](https://img.shields.io/badge/maintained_with-tend-bba580?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMCwxNikgc2NhbGUoMC4wMTI1LC0wLjAxMjUpIiBmaWxsPSIjZmZmIiBzdHJva2U9Im5vbmUiPjxwYXRoIGQ9Ik02ODAgMTEyOCBjNjIgLTk2IDY5IC0xNzggMjAgLTI0MSAtMTcgLTIyIC0yMCAtNDAgLTIwIC0xMzQgbDEgLTEwOCAyMSAyOCBjMTEgMTYgMzAgNDcgNDIgNzAgMTIgMjIgMzIgNDkgNDYgNTkgMzcgMjcgMTE0IDM4IDE4NCAyNyA5MyAtMTUgOTQgLTE4IDQ0IC03OSAtNzIgLTg4IC0xMDkgLTExMyAtMTc2IC0xMTcgLTMxIC0yIC02NCAxIC03MiA2IC0yMyAxNSAyMSA1NiAxMDcgOTggNDAgMjAgNzEgMzggNjkgNDAgLTYgNyAtODggLTE3IC0xMjYgLTM3IC00OSAtMjUgLTEwMCAtNzggLTEyMSAtMTI1IC0xNSAtMzMgLTE5IC02NiAtMTkgLTE4OCAwIC0xNTcgOCAtMTk1IDUwIC0yMzIgMTcgLTE2IDM2IC0yMCA4NSAtMTkgNjIgMSA2MyAxIDczIC0zMiA5IC0zMiA5IC0zMyAtMjIgLTQwIC01MCAtMTIgLTEzMiAtNyAtMTY0IDEwIC00MCAyMSAtNzkgNjkgLTkyIDExNCAtNSAyMCAtMTAgMTAyIC0xMCAxODIgMCA4MCAtNSAxNjIgLTExIDE4NCAtMjIgNzkgLTEzNSAxNjYgLTIzNCAxODEgLTM3IDYgLTM1IDMgMzAgLTI4IDc4IC0zOSAxNDQgLTkxIDEzMiAtMTA0IC01IC00IC0zNyAtOCAtNzEgLTggLTc3IDAgLTExNyAyNCAtMTgyIDEwOSAtNTIgNjggLTUxIDcwIDQyIDg1IDcxIDExIDE0MyAwIDE4MyAtMjkgMTYgLTExIDQwIC00MyA1NCAtNzMgMTMgLTI5IDMyIC01OSA0MSAtNjYgMTQgLTEyIDE2IC03IDE2IDU4IDAgNTkgNCA3NyAyMyAxMDIgMTkgMjYgMjMgNDYgMjUgMTMwIDMgNjcgMCA5OSAtNyA5OSAtNyAwIC0xMSAtMjMgLTEyIC01NyAwIC0zMiAtNiAtNzYgLTEyIC05NyBsLTEyIC00MCAtMjcgMzIgYy0zNCA0MSAtNDMgOTYgLTI0IDE1MSAxNCA0MSA3NSAxNDEgODYgMTQxIDMgMCAyMSAtMjQgNDAgLTUyeiIvPjwvZz48L3N2Zz4K)](https://github.com/max-sixty/tend)

> **Not ready for general use.** Watch this space, and hopefully there'll be more to
> say soon.

Generative UI for agents: the agent builds you the page rather than a scroll of
terminal text — a plan whose options you press to decide, a triage board you drag, a
dashboard that keeps up while a long job runs. When the project needs a widget that
doesn't exist, the agent writes one, and the same theme and checks cover it.

Underneath is a messaging and collaboration bus. Select any line and comment on it
like a shared doc, or drag a card, or rewrite a draft in your own words: it all
reaches the session as structured events, and the agent answers in the margin and
updates the page. You can also answer with one press: `ok` `no` `lost` `cut` `more`.
Every valid save becomes a live revision; meaningful checkpoints become immutable
stamped versions. The browser follows along on its own. Leaf is a plugin —
Claude Code and Codex so far.

![leaf demo](docs/demo.gif)

<https://leaf.page/> is the tour, the mechanism, the example pages, and the guide to
themes and project widgets. Each page uses leaf's own theme, so they double as
specimens, and each opens the same from a checkout ([`docs/`](docs/)) as from the web.

## Install

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

### Experimental Codex MCP App

The Codex plugin registers one bundled local MCP server. On builds that render
[MCP Apps](https://github.com/modelcontextprotocol/ext-apps), the agent can attach
the complete Leaf interface directly to the task: comments, package widgets,
version travel, and the ordinary event path all run unchanged. One ephemeral
loopback origin serves every page opened by that MCP process under a separate
random capability path. It writes no service state and disappears with the MCP
session; the page directory and `comments.jsonl` remain the durable record.

The embedded route is experimental and local-host-only. A comments-only authored
snapshot remains available as an explicit fallback, and builds that do not render
the app use the normal full browser page. In every case the detached Codex adapter,
not an MCP host message, carries durable feedback into the next task turn.

No config or account is required. It needs
[`uv`](https://docs.astral.sh/uv/) and
[`jq`](https://jqlang.github.io/jq/download/) 1.6 or newer on `PATH` (the plugin is a
uv project, and the first run syncs its environment through whatever index you have
already configured), plus a browser on the same machine as the session. Render checks
and export launch Google Chrome by default; on a host that has another Chromium
instead, set `LEAF_BROWSER_EXECUTABLE` to that executable's path and both use it.

Then ask the agent for a page. The explicit skill is `/leaf [topic]` in Claude Code
and `$leaf [topic]` in Codex; with no argument it presents whatever the session is
currently about.

To expose the same resources from a checkout to another local MCP Apps host, run:

```sh
bin/leaf mcp
```

The model-visible `leaf_present` tool takes an initialized page's absolute
directory. `leaf_present_snapshot` selects the smaller fallback explicitly.

## Packages

A package carries a reusable theme, widget, browser module, data contract, or role
guide. Leaf's own content widgets use this contract. The
[package tutorial](docs/packages.html) builds a small one; the
[package reference](skills/leaf/references/packages.md) owns the complete
contract.

## Examples

[`examples/`](examples/) holds a complete page for each kind of work, including a
dashboard meant to change as work finishes. They are live in the visual index at
<https://leaf.page/examples.html>; every example opens as its own complete page.
From a checkout, `scripts/site.py --serve` previews that catalog and all its routes;
`scripts/preview.py triage-board` serves one page with the real agent loop behind it.
