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
 * `value`, in a box after the element's (empty) authored content. Each root's fold is
 * the browser's, as root AGENTS.md has open disclosures, and no copy of it stands in
 * the Model: the view opens a root as it arrives and writes its `open` no more, and
 * one Mount (`Folds`) reads the roots' folds where it needs them, makes the widget's
 * own folds through their nodes, and keeps Expand all and Collapse all saying which
 * they do. A capture that keeps a root keeps its node, and its fold.
 * Rows are keyed by call within their root, so a row the next capture keeps under the
 * same root keeps its nodes, and the selection or focus on it. A row a capture moves
 * under another root is a new node there, in that root's fold, since Effect UI keys
 * children within one parent. A user on the row lands on the new row by its datum key,
 * the row itself rather than its location link (effect-widget.js), and a folded
 * destination opens to show it, since the user's place outweighs a fold made before
 * the row arrived. A row moved without focus leaves its destination's fold as it was.
 * After each commit the root says the
 * value it drew (`drawn`, host/element-data.js), so Leaf stamps the rows' datum marks
 * with that value's snapshot. */
import {
  Component,
  Effect,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { Announce, NavigateToDatum } from "/runtime/widget-services.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { onCurrentLocation } from "/runtime/widget-api.js";
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

const CallDiffModel = Schema.Struct({});

export const CallDiffMessage = UiSchema.TaggedEnum({
  Folded: { open: Schema.Boolean },
  ClickedLocation: { key: Schema.String, text: Schema.String },
});

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

// The roots' folds, which the browser holds (each root's `open`, which the view writes
// only as the root arrives), read and made here, where the widget needs them:
//
// - Expand all and Collapse all: the control reads the roots' folds as it is pressed,
//   folds every root, and says the fold it made, which the update announces. Its face,
//   the action's symbol and the count as its name, which a view's attributes can't
//   write (controls.js, `pressAttributes`), follows each root's fold, heard with
//   `toggle`, and each commit, with no draw of the capture.
// - The user on a row a capture moves into a folded root goes with it there: the mount
//   hears each commit once its rows are patched, before defineWidget's hold puts the
//   user back on the row by its key (effect-widget.js), and opens that root. It follows
//   where the user is, except that a change removing or hiding their node leaves it on
//   the node they lost.
const Folds = Mount.makeStream(
  "Folds",
  { args: { value: Schema.NullOr(Document) } },
  (node: HTMLElement, _args, changes) =>
    Stream.callback<boolean>((queue) =>
      Effect.gen(function* () {
        const roots = () => [
          ...node.querySelectorAll<HTMLDetailsElement>("details.lf-call-group"),
        ];
        const control = () =>
          node.querySelector<HTMLButtonElement>(":scope > .lf-call-tools > button");
        let face: string | null = null;
        let faced: Element | null = null;
        let expanding = false;
        const paint = () => {
          const button = control();
          if (!button) return;
          const all = roots();
          const expand = all.some((root) => !root.open);
          expanding = expand;
          const word = all.length === 1 ? "root" : "roots";
          const label = `${expand ? "Expand" : "Collapse"} all ${all.length} call-tree ${word}`;
          if (label === face && button === faced) return;
          face = label;
          faced = button;
          offerActionElement(button, "symbol", "lf-call-toggle", label, {
            action: expand ? "expand-all" : "collapse-all",
          });
        };
        const press = (event: Event) => {
          const button = control();
          if (
            !button ||
            !(event.target instanceof Node) ||
            !button.contains(event.target)
          )
            return;
          const all = roots();
          const open = all.some((root) => !root.open);
          for (const root of all) if (root.open !== open) root.open = open;
          paint();
          Queue.offerUnsafe(queue, open);
        };
        let held: Element | null = null;
        const stop = onCurrentLocation((at, cause) => {
          if (cause !== "drop") held = at && node.contains(at) ? at : null;
        });
        // A root's fold can only turn the face to Expand all, and its opening only back
        // from it, so the toggles a bulk press sets off read nothing.
        const toggled = (event: Event) => {
          const root = event.target as HTMLDetailsElement;
          if (root.matches?.("details.lf-call-group") && root.open === expanding)
            paint();
        };
        node.addEventListener("click", press);
        node.addEventListener("toggle", toggled, true);
        yield* Effect.addFinalizer(() =>
          Effect.sync(() => {
            stop();
            node.removeEventListener("click", press);
            node.removeEventListener("toggle", toggled, true);
          }),
        );
        paint();
        yield* Effect.forkScoped(
          Stream.runForEach(changes, () =>
            Effect.sync(() => {
              // The folded root that now holds the row the commit took the user from.
              const key = held?.isConnected
                ? null
                : held?.closest("[data-lf-datum]")?.getAttribute("data-lf-datum");
              const root = key
                ? node
                    .querySelector(`[data-lf-datum="${CSS.escape(key)}"]`)
                    ?.closest("details")
                : null;
              if (root && !root.open) root.open = true;
              paint();
            }),
          ),
        );
      }),
    ),
);

export const CallDiff = Html.component({
  name: "CallDiff",
  props: CallDiffProps,
  model: CallDiffModel,
  message: CallDiffMessage,
}).make({
  init: () => ({}),
  update: {
    Folded: ($, { open }) =>
      $.run(
        Announce.make({
          words: `${open ? "Expanded" : "Collapsed"} all call-tree roots`,
        }),
      ),
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
  view: (h) => {
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
    const rootsWord = roots === 1 ? "root" : "roots";
    return frame.children(
      h.div
        .style({ display: "contents" })
        .onMount(
          Folds({ value }).pipe(Mount.map((open) => CallDiffMessage.Folded({ open }))),
        )
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
              // Its face and its press are `Folds`'.
              h.button,
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
              // Every root opens as it arrives; from then on its fold is the
              // browser's, which no draw writes (`Folds`).
              .attr("open", "")
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
