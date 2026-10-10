"""A live comparison shares authored edits and owns both foreground previews."""

import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

import pytest
from interact_support import STATED_TIMEOUT, wait_for
from leaf_dev.arms import environment


@pytest.mark.parametrize(
    ("user", "harness"), [(False, "claude-code"), (True, "claude-code"), (True, None)]
)
def test_compare_follows_shared_source_and_stops_both_arms(
    tmp_path, spawn, user, harness
):
    source = tmp_path / "comparison.html"
    source.write_text(
        '<!doctype html><html><head><title>Compare</title></head><body><main><p id="value">Initial source</p></main></body></html>'
    )
    log = tmp_path / "compare.log"
    env = environment(
        LEAF_PREVIEWS_ROOT=str(tmp_path / "previews"),
        XDG_STATE_HOME=str(tmp_path / "state"),
    )
    if harness == "claude-code":
        env |= {
            "CLAUDE_CODE_SESSION_ID": str(uuid.uuid4()),
            "CLAUDE_PID": str(os.getpid()),
        }
    with log.open("w") as stream:
        process = spawn(
            [
                sys.executable,
                "-m",
                "leaf_dev.compare",
                "--base",
                "HEAD",
                "--source",
                str(source),
                *(["--user"] if user else []),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=env,
        )

        def announced():
            assert process.poll() is None, log.read_text()
            return dict(
                re.findall(
                    r"^(baseline|candidate): (http://\S+)$",
                    log.read_text(),
                    re.MULTILINE,
                )
            )

        urls = wait_for(announced, lambda value: len(value) == 2, failure=log.read_text)

        def contents(url):
            with urllib.request.urlopen(url) as response:
                return response.read().decode()

        for url in urls.values():
            assert "Initial source" in contents(url)
        source.write_text(source.read_text().replace("Initial source", "Shared edit"))
        for url in urls.values():
            wait_for(
                lambda url=url: contents(url),
                lambda body: "Shared edit" in body,
                failure=log.read_text,
            )
        if user:
            baseline = next((tmp_path / "previews").glob("*-baseline"))
            subprocess.run(
                [sys.executable, "-m", "leaf", "server", "stop", str(baseline)],
                env=env,
                check=True,
                capture_output=True,
            )
        else:
            process.terminate()
        process.wait(timeout=STATED_TIMEOUT)
    for url in urls.values():
        with pytest.raises(urllib.error.URLError):
            contents(url)
