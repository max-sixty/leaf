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
// after the last edit, in the operation that puts the words away: Escape, Send, Cancel, a press
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
// Input provenance comes from input_work_watch.js: a delayed callback retains the
// exact trusted input that scheduled it, while unrelated timers and news retain none.
// A component declaring `input` as its exact native field may commit `value` before
// that field paints. The first reading of that value edge retains its source,
// including a passive source, until the same field paints the same value. A different
// field, value or newer edit cannot borrow it; words are judged only after native paint.
// A trusted paste may edit a closed editor without native beforeinput. Its own host
// input commits that edit only within the same paste callback; a cancelled or no-edit
// paste never suspends observation, and its unused attempt ends with the dispatch.
// The watch keeps its own frame function, so its observation never owns page work.
(() => {
  const frame = window.lfWatchPlatform.frame;
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

  // A key that edits is not a command putting words away. beforeinput withdraws
  // its keydown's credit in the same dispatch turn; command chords retain theirs.
  const MOVES =
    /^(Shift|Control|Alt|Meta|CapsLock|Tab|Arrow\w+|Home|End|PageUp|PageDown| )$/;
  const editingKeys = new WeakSet();
  let key = null;
  const clearKey = window.lfWatchPlatform.later;
  addEventListener(
    "keydown",
    (event) => {
      if (!event.isTrusted || event.ctrlKey || event.metaKey || event.altKey) return;
      key = event;
      clearKey(() => {
        if (key === event) key = null;
      });
    },
    true,
  );
  // Fields a trusted `beforeinput` named, with when, read at the next frame once the edit
  // has applied. `beforeinput` rather than `input`: a `leaf-text` announces its edits
  // with an `input` of its own making, which is not trusted. The edit's own trusted
  // `input` is read too, ahead of the page's handlers, so words a handler takes away in
  // the same turn, announcing it with an `input` of its own or not, are still the words
  // the user typed.
  const edited = new Map();
  const pasting = new Map();
  addEventListener(
    "paste",
    (event) => {
      const field = event.composedPath()[0];
      if (event.isTrusted && typed(field)) {
        const input = (event) => {
          // A host's canonical input need not compose through an enclosing widget.
          if (!event.composed) readInput(event);
        };
        pasting.set(field, {
          source: window.lfInputWork.current(),
          words: text(field),
          input,
        });
        field.addEventListener("input", input);
      }
    },
    true,
  );
  addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      if (key !== null) editingKeys.add(key);
      key = null;
      const field = event.composedPath()[0];
      if (!typed(field)) return;
      edited.set(field, {
        typedOrder: window.lfInputWork.current().order,
        words: "",
        ready: false,
      });
      watching();
    },
    true,
  );
  const endPaste = (field) => {
    field.removeEventListener("input", pasting.get(field).input);
    pasting.delete(field);
  };
  const readInput = (event) => {
    const edit = edited.get(event.composedPath()[0]);
    const field = event.composedPath()[0];
    const paste = pasting.get(field);
    if (
      !edit &&
      field.localName === "leaf-text" &&
      drawn(field) &&
      paste &&
      window.lfInputWork.current()?.event === paste.source.event &&
      text(field) !== paste.words
    ) {
      edited.set(field, {
        typedOrder: paste.source.order,
        words: text(field),
        ready: true,
      });
      endPaste(field);
    }
    // leaf-text's native input precedes its host value update; its own input
    // announces the updated host. Read that announcement before page handlers.
    if (edit && (event.isTrusted || field.localName === "leaf-text")) {
      edit.words = text(field);
      edit.ready = field.localName !== "leaf-text" || !event.isTrusted;
    }
  };
  addEventListener("input", readInput, true);

  // Each field holding words: the words, and when the user last edited them.
  const holding = new Map();
  const pending = new Map();
  // A value component names its actual field with `input` (WA input/textarea).
  // Its value commits before its native-await renderer paints the inner field.
  // Retain that exact value operation until the same field proves its paint;
  // a select's typed filter is not its `input` and never borrows its selected value.
  const painting = new Map();
  const valueOwner = (field) => {
    const host = field.getRootNode().host;
    return host?.input === field && typeof host.value === "string" ? host : null;
  };
  const putAway = (field, typedOrder, source) => {
    if (!source || source.order <= typedOrder) return false;
    // Native disclosure activation puts away only the fields its close hides.
    // The same dispatch cannot redeem a passive loss elsewhere on the page.
    if (source.nativeDefault) {
      if (source.event.defaultPrevented || drawn(field)) return false;
      let owner = field;
      while (owner && owner !== source.nativeDefault)
        owner = owner.parentNode ?? owner.host;
      if (!owner) return false;
    }
    const { event, node } = source;
    if (event.type === "keydown")
      return !MOVES.test(event.key) && !editingKeys.has(event);
    if (event.type === "storage") return true;
    return (
      [
        "pointerdown",
        "mousedown",
        "touchstart",
        "pointerup",
        "mouseup",
        "touchend",
        "click",
        "contextmenu",
      ].includes(event.type) && !(node && (node === field || field.contains(node)))
    );
  };
  const judge = (field, { words, typedOrder }, source) => {
    // Back by the time of judging: a re-render that put them straight back.
    const heir = shownIn(words);
    if (heir) {
      holding.set(heir, { words, typedOrder });
      watching();
      return;
    }
    if (putAway(field, typedOrder, source)) return;
    const place = window.lfPlace?.(field) ?? field.localName;
    console.error(
      `typed words left the screen without a key or press: ${JSON.stringify(words)}` +
        ` in ${place}`,
    );
  };
  const look = (source, afterFrame = false) => {
    if (!source && afterFrame) for (const field of pasting.keys()) endPaste(field);
    for (const [field, { typedOrder, words: heard, ready }] of edited) {
      if (!ready && !afterFrame) continue;
      edited.delete(field);
      // What the field holds now, or, where something emptied it in the edit's own
      // turn, what its `input` heard.
      const words = text(field).trim() ? text(field) : heard;
      if (words.trim()) holding.set(field, { words, typedOrder });
      else holding.delete(field);
    }
    for (const [field, held] of holding) {
      // beforeinput has named the next edit, but its trusted input has not read it.
      if (edited.has(field)) continue;
      // A paste transaction announces its new value from the host after writing it.
      // The nested input listener checkpoints before that announcement is read.
      const paste = pasting.get(field);
      if (paste && paste.source.event === source?.event) continue;
      const owner = valueOwner(field);
      if (drawn(field) && text(field) === held.words) {
        if (owner && owner.value !== held.words) {
          const operation = painting.get(field);
          if (operation?.owner !== owner || operation.value !== owner.value)
            painting.set(field, { owner, value: owner.value, source });
        } else painting.delete(field);
        continue;
      }
      holding.delete(field);
      const operation = painting.get(field);
      painting.delete(field);
      const effectSource =
        operation &&
        owner === operation.owner &&
        owner.value === operation.value &&
        drawn(field) &&
        text(field) === operation.value
          ? operation.source
          : source;
      const heir = shownIn(held.words);
      if (heir) holding.set(heir, held);
      else pending.set(field, { held, source: effectSource });
    }
  };
  const judgePending = () => {
    for (const [field, { held, source }] of pending) {
      pending.delete(field);
      judge(field, held, source);
    }
  };
  // One frame at a time while there is anything to watch, and none on a page nobody has
  // typed in.
  let looking = false;
  const watch = () => {
    if (!window.lfInputWork.dispatching()) look(undefined, true);
    judgePending();
    looking = holding.size > 0 || edited.size > 0 || pending.size > 0;
    if (looking) frame(watch);
  };
  const watching = () => {
    if (looking) return;
    looking = true;
    frame(watch);
  };
  window.lfInputWork.subscribe(look);
  // Losses are read at the operation's own checkpoint; a frame also sees passive
  // work. No later input is allowed to redeem words already lost.
  window.lfWordsJudged = async () => {
    await window.lfInputWork.dispatched();
    look(undefined, true);
    judgePending();
  };
})();
