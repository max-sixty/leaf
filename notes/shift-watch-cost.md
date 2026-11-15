# Shift-watch cost

`tests/shift_watch.js` owns the shift watch and explains why Chrome's
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

`tests/browser/test_render_floating_panel.py` (118 tests, `-n 3`) on October 25,
2026, with the watch removed by patching `render_harness.watches_shifts`, one run
per condition:

| CPU         |         Unwatched |            Watched |
| ----------- | ----------------: | -----------------: |
| Full speed  |   1.02 s per test |    1.28 s per test |
| 4× throttle | 288 CPU-s, 75.9 s | 422 CPU-s, 114.7 s |

The modules the watch covers, those not marked `shifts_unsurveyed`, took 22.7 of
the 161.5 CPU-minutes of main's push run 40168562615, 9.5 of them in that file.

A JavaScript profile of the same 118 tests (Chrome's sampler at 200 µs) found
about 53 s of script outside idle time, garbage collection and `(program)`, about
32 s of it in the suite's init scripts and most of that in the shift watch: `read`
17 s, the `getAnimations` calls behind `allAnimations` 4 s, `watchArrival` and
`tick` about 1 s each. `read`'s self time spreads over its per-node geometry and
style reads rather than gathering on one line, so a cheaper watch reads fewer
nodes or fewer frames rather than doing one read faster. `read` also enumerates
the composed tree's animations twice per frame, once through `readMotion`, and
`tick` again for each open rendering.

## The feature gallery's load

A complete reading costs about 14 µs a node, timed around `read()` in a scratch
copy of the watch while the gallery loads (November 2026); about 3,700 of the
gallery's 5,913 nodes stand in its shut tabs and other skipped content.

Each live sample's frame loads a Leaf runtime of its own, and the page's readiness
waits for every sample that has started. Until November 2026 every sample started as
it mounted, and the gallery's 17, 16 of them in shut tabs, took it from presenting at
about 2.1 s to settling at about 8.2 s on an M-series Mac. A sample now starts only
as it nears the window (`whenNear`, `browser/runtime/presentation.js`), so one
starts and the gallery settles at about 1.8 s; the probe below reports both.

```sh
uv run leaf-dev probe feature-gallery --motion reduce --viewport 1200x900 \
  --js "() => ({settled: Math.round(performance.now()), started: [...document.querySelectorAll('lf-sample iframe')].filter(frame => frame.hasAttribute('src')).length})"
```

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
On October 25, 2026, on an M-series Mac, a ready page left still for six seconds
cost about 25 ms of renderer CPU and 7 ms in Chrome's other processes per second
with the watch, and 3 ms of each without it; its page server's freshness polls
cost about 11 ms per second either way. Tests rarely leave a page still for long, so the active cost
above is the larger share of what the watch costs the suite.

## Open findings

- **A complete reading still grows with the drawn page.** Readings that skip
  unchanged frames (#1951), unpresented frames (#3281) and skipped content each
  cut the same cost, a full record of every node per changed frame. A page that
  skips nothing, such as `leaf-dev bench`'s 512-section prose page, still pays
  it in full: there the sensors added about 290 ms to a click (#5523). The
  runtime's input work follows what the window shows (root `AGENTS.md`,
  "Responsiveness"), and the watch could too: read each drawn node's rect and
  scroll offsets, about 1 µs a node on a clean layout, and the full record only
  for nodes within a band around the window in this reading or the last, with
  their rendered ancestors and scrollers. A box that jumps into the window from
  beyond the band without input would then have a rect but no record from before,
  so the user would decide what the watch owes that case.

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
