/* Where a finding is, in words its author can find in the source.
 *
 * A finding is read by whoever wrote the page, usually an agent that cannot see it
 * drawn, so a bare `<code>` on a page holding forty of them names nothing. An element
 * with an id is named by it. One without is named with the nearest element that has
 * one, across any shadow root between them, since ids are what the author wrote and
 * what `page state` addresses content by.
 *
 * Written once, for the reason `open-roots.js` is: a probe that names elements its own
 * way reports the same box under two names. */
const tag = (el) => `<${el.localName}${el.id ? " id=" + el.id : ""}>`;

export const at = (el) => {
  if (!el?.localName) return "<?>";
  if (el.id) return tag(el);
  for (let node = el; node; node = node.getRootNode?.()?.host) {
    const named = node.closest?.("[id]");
    if (named) return `${tag(el)} in ${tag(named)}`;
  }
  return tag(el);
};
