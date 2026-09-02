import { outbox } from "../outbox.js";
import { measure, reserve } from "../widget-elements.js";

/* Settlement controls share the outbox across panel and inline views. */
export function createThreadSettlement({ keys, offer, paintKeys, post, PRESS }) {
  const news = "lf-thread-settlement";
  const pendingSettlement = (id) =>
    outbox.find(
      ({ event }) =>
        event.parent === id && (event.kind === "resolve" || event.kind === "unresolve"),
    );
  const busy = (id) => Boolean(pendingSettlement(id));
  const tell = (id) =>
    document.dispatchEvent(new CustomEvent(news, { detail: { id } }));

  function settlementControl(t, { prepareLanding } = {}) {
    const id = t.root.id;
    const reopen = Boolean(t.resolved);
    const kind = reopen ? "unresolve" : "resolve";
    const word = reopen ? "Reopen" : "Resolve";
    const pendingWord = reopen ? "Reopening…" : "Resolving…";
    const button = offer(
      "button",
      reopen ? "lf-btn lf-reopen lf-thread-action" : "lf-btn lf-resolve",
      word,
    );
    const sync = () => {
      // A fold owns its accepted outcome until it removes the old control.
      if (button.closest(".lf-going")) return;
      const pending = pendingSettlement(id);
      button.setAttribute("aria-disabled", String(Boolean(pending)));
      button.setAttribute("aria-busy", String(Boolean(pending)));
      button.textContent = pending?.event.kind === kind ? pendingWord : word;
    };
    const update = (ev) => {
      if (!button.isConnected) return document.removeEventListener(news, update);
      if (ev.detail.id !== id) return;
      sync();
    };
    document.addEventListener(news, update);
    button.onclick = async () => {
      if (busy(id)) return;
      const land = prepareLanding?.();
      const sent = post({ kind, parent: id });
      tell(id);
      paintKeys();
      try {
        if (await sent) land?.();
      } finally {
        tell(id);
        paintKeys();
      }
    };
    keys(button, `On a thread's ${word} button`, [
      {
        id: reopen ? "thread.reopen" : "thread.resolve",
        keys: [...PRESS, "x"],
        does: `${word} it`,
        line: word.toLowerCase(),
        when: () => !busy(id),
        run: () => button.click(),
      },
    ]);
    // Showing one view can release a hidden control's measurement during resize
    // delivery. Reserve outside that delivery because its thread also observes size.
    const fit = () => reserve(button, [word, pendingWord, "✓ Resolved"]);
    measure(button, () => requestAnimationFrame(() => measure(button, fit)));
    sync();
    return button;
  }

  return { settlementControl };
}

/* Resolution-fold state and motion for comment-panel threads. */
export function createThreadFolding({ FOLD_MS, motion, renderPanel, threadsBox }) {
  // A thread the log has resolved and the open list is still holding. Its place is not
  // given up in the frame the log settles it: the node stays where it stood, says what
  // was done to it on the control that was pressed, and folds, so the threads under it
  // rise where the eye can follow instead of arriving somewhere else. The disclosure
  // gets the thread when the fold is over, which is what keeps one node per thread the
  // whole way through.
  //
  // Driven from the reconcile rather than from the press, because the log is what
  // resolves a thread and a resolve with no gesture behind it — a second tab's, or the
  // agent's — takes the same room out of the same list. That is the case that needs the
  // motion more: nothing in this tab moved, so the fold is the only thing saying so.
  //
  // Everything that walks the list asks for .lf-thread, so the one rename takes the
  // node out of t/T, out of the g addresses, out of x's press and out of what the panel
  // repaints, in a stroke: what stands there is room, not a thread. `inert` says the
  // same to the pointer and the tab order, so the fold can't be pressed a second time
  // or typed into on its way out.
  //
  // Null where there is nothing to fold: a thread this page never drew open, or a
  // reader who asked for less motion, for whom the room goes in the frame it always did.
  const folding = new Map(); // thread id -> the node folding out of the open list
  function foldOut(t) {
    const going = folding.get(t.root.id);
    // For as long as it stands in the list, which is the whole of what the record
    // claims. A reader who reopens a thread mid-fold has that render drop the folding
    // node from the list, and the entry left behind names a node in nothing: handed
    // back when they settle the thread again, it would stand a spent animation where
    // the thread is, saying what the thread said before it reopened, and the thread
    // would leave with no fold at all. The node's own connectedness is that fact, read
    // here rather than written from wherever a node leaves the list, which is the
    // difference between one writer and every caller of setChildren remembering.
    // Dropped rather than passed over, because the two returns below leave without
    // setting one, and an entry over a thread nothing is folding hides that thread
    // from the disclosure that should be holding it by then.
    if (going?.isConnected) return going;
    folding.delete(t.root.id);
    const node = threadsBox.querySelector(
      `:scope > .lf-thread[data-id="${t.root.id}"]`,
    );
    if (!node) return null;
    // Measured before anything about the node changes, and stated as a border box —
    // the measurement to hand is the rendered one, and .lf-going sizes to match. The
    // border and padding go with the height because border-box floors the box at
    // their sum: left standing, they would hold 22px open under a height of zero.
    const style = getComputedStyle(node);
    const from = {
      height: node.getBoundingClientRect().height + "px",
      marginBottom: style.marginBottom,
      borderTopWidth: style.borderTopWidth,
      borderBottomWidth: style.borderBottomWidth,
      paddingTop: style.paddingTop,
      paddingBottom: style.paddingBottom,
      opacity: 1,
    };
    const to = Object.fromEntries(Object.keys(from).map((k) => [k, "0px"]));
    to.opacity = 0;
    const played = motion(node, [from, to], FOLD_MS);
    if (!played) return null;
    // The pressed control states the outcome in the room it already reserved. Send
    // stays in the row with visibility hidden, keeping its room without reading as live.
    const resolve = node.querySelector(
      ":scope > .lf-compose > .lf-thread-actions > .lf-resolve",
    );
    resolve.textContent = "✓ Resolved";
    resolve.setAttribute("aria-busy", "false");
    node.className = "lf-going";
    if (node.matches(":focus-within")) threadsBox.focus({ preventScroll: true });
    node.inert = true;
    folding.set(t.root.id, node);
    // Straight off the promise, and nothing between: motion() holds the last keyframe
    // while this direct reaction reconciles the node away, then its shared reaction
    // releases the effect. `renderPanel` remains the list's one writer, so it can hold
    // a surviving card through the final removal. Deferring this cleanup past that
    // contract would put the whole thread back before it goes. What holds the line is
    // test_the_fold_never_paints_a_frame_that_undoes_the_last, since no held frame can
    // see it.
    played.finished.then(() => {
      // This node's own entry, never whatever the thread's key holds now: a fold the
      // line above superseded is still running, and the older one finishing must not
      // take the live one's record with it.
      if (folding.get(t.root.id) === node) folding.delete(t.root.id);
      renderPanel();
    });
    return node;
  }

  return {
    foldOut,
    hasFolding: () => [...folding.values()].some((node) => node.isConnected),
    isFolding: (id) => folding.has(id),
  };
}
