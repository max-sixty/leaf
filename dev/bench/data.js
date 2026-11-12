window.BENCHMARK_DATA = {
  "lastUpdate": 1794483385083,
  "repoUrl": "https://github.com/max-sixty/leaf",
  "entries": {
    "Bench at 64 sections": [
      {
        "commit": {
          "author": {
            "name": "Maximilian Roos",
            "username": "max-sixty",
            "email": "5635139+max-sixty@users.noreply.github.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "62cb54fc8b767e0b8759326593daee7d1f76202f",
          "message": "Say a Resolve's Undo and its key at the panel field's end, where Comment… c stands (#5613)\n\nAfter a Resolve, the panel's field now says *Resolved \"…\"* as its words\nand *Undo* `z` at its right end, in the same dim italic and key badge as\n*Comment…* `c`. The rule behind it: a box's right side holds the\nshortcut that matters most right now.\n\nBefore this change, the notice drew *Resolved \"…\" · Undo z* over the\nfield's start on a line of its own, and Undo was the only press in the\nrow with a face of its own: inked and semibold.\n\n- **The box owns its end press.** `enters`\n(`browser/runtime/composing/input.js`) can return a `BoxPress`, `{word,\nkeys, run}`, in place of a string. The box renders it into a new `end`\nslot of `leaf-text` (`text-field.js`), at the placeholder's far end, and\ntakes the press itself. Only the placeholder's words are hidden from\nassistive technology, so a screen reader finds the press as a button\nnamed Undo. The press is visible exactly when the field's words are, it\nfollows the field's text direction, and the words shorten before it.\nWhile the slot holds a press, the field raises the placeholder over the\nempty line so the press gets the pointer, and a press on it never\nfocuses the field. The element is built by the inline role, and its\n`data-lf-hint` variant gives it the empty field's face, without the\nhover wash (`control-faces.js`, `controls.css`).\n- **The panel hands the notice's press to the field.** `fieldReading`\n(`floating-panel.js`) returns it as `offer`. The page box and the thread\nreply box both pass it to `enters`. The overlay button, its anchor\npositioning and `rowNotice`'s passing branch are deleted, so the row's\nnotice is now only the chip for an older version.\n- **Errors wait while a notice's press stands.** An error the field\nwould say counts as unsaid until the notice passes, so it waits in the\nmenu's Errors list with the leaf's dot instead of going unshown.\n- **Keys:** `z` stays the keyboard route. The press has no tab stop,\nsince the first Tab retired the notice before it could reach the old\nbutton. Touch screens show *Undo* alone, as every box shows no keys\nthere.\n\nTests: the Undo notice tests read the field's words and its end, and\nread the press from Chromium's accessibility tree (`accessible_node` in\n`tests/render_harness.py`), since Playwright's role locator misses\n`aria-hidden` on a shadow ancestor of slotted content.\n`test_resolving`'s way-back route now clicks the field's press. The\nnarrow-box test now checks that the seat's longer label shortens at\nphone width, because the panel's *Comment…* fits there with both keys\nsince #5448.\n\n> _This was written by Claude Code on behalf of max-sixty_",
          "timestamp": "2026-11-06T10:34:19Z",
          "url": "https://github.com/max-sixty/leaf/commit/62cb54fc8b767e0b8759326593daee7d1f76202f"
        },
        "date": 1793965354700,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1381.62,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 60.83,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 11.53,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 68.16,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 30.74,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.96,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 429.97,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 398.39,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 131.23,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 507.57,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 100.47,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 31.62,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 92.25,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 338.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 670.22,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 68.74,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 18.47,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 50.05,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 54.5,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 10.87,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 178.39,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 144.72,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 124.43,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 299.15,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 130.09,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 50.27,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 51.3,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 267.7,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 526.9,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 39.33,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 11.13,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 34.96,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 29.1,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.29,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 69.56,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 79.79,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 82.55,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 226.37,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 86.55,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 25.9,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 35.25,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 219.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 565.27,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 36.91,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.65,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 46.95,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 61.99,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 5.13,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 85.23,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 82.78,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 61.05,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 235,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 79.26,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 24.06,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 39.4,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 248,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 847.12,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 61.09,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 11.61,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 57.02,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 57.79,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 5.47,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 190.68,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 193.62,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 96.27,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 303.66,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 105.91,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 38.01,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 56.5,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 330.1,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "leaf-agent",
            "username": "leaf-agent",
            "email": "l@leaf.page"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "391c24622d06c03d62eeb1e8862fbf6e1fc81998",
          "message": "Draw the contents map inside its sidebar track (#5637)\n\nThe contents map in a document sidebar is now an ordinary block in its\ntrack, with its labels always shown, instead of a fixed 24px spine that\nrevealed labels over the body on hover. That deletes the overlay and the\npatches each side carried for it, and the sidebar's reserved width now\nholds the labels instead of standing blank (#5619). Approved direction:\n[#5619\n(comment)](https://github.com/max-sixty/leaf/issues/5619#issuecomment-6705043478).\n\n**Before** (`contents-map-keyboard`, 1440×900, focus on a map link): the\nlabels lie over the first words of the prose.\n\n\n![Before](https://github.com/user-attachments/assets/6f8dfbe7-3976-42e1-892e-35afa111b033)\n\n**After**: the same map in its own track. Nothing covers the prose, and\nthe column starts where it did.\n\n\n![After](https://github.com/user-attachments/assets/1539b02b-af76-4a06-8a51-842ff6dac939)\n\n**Removed**\n- `layouts.css`: the aside's `z-index` and the body's `isolation`, which\nexisted only so the revealed labels covered the body (#5117).\n- `toc.css`: the reveal machinery (`:hover` / `[data-lf-focus-within]` /\ngo-to widening, the press strip on the spine, `pointer-events` toggling,\nthe label fade) and the `lf-toc + :not(.lf-ui)` clearance rule with its\nrestyle-cost notes (#5309, #5363, #5370).\n- Render checks: `restsOverPage`, the resting-overlay exemption from the\nwidth floor and from the margin readings (#3109).\n\n**What users see change**\n- No quiet resting state: the labels always show, and pressing a label\nfollows it directly.\n- The map's height fits the stuck track at the document's end, so its\nstart stays in the window (about 700px at a 900px window, was 828). Once\nits sidebar ends, the map scrolls away with it, as any sticky block\ndoes.\n- A block after the map in the track now follows it below, where\nscrolling the track reaches it. Before, it stood at the track's top\nbeside the spine. `page-layout.md` and `page-authoring.md` now say this\nand suggest putting a status the reader should see at once at the top of\nthe body. No example or `docs/` page puts anything after the map.\n- Labels wrap at the track's width (~210px, was ~320px), so close\nsections pack together one label apart sooner.\n\n`--lf-sidebar-slot` stays. It still tells the map (margin) apart from\nthe open outline (beside); merging the two is a separate call.\n\n**Verification**: I ran these locally and they pass: the rewritten\njourney\n`test_a_margin_table_of_contents_maps_the_document_in_its_track`,\n`tests/browser/test_render_toc_disclosure.py`, the contents tests in\n`test_contents_and_glosses.py`, the go-to hints test, and the render\ngate on `sidebar-contents`. The npm-based gates (`pnpm run check`,\nprettier, eslint) have no `node_modules` in this sandbox, so they're\nleft to CI.\n\n<details><summary>Test changes</summary>\n\n- Rewritten to the in-track map: the margin-map journey (the reveal,\nhover and spine-width steps are gone; it now checks the map stays clear\nof the body, stays put while its track is stuck, and stays clear of the\npanel's room), the history, hidden-sidebar and crowded-map tests, the\n\"map only beside the body\" test, and the go-to hints test.\n- The status-line test now asserts the status follows the map and a\npress on it reaches it.\n- Deleted, since their subject is gone:\n`test_the_revealed_margin_map_covers_every_box_the_body_paints` and\n`test_the_gate_passes_a_contents_map_resting_as_its_spine`.\n- Stills: `contents-over-reading` is deleted, and\n`contents-spine-keyboard` is renamed `contents-map-keyboard`.\n\n</details>\n\nCloses #5619\n\n---------\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-11-07T10:19:59Z",
          "url": "https://github.com/max-sixty/leaf/commit/391c24622d06c03d62eeb1e8862fbf6e1fc81998"
        },
        "date": 1794051532463,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1120.78,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 47.85,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.29,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 48,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 26.02,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.33,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 309.25,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 309.14,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 93.55,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 346.5,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 95.84,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 28.52,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 50.75,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 300.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 607.8,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 52.39,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.93,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 40.64,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 47.35,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.9,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 140.87,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 128.36,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 91.47,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 291.51,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 117.79,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 43.95,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 37.45,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 206.5,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 469.64,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 28.48,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.14,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 32.24,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 28.14,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.75,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 58.69,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 63.48,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 58.33,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 212.7,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 77.34,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 20.76,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 37.35,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 185.8,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 496.86,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 28.51,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 9.48,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 39.88,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 55.08,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.1,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 72.64,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 72.26,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 52.96,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 195.86,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 78.54,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.44,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 31.7,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 206.7,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 642.47,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 53.7,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 10.18,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 45.96,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 55.81,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.32,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 98.94,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 115.38,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 70.76,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 315.65,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 91,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 25.89,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 48.8,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 233.3,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "leaf-agent",
            "username": "leaf-agent",
            "email": "l@leaf.page"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "f926f4fa77db74971e9445ea1b903788ddb7ebfb",
          "message": "test: let 24 preview, mark and chart waits take the suite's deadline (#5701)\n\nThe nightly journey `test_a_wait_takes_the_suites_deadline` has failed\nsince scheduled run\n[42365682113](https://github.com/max-sixty/leaf/actions/runs/42365682113).\nIt found 24 waits with literal 2 s or 3 s timeouts, added by #5617\n(`test_previews.py`, `test_charts.py`) and #5618\n(`test_render_anchors.py`). This PR drops each `timeout=` argument, so\nthose waits take the suite's default deadline (`SERVED_TIMEOUT_MS`,\nwhich `render_harness` sets). What each wait waits for doesn't change.\nThe literal values were sized to a fast machine, which is why the check\nrejects them.\n\nVerification on main `fcad5fa09`: the check fails before this change,\nlisting all 24 sites, and passes after it. The 19 browser tests that\nhold those waits pass under `--run-main` (42 cases).\n\nThe same check went red for the same reason on Nov 5, and #5455 fixed\nthat. It's a 2–6 s static scan of the test sources, but it lives in\n`tests/journeys/`, which only the scheduled run reaches. So a pull\nrequest that adds a literal deadline passes its own CI, and main finds\nout the next day. The durable fix is to run this check on every pull\nrequest; I'm filing that separately.\n\nRefs #4225 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-08T08:36:06Z",
          "url": "https://github.com/max-sixty/leaf/commit/f926f4fa77db74971e9445ea1b903788ddb7ebfb"
        },
        "date": 1794137996498,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1016.07,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 41.31,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 8.67,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 41.03,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 30.74,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.49,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 284.28,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 269.96,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 89.75,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 339.65,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 85.36,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 22.29,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 42.95,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 269.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 517.11,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 48.25,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 14.31,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 39.89,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 52.73,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 9.08,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 139.39,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 132.37,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 75.13,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 228.01,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 106.62,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 39.81,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 37.5,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 191.7,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 413.53,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 26.07,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 8.93,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 27.13,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 30.29,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.97,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 56.55,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 80.76,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 54.69,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 202.34,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 86.22,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 19.91,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 31.4,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 157.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 440.5,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 24.16,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 8.25,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 39.07,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 56.57,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.85,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 70.23,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 71.93,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 51.63,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 194.37,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 74.9,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 18.47,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.25,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 195.2,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 535.89,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 45.04,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 8.82,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 41.12,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 55.86,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.99,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 98.33,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 95.73,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 72.2,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 247.06,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 99.86,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 22.82,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 44.75,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 227.2,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "leaf-agent",
            "username": "leaf-agent",
            "email": "l@leaf.page"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "28c3b37f3bf20a062ec183766b77c1d01b239e1a",
          "message": "test: read the Firefox send flash only from frames that drew the settled card (#5749)\n\n`test_firefox_paints_the_author_and_words_in_the_same_send_flash` failed\nintermittently: 3 of 10 local runs on `main`, plus the scheduled run\nthat #5710 cites. Its frame filter let through screencast frames that\nsay nothing about the sent message's grounds. On a loaded runner, its\nfade-density check also failed on real fades. The assertion that the\nauthor's row and the words fade together is unchanged and still catches\na head that lags its words. Test-only; no product behavior changes.\n\n**Frames that were getting through**, from frames captured in failing\nlocal runs:\n\n- **Stale page content over the card.** Headless Firefox sometimes\ncomposites a band of earlier page content (here, the diff widget) over\nthe card. The existing check compares the card's right edge on both\nrows, but the band can cover the author's row and stop short of that\nedge, leaving the author's row reading the page's white `(255, 255,\n255)`. This is the frame in the failing [scheduled\nrun](https://github.com/max-sixty/leaf/actions/runs/42365682113): head\n`(255, 255, 255)`, words `(253, 249, 222)`, both edges `(250, 249,\n245)`.\n- **The card still growing.** In the first frame of the arrival, the\nreply field still covers the words. The words' sample, 3px above the\nmessage's foot, read a blend of field and highlight, e.g. head `(255,\n249, 199)` against words `(253, 251, 230)`.\n\n**The filter now:**\n\n- Samples the words at the middle of their row, beside the short\nsentence.\n- Reads a frame only when three things hold: the card's edge matches on\nboth rows; the author's row shows a colour the message's ground can take\n(its yellow, the card's paper, or a mix), which the page's white fails;\nand the reply field's top ring reads as it does in most of those frames,\nso the card has grown into place.\n- Takes that ring majority only over frames that already passed the\nfirst two checks, because under load the band frames can outnumber the\nrest.\n\n**Fade density.** The test required three distinct fade colours at least\n12 apart. On this PR's loaded CI runner it captured only two frames\ninside the fade. Locally, under five busy loops on four cores, it often\ncaptured two colours, or several within 8 of each other. The check\nexists to reject a discrete jump (no intermediate colour) and the\nconstant 0.5 pending blend (one colour plus JPEG jitter). It now\nrequires intermediate colours more than 6 apart, which still rules out\nboth.\n\n**Verification** (local Linux, `--run-nightly -n0`):\n\n- `main`: 3 of 10 runs failed.\n- This head: 10 of 10 pass idle and 12 of 12 under five busy loops.\nBefore the density change, the filter alone passed 50 of 50 idle and 8\nof 8 under two busy loops.\n- Injecting a head that stays 60% highlighted (`.lf-margin-preview\n.lf-msg-head { background: color-mix(in srgb, #fff8c5 60%, var(--paper))\n!important }`) still fails the head-against-words assertion.\n\nThe test came in with #1933, and its edge filter with #3100. The next\nscheduled `ci` run will settle the macOS lane.\n\nCloses #5710 — automated triage\n\n---------\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-09T10:24:09Z",
          "url": "https://github.com/max-sixty/leaf/commit/28c3b37f3bf20a062ec183766b77c1d01b239e1a"
        },
        "date": 1794224217844,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 862.42,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 39.62,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 6.72,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 31.94,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 25.24,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.53,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 232.96,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 209.04,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 74.67,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 268.88,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 83.11,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 25.3,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 45.35,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 246.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 478.55,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 44.38,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 13.63,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 30.36,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 43.73,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 7.85,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 109.81,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 112.84,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 68.99,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 222.26,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 102.27,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 36.63,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 37.1,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 153.1,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 364.35,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 24.74,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 8.3,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 28.12,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 30.12,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.24,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 54.38,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 65.58,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 55.62,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 190.12,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 75.58,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 21.15,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.3,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 146.2,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 395.35,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.7,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 8.67,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 34.92,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 48.7,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.33,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 61.33,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 63.5,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 51.37,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 181.86,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 60.45,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 18.5,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 31.8,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 164.8,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 472.27,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 38.21,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 6.73,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 34.42,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 46.81,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.24,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 82.08,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 86.25,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 72.72,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 199.54,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 72.2,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 21.91,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 52.15,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 197.7,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "leaf-agent",
            "username": "leaf-agent",
            "email": "l@leaf.page"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "e6756ad433b930c9cc8db95be485477b41723a61",
          "message": "test: keep the shift watch's input rendering open while its scroll's work is pending (#5795)\n\nThe shift watch closed a wheel's rendering before the wheel's own scroll\nhad finished drawing. That made\n`test_a_standing_preview_takes_its_place_again_as_what_holds_it_changes`\nfail intermittently, with the preview's word reported as moved without\ninput. The runtime was already doing the right thing. It re-places the\npreview in the frame where the scroll reaches the page, which\n`AGENTS.md` **Responsiveness** asks for.\n\n**Cause.** Chrome delivers a wheel's scroll to the main thread one frame\nafter the wheel event. If the loop read as settled on the watch's first\ntick after the wheel, the watch ended the rendering on its next tick and\nnever checked the loop again. In that same frame, the preview's scroll\nlistener had queued `decide` (`preview.js`, `nextRender`), which ran\njust after the watch's tick. So the paint that moved the preview's side\ncame after the credited window. This happened only on a slow CPU, where\nthe scroll and the decision fell into the closing tick's frame.\n\nTimeline from a failing copy at `--cpu-throttle 6`, in page\nmilliseconds:\n\n| ms | event |\n|---|---|\n| 34644 | wheel |\n| 34672 | scroll event; preview queues `decide` |\n| ~34811 | watch tick closes the wheel's rendering |\n| 34812 | the decision runs |\n| 35008 | the paint shows the move, uncredited |\n\n**Change.** The rendering now ends only if the loop still reads as\nsettled at the tick that would end it. Otherwise it continues until the\nloop settles, which is already how the watch treats work pending at the\nfirst reading. Preparation landings follow the same rule. Pages without\nthe Leaf runtime always read as settled, so nothing changes for them.\n\n**Verification.** I ran `uv run leaf-dev flake --cpu-throttle 6` on the\ntest at current `main`. Without the change, 14 of 18 copies fail with\nthe reported message. With it, 18 of 18 pass, and also 18 of 18 at\nthrottle 12. The 57 tests in `tests/browser/test_render_shift_watch.py`\nselected by `-k \"news or passive or settle or wheel or prepar or landing\nor completion or later\"` pass.\n\nCloses #5792 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-10T09:27:28Z",
          "url": "https://github.com/max-sixty/leaf/commit/e6756ad433b930c9cc8db95be485477b41723a61"
        },
        "date": 1794310946399,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1299.63,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 52.24,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 11.17,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 53.85,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 40.39,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.99,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 353.16,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 359.13,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 106.86,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 422.11,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 102.99,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 30.04,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 55.25,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 341.6,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 721.93,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 60.36,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 19.25,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 46.14,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 66.24,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 11.93,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 170.55,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 140.83,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 152.65,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 295.54,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 147.87,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 44.28,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 43.05,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 247.8,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 532.67,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 33.08,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 11.31,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 35.59,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 39.95,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.38,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 70.48,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 83.48,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 74.95,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 256.81,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 93.33,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 22.74,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.2,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 216.4,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 566.84,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 31.02,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.81,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 43.84,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 70.61,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 5.09,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 84.78,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 85.06,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 58.59,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 233.86,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 89.47,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 21.1,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 36,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 224.4,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 743.12,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 58.7,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 11.85,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 51.03,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 74.01,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 5.53,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 123.94,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 125.77,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 96.58,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 335.07,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 114.41,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 34.87,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 52,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 291.8,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "leaf-agent",
            "username": "leaf-agent",
            "email": "l@leaf.page"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "a52abb1bb667f068a6a358c899cc634b644215c7",
          "message": "fix: expect a margin card's reply box, not its ground, to move when a refused reply returns its room (#5831)\n\nThe refused-reply journey's `[margin]` case expected the wrong thing to\nmove. #5770 deliberately made a margin card hold its top through a send.\nSo when a refused reply's turn is removed, the head row stays put and\nthe reply box rises into the freed room, 101px here. Before #5770 the\ncard held its foot, and the whole card's ground moved down 80px. The\ntest's `carried_by_card` allowance still matched only\n`div.lf-box-ground.lf-margin-preview-ground`. The ground no longer\nshifts, so Chrome doesn't list it beside the move, and the allowance\nrefused the reply field's move.\n\nThis replaces the ground in the allowance with the reply box\n(`div.lf-thread-reply`), so the accepted set doesn't grow. A new\nassertion, for the margin case only, checks that the card's close button\nin the head row keeps its top. That is the behavior #5770 meant to\nprotect, and the reply-box prefix alone wouldn't catch it regressing.\n\nThe failure isn't Playwright 1.65's doing:\n\n- On current `main` the margin case fails the same way under Playwright\n1.64 (Chromium 156) as under 1.65.\n- `git bisect run` under 1.64, from `e6756ad43` (pass) to `ce2d27f9b`\n(fail), lands on 77ef6600f (#5770).\n- At `e6756ad43` under 1.65, the test failed only on Chromium 158's\n`position-visibility: anchors-visible` deprecation warning, which #5803\nfixed.\n\nVerification: all four `test_refused_reply_retains_its_live_foot` cases\npass locally on this branch under Playwright 1.65. The margin case\nfailed before this change. On the runtime just before #5770, the new\nhead assertion fails by 80px. Ruff check and format pass.\n\nCloses #5829 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-11T09:01:25Z",
          "url": "https://github.com/max-sixty/leaf/commit/a52abb1bb667f068a6a358c899cc634b644215c7"
        },
        "date": 1794397376472,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1037.87,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 42.8,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 9.56,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 26.81,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 32.47,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.84,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 289.1,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 270.12,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 89.88,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 296.92,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 129.39,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 81.94,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 21.55,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 61,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 235.6,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 107.3,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 536.17,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 48.04,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 13.93,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 35.25,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 51.07,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.76,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 132,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 118.3,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 71.53,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 229.55,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 122.43,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 127.61,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 46.02,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 42,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 205.9,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 86.3,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 426.88,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 27.96,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 9.33,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 24.24,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 30.91,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.96,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 58.07,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 66.06,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 51.87,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 213.5,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 85.22,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 72.43,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 19.83,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.9,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 170.3,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 72.8,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 456.67,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 26.31,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 9.33,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 40.88,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 56.15,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.55,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 74.09,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 72.39,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 52.02,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 197.84,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 104.51,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 71.94,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.59,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.1,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 185.7,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 108.6,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 568.01,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 45.32,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 8.97,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 22.02,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 55.56,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.1,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 98.8,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 118.37,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 68.82,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 236.81,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 103.73,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 94.56,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 31.28,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 46.1,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 229.7,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 101.4,
            "unit": "ms"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Maximilian Roos",
            "username": "max-sixty",
            "email": "5635139+max-sixty@users.noreply.github.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "e5559a2b614ee6a9b68a9b5f3475703b643cd61f",
          "message": "Find a selection's copies by string search, and search the page a part at a time (#5875)\n\nOn #4781's page (30 tabs, each a 4 MB text document, one comment), a\ntriple click on a line of the open document held the main thread 450–580\nms in Chromium and 0.9–1.5 s in Firefox, and a page search held it for\nthe whole search: 2.6–2.7 s in Chromium and 4–4.3 s in Firefox for a\nword the page doesn't hold, and for a common word typed a key at a time,\n6–11 s a key in Firefox and minutes in Chromium. Now a triple click\nholds it 185–270 ms in Chromium and 210–380 ms in Firefox, and each of\nthe search's own tasks reads at most one document: under 200 ms in\nChromium and under 380 ms in Firefox, for a word the page doesn't hold\nor a common word typed. Find returns the same matches in the same order,\na walk through them steps as main's does, and a stored anchor resolves\nor detaches as before.\n\nTwo costs on Find's path are not the search and stay, both on main too:\nopening the search field the first time restyles the whole page in\nFirefox (6 s here), and landing on a match in a closed tab reveals it\n(1.4 s in Chromium, 1.6–5 s in Firefox). See \"Left as it was\".\n\n## The triple click\n\nA selection's anchor is checked unique in its datum's words (root\n`AGENTS.md`, \"Validate once and share readings\"). Profiles in both\nengines showed most of the gesture was that check reading the 4 MB\ndocument again, several times:\n\n- **Finding the quote's copies.** One JavaScript pass of an automaton\nover every character, 85–125 ms over the document in either engine, once\nfor the word the double click selects and once for the line. A reading's\nletters (its characters less whitespace and edges) are now kept with it\n(`spell`), taken out by the platform's own replace and marked every 32\nletters, 15–30 ms once a reading. A few quotes are found in them by the\nplatform's string search, under 1 ms a quote; a batch of more than 32\nstill takes one automaton pass, so placing many comments stays linear in\nthe page and the quotes (`eachPlace`, which `findEach` uses too). Each\nplace is held to its quote's spaces where it stands in raw (`copyAt`),\nas before.\n- **Telling a common word's 17,000 copies apart.** `holds` read the\nwords around every copy. It now compares a side's letters outward\nthrough raw first and refutes at the first letter that differs,\nrecording that span as what it read, so the index still re-places a\nquote when a change there could complete its context. Only a copy whose\nletters all match has its words read.\n- **Checking each copy stands under the datum.** Two binary searches and\ntwo climbs of the tree per copy, 0.7 s in Firefox for the word. A copy\nin an element's own reading stands under it, unless a slot of the\nelement's own tree shows it words from outside.\n- **Asking again.** The comment button's placement, the command bar's\navailability, the response target and the remembered selection each\nasked for the anchor, so the check ran up to eight times a gesture.\n`findQuote` keeps its answer with the reading it answered for; a change\nmakes a new reading. It still asks the quote's copies first each time,\nsince that is what brings a quote the index has come to keep into it, so\na change to a quote first answered for a selection is heard once its\ndraft is placed.\n\nWhat a triple click still pays beyond its cost on the same page with 40\nKB documents (89–110 ms in Chromium, 74–99 ms in Firefox): the datum's\nindexed reading on its first capture (14 ms in Chromium, 30–50 ms in\nFirefox), its letters (15–30 ms), the list of the word's 17,000 copies,\nwhich anchor placement keeps for the draft's quote, and the garbage\nthose leave. In Firefox the three clicks run as two tasks; the second\nholds 120–250 ms on this branch and 180–230 ms on main.\n\n## Page search\n\n`pageMatches` (was `pageFind`) is a generator: it reads a part when the\nsearch reaches it, and yields null before each part and for each match\nthe page hides. The target picker takes matches 8 ms at a time, the\nfirst slice in the input's own task and each later one in a task of its\nown, so a search waits on at most one document's reading. Matches arrive\nin reading order, and the search lands where it did: the first match at\nor below the top of the window, else the first; after a page change,\nwhere it stood. Until it lands, the count slot shows an ellipsis; after,\nthe count grows where it stands. The status is busy (`aria-busy`) while\nthe search runs, so a screen reader says the count once, as it ends,\nrather than at each slice (\"Searching\" and \"Match 3 of 120 so far\" are\nits name meanwhile).\n\nMain searched once, as the query was typed (and again before a step\nafter the page changed), so a step after that took 20–48 ms. Here a step\nor a choice (Tab, Shift+Tab, Enter, `n`) waits only when its target\nhasn't arrived: it takes matches at once until the search has landed,\nwhere it stood if the page changed under it, and the match the step goes\nto has arrived, or the search has ended (`settle`). That matters most\nafter a match in a closed tab: bringing it into sight opens the tab,\nwhich changes the page, so the next step searches again from where it\nstood. A step back past the first match is the one step whose match\ncomes last, so while the search runs it stays put and says \"Searching\"\nrather than wait for all of it. Once Enter has closed the field, a\nsearch still finding stops at the first page change rather than start\nagain, and `n` searches again from there; only the open field searches\nagain where it stood after a change, as a reveal makes.\n\n## Measurements\n\n#4781's page, served by `leaf server run --lifetime temporary` with a\nthrowaway state home: main at b3387f111, the merge base, against this\nbranch, each arm a snapshot of its tree. One browser per engine and\nround, warmed 15 s; each gesture on a fresh load, 5 s after the\ncomment's mark stood and every document drew, with the page's view\nchecks stubbed in both arms. The longest task is the longest gap in a\nchain of zero timeouts, which only main-thread work holds back. Arms\nalternate within each round; load average 3–13. The branch arm is this\nPR before its last change, the busy status, which redraws the count each\nslice as the first push did. Chromium 156 headless and Firefox 157\nthrough Playwright. Milliseconds, one per round.\n\n| Longest task | Chromium, main | Chromium, branch | Firefox, main |\nFirefox, branch |\n|---|---|---|---|---|\n| Triple click, first gesture | 548, 575, 552 | 253, 270, 254 | 1,179,\n1,157, 1,112 | 376, 222, 332 |\n| Triple click, after a click | 448, 455, 446 | 185, 187, 192 | 1,022,\n1,474, 901 | 210, 210, 224 |\n| Find, a word nowhere on the page | 2,654, 2,731, 2,595 | 181, 196, 192\n| 4,116, 3,953, 4,318 | 323, 373, 321 |\n| Find, `heap` typed | not run | 98, 78, 100 | 11,144, 6,387, 6,702 |\n364, 219, 321 |\n\nEach Find opens and closes the search once before its window, so\nFirefox's first-open restyle stays out of it, then pastes or types its\nword. \"Nowhere\" reads every document; `heap` matches 530,000 times. In\nChromium the typed search is still running 12 s later: whether a match\nshows is read from its styles, and a match in a run of a text document\nthe browser hasn't drawn makes it style that run to answer, 26 ms a run\nhere, in 15,900 runs. The page stays live meanwhile; main's arm isn't\nrun, since `pageFind(\"widget asks\")` had not returned after 14 minutes.\nOn the first push, at load 12–30, a word in a closed tab held 4.1 s in\nChromium and 8.7–15 s in Firefox on main; on the branch its search tasks\nheld at most 206 ms and 349 ms, and the reveal on landing 1.4 s and\n4.3–5 s. Walking `FINDTOP`'s 30 matches, one a document, Tab goes 1 to 6\nin both engines, and `n` after Enter selects the next.\n\nSteps right after typing `heap` in Firefox, while the branch's search\nstill runs (main's has ended, since it searched as the key was typed):\neach key's time from its keydown to the next paint, by Event Timing,\nthree rounds per arm, alternating, load 13–31.\n\n| Keydown to next paint | Firefox, main | Firefox, branch |\n|---|---|---|\n| Longest key typing `heap` | 11,912, 10,752, 11,040 | 56, 88, 80 |\n| Tab | 48, 64, 72 | 32, 72, 48 |\n| Shift+Tab | 48, 48, 40 | 32, 56, 48 |\n| Shift+Tab from the first match | 5,696, 5,368, 6,400 | 32, 24, 24 |\n\nMain's wrap lands on the last of the 529,957 matches, in a closed tab,\nand reveals it; the branch's stays on the first and says \"Searching\".\n\nProfiles: Chromium through CDP's profiler, Firefox through the Gecko\nprofiler (`MOZ_PROFILER_STARTUP`), for each arm's triple click and\nsearch.\n\n## Left as it was\n\n- **Firefox's first open of the search field** restyles the whole page\nas focus enters it: 6.0 s here on main, 58 ms on the 40 KB page, 41 ms\nthe second time. In single runs, disabling the theme's sheet brought it\nto 0.9 s and deleting every `:has()` and focus rule only to 2.7 s, so I\ndidn't find the rule. #5844 fixed focus restyles in Chromium.\n- **Revealing a closed tab that holds a large document**, as landing on\na match there does: 1.4 s in Chromium, 0.9 s of it `claimPaintedRoots`\n(`keyboard/scopes.js`) walking every element of the revealed document;\n1.6–5 s in Firefox, mostly the tab's activation. A click on the tab pays\nthe same.\n- **A common word in Chromium** runs for minutes behind the page, as\nabove. Reading only the style of the box that skips a run (`skipper`)\nwould end it in seconds but find words CSS hides inside a run or closed\ntab the browser hasn't drawn; capping the count, as Firefox's find bar\ndoes at 1,000, would too. Either changes Find's results, so it's yours\nto choose. The text document's line-number counters make each run's\nforced style 26 ms rather than 4 ms.\n\n## Calls you may reverse\n\n- **32 quotes** as the line between string search and one automaton\npass. I kept the automaton so many comments on one large document stay\nlinear in the page and the quotes; one mechanism would drop either that\nor the 1 ms single-quote search.\n- **A step waits for its match, and a wrap back stays put.** A step past\nthe last match found takes matches at once until the next has arrived or\nthe search has ended, as main's search did up front; Shift+Tab from the\nfirst match while the search runs stays and says \"Searching\". Tab and\nEnter in the field before the first match has arrived do what they do\nwith no match, as on main for a query with none.\n- **The count slot's ellipsis** before the search lands, and the count\ngrowing under a busy status after. The slot is 7 characters wide, so a\nword wouldn't fit; a count over \"99 of 99\" was already cut by its\nellipsis on main.\n\n## Tests\n\n-\n`test_a_walk_through_search_matches_in_closed_tabs_reaches_each_in_turn`\n(both engines): Tab walks four matches in closed tabs and Shift+Tab back\none, with the page's clock run fast so each of the search's slices takes\none step; then Enter selects the match and `n` the next. It fails on the\nfirst push of this PR.\n-\n`test_a_step_back_past_the_first_search_match_stays_while_the_search_runs`\n(both engines): with the page's zero-delay timers held, so the search\nstands unfinished, Shift+Tab from the first match stays and says\n\"Searching\", and Tab goes on to the next. It fails on the second push.\n- `tests/runtime/passage-boundaries.test.mjs`, \"a quote first answered\nbefore the index kept it is heard when its words are redrawn\": fails\nwith the kept answer asked before the copies.\n- `tests/runtime/datum-quotes.test.mjs`: capturing a word a datum\nrepeats 2,000 times reads only the words beside the selected copy (fails\nwithout the letter check, reading every line), and a datum's quote\ncounts no copy among the words its slot shows from outside it (fails\nwithout the slot guard).\n-\n`test_a_search_finds_each_match_in_prose_and_every_part_in_reading_order`\nalso holds a search to reading no part ahead of the matches taken (fails\nwhen the search reads every part first).\n- The shared quote cases cover the letters and the letter check\n(reversing the letter order or dropping the spaces check fails them).\nBoth sides of the 32-quote line run in the existing tests: `findEach`'s\ncases, and 42 quotes in \"a line rewritten in a part changes only the\nquotes standing on it\".\n\nRan: `pnpm run test:runtime` (951 passed), `pnpm run check:browser`,\npre-commit on the changed files, and browser selections `-k \"search or\nfind or match\"` (62 passed) and `-k \"quote or capture or selection or\nselect or repeated or twice or datum or comment_on\"` (87 passed, 3\nfailed) over `test_render_anchors`, `test_render_semantic_selection`,\n`test_render_floating_panel`, `test_render_aim`, `test_reading_pieces`,\n`test_command_reference`, `test_render_diff_controls`,\n`test_render_gate`, `test_code_review` and `test_code_and_documents`.\nThe 3 failures fail the same with main's runtime files at the merge\nbase:\n`test_a_text_document_update_keeps_a_selection_it_carries_into_another_run[browser]`,\n`test_dense_selection_hints_stay_short_and_reach_an_atomic_visual` and\n`test_target_hints_name_only_addressable_elements_shown_by_a_disclosure`.\nNot run: the whole suite (CI), journeys, Safari.\n\n#5843 (open) adds the same `COLLAPSE_CHARS` export and builds the same\nclass of gaps, whitespace and edges, in `findText`'s pattern that this\nbuilds as `GAPS`. Whichever lands second should take the other's:\n`findText` can join its words with `GAPS.source`, or `GAPS` can move\nbeside `COLLAPSE` in `kernel-facts.js`.\n\nPart of #5194.",
          "timestamp": "2026-11-12T10:25:02Z",
          "url": "https://github.com/max-sixty/leaf/commit/e5559a2b614ee6a9b68a9b5f3475703b643cd61f"
        },
        "date": 1794483384450,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1234.32,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 42.42,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 9.29,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 37.72,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 40.31,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 6.28,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 299.59,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 314.59,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 60.5,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 138.13,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 172.51,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 88.59,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 75.18,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 24.59,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 59.15,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 177.7,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 78.3,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 517.3,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 48.13,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 13.41,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 37.6,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 45.13,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.29,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 111.31,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 108.38,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 66.09,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 265.89,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 110.63,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 111.04,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 49.06,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 38.5,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 176.9,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 75.5,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 390.31,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 26.49,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 8.9,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 22.03,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 29.61,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.81,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 62.2,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 53.75,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 50.91,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 180.9,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 68.74,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 55.69,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 19.96,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.3,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 153.5,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 61.6,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 425.96,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 24.35,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 8.64,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 34.4,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 51.69,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.64,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 83.4,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 67.01,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 50.9,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 196.48,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 94.22,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 55.1,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 17.65,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.15,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 173.8,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 95.5,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 563.86,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 46.63,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 9.11,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 18.64,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 53.93,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.9,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 94.51,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 100.31,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 56.85,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 207.2,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 100.21,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 86.27,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 27.66,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 43,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 193.1,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 96.5,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}