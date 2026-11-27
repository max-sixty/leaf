window.BENCHMARK_DATA = {
  "lastUpdate": 1795781202507,
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
          "id": "a9e4d3e99e7e9963bf13316cf47a04b7b588619c",
          "message": "fix: decide a margin card's scrollbar gutter in its fit, outside the transcript's size delivery (#5934)\n\nA margin card's transcript holds a scrollbar gutter once its turns\noverflow (`data-lf-overflows` → `scrollbar-gutter: stable`,\n`annotation-chrome.css`), which narrows its content box. Only the reach\npass's paint decided that gutter (`paintContinuation` in\n`thread-preview.js`). That paint runs inside reach's own ResizeObserver\ndelivery for the transcript, so marking the gutter resized a box the\ndelivery had just reported, and Chromium raised `ResizeObserver loop\ncompleted with undelivered notifications`. The nightly journey\n`test_a_second_margin_reply_grows_below_the_first_line` hit this at\nteardown.\n\nBefore #5811, the card's fit scrolled a reader at the end to the new\nend, and that scroll ran the same paint in the placement's script,\nbefore the frame's layout. #5811 (intended: one keeper, `followEnd`, for\na reader at the transcript's end) removed that scroll, so the decision\nwaited for reach's delivery. This PR keeps #5811's design. The gutter\ndecision is now one function, and the card's fit (`measureThreadCard`)\ncalls it right after changing the card's room, before the frame's\nlayout. The paint still calls it for overflow that no fit answers. What\nthe gutter is and when it changes are unchanged.\n\n**Verification**\n- The journey errors on main `415cf1d6f` and passes three of three runs\nwith the change.\n- 33 card and margin-journey tests pass: scrollbar room, end-following,\nNew reply, ride and bounded draft (`-k \"scrollbar or\nfollows_its_last_turn or new_reply_once_its_picture or grows_below or\nbounded or end or ride\"` over `tests/browser/margin/test_card_reply.py`\nand `tests/journeys/test_render_margin.py`).\n- `pnpm run check:browser` and `pnpm run test:runtime` pass.\n\n<details><summary>How the delivery was traced</summary>\n\nI wrapped `ResizeObserver` and added a document `MutationObserver` in an\ninit script. On main, in the frame that errors, the order is:\n\n1. The card's `max-height` drops from 534px to 260px.\n2. reach's observer (`reach.js:419`) is delivered the transcript at\n413px wide.\n3. `data-lf-overflows` is set during that delivery.\n4. The next round reports the transcript at 403px, and the error fires.\n5. reach is delivered the 403px reading one frame late.\n\nAt #5811's parent, the same trace shows `data-lf-overflows` set right\nafter the `max-height` write, before any delivery in that frame.\n\n</details>\n\nOne path is left. If the gutter's answer changes when a turn grows\ninside a card already at its cap, with no new fit, the decision still\nlands in a size delivery. That path predates #5811, and nothing\ncurrently reports it.\n\nCloses #5933 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-13T09:31:31Z",
          "url": "https://github.com/max-sixty/leaf/commit/a9e4d3e99e7e9963bf13316cf47a04b7b588619c"
        },
        "date": 1794570429325,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1582.13,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 45.52,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.76,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 35.28,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 43.94,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 6.52,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 386.98,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 411.77,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 82.67,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 154.61,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 193.19,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 93.53,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 80.42,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 25.12,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 50.1,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 206.9,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 89,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 653.77,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 55.82,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.78,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 38.09,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 48.23,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 10.18,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 137.39,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 129.09,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 79.49,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 292.77,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 125.68,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 125.58,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 127.63,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 36.95,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 215.7,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 90.4,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 496.96,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 31.38,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.36,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 20.51,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 34.38,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.04,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 74.11,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 62.6,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 61.63,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 218.29,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 81.92,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 68.29,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 20.37,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.8,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 201.7,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 74.6,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 523.31,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 28.39,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.04,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 23.78,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 46.62,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.94,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 83.08,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 84.11,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 52.69,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 192.93,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 99.93,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 62.8,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.45,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 45.6,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 195.4,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 105.6,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 743.62,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 56.41,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 10.92,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 20.61,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 62.85,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.38,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 116.75,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 115.86,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 82.08,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 238.18,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 117.69,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 87.59,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 23.04,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 53.6,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 234.7,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 95.1,
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
          "id": "6cfc59a83cfc5fc83df47a8df22ebc35e58778e4",
          "message": "test: wait for the server's reading of a send before reading what only it decides (#5943)\n\n#5899 made `applyState` (`browser/runtime/state-application.js`) wait\nfor the frame a gesture owes before it adopts the server's reading, so\nthe gesture's own result paints first. So the send's answer, which\n`round_trip` and `sending` wait for, now lands a task before the page\nholds the server's thread or offers Undo. Six of the seven macOS\nfailures in #5941 read that state right after the trip: `readThreads()`\nthrough `open_panel_thread`, a package widget's thread id, or a `z`\npressed straight after a Resolve. They saw the tab's pending copy, and\nthe dropped `z` never retried. This PR makes them wait for the reading\nitself. It changes no product code. The harness already says delivery\ndoes not mean the page applied the returned state (`_Traffic` in\n`tests/render_harness.py`).\n\n- `open_panel_thread` waits until `readThreads()` holds the thread\ninstead of reading it once.\n- `test_one_field_starts_a_thread_takes_its_reply_and_settles_it` and\n`test_a_thread_s_keys_answer_in_its_view` undo the Resolve with the\nexisting `undo(page)`, which waits until the dispatcher would take `z`.\n-\n`test_package_thread_widgets_keep_local_filters_and_independent_subscriptions`\nwaits for the server's id before it names the panel view.\n\n**Verification.** On Linux, the failing state appears when `z` is\npressed right after the Resolve is acked. A probe did that 15 times per\narm. It failed 6 of 15 at #5899 (`c0ff621c1`), 5 of 15 on main, and 0 of\n30 at #5899's parent. In each failing run, a second `z` a second later\nsent the undo, so the page catches up; only the early press is lost. The\nsame probe using `undo(page)` passed 15 of 15. The six edited tests pass\nlocally. They passed on Linux before this change too, so the macOS\nevidence is the next scheduled run after merge. I couldn't make the old\none-shot `open_panel_thread` read fail on Linux, even with\n`--cpu-throttle 15`.\n\n**What this leaves.**\n`test_undo_waits_while_the_candidate_is_applying_then_reads_accepted_truth`\nalready uses `undo(page)`. On macOS its page ended at `#sug-thistle`, so\nthat `z` showed the suggestion rather than taking it. That's a different\nmechanism, and it stays open on #5941. If the next macOS run still shows\n`readThreads` without the server's thread after these waits, the reading\nnever got adopted, not just adopted late. The likely cause would be an\nowed frame that never paints, leaving `afterOwedFrame` unresolved.\n\nRefs #5941 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-14T08:43:43Z",
          "url": "https://github.com/max-sixty/leaf/commit/6cfc59a83cfc5fc83df47a8df22ebc35e58778e4"
        },
        "date": 1794656346475,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1097.63,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 37.3,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 7.86,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 31.91,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 33.28,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.69,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 264.82,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 244.52,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 54.24,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 100.61,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 136.28,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 72.89,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 63.97,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 21.64,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 35.75,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 146.5,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 77.1,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 476.46,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 44.03,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 13.73,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 28.85,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 36.44,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 7.84,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 102.85,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 109.7,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 56.61,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 236.22,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 100.63,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 97.22,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 39.26,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 31.7,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 163.3,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 84.8,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 361.72,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 23.75,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 8.19,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 21.4,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 26.01,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.6,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 49.19,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 48.75,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 47.05,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 157,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 61.98,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 51.5,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 17.21,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 31.6,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 157.1,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 75.2,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 386.7,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.5,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 7.5,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 18.35,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 32.42,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.68,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 69.86,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 67.48,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 57.53,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 162.35,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 73.49,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 55.03,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 18.25,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 31,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 140.8,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 73.1,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 514.41,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 43.8,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 8.42,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 17.65,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 46.76,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.26,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 84.54,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 84.04,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 55.2,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 181.7,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 86.12,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 67.2,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 20.08,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 36.15,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 182.9,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 77.7,
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
          "id": "f20c08b730013f354f568fb2cb794c58a119056e",
          "message": "Bench #4781's tabs of large documents, with the inputs that found its costs (#6033)\n\n`leaf-dev bench` now generates #4781's page, a side list of tabs each\nholding a large text document bound to its own source, and measures the\ninputs that found this week's costs on it by hand. The daily `bench` job\nruns it, so Tend's review sees these costs grow with the page.\n\n## The page\n\n`documents` holds the shown document, one more in a closed tab for each\neight of `n`, and one more again: 3 documents on the BASE page, so\n`reveal` has two closed tabs to open there, then 10, 18 and 34 at the\ndaily sizes 64, 128 and 256, about #4781's 30 tabs at the largest. Each\nsource is 2,048 lines of Python (16 of a listing's 128-row runs), the\nsame at every size. So a cost that grows with the documents a page holds\ngrows with `n` and shows in the exponent. A cost that grows with the\nlength of the one document opened stays level and shows only beside\nanother arm (`--base`).\n\nThe largest page holds 69,000 rows where #4781's held 2.9 million. That\nis enough for a walk of every panel on each tab switch (#5996) to fit an\nexponent in Chromium, and it keeps the daily run short (below). The text\nis Python rather than #4781's Markdown, because Python's syntax colour\npaints most words, and the colour a closed tab keeps is what `browse`\nreads.\n\nThe sources are set through the fixture's data companion\n(`page.data.json`, which `prepare_page` sets with `leaf data set`), so\neach arm builds the page with its own Leaf. `Collection` gains `data`\nfor it, which `server_paths.build` also sets in process.\n\n## The inputs\n\n| Input | What it does | Fix it watches |\n|---|---|---|\n| `data` | the agent's `leaf data set` changes the first line of the\nshown document's source; `painted` is the frame that draws the new line\n| #5992 |\n| `reveal` | a click opens the second tab, then the third, neither\nopened before | #5996 |\n| `search` | the first `/`, which opens page search | #5999 |\n| `matches` | type `value`, which every line holds, into page search,\nuntil the count is final | none yet |\n| `browse` | put away page search, open every closed tab, then turn the\nwheel a run's height down and up the last one's listing, 16 steps |\nclosed tabs keep their colour ranges (still on main; #6035) |\n\nThey run in that order, so `search` and `matches` read the page before\n`browse` has opened every tab, whose kept colour every later input would\nmeet. They need the page's own ids (`#docs #d0[source]`) and find the\nother tabs and documents by them. Each finds what it acts on through\n`page.evaluate`, never a locator, since a Playwright locator walks every\nelement of the page for each query. `holds`, which decides whether a\npage has what an input needs, now asks the document with `querySelector`\nfor the same reason. `painted.js` gains three facts: `shows` (an element\nis drawn and holds some words), `searching` (page search's field holds\nthe caret) and `searched` (its count is final). `BenchPage.written`\ntakes the file a command writes, here the source's file rather than the\nlog.\n\n## What the marks hold\n\n`held` now covers the requests and bytes any input causes, the size of\nthe answer to each of its POSTs (`<input> event KB`) included, besides\nthe CPU of an input the browser answers alone: root `AGENTS.md`,\n\"Responsiveness\", holds an input's work to what it changes. Without it,\n#5992's cost, every source sent to the tab after a write to one, fits\nexponent 1.08 with no mark, since an agent's write may grow with the\npage. An input whose result is the whole page is exempt, through a new\n`Input.whole`: `revision` and `stamp`, which carry the new document, and\n`matches`. A held count's noise floor is a quarter of its own reading on\nthe BASE page and at least one, where every count's was a fixed 10 KB or\none request.\n\nRe-judged under main's rules and this branch's, the nine daily reports\nof 11-06 to 11-14 differ in one reading: `asks` `comment event KB`, 4.9,\n8.1, 11.9 and 19.6 KB across the sizes in the six reports of 11-06 to\n11-11, now marked at 1.08. Those reports showed it with no mark; it\nreads level from 11-12 on. On this page's runs the only differences are\n`matches`, which `whole` lets grow, and `data KB` with #5992 reverted.\n\n## Evidence\n\nAll on this Mac (M5 Max, 18 cores, load average 3–21 from other\nsessions), `uv run leaf-dev bench documents --sizes 64,128,256 …`.\n\nCurrent main, Chromium, the daily job's command (`--rounds 2 --input\ndata --input reveal --input search --input matches --input browse`), 266\ns:\n\n```\n                            8         64        128        256   exponent\nelements               6435.0    20988.0    37620.0    70884.0         - \nload cpu ms             200.0      242.8      299.5      510.5      1.43 \ndata cpu ms              23.1       21.3       25.5       30.7         - \nreveal cpu ms            46.0       42.0       43.9       47.1         - \nsearch cpu ms            18.3       17.3       18.4       19.7         - \nmatches cpu ms          290.5      718.7     1271.1     2328.5      1.13 \nbrowse cpu ms            15.4       19.5       25.4       28.0      0.81!\ndata painted ms         133.5       99.9       68.6       99.5         - \ndata requests             1.0        1.0        1.0        1.0         - \ndata KB                  82.6       82.6       82.6       82.6         - \nreveal painted ms        37.2       33.5       34.8       36.1         - \nreveal requests           0.0        0.0        0.0        0.0         - \nreveal KB                 0.0        0.0        0.0        0.0         - \n```\n\nCurrent main, Firefox, the first commit's page and input order with\n`--browser firefox`:\n\n```\n                         8         64        128        256   exponent\nelements            4351.0    18904.0    35536.0    68800.0         - \nload cpu ms          344.8      521.9      557.5      917.8      0.85 \ndata cpu ms           40.6       56.2       43.4       52.0         - \nreveal cpu ms         73.5       78.3       65.0       71.7         - \nbrowse cpu ms         43.9       51.4       54.6       68.1         - \nsearch cpu ms         37.5       61.3       40.8       48.5     -0.56 \nmatches cpu ms        98.3      115.0      201.3      287.1      0.87 \n```\n\nWhat main shows, with a V8 profile of each growing input from\n`--profile`, which lists the functions whose time grew past the input's\nlimit from the smallest page to the largest:\n\n- **`browse`, 0.81 `!` in Chromium**, and 0.96 and 1.04 in two runs of\n`browse` alone. A closed tab keeps the colour ranges of the runs it last\nshowed (896 a tab here), and each run a step colours rebuilds highlights\nholding every opened tab's ranges. The profile names `unpaint` and\n`follow` (`lf-text-document.js`), 3 to 40–45 ms. This is the cost\n#5996's body left unmeasured, which #6035 removes: with its change,\nreview read `browse` level. Firefox grows too (44 to 68 ms), but under\nthe noise floor in one of two runs.\n- **`load cpu`**, 1.43 here and between 1.02 and 1.71 across seven runs\non main, above 1.5 in two. The profile names an anonymous function at\n`addressable-names.js:187`, `headingsIn`'s query of every heading under\nan element, growing from 1 to 126 ms (exponent 1.54). Read from the\ncode, not confirmed: each document's first draw may start a new page\nreading, whose heading queries walk the whole page again.\n- `matches` grows at 1.13 in Chromium and 0.87 in Firefox, within its\nlimit as a `whole` input. Chromium's 2.3 s at 34 documents against\nFirefox's 0.29 s is #5999's note that a match's visibility read styles\neach run it lies in.\n- `search`, `data` and `reveal` stay level in both engines. In the first\ncommit `search` ran after `browse` and grew with the tabs `browse` left\ncoloured (0.79 `!`); run before it, it reads 17 to 20 ms.\n\nEach fix reverted in the working tree (`git revert --no-commit`), with\n`--base HEAD` for main beside it. The #5992 and #5999 rows are from the\nfirst commit's page, which held one document fewer:\n\n- **#5992**, Chromium: `data KB` goes 164, 736, 1,398, 2,722 KB with the\nfix reverted, exponent 1.08 `!`; main reads 82.6 KB at every size.\n- **#5996**, Chromium, two rounds, this head's page and `reveal`:\n`reveal cpu` goes 48, 50, 63, 84 ms with the fix reverted, exponent 1.25\n`!`; main reads 48, 43, 51, 49 ms. On the first commit's page, whose\n`reveal` reopened the first tab for its second sample, the revert read\n1.77 `!`. In Firefox the revert raises `reveal cpu` to 210–290 ms at\nevery size from 60–90 ms, level rather than growing, since the Firefox\nhalf of #5996 (the fold rule) scaled with the opened document's length,\nwhich this page holds fixed.\n- **#5999**, Firefox, two rounds: `search cpu` goes 45, 83, 92, 165 ms\nwith the fix reverted, exponent 0.82 `!`; main reads 26, 30, 28, 24 ms.\n\n## CI time\n\nThe daily job measures `documents` in a step of its own after the\ndefault pages, with only these five inputs, since the `document` page's\ntext already grows under every other input. The step runs after a failed\none, and the readings to chart are collected once both have run, so one\npage's failure keeps the other's chart. Its table goes to\n`documents.txt` in the `bench-report` artifact, which Tend's benchmark\nreview (`.claude/skills/running-tend/SKILL.md`) now names beside the\nbrowser and server tables. The command took 266–284 s here. To scale it\nto the runner: the `rows` page with the daily job's arguments took 397 s\nhere and 7.5 minutes on the runner on 2026-11-14, a ratio of 1.13, while\nthe runner's load CPU is 2.2 times this Mac's. So the job should grow by\nbetween about 5 and 10.5 minutes, nearer the first, since most of a run\nis waiting rather than CPU.\n\n## Not verified\n\n- The runner's time for the new step, which the first daily run's step\ntimings will show.\n- Firefox on CI. The Firefox clock (`ContentClock`) reads macOS's thread\ntimes, so the daily job reads Chromium only, and a Firefox-only cost\nsuch as #5999's shows only in a local run.\n- WebKit.\n\nNo `dev/tests` smoke test: the bench has none, and each input ran here\nin both engines at four sizes.\n\n## Calls Max may reverse\n\n- `held` covering requests and bytes, with `Input.whole` to exempt a\nrevision and a search.\n- The CI step's input list, rather than every input on this page.\n- Python content, 2,048 lines a document and `2 + n/8` documents.\n- `browse`'s 16 steps, which over two runs fitted 0.96 and 1.04 where\nthree runs of 8 fitted 0.49 to 0.75.\n\nPart of #5194.",
          "timestamp": "2026-11-15T10:38:39Z",
          "url": "https://github.com/max-sixty/leaf/commit/f20c08b730013f354f568fb2cb794c58a119056e"
        },
        "date": 1794743867531,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "documents: load cpu",
            "value": 783.01,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 72.83,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 113.89,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 47.82,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 2165.13,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 47.61,
            "unit": "ms"
          },
          {
            "name": "asks: load cpu",
            "value": 1418.65,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 42.44,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.7,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 28.14,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 41.74,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.31,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.96,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 328.01,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 309.2,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 89.97,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 132.17,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 191.1,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 85.95,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 78.39,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 24.61,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 69.15,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 195.4,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 89.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 618.42,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 54.6,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.33,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 37.71,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 47.55,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 10.21,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.25,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 125.63,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 140.63,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 69.45,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 236.81,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 125.61,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 119.84,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 45.68,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 53.6,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 198.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 91.5,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 481.78,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 29.76,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.39,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 24.97,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 32.05,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.58,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.39,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 74.13,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 72.87,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 64.32,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 174.39,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 79.77,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 70.92,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 19.54,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.65,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 189.5,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 76.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 496.91,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 29.95,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 9.87,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 24.4,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 42.42,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.18,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.78,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 88.17,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 88.14,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 51.61,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 178.13,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 87.99,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 60.61,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 18.49,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 33.35,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 171.4,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 89.5,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 682.99,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 53.35,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 11.1,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 22.16,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 60.57,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.49,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 4.22,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 121.13,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 114.82,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 71.03,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 233.51,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 106.89,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 84.95,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 24.36,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 69.8,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 219.5,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 95,
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
          "id": "1740bb536f99b592c4f947a334a1a87f64b172cb",
          "message": "Name every widget by the markup it opens with, and retire x-name (#6088)\n\nCloses #5595\n\nEvery element Leaf names now takes its name from markup it opens with,\nas a section is named by its heading: a tab, a part, a board column, a\nsample, a pane, a text document, a worktree, a playground control,\nchoice and preset, a timeline run, lane and event, and a trace with its\nbookmarks. The registry's `x-name` key is gone, with the `label`\nattributes it pointed at, the `$attributes` entry that kept `label` as a\nname on every widget (`NAME_ATTRIBUTE`), and the `summary` attribute of\ntabs and parts.\n\n```html\n<lf-part id=\"part-readme\">\n  <header>\n    <strong><code>README.md</code></strong>\n    <p><span class=\"added\">+120</span> <span class=\"removed\">−45</span> lines</p>\n  </header>\n  <article class=\"layout-column\">…</article>\n</lf-part>\n```\n\nThe list of parts shows `README.md` in code type over the coloured\ndiffstat.\n\n## The rule and where it lives\n\nAn element's name is its leading title: a leading `<summary>`, heading\nor `<strong>`, looked for inside a leading `<header>` or `<hgroup>` too.\nThe rule already named sections, disclosures and titled members, and now\nnames widgets.\n\nA widget that draws, moves or hides its name takes it only where it\nopens the widget: the title, or the `<header>` or `<hgroup>` holding it,\nis the widget's first element. A quoted sample whose heading follows its\nfirst paragraph keeps the heading where it stands, and a tab whose\nheading follows a paragraph is unnamed, which `page check` refuses.\nWhere a name is only read, as a section's heading after an eyebrow or an\noption's title after its chips, it may follow those elements, as on\nmain: requiring it to open them too would have unnamed 41 options, 66\nsections and 39 list items in the corpus.\n\nEach runtime states the rule once:\n\n- **Browser**: `leading-title.js`. Packages get one reader,\n`openingTitle` (`portable-api.js`, and through it `widget-api.js`),\nwhich returns the name an element opens with as `{title, holder}`, or\nnull: the title naming it, and the holder, its first element, which is\nthat title or the `<header>` or `<hgroup>` around it. The board, tabs,\ntext document, worktree, playground, timeline and version diff read\nnames through it, and a widget draws, moves or hides the holder.\n`leadingTitle`, which reads past an eyebrow or an option's chips, stays\ninternal to the runtime. `addressable-names.js` reads the name's words\nas the author wrote them (`addressableName`) and copies a node's markup\nwithout ids or generated words for a surface that shows a name away from\nits element (`echoCopy`).\n- **Python**: `gesture_words.leading_title_node`, `leading_title` and\n`leading_title_holder`. `tests/name_cases.json` holds both runtimes to\nthe same names and the same holders.\n- **CSS**: one selector, `:first-child:is(summary, h1, h2, h3, h4, h5,\nh6, strong, header, hgroup)`, the holder `openingTitle` returns. CSS\ncan't see text, so it also matches a title that loose text precedes, as\n`strong:first-child` did on main.\n\n## How each widget shows its name\n\n- **Tab strip along a row** shows only each panel's name, so the panel\nkeeps its `<strong>` or `<header>` as the eyebrow over its first\nheading, in the reading theme's `.eyebrow` face, and the block under the\neyebrow takes the panel's top edge as the first block would. The tab's\ncopy is an echo (`says: \"echo\"`), so a comment on the name anchors in\nthe panel. A panel named by a heading keeps the heading as it is.\n- **Side list and a page's parts** show the name with the summary under\nit, so on screen the panel hides its name and the list's copy is the\npage speaking (`says: true`): page search finds the name in the list and\na comment on it anchors there. On paper the list is gone and each item\nprints under its name. A side list reserves a summary's line before\nupgrade from a panel's header, so a phone's row strip keeps its height\nwhen the module draws.\n- **Column, sample, pane, text document, worktree**: the authored name\nstands where the widget draws one. A text document's name heads its\nframe and names its figure. A worktree's `<strong>` stands in its row's\nroom from first paint, before the module slots it into the row. A pane's\nregion is named by its header's title unless its author gave it an\n`aria-label`.\n- **Playground control, choice and preset**: the name stays the\nelement's first child, hidden once the playground draws, and the view\ndraws a copy as the radio's label or on the preset's button. The\nplayground refuses a name holding a link, a control or a widget, which\nthe copy would nest inside that control. Its list of such tags and page\ncheck's are held together by `tests/nested_name_cases.json`, which both\nruntimes answer.\n- **Code block, chart, draft, diagram, diff**: a widget that draws its\nown content keeps the name it opens with over what it draws. The four\nlight-DOM modules put the holder back first when they replace their\nchildren, and `shadowStage`, the runtime's helper for a shadow-DOM\nwidget, keeps it in the light tree and slots it alone at the top of the\nstage, which covers the diff, the file tree and the file editor.\n- **Places that take only text** read `addressableName`: every tab's and\npane's `aria-label`, a thread card's heading, the timeline's chart\nlabels, the trace chooser and the board's announcements. Each panel is\nlabelled by its tab.\n\n## Checks\n\n- Under `x-content: members` and `data`, a widget may open with the\nelement its name stands in, a title or a `<header>` holding one, before\nits members or its `<pre>`. A `<header>` with no title names nothing and\nstays a stray member. Which widgets take a name is what their modules\nkeep: `page check --render` reports a name a module drew over\n(`dropped-name`), so a package's module that drops one hears it, with no\nper-widget key.\n- A revision that renames a tab, a part or a pane replaces the widget,\nas one that changed its `label` did: a members-patched widget's shell\nholds its own opening name and each member's whole.\n- `page check` refuses a view whose name doesn't open it\n(`unnamed-view`), and a link, control or widget in a view's header,\nwhich its tab, a control, copies (`interactive-name`). Another widget's\nname is drawn in place or read as words, so a question's heading or an\noption's title may link a pull request.\n- `x-says` is a list of attribute names, each said after the element's\nwords. Its `before` edge served only the column and sample labels this\nchange retires.\n\n## Evidence\n\n- **Corpus**: all 57 pages under `examples/`, `examples/developer/`,\n`docs/` and `tests/fixtures/pages/` build and pass `leaf page check`.\n- **Tests**: `pnpm run test:runtime` 992 passed; `pnpm run\ncheck:browser` clean; the touched model tests (959) pass; 191 browser\nand journey tests across the tab, document, workspace, playground,\nsample and version-diff files, the worktree rows, the pane names, the\nanchors selections, and the four tests CI failed on the first head pass.\n- **New tests**: a comment on a side list's name anchors on the list's\ncopy and survives a revision (fails on `says: \"echo\"`); an author's\n`aria-label` names a pane (fails when the header always wins); a quoted\nsample's heading after its first paragraph stays a heading (fails on the\nlenient selector); a tab whose heading follows a paragraph is refused; a\nplayground refuses a link in a preset's name; a code block, a draft and\na diff keep and show the name they open with; a revision that renames a\ntab reaches its strip and one that renames a pane its region (both\nfailed before); the render gate reports a widget that draws over its\nname; a removal that empties a nameless box stands in it, the version\ndiff's `gapIn`, which kept no test once a tab keeps its name.\n- **A stale journey**: `test_render_shift_watch.py`, which this branch\nedits and so CI runs, expected a message head to say \"just now\"; since\n#6097 a head says its clock time, so the journey now advances days\n(\"Yesterday 22:10\", \"13 Nov 22:10\") and still holds the thread in place.\n- **Probes**: a printed queue (`alert-review`) shows each item's header\nunder its group, where main printed the group and label together; a\nnamed text document's figure reads as `figure \"Reviewed\"`.\n- **Page search** on the root parts (`root-parts`): Workbench 4,\nEvidence 6, Plan 7, as on main.\n- **Stills** (`leaf-dev stills --authored` against main; Chromium and\nFirefox light, Chromium dark): the side list and the root parts are\npixel-identical to main. Both text documents' caption bars match main in\nboth schemes. A worktree's first paint differs only by its name standing\nin the row's room, which main leaves empty, with its body where main's\nis (Chromium only, since Firefox can't hold the runtime). The gallery's\npage of parts gains the `README.md` part, in code type over +120 −45.\nEach horizontal tab panel shows its name as the eyebrow over its first\nheading, in the face of a section's eyebrow under it: the root tabs, the\ngallery and a boxed set. A printed queue (`printed-queue`, new) prints\neach item's group, then its name and summary, where main printed the\ngroup and name on one line. A quoted sample whose heading follows its\nfirst paragraph keeps the heading where main does (`leaf-dev probe`\npair).\n- **Evals** (Claude Code, paired base): every head sample (8) wrote each\nname as markup and passed `page check`; base wrote `label` attributes.\nRubric results, head vs base: queue 1/1 vs 1/1; presets 2/3 vs 3/3;\nparts 0/4 vs 3/4, every head sample choosing a `layout-sidebar` with a\ncontents outline, which the rubric then refused and accepts since #6111.\n\n## Calls Max may reverse\n\n- **The eyebrow takes a `<strong>` or `<header>` name only**; a heading\nthat names a panel stays a heading.\n- **`x-says` became a list** rather than a map whose only value is\n`after`.\n- **A text document's caption bar keeps the figure's ground**: code's\nunder a source capture, the page's under a preview's tabs. Dropping the\nground made a source capture's caption paper where main's is white.\n- **A widget draws only a name that opens it, and only where a widget\ndraws its name**; reading a name stays as lenient as main's, past an\neyebrow or an option's chips.\n- **Only a view's name is required** (`unnamed-view`); columns,\ncontrols, choices and events may go unnamed.\n- **`lf-event` and `lf-trace-bookmark` declare `x-content: members` with\nno members** to hold only a name.\n\n## Adds\n\n- `openingTitle` in `portable-api.js`, returning `{title, holder}`;\n`addressableName` and `echoCopy` in `widget-api.js`, documented in\n`module-reading.md`.\n- `tests/nested_name_cases.json`, which the validator's `nested_in` and\nthe playground's `nestedIn` both answer.\n- The findings `unnamed-view` and `interactive-name`; the content-model\nrule that admits a leading name; the playground's refusal of a name\nholding a control.\n- `slot=\"lf-worktree-name\"` on a worktree's authored name, and\n`slot=\"lf-name\"` on the name of a widget `shadowStage` stages; the\n`parts-list` and `printed-queue` stills states.\n- The render finding `dropped-name` (`droppedNames`,\n`render-checks/words.js`).\n\n## Not verified\n\n- Page search finds a worktree's name and its branch separately, but no\nquery spanning both, which it did when both were the row's generated\nwords.\n- Option labels, board card titles and the quiet word's seat still read\n`:scope > strong`, a lookup that predates `x-name` and agrees with the\nrule wherever no text precedes the title.\n-\n`tests/journeys/margin/test_card_placement.py::test_the_shipped_long_thread_keeps_the_margin_and_its_height`\nfails here with a 320 px card where it asks for 379: #5991, on main,\nmade a card slim at 320 px until a message stands tall and left this\nassertion as it was. It fails without this branch's thread-card change\ntoo.",
          "timestamp": "2026-11-16T10:35:01Z",
          "url": "https://github.com/max-sixty/leaf/commit/1740bb536f99b592c4f947a334a1a87f64b172cb"
        },
        "date": 1794831010541,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "documents: load cpu",
            "value": 823.03,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 50.17,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 80.92,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 164.65,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 119.69,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 113.71,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 43.34,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 2014.06,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 39.6,
            "unit": "ms"
          },
          {
            "name": "asks: load cpu",
            "value": 1502.54,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 43.11,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 14.08,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 41.52,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 32.64,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.81,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 2.36,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 483.43,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 151.72,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 284.55,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 284.07,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 273.05,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 77.24,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 100.88,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 176.06,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 122.55,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 80.08,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 25.93,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 65.65,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 186.2,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 108.8,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 612.61,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 53.36,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 18.5,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 37.12,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 39.1,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 10.81,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.1,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 62.06,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 80.37,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 157.27,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 116.39,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 106.73,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 67.26,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 208.77,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 122.19,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 97.72,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 45.67,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 39.45,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 178.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 104.7,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 464.27,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 30.51,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 11.93,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 21.81,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 28.81,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.42,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.71,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 88.05,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 42.44,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 61.25,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 72.55,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 87.56,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 57.16,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 185.18,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 77.14,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 68.58,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 20.26,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 33.05,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 179.2,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 74.8,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 491.55,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 28.55,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 12.32,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 25.29,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 38.84,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.41,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 1.07,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 46.85,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 42.66,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 63.75,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 75.52,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 75.26,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 63.98,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 184.52,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 104.47,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 65.65,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.95,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 37.5,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 173.6,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 90.2,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 711.7,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 52.94,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 13.07,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 22.78,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 54.68,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.72,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 4.69,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 94.31,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 67.99,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 94.46,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 98.15,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 102.33,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 71.13,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 274.27,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 141.62,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 92.97,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 21.94,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 55.3,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 185.1,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 125.9,
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
          "id": "2aabb5436560c7427f26cf75acac3e8199080bc8",
          "message": "fix: restore a drag's passage when it is released over the floating panel (#6288)\n\nReleasing a drag over the floating panel's thread quote stored\neverything from the press to the page's end as the passage. The guard\nthat restores a drag's in-document range reads where the browser put the\nselection's far end (`leftThePage`). Over the layer's quote, Chrome\nleaves that end on the page's last words, which reads as still inside\nthe document. So the runaway range was both remembered as \"what the drag\nheld\" and kept at release. The press now records whether the hand last\nmoved over page words (`away`, set on `pointermove` with the same\n`pageWords` reading the press begins with). The remembered range stops\ngrowing once the hand leaves, and a release with the hand away restores\nit. ⌘A still never reaches this path.\n\n`test_a_drag_that_overshoots_the_layer_is_not_a_passage` fails on main\n(4384 characters stored against 684 covered) and passes with this\nchange. #6254 did not cause the failure; its CSS moved the panel's quote\n10px. Before that, the test's first leg already ended on the quote, so\nits `covered` reading was itself the 4434-character runaway, and the\nassertion passed without exercising the guard. With the panel's scroll\npadding forced to 0, the drag covers 8 characters and the release now\nrestores exactly that passage.\n\nThe test still doesn't drag sideways: the root's `scroll-padding-bottom`\nmakes Chromium autoscroll the page during the drag, so the in-document\nrange it restores spans paragraphs 9–16. That cause is a tradeoff\nagainst the panel's landing clearance, filed as #6287.\n\nRan the focused selection and drag tests in `test_render_anchors.py`,\n`controls/test_covering.py`, `test_render_aim.py`,\n`test_render_widgets.py`, `drafts/test_comment_targets.py`,\n`controls/test_press_away.py`, `test_render_reactions.py` and\n`test_render_formulas.py` (85 passed), plus `pnpm run test:runtime`\n(1007 passed) and `pnpm run check`.\n\nCloses #6286 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-17T10:04:54Z",
          "url": "https://github.com/max-sixty/leaf/commit/2aabb5436560c7427f26cf75acac3e8199080bc8"
        },
        "date": 1794916932248,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1024.72,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 34.23,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.88,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 22.19,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 24.53,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.6,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.43,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 4.02,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 221.86,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 85.6,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 180.17,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 138.91,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 133.94,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 55.28,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 74.78,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 129.34,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 79.41,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 53.45,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 21.71,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 54.5,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 160,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 88.6,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 494.39,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 46.76,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 16.81,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 31.99,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 34.72,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.45,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.12,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.89,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 49.87,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 59.11,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 101.88,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 82.6,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 70.3,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 61.85,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 184.91,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 110.46,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 98.25,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 40.88,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 44.2,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 336.73,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 35.75,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 172.7,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 84.1,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 377.33,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 24.67,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.47,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 17.19,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 23.33,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.31,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 3.32,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 6.82,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 61.93,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 28.58,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 42.4,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 63.74,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 49.23,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 49.84,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 148.66,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 61.85,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 47.25,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 18.19,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.4,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 143.9,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 71.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 390.55,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.19,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 11.01,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 22.69,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 30.68,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.26,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 1.11,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 5.02,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 38.33,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 28.61,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 47.38,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 52.84,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 54.25,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 50.53,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 155.47,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 68.62,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 50.91,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 22.03,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 48.7,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 159.1,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 78.3,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 517.92,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 41.43,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 10.08,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 19.43,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 40.38,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.35,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 4.73,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 7.52,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 79.03,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 45.69,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 71.03,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 81.43,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 85.96,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 52.8,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 189.09,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 77.33,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 91.25,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 26.11,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 48.3,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 165.6,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 91.4,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 623.77,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 37.05,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 13.43,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 33.64,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 89.93,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 56.71,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 90.23,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 90.78,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 92.18,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 36.22,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1472.42,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 31.91,
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
          "id": "8afbebff48f78a211546aca490166a15619bc76b",
          "message": "Say what holds now in hook, activity and fork docstrings, and drop fork eval keys nothing reads (#6360)\n\nComment, docstring and eval-data corrections from the nightly sweep, so\ntext in the tree says what holds now (root AGENTS.md, \"Where\ninstructions live\"). No behavior changes.\n\n`hooks.cmd_pages` keeps its two rules (a newer Leaf reads an older\nfollower's lane as no one's, and a follower whose module isn't this\nLeaf's keeps nothing back) and points at `activity.STARTING_GRACE`\ninstead of a 30 s hold that no longer exists. The dated incidents behind\nthem move to the commit message, as do the measurements that settled\n`STARTING_GRACE`.\n\nThe `summary_fork` header now states the decision and its reason without\ntelling its history. The `fork_eval` header and `evals/README.md` now\nname the summary fork, which the executor already runs\n(`evals/summary-fork`).\n\nStale references fixed: `events.summary_range` now points at\n`thread_context.summary_hint`, the `agent_state` header describes a\nthread's holder as `holding.holder` names it (main thread, line turn or\nworking fork, with whether that turn runs, closed or lapsed), and the\nworker cites `inference.CODEX_MODEL` instead of the nonexistent\n`thread_titles.CODEX_TITLE_MODEL`.\n\n`evals/workflows/fork_eval.yaml` loses the top-level `thread:` key on\nten line-fork cases. `fork_eval` takes the thread from KEEP's output,\nand a grep finds no reader of `scenario[\"thread\"]`.\n\nChecks run: ruff check and format on the touched Python, and\n`dev/tests/test_evals.py -k \"fork or case or catalog\"` (the fork replay\ncases and the catalog build), which passed.\n\n---------\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-18T08:44:24Z",
          "url": "https://github.com/max-sixty/leaf/commit/8afbebff48f78a211546aca490166a15619bc76b"
        },
        "date": 1795003742773,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1302.6,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 37.19,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 12.3,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 23.66,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 37.21,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 52.76,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.27,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 3.92,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 299.47,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 124.2,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 225.73,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 180.85,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 156.2,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 65.31,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 99.9,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 169.64,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 86.61,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 66.41,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 21.51,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 39.2,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 189.5,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 76.3,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 633.85,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 54.63,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 18.34,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 34.03,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 50.51,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 45.3,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 10.94,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.08,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 10.62,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 53.95,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 72.48,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 124.3,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 92.55,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 80.78,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 72.89,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 230.4,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 118.01,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 102.27,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 50.28,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 49.51,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 426.61,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 40.1,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 204,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 90.1,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 474.29,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 30.21,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 12.86,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 17.93,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 38.28,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 19.93,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.78,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.87,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 8.13,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 69.82,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 37.39,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 59.37,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 64.15,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 66.38,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 58.26,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 190.51,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 70.6,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 58.01,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 19.27,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.6,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 183.5,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 76.4,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 515.18,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 30.88,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 12.96,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 22.39,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 48.62,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 32.15,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.61,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.87,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 7.63,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 36.67,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 41.66,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 58.54,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 70.2,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 69.24,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 50.77,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 199.93,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 87.43,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 57.91,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.88,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 33.15,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 186,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 91.8,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 710,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 57.06,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 13.79,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 18.95,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 63.86,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 22.05,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 6.07,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 5.72,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 8.34,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 95.86,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 60.03,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 99.44,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 105.88,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 121.63,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 66.24,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 221.78,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 105.29,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 74.54,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 22.86,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 50.6,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 208.9,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 90.7,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 766.35,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 48.26,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 15.97,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 42.06,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 128.83,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 67.67,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 114.42,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 118.56,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 104.7,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 39.4,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1959.71,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 36.91,
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
          "id": "8512ab218640cdb7acf13797a83310debb56a3d4",
          "message": "fix: mark no line after a change that ends at the field's end (#6510)\n\nClearing a panel or comment field marked its only line as \"after the\nchange\", and that is what broke\n`test_an_explicit_target_does_not_overwrite_its_existing_draft` on\n`main`. #6476 added the mark (`data-lf-after`, `afterChange` in\n`field-editor.js`) so a removal's carry can split between the words\nbefore a removed line and the words after it. A change that ended at the\nfield's end still marked a line when that end fell at a line start. When\nthe field switches drafts, it clears and refills in a single task, so\nthe mark landed on the line and came off again. The write watch then\nfailed the test at teardown with `unchanged write: data-lf-after on\ndiv.cm-line.lf-face-p …\nleaf-text.lf-ui.lf-response-control.lf-fab-input` ([run\n44480242315](https://github.com/max-sixty/leaf/actions/runs/44480242315)).\nNo words follow a change that ends at the field's end, so the field now\nmarks no line there. Every other placement of the mark stays as #6476\nleft it.\n\nEvidence, run locally:\n\n- `test_an_explicit_target_does_not_overwrite_its_existing_draft` passes\non #6476's parent, errors at #6476 (`626ddc467`) and on `main`, and\npasses with this change.\n- #6476's own\n`test_a_line_removed_among_the_words_moves_only_what_layout_moved`\npasses in all six cases (panel, card and comment box, in Chromium and\nFirefox). The rest of `test_comment_targets.py` and `pnpm run\ntest:runtime` pass too.\n\nRefs #6418 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-19T10:01:27Z",
          "url": "https://github.com/max-sixty/leaf/commit/8512ab218640cdb7acf13797a83310debb56a3d4"
        },
        "date": 1795089586841,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 946.03,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 35.05,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.91,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 27.27,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 32.05,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 43.47,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.79,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.48,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 4.05,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 197.42,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 77.88,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 154.66,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 122.11,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 130.27,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 55.92,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 79.36,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 138.53,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 67.9,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 54.54,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 20.46,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 33.45,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 157.7,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 82.2,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 402.06,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 41.24,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.09,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 23.79,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 37.99,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 34.41,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 7.75,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.63,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.09,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 43.52,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 58.76,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 83.78,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 64.46,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 62.75,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 48.27,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 236.12,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 92.55,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 71.01,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 32.79,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 37.5,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 305.98,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 32.65,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 175.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 82.9,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 339.1,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 25.01,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.1,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 14.71,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 28.83,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 18.11,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.43,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.76,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 6.54,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 57.01,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 24.71,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 47.82,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 48.96,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 52.49,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 44.83,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 152.25,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 60.45,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 46.98,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 20.33,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 33.1,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 166.4,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 82.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 356.18,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 27.87,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.55,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 19.58,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 36.4,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 24.17,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 2.91,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.81,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 4.72,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 46.57,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 26.93,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 47.77,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 55.55,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 57.83,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 49.78,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 155.17,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 62.59,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 44.54,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 16.51,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.2,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 147,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 71.2,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 456.84,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 32.52,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 8.55,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 13.87,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 47.53,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 17.45,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.83,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 3.47,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 6.1,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 61.92,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 45.33,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 70.34,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 59.55,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 71.79,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 49.57,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 179.88,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 74.01,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 53.43,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 20.89,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 39.55,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 170.4,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 86.8,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 501.17,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 35.97,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 11.02,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 21.38,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 73.03,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 47.8,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 76.91,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 71.46,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 68.92,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 26.8,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1137.68,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 26.64,
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
          "id": "d714c2e603f1cf14e76f10153f30a4316c6024f8",
          "message": "Press the sent thread card's Resolve in place in the margin seats test (#6594)\n\n`test_a_pass_for_a_change_to_the_rows_seats_them_as_a_whole_pass_would`\nfails in two ways after a comment is sent from a selection. This PR\nremoves the more frequent one. `locator.click()` on the sent card's\nResolve makes Chromium scroll the document by about 444 px, even though\nResolve is already in view (y 844–872 in a 900 px window). The anchored\ncard follows that scroll a frame or two later. Playwright clicks the old\npoint, which by then is the page's heading or article, and that press\ndismisses the card. That matches the reported call log: \"article\nintercepts pointer events\", then \"element is inert\", then \"not visible\"\nuntil the timeout. The test now presses through `press_visible`\n(`tests/render_harness.py`), which exists for this Chromium behavior and\nclicks the control where it stands.\n\nUnder `leaf-dev suite flake <node> --cpu-throttle 8`, main failed 7/18\nand 5/16 copies with that signature. With this change, 3 of 18 copies\nstill fail, all at `press_visible`'s `to_be_in_viewport`, and none show\nthe scroll signature. Those three are the second failure mode, which\n#6591 keeps open. In some copies, the frame the comment box hands its\ncard at Send (`floating-response.js`, read from the field's\n`getBoundingClientRect()`) reads the box 297 px below where it paints,\nwith the same inline style, no running animation and the same `scrollY`.\nThe card adopts that offset (`comment-placement.js`, `initialHold`) and\nstands wholly below the window until a later scroll re-places it. That's\na runtime bug I haven't explained yet.\n\nThe issue's lead, `fitOpened` in #6557, is ruled out. Restoring its old\nunconditional `fitting = false` still failed 4/18.\n\nRefs #6591 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-20T08:54:59Z",
          "url": "https://github.com/max-sixty/leaf/commit/d714c2e603f1cf14e76f10153f30a4316c6024f8"
        },
        "date": 1795176235624,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1036.83,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 35.94,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.46,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 28.77,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 34.32,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 51.63,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.81,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.36,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 4,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 200.8,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 101.73,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 176.81,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 164.19,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 131.47,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 54.7,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 94.74,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 165.93,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 75.91,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 56.39,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 23.14,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 37.5,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 190.7,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 77.3,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 513.79,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 47.47,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 14.91,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 27.31,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 44.45,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 42.67,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.32,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.04,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 9,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 78.22,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 72.31,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 118.73,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 76.88,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 72.97,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 58.32,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 201.86,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 113.62,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 79.17,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 38.33,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 42.86,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 427.99,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 34.65,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 190.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 88.6,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 410.78,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 26.5,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.41,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 15.92,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 32,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 18.87,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.07,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.83,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 7.24,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 58.05,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 30.9,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 47.66,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 50.07,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 51.82,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 43.3,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 143.99,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 66.24,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 53.32,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 18.89,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.5,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 172.5,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 77.3,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 414.32,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 26.61,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 11.6,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 18.37,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 41,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 29.29,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 2.65,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.8,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 4.95,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 50.9,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 30.78,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 48.77,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 52.08,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 53.62,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 40.21,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 161.34,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 99.27,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 44.61,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 16.92,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.6,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 175.4,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 77.3,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 554.17,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 39.63,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 10.79,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 16.43,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 57.18,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 21.25,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.33,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 5.11,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 7.27,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 65.24,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 58.61,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 68.31,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 94.35,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 86.19,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 57.88,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 188.59,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 102.79,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 61.38,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 26.65,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 37.5,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 190.8,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 93.8,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 612.69,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 43.02,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 13.27,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 25.78,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 91.22,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 55,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 99.03,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 89.35,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 87.57,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 33.02,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1369.18,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 31.37,
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
          "id": "c72a8ad0319206a131c9ac549366a09224989090",
          "message": "test: read #6641's finding kinds in four browser tests (#6656)\n\n#6641 changed three things about findings without updating four browser\ntests outside the set it ran by node id. Those four failed in push run\n[44879949277](https://github.com/max-sixty/leaf/actions/runs/44879949277)\non `8faa6acf1`. This PR updates them to read the new finding kinds.\nProduct code is unchanged.\n\nThe three changes, all deliberate in #6641's audit:\n\n- A refusal's words now end with the guarantee it keeps.\n- `gate-failed` is now a not-read finding rather than a refusal: the\ngate counts as not run.\n- The new `ids-taken-by-events` check refuses an element id the log\nalready gives an event.\n\n| Test | What broke | Change |\n|---|---|---|\n| `test_browser_like_console_words_remain_console_diagnostics` |\n`str(problem)` now ends with \"(fails the check so that …)\" | compares\n`problem.said`, the console's words, which is what the test protects |\n| `test_an_async_reading_probe_is_refused_instead_of_awaited` |\n`.failures` keeps only refusing findings, so the probe's `gate-failed`\ndropped out | reads the unread findings and asserts the gate refused\nnothing; renamed `…_leaves_the_page_unread_instead_of_awaited` |\n| `test_a_rendering_turn_is_polled_from_the_driver` | same as above |\nsame as above |\n| `test_the_report_feed_reads_reports_by_typed_target` | the thread took\nthe widget's id `ag-wren` on purpose, so the test's later stamp was\nrefused | the thread is `c-wren`; a `{kind: 'thread', id: 'ag-wren'}`\ntarget still reads none of the widget's reports, and a bare id is still\nrefused |\n\nVerification: all four pass on the commit before #6641 (`67718fd12`).\nThey fail on `main` at `7abe4c3d9` with the same errors as the CI run,\nand pass on this branch.\n\nRefs #6655 — automated triage\n\nCo-authored-by: leaf-agent <leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-21T09:50:36Z",
          "url": "https://github.com/max-sixty/leaf/commit/c72a8ad0319206a131c9ac549366a09224989090"
        },
        "date": 1795262293747,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 915.51,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 34.44,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 8.92,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 28.22,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 29.98,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 45.8,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 3.66,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 0.99,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 2.71,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 162.76,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 103.17,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 154.73,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 119.22,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 126.37,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 51.91,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 87.34,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 133.58,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 75.93,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 56.36,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 19.13,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 31.05,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 152.7,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 79.3,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 466.28,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 45.15,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 13.09,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 24.93,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 39.49,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 39.04,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 6.69,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.82,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 7.61,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 79.78,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 66.5,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 111.38,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 68.35,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 66.24,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 51.43,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 176.33,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 164.81,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 71.8,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 32.05,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 39.93,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 352.43,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 34,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 184.7,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 74.3,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 367.15,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 24.67,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 9.07,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 15.23,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 30.09,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 18.56,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 1.97,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 3.21,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 6.74,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 57.9,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 29.54,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 56.39,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 47.35,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 48.87,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 40,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 172.14,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 59.65,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 48.39,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 16.38,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 31.05,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 161.7,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 61.7,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 376.05,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.88,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.43,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 16.99,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 37.21,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 27.25,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 2.65,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.74,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 5.14,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 48.32,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 30.04,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 47.04,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 48,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 50.61,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 44.61,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 143.95,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 67.05,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 45.03,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 15.93,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 31.45,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 147.2,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 75.6,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 480.16,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 34.49,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 9.46,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 16.08,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 49.76,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 20.29,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.54,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 4.03,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 7.02,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 57.92,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 57.42,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 77.69,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 72.49,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 71.93,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 48.84,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 171.24,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 91.05,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 56.37,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 19.06,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 34.5,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 164.9,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 90.7,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 542.14,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 41.6,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 10.27,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 20.41,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 84.84,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 50.58,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 86.87,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 70.91,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 76.02,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 31.54,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1150.03,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 27.66,
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
          "id": "d53e9994f4709e10feeee3fdb15b93b4e26cca10",
          "message": "fix: carry the comment box's frame through a saved-state handoff without the scroll lag (#6735)\n\nKeeps #6725's scroll compensation for Send, and stops the open comment\nbox from jumping when saved state moves what it's attached to. That jump\nturned `test_saved_widget_words_cannot_dismiss_an_unfinished_comment`\nred on main for three of its cases (`widget`, `revision`,\n`dragged-revision`) in [run\n44999105534](https://github.com/max-sixty/leaf/actions/runs/44999105534).\n\n#6725 added `floatingPlacement.lag()`, the comment box's client\nrectangle minus where its last placement stands it, measured from the\nanchor's box read now. `fabFrameAt` subtracts it so a Send in the task\nthat scrolled the page opens its card where the box paints. `fabFrameAt`\nhas a second caller, though: the handoff in `placeFab`, which adopts the\nseated editor's frame when saved state moves the box's attachment from\nquoted words to their subject. There the anchor moved because its\ncontent changed, not because of a scroll, so `lag()` counted that move\nas lag and the box jumped (247 px in the `widget` case) while the user\nwas writing.\n\n**The change** (net against `main`, one file): the frame computation now\ntakes the lag to subtract. `fabFrameAt`, which Send reads through the\nexported `frame`, still passes `lag()`. The handoff in `placeFab` passes\nzero and adopts the frame as its rectangles read, as it did before\n#6725. Both of #6725's behaviors and its regression test stay.\n\n**Verification** on the head `cf813f0fa`:\n- `test_saved_widget_words_cannot_dismiss_an_unfinished_comment` (all\nsix cases) and\n`test_a_send_in_the_task_that_scrolls_the_page_opens_the_card_where_the_box_stood`\npass: 7 passed.\n- With `fabFrameAt` also passing zero, the Send test fails with the card\n120 px off, which is the injected scroll. So the test still guards the\nSend path.\n- `pnpm run check:browser` passes.\n\nCloses #6591. The previous commit on this branch reopened it while the\nbranch reverted #6725; with #6725 kept, its second failure mode stays\nfixed.\n\nRefs #6734\n\n---------\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-22T10:23:11Z",
          "url": "https://github.com/max-sixty/leaf/commit/d53e9994f4709e10feeee3fdb15b93b4e26cca10"
        },
        "date": 1795348974502,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 992.19,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 36.4,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 11.92,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 21.23,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 34.71,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 51.85,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.65,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.31,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 3.92,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 209.57,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 94.85,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 183.19,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 136.74,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 123.76,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 54.25,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 98.58,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 147.98,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 88.24,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 97.99,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 29.15,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 38.45,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 160.2,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 78,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 480.15,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 46.69,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 16.07,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 28.93,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 46.67,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 42.67,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 7.95,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.91,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.77,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 75.52,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 71.77,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 128.67,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 71.07,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 69.69,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 58.33,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 195.31,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 119.86,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 114.27,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 45.1,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 46.11,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 391.59,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 38.65,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 210.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 93.2,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 376.24,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 25.67,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 11.97,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 14.87,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 35.21,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 18.97,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 1.95,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.66,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 7.13,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 67.2,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 34.03,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 50.14,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 50.69,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 55.67,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 38.75,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 147.55,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 70.43,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 86.99,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 23.63,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 31.9,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 160.9,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 81,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 394.22,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 25.22,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 11.78,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 17.15,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 41.92,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 26.5,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 2.46,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.58,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 4.81,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 41,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 26.38,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 50.05,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 48.52,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 52.1,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 44.42,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 148.83,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 77.7,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 88.53,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 22.36,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.9,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 157.8,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 89.2,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 534.68,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 40.7,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 11.82,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 16.5,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 58.43,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 21.32,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 4.74,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 4.24,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 7.06,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 63.01,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 60.44,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 73.95,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 91,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 83.19,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 50.82,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 197.55,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 103.81,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 106.26,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 27.6,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 36.75,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 186.8,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 97.6,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 618.59,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 42.11,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 13.09,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 25.9,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 89.9,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 54.38,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 96.81,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 87.45,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 83.02,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 33.09,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1314.67,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 28.97,
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
          "id": "c8ab9ec1df44f4bcb76df080159d478d04e67493",
          "message": "fix: strip the bootstrap's marks from failed requests' frames and order the missed stage after the page's reports (#6861)\n\nThe page-code reading (`src/leaf/render_gate/page_code.py`) reported two\nfacts in a form that depended on timing. On macOS runners both came out\nwrong often enough to fail\n`test_plain_check_reports_page_request_failures_but_ignores_optional_assets`,\nthe recovered-frame failure in #6767:\n\n- **A failed request's frame kept the bootstrap's marks.** A failure can\nreach the checker before the bootstrap's address rewrite does. When it\ndid, the image 404 named its frame\n`…/v1.html?t=test-page-key&_leaf-recovered`, with the host key the\nbootstrap strips from the address bar, and the render check's reading\ndisagreed with `run_page_code`'s. Each failure still takes its frame's\naddress when it arrives, as it did before, and `frame_address` now\nremoves the marks `bootstrap.js` removes and spells the query left as\nthe bootstrap's `URLSearchParams` does, so a marked and a rewritten\naddress read the same. Those marks are `ADDRESS_MARKS` in\n`render_checks.py`, and a test holds them to the bootstrap's list. Model\ntests cover a marked address, its rewritten spelling, and a navigation\nbetween two failures.\n- **The missed stage could come before the runtime's report.**\n`findings` appended `not-ready` before waiting for the runtime's report,\nand the report can reach the console during that wait, so the report\nsometimes followed the stage. The stage now joins the reports after the\nwait, which is the order the findings' docstring states. A wait that\nraises still leaves the stage in `reports` for `run_page_code`'s error\npath.\n\nVerified with `ci` dispatches of 54 copies of the test on the\n`test-macos` runner:\n\n- Current `main` failed 8 of 54, every one on the recovered frame ([run\n45127377819](https://github.com/max-sixty/leaf/actions/runs/45127377819)).\n- With only the frame change, 2 of 54 failed, both on the stage order\n([run\n45127381246](https://github.com/max-sixty/leaf/actions/runs/45127381246)).\n- This head passed 54 of 54 ([run\n45151463262](https://github.com/max-sixty/leaf/actions/runs/45151463262)).\n\nThe PR's `test` job fails only\n`test_every_skill_file_reads_in_one_command`, on\n`skills/leaf/references/module-input.md` at 30002 bytes; this diff\ndoesn't touch that file, `main`'s own push run fails the same way ([run\n45133210016](https://github.com/max-sixty/leaf/actions/runs/45133210016)),\nand #6826 fixes it. Locally, the test, its Firefox sibling,\n`tests/model/test_render_gate.py`, and the other `run_page_code` and\nrender-check page-code consumers pass.\n\n#6767 also tracks a Firefox wheel defect in `keepFoot` and the\nsmooth-revision-above Firefox case, which this leaves open.\n\nRefs #6767 — automated triage\n\n---------\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-11-23T10:09:05Z",
          "url": "https://github.com/max-sixty/leaf/commit/c8ab9ec1df44f4bcb76df080159d478d04e67493"
        },
        "date": 1795436024734,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1374.9,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 43.42,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 13.4,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 34.31,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 40.87,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 52.57,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 6.25,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 2.19,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 13.89,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 348.64,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 141.37,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 245.92,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 206.63,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 180.03,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 74.29,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 105.85,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 168.59,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 107.2,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 107.97,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 33.03,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 49.65,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 195.6,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 100.7,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 681.01,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 64.54,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 19.68,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 39.54,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 45.81,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 56.3,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 12.45,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.32,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 11.39,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 67.65,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 100.52,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 141.84,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 121.26,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 98.94,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 81.95,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 236.28,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 140.8,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 130.19,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 60.57,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 60.76,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 566.07,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 42.15,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 227,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 110.6,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 518.64,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 33.27,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 13.89,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 20.58,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 32.41,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 19.76,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.96,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 3.61,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 9.06,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 71.82,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 42.46,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 56.13,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 69.56,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 73.5,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 53.26,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 195.67,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 87.3,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 102.49,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 28.61,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 46,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 187.9,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 87.6,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 537.19,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 35.28,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 14.75,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 25.53,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 46.77,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 35.76,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 5.2,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.94,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 6.56,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 39.3,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 40.47,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 60.93,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 70.44,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 71.27,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 55.09,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 191.23,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 125.91,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 96.05,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 27.74,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 35.8,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 186.8,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 104.3,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 801.18,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 55.38,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 14.22,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 22.6,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 58.69,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 29.11,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 6.03,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 5.41,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 9.36,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 105.95,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 67.29,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 90.86,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 107.01,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 113.54,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 74.01,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 298.77,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 122.81,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 126.26,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 35.48,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 69,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 256.7,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 130.2,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 875,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 61.06,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 18.6,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 38.63,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 128.01,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 79.17,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 132.74,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 127.39,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 127.53,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 48.74,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 2028.3,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 43.16,
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
          "id": "e7d5808f3b0ce639888c4e1befa3a6cd3b34b6a1",
          "message": "Move el and rove into the library, and write Leaf's text field by its tag (#6998)\n\nOne step of the package-interface redesign (step six, group `lib-dom`):\nshared web code leaves the package API for the library, and a widget\nwrites Leaf's text field by its tag. `el` moves to `lib/elements.js` and\n`rove` to `lib/roving.js`, since neither reads anything of Leaf's. A\nwidget builds its text box as `offer(\"leaf-text\")`, the tag the options\npackage's CSS already writes, in place of the `TEXT_FIELD` constant; the\nruntime keeps the constant for its own readers. The package API goes\nfrom 112 names to 109.\n\nTo weigh:\n\n- **Left: the three child-list helpers.** `setChildren`, `setChildLists`\nand `setRenderedChildren` each place nodes through `move` (dom-move.js),\nwhich keeps focus in a moved node, and `setChildLists` also puts the\npage's selection back through dom-move.js. `move` stays Leaf's, so they\nstay with it; dom-children.js's header now says why it is not library\ncode.\n- **Pages.** A page's own widget importing `el` or `rove` from\n`widget-api.js` fails to load until its import changes; `page check\n--render` reports it.\n- **References.** They name the two library modules where a task needs\nthem; unscored, since no rule changed.\n\nRan `pnpm run check`, pre-commit, 13 browser tests and eight hold-still\ncases by node id, and `leaf-dev probe --base origin/main` on six pages\nin Chromium and Firefox, whose arms read the same.\n\n> _This was written by Claude Code on behalf of max-sixty_",
          "timestamp": "2026-11-24T10:07:15Z",
          "url": "https://github.com/max-sixty/leaf/commit/e7d5808f3b0ce639888c4e1befa3a6cd3b34b6a1"
        },
        "date": 1795521737025,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 969.97,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 35.08,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 9.94,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 28.34,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 26.86,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 41.54,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 5.52,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 2.22,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 5.07,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 188.63,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 81.05,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 128.69,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 121.52,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 122.4,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 52.61,
            "unit": "ms"
          },
          {
            "name": "asks: draft cpu",
            "value": 10.87,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 60.06,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 141.55,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 82.73,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 62.69,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 25.3,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 50.65,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 139.6,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 73.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 476.52,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 48.29,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.12,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 25.6,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 29.84,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 30.76,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 8.62,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.8,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.37,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 46.84,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 55.59,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 104.46,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 61.79,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 65.56,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 53.08,
            "unit": "ms"
          },
          {
            "name": "document: draft cpu",
            "value": 24.57,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 141.75,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 96.42,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 81.06,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 39.53,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 42.12,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 356.95,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 34.45,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 179,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 72,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 326.24,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 23.2,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 7.54,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 13.4,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 18.67,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 11.92,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 2.01,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 1.77,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 5.24,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 49.67,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 26.39,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 37.99,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 40.84,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 45.09,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 32.85,
            "unit": "ms"
          },
          {
            "name": "prose: draft cpu",
            "value": 10.42,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 108.57,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 57.81,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 55.36,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 22.08,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.05,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 142.4,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 62.5,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 347.85,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.54,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 9.77,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 16.79,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 29.05,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 23.88,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.15,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.84,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 4.26,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 41.37,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 27.42,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 44.32,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 47.1,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 44.16,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 39.59,
            "unit": "ms"
          },
          {
            "name": "rows: draft cpu",
            "value": 10.99,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 115.42,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 65.65,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 59.11,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 21.82,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 32.55,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 128.3,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 62.4,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 505.99,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 38.67,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 9.62,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 15.98,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 40.1,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 15.55,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.96,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 3.88,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 5.7,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 49.74,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 52.78,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 60.77,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 67.57,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 68.1,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 45.84,
            "unit": "ms"
          },
          {
            "name": "threads: draft cpu",
            "value": 12.73,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 139.76,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 82.45,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 70.86,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 28.99,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 52.55,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 162.8,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 97.3,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 633.44,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 44.52,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 13.18,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 27.04,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 87.89,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 54.02,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 90.86,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 77.94,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 79.45,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 63.08,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1213.37,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 28.86,
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
          "id": "118f31f6d9e63078ceca107d716d080c1a505ef8",
          "message": "Copy a link to any thread message, and land a reply's link on that reply (#7159)\n\nEach message drawn in a thread now shows a Copy link control (the\n`copy-link` action's link symbol) beside Copy. It copies the page's\naddress naming that message, `?thread=<id>`, without the fragment the\naddress held, and opening the link opens the thread on that message: a\nreply's link now lands on the reply (part `message`) rather than where\nopening the thread lands, and a link naming a message drawn with no row\nof its own (a reaction's chip, a step of the agent's work) lands on its\nthread, as before. The opening message's link is the thread's. `y` in a\nthread presses the Copy link of the message the user is in, else of the\nopening message, from any control of the thread, the panel's Resolve on\nits head line included; `Mod+c` (Copy) now reaches the messages from\nthere too.\n\nTo weigh: with a pointer the control shows on hover or focus, as Copy\ndoes. Under a finger it always shows, beside the reaction or Edit, since\nthe address bar names only the thread; Copy stays hidden there. On a\n390px phone the panel's message head keeps about 170px to spare with\nboth controls, so they cut no words. On a margin card, the first\nmessage's head also holds the thread's controls, so while the pointer is\non that message the wider group covers the end of its time (`10:10 AM`\nshows `10:10 A`), by the head's existing rule that controls cover the\nwords' end. The link carries no access key, like a section's link; the\nmenu's link row stays the route that adds one. `y` was unused;\n`Mod+Shift+C` opens the inspector in Chrome and Firefox.\n\nMax asked for it (\"a link to things like threads, and a button that\ncould copy the link\"); a fresh-context review of the captures and a\nCodex review read it, and Codex's four findings are folded in.\n\nTests: new browser tests copy a reply's link and the thread's (`y` from\nthe panel's Resolve) and follow the reply's link to the reply, copy a\nreply's link under a finger, open a link naming a reaction or a progress\nstep on its thread, and open a link to a message a summary folds; the\ntabbed-thread arrival test now expects focus on the reply its URL names,\nand the Copy test's show-and-hide check no longer counts two controls.\n\n> _This was written by Claude Code on behalf of max-sixty_",
          "timestamp": "2026-11-25T10:33:15Z",
          "url": "https://github.com/max-sixty/leaf/commit/118f31f6d9e63078ceca107d716d080c1a505ef8"
        },
        "date": 1795608008735,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 996.29,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 34.31,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 9.75,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 23.16,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 26.75,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 39.65,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.68,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 2.01,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 4.85,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 206.38,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 94.49,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 150.89,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 131.2,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 128.42,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 53.35,
            "unit": "ms"
          },
          {
            "name": "asks: draft cpu",
            "value": 10.91,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 71.89,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 124.45,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 74.22,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 67.11,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 23.28,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 49.35,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 143.4,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 73.5,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 494.21,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 45.03,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 14.84,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 28.2,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 34.92,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 36.39,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 7.29,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 1.04,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 9,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 62.64,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 56.45,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 104.41,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 72.98,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 115.16,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 62.18,
            "unit": "ms"
          },
          {
            "name": "document: draft cpu",
            "value": 20.3,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 161.25,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 102.79,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 88.54,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 38.26,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 46.83,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 319.28,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 36.3,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 179.3,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 89.1,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 399.61,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 25.89,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.1,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 16.36,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 24.05,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 16.25,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.19,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.96,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 6.86,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 60.41,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 31.11,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 46.27,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 50.72,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 50.37,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 43.31,
            "unit": "ms"
          },
          {
            "name": "prose: draft cpu",
            "value": 10.59,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 127.42,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 63.86,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 63.72,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 21.91,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 30.45,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 143.8,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 72.6,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 371.59,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 20.28,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 8.77,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 16.75,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 28.61,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 31.12,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 2.48,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.52,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 4.8,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 49.16,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 28.17,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 46.14,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 47.06,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 44.27,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 46.85,
            "unit": "ms"
          },
          {
            "name": "rows: draft cpu",
            "value": 8.98,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 151.41,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 65.61,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 62.74,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.58,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 30.6,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 142.4,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 77.5,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 494.39,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 26.49,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 7.83,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 17.81,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 37.22,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 14.7,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 3.31,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 3.33,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 5.31,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 56.59,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 52.49,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 61.72,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 65.34,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 62.62,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 45.78,
            "unit": "ms"
          },
          {
            "name": "threads: draft cpu",
            "value": 10.97,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 134.72,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 77.5,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 76.84,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 18.55,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 33.2,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 155.7,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 83.2,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 543.06,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 36.34,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 9.95,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 19.94,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 80.87,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 47.19,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 81.79,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 70.57,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 69.62,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 27.7,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1116.08,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 23.99,
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
          "id": "7836b3859d533958d3e85f45e2852e2e21f20960",
          "message": "Make a text field's host a group, so a screen reader hears an empty field as empty (#7267)\n\nA `leaf-text` host now takes `role=\"group\"`, and the node inside is the\nfield's one textbox. Chromium reads a textbox that isn't a native input\nby its slotted text, `aria-hidden` included, so a screen reader heard\nthe panel's empty reply box as a textbox holding \"Resolved “…” Next\nthread t\", with the Next thread button inside it and a second, empty\ntextbox inside that. Every rich hint did too: an idle margin Reply held\n\"Reply… ⏎ · New line ⇧⏎\". Now it hears a group holding the press as a\nbutton beside one empty textbox. `leaf-dev stills --base` shows no\nchange in Chromium, Firefox or WebKit.\n\nARIA allows `aria-multiline` only on a textbox, so the one-line\ndeclaration becomes Leaf's boolean `one-line`, and every reader,\n`module-input.md` included, moves to it.\n\nTo weigh: Playwright can't see into the closed root, so tests that found\na field by role textbox now call `text_field(scope, name)`, which finds\nthe `leaf-text` group by the same name and exactness. 82 locators\nchanged mechanically; 51 finding a page's own inputs stay.\n\nTests: focused browser tests (press, Undo, Next On Me, one-line options,\nrewritten locators); `pnpm run test:runtime`.\n\n> _This was written by Claude Code on behalf of max-sixty_",
          "timestamp": "2026-11-26T10:45:17Z",
          "url": "https://github.com/max-sixty/leaf/commit/7836b3859d533958d3e85f45e2852e2e21f20960"
        },
        "date": 1795694670304,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 1063.44,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 34.63,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 10.59,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 28.82,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 29.81,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 39.58,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 6.45,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.7,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 5.3,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 233.61,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 99.8,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 166.29,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 143.39,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 126.08,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 60.73,
            "unit": "ms"
          },
          {
            "name": "asks: draft cpu",
            "value": 11.4,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 72.44,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 143.18,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 87.11,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 77.71,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 24.3,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 34.15,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 147.2,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 72.7,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 499.58,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 46.71,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 15.52,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 35.68,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 34.84,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 39.54,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 17.27,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.9,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.83,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 48.34,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 76.26,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 125.09,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 72.74,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 72.34,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 68.73,
            "unit": "ms"
          },
          {
            "name": "document: draft cpu",
            "value": 24.15,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 164.08,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 106.63,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 94.44,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 40.84,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 46.65,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 356.75,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 34.2,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 205.5,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 91.2,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 393.24,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 24.7,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 10.6,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 21.29,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 23.42,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 16.25,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.33,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.47,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 6.41,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 55.72,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 32.15,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 47.02,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 48.91,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 60.33,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 46.76,
            "unit": "ms"
          },
          {
            "name": "prose: draft cpu",
            "value": 10.36,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 128.18,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 63.09,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 73.98,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 22.82,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 32.7,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 157.8,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 78.8,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 402.38,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 24.78,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 10.56,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 25.52,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 35.14,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 33.88,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 4.34,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.68,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 5.69,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 47.45,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 31.4,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 49.44,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 48.88,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 52.76,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 44.78,
            "unit": "ms"
          },
          {
            "name": "rows: draft cpu",
            "value": 10.42,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 134.32,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 69.13,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 72.34,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 21.65,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 33.2,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 157.1,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 86.2,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 587.71,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 33.5,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 10.14,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 22.92,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 46.9,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 19.79,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 6.43,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 3.05,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 6.94,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 87.05,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 49.7,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 85.41,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 83.95,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 86.35,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 68.07,
            "unit": "ms"
          },
          {
            "name": "threads: draft cpu",
            "value": 13.1,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 178.01,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 89.63,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 92.28,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 24.53,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 48.55,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 174.9,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 96.6,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 630.81,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 42.46,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 12.97,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 25.79,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 92.35,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 55.86,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 98.52,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 89.31,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 96.73,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 32.5,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1370.87,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 29.41,
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
          "id": "21c613f057621acc3e2cd6a47b1adf17540331df",
          "message": "fix: choose a comment's side again when its side runs out of room, and carry it from its subject's whole left edge (#7383)\n\nTwo browser tests about a comment box beside words that move sideways\nhave failed on `main` since #7363. This fixes both in `commentPlacement`\n(`comment-placement.js`) and keeps #7363's intent: a sideways scroll of\na box around the log still carries the comment box with its words, on\nthe side it already holds.\n\n**A held side is chosen again when it runs out of room.** #7363 keyed\nthe fresh side choice on the subject's width instead of its left and\nright edges, so motion the words share with their box no longer jumps\nthe box. It also stopped the choice when a transform carried the\nparagraph 600 px toward the right rail, which left the box `right-start`\non a side with no room. `choose` now also chooses afresh when the room\nbeside the subject on the held side no longer fits the least card width.\nThat is the test `commentSide` already chose the side by, now shared as\n`besideFits`. A sideways scroll that leaves room keeps the side, as\n#7363 intended.\n\n**The carried offset is measured from the subject's whole box.** #7363\nremoved the old edge key, so a box beside a part of a scrolled diagram\nis no longer placed afresh when the part's left edge slides under its\nscroller's edge. Its carried offset was measured from `clear.left`, the\nclipped edge, which stops moving once clipped, so the box lagged the\npart by 6 px. The offset is now measured from `extent.left`, the\nunclipped box, which moves with its content. Quoted passages still\nmeasure from their column. Both callers of `options` now pass `extent`.\n\nWhat a user sees differently from current `main`:\n- A comment box whose paragraph moves (by a transform) until the box no\nlonger fits on its side moves to the other side, as it did before #7363.\n- A box beside a partly scrolled-away diagram part follows the part\nexactly.\n\nNothing else should change. Every other placement keeps its side and\noffset.\n\nVerification:\n- On `main`,\n`test_render_aim.py::test_a_side_comment_rechooses_its_rail_after_horizontal_target_motion[inline]`\nand `[ancestor]`, and\n`test_render_reactions.py::test_a_visual_action_follows_its_own_scroller_even_when_the_target_is_gone`,\nall fail. On this branch all three pass.\n- `pnpm run test:runtime` passes 1176/1176, including #7363's runtime\ncases for a sideways scroll of the log and of a box around it.\n- `pnpm run check:framework` passes.\n- Focused browser placement tests pass, including #7363's right-to-left\nand padded-start cases and the side-keeping, rise and scroller-clip\ntests (12 tests).\n\nCloses #7380 — automated triage\n\nCo-authored-by: leaf-agent <318509791+leaf-agent@users.noreply.github.com>",
          "timestamp": "2026-11-27T10:50:26Z",
          "url": "https://github.com/max-sixty/leaf/commit/21c613f057621acc3e2cd6a47b1adf17540331df"
        },
        "date": 1795781201614,
        "tool": "customSmallerIsBetter",
        "benches": [
          {
            "name": "asks: load cpu",
            "value": 978.43,
            "unit": "ms"
          },
          {
            "name": "asks: click cpu",
            "value": 34.77,
            "unit": "ms"
          },
          {
            "name": "asks: key cpu",
            "value": 9.23,
            "unit": "ms"
          },
          {
            "name": "asks: leave cpu",
            "value": 37.72,
            "unit": "ms"
          },
          {
            "name": "asks: tab cpu",
            "value": 27.63,
            "unit": "ms"
          },
          {
            "name": "asks: walk cpu",
            "value": 39.23,
            "unit": "ms"
          },
          {
            "name": "asks: scroll cpu",
            "value": 4.96,
            "unit": "ms"
          },
          {
            "name": "asks: hover cpu",
            "value": 1.59,
            "unit": "ms"
          },
          {
            "name": "asks: aim cpu",
            "value": 4.98,
            "unit": "ms"
          },
          {
            "name": "asks: design cpu",
            "value": 210.79,
            "unit": "ms"
          },
          {
            "name": "asks: draw cpu",
            "value": 96.55,
            "unit": "ms"
          },
          {
            "name": "asks: capture cpu",
            "value": 155.14,
            "unit": "ms"
          },
          {
            "name": "asks: revision cpu",
            "value": 130.27,
            "unit": "ms"
          },
          {
            "name": "asks: stamp cpu",
            "value": 129.93,
            "unit": "ms"
          },
          {
            "name": "asks: select cpu",
            "value": 63.45,
            "unit": "ms"
          },
          {
            "name": "asks: draft cpu",
            "value": 10.07,
            "unit": "ms"
          },
          {
            "name": "asks: open cpu",
            "value": 82.95,
            "unit": "ms"
          },
          {
            "name": "asks: comment cpu",
            "value": 135.97,
            "unit": "ms"
          },
          {
            "name": "asks: resolve cpu",
            "value": 76.34,
            "unit": "ms"
          },
          {
            "name": "asks: reply cpu",
            "value": 72.48,
            "unit": "ms"
          },
          {
            "name": "asks: status cpu",
            "value": 24.34,
            "unit": "ms"
          },
          {
            "name": "asks: click shown",
            "value": 49.95,
            "unit": "ms"
          },
          {
            "name": "asks: comment shown",
            "value": 145.3,
            "unit": "ms"
          },
          {
            "name": "asks: resolve shown",
            "value": 70.7,
            "unit": "ms"
          },
          {
            "name": "document: load cpu",
            "value": 491.63,
            "unit": "ms"
          },
          {
            "name": "document: click cpu",
            "value": 46.05,
            "unit": "ms"
          },
          {
            "name": "document: key cpu",
            "value": 14.69,
            "unit": "ms"
          },
          {
            "name": "document: leave cpu",
            "value": 36.77,
            "unit": "ms"
          },
          {
            "name": "document: tab cpu",
            "value": 34.47,
            "unit": "ms"
          },
          {
            "name": "document: walk cpu",
            "value": 39.62,
            "unit": "ms"
          },
          {
            "name": "document: scroll cpu",
            "value": 15.23,
            "unit": "ms"
          },
          {
            "name": "document: hover cpu",
            "value": 0.98,
            "unit": "ms"
          },
          {
            "name": "document: aim cpu",
            "value": 8.73,
            "unit": "ms"
          },
          {
            "name": "document: design cpu",
            "value": 48.64,
            "unit": "ms"
          },
          {
            "name": "document: draw cpu",
            "value": 57.6,
            "unit": "ms"
          },
          {
            "name": "document: capture cpu",
            "value": 138.02,
            "unit": "ms"
          },
          {
            "name": "document: revision cpu",
            "value": 67.83,
            "unit": "ms"
          },
          {
            "name": "document: stamp cpu",
            "value": 65.93,
            "unit": "ms"
          },
          {
            "name": "document: select cpu",
            "value": 70.06,
            "unit": "ms"
          },
          {
            "name": "document: draft cpu",
            "value": 18.85,
            "unit": "ms"
          },
          {
            "name": "document: comment cpu",
            "value": 163.32,
            "unit": "ms"
          },
          {
            "name": "document: resolve cpu",
            "value": 100.07,
            "unit": "ms"
          },
          {
            "name": "document: reply cpu",
            "value": 88.73,
            "unit": "ms"
          },
          {
            "name": "document: status cpu",
            "value": 41.53,
            "unit": "ms"
          },
          {
            "name": "document: search cpu",
            "value": 45.35,
            "unit": "ms"
          },
          {
            "name": "document: matches cpu",
            "value": 323.18,
            "unit": "ms"
          },
          {
            "name": "document: click shown",
            "value": 37.45,
            "unit": "ms"
          },
          {
            "name": "document: comment shown",
            "value": 167,
            "unit": "ms"
          },
          {
            "name": "document: resolve shown",
            "value": 85.2,
            "unit": "ms"
          },
          {
            "name": "prose: load cpu",
            "value": 367.62,
            "unit": "ms"
          },
          {
            "name": "prose: click cpu",
            "value": 23.83,
            "unit": "ms"
          },
          {
            "name": "prose: key cpu",
            "value": 9.41,
            "unit": "ms"
          },
          {
            "name": "prose: leave cpu",
            "value": 22.32,
            "unit": "ms"
          },
          {
            "name": "prose: tab cpu",
            "value": 21.53,
            "unit": "ms"
          },
          {
            "name": "prose: walk cpu",
            "value": 15.95,
            "unit": "ms"
          },
          {
            "name": "prose: scroll cpu",
            "value": 3.01,
            "unit": "ms"
          },
          {
            "name": "prose: hover cpu",
            "value": 2.57,
            "unit": "ms"
          },
          {
            "name": "prose: aim cpu",
            "value": 9.42,
            "unit": "ms"
          },
          {
            "name": "prose: design cpu",
            "value": 51.09,
            "unit": "ms"
          },
          {
            "name": "prose: draw cpu",
            "value": 42.54,
            "unit": "ms"
          },
          {
            "name": "prose: capture cpu",
            "value": 48.44,
            "unit": "ms"
          },
          {
            "name": "prose: revision cpu",
            "value": 60.97,
            "unit": "ms"
          },
          {
            "name": "prose: stamp cpu",
            "value": 52.98,
            "unit": "ms"
          },
          {
            "name": "prose: select cpu",
            "value": 46.1,
            "unit": "ms"
          },
          {
            "name": "prose: draft cpu",
            "value": 10,
            "unit": "ms"
          },
          {
            "name": "prose: comment cpu",
            "value": 121.47,
            "unit": "ms"
          },
          {
            "name": "prose: resolve cpu",
            "value": 61.32,
            "unit": "ms"
          },
          {
            "name": "prose: reply cpu",
            "value": 69.13,
            "unit": "ms"
          },
          {
            "name": "prose: status cpu",
            "value": 21.15,
            "unit": "ms"
          },
          {
            "name": "prose: click shown",
            "value": 35.6,
            "unit": "ms"
          },
          {
            "name": "prose: comment shown",
            "value": 143.4,
            "unit": "ms"
          },
          {
            "name": "prose: resolve shown",
            "value": 78.3,
            "unit": "ms"
          },
          {
            "name": "rows: load cpu",
            "value": 371.73,
            "unit": "ms"
          },
          {
            "name": "rows: click cpu",
            "value": 23.33,
            "unit": "ms"
          },
          {
            "name": "rows: key cpu",
            "value": 9.71,
            "unit": "ms"
          },
          {
            "name": "rows: leave cpu",
            "value": 25.02,
            "unit": "ms"
          },
          {
            "name": "rows: tab cpu",
            "value": 31.7,
            "unit": "ms"
          },
          {
            "name": "rows: walk cpu",
            "value": 29.78,
            "unit": "ms"
          },
          {
            "name": "rows: scroll cpu",
            "value": 3.55,
            "unit": "ms"
          },
          {
            "name": "rows: hover cpu",
            "value": 0.41,
            "unit": "ms"
          },
          {
            "name": "rows: aim cpu",
            "value": 5.04,
            "unit": "ms"
          },
          {
            "name": "rows: design cpu",
            "value": 50.04,
            "unit": "ms"
          },
          {
            "name": "rows: draw cpu",
            "value": 30.32,
            "unit": "ms"
          },
          {
            "name": "rows: capture cpu",
            "value": 48.43,
            "unit": "ms"
          },
          {
            "name": "rows: revision cpu",
            "value": 46.32,
            "unit": "ms"
          },
          {
            "name": "rows: stamp cpu",
            "value": 48.73,
            "unit": "ms"
          },
          {
            "name": "rows: select cpu",
            "value": 40.85,
            "unit": "ms"
          },
          {
            "name": "rows: draft cpu",
            "value": 9.18,
            "unit": "ms"
          },
          {
            "name": "rows: comment cpu",
            "value": 125.45,
            "unit": "ms"
          },
          {
            "name": "rows: resolve cpu",
            "value": 65.2,
            "unit": "ms"
          },
          {
            "name": "rows: reply cpu",
            "value": 64.16,
            "unit": "ms"
          },
          {
            "name": "rows: status cpu",
            "value": 19.21,
            "unit": "ms"
          },
          {
            "name": "rows: click shown",
            "value": 30.7,
            "unit": "ms"
          },
          {
            "name": "rows: comment shown",
            "value": 143.8,
            "unit": "ms"
          },
          {
            "name": "rows: resolve shown",
            "value": 74.4,
            "unit": "ms"
          },
          {
            "name": "threads: load cpu",
            "value": 534.47,
            "unit": "ms"
          },
          {
            "name": "threads: click cpu",
            "value": 30.46,
            "unit": "ms"
          },
          {
            "name": "threads: key cpu",
            "value": 9.92,
            "unit": "ms"
          },
          {
            "name": "threads: leave cpu",
            "value": 24.7,
            "unit": "ms"
          },
          {
            "name": "threads: tab cpu",
            "value": 45.73,
            "unit": "ms"
          },
          {
            "name": "threads: walk cpu",
            "value": 19.42,
            "unit": "ms"
          },
          {
            "name": "threads: scroll cpu",
            "value": 5.34,
            "unit": "ms"
          },
          {
            "name": "threads: hover cpu",
            "value": 2.68,
            "unit": "ms"
          },
          {
            "name": "threads: aim cpu",
            "value": 6.89,
            "unit": "ms"
          },
          {
            "name": "threads: design cpu",
            "value": 80.26,
            "unit": "ms"
          },
          {
            "name": "threads: draw cpu",
            "value": 46.92,
            "unit": "ms"
          },
          {
            "name": "threads: capture cpu",
            "value": 80.67,
            "unit": "ms"
          },
          {
            "name": "threads: revision cpu",
            "value": 76.75,
            "unit": "ms"
          },
          {
            "name": "threads: stamp cpu",
            "value": 70.29,
            "unit": "ms"
          },
          {
            "name": "threads: select cpu",
            "value": 58.04,
            "unit": "ms"
          },
          {
            "name": "threads: draft cpu",
            "value": 10.33,
            "unit": "ms"
          },
          {
            "name": "threads: comment cpu",
            "value": 152.17,
            "unit": "ms"
          },
          {
            "name": "threads: resolve cpu",
            "value": 90.86,
            "unit": "ms"
          },
          {
            "name": "threads: reply cpu",
            "value": 82.29,
            "unit": "ms"
          },
          {
            "name": "threads: status cpu",
            "value": 23.57,
            "unit": "ms"
          },
          {
            "name": "threads: click shown",
            "value": 35.7,
            "unit": "ms"
          },
          {
            "name": "threads: comment shown",
            "value": 163.5,
            "unit": "ms"
          },
          {
            "name": "threads: resolve shown",
            "value": 96,
            "unit": "ms"
          },
          {
            "name": "documents: load cpu",
            "value": 625.52,
            "unit": "ms"
          },
          {
            "name": "documents: design cpu",
            "value": 43.61,
            "unit": "ms"
          },
          {
            "name": "documents: inspect cpu",
            "value": 13.07,
            "unit": "ms"
          },
          {
            "name": "documents: pick cpu",
            "value": 26.3,
            "unit": "ms"
          },
          {
            "name": "documents: part cpu",
            "value": 72.41,
            "unit": "ms"
          },
          {
            "name": "documents: draw cpu",
            "value": 54.14,
            "unit": "ms"
          },
          {
            "name": "documents: capture cpu",
            "value": 95.39,
            "unit": "ms"
          },
          {
            "name": "documents: data cpu",
            "value": 75.08,
            "unit": "ms"
          },
          {
            "name": "documents: reveal cpu",
            "value": 89.66,
            "unit": "ms"
          },
          {
            "name": "documents: search cpu",
            "value": 33.06,
            "unit": "ms"
          },
          {
            "name": "documents: matches cpu",
            "value": 1337.18,
            "unit": "ms"
          },
          {
            "name": "documents: browse cpu",
            "value": 30.25,
            "unit": "ms"
          }
        ]
      }
    ]
  }
}