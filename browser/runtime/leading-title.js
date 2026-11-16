/* What names an element, where the authoring contract gives it a name
 * (`skills/leaf/references/module-reading.md`, "Naming elements"): a leading disclosure
 * summary, heading, or <strong>, looked for inside a leading <header> or <hgroup> too.
 * A section is named by its heading, a disclosure by its summary, a titled member by its
 * <strong>, and a widget the same way, so a tab, a column or a playground control holds
 * its name as markup. Leading means no words come before it; elements may, as a titled
 * member's comparison chips stand in the band above its title and an eyebrow above a
 * header's heading. Chrome inside the element names nothing, asked about the element's
 * own insides, since a widget an agent sent in a reply stands inside the floating
 * panel's chrome and its heading is still its name.
 *
 * It reads only the element's children, so it loads in any document (portable-api.js):
 * a widget that runs on a plain page names its parts by the same rule. On a Leaf page,
 * addressable-names.js keeps each answer with the page reading and reads the name's
 * words; the server reads the same rule off the document (`gesture_words.element_name`),
 * and `tests/name_cases.json` holds both runtimes to the same cases.
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
