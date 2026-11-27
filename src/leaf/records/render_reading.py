"""The page's render reading: what the latest render check, by `page check --render` or
the page's server (`handover_pass`, which decides when one is kept), read of one
version with the page's data as it then stood. Beside its findings it keeps what each
visual drew (`drawn_visuals`): the parts it offered a thread, and whether the page puts
a thread on a part the visual didn't draw on the whole visual, as it does for a visual
that draws a part on request or once it can (`drawsAbsentParts` in
`state/visual-parts.js`). `leaf page state` lists the parts, so an agent naming one
takes its id from what the page drew rather than working it out from a widget's prose.
`leaf thread create --part` reads both, and refuses a part the page would show nowhere
(`anchor_capture.drawn_part`).

The reading holds only while the page shows the version and holds the data the reading
read. Until a check reads the page again, `page state` lists no parts and `thread
create --part` draws the page itself (`render_gate.drawn_anchor`). That happens after a
data update, which changes no version but can change what a visual draws, as clearing a
trace's recording removes its rows. It happens too after a check of an older version
finishes after a newer one's and replaces its reading. The agent's next `page check
--render` restores the list (`threads.md`), so a reading is written without a guard
against a later save: the page's file stamps, the only cheap sign of one, also move
when the user pastes an image into a comment they haven't sent. A Leaf update that
changes a widget's part ids while the version stands leaves the old ids in the reading
until that check, so until then `thread create --part` names the old ids and may refuse
a new one; keying the reading by the execution identity too
(`runtime_selection.execution_identity`) would compose the page's layer for every `page
state`.

A visual lists the parts it draws when the check reads it, so a part it finds only when
asked for it, or draws only while a view of it is open, may be missing from the list
and still be one the visual can show. Such a visual gives `find` or `reveal`
(`module-annotations.md`, "Visual parts"), so the page puts a thread on a part missing
from the list on the whole visual until the visual draws it, and `thread create`
admits the part rather than refusing it."""

from pathlib import Path

from leaf.base.state import (
    STRING,
    Record,
    described,
    object_schema,
    page_key,
    state_home,
)

READING = Record(
    "render-reading",
    described(
        "The latest render check of a page, by `page check --render` or its server "
        "(`handover_pass`), in the state home's "
        "`render-readings/<page key>.json`. Disposable: without it, a version is read "
        "again.",
        object_schema(
            {
                "page": described("The page directory.", STRING),
                "digest": described("The artifact digest of the version read.", STRING),
                "data": described(
                    "The version of the page's data the check read the page with "
                    "(`data.data_version`); null where the check never read the page, "
                    "as where it overran its deadline.",
                    {"type": ["string", "null"]},
                ),
                "findings": described(
                    "What it found (`findings.Finding.json`), every finding of which "
                    "the agent has heard.",
                    {"type": "array", "items": {"type": "object"}},
                ),
                "visuals": described(
                    "What each visual in the page drew at the desktop window, by the "
                    "visual's id (`drawnVisuals` in `render-checks/widgets.js`); empty "
                    "where the check stopped before it read them.",
                    {
                        "type": "object",
                        "additionalProperties": object_schema(
                            {
                                "parts": described(
                                    "The parts the visual offered a thread.",
                                    {
                                        "type": "array",
                                        "items": object_schema(
                                            {"id": STRING, "label": STRING}
                                        ),
                                    },
                                ),
                                "whole": described(
                                    "Whether the page puts a thread on a part the "
                                    "visual didn't draw on the whole visual, rather "
                                    "than nowhere (`drawsAbsentParts`).",
                                    {"type": "boolean"},
                                ),
                            }
                        ),
                    },
                ),
            }
        ),
    ),
    since=57,
)


def _reading_path(page_dir: Path) -> Path:
    return state_home() / "render-readings" / f"{page_key(page_dir)}.json"


def read_reading(page_dir: Path) -> dict | None:
    return READING.read(_reading_path(page_dir))


def write_reading(
    page_dir: Path,
    digest: str,
    data: str | None,
    findings: list[dict],
    visuals: dict[str, dict],
) -> None:
    path = _reading_path(page_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    READING.write(
        path,
        {
            "page": str(page_dir),
            "digest": digest,
            "data": data,
            "findings": findings,
            "visuals": visuals,
        },
    )


def drawn_visuals(page_dir: Path, digest: str, data: str) -> dict[str, dict]:
    """What each visual drew, by the visual's id, where the page's render reading read
    the version `digest` with the data version `data`: its `parts`, each an `id` and
    `label`, and `whole`; none where the reading read another version, other data or
    nothing."""
    reading = read_reading(page_dir)
    if reading is None or (reading["digest"], reading["data"]) != (digest, data):
        return {}
    return reading["visuals"]
