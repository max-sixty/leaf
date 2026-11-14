"""The work-state scenarios (`work_scenarios.py`): each builds through the real doors,
and every moment it stops at serves a reading that holds the served state's schema."""

import pytest
from interact_support import served_state_error
from work_scenarios import SCENARIOS, Stage, served


@pytest.mark.parametrize("key", SCENARIOS)
def test_every_checkpoint_serves_a_reading_that_holds_its_schema(
    key, claimed, tmp_path
):
    scenario = SCENARIOS[key]
    stage = Stage(claimed, tmp_path)
    names = []
    try:
        for checkpoint in scenario.build(stage):
            names.append(checkpoint.name)
            stage.publish_row(*checkpoint.pages)
            for page in (claimed, *checkpoint.pages):
                assert served_state_error(served(page, checkpoint.after)) is None, (
                    f"{scenario.title}, {checkpoint.name}: {checkpoint.story}"
                )
    finally:
        stage.close()
    # A reader names a moment by its checkpoint, so a scenario names each once.
    assert names and len(names) == len(set(names))
