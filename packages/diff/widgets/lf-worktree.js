/* One native disclosure from delivery through live updates, drawn by an Effect UI
 * component (runtime/effect-widget.js) from the snapshot's attributes. The disclosure owns
 * its open state: the view writes `open` from the markup and never again while the
 * markup says the same, so the user's toggle stands. Authored evidence stays in the
 * host's light DOM, and the browser distributes it through the slot. */
import { Html, Schema } from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";

const WorktreeProps = Schema.Struct({
  ...widgetProps,
  id: Schema.String,
  label: Schema.String,
  path: Schema.String,
  identity: Schema.String,
  status: Schema.String,
  files: Schema.Number,
  binary: Schema.Number,
  additions: Schema.String,
  deletions: Schema.String,
  open: Schema.Boolean,
});

const Worktree = Html.component({
  name: "Worktree",
  props: WorktreeProps,
  model: Schema.Struct({}),
  message: Schema.Never,
}).make({
  init: () => ({}),
  update: {},
  view: (h) => {
    const { id, label, path, identity, status, files, binary, additions, deletions } =
      h.props;
    // Counts already say a row changed; only Clean/Unavailable need another word.
    const word =
      status === "clean" ? "Clean" : status === "unavailable" ? "Unavailable" : null;
    return h.details
      .class("lf-worktree-disclosure")
      .attr("open", h.props.open ? "" : undefined)
      .attr("data-lf-open-key", `worktree:${id}`)
      .children(
        h.summary
          .class("lf-worktree-summary lf-disclosure-marker")
          .attr("data-lf-gen", "1")
          .attr("data-lf-said", "")
          .children(
            h.span
              .class("lf-worktree-identity")
              .children(
                h.strong.class("lf-worktree-label").children(label),
                " ",
                h.span.class("lf-worktree-ref").children(identity),
              ),
            word && h.span.class("lf-worktree-status").children(word),
            h.span
              .class("lf-worktree-stats")
              .children(
                ...(status === "unavailable"
                  ? []
                  : [
                      h.span.children(`${files} ${files === 1 ? "file" : "files"}`),
                      h.span.class("lf-worktree-additions").children(`+${additions}`),
                      h.span.class("lf-worktree-deletions").children(`−${deletions}`),
                      binary
                        ? h.span
                            .class("lf-worktree-binary")
                            .children(`${binary} binary`)
                        : null,
                    ]),
              ),
          ),
        h.div
          .class("lf-worktree-path")
          .attr("data-lf-gen", "1")
          .attr("data-lf-said", "")
          .children(h.span.children("Worktree"), " ", h.code.children(path)),
        h.div.class("lf-worktree-body").children(h.slot),
      );
  },
});

defineWidget("lf-worktree", Worktree, {
  shadow: true,
  statics: { lfPatch: "members" },
  inputs: (host) => {
    const branch = host.getAttribute("branch");
    const head = host.getAttribute("head");
    return {
      id: host.getAttribute("id") ?? "",
      label: host.getAttribute("label") ?? "",
      path: host.getAttribute("path") ?? "",
      identity: [branch || (head ? "Detached HEAD" : null), head?.slice(0, 8)]
        .filter(Boolean)
        .join(" · "),
      status: host.getAttribute("status") ?? "",
      files: Number(host.getAttribute("files")),
      binary: Number(host.getAttribute("binary-files")),
      additions: host.getAttribute("additions") ?? "",
      deletions: host.getAttribute("deletions") ?? "",
      open: host.hasAttribute("open"),
    };
  },
});
