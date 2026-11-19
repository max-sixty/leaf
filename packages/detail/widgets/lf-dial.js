/* lf-dial: how much of the page to show, from the author's gists to every detail.
 *
 * Three depths, each showing all the one before it shows and more, so turning the
 * dial only ever adds or removes text and never swaps one wording for another:
 * Skim shows the lede, each block the author marked `.gist`, every picture and the
 * headings above them; Read shows the page as written; Everything also opens every
 * closed `details`. Skim shows nothing Read doesn't, so it keeps nothing inside a
 * closed `details`.
 *
 * A picture is one HTML draws (a figure, an image, a drawing, a video, a canvas) or a
 * widget whose entry says it draws one (`visual`, painted `data-lf-visual`), such as a
 * chart, a diagram or a screenshot pair, with its caption where a `figure` gives it
 * one. A reader on a quick pass reads a page by its pictures as much as by its words,
 * so Skim keeps every picture the page shows rather than only the ones an author marks
 * (the maintainer's choice). Rejected: folding every picture the author left unmarked,
 * which made Skim words alone. What HTML marks as decoration (`aria-hidden`, an empty
 * `alt`, a presentation role) is no picture, nor is Leaf's own chrome, and a picture
 * inside a widget that draws its own content (`content` `data` or `empty`), such as an
 * icon in a code view, is that widget's drawing. A widget holding the author's markup,
 * such as a tab, a question or an animation, stays whole at Skim when a picture or a
 * gist stands inside it.
 * Which depth stands is this tab's view of the page, as a tab set's open panel is
 * (`tabStore`): no event records it, and a reload comes back to it. Read is the
 * default, so a page shows as authored until the reader turns the dial.
 *
 * Skim folds the rest with `hidden="until-found"`, so find-in-page, a fragment, the On
 * walk and travel to a comment still reach folded text and open the run holding it
 * (`beforematch`). Folding walks the dial's document (the view or `main`
 * holding it, as `lf-toc`'s outline does) and descends only into HTML's sections and
 * groups of blocks (`section`, `div`, a list item, a quote and the like) that hold the
 * lede, a gist, a picture or a heading that stands, and have no words of their own.
 * Everything else
 * is folded or kept whole: a paragraph or other line of text, which keeps a picture in
 * its line whole; a table, whose cells stand in its grid; a disclosure, whose summary
 * is its control; and a Leaf element, whose children are its own. A heading stands at
 * Skim when a lede, gist or picture follows it in document order before the next
 * heading of its rank or above, so a section with nothing for a skimmer folds whole,
 * heading included. Keeping every heading was rejected: it made Skim a fixed cut of
 * every section, whether or not one had anything for a skimmer.
 *
 * Skim draws one quiet ⋯ for each gap in what it shows, after the block the gap
 * follows, and pressing it unfolds that gap alone. A gap is every block between two
 * kept ones in document order, whatever structure holds them, so a section folded whole
 * joins the folded rest of the section before it, and nested sections fold as flat
 * ones do. A ⋯ at a section's end and another for the gist-less section after it was
 * rejected: two marks stood for one gap. A ⋯ whose gap holds a heading previews the
 * outermost headings in it (`lfPreview`), so a skimmer can tell which sections lie
 * behind it before pressing. Writing those names on the page was rejected, since Skim
 * shows only the passages the author chose. The dial writes only what it folded: an
 * element already hidden, such as an inactive tab, is never touched, the margin is
 * never folded, and leaving Skim takes back exactly the folds and markers it made.
 *
 * Turning the dial keeps the reader's place. The block at the reading line, a quarter
 * of the way down the window, stays where it stood; when Skim folds that block, the
 * heading or gist it ran under takes its place on the line, so the reader lands on
 * what summarizes what they were reading. The blocks still shown then glide from where
 * they stood and the ones arriving fade in, so the eye can follow the page closing up
 * around the reader or opening out from them. Leaf's one hold keeps the place
 * (`holdPlace`, given the line's words by `readingAt`), since the browser's scroll
 * anchoring can't: Skim hides the block it anchors.
 *
 * The dial is a radio group of the three depths, Web Awesome's, the control every
 * choice among a few views takes, as a recording's scopes and an image pair's views
 * do. Tab and the go-to key reach it, and inside it the arrow keys step one depth, as
 * in any radio group. It sticks at the window's top, at the column's end, so the
 * reader can turn it wherever they are reading rather than only at the top, which is
 * where keeping their place matters. */
import {
  actionClass,
  addressableLabel,
  authoredScope,
  focusDestination,
  foldDuration,
  holdPlace,
  LeafElement,
  motion,
  move,
  offer,
  offerAction,
  PAGE_INTERFACE,
  readingAt,
  registerRootHeader,
  shownWindow,
  tabStore,
  viewDocument,
  whileConnected,
} from "/runtime/widget-api.js";
import "/vendor/webawesome-views.js";

const DEPTHS = [
  { name: "skim", label: "Skim", title: "The page's argument and what it asks of you" },
  { name: "read", label: "Read", title: "The page as written" },
  { name: "all", label: "Everything", title: "With every closed detail open" },
];
const RANKED = "h1, h2, h3, h4, h5, h6";
const HEADING = `${RANKED}, hgroup`;
// What Skim keeps for its own sake, with every picture; a heading stands for the ones
// it heads.
const SUMMARY = ".lede, .gist";
const PICTURE = "figure, img, picture, svg, video, canvas, [data-lf-visual]";
// What HTML says is decoration, which no reader looks at for its own sake.
const DECORATIVE =
  '[aria-hidden="true"], img[alt=""], [role="presentation"], [role="none"]';
// A Leaf element that draws its own content, whose pictures are its drawing.
const DRAWS = '[data-lf-content="data"], [data-lf-content="empty"]';
// HTML's sections and the elements that group blocks, a list's items and a quote's
// included, the only structure the dial lays out in place of itself.
const SECTIONING =
  "main, section, article, div, header, footer, nav, search, ul, ol, menu, li, dl, dd, blockquote";
// Never folded: what the reader steers by or what isn't the page's flow.
const STANDS = "script, style, template, [data-lf-gen], aside";
const FOLDED = "data-lf-dial-folded";
// Motion past this many blocks would cost more than the eye can follow.
const MOVING = 120;

/** @param {Element} node */
const isLeafElement = (node) => node.localName.startsWith("lf-");
/** @param {Element} heading */
const rank = (heading) =>
  Number(
    (heading.matches(RANKED) ? heading : heading.querySelector(RANKED))?.localName[1] ??
      7,
  );
// Whether an element is a line of text: one with words of its own beside its children.
/** @param {Element} element */
const ownsWords = (element) =>
  [...element.childNodes].some(
    (node) => node.nodeType === Node.TEXT_NODE && /\S/.test(node.textContent ?? ""),
  );
// The headings in `blocks` that no earlier one among them outranks: the sections a run
// folds, rather than each of their subsections.
/** @param {Element[]} blocks */
const outermost = (blocks) => {
  const found = [];
  let top = 7;
  for (const block of blocks)
    for (const heading of [block, ...block.querySelectorAll(RANKED)]) {
      if (!heading.matches(RANKED) || rank(heading) > top) continue;
      top = rank(heading);
      found.push(heading);
    }
  return found;
};
/** @param {Element} node */
const shown = (node) => node.isConnected && !node.closest(`[${FOLDED}]`);

/** @typedef {{after: Element | null, blocks: Element[]}} FoldRun */

customElements.define(
  "lf-dial",
  class extends LeafElement {
    /** @type {import("@awesome.me/webawesome/dist/components/radio-group/radio-group.js").default | null} */
    #depths = null;
    #depth = "read";
    // Each fold this dial made: the run's marker, mapped to the blocks it folded and
    // the block they follow.
    /** @type {Map<HTMLElement, FoldRun>} */
    #runs = new Map();
    // The disclosures Everything opened, which leaving it closes again.
    /** @type {Set<HTMLDetailsElement>} */
    #opened = new Set();
    /** @type {AbortController | null} */
    #listening = null;

    get #key() {
      return `lf-dial:${this.id}`;
    }

    // The document the dial governs: the view or `main` holding it, the page's `main`
    // for a dial standing beside it, and in an agent's message that message's markup.
    get #scope() {
      const scope = authoredScope(this);
      return (
        viewDocument(this) ??
        (scope === this.ownerDocument.body
          ? scope.querySelector(":scope > main")
          : scope)
      );
    }

    setup() {
      const group = (this.#depths = offer(
        "wa-radio-group",
        "lf-dial-depths lf-label-hidden",
      ));
      group.label = "How much to show";
      group.name = `${this.id}-depth`;
      group.size = "s";
      group.orientation = "horizontal";
      for (const { name, label, title } of DEPTHS) {
        const depth = offer(
          "wa-radio",
          actionClass("word", "lf-dial-depth"),
          label,
          undefined,
          true,
        );
        depth.value = name;
        // An attribute, so the theme seats it as a chooser from its first paint.
        depth.setAttribute("appearance", "button");
        depth.title = title;
        group.append(depth);
      }
      group.addEventListener("change", () => this.turn(String(group.value)));
      this.append(group);
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
    /** @param {string} name */
    turn(name) {
      if (name === this.#depth) return;
      tabStore.set(this.#key, name === "read" ? null : name);
      this.#apply(name, { moving: true });
    }

    #draw() {
      if (this.#depths) this.#depths.value = this.#depth;
    }

    /** @param {string} name @param {{moving: boolean}} options */
    #apply(name, { moving }) {
      const scope = this.#scope;
      if (!scope) return;
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

    /** @param {Element} block */
    #unfoldBlock(block) {
      if (!block.hasAttribute(FOLDED)) return;
      block.removeAttribute(FOLDED);
      if (block.getAttribute("hidden") === "until-found")
        block.removeAttribute("hidden");
    }

    /** @param {Element} scope */
    #fold(scope) {
      const listening = (this.#listening = new AbortController());
      for (const run of this.#runsIn(scope)) this.#foldRun(run, listening.signal);
    }

    // Whether `node` is a disclosure whose body Read shows none of, so Skim keeps
    // nothing inside it, counting those Everything opened as closed.
    /** @param {Element} node */
    #closed(node) {
      return (
        node instanceof HTMLDetailsElement && (!node.open || this.#opened.has(node))
      );
    }
    // Whether `node` is a picture Skim keeps: not decoration, and standing in the
    // author's markup in `scope`, so not inside another picture, Leaf's chrome, a
    // widget that draws its own content or a closed disclosure.
    /** @param {Element} node @param {Element} scope */
    #isPicture(node, scope) {
      if (!node.matches(PICTURE) || node.matches(DECORATIVE)) return false;
      for (let at = node.parentElement; at && at !== scope; at = at.parentElement)
        if (
          at.matches(`${PICTURE}, ${STANDS}, ${DRAWS}, [aria-hidden="true"]`) ||
          (isLeafElement(at) && !at.hasAttribute("data-lf-content")) ||
          this.#closed(at)
        )
          return false;
      return true;
    }
    // Whether a child is kept whole at Skim: what Skim shows, or a block holding some of
    // it that the dial doesn't enter.
    /** @param {Element} child @param {Element} scope */
    #kept(child, scope) {
      return (
        child === this ||
        child.matches(SUMMARY) ||
        this.#isPicture(child, scope) ||
        (child.matches(HEADING) && this.#heads(child, scope)) ||
        (!this.#enters(child) && this.#holds(child, scope))
      );
    }
    // Whether the dial may lay out a child's children in its place: a section or a
    // group of blocks with no words of its own.
    /** @param {Element} child */
    #enters(child) {
      return child.matches(SECTIONING) && !ownsWords(child);
    }
    // Whether a child holds anything Skim shows.
    /** @param {Element} child @param {Element} scope */
    #holds(child, scope) {
      if (this.#closed(child)) return false;
      /** @param {Element} node */
      const inside = (node) => {
        for (let at = node.parentElement; at && at !== child; at = at.parentElement)
          if (this.#closed(at)) return false;
        return true;
      };
      return (
        child.contains(this) ||
        [...child.querySelectorAll(SUMMARY)].some(inside) ||
        [...child.querySelectorAll(PICTURE)].some((node) =>
          this.#isPicture(node, scope),
        ) ||
        [...child.querySelectorAll(HEADING)].some((heading) =>
          this.#heads(heading, scope),
        )
      );
    }
    // Whether a lede, gist or picture follows a heading in `scope`, in document order,
    // before the next heading of its rank or above. Reading past the heading's parent
    // lets a heading inside a `header` or other wrapper head the section it opens.
    /** @param {Element} heading @param {Element} scope */
    #heads(heading, scope) {
      const own = rank(heading);
      const walker = heading.ownerDocument.createTreeWalker(
        scope,
        NodeFilter.SHOW_ELEMENT,
        (node) =>
          /** @type {Element} */ (node).matches(STANDS) ||
          this.#closed(/** @type {Element} */ (node))
            ? NodeFilter.FILTER_REJECT
            : NodeFilter.FILTER_ACCEPT,
      );
      walker.currentNode = heading;
      // Step past the heading's own content.
      while (!walker.nextSibling()) if (!walker.parentNode()) return false;
      /** @type {Node | null} */
      let node = walker.currentNode;
      for (; node; node = walker.nextNode()) {
        const element = /** @type {Element} */ (node);
        if (element.matches(SUMMARY) || this.#isPicture(element, scope)) return true;
        if (element.matches(RANKED) && rank(element) <= own) return false;
      }
      return false;
    }

    // The blocks the dial lays out, in document order: each child of the document, and
    // the children of the plain structure it descends into in place of that structure,
    // leaving out an element already hidden. A snapshot of each container's children,
    // since folding puts its markers among them as the walk goes.
    /** @param {Element} container @param {Element} scope @returns {Generator<Element>} */
    *#blocks(container, scope) {
      for (const child of [...container.children]) {
        if (child.matches(STANDS)) continue;
        if (
          child !== this &&
          child.hasAttribute("hidden") &&
          !child.hasAttribute(FOLDED)
        )
          continue;
        if (
          !this.#kept(child, scope) &&
          this.#enters(child) &&
          this.#holds(child, scope)
        )
          yield* this.#blocks(child, scope);
        else yield child;
      }
    }

    // The runs Skim folds in `scope`: each the blocks between two it keeps, and the kept
    // block they follow, or null where nothing kept precedes them.
    /** @param {Element} scope @returns {Generator<FoldRun>} */
    *#runsIn(scope) {
      /** @type {FoldRun} */
      let run = { after: null, blocks: [] };
      for (const block of this.#blocks(scope, scope)) {
        if (this.#kept(block, scope)) {
          if (run.blocks.length) yield run;
          run = { after: block, blocks: [] };
        } else run.blocks.push(block);
      }
      if (run.blocks.length) yield run;
    }

    /** @param {FoldRun} run @param {AbortSignal} signal */
    #foldRun({ after, blocks }, signal) {
      const marker = offer("div", "lf-dial-more");
      const button = offerAction("symbol", "lf-dial-unfold", "Show the rest", {
        action: "more",
      });
      button.addEventListener("click", () =>
        this.#unfoldRun(marker, { pressed: true }),
      );
      button.lfPreview = () => {
        const names = outermost(blocks).map(addressableLabel).filter(Boolean);
        return names.length
          ? {
              list: {
                items: names,
                more: (/** @type {number} */ count) => `and ${count} more`,
              },
            }
          : null;
      };
      marker.append(button);
      const [first] = blocks;
      if (first?.parentElement) move(first.parentElement, marker, first);
      for (const block of blocks) {
        block.setAttribute(FOLDED, "");
        block.setAttribute("hidden", "until-found");
        // Find-in-page, a fragment or travel to something inside opens its run.
        block.addEventListener("beforematch", () => this.#unfoldRun(marker), {
          signal,
        });
      }
      this.#runs.set(marker, { after, blocks });
    }

    // Unfold one run, leaving the rest of the page at its depth.
    /** @param {HTMLElement} marker @param {{pressed?: boolean}} [options] */
    #unfoldRun(marker, { pressed = false } = {}) {
      const run = this.#runs.get(marker);
      if (!run) return;
      const scope = this.#scope;
      if (!scope) return;
      const before = pressed ? this.#positions(scope) : null;
      for (const block of run.blocks) this.#unfoldBlock(block);
      this.#runs.delete(marker);
      marker.remove();
      if (before) {
        // The press's own control is gone, so the reader lands on what it showed.
        const [first] = run.blocks;
        if (first) focusDestination(first, "return");
        this.#move(before, scope);
      }
    }

    // Make `change` keep the reader's place: what stands at the reading line, or, where
    // Skim folds it, the heading or gist its run follows, lands where it stood
    // (`holdPlace`). Each run's ⋯ stands for that heading or gist too, as leaving Skim
    // takes it away.
    /** @param {Element} scope @param {() => void} change */
    #keepingPlace(scope, change) {
      /** @type {Map<Element, Element>} */
      const owner = new Map();
      for (const run of this.#runsIn(scope))
        for (const block of run.blocks) owner.set(block, run.after ?? scope);
      for (const [marker, { after }] of this.#runs) if (after) owner.set(marker, after);
      // The block holding the words at the line, since a fold replaces whole blocks:
      // its gist lands where the block's top stood, line for line. A block that began
      // above the window would take its gist out of sight with its top, 978px up for a
      // paragraph of 2,700px, so its gist lands where the words read stood.
      const words = readingAt(scope);
      const at = words instanceof Range ? words.startContainer : words;
      const block =
        at && [...this.#blocks(scope, scope)].find((each) => each.contains(at));
      const begun = block && block.getBoundingClientRect().top < shownWindow().top;
      const hold = holdPlace(block && !begun ? block : words, (node) => {
        const folded = node.closest(`[${FOLDED}], .lf-dial-more`);
        return folded && owner.get(folded);
      });
      change();
      hold();
    }

    // Where each block shown near the window stands in it now.
    /** @param {Element} scope */
    #positions(scope) {
      const window = shownWindow();
      const span = window.bottom - window.top;
      /** @type {Map<Element, number>} */
      const at = new Map();
      for (const block of this.#blocks(scope, scope)) {
        if (at.size >= MOVING) break;
        if (!shown(block)) continue;
        const box = block.getBoundingClientRect();
        if (box.bottom > window.top - span && box.top < window.bottom + span)
          at.set(block, box.top);
      }
      return at;
    }

    // Glide the blocks still shown from where they stood; fade in the ones arriving. A
    // gliding block is no scroll anchor while it glides: Firefox anchors on where a box
    // is drawn, so anchoring on one the glide carries scrolled the page by its glide,
    // frame by frame, and took the reader 360px off the line the hold had kept.
    /** @param {Map<Element, number>} before @param {Element} scope */
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
          motion(
            node,
            [
              { translate: `0 ${by}px`, overflowAnchor: "none" },
              { translate: "0 0", overflowAnchor: "none" },
            ],
            duration,
          );
      }
    }
  },
);
