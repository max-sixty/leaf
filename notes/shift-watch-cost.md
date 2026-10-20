# What the shift watch costs, and the cheaper gate we didn't land

`tests/shift_watch.js` enforces the Stability rule (`skills/leaf/assets/AGENTS.md`,
"Stability") by keeping a ledger of where everything on the page stands and re-reading
it after each change. This note records what that costs, an alternative that was built,
measured and dropped in October 2026, and what would make it worth revisiting.

## Where the cost lands

- **Few tests pay it.** Of 3,896 browser, smoke and journey tests, 2,699 sit in modules
  marked `shifts_unsurveyed` and run without the watch. It watches 1,197, and 412 of
  those are its own tests.
- **Watched tests pay a lot.** Comparing the ledger with the gate below, serial runs,
  mean of 3, on the source runtime before #2767:

  | selection                          | ledger |          gate |
  | ---------------------------------- | -----: | ------------: |
  | 6 typing-heavy tests               | 27.3 s | 19.9 s (−27%) |
  | 4 tests opening many sample frames | 25.6 s | 15.5 s (−39%) |
  | 13 ordinary interaction tests      | 20.3 s | 18.1 s (−11%) |

  The four tests whose subject is the feature gallery took, serially on an M-series
  Mac under other sessions' load, one run each (October 2026):

  | CPU         | unwatched | watched |
  | ----------- | --------: | ------: |
  | full speed  |    53.4 s | 119.1 s |
  | 4x throttle |   150.9 s | 469.6 s |

  The two in `tests/browser/`, which run on each push to main, take 35.1 s of the
  unwatched and 77.9 s of the watched full-speed time.

- **The time goes on full readings of frames where something changed**: page load,
  sample frames upgrading, trace playback, and the frames around each key. The ledger
  needs those readings to judge. A ledger-only variant that reused unchanged readings
  in child frames and read only the field during a key's rendering (51 lines, passing
  the watch's own tests) saved 1–2%.
- **A scroll-driven animation changes nothing between scrolls.** Until October 2026 the
  watch counted lf-toc's contents window, whose scroll-driven animation always reads as
  running, as motion, and read every node on every frame of any page with a contents
  list. That held the gallery at 15 frames a second watched against 60 unwatched, and
  timed a gallery test out at 4x throttle.
- **CI barely notices.** Browser tests run on pushes to main and nightly, about 3% of
  runner-hours. The saving matters to an agent running a watched test locally.

## The gate that was dropped

The gate made Chrome's `layout-shift` entries the default judge. It credited a move to
the watch's own record of which input caused each frame, never to Chrome's 500 ms
`hadRecentInput` window, which hid at least 7 real 28–74 px defects until #1494. It
compared each source's `previousRect` and `currentRect` against small per-frame
readings of the declared `data-lf-reflow` regions, and while the reader typed it read
only the field and its holders. The ledger stayed behind `LEAF_SHIFT_LEDGER=1`.

It was dropped because it judged less than the ledger, on the suite's one set of tests
that enforces Stability:

- **Missed moves.** Chrome names at most five sources per entry and reports boxes, not
  their contents. So the gate missed a box moving further than the container Chrome
  named, and a control beyond the five outside a `text` region. Catching either means
  reading every frame.
- **Wrong failures.** It didn't model the ledger's credits for animations an input
  started that outlive its rendering, floating surfaces placed by their solver, or
  `translate` slides (#2797). Those families stayed on the ledger.
- **Accretion.** Each exemption needed state the ledger already kept, and a review
  round found five cases the first version got wrong. 17 known gaps were recorded as
  strict expected failures.

## Revisit when

- **Browser tests return to the PR gate**, or watched tests grow to a large share of
  runner-hours, so the 11–39% reaches CI.
- **Chrome's entries carry more**: more than five sources, or the content a box
  carried.
- **A change already reads the declared regions every frame** for another reason, so
  the gate's extra state costs nothing.

## Open findings

- **Most browser tests are unwatched.** Whether each `shifts_unsurveyed` module still
  needs its exemption hasn't been reviewed. Watching more tests costs time, at the rates
  above.
