/* What a place on the page shows as a preview (preview.js), so a link into the page
   says where it points before a press takes the reader there (browser/AGENTS.md,
   "Pointing reads; pressing acts").

   A link into the page is one an author wrote, in the page or in a message's markup,
   whose fragment names a place of the page (`fragmentTarget`): an element by its id,
   or the part of a widget its key names. A link Leaf or a widget draws, such as a
   contents row or a heading's own link, is its drawer's to preview (`lfPreview`), since
   only it knows whether its words already say what the place holds; a contents row
   does. A link to another document keeps only the browser's status bar.

   The preview is a short rendering of the place, in the popover face:

   - its name, the way the chrome names an element away from the page
     (addressable-names.js): a heading's words, a section's leading heading, a tab's
     label, a table's or figure's caption, and for a widget with no name of its own, the
     name of what holds it, as a question names its options;
   - its first few parts, in the page's order, each as the page reads it: a heading, a
     paragraph cut to three lines, a list's first items, a table's first rows, a
     figure's picture and caption, a code block's first lines, and a closed disclosure's
     summary alone. A heading's parts are those of the section it opens. Anything drawn
     before the name, such as an eyebrow, and anything Leaf draws inside the place are
     left out;
   - a widget's current state, from the reading the page already holds: where it asks
     the user something, its obligation's answer in the words a Done row says it in, or
     that it waits on the user, and an answered question shows its answer in place of
     its options; elsewhere, its options with each one its answer picks checked, as
     the widget reads its own state, so a question authored settled marks its pick;
   - the open conversations about the place or anything in it, and whether one is the
     user's turn, as a margin entry says it.

   It is made of the place's words, never its nodes: a copy would repeat ids, upgrade
   widgets and carry controls, and the preview holds no control. The walk stops once it
   has the parts it shows, and it reads each part's words by the page's own reading
   (`elementReading`), so a preview's work is the link's and its place's, whatever the
   page holds (root AGENTS.md, "Responsiveness"). Obligations and conversations come
   from the indexes the publisher keeps as each reading arrives, by an obligation's id
   and by the element a thread is about, so the preview looks up what it shows and
   walks nothing else.

   Decisions: a table shows its first rows in its own columns, cut to one line a cell,
   since a row's cells read apart are a table's point; a figure shows its picture, the
   part a reader recognises it by; a chart, a diagram or anything else a widget draws
   shows only its name and words, since copying its drawing would carry its controls.
   Rejected: a clone of the place made inert, which repeats every id it holds and
   upgrades every widget in it. */
import { html, nothing } from "/runtime/framework.js";
import { fragmentTarget } from "./anchor-resolution.js";
import {
  addressableLabel,
  addressableWord,
  leadingTitle,
  ownName,
} from "./addressable-names.js";
import { TEXT_BLOCK } from "./kernel-facts.js";
import { obligationEnding } from "./obligations/answer.js";
import { readObligations } from "./obligations/model.js";
import { hasObligationSource } from "./obligations/source.js";
import {
  authoredScope,
  elementReading,
  GENERATED,
  HEADING,
  inPage,
  LEAF_SURFACE,
  pageDocument,
} from "./passages.js";
import { declarationFor, registry } from "./registry.js";
import { agentName, readPart } from "./semantic-state.js";
import { declaredRoot, overIn } from "./shadow.js";
import { threadsOnSection } from "./thread/state.js";
import { discussed } from "./thread/model.js";
import { threadAttention } from "./thread/workflow.js";
import { leafSays, voiced } from "./voice.js";
import { capitalized, counted, excerptWords, labelWords } from "./words.js";

/** @typedef {import("./voice.js").Words} Words
 * @typedef {{kind: "heading" | "text", words: string}
 *   | {kind: "list", items: {words: string, chosen: boolean}[], more: string | null}
 *   | {kind: "table", rows: {words: string, head: boolean}[][], more: string | null}
 *   | {kind: "figure", src: string, caption: string}
 *   | {kind: "code", lines: string}
 *   | {kind: "state", words: Words}} Part */

// How much of a place a preview shows: parts after its name, a paragraph's words (CSS
// cuts it to its lines), a list's items, a table's rows and columns, a code block's
// lines.
const PARTS = 2;
const WORDS = 280;
const ITEMS = 3;
const ROWS = 3;
const COLUMNS = 4;
const LINES = 4;

// What a preview leaves out of a place: what Leaf draws in it, what the page never
// draws, and what it hides until the reader opens it, except a closed tab's panel,
// which the browser shows once a find reaches it.
const UNSHOWN = `${GENERATED}, ${LEAF_SURFACE}, script, style, template, noscript, [aria-hidden="true"], [hidden]:not([hidden="until-found"])`;
const LIST = "ul, ol, menu, dl";

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

/** A place on the page as a preview shows it, in the popover face.
 * @param {Element} place */
export function placePreview(place) {
  const heading = place.matches(HEADING);
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
    popover: html`<span class="lf-place"
      >${name ? html`<span class="lf-place-name">${name}</span>` : nothing}${parts.map(
        partView,
      )}${foot}</span
    >`,
  };
}

// A widget with no name of its own takes the name of what holds it, as a question's
// options do, and then its word; plain markup with no name shows its words alone.
/** @param {Element} place */
function placeName(place) {
  const own = ownName(place);
  if (own || !registry[place.localName]) return own;
  return addressableLabel(place) || capitalized(addressableWord(place));
}

/** The authored words an element holds, as the page reads them.
 * @param {Element} element */
const words = (element) => labelWords(elementReading(element, "wrote"));

// The parts of the section a heading opens: the blocks after it, up to the next heading
// of its rank or above, or a block such a heading opens.
/** @param {Element} heading */
function sectionParts(heading) {
  const rank = Number(heading.localName.slice(1));
  /** @type {Part[]} */
  const parts = [];
  for (
    let next = heading.nextElementSibling;
    next && parts.length < PARTS;
    next = next.nextElementSibling
  ) {
    const opens = next.matches(HEADING) ? next : leadingTitle(next);
    if (opens?.matches(HEADING) && Number(opens.localName.slice(1)) <= rank) break;
    if (!next.matches(UNSHOWN)) read(next, parts, null);
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
  if (element === title) return null;
  if (title && !element.contains(title)) return title;
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
      said(parts, "text", at < 0 ? all : all.slice(at + named.length).trim());
    } else readChildren(element, parts, title);
  }
  if (asks) parts.push({ kind: "state", words: asks.words });
  return null;
}

// The part `element` makes as the page draws it, or its children's parts.
/** @param {Element} element @param {Part[]} parts */
function drawn(element, parts) {
  if (element.matches(HEADING)) said(parts, "heading", words(element));
  else if (element.matches(LIST)) listPart(element, parts);
  else if (element.localName === "table") tablePart(element, parts);
  else if (element.localName === "figure" || element.localName === "img")
    figurePart(element, parts);
  else if (element.localName === "pre") {
    const lines = element.textContent?.split("\n").slice(0, LINES).join("\n") ?? "";
    if (lines.trim()) parts.push({ kind: "code", lines });
  } else if (element.localName === "details" && !element.hasAttribute("open")) {
    const summary = element.querySelector(":scope > summary");
    if (summary) said(parts, "text", words(summary));
  } else if (element.matches(TEXT_BLOCK) || holdsText(element)) {
    said(parts, "text", words(element));
  } else if (!membersPart(element, parts)) readChildren(element, parts, null);
}

/** @param {Element} element @param {Part[]} parts @param {Element | null} title */
function readChildren(element, parts, title) {
  let still = title;
  for (const child of (declaredRoot(element) ?? element).children) {
    if (parts.length >= PARTS) break;
    if (!child.matches(UNSHOWN)) still = read(child, parts, still);
  }
  return still;
}

/** @param {Part[]} parts @param {"heading" | "text"} kind @param {string} text */
function said(parts, kind, text) {
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
    (item) =>
      item.matches(list.localName === "dl" ? "dt" : "li") && !item.matches(UNSHOWN),
  );
  const shown = items.slice(0, ITEMS).map((item) => ({
    words: item.localName === "dt" ? termWords(item) : excerptWords(words(item), WORDS),
    chosen: false,
  }));
  listed(parts, shown, items.length);
}

// A run of like members, as a question's options, a board's columns or a set of tabs
// are, reads as a list of their names, the first few and every one the widget's answer
// picks, marked as picked.
/** @param {Element} element @param {Part[]} parts */
function membersPart(element, parts) {
  const members = [...(declaredRoot(element) ?? element).children].filter(
    (member) => !member.matches(UNSHOWN),
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
      words: excerptWords(ownName(member) || words(member), WORDS),
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
  if (caption) said(parts, "heading", words(caption));
  const rows = /** @type {HTMLTableElement} */ (table).rows;
  /** @type {{words: string, head: boolean}[][]} */
  const shown = [];
  for (const row of rows) {
    if (shown.length >= ROWS) break;
    if (row.matches(UNSHOWN)) continue;
    shown.push(
      [...row.cells]
        .slice(0, COLUMNS)
        .map((cell) => ({ words: words(cell), head: cell.localName === "th" })),
    );
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
  const figcaption = figure.querySelector(":scope > figcaption");
  const caption = figcaption ? words(figcaption) : "";
  const src = image?.currentSrc || image?.src || "";
  if (src)
    parts.push({
      kind: "figure",
      src,
      caption: excerptWords(caption || image?.alt, WORDS),
    });
  // A drawing the page holds inline is said by its title.
  else
    said(
      parts,
      "text",
      labelWords(figure.querySelector("svg > title")?.textContent) || caption,
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
  if (item.status !== "open") return { words: obligationEnding(item), settled: true };
  return item.next_actor === "user"
    ? { words: leafSays("Waiting on me"), settled: false }
    : null;
}

// The open conversations about the place and the elements it holds, from the threads
// the publisher indexed by the element each is about as they arrived
// (`threadsOnSection`): a lookup for each id the place holds, so the work is the place's.
/** @param {Element} place */
function threadsAbout(place) {
  return [place, ...place.querySelectorAll("[id]")]
    .flatMap((element) => threadsOnSection(element.id))
    .filter((thread) => !thread.resolved && discussed(thread));
}

// How many conversations stand open about the place, and the user's turn where one is
// theirs (`threadAttention`).
/** @param {Element} place */
function conversations(place) {
  const threads = threadsAbout(place);
  if (!threads.length) return null;
  const agent = agentName();
  const turn = threads
    .map((thread) => threadAttention(thread, agent))
    .find((attention) => attention?.kind === "needs_user");
  return html`<span class="lf-place-foot"
    ><span>${counted(threads.length, "thread")}</span>${
      turn ? html`<span class="lf-place-turn">${voiced(turn.word)}</span>` : nothing
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
