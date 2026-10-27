/* lf-dial: how much of the page to show, from each section's gist to every detail.
 *
 * Three depths, each showing all the one before it shows and more, so turning the
 * dial only ever adds or removes text and never swaps one wording for another:
 * Skim shows the headings, the lede and each block the author marked `.gist`; Read
 * shows the page as written; Everything also opens every closed `details`. Which
 * depth stands is this tab's view of the page, as a tab set's open panel is
 * (`tabStore`): no event records it, and a reload comes back to it. Read is the
 * default, so a page shows as authored until the reader turns the dial.
 *
 * Skim folds the rest with `hidden="until-found"`, so find-in-page, a fragment, the On
 * walk and travel to a comment still reach folded text and open the run holding it
 * (`beforematch`, `lf-reveal`). Folding walks the dial's document (the view or `main`
 * holding it, as `lf-toc`'s outline does) and descends only into plain structure that
 * holds a heading or a gist. A Leaf element is folded or kept whole, never entered,
 * since its children are its own. Each run of folded blocks gets a quiet ⋯ after the
 * block it follows, which unfolds that run alone. The dial writes only what it folded:
 * an element already hidden, such as an inactive tab, is never touched, the margin is
 * never folded, and leaving Skim takes back exactly the folds and markers it made.
 *
 * Turning the dial keeps the reader's place. The block at the reading line, a quarter
 * of the way down the window, stays where it stood; when Skim folds that block, the
 * heading or gist it ran under takes its place on the line, so the reader lands on
 * what summarizes what they were reading. The blocks still shown then glide from where
 * they stood and the ones arriving fade in, so the eye can follow the page closing up
 * around the reader or opening out from them. Leaf's place keeper holds the place,
 * given the block at the line as the reading and, as each block's identity, the kept
 * block its run follows, so a folded block hands its place to its gist.
 *
 * The dial is three word toggles of one face, as an image pair's views are, reached by
 * Tab and the go-to key; inside the dial the arrow keys toward and away from the
 * text's start step one depth. It sticks at the window's top, at the column's end, so
 * the reader can turn it wherever they are reading rather than only at the top, which
 * is where keeping their place matters. */
import {
  commands,
  focusDestination,
  foldDuration,
  keeps,
  LeafElement,
  motion,
  move,
  offer,
  offerAction,
  PAGE_INTERFACE,
  placeKeeper,
  registerRootHeader,
  rowArrows,
  scrollerFor,
  shownWindow,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";

const DEPTHS = [
  { name: "skim", label: "Skim", title: "Headings and each section's gist" },
  { name: "read", label: "Read", title: "The page as written" },
  { name: "all", label: "Everything", title: "With every closed detail open" },
];
const HEADING = "h1, h2, h3, h4, h5, h6, hgroup";
const KEPT = `${HEADING}, .lede, .gist`;
// Never folded: what the reader steers by or what isn't the page's flow.
const STANDS =
  "script, style, template, [data-lf-gen], aside.sidebar, [data-lf-margin-content]";
const FOLDED = "data-lf-dial-folded";
// Marks the blocks that can hold the reader's place while the dial turns.
const BLOCK = "data-lf-dial-block";
// How far down the window the reader is taken to be reading.
const READING_LINE = 0.25;
// Motion past this many blocks would cost more than the eye can follow.
const MOVING = 120;

// A stable key for each node, which the place keeper matches across a turn.
const keys = new WeakMap();
let nextKey = 0;
const keyOf = (node) => {
  if (!keys.has(node)) keys.set(node, `lf-dial-${nextKey++}`);
  return keys.get(node);
};

const isLeafElement = (node) => node.localName.startsWith("lf-");
const shown = (node) => node.isConnected && !node.closest(`[${FOLDED}]`);

customElements.define(
  "lf-dial",
  class extends LeafElement {
    #buttons = new Map();
    #depth = "read";
    // Each fold this dial made: the run's marker, mapped to the blocks it folded and
    // the block they follow (or their container, where nothing kept precedes them).
    #runs = new Map();
    // The disclosures Everything opened, which leaving it closes again.
    #opened = new Set();
    #listening = null;

    get #key() {
      return `lf-dial:${this.id}`;
    }

    // The document the dial governs.
    get #scope() {
      return this.closest("[data-lf-views] > *, main") ?? this.ownerDocument.body;
    }

    setup() {
      const group = offer("div", "lf-dial-depths");
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", "How much to show");
      for (const { name, label, title } of DEPTHS) {
        const button = offerAction("word", "lf-dial-depth", label, { title });
        button.addEventListener("click", () => this.turn(name));
        this.#buttons.set(name, button);
        group.append(button);
      }
      this.append(group);
      const [back, ahead] = rowArrows(this);
      const step = (by) => {
        const at = DEPTHS.findIndex((depth) => depth.name === this.#depth);
        const next = DEPTHS[at + by];
        if (!next) return;
        this.turn(next.name);
        focusDestination(this.#buttons.get(next.name), "move");
      };
      commands(this, "In the detail dial", [
        { id: "dial.less", keys: [back], title: "Less detail", run: () => step(-1) },
        { id: "dial.more", keys: [ahead], title: "More detail", run: () => step(1) },
      ]);
      this.#draw();
      whileConnected(this, (signal) => {
        // A revision applied in place rebuilds the folds over its new structure.
        this.ownerDocument.addEventListener(
          PAGE_INTERFACE,
          () => this.#apply(this.#depth, { moving: false }),
          { signal },
        );
        const stored = tabStore.get(this.#key);
        if (stored) this.#apply(stored, { moving: false });
        // The dial sticks at the window's top while the reader scrolls the page under
        // it, so landings arrive below it.
        const stopHeader = registerRootHeader(this);
        return () => {
          stopHeader();
          this.#restore();
        };
      });
    }

    // Turn the dial to `name`, keeping the reader's place and moving the page there.
    turn(name) {
      if (name === this.#depth) return;
      tabStore.set(this.#key, name === "read" ? null : name);
      this.#apply(name, { moving: true });
    }

    #draw() {
      for (const [name, button] of this.#buttons)
        keeps(button, "aria-pressed", String(name === this.#depth));
    }

    #apply(name, { moving }) {
      const scope = this.#scope;
      const before = moving ? this.#positions(scope) : null;
      const change = () => {
        this.#restore();
        this.#depth = name;
        if (name === "skim") this.#fold(scope);
        if (name === "all") {
          for (const details of scope.querySelectorAll("details")) {
            if (details.open || details.closest(STANDS)) continue;
            details.open = true;
            this.#opened.add(details);
          }
        }
      };
      if (moving) this.#keepingPlace(scope, change);
      else change();
      this.#draw();
      if (before) this.#move(before, scope);
    }

    // Take back every fold, marker and opened disclosure this dial made.
    #restore() {
      this.#listening?.abort();
      this.#listening = null;
      for (const [marker, { blocks }] of this.#runs) {
        for (const block of blocks) this.#unfoldBlock(block);
        marker.remove();
      }
      this.#runs.clear();
      for (const details of this.#opened) details.open = false;
      this.#opened.clear();
    }

    #unfoldBlock(block) {
      if (!block.hasAttribute(FOLDED)) return;
      block.removeAttribute(FOLDED);
      if (block.getAttribute("hidden") === "until-found")
        block.removeAttribute("hidden");
    }

    #fold(scope) {
      this.#listening = new AbortController();
      for (const run of [...this.#runsIn(scope)]) this.#foldRun(run);
    }

    // Whether a child is kept whole at Skim, and whether the dial descends into it.
    #kept(child) {
      return child === this || child.matches(KEPT);
    }
    #holds(child) {
      if (isLeafElement(child)) return Boolean(child.querySelector(".gist"));
      return child.contains(this) || Boolean(child.querySelector(KEPT));
    }

    // The blocks the dial lays out: each child of the document, and the children of
    // the plain structure it descends into in place of that structure.
    *#blocks(container) {
      for (const child of container.children) {
        if (child.matches(STANDS)) continue;
        if (!this.#kept(child) && !isLeafElement(child) && this.#holds(child))
          yield* this.#blocks(child);
        else yield child;
      }
    }

    // The runs Skim folds within `container`: each a list of blocks, and the kept block
    // they follow, or null where nothing kept precedes them.
    *#runsIn(container) {
      let run = { container, after: null, blocks: [] };
      for (const child of [...container.children]) {
        if (child.matches(STANDS)) continue;
        if (child !== this && child.hidden && !child.hasAttribute(FOLDED)) continue;
        if (this.#kept(child)) {
          // A heading starts a run of its own; a gist straight after it, or after
          // another gist, extends what the run follows.
          if (child.matches(HEADING) || run.blocks.length) {
            if (run.blocks.length) yield run;
            run = { container, after: child, blocks: [] };
          } else run.after = child;
          continue;
        }
        if (this.#holds(child)) {
          if (run.blocks.length) yield run;
          if (!isLeafElement(child)) yield* this.#runsIn(child);
          run = { container, after: child, blocks: [] };
          continue;
        }
        run.blocks.push(child);
      }
      if (run.blocks.length) yield run;
    }

    #foldRun({ container, after, blocks }) {
      const marker = offer("div", "lf-dial-more");
      const button = offerAction("symbol", "lf-dial-unfold", "Show the rest", {
        icon: "more",
      });
      button.addEventListener("click", () =>
        this.#unfoldRun(marker, { pressed: true }),
      );
      marker.append(button);
      move(container, marker, blocks[0]);
      const { signal } = this.#listening;
      for (const block of blocks) {
        block.setAttribute(FOLDED, "");
        block.setAttribute("hidden", "until-found");
        // Find-in-page, a fragment or travel to something inside opens its run.
        block.addEventListener("beforematch", () => this.#unfoldRun(marker), {
          signal,
        });
        block.addEventListener("lf-reveal", () => this.#unfoldRun(marker), { signal });
      }
      this.#runs.set(marker, { after, blocks });
    }

    // Unfold one run, leaving the rest of the page at its depth.
    #unfoldRun(marker, { pressed = false } = {}) {
      const run = this.#runs.get(marker);
      if (!run) return;
      const scope = this.#scope;
      const before = pressed ? this.#positions(scope) : null;
      for (const block of run.blocks) this.#unfoldBlock(block);
      this.#runs.delete(marker);
      marker.remove();
      if (pressed) {
        // The press's own control is gone, so the reader lands on what it showed.
        focusDestination(run.blocks[0], "return");
        this.#move(before, scope);
      }
    }

    // Make `change` keep the reader's place: the block at the reading line, or, where
    // Skim folds it, the heading or gist it runs under, lands where it stood. Leaf's
    // place keeper hands a place across to the node drawn under the same identity, so
    // each block's identity is the kept block its run follows.
    #keepingPlace(scope, change) {
      const owner = new Map();
      for (const run of this.#runsIn(scope))
        for (const block of run.blocks) owner.set(block, run.after ?? run.container);
      // The dial itself, stuck over the page and under the pointer that turned it,
      // names no place in what scrolls beneath it. The mark stays, so a later turn
      // writes it only on blocks a revision added.
      const blocks = [...this.#blocks(scope)].filter((block) => block !== this);
      for (const block of blocks) keeps(block, BLOCK, "");
      const window = shownWindow();
      const line = window.top + (window.bottom - window.top) * READING_LINE;
      const reading = blocks.find(
        (block) => shown(block) && block.getBoundingClientRect().bottom > line,
      );
      const keeper = placeKeeper(scrollerFor(scope), {
        items: `[${BLOCK}]`,
        identity: (node) => keyOf(owner.get(node) ?? node),
        preferred: () => reading ?? null,
      });
      keeper.around(change);
    }

    // Where each block shown near the window stands in it now.
    #positions(scope) {
      const window = shownWindow();
      const span = window.bottom - window.top;
      const at = new Map();
      for (const block of this.#blocks(scope)) {
        if (at.size >= MOVING) break;
        if (!shown(block)) continue;
        const box = block.getBoundingClientRect();
        if (box.bottom > window.top - span && box.top < window.bottom + span)
          at.set(block, box.top);
      }
      return at;
    }

    // Glide the blocks still shown from where they stood; fade in the ones arriving.
    #move(before, scope) {
      const duration = foldDuration();
      const window = shownWindow();
      const after = this.#positions(scope);
      for (const [node, top] of after) {
        const box = node.getBoundingClientRect();
        if (box.bottom < window.top || box.top > window.bottom) continue;
        const was = before.get(node);
        if (was === undefined) {
          motion(node, [{ opacity: 0 }, { opacity: 1 }], duration);
          continue;
        }
        const by = was - top;
        if (Math.abs(by) >= 1)
          motion(node, [{ translate: `0 ${by}px` }, { translate: "0 0" }], duration);
      }
    }
  },
);
