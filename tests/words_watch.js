// Watches every page for words the user typed leaving the screen without the user
// putting them away: the "Words stay where they were typed" rule
// (skills/leaf/assets/AGENTS.md). The browser fixture installs it on every page a test
// opens (render_harness.watched), so every test checks it.
//
// A field holds words once a trusted `beforeinput` edits it and text is left in it: a
// textarea, an input that takes text, an editable element, or the host of a
// `leaf-text`'s closed editor, whose `value` is the text. At every frame each such field
// is asked whether its words are still on the page: the field itself, still connected
// and laid out (`checkVisibility`, which a field under `display: none` fails) and still
// holding them, or else another
// laid-out field holding the same words, which is how a re-render hands a draft to the
// node replacing its box, and where the watch follows them. A field scrolled out of view
// is still on the page, and so is one under `visibility: hidden`, which is how a surface
// whose target a pane has scrolled past waits out of view for it to come back.
//
// Words that are gone are the user's to have put away, so a key or a press must come
// after the last edit and by shortly after the words went: Escape, Send, Cancel, a press
// elsewhere, choosing another target. A key that typed (one a trusted `beforeinput`
// followed) is editing, not putting away; a wheel, a scroll, a resize, a timer and the
// server's news are none of them. Words gone with no such key or press are reported on
// the console as a browser problem, which fails the test like any other. Either way the
// field is no longer watched until the user types in it again.
(() => {
  // How long after the words went a key or press may come and still be what put them
  // away: a press whose surface closes before the press's own click arrives.
  const AFTER = 200;
  const text = (field) =>
    typeof field.value === "string" ? field.value : (field.textContent ?? "");
  const drawn = (node) => node.isConnected && node.checkVisibility();
  // Every field of the page, through its open shadow roots; a `leaf-text` is its host.
  const FIELDS = "textarea, input, [contenteditable], leaf-text";
  function* fields(root = document) {
    for (const node of root.querySelectorAll("*")) {
      if (node.matches(FIELDS)) yield node;
      if (node.shadowRoot) yield* fields(node.shadowRoot);
    }
  }
  // The laid-out field holding these words, if any does.
  const shownIn = (words) =>
    [...fields()].find((field) => drawn(field) && text(field) === words) ?? null;
  // A field words are typed into: an input only where it takes text, not a checkbox or
  // a range, whose `value` is not words.
  const TYPED = new Set(["text", "search", "url", "email", "tel", "number"]);
  const typed = (field) =>
    field instanceof HTMLInputElement
      ? TYPED.has(field.type)
      : field instanceof Element && field.matches(FIELDS);

  // When the user last did something that can put words away: a press, or a key that
  // did not type.
  let gesture = -Infinity;
  let key = null;
  for (const type of ["pointerdown", "mousedown", "touchstart", "click", "contextmenu"])
    addEventListener(
      type,
      (event) => {
        if (event.isTrusted) gesture = event.timeStamp;
      },
      true,
    );
  addEventListener(
    "keydown",
    (event) => {
      if (!event.isTrusted) return;
      key = event.timeStamp;
      // A key that types fires its `beforeinput` in this same task, after its keydown.
      setTimeout(() => {
        if (key !== null) gesture = Math.max(gesture, key);
        key = null;
      });
    },
    true,
  );
  // Fields a trusted `beforeinput` named, with when, read at the next frame once the edit
  // has applied. `beforeinput` rather than `input`: a `leaf-text` announces its edits
  // with an `input` of its own making, which is not trusted.
  const edited = new Map();
  addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      key = null;
      const field = event.composedPath()[0];
      if (typed(field)) edited.set(field, event.timeStamp);
    },
    true,
  );

  // Each field holding words: the words, and when the user last edited them.
  const holding = new Map();
  const judge = (field, { words, typedAt }, gone) => {
    if (gesture > typedAt && gesture <= gone + AFTER) return;
    // Back by the time of judging: a re-render that put them straight back.
    if (shownIn(words)) return;
    const place = window.lfPlace?.(field) ?? field.localName;
    console.error(
      `typed words left the screen without a key or press: ${JSON.stringify(words)}` +
        ` in ${place}`,
    );
  };
  // Losses waiting out AFTER for the key or press that may still answer for them.
  const pending = new Map();
  const look = (at) => {
    for (const [field, typedAt] of edited) {
      const words = text(field);
      if (words.trim()) holding.set(field, { words, typedAt });
      else holding.delete(field);
    }
    edited.clear();
    for (const [field, held] of holding) {
      if (drawn(field) && text(field) === held.words) continue;
      holding.delete(field);
      const heir = shownIn(held.words);
      if (heir) holding.set(heir, held);
      else {
        const due = () => {
          pending.delete(due);
          judge(field, held, at);
        };
        pending.set(due, setTimeout(due, AFTER));
      }
    }
  };
  const watch = (at) => {
    look(at);
    requestAnimationFrame(watch);
  };
  requestAnimationFrame(watch);
  // Every loss so far judged now, with no more keys or presses to wait for: the browser
  // fixture awaits this as the test body returns (`render_harness.judge_watches`).
  window.lfWordsJudged = () => {
    look(performance.now());
    for (const [due, timer] of pending) {
      clearTimeout(timer);
      due();
    }
  };
})();
