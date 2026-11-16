"""The user's drafts on the page's server (`leaf.drafts`): a write takes only the
generation it names, admitting a send settles the generation it carries, and tabs hear
drafts through their own news, which moves no reading of the page and reaches no part of
what the agent reads."""

import json

from click.testing import CliRunner
from interact_support import fetch, publish, server  # noqa: F401 (fixture)

from leaf import cli as cli_model
from leaf import drafts as drafts_model


def _write(page_dir, expect, attempt, text="Words", **record):
    return drafts_model.write_draft(
        page_dir,
        {
            "context": "general",
            "expect": expect,
            "record": {"attempt": attempt, "text": text, **record},
        },
    )


def test_a_draft_write_takes_only_the_generation_it_names(tmp_path):
    """A tab replaces the generation it last knew the server held, so words another tab
    wrote or sent meanwhile come back to it rather than being overwritten."""
    assert _write(tmp_path, None, "a1")["written"]
    refused = _write(tmp_path, None, "a2")
    assert not refused["written"]
    assert refused["record"]["attempt"] == "a1"
    assert _write(tmp_path, "a1", "a2", "Newer words")["written"]
    settled = drafts_model.write_draft(
        tmp_path,
        {
            "context": "general",
            "expect": "a2",
            "record": {"attempt": "a2", "settled": True},
        },
    )
    assert settled["written"]
    assert drafts_model.read_drafts(tmp_path)["drafts"] == {}
    # A tab that never heard of the settled generation starts the next one.
    assert _write(tmp_path, None, "a3", "A new thought")["written"]
    # A tab still holding the settled generation's predecessor hears the new one back.
    stale = _write(tmp_path, "a1", "a4")
    assert not stale["written"]
    assert stale["record"]["text"] == "A new thought"
    reading = drafts_model.read_drafts(tmp_path)
    assert reading["drafts"]["general"]["attempt"] == "a3"
    assert reading["version"] == reading["drafts"]["general"]["version"] == 4


def test_admitting_a_send_settles_the_generation_it_carries(server, page_dir):  # noqa: F811
    """The send settles its own generation in every tab and device, and only that one."""
    publish(page_dir)
    for context, attempt in (
        ("general", "sent-attempt-00001"),
        ("reply:other", "kept-attempt-00001"),
    ):
        status, body = fetch(
            f"{server}/api/draft",
            data=json.dumps(
                {
                    "context": context,
                    "expect": None,
                    "record": {"attempt": attempt, "text": f"Words {attempt}"},
                }
            ).encode(),
        )
        assert status == 200, body
    comment = {
        "kind": "comment",
        "revision": 1,
        "text": "Words",
        "attempt": "sent-attempt-00001",
    }
    status, body = fetch(f"{server}/api/event", data=json.dumps(comment).encode())
    assert status == 200, body

    status, body = fetch(f"{server}/api/drafts")
    assert status == 200, body
    assert list(json.loads(body)["drafts"]) == ["reply:other"]


def test_a_draft_moves_the_tabs_news_and_nothing_the_page_or_agent_reads(
    server,  # noqa: F811
    page_dir,
):
    """A keystroke's write is news to the page's tabs, which read it from the document
    and `/api/drafts`, and no part of the page's reading or of `page state`."""
    publish(page_dir)
    words = "A thought the user hasn't sent."
    before = json.loads(fetch(f"{server}/api/news")[1])
    status, body = fetch(
        f"{server}/api/draft",
        data=json.dumps(
            {
                "context": "general",
                "expect": None,
                "record": {"attempt": "a1", "text": words},
            }
        ).encode(),
    )
    assert status == 200, body
    after = json.loads(fetch(f"{server}/api/news")[1])
    assert after["reading"] == before["reading"]
    assert after["drafts"] == before["drafts"] + 1

    status, document = fetch(f"{server}/")
    assert status == 200
    assert 'id="lf-drafts"' in document.decode() and words in document.decode()

    state = CliRunner().invoke(cli_model.cli, ["page", "state", str(page_dir)])
    assert state.exit_code == 0, state.output
    assert words not in state.output


def test_a_draft_of_the_wrong_shape_is_refused(server, page_dir):  # noqa: F811
    publish(page_dir)
    status, body = fetch(
        f"{server}/api/draft",
        data=json.dumps(
            {"context": "general", "record": {"text": "No attempt"}}
        ).encode(),
    )
    assert status == 400
    assert "invalid draft" in json.loads(body)["error"]
