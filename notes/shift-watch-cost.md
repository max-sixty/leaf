# Shift-watch cost

`tests/shift_watch.js` owns the Stability sensor and explains why Chrome's
layout-shift source rectangles cannot replace its landmark ledger. Its header
also describes the current reuse of unchanged readings. This note holds cost
evidence and remaining optimization work; `tests/AGENTS.md` owns test selection.

## Active-page cost

Four feature-gallery tests ran serially on an M-series Mac under other sessions'
load in October 2026, with one run per condition:

| CPU         | Unwatched | Watched |
| ----------- | --------: | ------: |
| Full speed  |    53.4 s | 119.1 s |
| 4× throttle |   150.9 s | 469.6 s |

## Gesture scroll judgement

Judging the scrolls a gesture makes ("Scrolls a gesture makes") adds one fresh
reading of the pressed control per input, and per frame only while a gesture that
called a scrolling API is still rendering. Timing the frame callback (`tick`) with
`performance.now()` in a scratch copy of the watch, at `--cpu-throttle 4`, serially
on an M-series Mac under other sessions' load in October 2026, over two runs each,
interleaved:

```sh
uv run pytest -n0 --cpu-throttle 4 \
  "tests/browser/test_render_send_placement.py::test_send_grows_thread_around_the_words[size0-0.4-False-False-False-False-browser]" \
  "tests/browser/test_render_send_placement.py::test_send_grows_thread_around_the_words[size4-0.4-scrolled-False-False-False-browser]" \
  tests/browser/test_render_floating_panel.py::test_the_thread_walk_stands_on_each_thread_it_opens \
  tests/browser/margin/test_card_placement.py::test_a_press_in_the_card_keeps_the_pressed_spot_still \
  tests/smoke/test_smoke.py::test_a_sent_margin_reply_shows_its_words_while_delivery_is_pending
```

| Watch  | Frames per run | Mean frame callback |  Wall time |
| ------ | -------------: | ------------------: | ---------: |
| Before |   1,372, 1,334 |       23.6, 23.1 ms | 96 s, 93 s |
| After  |   1,323, 1,306 |       23.3, 23.4 ms | 96 s, 96 s |

The difference is inside the run-to-run spread.

## Idle cost

The sensor's frame loop and paint checkpoint keep requesting frames on a still
page. In two October 2026 CI jobs, this cost 0.03–0.05 s of main-thread time and
0.04–0.065 s of CPU across processes for each second the page stayed open.
Rerun those historical measurements before estimating current savings.

## Open findings

- **Coverage exemptions need review.** Whether each `shifts_unsurveyed` module
  still needs its exemption hasn't been reviewed. Measure the cost of watching
  the affected tests before widening coverage.
- **The idle cost has a fix that changes the watch's self-check.** Stopping the
  frame loop while nothing is announced or running, and restarting it on the
  next announcement or layout-shift entry, would let a still page stop rendering.
  The VERIFY reading would then run only at judgement rather than every 30th
  quiet frame, so the user would decide whether that self-check is worth the
  idle cost.
- **Unconfirmed: a reading may lay a frame out twice.** `tick` runs in the frame's
  first callback, before the page's own frame callbacks write, so where those
  write, the browser may lay the frame out once for the reading and again to
  paint it. Reading after layout would change which pose a frame records, which
  the ledger's frame pairing rests on.
