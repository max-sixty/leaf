/* An element made in one call: its tag, its classes and the words it starts with.

   ```js
   const caption = el("p", "my-caption", "Before");
   ``` */

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  cls?: string,
  text?: string | null,
): HTMLElementTagNameMap[K];
export function el(tag: string, cls?: string, text?: string | null): HTMLElement;
export function el(tag: string, cls?: string, text?: string | null) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
