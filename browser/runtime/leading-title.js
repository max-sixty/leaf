/* What names an element, where the authoring contract gives it a name
 * (`skills/leaf/references/module-reading.md`, "Naming elements"): a leading disclosure
 * summary, heading, or <strong>, looked for inside a leading <header> or <hgroup> too.
 * A section is named by its heading, a disclosure by its summary, a titled member by its
 * <strong>, and a widget the same way, so a tab, a column or a playground control holds
 * its name as markup. Leading means no words come before it; elements may, as a titled
 * member's comparison chips stand in the band above its title and an eyebrow above a
 * section's heading (`leadingTitle`). Chrome inside the element names nothing, asked
 * about the element's own insides, since a widget an agent sent in a reply stands
 * inside the floating panel's chrome and its heading is still its name.
 *
 * A widget takes its name only where it opens the widget (`openingTitle`): the title,
 * or the <header> or <hgroup> holding it, is the widget's first element. A quoted
 * sample whose second paragraph is a heading keeps the heading where it stands rather
 * than lifting it into its note, and a tab whose heading follows a paragraph is unnamed,
 * which `page check` refuses (`unnamed-view`). The theme's selector for the element
 * holding it is `:first-child:is(summary, h1, h2, h3, h4, h5, h6, strong, header,
 * hgroup)`. Packages read only that title (portable-api.js), which `page check` holds
 * every widget's name to; the leading title, which a section's or an option's label
 * reads past an eyebrow or chips, stays the runtime's (addressable-names.js).
 *
 * It reads only the element's children, so it loads in any document: a widget that runs
 * on a plain page names its parts by the same rule. The server reads the same rule off
 * the document (`gesture_words.leading_title`, `leading_title_holder`), and
 * `tests/name_cases.json` holds both runtimes to the same cases.
 *
 * Replaced: a registry entry could declare one of its attributes as its element's
 * name, as a tab's `label` was. An attribute holds only text, so a tab listing
 * files could not set a name in code type or colour a diffstat, and its words stood
 * outside the page's elements, where page check, comment anchoring and the version
 * diff read. */
import { uiInside } from "./shadow-tree.js";

const TITLES = "summary, h1, h2, h3, h4, h5, h6, strong";

/** The element whose words name `container` by that rule, or null.
 * @param {Element} container @returns {Element | null} */
export function leadingTitle(container) {
  for (const node of container.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) return null;
    if (!(node instanceof Element) || uiInside(node, container)) continue;
    if (node.matches(TITLES)) return node;
    if (["header", "hgroup"].includes(node.localName)) return leadingTitle(node);
  }
  return null;
}

/** The title naming `container` where it opens it: the title itself, or the one in the
 * <header> or <hgroup> that is `container`'s first element; null otherwise. The element
 * a widget draws, moves or hides as its name is its child holding this title.
 * @param {Element} container @returns {Element | null} */
export function openingTitle(container) {
  const title = leadingTitle(container);
  if (!title) return null;
  const first = [...container.children].find((child) => !uiInside(child, container));
  return first?.contains(title) ? title : null;
}
