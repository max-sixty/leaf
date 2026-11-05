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

## The gallery's load, split

On November 5, 2026, on an M-series Mac under other sessions' load (one-minute
load 6–25), the feature gallery opened in a 1200×900 context with reduced motion
and waited for `wait_until_ready`, three interleaved rounds per arm:

| Arm                                  | To ready    | Complete readings                   |
| ------------------------------------ | ----------- | ----------------------------------- |
| `browser.unwatched`                  | 7.0–8.4 s   | none                                |
| Watched, reading every node          | 13.6–16.1 s | 85–99 of 5,913 nodes, 6.8–8.5 s     |
| Watched, leaving skipped content out | 9.5–10.9 s  | 92–94 of at most 2,923 nodes, 3.1 s |

The page presents at about 1.6 s. Its 16 live samples then report ready one
after another, the first at about 2.6 s and the last at 6.7–7.6 s, and the page
is ready within 0.1 s of the last. Its JavaScript profile spreads over many
runtime modules with none above 300 ms.

A complete reading costs about 14 µs a node. Of the gallery's 4,049 elements and
1,782 text nodes, about 3,700 stood in shut tabs and other skipped content, so
the watch now leaves skipped content out ("Skipped content" in its header). Of
the 2,160 nodes still drawn once the page settles, 223 elements lie within one
window-height of the 900-pixel window.

Of the gallery tests CI's daily run takes longest on, only
`test_the_feature_gallery_exercises_its_core_journeys` runs the shift watch:
`test_render_gate.py`, `test_render_pages.py` and `test_render_anchors.py` are
marked `shifts_unsurveyed`. Call seconds on the same Mac, `-n0`:

| Test                                                        | Every node | Skipped left out | No shift watch | No sensors |
| ----------------------------------------------------------- | ---------- | ---------------- | -------------- | ---------- |
| `test_page_fixture_renders[feature-gallery]`                | 110, 115   | 116, 110         | 109            | 113        |
| `test_the_feature_gallery_exercises_its_core_journeys`      | 63, 63     | 43, 44           | 19             | 20         |
| `test_an_anchor_written_from_the_mapped_revision_lands_...` | 25, 24     | 25, 24           | 23             | 24         |
| `test_real_page_passages_can_be_quoted[feature-gallery]`    | 24, 22     | 25, 22           | 22             | 23         |

`test_page_fixture_renders[feature-gallery]` spends about 55 s of its 110 s in
seven `wait_until_ready` calls, about 8 s per gallery load, and the rest in its
journeys' own probes. On CI's daily runs of November 4 and 5 the same seven calls
took 292 s and 327 s.

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
  skips nothing, such as `leaf-dev scaling`'s 512-section prose page, still pays
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
