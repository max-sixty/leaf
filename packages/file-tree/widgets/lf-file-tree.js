/* lf-file-tree: a navigator over a declared file list, supplied by a source or by
 * another widget's `files` output. Its only cross-widget operation is Leaf's declared
 * datum reveal (`NavigateToDatum`, widget-services.js); nothing the reader does in the
 * tree enters Leaf's event log.
 *
 * An Effect UI component (runtime/effect-widget.js) draws the list from its `value`
 * property. The Model holds what the reader is doing: the search query, the folders
 * they closed, the row that holds the tree's one tab stop, and the file they picked.
 * Every folder opens at first, a new one included, and a folder the reader closed stays
 * closed for as long as its path is in the list. The picked file is the selection
 * unless the list names a `current` file, the one its viewer shows.
 *
 * The tree is the ARIA tree pattern over native buttons, one row per visible folder or
 * file, flat with `aria-level`: ↑ ↓ Home End move among rows, → opens a folder or
 * enters it, ← closes it or goes to its parent, and Enter or Space presses the row's
 * button, which toggles a folder or opens a file. A folder holding only one folder
 * shows as one row, `a/b`. Search keeps the files whose path holds the query, with
 * their folders, under the same expansion. A letter typed on a row types into it; ↓
 * there goes to the first match, Enter chooses it and empties the search, and Escape
 * empties it. Opening a file empties it too.
 *
 * One mount (`AttachToLeaf`) joins the drawn tree to Leaf's keyboard and focus: it
 * names the rows' keys as the element's `lfCommands`, reveals a row the keyboard
 * reaches in Leaf's reading viewport, and puts a route that lands on the navigator in
 * its search. Rows take focus with `preventScroll`, so that reveal is the only scroll. */
import {
  Component,
  Effect,
  Html,
  HtmlCommand,
  Mount,
  Schema,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  focusDestination,
  onCurrentLocation,
  scrollIntoView,
} from "/runtime/widget-api.js";
import { NavigateToDatum } from "/runtime/widget-services.js";
import { PRESS } from "/runtime/lib/keys.js";
import { COMMANDS } from "/runtime/lib/widget-events.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";

const Status = Schema.Literals(["added", "modified", "deleted", "renamed"]);
const FileList = Schema.Struct({
  files: Schema.Array(
    Schema.Struct({
      path: Schema.String,
      key: Schema.optional(Schema.String),
      status: Schema.optional(Status),
    }),
  ),
  current: Schema.optional(Schema.String),
});

const FileTreeProps = Schema.Struct({
  ...widgetProps,
  // The file list Leaf sets from the bound source or widget, null while it has none.
  value: Schema.optional(Schema.NullOr(FileList)),
  label: Schema.String,
  linked: Schema.Boolean,
});
const FileTreeModel = Schema.Struct({
  query: Schema.String,
  closed: Schema.Array(Schema.String),
  active: Schema.NullOr(Schema.String),
  picked: Schema.NullOr(Schema.String),
});
export const FileTreeMessage = UiSchema.TaggedEnum({
  UpdatedQuery: { value: Schema.String },
  PressedSearchKey: { key: Schema.String },
  ClickedRow: { id: Schema.String },
  PressedRowKey: { id: Schema.String, key: Schema.String },
});

const Search = Html.ref("FileTree.search", "input");
const Row = Html.ref("FileTree.row", "button");
const silent = () => Component.noop;
const quietly = { preventScroll: true };

/**
 * @typedef {typeof FileList.Type["files"][number]} File
 * @typedef {{name: string, path: string, file: File | null, children: Map<string, Folder>}} Folder
 * @typedef {{id: string, path: string, name: string, level: number, size: number,
 *   position: number, parent: string | null, folder: boolean, open: boolean,
 *   file: File | null}} TreeRow
 */

/** The folder tree the paths stand in. @param {readonly File[]} files */
const grow = (files) => {
  /** @type {Folder} */
  const root = { name: "", path: "", file: null, children: new Map() };
  for (const file of files) {
    const parts = file.path.split("/");
    let node = root;
    parts.forEach((part, index) => {
      let child = node.children.get(part);
      if (!child) {
        child = {
          name: part,
          path: parts.slice(0, index + 1).join("/"),
          file: null,
          children: new Map(),
        };
        node.children.set(part, child);
      }
      if (index === parts.length - 1) child.file = file;
      node = child;
    });
  }
  return root;
};

const collator = new Intl.Collator(undefined, { numeric: true });
/** Folders first, then files, each by name. @param {Folder} a @param {Folder} b */
const order = (a, b) =>
  Number(Boolean(a.file)) - Number(Boolean(b.file)) || collator.compare(a.name, b.name);

/**
 * The rows the reader can see, in order.
 * @param {readonly File[]} files @param {{query: string, closed: readonly string[]}} model
 * @returns {TreeRow[]}
 */
export const visibleRows = (files, { query, closed }) => {
  const needle = query.toLowerCase();
  /** @param {Folder} node @returns {boolean} */
  const shown = (node) =>
    node.file
      ? node.file.path.toLowerCase().includes(needle)
      : [...node.children.values()].some(shown);
  const shut = new Set(closed);
  /** @type {TreeRow[]} */
  const rows = [];
  /** @param {Folder} folder @param {number} level @param {string | null} parent */
  const walk = (folder, level, parent) => {
    const children = [...folder.children.values()].filter(shown).sort(order);
    children.forEach((start, index) => {
      let node = start;
      let name = node.name;
      // A folder holding only one folder is one row.
      while (!node.file && node.children.size === 1) {
        const only = /** @type {Folder} */ (node.children.values().next().value);
        if (only.file) break;
        node = only;
        name = `${name}/${node.name}`;
      }
      const folderRow = !node.file;
      const open = folderRow && !shut.has(node.path);
      const id = `${folderRow ? "folder" : "file"}:${node.path}`;
      rows.push({
        id,
        path: node.path,
        name,
        level,
        size: children.length,
        position: index + 1,
        parent,
        folder: folderRow,
        open,
        file: node.file,
      });
      if (open) walk(node, level + 1, id);
    });
  };
  walk(grow(files), 1, null);
  return rows;
};

/** @param {readonly TreeRow[]} rows @param {string | null} active */
const tabStop = (rows, active) => rows.find((row) => row.id === active) ?? rows[0];

/** @param {any} $ @param {TreeRow | undefined} row */
const goTo = ($, row) =>
  row
    ? $.evolve({ active: row.id }).run(
        HtmlCommand.focus(Row.at(row.id), silent, quietly),
      )
    : $.model;

/** @param {any} $ @param {TreeRow} row @param {boolean} open */
const setOpen = ($, row, open) =>
  $.evolve({
    active: row.id,
    closed: (/** @type {readonly string[]} */ closed) =>
      open ? closed.filter((path) => path !== row.path) : [...closed, row.path],
  });

/** @param {string} key @param {{alt: boolean, ctrl: boolean, meta: boolean}} mods */
const typed = (key, { alt, ctrl, meta }) =>
  [...key].length === 1 && key !== " " && !alt && !ctrl && !meta;

const ROW_KEYS = new Set([
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Home",
  "End",
]);

// Joins the drawn tree to Leaf: the rows' keys, the reveal of a row the keyboard
// reaches, and a route's landing on the navigator.
const AttachToLeaf = Mount.make(
  "AttachToLeaf",
  {},
  (/** @type {HTMLElement} */ node) => {
    const root = /** @type {ShadowRoot} */ (node.getRootNode());
    const host = /** @type {HTMLElement} */ (root.host);
    const onRow = () => root.activeElement?.getAttribute("role") === "treeitem";
    const announce = () =>
      host.dispatchEvent(new CustomEvent(COMMANDS, { bubbles: true, composed: true }));
    return Effect.acquireRelease(
      Effect.sync(() => {
        host.lfCommands = {
          title: "In files",
          rows: [
            {
              id: "files.open",
              title: "Open file or toggle folder",
              keys: PRESS,
              when: onRow,
            },
            {
              id: "files.walk",
              title: "Move among files and folders",
              keys: [...ROW_KEYS],
              when: onRow,
            },
          ],
        };
        announce();
        return onCurrentLocation(
          (/** @type {Element | null} */ place, /** @type {string} */ cause) => {
            if (place === host) {
              const search = root.querySelector("input");
              if (search) focusDestination(search, "return");
            } else if (
              place?.getAttribute("role") === "treeitem" &&
              root.contains(place) &&
              // A row the user pressed is where they aimed, so it stays under the
              // pointer until the press ends.
              cause !== "press"
            )
              scrollIntoView(place, { block: "nearest" });
          },
        );
      }),
      (stop) =>
        Effect.sync(() => {
          stop();
          host.lfCommands = null;
          announce();
        }),
    ).pipe(Effect.as(Component.noop));
  },
);

export const FileTree = Html.component({
  name: "FileTree",
  props: FileTreeProps,
  model: FileTreeModel,
  message: FileTreeMessage,
}).make({
  init: () => ({ query: "", closed: [], active: null, picked: null }),
  update: ($, message) => {
    const files = $.props.value?.files ?? [];
    const rows = visibleRows(files, $.model);
    return FileTreeMessage.match(message, {
      UpdatedQuery: ({ value }) => $.evolve({ query: value }),
      PressedSearchKey: ({ key }) => {
        const match = rows.find((row) => !row.folder);
        switch (key) {
          case "Escape":
            return $.evolve({ query: "" });
          case "Enter":
            return match ? goTo($, match).evolve({ query: "" }) : $.model;
          default:
            return goTo($, $.model.query ? match : tabStop(rows, $.model.active));
        }
      },
      ClickedRow: ({ id }) => {
        const row = rows.find((row) => row.id === id);
        if (!row) return $.model;
        if (row.folder) return setOpen($, row, !row.open);
        const step = $.evolve({ active: row.id, picked: row.path, query: "" });
        const key = row.file?.key;
        return $.props.linked && key
          ? step.run(
              NavigateToDatum.make({
                reference: "for",
                key,
                success: `Opened ${row.path}.`,
                missing: `${row.path} is no longer available.`,
              }),
            )
          : step;
      },
      PressedRowKey: ({ id, key }) => {
        const index = rows.findIndex((row) => row.id === id);
        const row = rows[index];
        if (!row) return $.model;
        switch (key) {
          case "ArrowDown":
            return goTo($, rows[index + 1]);
          case "ArrowUp":
            return goTo($, rows[index - 1]);
          case "Home":
            return goTo($, rows[0]);
          case "End":
            return goTo($, rows.at(-1));
          case "ArrowRight":
            if (!row.folder) return $.model;
            return row.open ? goTo($, rows[index + 1]) : setOpen($, row, true);
          case "ArrowLeft":
            return row.folder && row.open
              ? setOpen($, row, false)
              : goTo(
                  $,
                  rows.find((other) => other.id === row.parent),
                );
          default:
            return $.evolve({ query: (query) => query + key }).run(
              HtmlCommand.focus(Search, silent),
            );
        }
      },
    });
  },
  view: (h, model) => {
    const { value, label } = h.props;
    const files = value?.files ?? [];
    const rows = visibleRows(files, model);
    const stop = tabStop(rows, model.active);
    const selected = value?.current ?? model.picked;
    const empty = !value
      ? "No files available."
      : !files.length
        ? "No files."
        : !rows.length
          ? "No matching files."
          : null;
    return h.div
      .class("lf-file-tree lf-ui")
      .onMount(AttachToLeaf())
      .children(
        files.length
          ? h.input
              .ref(Search)
              .class("lf-file-tree-search")
              .attrs({
                type: "text",
                name: "files",
                "aria-label": `Search ${label}`,
                placeholder: "Search",
                autocomplete: "off",
                spellcheck: "false",
              })
              .value(model.query)
              .on("input", ({ value }) => FileTreeMessage.UpdatedQuery({ value }))
              .on(
                "keydown",
                ({ key, composing }) =>
                  !composing &&
                  (((key === "Escape" || key === "Enter") && model.query) ||
                    (key === "ArrowDown" && rows.length))
                    ? FileTreeMessage.PressedSearchKey({ key })
                    : undefined,
                { preventDefault: true },
              )
          : null,
        files.length
          ? h.div
              .class("lf-file-tree-rows")
              .attrs({ role: "tree", "aria-label": label })
              .children(
                rows.map((row) => {
                  const status = row.file?.status;
                  return h.button
                    .key(row.id)
                    .ref(Row.at(row.id))
                    .class("lf-file-tree-row")
                    .attrs({
                      type: "button",
                      role: "treeitem",
                      tabindex: row === stop ? "0" : "-1",
                      "aria-level": String(row.level),
                      "aria-setsize": String(row.size),
                      "aria-posinset": String(row.position),
                      "aria-expanded": row.folder ? String(row.open) : undefined,
                      "aria-selected": String(!row.folder && row.path === selected),
                      "aria-description": status,
                      "data-status": status,
                    })
                    .style({ "--lf-file-tree-level": String(row.level) })
                    .on("click", ({ button, alt, ctrl, meta, shift }) =>
                      // A modified press keeps its usual meaning.
                      button === 0 && !alt && !ctrl && !meta && !shift
                        ? FileTreeMessage.ClickedRow({ id: row.id })
                        : undefined,
                    )
                    .on(
                      "keydown",
                      ({ key, composing, ...mods }) =>
                        !composing && (ROW_KEYS.has(key) || typed(key, mods))
                          ? FileTreeMessage.PressedRowKey({ id: row.id, key })
                          : undefined,
                      { preventDefault: true },
                    )
                    .children(
                      h.span
                        .class(row.folder ? "lf-file-tree-twisty" : "lf-file-tree-leaf")
                        .attr("aria-hidden", "true"),
                      h.span.class("lf-file-tree-name").children(row.name),
                      status
                        ? h.span
                            .class("lf-file-tree-status")
                            .attr("aria-hidden", "true")
                            .children(status.charAt(0).toUpperCase())
                        : null,
                    );
                }),
              )
          : null,
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
