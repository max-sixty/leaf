/* A file tree consumes a declared file-list input, whether supplied by a source or
 * another widget. Its only cross-widget operation is Leaf's declared datum reveal.
 * Trees owns paths, sorting, search, folder expansion, selection and virtualization;
 * none of that mechanical reading state enters Leaf's event log.
 *
 * One upstream model survives updates and departures. Identical paths leave the
 * model untouched; changed paths retain surviving focus, selection, active search, and the
 * folders the reader expanded, including expanded descendants of a closed folder.
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
import {
  PRESS,
  commands,
  commandScope,
  focused,
  focusDestination,
  keeps,
  navigateToDatum,
  offer,
  LeafElement,
  render,
  onCurrentLocation,
  paintKeys,
  plainPress,
  scrollIntoView,
  shadowStage,
  whileConnected,
} from "/runtime/widget-api.js";

let library;
const loadTrees = () => (library ??= import("/vendor/pierre-trees.esm.js"));

customElements.define(
  "lf-file-tree",
  class extends LeafElement {
    // The file list, set by whoever hosts the widget: Leaf from the bound source or
    // diff (the registry's `x-data.files.property`), or null while it has none.
    static properties = { value: { attribute: false } };

    constructor() {
      super();
      this.value = null;
    }

    // The file list the last render read, the one last applied, and its application.
    #delivered;
    #shown;
    #applied;
    #emptyRoot;
    #empty = "No files available.";

    createRenderRoot() {
      return this.#emptyRoot;
    }

    setup() {
      const empty = (this.#emptyRoot = offer("p", "lf-file-tree-empty"));
      const root = shadowStage(this, [empty]);
      const theme = root.firstChild;
      const label = this.getAttribute("aria-label") || "Files";
      keeps(this, "aria-label", label);

      let tree = null;
      let files = [];
      let paths = [];
      let mounted = false;
      let available = false;
      let stopModel = null;
      let generation = 0;
      const expanded = new Set();
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
      const rememberExpansion = () => {
        if (!tree) return;
        for (const row of tree.getVisibleRows(0, tree.getVisibleCount() - 1)) {
          if (row.kind !== "directory") continue;
          if (row.isExpanded) expanded.add(row.path);
          else expanded.delete(row.path);
        }
        paintEmpty();
        paintKeys();
      };
      const mount = () => {
        if (!tree || mounted || !files.length) return;
        tree.render({ fileTreeContainer: this });
        // Upstream has adopted its sheet and appended its nodes. Restaging shares
        // that sheet with Leaf's and retains those exact nodes and the theme.
        const nodes = [...root.childNodes].filter(
          (node) => node !== theme && node !== empty,
        );
        for (const node of nodes)
          if (node instanceof HTMLElement) node.classList.add("lf-ui");
        shadowStage(this, [...nodes, empty]);
        keeps(root.querySelector('[role="tree"]'), "aria-label", label);
        const search = root.querySelector("input");
        keeps(search, "aria-label", `Search ${label}`);
        keeps(search, "name", "files");
        stopModel = tree.subscribe(rememberExpansion);
        mounted = true;
      };
      const focusedRow = () => {
        const element = focused();
        return element?.getAttribute("role") === "treeitem" && root.contains(element);
      };
      const selectOnly = (path) => {
        for (const selected of tree.getSelectedPaths())
          if (selected !== path) tree.getItem(selected)?.deselect();
        tree.getItem(path)?.select();
      };
      const activate = (toggleDirectory) => {
        const item = tree?.getFocusedItem();
        if (!item) return;
        if (item.isDirectory()) {
          if (toggleDirectory) item.toggle();
          return;
        }
        selectOnly(item.getPath());
        const file = files.find((entry) => entry.path === item.getPath());
        if (this.hasAttribute("for") && file?.key)
          void navigateToDatum(this, "for", file.key, {
            focus: false,
            success: `Opened ${file.path}.`,
            missing: `${file.path} is no longer available.`,
          });
      };
      const fileActions = commandScope("In files", [
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
      ]);
      commands(this, fileActions);
      whileConnected(this, (signal) => {
        mount();
        // Trees scrolls its virtualized list and focuses with preventScroll. The
        // row can still lie outside Leaf's outer reading viewport, so hand that
        // remaining reveal to the same scrolling owner every widget uses.
        const stopCurrentLocation = onCurrentLocation((row) => {
          // A route to this navigator lands on its usable entry control.
          if (row === this) {
            const input = root.querySelector("input");
            if (input) focusDestination(input, "return");
          }
          if (row?.getAttribute("role") === "treeitem" && root.contains(row)) {
            // Each upstream row is a native button. Its exact scope precedes
            // native activation; an ancestor scope cannot own that press.
            commands(row, fileActions);
            scrollIntoView(row, { block: "nearest" });
          }
        });
        this.addEventListener(
          "click",
          (event) => {
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
        return () => {
          stopCurrentLocation();
          generation++;
          this.#shown = undefined;
          stopModel?.();
          stopModel = null;
          rememberExpansion();
          tree?.unmount();
          mounted = false;
        };
      });
      this.applyFiles = async (value) => {
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
          rememberExpansion();
          tree.resetPaths(nextPaths, { initialExpandedPaths: [...expanded] });
          paths = nextPaths;
          for (const path of expanded)
            if (!tree.getItem(path)?.isDirectory()) expanded.delete(path);
        }
        tree.setGitStatus(
          files
            .filter((file) => file.status)
            .map(({ path, status }) => ({ path, status })),
        );
        if (value?.current) selectOnly(value.current);
        if (!files.length) {
          stopModel?.();
          stopModel = null;
          tree.unmount();
          mounted = false;
          shadowStage(this, [empty]);
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
    updated(changed) {
      super.updated(changed);
      this.#applied =
        this.#delivered === this.#shown
          ? undefined
          : this.applyFiles((this.#shown = this.#delivered));
    }

    // Also waits for the drawing the latest update started: a newer update's drawing
    // replaces one still pending.
    async getUpdateComplete() {
      const result = await super.getUpdateComplete();
      await this.#applied;
      return result;
    }
  },
);
