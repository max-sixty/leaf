/* What the chrome calls an addressable element: the words it says
 * (`addressableSays`), the name the authoring contract gives it (`addressableName`),
 * the element a heading titles by that contract (`titledElement`), the label every
 * surface shows for it away from the page (`addressableLabel`), and the word and label
 * an anchor on it shows (`sectionLabel`). Each reads authored words through the passage
 * reader, so generated chrome never names anything. The word for an element's kind is
 * the library's (lib/element-word.js, `addressableWord`). */
import { isElementName } from "../state/registry-contract.js";
import { registry } from "../state/registry.js";
import { authoredScope, elementReading, HEADING, readsElement } from "./passages.js";
import { keptEach } from "../state/kept.js";
import { TEXT_BLOCK } from "../state/kernel-facts.js";
import { addressableWord } from "../lib/element-word.js";
import { upFrom } from "../lib/shadow-tree.js";
import { uiInside } from "../base/ui-marks.js";
import { excerptWords } from "../lib/words.js";

// The label is rooted at the addressable and reads its authored words. Generated annotation
// chrome is excluded by the same passage reader used for anchor resolution. Display
// surfaces constrain these complete words to their available space.
/** @param {Element | null | undefined} addressable */
export function addressableSays(addressable) {
  if (!addressable) return "";
  return addressable.lfSays?.() || elementReading(addressable);
}

// What names an element, where the authoring contract gives it a name
// (`skills/leaf/references/module-reading.md`, "Naming"): the name its author
// declares, else the caption HTML gives it. A widget the registry registers declares
// its name in its `label` attribute (the registry's `$attributes`), as an option, a
// card, a tab or a column does, and takes none from its markup. Plain markup is named
// by its caption: a disclosure by its <summary>, an <hgroup> by its heading, and a
// `section` or `article` by the heading it opens with, alone or in an <hgroup>. That
// last is a reading of position the maintainer agreed to (root AGENTS.md, "Read what
// the page states"): HTML calls h1–h6 "headings for their sections" without saying
// which element is the section, and an element that opens with its heading is the case
// where the two agree. No other element is named by a heading inside it, and a <strong>
// names nothing. The words are the ones the author wrote less a popover's (the `named`
// reading), so a gloss's explanation is no part of a heading's name, and generated
// chrome names nothing: chrome inside the element, asked about the element's
// own insides, since a section an agent sent in a reply stands inside the floating
// panel's chrome and its heading is still its name. An element the contract gives no
// name answers "". The server names an obligation's element by the same rule off the
// document (`passages.element_name`), and `tests/name_cases.json` holds both to
// the same cases.
//
// Rejected: naming any element by a leading heading, looked for inside a <header> or
// past an eyebrow, which names a `div` by where a heading happens to stand; and titling
// a widget by its leading heading, summary or <strong>, which names an option by how its
// first words look.
const SECTIONS = "section, article";
/** The caption that names plain markup by that rule, or null: a disclosure's first
 * <summary>, an hgroup's heading, or the heading a section or article opens with, alone
 * or in an <hgroup>. Finding it reads the element's children, so the answer is kept as
 * long as the piece of the page reading the element stands in (passages.js,
 * `readsElement`), as an element's words are: a label asked again on every pass, or a
 * preview climbing past a long run of paragraphs, reads them once.
 * @param {Element} container @returns {Element | null} */
export const leadingTitle = (container) =>
  registered(container) ? null : openingTitleKept(container);
const openingTitleKept = keptEach((/** @type {Element} */ container) => {
  readsElement(container);
  return openingTitle(container);
});
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
// The element a heading titles: the outermost one it names by the rule above, its
// hgroup and the section or article that opens with it; or else the heading itself.
// `lf-toc` starts each row's stretch of the page at it, a heading's link takes
// its address, and a heading's link preview counts the conversations about it
// (records/thread/placement.js, `conversationsAbout`). `titlingHeading` reads it the other way
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
    if (leadingTitle(at) === heading) titled = at;
    else break;
  return titled;
}
/** The heading that titles `element` (`titledElement`), or null.
 * @param {Element} element @returns {Element | null} */
export function titlingHeading(element) {
  const title = leadingTitle(element);
  return title?.matches(HEADING) ? title : null;
}
// The title a widget's `label` attribute holds, such as a tab's: the one attribute
// that names its element on every widget that takes it (`$attributes`, Python's
// `registry.contract.NAME_ATTRIBUTE`).
/** @param {Element} element */
function declaredName(element) {
  return (registered(element) && element.getAttribute("label")?.trim()) || "";
}
// Where a name comes from: an attribute's words, or an element whose words, in the
// `named` reading, are the name. A reader that reads names as something else draws
// them, as a preview reads them as the page draws them, reads the same source.
/** @typedef {{words: string} | {by: Element}} Naming */
/** @param {Naming | null} naming @returns {string} */
const namingWords = (naming) =>
  !naming ? "" : "words" in naming ? naming.words : elementReading(naming.by, "named");
// What `addressableName` reads, by the rule above: its declared attribute, else its
// leading title.
/** @param {Element} element @returns {Naming | null} */
function addressableNaming(element) {
  const declared = declaredName(element);
  if (declared) return { words: declared };
  const title = leadingTitle(element);
  return title && elementReading(title, "named") ? { by: title } : null;
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
  const caption = captionOf(element);
  return caption && elementReading(caption, "named") ? { by: caption } : null;
};
// An element's own caption, kept as its words are (passages.js, `readsElement`).
const captionOf = keptEach((/** @type {Element} */ element) => {
  readsElement(element);
  return [...element.children].find(
    (child) => child.matches("figcaption, caption") && !uiInside(child, element),
  );
});
// A form control's caption is its <label>.
/** @param {Element & Partial<Pick<HTMLInputElement, "labels" | "alt">>} element
 * @returns {Naming | null} */
function accessibleNaming(element) {
  const label = element.getAttribute("aria-label")?.trim();
  if (label) return { words: label };
  const labelled = element.labels?.[0];
  if (labelled && elementReading(labelled, "named")) return { by: labelled };
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
// holder too, is records/thread/placement.js's `partOver`. The page's column is `main`, beside the
// body's other content; a name its author gives it, such as an `aria-label`, names the
// page, not each unnamed element in it.
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
