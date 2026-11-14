/* What a place on the page shows as a preview (preview.js), so a link into the page
   says where it points before a press takes the reader there (browser/AGENTS.md,
   "Pointing reads; pressing acts").

   A link into the page is one an author wrote, in the page or in a message's markup,
   whose fragment names a place of the page (`fragmentTarget`): an element by its id,
   or the part of a widget its key names. A link Leaf or a widget draws, such as a
   contents row or a heading's own link, is its drawer's to preview (`lfPreview`), since
   only it knows whether its words already say what the place holds; a contents row
   does. A link to another document keeps only the browser's status bar.

   The preview is a short rendering of the place, in the face's excerpt room:

   - its name, the way the authoring contract names an element (addressable-names.js,
     `ownNaming`): a heading's words, a section's leading heading, a tab's label, a
     table's or figure's caption, an `aria-label`; and for a place with no name of its
     own, or one the page draws nothing of, the name of the part it stands in, by the
     rule On Me groups its items by (thread/placement.js, `partOver`): the heading over
     it, or the nearest element holding it that the contract names;
   - its first few parts, in the page's order, each as the page draws it now and each a
     line of detail the face fits to its room (preview.js, `fit`): a heading, a
     paragraph's words, a list's first items, a table's first rows, a figure's picture
     and caption, and a code block's first lines. A heading's
     parts are those of the part it heads itself: what follows it in its container, up to
     the next heading of its document's outline, however deep in a block that stands.
     Anything drawn before the name, such as an eyebrow, anything Leaf draws inside the
     place, and anything in it the page draws nothing of, are left out;
   - a widget's current state, from the reading the page already holds: where it asks
     the user something, its obligation's answer in the words a Done row says it in, or
     that it waits on the user, and an answered question shows its answer in place of
     its options; elsewhere, its options with each one its answer picks checked, as
     the widget reads its own state, so a question authored settled marks its pick;
   - the open conversations about the place or anything in it, a heading's about the
     part it heads, and whether one is the user's turn, as a margin entry says it.

   It is made of the place's words, never its nodes: a copy would repeat ids, upgrade
   widgets and carry controls, and the preview holds no control. Every word it shows,
   a name's, a part's or a code block's, is read by one reader: the page's reading of
   the element (`says`), so Leaf's own controls in it say nothing, keeping only what the
   browser computes as drawn now, word by word as the walk meets it (passages.js,
   `drawsWithin`), so `display: none`, `hidden`, `visibility: hidden`, a script, a
   closed disclosure's body and what `content-visibility: hidden` skips, such as a tab
   not chosen, say nothing, while a drawn word inside a hidden element still shows. A
   place the page draws none of what it holds, as a tab not chosen or anything in it,
   reads whole, as the platform's own `innerText` reads an element it does not render.

   A heading's section is walked from the heading out to the part it heads, each run of
   siblings, a slot's assignment included, enumerated once in the page's reading order
   (passages.js, `readingParent`, `readingChildren`), and no further than the parts the
   preview shows, so its work follows the excerpt, not the section or the page (root
   AGENTS.md, "Responsiveness"). Which heading heads what is one reading, the
   document's outline (thread/placement.js): `partOver` names a place, `headingAfter`
   ends a heading's excerpt, and the conversations under each element and heading are
   gathered from it once for each reading of the threads and the page
   (`conversationsAbout`), so a preview looks them up. Obligations come from the index
   the publisher keeps by an obligation's id.

   Decisions: a table shows its first rows in its own columns, cut to one line a cell,
   since a row's cells read apart are a table's point; a figure shows its picture, the
   part a reader recognises it by; a chart, a diagram or anything else a widget draws
   shows only its name and words, since copying its drawing would carry its controls.
   Rejected: a clone of the place made inert, which repeats every id it holds and
   upgrades every widget in it. */
import { html, nothing } from "/runtime/framework.js";
import { fragmentTarget } from "./anchor-resolution.js";
import { addressableWord, leadingTitle, ownNaming } from "./addressable-names.js";
import { TEXT_BLOCK } from "./kernel-facts.js";
import { obligationEnding } from "./obligations/answer.js";
import { readObligations } from "./obligations/model.js";
import { hasObligationSource } from "./obligations/source.js";
import {
  authoredScope,
  drawsWithin,
  excerpt,
  GENERATED,
  headed,
  HEADING,
  inPage,
  LEAF_SURFACE,
  pageDocument,
  readingChildren,
  readingParent,
  readingUnder,
} from "./passages.js";
import { declarationFor, registry } from "./registry.js";
import { readPart } from "./semantic-state.js";
import { overIn } from "./shadow.js";
import { conversationsAbout, headingAfter, partOver } from "./thread/placement.js";
import { leafSays, voiced } from "./voice.js";
import { capitalized, counted, excerptWords, labelWords } from "./words.js";

/** @typedef {import("./voice.js").Words} Words
 * @typedef {{kind: "heading" | "text", words: string}
 *   | {kind: "list", items: {words: string, chosen: boolean}[], more: string | null}
 *   | {kind: "table", rows: {words: string, head: boolean}[][], more: string | null}
 *   | {kind: "figure", src: string, caption: string}
 *   | {kind: "code", lines: string}
 *   | {kind: "state", words: Words}} Part */

// How much of a place a preview shows: its name's words, parts after its name, a
// paragraph's words, a list's items, a table's rows and columns, a code block's lines.
// The face cuts what its room doesn't hold.
const NAME = 120;
const PARTS = 2;
const WORDS = 280;
const ITEMS = 3;
const ROWS = 3;
const COLUMNS = 4;
const LINES = 4;
// The most of an element's words a preview reads, other than whitespace: enough for each
// cut above, with a title read before a part's words; and of a code block's, its lines,
// each up to far longer than a card shows of one. So pointing at a link to a long log or
// a deep outline costs what the preview shows.
const READ = 2 * WORDS;
const CODE = LINES * 1000;

// What Leaf draws in a place, which is no part of what its author put there.
const LEAF_DRAWN = `${GENERATED}, ${LEAF_SURFACE}`;
const LIST = "ul, ol, menu, dl";
// How the preview being read reads, set as it starts, and read by nothing after it
// ends: `whole` where the page draws none of what the place holds, which then reads
// whole, as the platform's `innerText` reads an element it does not render; `stop`, the
// heading that ends a heading's excerpt (`headingAfter`), null for any other place; and
// `ended` once the reading has met it.
/** @type {{whole: boolean, stop: Element | null, ended: boolean}} */
let reading = { whole: false, stop: null, ended: false };
/** @param {readonly Part[]} parts */
const full = (parts) => reading.ended || parts.length >= PARTS;
// The words an element shows, as the page draws them now, up to the heading that ends
// the excerpt (passages.js, `says`): the one reader of every word the preview says.
// `whole` reads them drawn or not, as a widget's members are named (`membersPart`).
// Each reading reads no more than the preview shows (passages.js, `excerpt`), and words
// cut short end in an ellipsis.
/** @param {Element} element @param {"prose" | "lines"} [format] @param {boolean} [whole]
 * @param {{upTo?: number, lines?: number}} [bound] */
const said = (
  element,
  format = "prose",
  whole = reading.whole,
  bound = { upTo: READ },
) => excerpt(element, { format, drawn: !whole, until: reading.stop, ...bound });
/** @param {Element} element @param {boolean} [whole] */
const words = (element, whole = reading.whole) => {
  const { text, cut } = said(element, "prose", whole);
  const shown = labelWords(text);
  return cut && shown ? `${shown}…` : shown;
};
// Whether the page draws what `element` holds, for a part with no words of its own to
// ask, as a list's item counted or a row of a table.
/** @param {Element} element */
const draws = (element) => reading.whole || drawsWithin(element, false);

/** The place a link into the page names, or null for any other link.
 * @param {Element} link */
export function linkedPlace(link) {
  if (!link.matches('a[href^="#"]')) return null;
  const scope = authoredScope(link);
  const authored =
    (scope !== pageDocument() || inPage(link)) && !overIn(link, GENERATED, scope);
  return authored ? fragmentTarget(link.getAttribute("href")) : null;
}

/** What a link into the page previews: the place it names (`placePreview`).
 * @param {Element} link */
export function linkPreview(link) {
  const place = linkedPlace(link);
  return place ? placePreview(place) : null;
}

/** A place on the page as a preview shows it (preview.js, `Preview`): its name, then
 * each of its parts and the conversations about it as a line of detail, so a face held to
 * a short room keeps the parts that fit whole and cuts the one the room ends in
 * (preview.js, `fit`), in the face's excerpt room, about the place itself, so where the
 * page shows the place, the card stands clear of it rather than over what it previews.
 * @param {Element} place */
export function placePreview(place) {
  const heading = place.matches(HEADING);
  reading = {
    whole: !drawsWithin(place, false),
    stop: heading ? headingAfter(place) : null,
    ended: false,
  };
  const title = heading ? null : leadingTitle(place);
  const name = heading ? words(place) : placeName(place);
  // A caption or a lone heading that names the place says nothing again below it.
  const parts = (heading ? sectionParts(place) : partsOf(place, title))
    .filter((part) => !("words" in part) || part.words !== name)
    .map((part) =>
      part.kind === "figure" && part.caption === name ? { ...part, caption: "" } : part,
    );
  const foot = conversations(place);
  if (!name && !parts.length && !foot) return null;
  return {
    name: name ? excerptWords(name, NAME) : null,
    detail: [...parts.map(partView), foot],
    about: place,
    excerpt: true,
  };
}

// A place with no name of its own takes the name of the part it stands in (`partOver`):
// the heading over it, or the nearest element holding it that the contract names, as
// a question's options take the question's and a paragraph under a sub-heading the
// sub-heading's. Its parts then say its words. A widget in no named part takes its
// word. A name an element gives is read as the page draws it, as the parts are, so a
// name the page draws nothing of, as a title hidden away, gives way to the next.
/** @param {Element} place */
function placeName(place) {
  return (
    namedBy(ownNaming(place)) ||
    partName(partOver(place)) ||
    (registry[place.localName] ? capitalized(addressableWord(place)) : "")
  );
}
/** @param {Element | null} part */
const partName = (part) =>
  !part ? "" : part.matches(HEADING) ? words(part) : namedBy(ownNaming(part));

// A name's words, read as the page draws them where an element gives them.
/** @param {import("./addressable-names.js").Naming | null} naming @param {boolean} [whole] */
const namedBy = (naming, whole = reading.whole) =>
  !naming ? "" : "words" in naming ? naming.words : words(naming.by, whole);

// The blocks after a heading in the page's reading, from the heading out to the part it
// heads (passages.js, `headed`), as the reader asks for them: the next heading of the
// outline ends the reading (`read`), and the reader stops asking once it holds what the
// preview shows.
/** @param {Element} heading @returns {Generator<Element>} */
function* sectionOf(heading) {
  const container = headed(heading);
  for (
    let at = /** @type {Node | null} */ (heading);
    at && at !== container;
    at = readingParent(at)
  )
    yield* after(at);
}
// The elements after `node` in the page's reading, its run of siblings enumerated once:
// a slot's assignment, or the elements after it in its tree.
/** @param {Node} node @returns {Generator<Element>} */
function* after(node) {
  if (!(node instanceof Element)) return;
  const holder = readingParent(node);
  if (holder instanceof Element && holder.localName === "slot") {
    const run = readingChildren(holder);
    for (let at = run.indexOf(node) + 1; at < run.length; at += 1) {
      const next = run[at];
      if (next) yield next;
    }
  } else
    for (let next = node.nextElementSibling; next; next = next.nextElementSibling)
      yield next;
}

// The parts of the blocks a heading heads.
/** @param {Element} heading */
function sectionParts(heading) {
  /** @type {Part[]} */
  const parts = [];
  for (const block of sectionOf(heading)) {
    if (full(parts)) break;
    read(block, parts, null);
  }
  return parts;
}

/** @param {Element} place @param {Element | null} title */
function partsOf(place, title) {
  /** @type {Part[]} */
  const parts = [];
  read(place, parts, title);
  return parts;
}

// Read `element` into `parts`, until they hold what the preview shows. A title, and
// what stands before it, has been said by the name; `title` is null once it has passed.
/** @param {Element} element @param {Part[]} parts @param {Element | null} title
 * @returns {Element | null} the title still to come, or null once it has passed */
function read(element, parts, title) {
  if (element === reading.stop) reading.ended = true;
  if (reading.ended || element === title) return null;
  if (element.matches(LEAF_DRAWN) || (title && !readingUnder(title, element)))
    return title;
  // A question the user has answered shows its answer in place of its options; one
  // still open shows its options and then whose turn it is.
  const asks = question(element);
  if (!asks?.settled) {
    if (!title) drawn(element, parts);
    // Words standing beside a title of their own, as a titled item's do, follow it.
    else if (element.matches(TEXT_BLOCK) || holdsText(element)) {
      const all = words(element);
      const named = words(title);
      const at = all.indexOf(named);
      part(parts, "text", at < 0 ? all : all.slice(at + named.length).trim());
    } else readChildren(element, parts, title);
  }
  if (asks) parts.push({ kind: "state", words: asks.words });
  return null;
}

// The part `element` makes as the page draws it, or its children's parts.
/** @param {Element} element @param {Part[]} parts */
function drawn(element, parts) {
  // A block holding the heading that ends the excerpt says what stands before it there.
  const holdsStop = reading.stop !== null && readingUnder(reading.stop, element);
  const textual = element.matches(TEXT_BLOCK) || holdsText(element);
  if (element.matches(HEADING)) part(parts, "heading", words(element));
  else if (holdsStop && !textual) readChildren(element, parts, null);
  else if (element.matches(LIST)) listPart(element, parts);
  else if (element.localName === "table") tablePart(element, parts);
  else if (element.localName === "figure" || element.localName === "img")
    figurePart(element, parts);
  else if (element.localName === "pre") {
    // Its first lines, and where the block runs on, the ellipsis cut prose ends in
    // (words.js, `excerptWords`).
    const { text, cut } = said(element, "lines", reading.whole, {
      lines: LINES,
      upTo: CODE,
    });
    const lines = text.trimEnd();
    if (lines.trim()) parts.push({ kind: "code", lines: cut ? `${lines}…` : lines });
  } else if (textual) {
    part(parts, "text", words(element));
    if (holdsStop) reading.ended = true;
  } else if (!membersPart(element, parts)) readChildren(element, parts, null);
}

/** @param {Element} element @param {Part[]} parts @param {Element | null} title */
function readChildren(element, parts, title) {
  let still = title;
  for (const child of readingChildren(element)) {
    if (full(parts)) break;
    still = read(child, parts, still);
  }
  return still;
}

/** @param {Part[]} parts @param {"heading" | "text"} kind @param {string} text */
function part(parts, kind, text) {
  if (text) parts.push({ kind, words: excerptWords(text, WORDS) });
}

// Words standing in an element of their own, as an option's do, make it a block of text.
/** @param {Element} element */
const holdsText = (element) =>
  [...element.childNodes].some(
    (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
  );

/** @param {Element} list @param {Part[]} parts */
function listPart(list, parts) {
  const items = [...list.children].filter(
    (item) => item.matches(list.localName === "dl" ? "dt" : "li") && draws(item),
  );
  /** @type {{words: string, chosen: boolean}[]} */
  const shown = [];
  for (const item of items) {
    if (shown.length >= ITEMS) break;
    const said =
      item.localName === "dt" ? termWords(item) : excerptWords(words(item), WORDS);
    if (said) shown.push({ words: said, chosen: false });
  }
  listed(parts, shown, items.length);
}

// A run of like members, as a question's options, a board's columns or a set of tabs
// are, reads as a list of their names, the first few and every one the widget's answer
// picks, marked as picked.
/** @param {Element} element @param {Part[]} parts */
function membersPart(element, parts) {
  // Each member is named, shown or not, as a set of tabs names each of its panels and
  // a settled question its folded options.
  const members = readingChildren(element).filter(
    (member) => !member.matches(LEAF_DRAWN),
  );
  const [first] = members;
  if (
    !first ||
    members.length < 2 ||
    !registry[first.localName] ||
    members.some((member) => member.localName !== first.localName)
  )
    return false;
  const chosen = picked(element);
  const kept = new Set(members.filter((member) => chosen.has(member.id)));
  for (const member of members) {
    if (kept.size >= ITEMS) break;
    kept.add(member);
  }
  const shown = members
    .filter((member) => kept.has(member))
    .map((member) => ({
      words: excerptWords(
        namedBy(ownNaming(member), true) || words(member, true),
        WORDS,
      ),
      chosen: chosen.has(member.id),
    }));
  listed(parts, shown, members.length);
  return true;
}

const widgetStates = readPart((root) => root.effective.widgets);
// The members a widget's answer picks, as the widget reads its own state: the value of
// its `x-awaits` verb where that verb records a pick on the members it names (`x-state`),
// folded from the authored initial values and every action in force since, so a group
// authored settled with its pick `chosen` marks that pick as the widget does.
/** @param {Element} widget @returns {ReadonlySet<unknown>} */
function picked(widget) {
  const verb = declarationFor(widget, "x-awaits")?.value;
  const record = verb ? declarationFor(widget, "x-state")?.[verb]?.record : null;
  const value =
    verb && record?.kind === "attribute"
      ? widgetStates().get(widget.id)?.state[verb]?.value
      : null;
  return new Set(Array.isArray(value) ? value : []);
}

/** @param {Part[]} parts @param {{words: string, chosen: boolean}[]} items @param {number} of */
function listed(parts, items, of) {
  if (items.length)
    parts.push({
      kind: "list",
      items,
      more: of > items.length ? `${of - items.length} more` : null,
    });
}

// A term with the descriptions after it, as a list of facts reads: “Observed: 1 in 40”.
/** @param {Element} term */
function termWords(term) {
  const told = [];
  for (
    let at = term.nextElementSibling;
    at?.localName === "dd";
    at = at.nextElementSibling
  )
    told.push(words(at));
  return excerptWords([words(term), told.join("; ")].filter(Boolean).join(": "), WORDS);
}

/** @param {Element} table @param {Part[]} parts */
function tablePart(table, parts) {
  const caption = table.querySelector(":scope > caption");
  if (caption) part(parts, "heading", words(caption));
  const rows = /** @type {HTMLTableElement} */ (table).rows;
  /** @type {{words: string, head: boolean}[][]} */
  const shown = [];
  for (const row of rows) {
    if (shown.length >= ROWS) break;
    if (!draws(row)) continue;
    const cells = [...row.cells]
      .slice(0, COLUMNS)
      .map((cell) => ({ words: words(cell), head: cell.localName === "th" }));
    if (cells.some((cell) => cell.words)) shown.push(cells);
  }
  const rest = rows.length - shown.length;
  if (shown.length && parts.length < PARTS)
    parts.push({
      kind: "table",
      rows: shown,
      more: rest > 0 ? counted(rest, "more row") : null,
    });
}

/** @param {Element} figure @param {Part[]} parts */
function figurePart(figure, parts) {
  const image = /** @type {HTMLImageElement | null} */ (
    figure.localName === "img" ? figure : figure.querySelector("img:not([data-lf-gen])")
  );
  const drawing = figure.querySelector("svg");
  const figcaption = figure.querySelector(":scope > figcaption");
  const caption = figcaption ? words(figcaption) : "";
  // A picture is said where the page draws it, as its words are.
  const shows = (/** @type {Element | null} */ picture) =>
    Boolean(picture && (reading.whole || drawsWithin(picture)));
  const src = image && shows(image) ? image.currentSrc || image.src : "";
  if (src)
    parts.push({
      kind: "figure",
      src,
      caption: excerptWords(caption || image?.alt, WORDS),
    });
  // A drawing the page holds inline is said by its title.
  else
    part(
      parts,
      "text",
      (shows(drawing) &&
        labelWords(drawing?.querySelector(":scope > title")?.textContent)) ||
        caption,
    );
}

// What a widget asks of the user, where it asks, by the page's reading: its answer as a
// Done row says it, or that it waits on the user; `settled` once its options no longer
// stand open.
/** @param {Element} element @returns {{words: Words, settled: boolean} | null} */
function question(element) {
  if (!element.id || !registry[element.localName]) return null;
  const item = readObligations().byId.get(`widget:${element.id}`);
  if (!hasObligationSource(item, "widget")) return null;
  if (item.state === "done") return { words: obligationEnding(item), settled: true };
  return item.next_actor === "user"
    ? { words: leafSays("Waiting on me"), settled: false }
    : null;
}

// How many conversations stand open about the place or anything in it, a heading's
// about the part it heads, and the user's turn where one is theirs, as the outline's
// owner gathered them (`conversationsAbout`).
/** @param {Element} place */
function conversations(place) {
  const about = conversationsAbout(place);
  if (!about) return null;
  return html`<span class="lf-place-foot"
    ><span>${counted(about.threads, "thread")}</span>${
      about.turn
        ? html`<span class="lf-place-turn">${voiced(about.turn.word)}</span>`
        : nothing
    }</span
  >`;
}

/** @param {Part} part */
function partView(part) {
  switch (part.kind) {
    case "heading":
      return html`<span class="lf-place-heading">${part.words}</span>`;
    case "text":
      return html`<span class="lf-place-text">${part.words}</span>`;
    case "state":
      return html`<span class="lf-place-state">${voiced(part.words)}</span>`;
    case "code":
      return html`<span class="lf-place-code">${part.lines}</span>`;
    case "figure":
      return html`<span class="lf-place-figure"
        ><img src=${part.src} alt="" />${
          part.caption
            ? html`<span class="lf-place-text">${part.caption}</span>`
            : nothing
        }</span
      >`;
    case "list":
      return html`<span class="lf-place-list"
        >${part.items.map(
          (item) =>
            html`<span class="lf-place-item" ?data-lf-chosen=${item.chosen}
              >${item.words}</span
            >`,
        )}${more(part.more)}</span
      >`;
    case "table":
      return html`<span
        class="lf-place-table"
        style=${`--lf-columns: ${Math.max(...part.rows.map((row) => row.length))}`}
        >${part.rows.map(
          (row) =>
            html`<span class="lf-place-row"
              >${row.map(
                (cell) =>
                  html`<span class="lf-place-cell" ?data-lf-head=${cell.head}
                    >${cell.words}</span
                  >`,
              )}</span
            >`,
        )}${more(part.more)}</span
      >`;
  }
}

/** @param {string | null} words */
const more = (words) =>
  words ? html`<span class="lf-place-more">${words}</span>` : nothing;
