/* What the chrome calls an addressable element: the word for its kind
 * (`addressableWord`), the words it says (`addressableSays`), the name the authoring
 * contract gives it (`addressableName`), the label every surface shows for it away
 * from the page (`addressableLabel`), and the word and label an anchor on it shows
 * (`sectionLabel`). Each reads authored words through the passage
 * reader, so generated chrome never names anything. */
import { isElementName } from "./registry-contract.js";
import { registry } from "./registry.js";
import { authoredScope, elementReading } from "./passages.js";
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

// A widget's word for its kind: its registry's fixed `x-word`, its module's `lfWord()`
// where `x-word` is `module` and `element` is drawn, else its tag without the prefix.
/** @param {string} tag @param {Element | null} [element] */
export function widgetWord(tag, element = null) {
  const declared = registry[tag]?.["x-word"];
  const own = declared === "module" ? element?.lfWord?.() : declared;
  return own || (tag.startsWith("lf-") ? tag.slice(3) : "");
}

// The label is rooted at the addressable and reads its authored words. Generated annotation
// chrome is excluded by the same passage reader used for anchor resolution. Display
// surfaces constrain these complete words to their available space.
/** @param {Element | null | undefined} addressable */
export function addressableSays(addressable) {
  if (!addressable) return "";
  const own =
    registry[addressable.localName]?.["x-word"] === "module"
      ? addressable.lfSays?.()
      : "";
  return own || elementReading(addressable);
}

// What names an element, where the authoring contract gives it a name
// (`../../references/page-authoring.md`): the attribute its registry entry declares
// with `x-name`, else a leading disclosure summary, heading, or titled member's
// <strong>, looked for inside a leading <header> or <hgroup> too. Leading means no words come
// before it; elements may, as a titled member's comparison chips stand in the band
// above its title and an eyebrow above a header's heading. The words are the ones the
// author wrote (the `wrote` reading), so a gloss's tip the page draws beside its phrase
// is no part of a heading's name, and generated chrome names nothing: chrome inside
// the element, asked about the element's own insides, since a widget an agent sent in
// a reply stands inside the floating panel's chrome and its heading is still its name.
// An element the contract gives no name answers "". The server names an obligation's
// element by the same rule off the document (`gesture_words.element_name`), and
// `tests/name_cases.json` holds both to the same cases.
const TITLES = "summary, h1, h2, h3, h4, h5, h6, strong";
/** The element whose words name `container` by that rule, or null. */
/** @param {Element} container @returns {Element | null} */
export function leadingTitle(container) {
  for (const node of container.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) return null;
    if (!(node instanceof Element) || uiInside(node, container)) continue;
    if (node.matches(TITLES)) return node;
    if (["header", "hgroup"].includes(node.localName)) return leadingTitle(node);
  }
  return null;
}
// The title an element's attribute holds, as its declaration names (`x-name`), such
// as a tab's label.
/** @param {Element} element */
export function declaredName(element) {
  const attribute = registry[element.localName]?.["x-name"];
  return (attribute && element.getAttribute(attribute)?.trim()) || "";
}
/** @param {Element | null | undefined} element */
export function addressableName(element) {
  if (!element) return "";
  const declared = declaredName(element);
  if (declared) return declared;
  const title = leadingTitle(element);
  return title ? elementReading(title, "wrote") : "";
}

// What the chrome calls an element away from it: an On me row, a Page Map heading,
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
/** @param {Element} element */
const captionOf = (element) => {
  const caption = [...element.children].find(
    (child) => child.matches("figcaption, caption") && !uiInside(child, element),
  );
  return caption ? elementReading(caption) : "";
};
// A form control's caption is its <label>.
/** @param {Element & Partial<Pick<HTMLInputElement, "labels" | "alt">>} element */
export const accessibleName = (element) =>
  element.getAttribute("aria-label")?.trim() ||
  (element.labels?.[0] ? elementReading(element.labels[0]) : "") ||
  element.alt?.trim() ||
  "";
// The name an element has itself, before any holder lends it one.
/** @param {Element} element */
export const ownName = (element) =>
  addressableName(element) || captionOf(element) || accessibleName(element);
/** @param {Element} element */
const saysItself = (element) =>
  element.matches(TEXT_BLOCK) ||
  (registry[element.localName]?.["x-word"] === "module" && element.lfSays?.()) ||
  [...element.childNodes].some(
    (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
  );
/** @param {Element | null | undefined} element */
export function addressableLabel(element) {
  if (!element) return "";
  const own = ownName(element);
  if (own) return own;
  if (saysItself(element)) return excerptWords(addressableSays(element), LABEL_WORDS);
  const scope = authoredScope(element);
  for (let at = upFrom(element); at && at !== scope; at = upFrom(at)) {
    const name = ownName(at);
    if (name) return name;
  }
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

// A thread's § coordinate and the visual-action picker both show it.
/** @param {Element | null | undefined} addressable */
export const sectionLabel = (addressable) =>
  [addressableWord(addressable), addressableLabel(addressable)]
    .filter(Boolean)
    .join(" · ");
