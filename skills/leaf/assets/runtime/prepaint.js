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

  // Whether the runtime could not start, named on the root (`data-lf-startup-error`)
  // for whatever reports it. A fault is `incomplete` where something the page needs
  // did not arrive: its entry module or one it imports, its theme, or what the page
  // declares itself (`lf-startup-failed`). Such a page upgrades nothing more, so the
  // mark above comes off and every widget still waiting gets back the readable
  // fallback the themes give a page without the runtime, such as a tab set's stacked
  // panels or a diagram's source in the column. An uncaught error in code that did
  // load, before the page presents, is a fault too, but the page may still present
  // with everything it has, so its widgets keep their boxes. Each fault is said once
  // more as `lf-startup-fault`, which a served page's bootstrap answers by waiting for
  // a server that can start the page (bootstrap.js); an export has no server to wait
  // for.
  const fault = (reason, incomplete) => {
    if (incomplete) root.toggleAttribute("data-lf-interactive", false);
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

  // Tab memory has one storage policy, including before the module graph starts.
  // Initial package drawings and their later controllers read the same values.
  const stored = (open, name, prefix = "") => ({
    read(key) {
      try {
        return { available: true, value: open().getItem(prefix + key) };
      } catch {
        return { available: false, value: null };
      }
    },
    get(key) {
      return this.read(key).value;
    },
    set(key, value) {
      try {
        if (value === null) open().removeItem(prefix + key);
        else open().setItem(prefix + key, value);
        return true;
      } catch {
        return false;
      }
    },
    where(key) {
      return { store: name, key: prefix + key };
    },
    keys() {
      try {
        return Object.keys(open())
          .filter((key) => key.startsWith(prefix))
          .map((key) => key.slice(prefix.length));
      } catch {
        return [];
      }
    },
  });
  const tabStore = stored(() => sessionStorage, "session", scope);
  root.lfStorage = { stored, tabStore };

  // A package's synchronous producer draws real instance markup before modules can
  // run. Delivery calls paint just after the parser closes each declared host; the
  // module calls it again to adopt those exact nodes, or to draw a later arrival.
  // Only mechanical tab state enters this drawing. Semantic initial values still
  // come from the authored document, so keep its original structure and node routes
  // before a producer moves or replaces anything. These inert copies are the source
  // of version comparison, never current application state.
  const producers = new Map();
  const drawings = new WeakMap();
  const sources = new WeakMap();
  const sourceScopes = new WeakSet();
  const sourceShells = new WeakMap();
  // Initial geometry writes a root style before modules exist. Later root writers
  // adopt this same registry, so a revision replaces only the authored share.
  const runtimeStyles = new WeakMap();
  const setRuntimeRootStyle = (node, property, value, priority = "") => {
    let properties = runtimeStyles.get(node);
    if (!properties) runtimeStyles.set(node, (properties = new Set()));
    properties.add(property);
    if (
      node.style.getPropertyValue(property) !== value ||
      node.style.getPropertyPriority(property) !== priority
    )
      node.style.setProperty(property, value, priority);
  };
  const removeRuntimeRootStyle = (node, property) => {
    runtimeStyles.get(node)?.delete(property);
    if (node.style.getPropertyValue(property)) node.style.removeProperty(property);
  };
  const origins = new WeakMap();
  const parents = new WeakMap();
  const keepsAttribute = (node, name, value) => {
    if (node.getAttribute(name) !== value) node.setAttribute(name, value);
  };
  const offerElement = (node, cls, pressable = false) => {
    if (node instanceof HTMLButtonElement && !node.hasAttribute("type"))
      keepsAttribute(node, "type", "button");
    const face = node.localName.includes("-") ? "" : " lf-ui-face";
    keepsAttribute(node, "class", `${cls ? `${cls} ` : ""}lf-ui${face}`);
    keepsAttribute(node, "data-lf-gen", "1");
    // Native summary is the browser's disclosure press, without a type property
    // or a specialized HTML element class. Its offer must name that same control.
    keepsAttribute(
      node,
      "data-lf-offer",
      pressable
        ? node.localName
        : node instanceof HTMLButtonElement ||
            node.localName === "summary" ||
            (node.localName === "input" && ["checkbox", "radio"].includes(node.type))
          ? (node.type ?? node.localName)
          : "",
    );
    return node;
  };
  const offer = (tag, cls, label, inputType, pressable = false) => {
    const node = document.createElement(tag);
    if (inputType !== undefined) {
      if (tag !== "input")
        throw new TypeError("only an input offer can declare an input type");
      node.type = inputType;
    }
    offerElement(node, cls, pressable);
    if (label !== undefined) node.textContent = label;
    return node;
  };
  const authoredCopy = (node, target = null) => {
    if (target === null) {
      // A cloned live document retains custom-element definitions, so attaching
      // its source tree could run widget constructors and connected callbacks.
      // Import into a document with no browsing context or widget registry instead.
      target = document.implementation.createHTMLDocument("");
      target.replaceChildren();
    }
    const source = sources.get(node) ?? node;
    const copy =
      source.nodeType === Node.DOCUMENT_NODE
        ? target
        : target.importNode(sourceShells.get(source) ?? source, false);
    origins.set(copy, origins.get(source) ?? node);
    copy.removeAttribute?.("data-lf-opening");
    const held = source.localName === "template" ? source.content : source;
    const into = copy.localName === "template" ? copy.content : copy;
    if (source.localName === "template") origins.set(into, origins.get(held) ?? held);
    for (const child of held.childNodes) {
      if (child.matches?.("[data-lf-prepaint], script[data-lf-initial]")) continue;
      into.append(authoredCopy(child, target));
    }
    return copy;
  };
  const rememberSource = (source) => {
    sources.set(origins.get(source), source);
    const held = source.localName === "template" ? source.content : source;
    for (const child of held.childNodes) rememberSource(child);
  };
  // Margin residency is initial document geometry, not a widget upgrade. The parser
  // observer seats authored residents before a frame can paint them in another
  // posture; content-layout adopts this same computation for subsequent changes.
  // The body's authored annotation declaration is the same executable fact the
  // module graph reads, so rail admission needs no second delivery configuration.
  const POSTURES = {
    sidebar: ["left", "--sidebar"],
    map: ["left", "--map"],
    note: ["right", "--note"],
  };
  // The nearest painted ancestor distinguishes skipped contents from a box the page
  // hides itself. Geometry adopts this same reading with its composed-parent walk.
  const skipped = (element, parent = (node) => node.parentElement) => {
    if (element.checkVisibility()) return false;
    let child = element;
    let box = parent(element);
    while (box && !box.checkVisibility()) {
      child = box;
      box = parent(box);
    }
    if (!box) return false;
    if (box.localName === "details") return !box.open && child.localName !== "summary";
    return getComputedStyle(box).contentVisibility === "hidden";
  };
  const residency = () => {
    const main = document.querySelector("main");
    if (!main) return false;
    const style = getComputedStyle(main);
    const need = (token) => parseFloat(style.getPropertyValue(token)) || 0;
    // Remove only the physical offset the shell's grid tracks actually apply. An
    // author's relative offset remains part of the available room. Read rendered
    // tracks rather than the last written shift, including under RTL.
    const shellStyle = getComputedStyle(document.body);
    const tracks = shellStyle.gridTemplateColumns.split(" ").map(parseFloat);
    const canShift = shellStyle.display === "grid" && style.gridColumnStart === "2";
    const gridShift = canShift
      ? ((tracks[0] - tracks.at(-1)) / 2) * (shellStyle.direction === "rtl" ? -1 : 1)
      : 0;
    const shifted = gridShift;
    const shellWritten =
      parseFloat(document.body.style.getPropertyValue("--lf-column-shift")) || 0;
    const column = main.getBoundingClientRect();
    const shell = document.body.getBoundingClientRect();
    const room = {
      left: column.left - shifted - shell.left,
      right: shell.right - column.right + shifted,
    };
    const taken = { left: 0, right: 0 };
    const standing = [];
    if (
      (document.body.dataset.annotations ?? "overlay") === "overlay" &&
      document.body.getAttribute("data-rail") !== "none" &&
      room.right >= need("--rail")
    ) {
      standing.push("rail");
      taken.right = need("--rail");
    }
    const declared = new Map();
    // A resident a box around it hides (a closed disclosure, a tab not chosen) needs no
    // room. One the page hides itself stays a resident, since a page may hide it until it
    // stands in the margin.
    for (const aside of main.querySelectorAll("aside")) {
      if (skipped(aside)) continue;
      const own = getComputedStyle(aside);
      const hiddenItself =
        own.display === "none" && aside.parentElement.checkVisibility();
      if (!aside.checkVisibility() && !hiddenItself) continue;
      const postures = own
        .getPropertyValue("--lf-resident")
        .split(" ")
        .filter((posture) => posture in POSTURES);
      if (postures.length) declared.set(postures.join(" "), postures);
    }
    const side = (postures) => POSTURES[postures[0]][0];
    for (const postures of [...declared.values()].sort(
      (a, b) => (side(a) === "left" ? 0 : 1) - (side(b) === "left" ? 0 : 1),
    ))
      for (const posture of postures) {
        const [at, token] = POSTURES[posture];
        const wants = { ...taken, [at]: Math.max(taken[at], need(token)) };
        if (wants.left + wants.right > room.left + room.right + 0.5) continue;
        // An authored shell can override the grid. It still admits residents where
        // they fit, but cannot promise room that only moving the column would supply.
        if (!canShift && (wants.left > room.left || wants.right > room.right)) continue;
        standing.push(posture);
        Object.assign(taken, wants);
        break;
      }
    const shift = Math.round(
      taken.left > room.left
        ? taken.left - room.left
        : taken.right > room.right
          ? room.right - taken.right
          : 0,
    );
    const tokens = standing.join(" ");
    const seated = (main.getAttribute("data-lf-margin") ?? "") !== tokens;
    if (!seated && shift === shellWritten) return false;
    // Source copies keep the authored shell before initial geometry writes to it;
    // children still follow their original routes as the parser continues.
    if (!sourceShells.has(main)) sourceShells.set(main, main.cloneNode(false));
    if (!sourceShells.has(document.body))
      sourceShells.set(document.body, document.body.cloneNode(false));
    if (seated) {
      if (tokens) main.setAttribute("data-lf-margin", tokens);
      else main.removeAttribute("data-lf-margin");
    }
    // Module-time adoption announces changed seats to reading-region discovery;
    // before upgrade the same attributes already provide the final authored box.
    if (shift) setRuntimeRootStyle(document.body, "--lf-column-shift", `${shift}px`);
    else removeRuntimeRootStyle(document.body, "--lf-column-shift");
    return true;
  };

  root.lfInitial = {
    setRuntimeRootStyle,
    removeRuntimeRootStyle,
    runtimeRootStyles: (node) => new Set(runtimeStyles.get(node) ?? []),
    authoredShell: (node) => sourceShells.get(node) ?? sources.get(node) ?? node,
    residency,
    skipped,
    register(tag, render) {
      // The widget loader imports unregistered producers for later revisions and
      // thread markup that were absent from the initially delivered document.
      if (!producers.has(tag)) producers.set(tag, render);
    },
    has(tag) {
      return producers.has(tag);
    },
    paint(host) {
      if (drawings.has(host)) return drawings.get(host);
      const render = producers.get(host.localName);
      if (!render) throw new Error(`no initial renderer for <${host.localName}>`);
      for (const node of [host, ...host.querySelectorAll("*")])
        if (!parents.has(node)) parents.set(node, node.parentElement);
      rememberSource(authoredCopy(host));
      for (let node = host; node; node = node.parentNode) sourceScopes.add(node);
      const drawing = render(host, { tabStore, offer, offerElement });
      if (drawing?.then)
        throw new TypeError(
          `initial renderer for <${host.localName}> must be synchronous`,
        );
      drawings.set(host, drawing);
      return drawing;
    },
    mount(template) {
      const host = template.content.firstElementChild;
      // The host stays inert while any part of its source is still arriving. Put
      // its complete source in place, then draw deepest-first in this same task:
      // no frame can show an unfinished or uninitialized instance.
      template.replaceWith(host);
      for (const node of [host, ...host.querySelectorAll("*")].reverse())
        if (producers.has(node.localName)) this.paint(node);
    },
    restoreSource(root) {
      for (const template of root.querySelectorAll("template[data-lf-initial-source]"))
        template.replaceWith(template.content);
      for (const delivery of root.querySelectorAll("script[data-lf-initial]"))
        delivery.remove();
      for (const placeholder of root.querySelectorAll("[data-lf-prepaint]"))
        placeholder.remove();
      return root;
    },
    authoredCopy,
    reading(node) {
      return sources.get(node) ?? (sourceScopes.has(node) ? authoredCopy(node) : node);
    },
    offer,
    offerElement,
    origin(node) {
      return origins.get(node);
    },
    parent(node) {
      return parents.has(node) ? parents.get(node) : node.parentElement;
    },
  };

  // A holder that shows one member at a time (`x-views`, painted `data-lf-views`) opens
  // on the member holding the element the address's fragment names, else on the member
  // this browser tab last showed, else on its first member. A reload puts the member
  // last shown first, because the address need not have followed what was shown: a set
  // below the page's own tab strip changes its member and leaves the fragment.
  const OPEN_KEY = "lf-open:";
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
    const id = tabStore.get(OPEN_KEY + holder.id);
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
  const initialLayout = () => {
    mark();
    residency();
  };
  const parsing = new MutationObserver(initialLayout);
  parsing.observe(root, { childList: true, subtree: true });
  document.addEventListener(
    "readystatechange",
    () => {
      initialLayout();
      parsing.disconnect();
    },
    { once: true },
  );

  // The holder's module asks once, as it upgrades, which member opens, and from then on
  // shows that member itself, so the mark comes off. It records each member it shows,
  // which a reload reopens (storage.js).
  root.lfViews = {
    opening(holder, members) {
      for (const member of holder.querySelectorAll(`:scope > [${OPENING}]`))
        member.removeAttribute(OPENING);
      return choose(holder, members);
    },
    keep(holder, member) {
      tabStore.set(OPEN_KEY + holder.id, member.id);
    },
  };
})();
