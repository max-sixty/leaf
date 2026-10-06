/* Comment on the page: the one owner of where a page thread is started.

   A comment on the page has two boxes: Threads' general box, and the page comment card
   the banner's Comment on the page control hangs from its own foot, its top edge on the
   banner's and its right edge on the control's. They are one destination: while Threads
   is open its box stands right there, so the control, `c` with nothing to comment on,
   and Resume writing go to that box; otherwise all three open the card. Both boxes are
   wired here, with one hint, one draft (`general`), and one send, so the two never
   differ in what they say or post. In Design mode both comment on the design.

   The card is for starting a thread and nothing after. A send puts it away and flashes
   Threads, where the new thread now lives, without opening the panel; the Threads count
   rising is the rest of that answer. A refused send opens the card again on the words
   the refusal handed back. Threads' own box keeps the user in it after a send, and its
   thread is revealed in the list.

   The card is an auto popover, so a press outside puts it away. Escape is its own row in
   the register, so the shortcut line says whether the words stay. Either way focus goes
   back to where the card was opened from: the control, or, for a key such as `c` that
   opens it from the page, the control too, since the key runs the control's press
   (keyboard/dispatch.js). On a phone the control stands behind More in its words, and
   the card spans the window under the banner. */
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
import { FLASH_MS, motion } from "../motion.js";
import { keys } from "../keyboard/scopes.js";
import { commandShortcut } from "../keyboard/control-keys.js";
import { keeps } from "../keeps.js";
import {
  BANNER_CONTROL_RANK,
  bannerControlDoor,
  dismissBannerControls,
  registerBannerControl,
} from "../banner-toolbar.js";

const NAME = "Comment on the page";

export function createPageComment({
  wireInput,
  createPageComment,
  designModeActive,
  panelIsOpen,
  setPanel,
  panelBox,
  panelSend,
  showThread,
  threadsToggle,
}) {
  const control = el("button", "lf-btn lf-page-comment");
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

  const input = textField();
  input.name = "comment";
  const send = el("button", "lf-btn", "Send");
  const composer = el("div", "lf-page-composer");
  composer.append(input, send);
  card.append(composer);

  const hint = () => (designModeActive() ? "Comment on the design" : NAME);
  const holds = () => Boolean(loadDraft("general")?.trim());
  const cardIsOpen = () => card.matches(":popover-open");
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

  card.addEventListener("toggle", (event) =>
    keeps(control, "aria-expanded", String(event.newState === "open")),
  );

  const openPanelBox = () => {
    setPanel(true);
    panelBox.focus({ preventScroll: true });
  };
  // The control's press is the same `open` as `c`, or a second press putting the card
  // away; opened with the control as its source, the card does not count a press on the
  // control as one outside it.
  control.addEventListener("click", () => {
    if (cardIsOpen()) card.hidePopover();
    else open();
  });
  registerBannerControl({
    key: "page-comment",
    control,
    rank: BANNER_CONTROL_RANK.pageComment,
    seat: { desk: "row", phone: "menu" },
  });

  function showCard() {
    // More comes down first, whichever route opens the card, so the card is never More's
    // child that closing More would take with it.
    dismissBannerControls();
    if (!cardIsOpen()) {
      // Opened from the control's own place, so Escape hands the user to the control
      // whether a press or a key opened it: the door where the control stands, More's on
      // a phone.
      bannerControlDoor(control)?.focus({ preventScroll: true });
      card.showPopover({ source: control });
    }
    // At once rather than at `toggle`, which comes a task later: the words typed right
    // after the press belong in the box, not to the control or the page's keys.
    input.focus({ preventScroll: true });
  }
  // With Threads open, Comment on the page is the panel's own box.
  function open() {
    if (panelIsOpen()) openPanelBox();
    else showCard();
  }

  // Each box sends the same event and differs only in where its sender is left.
  const wireBox = (box, sendBtn, sent) =>
    wireInput(box, {
      hint,
      accessibleName: hint,
      sends: "send",
      sendBtn,
      // localStorage tells other tabs and skips this document, and the page's draft has
      // two views here, so they take the same bus directly, as reply boxes do
      // (replies.js).
      save: (text) => {
        saveDraft("general", text);
        tellDraft("general", text);
      },
      send: async (_text, raw, owns) => {
        let flight = null;
        const handle = await sendMessage("general", owns, (attempt) => {
          const event = { attempt, text: raw };
          if (designModeActive()) event.about = "design";
          return (flight = createPageComment(event));
        });
        if (handle) sent(handle, flight);
      },
    });

  const syncs = [];
  const stops = [];
  function mount(chromeRoot) {
    chromeRoot.append(card);
    // `c` reaches this control's press from wherever nothing else is commented on,
    // which is everywhere the control can be pressed, so its name carries the key.
    // Not a `control` on the `c` row: that row answers for every destination, and a
    // control it named would make it wait on this one.
    control.title = `${NAME} (${commandShortcut("comment.create")})`;
    for (const box of [panelBox, input]) box.value = loadDraft("general") ?? "";
    syncs.push(
      // The message renderer cues the send; revealing its thread only lands it.
      wireBox(panelBox, panelSend, (handle) =>
        showThread(handle.id, { focus: false, flash: false }),
      ),
      wireBox(input, send, (_handle, flight) => {
        card.hidePopover();
        motion(
          threadsToggle,
          [{ backgroundColor: "var(--hi-tint)" }, { backgroundColor: "transparent" }],
          FLASH_MS,
        );
        // A refusal can come long after the send, while delivery retries. The card opens
        // again on the words only where the user still stands where the send left them;
        // anywhere else it would take their keys, and the words wait in the draft for
        // the control, `c` or Resume writing.
        void Promise.resolve(flight).then((accepted) => {
          const still = [control, document.body, null].includes(document.activeElement);
          if (!accepted && still && !panelIsOpen()) showCard();
        });
      }),
    );
    for (const sync of syncs) sync();
    stops.push(
      mirrorDraft(panelBox, syncs[0], "general"),
      mirrorDraft(input, syncs[1], "general", {
        resume: () =>
          panelIsOpen()
            ? { where: panelBox, input: () => panelBox, open: () => setPanel(true) }
            : {
                where: input,
                input: () => input,
                open: showCard,
              },
      }),
    );
  }

  return {
    control,
    open,
    close: () => cardIsOpen() && card.hidePopover(),
    // The box Comment on the page writes in now, which carries `c`'s hint.
    box: () => (panelIsOpen() ? panelBox : input),
    // Both boxes restate their hint and Send state (Design mode, a restored draft).
    sync: () => {
      for (const sync of syncs) sync();
    },
    mount,
    dispose: () => {
      for (const stop of stops) stop();
    },
  };
}
