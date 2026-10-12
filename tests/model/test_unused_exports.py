"""Every JavaScript and TypeScript export has a reader in another file.

An export nothing imports is what a removed caller leaves behind: the module keeps
offering it, the next reader takes it for a contract, and the code it holds up
outlives its last use. The check runs here, over the whole tree, rather than in a
JavaScript tool such as knip, because the runtime's readers are not all JavaScript.

What a module exports, and what each module reads from others, come from its parse
(`tests/js_facts.mjs`, `exports` and `imports`), a TypeScript module's types and
interfaces included. A module reads a name it imports or re-exports, names in a type
`import("…").Name`, TypeScript's or a JSDoc comment's, or takes from a module
namespace, each resolved to the module that exports it; `imports` says how. A read
through `export * from` reaches the modules re-exported. A committed bundle exports
nothing this checks, since its source is checked, but its imports are readers: what
it left external is what it reads from the tree. A read of a bundle compiled from one
module here, such as `vendor/browser-runtime.js`, is a read of that module.

The readers that are not JavaScript are found by word, and only in the files that hold
them: a Python test that imports runtime modules inside a string
(`__lfRuntimeImport('/runtime/…')`) or a render gate that calls probes by name, a
page's inline script, and a contract's prose. A name counts as read where one of
those files names it as a word, so a name that collides with another word there can
still hide an unused export.

A host reads the module it loads by its own rules: the Workers runtime reads each
export of the Worker's entry (`worker/wrangler.toml`'s `main`) by name, as
`@cloudflare/containers` does `ContainerProxy`, so all of them are read.

A default export has no name of its own: its readers import the module, or a tool
loads it by path, as eslint loads `eslint.config.mjs` and Pi loads `hooks/pi.ts`.
So it counts as read where a module imports it, another file names the module's
file name, or a registry declares an upgraded widget that loads its constructor.
"""

import json
import re
import tomllib
from pathlib import PurePosixPath

from interact_support import PLUGIN_ROOT, js_facts, shipped_payload
from leaf.registry.contract import element_declarations

SOURCES = (".js", ".mjs", ".ts")
WORDED = (".py", ".html", ".md")
VENDORED = re.compile(r"(^|/)vendor/")
# A third-party bundle's own input under `build/` exports the surface of the package
# it stands in for, which the bundled dependency reads and this tree never names
# (`build/AGENTS.md`). Its own imports are still readers. `protocol-contract.d.ts` is
# `event-contract.d.ts` as it last stood at this protocol, which `build/browser/build.mjs`
# copies whole, so its exports are those of the contract this checks.
UNCHECKED = re.compile(
    r"^build/(?!browser/)[^/]+/|^build/browser/protocol-contract\.d\.ts$"
)
# An escape is consumed whole, so `"\ndefine(…)"` in a Python string reads `define`.
WORD = re.compile(r"\\[a-z]|([A-Za-z_$][\w$]*)")
WORKER = "worker/wrangler.toml"


def widget_default_readers(texts):
    """Registry-owned constructor imports consumed by publicationVocabulary.load."""
    return {
        (PurePosixPath(relative).parent / "widgets" / f"{tag}.js").as_posix()
        for relative, text in texts.items()
        if PurePosixPath(relative).name == "registry.json"
        for tag, entry in element_declarations(json.loads(text)).items()
        if entry.get("x-upgrade")
    }


def test_dynamic_default_readers_require_an_upgraded_element_declaration():
    texts = {
        "page/registry.json": json.dumps(
            {
                "lf-loaded": {"x-upgrade": True},
                "lf-static": {"x-upgrade": False},
                "lf-selector.selected": {"x-upgrade": True},
            }
        ),
        "reader.js": 'import value from "./ordinary.js";',
        "other/widgets/lf-loaded.js": "export default class {}",
    }
    assert widget_default_readers(texts) == {"page/widgets/lf-loaded.js"}


def test_every_export_has_a_reader_in_another_file():
    texts = {}
    for path in shipped_payload():
        relative = path.relative_to(PLUGIN_ROOT).as_posix()
        if not path.is_file():
            continue
        try:
            texts[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    sources = [relative for relative in texts if relative.endswith(SOURCES)]
    modules = [
        relative
        for relative in sources
        if not VENDORED.search(relative) and not UNCHECKED.search(relative)
    ]
    exported = json.loads(js_facts("exports", modules))
    imported = json.loads(js_facts("imports", sources))
    exporters = {}
    for module in modules:
        for name in exported[module]["names"]:
            exporters.setdefault(name, set()).add(module)
    assert exporters, "no exports read — an empty set guards nothing"

    read = set()

    def mark(module, name, through=()):
        """Read `name` of `module`, or each of its names for `*`, through its stars."""
        if module in through or module not in imported:
            return
        names = set(exported.get(module, {"names": []})["names"]) | {"default"}
        if name == "*":
            read.update((module, each) for each in names)
        elif name in names:
            read.add((module, name))
            return
        for star in imported[module]["stars"]:
            mark(star, name, (*through, module))

    for reader, facts in imported.items():
        for module, name in facts["reads"]:
            for target in exporters.get(name, ()) if module is None else (module,):
                if target != reader:
                    mark(target, name)
    for module in widget_default_readers(texts):
        mark(module, "default")
    worker = PurePosixPath(WORKER).parent
    mark(str(worker / tomllib.loads(texts[WORKER])["main"]), "*")

    worded = {
        relative: text for relative, text in texts.items() if relative.endswith(WORDED)
    }
    words = set()
    for text in worded.values():
        words.update(WORD.findall(text))

    unread = sorted(
        [
            f"{module}: {name}"
            for module in modules
            for name in exported[module]["names"]
            if (module, name) not in read and name not in words
        ]
        + [
            f"{module}: default"
            for module in modules
            if exported[module]["default"]
            and (module, "default") not in read
            and not any(
                PurePosixPath(module).name in text
                for relative, text in texts.items()
                if relative != module and not VENDORED.search(relative)
            )
        ]
    )
    assert not unread, (
        "exports nothing reads; drop `export` where only the module itself uses the "
        "name, and delete what nothing uses:\n" + "\n".join(unread)
    )
