/* One selected auxiliary surface, its remembered selection, and its covering boundary.

   Registered surfaces retain their own rendering and scrollports. Selecting one closes
   the previous surface before opening it; there is no per-surface visibility state.
   Every surface stands over the page and takes no room from it, so selecting one never
   changes the page's geometry. A surface whose rows need the first server reading
   declares presentation-time arrival, so its rendering and covering boundary wait for
   that reading.

   A surface either always covers the page or declares that it may stand `beside` it,
   leaving the page live. One that may stand beside covers the page only where it would
   leave less than a usable page beside it, and the stylesheet states that once for every
   such surface, as the width the selected one stands at or nothing where it covers
   (theme.css, `--lf-auxiliary-beside`); `standsBeside` is the runtime's one reading of it.

   The selected surface is seated in one native dialog, nonmodal beside the page and
   modal where it covers. Its actual nodes and the chrome foreground permitted above
   the scrim have permanent homes in that dialog: changing posture never disconnects
   editors, disclosures, embedded documents or standing native layers. The browser excludes
   every background subtree, including one a page revision adds. The retained visual
   scrim stays inside the dialog so page and chrome targeting keep their paint planes.

   Travel asks this owner to clear whatever surface hides a destination (`clearFor`),
   so every trip that promises to show one closes the same surfaces by the same rule.

   A surface that stands under the bottom bar, as a drawer does (its list ends above the
   band's stated height), keeps that band over it in the covering posture too: the band
   is the one always-visible guide to the keys the surface answers, and its More control
   stays live, so this owner contains it in the modal foreground and marks it
   `data-lf-over-covering` for the stylesheet to raise it over the scrim and the
   surface. The thread panel carries its own foot, and the band yields to it instead.

   Native modality owns background pointer and programmatic-focus exclusion. This owner
   keeps the existing Tab wrap, because native forward Tab can leave for browser chrome,
   and suppresses native opening focus while a restored sample has no document focus.
   Entering the covering boundary dismisses pre-existing outside popovers. Native dialogs
   and popovers opened inside the foreground then join the browser's own layer order. */

import { openPopovers, transitionNativeAncestor } from "./keyboard/layer-stack.js";
import { registerCoveringAuxiliarySurface } from "./keyboard/register.js";
import { hides, placeHolder } from "./geometry.js";
import { under } from "./shadow.js";
import { deepFocus, tabStops, holdFocus, returningFocus } from "./focus.js";
import { userStore } from "./storage.js";
import { pagePresented } from "./presentation.js";
import { keeps, keepsHidden } from "./keeps.js";
import { nextRender } from "./rendering.js";

export const AUXILIARY_SURFACE_KEY = "lf-auxiliary-surface";
let selectedKey = null;
export const currentAuxiliarySurface = () => selectedKey;
// Whether the selected surface stands beside the page, leaving it live: the length the
// stylesheet answers from the surface's width and the window's is more than nothing.
export const standsBeside = () =>
  parseFloat(
    getComputedStyle(document.body).getPropertyValue("--lf-auxiliary-beside"),
  ) > 0;

export function createAuxiliarySurfaces({
  envelope,
  band,
  syncLayout,
  afterChange,
  reachChanged,
}) {
  const controllers = new Map();
  const scrim = document.createElement("div");
  scrim.className = "lf-auxiliary-scrim";
  scrim.hidden = true;
  scrim.setAttribute("aria-hidden", "true");
  envelope.className = "lf-ui lf-auxiliary-envelope";
  // Start as an ordinary nonmodal presentation group. Initial `open` markup performs
  // no dialog focusing steps, so mounting chrome cannot borrow an author's focus.
  envelope.setAttribute("open", "");
  envelope.setAttribute("role", "presentation");
  envelope.append(scrim);
  let active = null;
  let standing = null;
  let mounted = false;
  let arriving = null;

  const place = (node) => {
    node.focus({ preventScroll: true });
  };
  function seat(selected) {
    const next = selected?.covers() ? selected : null;
    if (standing === selected && active === next) return;
    const previous = active;
    const changedPosture = Boolean(active) !== Boolean(next);
    if (next)
      for (const popover of openPopovers())
        if (!under(popover, next.surface)) popover.hidePopover();
    const held = holdFocus(document);
    returningFocus(() => {
      if (previous) previous.surface.removeAttribute("data-lf-covered");
      active = next;
      standing = selected;
      keeps(band, "inert", next && !next.underBand ? "" : null);
      if (next) keeps(next.surface, "data-lf-covered", "");
      if (changedPosture || !envelope.open) {
        // Opening a restored sample must not take focus from its containing page.
        // Native modality still begins while its own focusing steps are suppressed.
        transitionNativeAncestor(envelope, () => {
          if (envelope.open) envelope.close();
          const unfocused = !document.hasFocus();
          if (unfocused) envelope.inert = true;
          if (next) envelope.showModal();
          else envelope.show();
          if (unfocused) envelope.inert = false;
        });
      }
    });
    band.toggleAttribute("data-lf-over-covering", Boolean(next?.underBand));
    keepsHidden(scrim, !next);
    keeps(document.documentElement, "data-lf-covering-surface", next?.surface.id);
    const restored = held?.();
    if (
      next &&
      document.hasFocus() &&
      !restored &&
      !document.activeElement?.closest(":popover-open")
    )
      place(next.focus() ?? next.surface);
  }

  function registerAuxiliarySurface({
    key,
    surface,
    scroller,
    beside = false,
    underBand = false,
    focus,
    show,
    hide,
    arrival = "mount",
  }) {
    // The native dialog takes the selected surface's accessible name.
    if (
      !key ||
      !surface?.id ||
      !(
        surface.hasAttribute("aria-label") || surface.hasAttribute("aria-labelledby")
      ) ||
      !scroller ||
      !focus ||
      !show ||
      !hide
    )
      throw new Error(
        "leaf: an auxiliary surface needs a key, an id and an accessible name, a scroller, a focus destination, and visibility callbacks",
      );
    if (controllers.has(key))
      throw new Error(`leaf: duplicate auxiliary surface ${key}`);
    const controller = {
      key,
      surface,
      scroller,
      covers: () => !beside || !standsBeside(),
      underBand,
      focus,
      show,
      hide,
      arrival,
    };
    controllers.set(key, controller);
    return () => {
      if (controllers.get(key) !== controller) return;
      if (selectedKey === key) select(null);
      controllers.delete(key);
    };
  }

  // What the page can seat the user in changes with what stands over it: a surface
  // opening, closing, arriving, or its edge or the window moving. One reading a frame,
  // since a drag or a resize syncs on every event.
  let reachQueued = false;
  function sync() {
    const selected = controllers.get(selectedKey);
    const shown = selected && selected !== arriving ? selected : null;
    // Selection states the final accessible surface once. Lifting a previous native
    // boundary before its hide callback is only a mechanical handoff, not a visit to
    // the idle presentation group between two selected surfaces.
    keeps(envelope, "role", shown ? null : "presentation");
    keeps(envelope, "aria-label", shown?.surface.getAttribute("aria-label"));
    keeps(envelope, "aria-labelledby", shown?.surface.getAttribute("aria-labelledby"));
    seat(shown);
    if (reachQueued) return;
    reachQueued = true;
    nextRender(() => {
      reachQueued = false;
      reachChanged();
    });
  }

  function select(
    key,
    { remember = true, returnFocus = true, phase = "gesture" } = {},
  ) {
    if (key !== null && !controllers.has(key))
      throw new Error(`leaf: unknown auxiliary surface ${key}`);
    if (selectedKey === key) return;
    const previous = controllers.get(selectedKey);
    selectedKey = key;
    const selected = controllers.get(key);
    // The selected surface's width reaches the stylesheet's covering rule through this.
    if (key) document.body.dataset.lfAuxiliarySurface = key;
    else delete document.body.dataset.lfAuxiliarySurface;
    arriving =
      selected &&
      phase === "arrival" &&
      selected.arrival === "presentation" &&
      !pagePresented()
        ? selected
        : null;
    // The native boundary lifts before the previous surface hides, so the focus it
    // hands back lands on a live page. The selected surface takes the boundary at sync.
    if (!selected || arriving || Boolean(active) !== selected.covers()) seat(null);
    previous?.hide({ returnFocus });
    if (selected && !arriving) selected.show({ phase });
    sync();
    syncLayout();
    afterChange();
    if (remember) userStore.set(AUXILIARY_SURFACE_KEY, key ?? "");
  }

  function restore() {
    const key = userStore.get(AUXILIARY_SURFACE_KEY);
    select(controllers.has(key) ? key : null, { remember: false, phase: "arrival" });
  }

  function present() {
    if (!arriving) return;
    const surface = arriving;
    arriving = null;
    surface.show({ phase: "arrival" });
    sync();
    syncLayout();
    afterChange();
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    scrim.addEventListener("pointerdown", (event) => event.preventDefault());
    scrim.addEventListener("click", () => select(null));
    document.addEventListener(
      "keydown",
      (event) => {
        if (
          !active ||
          event.key !== "Tab" ||
          event.altKey ||
          event.ctrlKey ||
          event.metaKey
        )
          return;
        const available = tabStops(active.surface);
        if (!available.length) {
          event.preventDefault();
          place(active.surface);
          return;
        }
        const at = available.indexOf(deepFocus());
        if (
          (!event.shiftKey && at === available.length - 1) ||
          (event.shiftKey && at === 0)
        ) {
          event.preventDefault();
          place(event.shiftKey ? available.at(-1) : available[0]);
        }
      },
      true,
    );
  }

  // Travel that promises to show a destination clears the selected surface hiding it:
  // one covering the page, for anything outside it, or one standing over most of the
  // destination where it lands (geometry.js, `hides`). A destination inside the surface
  // is the surface's own to show. The one owner of this, so a trip to a thread, an Ask
  // or a datum each clears whatever surface happens to stand.
  function clearFor(where) {
    const selected = controllers.get(selectedKey);
    const holder = where && placeHolder(where);
    if (!selected || !holder || under(holder, selected.surface)) return;
    if (selected.covers() || hides(selected.surface, where)) select(null);
  }
  const selectedSurface = () => controllers.get(selectedKey)?.surface ?? null;
  const coveringSurface = () => active?.surface ?? null;
  const coveringScroller = () => active?.scroller() ?? null;
  const coveringFocus = () => (active ? (active.focus() ?? active.surface) : null);
  // The keyboard register carries this reading to the dispatcher, whose own closure stops
  // there: a direct edge to this owner would give a key press this owner's whole
  // initialization graph.
  registerCoveringAuxiliarySurface(coveringSurface);
  return {
    registerAuxiliarySurface,
    select,
    restore,
    present,
    sync,
    mount,
    clearFor,
    selectedSurface,
    coveringSurface,
    coveringScroller,
    coveringFocus,
  };
}
