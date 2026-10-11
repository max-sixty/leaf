"""Every JavaScript and TypeScript export has a reader in another file.

An export nothing imports is what a removed caller leaves behind: the module keeps
offering it, the next reader takes it for a contract, and the code it holds up
outlives its last use. The check runs here, over the whole tree, rather than in a
JavaScript tool such as knip, because the runtime's readers are not all
JavaScript: the browser tests import runtime modules inside Python strings
(`__lfRuntimeImport('/runtime/…')`), the render gate calls probes by name, and
packages load by tag. A word search sees all of them.

A name counts as read when any other tracked text file mentions it as a word,
prose included. So a name that collides with another word in the tree can hide an
unused export; the check never reports a used one.
"""

import re

from interact_support import PLUGIN_ROOT, shipped_payload

SOURCES = (".js", ".mjs", ".ts")
# Committed bundles are generated from the sources this reads, and a bundle names
# every export it inlined, so they neither export nor read.
VENDORED = re.compile(r"(^|/)vendor/")
# A third-party bundle's own input under `build/` exports the surface of the package
# it stands in for, which the bundled dependency reads and this tree never names
# (`build/AGENTS.md`). Its own imports are still readers.
STAND_INS = re.compile(r"^build/(?!browser/)[^/]+/")
DECLARED = re.compile(
    r"^export\s+(?:async\s+)?(?:function\*?|const|let|var|class|type|interface|enum)"
    r"\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
LISTED = re.compile(r"^export\s+(?:type\s+)?\{([^}]*)\}", re.MULTILINE)
# An escape is consumed whole, so `"\ndefine(…)"` in a Python string reads `define`.
WORD = re.compile(r"\\[a-z]|([A-Za-z_$][\w$]*)")


def exported_names(text):
    names = set(DECLARED.findall(text))
    for listed in LISTED.findall(text):
        for item in listed.split(","):
            if name := item.split(" as ")[-1].strip():
                names.add(name)
    return names - {"default"}


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
    exporters = {}
    for relative, text in texts.items():
        if relative.endswith(SOURCES) and not STAND_INS.match(relative):
            for name in exported_names(text):
                exporters.setdefault(name, set()).add(relative)
    assert exporters, "no exports read — an empty set guards nothing"

    readers = {}
    for relative, text in texts.items():
        for name in set(WORD.findall(text)) & exporters.keys():
            readers.setdefault(name, set()).add(relative)

    unread = sorted(
        f"{exporter}: {name}"
        for name, files in exporters.items()
        if not readers.get(name, set()) - files
        for exporter in files
    )
    assert not unread, (
        "exports no other file names; drop `export` where only the module itself "
        "uses the name, and delete what nothing uses:\n" + "\n".join(unread)
    )
