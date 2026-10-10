/* Comment on the page: the one place a page thread is started.

   The banner's Comment on the page control hangs the page comment card from its own
   foot, its top edge on the banner's and its right edge on the control's where that fits
   the window, moving only far enough to remain inside the window otherwise. The editor
   takes the room beneath the banner, and the card scrolls if its minimum controls
   exhaust it. The control, `c` with nothing to comment on, and Resume writing all open
   it, and it holds the page's one general box, with its draft (`general`). Threads has
   no box of its own: it is where a thread lives once started, not where one starts, and
   the card hangs over it when it is open. In Design mode the box comments on the design.

   The card starts page threads; their conversations live in Threads. Sending closes
   the card, returns focus to its banner door and flashes Threads without opening the
   panel. Its count rises for the new thread, and an open panel reveals the thread in
   its list. `c` opens the card again. A refused send restores the draft and reopens
   the editor only while the send still owns the user's intent at that door. A revision
   arriving while the user writes in the card opens it again through its Resume writing
   route (drafts.js).

   The card is an auto popover, so a press outside puts it away. Escape is its own row in
   the register, so the shortcut line says whether the words stay. Either way focus goes
   back to where the card was opened from: the control, or, for a key such as `c` that
   opens it from the page, the control too, since the key runs the control's press
   (keyboard/dispatch.js). On a phone the control stands behind More in its words, and
   the card spans the window under the banner. The box stands and takes words from the
   first paint: the offline banner says a comment will not send, not that there is
   nowhere to write it. */
import { el } from "../widget-elements.js";
import { iconElement } from "../icons.js";
import { textField } from "../composing/text-field.js";
import { closeLayer, focusDestination } from "../focus.js";
import { retainUserIntent } from "../user-intent.js";
import { loadDraft, mirrorDraft, saveDraft, sendMessage } from "../drafts.js";
import { flashDuration, backgroundFlash } from "../motion.js";
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
  const composer = el("div", "lf-general lf-comment-box");
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

  function open() {
    // More comes down first, whichever route opens the card, so the card is never More's
    // child that closing More would take with it.
    dismissBannerControls();
    if (!cardIsOpen()) {
      // Opened from the control's own place, so Escape hands the user to the control
      // whether a press or a key opened it: the door where the control stands, More's on
      // a phone.
      const door = bannerControlDoor(control);
      if (door) focusDestination(door, "move");
      card.showPopover({ source: control });
    }
    // At once rather than at `toggle`, which comes a task later: the words typed right
    // after the press belong in the box, not to the control or the page's keys.
    focusDestination(input, "move");
  }

  let sync = () => {};
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
    input.value = loadDraft("general") ?? "";
    sync = wireInput(input, {
      hint,
      accessibleName: hint,
      sends: "send",
      sendBtn: send,
      save: (text) => saveDraft("general", text),
      send: (_text, raw, owns) => {
        let flight = null;
        const handle = sendMessage("general", owns, (attempt) => {
          const event = { attempt, text: raw };
          if (designModeActive()) event.about = "design";
          return (flight = createPageComment(event));
        });
        if (!handle) return;
        const door = bannerControlDoor(control);
        closeLayer(
          () => card.hidePopover(),
          () => focusDestination(door, "return"),
        );
        const mayRestore = retainUserIntent({
          source: door,
          available: () => card.isConnected && !cardIsOpen(),
        });
        // Open, Threads shows the thread where it lands, as it does an anchored comment's
        // (composing/selection.js); the user returns to the banner door.
        if (panelIsOpen()) void showThread(handle.id, { focus: false, flash: false });
        backgroundFlash(threadsToggle, flashDuration());
        // Delivery may refuse long after Send. Restore text entry only while the user
        // still stands at the door; a later gesture owns its focus and disclosure.
        void Promise.resolve(flight).then((accepted) => {
          if (!accepted && document.activeElement === door && mayRestore())
            mayRestore.handoff(open);
        });
      },
    });
    sync();
    stops.push(
      mirrorDraft(input, sync, "general", {
        resume: () => ({ where: input, input: () => input, open }),
      }),
    );
  }

  return {
    control,
    open,
    close: () => cardIsOpen() && card.hidePopover(),
    // The box `c` names when there is nothing else to comment on.
    box: input,
    // The box restates its hint and Send state when Design mode changes.
    sync: () => sync(),
    mount,
    dispose: () => {
      for (const stop of stops) stop();
    },
  };
}
