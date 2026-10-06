/* The page comment card: a page thread started from the banner, with Threads shut.

   The banner's Comment on the page control opens a card hung from its own foot: the
   card's top edge meets the banner's and its right edge the control's, and it holds one
   composer. The card is for starting a thread and nothing after: a send puts it away and
   flashes Threads, where the new thread now lives, without opening the panel; the
   Threads count rising is the rest of that answer. The card is an auto popover, so
   Escape or a press outside puts it away too, focus going back to where it was opened
   from (the control, or the page `c` was pressed on).

   Comment on the page is one destination with two boxes. While Threads is open its
   general box stands right there, so the control and `c` go to that box instead of
   hanging a card over the panel; otherwise both open this card. The two boxes keep one
   draft, `general`: the panel's box is that draft's root editor and this one its mirror,
   and Resume writing goes where the control would. In Design mode both comment on the
   design.

   On a desk the control stands on the banner's row as a symbol. On a phone it stands
   behind More in its words, and the card hangs from More's door across the window. */
import { el } from "../widget-elements.js";
import { iconElement } from "../icons.js";
import { textField } from "../composing/text-field.js";
import {
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { motion } from "../motion.js";
import { keys } from "../keyboard/scopes.js";
import {
  BANNER_CONTROL_RANK,
  dismissBannerControls,
  registerBannerControl,
} from "../banner-toolbar.js";

const NAME = "Comment on the page";
// As long as the arrival flash a thread wears in Threads (chrome.css, `.flash`).
const FLASH_MS = 1200;

export function createPageCommentCard({
  wireInput,
  createPageComment,
  designModeActive,
  panelIsOpen,
  setPanel,
  panelBox,
  threadsToggle,
}) {
  const control = el("button", "lf-btn lf-auxiliary-toggle lf-page-comment");
  control.type = "button";
  control.setAttribute("aria-label", NAME);
  control.title = NAME;
  control.setAttribute("aria-expanded", "false");
  control.append(
    iconElement("comment-add", "lf-page-comment-icon"),
    el("span", "lf-page-comment-label", NAME),
  );

  const card = el("section", "lf-ui lf-page-comment-card");
  card.setAttribute("popover", "auto");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-label", NAME);
  control.popoverTargetElement = card;

  const input = textField();
  input.name = "comment";
  const send = el("button", "lf-btn", "Send");
  const composer = el("div", "lf-page-composer");
  composer.append(input, send);
  card.append(composer);

  // The card's own way out, rather than the popover's native close watcher: the
  // register shows it on the shortcut line and says whether the words stay.
  const holds = () => Boolean(loadDraft("general")?.trim());
  keys(card, "In the page comment card", [
    {
      id: "comment.card-close",
      keys: ["Escape"],
      description: () =>
        holds() ? "Close the card, keeping the draft" : "Close the card",
      title: () => (holds() ? "close — draft kept" : "close"),
      run: () => card.hidePopover(),
    },
  ]);

  const hint = () => (designModeActive() ? "Comment on the design" : NAME);
  let sync = () => {};
  let stopMirroring = () => {};

  card.addEventListener("toggle", (event) => {
    const open = event.newState === "open";
    control.setAttribute("aria-expanded", String(open));
    if (!open) return;
    sync();
    input.focus({ preventScroll: true });
  });

  const openPanelBox = () => {
    setPanel(true);
    panelBox.focus({ preventScroll: true });
  };
  // With Threads open, Comment on the page is the panel's own box. Behind More, the
  // press takes the menu down before the card opens, so the card is not More's child.
  control.addEventListener("click", (event) => {
    dismissBannerControls();
    if (!panelIsOpen()) return;
    event.preventDefault();
    openPanelBox();
  });
  registerBannerControl({
    key: "page-comment",
    control,
    rank: BANNER_CONTROL_RANK.pageComment,
    seat: { desk: "row", phone: "menu" },
  });

  function open() {
    if (panelIsOpen()) return openPanelBox();
    if (!card.matches(":popover-open")) card.showPopover({ source: control });
    else input.focus({ preventScroll: true });
  }

  function mount(chromeRoot) {
    chromeRoot.append(card);
    input.value = loadDraft("general") ?? "";
    sync = wireInput(input, {
      hint,
      accessibleName: hint,
      sends: "send",
      sendBtn: send,
      // localStorage tells other tabs and skips this document, and the page's draft
      // has two views here, this box and the other place Comment on the page writes,
      // so they take the same bus directly, as reply boxes do (replies.js).
      save: (text) => {
        saveDraft("general", text);
        tellDraft("general", text);
      },
      send: async (_text, raw, owns) => {
        const sent = await sendMessage("general", owns, (attempt) => {
          const event = { attempt, text: raw };
          if (designModeActive()) event.about = "design";
          return createPageComment(event);
        });
        if (!sent) return;
        card.hidePopover();
        motion(
          threadsToggle,
          [{ backgroundColor: "var(--hi-tint)" }, { backgroundColor: "transparent" }],
          FLASH_MS,
        );
      },
    });
    stopMirroring = mirrorDraft(input, sync, "general", {
      mirrored: true,
      resume: () =>
        panelIsOpen()
          ? { where: panelBox, input: () => panelBox, open: () => setPanel(true) }
          : {
              where: input,
              input: () => input,
              open: () => {
                if (!card.matches(":popover-open"))
                  card.showPopover({ source: control });
              },
            },
    });
  }

  return {
    control,
    card,
    input,
    open,
    // The box Comment on the page writes in now, which carries `c`'s hint.
    box: () => (panelIsOpen() ? panelBox : input),
    mount,
    dispose: () => stopMirroring(),
  };
}
