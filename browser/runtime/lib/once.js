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

/** True on `el`'s first connection, and false on every later one. A clone is another
 * element, so it starts its own lifetime. */
export function once(el) {
  if (initialized.has(el)) return false;
  initialized.add(el);
  return true;
}
