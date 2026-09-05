"""The product pages are Leaf documents using the site's composed vocabulary."""

import html
import json
import re
import shlex
import subprocess
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from leaf import cli as cli_model
from leaf.registry import validation as registry_validation
from leaf.validation import compatibility as validation_model

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "skills" / "leaf" / "assets"
DEFAULT_PACKAGE = ROOT / "skills" / "leaf" / "packages" / "default"
DOCS = ROOT / "docs"


def test_docs_pages_use_the_leaf_document_scaffold():
    pages = sorted(DOCS.glob("*.html"))
    assert {page.name for page in pages} == {
        "index.html",
        "examples.html",
        "how-it-works.html",
        "packages.html",
        "registry.html",
    }
    for page in pages:
        text = page.read_text()
        assert text.count('<link rel="stylesheet" href="/theme.css"') == 1, page.name
        assert text.count('<script type="module" src="/leaf.js"') == 1, page.name
        assert text.count("Content-Security-Policy") == 1, page.name
        assert '<body class="site-page' in text, page.name


def test_docs_pages_use_only_registered_widgets():
    package_names = json.loads((ROOT / "examples" / "layer.json").read_text())
    registries = [
        ASSETS / "registry.json",
        DEFAULT_PACKAGE / "registry.json",
        *(
            ROOT / "skills" / "leaf" / "packages" / name / "registry.json"
            for name in package_names
        ),
        DOCS / "package" / "registry.json",
    ]
    registry = {}
    for source in registries:
        if source.exists():
            registry.update(json.loads(source.read_text()))
    used = {
        tag
        for page in DOCS.glob("*.html")
        for tag in re.findall(r"<(lf-[a-z-]+)", page.read_text())
    }
    assert used and used <= set(registry)


def test_package_guide_sits_beside_how_it_works():
    packages = (DOCS / "packages.html").read_text()
    assert 'href="/how-it-works/"' in packages
    assert 'href="/registry/"' in packages
    assert 'href="/packages/"' in (DOCS / "registry.html").read_text()
    for source in ("index.html", "how-it-works.html"):
        assert 'href="/packages/"' in (DOCS / source).read_text()


def test_package_tutorial_registry_entry_is_valid(page_dir):
    blocks = re.findall(
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>",
        (DOCS / "packages.html").read_text(),
        re.DOTALL,
    )
    entry = json.loads(
        html.unescape(next(block for block in blocks if block.lstrip().startswith("{")))
    )
    registry = json.loads((page_dir / "registry.json").read_text()) | entry

    registry_validation.validate_registry(registry, "package tutorial")
    validation_model.validate_registry_examples(registry, "package tutorial")


def test_how_it_works_quotes_the_real_check_and_stamp_lines(page_dir):
    """Both lines the transcript shows an agent, taken from the commands themselves.

    A shown line is a promise about what the reader will see. The changelog is the
    page's own, so the stamp line is generated here with the transcript's text
    rather than pattern-matched — a renamed field or a changed separator has to be
    written into the page before this passes again.
    """
    checked = CliRunner().invoke(cli_model.cli, ["version", "check", str(page_dir)])
    assert checked.exit_code == 0, checked.output
    success = next(
        line for line in checked.output.splitlines() if line.startswith("✓ index.html:")
    )

    changelog = "Two ways to shed load — which?"
    stamped = CliRunner().invoke(
        cli_model.cli, ["version", "stamp", str(page_dir), "--text", changelog]
    )
    assert stamped.exit_code == 0, stamped.output

    transcript = html.unescape((DOCS / "how-it-works.html").read_text())
    assert success in transcript
    assert stamped.output.strip() in transcript


def test_every_command_the_docs_show_is_one_leaf_has():
    """A shown command is a promise the reader will type it.

    The pages narrate the agent's half of the loop and `how-it-works.html` now shows
    it, and a renamed subcommand is what quietly breaks that: the transcript is prose
    to every other gate here, so a stale `leaf ack` would go on being published
    indefinitely. The names are resolved against click's own tree rather than listed
    in this file, because a list here is a second copy of the command surface and goes
    stale the same way the page does.
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
        command, path = cli_model.cli, []
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


@pytest.mark.nightly
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
