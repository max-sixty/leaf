/* A file tree consumes a declared file-list input, whether supplied by a source or
 * another widget. Its only cross-widget operation is Leaf's declared datum reveal.
 * Trees owns paths, sorting, search, folder expansion, selection and virtualization;
 * none of that mechanical reading state enters Leaf's event log.
 *
 * One upstream model survives updates and departures. Identical paths leave the
 * model untouched; changed paths retain surviving focus, selection, active search, and the
 * folders the reader closed, including closed folders inside another closed one; every
 * other folder, a new one included, opens.
 * Search clears on blur or activation. Enter in search chooses a row; Enter on
 * that row opens its file through Leaf's ordinary datum route.
 * Trees draws into the widget's one declared shadow stage, sharing it with Leaf's
 * focus and arrival observers. No nested, unregistered shadow root holds controls.
 *
 * Upstream exposes selection changes rather than activation, and repeated selection
 * emits no change. Activation therefore uses ordinary click and declared keyboard
 * commands, reading the focused item through the public model. The standard ARIA
 * treeitem role distinguishes row clicks from search and other tree controls.
 */
import { render } from "/vendor/lit.js";
import { go } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { offer } from "/runtime/lib/controls.js";
import { PRESS, plainPress } from "/runtime/lib/keys.js";
import { keeps } from "/runtime/lib/keeps.js";

let library;
const loadTrees = () => (library ??= import("/vendor/pierre-trees.esm.js"));

// Every folder the paths stand in, in Trees' canonical form, ending in a slash.
/** @param {string[]} paths */
const folders = (paths) => {
  /** @type {Set<string>} */
  const found = new Set();
  for (const path of paths) {
    const parts = path.split("/");
    for (let depth = 1; depth < parts.length; depth++)
      found.add(`${parts.slice(0, depth).join("/")}/`);
  }
  return [...found];
};
/** @param {import("@pierre/trees").FileTree} tree @param {string} path
 * @returns {import("@pierre/trees").FileTreeDirectoryHandle | null} */
const directory = (tree, path) => {
  const item = tree.getItem(path);
  return item?.isDirectory()
    ? /** @type {import("@pierre/trees").FileTreeDirectoryHandle} */ (item)
    : null;
};

class FileTreeWidget extends LeafElement {
  // The file list, set by whoever hosts the widget: Leaf from the bound source or
  // diff (the registry's `inputs.files.property`), or null while it has none.
  static properties = { value: { attribute: false } };

  constructor() {
    super();
    /** @type {import("../../../browser/types/contract.js").DataFileList | null} */
    this.value = null;
  }

  // The file list the last render read, the one last applied, and its application.
  /** @type {import("../../../browser/types/contract.js").DataFileList | null | undefined} */
  #delivered;
  /** @type {import("../../../browser/types/contract.js").DataFileList | null | undefined} */
  #shown;
  /** @type {Promise<void> | undefined} */
  #applied;
  #emptyRoot = offer("p", "lf-file-tree-empty");
  // The open root the tree renders in, attached before the first `lf-connect`, so Leaf
  // dresses it then: the theme's style node first, and the shared sheets.
  #root = this.attachShadow({ mode: "open" });
  /** @type {ReturnType<FileTreeWidget["createTree"]> | undefined} */
  #apply;
  get #applyFiles() {
    return (this.#apply ??= this.createTree());
  }
  #empty = "No files available.";

  createRenderRoot() {
    return this.#emptyRoot;
  }

  // What each connection starts, and what its end stops.
  /** @type {((signal: AbortSignal) => void) | null} */
  #connect = null;
  /** @type {(() => void) | null} */
  #disconnect = null;
  #connection = new AbortController();

  setup() {
    void this.#applyFiles;
  }

  connectedCallback() {
    super.connectedCallback();
    this.#connection = new AbortController();
    this.#connect?.(this.#connection.signal);
  }

  // A move keeps the mounted tree and the place the user scrolled it to.
  connectedMoveCallback() {}

  disconnectedCallback() {
    super.disconnectedCallback();
    this.#connection.abort();
    this.#disconnect?.();
  }

  createTree() {
    const empty = this.#emptyRoot;
    const root = this.#root;
    const theme = root.firstChild;
    root.append(empty);
    const label = this.getAttribute("aria-label") || "Files";
    keeps(this, "aria-label", label);

    /** @type {import("@pierre/trees").FileTree | null} */
    let tree = null;
    /** @type {import("../../../browser/types/contract.js").DataFileList["files"]} */
    let files = [];
    /** @type {string[]} */
    let paths = [];
    let mounted = false;
    let available = false;
    /** @type {(() => void) | null} */
    let stopModel = null;
    let generation = 0;
    const paintEmpty = () => {
      const noMatches = files.length > 0 && tree?.getVisibleCount() === 0;
      this.#empty = noMatches
        ? "No matching files."
        : available
          ? "No files."
          : "No files available.";
      keeps(empty, "hidden", files.length > 0 && !noMatches ? "" : null);
      render(this.#empty, empty, this.renderOptions);
    };
    // A change to the model, such as a key that moves focus or a letter typed in search,
    // reads no rows: what it costs doesn't grow with the tree.
    const modelChanged = () => {
      paintEmpty();
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    };
    const mount = () => {
      if (!tree || mounted || !files.length) return;
      // Upstream replaces the root's adopted sheets with its own and appends its
      // nodes after the theme and the empty line, so the sheets Leaf shared go back
      // after its own, and the empty line goes last.
      const shared = root.adoptedStyleSheets;
      tree.render({ fileTreeContainer: this });
      root.adoptedStyleSheets = [...new Set([...root.adoptedStyleSheets, ...shared])];
      for (const node of root.children)
        if (node instanceof HTMLElement && node !== theme && node !== empty)
          node.classList.add("lf-ui");
      root.append(empty);
      keeps(root.querySelector('[role="tree"]'), "aria-label", label);
      const search = root.querySelector("input");
      keeps(search, "aria-label", `Search ${label}`);
      keeps(search, "name", "files");
      stopModel = tree.subscribe(modelChanged);
      mounted = true;
    };
    const focusedRow = () => root.activeElement?.getAttribute("role") === "treeitem";
    /** @param {import("@pierre/trees").FileTree} tree @param {string} path */
    const selectOnly = (tree, path) => {
      for (const selected of tree.getSelectedPaths())
        if (selected !== path) tree.getItem(selected)?.deselect();
      tree.getItem(path)?.select();
    };
    const activate = (/** @type {boolean} */ toggleDirectory) => {
      const current = tree;
      if (!current) return;
      const item = current.getFocusedItem();
      if (!item) return;
      if ("toggle" in item) {
        if (toggleDirectory) item.toggle();
        return;
      }
      selectOnly(current, item.getPath());
      const file = files.find((entry) => entry.path === item.getPath());
      const id = this.getAttribute("for");
      const target = id
        ? /** @type {Document | ShadowRoot} */ (this.getRootNode()).getElementById(id)
        : null;
      if (target && file?.key)
        void go(target, {
          key: file.key,
          focus: false,
          success: `Opened ${file.path}.`,
          missing: `${file.path} is no longer available.`,
        });
    };
    /** @type {HTMLElement["lfCommands"]} */
    const fileActions = {
      title: "In files",
      rows: [
        {
          id: "files.open",
          title: "Open file or toggle folder",
          keys: PRESS,
          when: focusedRow,
          run: () => activate(true),
        },
        {
          id: "files.walk",
          title: "Move among files and folders",
          keys: ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"],
          when: focusedRow,
        },
      ],
    };
    this.lfCommands = fileActions;
    this.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    this.#connect = (signal) => {
      mount();
      // Trees scrolls its virtualized list and focuses with preventScroll. The
      // row can still lie outside the page's window, so a row the keyboard reached
      // comes in at the nearest edge. A row the user pressed is where they aimed, so it
      // stays there: focus arrives on the press's mousedown, and a reveal there would
      // move the row from under the pointer before the mouseup, which would fall on
      // another row and open neither.
      /** @param {EventTarget | null} node */
      const rowOf = (node) =>
        node instanceof HTMLElement && node.getAttribute("role") === "treeitem"
          ? node
          : null;
      /** @param {HTMLElement} row @param {typeof fileActions | null} commands */
      const scope = (row, commands) => {
        row.lfCommands = commands;
        row.dispatchEvent(
          new CustomEvent("lf-commands", { bubbles: true, composed: true }),
        );
      };
      // Only the focused row carries the rows' scope. Its `when` reads focus anywhere
      // in this tree, and Leaf reads a scope's rows again only as focus moves into, out
      // of or within that scope, so a row focus has left would go on naming its keys
      // as they stood when focus left it.
      root.addEventListener(
        "focusout",
        (event) => {
          const left = rowOf(event.target);
          if (left && left.lfCommands === fileActions) scope(left, null);
        },
        { signal },
      );
      root.addEventListener(
        "focusin",
        (event) => {
          const row = rowOf(event.target);
          if (!row) return;
          // Each upstream row is a native button. Its exact scope precedes native
          // activation; an ancestor scope cannot own that press.
          scope(row, fileActions);
          if (row.matches(":focus-visible")) row.scrollIntoView({ block: "nearest" });
        },
        { signal },
      );
      // A route to this navigator lands on its usable entry control.
      this.addEventListener(
        "focus",
        (event) => {
          if (event.composedPath()[0] !== this) return;
          root.querySelector("input")?.focus({ preventScroll: true });
        },
        { signal },
      );
      this.addEventListener(
        "click",
        (event) => {
          // A modified click keeps its usual meaning.
          if (
            plainPress(event) &&
            event
              .composedPath()
              .some(
                (node) =>
                  node instanceof HTMLElement &&
                  node.getAttribute("role") === "treeitem",
              )
          )
            activate(false);
        },
        { signal },
      );
    };
    this.#disconnect = () => {
      generation++;
      this.#shown = undefined;
      stopModel?.();
      stopModel = null;
      tree?.unmount();
      mounted = false;
    };
    return async (
      /** @type {import("../../../browser/types/contract.js").DataFileList | null | undefined} */ value,
    ) => {
      const current = ++generation;
      files = value?.files ?? [];
      available = value !== null;
      paintEmpty();
      if (!tree && files.length) {
        const { FileTree } = await loadTrees();
        if (current !== generation || !this.isConnected) return;
        tree = new FileTree({
          paths: files.map((file) => file.path),
          initialExpansion: "open",
          search: true,
          // The virtualizer and the drawn rows use the same hit-target height.
          itemHeight: matchMedia("(pointer: coarse)").matches ? 44 : 30,
        });
        paths = files.map((file) => file.path);
      }
      if (!tree) return;
      const nextPaths = files.map((file) => file.path);
      if (
        paths.length !== nextPaths.length ||
        paths.some((path, index) => path !== nextPaths[index])
      ) {
        // A new model opens every folder (`initialExpansion`), so the folders the
        // reader closed are read from the old one and closed again.
        const model = tree;
        const closed = folders(paths).filter(
          (folder) => !directory(model, folder)?.isExpanded(),
        );
        model.resetPaths(nextPaths);
        paths = nextPaths;
        for (const folder of closed) directory(model, folder)?.collapse();
      }
      tree.setGitStatus(
        files.flatMap(({ path, status }) => (status ? [{ path, status }] : [])),
      );
      if (value?.current) selectOnly(tree, value.current);
      if (!files.length) {
        stopModel?.();
        stopModel = null;
        tree.unmount();
        mounted = false;
        for (const node of [...root.childNodes])
          if (node !== theme && node !== empty) node.remove();
      } else mount();
      paintEmpty();
    };
  }

  render() {
    this.#delivered = this.value;
    return this.#empty;
  }

  // The tree loads and draws each list after the update that read it, and that
  // update's `updateComplete` waits for it.
  /** @param {import("lit").PropertyValues} changed */
  updated(changed) {
    super.updated(changed);
    this.#applied =
      this.#delivered === this.#shown
        ? undefined
        : this.#applyFiles((this.#shown = this.#delivered));
  }

  // Also waits for the drawing the latest update started: a newer update's drawing
  // replaces one still pending.
  async getUpdateComplete() {
    const result = await super.getUpdateComplete();
    await this.#applied;
    return result;
  }
}
customElements.define("lf-file-tree", FileTreeWidget);
