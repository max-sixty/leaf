# leaf

> **Not ready for general use.** Watch this space, and hopefully there'll be more to
> say soon.

Generative UI for agents: the agent builds you the page rather than a scroll of
terminal text — a plan whose options you press to decide, a triage board you drag, a
dashboard that keeps up while a long job runs. When the project needs a widget that
doesn't exist, the agent writes one, and the same theme and checks cover it.

Underneath is a messaging and collaboration bus. Select any line and comment on it
like a shared doc, or drag a card, or rewrite a draft in your own words: it all
reaches the session as structured events, and the agent answers in the margin and
ships a revised version. The browser follows along on its own. Leaf is a plugin —
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

No config or account is required. It needs
[`uv`](https://docs.astral.sh/uv/) on `PATH` (`interact.py` declares its dependencies
in a PEP 723 header) and a browser on the same machine as the session.

Then ask the agent for a page. The explicit skill is `/leaf [topic]` in Claude Code
and `$leaf [topic]` in Codex; with no argument it presents whatever the session is
currently about.

## Customize

Project customizations live in `.leaf/`; user customizations live in
`~/.config/leaf/`. The agent works the project layer with the same commands when it
generates a widget. A short theme file cascades over the defaults, and a widget
scaffold adds a registry entry, CSS, and optionally an ES module:

```
leaf customize theme
leaf customize widget lf-callout
```

Add `--upgrade` to the widget's first scaffold command when it needs browser
behavior.

The next `leaf page init <page-dir>` vendors the merged layer. The
[customization guide](docs/customizing.html) covers the file contracts and the
project/user precedence.

## Examples

[`examples/`](examples/) holds a complete page for each kind of work, including a
dashboard meant to change as work finishes; they are live at
<https://leaf.page/examples.html>, and `gallery.html` puts them on one page as tabs.

## Related

[`notes/comparisons.md`](notes/comparisons.md) reads the nearby projects against
leaf, and covers where leaf is the wrong choice.

## Developing

[`CLAUDE.md`](CLAUDE.md) is how the thing is built: the shape of the payload, the
norms each part is held to, and the commands — the suite, the site, the vendored
bundles.

## License

MIT. See [LICENSE](LICENSE).
