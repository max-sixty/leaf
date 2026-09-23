/* Tray DOM and readonly visibility are safe to import before browser boot.
 * createTrays binds modality transitions to explicit commands and paint functions;
 * mountTrays installs the controls only after chrome has been attached. */
import { el } from "./widget-elements.js";
import { drawnEdge } from "./drawn-edge.js";
import { motion } from "./motion.js";
import { currentAuxiliarySurface } from "./auxiliary-surfaces.js";
import { letGo } from "./focus.js";
import { keys } from "./keyboard/scopes.js";
import { pageRung } from "./keyboard/register.js";
import { pagePresented } from "./presentation.js";
import { allAsks } from "./asks/model.js";
import { walkRows } from "./keyboard/bindings.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";
import { iconElement } from "./icons.js";
import { createLiveLeavesList } from "./live-leaves-list.js";
import { bannerControlDoor, dismissBannerControls } from "./banner-shelf.js";
import { createAskTrayList } from "./asks/tray-list.js";
// The left side holds one tray at a time, selected by the shared auxiliary-surface owner.
// The leaves tray overlays the document because its
// rows leave the page. The asks tray takes a strip because its rows travel within the
// page and the reader must keep the target visible. Both entry controls call the same
// tray setter.
//
// Trays declare presentation-time arrival: their first paint needs the state-dependent
// rows, while their remembered selection reserves the shell geometry during startup.
//
// A handle lives inside the region it draws, so a drawn region must not be its own scroll
// container: a scroller clips a handle straddling its border and carries it away with the
// content. A tray is a shell holding a `.lf-tray-list`, and every tray list reserves the
// shortcut bar's room where their horizontal spans meet. Wide content reads the shell's CSS
// value directly; there is no observed measurement loop or second number system to
// reconcile during a transition.

// The trays' edge, on the left, and everything said above said again for it: the width
// it stands at until the reader moves it, how narrow they may draw it, and the window
// under which a tray covers the page rather than standing beside it. The same bargain at
// the same ratio, because a reader who has learned one edge has learned the other.
//
// 220 is where the tray's own row stops being one. A leaf's row spends 45px before any
// word of the page's — the status dot's 9px, its 8px gap, and the 20px and 8px the row
// and the tray take for padding — and what is left holds a title that ellipsizes rather
// than wrapping, so under this the tray is furniture showing the first syllable of every
// name on it. The Asks tray's rows clamp to three lines instead and would go on reading
// further down, which is why the floor is the leaves tray's to set.
const TRAY_SLOT_W = 300;
const TRAY_SLOT_MIN = 220;
const TRAY_COVERING = `(width <= ${TRAY_SLOT_W * 2}px)`;
// Where the standing width is written, and where the cascade reads it. chrome.css
// spells the same name and the same covering width, and the layer test holds the two
// spellings equal, since a stylesheet cannot read a constant.
export const TRAY_SLOT_PROP = "--lf-tray-slot-width";
const trayCovering = matchMedia(TRAY_COVERING);
export const trayCovers = () => trayCovering.matches;

// The rows' own box, one per tray. Collected privately as they are made, because what
// the layout reserves at the foot of one it reserves at the foot of every one — and a
// second place to remember that is exactly where the Asks tray was left out of it: its
// walk parked the last row 47px under the shortcut bar, on the one tray nothing had ever
// walked to the end of. Callers state the clearance; this owner decides which lists it
// reaches and how each one spends it.
const trayLists = [];
function trayFurniture(panel, name, list = el("div", "lf-tray-list")) {
  const head = el("div", "lf-tray-head");
  const title = el("span", "lf-auxiliary-title", name);
  const close = el("button", "lf-btn lf-icon-action lf-close-action");
  close.append(iconElement("cross", "lf-action-icon"));
  close.title = `Close ${name.toLowerCase()} (Esc)`;
  close.setAttribute("aria-label", `Close ${name.toLowerCase()}`);
  list.classList.add("lf-tray-list");
  head.append(title, close);
  panel.append(head, list);
  trayLists.push(list);
  return { list, close };
}
export function reserveListClearance(clear) {
  for (const list of trayLists) {
    list.style.paddingBottom = clear;
    list.style.scrollPaddingBottom = clear;
  }
}

// Every active Ask and the route back through its current answer. The banner says
// completed/total (sayAsks); a/A still walks only the open worklist.
export const asksBtn = el("button", "lf-btn lf-asks", "");
// The machine's live leaves and what each is doing: a left panel of rows, each a
// link opening that page in its own tab, judged by the same `presented` the banner
// answers with, from the same facts — `others` on /api/state carries them for every
// live page, and every URL in the list carries only the key this reader already
// holds, since there is one key for the machine (`host_key`). The current page heads
// the list as a marked, unlinked row, so the panel reads as the whole machine. A
// status tray's point is being live, so rows reconcile on every applied state, keyed by URL —
// the stable identity, since address, port and key all survive a restart — and a
// status change repaints the row's own dot and words without moving it.
export const othersBtn = el("button", "lf-btn lf-others", "");
othersBtn.title = "Leaves live on this machine, and what each is doing";
// A nav, because navigation is what it is and a bare div may not carry the
// aria-label the card needs (axe: aria-prohibited-attr, serious).
export const othersPanel = el("nav", "lf-ui lf-tray-panel lf-others-panel");
othersPanel.id = "lf-leaves";
othersPanel.setAttribute("aria-label", "Leaves on this machine");
othersPanel.tabIndex = -1;
const leavesFurniture = trayFurniture(
  othersPanel,
  "Leaves",
  createLiveLeavesList(othersBtn),
);
export const liveLeavesList = leavesFurniture.list;
// A tray of the page's active asks, on the same edge: open and answered rows in the
// order the page asks them. The list is declaration-driven, so a widget joins without
// a row here knowing what kind of thing it is standing for.
export const asksPanel = el("nav", "lf-ui lf-tray-panel lf-asks-panel");
asksPanel.id = "lf-asks";
asksPanel.setAttribute("aria-label", "Asks from this page");
asksPanel.tabIndex = -1;
const asksFurniture = trayFurniture(asksPanel, "Asks", createAskTrayList());
export const asksList = asksFurniture.list;

// Furniture is local to this edge; selection belongs to the auxiliary-surface owner.
const trays = new Map();
export const currentTray = () =>
  trays.has(currentAuxiliarySurface()) ? currentAuxiliarySurface() : null;
export const trayIsOpen = (key) => currentTray() === key;
// Each tray's one offer: something to show, or the tray already standing so its button
// can still close it. An Asks tray of none is the same.
export const asksOffered = () =>
  pagePresented() && (allAsks().length > 0 || trayIsOpen("asks"));
export const askRows = () => [...asksPanel.querySelectorAll("button.lf-asks-row")];

export function createTrays({
  landEdge,
  auxiliarySurfaces,
  closePreview,
  leavesOffered,
  presentLeaves,
  syncAsks,
}) {
  const traysEdge = drawnEdge({
    side: "left",
    noun: "tray panel",
    wide: TRAY_SLOT_W,
    min: TRAY_SLOT_MIN,
    prop: TRAY_SLOT_PROP,
    key: "lf-tray-slot-width",
    covering: TRAY_COVERING,
    when: () => leavesOffered() || asksOffered(),
    land: landEdge,
  });

  function setOpenTray(key, options) {
    if (key || currentTray()) auxiliarySurfaces.select(key, options);
  }
  function registerTray(key, panel, btn, close, paint) {
    auxiliarySurfaces.registerAuxiliarySurface({
      key,
      surface: panel,
      scroller: () => panel.querySelector(".lf-tray-list"),
      // Asks needs the document beside it because its rows lead to controls there.
      // Other trays cover it unless they declare their own beside-page geometry.
      covers: () => key !== "asks" || trayCovers(),
      focus: () =>
        panel.querySelector(".lf-tray-list button, .lf-tray-list a[href]") ?? panel,
      arrival: "presentation",
      show({ phase }) {
        dismissBannerControls();
        closePreview();
        btn.setAttribute("aria-expanded", "true");
        // Filled before it is shown, so the tray is its own list from the first frame of
        // the slide rather than a blank card that populates a moment later. The way down
        // is the mirror of it, below: emptied once it is hidden, never before, or the
        // reader watches the list they just closed blank out and an empty card slide away.
        paint?.();
        panel.classList.add("open");
        if (phase === "gesture")
          motion(
            panel,
            [{ transform: "translateX(-100%)" }, { transform: "translateX(0)" }],
            200,
          );
      },
      hide({ returnFocus }) {
        btn.setAttribute("aria-expanded", "false");
        if (!panel.classList.contains("open")) return;
        // Slid out before hidden, and hidden only if still closed on arrival — a
        // reopen mid-slide leaves the panel standing rather than racing the finish.
        const out = motion(
          panel,
          [{ transform: "translateX(0)" }, { transform: "translateX(-100%)" }],
          160,
        );
        const hide = () => {
          if (trayIsOpen(key)) return; // reopened mid-slide; it stays up, list and all
          panel.classList.remove("open");
          paint?.();
        };
        if (out) out.finished.then(hide, () => {});
        else hide();
        if (returnFocus && panel.contains(document.activeElement))
          bannerControlDoor(btn)?.focus({ preventScroll: true });
      },
    });
    trays.set(key, { panel, btn, close });
  }
  // The painters are thunks: each tray's owner imports this module back, so neither
  // painter is a binding this module can read as it evaluates.
  registerTray("leaves", othersPanel, othersBtn, leavesFurniture.close, presentLeaves);
  registerTray("asks", asksPanel, asksBtn, asksFurniture.close, syncAsks);
  const trayNames = Object.freeze([...trays.keys()]);

  // The Asks tray's own walk, the leaves tray's twin: ArrowUp and ArrowDown are the page's
  // scroll everywhere else and the tray's here, and Enter is the platform's, a row being a
  // button — so the scope names what walking does and leaves the press to the button.
  function mountTrays() {
    traysEdge.handle(othersPanel, () => othersBtn);
    traysEdge.handle(asksPanel, () => asksBtn);
    for (const [key, { btn, close }] of trays) {
      btn.classList.add("lf-auxiliary-toggle");
      btn.onclick = () => setOpenTray(trayIsOpen(key) ? null : key);
      close.onclick = () => setOpenTray(null);
      btn.setAttribute("aria-expanded", "false");
    }
    keys(
      asksPanel,
      "In the Asks tray",
      [
        {
          id: "ask.list-walk",
          keys: ["ArrowUp", "ArrowDown"],
          routes: [
            {
              id: "ask.row-previous",
              binding: "ArrowUp",
              does: "Previous ask",
            },
            { id: "ask.row-next", binding: "ArrowDown", does: "Next ask" },
          ],
          does: "Walk the asks",
          line: "walk the asks",
          repeat: true,
          run: (binding) => {
            walkRows(askRows(), binding === "ArrowDown" ? 1 : -1);
            beginWalk("ask-tray", "Ask", () =>
              listWalkPosition(askRows(), document.activeElement),
            );
          },
        },
      ],
      () => askRows().length > 0,
    );
  }
  // A standing tray is one layer of the page the reader put on by pressing its button, so
  // Escape takes it off again. Whichever tray holds the edge is named by the step, so the
  // reader is told what the press will take rather than being told "close the tray" over
  // two of them; the tray's key is the runtime's, and the reader knows the strip by the
  // banner's word. Rooted at the open tray, so the step survives the width at which that
  // tray covers the page and becomes the floor.
  pageRung("tray", () =>
    currentTray()
      ? {
          root: trays.get(currentTray()).panel,
          says: `close ${currentTray()}`,
          does: `Close the ${currentTray()} tray`,
          // A tray's parent is the document, so its step lands the reader there rather
          // than on the edge button that reopens it.
          out: () => {
            setOpenTray(null, { returnFocus: false });
            letGo();
          },
        }
      : null,
  );

  return { setOpenTray, traysEdge, trayNames, mountTrays };
}
