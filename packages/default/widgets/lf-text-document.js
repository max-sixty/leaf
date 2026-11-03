/* A document owns one text and its source/preview readings. The text is its `value`,
 * which Leaf sets from a bound source or widget output, or from the `<pre>` the page
 * wrote when the markup binds neither (element-data.js, "Bound values"). Optional
 * previews compose the ordinary lf-tabs switcher, so keyboard, reveal, and tab
 * memory have the same owner as authored views. Each reading has its own bounded
 * viewport, which keeps its scroll place independent, and switching keeps the page
 * still. Where the text can arrive after first paint, the viewport is `--lf-bound`
 * tall. A Markdown preview of written text instead takes its rendered height, which
 * its first paint already holds (`x-prepaint`), and its Source tab takes the same
 * height (`holdSource`), drawn on it or switched to it. Where that height cuts the
 * source, a press shows every line (`cut`), as a thread's Full quote shows a whole
 * quote: a reflow the reader asks for. The cut box doesn't scroll, so the press is the
 * one way to the rest, and stays at the box's foot rather than scrolling off with the
 * lines.
 * Pierre draws numbered source using the same static renderer as diffs. Its sheets
 * are scoped to the listing; gutter glyphs are generated content, so selecting or
 * copying the source never includes line numbers. The listing's rows stand in runs that
 * the browser draws only in view (`inRuns`), each sized ahead of drawing by the lines
 * its rows fill (`sizeRuns`). The Markdown preview renders a file, whose soft line
 * breaks are spaces, so a paragraph wraps to the preview's width. The source and
 * Markdown renderers reconcile unchanged text across source updates, the source's rows
 * across the whole listing (`reconcileRuns`). HTML
 * lives in a separate frame so its styles and scripts cannot access Leaf’s document.
 * Source provenance is stamped with its text before awaiting the frame's presentation. */
import {
  failSoft,
  generatedElement,
  ensureSyntaxLanguage,
  inBaseLayer,
  LeafElement,
  nothing,
  whileConnected,
  keepsText,
  setRenderedChildren,
  setChildLists,
  setChildren,
  focusDestination,
  keepsHidden,
  offer,
  offerAction,
  loadMarkdown,
  renderMarkdown,
  sizeObserver,
  layoutPx,
  textWidth,
  nextFrame,
} from "/runtime/widget-api.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";
import { pierre, markSyntax } from "./pierre.js";

// A Markdown preview of text written in the page, whose rendering sets the box both
// tabs share (text-document.css).
const WRITTEN = '[preview="markdown"]:not([source], [for])';

// Writing the same key again would still be a mutation the page's observers see.
/** @param {HTMLElement} node @param {string} key */
const mark = (node, key) => {
  if (node.dataset.lfDatum !== key) node.dataset.lfDatum = key;
};

/** @param {string} source @param {string | null} language */
async function sourceListing(source, language) {
  const [{ preloadFile }, { themeName, foreground }] = await Promise.all([
    pierre(),
    ensureSyntaxLanguage(language),
  ]);
  const { prerenderedHTML } = await preloadFile({
    file: { name: "source", contents: source, lang: language ?? "text" },
    options: { theme: themeName, disableFileHeader: true, overflow: "wrap" },
  });
  const template = document.createElement("template");
  template.innerHTML = prerenderedHTML;
  const rendered = template.content;
  rendered.querySelector("svg[data-icon-sprite]")?.remove();
  for (const style of rendered.querySelectorAll("style")) {
    // A style's implicit @scope root is its parent listing. Pierre's :host rules
    // describe that file box here, without adding a second shadow-tree owner.
    style.textContent = inBaseLayer(
      `@scope { ${style.textContent.replaceAll(":host", ":scope")} }`,
    );
  }
  // A line number is Leaf's control, drawn from `data-number`; dropping Pierre's
  // attribute keeps its sheet's rule for that span (a positioned, stacked
  // inline-block) off it.
  for (const number of rendered.querySelectorAll("span[data-line-number-content]")) {
    number.removeAttribute("data-line-number-content");
    number.setAttribute("data-number", number.textContent);
    number.textContent = "";
    number.classList.add("lf-ui");
    generatedElement(number, { says: false });
    number.setAttribute("aria-hidden", "true");
  }
  // Pierre uses block rows without source newlines. Retain the exact input in the
  // DOM as well as its drawing, including its final newline (or absence of one).
  const lines = [...rendered.querySelectorAll("[data-content] [data-line]")];
  const text = source.split(/\r\n|\r|\n/);
  const endings = source.match(/\r\n|\r|\n/g) ?? [];
  lines.forEach((line, index) => {
    // Some grammars represent an empty row with a newline placeholder.
    if (text[index] === "" && line.textContent === "\n") line.replaceChildren();
    const ending = endings[index];
    if (ending !== undefined) line.append(ending);
  });
  const code = rendered.querySelector("code");
  const pre = rendered.querySelector("pre");
  if (!code || !pre) throw new Error("Pierre did not return a listing");
  inRuns(code);
  if (code.textContent !== source)
    throw new Error("Pierre did not return the source unchanged");
  markSyntax(rendered, foreground);
  return { rendered, pre, code, text };
}

// Rows per run: several times the lines a document's box shows, so the runs in view
// are cheap to draw, and a megabyte of text makes about 150 runs.
const RUN = 128;

// Pierre draws the numbers and the lines as two columns, each a subgrid spanning every
// row. This regroups them into runs of rows, each a grid of the two columns that the
// browser skips while it is out of view (`content-visibility: auto`). The browser
// styles and lays out a skipped run only when it comes into view, a search lands in
// it, or a script measures it, and its text stays in the DOM for find-in-page,
// selection, copy and comments. When every row was styled on each change to the page,
// a few megabytes of text took tens of seconds and gigabytes of memory to draw. A lone
// run stays drawn (text-document.css): skipping it buys nothing, and its rows would
// stand undrawn for the frames after the document scrolls into view.
/** @param {Element} code */
function inRuns(code) {
  const [gutter, content] = /** @type {[Element, Element]} */ ([...code.children]);
  const numbers = [...gutter.children];
  const lines = [...content.children];
  /** @param {Element} column @param {Element[]} cells @param {number} first @param {number} rows */
  const part = (column, cells, first, rows) => {
    const box = /** @type {HTMLElement} */ (column.cloneNode(false));
    box.style.gridRow = `span ${rows}`;
    box.append(...cells.slice(first, first + rows));
    return box;
  };
  const runs = [];
  for (let first = 0; first < lines.length; first += RUN) {
    const rows = Math.min(RUN, lines.length - first);
    const run = document.createElement("div");
    run.className = "lf-text-document-run";
    // A line a row until the drawn listing says how long a line is (`sizeRuns`).
    run.style.containIntrinsicBlockSize = `auto ${rows}lh`;
    run.append(part(gutter, numbers, first, rows), part(content, lines, first, rows));
    runs.push(run);
  }
  code.replaceChildren(...runs);
}

// Which line of `before` each line of `after` stands for, or -1 for a line it adds,
// from a walk over whole lines capped as the runtime's text alignment is; null where a
// rewrite runs past the cap. A run of lines replaced by as many others stands for them
// one for one, so an edited line keeps the row of the line it replaced. Exported for
// its test.
/** @param {readonly string[]} before @param {readonly string[]} after @param {number} [maxEditLength] @returns {number[] | null} */
export function keptLines(before, after, maxEditLength = 1_000) {
  const changes = diffArrays([...before], [...after], { maxEditLength });
  if (!changes) return null;
  const kept = after.map(() => -1);
  let from = 0;
  let to = 0;
  // jsdiff puts a removed run before the added run that replaces it.
  let removed = 0;
  for (const { count = 0, added, removed: gone } of changes) {
    if (gone) {
      removed = count;
      from += count;
      continue;
    }
    if (added) {
      if (count === removed)
        for (let line = 0; line < count; line++) kept[to + line] = from - count + line;
      to += count;
    } else for (const end = to + count; to < end;) kept[to++] = from++;
    removed = 0;
  }
  return kept;
}

// Reconciles a new text's runs (`drawn`) into the runs on the page (`code`), as a
// drawing boundary rather than a row's identity: each row the new text keeps first
// moves into the run the new text puts it in (`setChildLists`, which keeps a selection
// in it), and each run then reconciles its rows (`setRenderedChildren`), finding its
// kept rows in place. An edited line keeps the row of the line it replaced, so its
// text is patched in place. A run's numbers stay with it, since they count its places
// rather than its rows. Reconciled run by run alone, a row that lines added above it
// carried across a run's edge was drawn anew, and a selection in it was lost, or grew
// to take in the row before it. Where a rewrite runs past the line walk's cap
// (`keptLines`), nothing moves and each run reconciles its own rows: walked to the end,
// every line of 4 MB rewritten took 285 s.
/** @param {Element} code @param {Element} drawn @param {readonly string[]} before @param {readonly string[]} after */
function reconcileRuns(code, drawn, before, after) {
  const held = [...code.children];
  const kept = keptLines(before, after);
  const fresh = [...drawn.children];
  const runs = fresh.map((run, at) => {
    const live = held[at];
    if (live) return live;
    const shell = /** @type {Element} */ (run.cloneNode(false));
    shell.append(...[...run.children].map((part) => part.cloneNode(false)));
    code.append(shell);
    return shell;
  });
  if (kept) {
    const lines = held.flatMap((run) => [...(run.lastElementChild?.children ?? [])]);
    let line = 0;
    /** @type {[Element, Element[]][]} */
    const lists = [];
    runs.forEach((run, at) => {
      const rows = kept
        .slice(line, (line += fresh[at]?.lastElementChild?.childElementCount ?? 0))
        .filter((row) => row >= 0);
      if (run.lastElementChild)
        lists.push([run.lastElementChild, rows.flatMap((row) => lines[row] ?? [])]);
    });
    setChildLists(lists);
  }
  runs.forEach((run, at) => setRenderedChildren(run, fresh[at]?.childNodes ?? []));
  setChildren(code, runs);
}

// How many characters a line of the listing holds, and a tab's width in them: a row's
// text box over the average advance of the first run's one-line rows, as drawn. The
// face drawn need not be the one named: a freshly started Firefox sets the listing in a
// proportional fallback until its font list loads, seconds later. Null while the rows
// have no box, as in a hidden tab.
/** @param {Element} code */
function lineColumns(code) {
  const rows = [...(code.firstElementChild?.lastElementChild?.children ?? [])];
  const first = rows[0];
  if (!(first instanceof HTMLElement) || !first.clientWidth) return null;
  const style = getComputedStyle(first);
  const line = parseFloat(style.lineHeight);
  const range = document.createRange();
  let width = 0;
  let characters = 0;
  for (const row of rows) {
    const text = row.textContent?.replace(/\r?\n$/, "") ?? "";
    if (text.length < 8 || text.includes("\t")) continue;
    if (row.getBoundingClientRect().height > line * 1.5) continue;
    range.selectNodeContents(row);
    width += range.getBoundingClientRect().width;
    characters += text.length;
    if (characters > 1000) break;
  }
  const face = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  const advance = characters ? width / characters : textWidth("0", face);
  const room =
    first.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
  return {
    columns: Math.max(1, Math.floor(room / advance)),
    tab: parseFloat(style.tabSize) || 8,
  };
}

// The lines a row takes in a line of `columns` characters, broken as `pre-wrap` breaks
// it: after a space, where the spaces past a line's end hang, and within a word longer
// than a line. A tab counts `tab` characters.
/** @param {string} row @param {number} columns @param {number} tab */
function rowLines(row, columns, tab) {
  if (row.length <= columns && !row.includes("\t")) return 1;
  let lines = 1;
  let used = 0;
  for (const piece of row.replaceAll("\t", " ".repeat(tab)).split(/(?<= )(?=[^ ])/)) {
    const word = piece.trimEnd().length;
    if (used && used + word > columns) {
      lines++;
      used = 0;
    }
    if (word > columns) {
      lines += Math.ceil(word / columns) - 1;
      used = word % columns || columns;
      used += piece.length - word;
    } else used += piece.length;
  }
  return lines;
}

// The height the browser gives each run until it draws it, in lines (`rowLines`). That
// is exact for a monospaced face and close for any other. A run the browser has drawn
// keeps its drawn height (`auto`). Estimated a line a row, wrapped text was thousands
// of pixels short, and End, a drag to the bottom and travel to a line each stopped
// short as the runs they passed took their real heights.
//
// A skipped run keeps the height it was last drawn at, whatever its size says, until
// its style resolves with neither `auto` nor `content-visibility: auto`. Chromium,
// Firefox and WebKit all do so, though css-sizing-4 says otherwise
// (notes/browser-support.md). Narrowed after its last runs were drawn, a long text
// left End 240 to 1,834 px short. So when the line length changes, each run the
// browser has `drawn` that is skipped now resolves its style once as `hidden` without
// `auto`, and takes both back before anything is drawn. Only those runs: the
// resolution cost Firefox about 60 ms on 4 MB, and 426 ms over every resized run.
/** @param {Element} code @param {readonly string[]} text @param {{columns: number, tab: number}} length @param {WeakSet<Element>} [drawn] the runs drawn since they last forgot a height */
function sizeRuns(code, text, { columns, tab }, drawn) {
  /** @type {[HTMLElement, number][]} */
  const resized = [];
  let line = 0;
  for (const run of code.children) {
    if (!(run instanceof HTMLElement)) continue;
    let lines = 0;
    for (
      const end = line + (run.lastElementChild?.childElementCount ?? 0);
      line < end;
      line++
    )
      lines += rowLines(text[line] ?? "", columns, tab);
    if (run.style.containIntrinsicBlockSize !== `auto ${lines}lh`)
      resized.push([run, lines]);
  }
  const forgetting = resized.filter(
    ([run]) =>
      drawn?.has(run) &&
      run.lastElementChild?.firstElementChild?.checkVisibility({
        contentVisibilityAuto: true,
      }) === false,
  );
  for (const [run, lines] of forgetting) {
    drawn?.delete(run);
    run.style.contentVisibility = "hidden";
    run.style.containIntrinsicBlockSize = `${lines}lh`;
  }
  for (const [run] of forgetting) getComputedStyle(run).contentVisibility;
  for (const [run] of forgetting) run.style.removeProperty("content-visibility");
  for (const [run, lines] of resized)
    run.style.containIntrinsicBlockSize = `auto ${lines}lh`;
}

class TextDocument extends LeafElement {
  rendering = 0;
  /** @type {(() => void) | null} */
  finishFrame = null;
  /** @type {Promise<void> | undefined} */
  frameLoaded;
  /** @type {ReturnType<TextDocument["build"]> | undefined} */
  view;
  /** @type {{pre: HTMLPreElement, code: HTMLElement} | null} */
  sourceView = null;
  /** @type {readonly string[]} */
  text = [];
  /** @type {{columns: number, tab: number} | null} */
  lineLength = null;
  // A new width gives the listing's lines another length, and its runs another height.
  // So can a new face, which shows where a drawn run changes height. The runs are
  // sized again in the next frame, outside the observer's delivery: sized in it when
  // Firefox's face arrived, they resized the code it watches, and Firefox reported the
  // notification it couldn't deliver as an error.
  sizes = sizeObserver(() =>
    nextFrame(() => {
      this.refit();
      this.holdSource();
      this.measureCut();
    }),
  );
  // A written preview's Source tab, which shows what the preview's height holds, and
  // the press that shows the rest where that height cuts the source.
  /** @type {{panel: HTMLElement, box: HTMLElement, press: HTMLButtonElement} | null} */
  cut = null;
  // The Source tab takes the preview's height, so switching to it moves nothing below
  // the document. A closed tab skips its contents' layout (`hidden="until-found"`), so
  // the height is read while the preview shows, after each of its resizes. A document
  // drawn on Source, as after a reload, never showed its preview; it keeps the box the
  // page first painted (`firstBox`), which holds the preview's rendering (`x-prepaint`).
  // Either reaches the Source tab before the frame paints.
  /** @param {number | null} [firstBox] */
  holdSource(firstBox = null) {
    const preview = this.view?.preview;
    const tab = preview?.parentElement;
    if (!this.cut || !preview || !tab) return;
    const { panel } = this.cut;
    let measured;
    if (!tab.hidden) measured = preview.getBoundingClientRect().height;
    else if (firstBox !== null)
      measured =
        panel.getBoundingClientRect().height +
        firstBox -
        this.getBoundingClientRect().height;
    else return;
    const height = layoutPx(measured);
    const { style } = panel;
    if (style.getPropertyValue("--lf-preview-block") !== height)
      style.setProperty("--lf-preview-block", height);
  }
  // The press shows only while the box cuts lines off, as a thread's Full quote does.
  measureCut() {
    if (!this.cut) return;
    const { panel, box } = this.cut;
    keepsHidden(
      box,
      panel.hidden ||
        panel.hasAttribute("data-lf-all") ||
        panel.scrollHeight <= panel.clientHeight + 1,
    );
  }
  // The runs the browser has drawn since they last forgot a height (`sizeRuns`).
  drawn = new WeakSet();
  // Size the drawn runs again where the listing's line length changed.
  refit() {
    const code = this.sourceView?.code;
    const length = code && lineColumns(code);
    const last = this.lineLength;
    if (!length || (length.columns === last?.columns && length.tab === last.tab))
      return;
    this.lineLength = length;
    sizeRuns(code, this.text, length, this.drawn);
  }

  setup() {
    // A departure abandons the rendering in flight and its frame's wait.
    whileConnected(this, () => () => {
      this.rendering = this.rendering + 1;
      this.finishFrame?.();
    });
  }

  // The text, set by whoever hosts the widget: Leaf from the bound source or output
  // (the registry's `x-data.document.property`), or from the written `<pre>`; null
  // while a bound source has none.
  static properties = { value: { attribute: false } };

  constructor() {
    super();
    this.addEventListener(
      "contentvisibilityautostatechange",
      (event) => {
        const { skipped, target } =
          /** @type {ContentVisibilityAutoStateChangeEvent} */ (event);
        if (!skipped && target instanceof Element) this.drawn.add(target);
      },
      { capture: true },
    );
    /** @type {string | null} */
    this.value = null;
  }

  render() {
    return nothing;
  }

  // Highlighting and the preview load after the draw; `updateComplete` waits for
  // them, as a Lit element's completion does for work its update starts.
  /** @param {import("lit").PropertyValues} changed */
  updated(changed) {
    super.updated(changed);
    this.showing = this.show(this.value);
  }

  // Also waits for the drawing the latest update started: a newer update's drawing
  // replaces one still pending.
  async getUpdateComplete() {
    const result = await super.getUpdateComplete();
    await this.showing;
    return result;
  }

  /** @param {string | null} value */
  async show(value) {
    const rendering = this.rendering + 1;
    this.rendering = rendering;
    const source = value ?? "";
    const preview = this.getAttribute("preview");
    try {
      if (preview) await import("./lf-tabs.js");
      const language = this.getAttribute("language") ?? preview;
      const {
        rendered: listing,
        pre: drawnPre,
        code: drawnCode,
        text,
      } = await sourceListing(source, language);
      if (preview === "markdown") {
        let failure;
        if (!(await loadMarkdown((error) => (failure = error)))) throw failure;
      }
      if (rendering !== this.rendering || !this.isConnected) return;
      const view = (this.view ??= this.build(preview));
      const label =
        this.getAttribute("label") ??
        this.getAttribute("source") ??
        this.getAttribute("for");
      keepsText(view.caption, value == null ? `${label} · no data` : label);
      const previous = this.text;
      this.text = text;
      if (this.cut) keepsText(this.cut.press, `Show all ${text.length} lines`);
      if (!this.sourceView) {
        setChildren(view.listing, [...listing.childNodes]);
        this.sourceView = { pre: drawnPre, code: drawnCode };
        this.sizes.observe(view.listing);
        this.sizes.observe(drawnCode);
        if (this.cut && view.preview) {
          this.sizes.observe(this.cut.panel);
          this.sizes.observe(view.preview);
        }
      } else {
        // The pre owns provenance and scroll; the code owns its native reach stop.
        // Reconcile only their source children, leaving those independent owners
        // in place while unchanged lines keep their text nodes and selection.
        reconcileRuns(this.sourceView.code, drawnCode, previous, text);
        if (this.lineLength)
          sizeRuns(this.sourceView.code, text, this.lineLength, this.drawn);
        const width = "--diffs-min-number-column-width-default";
        const drawnWidth = drawnPre.style.getPropertyValue(width);
        if (this.sourceView.pre.style.getPropertyValue(width) !== drawnWidth)
          this.sourceView.pre.style.setProperty(width, drawnWidth);
      }
      let loaded = this.frameLoaded;
      const previewNode = view.preview;
      if (previewNode instanceof HTMLDivElement) {
        const template = document.createElement("template");
        template.innerHTML = renderMarkdown(source, false);
        setRenderedChildren(previewNode, template.content.childNodes);
      } else if (
        previewNode instanceof HTMLIFrameElement &&
        (!previewNode.isConnected ||
          !previewNode.hasAttribute("srcdoc") ||
          previewNode.srcdoc !== source)
      ) {
        this.finishFrame?.();
        loaded = this.frameLoaded = new Promise((resolve) => {
          const finish = () => {
            previewNode.removeEventListener("load", finish);
            if (this.finishFrame === finish) this.finishFrame = null;
            resolve(undefined);
          };
          this.finishFrame = finish;
          previewNode.addEventListener("load", finish);
        });
        if (!previewNode.hasAttribute("srcdoc") || previewNode.srcdoc !== source)
          previewNode.srcdoc = source;
      }
      const firstBox =
        this.cut && !view.figure.isConnected
          ? this.getBoundingClientRect().height
          : null;
      setChildren(this, [view.figure]);
      this.refit();
      // The drawn text's items, marked for whoever hosts the widget: on a Leaf page,
      // comments on them anchor to the document's data.
      if (previewNode) {
        mark(this.sourceView.pre, "source");
        mark(previewNode, "preview");
      } else mark(view.figure, "document");
      this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      if (loaded) await loaded;
      if (rendering !== this.rendering || !this.isConnected) return;
      this.classList.toggle("lf-rendered", true);
      // Measured once drawn, since until then the host wears the source face
      // (reading.css).
      this.holdSource(firstBox);
    } catch (error) {
      if (rendering !== this.rendering || !this.isConnected) return;
      failSoft(this, error, source);
    }
  }

  /** @param {string | null} preview
   * @returns {{figure: HTMLElement, caption: HTMLElement, listing: HTMLDivElement, preview: HTMLElement | null}} */
  build(preview) {
    const figure = document.createElement("figure");
    figure.className = "lf-text-document-view";
    const caption = document.createElement("figcaption");
    const listing = document.createElement("div");
    listing.className = "lf-text-document-listing scroll";
    figure.append(caption);
    if (!preview) {
      figure.append(listing);
      return { figure, caption, listing, preview: null };
    }
    const tabs = document.createElement("lf-tabs");
    tabs.id = `${this.id}--views`;
    // Its members are this document's data readings, not authored page content.
    generatedElement(tabs, { says: false });
    const bound = this.getAttribute("data-lf-bound") ?? "start";
    const rendered = document.createElement("lf-tab");
    rendered.id = `${this.id}--preview`;
    rendered.setAttribute("label", "Preview");
    rendered.setAttribute("data-lf-bound", bound);
    const literal = document.createElement("lf-tab");
    literal.id = `${this.id}--source`;
    literal.setAttribute("label", "Source");
    literal.setAttribute("data-lf-bound", bound);
    const drawn =
      preview === "html"
        ? document.createElement("iframe")
        : document.createElement("div");
    drawn.className = "lf-text-document-preview";
    if (drawn instanceof HTMLIFrameElement) {
      drawn.title = `${this.getAttribute("label") ?? this.getAttribute("source") ?? this.getAttribute("for")} preview`;
      drawn.setAttribute("sandbox", "allow-scripts");
    }
    rendered.append(drawn);
    literal.append(listing);
    if (this.matches(WRITTEN)) {
      const box = offer("div", "lf-text-document-cut");
      box.hidden = true;
      const press = offerAction("inline", "lf-text-document-more", "");
      // The press goes once it has shown the lines, so focus moves to the listing.
      press.addEventListener("click", () => {
        literal.toggleAttribute("data-lf-all", true);
        keepsHidden(box, true);
        if (this.sourceView) focusDestination(this.sourceView.pre, "return");
      });
      box.append(press);
      literal.append(box);
      this.cut = { panel: literal, box, press };
    }
    tabs.append(rendered, literal);
    figure.append(tabs);
    return { figure, caption, listing, preview: drawn };
  }
}
customElements.define("lf-text-document", TextDocument);
