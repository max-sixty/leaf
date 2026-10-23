/* Approval owns one drawing from first paint through recorded state changes.
 * The live widget keeps this closure and its control, preserving focus on Undo. */
import { html, ref, render } from "/vendor/lit.js";

document.documentElement.lfInitial.register("lf-approval", (host, { offerElement }) => {
  const root = host.ownerDocument.createElement("div");
  root.className = "lf-approval-actions";
  root.dataset.lfGen = "1";
  host.append(root);
  const drawing = { button: null, paint };
  function paint(approved = false) {
    render(
      html` <span
          class="lf-approval-status"
          role="status"
          data-lf-said
          data-room=${"Awaiting approval\nApproved"}
        >
          <span>${approved ? "Approved" : "Awaiting approval"}</span>
        </span>
        <button
          type="button"
          data-lf-carry="approve"
          data-room=${"Approve\nUndo approval"}
          ${ref((button) => {
            if (!button) return;
            drawing.button = button;
            offerElement(button, "lf-btn");
          })}
        >
          <span>${approved ? "Undo approval" : "Approve"}</span>
        </button>`,
      root,
    );
  }
  paint();
  return drawing;
});
