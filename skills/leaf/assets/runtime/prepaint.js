// What a document Leaf's runtime will run in, served or exported, has to say before its
// first paint, which no module can reach: modules run once the document has parsed, and
// the browser paints what has arrived well before that. Delivery places this script
// after the head's canonical link, so the page root that link declares is in the
// document when it runs, and before the bootstrap and the theme (`compose_document`).
(() => {
  const root = document.documentElement;
  // The runtime will run here and upgrade the page's widgets, so the themes give each
  // widget the box its module will draw it at (`html[data-lf-interactive]`). A reading
  // with no runtime, a source file or a page with scripts off, keeps the readable
  // fallback, and only a served page draws the live chrome (`data-lf-live`, bootstrap.js).
  root.toggleAttribute("data-lf-interactive", true);

  // Whether the runtime could not start, which the same themes read to give back the
  // readable fallback a widget that will not upgrade needs, such as a tab set's stacked
  // panels (`data-lf-startup-error`). A fault is `incomplete` where something the page
  // needs did not arrive: its entry module or one it imports, its theme, or what the
  // page declares itself (`lf-startup-failed`). An uncaught error in code that did load,
  // before the page presents, is a fault too. Each is said once more as
  // `lf-startup-fault`, which a served page's bootstrap answers by waiting for a server
  // that can start the page (bootstrap.js); an export has no server to wait for.
  const fault = (reason, incomplete) => {
    root.dataset.lfStartupError = reason;
    window.dispatchEvent(
      new CustomEvent("lf-startup-fault", { detail: { reason, incomplete } }),
    );
  };
  window.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (
        target instanceof HTMLScriptElement &&
        target.matches("[type=module][data-lf-runtime]")
      )
        fault("entry module did not load", true);
      else if (
        target instanceof HTMLLinkElement &&
        target.matches("[rel=stylesheet][data-lf-runtime]")
      )
        fault("theme stylesheet did not load", true);
      else if (target === window && !document.body?.hasAttribute("data-lf-presented"))
        // A browser that treats the script as another origin gives "Script error." and
        // nothing else, so the file and line ride along: between them they are enough
        // to find the fault in a build nobody here can run.
        fault(
          `${event.message || "uncaught error"} (${event.filename || "?"}:${event.lineno ?? "?"})`,
          false,
        );
    },
    true,
  );
  window.addEventListener("lf-startup-failed", (event) =>
    fault(event.detail?.reason || "the page reported it could not start", true),
  );

  // Which page this document is, as the prefix of what the browser tab keeps for it.
  // Two leaf pages on one origin is what needs it: web storage is the origin's, so the
  // reading position a user left on one example was handed back on the next, at an
  // offset that meant nothing there. Read off the root the server declares in the
  // canonical link, a draft typed on the live root is the draft on each of its version
  // addresses. "" where that root is the origin's own, so a server serving one page
  // keeps every key unprefixed; an export, which has no server and no link, is its own
  // address. The runtime's stores read it from here (storage.js).
  const canonical = document.querySelector('link[rel="canonical"][data-lf-runtime]');
  const rootPath = canonical ? new URL(canonical.href).pathname : location.pathname;
  const scope = rootPath === "/" ? "" : rootPath;
  root.dataset.lfPageScope = scope;

  // A holder that shows one member at a time (`x-views`, painted `data-lf-views`) opens
  // on the member holding the element the address's fragment names, else on the member
  // this browser tab last showed, else on its first member. A reload puts the member
  // last shown first, because the address need not have followed what was shown: a set
  // below the page's own tab strip changes its member and leaves the fragment.
  const OPEN_KEY = `${scope}lf-open:`;
  const reloaded = performance.getEntriesByType("navigation")[0]?.type === "reload";
  const named = (members) => {
    if (!location.hash) return null;
    let target;
    try {
      target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    } catch {
      return null;
    }
    return target && members.find((member) => member.contains(target));
  };
  const kept = (holder, members) => {
    let id;
    try {
      id = sessionStorage.getItem(OPEN_KEY + holder.id);
    } catch {
      return null;
    }
    return members.find((member) => member.id === id);
  };
  const choose = (holder, members) =>
    (reloaded
      ? kept(holder, members) || named(members)
      : named(members) || kept(holder, members)) || members[0];

  // Until its module upgrades it, the holder's opening member wears `data-lf-opening`,
  // so its theme can show that member alone at first paint. Marked as the parser
  // inserts each holder and member, since a paint can come between any two of the
  // parser's tasks and never inside one, and a member parsed later may be the one that
  // opens. Parsing is over before any module runs, so nothing here races an upgrade.
  const OPENING = "data-lf-opening";
  const mark = () => {
    for (const holder of document.querySelectorAll("[data-lf-views]")) {
      const members = [...holder.children];
      const open = choose(holder, members);
      for (const member of members)
        if (member.hasAttribute(OPENING) !== (member === open))
          member.toggleAttribute(OPENING, member === open);
    }
  };
  const parsing = new MutationObserver(mark);
  parsing.observe(root, { childList: true, subtree: true });
  document.addEventListener(
    "readystatechange",
    () => {
      mark();
      parsing.disconnect();
    },
    { once: true },
  );

  // The marks under `node` taken off. No revision's markup carries them, so a copy of
  // the page taken to stand for what its author wrote is read without them.
  const unmarked = (node) => {
    for (const member of node.querySelectorAll(`[${OPENING}]`))
      member.removeAttribute(OPENING);
    return node;
  };

  // The holder's module asks once, as it upgrades, which member opens, and from then on
  // shows that member itself, so the mark comes off. It records each member it shows,
  // which a reload reopens (storage.js).
  root.lfViews = {
    unmarked,
    opening(holder, members) {
      for (const member of holder.querySelectorAll(`:scope > [${OPENING}]`))
        member.removeAttribute(OPENING);
      return choose(holder, members);
    },
    keep(holder, member) {
      try {
        sessionStorage.setItem(OPEN_KEY + holder.id, member.id);
      } catch {
        // A tab that cannot remember still shows the member.
      }
    },
  };
})();
