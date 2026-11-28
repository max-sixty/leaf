/* CallDiff owns the call hierarchy, status and source coordinates in its native JSON.
 * This widget draws trees[].tree as commentable evidence, retaining unchanged nodes
 * and deriving only the visible tree rails. Its optional locations are used directly,
 * including paths with whitespace; terminal output is never read back as data.
 * Each root keeps its disclosure separate from its source link. Every root opens as it
 * arrives, the maintainer's choice, so the whole capture reads at once; the toolbar's
 * Collapse all folds a long one.
 * Ordinary activation travels to the exact line (`NavigateToDatum`, widget-services.js);
 * modified activation keeps the native link's separate-tab, separate-window and
 * context-menu routes. CallDiff locations name the after tree for added and unchanged
 * rows, and the before tree for removed rows (calldiff's diffNode/pickLoc contract).
 * Source navigation keeps that side even when the same number names a different line
 * on the other side.
 * Comments stay bound to the capture's source revision: callee keys do not identify
 * persistent invocation instances.
 *
 * An Effect UI component (runtime/effect-widget.js) draws the document Leaf sets as
 * `value`, in a box after the element's (empty) authored content. Its Model is the
 * roots the reader folded, by root key, so a capture that keeps a root keeps its fold.
 * Rows are keyed by call within their root, so a row the next capture keeps under the
 * same root keeps its nodes, and the selection or focus on it. A row a capture moves
 * under another root is a new node there, in that root's fold, since Effect UI keys
 * children within one parent, and focus on the old one drops to the body. After each
 * commit the root says the
 * value it drew (`drawn`, host/element-data.js), so Leaf stamps the rows' datum marks
 * with that value's snapshot. */
import {
  Component,
  Effect,
  Html,
  Mount,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { Announce, NavigateToDatum } from "/runtime/widget-services.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { offerActionElement } from "/runtime/lib/controls.js";
import type {
  DataCalldiff,
  DataCalldiffNode,
} from "../../../browser/types/contract.js";

import { diffLocationKey } from "./diff-coordinates.js";

type Status = "unchanged" | "added" | "removed";
type CallRecord = {
  body: string;
  key: string;
  location: { text: string; path: string; line: number } | null;
  root: boolean;
  meta: boolean;
  status: Status;
  originPath: (string | number)[];
};

function recordsOf(document: DataCalldiff) {
  const meta: CallRecord = {
    body:
      (!document.trees.length && document.message) ||
      `calldiff diff ${document.from} → ${document.to}`,
    key: "meta",
    location: null,
    root: false,
    meta: true,
    status: "unchanged",
    originPath: [],
  };
  const occurrences = new Map<string, number>();
  const groups = document.trees.map(({ entry, tree }, treeIndex) => {
    const walk = (
      node: DataCalldiffNode,
      indent: string,
      last: boolean,
      root: boolean,
      originPath: (string | number)[],
    ): CallRecord[] => {
      const status = node.status === "same" ? "unchanged" : node.status;
      const location =
        node.file && node.line != null
          ? {
              text: `${node.file}:${node.line}${node.endLine != null && node.endLine !== node.line ? `-${node.endLine}` : ""}`,
              path: node.file,
              line: node.line,
            }
          : null;
      // Occurrences distinguish repeated native keys without tying a row to its parent.
      const keyParts = [entry, node.key, status, node.file, node.line];
      const occurrenceKey = JSON.stringify(keyParts);
      const occurrence = occurrences.get(occurrenceKey) ?? 0;
      occurrences.set(occurrenceKey, occurrence + 1);
      const record: CallRecord = {
        body: `${indent}${root ? "" : last ? "└─ " : "├─ "}${node.label}`,
        originPath,
        key: JSON.stringify([...keyParts, occurrence]),
        location,
        root,
        meta: false,
        status,
      };
      const rail = node.kind === "branch" || last || root ? "   " : "│  ";
      const childIndent = root ? "" : `${indent}${rail}`;
      return [
        record,
        ...node.children.flatMap((child, index) =>
          walk(child, childIndent, index === node.children.length - 1, false, [
            ...originPath,
            "children",
            index,
          ]),
        ),
      ];
    };
    const [root, ...children] = walk(tree, "", true, true, [
      "trees",
      treeIndex,
      "tree",
    ]);
    return { root: root!, children };
  });
  return { meta, groups };
}

const counted = (records: CallRecord[], status: Status) =>
  records.filter((record) => record.status === status).length;

function groupLabel(records: CallRecord[]) {
  const added = counted(records, "added");
  const removed = counted(records, "removed");
  const context = records.length - added - removed;
  return [
    added ? `${added} added` : "",
    removed ? `${removed} removed` : "",
    context ? `${context} context` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function labelOf(record: CallRecord) {
  if (record.meta) return record.body;
  const location = record.location ? ` at ${record.location.text}` : "";
  return `${record.status} call-tree item ${record.body.trim()}${location}`;
}

// The CallDiff document, compared by identity: Leaf names the snapshot that supplied
// a drawing by the value object it set.
const Document = Schema.declare(
  (value: unknown): value is DataCalldiff =>
    typeof value === "object" && value !== null,
);

const CallDiffProps = Schema.Struct({
  ...widgetProps,
  value: Schema.optional(Schema.NullOr(Document)),
  diff: Schema.String,
});

const CallDiffModel = Schema.Struct({ closed: Schema.Array(Schema.String) });

export const CallDiffMessage = UiSchema.TaggedEnum({
  ToggledGroup: { key: Schema.String, open: Schema.Boolean },
  ClickedToggle: {},
  ClickedLocation: { key: Schema.String, text: Schema.String },
});

// Expand all and Collapse all draw their action's symbol, which a view's attributes
// can't write (controls.js, `pressAttributes`), and say the count as their name.
const OfferToggle = Mount.make(
  "OfferToggle",
  { args: { action: Schema.String, label: Schema.String } },
  (node: HTMLButtonElement, _args, changes) =>
    Stream.runForEach(changes, ({ action, label }) =>
      Effect.sync(() => {
        offerActionElement(node, "symbol", "lf-call-toggle", label, { action });
      }),
    ).pipe(Effect.as(Component.noop)),
);

// After each commit, the element says the value it drew, and whether it drew one.
const ReportDrawn = Mount.make(
  "ReportDrawn",
  { args: { value: Schema.NullOr(Document) } },
  (node: HTMLElement, _args, changes) =>
    Stream.runForEach(changes, ({ value }) =>
      Effect.sync(() => {
        const element = node.parentElement?.closest("lf-call-diff");
        if (!element) return;
        element.classList.toggle("lf-rendered", value !== null);
        element.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
      }),
    ).pipe(Effect.as(Component.noop)),
);

const rootKeys = (value: DataCalldiff | null | undefined) =>
  value ? recordsOf(value).groups.map(({ root }) => root.key) : [];

export const CallDiff = Html.component({
  name: "CallDiff",
  props: CallDiffProps,
  model: CallDiffModel,
  message: CallDiffMessage,
}).make({
  init: () => ({ closed: [] }),
  update: {
    ToggledGroup: ($, { key, open }) =>
      $.evolve({
        closed: (closed) =>
          open
            ? closed.filter((folded) => folded !== key)
            : [...new Set([...closed, key])],
      }),
    ClickedToggle: ($) => {
      const keys = rootKeys($.props.value);
      const open = keys.some((key) => $.model.closed.includes(key));
      return $.evolve({ closed: open ? [] : keys }).run(
        Announce.make({
          words: `${open ? "Expanded" : "Collapsed"} all call-tree roots`,
        }),
      );
    },
    ClickedLocation: ($, { key, text }) =>
      $.run(
        NavigateToDatum.make({
          reference: "diff",
          key,
          success: `Opened ${text} in the exact patch`,
          missing: `${text} is not present in the exact patch`,
          focus: true,
        }),
      ),
  },
  view: (h, model) => {
    const value = h.props.value ?? null;
    const frame = h.div.style({ display: "contents" }).onMount(ReportDrawn({ value }));
    if (!value)
      return frame.children(
        h.div
          .class("lf-call-line lf-call-missing")
          .attr("data-lf-datum", "unavailable")
          .attr("data-lf-datum-label", "Call-diff data unavailable")
          .children("Waiting for call-diff data."),
      );

    const href = `#${h.props.diff}`;
    const locationLink = (record: CallRecord) => {
      const location = record.location;
      if (!location) return null;
      const key = diffLocationKey(
        location.path,
        record.status === "removed" ? "old" : "new",
        location.line,
      );
      return h.a
        .class("lf-call-location")
        .attr("href", href)
        .on(
          "click",
          // A modified click keeps the link's own meaning, such as opening a new tab.
          (press) =>
            press.button === 0 &&
            !press.alt &&
            !press.ctrl &&
            !press.meta &&
            !press.shift
              ? CallDiffMessage.ClickedLocation({ key, text: location.text })
              : undefined,
          { preventDefault: true },
        )
        .children(location.text);
    };
    // A drawn row's marks make it a datum on a Leaf page (`module-state.md`, "Marking
    // drawn data").
    const marks = (record: CallRecord): Record<string, string> => ({
      "data-lf-status": record.status,
      ...(record.root && { "data-lf-root": "" }),
      ...(record.meta && { "data-lf-meta": "" }),
      "data-lf-datum": record.key,
      "data-lf-datum-label": labelOf(record),
      "data-lf-origin-path": JSON.stringify(record.originPath),
    });
    const words = (record: CallRecord, count: string | null = null) => [
      h.span
        .class("lf-call-marker")
        .attr("aria-hidden", "true")
        .children(
          record.status === "added" ? "+" : record.status === "removed" ? "−" : " ",
        ),
      h.span.class("lf-call-body").children(record.body),
      record.root ? null : locationLink(record),
      count === null
        ? null
        : h.span.class("lf-call-group-count").attr("data-lf-gen", "1").children(count),
    ];

    const records = recordsOf(value);
    const rows = records.groups.flatMap(({ root, children }) => [root, ...children]);
    const roots = records.groups.length;
    const closed = new Set(model.closed);
    const expand = records.groups.some(({ root }) => closed.has(root.key));
    const rootsWord = roots === 1 ? "root" : "roots";
    return frame.children(
      h.div
        .style({ display: "contents" })
        .children(
          h.div
            .key("tools")
            .class("lf-call-tools")
            .children(
              // The counts are an account of the tree, not words the page holds, so
              // `data-lf-gen` takes them out of the version diff and makes each its own
              // passage cell, as `lf-diff` marks its own injected stat.
              h.p
                .class("lf-call-summary")
                .attr("data-lf-gen", "1")
                .children(
                  `${roots} changed ${rootsWord} · ${counted(rows, "added")} added · ${counted(rows, "removed")} removed · ${rows.length} items`,
                ),
              h.button
                .onMount(
                  OfferToggle({
                    action: expand ? "expand-all" : "collapse-all",
                    label: `${expand ? "Expand" : "Collapse"} all ${roots} call-tree ${rootsWord}`,
                  }),
                )
                .on("click", CallDiffMessage.ClickedToggle()),
            ),
          h.div
            .key("meta")
            .class("lf-call-line")
            .attrs(marks(records.meta))
            .children(...words(records.meta)),
          ...records.groups.flatMap(({ root, children }) => [
            // Source navigation and disclosure are separate controls: a link nested in
            // summary disappears from some accessibility readings. The summary stays the
            // tight root datum, and its source control stands beside it rather than
            // around the whole call tree.
            h.div
              .key(`location:${root.key}`)
              .class("lf-call-root-location")
              .attr("data-lf-status", root.status)
              .children(locationLink(root)),
            h.details
              .key(`group:${root.key}`)
              .class("lf-call-group")
              .attr("data-lf-call-group", root.key)
              .open(!closed.has(root.key))
              .on("toggle", ({ open }) =>
                CallDiffMessage.ToggledGroup({ key: root.key, open }),
              )
              .children(
                h.summary
                  .class("lf-call-line lf-call-group-summary lf-disclosure-marker")
                  .attrs(marks(root))
                  .children(...words(root, groupLabel([root, ...children]))),
                h.div
                  .class("lf-call-group-body lf-text-scroller")
                  .attr("data-lf-scroll", "")
                  .children(
                    ...children.map((record) =>
                      h.div
                        .key(record.key)
                        .class("lf-call-line")
                        .attrs(marks(record))
                        .children(...words(record)),
                    ),
                  ),
              ),
          ]),
        ),
    );
  },
});

defineWidget("lf-call-diff", CallDiff, {
  properties: ["value"],
  inputs: (element) => ({ diff: element.getAttribute("diff") ?? "" }),
});
