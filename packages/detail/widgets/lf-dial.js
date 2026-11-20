/* lf-dial: how much of the page to show, from the author's gists to every detail.
 *
 * Three depths, each showing all the one before it shows and more, so turning the
 * dial only ever adds or removes text and never swaps one wording for another:
 * Skim shows the lede, each block the author marked `.gist`, every picture and the
 * headings above them; Read shows the page as written; Everything also opens every
 * closed `details`. Skim shows nothing Read doesn't, so it keeps nothing inside a
 * closed `details`.
 *
 * A picture is what Leaf reads as one wherever a reader points at it (`visualTags`): a
 * figure, an image, an inline drawing, or a widget whose entry declares `visual`, such
 * as a chart, a diagram or a screenshot pair, with its caption where a `figure` gives
 * it one. A reader on a quick pass reads a page by its pictures as much as by its words,
 * so Skim keeps every picture the page shows rather than only the ones an author marks
 * (the maintainer's choice). Rejected: folding every picture the author left unmarked,
 * which made Skim words alone. What HTML marks as decoration (`aria-hidden`, an empty
 * `alt`, a presentation role) is no picture, nor is Leaf's own chrome, and a picture
 * inside a widget that draws its own content (`content` `data` or `empty`), such as an
 * icon in a code view, is that widget's drawing. A widget holding the author's markup,
 * such as a tab, a question or an animation, stays whole at Skim when a picture or a
 * gist stands inside it.
 *
 * Which depth stands is this tab's view of the page, as a tab set's open panel is
 * (`tabStore`): no event records it, and a reload comes back to it. Read is the
 * default, so a page shows as authored until the reader turns the dial.
 *
 * Skim folds the rest with `hidden="until-found"`, so find-in-page, a fragment, the On
 * walk and travel to a comment still reach folded text and open the run holding it
 * (`beforematch`). Folding walks the dial's document (the view or `main` holding it, as
 * `lf-toc`'s outline does) and descends only into plain structure that holds the lede,
 * a gist, a picture or a heading that stands. Everything else is folded or kept whole:
 * a line of text, one with words of its own or only inline children, which keeps a
 * picture in its line whole; a table, whose cells stand in its grid; a disclosure,
 * whose summary is its control; and a Leaf element, whose children are its own. A
 * heading stands at Skim when a lede, gist or picture follows it in document order
 * before the next heading of its rank or above, so a section with nothing for a
 * skimmer folds whole, heading included. Keeping every heading was rejected: it made
 * Skim a fixed cut of every section, whether or not one had anything for a skimmer.
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
  phrasing,
  PREVIEW_ENDED,
  readingAt,
  registerRootHeader,
  shownWindow,
  tabStore,
  viewDocument,
  visualTags,
  whileConnected,
} from "/runtime/widget-api.js";
import { html, svg } from "/vendor/lit.js";
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
// What HTML says is decoration, which no reader looks at for its own sake.
const DECORATIVE =
  '[aria-hidden="true"], img[alt=""], [role="presentation"], [role="none"]';
// A Leaf element that draws its own content, whose pictures are its drawing.
const DRAWS = '[data-lf-content="data"], [data-lf-content="empty"]';
// Blocks the dial keeps whole whatever they hold: a table, whose cells stand in its
// grid, and a disclosure, whose summary is its control.
const WHOLE = "table, details";
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
// Whether an element is a line of text: one with words of its own, or one whose
// children all stand in a line of words (`phrasing`), as an image beside a link and an
// `em` does. A block among its children makes it structure, whose stray inline
// children, such as a button, fold as blocks.
/** @param {Element} element */
const isLine = (element) => {
  if (
    [...element.childNodes].some(
      (node) => node.nodeType === Node.TEXT_NODE && /\S/.test(node.textContent ?? ""),
    )
  )
    return true;
  const children = [...element.children].filter((child) => !child.matches(STANDS));
  return children.length > 0 && children.every(phrasing);
};
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

// PROTOTYPE: ways the dial can show how long each depth takes, for the maintainer to
// pick from. Each is a custom property a page sets on the dial, read as it draws:
// `--lf-dial-rest` (`none`, `minutes`, `stacked`, `gauge`), what the dial shows at
// rest; `--lf-dial-point` (`title`, `words`, `bars`, `strips`, `map`), what pointing at a depth
// adds; `--lf-dial-page` (`none`, `ghost`), whether pointing at a depth marks on the
// page what turning to it would hide or open; and `--lf-dial-folds` (`plain`,
// `minutes`), whether each ⋯ at Skim says how long its gap takes.
//
// A depth's time is its words at a silent reading rate of 238 a minute, Brysbaert's
// (2019) mean for non-fiction, and 12 seconds for each picture.
const WORDS_PER_SECOND = 238 / 60;
const PICTURE_SECONDS = 12;
// What holds no words a reader reads: Leaf's chrome, a drawing, a widget's data.
const UNREAD = `${STANDS}, svg, [data-lf-content="data"]`;
const GHOST = "data-lf-dial-ghost";

/** @typedef {{kind: "heading" | "picture" | "text", skim: boolean, read: number, all: number}} Sized */
/** @typedef {{skim: number, read: number, all: number, blocks: Sized[]}} Sizes */
/** @typedef {"skim" | "read" | "all"} Depth */

// Set a property only where it changes, so observers of the dial hear no idle write.
/** @param {HTMLElement} node @param {string} name @param {string} value */
const restyle = (node, name, value) => {
  if (node.style.getPropertyValue(name) !== value) node.style.setProperty(name, value);
};
/** @param {number} seconds */
const minutes = (seconds) => `${Math.max(1, Math.round(seconds / 60))} min`;
/** @param {Sized} block @param {string} depth */
const secondsAt = (block, depth) =>
  depth === "skim"
    ? block.skim
      ? block.read
      : 0
    : depth === "read"
      ? block.read
      : block.all;

// Each depth a bar on one baseline, as long as it takes to read, the pointed one in
// full ink and the others faint.
/** @param {Sizes} sizes @param {string} pointed */
const sizeBars = (sizes, pointed) =>
  html`<span class="lf-dial-bars">
    ${DEPTHS.map(({ name, label }) => {
      const time = sizes[/** @type {Depth} */ (name)];
      return html`<span
        class="lf-dial-bars-row"
        ?data-pointed=${name === pointed}
        style=${`--share: ${(100 * time) / Math.max(sizes.all, 1)}%`}
      >
        <span class="lf-dial-bars-name">${label}</span>
        <span class="lf-dial-bars-track"><span class="lf-dial-bars-fill"></span></span>
        <span class="lf-dial-bars-time">${minutes(time)}</span>
      </span>`;
    })}
  </span>`;

// The bars, each drawn as the page it reads: a run of the depth's blocks in order,
// each as long as it takes to read, a heading strong, a picture tinted, text pale.
/** @param {Sizes} sizes @param {string} pointed */
const sizeStrips = (sizes, pointed) =>
  html`<span class="lf-dial-bars lf-dial-strips">
    ${DEPTHS.map(({ name, label }) => {
      const time = sizes[/** @type {Depth} */ (name)];
      const all = Math.max(sizes.all, 1);
      return html`<span class="lf-dial-bars-row" ?data-pointed=${name === pointed}>
        <span class="lf-dial-bars-name">${label}</span>
        <span class="lf-dial-bars-track"
          >${sizes.blocks.map((block) => {
            const seconds = secondsAt(block, name);
            return seconds
              ? html`<span
                  class=${`lf-dial-strip-${block.kind}`}
                  style=${`inline-size: ${(100 * seconds) / all}%`}
                ></span>`
              : null;
          })}</span
        >
        <span class="lf-dial-bars-time">${minutes(time)}</span>
      </span>`;
    })}
  </span>`;

// The page at each depth, drawn to one scale, each block a bar as long as it takes
// to read: a heading a short strong bar, a picture a tinted box, text a pale bar.
/** @param {Sizes} sizes @param {string} pointed */
const sizeMap = (sizes, pointed) => {
  const width = 56;
  const gap = 20;
  const tall = 120;
  const inset = 5;
  const scale = (tall - 2 * inset) / Math.max(sizes.all, 1);
  const columns = DEPTHS.map(({ name, label }, i) => {
    const x = i * (width + gap);
    let y = inset;
    const bars = [];
    for (const block of sizes.blocks) {
      const seconds = secondsAt(block, name);
      if (!seconds) continue;
      const high = seconds * scale;
      bars.push(
        svg`<rect class=${`lf-dial-map-${block.kind}`} x=${x + inset} y=${y} rx="1" width=${
          block.kind === "heading" ? (width - 2 * inset) * 0.55 : width - 2 * inset
        } height=${Math.max(high - 1.5, 1)}></rect>`,
      );
      y += high;
    }
    const time = sizes[/** @type {Depth} */ (name)];
    return svg`<g class=${name === pointed ? "lf-dial-map-pointed" : "lf-dial-map-other"}>
      <rect class="lf-dial-map-page" x=${x} y="0" rx="3" width=${width} height=${y + inset}></rect>
      ${bars}
      <text x=${x + width / 2} y=${tall + 15}>${label}</text>
      <text class="lf-dial-map-time" x=${x + width / 2} y=${tall + 28}>${minutes(time)}</text>
    </g>`;
  });
  const across = 3 * width + 2 * gap;
  return html`<svg
    class="lf-dial-map"
    viewBox=${`-2 -2 ${across + 4} ${tall + 36}`}
    width=${across + 4}
    height=${tall + 36}
    aria-hidden="true"
  >
    ${columns}
  </svg>`;
};

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
    // PROTOTYPE: the page's reading time at each depth, measured once for each
    // presentation of the page.
    /** @type {Sizes | null} */
    #sizes = null;
    /** @type {HTMLElement | null} */
    #gauge = null;
    // Each depth's radio, by depth.
    /** @type {Map<string, HTMLElement>} */
    #radios = new Map();
    // Taking back what pointing at a depth marked on the page.
    /** @type {(() => void) | null} */
    #unghost = null;
    // The tags Leaf reads as a picture, from the page's layer.
    #pictures = "";

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
      this.#pictures = visualTags().join(", ");
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
        /** @type {any} */ (depth).lfPreview = () => this.#preview(name, title);
        // PROTOTYPE: the depth's time, which the dial's `rest` shows or hides.
        depth.append(offer("span", "lf-dial-time"));
        depth.addEventListener(PREVIEW_ENDED, () => {
          this.#unghost?.();
          this.#unghost = null;
          delete this.dataset.pointed;
        });
        this.#radios.set(name, depth);
        group.append(depth);
      }
      group.addEventListener("change", () => this.turn(String(group.value)));
      this.append(group);
      this.#gauge = offer("div", "lf-dial-gauge");
      this.#gauge.setAttribute("aria-hidden", "true");
      this.#gauge.append(
        offer("span", "lf-dial-gauge-fill"),
        offer("span", "lf-dial-gauge-pointed"),
      );
      for (const { name } of DEPTHS)
        this.#gauge.append(offer("span", `lf-dial-gauge-mark lf-dial-gauge-${name}`));
      this.append(this.#gauge);
      this.#draw();
      whileConnected(this, (signal) => {
        // PROTOTYPE: a playground sets the dial's settings through its sample's root.
        const settings = new MutationObserver(() => this.#draw());
        settings.observe(this.ownerDocument.documentElement, { attributes: true });
        signal.addEventListener("abort", () => settings.disconnect());
        // A revision applied in place rebuilds the folds over its new structure.
        this.ownerDocument.addEventListener(
          PAGE_INTERFACE,
          () => {
            this.#sizes = null;
            this.#apply(this.#depth, { moving: false });
          },
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
      // PROTOTYPE: the settings, and each depth's size where they show it.
      const rest = this.#setting("rest", "none");
      if (this.dataset.rest !== rest) this.dataset.rest = rest;
      const folds = this.#setting("folds", "plain");
      for (const marker of this.#runs.keys())
        if (marker.dataset.folds !== folds) marker.dataset.folds = folds;
      const sizes = rest === "none" ? null : this.#measure();
      if (!sizes || !this.#gauge) return;
      const share = (/** @type {number} */ seconds) =>
        `${(100 * seconds) / Math.max(sizes.all, 1)}%`;
      for (const [name, radio] of this.#radios) {
        const time = sizes[/** @type {Depth} */ (name)];
        const words = radio.querySelector(".lf-dial-time");
        if (words && words.textContent !== ` ${minutes(time)}`)
          words.textContent = ` ${minutes(time)}`;
      }
      restyle(this.#gauge, "--skim", share(sizes.skim));
      restyle(this.#gauge, "--read", share(sizes.read));
      restyle(this.#gauge, "--at", share(sizes[/** @type {Depth} */ (this.#depth)]));
    }

    // PROTOTYPE: one of the dial's settings, from its `--lf-dial-NAME`.
    /** @param {string} name @param {string} fallback */
    #setting(name, fallback) {
      return (
        getComputedStyle(this)
          .getPropertyValue(`--lf-dial-${name}`)
          .trim()
          .replace(/^"|"$/g, "") || fallback
      );
    }

    // What pointing at a depth shows: what it is, and as the settings say, how long it
    // takes to read, the depths side by side, and on the page, what turning to it would
    // hide or open.
    /** @param {string} name @param {string} title */
    #preview(name, title) {
      this.#unghost?.();
      this.#unghost =
        this.#setting("page", "none") === "ghost" ? this.#ghost(name) : null;
      const all = this.#measure()?.all ?? 1;
      const at = this.#measure()?.[/** @type {Depth} */ (name)] ?? 0;
      if (this.dataset.pointed !== name) this.dataset.pointed = name;
      if (this.#gauge)
        restyle(this.#gauge, "--pointed", `${(100 * at) / Math.max(all, 1)}%`);
      const point = this.#setting("point", "words");
      const sizes = point === "title" ? null : this.#measure();
      if (!sizes) return { detail: [title] };
      const time = sizes[/** @type {Depth} */ (name)];
      if (point === "map") return { detail: [title, sizeMap(sizes, name)] };
      if (point === "bars") return { detail: [title, sizeBars(sizes, name)] };
      if (point === "strips") return { detail: [title, sizeStrips(sizes, name)] };
      return {
        detail: [
          title,
          time < 45 ? "Under a minute to read" : `About ${minutes(time)} to read`,
        ],
      };
    }

    // PROTOTYPE: mark on the page what turning to `name` would change: fade what it
    // would hide and ring where it would open more. Returns what takes the marks back.
    /** @param {string} name */
    #ghost(name) {
      const scope = this.#scope;
      if (!scope || name === this.#depth) return null;
      /** @type {Element[]} */
      const goes = [];
      /** @type {Element[]} */
      const comes = [];
      if (name === "skim")
        for (const run of this.#runsIn(scope))
          for (const block of run.blocks) if (shown(block)) goes.push(block);
      // Everything's disclosures close at Skim and Read.
      if (this.#depth === "all")
        for (const details of this.#opened)
          if (shown(details))
            goes.push(
              ...[...details.children].filter((child) => child.localName !== "summary"),
            );
      // Leaving Skim opens every fold.
      if (this.#depth === "skim") comes.push(...this.#runs.keys());
      if (name === "all")
        for (const details of scope.querySelectorAll("details:not([open])"))
          if (shown(details) && !details.closest(STANDS)) comes.push(details);
      for (const node of goes) node.setAttribute(GHOST, "goes");
      for (const node of comes) node.setAttribute(GHOST, "comes");
      return () => {
        for (const node of [...goes, ...comes]) node.removeAttribute(GHOST);
      };
    }

    // Seconds to read `block` as Read shows it, or with `all` as Everything does.
    /** @param {Element} block @param {Element} scope @param {boolean} all */
    #secondsIn(block, scope, all) {
      let words = 0;
      if (!block.matches(UNREAD)) {
        const walker = block.ownerDocument.createTreeWalker(
          block,
          NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
          (node) =>
            node instanceof Element &&
            (node.matches(UNREAD) ||
              (!all &&
                node.parentElement !== null &&
                this.#closed(node.parentElement) &&
                node.localName !== "summary"))
              ? NodeFilter.FILTER_REJECT
              : NodeFilter.FILTER_ACCEPT,
        );
        for (let node = walker.nextNode(); node; node = walker.nextNode())
          if (node.nodeType === Node.TEXT_NODE)
            words += node.textContent?.match(/\S+/g)?.length ?? 0;
      }
      const pictures = [block, ...block.querySelectorAll(this.#pictures)].filter(
        (node) => this.#isPicture(node, scope, all),
      ).length;
      return words / WORDS_PER_SECOND + pictures * PICTURE_SECONDS;
    }

    // The page's reading time at each depth, and each block's part in it.
    #measure() {
      if (this.#sizes) return this.#sizes;
      const scope = this.#scope;
      if (!scope) return null;
      /** @type {Sized[]} */
      const blocks = [];
      for (const block of this.#blocks(scope, scope)) {
        if (block === this) continue;
        blocks.push({
          kind: block.matches(HEADING)
            ? "heading"
            : [block, ...block.querySelectorAll(this.#pictures)].some((node) =>
                  this.#isPicture(node, scope),
                )
              ? "picture"
              : "text",
          skim: this.#kept(block, scope),
          read: this.#secondsIn(block, scope, false),
          all: this.#secondsIn(block, scope, true),
        });
      }
      const total = (/** @type {string} */ depth) =>
        blocks.reduce((sum, block) => sum + secondsAt(block, depth), 0);
      return (this.#sizes = {
        skim: total("skim"),
        read: total("read"),
        all: total("all"),
        blocks,
      });
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
    /** @param {Element} node @param {Element} scope @param {boolean} [all] */
    #isPicture(node, scope, all = false) {
      if (!node.matches(this.#pictures) || node.matches(DECORATIVE)) return false;
      for (let at = node.parentElement; at && at !== scope; at = at.parentElement)
        if (
          at.matches(`${this.#pictures}, ${STANDS}, ${DRAWS}, [aria-hidden="true"]`) ||
          (isLeafElement(at) && !at.hasAttribute("data-lf-content")) ||
          (!all && this.#closed(at))
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
    // Whether the dial may lay out a child's children in its place: plain structure
    // that is no line of text and no block it keeps whole.
    /** @param {Element} child */
    #enters(child) {
      return !isLeafElement(child) && !child.matches(WHOLE) && !isLine(child);
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
        [...child.querySelectorAll(this.#pictures)].some((node) =>
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
      // PROTOTYPE: how long the gap takes, which the dial's `folds` shows or hides.
      const scope = this.#scope;
      if (scope) {
        const seconds = blocks.reduce(
          (sum, block) => sum + this.#secondsIn(block, scope, false),
          0,
        );
        marker.append(
          offer(
            "span",
            "lf-dial-more-time",
            seconds < 50
              ? `${Math.max(10, Math.round(seconds / 10) * 10)} s`
              : minutes(seconds),
          ),
        );
        marker.dataset.folds = this.#setting("folds", "plain");
      }
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
