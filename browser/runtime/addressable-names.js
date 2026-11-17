/* What the chrome calls an addressable element: the word for its kind
 * (`addressableWord`), the words it says (`addressableSays`), the name the authoring
 * contract gives it (`addressableName`), the element a heading titles by that contract
 * (`titledElement`), the label every surface shows for it away from the page
 * (`addressableLabel`), and the word and label an anchor on it shows (`sectionLabel`).
 * Each reads authored words through the passage reader, so generated chrome never
 * names anything. */
import { isElementName } from "./registry-contract.js";
import { registry } from "./registry.js";
import { authoredScope, elementReading, HEADING, keptAnswer } from "./passages.js";
import { TEXT_BLOCK } from "./kernel-facts.js";
import { uiInside, upFrom } from "./shadow.js";
import { excerptWords } from "./words.js";

/** @type {Record<string, string>} */
const HTML_WORDS = {
  input: "control",
  select: "control",
  button: "control",
  p: "paragraph",
  li: "item",
  tr: "row",
  td: "cell",
  th: "cell",
  figure: "figure",
  blockquote: "quote",
  pre: "block",
  section: "section",
  article: "section",
  aside: "aside",
  ul: "list",
  ol: "list",
  dl: "list",
  table: "table",
  details: "note",
  h1: "heading",
  h2: "heading",
  h3: "heading",
  h4: "heading",
  h5: "heading",
  h6: "heading",
};

/** @param {Element | null | undefined} addressable */
export function addressableWord(addressable) {
  if (!addressable) return "";
  const tag = addressable.tagName.toLowerCase();
  const word = widgetWord(tag, addressable);
  if (word) return word;
  if (tag === "pre")
    return addressable.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}

// A widget's word for its kind: its declaration's fixed word (`words.word`), else what
// its module answers from `lfWord()` where `element` is drawn and has the method, else
// its tag without the prefix.
/** @param {string} tag @param {Element | null} [element] */
export function widgetWord(tag, element = null) {
  return (
    registry[tag]?.words?.word ||
    element?.lfWord?.() ||
    (tag.startsWith("lf-") ? tag.slice(3) : "")
  );
}

// The label is rooted at the addressable and reads its authored words. Generated annotation
// chrome is excluded by the same passage reader used for anchor resolution. Display
// surfaces constrain these complete words to their available space.
/** @param {Element | null | undefined} addressable */
export function addressableSays(addressable) {
  if (!addressable) return "";
  return addressable.lfSays?.() || elementReading(addressable);
}

// What names an element, where the authoring contract gives it a name
// (`skills/leaf/references/module-reading.md`, "Naming elements"): the name its author
// declares, else the caption HTML gives it. A widget the registry registers declares
// its name in its `label` attribute (the registry's `$attributes`), as an option, a
// card, a tab or a column does, and takes none from its markup. Plain markup declares
// its name as ARIA does (`ariaNaming`); else it is named by its caption: a disclosure by
// its <summary>, an <hgroup> by its heading, and a `section` or `article` by the heading
// it opens with, alone or in an <hgroup>. That last is a reading of position the
// maintainer agreed to (root AGENTS.md, "Read what the page states"): HTML calls h1–h6
// "headings for their sections" without saying which element is the section, and an
// element that opens with its heading is the case where the two agree. No other element
// is named by a heading inside it, and a <strong> names nothing. The words are the ones
// the author wrote (the `wrote` reading), so a gloss's tip the page draws beside its
// phrase is no part of a heading's name, and generated chrome names nothing: chrome
// inside the element, asked about the element's own insides, since a section an agent
// sent in a reply stands inside the floating panel's chrome and its heading is still its
// name. An element the contract gives no name answers "". The server names an
// obligation's element by the same rule off the document (`gesture_words.element_name`),
// and `tests/name_cases.json` holds both to the same cases.
//
// Rejected: naming any element by a leading heading, looked for inside a <header> or
// past an eyebrow, which names a `div` by where a heading happens to stand; and titling
// a widget by its leading heading, summary or <strong>, which names an option by how its
// first words look.
const SECTIONS = "section, article";
/** The caption that names plain markup by that rule, or null: a disclosure's first
 * <summary>, an hgroup's heading, or the heading a section or article opens with, alone
 * or in an <hgroup>. Finding it reads the element's children, so the answer is kept as
 * long as the page reading stands (`keptAnswer`), as an element's words are: a label
 * asked again on every pass, or a preview climbing past a long run of paragraphs, reads
 * them once.
 * @param {Element} container @returns {Element | null} */
export const leadingTitle = (container) =>
  registered(container)
    ? null
    : keptAnswer(container, "leading title", () => openingTitle(container));
/** @param {Element} element @returns {Element | null} */
function openingTitle(element) {
  const child = (/** @type {string} */ selector) =>
    [...element.children].find(
      (node) => node.matches(selector) && !uiInside(node, element),
    ) ?? null;
  if (element.localName === "details") return child("summary");
  if (element.localName === "hgroup") return child(HEADING);
  if (!element.matches(SECTIONS)) return null;
  for (const node of element.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) return null;
    if (!(node instanceof Element) || uiInside(node, element)) continue;
    if (node.localName === "hgroup") return openingTitle(node);
    return node.matches(HEADING) ? node : null;
  }
  return null;
}
// Whether the registry registers the element, as it does each widget.
/** @param {Element} element */
const registered = (element) =>
  isElementName(element.localName) && Object.hasOwn(registry, element.localName);
// The element a heading titles: the outermost one it titles by position under the rule
// above, its hgroup and the section or article that opens with it, short of an element
// its author names otherwise, as a section's `aria-label` does; or else the heading
// itself. A
// declared name can withdraw a heading's title but never give one: a section whose
// `aria-labelledby` names its opening heading is still that heading's, and one naming a
// later heading is no heading's, so which heading heads which part stays the order the
// page reads in. `lf-toc` starts each row's stretch of the page at it, a heading's link takes
// its address, and a heading's link preview counts the conversations about it
// (thread/placement.js, `conversationsAbout`). `titlingHeading` reads it the other way
// round.
//
// Rejected: titling the outermost element whose first heading this is, past wrappers
// and an eyebrow, wherever every other heading inside ranks lower. It reads position
// and rank anywhere around the heading, so a `div`, a page's column or a section
// wrapping a question takes a title its author never gave it, and answering needs the
// document's whole outline.
/** @param {Element} heading @returns {Element} */
export function titledElement(heading) {
  let titled = heading;
  for (let at = heading.parentElement; at; at = at.parentElement)
    if (titleOf(at) === heading) titled = at;
    else break;
  return titled;
}
/** The heading that titles `element` (`titledElement`), or null.
 * @param {Element} element @returns {Element | null} */
export function titlingHeading(element) {
  const title = titleOf(element);
  return title?.matches(HEADING) ? title : null;
}
// The element that titles `element` by position (`leadingTitle`), or null where its
// author names it otherwise.
/** @param {Element} element */
const titleOf = (element) => {
  const title = leadingTitle(element);
  if (!title) return null;
  const naming = addressableNaming(element);
  return !naming || ("by" in naming && naming.by === title) ? title : null;
};
// The title a widget's `label` attribute holds, such as a tab's: the one attribute
// that names its element on every widget that takes it (`$attributes`, Python's
// `registry.contract.NAME_ATTRIBUTE`).
/** @param {Element} element */
function declaredName(element) {
  return (registered(element) && element.getAttribute("label")?.trim()) || "";
}
// The name ARIA gives an element whose author names it, as the browser's
// accessibility tree computes it (HTML-AAM): the words of the elements its
// `aria-labelledby` names, else its `aria-label`, else a fieldset's first <legend>. A
// question's group takes its name this way, which the server reads by the same rule
// (`gesture_words.aria_name`) to require one of a question's group and to name it. A
// registered widget declares its name in `label` instead, so `addressableNaming` skips
// ARIA for one, and the chrome reads it only where the widget has no other name
// (`accessibleNaming`).
/** @param {Element} element @returns {Naming | null} */
function ariaNaming(element) {
  const named = labelledBy(element);
  const [only] = named;
  if (named.length === 1 && only && elementReading(only, "wrote"))
    return { by: only, reading: "wrote" };
  const words = named.map((node) => elementReading(node, "wrote")).filter(Boolean);
  if (words.length) return { words: words.join(" ") };
  const label = element.getAttribute("aria-label")?.replace(/\s+/g, " ").trim();
  if (label) return { words: label };
  if (element.localName !== "fieldset") return null;
  const legend = keptAnswer(element, "legend", () =>
    [...element.children].find((child) => child.localName === "legend"),
  );
  return legend && elementReading(legend, "wrote")
    ? { by: legend, reading: "wrote" }
    : null;
}
/** The elements an element's `aria-labelledby` names, found by id in its tree. Not its
 * `ariaLabelledByElements`: Firefox's content process crashes once the page and an
 * isolated world, such as Playwright's role locator, have both read that property
 * (https://bugzilla.mozilla.org/show_bug.cgi?id=2090055).
 * @param {Element} element @returns {Element[]} */
export function labelledBy(element) {
  const ids = element.getAttribute("aria-labelledby")?.trim();
  if (!ids) return [];
  const root = /** @type {Document | ShadowRoot} */ (element.getRootNode());
  if (!("getElementById" in root)) return [];
  return ids.split(/\s+/).flatMap((id) => root.getElementById(id) ?? []);
}
// Where a name comes from: an attribute's words, or an element whose words are the name,
// read by the reading the rule names. A reader that reads names as something else draws
// them, as a preview reads them as the page draws them, reads the same source.
/** @typedef {{words: string} | {by: Element, reading: "wrote" | "says"}} Naming */
/** @param {Naming | null} naming @returns {string} */
const namingWords = (naming) =>
  !naming
    ? ""
    : "words" in naming
      ? naming.words
      : elementReading(naming.by, naming.reading);
// What `addressableName` reads, by the rule above: its declared name, else its leading
// title.
/** @param {Element} element @returns {Naming | null} */
function addressableNaming(element) {
  const aria = registered(element) ? null : ariaNaming(element);
  if (aria) return aria;
  const declared = declaredName(element);
  if (declared) return { words: declared };
  const title = leadingTitle(element);
  return title && elementReading(title, "wrote")
    ? { by: title, reading: "wrote" }
    : null;
}
/** @param {Element | null | undefined} element */
export const addressableName = (element) =>
  element ? namingWords(addressableNaming(element)) : "";

// What the chrome calls an element away from it: an On Me row, a Page Map heading,
// a thread's anchor, a feed row. The element's name comes first: `addressableName`,
// else its own caption, the `aria-label` its author gave it, or a control's <label>.
// An element whose words are its own (a block of prose, anything holding text of its
// own, or a module that answers `lfSays`) is otherwise named by them, cut short. Any other
// element's words are its members' run together, a question's with its options' and
// their chips', which name nothing, so it takes the name of the nearest element
// holding it that has one, short of the document it stands in (the page's column, or
// a message's body): a question's options by the question, a chart by its section.
// Past that, plain markup is named by its words cut short, and a registered widget by
// nothing: empty, and the caller says the element's word (`addressableWord`), which it
// usually shows beside this anyway.
export const LABEL_WORDS = 60;
/** @param {Element} element @returns {Naming | null} */
const captionNaming = (element) => {
  const caption = keptAnswer(element, "caption", () =>
    [...element.children].find(
      (child) => child.matches("figcaption, caption") && !uiInside(child, element),
    ),
  );
  return caption && elementReading(caption) ? { by: caption, reading: "says" } : null;
};
// The name a reader who can't see the page hears for an element: its ARIA name, a form
// control's <label>, or an image's `alt`.
/** @param {Element & Partial<Pick<HTMLInputElement, "labels" | "alt">>} element
 * @returns {Naming | null} */
function accessibleNaming(element) {
  const aria = ariaNaming(element);
  if (aria) return aria;
  const labelled = element.labels?.[0];
  if (labelled && elementReading(labelled)) return { by: labelled, reading: "says" };
  const alt = element.alt?.trim();
  return alt ? { words: alt } : null;
}
/** @param {Element} element */
export const accessibleName = (element) => namingWords(accessibleNaming(element));
// The name an element has itself, before any holder lends it one, and where it comes
// from.
/** @param {Element} element @returns {Naming | null} */
export const ownNaming = (element) =>
  addressableNaming(element) ?? captionNaming(element) ?? accessibleNaming(element);
/** @param {Element} element */
export const ownName = (element) => namingWords(ownNaming(element));
/** @param {Element} element */
const saysItself = (element) =>
  element.matches(TEXT_BLOCK) ||
  element.lfSays?.() ||
  [...element.childNodes].some(
    (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
  );
/** @param {Element | null | undefined} element */
export function addressableLabel(element) {
  if (!element) return "";
  const own = ownName(element);
  if (own) return own;
  if (saysItself(element)) return excerptWords(addressableSays(element), LABEL_WORDS);
  const held = namingWords(holderNaming(element));
  if (held) return held;
  // A registered widget has a word of its own, which says more than its members' words
  // run together. Plain markup has none worth saying (a `div`), so its words are the
  // last resort.
  if (registered(element)) return "";
  return excerptWords(addressableSays(element), LABEL_WORDS);
}

// The name of the nearest element holding `element` that has one, short of the document
// it stands in (the page's column, or a message's body), or "": a question's options are
// named by the question, a chart by its section. The chrome's label for an element
// reads it (`addressableLabel`); a place's name, which follows headings inside the
// holder too, is thread/placement.js's `partOver`. The page's column is `main`, beside the
// body's other content; its leading heading titles the page, not each unnamed element in
// it.
/** @param {Element} element @returns {Naming | null} */
function holderNaming(element) {
  const scope = authoredScope(element);
  const column = (/** @type {Element} */ at) =>
    at.localName === "main" && at.parentElement === scope;
  for (let at = upFrom(element); at && at !== scope && !column(at); at = upFrom(at)) {
    const naming = ownNaming(at);
    if (naming) return naming;
  }
  return null;
}

// A thread's § coordinate and the visual-action picker both show it.
/** @param {Element | null | undefined} addressable */
export const sectionLabel = (addressable) =>
  [addressableWord(addressable), addressableLabel(addressable)]
    .filter(Boolean)
    .join(" · ");
