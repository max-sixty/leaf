/* lf-file-tree: a navigator over a declared file list, supplied by a source or by
 * another widget's `files` output. Its only cross-widget operation is Leaf's declared
 * datum reveal (`NavigateToDatum`, widget-services.js); nothing the reader does in the
 * tree enters Leaf's event log.
 *
 * An Effect UI component (runtime/effect-widget.js) draws the navigator's chrome, its
 * search field and empty state, and one container the rows draw in. Pierre Trees draws
 * the rows there, virtualized, and owns their paths, sorting, folder expansion, focus
 * and selection. One stream mount (`DrawTrees`) owns the Trees instance: it feeds it
 * each new file list, `current` file and query from the mount's args, and sends what
 * the reader does in the rows back as messages. The Model holds the search query, which
 * the reader types in the component's own field, and whether the query leaves any row.
 *
 * Trees draws into a shadow root on the container, staged as Leaf's (`shadowStage`) so
 * Leaf's focus and arrival observers see its controls; Leaf's sheets go back on it
 * after Trees adopts its own. One model survives updates and departures. Identical
 * paths leave it untouched; changed paths retain the surviving focus, selection and
 * the folders the reader closed, closed folders inside another closed one included;
 * every other folder, a new one included, opens.
 *
 * In the search, ↓ goes to the first matching file's row and Enter chooses it and
 * empties the search; Escape empties it, there or on a row. A letter typed on a row
 * types into the search. Opening a file empties it too. Upstream reports selection
 * changes rather than activation, and a repeated selection reports nothing, so a row's
 * activation is an ordinary click or the row's declared keys, reading the focused item
 * through Trees' model. Each row is a native button whose own key scope must precede
 * native activation, so the scope stands on the focused row. */
import {
  Effect,
  Html,
  HtmlCommand,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
  Component,
} from "/vendor/effect-ui.js";
import {
  focusDestination,
  onCurrentLocation,
  scrollIntoView,
  shadowStage,
} from "/runtime/widget-api.js";
import { NavigateToDatum } from "/runtime/widget-services.js";
import { PRESS, plainPress } from "/runtime/lib/keys.js";
import { COMMANDS } from "/runtime/lib/widget-events.js";
import { keeps } from "/runtime/lib/keeps.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";

const Status = Schema.Literals(["added", "modified", "deleted", "renamed"]);
const Files = Schema.Array(
  Schema.Struct({
    path: Schema.String,
    key: Schema.optional(Schema.String),
    status: Schema.optional(Status),
  }),
);

const FileTreeProps = Schema.Struct({
  ...widgetProps,
  // The file list Leaf sets from the bound source or widget, null while it has none.
  value: Schema.optional(
    Schema.NullOr(
      Schema.Struct({ files: Files, current: Schema.optional(Schema.String) }),
    ),
  ),
  label: Schema.String,
  linked: Schema.Boolean,
});
const FileTreeModel = Schema.Struct({ query: Schema.String, rows: Schema.Number });
export const FileTreeMessage = UiSchema.TaggedEnum({
  UpdatedQuery: { value: Schema.String },
  PressedEscape: {},
  ChoseMatch: {},
  ClosedTreeSearch: {},
  TypedOnRow: { key: Schema.String },
  OpenedFile: { path: Schema.String },
  CountedRows: { rows: Schema.Number },
});

const Search = Html.ref("FileTree.search", "input");
const silent = () => Component.noop;

let library;
const loadTrees = () => (library ??= import("/vendor/pierre-trees.esm.js"));

// Every folder the paths stand in, in Trees' canonical form, ending in a slash.
/** @param {readonly string[]} paths */
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
/** @param {import("@pierre/trees").FileTree} tree @param {string} path */
const selectOnly = (tree, path) => {
  for (const selected of tree.getSelectedPaths())
    if (selected !== path) tree.getItem(selected)?.deselect();
  tree.getItem(path)?.select();
};
/** @param {EventTarget} target */
const commandsChanged = (target) =>
  target.dispatchEvent(new CustomEvent(COMMANDS, { bubbles: true, composed: true }));
/** @param {{key: string, altKey: boolean, ctrlKey: boolean, metaKey: boolean}} event */
const typed = ({ key, altKey, ctrlKey, metaKey }) =>
  [...key].length === 1 && key !== " " && !altKey && !ctrlKey && !metaKey;

// Trees on the container: the args feed it, and what the reader does in its rows
// comes back as messages.
const DrawTrees = Mount.makeStream(
  "DrawTrees",
  {
    args: {
      files: Files,
      current: Schema.optional(Schema.String),
      query: Schema.String,
      label: Schema.String,
    },
  },
  (/** @type {HTMLElement} */ node, args, changes) =>
    Stream.callback((/** @type {any} */ queue) =>
      Effect.gen(function* () {
        const { FileTree } = yield* Effect.promise(loadTrees);
        /** @param {unknown} message */
        const send = (message) => Queue.offerUnsafe(queue, message);
        const outer = /** @type {ShadowRoot} */ (node.getRootNode());
        const host = /** @type {HTMLElement} */ (outer.host);
        const stage = shadowStage(node, []);
        /** @type {string[]} */
        let paths = args.files.map((file) => file.path);
        let query = "";
        let rows = -1;
        const tree = new FileTree({
          paths,
          initialExpansion: "open",
          // The virtualizer and the drawn rows use the same hit-target height.
          itemHeight: matchMedia("(pointer: coarse)").matches ? 44 : 30,
        });
        const onRow = () => stage.activeElement?.getAttribute("role") === "treeitem";
        const activate = (/** @type {boolean} */ toggleDirectory) => {
          const item = tree.getFocusedItem();
          if (!item) return;
          if ("toggle" in item) {
            if (toggleDirectory) item.toggle();
            return;
          }
          selectOnly(tree, item.getPath());
          send(FileTreeMessage.OpenedFile({ path: item.getPath() }));
        };
        /** @type {HTMLElement["lfCommands"]} */
        const fileActions = {
          title: "In files",
          rows: [
            {
              id: "files.open",
              title: "Open file or toggle folder",
              keys: PRESS,
              when: onRow,
              run: () => activate(true),
            },
            {
              id: "files.walk",
              title: "Move among files and folders",
              keys: ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End"],
              when: onRow,
            },
          ],
        };
        // The first file the search leaves, focused as a row.
        const toMatch = () => {
          const count = tree.getVisibleCount();
          const match = count
            ? tree.getVisibleRows(0, count - 1).find((/** @type {{path: string, kind: string}} */ row) => row.kind !== "directory")
            : undefined;
          if (!match) return false;
          tree.focusPath(match.path);
          const row = stage.querySelector(
            `[data-item-path="${CSS.escape(match.path)}"]`,
          );
          if (row instanceof HTMLElement) focusDestination(row, "move");
          return true;
        };
        /** @param {typeof args} next */
        const apply = (next) => {
          const nextPaths = next.files.map((file) => file.path);
          if (
            paths.length !== nextPaths.length ||
            paths.some((path, index) => path !== nextPaths[index])
          ) {
            // A new model opens every folder (`initialExpansion`), so the folders the
            // reader closed are read from the old one and closed again.
            const closed = folders(paths).filter(
              (folder) => !directory(tree, folder)?.isExpanded(),
            );
            tree.resetPaths(nextPaths);
            paths = nextPaths;
            for (const folder of closed) directory(tree, folder)?.collapse();
          }
          tree.setGitStatus(
            next.files.flatMap(({ path, status }) => (status ? [{ path, status }] : [])),
          );
          if (next.current) selectOnly(tree, next.current);
          if (next.query !== query) {
            query = next.query;
            if (query) tree.setSearch(query);
            else if (tree.getSearchValue() !== null) tree.closeSearch();
          }
          keeps(stage.querySelector('[role="tree"]'), "aria-label", next.label);
        };
        yield* Effect.acquireRelease(
          Effect.sync(() => {
            tree.render({ fileTreeContainer: node });
            // Trees has adopted its sheet; restaging puts Leaf's back beside it and
            // keeps Trees' nodes.
            shadowStage(
              node,
              [...stage.childNodes].filter(
                (child) =>
                  !(child instanceof HTMLStyleElement && child.hasAttribute("data-lf-gen")),
              ),
            );
            for (const child of stage.children) child.classList.add("lf-ui");
            apply(args);
            send(FileTreeMessage.CountedRows({ rows: (rows = tree.getVisibleCount()) }));
            const stopModel = tree.subscribe(() => {
              // Trees closes its search for Escape on a row.
              if (query && tree.getSearchValue() === null)
                send(FileTreeMessage.ClosedTreeSearch());
              const count = tree.getVisibleCount();
              if (count !== rows) send(FileTreeMessage.CountedRows({ rows: (rows = count) }));
            });
            const controller = new AbortController();
            const { signal } = controller;
            node.addEventListener(
              "click",
              (event) => {
                // A modified click keeps its usual meaning.
                if (
                  plainPress(event) &&
                  event
                    .composedPath()
                    .some(
                      (target) =>
                        target instanceof HTMLElement &&
                        target.getAttribute("role") === "treeitem",
                    )
                )
                  activate(false);
              },
              { signal },
            );
            stage.addEventListener(
              "keydown",
              (pressed) => {
                const event = /** @type {KeyboardEvent} */ (pressed);
                if (!event.defaultPrevented && onRow() && typed(event)) {
                  event.preventDefault();
                  send(FileTreeMessage.TypedOnRow({ key: event.key }));
                }
              },
              { signal },
            );
            outer.addEventListener(
              "keydown",
              (pressed) => {
                const event = /** @type {KeyboardEvent} */ (pressed);
                const field = event.composedPath()[0];
                if (!(field instanceof HTMLInputElement) || !field.value || event.isComposing)
                  return;
                if (event.key === "ArrowDown" || event.key === "Enter") {
                  if (toMatch()) event.preventDefault();
                  if (event.key === "Enter") send(FileTreeMessage.ChoseMatch());
                }
              },
              { signal },
            );
            // Trees scrolls its virtualized list and focuses with preventScroll. The
            // row can still lie outside Leaf's outer reading viewport, so that reveal
            // goes to the scrolling owner every widget uses. A row the user pressed is
            // where they aimed, so it stays there: focus arrives on the press's
            // mousedown, and a reveal there would move the row from under the pointer
            // before the mouseup, which would fall on another row and open neither.
            const stopLocation = onCurrentLocation(
              (
                /** @type {Element | null} */ place,
                /** @type {string} */ cause,
                /** @type {Element | null} */ left,
              ) => {
                // Only the focused row carries the rows' scope, so a row focus has
                // left names no keys.
                if (left !== place && left?.lfCommands === fileActions) {
                  left.lfCommands = null;
                  commandsChanged(left);
                }
                // A route to this navigator lands on its search.
                if (place === host) {
                  const search = outer.querySelector("input");
                  if (search) focusDestination(search, "return");
                }
                if (place?.getAttribute("role") === "treeitem" && stage.contains(place)) {
                  place.lfCommands = fileActions;
                  commandsChanged(place);
                  if (cause !== "press") scrollIntoView(place, { block: "nearest" });
                }
              },
            );
            return () => {
              stopLocation();
              controller.abort();
              stopModel();
              tree.unmount();
            };
          }),
          (release) => Effect.sync(release),
        );
        yield* Stream.runForEach(changes, (next) => Effect.sync(() => apply(next))).pipe(
          Effect.forkScoped,
        );
      }),
    ),
);

export const FileTree = Html.component({
  name: "FileTree",
  props: FileTreeProps,
  model: FileTreeModel,
  message: FileTreeMessage,
}).make({
  init: () => ({ query: "", rows: -1 }),
  update: ($, message) =>
    FileTreeMessage.match(message, {
      UpdatedQuery: ({ value }) => $.evolve({ query: value }),
      PressedEscape: () => $.evolve({ query: "" }),
      ChoseMatch: () => $.evolve({ query: "" }),
      ClosedTreeSearch: () => $.evolve({ query: "" }),
      TypedOnRow: ({ key }) =>
        $.evolve({ query: (query) => query + key }).run(HtmlCommand.focus(Search, silent)),
      CountedRows: ({ rows }) => $.evolve({ rows }),
      OpenedFile: ({ path }) => {
        const step = $.evolve({ query: "" });
        const key = $.props.value?.files.find((file) => file.path === path)?.key;
        return $.props.linked && key
          ? step.run(
              NavigateToDatum.make({
                reference: "for",
                key,
                success: `Opened ${path}.`,
                missing: `${path} is no longer available.`,
              }),
            )
          : step;
      },
    }),
  view: (h, model) => {
    const { value, label } = h.props;
    const files = value?.files ?? [];
    const empty = !value
      ? "No files available."
      : !files.length
        ? "No files."
        : model.query && model.rows === 0
          ? "No matching files."
          : null;
    return h.div.class("lf-file-tree lf-ui").children(
      files.length
        ? h.input
            .ref(Search)
            .class("lf-file-tree-search")
            .attrs({
              type: "text",
              name: "files",
              "aria-label": `Search ${label}`,
              placeholder: "Search…",
              autocomplete: "off",
              spellcheck: "false",
            })
            .value(model.query)
            .on("input", ({ value }) => FileTreeMessage.UpdatedQuery({ value }))
            .on(
              "keydown",
              ({ key, composing }) =>
                key === "Escape" && model.query && !composing
                  ? FileTreeMessage.PressedEscape()
                  : undefined,
              { preventDefault: true },
            )
        : null,
      h.div
        .class("lf-file-tree-rows")
        .attr("hidden", files.length ? undefined : "")
        .onMount(
          DrawTrees({
            files,
            ...(value?.current ? { current: value.current } : {}),
            query: model.query,
            label,
          }).pipe(Mount.map((/** @type {any} */ message) => message)),
        ),
      empty ? h.p.class("lf-file-tree-empty").children(empty) : null,
    );
  },
});

defineWidget("lf-file-tree", FileTree, {
  shadow: true,
  properties: ["value"],
  inputs: (element) => ({
    label: element.getAttribute("aria-label") || "Files",
    linked: element.hasAttribute("for"),
  }),
});
