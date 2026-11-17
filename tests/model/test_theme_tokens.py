"""The theme's custom properties as a contract: every name is Leaf's own, and the ones
Leaf's examples and instructions teach are the ones its references name."""

import json
import re

from leaf.schema import ASSETS, BUNDLED_PACKAGES
from leaf.state import PLUGIN_ROOT

REFERENCES = PLUGIN_ROOT / "skills/leaf/references"
# A dependency's own properties, which Leaf sets or reads under the dependency's names.
DEPENDENCY = (
    "--wa-",
    "--pele-",
    "--trees-",
    "--pswp-",
    "--diffs-",
    "--plot-",
    "--divider-width",
    "--handle-size",
)
NAME = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?![\w-])")
DECLARED = re.compile(
    r"(?<![\w-])(--[A-Za-z0-9_-]+)\s*:|@property\s+(--[A-Za-z0-9_-]+)"
)
COMMENT = re.compile(r"/\*.*?\*/", re.S)
# A stylesheet's or a module's comments, which name properties without using them.
CODE_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\"'`])//[^\n]*", re.S)


def sheets():
    """The core's sheets and the bundled packages', less what they vendor."""
    return [
        path
        for root in (ASSETS, BUNDLED_PACKAGES)
        for path in sorted(root.rglob("*.css"))
        if "vendor" not in path.parts
    ]


def declared(text):
    return {a or b for a, b in DECLARED.findall(COMMENT.sub("", text))}


def documented():
    """Every custom property a reference names."""
    return {
        name
        for path in REFERENCES.glob("*.md")
        for name in NAME.findall(path.read_text())
        if name.startswith("--lf-")
    }


def test_every_property_leaf_declares_is_named_as_leaf_s():
    """A page's own CSS, or the framework it brings, declares custom properties on the
    same root Leaf's do, so a name they share sets Leaf's token too. Leaf's were bare
    (`--muted`, `--accent`, `--card`, `--sidebar`), which are also the names shadcn's
    tokens give a pale surface, a hover ground, a card and a sidebar's colour: on such a
    page the panel's quiet words took the surface's colour and read 1.1:1."""
    foreign = sorted(
        f"{sheet.relative_to(PLUGIN_ROOT)}: {name}"
        for sheet in sheets()
        for name in declared(sheet.read_text())
        if not name.startswith(("--lf-", *DEPENDENCY))
    )
    assert not foreign, (
        "these custom properties would meet a page's own names; start each with "
        "`--lf-`:\n  " + "\n  ".join(foreign)
    )


def test_what_leaf_teaches_reads_only_the_tokens_its_references_name():
    """An author learns Leaf's tokens from its examples, each widget's registry example
    and the packages' instructions, and copies what those read. Each `--lf-` property
    they read or set is one a reference names, or one the page declares for itself, so
    nothing an author copies is a name Leaf may change without notice."""
    public = documented()
    assert {"--lf-paper", "--lf-ink", "--lf-accent", "--lf-muted"} <= public, (
        "this reading has stopped finding the references' tokens"
    )
    taught = {}
    examples = PLUGIN_ROOT / "examples"
    for path in sorted(examples.rglob("*")):
        if path.suffix in {".html", ".css", ".js"} and path.is_file():
            taught[path.relative_to(PLUGIN_ROOT)] = path.read_text()
    for root in (ASSETS, BUNDLED_PACKAGES):
        for path in sorted(root.rglob("registry.json")):
            entries = json.loads(path.read_text())
            taught[path.relative_to(PLUGIN_ROOT)] = "\n".join(
                str(entry.get(key, ""))
                for name, entry in entries.items()
                if not name.startswith("$")
                for key in ("example", "instructions", "description")
            )
        for path in sorted(root.rglob("instructions/*.md")):
            taught[path.relative_to(PLUGIN_ROOT)] = path.read_text()

    def own(where, text):
        """What a page declares for itself, and what a package's sheets and modules
        declare, which its own instructions may name as its inputs."""
        names = declared(text)
        if where.parts[0] == "packages":
            package = PLUGIN_ROOT / where.parts[0] / where.parts[1]
            for path in package.rglob("*"):
                if path.suffix in {".css", ".js"} and "vendor" not in path.parts:
                    names |= set(NAME.findall(path.read_text()))
        return names

    private = sorted(
        f"{where}: {name}"
        for where, text in taught.items()
        for name in set(NAME.findall(text)) - public - own(where, text)
        if name.startswith("--lf-")
    )
    assert not private, (
        "these teach a property no reference names; use a theme token "
        '(package-themes.md, "Theme tokens"), or name the property in the reference '
        "that owns it:\n  " + "\n  ".join(private)
    )


def test_every_token_a_reference_names_is_one_leaf_uses():
    """The references' tokens are the contract an author reads, so each names a property
    Leaf's own code knows: one a sheet declares or reads, as it reads an author's
    `--lf-bound`, or one a module sets or reads by name. A name nothing uses is a
    renamed or removed token the prose still teaches, and a rule written from it does
    nothing, with no error its author would see. Whether each property a sheet reads
    is also set is `test_every_token_a_sheet_reads_is_set_somewhere`'s to hold."""
    used = set()
    sources = (ASSETS, BUNDLED_PACKAGES, PLUGIN_ROOT / "src/leaf")
    for source in sorted(path for root in sources for path in root.rglob("*")):
        if source.suffix in {".css", ".js", ".py"} and "vendor" not in source.parts:
            text = source.read_text()
            used |= set(
                NAME.findall(
                    text if source.suffix == ".py" else CODE_COMMENT.sub("", text)
                )
            )
    unused = sorted(documented() - used)
    assert not unused, f"the references name properties Leaf never uses: {unused}"
