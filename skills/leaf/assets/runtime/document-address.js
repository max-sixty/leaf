/* Which address this document is: its path, whether it is the live root, the page
   root every page operation resolves against, and the share address a keyed
   transport declares. Read once from the served document; imports nothing. */

// Which version a document is comes from its served `lf-version` marker
// (`document-identity.js`), and where another version is from that version's `url` in
// the state reading, which the server addresses at the page root. Neither is read off
// this path.
const PAGE_PATH = location.pathname;
// The live root follows the active revision in place; a virtual version address
// (`versions/vN.html`) stays pinned to its mapped revision.
export const LIVE_ROOT = PAGE_PATH.endsWith("/");
// Which page this document belongs to. The server declares the page's root in the
// canonical link it adds to every document it serves, the live root and each version
// address alike, and every page operation resolves against it. An interactive export
// has no server and no link, so no root: the file is the page.
export const PAGE_ROOT =
  document.querySelector('link[rel="canonical"][data-lf-runtime]')?.href ?? null;
// A keyed transport declares its share address even on a cookie-authorized reload.
// Samples and the public website have no share address. Preserve the current
// version path, query and passage while taking access from the transport's URL.
export const SHARE_ROOT = document.querySelector(
  "script[data-lf-runtime][data-lf-server]",
)?.dataset.lfShareUrl;
export function shareUrl() {
  const url = new URL(SHARE_ROOT);
  url.pathname = location.pathname;
  const access = [...url.searchParams];
  url.search = location.search;
  for (const [key, value] of access) url.searchParams.set(key, value);
  url.hash = location.hash;
  return url.href;
}
