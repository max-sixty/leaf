"""The user's drafts on the page's server (`leaf.drafts`): a write takes only the
generation it names, admitting a send settles the generation it carries, and tabs hear
drafts through their own news, which moves no reading of the page and reaches no part of
what the agent reads."""

import json

from click.testing import CliRunner
from interact_support import fetch, publish, server  # noqa: F401 (fixture)

from leaf import cli as cli_model
from leaf import drafts as drafts_model
from leaf.event_log import append_event, start_log


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
    """A tab replaces a generation it knows the server may hold, so words another tab
    wrote or sent meanwhile come back to it rather than being overwritten."""
    assert _write(tmp_path, [], "a1")["written"]
    refused = _write(tmp_path, [], "a2")
    assert not refused["written"]
    assert refused["record"]["attempt"] == "a1"
    assert _write(tmp_path, ["a1"], "a2", "Newer words")["written"]
    settled = drafts_model.write_draft(
        tmp_path,
        {
            "context": "general",
            "expect": ["a2"],
            "record": {"attempt": "a2", "settled": True},
        },
    )
    assert settled["written"]
    assert drafts_model.read_drafts(tmp_path)["drafts"] == {}
    # A tab that never heard of the settled generation starts the next one.
    assert _write(tmp_path, [], "a3", "A new thought")["written"]
    # A tab still holding the settled generation's predecessor hears the new one back.
    stale = _write(tmp_path, ["a1"], "a4")
    assert not stale["written"]
    assert stale["record"]["text"] == "A new thought"
    reading = drafts_model.read_drafts(tmp_path)
    assert reading["drafts"]["general"]["attempt"] == "a3"
    assert reading["version"] == reading["drafts"]["general"]["version"] == 4
    # A write that can't know which of two generations the store holds names both.
    assert _write(tmp_path, ["a2", "a3"], "a5")["written"]


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
                    "expect": [],
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
    before = json.loads(fetch(f"{server}/api/news")[1])["drafts"]
    status, body = fetch(f"{server}/api/event", data=json.dumps(comment).encode())
    assert status == 200, body
    # Every tab hears the send settle its draft at its next look.
    assert json.loads(fetch(f"{server}/api/news")[1])["drafts"] > before

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
                "expect": [],
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


def test_the_log_settles_every_generation_it_admitted(tmp_path):
    """The log answers whether words were sent, so they never come back as a draft: not
    from a tab's write that lands after its send, however many sends came between, nor
    from a store whose last reading came before the send."""
    start_log(tmp_path)
    assert _write(tmp_path, [], "a1", "Words")["written"]
    for n in range(100):
        append_event(tmp_path, {"kind": "comment", "text": "Sent", "attempt": f"s{n}"})
    late = _write(tmp_path, ["a1"], "s0", "Words, sent")
    assert late["written"]
    assert late["record"] is None
    assert drafts_model.read_drafts(tmp_path)["drafts"] == {}

    sending = _write(tmp_path, [], "a2", "Words a tab in another window shows")
    append_event(tmp_path, {"kind": "comment", "text": "Sent", "attempt": "a2"})
    reading = drafts_model.read_drafts(tmp_path)
    assert reading == {"version": sending["version"] + 1, "drafts": {}}
    assert _write(tmp_path, [], "a3", "A new thought")["written"]


def _post(page_dir, expect, record, **write):
    return drafts_model.write_draft(
        page_dir, {"context": "general", "expect": expect, "record": record, **write}
    )


def test_a_write_landing_after_its_words_were_put_away_leaves_them_away(tmp_path):
    """A Cancel was undone by a write of the same words landing after it, as a closing
    tab's resend can, since the store kept nothing of a draft it settled. It now
    remembers the last generation it settled of each draft, so that write settles it
    again, while words typed over it still start the draft again."""
    assert _write(tmp_path, [], "a1")["written"]
    assert _post(tmp_path, ["a1"], {"attempt": "a1", "settled": True})["written"]
    assert _write(tmp_path, ["a1"], "a1")["record"] is None
    assert drafts_model.read_drafts(tmp_path)["drafts"] == {}
    assert _write(tmp_path, ["a1"], "a2", "Typed over them")["written"]


def test_a_replay_of_words_replaced_before_their_settling_is_turned_away(tmp_path):
    """A page's next load replays the writes a closing tab queued while the server was
    out of reach, maybe long after. Words another device replaced and then sent or put
    away meanwhile stay away; words queued after the settling stand."""
    assert _write(tmp_path, [], "g")["written"]
    queued = drafts_model.read_drafts(tmp_path)["version"]
    assert _write(tmp_path, ["g"], "h", "Edited elsewhere")["written"]
    assert _post(tmp_path, ["h"], {"attempt": "h", "settled": True})["written"]
    replay = _post(tmp_path, ["g"], {"attempt": "g", "text": "Words"}, since=queued)
    assert not replay["written"]
    assert drafts_model.read_drafts(tmp_path)["drafts"] == {}
    later = drafts_model.read_drafts(tmp_path)["version"]
    fresh = {"attempt": "k", "text": "Queued after"}
    assert _post(tmp_path, [], fresh, since=later)["written"]
