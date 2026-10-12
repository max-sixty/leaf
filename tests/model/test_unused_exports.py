"""Every JavaScript and TypeScript export has a reader in another file.

An export nothing imports is what a removed caller leaves behind: the module keeps
offering it, the next reader takes it for a contract, and the code it holds up
outlives its last use. The check runs here, over the whole tree, rather than in a
JavaScript tool such as knip, because the runtime's readers are not all
JavaScript: the browser tests import runtime modules inside Python strings
(`__lfRuntimeImport('/runtime/…')`), the render gate calls probes by name, and
packages load by tag. A word search sees all of them.

A default export has no name of its own: its readers import the module, or a tool
loads it by path, as eslint loads `eslint.config.mjs` and Pi loads `hooks/pi.ts`.
So it counts as read where another file names the module's file name, or a
registry declares an upgraded widget that loads its default constructor by tag.

What a module exports is read from its parse (`tests/js_facts.mjs`, `exports`), a
TypeScript module's types and interfaces included. A name counts as read where another
tracked file names it as a word: in code, in a Python string, in a page, or in a
contract's prose. A JavaScript comment or a stylesheet reads nothing, since a module's
comment about another's helper keeps no caller alive, except for a JSDoc type import
(`import("…").Name`). A name that collides with another word can still hide an unused
export. The comment reading is textual, so a `/*` inside a string can only make the
check report a used export, never pass an unused one.
"""

import json
import re
from pathlib import PurePosixPath

from interact_support import PLUGIN_ROOT, js_facts, shipped_payload
from leaf.registry.contract import element_declarations

SOURCES = (".js", ".mjs", ".ts")
# Not `//` after a colon, quote or backtick, which is a URL or a string.
COMMENT = re.compile(r"/\*.*?\*/|(?<![:\"'`\\])//[^\n]*", re.DOTALL)
TYPE_IMPORT = re.compile(r"import\(\s*[\"'][^\"']+[\"']\s*\)\.([A-Za-z_$][\w$]*)")
# Committed bundles are generated from the sources this reads, and a bundle names
# every export it inlined, so they neither export nor read.
VENDORED = re.compile(r"(^|/)vendor/")
# A third-party bundle's own input under `build/` exports the surface of the package
# it stands in for, which the bundled dependency reads and this tree never names
# (`build/AGENTS.md`). Its own imports are still readers.
STAND_INS = re.compile(r"^build/(?!browser/)[^/]+/")
# An escape is consumed whole, so `"\ndefine(…)"` in a Python string reads `define`.
WORD = re.compile(r"\\[a-z]|([A-Za-z_$][\w$]*)")


def reading(relative, text):
    """The text of `relative` that can read an export."""
    if relative.endswith(".css"):
        return ""
    if relative.endswith(SOURCES):
        return COMMENT.sub(" ", text) + " ".join(TYPE_IMPORT.findall(text))
    return text


def unread_defaults(modules, readings):
    """Defaults without a textual reader or a registry-owned widget loader."""
    # publicationVocabulary.load consumes the constructor from /widgets/<tag>.js;
    # the same sibling directory contract holds for packages and page-local widgets.
    widget_modules = {
        (PurePosixPath(relative).parent / "widgets" / f"{tag}.js").as_posix()
        for relative, text in readings.items()
        if PurePosixPath(relative).name == "registry.json"
        for tag, entry in element_declarations(json.loads(text)).items()
        if entry.get("x-upgrade")
    }
    return [
        module
        for module in modules
        if module not in widget_modules
        and not any(
            PurePosixPath(module).name in text
            for relative, text in readings.items()
            if relative != module
        )
    ]


def test_dynamic_default_readers_require_an_upgraded_element_declaration():
    readings = {
        "page/registry.json": json.dumps(
            {
                "lf-loaded": {"x-upgrade": True},
                "lf-static": {"x-upgrade": False},
                "lf-selector.selected": {"x-upgrade": True},
            }
        ),
        "reader.js": 'import value from "./ordinary.js";',
    }
    modules = [
        "page/widgets/lf-loaded.js",
        "page/widgets/lf-static.js",
        "page/widgets/lf-orphan.js",
        "page/widgets/lf-selector.selected.js",
        "other/widgets/lf-loaded.js",
        "ordinary.js",
        "unused.js",
    ]
    assert unread_defaults(modules, readings) == [
        "page/widgets/lf-static.js",
        "page/widgets/lf-orphan.js",
        "page/widgets/lf-selector.selected.js",
        "other/widgets/lf-loaded.js",
        "unused.js",
    ]


def test_every_export_has_a_reader_in_another_file():
    texts = {}
    for path in shipped_payload():
        relative = path.relative_to(PLUGIN_ROOT).as_posix()
        if not path.is_file() or VENDORED.search(relative):
            continue
        try:
            texts[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    modules = [
        relative
        for relative in texts
        if relative.endswith(SOURCES) and not STAND_INS.match(relative)
    ]
    parsed = json.loads(js_facts("exports", modules))
    exporters = {}
    defaults = []
    for relative in modules:
        for name in parsed[relative]["names"]:
            exporters.setdefault(name, set()).add(relative)
        if parsed[relative]["default"]:
            defaults.append(relative)
    assert exporters, "no exports read — an empty set guards nothing"

    readings = {relative: reading(relative, text) for relative, text in texts.items()}
    readers = {}
    for relative, text in readings.items():
        for name in set(WORD.findall(text)) & exporters.keys():
            readers.setdefault(name, set()).add(relative)

    unread = sorted(
        [
            f"{exporter}: {name}"
            for name, files in exporters.items()
            if not readers.get(name, set()) - files
            for exporter in files
        ]
        + [f"{module}: default" for module in unread_defaults(defaults, readings)]
    )
    assert not unread, (
        "exports no other file names; drop `export` where only the module itself "
        "uses the name, and delete what nothing uses:\n" + "\n".join(unread)
    )
