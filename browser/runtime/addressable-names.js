/* What the chrome calls an addressable element: the word for its kind
 * (`addressableWord`), the words it says (`addressableSays`), the name the authoring
 * contract gives it (`addressableName`), the label every surface shows for it away
 * from the page (`addressableLabel`), and the word and label an anchor on it shows
 * (`sectionLabel`). Each reads authored words through the passage
 * reader, so generated chrome never names anything. */
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

// A widget's word for its kind: what its module answers from `lfWord()` where `element`
// is drawn and has the method, else its registry's fixed `x-word`, else its tag without
// the prefix.
/** @param {string} tag @param {Element | null} [element] */
export function widgetWord(tag, element = null) {
  const own = element?.lfWord?.() || registry[tag]?.["x-word"];
  return own || (tag.startsWith("lf-") ? tag.slice(3) : "");
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
// (`skills/leaf/references/module-reading.md`, "Naming elements"): a widget's `label`
// attribute (the registry's `$attributes`), else a leading disclosure summary, heading,
// or titled member's <strong>, looked for inside a leading <header> or <hgroup> too. Leading means no words come
// before it; elements may, as a titled member's comparison chips stand in the band
// above its title and an eyebrow above a header's heading. The words are the ones the
// author wrote (the `wrote` reading), so a gloss's tip the page draws beside its phrase
// is no part of a heading's name, and generated chrome names nothing: chrome inside
// the element, asked about the element's own insides, since a widget an agent sent in
// a reply stands inside the floating panel's chrome and its heading is still its name.
// An element the contract gives no name answers "". The server names an obligation's
// element by the same rule off the document (`gesture_words.element_name`), and
// `tests/name_cases.json` holds both to the same cases.
const TITLES = `summary, ${HEADING}, strong`;
/** The element whose words name `container` by that rule, or null. Finding it reads the
 * container's children, so the answer is kept as long as the page reading stands
 * (`keptAnswer`), as an element's words are: a label asked again on every pass, or a
 * preview climbing past a long run of paragraphs, reads them once.
 * @param {Element} container @returns {Element | null} */
export const leadingTitle = (container) =>
  keptAnswer(container, "leading title", () => readLeadingTitle(container));
/** @param {Element} container @returns {Element | null} */
function readLeadingTitle(container) {
  for (const node of container.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) return null;
    if (!(node instanceof Element) || uiInside(node, container)) continue;
    if (node.matches(TITLES)) return node;
    if (["header", "hgroup"].includes(node.localName)) return leadingTitle(node);
  }
  return null;
}
// The title a widget's `label` attribute holds, such as a tab's: the one attribute
// that names its element on every widget that takes it (`$attributes`, Python's
// `registry.contract.NAME_ATTRIBUTE`).
/** @param {Element} element */
function declaredName(element) {
  const widget =
    isElementName(element.localName) && Object.hasOwn(registry, element.localName);
  return (widget && element.getAttribute("label")?.trim()) || "";
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
// What `addressableName` reads, by the rule above: its declared attribute, else its
// leading title.
/** @param {Element} element @returns {Naming | null} */
function addressableNaming(element) {
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
const LABEL_WORDS = 60;
/** @param {Element} element @returns {Naming | null} */
const captionNaming = (element) => {
  const caption = keptAnswer(element, "caption", () =>
    [...element.children].find(
      (child) => child.matches("figcaption, caption") && !uiInside(child, element),
    ),
  );
  return caption && elementReading(caption) ? { by: caption, reading: "says" } : null;
};
// A form control's caption is its <label>.
/** @param {Element & Partial<Pick<HTMLInputElement, "labels" | "alt">>} element
 * @returns {Naming | null} */
function accessibleNaming(element) {
  const label = element.getAttribute("aria-label")?.trim();
  if (label) return { words: label };
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
  // run together. Plain markup has none worth saying (a `div`), so its words, or the
  // name of the picture it holds, are the last resort.
  if (isElementName(element.localName) && registry[element.localName]) return "";
  return excerptWords(
    addressableSays(element) ||
      element.querySelector("[aria-label]")?.getAttribute("aria-label"),
    LABEL_WORDS,
  );
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
