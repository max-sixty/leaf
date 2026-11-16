/* A margin a page draws for itself, through the public package interface alone.

   On a page whose `body` has `data-annotations="page"`, Leaf draws no margin, marks or
   thread cards. This widget supplies them: a mark beside each commented passage, a tint
   on its words, the open thread's card and the comment box beside theirs, and the
   page's On Me marks and contributed actions beside what they are about. Leaf keeps
   every thread, message, draft and obligation; the widget only chooses where each
   stands (module-annotations.md, "Page annotation presentation").

   It takes no room in the page: every box it draws is fixed and anchored to the words
   it stands by, so the browser carries it with them through each scroll. Where the
   window has room right of the reading column the marks stand there with their words,
   covering nothing, and a card stands beside them. Where it has none, each mark is a
   pin at the window's edge, its symbol alone, and a card stands under its passage, as
   far into what room the margin has as it goes. While the user hides annotations (`o`)
   the pins, tints and cards go, and marks standing clear of the column stay.

   Commented words are tinted and nothing more: pointing at them reads no preview and a
   press on them opens no thread, both of which Leaf's own margin does from an index of
   every passage that no public call reaches. */
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
  isNativeLayer,
  keeps,
  keepsHidden,
  keepsText,
  nameAction,
  offer,
  offerAction,
  onPressAway,
  placePageThreads,
  setChildren,
  shownWindow,
  sizeObserver,
  threadActions,
  threadSummary,
  under,
  watchAnnotationLayer,
  whileConnected,
} from "/runtime/widget-api.js";
import { computePosition, flip, offset, shift } from "/vendor/floating-ui.esm.js";

const TINT = "lf-x-margin-passage";
// The mark Leaf's own passage highlights put on each element holding marked words,
// which a highlight's rule names (module-annotations.md).
const WORDS = "data-lf-marked-words";
const GAP = 12; // between the reading column and the marks
const RAIL = 184; // the room a mark with its words takes right of the column
const STACK = 4; // between two marks beside one line
const CARD_GAP = 40; // a card stands right of the marks
const CARD_MIN = 256; // the least width a card beside the column reads at
const EDGE = 8; // a card keeps this far from the window's edge and Leaf's panel

const STYLE = `
@layer lf-base {
  lf-x-margin { position: absolute; inline-size: 0; block-size: 0; }
  /* Fixed from the start, so each box has its own size before it is first placed.
     A mark goes while a box has scrolled its words out of sight. */
  lf-x-margin .xm-mark {
    position: fixed; position-visibility: var(--lf-anchor-visible);
    display: flex; align-items: center; gap: var(--lf-sp-1);
    inline-size: max-content; z-index: 2;
    color: var(--lf-ink-2); font: var(--lf-t-6)/1.3 var(--lf-sans);
  }
  /* A mark's colour says one thing, as on Leaf's own marks: a thread, the user's turn
     or the agent at work. Its dot says the thread holds something unread. A pin keeps
     both, where it has no room for its words. */
  lf-x-margin .xm-press { color: var(--lf-thread); }
  lf-x-margin .xm-mark[data-progress="working"] > .xm-press { color: var(--lf-work); }
  lf-x-margin .xm-mark[data-turn] > .xm-press { color: var(--lf-turn-ink); }
  lf-x-margin .xm-dot {
    position: absolute; inset-block-start: 2px; inset-inline-start: 19px;
    inline-size: 7px; block-size: 7px; border-radius: 50%;
    background: var(--lf-news); pointer-events: none;
  }
  lf-x-margin .xm-mark:not([data-unread]) > .xm-dot { display: none; }
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
     a box, where a mark goes with them. Beside the column it takes the room right of
     the marks. Under its words it takes the width Leaf's thread needs to say a
     message's line whole beside its controls. */
  lf-x-margin .xm-card {
    position: fixed; z-index: 3; position-visibility: always;
    inline-size: min(var(--xm-room, 22rem), 22rem);
    max-inline-size: calc(100vw - 16px); max-block-size: 70vh; overflow: auto;
    --lf-ground: var(--lf-card);
    padding: var(--lf-sp-2); border: 1px solid var(--lf-border);
    border-radius: var(--lf-r-l); background: var(--lf-ground); color: var(--lf-ink);
    box-shadow: var(--lf-raise-2);
  }
  lf-x-margin[data-under] .xm-card { inline-size: 26rem; }
  /* An outlet Leaf has yet to fill, or left to its panel, shows nothing. */
  lf-x-margin .xm-card:empty { display: none; }
  /* A wash of the theme's thread colour over the commented words. The rule names the
     elements holding them: one naming none would restyle every element on the page,
     and Firefox paints a highlight only from a rule matching the words' own element. */
  [${WORDS}]::highlight(${TINT}) {
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

// A mark: a press wearing one of Leaf's symbols, the words beside it, and the dot it
// wears while it holds something unread.
function mark(action, run) {
  const press = offerAction("symbol", "xm-press", "", { action });
  press.addEventListener("click", run);
  const word = offer("span", "xm-word");
  const node = offer("div", "xm-mark");
  node.append(press, word, offer("span", "xm-dot"));
  return { node, press, word };
}

customElements.define(
  "lf-x-margin",
  class extends LeafElement {
    #layer = offer("div", "xm-layer");
    #surface = null;
    #view = null;
    #sizes = null;
    #activate = null; // runs an inventory item, from the view Leaf last painted with
    #targets = [];
    #threadMarks = new Map(); // thread key -> {node, press, word, thread, placement}
    #owedMarks = new Map(); // On Me item key -> {node, press, word, item, placement}
    #rows = new Map(); // inventory entry key -> {node, placement}, its contributed controls
    #order = []; // the marks in page order, as the last layout read them
    #outlets = new Map(); // thread key -> outlet
    #composer = null; // the comment box's outlet, while Leaf asks for one
    #composing = null; // the comment box's placement
    #standing = new Set(); // the outlets in the document, until a pass retires them
    #open = null; // the key of the thread whose card is open
    #hidden = false; // whether the user has hidden the annotation layer
    #pinned = false; // whether the marks stand as pins over the page
    #room = null; // the width a card has right of the marks, or null under its words
    #tinted = new Set(); // the elements holding tinted words
    #schedule = frameFor(this, () => this.#layout());
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
      this.append(style, this.#layer);
      whileConnected(this, (signal) => {
        this.#sizes = sizeObserver(this.#schedule);
        this.#sizes.observe(this.#column());
        this.#surface = placePageThreads(
          this,
          (targets, context) => this.#placeThreads(targets, context),
          { reveal: (key) => this.#reveal(key) },
        );
        this.#view = consumeAnnotations(this, (entries, view) =>
          this.#placeEntries(entries, view),
        );
        const stopHiding = watchAnnotationLayer((hidden) => this.#hide(hidden));
        // A press away from the open card puts it away, as it does Leaf's own. Leaf
        // keeps the words of a reply being written there as its draft.
        const stopPresses = onPressAway(
          (path) => this.#pressedAway(path),
          () => this.#close(),
        );
        addEventListener("resize", this.#schedule, { signal });
        document.addEventListener(PAGE_INTERFACE, this.#schedule, { signal });
        return () => {
          stopHiding();
          stopPresses();
          this.#sizes.disconnect();
          this.#surface.unregister();
          this.#view.unregister();
          this.#surface = this.#view = this.#sizes = null;
          CSS.highlights.delete(TINT);
          this.#tint([]);
        };
      });
    }

    // The page's reading column. No public call names it, so this reads the page's
    // content frame, `main`, as a page written for this margin has one.
    #column() {
      return this.closest("main") ?? document.body;
    }

    // Whether the marks themselves are hidden: pins stand over the page's words, which
    // the user hid annotations to read.
    #gone() {
      return this.#hidden && this.#pinned;
    }

    // Leaf hands over every thread that has a place and the open comment box, and
    // takes back an outlet for each one this margin draws now: the open thread's card
    // and the comment box. Every other thread stays a mark until it is asked for.
    #placeThreads(targets, { onCommit }) {
      this.#targets = targets;
      if (!targets.some(({ thread }) => thread?.key === this.#open)) this.#open = null;
      this.#composing = null;
      const outlets = targets.map(({ thread, placement }) => {
        // Hidden, a card and the comment box are Leaf's panel's.
        if (this.#hidden) return null;
        if (thread === null) {
          this.#composing = placement;
          return (this.#composer ??= this.#outlet());
        }
        if (thread.key !== this.#open) return null;
        if (!this.#outlets.has(thread.key)) {
          const outlet = this.#outlet();
          outlet.lfCommands = this.#cardKeys;
          commandsChanged(outlet);
          this.#outlets.set(thread.key, outlet);
        }
        return this.#outlets.get(thread.key);
      });
      const drawn = new Set(outlets.filter(Boolean));
      for (const outlet of drawn) this.#standing.add(outlet);
      this.#drawThreadMarks();
      // An outlet no longer returned may still hold the comment box until this pass
      // takes effect, so it leaves only then.
      onCommit(() => {
        for (const outlet of this.#standing)
          if (!drawn.has(outlet)) {
            this.#standing.delete(outlet);
            this.#sizes.unobserve(outlet);
          }
        for (const [key, outlet] of this.#outlets)
          if (!drawn.has(outlet)) this.#outlets.delete(key);
        if (!drawn.has(this.#composer)) this.#composer = null;
        this.#arrange();
        this.#layout();
      });
      return outlets;
    }

    // An outlet's size is Leaf's to change, as a thread gains a message.
    #outlet() {
      const outlet = offer("div", "xm-card");
      this.#sizes.observe(outlet);
      return outlet;
    }

    // One mark for each open thread, saying what Leaf's own margin says of it: by its
    // colour whose turn it is, by its dot that it holds something unread, and in words
    // its line, such as where the agent's work on it stands.
    #drawThreadMarks() {
      const next = new Map();
      for (const { thread, placement } of this.#gone() ? [] : this.#targets) {
        if (!thread || (thread.resolved && thread.key !== this.#open)) continue;
        const { key } = thread;
        const drawn =
          this.#threadMarks.get(key) ?? mark("comment", () => this.#press(key));
        const { topic, line, progress, unread } = threadSummary(thread);
        nameAction(drawn.press, "comment", {
          label: [`Thread: ${topic}`, line?.text].filter(Boolean).join(", "),
        });
        keeps(drawn.press, "aria-expanded", String(key === this.#open));
        // Pointing at the mark reads the thread's name, and its line where the mark is
        // a pin with no room to show it. An open thread is in front of the user.
        drawn.press.lfPreview = () =>
          key === this.#open
            ? null
            : { name: topic, detail: this.#pinned ? [line?.text] : [] };
        keepsText(drawn.word, line?.text ?? "");
        keeps(drawn.word, "data-lf-voice", line?.voice ?? null);
        keeps(
          drawn.node,
          "data-turn",
          thread.attention?.kind === "needs_user" ? "" : null,
        );
        keeps(drawn.node, "data-progress", progress);
        keeps(drawn.node, "data-unread", unread ? "" : null);
        next.set(key, { ...drawn, thread, placement });
      }
      this.#threadMarks = next;
      this.#arrange();
      this.#schedule();
    }

    // The page's other annotations, one entry for each place Leaf lists: its On Me
    // items as marks, and the real controls of whatever a widget contributed there.
    // Each row is tied to its entry, and a mark to the item it stands for, so the user
    // comments from it on its place, and Go-to finds it among the margin's targets and
    // a thread's mark among the Thread controls. A thread no card holds is listed here
    // too, so its mark, drawn above from where its words stand, is tied here.
    #placeEntries(entries, view) {
      this.#activate = view.activate;
      const owed = new Map();
      const rows = new Map();
      for (const entry of this.#gone() ? [] : entries) {
        const placement = { place: view.target(entry) };
        for (const item of view.items(entry)) {
          if (item.kind === "comment") {
            const drawn = this.#threadMarks.get(item.thread.key);
            if (drawn) view.place(entry, drawn.node, item);
          } else if (item.kind === "on-me") {
            const key = contributionItemKey(item);
            // The press runs the item its mark last drew, which a later reading may
            // have replaced under the same key.
            const drawn =
              this.#owedMarks.get(key) ??
              mark("show", () => this.#activate(this.#owedMarks.get(key).item));
            nameAction(drawn.press, "show", {
              label: [item.text, item.label].filter(Boolean).join(": "),
            });
            keepsText(drawn.word, item.text);
            keeps(drawn.node, "data-turn", "");
            view.place(entry, drawn.node, item);
            owed.set(key, { ...drawn, item, placement });
          }
        }
        const controls = view.controls(entry);
        if (!controls.length) continue;
        const node = this.#rows.get(entry.key)?.node ?? offer("div", "xm-mark");
        setChildren(node, controls);
        view.place(entry, node);
        rows.set(entry.key, { node, placement });
      }
      this.#owedMarks = owed;
      this.#rows = rows;
      this.#arrange();
      this.#schedule();
    }

    #marks() {
      return [
        ...this.#threadMarks.values(),
        ...this.#owedMarks.values(),
        ...this.#rows.values(),
      ];
    }

    // The marks in page order, each thread's card after its mark, so Tab reads the
    // margin down the page and steps from a mark into its card.
    #arrange() {
      const marks = this.#marks().map(({ node }) => node);
      const card = this.#outlets.get(this.#open);
      const opener = this.#threadMarks.get(this.#open)?.node;
      const ordered = [
        ...this.#order.filter((node) => marks.includes(node)),
        ...marks.filter((node) => !this.#order.includes(node)),
      ].flatMap((node) =>
        node === opener && this.#standing.has(card) ? [node, card] : [node],
      );
      setChildren(this.#layer, [
        ...ordered,
        ...[...this.#standing].filter((outlet) => !ordered.includes(outlet)),
      ]);
    }

    #press(key) {
      if (this.#open === key) return this.#close();
      // Leaf's route to the thread: it asks `#reveal` for the card, then lands the
      // user in it, in the reply after a press and on the thread after a key.
      void threadActions.open(key, { travel: false });
    }

    // Any route to a thread no card shows comes here: a press on its mark, `t`, Show
    // on page in Leaf's panel. The pass that follows places the outlet `#placeThreads`
    // gives. Declining, while annotations are hidden, leaves the thread to the panel.
    #reveal(key) {
      if (this.#hidden) return false;
      this.#open = key;
    }

    #close() {
      const card = this.#outlets.get(this.#open);
      const opener = this.#threadMarks.get(this.#open)?.press;
      this.#open = null;
      // A user in the card leaves it for its mark before the pass takes the card down.
      if (card && under(focused(), card) && opener?.isConnected)
        focusDestination(opener, "return");
      void this.#surface.update();
    }

    // Whether a press began and ended away from the open card: outside the card, its
    // mark, the block its words stand in, and anything the card opened over the page.
    #pressedAway(path) {
      const opener = this.#threadMarks.get(this.#open);
      if (!opener) return false;
      const kept = [this.#outlets.get(this.#open), opener.node, opener.placement.place];
      return !path.some((node) => kept.includes(node) || isNativeLayer(node));
    }

    // The user hid or showed annotations (`o`): what stands over the page's words
    // goes, and a user on any of it goes to the words it stood by.
    #hide(hidden) {
      if (hidden === this.#hidden) return;
      this.#hidden = hidden;
      if (hidden) {
        const at = focused();
        const card = this.#outlets.get(this.#open);
        const from =
          card && under(at, card)
            ? this.#threadMarks.get(this.#open)
            : this.#pinned && this.#marks().find(({ node }) => under(at, node));
        if (from) focusDestination(from.placement.place, "return");
        this.#open = null;
      }
      this.#redraw();
    }

    #redraw() {
      void this.#surface.update();
      void this.#view.update();
      this.#schedule();
    }

    // Tint the words `ranges` cover, with the platform's highlights, and mark the
    // elements holding them for the highlight's rule to name: each end's parent, or
    // the host of a shadow tree holding the words directly.
    #tint(ranges) {
      CSS.highlights.set(TINT, new Highlight(...ranges));
      const holding = new Set(
        ranges.flatMap(({ startContainer, endContainer }) =>
          [startContainer, endContainer].map(
            (node) => node.parentElement ?? node.parentNode?.host,
          ),
        ),
      );
      holding.delete(undefined);
      for (const element of this.#tinted)
        if (!holding.has(element)) element.removeAttribute(WORDS);
      for (const element of holding) keeps(element, WORDS, "");
      this.#tinted = holding;
    }

    #layout() {
      const column = this.#column().getBoundingClientRect();
      // The window, and the part of it clear of Leaf's panel, which a card keeps inside.
      const page = shownWindow();
      const edge = shownWindow({ gap: EDGE });
      const pinned = page.right - column.right < GAP + RAIL;
      if (pinned !== this.#pinned) {
        this.#pinned = pinned;
        keeps(this, "data-pinned", pinned ? "" : null);
        // Pins go with hidden annotations, and marks clear of the column come back.
        if (this.#hidden) this.#redraw();
      }
      // A card stands beside the column where the margin has the room for one.
      const free = Math.round(edge.right - column.right - CARD_GAP);
      const room = free >= CARD_MIN ? free : null;
      if (room !== this.#room) {
        this.#room = room;
        keeps(this, "data-under", room === null ? "" : null);
        if (room === null) this.style.removeProperty("--xm-room");
        else this.style.setProperty("--xm-room", `${room}px`);
      }
      // Read every box before writing any, so the pass lays the page out once.
      const marks = this.#marks().map(({ node, placement }) => {
        const at = standing(placement);
        const shown = at.lines.some((line) => line.width || line.height);
        keepsHidden(node, !shown);
        return { node, shown, ...at };
      });
      const shown = marks.filter(({ shown }) => shown);
      for (const drawn of shown) drawn.size = drawn.node.getBoundingClientRect();
      const card = this.#outlets.get(this.#open);
      const floats = [
        ...(card
          ? [{ node: card, ...standing(this.#threadMarks.get(this.#open).placement) }]
          : []),
        ...(this.#composer && this.#composing
          ? [{ node: this.#composer, ...standing(this.#composing) }]
          : []),
      ].map((float) => ({ ...float, width: float.node.offsetWidth }));

      // Marks beside one line stack down the margin in page order: right of the
      // column, or as pins at the window's edge.
      shown.sort((a, b) => a.lines[0].top - b.lines[0].top);
      let floor = -Infinity;
      for (const drawn of shown) {
        const top = Math.max(drawn.lines[0].top, floor);
        const left = pinned ? page.right - drawn.size.width - 4 : column.right + GAP;
        anchorTo(drawn.node, drawn.context, { left, top });
        floor = top + drawn.size.height + STACK;
      }
      const order = shown.map(({ node }) => node);
      if (order.some((node, at) => node !== this.#order[at])) {
        this.#order = order;
        this.#arrange();
      }

      // A card stands right of the marks, beside the line its words start on. Where
      // the margin lacks the room it stands under its words instead, so it covers none
      // of them, as far into the margin as the window lets it. Either way it keeps
      // clear of Leaf's panel, where Leaf would not seat the comment box.
      const beside = room !== null;
      for (const { node, lines, context, width } of floats) {
        if (!width) continue;
        const [first] = lines;
        const last = lines.at(-1);
        const left = beside
          ? column.right + CARD_GAP
          : Math.max(edge.left, edge.right - width);
        const clear = shownWindow({ gap: EDGE, across: { left, right: left + width } });
        const rootBoundary = {
          x: clear.x,
          y: clear.y,
          width: clear.width,
          height: clear.height,
        };
        const reference = {
          getBoundingClientRect: () =>
            beside
              ? new DOMRect(left, first.top, 0, first.height)
              : new DOMRect(left, first.top, width, last.bottom - first.top),
        };
        void computePosition(reference, node, {
          strategy: "fixed",
          placement: beside ? "right-start" : "bottom-start",
          middleware: [
            offset(beside ? 0 : STACK),
            ...(beside ? [] : [flip({ rootBoundary })]),
            shift({ rootBoundary }),
          ],
        }).then(({ x, y }) => {
          if (node.isConnected) anchorTo(node, context, { left: x, top: y });
        });
      }

      // The commented words, and the words the comment box is about, from the ranges
      // Leaf keeps of each passage. Hidden, no words are tinted.
      this.#tint(
        this.#hidden
          ? []
          : [
              ...[...this.#threadMarks.values()].flatMap(
                ({ placement }) => placement.ranges ?? [],
              ),
              ...(this.#composing?.ranges ?? []),
            ],
      );
    }
  },
);
