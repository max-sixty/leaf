/* lf-dial: how much of the page to show, from the author's gists to every detail.
 *
 * Three depths, each showing all the one before it shows and more, so turning the
 * dial only ever adds or removes text and never swaps one wording for another:
 * Skim shows the lede, each block the author marked `.gist` and the headings above
 * them; Read shows the page as written; Everything also opens every closed `details`.
 * Skim shows nothing Read doesn't, so it keeps nothing inside a closed `details`.
 *
 * A gist is whatever a reader needs to understand the page at a high level, of any
 * kind: a passage's conclusion, a figure with its caption, a chart, a video, a canvas,
 * a table or a question they owe an answer. Which blocks those are is the author's
 * judgment for this page and its reader, so Skim keeps what the author marks and folds
 * everything else (the maintainer's choice: Skim cuts by its goal, not by a list).
 * Rejected: keeping every picture Leaf reads as one (`visualTags`) whether marked or
 * not. Its list of tags folded a video or a canvas a skimmer needed, kept pictures one
 * didn't, and grew an exception for each kind of picture that wasn't the page's, such
 * as decoration and the icons a widget draws. A widget holding the author's markup,
 * such as a tab, a question or an animation, stays whole at Skim when a gist stands
 * inside it.
 *
 * Which depth stands is this tab's view of the page, as a tab set's open panel is
 * (`tabStore`): no event records it, and a reload comes back to it. Read is the
 * default, so a page shows as authored until the reader turns the dial.
 *
 * Skim folds the rest with `hidden="until-found"`, so find-in-page, a fragment, the On
 * walk and travel to a comment still reach folded text and open the run holding it
 * (`beforematch`). Folding walks the dial's document (the view or `main` holding it, as
 * `lf-toc`'s outline does) and descends only into plain structure that holds the lede,
 * a gist or a heading that stands. Everything else is folded or kept whole: a line of
 * text, one with words of its own or only inline children, which keeps a gist in its
 * line whole; a table, whose cells stand in its grid; a figure, whose caption labels
 * all it holds, so a gist inside one shows the rest of it too; a disclosure, whose
 * summary is its control; and a Leaf element, whose children are its own. Such a block
 * stays only for a gist or lede inside it, since a heading in it can't stand alone. A
 * heading stands at Skim when a lede or gist follows it in document order
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
  commandsChanged,
  focusDestination,
  foldDuration,
  holdPlace,
  keeps,
  keepsText,
  LeafElement,
  motion,
  move,
  nextRender,
  offer,
  offerAction,
  onCurrentLocation,
  PAGE_INTERFACE,
  phrasing,
  plainPress,
  PREVIEW_ENDED,
  readingAt,
  registerRootHeader,
  shownWindow,
  signal,
  tabStore,
  viewDocument,
  whileConnected,
} from "/runtime/widget-api.js";
import { html, render, svg } from "/vendor/lit.js";
import "/vendor/webawesome-views.js";

const DEPTHS = [
  { name: "skim", label: "Skim", title: "The page's argument and what it asks of you" },
  { name: "read", label: "Read", title: "The page as written" },
  { name: "all", label: "Everything", title: "With every closed detail open" },
];
const RANKED = "h1, h2, h3, h4, h5, h6";
const HEADING = `${RANKED}, hgroup`;
// What Skim keeps for its own sake; a heading stands for the ones it heads.
const SUMMARY = ".lede, .gist";
// Blocks the dial keeps whole whatever they hold: a table, whose cells stand in its
// grid, a figure, whose caption labels all it holds, and a disclosure, whose summary is
// its control.
const WHOLE = "table, figure, details";
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
// rest; `--lf-dial-point` (`title`, `words`, `bars`, `strips`, `map`, `hang`), what pointing at a
// depth adds; `--lf-dial-page` (`none`, `ghost`), whether pointing at a depth marks on the
// page what turning to it would hide or open; and `--lf-dial-folds` (`plain`,
// `minutes`), whether each ⋯ at Skim says how long its gap takes.
//
// A depth's time is its words at a silent reading rate of 238 a minute, Brysbaert's
// (2019) mean for non-fiction, and 12 seconds for each picture.
const WORDS_PER_SECOND = 238 / 60;
const PICTURE_SECONDS = 12;
// What holds no words a reader reads: Leaf's chrome, a drawing, a widget's data.
const UNREAD = `${STANDS}, svg, [data-lf-content="data"]`;
// What the estimate times as a picture: what draws rather than says, apart from
// decoration, which no reader looks at for its own sake.
const PICTURE = 'img, svg, video, canvas, [data-lf-content="data"]';
const DECORATIVE =
  '[aria-hidden="true"], img[alt=""], [role="presentation"], [role="none"]';
const GHOST = "data-lf-dial-ghost";

/** @typedef {{kind: "heading" | "picture" | "text", skim: boolean, read: number, all: number}} Sized */
/** @typedef {{skim: number, read: number, all: number, blocks: Sized[]}} Sizes */
/** @typedef {"skim" | "read" | "all"} Depth */

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
// full ink and the others faint, with its minutes unless the dial shows them at rest.
/** @param {Sizes} sizes @param {string} pointed @param {boolean} timed */
const sizeBars = (sizes, pointed, timed) =>
  html`<span class="lf-dial-bars" ?data-timed=${timed}>
    ${DEPTHS.map(({ name, label }) => {
      const time = sizes[/** @type {Depth} */ (name)];
      return html`<span
        class="lf-dial-bars-row"
        ?data-pointed=${name === pointed}
        style=${`--share: ${(100 * time) / Math.max(sizes.all, 1)}%`}
      >
        <span class="lf-dial-bars-name">${label}</span>
        <span class="lf-dial-bars-track"><span class="lf-dial-bars-fill"></span></span>
        ${timed ? html`<span class="lf-dial-bars-time">${minutes(time)}</span>` : null}
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

// The page at each depth hanging under its own button as a sheet of its own, to one
// scale, each block a bar as long as it takes to read, so the three sheets read as how
// far down each depth's page runs, with the page showing between them. A frame rings
// the depth that stands and glides to the next as the reader turns the dial, and under
// the sheets a caption names the pointed depth and what it shows. `columns` is where
// each button stands across the dial, which the panel spans edge to edge. A sheet is its
// depth's to point at and to press, as its button is (`point`, `pick`).
/** @param {Sizes} sizes @param {string} pointed @param {string} chosen @param {{left: number, width: number}[]} columns @param {boolean} timed @param {(name: string) => void} point @param {(name: string) => void} pick */
const sizeHang = (sizes, pointed, chosen, columns, timed, point, pick) => {
  const tall = 112;
  const scale = tall / Math.max(sizes.all, 1);
  const at = DEPTHS.findIndex(({ name }) => name === chosen);
  const frame = columns[at] ?? { left: 0, width: 0 };
  const { label, title } = /** @type {(typeof DEPTHS)[number]} */ (
    DEPTHS.find(({ name }) => name === pointed)
  );
  // A sheet's height: its bars, its padding and its border, and its minutes.
  const sheet = (/** @type {Depth} */ name) => sizes[name] * scale + 10;
  return html`<span
    class="lf-dial-hang"
    style=${`--tall: ${tall}px`}
    ?data-timed=${timed}
  >
    ${DEPTHS.map(({ name }, i) => {
      const { left, width } = columns[i] ?? { left: 0, width: 0 };
      const time = sizes[/** @type {Depth} */ (name)];
      return html`<span
        class="lf-dial-hang-column"
        ?data-pointed=${name === pointed}
        ?data-chosen=${name === chosen}
        style=${`inset-inline-start: ${left}px; inline-size: ${width}px; --i: ${i}`}
        @pointerenter=${() => point(name)}
        @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
        @click=${() => pick(name)}
      >
        <span class="lf-dial-hang-page"
          ><span class="lf-dial-hang-bars" style=${`block-size: ${time * scale}px`}
            >${sizes.blocks.map((block) => {
              const seconds = secondsAt(block, name);
              return seconds
                ? html`<span
                    class=${`lf-dial-hang-${block.kind}`}
                    style=${`block-size: ${seconds * scale}px`}
                  ></span>`
                : null;
            })}</span
          >${
            timed ? html`<span class="lf-dial-hang-time">${minutes(time)}</span>` : null
          }</span
        >
      </span>`;
    })}
    <span
      class="lf-dial-hang-frame"
      style=${`inset-inline-start: ${frame.left}px; inline-size: ${frame.width}px; --sheet: ${sheet(/** @type {Depth} */ (chosen))}px`}
    ></span>
    <span class="lf-dial-hang-title"
      ><span><strong>${label}</strong> ${title}</span></span
    >
  </span>`;
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
    // What the last depth's preview declared, whose ending alone takes back its marks.
    /** @type {object | null} */
    #declared = null;
    // The depth whose preview stands.
    /** @type {string | null} */
    #pointed = null;
    // PROTOTYPE: whether the hanging pages stay up after Leaf's preview went, as a press
    // or an arrow key on the dial keeps them.
    #staying = signal(false);
    // The next depth's reading comes before the last one's ending, which then takes back
    // nothing. The pages go a frame later, so a press or a key that keeps them, heard
    // after Leaf's preview has gone, keeps them without a flicker.
    #ended = (/** @type {Event} */ event) => {
      if (/** @type {CustomEvent} */ (event).detail.declared !== this.#declared) return;
      const declared = this.#declared;
      nextRender(() => {
        if (!this.#staying.value && this.#declared === declared) this.#unpoint();
      });
    };
    // PROTOTYPE: the panel hanging each depth's page under its button, which the dial
    // draws under itself while its preview stands.
    /** @type {HTMLElement | null} */
    #hang = null;

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
      for (const { name, label } of DEPTHS) {
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
        // PROTOTYPE: the depth's time, which the dial's `rest` shows or hides.
        depth.append(offer("span", "lf-dial-time"));
        /** @type {any} */ (depth).lfPreview = () => this.#read(name);
        depth.addEventListener(PREVIEW_ENDED, this.#ended);
        // PROTOTYPE: kept pages follow the pointer across the buttons at once, as
        // across the sheets, where Leaf's preview waits its dwell after a press.
        depth.addEventListener("pointerenter", () => {
          if (this.#staying.value) this.#preview(name);
        });
        this.#radios.set(name, depth);
        group.append(depth);
      }
      group.addEventListener("change", () => this.turn(String(group.value)));
      this.append(group);
      this.#hang = offer("div", "lf-dial-hang-panel");
      this.#hang.setAttribute("aria-hidden", "true");
      this.append(this.#hang);
      // The hanging pages are the preview's face, so the pointer reaching them, or the
      // gaps between the buttons, reads the depth last pointed at again, standing by
      // the dial as each depth's does, and keeps them.
      /** @type {any} */ (this).lfPreview = () =>
        this.#pointed && this.#setting("point", "words") === "hang"
          ? this.#read(this.#pointed)
          : null;
      this.addEventListener(PREVIEW_ENDED, this.#ended);
      /** @type {any} */ (this).lfCommands = {
        title: "On the Skim control",
        rows: [
          {
            id: "dial.sizes-away",
            keys: ["Escape"],
            title: "put the sizes away",
            reach: "while the sizes hang under it",
            when: () => this.#staying.value,
            run: () => this.#keep(false),
          },
        ],
      };
      commandsChanged(this);
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
            if (this.#staying.value && this.#pointed) this.#preview(this.#pointed);
          },
          { signal },
        );
        // PROTOTYPE: a plain press on the dial while its pages hang keeps them, since the
        // press turns the dial and the pages show the depth moving to it, as an arrow
        // key in its depths does. Leaf's preview puts its reading away at the press or
        // the key, which it hears first, and reads again where the pointer goes next.
        // Kept pages go at Escape (the dial's command), as the pointer leaves the dial,
        // as focus leaves it, or at a press elsewhere.
        this.addEventListener(
          "pointerdown",
          (event) => {
            if (event.pointerType === "mouse" && plainPress(event)) this.#keep(true);
          },
          { signal },
        );
        // Leaving puts kept pages away after the dwell Leaf's preview leaves with, so a
        // pointer overshooting the dial's edge and coming back keeps them.
        let leaving = 0;
        this.addEventListener(
          "pointerleave",
          () => {
            if (this.#staying.value) leaving = setTimeout(() => this.#keep(false), 200);
          },
          { signal },
        );
        this.addEventListener("pointerenter", () => clearTimeout(leaving), { signal });
        const stopLocation = onCurrentLocation((/** @type {Element | null} */ at) => {
          if (this.#staying.value && !(at && this.contains(at))) this.#keep(false);
        });
        signal.addEventListener("abort", stopLocation);
        this.ownerDocument.addEventListener(
          "pointerdown",
          (event) => {
            if (this.#staying.value && !event.composedPath().includes(this))
              this.#keep(false);
          },
          { capture: true, signal },
        );
        this.ownerDocument.addEventListener(
          "keydown",
          (event) => {
            if (event.key.startsWith("Arrow") && event.composedPath().includes(this))
              this.#keep(true);
          },
          { capture: true, signal },
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
      // PROTOTYPE: pages the turn kept up show the depth it turned to.
      if (this.#pointed) this.#preview(name);
    }

    #draw() {
      if (this.#depths) this.#depths.value = this.#depth;
      // PROTOTYPE: the settings, and each depth's size where they show it.
      const rest = this.#setting("rest", "none");
      keeps(this, "data-rest", rest);
      const folds = this.#setting("folds", "plain");
      for (const marker of this.#runs.keys()) keeps(marker, "data-folds", folds);
      const sizes = rest === "none" ? null : this.#measure();
      if (!sizes || !this.#gauge) return;
      const share = (/** @type {number} */ seconds) =>
        `${(100 * seconds) / Math.max(sizes.all, 1)}%`;
      for (const [name, radio] of this.#radios) {
        const time = sizes[/** @type {Depth} */ (name)];
        const words = radio.querySelector(".lf-dial-time");
        keepsText(words, ` ${minutes(time)}`);
      }
      this.#gauge.style.setProperty("--skim", share(sizes.skim));
      this.#gauge.style.setProperty("--read", share(sizes.read));
      this.#gauge.style.setProperty(
        "--at",
        share(sizes[/** @type {Depth} */ (this.#depth)]),
      );
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

    // PROTOTYPE: keep the hanging pages up past Leaf's preview, or put them away.
    /** @param {boolean} kept */
    #keep(kept) {
      if (!this.#hang?.hasAttribute("data-open")) return;
      this.#staying.value = kept;
      if (!kept) this.#unpoint();
    }

    // Read what pointing at a depth shows, as Leaf's preview of it does.
    /** @param {string} name */
    #read(name) {
      this.#staying.value = false;
      return (this.#declared = this.#preview(name));
    }

    // Take back what pointing at a depth showed, as its preview goes.
    #unpoint() {
      this.#unghost?.();
      this.#unghost = null;
      this.#pointed = null;
      this.#staying.value = false;
      keeps(this, "data-pointed", null);
      if (this.#hang) keeps(this.#hang, "data-open", null);
    }

    // What pointing at a depth shows: what it is, and as the settings say, how long it
    // takes to read, the depths side by side, and on the page, what turning to it would
    // hide or open.
    /** @param {string} name */
    #preview(name) {
      const { label, title } = /** @type {(typeof DEPTHS)[number]} */ (
        DEPTHS.find((depth) => depth.name === name)
      );
      this.#unghost?.();
      this.#unghost =
        this.#setting("page", "none") === "ghost" ? this.#ghost(name) : null;
      const whole = this.#measure()?.all ?? 1;
      const part = this.#measure()?.[/** @type {Depth} */ (name)] ?? 0;
      this.#pointed = name;
      keeps(this, "data-pointed", name);
      if (this.#gauge)
        this.#gauge.style.setProperty(
          "--pointed",
          `${(100 * part) / Math.max(whole, 1)}%`,
        );
      const point = this.#setting("point", "words");
      const sizes = point === "title" ? null : this.#measure();
      if (!sizes) return { detail: [title] };
      const time = sizes[/** @type {Depth} */ (name)];
      const timed = !["minutes", "stacked"].includes(this.#setting("rest", "none"));
      // The hanging pages are the dial's own panel, opened and put away with its
      // preview (pointer, focus, a finger's hold, Escape), and kept up through a press
      // or an arrow key that turns the dial (`#staying`), whose face stays unseen:
      // Leaf's preview stands clear of the controls on the page, so where a link sat
      // under the dial it stood beside it, away from the buttons its columns hang from.
      // Each depth's stands by the dial, so crossing the buttons redraws it in place.
      if (point === "hang" && this.#hang) {
        keeps(this.#hang, "data-open", "");
        // Each button's place across the panel's inside, which its border insets.
        const from = this.getBoundingClientRect().left + this.#hang.clientLeft;
        const columns = DEPTHS.map((depth) => {
          const box = this.#radios.get(depth.name)?.getBoundingClientRect();
          return box
            ? { left: box.left - from, width: box.width }
            : { left: 0, width: 0 };
        });
        render(
          sizeHang(
            sizes,
            name,
            this.#depth,
            columns,
            timed,
            (depth) => this.#pointed && this.#preview(depth),
            (depth) => this.turn(depth),
          ),
          this.#hang,
        );
        return {
          name: html`<span class="lf-dial-hang-unseen">${label}: ${title}</span>`,
          at: this,
        };
      }
      if (point === "map") return { detail: [title, sizeMap(sizes, name)] };
      if (point === "bars") return { detail: [title, sizeBars(sizes, name, timed)] };
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
      return (
        words / WORDS_PER_SECOND + this.#picturesIn(block, scope, all) * PICTURE_SECONDS
      );
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
            : this.#picturesIn(block, scope, false)
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
    // PROTOTYPE: how many pictures in `block` the estimate times: each outermost one in
    // the author's markup in `scope`, so not decoration, Leaf's chrome or a widget's own
    // icons, and with `all` false, not inside a closed disclosure.
    /** @param {Element} block @param {Element} scope @param {boolean} all */
    #picturesIn(block, scope, all) {
      return [block, ...block.querySelectorAll(PICTURE)].filter((node) => {
        if (!node.matches(PICTURE) || node.matches(DECORATIVE)) return false;
        for (let at = node.parentElement; at && at !== scope; at = at.parentElement)
          if (
            at.matches(`${PICTURE}, ${STANDS}, ${DECORATIVE}`) ||
            (isLeafElement(at) && !at.hasAttribute("data-lf-content")) ||
            (!all && this.#closed(at))
          )
            return false;
        return true;
      }).length;
    }
    // Whether a child is kept whole at Skim: what Skim shows, or a block holding some of
    // it that the dial doesn't enter.
    /** @param {Element} child @param {Element} scope */
    #kept(child, scope) {
      return (
        child === this ||
        child.matches(SUMMARY) ||
        (child.matches(HEADING) && this.#heads(child, scope)) ||
        (!this.#enters(child) && this.#summarizes(child))
      );
    }
    // Whether the dial may lay out a child's children in its place: plain structure
    // that is no line of text and no block it keeps whole.
    /** @param {Element} child */
    #enters(child) {
      return !isLeafElement(child) && !child.matches(WHOLE) && !isLine(child);
    }
    // Whether Read shows `node` inside `child`: no closed disclosure between them.
    /** @param {Element} node @param {Element} child */
    #open(node, child) {
      if (this.#closed(child)) return false;
      for (let at = node.parentElement; at && at !== child; at = at.parentElement)
        if (this.#closed(at)) return false;
      return true;
    }
    // Whether a child holds the dial, a lede or a gist.
    /** @param {Element} child */
    #summarizes(child) {
      return (
        (child.contains(this) && !this.#closed(child)) ||
        [...child.querySelectorAll(SUMMARY)].some((node) => this.#open(node, child))
      );
    }
    // Whether a child holds anything Skim shows: the dial, a lede, a gist or a heading
    // that stands.
    /** @param {Element} child @param {Element} scope */
    #holds(child, scope) {
      return (
        this.#summarizes(child) ||
        [...child.querySelectorAll(HEADING)].some(
          (heading) => this.#open(heading, child) && this.#heads(heading, scope),
        )
      );
    }
    // Whether a lede or gist follows a heading in `scope`, in document order,
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
        if (element.matches(SUMMARY)) return true;
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
        keeps(marker, "data-folds", this.#setting("folds", "plain"));
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
