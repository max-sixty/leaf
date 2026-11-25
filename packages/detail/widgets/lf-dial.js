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
 * (`beforematch`). Folding walks the element the dial stands in, which is also the box
 * it sticks within, such as a column page's `main`, a sidebar page's body, a tab or a
 * message, so where the author writes the dial says what it governs. An `aside` there
 * folds like any block (the maintainer's request). Rejected: walking the view or
 * `main` holding the dial. On a sidebar page that walk takes the Layout's regions for
 * blocks, folding the sidebar's contents and setting a ⋯ in the Layout's row, and
 * sparing the sidebar takes a rule that never folds an `aside`, which keeps every
 * aside in the flow at Skim, gist or not. Rejected too: finding the dial's region from
 * the Layout's declarations, which couples the dial to the Layout's internals, and
 * which can't say what a dial in a header spanning both regions governs. The walk
 * descends only into plain structure that holds the lede,
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
 * Skim draws one quiet ⋯ for each gap in what it shows, and pressing it unfolds that
 * gap alone. A gap is every block between two kept ones in document order, whatever
 * structure holds them, so a section folded whole joins the folded rest of the section
 * before it, and nested sections fold as flat ones do. A ⋯ at a section's end and
 * another for the gist-less section after it was rejected: two marks stood for one
 * gap. The ⋯ stands after the gap's blocks in the box the gap starts in, so a gap that
 * runs to that box's end, as the rest of a section does, leaves its ⋯ as the box's
 * last child, and the section's box and every mark drawn on it hold the ⋯. After a
 * press the page shows more than Skim, so Skim's button wears its selection faded, and
 * pressing it folds the page to Skim again (the maintainer's request). A ⋯ whose gap
 * holds a heading previews the outermost headings in it (`lfPreview`), so a skimmer
 * can tell which sections lie behind it before pressing. Writing those names on the
 * page was rejected, since Skim shows only the passages the author chose. The dial
 * writes only what it folded: an element already hidden, such as an inactive tab, is
 * never touched, the margin is never folded, and leaving Skim takes back exactly the
 * folds and markers it made.
 *
 * Turning the dial keeps the reader's place. The block at the reading line, a quarter
 * of the way down the window, stays where it stood; when Skim folds that block, the
 * heading or gist it ran under takes its place on the line, so the reader lands on
 * what summarizes what they were reading. The blocks still shown then glide from where
 * they stood and the ones arriving fade in, so the eye can follow the page closing up
 * around the reader or opening out from them. Leaf's one hold keeps the place
 * (`holdPlace`), since the browser's scroll anchoring can't: Skim hides the block it
 * anchors.
 *
 * The dial is a radio group of the three depths, Web Awesome's, the control every
 * choice among a few views takes, as a recording's scopes and an image pair's views
 * do. Tab and the go-to key reach it, and inside it the arrow keys step one depth, as
 * in any radio group. It sticks at the window's top, at the column's end, so the
 * reader can turn it wherever they are reading rather than only at the top, which is
 * where keeping their place matters.
 *
 * Each depth's button says under its word how long that depth takes to read, so the
 * reader can weigh a depth before turning to it. The time is an estimate: the words a
 * depth shows at a silent reading rate, and a fixed time for each picture
 * (`WORDS_PER_SECOND`, `PICTURE_SECONDS`). Pointing at a depth, with a pointer, focus or
 * a finger's hold, hangs each depth's page under its own button as a sheet of its own,
 * drawn to one scale, so how far down a sheet runs shows how much of the page its depth
 * keeps. The page shows between the sheets, the pointed one stands in full ink, and a
 * frame in the accent rings the depth that stands. On the page, what turning to the
 * pointed depth would hide fades, and where it would open more wears a dashed ring. The
 * maintainer chose this from a playground that also tried minutes beside each word and
 * a gauge at rest, and bars, strips and a map of the page in Leaf's preview face, and
 * minutes on each ⋯.
 *
 * The sheets are the dial's preview, drawn by the dial while Leaf keeps its own preview
 * face unseen (`unseen`, module-previews.md). Leaf's preview stands clear of the
 * controls on the page, so where a link sat under the dial a chart in it stood beside
 * the dial, away from the buttons it compares; hanging each sheet under its own button
 * is an exception to one preview face the maintainer chose. Leaf still opens and ends
 * the preview on every route, makes it Escape's first step and gives a screen reader
 * each depth's description on focus. A plain click on the dial or an arrow key in its
 * depths, while the sheets hang, aims at the depth it reached, as a chart's key reaching
 * another point does (`lf-preview` with `aim`), so the sheets stay up and the frame
 * can be seen gliding to the depth turned to, the maintainer's choice. Otherwise they go
 * as Leaf's preview goes, a tap on touch included, since a finger that lifted reads no
 * preview. A sheet holds no control, since a preview reads and never
 * acts: pressing one only aims at the sheets again. Pointing marks the page only within
 * a window's height of what the window shows, so a reader who scrolls far while
 * pointing finds the rest unmarked; that keeps pointing the same cost on any page. */
import {
  nameOf,
  focusDestination,
  holdPlace,
  motion,
  move,
  phrasing,
  onPress,
  shownWindow,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { actionClass } from "/runtime/lib/control-faces.js";
import { offer, offerAction } from "/runtime/lib/controls.js";
import { nextRender } from "/runtime/lib/frame-pass.js";
import { motionTime } from "/runtime/lib/motion-timing.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
import { plainPress } from "/runtime/lib/keys.js";
import { html, render } from "/vendor/lit.js";
import "/vendor/webawesome-views.js";

const DEPTHS = [
  { name: "skim", label: "Skim", title: "The page's argument and what it asks of you" },
  { name: "read", label: "Read", title: "The page as written" },
  { name: "all", label: "Everything", title: "With every closed detail open" },
];
const RANKED = "h1, h2, h3, h4, h5, h6";
const HEADING = `${RANKED}, hgroup`;
// What Skim keeps for its own sake; a heading stands for the ones it heads.
const SUMMARY = ".lf-lede, .gist";
// Blocks the dial keeps whole whatever they hold: a table, whose cells stand in its
// grid, a figure, whose caption labels all it holds, and a disclosure, whose summary is
// its control.
const WHOLE = "table, figure, details";
// Never folded: what draws nothing, and words no author wrote, such as Leaf's labels.
const STANDS = "script, style, template, [data-lf-gen]";
const FOLDED = "data-lf-dial-folded";
// On the standing depth's button while the page shows a gap it folded: the word
// face's variant for a selection the page shows only in part (control-faces.js).
const PARTIAL = "data-lf-partial";
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
// How tall Everything's sheet stands, the tallest, since each depth shows all the one
// before it does. A sheet is drawn in rows of one line of text and its gap.
const TALL = 112;
const ROW = 3;

/** @typedef {"skim" | "read" | "all"} Depth */
/** @typedef {{kind: "heading" | "picture" | "text", skim: boolean, read: number, all: number}} Sized */
/** @typedef {{kind: Sized["kind"], rows: number}} Bar */
/** @typedef {{skim: number, read: number, all: number, bars: Record<Depth, Bar[]>, folds: Element[], closed: HTMLDetailsElement[]}} Sizes */

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

// A depth's blocks as the bars its sheet draws, `scale` rows' worth of pixels to the
// second: each block as many rows as its place on the sheet rounds to, and a heading or
// a picture a row at least, where that leaves the sheet no more than a row past its
// length. A block with no row of its own is drawn with the bar after it, so a sheet
// draws at most a bar a row however long the page.
/** @param {Sized[]} blocks @param {Depth} depth @param {number} scale */
const barsAt = (blocks, depth, scale) => {
  /** @type {Bar[]} */
  const bars = [];
  let length = 0;
  let rows = 0;
  for (const block of blocks) {
    const seconds = secondsAt(block, depth);
    if (!seconds) continue;
    length += seconds * scale;
    const due = Math.round(length / ROW);
    const to = block.kind === "text" ? due : Math.max(due, Math.min(rows + 1, due + 1));
    if (to > rows) bars.push({ kind: block.kind, rows: to - rows });
    rows = Math.max(rows, to);
  }
  return bars;
};
/** @param {Bar[]} bars */
const rowsOf = (bars) => bars.reduce((sum, bar) => sum + bar.rows, 0);

// The nodes among `nodes`, in document order down the page, that stand within a
// window's height of what the window shows, found by halving, so pointing marks the
// same few blocks on a page of any length.
/** @template {Element} T @param {T[]} nodes @returns {T[]} */
const nearWindow = (nodes) => {
  const window = shownWindow();
  const reach = window.bottom - window.top;
  let low = 0;
  let high = nodes.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    const box = /** @type {T} */ (nodes[middle]).getBoundingClientRect();
    if (box.bottom < window.top - reach) low = middle + 1;
    else high = middle;
  }
  const near = [];
  for (const node of nodes.slice(low)) {
    if (node.getBoundingClientRect().top > window.bottom + reach) break;
    near.push(node);
  }
  return near;
};

// Each depth's page hanging under its own button as a sheet of its own, to one scale,
// each block a bar as long as it takes to read, so the sheets read as how far down
// each depth's page runs, with the page showing between them. The pointed sheet stands
// in full ink, and a frame rings the depth that stands. `columns` is where each button
// stands across the dial, which the panel spans edge to edge; the pointer reaching a
// sheet points at its depth (`point`).
/** @param {Sizes} sizes @param {string} pointed @param {string} chosen @param {{left: number, width: number}[]} columns @param {(name: string) => void} point */
const sizeHang = (sizes, pointed, chosen, columns, point) => {
  const at = DEPTHS.findIndex(({ name }) => name === chosen);
  const frame = columns[at] ?? { left: 0, width: 0 };
  // A sheet's height: its rows, its padding and its border.
  const sheet = rowsOf(sizes.bars[/** @type {Depth} */ (chosen)]) * ROW + 10;
  return html`<span
    class="lf-dial-hang"
    style=${`--tall: ${rowsOf(sizes.bars.all) * ROW}px`}
  >
    ${DEPTHS.map(({ name }, i) => {
      const { left, width } = columns[i] ?? { left: 0, width: 0 };
      return html`<span
        class="lf-dial-hang-column"
        ?data-lf-pointed=${name === pointed}
        style=${`inset-inline-start: ${left}px; inline-size: ${width}px`}
        @pointerenter=${() => point(name)}
      >
        <span class="lf-dial-hang-page"
          ><span class="lf-dial-hang-bars"
            >${sizes.bars[/** @type {Depth} */ (name)].map(
              ({ kind, rows }) =>
                html`<span
                  class=${`lf-dial-hang-${kind}`}
                  style=${`block-size: ${rows * ROW}px`}
                ></span>`,
            )}</span
          ></span
        >
      </span>`;
    })}
    <span
      class="lf-dial-hang-frame"
      style=${`inset-inline-start: ${frame.left}px; inline-size: ${frame.width}px; --sheet: ${sheet}px`}
    ></span>
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
    // The page's reading time at each depth, measured once for each presentation of the
    // page.
    /** @type {Sizes | null} */
    #sizes = null;
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
    // Whether a plain press on the dial is under way.
    #pressing = false;
    // What puts the sheets away once the press on the dial is over.
    /** @type {(() => void) | null} */
    #lifted = null;
    // The sheets go as the reading they show ends, unless a newer one took its place: the
    // next depth's reading comes before the last one's ending, and a turn reads the depth
    // it turned to again (`#aim`) after the press or key that put Leaf's preview away.
    // So they go a frame later, or for a press once it is over, and stay up through a
    // turn without a flicker.
    #ended = (/** @type {Event} */ event) => {
      if (/** @type {CustomEvent} */ (event).detail.declared !== this.#declared) return;
      const declared = this.#declared;
      const away = () => {
        if (this.#declared === declared) this.#unpoint();
      };
      // Leaf's preview hears a press go down before the dial does.
      nextRender(() => {
        if (this.#pressing) this.#lifted = away;
        else away();
      });
    };
    // The panel the sheets hang in, under the dial, open while its preview stands.
    /** @type {HTMLElement | null} */
    #hang = null;

    get #key() {
      return `lf-dial:${this.id}`;
    }

    // What the dial governs: the element it stands in.
    get #scope() {
      return this.parentElement;
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
        depth.append(offer("span", "lf-dial-time"));
        /** @type {any} */ (depth).lfPreview = () => this.#read(name);
        depth.addEventListener("lf-preview-ended", this.#ended);
        this.#radios.set(name, depth);
        group.append(depth);
      }
      group.addEventListener("change", () => {
        const name = String(group.value);
        this.turn(name);
        this.#aim(this.#radios.get(name) ?? this);
      });
      this.append(group);
      this.#hang = offer("div", "lf-dial-hang-panel");
      this.#hang.setAttribute("aria-hidden", "true");
      // A press on the sheets leaves focus where it was.
      this.#hang.addEventListener("mousedown", (event) => event.preventDefault());
      this.append(this.#hang);
      // The sheets are the preview's face, so the pointer reaching them, or the gaps
      // between the buttons, reads the depth last pointed at again, standing by the dial
      // as each depth's does, and keeps them.
      /** @type {any} */ (this).lfPreview = () =>
        this.#pointed ? this.#read(this.#pointed) : null;
      this.addEventListener("lf-preview-ended", this.#ended);
      // The dial sticks at the window's top while the reader scrolls the page under it,
      // so landings arrive below it.
      this.toggleAttribute("data-lf-root-header", true);
      this.#draw();
      whileConnected(this, (signal) => {
        // A revision applied in place rebuilds the folds over its new structure.
        this.ownerDocument.addEventListener(
          "lf-page-interface",
          () => {
            this.#sizes = null;
            this.#apply(this.#depth, { moving: false });
          },
          { signal },
        );
        // A plain press on the dial puts Leaf's preview away as it goes down, and its
        // click turns the dial or aims at the sheets again (`#aim`), so the sheets wait
        // until the press is over. A finger's tap reads no preview again, so its sheets
        // go at once.
        const stopPress = onPress((down, path) => {
          if (!path.includes(this) || !plainPress(down) || down.pointerType === "touch")
            return null;
          this.#pressing = true;
          return () => () => {
            this.#pressing = false;
            const away = this.#lifted;
            this.#lifted = null;
            if (away) nextRender(away);
          };
        });
        signal.addEventListener("abort", stopPress);
        this.addEventListener(
          "click",
          (event) => {
            if (!plainPress(event)) return;
            const depth =
              event.target instanceof Element && event.target.closest(".lf-dial-depth");
            // The standing depth's button, which turns no radio, folds an unfolded gap.
            if (depth && depth === this.#radios.get(this.#depth))
              this.turn(this.#depth);
            this.#aim(depth || this);
          },
          { signal },
        );
        const stored = tabStore.get(this.#key);
        if (stored) this.#apply(stored, { moving: false });
        return () => this.#restore();
      });
    }

    // Turn the dial to `name`, keeping the reader's place and moving the page there.
    /** @param {string} name */
    turn(name) {
      if (name === this.#depth) {
        if (this.#radios.get(name)?.hasAttribute(PARTIAL)) this.#refold();
        return;
      }
      tabStore.set(this.#key, name === "read" ? null : name);
      this.#apply(name, { moving: true });
    }

    // Fold again the gaps the reader unfolded at Skim, keeping their place.
    #refold() {
      const scope = this.#scope;
      if (!scope) return;
      const before = this.#positions(scope);
      this.#keepingPlace(scope, () => this.#fold(scope));
      this.#move(before, scope);
    }

    #draw() {
      if (this.#depths) this.#depths.value = this.#depth;
      const sizes = this.#measure();
      if (!sizes) return;
      for (const [name, radio] of this.#radios)
        keepsText(
          radio.querySelector(".lf-dial-time"),
          ` ${minutes(sizes[/** @type {Depth} */ (name)])}`,
        );
    }

    // While the sheets hang, a press or an arrow key on the dial aims at what it reached,
    // as a chart's key reaching another point does, so Leaf's preview reads the depth it
    // turned to, or the sheets, again, whatever put the last reading away, and the frame
    // glides there with the sheets up (the maintainer's choice).
    /** @param {Element} at */
    #aim(at) {
      if (this.#pointed)
        at.dispatchEvent(
          new CustomEvent("lf-preview", {
            bubbles: true,
            composed: true,
            detail: { aim: true },
          }),
        );
    }

    // Read what pointing at a depth shows, as Leaf's preview of it does.
    /** @param {string} name */
    #read(name) {
      return (this.#declared = this.#preview(name));
    }

    // Take back what pointing at a depth showed, as its preview goes.
    #unpoint() {
      this.#unghost?.();
      this.#unghost = null;
      this.#pointed = null;
      if (this.#hang) keeps(this.#hang, "data-lf-open", null);
    }

    // What pointing at a depth shows: the sheets under the dial, and on the page, what
    // turning to it would hide or open. Leaf's preview keeps what the depth shows unseen,
    // for a screen reader to hear on focus; it stands by the dial for each depth, so
    // crossing the buttons redraws it in place.
    /** @param {string} name */
    #preview(name) {
      const { title } = /** @type {(typeof DEPTHS)[number]} */ (
        DEPTHS.find((depth) => depth.name === name)
      );
      const sizes = this.#measure();
      if (!sizes || !this.#hang) return { detail: [title] };
      this.#unghost?.();
      this.#unghost = this.#ghost(name);
      this.#pointed = name;
      keeps(this.#hang, "data-lf-open", "");
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
          (depth) => this.#pointed && this.#preview(depth),
        ),
        this.#hang,
      );
      return { name: title, unseen: true, at: this };
    }

    // Mark on the page what turning to `name` would change, near the window: fade what
    // it would hide and ring where it would open more. Returns what takes the marks back.
    /** @param {string} name */
    #ghost(name) {
      const sizes = this.#measure();
      if (
        !sizes ||
        (name === this.#depth && !this.#radios.get(name)?.hasAttribute(PARTIAL))
      )
        return null;
      /** @type {Element[]} */
      const goes = [];
      /** @type {Element[]} */
      const comes = [];
      if (name === "skim")
        for (const block of nearWindow(sizes.folds)) if (shown(block)) goes.push(block);
      // Everything's disclosures close at Skim and Read.
      if (this.#depth === "all")
        for (const details of nearWindow([...this.#opened]))
          if (shown(details))
            goes.push(
              ...[...details.children].filter((child) => child.localName !== "summary"),
            );
      // Leaving Skim opens every fold.
      if (this.#depth === "skim" && name !== "skim")
        comes.push(...nearWindow([...this.#runs.keys()]));
      if (name === "all")
        for (const details of nearWindow(sizes.closed))
          if (!details.open && shown(details)) comes.push(details);
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

    // The page's reading time at each depth and the bars each sheet draws, with the
    // blocks Skim folds and the closed disclosures Everything opens, read once for each
    // presentation of the page.
    #measure() {
      if (this.#sizes) return this.#sizes;
      const scope = this.#scope;
      if (!scope) return null;
      /** @type {Sized[]} */
      const blocks = [];
      /** @type {Element[]} */
      const folds = [];
      for (const block of this.#blocks(scope, scope)) {
        if (block === this) continue;
        const skim = this.#kept(block, scope);
        if (!skim) folds.push(block);
        blocks.push({
          kind: block.matches(HEADING)
            ? "heading"
            : this.#picturesIn(block, scope, false)
              ? "picture"
              : "text",
          skim,
          read: this.#secondsIn(block, scope, false),
          all: this.#secondsIn(block, scope, true),
        });
      }
      const total = (/** @type {Depth} */ depth) =>
        blocks.reduce((sum, block) => sum + secondsAt(block, depth), 0);
      const all = total("all");
      const scale = TALL / Math.max(all, 1);
      return (this.#sizes = {
        skim: total("skim"),
        read: total("read"),
        all,
        bars: {
          skim: barsAt(blocks, "skim", scale),
          read: barsAt(blocks, "read", scale),
          all: barsAt(blocks, "all", scale),
        },
        folds,
        closed: [...scope.querySelectorAll("details")].filter(
          (details) =>
            (!details.open || this.#opened.has(details)) && !details.closest(STANDS),
        ),
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
      this.#radios.get(this.#depth)?.removeAttribute(PARTIAL);
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

    // Fold each gap not folded already.
    /** @param {Element} scope */
    #fold(scope) {
      const listening = (this.#listening ??= new AbortController());
      for (const run of this.#runsIn(scope))
        if (!run.blocks[0]?.hasAttribute(FOLDED)) this.#foldRun(run, listening.signal);
      this.#radios.get(this.#depth)?.removeAttribute(PARTIAL);
    }

    // Whether `node` is a disclosure whose body Read shows none of, so Skim keeps
    // nothing inside it, counting those Everything opened as closed.
    /** @param {Element} node */
    #closed(node) {
      return (
        node instanceof HTMLDetailsElement && (!node.open || this.#opened.has(node))
      );
    }
    // How many pictures in `block` the estimate times: each outermost one in the
    // author's markup in `scope`, so not decoration, Leaf's chrome or a widget's own
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
        const names = outermost(blocks).map(nameOf).filter(Boolean);
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
      // After the run's blocks in the box it starts in, so a run that runs to that
      // box's end, as a section's rest does, leaves the ⋯ the box's last child.
      const parent = blocks[0]?.parentElement;
      const last = blocks.findLast((block) => block.parentElement === parent);
      if (parent && last) move(parent, marker, last.nextSibling);
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
      this.#radios.get(this.#depth)?.setAttribute(PARTIAL, "");
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
      const hold = holdPlace(scope, (node) => {
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
      const duration = motionTime("--lf-motion-fold");
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
