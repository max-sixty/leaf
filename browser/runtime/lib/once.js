// Compiled from once.ts by build/typescript.mjs; edit that file.
/* Whether an element is connecting for the first time: the guard a custom element's
   `connectedCallback` builds behind, since the callback runs again each time something
   moves the element or takes it out of the page and puts it back.

   ```js
   connectedCallback() {
     if (!once(this)) return;
     // build what the element builds once
   }
   ``` */

const initialized = new WeakSet();

// Whether `el` stands in this window's document, the only one where an element
// initializes. A copy in a document of its own stays markup in every engine but one:
// Firefox (160), asked for the contents of a selection a drag carried through a shadow
// root (`Range.cloneContents`), copies the Document itself, and upgrades and connects
// the custom elements it copies into that copy before it throws. Highlighter extensions
// read each selection the user makes that way. The check goes once Firefox clones the
// range alone (`test_firefox_s_copy_of_a_group_builds_no_add_field`).
export const inWindowDocument = (el) => el.ownerDocument === document;

/** True on `el`'s first connection in this window's document, and false on every later
 * one. A clone is another element, so it starts its own lifetime, and a copy connected
 * outside the window's document (`inWindowDocument`) never initializes. */
export function once(el) {
  if (initialized.has(el) || !inWindowDocument(el)) return false;
  initialized.add(el);
  return true;
}
