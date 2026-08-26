// ---------- where a page's versions are ----------
// A page directory's versions are served as siblings under its own root:
// versions/v1.html, v2.html… Three things read that path — which version this document
// is, where another version of it is, and which page a tab's working state belongs
// to — so the shape is spelled once here rather than three times, and a document served
// under a directory of its own cannot have one of them agreeing with its URL while the
// next two contradict it.
export const VERSION_PATH = /\/versions\/v([1-9]\d*)\.html$/;
// Where another version is: beside this one. It was "/versions/vN.html" at the three
// seats that travel, which is a claim about where the page directory sits — true of a
// server serving one page at a root of its own, and of nothing else. The published site
// serves every example from one vendored layer with each page under its own directory,
// and there each absolute jump left the page for a root that serves nothing. Resolved
// against the document, the travel agrees with the path the version number itself was
// read off, which is the one form that cannot disagree with what this document is.
export const versionUrl = (version) =>
  `${location.pathname.match(VERSION_PATH) ? "" : "versions/"}v${version}.html`;
// Which page this document belongs to, as a prefix for what the tab keeps: "" wherever a
// server serves one page at its own root, so every key below is spelled exactly as it was.
// Two leaf pages on one origin is what needs it — web storage is the origin's, so the
// reading position a reader left on one example was handed back on the next, at an offset
// that meant nothing there.
export const PAGE_SCOPE =
  location.pathname === "/" ? "" : location.pathname.replace(VERSION_PATH, "");

// ---------- what the page keeps, and what a store may refuse ----------
// Reading or writing web storage throws outright where the browser has it switched off —
// a locked-down profile, a private window on some engines — and nothing kept here is
// worth breaking the page for: a reader who cannot save which tab they were on still
// gets the page. Said once, because a policy spelled at each caller is a policy free to
// be spelled differently at the next one, and eleven of them had accumulated across the
// runtime and two widget modules.
//
// Which store is the part worth reading at a call site, and naming them is what puts it
// there. `tabStore` is this window's working state and dies with the tab — the reading
// position, which panel of a widget stands open, whether design mode is on — because each
// of those is about the window rather than about the page. `draftStore` is what the user
// typed and hasn't sent: it outlives the tab, because closing one is the ordinary end of
// a tab here, and every tab shows one live copy of it (see the draft section below).
// `readerStore` is this reader's standing preference across pages, which is the chrome
// they arrange and expect to find arranged. Anything two tabs must *agree* about is none
// of the three: it goes in the log.
//
// Values are the store's own vocabulary, strings and null, so nothing here has an
// opinion about encoding: an absent key reads back as null, and writing null removes it.
const stored = (open, name, scope = "") => ({
  read(key) {
    try {
      return { available: true, value: open().getItem(scope + key) };
    } catch {
      return { available: false, value: null };
    }
  },
  get(key) {
    return this.read(key).value;
  },
  set(key, value) {
    try {
      if (value === null) open().removeItem(scope + key);
      else open().setItem(scope + key, value);
      return true;
    } catch {
      /* a page that cannot remember still renders */
      return false;
    }
  },
  // Where this store puts a key, as the platform's own two names for its stores plus
  // the key the backing actually holds. Only the browser gate asks: it seeds a store
  // before the page has run, so it cannot ask a store that does not exist yet, and the
  // alternative is a second copy of the scope rule kept over there to go stale.
  where(key) {
    return {
      store: name,
      key: scope + key,
    };
  },
  // What this scope holds, spelled as the callers spell it. The drafts are what needs
  // it: a composer's key is the passage it is on, so which draft to reopen at load is a
  // question about the set rather than about a key someone already knows.
  keys() {
    try {
      return Object.keys(open())
        .filter((key) => key.startsWith(scope))
        .map((key) => key.slice(scope.length));
    } catch {
      return [];
    }
  },
});
// Two of the three are scoped to the page (PAGE_SCOPE), and the odd one out is the reason
// there are three backings: what the reader arranges is theirs wherever they are reading,
// while what they typed here belongs to this page. tabStore is the only one on the helper
// surface, because only widgets keep working state (lf-tabs' open panel, lf-options'
// collapsed group) — a module reaches its drafts through saveDraft/watchDraft, the chrome
// the reader arranges is the runtime's own, and an export nothing imports is a promise
// nobody asked for.
export const tabStore = stored(() => sessionStorage, "session", PAGE_SCOPE);
export const draftStore = stored(() => localStorage, "local", PAGE_SCOPE);
export const readerStore = stored(() => localStorage, "local");
