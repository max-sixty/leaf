// Compiled from elements.ts by build/typescript.mjs; edit that file.
/* An element made in one call: its tag, its classes and the words it starts with.

   ```js
   const caption = el("p", "my-caption", "Before");
   ``` */

export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
