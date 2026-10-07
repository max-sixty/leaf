"""Capture a Playwright journey with its native trace and screencast.

`recording(page, directory)` works with any Playwright page, independently of Leaf.
It must start before navigation; it owns tracing and screencasting on that context.
The trace is native evidence for Playwright's viewer and Leaf's review package. Video
and optional GIF retain actual frame timing, without inserting demonstration waits.
Action decorations are opt-in: Playwright waits 500 ms before each annotated
input, so they are for demonstrations rather than timing-sensitive reproductions.
Native video holds the final frame for at least one second. Artifacts
are finalized even when a journey raises, so failures remain inspectable.
"""

import io
import time
from collections.abc import Iterable
from contextlib import contextmanager
from itertools import pairwise
from pathlib import Path

from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page


def write_gif(
    frames: Iterable[Image.Image], durations: list[int], output: Path
) -> None:
    """Encode captured frames with their durations into a looping GIF.

    Chrome can send a smaller initial frame while applying the viewport. GIF has
    one logical canvas, so pad smaller frames to the largest captured dimensions;
    never scale text or let the first frame crop the rest of the recording.
    """
    palette_frames = [
        frame.quantize(colors=192, method=Image.Quantize.MEDIANCUT) for frame in frames
    ]
    size = (
        max(frame.width for frame in palette_frames),
        max(frame.height for frame in palette_frames),
    )
    for index, frame in enumerate(palette_frames):
        if frame.size != size:
            canvas = Image.new("RGB", size, "white")
            canvas.paste(frame)
            palette_frames[index] = canvas.quantize(
                colors=192, method=Image.Quantize.MEDIANCUT
            )
    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )


@contextmanager
def recording(
    page: Page, directory: Path, *, gif=False, actions=False, checkpoint_images=False
):
    """Write trace.zip and video.webm, and optionally a short journey's GIF.

    GIF encoding buffers frames in memory; video and trace stream to disk. Start
    screencasting first so tracing shares the viewport-sized frame stream rather
    than imposing its smaller thumbnail dimensions. Close this before the page.
    If the journey closes its page, the live context still saves its trace and
    buffered GIF frames, but Playwright cannot save the screencast's video.
    Accessibility snapshots supply saved-element targets. `checkpoint_images`
    adds native PNG images at action phases for checkpoint review. Taking them adds
    capture work and temporarily hides the live caret, so ordinary motion capture
    leaves them off; the filmstrip and video then retain ordinary caret paint.
    The directory's three generated filenames belong to this capture: retire
    previous outputs first so a repeat cannot mix evidence from different runs.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for filename in ("trace.zip", "video.webm", "recording.gif"):
        (directory / filename).unlink(missing_ok=True)
    frames = []

    def receive(frame):
        if gif:
            frames.append(frame)

    page.screencast.start(
        on_frame=receive if gif else None,
        path=directory / "video.webm",
        size=page.viewport_size,
    )
    completed = False
    try:
        page.context.tracing.start(
            screenshots=True,
            snapshots=True,
            aria_snapshots=True,
            screen_snapshots=checkpoint_images,
            sources=True,
        )
        try:
            if actions:
                page.screencast.show_actions()
            yield
            completed = True
        finally:
            try:
                if actions and not page.is_closed():
                    page.screencast.hide_actions()
            finally:
                page.context.tracing.stop(path=directory / "trace.zip")
    finally:
        if not page.is_closed():
            page.screencast.stop()
        if gif and frames:
            images = (
                Image.open(io.BytesIO(frame["data"])).convert("RGB") for frame in frames
            )
            timestamps = [frame["timestamp"] for frame in frames] + [time.time() * 1000]
            durations = [
                max(10, round((end - start) / 10) * 10)
                for start, end in pairwise(timestamps)
            ]
            write_gif(images, durations, directory / "recording.gif")
        if page.is_closed() and completed:
            raise PlaywrightError(
                "the journey closed its page; video could not be saved"
            )
