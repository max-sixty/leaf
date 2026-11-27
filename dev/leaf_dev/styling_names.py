"""Leaf's styling names: the custom properties and `lf-` classes Leaf's own code
names, and the ones its references declare, which are the ones a page, theme or
package may rely on. `tests/model/test_theme_tokens.py` holds Leaf's teaching and the
bundled packages to the declared names, and `leaf-dev interface` reports each with who
sets it and who reads it. Each reading takes the root of the tree it reads, so the
census can read another commit's.

A name is read from a file's text, less its comments, by its shape: a custom property
is `--` and lowercase words, and a class an `lf-` word, as a selector, a module or a
reference writes it.
"""

import json
import re
from pathlib import Path

from leaf.source.structure import authored_classes

NAME = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?![\w-])")
CLASS = re.compile(r"(?<![\w/-])lf-[a-z0-9]+(?:-[a-z0-9]+)*(?![\w-])")
# A stylesheet's or a module's comments, which name properties without using them.
CODE_COMMENT = re.compile(r"/\*.*?\*/|(?<![:\"'`])//[^\n]*", re.S)
REFERENCES = "skills/leaf/references"


def sources(*roots: Path) -> list[Path]:
    """Each sheet and module under `roots`, vendored bundles aside."""
    return [
        path
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.suffix in {".css", ".js", ".py"} and "vendor" not in path.parts
    ]


def code(source: Path) -> str:
    """The names a sheet or a module uses: its text, less its comments."""
    text = source.read_text()
    return text if source.suffix == ".py" else CODE_COMMENT.sub("", text)


def documented(root: Path) -> set[str]:
    """Every custom property a reference names."""
    return {
        name
        for path in (root / REFERENCES).glob("*.md")
        for name in NAME.findall(path.read_text())
        if name.startswith("--lf-")
    }


def leaf_names(root: Path) -> tuple[set[str], set[str]]:
    """Leaf's own names: each `--lf-` property Leaf's code names, and each `lf-` class a
    sheet of Leaf's styles. Any other a package names is the package's own."""
    kernel = sources(root / "browser", root / "src/leaf")
    properties = {
        name
        for source in kernel
        for name in NAME.findall(code(source))
        if name.startswith("--lf-")
    }
    classes = {
        name
        for sheet in kernel
        if sheet.suffix == ".css"
        for name in re.findall(rf"\.({CLASS.pattern})", code(sheet))
    }
    return properties, classes


def idioms(root: Path) -> frozenset[str]:
    """The classes a kernel idiom lets a page write."""
    return authored_classes(json.loads((root / "browser/registry.json").read_text()))


def public_names(root: Path) -> set[str]:
    """The names an author can learn from the references: each custom property and
    `lf-` word a reference names, and each class a kernel idiom lets a page write."""
    return (
        documented(root)
        | idioms(root)
        | {
            name
            for path in (root / REFERENCES).glob("*.md")
            for name in CLASS.findall(path.read_text())
        }
    )
