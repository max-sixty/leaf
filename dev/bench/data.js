window.BENCHMARK_DATA = {
  "lastUpdate": 1794397377491,
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
      }
    ]
  }
}