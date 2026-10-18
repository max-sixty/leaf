"""The product pages are Leaf documents using the site's composed vocabulary."""

import subprocess
import sys

from PIL import Image


def test_demo_recording_drives_the_browser_journey(tmp_path):
    output = tmp_path / "demo"
    # Not check=True: with the streams captured, the CalledProcessError it raises
    # names the command and the exit status and takes both of them down with it,
    # so a browser step that timed out and a server that never bound report the
    # same nothing. This is `open_page`'s complaint about "Failed to load
    # resource" one file over — carry what failed into the failure.
    recorded = subprocess.run(
        [sys.executable, "-m", "leaf_dev", "record-demo", "--output", output],
        capture_output=True,
        text=True,
        check=False,
    )

    assert recorded.returncode == 0, (
        f"leaf-dev record-demo exited {recorded.returncode}\n"
        f"{recorded.stdout}{recorded.stderr}".rstrip()
    )
    assert recorded.stdout.strip() == f"Recorded {output}"
    assert (output / "demo.gif").read_bytes().startswith(b"GIF89a")
    # One staged scene, photographed for each surface that shows it: the landing
    # page's figure in both schemes, and the card, at the 1.91:1 an unfurler draws.
    # Shot at that shape rather than cropped to it, so the banner survives the trip.
    for name, size in (
        ("session-light.png", (1280, 953)),
        ("session-dark.png", (1280, 953)),
        ("session-card.png", (1200, 630)),
    ):
        with Image.open(output / name) as still:
            assert still.size == size, name
