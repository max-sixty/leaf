/* The thread panel's scaffold: the dialog, its head, the narrowing row, the thread list,
   and the foot the general box stands in. Built here, once, so every owner that draws
   into the panel imports the same nodes; the reconciler renders into them and the
   chrome-layout.js places them. */
import { el } from "../widget-elements.js";
import { setPanel } from "../chrome-layout.js";
import { designOn } from "../design.js";
import { labelOf } from "../keyboard/bindings.js";
import { PANEL_SAY } from "../keyboard/page.js";
import { loadDraft, mirrorDraft, saveDraft, sendDraft } from "../drafts.js";
import { runtime } from "../context.js";
import { post } from "../outbox.js";
import { landTyping, mayLandTyping } from "../composing/capture.js";
import { wireInput } from "../composing/input.js";
import { showThread } from "./landing.js";

export const panel = el("dialog", "lf-ui lf-panel");
const panelHead = el("div", "lf-panel-head");
export const closeBtn = el("button", "lf-btn", "×");
closeBtn.title = "Close (Esc)";
closeBtn.setAttribute("aria-label", "Close threads");
// The head's own line: the panel's name while it shows the whole conversation, and what
// it is showing instead the moment a narrowing stands. One slot, because they are one
// fact — how much of the log is in front of the reader — and a count in a second place
// is a count free to disagree with the list under it.
export const panelTitle = el("span", "", "Threads");
panelHead.append(panelTitle, closeBtn);

// Narrowing the list, which is the panel's own view and not the page's state: neither
// box is remembered across a reload, the way a browser's find bar is not. A remembered
// narrowing is a trap: the reader returns to three of twenty-four threads with nothing on
// screen saying why, and a comment arriving outside it never appears at all. Here the head
// says "Showing 3 of 24" for as long as one stands, and a reload is the whole conversation
// again.
const findRow = el("div", "lf-find");
export const findInput = document.createElement("input");
findInput.type = "search";
findInput.className = "lf-find-box";
findInput.placeholder = "Find in threads";
findInput.setAttribute("aria-label", "Find in threads");
// The register appends the key that reaches it (`control`), so the control and the row
// cannot spell the binding differently.
findInput.title = "Find in threads";
// What is waiting on the reader: an agent comment, an explicit question in a reply, or a
// reply whose own x-awaits markup still asks. The last case is derived from the same
// declaration-driven projection as the Asks tray; settling reactions can acknowledge
// either kind without closing the thread.
export const needsBtn = el("button", "lf-btn lf-needs", "Waiting on you");
needsBtn.setAttribute("aria-pressed", "false");
findRow.append(findInput, needsBtn);
export const threadsBox = el("div", "lf-threads");
// A stable panel landing for g T, for c entered from the list, and for pointer/Tab
// fallbacks that have no command frame. -1 keeps it out of the Tab order.
threadsBox.tabIndex = -1;
// And a name, because `g T` lands a reader here and the panel's visible heading alone does
// not name a focusable container. A page key's arrival has to say where it arrived — the
// other direct destinations are named by a leaf link, an Ask row, or a Page-map marker
// — or the press is silent to exactly the reader who cannot see the ring it painted. The
// same reason the reference dialog carries a role and a label beside its -1.
// `group` rather than `list`: the box holds run headings as well as threads, so a list
// role fails `aria-required-children` outright and leaves a screen reader announcing a list
// with no items. The name is what the landing needed; the role is only there because a bare
// div may not carry one.
threadsBox.setAttribute("role", "group");
threadsBox.setAttribute("aria-label", "Threads");
export const generalRow = el("div", "lf-general");
export const generalInput = document.createElement("textarea");
const generalSend = el("button", "lf-btn primary", "Send");
generalRow.append(generalInput, generalSend);
// The panel's foot: the general box below the scrolling thread list.
export const panelFoot = el("div", "lf-panel-foot");
panelFoot.append(generalRow);
panel.append(panelHead, findRow, threadsBox, panelFoot);

closeBtn.onclick = () => setPanel(false);

// What the general box is for, said once: its own placeholder wears it, and so does the
// panel row whose key opens it. Two strings would be two chances to rename the mode in
// one of them.
export const generalHint = () =>
  designOn ? "Comment on the layer" : "Comment on the page";

let sync = () => {};
export const syncGeneral = () => sync();
export function wireGeneralBox() {
  generalInput.value = loadDraft("general") ?? "";
  sync = wireInput(generalInput, {
    // The box has no anchor to decide it at an open, so what it posts is decided at the
    // send, by the mode standing then — and the hint says which, so the reader typing in
    // design mode knows their remark is about the layer as a whole.
    hint: generalHint,
    // The box's own address: unfocused, the placeholder reads "Comment on the page · c".
    // The same c reaches this box from the page or from the panel list. One key rather than
    // a chord, because “comment” is the intent in both contexts.
    //
    // Read off the row that answers the press rather than spelled here, which is the rule
    // the reference states about itself: a fact about a binding written somewhere the
    // binding cannot correct it goes on promising a key nobody rebound it with. Named for
    // that alone — the row is otherwise `PANEL`'s like any other. The forward reference is
    // only ever resolved at paint.
    address: () => labelOf(PANEL_SAY),
    sends: "send",
    sendBtn: generalSend,
    save: (v) => saveDraft("general", v),
    send: async (text, raw, owns) => {
      const event = { kind: "comment", revision: runtime.currentRevision, text };
      if (designOn) event.about = "layer";
      const sent = await sendDraft("general", owns, (attempt) =>
        post({ ...event, attempt }),
      );
      if (!sent) return;
      const shouldLand = mayLandTyping(generalInput);
      showThread(sent.id, { stand: false });
      if (shouldLand) landTyping(generalInput); // both send routes end where typing was
    },
  });

  sync();
  mirrorDraft(generalInput, sync, "general");
}
