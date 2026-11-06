window.BENCHMARK_DATA = {
  "lastUpdate": 1793965355440,
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
      }
    ]
  }
}