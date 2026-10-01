// Watches every page for words the user typed leaving the screen without the user
// putting them away: the "Words stay where they were typed" rule
// (skills/leaf/assets/AGENTS.md). The browser fixture installs it on every page a test
// opens (render_harness.watched), so every test checks it.
//
// A field holds words once a trusted `beforeinput` edits it and the edit leaves text: a
// textarea, an input that takes text, an editable element, or the host of a
// `leaf-text`'s closed editor, whose `value` is the text. At every frame while any field
// holds words, each is asked whether its words are still on the page: the field itself,
// still connected and laid out (`checkVisibility`, which a field under `display: none`
// fails) and still holding them, or else another laid-out field holding the same words,
// which is how a re-render hands a draft to the node replacing its box, and where the
// watch follows them. A field scrolled out of view is still on the page, and so is one
// under `visibility: hidden`, which is how a surface whose target a pane has scrolled
// past waits out of view for it to come back.
//
// Words that are gone are the user's to have put away, so a key or a press must come
// after the last edit, within a moment of the words going: Escape, Send, Cancel, a press
// elsewhere, choosing another target, or an edit in another tab of the page that reaches
// this one as storage news. What only moves the user around the words does
// not count: a key that typed (one a trusted `beforeinput` followed), a modifier, the
// caret keys, Tab, the page's scroll keys, and a press on the field itself. A wheel,
// a scroll, a resize, a timer and the server's news are none of them either. Words gone
// with no such key or press are reported on the console as a browser problem, which
// fails the test like any other; a test whose words go for a reason the rule allows, as
// a box's subject leaving the document, consumes the report where it causes it. Either
// way the field is no longer watched until the user types in it again.
//
// The watch keeps the browser's own frame and timer functions from before the page
// loads, so a test that counts the frames or timers a page asks for counts none of its.
(() => {
  const frame = window.requestAnimationFrame.bind(window);
  const later = window.setTimeout.bind(window);
  const cancel = window.clearTimeout.bind(window);
  // How long before the words went a key or press may come and still be what put them
  // away, a send whose answer re-renders the box; and how long after, a press whose
  // surface closes before the press's own click arrives.
  const BEFORE = 2000;
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

  // The recent keys and presses that can put words away: when, and for a press, the
  // node pressed, which a field's own press is not.
  const gestures = [];
  const gestured = (at, node = null) => {
    gestures.push({ at, node });
    if (gestures.length > 20) gestures.shift();
  };
  // A press in this document, or in a same-origin document holding it, as a sample's
  // host page drives the sample inside it, on this document's clock.
  for (let view = window; ; view = view.parent) {
    let held;
    try {
      held = view.document;
    } catch {
      break;
    }
    const skew = view.performance.timeOrigin - performance.timeOrigin;
    for (const type of [
      "pointerdown",
      "mousedown",
      "touchstart",
      "click",
      "contextmenu",
    ])
      held.addEventListener(
        type,
        (event) => {
          if (event.isTrusted)
            gestured(event.timeStamp + skew, event.composedPath()[0]);
        },
        true,
      );
    if (view === view.parent) break;
  }
  // The same user's edit in another tab of the page, which reaches this one as storage
  // news and may take the words over: what they did there they did here.
  addEventListener("storage", (event) => {
    if (event.isTrusted) gestured(event.timeStamp);
  });
  // Keys that move the user among the words, or the page under them, rather than
  // doing anything to them.
  const MOVES =
    /^(Shift|Control|Alt|Meta|CapsLock|Tab|Arrow\w+|Home|End|PageUp|PageDown| )$/;
  // A key counts from its keydown, and a `beforeinput` following it in the same task
  // takes it back as typing; a chord is a command whatever the field makes of it, as
  // Linux's Chrome still hands a contenteditable the line break of a Control+Enter the
  // page sent on.
  let key = null;
  addEventListener(
    "keydown",
    (event) => {
      if (!event.isTrusted || MOVES.test(event.key)) return;
      const at = event.timeStamp;
      gestured(at);
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      key = at;
      later(() => {
        if (key === at) key = null;
      });
    },
    true,
  );
  // Fields a trusted `beforeinput` named, with when, read at the next frame once the edit
  // has applied. `beforeinput` rather than `input`: a `leaf-text` announces its edits
  // with an `input` of its own making, which is not trusted. The edit's own `input` is
  // read too, ahead of the page's handlers, so words a handler takes away in the same
  // turn are still the words the user typed.
  const edited = new Map();
  addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      if (key !== null && gestures.at(-1)?.at === key) gestures.pop();
      key = null;
      const field = event.composedPath()[0];
      if (!typed(field)) return;
      edited.set(field, { typedAt: event.timeStamp, words: "" });
      watching();
    },
    true,
  );
  addEventListener(
    "input",
    (event) => {
      const edit = edited.get(event.composedPath()[0]);
      if (edit) edit.words = text(event.composedPath()[0]);
    },
    true,
  );

  // Each field holding words: the words, and when the user last edited them.
  const holding = new Map();
  const putAway = (field, typedAt, gone) =>
    gestures.some(
      ({ at, node }) =>
        at > typedAt &&
        at >= gone - BEFORE &&
        at <= gone + AFTER &&
        !(node && (node === field || field.contains(node))),
    );
  const judge = (field, { words, typedAt }, gone) => {
    if (putAway(field, typedAt, gone)) return;
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
  const look = () => {
    const at = performance.now();
    for (const [field, { typedAt, words: heard }] of edited) {
      // What the field holds now, or, where something emptied it in the edit's own
      // turn, what its `input` heard.
      const words = text(field).trim() ? text(field) : heard;
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
        pending.set(due, later(due, AFTER));
      }
    }
  };
  // One frame at a time while there is anything to watch, and none on a page nobody has
  // typed in.
  let looking = false;
  const watch = () => {
    look();
    looking = holding.size > 0 || edited.size > 0;
    if (looking) frame(watch);
  };
  const watching = () => {
    if (looking) return;
    looking = true;
    frame(watch);
  };
  // Every loss so far judged now, with no more keys or presses to wait for: the browser
  // fixture awaits this as the test body returns (`render_harness.judge_watches`).
  window.lfWordsJudged = () => {
    look();
    for (const [due, timer] of pending) {
      cancel(timer);
      due();
    }
  };
})();
