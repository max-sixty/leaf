// What a document Leaf's runtime will run in, served or exported, has to say before its
// first paint, which no module can reach: modules run once the document has parsed, and
// the browser paints what has arrived well before that. Delivery places this script
// after the head's canonical link, so the page root that link declares is in the
// document when it runs, and before the bootstrap and the theme (`compose_document`).
/** @typedef {import("../types/contract.js").AuthoredAllocations} Allocations */
(() => {
  const root = document.documentElement;
  // A page-wide allocation `body` states (`$authored`), or null where it states none.
  /** @template {keyof Allocations} A @param {A} name @returns {Allocations[A] | null} */
  const pageAllocation = (name) =>
    /** @type {any} */ (document.body.getAttribute(name));
  // A document reports faults only until it departs. A navigation away aborts the
  // document's requests, and those failures are the navigation's, not the page's.
  // Chrome fires `pageswap` and `pagehide` before it rejects the aborted requests.
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
  let leaving = false;
  /** @type {Map<string, () => void>} */
  let waiting = new Map();
  root.lfDocumentLifetime = Object.freeze({
    /** Run `report` of `fault` now, once the document is known to have stayed, or never. */
    whenActive(fault, report) {
      if (!swapped && !leaving) report();
      else if (!swapped && !waiting.has(fault)) waiting.set(fault, report);
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
      swapped = true;
      waiting = new Map();
    });
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    swapped = false;
    leaving = false;
  });
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
  // Early key holding and the runtime ask the same question of a key's origin.
  // Selects and custom options keep typeahead without being text editors.
  const textField = "leaf-text";
  const textBox = `textarea, ${textField}`;
  const typedTypes = new Set([
    "text",
    "search",
    "url",
    "tel",
    "email",
    "password",
    "number",
    "date",
    "time",
    "datetime-local",
    "month",
    "week",
  ]);
  const typesText = (node) =>
    Boolean(node) &&
    (node.matches(textBox) ||
      node.isContentEditable ||
      (node.localName === "input" && typedTypes.has(node.type)));
  const takesLetters = (node) =>
    typesText(node) ||
    (Boolean(node) &&
      (node.localName === "select" || node.getAttribute("role") === "option"));
  root.lfInputs = {
    textField,
    textBox,
    typesText,
    takesLetters,
    get count() {
      return inputs;
    },
    observe(read) {
      inputReaders.add(read);
      return () => inputReaders.delete(read);
    },
  };
  const input = (event) => {
    // Firefox can send an inaccessible foreign wheel object to an arriving
    // sandboxed window. It is not this realm's Event and reaches no document.
    // Reject it before reading fields or handing it to the input subscribers.
    if (!(event instanceof Event)) return;
    if (event.type === "blur" && event.target !== window) return;
    if (event.type !== "blur" && event.type !== "wheel") stayed();
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
  const fault = (reason, incomplete, error = null, page = false) =>
    root.lfDocumentLifetime.whenActive(`fault ${reason}`, () => {
      if (incomplete) {
        root.toggleAttribute("data-lf-interactive", false);
        trade(PLAYER, "controls");
      }
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

  // The floating panel (floating-panel.js) is the page's chrome. The reader's one
  // preference is the size the panel was left at (`row`, the comment field and its
  // counts, or `mark`, the leaf alone in the window's corner), one for every page on
  // the origin, read here so the first paint already stands at it.
  const restKey = "lf-chrome-rest";
  const restValues = ["row", "mark"];
  const storedRest = userStore.get(restKey);
  let rest = restValues.includes(storedRest) ? storedRest : restValues[0];
  root.lfChrome = {
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
  // The box a producer built to hold every authored child of its host, which it then
  // seats inside boxes of its own, as a disclosure's body sits under the summary the
  // module writes. The box is the module's and its interior is the page's: render
  // checks read the boxes around it as the module's layout, and a revision that
  // reaches the host's members edits inside it (dom-children.js, `patchTree`). A sidebar
  // page's track has one too, which the Layout's own reading builds (`holdTrack`).
  const authoredBodies = new WeakMap();
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
  // Words an upgrade wrote, which the page's authored source lacks: the `wrote` reading
  // leaves them out, and they are a passage cell of their own. `says` is whether they
  // are the page speaking (data-lf-said, quotable even inside chrome), a copy of words
  // the page says elsewhere ("echo", data-lf-echo), or neither; widget-elements.js,
  // over `relabel`, says why each answer matters and why none is assumed.
  /**
   * @template {Element} T
   * @param {T} node
   * @param {{says?: boolean | "echo"}} [options]
   * @returns {T}
   */
  const generatedElement = (node, { says } = {}) => {
    if (typeof says !== "boolean" && says !== "echo")
      throw new TypeError(
        `Say whether these words are the page speaking: ` +
          `true, false, or "echo" for a copy of words it says elsewhere`,
      );
    keepsAttribute(node, "data-lf-gen", "1");
    // Toggling keeps an x-says span's attribute name (declared-words.js) where it stands.
    node.toggleAttribute("data-lf-said", says === true);
    node.toggleAttribute("data-lf-echo", says === "echo");
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
  // Leaf's controls come from a closed set of roles, and each role wears one face
  // (components/controls.css). A widget names the role and never the face's classes,
  // so two controls of one kind cannot be drawn two ways; this table is the only place
  // the classes are spelled (`test_controls_are_built_by_role_and_never_by_face` in
  // `tests/model/test_interact_layer.py` holds that).
  //
  // - `symbol`: a press drawn as one of Leaf's icons, named by its tooltip and
  //   accessible name (browser/AGENTS.md, "Visual grammar"): quiet at rest, the chip
  //   under a hovering pointer or visible focus.
  // - `word`: a press that says what it does in words, quiet as a symbol is. A toggle
  //   is a word whose `aria-pressed` the theme draws as selected.
  // - `commit`: the one press on a surface that commits the user's work, framed in the
  //   accent.
  // - `mark`: a small symbol seated on the thing it acts on, at a corner or on a
  //   block's border toolbar, where a larger face would cover the thing.
  // - `inline`: a press read as part of the line of words it stands in, such as a
  //   thread's held news or a quote's Full quote, drawn as words in the accent at the
  //   line's size with no frame. One that announces news waiting says so with
  //   `data-lf-news`, which draws it in the danger ink, and one whose words say a
  //   warning with `data-lf-tone="warn"`, in the warning's.
  // - `row`: one row of a list or menu, whose words are what the reader scans, so they
  //   stand in the ink; the row under the pointer or the keys is washed, and the row
  //   the list stands on (`aria-current`) wears the accent's stripe and tint.
  // - `answer`: one of the answers a question offers, such as a decision's choices on
  //   an On me card, framed so the set reads as one to pick from, the chosen one
  //   (`aria-pressed`) marked in the ok tone as the page marks its chosen option.
  //
  // A difference that was only a past choice is not a role: a symbol once came bordered
  // in some widgets and quiet in others, a word framed in some, quiet in others and a
  // list's row in a third, four presses among words drew four faces of their own, and
  // seven lists drew their rows six ways, before each merged.
  const ACTION_FACES = {
    symbol: "lf-icon-action",
    word: "lf-btn",
    commit: "lf-btn primary",
    mark: "lf-mark-action",
    inline: "lf-inline-action",
    row: "lf-row",
    answer: "lf-answer",
  };
  const faceOf = (role) => {
    const face = ACTION_FACES[role];
    if (!face)
      throw new TypeError(
        `A control's role is one of ${Object.keys(ACTION_FACES).join(", ")}, not ${role}`,
      );
    return face;
  };
  // `label` names the press. A worded role shows it, and `offerAction` writes it as the
  // words; the element writer leaves the words to whoever owns the element's content,
  // such as a template. A symbol or mark says it as the accessible name and the
  // tooltip, `title` where the tooltip says more, such as the key that does the same.
  const offerActionElement = (node, role, cls, label, { title = label } = {}) => {
    const face = faceOf(role);
    offerElement(node, cls ? `${face} ${cls}` : face);
    if (label !== undefined && (role === "symbol" || role === "mark")) {
      keepsAttribute(node, "aria-label", label);
      keepsAttribute(node, "title", title);
    }
    return node;
  };
  const offerAction = (role, cls, label, options) => {
    const node = offerActionElement(
      document.createElement("button"),
      role,
      cls,
      label,
      options,
    );
    if (label !== undefined && role !== "symbol" && role !== "mark")
      node.textContent = label;
    return node;
  };
  // `face` names the action role whose face a selectable press wears, such as a `row`
  // whose words are the page's own.
  const selectableOfferElement = (node, role, cls, face) => {
    const classes = [face && faceOf(face), cls, "lf-ui lf-ui-face"].filter(Boolean);
    keepsAttribute(node, "role", role);
    keepsAttribute(node, "class", classes.join(" "));
    keepsAttribute(node, "data-lf-gen", "1");
    keepsAttribute(node, "data-lf-offer", role);
    keepsAttribute(node, "data-lf-selectable-offer", "");
  };

  const selectableOffer = (role, cls, label, face) => {
    const node = document.createElement("span");
    selectableOfferElement(node, role, cls, face);
    node.tabIndex = 0;
    if (label !== undefined) node.textContent = label;
    return node;
  };

  // External marks occupy inline room, so the parser seats them before prose paints.
  // The module runtime adopts this owner and its baselines for subsequent arrivals.
  // External page links keep native link behavior but make the boundary explicit: the
  // target opens beside this Leaf, and the visible mark says it will leave the page. A URL
  // on this page's own origin is still local even when the author wrote it absolutely;
  // non-web schemes keep their platform meaning.
  //
  // The mark is also what a screen reader is told: the link's description names it, and it
  // carries the words as its label. It stays hidden, so the words are not part of the
  // link's name, and a description may name a hidden element. Everything the treatment adds
  // stands inside the link, so the page's own rules about which of a block's children
  // comes last, or what follows a link, match what the page wrote.
  const EXTERNAL_LINK_ATTRIBUTES = ["target", "rel", "aria-describedby"];
  const externalLinkState = new WeakMap();
  let externalMarkSequence = 0;
  const opensElsewhere = (href) => {
    try {
      const url = href === null ? null : new URL(href, document.baseURI);
      return (
        ["http:", "https:"].includes(url?.protocol) && url.origin !== location.origin
      );
    } catch {
      return false;
    }
  };
  const isExternalPageLink = (link) =>
    link instanceof HTMLAnchorElement && opensElsewhere(link.getAttribute("href"));
  function externalMark() {
    const mark = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mark.setAttribute("class", "lf-ui lf-external-mark");
    mark.setAttribute("viewBox", "0 0 16 16");
    mark.setAttribute("aria-hidden", "true");
    mark.setAttribute("aria-label", "opens in a new tab");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute(
      "d",
      "M6.5 3H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V9.5M9 3h4v4M13 3 7.5 8.5",
    );
    mark.append(line);
    return mark;
  }
  // The text field draws the same mark after a link it shows (composing/text-field.js).
  root.lfExternalLink = Object.freeze({ opensElsewhere, mark: externalMark });
  const linkAttributes = (link) =>
    Object.fromEntries(
      EXTERNAL_LINK_ATTRIBUTES.map((name) => [name, link.getAttribute(name)]),
    );
  const tokens = (value) => value?.split(/\s+/).filter(Boolean) ?? [];
  function withToken(value, token, insensitive = false) {
    const values = tokens(value);
    const wanted = insensitive ? token.toLowerCase() : token;
    if (!values.some((value) => (insensitive ? value.toLowerCase() : value) === wanted))
      values.push(token);
    return values.join(" ");
  }
  function withoutToken(value, token, insensitive = false) {
    if (value === null) return null;
    const unwanted = insensitive ? token.toLowerCase() : token;
    return tokens(value)
      .filter((value) => (insensitive ? value.toLowerCase() : value) !== unwanted)
      .join(" ");
  }
  function writeLinkAttributes(link, values) {
    for (const [name, value] of Object.entries(values))
      keepsAttribute(link, name, value);
  }
  function rememberExternalLinkChanges(link, state) {
    if (!state.painted) return;
    const current = linkAttributes(link);
    for (const name of EXTERNAL_LINK_ATTRIBUTES) {
      if (current[name] === state.painted[name]) continue;
      let value = current[name];
      if (name === "rel" && state.addedNoopener)
        value = withoutToken(value, "noopener", true);
      if (name === "aria-describedby") value = withoutToken(value, state.markId);
      state.baseline[name] = value;
    }
  }
  function clearExternalLink(link, state) {
    rememberExternalLinkChanges(link, state);
    writeLinkAttributes(link, state.baseline);
    link
      .querySelectorAll(':scope > .lf-external-mark[data-lf-gen="1"]')
      .forEach((node) => node.remove());
    externalLinkState.delete(link);
  }
  function leaveExternalLink(link) {
    const state = externalLinkState.get(link);
    if (state) clearExternalLink(link, state);
  }
  function renderExternalLink(link) {
    // SVG links share this selector but not the HTML anchor API, and they have no
    // dependable inline box in which an HTML text mark could stand.
    if (!(link instanceof HTMLAnchorElement)) return;
    if (!isExternalPageLink(link)) {
      leaveExternalLink(link);
      return;
    }
    let state = externalLinkState.get(link);
    if (!state) {
      state = {
        baseline: linkAttributes(link),
        painted: null,
        markId: `lf-external-mark-${++externalMarkSequence}`,
        addedNoopener: false,
      };
      externalLinkState.set(link, state);
    } else rememberExternalLinkChanges(link, state);
    /** @type {SVGElement | null} */
    let mark = link.querySelector(':scope > .lf-external-mark[data-lf-gen="1"]');
    if (!mark) {
      mark = generatedElement(externalMark(), { says: false });
    }
    // Parsing may yield while this anchor is still open. Keep the mark after any
    // words the parser (or a later render) has appended since the previous pass.
    if (mark !== link.lastChild) link.append(mark);
    // Written on a mark found as well as on one made: a link cloned with its mark, ids
    // stripped, is a new link to this pass, and its description must name its own mark.
    keepsAttribute(mark, "id", state.markId);
    state.addedNoopener = !tokens(state.baseline.rel).some(
      (value) => value.toLowerCase() === "noopener",
    );
    writeLinkAttributes(link, {
      target: "_blank",
      rel: withToken(state.baseline.rel, "noopener", true),
      "aria-describedby": withToken(state.baseline["aria-describedby"], state.markId),
    });
    state.painted = linkAttributes(link);
  }
  // A recording the runtime plays through its own bar (video-controls.js) shows no
  // browser controls from its first paint, which would otherwise draw until that
  // module arrives and then give way to the bar. Traded as the parser inserts each
  // video while the runtime is still expected, and given back to a page that cannot
  // start, as its readable fallback. A copy of what the author wrote (`authoredCopy`)
  // takes the trade back, whoever made it, so a revision compares `controls` with
  // `controls`.
  const PLAYER = "data-lf-player";
  const trade = (from, to) => {
    for (const video of document.querySelectorAll(`video[${from}]`)) {
      video.removeAttribute(from);
      video.setAttribute(to, "");
    }
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
    // View geometry is read before modules start, not authored by the page. Leave
    // it out of the baseline a revision compares with its unpainted source.
    copy.removeAttribute?.("data-lf-views-flow");
    copy.removeAttribute?.("data-lf-opening");
    copy.removeAttribute?.("data-lf-sole-content");
    if (copy.hasAttribute?.(PLAYER)) {
      copy.removeAttribute(PLAYER);
      copy.setAttribute("controls", "");
    }
    const linkState = externalLinkState.get(source);
    if (linkState) {
      rememberExternalLinkChanges(source, linkState);
      writeLinkAttributes(copy, linkState.baseline);
    }
    // A track's children stand in the body the runtime built (`holdTrack`); the page
    // wrote them in the track.
    const held =
      source.localName === "template"
        ? source.content
        : (authoredBodies.get(source) ?? source);
    const into = copy.localName === "template" ? copy.content : copy;
    if (source.localName === "template") origins.set(into, origins.get(held) ?? held);
    for (const child of held.childNodes) {
      if (
        child.matches?.("[data-lf-prepaint], script[data-lf-initial]") ||
        (linkState && child.matches?.('.lf-external-mark[data-lf-gen="1"]'))
      )
        continue;
      into.append(authoredCopy(child, target));
    }
    return copy;
  };
  const rememberSource = (source) => {
    sources.set(origins.get(source), source);
    const held = source.localName === "template" ? source.content : source;
    for (const child of held.childNodes) rememberSource(child);
  };
  // Margin content layout is initial document geometry, not a widget upgrade. The parser
  // observer seats authored margin elements before a frame can paint them in another
  // placement; content-layout adopts this same computation for subsequent changes.
  // The body's authored annotation declaration is the same executable fact the
  // module graph reads, so rail admission needs no second delivery configuration.
  const PLACEMENTS = {
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
      .filter(
        (sheet) =>
          !(
            /** @type {Element | null} */ (sheet.ownerNode)?.hasAttribute(
              "data-lf-runtime",
            )
          ),
      )
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
    if (element.checkVisibility({ contentVisibilityAuto: true })) return false;
    // A boxed descendant can retain layout while its auto container skips drawing.
    // Ask the native skip state before any geometry forces that content back.
    if (element.checkVisibility()) return true;
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
  // The box the page's Layout arranges (layouts.css, `--lf-layout-box`): the page's
  // `main` (passages.js, `pageDocument`), or the shown child of a `main` that carries no
  // Layout itself, or the shown child of a part of such a `main`, a member of its child
  // that holds the page's parts (`data-lf-views="parts"`). A part not shown hides what
  // it holds (`hidden="until-found"`), so a box in it is not shown. Its parent is the shell the
  // Layout places it in. CSS declares the box, so the runtime reads no Layout class.
  // Without a Layout, the box is `main`.
  const isLayoutBox = (box) =>
    getComputedStyle(box).getPropertyValue("--lf-layout-box").trim() === "1";
  const layoutBox = () => {
    const main = document.querySelector("body > main");
    if (!main || isLayoutBox(main)) return main;
    const parts = main.querySelector(':scope > [data-lf-views="parts"]');
    const boxes = [
      ...main.children,
      ...[...(parts?.children ?? [])].flatMap((part) => [...part.children]),
    ];
    return boxes.find((box) => box.checkVisibility() && isLayoutBox(box)) ?? main;
  };
  // The shell that last held the column, so a column that moves to another shell, as
  // when another part is shown, leaves none of its tracks behind.
  let lastShell = null;
  const seat = () => {
    const body = document.body;
    if (!body) return false;
    // Read here before any module runs.
    const box = layoutBox();
    const shellNode = box?.parentElement ?? body;
    // CSS declares the column's requested shell, without making the runtime read a
    // Layout class or making a root :has() re-check the whole page on every insertion.
    const tracksRequested =
      Boolean(box) &&
      getComputedStyle(box).getPropertyValue("--lf-column-shell").trim() === "grid";
    let shellChanged =
      shellNode.hasAttribute("data-lf-column-shell") !== tracksRequested;
    if (lastShell && lastShell !== shellNode) {
      shellChanged ||= lastShell.hasAttribute("data-lf-column-shell");
      setRuntimeRootAttribute(lastShell, "data-lf-column-shell", null);
    }
    lastShell = shellNode;
    if (!sourceShells.has(shellNode))
      sourceShells.set(shellNode, shellNode.cloneNode(false));
    setRuntimeRootAttribute(
      shellNode,
      "data-lf-column-shell",
      tracksRequested ? "" : null,
    );
    // The shift is written on `body` whatever the shell, and the shell's tracks inherit
    // it: `body` is root state, whose runtime styles a revision keeps (version.js).
    if (!box) {
      const shifted =
        body.style.getPropertyValue("--lf-column-shift") !== "" ||
        body.style.getPropertyValue("--lf-shell-left") !== "";
      removeRuntimeRootStyle(body, "--lf-column-shift");
      removeRuntimeRootStyle(body, "--lf-shell-left");
      return shellChanged || shifted;
    }
    const style = getComputedStyle(box);
    const need = (token) => parseFloat(style.getPropertyValue(token)) || 0;
    // Remove only the physical offset the shell's grid tracks actually apply. An
    // author's relative offset remains part of the available room. Read rendered
    // tracks rather than the last written shift, including under RTL.
    const shellStyle = getComputedStyle(shellNode);
    const tracks = shellStyle.gridTemplateColumns.split(" ").map(parseFloat);
    const canShift = shellStyle.display === "grid" && style.gridColumnStart === "2";
    const gridShift = canShift
      ? ((tracks[0] - tracks.at(-1)) / 2) * (shellStyle.direction === "rtl" ? -1 : 1)
      : 0;
    const shellWritten =
      parseFloat(body.style.getPropertyValue("--lf-column-shift")) || 0;
    const column = box.getBoundingClientRect();
    // Inside the shell's border and scrollbar gutters. A margin element may stand in its
    // padding, as the rail does in the strip `data-rail="right"` pads `body` with
    // (annotation-theme.css). The client box is in the shell's own pixels, so it is
    // scaled to the window's by any transform on the shell or around it.
    const shellRect = shellNode.getBoundingClientRect();
    const scale = shellRect.width / shellNode.offsetWidth || 1;
    const shellLeft = shellRect.left + shellNode.clientLeft * scale;
    const shell = { left: shellLeft, right: shellLeft + shellNode.clientWidth * scale };
    // A margin element fixed to the window, as the contents map is (toc.css), stands from the
    // shell's left edge rather than the window's, which differ where the page puts
    // something before the shell, as a page's list of parts does.
    const left = Math.round(shellLeft) ? `${Math.round(shellLeft)}px` : "";
    const moved = body.style.getPropertyValue("--lf-shell-left") !== left;
    if (left) setRuntimeRootStyle(body, "--lf-shell-left", left);
    else removeRuntimeRootStyle(body, "--lf-shell-left");
    const room = {
      left: column.left - gridShift - shell.left,
      right: shell.right - column.right + gridShift,
    };
    const declared = new Map();
    // A margin element a box around it hides (a closed disclosure, a tab not chosen) needs no
    // room. One the page hides itself stays a margin element, since a page may hide it until it
    // stands in the margin.
    for (const aside of box.querySelectorAll("aside")) {
      if (skipped(aside)) continue;
      const own = getComputedStyle(aside);
      const hiddenItself =
        own.display === "none" && aside.parentElement.checkVisibility();
      if (!aside.checkVisibility() && !hiddenItself) continue;
      const placements = own
        .getPropertyValue("--lf-margin-content")
        .split(" ")
        .filter((placement) => placement in PLACEMENTS);
      if (placements.length) declared.set(placements.join(" "), placements);
    }
    const side = (placements) => PLACEMENTS[placements[0]][0];
    const preferences = [...declared.values()].sort(
      (a, b) => (side(a) === "left" ? 0 : 1) - (side(b) === "left" ? 0 : 1),
    );
    const inputs = (rect = column, placement = shellStyle) => [
      rect.left,
      rect.right,
      shell.left,
      shell.right,
      placement.gridTemplateColumns,
      placement.direction,
      placement.display,
      box.getAttribute("style"),
      shellNode.getAttribute("style"),
      document.body.getAttribute("style"),
      box.className,
      document.body.className,
      root.className,
      document.body.dataset.annotations,
      document.body.dataset.rail,
      ...Object.values(PLACEMENTS).map(([, token]) => need(token)),
      need("--rail"),
      preferences.flat().join(" "),
      ...authoredSheets(),
    ];
    const priorFailure = failedPlacements.get(box);
    const currentInputs = priorFailure ? inputs() : null;
    const sameFailure =
      priorFailure &&
      currentInputs.length === priorFailure.length &&
      currentInputs.every((input, at) => input === priorFailure[at]);
    const allocate = (room, movable) => {
      const taken = { left: 0, right: 0 };
      const granted = [];
      /** @type {Allocations["data-annotations"]} */
      const annotations = pageAllocation("data-annotations") ?? "overlay";
      if (
        annotations === "overlay" &&
        pageAllocation("data-rail") !== "none" &&
        room.right >= need("--rail")
      ) {
        granted.push("rail");
        taken.right = need("--rail");
      }
      for (const placements of preferences)
        for (const placement of placements) {
          const [at, token] = PLACEMENTS[placement];
          const wants = { ...taken, [at]: Math.max(taken[at], need(token)) };
          if (wants.left + wants.right > room.left + room.right + 0.5) continue;
          if (!movable && (wants.left > room.left || wants.right > room.right))
            continue;
          granted.push(placement);
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
      const reach = Math.max(0, (shell.right - shell.left - column.width) / 2);
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
      if (shift) setRuntimeRootStyle(body, "--lf-column-shift", `${shift}px`);
      else removeRuntimeRootStyle(body, "--lf-column-shift");
    };
    place(allocation.shift);
    const supplied =
      allocation.shift === shellWritten ? column : box.getBoundingClientRect();
    if (
      allocation.taken.left > supplied.left - shell.left + 0.5 ||
      allocation.taken.right > shell.right - supplied.right + 0.5
    ) {
      place(0);
      const actual = box.getBoundingClientRect();
      allocation = allocate(
        { left: actual.left - shell.left, right: shell.right - actual.right },
        false,
      );
      failedPlacements.set(box, inputs(actual, getComputedStyle(shellNode)));
    } else if (!sameFailure) {
      failedPlacements.delete(box);
    }
    const { shift, granted } = allocation;
    const tokens = granted.join(" ");
    const seated = (box.getAttribute("data-lf-margin") ?? "") !== tokens;
    if (!seated && shift === shellWritten) return shellChanged || moved;
    // Source copies keep the authored shell before initial geometry writes to it;
    // children still follow their original routes as the parser continues.
    if (!sourceShells.has(box)) sourceShells.set(box, box.cloneNode(false));
    if (seated) {
      if (tokens) box.setAttribute("data-lf-margin", tokens);
      else box.removeAttribute("data-lf-margin");
    }
    // Module-time adoption announces changed seats to reading-region discovery;
    // before upgrade the same attributes already provide the final authored box.
    return true;
  };
  // Whether each breakout grows past its holder (layouts.css). Only a column grows one,
  // so a page whose Layout's box requests no column shell (`seat`) holds none, and a breakout
  // inside another takes its holder's width and is not read. In a column, a breakout
  // grows only from a holder whose content box is the column's own: the column, a section,
  // an item standing in it. Every other one wears `data-lf-kept` and keeps to the box it
  // is laid out in, since the room beside that box is not the page's to give, and the
  // holder's axis is not the prose's:
  //
  // - a holder standing in from the column, however it got there: a list item, a
  //   quotation, a page's own indented block;
  // - a breakout the page arranged, or one inside a box the page arranged, however wide:
  //   one its holder does not lay out in block flow, one under another, as an item of a
  //   grid, a flex line or a table, an inline block, one that floats or is positioned,
  //   and one in a holder's columns. The room beside it is the page's own, such as a
  //   sibling track's text: grown into it, a wide block in a grid cell stood over the
  //   other cell's words, a table widened its own track and crushed the other to 30px,
  //   and a block in a holder's second column stood over the first's words.
  //
  // A link or other inline around a block is no holder, since the browser sets the
  // block in its own holder's flow (`holderOf`). A breakout the browser is not drawing,
  // such as one in a tab not chosen, is not read, since reading skipped content forces
  // its style and layout: it keeps its last reading, and one never read grows. Every box
  // is read before any is written, so the page is laid out once however many breakouts
  // it holds. Read with the column, so a breakout parsed before first paint is placed
  // before it paints; one inserted or revealed later is read as it arrives
  // (content-layout.js).
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
  const BREAKOUT = "[data-lf-space]";
  const KEPT = "data-lf-kept";
  // The box a breakout is laid out in: its slot's where a widget slots it, past any
  // ancestor that draws no box of its own (shadow-tree.js, `renderedParent`), and past
  // an inline one, such as a link around a chart or an unknown element, since the
  // browser sets a block inside an inline in an anonymous block of the inline's own
  // holder's flow.
  const holderOf = (breakout, box) => {
    let holder = breakout;
    let display;
    do {
      // `renderedParent` spelled out: this classic script runs before any module loads.
      holder = holder.assignedSlot ?? holder.parentElement ?? holder.getRootNode().host;
      if (holder === box) break;
      display = getComputedStyle(holder).display;
    } while (display === "contents" || display === "inline");
    return holder;
  };
  // A holder whose inner display is flow or flow-root, and which sets no columns, lays
  // its children out one under another at its full width; the computed display names
  // that by its short keyword or in full.
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
  const arrangedAbove = (holder, box, verdicts) => {
    if (holder === box) return false;
    if (!verdicts.has(holder)) {
      const above = holderOf(holder, box);
      verdicts.set(
        holder,
        !inFlow(holder, above) || arrangedAbove(above, box, verdicts),
      );
    }
    return verdicts.get(holder);
  };
  // Returns whether any breakout's reading changed.
  const breakouts = () => {
    const box = layoutBox();
    if (!box) return { changed: false };
    const grows = Boolean(box.parentElement?.hasAttribute("data-lf-column-shell"));
    const readings = [];
    const verdicts = new Map();
    let column = null;
    for (const breakout of box.querySelectorAll(BREAKOUT)) {
      if (breakout.parentElement.closest(BREAKOUT)) continue;
      if (!grows) {
        readings.push([breakout, false]);
        continue;
      }
      if (!breakout.checkVisibility()) continue;
      const holder = holderOf(breakout, box);
      column ??= contentEdges(box);
      const edges = holder === box ? column : contentEdges(holder);
      readings.push([
        breakout,
        !inFlow(breakout, holder) ||
          arrangedAbove(holder, box, verdicts) ||
          Math.abs(edges.left - column.left) > 0.5 ||
          Math.abs(edges.right - column.right) > 0.5,
      ]);
    }
    let changed = false;
    for (const [breakout, held] of readings) {
      if (breakout.hasAttribute(KEPT) === held) continue;
      if (!sourceShells.has(breakout))
        sourceShells.set(breakout, breakout.cloneNode(false));
      setRuntimeRootAttribute(breakout, KEPT, held ? "" : null);
      changed = true;
    }
    return { changed };
  };
  // Whether each track (`--lf-margin-content: track`, a sidebar page's `aside`, layouts.css)
  // stands beside the body, which it says as `data-lf-beside` so the Layout keeps what
  // it holds in view only there. Flex wrapping places it, from the window's width,
  // the shares the page gives the track and the body, and the minimum the body's content
  // declares, and no query reads that. A track stands beside the body when one of the
  // other boxes the Layout's box lays out in its flex lines shares its line and stands wholly to
  // one side of it: a box it lays out is a child that draws a box and is not taken
  // out of the flow, or one inside a child that draws none (`display: contents`), and
  // another track does not count. A track runs its line's height (layouts.css), and a
  // line holds its items' margin boxes whatever margins a page gives them, so a box on
  // the line is level with the track and one on another line, such as the header, the
  // footer or a stacked body, is above or below it or spans it. Sticking moves only the
  // box inside the track, so the track's own box is where the flex line put it. Every
  // box is read before any track is written.
  const BESIDE = "data-lf-beside";
  // What a track holds stands in one box the runtime builds inside it, its body
  // (`data-lf-track-body`), which is what sticks (layouts.css), so one block and several
  // stick alike. A sticky box stays inside its containing block, and only a box inside
  // the track has the track, as tall as its flex line, for that block. Rejected
  // (2026-10): sticking the track itself, a flex item, which the whole flex container
  // bounds, so at the page's end it stood 40px over a one-line footer at 900×600.
  //
  // The body is the track's authored body, as a widget's module builds one
  // (`authoredBody`): the source copies read through it (`authoredCopy`), and a revision
  // writes the track's children inside it (dom-children.js, `patchTree`). It draws no
  // box of its own and says no words, so a passage, a page check and a version
  // comparison read the blocks as the page wrote them; a page rule naming the track's
  // children, such as `aside > p`, no longer reaches them (page-layout.md). It is built
  // as the parser inserts the track, before the first paint, and kept whatever width
  // the page stands at; on an unscrolled page it stands where its blocks would. Each
  // reading gathers into it what has arrived in the track since: the parser's later
  // children, a page module's insertions.
  const TRACK_BODY = "data-lf-track-body";
  const holdTrack = (track) => {
    let body = authoredBodies.get(track);
    if (!body) {
      body = document.createElement("div");
      body.setAttribute(TRACK_BODY, "");
      authoredBodies.set(track, body);
    }
    const seated = body.parentNode === track;
    // What stands before the body goes to its start, and what follows it to its end, so
    // the blocks keep the order the track had them in.
    const lead = [];
    const rest = [];
    let past = false;
    for (const node of track.childNodes)
      if (node === body) past = true;
      else (past ? rest : lead).push(node);
    if (seated && !lead.length && !rest.length) return false;
    const { move } = root.lfInitial;
    const first = seated ? body.firstChild : null;
    if (!seated) move(track, body, null);
    for (const [node, before] of [
      ...lead.map((node) => [node, first]),
      ...rest.map((node) => [node, null]),
    ]) {
      // The parent the page wrote it under, as for a widget's children (`parent`).
      if (!parents.has(node)) parents.set(node, track);
      move(body, node, before);
    }
    return true;
  };
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
        track: style.getPropertyValue("--lf-margin-content").trim() === "track",
        left,
        right,
        width,
        top: top - parseFloat(style.marginTop),
        bottom: bottom + parseFloat(style.marginBottom),
      },
    ];
  };
  const stand = () => {
    const box = layoutBox();
    if (!box) return false;
    const tracks = [...box.children].filter(
      (child) =>
        getComputedStyle(child).getPropertyValue("--lf-margin-content").trim() ===
        "track",
    );
    if (!tracks.length) return false;
    let changed = false;
    for (const track of tracks) changed = holdTrack(track) || changed;
    const laid = [...box.children].flatMap((child) => items(child));
    const own = laid.filter((item) => !item.track);
    const readings = tracks.map((track) => {
      const line = laid.find((item) => item.element === track);
      return /** @type {[Element, boolean]} */ ([
        track,
        line !== undefined &&
          own.some(
            (box) =>
              box.width > 0 &&
              box.top < line.bottom - 0.5 &&
              box.bottom > line.top + 0.5 &&
              (box.right <= line.left + 0.5 || box.left >= line.right - 0.5),
          ),
      ]);
    });
    for (const [track, beside] of readings) {
      if (track.hasAttribute(BESIDE) === beside) continue;
      if (!sourceShells.has(track)) sourceShells.set(track, track.cloneNode(false));
      track.toggleAttribute(BESIDE, beside);
      changed = true;
    }
    return changed;
  };
  // A page of parts' title scrolls within its fixed column. Declare that
  // surface alongside the layout, so reach need not discover it by scanning content.
  // CSS anchors its list below the title (layouts.css, "A page of parts").
  const title = () => {
    const main = document.querySelector("body > main");
    const parts =
      main && !isLayoutBox(main)
        ? main.querySelector(':scope > [data-lf-views="parts"]')
        : null;
    let marked = false;
    for (
      let node = parts?.previousElementSibling;
      node;
      node = node.previousElementSibling
    ) {
      if (!node.classList.contains("scroll")) {
        node.classList.add("scroll");
        marked = true;
      }
    }
    return marked;
  };
  // The header a Layout sticks over its body, as a workspace does where the window is
  // too small to be its screen (layouts.css, "Workspace"): what the body stands under is
  // the header's height, which no CSS can read, so it is written here for the body's
  // sticky-header slot (`--lf-top`, theme.css) to add. Which header sticks is the
  // stylesheet's to say; this reads its computed position.
  const HEAD = "--lf-layout-head-h";
  const head = () => {
    const body = document.body;
    if (!body) return false;
    const header = layoutBox()?.querySelector(":scope > header");
    const value =
      header && getComputedStyle(header).position === "sticky"
        ? `${Math.ceil(header.getBoundingClientRect().height)}px`
        : "";
    if (body.style.getPropertyValue(HEAD) === value) return false;
    if (value) setRuntimeRootStyle(body, HEAD, value);
    else removeRuntimeRootStyle(body, HEAD);
    return true;
  };
  const marginContentLayout = () => {
    const seated = seat();
    const titled = title();
    const headed = head();
    const stood = stand();
    const reading = breakouts();
    return {
      ...reading,
      changed: reading.changed || seated || titled || headed || stood,
    };
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
    // Parser-time producers create their first nodes before runtime modules exist.
    // dom-move.js installs the live mover before any module uses the shared Lit.
    move(parent, node, before) {
      return parent.insertBefore(node, before);
    },
    fragmentId,
    externalLinks: {
      attributes: EXTERNAL_LINK_ATTRIBUTES,
      matches: isExternalPageLink,
      arrive: renderExternalLink,
      leave: leaveExternalLink,
    },
    keepsAttribute,
    setRuntimeRootAttribute,
    runtimeRootAttributes: (node) => new Set(runtimeAttributes.get(node) ?? []),
    setRuntimeRootStyle,
    removeRuntimeRootStyle,
    wear,
    runtimeRootStyles: (node) => new Set(runtimeStyles.get(node) ?? []),
    authoredShell: (node) => sourceShells.get(node) ?? sources.get(node) ?? node,
    marginContentLayout,
    breakouts,
    layoutBox,
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
      for (let node = /** @type {Node} */ (host); node; node = node.parentNode)
        sourceScopes.add(node);
      const drawing = render(host, {
        tabStore,
        offer,
        offerElement,
        offerAction,
        offerActionElement,
        selectableOffer,
        selectableOfferElement,
        generatedElement,
        keeps: keepsAttribute,
        authoredBody(node) {
          node.append(...host.childNodes);
          authoredBodies.set(host, node);
          return node;
        },
      });
      if (drawing?.then)
        throw new TypeError(
          `initial renderer for <${host.localName}> must be synchronous`,
        );
      if (drawing !== null)
        root.lfInitial.lit.render(drawing.render(), drawing.root ?? host, { host });
      drawings.set(host, drawing);
      return drawing;
    },
    mount(host) {
      // The theme hides the host while any part of its source is still arriving
      // (`data-lf-arriving`, revision_delivery.mark_declared). Once its end tag has
      // parsed, show it and draw deepest-first in this same task: no frame can show
      // an unfinished or uninitialized instance.
      host.removeAttribute("data-lf-arriving");
      for (const node of [host, ...host.querySelectorAll("*")].reverse())
        if (producers.has(node.localName))
          this.paint(/** @type {HTMLElement} */ (node));
    },
    restoreSource(root) {
      for (const host of root.querySelectorAll("[data-lf-arriving]"))
        host.removeAttribute("data-lf-arriving");
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
    offerAction,
    offerActionElement,
    selectableOffer,
    selectableOfferElement,
    generatedElement,
    origin(node) {
      return origins.get(node);
    },
    authoredBody(host) {
      return authoredBodies.get(host) ?? null;
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
  const reloaded =
    /** @type {PerformanceNavigationTiming | undefined} */ (
      performance.getEntriesByType("navigation")[0]
    )?.type === "reload";
  const named = (members) => {
    if (!location.hash) return null;
    const target = document.getElementById(fragmentId(location.hash));
    return target && members.find((member) => member.contains(target));
  };
  // A member is kept by its own id, or by the first id inside it when it has none, as a
  // plain <figure> wrapping a recording does, and reopens as the member holding it.
  const kept = (holder, members) => {
    const id = tabStore.get(OPEN_KEY + holder.id);
    const target = id && document.getElementById(id);
    return target && members.find((member) => member.contains(target));
  };
  const choose = (holder, members, fallback = members[0]) =>
    (reloaded
      ? kept(holder, members) || named(members)
      : named(members) || kept(holder, members)) || fallback;

  // Until its module upgrades it, the holder's opening member wears `data-lf-opening`,
  // so its theme can show that member alone at first paint. Marked as the parser
  // inserts each holder and member, since a paint can come between any two of the
  // parser's tasks and never inside one, and a member parsed later may be the one that
  // opens. Parsing is over before any module runs, so nothing here races an upgrade.
  const OPENING = "data-lf-opening";
  // The opening view's only content block gets a marker so its first-paint height
  // rule need not put a structural selector over every element in the document.
  const SOLE_CONTENT = "data-lf-sole-content";
  const soleContents = new WeakMap();
  const soleContent = (member) => {
    let sole = null;
    for (const child of member.children) {
      if (child.matches("script, style, template")) continue;
      if (sole) return null;
      sole = child;
    }
    return sole;
  };
  const mark = () => {
    for (const holder of document.querySelectorAll("[data-lf-views]")) {
      const flow = getComputedStyle(holder).getPropertyValue("--lf-views-flow").trim();
      if (flow && holder.getAttribute("data-lf-views-flow") !== flow)
        holder.setAttribute("data-lf-views-flow", flow);
      const members = [...holder.children];
      const open = choose(holder, members);
      for (const member of members) {
        if (member.hasAttribute(OPENING) !== (member === open))
          member.toggleAttribute(OPENING, member === open);
        const sole = member === open ? soleContent(member) : null;
        const previous = soleContents.get(member);
        if (previous !== sole) {
          previous?.removeAttribute(SOLE_CONTENT);
          sole?.setAttribute(SOLE_CONTENT, "");
          soleContents.set(member, sole);
        }
      }
    }
  };
  const initialLayout = () => {
    mark();
    marginContentLayout();
    if (root.hasAttribute("data-lf-interactive")) trade("controls", PLAYER);
  };
  // Dress only links the parser added or is still filling. Unrelated arrivals
  // must not reparse every URL already on the page.
  const initialLinks = (records) => {
    const links = new Set();
    for (const { target, addedNodes } of records) {
      const owner = target instanceof Element && target.closest("a");
      if (owner) links.add(owner);
      for (const node of addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches("a")) links.add(node);
        for (const link of node.querySelectorAll("a")) links.add(link);
      }
    }
    for (const link of links) if (link.isConnected) renderExternalLink(link);
  };
  const parsing = new MutationObserver((records) => {
    initialLinks(records);
    initialLayout();
  });
  parsing.observe(root, { childList: true, subtree: true });
  document.addEventListener(
    "readystatechange",
    () => {
      initialLinks(parsing.takeRecords());
      initialLayout();
      parsing.disconnect();
    },
    { once: true },
  );

  // The holder's module asks once, as it upgrades, which member opens, and from then on
  // shows that member itself, so the mark comes off. It records each member it shows,
  // which a reload reopens (storage.js). A holder that chooses its own first member
  // where neither the tab nor the address names one passes `fallback`, as null.
  root.lfViews = {
    opening(holder, members, fallback) {
      for (const member of holder.querySelectorAll(`:scope > [${OPENING}]`))
        member.removeAttribute(OPENING);
      for (const member of members)
        soleContents.get(member)?.removeAttribute(SOLE_CONTENT);
      return choose(holder, members, fallback);
    },
    keep(holder, member) {
      tabStore.set(OPEN_KEY + holder.id, member.id || member.querySelector("[id]")?.id);
    },
  };
})();
