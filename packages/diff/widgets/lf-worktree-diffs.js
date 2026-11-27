/* The collection's totals, drawn by an Effect UI component (lib/effect-widget.js) from
 * the members' supplied scalars, never their rendered labels or patch text, and read
 * again as a revision's members connect. Unavailable snapshots stay apart from the
 * known totals. */
import { Html, Schema } from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/lib/effect-widget.js";

const WorktreeDiffsProps = Schema.Struct({
  ...widgetProps,
  members: Schema.Number,
  known: Schema.Number,
  files: Schema.Number,
  binary: Schema.Number,
  additions: Schema.Number,
  deletions: Schema.Number,
});

const WorktreeDiffs = Html.component({
  name: "WorktreeDiffs",
  props: WorktreeDiffsProps,
  model: Schema.Struct({}),
  message: Schema.Never,
}).make({
  init: () => ({}),
  update: {},
  view: (h) => {
    const { members, known, files, binary, additions, deletions } = h.props;
    // A view has one root, and this one takes no box, so the overview and the slot
    // stand in the shadow root's flow as two siblings would.
    return h.div.style({ display: "contents" }).children(
      h.div
        .class("lf-worktree-overview")
        .attr("data-lf-gen", "1")
        .attr("data-lf-said", "")
        .children(
          h.strong
            .class("lf-worktree-total")
            .children(
              members
                ? `${members} ${members === 1 ? "worktree" : "worktrees"}`
                : "No worktrees supplied",
            ),
          h.span
            .class("lf-worktree-stats")
            .attr("hidden", known ? undefined : "")
            .children(
              h.span.children(`${files} ${files === 1 ? "file" : "files"}`),
              h.span.class("lf-worktree-additions").children(`+${additions}`),
              h.span.class("lf-worktree-deletions").children(`−${deletions}`),
              h.span
                .class("lf-worktree-binary")
                .attr("hidden", binary ? undefined : "")
                .children(`${binary} binary`),
            ),
          h.span
            .class("lf-worktree-unavailable")
            .attr("hidden", known === members ? "" : undefined)
            .children(`${members - known} unavailable`),
        ),
      h.slot,
    );
  },
});

defineWidget("lf-worktree-diffs", WorktreeDiffs, {
  shadow: true,
  lfPatch: "members",
  inputs: (host) => {
    const members = [...host.querySelectorAll(":scope > lf-worktree")];
    const known = members.filter(
      (member) => member.getAttribute("status") !== "unavailable",
    );
    /** @param {string} attribute */
    const sum = (attribute) =>
      known.reduce(
        (total, member) => total + Number(member.getAttribute(attribute) ?? 0),
        0,
      );
    return {
      members: members.length,
      known: known.length,
      files: sum("files"),
      binary: sum("binary-files"),
      additions: sum("additions"),
      deletions: sum("deletions"),
    };
  },
});
