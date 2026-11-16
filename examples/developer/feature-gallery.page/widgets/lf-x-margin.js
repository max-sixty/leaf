/* A margin a page draws for itself, through the public package interface alone.

   On a page whose `body` has `data-annotations="page"`, Leaf draws no margin, marks or
   thread cards. This widget supplies them: a mark beside each commented passage, a tint
   on its words, the open thread's card and the comment box beside theirs, and the
   page's On Me marks and contributed actions beside what they are about. Leaf keeps
   every thread, message, draft and obligation; the widget only chooses where each
   stands (module-annotations.md, "Page annotation presentation").

   It takes no room in the page: every box it draws is fixed and anchored to the words
   it stands by, so the browser carries it with them through each scroll. Where the
   window has no room right of the reading column, each mark stands as a pin at the
   window's edge, its symbol alone, and a card stands under its passage. */
import {
  LeafElement,
  PAGE_INTERFACE,
  anchorTo,
  commandScope,
  commandsChanged,
  consumeAnnotations,
  contributionItemKey,
  focusDestination,
  focused,
  frameFor,
  keeps,
  keepsHidden,
  keepsText,
  nameAction,
  offer,
  offerAction,
  placePageThreads,
  plainPress,
  previewChanged,
  setChildren,
  sizeObserver,
  threadActions,
  threadSummary,
  under,
  watchAnnotationLayer,
  whileConnected,
  worksInside,
} from "/runtime/widget-api.js";
import { computePosition, flip, offset, shift } from "/vendor/floating-ui.esm.js";

const TINT = "lf-x-margin-passage";
const GAP = 12; // between the reading column and the marks
const RAIL = 184; // the room a mark with its words takes right of the column
const STACK = 4; // between two marks beside one line
const CARD_GAP = 40; // a card stands right of the marks

const STYLE = `
@layer lf-base {
  lf-x-margin { position: absolute; inline-size: 0; block-size: 0; }
  /* Fixed from the start, so each box has its own size before it is first placed.
     A mark goes while a box has scrolled its words out of sight. */
  lf-x-margin .xm-mark {
    position: fixed; position-visibility: var(--lf-anchor-visible);
    display: flex; align-items: center; gap: var(--lf-sp-1);
    inline-size: max-content; z-index: 2;
    color: var(--lf-thread); font: var(--lf-t-6)/1.3 var(--lf-sans);
  }
  lf-x-margin .xm-mark[data-turn] { color: var(--lf-turn-ink); }
  lf-x-margin .xm-mark[data-progress="working"] { color: var(--lf-work); }
  lf-x-margin .xm-word {
    max-inline-size: 9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  lf-x-margin .xm-word:empty { display: none; }
  /* A pin stands over the page's words, so it keeps to its symbol on the page's ground. */
  lf-x-margin[data-pinned] .xm-mark {
    border-radius: var(--lf-r); background: var(--lf-paper);
  }
  lf-x-margin[data-pinned] .xm-word { display: none; }
  /* A card is where the user writes, so it stays drawn while its words scroll out of
     a box, where a mark goes with them. */
  lf-x-margin .xm-card {
    position: fixed; z-index: 3; position-visibility: always;
    inline-size: min(18rem, calc(100vw - 16px)); max-block-size: 70vh; overflow: auto;
    --lf-ground: var(--lf-card);
    padding: var(--lf-sp-2); border: 1px solid var(--lf-border);
    border-radius: var(--lf-r); background: var(--lf-ground); color: var(--lf-ink);
    box-shadow: var(--lf-raise-2);
  }
  /* A wash of the theme's thread colour. The rule matches each element holding the
     words, since Firefox resolves a highlight's style from that element's rules alone. */
  ::highlight(${TINT}) {
    background-color: oklch(from var(--lf-thread) l c h / 0.16);
  }
}`;

// The lines a placement's words start on, and the node the browser carries a box
// beside them with: a passage's first range, else the element it stands by.
function standing({ place, ranges }) {
  const [range] = ranges ?? [];
  const lines = range ? [...range.getClientRects()].filter((line) => line.width) : [];
  return lines.length
    ? { lines, context: range.startContainer }
    : { lines: [place.getBoundingClientRect()], context: place };
}

customElements.define(
  "lf-x-margin",
  class extends LeafElement {
    #marks = offer("div", "xm-marks");
    #cards = offer("div", "xm-cards");
    #surface = null;
    #view = null;
    #activate = null; // runs an inventory item, from the view Leaf last painted with
    #targets = [];
    #threadMarks = new Map(); // thread key -> {node, press, word, placement}
    #rows = new Map(); // inventory entry key -> {node, items, placement}
    #outlets = new Map(); // thread key -> outlet
    #composer = null; // the comment box's outlet, while Leaf asks for one
    #composing = null; // the comment box's placement
    #open = null; // the key of the thread whose card is open
    #hidden = false;
    #tinted = new Map(); // tinted range -> thread key
    #previewed = new Set(); // the elements given a preview of their commented words
    #pointer = null; // the pointer's last move or press
    #aimed = null; // the commented words under it: {key, place, line}
    #schedule = frameFor(this, () => this.#layout());
    #aim = frameFor(this, () => this.#readAim());
    // A key pressed in a thread goes to the scopes on its outlet, then to the page
    // (module-input.md, "How scopes compose"), so the card's Escape is declared on each
    // outlet. Leaf's own steps inside the thread come first.
    #cardKeys = commandScope("In a margin card", [
      {
        id: "xmargin.card.close",
        keys: ["Escape"],
        title: "Close the thread card",
        run: () => this.#close(),
      },
    ]);

    createRenderRoot() {
      return this;
    }

    setup() {
      const style = document.createElement("style");
      style.textContent = STYLE;
      this.append(style, this.#marks, this.#cards);
      whileConnected(this, (signal) => {
        this.#surface = placePageThreads(
          this,
          (targets, context) => this.#placeThreads(targets, context),
          { reveal: (key) => this.#reveal(key) },
        );
        this.#view = consumeAnnotations(this, (entries, view) =>
          this.#placeEntries(entries, view),
        );
        const stopHiding = watchAnnotationLayer((hidden) => this.#hide(hidden));
        addEventListener("resize", this.#schedule, { signal });
        document.addEventListener(PAGE_INTERFACE, this.#schedule, { signal });
        document.addEventListener("click", (event) => this.#pressWords(event), {
          signal,
        });
        for (const type of ["pointermove", "pointerdown"])
          document.addEventListener(
            type,
            (event) => {
              this.#pointer = event;
              this.#aim();
            },
            { signal, passive: true },
          );
        const sizes = sizeObserver(this.#schedule);
        sizes.observe(this.#column());
        sizes.observe(this.#cards);
        return () => {
          stopHiding();
          sizes.disconnect();
          this.#surface.unregister();
          this.#view.unregister();
          this.#surface = this.#view = null;
          CSS.highlights.delete(TINT);
          for (const place of this.#previewed) delete place.lfPreview;
          this.#previewed.clear();
        };
      });
    }

    #column() {
      return this.closest("main") ?? document.body;
    }

    // Leaf hands over every thread that has a place and the open comment box, and
    // takes back an outlet for each one this margin draws now: the open thread's card
    // and the comment box. Every other thread stays a mark until it is asked for.
    #placeThreads(targets, { onCommit }) {
      this.#targets = targets;
      if (!targets.some(({ thread }) => thread?.key === this.#open)) this.#open = null;
      this.#composing = null;
      const outlets = targets.map(({ thread, placement }) => {
        if (this.#hidden) return null;
        if (thread === null) {
          this.#composing = placement;
          return (this.#composer ??= offer("div", "xm-card"));
        }
        return thread.key === this.#open ? this.#outletFor(thread.key) : null;
      });
      const drawn = new Set(outlets.filter(Boolean));
      setChildren(this.#cards, [...drawn]);
      this.#drawThreadMarks();
      // An outlet no longer returned may still hold the comment box until this pass
      // takes effect, so it is forgotten only then.
      onCommit(() => {
        for (const [key, outlet] of this.#outlets)
          if (!drawn.has(outlet)) this.#outlets.delete(key);
        if (!drawn.has(this.#composer)) this.#composer = null;
        this.#layout();
      });
      return outlets;
    }

    #outletFor(key) {
      let outlet = this.#outlets.get(key);
      if (!outlet) {
        outlet = offer("div", "xm-card");
        outlet.lfCommands = this.#cardKeys;
        commandsChanged(outlet);
        this.#outlets.set(key, outlet);
      }
      return outlet;
    }

    // One mark for each open thread, saying what Leaf's own margin says of it:
    // whose turn it is, where the agent's work on it stands, or what it holds unread.
    #drawThreadMarks() {
      const next = new Map();
      for (const { thread, placement } of this.#hidden ? [] : this.#targets) {
        if (!thread || (thread.resolved && thread.key !== this.#open)) continue;
        let mark = this.#threadMarks.get(thread.key);
        if (!mark) {
          const press = offerAction("symbol", "", "", { action: "comment" });
          press.addEventListener("click", () => this.#press(thread.key));
          const word = offer("span", "xm-word");
          const node = offer("div", "xm-mark");
          node.append(press, word);
          mark = { node, press, word };
        }
        const { topic, status, progress } = threadSummary(thread);
        nameAction(mark.press, "comment", { label: `Thread: ${topic}` });
        keeps(mark.press, "aria-expanded", String(thread.key === this.#open));
        keepsText(mark.word, status?.text ?? "");
        keeps(mark.word, "data-lf-voice", status?.voice ?? null);
        keeps(
          mark.node,
          "data-turn",
          thread.attention?.kind === "needs_user" ? "user" : null,
        );
        keeps(mark.node, "data-progress", progress);
        this.#previewWords(placement.place);
        next.set(thread.key, { ...mark, thread, placement });
      }
      this.#threadMarks = next;
      this.#drawMarks();
    }

    // The page's other annotations: for each place Leaf lists, its On Me items as
    // marks, and the real controls of whatever a widget contributed there.
    #placeEntries(entries, view) {
      this.#activate = view.activate;
      const next = new Map();
      for (const entry of this.#hidden ? [] : entries) {
        const owed = view.items(entry).filter((item) => item.kind === "on-me");
        const controls = view.controls(entry);
        if (!owed.length && !controls.length) continue;
        const last = this.#rows.get(entry.key);
        const node = last?.node ?? offer("div", "xm-mark");
        const items = new Map();
        for (const item of owed) {
          const key = contributionItemKey(item);
          const mark = last?.items.get(key) ?? this.#owedMark(entry.key, key);
          nameAction(mark.press, "show", {
            label: [item.text, item.label].filter(Boolean).join(": "),
          });
          keepsText(mark.word, item.text);
          items.set(key, { ...mark, item });
        }
        setChildren(node, [
          ...[...items.values()].flatMap(({ press, word }) => [press, word]),
          ...controls,
        ]);
        keeps(node, "data-turn", owed.length ? "user" : null);
        // Ties the row to the entry's place, so a comment or Escape from a control in
        // it acts on what the row is about.
        view.place(entry, node);
        next.set(entry.key, { node, items, placement: { place: view.target(entry) } });
      }
      this.#rows = next;
      this.#drawMarks();
    }

    // An On Me mark: a press that shows the question, and Leaf's words for it. The
    // press runs the item its row last drew, which a later reading may have replaced
    // under the same key.
    #owedMark(entry, key) {
      const press = offerAction("symbol", "", "", { action: "show" });
      press.addEventListener("click", () => {
        const item = this.#rows.get(entry)?.items.get(key)?.item;
        if (item) this.#activate(item);
      });
      return { press, word: offer("span", "xm-word") };
    }

    #drawMarks() {
      setChildren(this.#marks, [
        ...[...this.#threadMarks.values()].map(({ node }) => node),
        ...[...this.#rows.values()].map(({ node }) => node),
      ]);
      this.#schedule();
    }

    #press(key) {
      if (this.#open === key) return this.#close();
      // Leaf's route to the thread: it asks `#reveal` for the card, then lands the
      // user in it, in the reply after a press and on the thread after a key.
      void threadActions.open(key, { travel: false });
    }

    // Any route to a thread no card shows comes here: this press, `t`, a row of
    // Threads, a link. The pass that follows places the outlet `#placeThreads` gives.
    #reveal(key) {
      if (this.#hidden || !this.#targets.some(({ thread }) => thread?.key === key))
        return false;
      this.#open = key;
    }

    #close() {
      const mark = this.#threadMarks.get(this.#open)?.press;
      this.#open = null;
      // The user leaves the card for its mark before the pass takes the card down.
      if (under(focused(), this) && mark?.isConnected) focusDestination(mark, "return");
      void this.#surface?.update();
    }

    // The user hid or showed the annotation layer (`o`). Everything here stands over
    // the page, so all of it goes, and the user with it to the words they were at.
    #hide(hidden) {
      if (hidden === this.#hidden) return;
      this.#hidden = hidden;
      if (hidden) {
        const place = this.#threadMarks.get(this.#open)?.placement.place;
        if (under(focused(), this) && place?.isConnected)
          focusDestination(place, "return");
        this.#open = null;
      }
      void this.#surface?.update();
      void this.#view?.update();
    }

    // The commented words under a pointer event, as the browser's own hit test of the
    // tint's ranges says, where the event reached the page's words and no control in
    // them: the thread, the element holding the words and the line pointed at.
    #wordsAt(event) {
      const column = this.#column();
      const { target, clientX: x, clientY: y } = event;
      if (!under(target, column) || under(target, this) || worksInside(target, column))
        return null;
      const tint = CSS.highlights.get(TINT);
      const [range] =
        CSS.highlights
          .highlightsFromPoint?.(x, y)
          .find(({ highlight }) => highlight === tint)?.ranges ?? [];
      const mark = this.#threadMarks.get(this.#tinted.get(range));
      if (!mark) return null;
      const line = [...range.getClientRects()].find(
        (rect) =>
          y >= rect.top && y <= rect.bottom && x >= rect.left && x <= rect.right,
      );
      return line ? { key: mark.thread.key, place: mark.placement.place, line } : null;
    }

    // A press on commented words opens their thread, as a press on its mark does,
    // unless it selected words.
    #pressWords(event) {
      if (!plainPress(event) || event.defaultPrevented || !getSelection().isCollapsed)
        return;
      const key = this.#wordsAt(event)?.key;
      if (key && key !== this.#open) void threadActions.open(key, { travel: false });
    }

    // Pointing at commented words reads their thread, as pointing at its mark does.
    // Leaf shows every preview and asks the element under the pointer what to say, so
    // the element holding the words answers for them, while it declares nothing of its
    // own, and says when the pointer reaches or leaves them.
    #previewWords(place) {
      if (this.#previewed.has(place) || typeof place.lfPreview === "function") return;
      this.#previewed.add(place);
      place.lfPreview = (route) => {
        const aimed = this.#aimed;
        const thread = this.#threadMarks.get(aimed?.key)?.thread;
        if (route === "focus" || aimed?.place !== place || !thread) return null;
        const { topic, status } = threadSummary(thread);
        return { name: topic, detail: [status?.text], at: aimed.line };
      };
    }

    #readAim() {
      const was = this.#aimed;
      const now = this.#hidden || !this.#pointer ? null : this.#wordsAt(this.#pointer);
      if (was?.key === now?.key && was?.line.top === now?.line.top) return;
      this.#aimed = now;
      for (const place of new Set([was?.place, now?.place]))
        if (place?.isConnected) previewChanged(place, { aim: Boolean(now) });
    }

    #layout() {
      const column = this.#column().getBoundingClientRect();
      const pinned = innerWidth - column.right < GAP + RAIL;
      keeps(this, "data-pinned", pinned ? "" : null);
      // Read every box before writing any, so the pass lays the page out once.
      const marks = [...this.#threadMarks.values(), ...this.#rows.values()].map(
        ({ node, placement }) => {
          const at = standing(placement);
          const shown = at.lines.some((line) => line.width || line.height);
          keepsHidden(node, !shown);
          return { node, shown, ...at };
        },
      );
      const shown = marks.filter((mark) => mark.shown);
      for (const mark of shown) mark.size = mark.node.getBoundingClientRect();
      const card = this.#outlets.get(this.#open);
      const floats = [
        ...(card
          ? [{ node: card, ...standing(this.#threadMarks.get(this.#open).placement) }]
          : []),
        ...(this.#composer && this.#composing
          ? [{ node: this.#composer, ...standing(this.#composing) }]
          : []),
      ];

      // Marks beside one line stack down the margin in page order: right of the
      // column, or as pins at the window's edge.
      let floor = -Infinity;
      for (const mark of shown.sort((a, b) => a.lines[0].top - b.lines[0].top)) {
        const top = Math.max(mark.lines[0].top, floor);
        const left = pinned ? innerWidth - mark.size.width - 4 : column.right + GAP;
        anchorTo(mark.node, mark.context, { left, top });
        floor = top + mark.size.height + STACK;
      }
      // A card stands right of the marks, beside the line its words start on. Where
      // the window has no room there it stands under its words, so it covers none of
      // them. Either way it stays inside the window.
      for (const { node, lines, context } of floats) {
        const [first] = lines;
        const last = lines.at(-1);
        const beside = innerWidth - column.right >= node.offsetWidth + CARD_GAP;
        const reference = {
          getBoundingClientRect: () =>
            beside
              ? new DOMRect(column.right, first.top, 0, first.height)
              : new DOMRect(last.left, first.top, last.width, last.bottom - first.top),
        };
        void computePosition(reference, node, {
          strategy: "fixed",
          placement: beside ? "right-start" : "bottom-start",
          middleware: [
            offset(beside ? CARD_GAP : STACK),
            flip(),
            shift({ padding: 8 }),
          ],
        }).then(({ x, y }) => {
          if (node.isConnected) anchorTo(node, context, { left: x, top: y });
        });
      }

      // The commented words, and the words the comment box is about, tinted with the
      // platform's highlights from the ranges Leaf keeps of each passage.
      this.#tinted = new Map(
        [...this.#threadMarks].flatMap(([key, { placement }]) =>
          (placement.ranges ?? []).map((range) => [range, key]),
        ),
      );
      CSS.highlights.set(
        TINT,
        new Highlight(...this.#tinted.keys(), ...(this.#composing?.ranges ?? [])),
      );
    }
  },
);
