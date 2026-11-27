/* A settled options group's disclosure row: one line naming the outcome, which opens
 * and closes the group's options in place. It names only the outcome: its disclosure
 * marker already says the alternatives are inside. The user chose this over a
 * right-aligned count of the options. While the version diff is on, a Δ count says how
 * many of the group's parts changed, so a change can't hide behind the collapse.
 *
 * The row wears a button's role and `aria-expanded`, so Leaf answers its keys as it
 * does every disclosure's (module-input.md, "How scopes compose"). It is a span rather
 * than a button so its words stay selectable in WebKit (`selectableAttributes`). */
import { selectableAttributes } from "/runtime/lib/controls.js";

/** Where this tab keeps whether the group `id` stands open. @param {string} id */
export const settledKey = (id) => `lf-settled:${id}`;

/** @param {any} h
 *  @param {{open: boolean, names: string[], changes: number, toggled: unknown}} row */
export const SettledRow = (h, { open, names, changes, toggled }) =>
  h.span
    .attrs(selectableAttributes("button", "lf-settled lf-disclosure-marker", "fold"))
    .attr("tabindex", "0")
    .attr("part", open ? "cell settled open" : "cell settled")
    .attr("aria-expanded", String(open))
    .on("click", toggled)
    .children(
      h.span
        .attr("data-lf-gen", "1")
        .attr("data-lf-said", "")
        .children(names.length ? `Settled: ${names.join(", ")}` : "Settled"),
      changes
        ? h.span
            .class("lf-settled-diff lf-chip lf-change-count")
            .children(`Δ${changes}`)
        : null,
    );
