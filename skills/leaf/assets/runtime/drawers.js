/* Drawer DOM and readonly visibility are safe to import before browser boot.
 * createDrawers binds modality transitions to explicit commands and paint functions;
 * mountDrawers installs the controls only after chrome has been attached. */
import { closeControl, el } from "./widget-elements.js";
import { drawnEdge } from "./drawn-edge.js";
import { slide } from "./motion.js";
import { declareOccluder } from "./geometry.js";
import { currentAuxiliarySurface } from "./auxiliary-surfaces.js";
import { handBack, letGo } from "./focus.js";
import { keys } from "./keyboard/scopes.js";
import { pageRung } from "./keyboard/register.js";
import { pagePresented } from "./presentation.js";
import { allAsks } from "./asks/model.js";
import { rowWalk } from "./walk-position.js";
import { createLiveLeavesList } from "./live-leaves-list.js";
import { bannerControlDoor, dismissBannerControls } from "./banner-toolbar.js";
import { createAskDrawerList } from "./asks/drawer-list.js";
import { keeps } from "./keeps.js";
// The left side holds one drawer at a time, selected by the shared auxiliary-surface owner.
// Both stand over the page and take no room from it. The leaves drawer covers the document
// because its rows leave the page. The asks drawer leaves the page live beside it, because
// its rows travel within the page and the user must keep the target reachable; where that
// would leave less than a usable page it covers the page instead, by the rule the thread
// panel follows on the other side (auxiliary-surfaces.js, `standsBeside`). Both entry controls
// call the same drawer setter.
//
// Drawers declare presentation-time arrival: their first paint needs the state-dependent
// rows.
//
// A handle lives inside the region it draws, so a drawn region must not be its own scroll
// container: a scroller clips a handle straddling its border and carries it away with the
// content. A drawer is a shell holding a `.lf-drawer-list`, and every drawer list
// reserves the shortcut bar's room where their horizontal spans meet. Wide content reads
// the shell's CSS value directly; there is no observed measurement loop or second number
// system to reconcile during a transition.

// The drawers' edge, on the left, and everything said above said again for it: the width
// it stands at until the user moves it, and how narrow they may draw it.
//
// 220 is where the drawer's own row stops being one. A leaf's row spends 45px before any
// word of the page's — the status dot's 9px, its 8px gap, and the 20px and 8px the row
// and the drawer take for padding — and what is left holds a title that ellipsizes rather
// than wrapping, so under this the drawer is furniture showing the first syllable of every
// name on it. The Asks drawer's rows clamp to three lines instead and would go on reading
// further down, which is why the floor is the leaves drawer's to set.
const DRAWER_SLOT_W = 300;
const DRAWER_SLOT_MIN = 220;
// Where the standing width is written, and where the cascade reads it. theme.css and
// chrome.css spell the same name, and theme.css the same default for the first paint of
// a reloaded page, and the layer test holds the spellings equal, since a stylesheet
// cannot read a constant.
export const DRAWER_SLOT_PROP = "--lf-drawer-slot-width";

// The rows' own box, one per drawer. Collected privately as they are made, because what
// the layout reserves at the foot of one it reserves at the foot of every one — and a
// second place to remember that is exactly where the Asks drawer was left out of it: its
// walk parked the last row 47px under the shortcut bar, on the one drawer nothing had ever
// walked to the end of. Callers state the clearance; this owner decides which lists it
// reaches and how each one spends it.
function drawerFurniture(panel, name, list = el("div", "lf-drawer-list")) {
  const head = el("div", "lf-drawer-head");
  const title = el("span", "lf-auxiliary-title", name);
  const close = closeControl({
    name: `Close ${name.toLowerCase()}`,
    title: `Close ${name.toLowerCase()} (Esc)`,
  });
  list.classList.add("lf-drawer-list");
  head.append(title, close);
  panel.append(head, list);
  // An open drawer stands over the left of the page, so what it stands over is hidden
  // from every reading of what the page shows (geometry.js).
  declareOccluder(panel);
  return { list, close };
}

// Every active Ask and the route back through its current answer. The banner says
// completed/total (sayAsks); a/A still walks only the open worklist.
export const asksBtn = el("button", "lf-btn lf-asks", "");
// The machine's live leaves and what each is doing: a left panel of rows, each a
// link opening that page in its own tab, saying what that page's agent last declared
// in the shape of the banner's activity — `others` on /api/state carries it for every
// live page, and every URL in the list carries only the key this user already
// holds, since there is one key for the machine (`host_key`). The current page heads
// the list as a marked, unlinked row, so the panel reads as the whole machine. A
// status drawer's point is being live, so rows reconcile on every applied state, keyed by URL —
// the stable identity, since address, port and key all survive a restart — and a
// status change repaints the row's own dot and words without moving it.
export const othersBtn = el("button", "lf-btn lf-others", "");
othersBtn.title = "Leaves live on this machine, and what each is doing";
// A nav, because navigation is what it is and a bare div may not carry the
// aria-label the card needs (axe: aria-prohibited-attr, serious).
export const othersPanel = el("nav", "lf-ui lf-drawer-panel lf-others-panel");
othersPanel.id = "lf-leaves";
othersPanel.setAttribute("aria-label", "Leaves on this machine");
othersPanel.tabIndex = -1;
const leavesFurniture = drawerFurniture(
  othersPanel,
  "Leaves",
  createLiveLeavesList(othersBtn),
);
export const liveLeavesList = leavesFurniture.list;
// A drawer of the page's active asks, on the same edge: open and answered rows in the
// order the page asks them. The list is declaration-driven, so a widget joins without
// a row here knowing what kind of thing it is standing for.
export const asksPanel = el("nav", "lf-ui lf-drawer-panel lf-asks-panel");
asksPanel.id = "lf-asks";
asksPanel.setAttribute("aria-label", "Asks from this page");
asksPanel.tabIndex = -1;
const asksFurniture = drawerFurniture(asksPanel, "Asks", createAskDrawerList());
export const asksList = asksFurniture.list;

// Furniture is local to this edge; selection belongs to the auxiliary-surface owner.
const drawers = new Map();
export const currentDrawer = () =>
  drawers.has(currentAuxiliarySurface()) ? currentAuxiliarySurface() : null;
export const drawerIsOpen = (key) => currentDrawer() === key;
// Each drawer's one offer: something to show, or the drawer already standing so its button
// can still close it. An Asks drawer of none is the same.
export const asksOffered = () =>
  pagePresented() && (allAsks().length > 0 || drawerIsOpen("asks"));
export const askRows = () => [...asksPanel.querySelectorAll("button.lf-asks-row")];

export function createDrawers({
  landEdge,
  auxiliarySurfaces,
  closePreview,
  leavesOffered,
  presentLeaves,
  syncAsks,
}) {
  const drawersEdge = drawnEdge({
    side: "left",
    noun: "drawer panel",
    wide: DRAWER_SLOT_W,
    min: DRAWER_SLOT_MIN,
    prop: DRAWER_SLOT_PROP,
    key: "lf-drawer-slot-width",
    when: () => leavesOffered() || asksOffered(),
    land: landEdge,
  });

  function setOpenDrawer(key, options) {
    if (key || currentDrawer()) auxiliarySurfaces.select(key, options);
  }
  function registerDrawer(key, panel, btn, close, paint) {
    auxiliarySurfaces.registerAuxiliarySurface({
      key,
      surface: panel,
      scroller: () => panel.querySelector(".lf-drawer-list"),
      // Asks needs the document beside it because its rows lead to controls there.
      // Leaves covers it: its rows leave the page.
      beside: key === "asks",
      // Every drawer list ends above the bottom bar, which stands over the drawer in
      // both postures.
      underBand: true,
      focus: () =>
        panel.querySelector(".lf-drawer-list button, .lf-drawer-list a[href]") ?? panel,
      arrival: "presentation",
      show({ phase }) {
        dismissBannerControls();
        closePreview();
        keeps(btn, "aria-expanded", "true");
        // Filled before it is shown, so the drawer is its own list from the first frame of
        // the slide rather than a blank card that populates a moment later. The way down
        // is the mirror of it, below: emptied once it is hidden, never before, or the
        // user watches the list they just closed blank out and an empty card slide away.
        paint?.();
        panel.classList.toggle("open", true);
        if (phase === "gesture") slide(panel, "left", "in");
      },
      hide({ returnFocus }) {
        keeps(btn, "aria-expanded", "false");
        if (!panel.classList.contains("open")) return;
        // Before the slide, which makes the drawer inert and would drop focus to body.
        if (returnFocus && panel.contains(document.activeElement))
          handBack(bannerControlDoor(btn));
        // Slid out before hidden, and hidden only if still closed on arrival — a
        // reopen mid-slide leaves the panel standing rather than racing the finish.
        const out = slide(panel, "left", "out");
        const hide = () => {
          if (drawerIsOpen(key)) return; // reopened mid-slide; it stays up, list and all
          panel.classList.toggle("open", false);
          paint?.();
        };
        if (out) out.finished.then(hide, () => {});
        else hide();
      },
    });
    drawers.set(key, { panel, btn, close });
  }
  // The painters are thunks: each drawer's owner imports this module back, so neither
  // painter is a binding this module can read as it evaluates.
  registerDrawer(
    "leaves",
    othersPanel,
    othersBtn,
    leavesFurniture.close,
    presentLeaves,
  );
  registerDrawer("asks", asksPanel, asksBtn, asksFurniture.close, syncAsks);
  const drawerNames = Object.freeze([...drawers.keys()]);

  // The Asks drawer's own walk, the same one as the leaves drawer's: the arrows, Home and End
  // are the page's scroll everywhere else and the drawer's here, and Enter is the
  // platform's, a row being a button — so the scope names what walking does and leaves
  // the press to the button.
  function mountDrawers() {
    drawersEdge.handle(othersPanel, () => othersBtn);
    drawersEdge.handle(asksPanel, () => asksBtn);
    for (const [key, { btn, close }] of drawers) {
      btn.classList.add("lf-auxiliary-toggle");
      btn.onclick = () => setOpenDrawer(drawerIsOpen(key) ? null : key);
      close.onclick = () => setOpenDrawer(null);
      btn.setAttribute("aria-expanded", "false");
    }
    keys(
      asksPanel,
      "In the Asks drawer",
      rowWalk({ id: "ask.drawer", noun: "Ask", plural: "asks", rows: askRows }),
      () => askRows().length > 0,
    );
  }
  // A standing drawer is one layer of the page the user put on by pressing its button, so
  // Escape takes it off again. Whichever drawer holds the edge is named by the step, so the
  // user is told what the press will take rather than being told "close the drawer" over
  // two of them; the drawer's key is the runtime's, and the user knows the strip by the
  // banner's word. Rooted at the open drawer, so the step survives the width at which that
  // drawer covers the page and becomes the floor.
  pageRung("drawer", () =>
    currentDrawer()
      ? {
          root: drawers.get(currentDrawer()).panel,
          title: `close ${currentDrawer()}`,
          description: `Close the ${currentDrawer()} drawer`,
          // A drawer's parent is the document, so its step lands the user there rather
          // than on the edge button that reopens it.
          out: () => {
            setOpenDrawer(null, { returnFocus: false });
            letGo();
          },
        }
      : null,
  );

  return { setOpenDrawer, drawersEdge, drawerNames, mountDrawers };
}
