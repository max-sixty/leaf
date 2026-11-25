"""The page's render reading: what the latest render check, by `page check --render` or
the page's server (`render_gate.handover_pass`, which decides when one is kept), read
of one version with the page's data as it then stood. `leaf page state` lists the parts
it read (`drawn_parts`), so an agent naming a part takes its id from what the page drew
rather than working it out from a widget's prose.

The list holds only while the page shows the version and holds the data the reading
read. A data update changes no version but can change what a visual draws, as clearing
a trace's recording removes its rows, so after one `page state` lists no parts until a
check reads the page again. A check of an older version that finishes after a newer
one's replaces its reading, and the page then lists no parts either. Neither lists a
part the page no longer draws, and the agent's next `page check --render` restores the
list (`threads.md`), so a reading is written without a guard against a later save: the
page's file stamps, the only cheap sign of one, also move when the user pastes an image
into a comment they haven't sent.

The list is for finding a part, and decides nothing: a visual lists the parts it draws
now, so a part it finds only when asked for it, or draws only while a view of it is
open, may be missing from the list and still be one the visual can show."""

from pathlib import Path

from .state import STRING, Record, described, object_schema, page_key, state_home

READING = Record(
    "render-reading",
    described(
        "The latest render check of a page, by `page check --render` or its server "
        "(`render_gate.handover_pass`), in the state home's "
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
                "parts": described(
                    "The parts each visual in the page offered a thread at the "
                    "desktop window, by the visual's id (`drawnParts` in "
                    "`render-checks/widgets.js`); empty where the check stopped "
                    "before it read them.",
                    {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": object_schema({"id": STRING, "label": STRING}),
                        },
                    },
                ),
            }
        ),
    ),
    since=56,
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
    parts: dict[str, list[dict]],
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
            "parts": parts,
        },
    )


def drawn_parts(page_dir: Path, digest: str, data: str) -> dict[str, list[dict]]:
    """The parts each visual drew, by the visual's id, where the page's render reading
    read the version `digest` with the data version `data`; none where it read another
    version, other data or nothing."""
    reading = read_reading(page_dir)
    if reading is None or (reading["digest"], reading["data"]) != (digest, data):
        return {}
    return reading["parts"]
