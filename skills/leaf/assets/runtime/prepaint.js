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

  // Inputs belong to this document from its first script, even while the module
  // graph is still loading. Delayed arrival work must not take focus or scroll
  // back from someone already using the authored page. focus.js exposes this
  // same counter and subscription after startup; no later listener starts over.
  let inputs = 0;
  const inputReaders = new Set();
  root.lfInputs = {
    get count() {
      return inputs;
    },
    observe(read) {
      inputReaders.add(read);
      return () => inputReaders.delete(read);
    },
  };
  const input = (event) => {
    if (event.type === "blur" && event.target !== window) return;
    inputs++;
    for (const read of inputReaders) read(event);
  };
  for (const type of ["pointerdown", "keydown", "input", "wheel", "touchstart", "blur"])
    window.addEventListener(type, input, { capture: true, passive: true });

  // Whether the runtime could not start, named on the root (`data-lf-startup-error`)
  // for whatever reports it. A fault is `incomplete` where something the page needs
  // did not arrive: its entry module or one it imports, its theme, or what the page
  // declares itself (`lf-startup-failed`). Such a page upgrades nothing more, so the
  // mark above comes off and every widget still waiting gets back the readable
  // fallback the themes give a page without the runtime, such as a tab set's stacked
  // panels or a diagram's source in the column. An uncaught error in code that did
  // load, before the page presents, is a fault too, but the page may still present
  // with everything it has, so its widgets keep their boxes. A declared fault may be
  // the page's own (`page`), as a module that staged words the page cannot read
  // (passages.js, `refusesBareText`): incomplete too, but no server fixes it. The
  // first fault names the page and is said once more as `lf-startup-fault`, which a
  // served page's bootstrap answers by saying the page has a problem where it is the
  // page's own, and otherwise by waiting for a server that can start the page
  // (bootstrap.js); an export has no server to wait for. A later fault only takes the
  // mark off where it is incomplete. The first is the earliest evidence and a later one
  // is often its consequence; the bootstrap's report keeps the first as well.
  const fault = (reason, incomplete, error = null, page = false) => {
    if (incomplete) root.toggleAttribute("data-lf-interactive", false);
    if (root.hasAttribute("data-lf-startup-error")) return;
    root.dataset.lfStartupError = reason;
    // The attribute is the short display reason; this record retains the actual
    // exception before modules load, including for an opaque sample's private port.
    root.lfStartupException =
      error?.message === undefined
        ? null
        : {
            name: error.name,
            message: error.message,
            stack: error.stack,
          };
    window.dispatchEvent(
      new CustomEvent("lf-startup-fault", { detail: { reason, incomplete, page } }),
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
  const canonical = document.querySelector('link[rel="canonical"][data-lf-runtime]');
  const rootPath = canonical ? new URL(canonical.href).pathname : location.pathname;
  const scope = rootPath === "/" ? "" : rootPath;
  root.dataset.lfPageScope = scope;

  // Tab memory has one storage policy, including before the module graph starts.
  // Initial package drawings and their later controllers read the same values.
  // Samples own disposable browser state in their realm. Choosing the backing here
  // keeps early drawings, widget controllers, drafts and chrome on the same store,
  // without ever requesting storage denied to an opaque origin.
  const memoryStores = root.hasAttribute("data-lf-sample") ? new Map() : null;
  const memoryStore = (name) => {
    if (!memoryStores.has(name)) {
      const values = new Map();
      memoryStores.set(name, {
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
      });
    }
    return memoryStores.get(name);
  };
  const stored = (nativeOpen, name, prefix = "") => {
    const open = memoryStores ? () => memoryStore(name) : nativeOpen;
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
            .filter((key) => key !== null && key.startsWith(prefix))
            .map((key) => key.slice(prefix.length));
        } catch {
          return [];
        }
      },
    };
  };
  const tabStore = stored(() => sessionStorage, "session", scope);
  const userStore = stored(() => localStorage, "local", root.dataset.lfUserScope ?? "");
  root.lfStorage = { stored, tabStore, userStore };
  // Read before bootstrap can hold a character for later dispatch. This same
  // preference supplies every active binding and its visible/accessible hints.
  const quickKey = "lf-quick-keyboard-shortcuts";
  let quick = userStore.get(quickKey) !== "false";
  root.lfKeyboard = {
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

  // Which chrome the user reads the page with: the banner and bottom bar (`classic`,
  // the default) or the floating panel (`floating`, floating-panel.js), with the size the
  // panel was left at (`row`, the comment field and its counts, or `mark`, the leaf
  // alone in the window's corner). One preference for every page on
  // the origin, read here because the classic bars' room is reserved before the
  // first paint (theme.css). `?lf-chrome=floating` or `?lf-chrome=classic` sets it. A
  // sample child takes its parent's choice, or its element's, in its settings
  // (sample.js), since its store is its own.
  const chromeKeys = {
    mode: "lf-chrome",
    rest: "lf-chrome-rest",
  };
  const chromeValues = {
    mode: ["classic", "floating"],
    rest: ["row", "mark"],
  };
  const chrome = {};
  const paintChrome = () => {
    const floating = chrome.mode === "floating";
    const write = (name, value) => {
      if (root.getAttribute(name) !== value)
        if (value === null) root.removeAttribute(name);
        else root.setAttribute(name, value);
    };
    write("data-lf-floating-chrome", floating ? "" : null);
  };
  for (const [name, key] of Object.entries(chromeKeys)) {
    const value = userStore.get(key);
    chrome[name] = chromeValues[name].includes(value) ? value : chromeValues[name][0];
  }
  // The bootstrap takes the parameter out of the address with its other marks.
  const askedMode = new URL(location.href).searchParams.get("lf-chrome");
  if (chromeValues.mode.includes(askedMode)) {
    chrome.mode = askedMode;
    userStore.set(chromeKeys.mode, askedMode);
  }
  paintChrome();
  root.lfChrome = {
    get mode() {
      return chrome.mode;
    },
    get rest() {
      return chrome.rest;
    },
    // A sample's settings choose for it alone, so nothing is stored.
    adopt(mode) {
      if (!chromeValues.mode.includes(mode) || chrome.mode === mode) return;
      chrome.mode = mode;
      paintChrome();
    },
    set(name, value) {
      if (!chromeValues[name]?.includes(value) || chrome[name] === value) return;
      chrome[name] = value;
      userStore.set(chromeKeys[name], value);
      paintChrome();
      document.dispatchEvent(new CustomEvent("lf-chrome-preference"));
    },
  };

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
  // Initial geometry writes root attributes and styles before modules exist. Later
  // root writers adopt these registries, so revisions replace only the authored share.
  const runtimeAttributes = new WeakMap();
  const setRuntimeRootAttribute = (node, name, value) => {
    let attributes = runtimeAttributes.get(node);
    if (!attributes) runtimeAttributes.set(node, (attributes = new Set()));
    attributes.add(name);
    keepsAttribute(node, name, value);
  };
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
  // What an element wears: attributes and custom properties written as one set, so a
  // later set removes what the earlier one had and the next does not (dress.js). The
  // root and body wear theirs as runtime root state, so a revision keeps it; any other
  // element is no root state, and writes plainly.
  const worn = new WeakMap();
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
  const origins = new WeakMap();
  const parents = new WeakMap();
  // Null/undefined means absent; compare the string an attribute reads back. The
  // module keeps.js adopts this same no-restatement door after initial producers.
  const keepsAttribute = (node, name, value) => {
    if (!node) return;
    if (value == null) {
      if (node.hasAttribute(name)) node.removeAttribute(name);
    } else {
      const said = String(value);
      if (node.getAttribute(name) !== said) node.setAttribute(name, said);
    }
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
  // A failed placement is a mechanical fit result, retried only when its inputs
  // change. Keep authored sheet identities/rules too: two CSS declarations can draw
  // the same unshifted tracks while only one responds to a requested shift.
  const failedPlacements = new WeakMap();
  const authoredSheets = () =>
    [...document.styleSheets]
      .filter((sheet) => !sheet.ownerNode?.hasAttribute("data-lf-runtime"))
      .flatMap((sheet) => {
        let rules;
        try {
          rules = [...sheet.cssRules].map((rule) => rule.cssText).join("\n");
        } catch (error) {
          // An opaque cross-origin sheet cannot be modified through CSSOM either.
          if (error.name !== "SecurityError") throw error;
          rules = null;
        }
        return [sheet, sheet.disabled, sheet.media.mediaText, rules];
      });
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
  const seat = () => {
    const body = document.body;
    if (!body) return false;
    // The page's `main` (passages.js, `pageDocument`), read here before any module runs.
    const main = document.querySelector("body > main");
    // CSS declares the column's requested shell, without making the runtime read a
    // Layout class or making a root :has() re-check the whole page on every insertion.
    const tracksRequested =
      Boolean(main) &&
      getComputedStyle(main).getPropertyValue("--lf-column-shell").trim() === "grid";
    const shellChanged = body.hasAttribute("data-lf-column-shell") !== tracksRequested;
    if (!sourceShells.has(body)) sourceShells.set(body, body.cloneNode(false));
    setRuntimeRootAttribute(body, "data-lf-column-shell", tracksRequested ? "" : null);
    if (!main) {
      const shifted = body.style.getPropertyValue("--lf-column-shift") !== "";
      removeRuntimeRootStyle(body, "--lf-column-shift");
      return shellChanged || shifted;
    }
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
    const shellWritten =
      parseFloat(document.body.style.getPropertyValue("--lf-column-shift")) || 0;
    const column = main.getBoundingClientRect();
    const shell = document.body.getBoundingClientRect();
    const room = {
      left: column.left - gridShift - shell.left,
      right: shell.right - column.right + gridShift,
    };
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
    const preferences = [...declared.values()].sort(
      (a, b) => (side(a) === "left" ? 0 : 1) - (side(b) === "left" ? 0 : 1),
    );
    const inputs = (box = column, placement = shellStyle) => [
      box.left,
      box.right,
      shell.left,
      shell.right,
      placement.gridTemplateColumns,
      placement.direction,
      placement.display,
      main.getAttribute("style"),
      document.body.getAttribute("style"),
      main.className,
      document.body.className,
      root.className,
      document.body.dataset.annotations,
      document.body.dataset.rail,
      ...Object.values(POSTURES).map(([, token]) => need(token)),
      need("--rail"),
      preferences.flat().join(" "),
      ...authoredSheets(),
    ];
    const priorFailure = failedPlacements.get(main);
    const currentInputs = priorFailure ? inputs() : null;
    const sameFailure =
      priorFailure &&
      currentInputs.length === priorFailure.length &&
      currentInputs.every((input, at) => input === priorFailure[at]);
    const allocate = (room, movable) => {
      const taken = { left: 0, right: 0 };
      const granted = [];
      if (
        (document.body.dataset.annotations ?? "overlay") === "overlay" &&
        document.body.getAttribute("data-rail") !== "none" &&
        room.right >= need("--rail")
      ) {
        granted.push("rail");
        taken.right = need("--rail");
      }
      for (const postures of preferences)
        for (const posture of postures) {
          const [at, token] = POSTURES[posture];
          const wants = { ...taken, [at]: Math.max(taken[at], need(token)) };
          if (wants.left + wants.right > room.left + room.right + 0.5) continue;
          if (!movable && (wants.left > room.left || wants.right > room.right))
            continue;
          granted.push(posture);
          Object.assign(taken, wants);
          break;
        }
      const requested = Math.round(
        taken.left > room.left
          ? taken.left - room.left
          : taken.right > room.right
            ? room.right - taken.right
            : 0,
      );
      // Auto margins can centre the column only while its track still holds it.
      const reach = Math.max(0, (shell.width - column.width) / 2);
      const shift = movable ? Math.max(-reach, Math.min(reach, requested)) : 0;
      return { taken, granted, shift };
    };
    let allocation = allocate(
      sameFailure
        ? {
            left: column.left - shell.left,
            right: shell.right - column.right,
          }
        : room,
      canShift && !sameFailure,
    );
    // CSS is the placement authority. An authored track override can ignore our
    // requested shift even on a grid. Verify the supplied room before admitting it;
    // when it cannot supply the request, withdraw it and allocate in actual flow.
    const place = (shift) => {
      if (shift) setRuntimeRootStyle(document.body, "--lf-column-shift", `${shift}px`);
      else removeRuntimeRootStyle(document.body, "--lf-column-shift");
    };
    place(allocation.shift);
    const supplied =
      allocation.shift === shellWritten ? column : main.getBoundingClientRect();
    if (
      allocation.taken.left > supplied.left - shell.left + 0.5 ||
      allocation.taken.right > shell.right - supplied.right + 0.5
    ) {
      place(0);
      const actual = main.getBoundingClientRect();
      allocation = allocate(
        { left: actual.left - shell.left, right: shell.right - actual.right },
        false,
      );
      failedPlacements.set(main, inputs(actual, getComputedStyle(document.body)));
    } else if (!sameFailure) {
      failedPlacements.delete(main);
    }
    const { shift, granted } = allocation;
    const tokens = granted.join(" ");
    const seated = (main.getAttribute("data-lf-margin") ?? "") !== tokens;
    if (!seated && shift === shellWritten) return shellChanged;
    // Source copies keep the authored shell before initial geometry writes to it;
    // children still follow their original routes as the parser continues.
    if (!sourceShells.has(main)) sourceShells.set(main, main.cloneNode(false));
    if (seated) {
      if (tokens) main.setAttribute("data-lf-margin", tokens);
      else main.removeAttribute("data-lf-margin");
    }
    // Module-time adoption announces changed seats to reading-region discovery;
    // before upgrade the same attributes already provide the final authored box.
    return true;
  };
  // How far each breakout's holder stands in from the column on each side
  // (`--lf-indent-l`, `--lf-indent-r`), which the breakout's room counts as its own
  // (layouts.css): a list item, a list the page resets, a page's own indented block,
  // whatever moved it, read off the boxes rather than declared by each kind of holder.
  // Only a column grows a breakout past its holder, so a page whose `main` requests no
  // column shell (`seat`) carries no reading, and a breakout inside another takes its
  // holder's width and none of this room. A breakout the browser is not drawing, such
  // as one in a tab not chosen, is not read, since reading skipped content forces its
  // style and layout: it keeps its last reading, and one never read stands as if its
  // holder were the column. Every edge is read before any is written, so the page is
  // laid out once however many breakouts it holds. Read with the column, so a breakout
  // parsed before first paint is placed before it paints; one inserted, revealed or
  // moved later is read as it arrives or moves (content-layout.js).
  //
  // A breakout grows out of the column only down a chain of block flow: each box from
  // the breakout up to `main` a block-level box its holder lays out one under another.
  // Where the breakout, or a box between it and the column, is an item of a grid, a
  // flex line, a table or one of a holder's columns, is an inline block, floats or is
  // positioned, the page arranged that box itself, and the room beside it is the page's
  // own, such as a sibling track's text: grown into it, a wide block in a grid cell
  // stood over the other cell's words, and a table widened its own track and crushed
  // the other to 30px. A link or other inline around a block is no such box, since the
  // browser sets the block in its holder's flow (`holderOf`). Such a breakout
  // wears `data-lf-arranged` and keeps to the box it is laid out in (layouts.css), so
  // the indent is read only where the holder's content box is the breakout's block.
  const contentEdges = (element) => {
    const box = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      left:
        box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      right:
        box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
    };
  };
  const BREAKOUT = '[data-lf-space]:not([data-lf-space="column"])';
  const ARRANGED = "data-lf-arranged";
  // The box a breakout is laid out in: its slot's where a widget slots it, past any
  // ancestor that draws no box of its own (shadow-tree.js, `renderedParent`), and past
  // an inline one, such as a link around a chart or an unknown element, since the
  // browser sets a block inside an inline in an anonymous block of the inline's own
  // holder's flow.
  const holderOf = (breakout, main) => {
    let holder = breakout;
    let display;
    do {
      // `renderedParent` spelled out: this classic script runs before any module loads.
      holder = holder.assignedSlot ?? holder.parentElement ?? holder.getRootNode().host;
      if (holder === main) break;
      display = getComputedStyle(holder).display;
    } while (display === "contents" || display === "inline");
    return holder;
  };
  // A holder whose inner display is flow or flow-root, and which sets no columns, lays
  // its children out one under another at its full width; the computed display names
  // that by its short keyword or in full. One that sets columns computes as a block too,
  // and a wide block in its second column stood over the first's words.
  const FLOWS =
    /^(block|flow-root|list-item|inline-block|table-cell|table-caption)$|\bflow\b|\bflow-root\b|\blist-item\b/;
  const inFlow = (box, holder) => {
    const style = getComputedStyle(box);
    const held = getComputedStyle(holder);
    return (
      FLOWS.test(held.display) &&
      held.columnCount === "auto" &&
      held.columnWidth === "auto" &&
      !/^(inline|table-|ruby)/.test(style.display) &&
      style.float === "none" &&
      style.position !== "absolute" &&
      style.position !== "fixed"
    );
  };
  // Whether the page arranged `holder` or a box above it, once per holder a reading
  // meets however many breakouts it holds.
  const arrangedAbove = (holder, main, verdicts) => {
    if (holder === main) return false;
    if (!verdicts.has(holder)) {
      const above = holderOf(holder, main);
      verdicts.set(
        holder,
        !inFlow(holder, above) || arrangedAbove(above, main, verdicts),
      );
    }
    return verdicts.get(holder);
  };
  // Returns whether any breakout's indent or arrangement changed, every breakout it
  // answers for, and the holders it measured, each with its content box's width and
  // the breakouts it holds, for content-layout.js to watch: a class or style that pads
  // a holder changes its breakouts' room without inserting anything, and a box that
  // moves moves its breakout. The reading keeps none of them.
  const indents = () => {
    const holders = new Map();
    const breakouts = [];
    const main = document.querySelector("body > main");
    if (!main) return { changed: false, breakouts, holders };
    const grows = document.body.hasAttribute("data-lf-column-shell");
    const readings = [];
    const verdicts = new Map();
    let column = null;
    for (const breakout of main.querySelectorAll(BREAKOUT)) {
      if (breakout.parentElement.closest(BREAKOUT)) continue;
      if (!grows) {
        readings.push([breakout, 0, 0, false]);
        continue;
      }
      breakouts.push(breakout);
      if (!breakout.checkVisibility()) continue;
      const holder = holderOf(breakout, main);
      if (!inFlow(breakout, holder) || arrangedAbove(holder, main, verdicts)) {
        readings.push([breakout, 0, 0, true]);
        continue;
      }
      column ??= contentEdges(main);
      const edges = contentEdges(holder);
      const held = holders.get(holder);
      if (held) held.breakouts.push(breakout);
      else
        holders.set(holder, {
          width: edges.right - edges.left,
          breakouts: [breakout],
        });
      readings.push([
        breakout,
        Math.max(0, Math.round(edges.left - column.left)),
        Math.max(0, Math.round(column.right - edges.right)),
        false,
      ]);
    }
    let changed = false;
    for (const [breakout, left, right, arranged] of readings) {
      const writes = [
        ["--lf-indent-l", left],
        ["--lf-indent-r", right],
      ].filter(
        ([property, length]) =>
          breakout.style.getPropertyValue(property) !== (length ? `${length}px` : ""),
      );
      const rearranged = breakout.hasAttribute(ARRANGED) !== arranged;
      if (!writes.length && !rearranged) continue;
      if (!sourceShells.has(breakout))
        sourceShells.set(breakout, breakout.cloneNode(false));
      for (const [property, length] of writes)
        if (length) setRuntimeRootStyle(breakout, property, `${length}px`);
        else removeRuntimeRootStyle(breakout, property);
      if (rearranged) setRuntimeRootAttribute(breakout, ARRANGED, arranged ? "" : null);
      changed = true;
    }
    return { changed, breakouts, holders };
  };
  // Whether each track (`--lf-resident: track`, a sidebar page's `aside`, layouts.css)
  // stands beside the body, which it says as `data-lf-beside` so the Layout keeps the
  // block it holds in view only there. Flex wrapping places it, from the window's width,
  // the shares the page gives the track and the body, and the minimum the body's content
  // declares, and no query reads that. A track stands beside the body when one of the
  // other boxes `main` lays out in its flex lines shares its line and stands wholly to
  // one side of it: a box `main` lays out is a child that draws a box and is not taken
  // out of the flow, or one inside a child that draws none (`display: contents`), and
  // another track does not count. A track holding one block runs its line's height
  // (layouts.css), and a line holds its items' margin boxes whatever margins a page gives
  // them, so a box on the line is level with the track and one on another line, such as
  // the header, the footer or a stacked body, is above or below it or spans it. Sticking
  // moves only the block inside the track, so the track's own box is where the flex line
  // put it. Every box is read before any track is written.
  const BESIDE = "data-lf-beside";
  const items = (element) => {
    const style = getComputedStyle(element);
    if (style.display === "contents")
      return [...element.children].flatMap((child) => items(child));
    if (!element.checkVisibility() || ["absolute", "fixed"].includes(style.position))
      return [];
    const { left, right, top, bottom, width } = element.getBoundingClientRect();
    return [
      {
        element,
        track: style.getPropertyValue("--lf-resident").trim() === "track",
        left,
        right,
        width,
        top: top - parseFloat(style.marginTop),
        bottom: bottom + parseFloat(style.marginBottom),
      },
    ];
  };
  const stand = () => {
    const main = document.querySelector("body > main");
    if (!main) return false;
    const tracks = [...main.children].filter(
      (child) =>
        getComputedStyle(child).getPropertyValue("--lf-resident").trim() === "track",
    );
    if (!tracks.length) return false;
    const laid = [...main.children].flatMap((child) => items(child));
    const own = laid.filter((item) => !item.track);
    const readings = tracks.map((track) => {
      const line = laid.find((item) => item.element === track);
      return [
        track,
        line !== undefined &&
          own.some(
            (box) =>
              box.width > 0 &&
              box.top < line.bottom - 0.5 &&
              box.bottom > line.top + 0.5 &&
              (box.right <= line.left + 0.5 || box.left >= line.right - 0.5),
          ),
      ];
    });
    let changed = false;
    for (const [track, beside] of readings) {
      if (track.hasAttribute(BESIDE) === beside) continue;
      if (!sourceShells.has(track)) sourceShells.set(track, track.cloneNode(false));
      track.toggleAttribute(BESIDE, beside);
      changed = true;
    }
    return changed;
  };
  const residency = () => {
    const seated = seat();
    const stood = stand();
    const reading = indents();
    return { ...reading, changed: reading.changed || seated || stood };
  };

  // The id a URL fragment spells, for location.hash and for a link's href alike, from
  // the first script on (`named` below) to every module reading a destination
  // (`anchor-resolution.js`, `fragmentTarget`). A malformed escape keeps its literal
  // characters rather than making a durable reference unreadable.
  const fragmentId = (fragment) => {
    const raw = fragment.slice(1);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  };

  root.lfInitial = {
    fragmentId,
    keepsAttribute,
    setRuntimeRootAttribute,
    runtimeRootAttributes: (node) => new Set(runtimeAttributes.get(node) ?? []),
    setRuntimeRootStyle,
    removeRuntimeRootStyle,
    wear,
    runtimeRootStyles: (node) => new Set(runtimeStyles.get(node) ?? []),
    authoredShell: (node) => sourceShells.get(node) ?? sources.get(node) ?? node,
    residency,
    indents,
    skipped,
    register(tag, render) {
      const revision = document.currentScript.dataset.lfVocabulary;
      const key = `${revision}:${tag}`;
      if (producers.has(key))
        throw new Error(
          `initial renderer for <${tag}> in r${revision} is already registered`,
        );
      producers.set(key, render);
    },
    has(tag, revision) {
      return producers.has(`${revision}:${tag}`);
    },
    paint(host, revision = host.closest("[data-lf-vocabulary]").dataset.lfVocabulary) {
      if (drawings.has(host)) return drawings.get(host);
      const render = producers.get(`${revision}:${host.localName}`);
      if (!render) throw new Error(`no initial renderer for <${host.localName}>`);
      for (const node of [host, ...host.querySelectorAll("*")])
        if (!parents.has(node)) parents.set(node, node.parentElement);
      rememberSource(authoredCopy(host));
      for (let node = host; node; node = node.parentNode) sourceScopes.add(node);
      const drawing = render(host, {
        tabStore,
        offer,
        offerElement,
        keeps: keepsAttribute,
      });
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
        if (
          this.has(
            node.localName,
            node.closest("[data-lf-vocabulary]").dataset.lfVocabulary,
          )
        )
          this.paint(node);
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
    const target = document.getElementById(fragmentId(location.hash));
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
