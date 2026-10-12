"""Preview and offline export tests."""

import time

from click.testing import CliRunner
from interact_support import (
    STATED_TIMEOUT,
)
from leaf import cli as cli_model
from leaf_dev import preview as preview_model
from render_harness import (
    leaf_page,
)


def test_a_watch_subscription_collects_before_its_first_read(tmp_path):
    """An edit made while nobody is reading the subscription is still in it.

    watchfiles starts its rust watcher on the subscription's first read, and the
    read a preview's loop makes comes after the preview has announced its URL —
    so the edit a developer makes the moment that URL appears used to land in a
    window nothing was watching. The interval here is that announcement: long
    enough that the write is over and reported by the platform before anything
    reads, which is what an unstarted subscription cannot survive.
    """
    edited = tmp_path / "source.html"
    edited.write_text("<p>authored</p>", encoding="utf-8")
    changes = preview_model.watch_changes(
        preview_model.Watched((tmp_path,), frozenset({str(edited)}), frozenset())
    )
    try:
        edited.write_text("<p>edited</p>", encoding="utf-8")
        time.sleep(1)
        reported = set()
        deadline = time.monotonic() + STATED_TIMEOUT
        while str(edited) not in reported:
            assert time.monotonic() < deadline, (
                f"the edit was never reported: {reported}"
            )
            reported |= next(changes)
    finally:
        changes.close()


def test_export_refuses_server_dependent_samples(serve, tmp_path):
    serve(
        leaf_page(
            "Live sample",
            '<lf-sample id="practice" label="practice">'
            '<template id="practice-source" data-sample><h1>Child</h1></template>'
            "</lf-sample>",
        )
    )
    output = tmp_path / "offline.html"
    result = CliRunner().invoke(
        cli_model.cli,
        [
            "page",
            "export",
            str(serve.page_dir),
            "--out",
            str(output),
        ],
    )
    assert result.exit_code != 0
    assert "Live samples need a server" in result.output
    assert not output.exists()
