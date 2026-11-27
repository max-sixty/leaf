"""The row a serving page publishes for its neighbours: its record, where it lives in
the state home, and the read that takes only the live server's own.

`server_rows` writes it; `presence` reads the machine's rows for a page's neighbours,
`/api/pages` and the band of Leaf's Claude Code hooks module, whose follower the hook
gate lets run where a row names its session (`state.named_by_row`)."""

from collections.abc import Mapping
from pathlib import Path

from leaf.base.files import read_json
from leaf.base.state import (
    ROW_SINCE,
    STRING,
    Record,
    described,
    object_schema,
    page_key,
    state_home,
)

# The compact activity shape a row carries, as `/api/pages` serves it.
ACTIVITY_FIELDS = frozenset(
    read_json(
        Path(__file__).parents[1] / "serving" / "served_state" / "state.schema.json"
    )["$defs"]["LivePage"]["properties"]["activity"]["required"]
)
COUNT_FIELDS = frozenset({"running", "waiting", "blocked", "unseen"})


def compact_activity(activity: dict) -> dict:
    """The bounded presentation contract; owed updates and reply bodies stay local."""
    return {key: activity[key] for key in ACTIVITY_FIELDS}


def row_path(page_dir: Path) -> Path:
    return state_home() / "rows" / f"{page_key(page_dir)}.json"


COUNT = {"type": "integer", "minimum": 0}

ROW = Record(
    "row",
    described(
        "A serving page's row, which other pages show it by, in the state home's "
        "`rows/<page key>.json`.",
        object_schema(
            {
                "page": described("The page directory.", STRING),
                "page_key": described("The page's key (`state.page_key`).", STRING),
                "server_id": described(
                    "The server incarnation that published the row; a reader "
                    "takes only the live service's own.",
                    STRING,
                ),
                "started_in": described(
                    "The session from whose shell a Leaf that doesn't run it started "
                    "this server for no session (`harness.unserved_session`), so that "
                    "session's band lists the page it doesn't hold; null for any "
                    "other server.",
                    {"type": ["string", "null"]},
                ),
                "row": described(
                    "What other pages show of it.",
                    object_schema(
                        {
                            "title": described("The page's title.", STRING),
                            "session_cwd": described(
                                "The claimant session's working directory, or null.",
                                {"type": ["string", "null"]},
                            ),
                            "activity": described(
                                "The page's activity, bounded to the fields a row "
                                "shows (`compact_activity`).",
                                {
                                    "type": "object",
                                    "properties": {
                                        "counts": {
                                            "type": "object",
                                            "required": sorted(COUNT_FIELDS),
                                        }
                                    },
                                    "required": sorted(ACTIVITY_FIELDS),
                                },
                            ),
                            "on_user": described("How many rows On Me holds.", COUNT),
                            "threads": described(
                                "What the Leaf panel counts of the threads (`thread_counts`): "
                                "the open threads, and of those the ones the user hasn't read.",
                                object_schema({"open": COUNT, "unread": COUNT}),
                            ),
                        }
                    ),
                ),
            }
        ),
    ),
    since=ROW_SINCE,
)


def read_row(
    page_dir: Path, service: Mapping[str, object], *, record=None
) -> dict | None:
    """The row this live service's own incarnation published for the page, from
    `record` where the caller has already read it."""
    if record is None:
        record = ROW.read(row_path(page_dir))
    if record is None or record["server_id"] != service["server_id"]:
        return None
    return record["row"]
