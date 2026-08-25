/* Inspectable evidence under one disposable worker. Facts stay authored attributes;
 * the module adds a disclosure row and leaves the real diff in place. */
import { offer, once } from "/leaf.js";

function summary(tree) {
  const open = tree.hasAttribute("data-lf-open");
  let head = tree.querySelector(":scope > .lf-worktree-head[data-lf-gen]");
  if (!head) {
    head = offer("button", "lf-worktree-head");
    head.dataset.lfGen = "1";
    // These are the worktree's evidence as well as its disclosure door. Paper and an
    // exported copy keep the words while the runtime's export pass disarms the press.
    head.setAttribute("data-lf-said", "");
    head.addEventListener("click", (event) => {
      event.stopPropagation();
      tree.toggleAttribute("data-lf-open");
      summary(tree);
    });
    tree.prepend(head);
  }
  head.setAttribute("aria-expanded", String(open));
  const facts = [
    tree.getAttribute("branch"),
    `${tree.getAttribute("base")}…${tree.getAttribute("head")}`,
    `↑${tree.getAttribute("ahead")} ↓${tree.getAttribute("behind")}`,
    `+${tree.getAttribute("additions")} −${tree.getAttribute("deletions")}`,
    `${tree.getAttribute("commits")} commit${tree.getAttribute("commits") === "1" ? "" : "s"}`,
    `tests ${tree.getAttribute("tests")}`,
  ];
  const text = `${open ? "▾" : "▸"} ${facts.join(" · ")}`;
  if (head.textContent !== text) {
    head.textContent = text;
    document.dispatchEvent(new Event("lf-projection"));
  }
}

customElements.define(
  "lf-worktree",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.addEventListener("lf-reveal", () => {
        this.setAttribute("data-lf-open", "");
        summary(this);
      });
      summary(this);
    }
  },
);
