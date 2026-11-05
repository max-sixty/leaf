"""The render pass on a real server and in a real browser. What a turn hands over is
read once it ends, and a failure reaches the agent and refuses a stamp."""

import json

import pytest
from click.testing import CliRunner
from interact_support import STATED_TIMEOUT, publish, wait_for
from render_harness import LONG_PAGE

from leaf import cli as cli_model
from leaf import event_log as log_model
from leaf import state as state_model
from leaf.files import latest_revision
from leaf.refusals import Refused
from leaf.render_gate import handover_pass as handover_pass_model


def test_a_turn_hands_a_failing_version_over_and_hears_about_it(
    claimed, headless_shell, monkeypatch
):
    monkeypatch.delenv(handover_pass_model.VARIABLE)
    state_model.prompt_turn("s1")
    (claimed / "index.html").write_text(
        LONG_PAGE.replace(
            "</main>", "<div id='too-wide' style='width: 2000px'>Wide.</div>\n</main>"
        )
    )
    runner = CliRunner()
    started = runner.invoke(cli_model.cli, ["server", "start", str(claimed)])
    assert started.exit_code == 0, started.output
    try:
        state_model.close_session_turn("s1")
        [told] = wait_for(
            lambda: [
                event
                for event in log_model.read_events(claimed)
                if event["kind"] == "render"
            ],
            bool,
            failure="the server told the agent nothing of the version it read",
            timeout=max(STATED_TIMEOUT, handover_pass_model.DEADLINE_S),
        )
        assert told["attention"] is True
        assert told["revision"] == latest_revision(claimed)
        failed = [f for f in told["findings"] if f["severity"] == "error"]
        assert failed, json.dumps(told)

        with pytest.raises(Refused) as refused:
            publish(claimed)
        assert failed[0]["text"] in str(refused.value)

        # The agent's own check of its fix leaves the reading the server would have
        # taken, so the turn that hands the fix over reads nothing again.
        (claimed / "index.html").write_text(LONG_PAGE)
        checked = runner.invoke(
            cli_model.cli, ["page", "check", str(claimed), "--render"]
        )
        assert checked.exit_code == 0, checked.output
        reading = handover_pass_model.read_reading(claimed)
        assert reading is not None and reading["findings"] == []
        assert publish(claimed)["kind"] == "note"
    finally:
        runner.invoke(cli_model.cli, ["server", "stop", str(claimed)])
