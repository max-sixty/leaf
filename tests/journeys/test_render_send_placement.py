"""Where a comment stands before and after Send: the comment box the user types in, and
the thread card the sent comment becomes.

Each case is one gesture at one window size: words selected in a long paragraph, or an
element pointed at with ⌥-click. It types a comment, reads where the box stands,
presses Enter, and reads where the card stands once placed. The snapshot records the
effect rather than the pixels, in one document a reviewer reads as a scoreboard, so a
change of a few pixels records nothing and a change in where either goes records a
line:

- `expected`: the side the case is built to give both.
- `side`: where each stands relative to what it is about: `right`, `left`, `below` or
  `above`. Where the case allows more than one side and the surface took one of them,
  it records the case's `expected`: which of under and over has more room turns on the
  fonts a platform draws the page in, and the snapshot is read on more than one.
  `moves` still says whether the card took the box's side.
- `stands`: whether it stands where that side puts it: beside the block `level with
  the words`, or `clear of the block` under or over it, else how far off.
- `moves`: how far the card stands from where the box stood, at the edge each holds
  (the left edge across; the top down, or the foot where the card stands above),
  bucketed `still` (the same place), `near` (a line or two) or `away`.

Each case also writes the pair it read to its test's `tmp_path/<case>.png`: the box as
the user typed in it on the left, the card on the right with the box's outline drawn
over it, so a move shows at a glance. After an intentional change, re-record and read
the diff beside those pictures:

  uv run pytest --regtest-reset -n0 tests/*/test_render_send_placement.py"""

from browser.test_render_send_placement import CASES, sent
from interact_support import yaml_document


def test_where_a_comment_stands_before_and_after_send(
    browser, serve, snapshot, tmp_path
):
    snapshot.check(
        yaml_document(
            "Where each case's comment box, and the thread card it became, stand.",
            {name: sent(browser, serve, name, tmp_path) for name in CASES},
        )
    )
