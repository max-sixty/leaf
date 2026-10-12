"""Every owner the browser's question index names is an export of the module it names.

The index ("One answer for each question" in `skills/leaf/assets/AGENTS.md`) is
where an author looks before writing a predicate, so a row naming an owner that was
renamed or removed sends them to write a second copy. A rename fails here and points
at the row.
"""

import re

from interact_support import PLUGIN_ROOT

ASSETS = PLUGIN_ROOT / "skills/leaf/assets"
EXPORT = re.compile(
    r"^export\s+(?:async\s+)?(?:function|const|let|class)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)


def test_each_owner_in_the_question_index_is_exported_by_its_module():
    text = (ASSETS / "AGENTS.md").read_text()
    index = text.split("### One answer for each question", 1)[1].split("\n### ", 1)[0]
    rows = [
        line.split("|")[2]
        for line in index.splitlines()
        if line.startswith("| ") and not line.startswith(("| ---", "| Question"))
    ]
    named = [
        [code.split("(")[0] for code in re.findall(r"`([^`]+)`", owner)]
        for owner in rows
    ]
    owned = [
        (names[0], names[1:]) for names in named if names and names[0].endswith(".js")
    ]
    assert owned, "the question index lists no owners"
    missing = [
        f"{module} {name}"
        for module, names in owned
        for name in names
        if name not in EXPORT.findall((ASSETS / "runtime" / module).read_text())
        and not name.startswith("$")
    ]
    assert not missing, (
        f"the question index names owners its modules don't export: {missing}"
    )
