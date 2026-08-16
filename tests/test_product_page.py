"""The product pages use the shipped theme and widget vocabulary directly."""

import html
import json
import re
import shlex
import subprocess
from pathlib import Path

import click
from conftest import interact

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "plugins" / "leaf" / "skills" / "leaf" / "assets"
BUNDLED = ROOT / "plugins" / "leaf" / "skills" / "leaf" / "bundled"
DOCS = ROOT / "docs"


def test_docs_pages_link_the_shipped_theme():
    # Both shipped layers, in cascade order — a docs page renders the whole
    # vocabulary script-free, and the bundled widgets' rules are the second file.
    targets = (
        "../plugins/leaf/skills/leaf/assets/theme.css",
        "../plugins/leaf/skills/leaf/bundled/theme.css",
    )
    for layer in (ASSETS, BUNDLED):
        assert (layer / "theme.css").is_file()
    # The <link> around the href, not the whole tag spelled out: customizing.html also
    # links that same file as source to read, so the path alone would pass on a page
    # that had dropped its stylesheet. Attributes in any order and on any number of
    # lines, because a formatter decides that — prettier puts this one on four.
    pages = sorted(DOCS.glob("*.html"))
    # A glob that found nothing walks nothing and passes: this whole check is the loop.
    assert pages, f"no pages under {DOCS}"
    for page in pages:
        text = page.read_text()
        for target in targets:
            link = re.compile(rf'<link\b[^>]*?"{re.escape(target)}"')
            assert link.search(text), (page.name, target)


def test_docs_pages_use_only_registered_widgets():
    registry = json.loads((ASSETS / "registry.json").read_text()) | json.loads(
        (BUNDLED / "registry.json").read_text()
    )
    used = {
        tag
        for page in DOCS.glob("*.html")
        for tag in re.findall(r"<(lf-[a-z-]+)", page.read_text())
    }
    assert used and used <= set(registry)


def test_customizing_guide_documents_every_key_a_registry_entry_may_declare():
    """The guide's table of `x-` keys is written by hand, and the vocabulary it
    describes is not closed — a widget declaring a behaviour the layer didn't have
    adds a key, and the table is the only place an author meets it. Nothing held the
    two together, so the table drifted four keys behind the schema and the guide read
    as complete the whole time: a key it omits is one nobody writing a widget knows
    they may write.

    Against `EXTENSION_SCHEMA` rather than the shipped registries, because that is the
    closed set — `additionalProperties: False` means no entry can declare a key outside
    it, and a key lands there first, before any widget adopts it. Deriving the list from
    the registries instead would let a key go undocumented for as long as it went
    unused, which is exactly the stretch in which someone reads the guide to find out
    what is available."""
    documented = " ".join(
        (DOCS / "customizing.html").read_text().split()
    )  # collapsed: prettier decides where the lines in a table cell fall
    keys = sorted(k for k in interact.EXTENSION_SCHEMA["properties"] if k[:2] == "x-")
    assert keys, "no extension keys read — an empty vocabulary demonstrates itself"
    undocumented = [
        k for k in keys if not re.search(rf"\b{re.escape(k)}\b", documented)
    ]
    assert not undocumented, (
        f"docs/customizing.html documents no {', '.join(undocumented)}"
    )


def test_customizing_guide_sits_beside_how_it_works():
    customizing = (DOCS / "customizing.html").read_text()
    assert 'href="how-it-works.html"' in customizing
    for source in ("index.html", "how-it-works.html"):
        assert 'href="customizing.html"' in (DOCS / source).read_text()


def test_customizing_guide_uses_the_current_layer_and_cli_names():
    customizing = (DOCS / "customizing.html").read_text()

    assert ".claude/leaf" not in customizing
    assert "<code>.leaf/</code>" in customizing
    for stale in (
        "leaf init ",
        "leaf catalog ",
        "leaf check ",
    ):
        assert stale not in customizing
    for current in (
        "leaf page init ",
        "leaf page catalog ",
        "leaf version check ",
        'actionSequence(this, "verb")',
        'watchActions(this, "verb", render)',
    ):
        assert current in customizing


def test_every_command_the_docs_show_is_one_leaf_has():
    """A shown command is a promise the reader will type it.

    The pages narrate the agent's half of the loop and `how-it-works.html` now shows
    it, and a renamed subcommand is what quietly breaks that: the transcript is prose
    to every other gate here, so a stale `leaf ack` would go on being published
    indefinitely. The names are resolved against click's own tree rather than listed
    in this file, because a list is the second copy that goes stale the same way —
    which is the mistake the guide's own name check makes and this one is not
    repeating.
    """

    def shown_in(text):
        """Prompt lines inside a transcript, and the inline mentions in the prose.

        A block's own tags sit on its first and last lines — `<pre><code>$ leaf …`
        and `… 3</code></pre>` — so the markup comes out before the lines are read,
        or the sweep silently skips the first command it was written for.
        """
        for block in re.findall(r"<pre[^>]*>(.*?)</pre>", text, re.DOTALL):
            yield from re.findall(
                r"^\$ +leaf +(.+)$", re.sub(r"<[^>]+>", "", block), re.MULTILINE
            )
        yield from re.findall(r"<code>leaf +([^<]+)</code>", text)

    shown = [
        (source.name, line)
        for source in sorted(DOCS.glob("*.html"))
        for line in shown_in(html.unescape(source.read_text()))
    ]
    assert len(shown) > 10, (
        f"only {len(shown)} leaf commands found in the docs — the sweep is reading "
        f"past them rather than checking them"
    )

    def named(tokens):
        """The subcommand path these tokens walk, greedily, from the root group."""
        command, path = interact.cli, []
        for token in tokens:
            if not isinstance(command, click.Group):
                break
            sub = command.get_command(None, token)
            if sub is None:
                break
            path.append(token)
            command = sub
        return path

    unknown = [
        f"{source}: leaf {line}"
        for source, line in shown
        if not named(shlex.split(line))
    ]
    assert not unknown, "these pages show commands leaf hasn't got:\n  " + "\n  ".join(
        unknown
    )


def test_tour_walks_the_interactive_and_live_workflows():
    tour = (DOCS / "index.html").read_text()

    for example in ("triage-board", "live-progress"):
        assert f'href="../examples/{example}.html"' in tour
        assert f"scripts/preview.py {example}" in tour
    assert (
        '"widget":"release-board","action":"move","detail":{"card":"card-export"'
        in tour
    )
    assert 'src="demo.gif"' in tour

    live = (ROOT / "examples" / "live-progress.html").read_text()
    # Whitespace collapsed, because this asks what the page says and the source is
    # formatted: prettier re-derives every line break in a paragraph, so a sentence
    # asserted as source bytes is a sentence that fails the day it gets a word longer.
    assert "browser is following the newest version" in " ".join(live.lower().split())
    for status in ("done", "active", "planned"):
        assert f'status="{status}"' in live
    assert "<h2>Blocked</h2>" in live


def test_demo_recording_drives_the_browser_journey(tmp_path):
    output = tmp_path / "demo.gif"
    # Not check=True: with the streams captured, the CalledProcessError it raises
    # names the command and the exit status and takes both of them down with it,
    # so a browser step that timed out and a server that never bound report the
    # same nothing. This is `open_page`'s complaint about "Failed to load
    # resource" one file over — carry what failed into the failure.
    recorded = subprocess.run(
        [ROOT / "scripts" / "record-demo.sh", "--output", output],
        capture_output=True,
        text=True,
        check=False,
    )

    assert recorded.returncode == 0, (
        f"record-demo.sh exited {recorded.returncode}\n"
        f"{recorded.stdout}{recorded.stderr}".rstrip()
    )
    assert recorded.stdout.strip() == f"Recorded {output}"
    assert output.read_bytes().startswith(b"GIF89a")
