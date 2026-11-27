// Watches every page for words the user typed leaving the screen without the user
// putting them away: the "Typed words survive" rule
// (browser/AGENTS.md). The browser fixture installs it on every page a test
// opens (render_harness.watched), so every test checks it.
//
// A trusted native edit names an attempt; its actual input establishes held
// words when the edit leaves text: a
// textarea, an input that takes text, an editable element, or the host of a
// `leaf-text`'s closed editor, whose `value` is the text. At every frame while any field
// holds words, each is asked whether its words are still on the page: the field itself,
// still connected and laid out (`checkVisibility`, which a field under `display: none`
// fails) and still holding them, alone or within a longer text, or else another laid-out
// field holding the same words or the same longer text, which is how a re-render hands a
// draft to the node replacing its box, and where the watch follows them. A field
// scrolled out of view is still on the page, and so is one under `visibility: hidden`,
// which is how a surface whose target a pane has scrolled past waits out of view for it
// to come back.
//
// Words that are gone are the user's to have put away, so a key or a press must come
// after the last edit, in the operation that puts the words away: Escape, Send, Cancel, a press
// elsewhere, choosing another target, or an edit in another tab of the page. That edit
// reaches this one as storage news, or, where this document reads the store before
// that news is delivered, as its own reading of the store: words this document stored
// that the store no longer holds when they leave the screen, under a key whose value
// another document changed, are that edit's to have put away. Leaf keeps its drafts on
// the page's server rather than in the browser's storage (runtime/records/drafts.js), so the
// watch reads the drafts this document writes there and what the server answers it,
// as they pass and before the page reads them, as a store of the same kind: words this
// document wrote that the server holds no longer, under a draft another document
// changed or sent, are that edit's to have put away. A write arriving after
// they left is later input, which redeems nothing. A close watcher's close, such as Android's back
// gesture makes, puts words away only where the page's storage still holds them, as Leaf's
// drafts do for kept words and for saved ones until the log accepts them: back may close an editor but
// never throw its words away (dom/keyboard/close-requests.js), whether a gesture or a
// script asked for the close. What only moves the user around the words does
// not count: a key whose typing applied or was cancelled,
// a modifier, the caret keys unless the field edits with one, Tab unless the page takes it, the page's scroll keys, and a press on the field itself. A wheel,
// a scroll, a resize, a timer and the server's news are none of them either. Words gone
// with no such key or press are reported as a `words-left-screen` record through the
// fixture's `__leafWatchFinding` binding, a browser problem which
// fails the test like any other; a test whose words go for a reason the rule allows, as
// a box's subject leaving the document, consumes the report where it causes it. Either
// way the field is no longer watched until the user types in it again.
//
// Input provenance comes from input_work_watch.js: a delayed callback retains the
// exact trusted input that scheduled it, while unrelated timers and news retain none.
// A component declaring `input` as its exact native field may commit `value` before
// that field paints. The first reading of that value edge retains its source,
// including a passive source, until the same field paints the same value. Its exact
// source survives a later native no-op, while a cancelled typing attempt revokes
// its key credit. A different field, value or actual newer edit cannot borrow it;
// words are judged only after native paint.
// A trusted native edit may enter a closed editor without DOM beforeinput.
// Its host input commits that edit only within the same native callback; a cancelled
// or no-edit attempt never suspends observation beyond its dispatch.
// Native value controls link their editor through `input` and expose the committed
// `value`; an enclosing temporary value editor also declares its editing state as
// `open`. A trusted put-away gesture's exact close, retaining that value, ends that
// editor's lifetime before its asynchronous close paint. Capture the first close edge, including a passive one, then verify it in the next native
// task after the whole callback and its microtasks: a later listener can cancel it,
// and another input cannot claim it.
// The watch keeps its own frame function, so its observation never owns page work.
(() => {
  const { frame, later: task, listen } = window.lfWatchPlatform;
  const text = (field) =>
    typeof field.value === "string" ? field.value : (field.textContent ?? "");
  // Named document properties, such as a form named "host", are not ancestry.
  // Follow slots where the field is rendered, then cross a shadow root to its host.
  const parent = (node) =>
    node.assignedSlot ??
    node.parentNode ??
    (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? node.host : null);
  // A closed dialog has put its words away, though its pixels may still be fading out
  // (an exit transition keeps it drawn in the top layer meanwhile).
  const inClosedDialog = (node) => {
    for (let at = node; at; at = parent(at))
      if (at.localName === "dialog" && !at.open) return true;
    return false;
  };
  const drawn = (node) =>
    node.isConnected && node.checkVisibility() && !inClosedDialog(node);
  // Every field of the page, through its open shadow roots; a `leaf-text` is its host.
  const FIELDS = "textarea, input, [contenteditable], leaf-text";
  function* fields(root = document) {
    for (const node of root.querySelectorAll("*")) {
      if (node.matches(FIELDS)) yield node;
      if (node.shadowRoot) yield* fields(node.shadowRoot);
    }
  }
  // The laid-out field holding these words, if any does: their text alone, or the
  // longer text a field last showed them within (`shown`).
  const shownIn = ({ words, shown }) =>
    [...fields()].find(
      (field) => drawn(field) && (text(field) === words || text(field) === shown),
    ) ?? null;
  // A field words are typed into: an input only where it takes text, not a checkbox or
  // a range, whose `value` is not words.
  const TYPED = new Set(["text", "search", "url", "email", "tel", "number"]);
  const typed = (field) =>
    field.localName === "input"
      ? TYPED.has(field.type)
      : field instanceof Element && field.matches(FIELDS);
  function* valueOwners(field) {
    let input = field;
    for (let host = input.getRootNode().host; host; host = input.getRootNode().host) {
      if (host.input !== input || typeof host.value !== "string") break;
      yield host;
      input = host;
    }
  }
  const heldEdit = (field, words, typedOrder) => ({
    words,
    typedOrder,
    // This is the owner's declared input chain, not an arbitrary ancestor's `open`.
    editor: [...valueOwners(field)].find((owner) => owner.open === true) ?? null,
    close: null,
    // The longer text the field last showed the words within, as a draft join makes.
    shown: null,
  });

  // Applied or cancelled typing cannot put words away. An uncancelled native
  // no-op retains command credit and never replaces the held words. Native keyup
  // ends the key operation, and a newer input gesture supersedes it. Native edit
  // stages retain it while focus may move to the default's editing destination.
  const MOVES =
    /^(Shift|Control|Alt|Meta|CapsLock|Tab|Arrow\w+|Home|End|PageUp|PageDown| )$/;
  const editingKeys = new WeakSet();
  // A key the field takes for an edit of its own, as Down leaving a fence, moves no one.
  const commandKeys = new WeakSet();
  listen(
    window,
    "lf-before-edit",
    () => {
      const press = window.lfInputWork.current()?.event;
      if (press?.type === "keydown") commandKeys.add(press);
    },
    true,
  );
  let key = null;
  listen(
    window,
    "keydown",
    (event) => {
      if (!event.isTrusted) return;
      key = null;
      if (!event.ctrlKey && !event.metaKey && !event.altKey)
        key = window.lfInputWork.current();
    },
    true,
  );
  listen(
    window,
    "keyup",
    (event) => {
      if (event.isTrusted && key?.event.code === event.code) key = null;
    },
    true,
  );
  listen(window, "blur", (event) => {
    if (event.isTrusted) key = null;
  });
  // beforeinput identifies the trusted native attempt; input confirms its edit.
  // leaf-text commits through its own untrusted host input, after its native input.
  // Read each input ahead of page handlers, so words a handler takes away in
  // the same turn, announcing it with an `input` of its own or not, are still the words
  // the user typed.
  const edited = new Map();
  const hostEdits = new Map();
  const heard = new WeakSet();
  window.lfInputWork.subscribeEdits((source) => {
    const { event, node: field } = source;
    if (!typed(field)) return;
    if (event.type !== "beforeinput") {
      const input = (event) => {
        // A host's canonical input need not compose through an enclosing widget.
        if (!event.composed) readInput(event);
      };
      hostEdits.set(field, { source, words: text(field), input });
      field.addEventListener("input", input, true);
      return;
    }
    const editingKey = key?.event;
    key = null;
    // A `leaf-text`'s host input is not composed: inside a widget's shadow tree, where a
    // page may carry the field between edits, only a listener on the field hears it.
    if (!heard.has(field)) {
      heard.add(field);
      listen(field, "input", (event) => event.composed || readInput(event), true);
    }
    edited.set(field, {
      typedOrder: source.order,
      key: editingKey,
      attempt: event,
      words: "",
      ready: false,
    });
    watching();
  });
  const endHostEdit = (field) => {
    field.removeEventListener("input", hostEdits.get(field).input, true);
    hostEdits.delete(field);
  };
  const readInput = (event) => {
    const edit = edited.get(event.composedPath()[0]);
    const field = event.composedPath()[0];
    const attempt = hostEdits.get(field);
    if (
      !edit &&
      field.localName === "leaf-text" &&
      drawn(field) &&
      attempt &&
      window.lfInputWork.current()?.event === attempt.source.event &&
      text(field) !== attempt.words
    ) {
      edited.set(field, {
        typedOrder: attempt.source.order,
        words: text(field),
        ready: true,
      });
      endHostEdit(field);
    }
    // leaf-text's native input precedes its host value update; its own input
    // announces the updated host. Read that announcement before page handlers. Where
    // the host announced an edit of its own first, as taking a selection away before a
    // composition over it, the native input that follows reopens the edit.
    if (
      !edit &&
      event.isTrusted &&
      field.localName === "leaf-text" &&
      holding.has(field)
    )
      edited.set(field, {
        typedOrder: holding.get(field).typedOrder,
        words: text(field),
        ready: false,
      });
    else if (edit && (event.isTrusted || field.localName === "leaf-text")) {
      if (edit.key) editingKeys.add(edit.key);
      edit.words = text(field);
      edit.ready = field.localName !== "leaf-text" || !event.isTrusted;
    }
  };
  listen(window, "input", readInput, true);

  // Each field holding words: the words, and when the user last edited them.
  const holding = new Map();
  const pending = new Map();
  // A value component names its actual field with `input` (WA input/textarea).
  // Its value commits before its native-await renderer paints the inner field.
  // Retain that exact value operation until the same field proves its paint;
  // a select's typed filter is not its `input` and never borrows its selected value.
  const painting = new Map();
  // Whether the page's storage still holds these words, bare or as a JSON string.
  const holds = (value, words) =>
    value === words || Boolean(value?.includes(JSON.stringify(words)));
  // Leaf's drafts, read off what passes between this document and the page's server:
  // the words this document last wrote of each draft, the attempts it wrote them as,
  // the words of each write still out, by the write's place among the draft's writes,
  // and what the server said it holds of each in an answer asked for after this
  // document's last write of it, null for none, with the store and its version then.
  /** @type {Map<string, string | null>} */
  const draftsWritten = new Map();
  const attemptsWritten = new Set();
  /** @type {Map<string, number>} */
  const writesOf = new Map();
  /** @type {Map<string, Map<number, string | null>>} */
  const draftsOut = new Map();
  /** @type {Map<string, {attempt: string, text: string} | null>} */
  const draftsHeld = new Map();
  /** @type {Map<string, {store: string, version: number}>} */
  const heldAt = new Map();
  const { fetch: send } = window;
  const draftPath = (input) => {
    try {
      const { pathname } = new URL(
        input instanceof Request ? input.url : input,
        location.href,
      );
      return /\/api\/drafts$/.test(pathname)
        ? "reading"
        : /\/api\/draft$/.test(pathname)
          ? "write"
          : null;
    } catch {
      return null;
    }
  };
  window.fetch = function (input, init) {
    const kind = draftPath(input);
    // Any other request passes through untouched, its promise the page's own.
    if (!kind) return send.apply(this, arguments);
    // Each draft's writes so far as this request sets out: an answer speaks of a draft
    // only where no later write of it went out meanwhile.
    const asked = new Map(writesOf);
    let context = null;
    let place = 0;
    if (kind === "write")
      try {
        const written = JSON.parse(init.body);
        ({ context } = written);
        place = (writesOf.get(context) ?? 0) + 1;
        writesOf.set(context, place);
        asked.set(context, place);
        attemptsWritten.add(written.record.attempt);
        draftsWritten.set(context, written.record.text ?? null);
        draftsOut.set(
          context,
          new Map(draftsOut.get(context)).set(place, written.record.text ?? null),
        );
        draftsHeld.delete(context);
      } catch {
        // A body the watch can't read credits nothing.
      }
    const settle = () => {
      if (context !== null) draftsOut.get(context)?.delete(place);
    };
    // A reading may be served before a write out at the time, or answered after a
    // later one, so it speaks of a draft only with nothing newer heard of its store,
    // and, with a write of it out, only of another document's words, which the page
    // takes over that write as the server would (runtime/records/drafts.js). Another store's
    // versions order nothing against the one heard before it.
    /** @param {string} key @param {string} store @param {number} version @param {{attempt: string} | null} [held] */
    const current = (key, store, version, held = null) =>
      (writesOf.get(key) ?? 0) === (asked.get(key) ?? 0) &&
      (heldAt.get(key)?.store !== store || version >= heldAt.get(key).version) &&
      (kind === "write" ||
        !draftsOut.get(key)?.size ||
        Boolean(held && !attemptsWritten.has(held.attempt)));
    /** @param {string} key @param {{attempt: string, text: string} | null} held @param {string} store @param {number} version */
    const hear = (key, held, store, version) => {
      draftsHeld.set(key, held);
      heldAt.set(key, { store, version });
    };
    return send.apply(this, arguments).then(
      async (response) => {
        if (response.ok)
          try {
            const answer = await response.clone().json();
            if (kind === "reading") {
              for (const key of new Set([
                ...draftsHeld.keys(),
                ...Object.keys(answer.drafts),
              ]))
                if (current(key, answer.store, answer.version, answer.drafts[key]))
                  hear(key, answer.drafts[key] ?? null, answer.store, answer.version);
            } else if (
              context !== null &&
              current(context, answer.store, answer.version)
            )
              hear(context, answer.record, answer.store, answer.version);
          } catch {
            // An answer the watch can't read credits nothing.
          }
        // The write stays out until its answer is heard, so no moment between the
        // response's headers and its body holds the words in neither.
        settle();
        return response;
      },
      (error) => {
        settle();
        throw error;
      },
    );
  };
  // Words a server holds, or a write of them still out, which it may yet take; a
  // write it failed or turned away keeps nothing.
  const stored = (words) => {
    if ([...draftsHeld.values()].some((held) => held?.text === words)) return true;
    if ([...draftsOut.values()].some((out) => [...out.values()].includes(words)))
      return true;
    try {
      for (let i = 0; i < localStorage.length; i++)
        if (holds(localStorage.getItem(localStorage.key(i)), words)) return true;
    } catch {
      // An opaque origin, such as a data: URL, has no storage to keep words in.
    }
    return false;
  };
  // The value this document last wrote under each local storage key, null where it
  // removed one. Only another document changes a key away from that value, so a store
  // that now holds other words under a key whose last own write held these is another
  // tab's edit having replaced them, whichever way this document came to read it.
  const written = new Map();
  let local = null;
  try {
    local = localStorage;
  } catch {
    // An opaque origin has no storage to keep words in.
  }
  if (local) {
    const { setItem, removeItem, clear } = Storage.prototype;
    Storage.prototype.setItem = function (key, value) {
      setItem.call(this, key, value);
      if (this === local) written.set(String(key), String(value));
    };
    Storage.prototype.removeItem = function (key) {
      removeItem.call(this, key);
      if (this === local) written.set(String(key), null);
    };
    Storage.prototype.clear = function () {
      clear.call(this);
      if (this === local) written.clear();
    };
  }
  // A store that refuses reads, as a page's storage may, shows no other tab's edit.
  const replacedElsewhere = (words) => {
    for (const [context, mine] of draftsWritten) {
      if (mine !== words || !draftsHeld.has(context)) continue;
      const now = draftsHeld.get(context);
      if (now === null || (now.text !== words && !attemptsWritten.has(now.attempt)))
        return true;
    }
    try {
      for (const [key, mine] of written) {
        if (!holds(mine, words)) continue;
        const now = local.getItem(key);
        if (now !== mine && !holds(now, words)) return true;
      }
    } catch {
      // Nothing this document can read credits another tab.
    }
    return false;
  };
  const putAway = (field, typedOrder, source, words) => {
    if (!source || source.order <= typedOrder) return false;
    // Native disclosure activation puts away only the fields its close hides.
    // The same dispatch cannot redeem a passive loss elsewhere on the page.
    if (source.nativeDefault) {
      if (source.event.defaultPrevented || drawn(field)) return false;
      let owner = field;
      while (owner && owner !== source.nativeDefault) owner = parent(owner);
      if (!owner) return false;
    }
    const { event, node } = source;
    // A Tab the page takes for a command of its own, as a list's Tab nests its item,
    // moves no one.
    if (event.type === "keydown")
      return (
        (!MOVES.test(event.key) ||
          commandKeys.has(event) ||
          (event.key === "Tab" && event.defaultPrevented)) &&
        !editingKeys.has(event)
      );
    if (event.type === "storage") return true;
    if (event.type === "close") return stored(words);
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
  const acknowledgeClose = (field, held, close) => {
    close.pending = false;
    if (holding.get(field) !== held && pending.get(field)?.held !== held) return;
    if (held.close !== close) return;
    const editor = held.editor;
    if (
      ![...valueOwners(field)].includes(editor) ||
      editor.open !== false ||
      close.value !== held.words ||
      editor.value !== close.value ||
      !putAway(field, held.typedOrder, close.source, held.words)
    )
      return;
    if (holding.get(field) === held) holding.delete(field);
    if (pending.get(field)?.held === held) pending.delete(field);
    painting.delete(field);
  };
  // `replaced` is whether another tab's edit had replaced the words when the loss was
  // observed, read then: a foreign write arriving after the loss cannot redeem it.
  const judge = (field, held, source, replaced) => {
    const { words, typedOrder } = held;
    // Back by the time of judging: a re-render that put them straight back.
    const heir = shownIn(held);
    if (heir) {
      holding.set(heir, held);
      watching();
      return;
    }
    if (replaced || putAway(field, typedOrder, source, words)) return;
    const place = window.lfPlace?.(field) ?? [field.localName];
    window.__leafWatchFinding({ code: "words-left-screen", words, place });
  };
  const look = (source, afterFrame = false) => {
    // Input-work orders identify new gestures, not callback execution time. Native
    // beforeinput/input are stages of the key's default; a newer pointer or command
    // gesture supersedes it, while an old sourced callback cannot end a newer key.
    if (
      key &&
      source &&
      source.order > key.order &&
      source.event !== key.event &&
      source.event.type !== "beforeinput" &&
      source.event.type !== "input"
    )
      key = null;
    if (!source && afterFrame) for (const field of hostEdits.keys()) endHostEdit(field);
    for (const [
      field,
      { typedOrder, key: editingKey, attempt, words: heard, ready },
    ] of edited) {
      if (attempt?.defaultPrevented && editingKey) editingKeys.add(editingKey);
      if (!ready && !afterFrame) continue;
      edited.delete(field);
      if (!ready) continue;
      painting.delete(field);
      // What the field holds now, or, where something emptied it in the edit's own
      // turn, what its `input` heard.
      const words = text(field).trim() ? text(field) : heard;
      if (words.trim()) holding.set(field, heldEdit(field, words, typedOrder));
      else holding.delete(field);
    }
    for (const [field, held] of holding) {
      // A native editor edit announces its new value from the host after writing it.
      // The nested input listener checkpoints before that announcement is read.
      const attempt = hostEdits.get(field);
      if (attempt && attempt.source.event === source?.event) continue;
      const owners = [...valueOwners(field)];
      const editor = held.editor;
      const linked = editor && owners.includes(editor);
      if (linked) {
        if (editor.open === true) held.close = null;
        else if (editor.open === false && !held.close) {
          const close = { source, value: editor.value, pending: !!source };
          held.close = close;
          // The next native task sees the whole callback and its microtasks. For
          // work after the input dispatch, that callback owns its own close edge.
          if (source) task(() => acknowledgeClose(field, held, close));
        }
      }
      // An uncommitted native edit attempt must not hide a separate close edge.
      if (edited.has(field)) continue;
      if (drawn(field) && text(field) === held.words) {
        const owner = owners.find((candidate) => candidate.value !== held.words);
        if (owner) {
          const operation = painting.get(field);
          if (
            !operation ||
            operation.held !== held ||
            !owners.includes(operation.owner) ||
            operation.owner.value !== operation.value ||
            operation.value !== owner.value
          )
            painting.set(field, {
              held,
              owner,
              value: owner.value,
              source,
            });
        } else painting.delete(field);
        continue;
      }
      // A field whose text grew around the words still shows them, as a draft that
      // joins another tab's words does (runtime/records/drafts.js, `bothWords`).
      if (drawn(field) && text(field).includes(held.words)) {
        held.shown = text(field);
        painting.delete(field);
        continue;
      }
      holding.delete(field);
      const operation = painting.get(field);
      painting.delete(field);
      const matched =
        operation &&
        operation.held === held &&
        owners.includes(operation.owner) &&
        operation.owner.value === operation.value &&
        drawn(field) &&
        text(field) === operation.value;
      const effectSource = matched ? operation.source : source;
      const heir = shownIn(held);
      if (heir) holding.set(heir, held);
      else
        pending.set(field, {
          held,
          source: effectSource,
          replaced: replacedElsewhere(held.words),
        });
    }
  };
  const judgePending = () => {
    for (const [field, { held, source, replaced }] of pending) {
      if (held.close?.pending) continue;
      pending.delete(field);
      judge(field, held, source, replaced);
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
