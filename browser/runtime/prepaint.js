// What a document Leaf's runtime will run in, served or exported, has to say before its
// first paint, which no module can reach: modules run once the document has parsed, and
// the browser paints what has arrived well before that. Delivery places this script
// after the head's canonical link, so the page root that link declares is in the
// document when it runs, and before the bootstrap and the theme (`compose_document`).
(() => {
  const root = document.documentElement;
  // A document reports faults only until it departs. A navigation away aborts the
  // document's requests, and those failures are the navigation's, not the page's.
  // Navigation in Chrome fires `pageswap` and `pagehide` before it rejects the
  // aborted requests. Iframe removal can reject them inside the native removal,
  // before pagehide or window.closed records the departure. Reports read lifetime
  // in the next task, once the native operation has finished.
  // Firefox has no `pageswap`, and it aborts the requests as soon as a `beforeunload`
  // lets the navigation start, while the document stays shown and running until the
  // destination answers. Neither engine says whether a navigation that has started
  // will replace the document: the user can stay at a leave prompt, and a link
  // answered with a download or a 204 leaves the document in place, its aborted
  // requests failed for good. So a fault that arrives after `beforeunload` waits.
  // `pageswap` or `pagehide` drops it with the document. The user's next press, key
  // or edit shows the document stayed, and the fault is reported then. A wheel turn
  // shows nothing, since a reader may scroll a page they are leaving while its
  // destination loads, and neither does the document's own first `pageshow`, which
  // can follow a prompt the user stayed at. Each report names the fault it reports,
  // and only the first report of a fault waits, so a read that keeps failing while
  // the user does nothing adds nothing. A persisted `pageshow` reopens the lifetime
  // when the browser restores the same document from its page cache, the faults that
  // waited having gone with the `pagehide`.
  let swapped = false;
  let departure = 0;
  let leaving = false;
  /** @type {Map<string, () => void>} */
  let waiting = new Map();
  window.lfDocumentLifetime = Object.freeze({
    /** Report after the current native operation, once known to have stayed, or never. */
    whenActive(fault, report) {
      const lifetime = departure;
      setTimeout(() => {
        if (window.closed || lifetime !== departure) return;
        if (!swapped && !leaving) report();
        else if (!swapped && !waiting.has(fault)) waiting.set(fault, report);
      });
    },
  });
  const stayed = () => {
    if (!leaving) return;
    leaving = false;
    const reports = waiting;
    waiting = new Map();
    for (const report of reports.values()) report();
  };
  window.addEventListener("beforeunload", () => {
    leaving = true;
  });
  for (const type of ["pageswap", "pagehide"])
    window.addEventListener(type, () => {
      departure++;
      swapped = true;
      waiting = new Map();
    });
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    swapped = false;
    leaving = false;
  });
  // The runtime will upgrade the widgets here. Styles reserve fixed control rows;
  // authored content stays readable while modules load. A source file or a page with
  // scripts off keeps that content, and only a served page draws the live chrome
  // (`data-lf-live`, bootstrap.js).
  root.toggleAttribute("data-lf-interactive", true);

  // The early input owner is delivered before this script. Page lifetime subscribes
  // to that same stream rather than making a second input listener.
  const inputs = /** @type {DocumentInputs} */ (
    Reflect.get(window, Symbol.for("leaf.inputs"))
  );
  inputs.observe((event) => {
    if (event.type !== "blur" && event.type !== "wheel") stayed();
  });

  // Whether the runtime could not start, named on the root (`data-lf-startup-error`)
  // for whatever reports it. A fault is `incomplete` where something the page needs
  // did not arrive: its entry module or one it imports, its theme, or what the page
  // declares itself (`lf-startup-failed`). Such a page upgrades nothing more, so the
  // mark above comes off and every widget still waiting gets back the readable
  // fallback the themes give a page without the runtime, such as a tab set's stacked
  // panels or a diagram's source in the column. An unrelated uncaught page error
  // need not prevent boot finishing: it reports the fault while keeping the runtime's
  // presentation until startup either completes or declares its own failure. A
  // declared fault may be
  // the page's own (`page`), as a module that staged words the page cannot read
  // (passages.js, `refusesBareText`): incomplete too, but no server fixes it. The
  // first fault names the page and is said once more as `lf-startup-fault`, which a
  // served page's bootstrap answers by saying the page has a problem where it is the
  // page's own, and otherwise by waiting for a server that can start the page
  // (bootstrap.js); an export has no server to wait for. A later fault only takes the
  // mark off where it is incomplete. The first is the earliest evidence and a later one
  // is often its consequence; the bootstrap's report keeps the first as well.
  /** @param {string} reason @param {boolean} incomplete @param {unknown} [error] @param {boolean} [page] */
  const fault = (reason, incomplete, error = null, page = false) =>
    window.lfDocumentLifetime.whenActive(`fault ${reason}`, () => {
      if (incomplete) {
        root.toggleAttribute("data-lf-interactive", false);
        for (const member of document.querySelectorAll("[data-lf-view]"))
          member.removeAttribute("hidden");
      }
      if (root.hasAttribute("data-lf-startup-error")) return;
      root.dataset.lfStartupError = reason;
      // The attribute is the short display reason; this record retains the actual
      // exception before modules load, including for an opaque sample's private port.
      root.lfStartupException =
        error !== null &&
        typeof error === "object" &&
        "message" in error &&
        typeof error.message === "string"
          ? {
              name:
                "name" in error && typeof error.name === "string"
                  ? error.name
                  : "Error",
              message: error.message,
              ...("stack" in error && typeof error.stack === "string"
                ? { stack: error.stack }
                : {}),
            }
          : null;
      window.dispatchEvent(
        new CustomEvent("lf-startup-fault", { detail: { reason, incomplete, page } }),
      );
    });
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
      else if (target === window && !document.body?.hasAttribute("data-lf-upgraded"))
        // A browser that treats the script as another origin gives "Script error." and
        // nothing else, so the file and line ride along: between them they are enough
        // to find the fault in a build nobody here can run.
        fault(
          `${event.message || "uncaught error"} (${event.filename || "?"}:${event.lineno ?? "?"})`,
          false,
          event.error ?? null,
        );
    },
    true,
  );
  window.addEventListener("lf-startup-failed", (event) =>
    fault(
      event.detail?.reason || "the page reported it could not start",
      true,
      event.detail?.error ?? null,
      event.detail?.page === true,
    ),
  );

  // Which page this document is, as the prefix of what the browser tab keeps for it.
  // Two leaf pages on one origin is what needs it: web storage is the origin's, so the
  // reading position a user left on one example was handed back on the next, at an
  // offset that meant nothing there. Read off the root the server declares in the
  // canonical link, a draft typed on the live root is the draft on each of its version
  // addresses. "" where that root is the origin's own, so a server serving one page
  // keeps every key unprefixed; an export, which has no server and no link, is its own
  // address. The runtime's stores read it from here (storage.js).
  const canonical = /** @type {HTMLLinkElement | null} */ (
    document.querySelector('link[rel="canonical"][data-lf-runtime]')
  );
  const rootPath = canonical ? new URL(canonical.href).pathname : location.pathname;
  const scope = rootPath === "/" ? "" : rootPath;
  root.dataset.lfPageScope = scope;

  // Tab memory has one storage policy, including before the module graph starts.
  // Widgets and later controllers read the same values.
  // Samples own disposable browser state in their realm. Choosing the backing here
  // keeps widget controllers, drafts and chrome on the same store,
  // without ever requesting storage denied to an opaque origin.
  /** @typedef {Pick<Storage, "length" | "key" | "getItem" | "setItem" | "removeItem">} StorageBacking */
  const memoryStore = root.hasAttribute("data-lf-sample")
    ? (() => {
        /** @type {Map<string, StorageBacking>} */
        const stores = new Map();
        /** @param {string} name */
        return (name) => {
          const held = stores.get(name);
          if (held) return held;
          /** @type {Map<string, string>} */
          const values = new Map();
          /** @type {StorageBacking} */
          const backing = {
            get length() {
              return values.size;
            },
            key(index) {
              return [...values.keys()][index] ?? null;
            },
            getItem(key) {
              return values.get(key) ?? null;
            },
            setItem(key, value) {
              values.set(key, String(value));
            },
            removeItem(key) {
              values.delete(key);
            },
          };
          stores.set(name, backing);
          return backing;
        };
      })()
    : null;
  /** @type {Window["lfStorage"]["stored"]} */
  const stored = (nativeOpen, name, prefix = "") => {
    const open = memoryStore ? () => memoryStore(name) : nativeOpen;
    return {
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
          const backing = open();
          return Array.from({ length: backing.length }, (_, index) =>
            backing.key(index),
          )
            .filter((key) => key !== null)
            .filter((key) => key.startsWith(prefix))
            .map((key) => key.slice(prefix.length));
        } catch {
          return [];
        }
      },
    };
  };
  const tabStore = stored(() => sessionStorage, "session", scope);
  const userStore = stored(() => localStorage, "local", root.dataset.lfUserScope ?? "");
  // Native URL parsing owns the classification before the first paint and for later
  // links. CSS draws the mark; no generated child can change a link's line breaks.
  /** @type {Window["lfLinks"]["opensElsewhere"]} */
  const opensElsewhere = (href) => {
    try {
      const url = href === null ? null : new URL(href, document.baseURI);
      return (
        url !== null &&
        ["http:", "https:"].includes(url.protocol) &&
        url.origin !== location.origin
      );
    } catch {
      return false;
    }
  };
  /** @type {Window["lfLinks"]["markExternalLink"]} */
  const markExternalLink = (link) => {
    if (link instanceof HTMLAnchorElement)
      link.toggleAttribute(
        "data-lf-external",
        opensElsewhere(link.getAttribute("href")),
      );
  };
  window.lfLinks = { opensElsewhere, markExternalLink };
  // Native disclosures work from the HTML parser onward. Restore and save at
  // that same lifetime, so upgrade never has to replay a toggle or overwrite
  // an early choice with a tab preference. The explicit key is presentation;
  // the authored widget remains untouched. This owner also retains each native
  // disclosure's parser-time default for the document source baseline.
  /** @type {WeakMap<Element, boolean>} */
  const disclosures = new WeakMap();
  /** @type {Window["lfStorage"]["keepDisclosure"]} */
  const keepDisclosure = (tree) => {
    if (disclosures.has(tree)) return;
    disclosures.set(tree, tree.open);
    const key = tree.dataset.lfOpenKey;
    const kept = key ? tabStore.get(key) : null;
    if (kept !== null && tree.open !== (kept === "open")) tree.open = kept === "open";
    if (key)
      tree.addEventListener("toggle", () =>
        tabStore.set(
          key,
          tree.open === disclosures.get(tree) ? null : tree.open ? "open" : "closed",
        ),
      );
  };
  // Only parser-time content needs this early watch. Once modules arrive, the
  // runtime's native-content arrival watch owns later links and disclosures,
  // including shadow stages. Query matching nodes rather than walking every child.
  /** @param {Document | Element} tree */
  const visit = (tree) => {
    if (tree instanceof HTMLAnchorElement) markExternalLink(tree);
    if (tree instanceof HTMLDetailsElement) keepDisclosure(tree);
    for (const node of tree.querySelectorAll("a, details"))
      if (node instanceof HTMLDetailsElement) keepDisclosure(node);
      else markExternalLink(node);
  };
  const earlyContent = new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.addedNodes) if (node instanceof Element) visit(node);
  });
  earlyContent.observe(document, { childList: true, subtree: true });
  window.lfStorage = {
    stored,
    tabStore,
    userStore,
    keepDisclosure,
    finishEarlyContent: () => earlyContent.disconnect(),
    // `open` reflects interaction, unlike an input's separate defaultChecked.
    // The source baseline reads this parser-time default, never the later live value.
    initialDisclosureOpen: (node) => disclosures.get(node),
  };

  // View selection is tab-local browser state from parsing through later switches.
  // Delivery carries the registry's member selector; only the browser evaluates it.
  // Readers leave the DOM alone. Showing a choice paints membership and native hidden.
  /** @type {WeakMap<Element, {selected: Element | null | false | undefined}>} */
  const viewStates = new WeakMap();
  /** @param {Element} holder @param {string | null} [selector] */
  const viewMembers = (
    holder,
    selector = holder.getAttribute("data-lf-view-members"),
  ) =>
    selector
      ? [...holder.children].filter(
          (child) => !child.hasAttribute("data-lf-gen") && child.matches(selector),
        )
      : [];
  const reloaded =
    /** @type {PerformanceNavigationTiming | undefined} */
    (performance.getEntriesByType("navigation")[0])?.type === "reload";
  const fragment = () => {
    try {
      return decodeURIComponent(location.hash.slice(1));
    } catch {
      return location.hash.slice(1);
    }
  };
  /** @param {Element} holder @param {Element[]} members */
  const chooseView = (holder, members) => {
    const ids = [fragment(), tabStore.get("lf-open:" + holder.id)];
    if (reloaded) ids.reverse();
    for (const id of ids) {
      if (!id) continue;
      const target = document.getElementById(id);
      // A later parser chunk may hold the intended destination. Never flash the
      // fallback before that target arrives, or parsing proves it absent.
      if (!target && document.readyState === "loading") return undefined;
      const member = target && members.find((member) => member.contains(target));
      if (member) return member;
    }
    return null;
  };
  /** @param {Element} holder @param {Element[]} members */
  const viewState = (holder, members) => {
    let state = viewStates.get(holder);
    if (!state || (state.selected && !members.includes(state.selected)))
      viewStates.set(holder, (state = { selected: undefined }));
    if (state.selected === undefined) state.selected = chooseView(holder, members);
    return state;
  };
  /** @param {Element} holder @param {Element | null | undefined} member @param {Element | null} [leaving] */
  const showView = (holder, member, leaving = null) => {
    const members = new Set(viewMembers(holder));
    for (const each of holder.children) {
      const wasMember = each.hasAttribute("data-lf-view");
      const isMember = members.has(each);
      if (wasMember !== isMember) each.toggleAttribute("data-lf-view", isMember);
      if (!isMember) {
        if (wasMember && each.getAttribute("hidden") === "until-found")
          each.removeAttribute("hidden");
      } else if (each === member || each === leaving) {
        if (each.hasAttribute("hidden")) each.removeAttribute("hidden");
      } else if (each.getAttribute("hidden") !== "until-found")
        each.setAttribute("hidden", "until-found");
    }
  };
  window.lfViews = {
    members: viewMembers,
    opening(holder, fallback = undefined, selector = undefined) {
      const members = viewMembers(holder, selector);
      const selected = viewState(holder, members).selected;
      return selected === false
        ? null
        : selected || (fallback === undefined ? members[0] : fallback);
    },
    keep(holder, member, leaving = null) {
      // null from source means implicit first; false is an explicit empty view.
      viewStates.set(holder, { selected: member ?? false });
      showView(holder, member, leaving);
      if (member)
        tabStore.set(
          "lf-open:" + holder.id,
          member.id || member.querySelector("[id]")?.id || null,
        );
    },
  };
  let shown = false;
  window.addEventListener(
    "pageshow",
    () => {
      shown = true;
    },
    { once: true },
  );
  document.addEventListener(
    "beforematch",
    (event) => {
      const member = event.target;
      if (
        member instanceof HTMLElement &&
        member.parentElement &&
        member.hasAttribute("data-lf-view")
      )
        if (reloaded && !shown && inputs.count === 0) {
          // Native reload fragment reveal must not override the saved view. Restore
          // after the browser removes hidden, before the next paint.
          requestAnimationFrame(initialViews);
        } else window.lfViews.keep(member.parentElement, member);
    },
    true,
  );
  const initialViews = () => {
    if (!root.hasAttribute("data-lf-interactive")) return;
    for (const holder of document.querySelectorAll("[data-lf-views]")) {
      const members = viewMembers(holder);
      const selected = viewState(holder, members).selected;
      showView(
        holder,
        selected === undefined || selected === false ? null : selected || members[0],
      );
    }
  };
  const parsingViews = new MutationObserver(initialViews);
  parsingViews.observe(document, { childList: true, subtree: true });
  document.addEventListener(
    "readystatechange",
    () => {
      initialViews();
      parsingViews.disconnect();
    },
    { once: true },
  );

  visit(document);
  // Read before bootstrap can hold a character for later dispatch. This same
  // preference supplies every active binding and its visible/accessible hints.
  const quickKey = "lf-quick-keyboard-shortcuts";
  let quick = userStore.get(quickKey) !== "false";
  window.lfKeyboard = {
    get quick() {
      return quick;
    },
    setQuick(on) {
      if (quick === on) return;
      quick = on;
      userStore.set(quickKey, String(on));
      document.dispatchEvent(new CustomEvent("lf-keyboard-preference"));
    },
  };

  // The floating panel (floating-panel.js) is the page's chrome. The reader's one
  // preference is the size the panel was left at (`row`, the comment field and its
  // counts, or `mark`, the leaf alone in the window's corner), one for every page on
  // the origin, read here so the first paint already stands at it.
  const restKey = "lf-chrome-rest";
  const restValues = ["row", "mark"];
  const storedRest = userStore.get(restKey);
  let rest = restValues.find((value) => value === storedRest) ?? "row";
  window.lfChrome = {
    get rest() {
      return rest;
    },
    setRest(value) {
      if (!restValues.includes(value) || rest === value) return;
      rest = value;
      userStore.set(restKey, value);
      document.dispatchEvent(new CustomEvent("lf-chrome-preference"));
    },
  };

  /** @type {LeafRootState["keeps"]} */
  const keepsAttribute = (node, name, value) => {
    if (!node) return;
    if (value == null) {
      if (node.hasAttribute(name)) node.removeAttribute(name);
    } else {
      const said = String(value);
      if (node.getAttribute(name) !== said) node.setAttribute(name, said);
    }
  };
  /** @type {WeakMap<Element, Set<string>>} */
  const runtimeAttributes = new WeakMap();
  /** @type {LeafRootState["setRuntimeRootAttribute"]} */
  const setRuntimeRootAttribute = (node, name, value) => {
    let attributes = runtimeAttributes.get(node);
    if (!attributes) runtimeAttributes.set(node, (attributes = new Set()));
    attributes.add(name);
    keepsAttribute(node, name, value);
  };
  /** @type {WeakMap<ElementCSSInlineStyle, Set<string>>} */
  const runtimeStyles = new WeakMap();
  /** @type {LeafRootState["setRuntimeRootStyle"]} */
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
  /** @type {LeafRootState["removeRuntimeRootStyle"]} */
  const removeRuntimeRootStyle = (node, property) => {
    runtimeStyles.get(node)?.delete(property);
    if (node.style.getPropertyValue(property)) node.style.removeProperty(property);
  };
  // What an element wears: attributes and custom properties written as one set, so a
  // later set removes what the earlier one had and the next does not (dress.js). The
  // root and body wear theirs as runtime root state, so a revision keeps it; any other
  // element is no root state, and writes plainly.
  /** @type {WeakMap<HTMLElement, LeafDress>} */
  const worn = new WeakMap();
  /** @type {LeafRootState["wear"]} */
  const wear = (node, dress) => {
    const { documentElement, body } = node.ownerDocument;
    const owned = node === documentElement || node === body;
    const previous = worn.get(node);
    for (const name of Object.keys(previous?.attributes ?? {}))
      if (!Object.hasOwn(dress.attributes, name))
        (owned ? setRuntimeRootAttribute : keepsAttribute)(node, name, null);
    for (const name of Object.keys(previous?.properties ?? {}))
      if (!Object.hasOwn(dress.properties, name))
        if (owned) removeRuntimeRootStyle(node, name);
        else node.style.removeProperty(name);
    for (const [name, value] of Object.entries(dress.attributes))
      (owned ? setRuntimeRootAttribute : keepsAttribute)(node, name, value);
    for (const [name, value] of Object.entries(dress.properties))
      if (owned) setRuntimeRootStyle(node, name, value);
      else node.style.setProperty(name, value);
    worn.set(node, dress);
  };
  window.lfRootState = {
    keeps: keepsAttribute,
    setRuntimeRootAttribute,
    setRuntimeRootStyle,
    removeRuntimeRootStyle,
    wear,
    attributes: (node) => new Set(runtimeAttributes.get(node) ?? []),
    styles: (node) => new Set(runtimeStyles.get(node) ?? []),
  };
})();
