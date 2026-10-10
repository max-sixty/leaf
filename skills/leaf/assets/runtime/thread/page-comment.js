/* Comment on the page: the one owner of where a page thread is started.

   A comment on the page has two boxes: Threads' general box, and the page comment card
   the banner's Comment on the page control hangs from its own foot, its top edge on the
   banner's and its right edge on the control's where that fits the window, moving
   only far enough to remain inside the window otherwise. The editor takes the room
   beneath the banner, and the card scrolls if its minimum controls exhaust it.
   They are one destination: while Threads
   is open its box stands right there, so the control, `c` with nothing to comment on,
   and Resume writing go to that box; otherwise all three open the card. Both boxes are
   wired here, with one hint, one draft (`general`), and one send, so the two never
   differ in what they say or post. In Design mode both comment on the design.

   The card starts page threads; their conversations live in Threads. A send leaves
   focus on the open card and flashes Threads without opening the panel; its count
   rises for the new thread. `c` enters the card's box again. A refused send returns
   to the editor only while the user still stands on the card. Threads' own box keeps
   the user in it after a send, and its thread is revealed in the list.

   The card is an auto popover, so a press outside puts it away. Escape is its own row in
   the register, so the shortcut line says whether the words stay. Either way focus goes
   back to where the card was opened from: the control, or, for a key such as `c` that
   opens it from the page, the control too, since the key runs the control's press
   (keyboard/dispatch.js). On a phone the control stands behind More in its words, and
   the card spans the window under the banner. */
import { showNativeLayer, closeNativeLayer } from "../keyboard/layer-stack.js";
import { el } from "../widget-elements.js";
import { iconElement } from "../icons.js";
import { textField } from "../composing/text-field.js";
import { focusDestination } from "../focus.js";
import { retainUserIntent } from "../user-intent.js";
import {
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { FLASH_MS, backgroundFlash } from "../motion.js";
import { keys } from "../keyboard/scopes.js";
import { commandShortcut } from "../keyboard/control-keys.js";
import { keeps } from "../keeps.js";
import { registerReadingRegion } from "../reading-regions.js";
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
    iconElement("comment", "lf-page-comment-icon"),
    el("span", "lf-page-comment-label", NAME),
  );

  const card = el("section", "lf-ui lf-page-comment-card");
  card.setAttribute("popover", "auto");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-label", NAME);
  card.tabIndex = -1;

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
      run: () => closeNativeLayer(card),
    },
  ]);

  card.addEventListener("toggle", (event) =>
    keeps(control, "aria-expanded", String(event.newState === "open")),
  );

  const openPanelBox = () => {
    setPanel(true);
    focusDestination(panelBox, "move");
  };
  // The control's press is the same `open` as `c`, or a second press putting the card
  // away; opened with the control as its source, the card does not count a press on the
  // control as one outside it.
  control.addEventListener("click", () => {
    if (cardIsOpen()) closeNativeLayer(card);
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
      const door = bannerControlDoor(control);
      if (door) focusDestination(door, "move");
      showNativeLayer(card, { source: control });
    }
    // At once rather than at `toggle`, which comes a task later: the words typed right
    // after the press belong in the box, not to the control or the page's keys.
    focusDestination(input, "move");
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
    stops.push(
      registerReadingRegion({ id: "lf-region:page-comment", host: card, body: card }),
    );
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
        focusDestination(card, "return");
        const mayRestore = retainUserIntent({ source: card, available: cardIsOpen });
        backgroundFlash(threadsToggle, FLASH_MS);
        // Delivery may refuse long after Send. Restore text entry only while the user
        // still stands on the card; a later gesture owns its focus and disclosure.
        void Promise.resolve(flight).then((accepted) => {
          if (!accepted && document.activeElement === card && mayRestore())
            mayRestore.handoff(showCard);
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
    close: () => cardIsOpen() && closeNativeLayer(card),
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
