/* An element made in one call: its tag, its classes and the words it starts with.

   ```js
   const caption = el("p", "my-caption", "Before");
   ``` */

/** @template {keyof HTMLElementTagNameMap} K
 * @overload @param {K} tag @param {string} [cls] @param {string | null} [text]
 * @returns {HTMLElementTagNameMap[K]} */
/** @overload @param {string} tag @param {string} [cls] @param {string | null} [text]
 * @returns {HTMLElement} */
/** @param {string} tag @param {string} [cls] @param {string | null} [text] */
export function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
