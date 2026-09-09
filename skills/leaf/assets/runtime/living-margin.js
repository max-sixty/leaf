/* The living margin: each page target's margin element cluster, the thread card and Page map
   sheet those margin elements open, and each surface's way back out.

   A margin element is one stable circular unit attached to a page target. Its behavior
   may be `action`, `disclosure`, or `status`: action and disclosure margin elements are controls,
   while a status margin element is an indicator with no press. Behavior may change without
   changing the margin element's identity or moving its seat. The target's cluster is the single
   place for its controls, communications, and standing information such as comment
   threads, Asks, changes, or agent activity.

   `marginElement` is the implementation's neutral container name. Reader-facing labels and
   guidance name the current semantic role: action control, disclosure control, or status
   indicator.

   At rest a cluster has a two-margin element budget: the primary and one peer, or the primary and
   `…` when there are at least two peers. Hiding one peer costs the same margin element as
   showing it and adds a press, so it is not overflow. With no contributed control,
   standing information supplies the primary margin element using the face its reading declares.

   Durable state provenance is the one standing fact kept in Page map without a target
   margin element. It explains whether effective state came from the reader, a provisional
   report, or a version restatement; unlike an action it must not change target geometry,
   control density, or keyboard order. Its Page-map row travels back to the target.

   The expanded budget is six margin elements, including the primary or visible reading marker
   where one exists; a target made only of peer choices uses all six. A larger set shows
   the margin elements that fit and a final overflow margin element whose label gives the remaining count.
   That opens the existing Page map at the first excess action; every excess control has
   its own named row which performs that exact action. Do not grow another popover for
   overflow. The same limit and exact-action route apply when the cluster docks on a
   narrow screen.

   An engaged contribution exposes its peers within that budget. Engagement is the owner's
   semantic interaction state, not DOM focus: an open editor, for example, keeps Save and
   Cancel exposed until either action ends the edit, even if focus moves within the
   document. An unsettled reader action engages the whole target in the same way, keeping
   its delivery lifecycle visible until the handoff settles. An engaged set has no `…`;
   completion and escape actions take the first margin elements, so the density limit cannot hide
   the way to finish or leave the active interaction.

   An explicit owner-focused mode temporarily derives the rail from one contribution
   alone, while Page map retains the target's complete inventory. This is how a mode with
   six declared choices uses six direct margin elements even when the target already carries a
   reading or unrelated action; closing it restores the ordinary cluster.

   Keyboard arrival unfolds that same cluster immediately: Tab into any of its margin elements
   replaces `…` with the expanded set, and Left/Right wrap through those visible margin elements.
   A pointer press on `…` makes the same replacement and lands on the first revealed
   margin element. Escape folds that temporary expansion, restores `…`, and returns focus to it;
   moving focus or the pointer outside folds without taking focus. None of those routes
   folds peers required by an engaged contribution, and moving into a modal or thread
   surface the cluster opened does not count as leaving it. The cluster uses one temporary
   expansion state for both keyboard and pointer routes; focus does not create a parallel
   presentation. A category walk that lands on a margin element does not unfold its peers: it is
   navigation rather than Tab arrival, so one Escape still lets go of the destination the
   walk put down. A generated Page-map hint arrives the same way and then presses that
   margin element, so anything unfolded there is the press's own result rather than the arrival's,
   and Escape still lets go of where the press left the reader.

   An unsettled reader action reuses that same margin element rather than growing a status row
   inside authored content. Its server-projected information face advances from Sent or
   Waiting for pickup to Queued or Picked up, then to Active only when a typed local
   claim exists; an acknowledgment keeps the same retained target cluster throughout
   that live handoff. The delivery phases report a move already made, so the margin element
   wears the flat `status` behavior below. Active raises it back into a disclosure.
   Once no receipt or claim is live, the
   generated margin element disappears; the widget and action projection carry the durable state.
   A thread's existing thread margin element remains the page-edge route to the exact receipt in
   the full conversation; an Active claim joins that engaged cluster as an exposed peer. A
   standalone page-widget claim gets an Active margin element directly. When no page edge
   exists—inside the full thread panel or a widget frozen into conversation chrome—the
   compact `.lf-receipt` remains the local fallback.

   Content modules contribute through `registerMarginContribution({key, target, controls, subject,
   state, ...})`; they own their verbs and events, never placement or control styling.
   `key` is stable within a target. Optional `subject` is a string or live reading of the
   concise semantic subject used to name that target away from its own paint. Supply it
   only when plain text concatenation loses a relation the widget paints visually, such as
   a rewrite's `old → new`; contributions at the same target must agree. `state` is a
   value or live reading of `idle`, `engaged`, `busy`, or `failed`; every state but idle
   keeps the owner's peers exposed. A contribution item that sets `represents` and
   names its `kind` is also the visible reading of that state, so the margin suppresses a
   generated reading of the same kind at that exact target rather than showing the fact
   twice. Every margin element in a contribution is built with `marginElement(control, {key, icon,
   label, context, behavior, tone, role, state, writesRelation, writesSeat})`; an
   authored reaction can supply `glyph` instead of `icon`, never both. That is the one RHS control type: it owns the circle,
   size, type, focus, state paint, and glyph/word anatomy shared by Asks, editing,
   communications, and information triggers. Its behavior states what the margin element
   promises. Behavior, tone, and state are independent axes: never use a heavier border to
   mean positive, busy, selected, or complete.

   `marginElement` also establishes the canonical margin element record: key, face, label, context,
   behavior, tone, role, lifecycle state, and the relation writer the call declared. The
   record carries that last one because the options group rebuilds a proxy margin element from
   it, and a proxy that re-inferred the default would write a relation its source has no
   writer for. Registration assigns its stable owner and rejects duplicate margin element keys
   within that owner. The compact rail and complete Page map
   both render from this record; neither infers semantics by scraping the contributor's
   painted DOM. Transient native state such as disabled and `aria-expanded` is mirrored
   onto a retained proxy, while the original contributor control remains the only
   activation owner.

   - `action` has a uniformly heavier ring and a small lower shadow, carries an imperative
     verb, and performs its effect immediately;
   - `disclosure` has a firmer single ring than status and the same paper surface. It
     carries `aria-expanded`, reveals or hides context without settling it, and includes
     the generated More margin element whose ellipsis is its whole face. `marginElement` writes
     that attribute's default unless the call says `writesRelation: false`, which
     declares that another writer decides the disclosure's relation — the margin's own
     readings, whose `aria-controls` and `aria-expanded` are settled together from
     whether the reading opens a thread. Two writers over one attribute say something
     different each pass, so no record of theirs restates anything while the document's
     disclosure watch reads the pair as news. `writesSeat: false` says the same thing
     about the control's `tabindex`: the rail's roving stop writes every row's seat on
     the frame after each pass, so a marker that seated itself here would have the next
     pass contradict it. The two are declared apart because they part on the reading
     options, which stand outside the rail's walk and own their own seat while another
     writer owns their relation;
   - `status` reports a move already made and offers no press. It keeps its icon and its
     circular margin element silhouette and seat in the cluster on the page surface with a
     ghost hairline, but gives up its raised edge, hover response, pointer, and tab stop. It
     remains a `status` in the accessibility tree so the Page map can still land there and
     name the phase. Status is live-session information, so a copy drops it.

   A generated reading wears more than one of those over its life — a thread margin element while
   there is something to open, a status once the move is reported — and one element has to
   carry both, or the seat moves under a reader standing in it. Such a control is
   therefore a span, since a `<button>` cannot stop being one, and the activation the
   platform then does not supply is declared by the page map's own scope (`margin.press`)
   rather than by a listener on the control: a key the register does not hold is a key no
   surface can promise.

   Material and ring weight distinguish immediate actions, disclosures, and statuses:
   Action is raised, Open is outlined, and a read-only report stays flat behind the palest
   ring. Their resting interiors all use the page surface, so fill does not imply that a
   status is selected or pressed. The shape stays shared, with no added mark. A lone
   non-thread informational margin element reveals its target directly. Each additional non-thread
   reading gets its own peer margin element under `…`; pressing one reveals that reading directly
   rather than collecting readings in a card. All threads at one target share one Thread
   margin element and one conversation card. That card opens only on a press, never merely on
   focus or hover. It uses the right margin at a readable width, then the left, without
   changing sides as unrelated margin elements scroll past. It avoids its own cluster;
   other margin elements may pass behind it. When neither margin fits, it overlays the
   document above or below that cluster. Once the reader scrolls the cluster out of the
   visible region, the card closes rather than standing without its page address. Only
   an already-open Threads panel redirects the press to the complete index. The thread
   card is the only generated contextual pane, not a generic container for alternatives.

   Tone is `neutral`, `positive`, or `negative`, expressed through icon color only; rings,
   fills, and the busy mark keep their shared neutral treatment. `busy` is the one state
   that paints: a small open moving ring at the corner (static under reduced motion). It
   paints because it is the only state nothing else on the page states — a busy margin element
   stays at full opacity and keeps its pointer, so with no ring an in-flight press looks
   idle — and because a moving outline is the one mark this size a reader can still
   resolve. Busy also sets `aria-busy="true"`. The other states carry the same ordering
   and fold-open weight while painting nothing, because each already has words beside it:
   a failure keeps visible words beside the controls that can repair it, and an engaged
   margin element stands next to the open interaction it belongs to. A status's phase is its
   transient hover or focus label. Reaction toggles retain their vocabulary labels and
   `aria-pressed`, which is what their palette fill reads; a standing reaction mark exists
   only while its reaction stands, so its presence is the whole of what it has to say.
   `marginElementState(control, state)` changes that axis without changing the verb, ring,
   or tone. Built-in faces use the shared monochrome SVG vocabulary with `currentColor`;
   emoji and font-dependent symbols are not structural icons. Reaction glyphs are content
   declared by the layer and retain their declared vocabulary order.

   Ordering is semantic, not registration or DOM order. Active contributors rank failed,
   busy, then engaged; ordinary contributors follow. Within that order, roles rank
   `complete`, `escape`, `primary`, `secondary`, `reading`, then `overflow`. Stable
   contributor and control keys break ties. The primary is the first available contributed
   control; generated readings follow direct controls, and a temporary communication
   palette keeps its own keyed order after those readings. Reordering a module's setup
   must not move an unrelated action into the primary margin element.

   A failed mutation leaves Failed · Retry · Cancel at its target. Retry makes a new
   attempt only after a definitive refusal; an ambiguous transport result stays busy while
   the outbox retries the same attempt. Details is a disclosure only when there is useful
   detail to show. An editor retains the user's text; typing again returns from failed to
   engaged. Reversible actions normally act immediately and offer Undo, which withdraws
   the named logged gesture under the same authored-version, replayability, and
   pending-delivery guards as keyboard Undo. Confirmation is for a genuinely irreversible
   effect, not routine Save or Accept. The layer-wide submission lifecycle in CLAUDE.md
   governs feedback; a settled cluster keeps only the actions still available there, such
   as Undo, and never leaves an inert margin element-shaped status.

   The Page-map keyboard scope owns the cluster's way back out. When a thread card stands
   over an unfolded `…` group, Escape closes the card first and folds the secondary
   margin elements on the next press; each rung is named on the shortcut bar before it runs.

   A gesture that unfolds a cluster for its own use puts that fold back, and only that
   one: putting the reaction choices away folds back the cluster the raise unfolded, so a
   disarm over a reply strip or over a fold the reader opened themselves takes away no
   layer the gesture put on. That put-down folds without claiming the focus — it runs from
   wherever the reader is standing, so taking the focus would throw them onto a cluster
   they may have left, and would send a press already on its way to a margin element they were not
   standing on.

   Every margin element-shaped margin element keeps one circle. Its label appears as transient chrome on
   hover or keyboard focus without changing the cluster's geometry. An open disclosure
   suppresses the label because the context it opened now names the margin element's result. A
   disclosure label ends in an ellipsis because it opens something; action and status
   labels do not. A status may add a quieter context line, such as how long ago its phase
   began. The complete label remains in the DOM, and its accessible name tracks the
   control or status.

   A marker's accessible name also carries where it stands in the walk: which location of
   how many, and how far down the page. That is how a reader listening places it, and it
   belongs to the name alone. Painted beside the phase, the same words read as progress
   rather than position.

   Hover or focus on any interactive margin element connects it to its exact target with the same
   quiet neutral trace, including when packing displaced the cluster. The trace is
   correspondence, not keyboard focus, so it never borrows the accent ring that promises
   interaction. Hovering a status also shows its label without lifting the margin element. A
   generated Page-map arrival may still focus a margin element and trace its target deliberately.
   Labels stay inside the viewport without moving the margin element. Dense and narrow-screen
   tests must exercise that association and activate an excess action through Page map;
   counting hidden DOM nodes is not evidence of reachability.

   The living margin groups contributions and state readings by exact target identity,
   chooses the primary, and owns the generated disclosure and `…` margin elements plus the
   cluster's accessible group name. At wide widths it hoists that host into the main
   positioning context, preserving source and tab order when several targets share a
   top-level block. At compact widths it returns the host to flow immediately after the
   target's rendered text block (or the target itself). Adding another target action must
   not add another absolute row, control type, or rail measurement.

   Each render reads once which contributed controls paint, and it does not take that
   reading on paper. Print takes every injected control out of the page, so the reading
   comes back empty there and folds every cluster to nothing — the medium written down as
   the page's state, standing on screen after the print preview closes. A render asked for
   while `print` matches is refused whole and taken once the screen is back. It is the
   thread list's head-room rule on the layer's other measuring surface: a reading taken
   where the box is `display: none` is not a measurement.

   That ordered target collection is the Page map's complete location count and the source
   for the generated `g` target list. A location's disclosure margin element announces its
   position in the complete collection. The sequence exposes every actionable location in
   the visible window. `g M` and the banner's Map control open the complete sheet,
   which projects the same currently available contributed controls in owner and role
   order, plus readings that have no direct control. An offered reading that merely
   describes its owner's controls is omitted there rather than becoming a parallel “open
   action” beside the real verbs. Ordinary entry focuses the sheet's filter, so a large
   map is searchable by margin element name, concise target name, or the visible passage
   containing that target without tabbing through every preceding action. A spill opens
   this complete sheet focused on the first control the compact cluster omitted; it does
   not make a smaller overflow-only menu.

   Live reconciliation retains the DOM identity of each surviving margin element and each of its
   hit-tested descendants, including a count badge. State-feed refreshes can arrive
   between pointerdown and pointerup, so rebuilding an unchanged face would cancel the
   browser's click even if its replacement had identical markup. The open Page map follows
   the same rule for its groups and action proxies; a refresh updates their meaning
   without replacing the control under focus or a held pointer.

   A thread card names the target without offering a second route to the panel the banner
   already opens. It is the conversation itself, filling a readable side margin and
   shifting eight pixels above or below its own cluster when that cluster occupies the
   same strip. Without a readable side margin, the card uses that clearance over the page.
   While that margin element keeps focus, `c` enters the card's one reply box; several roots leave
   the destination ambiguous and preserve the page's ordinary comment route. Replacing an
   open panel waits for the column's workspace motion before choosing the card posture.

   Closing is not the mirror of that. The platform hides the dialog and restores focus at
   once but hands `close` to a task of its own, so a reader who leaves a surface and
   returns to it in the same breath — Esc off an overflow route and straight back onto the
   control that named it — is standing in the next opening before the first one's close
   arrives. A handler that tears down the opening's state therefore reads whether the
   dialog is open again and gives that reopening its state back rather than taking it: a
   `close` overtaken by a reopen has nothing left to close. The state a late close would
   have cleared is what the surface is read by, and losing it is silent — the sheet still
   stands, still says its name, and the next press inside it means something else.

   The same task boundary decides who puts focus back. A surface's own close route returns
   the reader to the control that opened it, which is right for a press on that control
   and wrong for a keyboard entry: the dispatcher captured the reader's exact place before
   the command ran and restores it synchronously, so a return route delivered a task later
   overwrites the restore and leaves them holding a door they never touched. A close that
   places the reader itself therefore says so, by raising the flag the `close` handler
   reads: `leavePageMap` unwinding the dispatcher's frame, so that frame's restore stands,
   and the two activation routes that land the reader on the map control or on the control
   the row forwards to. A close that raises nothing — the Close button, the platform's own
   dismissal — still runs the surface's own route. */

import {
  layoutMarginRows,
  registerMarginRow,
  reserveRail,
  scheduleMarginLayout,
  unregisterMarginRow,
  updateMarginRow,
} from "./margin-layout.js";
import { documentPoint, shownBox, shownParts } from "./geometry.js";
import { el, focusDestination, keeps, keepsHidden, offer } from "./widget-elements.js";
import { clampedRow, PRESS } from "./keyboard/bindings.js";
import { landInConversation, showThread } from "./conversation/landing.js";
import { ago, clocked } from "./presence.js";
import { runtime } from "./context.js";
import { readingRegionFor, shownRegionBounds } from "./reading-regions.js";
import { commentsEdge, panelIsOpen } from "./chrome-layout.js";
import { designOn } from "./design.js";
import { focused, keys, paintHere, paintKeys } from "./keyboard/scopes.js";
import { chromeRoot } from "./chrome.js";
import {
  comparisonBase,
  comparisonChanges,
  comparisonEarlier,
  toggleEarlier,
  versionBtn,
} from "./version.js";
import { foldShelf } from "./banner-shelf.js";
import { motion, scrollBehavior } from "./motion.js";
import { panel } from "./conversation/panel.js";
import { blockAt, closestAcross, elementById, inChrome, says } from "./passages.js";
import {
  itemSays,
  itemWord,
  placedAt,
  scrollToElement,
  scrollToThread,
  traceTarget,
} from "./anchors.js";
import { updateSequence, workClaimState } from "./updates.js";
import { threadList } from "./conversation/reconcile.js";
import { threadKey } from "./conversation/model.js";
import { openAsks } from "./asks/model.js";
import { goToAsk, standsWith } from "./asks/view.js";
import { stateOrigins, stateProjection } from "./projection/fold.js";
import { notice } from "./notifications.js";
import { iconElement } from "./icons.js";
import { claimed, focusSurface } from "./conversation/surfaces.js";
import { anchorLabel } from "./conversation/messages.js";
import { renderMarginThread } from "./conversation/inline.js";

const KINDS = {
  action: { label: "Action", icon: "dot", priority: -1 },
  change: { label: "Change", icon: "change", priority: 0 },
  restated: {
    label: "Rewritten",
    icon: "change",
    priority: 0,
    indication: true,
  },
  comment: { label: "Thread", icon: "comment", priority: 1 },
  ask: { label: "Ask", icon: "question", priority: 2 },
  sent: {
    label: "Sent",
    icon: "sent",
    priority: 3,
    indication: true,
    state: "busy",
  },
  pickup: {
    label: "Picked up",
    icon: "pickup",
    priority: 3,
    indication: true,
    state: "idle",
  },
  waiting: {
    label: "Waiting for pickup",
    icon: "waiting",
    priority: 3,
    indication: true,
    state: "busy",
  },
  reader: {
    label: "Your change",
    icon: "change",
    priority: 4,
    indication: true,
  },
  reported: {
    label: "Reported update",
    icon: "activity",
    priority: 4,
    indication: true,
  },
  activity: { label: "Active", icon: "activity", priority: 4, state: "busy" },
};

// Content modules contribute what their target offers; this projection decides where
// those controls stand and joins them to every other reading of the same target. The
// store is module-level because widgets upgrade after the margin is composed and may
// reconnect while a live version replaces the authored document.
const marginContributions = new Set();
const contributionListeners = new Set();
export const MARGIN_ELEMENT_SCHEMA = Object.freeze({
  tones: Object.freeze(["neutral", "positive", "negative"]),
  behaviors: Object.freeze(["action", "disclosure", "status"]),
  states: Object.freeze(["idle", "engaged", "busy", "failed"]),
  roles: Object.freeze([
    "complete",
    "escape",
    "primary",
    "secondary",
    "reading",
    "overflow",
  ]),
});
const MARGIN_ELEMENT_TONES = new Set(MARGIN_ELEMENT_SCHEMA.tones);
const MARGIN_ELEMENT_BEHAVIORS = new Set(MARGIN_ELEMENT_SCHEMA.behaviors);
const MARGIN_ELEMENT_STATES = new Set(MARGIN_ELEMENT_SCHEMA.states);
const MARGIN_ELEMENT_ROLES = new Set(MARGIN_ELEMENT_SCHEMA.roles);
const STATE_PRIORITY = new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["idle", 3],
]);
const ROLE_PRIORITY = new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5],
]);
const RESTING_MARGIN_ELEMENT_BUDGET = 2;
const EXPANDED_MARGIN_ELEMENT_BUDGET = 6;
const MARGIN_ELEMENT_RECORD = Symbol("Leaf margin element record");
const FORWARDED_MARGIN_ELEMENT_ATTRIBUTES = [
  "aria-busy",
  "aria-controls",
  "aria-disabled",
  "aria-expanded",
  "aria-haspopup",
  "aria-pressed",
];

const changedContributions = () => {
  for (const listener of contributionListeners) listener();
};

const visibleMarginElementLabel = ({ behavior, label }) =>
  behavior !== "disclosure" || label.endsWith("…") ? label : `${label}…`;

function marginElementRecord(control) {
  const record = control?.[MARGIN_ELEMENT_RECORD];
  if (!record)
    throw new TypeError("A contributed margin element must use marginElement");
  return record;
}

function marginElements(controls) {
  if (!(controls instanceof Element)) return [];
  if (controls.matches(".lf-margin-element")) return [controls];
  return [...controls.querySelectorAll(".lf-margin-element")];
}

function validateMarginElements(offered) {
  const keys = new Set();
  for (const control of marginElements(offered.controls)) {
    const record = marginElementRecord(control);
    if (keys.has(record.key))
      throw new TypeError(
        `Duplicate margin element key "${record.key}" in margin contribution "${offered.key}"`,
      );
    if (record.owner && record.owner !== offered.key)
      throw new TypeError(
        `margin element "${record.key}" already belongs to margin contribution "${record.owner}"`,
      );
    keys.add(record.key);
    record.owner = offered.key;
    control.dataset.lfMarginElementOwner = offered.key;
  }
}

function syncForwardedMarginElementState(projection, source) {
  const label = source.getAttribute("aria-label");
  if (label == null) projection.removeAttribute("aria-label");
  else keeps(projection, "aria-label", label);
  const disabled = source.disabled || source.getAttribute("aria-disabled") === "true";
  if (projection.disabled !== disabled) projection.disabled = disabled;
  for (const attribute of FORWARDED_MARGIN_ELEMENT_ATTRIBUTES) {
    const value = source.getAttribute(attribute);
    if (value == null) projection.removeAttribute(attribute);
    else keeps(projection, attribute, value);
  }
}

// One margin element grammar for every gesture in a target's RHS cluster. Contributors keep
// their verbs and events; the margin owns the behavior and anatomy that make the
// controls one family. The visible word stays in the DOM as a transient label, so
// every margin element-shaped margin element keeps one stable accessible name. Native `title`
// bubbles would repeat the word on a different timer and with a different face, so
// this anatomy owns its only visual presentation too.
export function marginElement(
  control,
  {
    glyph = null,
    icon = null,
    key,
    label,
    context = null,
    behavior = "action",
    tone = "neutral",
    role = "primary",
    state = "idle",
    // Whether this call writes the disclosure's relation. True for every disclosure the
    // layer draws, which carries `aria-expanded` from the moment it appears. False says
    // another writer owns it: the margin's readings, whose `aria-controls` and
    // `aria-expanded` `syncReadingRelation` decides together from whether the reading
    // opens a thread, or holds what its own item declares, and takes off together when
    // it holds neither. The declaration names
    // the writer rather than the role, because `marginElement` is published through the
    // widget API and a module reaching it brings no second writer with it.
    writesRelation = true,
    // Whether this call seats the control. True for every margin element that owns its own tab
    // stop, including the reading options, which stand in a group the rail's walk does
    // not reach. False says the rail's roving stop owns the seat: `holdTabStop` writes
    // every row's `tabindex` on the frame after each pass, so a seat written here is a
    // second writer the next pass contradicts — an unguardable `0` and `-1` taking turns
    // on every marker the stop is not on. Declared for the same reason as the relation:
    // the role cannot stand in for it, since a marker and a reading option wear the same
    // one and only the marker is a row.
    writesSeat = true,
  },
) {
  if (!(control instanceof Element))
    throw new TypeError("A margin element needs an Element control");
  if (!String(key ?? "").trim()) throw new TypeError("A margin element needs a key");
  if (Boolean(String(glyph ?? "").trim()) === Boolean(icon))
    throw new TypeError("A margin element needs exactly one glyph or icon");
  if (!String(label ?? "").trim())
    throw new TypeError("A margin element needs a label");
  if (!MARGIN_ELEMENT_TONES.has(tone))
    throw new TypeError(`Unknown margin element tone: ${tone}`);
  if (!MARGIN_ELEMENT_BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin element behavior: ${behavior}`);
  if (!MARGIN_ELEMENT_ROLES.has(role))
    throw new TypeError(`Unknown margin element role: ${role}`);
  const record = control[MARGIN_ELEMENT_RECORD] ?? {};
  Object.assign(record, {
    key: String(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: String(label),
    context: String(context ?? "").trim() || null,
    behavior,
    tone,
    role,
    state,
    // Carried on the record because `optionControlNode` rebuilds a margin element from one: a
    // proxy that re-inferred the default would write the disclosure relation its source
    // has no writer for, and `syncForwardedMarginElementState` would strip it again the same
    // pass. The seat is not carried — a proxy is a native button standing outside the
    // rail, so it always owns its own.
    writesRelation,
  });
  control[MARGIN_ELEMENT_RECORD] = record;

  if (!control.classList.contains("lf-margin-element"))
    control.classList.add("lf-margin-element");
  control.removeAttribute("title");
  keeps(control, "data-lf-margin-element-key", record.key);
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-role", record.role);
  keeps(control, "data-lf-offer", behavior === "status" ? "" : "button");
  marginElementState(control, state);
  const opens = behavior === "disclosure";
  // A default written where another writer owns the relation is a second writer the
  // same pass then strips — an add and a remove per heartbeat, and the remove reads as
  // news to the document's disclosure watch, so an untouched page repaints its keys at
  // the refresh rate.
  if (opens && writesRelation && !control.hasAttribute("aria-expanded"))
    control.setAttribute("aria-expanded", "false");
  if (!opens) control.removeAttribute("aria-expanded");
  if (behavior === "status") {
    keeps(control, "role", "status");
    // The attribute rather than the property: a span with no `tabindex` already reads
    // `tabIndex === -1`, so a property guard would never write the one that makes the
    // seat programmatically focusable, while an unguarded write restates it every pass.
    if (writesSeat) keeps(control, "tabindex", -1);
  } else if (!(control instanceof HTMLButtonElement)) {
    keeps(control, "role", "button");
    if (writesSeat && control.tabIndex < 0) control.tabIndex = 0;
  } else if (control.getAttribute("role") === "status") {
    control.removeAttribute("role");
    if (writesSeat) control.removeAttribute("tabindex");
  }
  let glyphNode = control.querySelector(
    ":scope > :is(.lf-margin-element-glyph, .lf-margin-element-icon)",
  );
  let spaceNode = control.querySelector(":scope > .lf-margin-element-space");
  let labelNode = control.querySelector(":scope > .lf-margin-element-label");
  if (icon) {
    if (!(glyphNode instanceof SVGSVGElement) || glyphNode.dataset.lfIcon !== icon)
      glyphNode = iconElement(icon);
  } else {
    if (!(glyphNode instanceof HTMLSpanElement))
      glyphNode = document.createElement("span");
    if (glyphNode.className !== "lf-margin-element-glyph")
      glyphNode.className = "lf-margin-element-glyph";
    if (glyphNode.hasAttribute("data-lf-icon"))
      glyphNode.removeAttribute("data-lf-icon");
    if (glyphNode.textContent !== glyph) glyphNode.textContent = glyph;
  }
  if (!spaceNode) spaceNode = document.createElement("span");
  if (!labelNode) labelNode = document.createElement("span");
  if (glyphNode.getAttribute("aria-hidden") !== "true")
    glyphNode.setAttribute("aria-hidden", "true");
  if (spaceNode.className !== "lf-margin-element-space")
    spaceNode.className = "lf-margin-element-space";
  if (spaceNode.getAttribute("aria-hidden") !== "true")
    spaceNode.setAttribute("aria-hidden", "true");
  if (spaceNode.textContent !== " ") spaceNode.textContent = " ";
  if (labelNode.className !== "lf-margin-element-label")
    labelNode.className = "lf-margin-element-label";
  if (labelNode.getAttribute("aria-hidden") !== "true")
    labelNode.setAttribute("aria-hidden", "true");
  const visibleLabel = visibleMarginElementLabel(record);
  let labelWord = labelNode.querySelector(":scope > .lf-margin-element-label-word");
  let contextNode = labelNode.querySelector(":scope > .lf-margin-element-context");
  if (!labelWord) labelWord = document.createElement("span");
  if (labelWord.className !== "lf-margin-element-label-word")
    labelWord.className = "lf-margin-element-label-word";
  if (labelWord.textContent !== visibleLabel) labelWord.textContent = visibleLabel;
  if (record.context && !contextNode) contextNode = document.createElement("span");
  if (!record.context) {
    contextNode?.remove();
    contextNode = null;
  }
  if (contextNode) {
    if (contextNode.className !== "lf-margin-element-context")
      contextNode.className = "lf-margin-element-context";
    if (contextNode.textContent !== record.context)
      contextNode.textContent = record.context;
  }
  const labelParts = [labelWord, ...(contextNode ? [contextNode] : [])];
  if (
    labelNode.childNodes.length !== labelParts.length ||
    labelParts.some((node, index) => labelNode.childNodes[index] !== node)
  )
    labelNode.replaceChildren(...labelParts);
  // A reading with several members adds one retained count badge. It remains part of
  // the same hit target, so a heartbeat between pointerdown and pointerup must preserve
  // it along with the icon and label.
  const countNode = control.querySelector(":scope > .lf-margin-count");
  const anatomy = [glyphNode, spaceNode, labelNode, ...(countNode ? [countNode] : [])];
  if (
    control.childNodes.length !== anatomy.length ||
    anatomy.some((node, index) => control.childNodes[index] !== node)
  )
    control.replaceChildren(...anatomy);
  if (!control.hasAttribute("aria-label"))
    control.setAttribute("aria-label", record.label);
  return control;
}

function syncMarginElementCount(control, count) {
  let badge = control.querySelector(":scope > .lf-margin-count");
  if (count <= 1) {
    badge?.remove();
    return;
  }
  if (!badge) badge = document.createElement("span");
  if (badge.className !== "lf-margin-count") badge.className = "lf-margin-count";
  if (badge.getAttribute("aria-hidden") !== "true")
    badge.setAttribute("aria-hidden", "true");
  if (badge.textContent !== String(count)) badge.textContent = count;
  if (control.lastChild !== badge) control.append(badge);
}

export function marginElementState(control, state) {
  if (!(control instanceof Element) || !control.classList.contains("lf-margin-element"))
    throw new TypeError("A margin element state needs a margin element");
  if (!MARGIN_ELEMENT_STATES.has(state))
    throw new TypeError(`Unknown margin element state: ${state}`);
  marginElementRecord(control).state = state;
  keeps(control, "data-lf-state", state);
  if (state === "busy") keeps(control, "aria-busy", "true");
  else control.removeAttribute("aria-busy");
  return control;
}

export function registerMarginContribution({
  key,
  target,
  controls,
  items = () => [],
  subject = null,
  state = "idle",
  side = "before",
  claim = true,
  reserve = 0,
}) {
  if (!String(key ?? "").trim())
    throw new TypeError("A margin contribution needs a key");
  if (!new Set(["before", "after"]).has(side))
    throw new TypeError(`Unknown margin contribution side: ${side}`);
  if (typeof state !== "string" && typeof state !== "function")
    throw new TypeError("A margin contribution's state must be a string or function");
  if (subject != null && typeof subject !== "string" && typeof subject !== "function")
    throw new TypeError("A margin contribution's subject must be a string or function");
  if (typeof state === "string" && !MARGIN_ELEMENT_STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  if (controls instanceof Element) controls.classList.add("lf-margin-contribution");
  const offered = {
    key: String(key),
    target,
    controls,
    items,
    subject,
    state,
    side,
    claim,
    reserve,
  };
  validateMarginElements(offered);
  marginContributions.add(offered);
  changedContributions();
  return {
    update({ immediate = false } = {}) {
      validateMarginElements(offered);
      changedContributions();
      if (immediate) layoutMarginRows();
    },
    unregister() {
      if (!marginContributions.delete(offered)) return;
      // Let the projection detach a focused contribution while its focus-settling
      // guard is active. Removing it first can synchronously fire focusout, whose
      // fold render moves that same node before Element.remove completes.
      changedContributions();
      for (const control of marginElements(controls)) {
        const record = marginElementRecord(control);
        if (record.owner === offered.key) delete record.owner;
        control.removeAttribute("data-lf-margin-element-owner");
      }
      controls?.remove();
    },
  };
}

const trimmed = (value, limit = 110) => {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
};

const humanized = (value) =>
  String(value ?? "")
    .replace(/[-_]+/g, " ")
    .trim();

function targetPath(target) {
  const root = target.getRootNode();
  // IDs and sibling paths are scoped to a shadow root. Prefix them with the host's
  // own stable path so two instances of the same shadow template stay distinct,
  // while a live-version replacement at the same authored coordinate can still
  // retain its marker and preview focus.
  const prefix = root instanceof ShadowRoot ? `${targetPath(root.host)}/shadow/` : "";
  if (target.id) return `${prefix}id:${target.id}`;
  const steps = [];
  for (let node = target; node;) {
    const parent =
      node.parentElement ??
      (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
    if (!parent) break;
    const siblings = [...parent.children].filter(
      (candidate) =>
        !candidate.classList.contains("lf-ui") &&
        !candidate.hasAttribute("data-lf-gen"),
    );
    steps.push(`${node.localName}:${siblings.indexOf(node)}`);
    if (node.localName === "main" || parent instanceof ShadowRoot) break;
    node = parent;
  }
  return `${prefix}path:${steps.reverse().join("/")}`;
}

function comesBefore(left, right) {
  if (left === right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  // compareDocumentPosition calls nodes in separate shadow trees disconnected and
  // leaves their order implementation-specific. Build each composed ancestry instead:
  // the first divergent nodes share a document or shadow root and therefore have a
  // stable order. Keeping every inner step also distinguishes a target in an outer
  // tree from a later target inside one of its nested shadow hosts.
  const ancestry = (target) => {
    const chain = [];
    for (let node = target; node;) {
      chain.push(node);
      node =
        node.assignedSlot ?? node.parentElement ?? node.getRootNode()?.host ?? null;
    }
    return chain.reverse();
  };
  const leftChain = ancestry(left);
  const rightChain = ancestry(right);
  let index = 0;
  while (
    index < leftChain.length &&
    index < rightChain.length &&
    leftChain[index] === rightChain[index]
  )
    index += 1;
  if (index === leftChain.length || index === rightChain.length)
    return leftChain.length - rightChain.length;
  return leftChain[index].compareDocumentPosition(rightChain[index]) &
    Node.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

const acknowledgments = () => runtime.activity?.interactions ?? [];
export const renderMargin = clocked(document.body, renderNow);
// The margin element the reader is standing on, or null off one: the press row's words read it.
const focusedMarginElementBehavior = () =>
  focused()?.[MARGIN_ELEMENT_RECORD]?.behavior ?? null;

const nav = el("nav", "lf-ui lf-living-margin");
// Every live page can gain an anchored comment, including one made entirely of prose.
reserveRail();
nav.dataset.lfGen = "1";
nav.setAttribute("aria-label", "Page map");
const toolbar = el("div", "lf-margin-toolbar");
toolbar.setAttribute("role", "toolbar");
toolbar.setAttribute(
  "aria-label",
  "Changes, threadList, asks, delivery status, and activity",
);
nav.append(toolbar);

function measureMargin(
  columnRect = document.querySelector("main")?.getBoundingClientRect(),
) {
  const main = document.querySelector("main");
  if (!main || !columnRect) return;
  const at = documentPoint(columnRect.left, columnRect.top);
  const height = main.scrollHeight;
  return () => {
    const dimensions = {
      left: `${at.left}px`,
      top: `${at.top}px`,
      width: `${columnRect.width}px`,
      height: `${height}px`,
    };
    for (const [property, value] of Object.entries(dimensions))
      if (nav.style[property] !== value) nav.style[property] = value;
  };
}

export const mapButton = el("button", "lf-btn lf-page-map-toggle", "Map");
mapButton.type = "button";
mapButton.hidden = true;
mapButton.title = "Open the page map";
function changePosture() {
  const marginHeld =
    toolbar.contains(document.activeElement) ||
    preview.contains(document.activeElement);
  if (commentsEdge.over.matches && preview.matches(":popover-open")) closePreview();
  if (commentsEdge.over.matches && marginHeld)
    requestAnimationFrame(() => focusMapControl());
  renderMargin();
}
// One seat in the banner's one order, taken once: the map stands with the page's other
// destinations, just before the version chooser. It used to take the far side of
// approval under the compact query and be re-placed on every crossing of it, which was
// the same address at two different places on one row — and, because a blanket answer
// that had arrived in between claims that same seat, the seat it landed in depended on
// which way the reader had last crossed 900px. Placed at build, before any of them.

const preview = el("aside", "lf-ui lf-margin-preview");
export { preview as marginPreview };
preview.id = "lf-margin-preview";
preview.setAttribute("popover", "auto");
preview.setAttribute("role", "dialog");
const previewHead = el("div", "lf-margin-preview-head");
export { previewHead as marginPreviewHead };
const previewTitle = el("strong", "lf-margin-preview-title");
const previewClose = el(
  "button",
  "lf-btn lf-icon-action lf-close-action lf-margin-preview-close",
);
previewClose.append(iconElement("cross", "lf-action-icon"));
previewClose.type = "button";
previewClose.setAttribute("aria-label", "Close thread");
previewClose.title = "Close thread (Esc)";
previewHead.append(previewTitle, previewClose);
const previewList = el("div", "lf-margin-preview-list");
preview.append(previewHead, previewList);
let threadTransitionEpoch = 0;
let threadTransitionMotions = [];

// The submitted composer and a developer replay describe the same starting box; the
// transition owns that geometry contract instead of making either caller duplicate it.
export function threadTransitionOrigin(element, text) {
  const box = element.getBoundingClientRect();
  const style = getComputedStyle(element);
  return {
    left: box.left,
    top: box.top,
    width: box.width,
    height: box.height,
    backgroundColor: style.backgroundColor,
    borderColor: style.borderColor,
    borderRadius: style.borderRadius,
    boxShadow: style.boxShadow,
    text,
  };
}

function clearThreadTransition() {
  threadTransitionEpoch += 1;
  for (const played of threadTransitionMotions) played.cancel();
  threadTransitionMotions = [];
  chromeRoot.querySelector(".lf-thread-transition")?.remove();
  preview.style.removeProperty("opacity");
}

// A comment written beside the page becomes this larger inline thread. Carry its
// submitted field to the card rather than replacing one rectangle with another in a
// frame; the real card fades through the carried shell, so its contents never stretch.
function transitionThread(origin) {
  if (!origin?.width || !origin?.height) return;
  const target = preview.getBoundingClientRect();
  if (!target.width || !target.height) return;

  const ghost = el("div", "lf-ui lf-response-control lf-thread-transition");
  const ghostText = el("span", "lf-thread-transition-text", origin.text);
  ghost.append(ghostText);
  ghost.setAttribute("aria-hidden", "true");
  Object.assign(ghost.style, {
    left: `${origin.left}px`,
    top: `${origin.top}px`,
    width: `${origin.width}px`,
    height: `${origin.height}px`,
    backgroundColor: origin.backgroundColor,
    borderColor: origin.borderColor,
    borderRadius: origin.borderRadius,
    boxShadow: origin.boxShadow,
  });
  chromeRoot.append(ghost);

  const end = getComputedStyle(preview);
  const duration = 280;
  const carried = motion(
    ghost,
    [
      { opacity: 1 },
      { opacity: 1, offset: 0.42 },
      {
        left: `${target.left}px`,
        top: `${target.top}px`,
        width: `${target.width}px`,
        height: `${target.height}px`,
        borderRadius: end.borderRadius,
        backgroundColor: end.backgroundColor,
        borderColor: end.borderColor,
        boxShadow: end.boxShadow,
        opacity: 0,
      },
    ],
    duration,
  );
  const revealed = motion(
    preview,
    [
      { opacity: 0, transform: "translateY(2px)" },
      {
        opacity: 0,
        transform: "translateY(2px)",
        offset: 0.42,
      },
      { opacity: 1, transform: "none" },
    ],
    duration,
  );
  const words = motion(
    ghostText,
    [{ opacity: 1 }, { opacity: 0, offset: 0.42 }, { opacity: 0 }],
    duration,
  );
  threadTransitionMotions = [carried, revealed, words].filter(Boolean);
  if (carried)
    carried.finished.then(
      () => ghost.remove(),
      () => ghost.remove(),
    );
  else ghost.remove();
  // `motion` releases its filled frame after this reaction. The card's ordinary
  // styles already are the final frame, so no separate cleanup can flash it back.
  revealed?.finished.catch(() => {});
}

function scheduleThreadTransition(origin, entry) {
  clearThreadTransition();
  const epoch = threadTransitionEpoch;
  // Margin packing finishes on the next frame. Keep the real card transparent until
  // then, so the carried shell aims at the marker's settled position without flashing
  // the card at its provisional one.
  preview.style.opacity = "0";
  requestAnimationFrame(() => {
    if (epoch !== threadTransitionEpoch) return;
    preview.style.removeProperty("opacity");
    if (previewEntry?.key !== entry.key || !preview.matches(":popover-open")) return;
    placeThreadPreview();
    transitionThread(origin);
  });
}

const sheet = document.createElement("dialog");
sheet.className = "lf-ui lf-page-map-sheet";
sheet.setAttribute("aria-label", "Page map");
sheet.setAttribute("aria-modal", "true");
const sheetHead = el("div", "lf-page-map-head");
sheetHead.append(el("strong", "", "Page map"));
const sheetClose = el("button", "lf-btn", "Close");
sheetClose.type = "button";
sheetClose.onclick = () => sheet.close();
sheetHead.append(sheetClose);
const sheetSearch = el("input", "lf-page-map-search");
sheetSearch.type = "search";
sheetSearch.name = "page-map-search";
sheetSearch.placeholder = "Find an action, status, or location";
sheetSearch.setAttribute(
  "aria-label",
  "Find an action, status, or location in Page map",
);
const sheetList = el("div", "lf-page-map-list");
const sheetEmpty = el(
  "p",
  "lf-page-map-empty",
  "No matching actions, statuses, or locations",
);
sheetEmpty.hidden = true;
sheetEmpty.setAttribute("role", "status");
sheet.append(sheetHead, sheetSearch, sheetList, sheetEmpty);

const rows = new Map();
const moreMarginElements = new Map();
const spillMarginElements = new Map();
const optionGroups = new Map();
const controlProxies = new WeakMap();
const readingMarginElements = new Map();
const hosts = new Map();
const inlineHosts = new Map();
let optionsOrdinal = 0;
let pageMapEntries = [];
let previewEntry = null;
let previewMarginElement = null;
let transferThreadFocus = false;
let previewShowing = false;
let pinnedKey = null;
let forcedInlineKey = null;
let forcedInlineOptionsKey = null;
let expandedOptionsKey = null;
// An explicit mode can focus one contribution inside the target's existing cluster.
// The rail then shows that owner's complete control set without spending margin elements on
// standing readings or unrelated actions; Page map still reads the whole entry.
let expandedOptionsOwner = null;
let hoveredHost = null;
let settlingOptionsFocus = false;
let suppressingOptionsArrival = false;
let highlighted = null;
let rovingFrame = 0;
let sheetCloseOwnsFocus = false;
let sheetFrom = null;
let sheetTarget = null;
const controlsOf = (offered) => marginElements(offered.controls);
const offerReadings = (offered) => {
  const items = typeof offered.items === "function" ? offered.items() : offered.items;
  return items ?? [];
};
const offerState = (offered) => {
  const state = typeof offered.state === "function" ? offered.state() : offered.state;
  if (!MARGIN_ELEMENT_STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  return state;
};
// One target has one lifecycle reading. Failure outranks work in flight, which
// outranks an open interaction; the ordinary idle state never forces peers open.
// Generated acknowledgment readings join through the same state axis rather than a
// second engagement flag.
const entryState = (entry) => {
  const states = [
    ...entry.offers.map(offerState),
    ...entry.items.map(
      (item) => item.state ?? (item.acknowledgmentFace ? "busy" : "idle"),
    ),
  ];
  return (
    states.sort(
      (left, right) => STATE_PRIORITY.get(left) - STATE_PRIORITY.get(right),
    )[0] ?? "idle"
  );
};
// Every state but idle keeps the cluster open, so the reading is the absence of idle
// rather than a second list of states beside the grammar's.
const entryEngaged = (entry) => entryState(entry) !== "idle";
// A modal or contextual thread surface temporarily owns focus without ending the
// document interaction beneath it. Preserve that context so its commands remain
// true and its owning margin element can receive focus when the surface closes.
const inRetainedContext = (node) =>
  node instanceof Element &&
  (Boolean(node.closest("dialog[open]")) ||
    preview.contains(node) ||
    (panelIsOpen() && panel.contains(node)));
const compareOffers = (left, right) => {
  const state =
    STATE_PRIORITY.get(offerState(left)) - STATE_PRIORITY.get(offerState(right));
  if (state) return state;
  return left.key.localeCompare(right.key);
};
const standingAfterOffers = (entry) =>
  entry.offers
    .filter((offered) => offered.side === "after" && offerReadings(offered).length > 0)
    .sort(compareOffers);
const directOffers = (entry) => [
  ...entry.offers.filter((offered) => offered.side === "before").sort(compareOffers),
  ...standingAfterOffers(entry),
];
const compareControlRecords = (left, right) => {
  const state =
    STATE_PRIORITY.get(offerState(left.offered)) -
    STATE_PRIORITY.get(offerState(right.offered));
  if (state) return state;
  const role =
    ROLE_PRIORITY.get(marginElementRecord(left.control).role) -
    ROLE_PRIORITY.get(marginElementRecord(right.control).role);
  if (role) return role;
  const offer = left.offered.key.localeCompare(right.offered.key);
  if (offer) return offer;
  return marginElementRecord(left.control).key.localeCompare(
    marginElementRecord(right.control).key,
  );
};
const directControlRecords = (entry) =>
  directOffers(entry)
    .flatMap((offered) => controlsOf(offered).map((control) => ({ control, offered })))
    .sort(compareControlRecords);
const directControls = (entry) =>
  directControlRecords(entry).map(({ control }) => control);
const controlsShownByOwner = (controls) => {
  // The margin hides non-primary controls with `display: none`, so ask how this
  // batch paints while exempt from that rule. Write every exemption before the first
  // style read: alternating an attribute write and getComputedStyle would recalculate
  // the whole page once per margin element. Contributor-owned `display` and `visibility`
  // still apply — including the retired half of a settled pair.
  const wasPrimary = controls.map((control) =>
    control.hasAttribute("data-lf-margin-element-primary"),
  );
  const wasOverflow = controls.map((control) =>
    control.hasAttribute("data-lf-margin-element-overflow"),
  );
  for (const control of controls) {
    control.toggleAttribute("data-lf-margin-element-primary", true);
    control.removeAttribute("data-lf-margin-element-overflow");
  }
  let shown;
  try {
    shown = controls.filter((control) => {
      const style = getComputedStyle(control);
      return (
        !control.hidden && style.display !== "none" && style.visibility !== "hidden"
      );
    });
  } finally {
    controls.forEach((control, index) => {
      control.toggleAttribute("data-lf-margin-element-primary", wasPrimary[index]);
      control.toggleAttribute("data-lf-margin-element-overflow", wasOverflow[index]);
    });
  }
  return shown;
};
function choosePrimary(entry) {
  return (
    directControlRecords(entry).find(({ control }) => entry.shownControls.has(control))
      ?.control ?? null
  );
}
function syncControlRoles(entry) {
  const primary = choosePrimary(entry);
  for (const control of directControls(entry))
    control.toggleAttribute("data-lf-margin-element-primary", control === primary);
  return primary;
}
const markerItems = (entry) => entry.items.filter((item) => item.marker !== false);
const entryHasMarginHost = (entry) =>
  entry.offers.length > 0 || markerItems(entry).length > 0;
const readingKey = (entry, choice) => `${entry.key}:${choice.key}`;
const readingChoices = (entry) => {
  const threadList = [];
  const choices = [];
  for (const item of markerItems(entry)) {
    if (item.kind === "comment") threadList.push(item);
    else
      choices.push({
        key: item.id,
        kind: item.kind,
        items: [item],
        text: item.text,
      });
  }
  if (threadList.length)
    choices.push({
      // One target owns one thread margin element. Membership changes repaint its badge and
      // card without replacing the control that owns an open conversation.
      key: "threadList",
      kind: "comment",
      items: threadList,
      text: threadList[0].text,
    });
  return choices.sort(
    (left, right) =>
      KINDS[left.kind].priority - KINDS[right.kind].priority ||
      left.key.localeCompare(right.key),
  );
};
const primaryReading = (entry) => readingChoices(entry)[0] ?? null;
const threadReading = (entry) =>
  readingChoices(entry).find((choice) => choice.kind === "comment") ?? null;
const secondaryReadings = (entry, primaryControl) =>
  readingChoices(entry).slice(primaryControl ? 0 : 1);

function threadMarginElement(entry) {
  const marker = rows.get(entry.key);
  if (marker && !marker.hidden && primaryReading(entry)?.kind === "comment")
    return marker;
  const choice = threadReading(entry);
  return choice ? (readingMarginElements.get(readingKey(entry, choice)) ?? null) : null;
}
const secondaryControls = (entry, primary) =>
  directControls(entry).filter(
    (control) => control !== primary && entry.shownControls.has(control),
  );
const afterOffers = (entry, { claimedOnly = false } = {}) =>
  entry.offers
    .filter(
      (offered) =>
        offered.side === "after" &&
        offerReadings(offered).length === 0 &&
        offered.controls &&
        (!claimedOnly || offered.claim),
    )
    .sort(compareOffers);
const secondaryCount = (entry, primary, { claimedOnly = false } = {}) => {
  const generated = secondaryReadings(entry, primary).length;
  const contributed = secondaryControls(entry, primary).length;
  const after = afterOffers(entry, { claimedOnly }).reduce(
    (count, offered) =>
      count +
      controlsOf(offered).filter((control) => entry.shownControls.has(control)).length,
    0,
  );
  if (claimedOnly && !entry.offers.some((offered) => offered.claim)) return generated;
  return generated + contributed + after;
};
// One peer is not overflow. It costs the same second circle as `…`, but the peer says
// what it does and is immediately usable. Ellipsis earns its place only from the third
// margin element onward.
const optionsOffered = (entry, primary, options = {}) =>
  secondaryCount(entry, primary, options) > RESTING_MARGIN_ELEMENT_BUDGET - 1;

function markerFace(entry) {
  const kinds = kindsIn(entry, { markerOnly: true });
  const choice = primaryReading(entry);
  const face = readingFace(choice);
  const faceCount = choice?.items.length ?? 0;
  return {
    kinds,
    face,
    label: faceCount > 1 ? `${face.label}s` : face.label,
    // The badge describes this margin element's result. Other readings live behind `…`
    // and must not make a thread margin element appear to open more threadList than it does.
    count: faceCount,
  };
}

function readingFace(choice) {
  return (
    (choice?.items.length === 1 && choice.items[0].acknowledgmentFace) ||
    KINDS[choice?.kind] ||
    KINDS.action
  );
}

function readingState(choice) {
  return (
    (choice?.items ?? [])
      .map((item) => item.state ?? item.acknowledgmentFace?.state ?? "idle")
      .sort((left, right) => STATE_PRIORITY.get(left) - STATE_PRIORITY.get(right))[0] ??
    "idle"
  );
}

const readingBehavior = (face) => (face.indication ? "status" : "disclosure");

function readingContext(choice) {
  if (choice?.items.length !== 1) return null;
  return choice.items[0].context ?? null;
}

// A reading wears two promises over its life — a margin element while there is something to
// open, a status once the move is made — and only one element may carry both, or the
// seat moves under a reader standing in it. A <button> cannot stop being one, so the
// seat is a span and `marginElement` writes whichever promise the reading now makes.
// What the platform then does not supply is the press, which the margin's own scope
// declares (margin.press) rather than a listener here: a key the register does not
// hold is a key no surface can promise.
const readingControl = (className) => offer("span", className);

// The one writer over a reading's disclosure relation, settling `aria-controls` and
// `aria-expanded` together because a control that says it opens something has to say
// whether it is open. Two shapes reach it. A thread margin element opens the local card while the
// panel is closed and the matching panel card while it is open. Any other reading is
// asked what it discloses, and a single item
// that answers has named the node and said which way it stands — the Change reading's
// earlier words, folded into the block itself. An item answering nothing promises
// nothing, which is what leaves a Change margin element over a block the comparison holds no
// earlier reading for the plain travel it always was.
function syncReadingRelation(control, choice) {
  if (choice?.kind === "comment") {
    const opensInline = !panelIsOpen();
    keeps(control, "aria-controls", opensInline ? preview.id : panel.id);
    if (opensInline) keeps(control, "aria-expanded", previewMarginElement === control);
    else control.removeAttribute("aria-expanded");
    return;
  }
  const disclosed = choice?.items.length === 1 ? choice.items[0].discloses?.() : null;
  if (!disclosed) {
    control.removeAttribute("aria-controls");
    control.removeAttribute("aria-expanded");
    return;
  }
  keeps(control, "aria-controls", disclosed.id);
  keeps(control, "aria-expanded", disclosed.open);
}
let postureFrame = 0;
let previewPositionFrame = 0;
let previewPositionRemeasure = false;
let previewPositionDismissDetached = false;
let previewPlacementMetrics = null;
let previewReferenceSeen = false;
function schedulePostureRender() {
  if (postureFrame) return;
  postureFrame = requestAnimationFrame(() => {
    postureFrame = 0;
    renderMargin();
  });
}
const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(value, maximum));
const overlaps = (one, other, gap = 0) =>
  one.left < other.right + gap &&
  other.left < one.right + gap &&
  one.top < other.bottom + gap &&
  other.top < one.bottom + gap;

function keepThreadPreviewFocusVisible() {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement) || !preview.contains(active)) return;
  const card = preview.getBoundingClientRect();
  const activeBox = active.getBoundingClientRect();
  const inset = 12;
  if (activeBox.bottom > card.bottom - inset)
    preview.scrollTop += activeBox.bottom - card.bottom + inset;
  else if (activeBox.top < card.top + inset)
    preview.scrollTop -= card.top + inset - activeBox.top;
}

function threadSidePlacement(left, width, height, target, firstTop, lastBottom) {
  const gap = 8;
  const totalHeight = lastBottom - firstTop;
  const cardHeight = Math.min(height, totalHeight);
  const lastTop = lastBottom - cardHeight;
  const desired = clamp(
    (target.top + target.bottom - cardHeight) / 2,
    firstTop,
    lastTop,
  );
  const candidate = {
    left,
    right: left + width,
    top: desired,
    bottom: desired + cardHeight,
  };
  if (!overlaps(candidate, target, gap))
    return { top: desired, maxHeight: totalHeight };

  const belowTop = Math.max(firstTop, Math.min(target.bottom + gap, lastBottom));
  const aboveBottom = Math.max(firstTop, Math.min(target.top - gap, lastBottom));
  const belowRoom = Math.max(0, lastBottom - belowTop);
  const aboveRoom = Math.max(0, aboveBottom - firstTop);
  const below = height <= belowRoom || (height > aboveRoom && belowRoom >= aboveRoom);
  const room = below ? belowRoom : aboveRoom;
  if (!room) return null;
  const placedHeight = Math.min(height, room);
  return {
    top: below ? belowTop : aboveBottom - placedHeight,
    maxHeight: room,
  };
}

function placeThreadPreview({ remeasure = true, dismissDetached = false } = {}) {
  if (
    !preview.matches(":popover-open") ||
    !preview.hasAttribute("data-lf-thread") ||
    !previewMarginElement?.isConnected
  )
    return;
  const controls =
    previewMarginElement.closest("[data-lf-margin-for]") ?? previewMarginElement;
  const target = controls.getBoundingClientRect();
  const readingRegion = readingRegionFor(previewEntry?.target);
  const regionBounds = readingRegion && shownRegionBounds(readingRegion);
  const main = readingRegion
    ? null
    : document.querySelector("main")?.getBoundingClientRect();
  const bannerBottom =
    document.querySelector(".lf-banner")?.getBoundingClientRect().bottom ?? 0;
  const gap = 8;
  const firstLeft = regionBounds?.left ?? 0;
  const lastRight = regionBounds?.right ?? innerWidth;
  const firstTop = Math.max(regionBounds?.top ?? 0, bannerBottom) + gap;
  const lastBottom = (regionBounds?.bottom ?? innerHeight) - gap;
  const totalHeight = Math.max(0, lastBottom - firstTop);
  const referenceVisible = target.bottom > firstTop && target.top < lastBottom;
  if (referenceVisible) {
    previewReferenceSeen = true;
  } else if (previewReferenceSeen && dismissDetached) {
    closePreview();
    return;
  }
  if (remeasure || !previewPlacementMetrics) {
    const style = getComputedStyle(preview);
    previewPlacementMetrics = {
      preferredWidth: Math.min(
        parseFloat(style.getPropertyValue("--thread-card")),
        lastRight - firstLeft - 2 * gap,
      ),
      minimumWidth: parseFloat(style.getPropertyValue("--thread-card-min")),
      borderHeight:
        parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth),
      heights: new Map(),
    };
  }
  const metrics = previewPlacementMetrics;
  const naturalHeight = (width) => {
    const key = width.toFixed(2);
    if (!metrics.heights.has(key)) {
      preview.style.setProperty("--lf-thread-width", `${width}px`);
      preview.style.setProperty("--lf-thread-max-height", `${totalHeight}px`);
      metrics.heights.set(key, preview.scrollHeight + metrics.borderHeight);
    }
    return metrics.heights.get(key);
  };
  const sideCandidates = main
    ? [
        {
          name: "right",
          width: Math.min(metrics.preferredWidth, innerWidth - main.right - 2 * gap),
          get left() {
            return innerWidth - gap - this.width;
          },
        },
        {
          name: "left",
          left: gap,
          width: Math.min(metrics.preferredWidth, main.left - 2 * gap),
        },
      ]
    : [];
  for (const side of sideCandidates) {
    if (side.width < metrics.minimumWidth) continue;
    const height = naturalHeight(side.width);
    const placement = threadSidePlacement(
      side.left,
      side.width,
      height,
      target,
      firstTop,
      lastBottom,
    );
    if (!placement) continue;
    preview.dataset.lfThreadPlacement = side.name;
    preview.style.setProperty("--lf-thread-width", `${side.width}px`);
    preview.style.setProperty("--lf-thread-max-height", `${placement.maxHeight}px`);
    preview.style.setProperty("--lf-thread-left", `${side.left}px`);
    preview.style.setProperty("--lf-thread-top", `${placement.top}px`);
    if (remeasure) keepThreadPreviewFocusVisible();
    return;
  }

  // Both margins are unavailable. Preserve the full reading measure over the document,
  // preferring the room below the selected cluster, then above, then the larger side as
  // a scrolling viewport. The cluster itself is never part of the area the card spends.
  const width = metrics.preferredWidth;
  const overlayHeight = naturalHeight(width);
  const belowTop = Math.max(firstTop, Math.min(target.bottom + gap, lastBottom));
  const aboveBottom = Math.max(firstTop, Math.min(target.top - gap, lastBottom));
  const belowRoom = Math.max(0, lastBottom - belowTop);
  const aboveRoom = Math.max(0, aboveBottom - firstTop);
  const below =
    overlayHeight <= belowRoom || (overlayHeight > aboveRoom && belowRoom >= aboveRoom);
  const room = below ? belowRoom : aboveRoom;
  const cardHeight = Math.min(overlayHeight, room);
  const lastLeft = lastRight - width - gap;
  const left = clamp(target.right - width, firstLeft + gap, lastLeft);
  const top = below ? belowTop : aboveBottom - cardHeight;
  preview.dataset.lfThreadPlacement = below ? "below" : "above";
  preview.style.setProperty("--lf-thread-width", `${width}px`);
  preview.style.setProperty("--lf-thread-max-height", `${room}px`);
  preview.style.setProperty("--lf-thread-left", `${left}px`);
  preview.style.setProperty("--lf-thread-top", `${top}px`);
  if (remeasure) keepThreadPreviewFocusVisible();
}
function scheduleThreadPreviewPosition(remeasure = false, dismissDetached = false) {
  if (remeasure) {
    previewPositionRemeasure = true;
    previewPositionDismissDetached = false;
  } else previewPositionDismissDetached ||= dismissDetached;
  if (previewPositionFrame) return;
  previewPositionFrame = requestAnimationFrame(() => {
    previewPositionFrame = 0;
    const measure = previewPositionRemeasure;
    const dismiss = previewPositionDismissDetached;
    previewPositionRemeasure = false;
    previewPositionDismissDetached = false;
    placeThreadPreview({ remeasure: measure, dismissDetached: dismiss });
  });
}
// A viewport posture change can replace the focused full conversation with its
// compact action. Reconcile after resize delivery so the browser can finish its
// own focus and popover bookkeeping before that node changes shape. Panel and tray
// changes notify this runtime directly through their owners.

// A margin cluster is hoisted away from the page target it belongs to, so ancestry
// cannot answer what a press on one of its controls is about. Keep that relationship
// behind the owner that performs the hoist. Design mode uses it to turn the press into
// a comment on the target and the named control instead of letting the action fire.
export function marginTargetAt(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  return closestAcross(at, "[data-lf-margin-for]")?.lfTarget ?? null;
}

function groupFor(groups, target) {
  let group = groups.get(target);
  if (!group) {
    const key = targetPath(target);
    const word = itemWord(target);
    group = {
      key,
      target,
      word,
      subject: null,
      title: null,
      items: [],
      offers: [],
    };
    groups.set(target, group);
  }
  return group;
}

function add(groups, target, item) {
  if (!target?.isConnected || inChrome(target)) return;
  const group = groupFor(groups, target);
  group.items.push(item);
}

function visibleAcknowledgments() {
  return acknowledgments().filter(
    (projected) => projected.revision <= runtime.currentRevision,
  );
}

function acknowledgmentFace(receipt) {
  const age = ago(receipt.ts);
  if (receipt.phase === "active") {
    return {
      kind: "activity",
      text: ["Active", receipt.detail, receipt.quiet ? "quiet" : null]
        .filter(Boolean)
        .join(" · "),
      context: [age && `Checked in ${age}`, receipt.detail].filter(Boolean).join(" · "),
    };
  }
  if (receipt.phase === "queued")
    return { kind: "pickup", text: "Queued", context: age };
  if (receipt.phase === "picked_up")
    return {
      kind: receipt.dropped ? "waiting" : "pickup",
      text: receipt.dropped ? "Picked up · turn ended" : "Picked up",
      context: age,
    };
  if (receipt.phase === "waiting")
    return {
      kind: "waiting",
      text: "Waiting for pickup",
      context: age && `Sent ${age}`,
    };
  return { kind: "sent", text: "Sent", context: age };
}

const marginThreadItem = (thread) => (thread ? `comment:${threadKey(thread)}` : null);

function collectEntries() {
  const groups = new Map();
  const receiptByCoordinate = new Map();
  for (const receipt of visibleAcknowledgments()) {
    receiptByCoordinate.set(JSON.stringify(receipt.coordinate), receipt);
  }
  for (const thread of threadList()) {
    if (thread.resolved || !thread.anchor || claimed(thread.root.id)) continue;
    const id = thread.root.id;
    add(groups, placedAt(id)?.element, {
      kind: "comment",
      // One row for one conversation, across the log answering for it. A thread the
      // reader just opened is known by its attempt until the log names it, and a row
      // whose identity changed there would be rebuilt — taking with it the reply box
      // the send had just put them in.
      id: marginThreadItem(thread),
      text: trimmed(thread.root.text || anchorLabel(thread.anchor, thread.root.about)),
      thread,
      activate: () => showThread(id),
    });
  }

  const asks = openAsks();
  for (const ask of asks) {
    const id = ask.id;
    add(groups, ask, {
      kind: "ask",
      id: `ask:${id}`,
      text: trimmed(`${itemWord(ask)} · ${itemSays(ask) || id}`),
      activate: () => {
        const standing = openAsks();
        const next = standing.find((candidate) => candidate.id === id);
        if (next) goToAsk(next, standing);
      },
    });
  }

  const projection = stateProjection();
  for (const origin of stateOrigins(projection)) {
    const target = elementById(origin.unit);
    if (!target) continue;
    const face = KINDS[origin.origin];
    add(groups, target, {
      kind: origin.origin,
      id: `state-origin:${origin.origin}:${origin.unit}`,
      // Durable provenance belongs in Page map rather than another target margin element:
      // it remains explicit without changing the page's action density or geometry.
      marker: false,
      text: trimmed(
        [face.label, itemWord(target), itemSays(target)].filter(Boolean).join(" · "),
      ),
      activate: () => revealTarget(target, `${face.label}: ${itemSays(target)}`),
    });
  }
  const claimActivity = new Map(
    acknowledgments()
      .filter((item) => item.phase === "active")
      .map((item) => [`${item.target.kind}:${item.target.id}`, item]),
  );
  const activityAlreadyShown = new Set();
  for (const [coordinate, entry] of projection.desired) {
    if (entry.e.kind !== "action") continue;
    const target = elementById(entry.unit) ?? elementById(entry.e.widget);
    if (!target) continue;
    const receipt = receiptByCoordinate.get(coordinate);
    if (!receipt) continue;
    const account = [itemWord(target), humanized(entry.e.action), itemSays(target)]
      .filter(Boolean)
      .join(" · ");
    const face = acknowledgmentFace(receipt);
    if (face.kind === "activity")
      activityAlreadyShown.add(`widget:${receipt.target.id}`);
    add(groups, target, {
      kind: face.kind,
      id: `acknowledgment:${receipt.id}`,
      text: trimmed(`${face.text} · ${account}`),
      acknowledgmentFace: KINDS[face.kind],
      ...(face.context ? { context: face.context } : {}),
      activate: () => revealTarget(target, `${face.text}: ${account}`),
    });
  }

  const base = comparisonBase();
  comparisonChanges().forEach((target, index) => {
    const account = `${itemWord(target)} changed${base == null ? "" : ` since v${base}`}`;
    const earlier = comparisonEarlier(target);
    add(groups, target, {
      kind: "change",
      id: `change:${targetPath(target)}:${index}`,
      text: trimmed(`${account} · ${itemSays(target)}`),
      // A disclosure has to say what it holds, or its one word reports a fact and
      // promises nothing. The margin element's quieter line carries it, and a block the
      // comparison holds nothing for has none, so no margin element offers a press it has
      // not got.
      ...(earlier ? { context: earlier.offer } : {}),
      // What a Change reading holds, where the comparison kept the base version's
      // words for this block: pressing it folds them open under the block and says
      // them, so the reader learns what changed without travelling to the other
      // version and back. Where it kept none, the press is the travel it always was,
      // and `discloses` answering null is what says so — to the margin element's relation, to
      // the shortcut bar's word for the press, and to the reference.
      discloses: () => comparisonEarlier(target),
      activate: () => {
        const said = toggleEarlier(target);
        revealTarget(target, said ? `${account} · ${said}` : account);
      },
    });
  });

  if (workClaimState().claimsHeld)
    for (const update of updateSequence()) {
      if (update.source !== "claim" || update.disposition !== "effective") continue;
      if (update.revision > runtime.currentRevision) continue;
      if (activityAlreadyShown.has(`${update.target.kind}:${update.target.id}`))
        continue;
      const target =
        update.target.kind === "thread"
          ? placedAt(update.target.id)?.element
          : elementById(update.target.id);
      const quiet =
        claimActivity.get(`${update.target.kind}:${update.target.id}`)?.quiet ?? false;
      const account = [
        update.agent || "Agent",
        update.text || humanized(update.action),
        quiet ? "quiet" : null,
      ]
        .filter(Boolean)
        .join(" · ");
      const age = ago(update.ts);
      add(groups, target, {
        kind: "activity",
        id: `activity:${update.id}`,
        text: trimmed(account),
        acknowledgmentFace: KINDS.activity,
        context: [age && `Checked in ${age}`, update.text].filter(Boolean).join(" · "),
        activate: () => revealTarget(target, account),
      });
    }

  for (const offered of marginContributions) {
    const target =
      typeof offered.target === "function" ? offered.target() : offered.target;
    if (!target?.isConnected || inChrome(target)) continue;
    const group = groupFor(groups, target);
    if (group.offers.some((candidate) => candidate.key === offered.key))
      throw new TypeError(
        `Duplicate margin contribution key for ${target.id || targetPath(target)}: ${offered.key}`,
      );
    group.offers.push(offered);
    const subject =
      typeof offered.subject === "function" ? offered.subject() : offered.subject;
    if (String(subject ?? "").trim()) {
      if (group.subject && group.subject !== String(subject).trim())
        throw new TypeError(
          `Conflicting margin contribution subjects for ${target.id || targetPath(target)}`,
        );
      group.subject = String(subject).trim();
    }
    const items = typeof offered.items === "function" ? offered.items() : offered.items;
    for (const item of items ?? []) {
      const kind = item.kind ?? "action";
      if (!KINDS[kind]) throw new TypeError(`Unknown margin reading kind: ${kind}`);
      group.items.push({ marker: false, ...item, owner: offered.key, kind });
    }
  }

  return [...groups.values()]
    .map((group) => {
      const items = group.items;
      const represented = new Set(
        items
          .filter((item) => item.marker === false && item.represents)
          .map((item) => item.kind),
      );
      return {
        ...group,
        title: trimmed(
          [group.word, group.subject ?? itemSays(group.target)]
            .filter(Boolean)
            .join(" · "),
          72,
        ),
        items: items
          .filter(
            (item) =>
              item.marker === false ||
              item.acknowledgmentFace ||
              !represented.has(item.kind),
          )
          .sort(
            (left, right) =>
              KINDS[left.kind].priority - KINDS[right.kind].priority ||
              // Threads at one target keep the conversation's log order, not
              // the arbitrary spelling of their event identities.
              (left.kind === "comment" ? 0 : left.id.localeCompare(right.id)),
          ),
      };
    })
    .sort((left, right) => comesBefore(left.target, right.target));
}

function revealTarget(target, account) {
  if (!target?.isConnected) return;
  scrollToElement(target, scrollBehavior(), "nearest");
  // The account goes to the banner's notice slot rather than to the live region alone:
  // a Change margin element's target is usually already on screen, so the scroll moves nothing
  // and a press that only announced was, to a sighted reader, a press that did nothing.
  notice(account);
}

function markerOptions(row) {
  return {
    anchor: () => row.lfEntry?.target,
    ...(row.lfEntry?.offers.length || readingRegionFor(row.lfEntry?.target)
      ? {}
      : { fallback: "hide" }),
    priority: 10,
    claim: () => {
      const entry = row.lfEntry;
      if (!entry) return 0;
      if (readingRegionFor(entry.target)) return 0;
      const primary = choosePrimary(entry);
      const stable = [];
      if (primary && entry.offers.some((offered) => offered.claim))
        stable.push(primary);
      const marker = rows.get(entry.key);
      if (!primary && marker && !marker.hidden) stable.push(marker);
      const more = moreMarginElements.get(entry.key);
      if (more && optionsOffered(entry, primary, { claimedOnly: true }))
        stable.push(more);
      const options = optionGroups.get(entry.key);
      if (
        options &&
        !optionsOffered(entry, primary, { claimedOnly: true }) &&
        secondaryCount(entry, primary, { claimedOnly: true }) > 0
      )
        stable.push(...clusterMarginElements(options));
      const widths = stable
        .map((part) => part.getBoundingClientRect().width)
        .filter(Boolean);
      const reserved = Math.max(
        0,
        ...entry.offers.map((offered) =>
          typeof offered.reserve === "function"
            ? offered.reserve()
            : offered.reserve || 0,
        ),
      );
      if (!widths.length && !reserved) return 0;
      const style = getComputedStyle(row);
      const gap = parseFloat(style.columnGap || style.gap) || 0;
      const current =
        widths.reduce((total, width) => total + width, 0) +
        gap * Math.max(0, widths.length - 1);
      return (
        Math.max(current, reserved) +
        (parseFloat(style.paddingLeft) || 0) +
        (parseFloat(style.paddingRight) || 0)
      );
    },
    shown: (target) =>
      Boolean(target && shownParts(target).some((part) => part.checkVisibility())),
    // Compact mode has no page rail. Dock every contributed item even when a
    // positioned widget happens to leave enough local room for the absolute
    // prototype; that accident must not give one nested target a desktop posture.
    hangs: () => !readingRegionFor(row.lfEntry?.target) && !commentsEdge.over.matches,
    // A wide row is hoisted into main's positioning context. If its live width no
    // longer fits the rail, move the same node beside its target before static flow
    // takes over; restore the hoist before measuring whether it fits again.
    float: (item) => {
      if (item.lfEntry?.offers.length || readingRegionFor(item.lfEntry?.target))
        moveExternalHost(item, false);
    },
    dock: (item) => {
      if (item.lfEntry?.offers.length || readingRegionFor(item.lfEntry?.target))
        moveExternalHost(item, true);
    },
    place: (item, column) => {
      const target = item.lfEntry?.target;
      if (!target) return;
      const place = nav.contains(item) ? measureMargin(column) : null;
      const top = Math.max(0, shownBox(target).top - column.top);
      return () => {
        place?.();
        item.style.top = `${top}px`;
      };
    },
  };
}

function kindsIn(entry, { markerOnly = false } = {}) {
  const counts = new Map();
  for (const item of entry.items) {
    if (!markerOnly || item.marker !== false)
      counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
  }
  return [...counts].map(([kind, count]) => ({ kind, count, ...KINDS[kind] }));
}

function markerName(entry, index, anchored, position) {
  const choice = primaryReading(entry);
  const face = markerFace(entry).face;
  const count = choice?.items.length ?? 0;
  const reading = `${face.label}${count > 1 ? `s (${count})` : ""}`;
  const subject =
    count === 1 && choice.items[0].acknowledgmentFace ? choice.text : entry.title;
  return `${reading}, ${index + 1} of ${anchored}, ${subject}${position == null ? "" : `, ${Math.max(0, Math.min(100, position))} percent down`}`;
}

function availableRows() {
  return [...rows.values()].filter(
    (row) => !row.hidden && !row.closest(".lf-waiting") && row.checkVisibility(),
  );
}

function visibleRows() {
  return availableRows().filter((row) => {
    const box = row.getBoundingClientRect();
    return box.bottom > 0 && box.top < innerHeight;
  });
}

function clusterMarginElements(host) {
  if (!host) return [];
  return [...host.querySelectorAll(".lf-margin-element")].filter(
    (button) =>
      !button.disabled &&
      button.getAttribute("aria-disabled") !== "true" &&
      button.checkVisibility(),
  );
}

const marginElementHost = (target) =>
  [...hosts.values()].find((host) => host.lfTarget === target) ?? null;

export function marginElementContextContains(target, node) {
  return (
    Boolean(marginElementHost(target)?.contains(node)) ||
    (sheet.open && sheetTarget === target && sheet.contains(node))
  );
}

function stepClusterMarginElements(binding) {
  const active = focused();
  const host = closestAcross(active, "[data-lf-margin-for]");
  const buttons = clusterMarginElements(host);
  const at = buttons.indexOf(active);
  if (at < 0 || buttons.length < 2) return;
  const direction = binding === "ArrowRight" ? 1 : -1;
  buttons[(at + direction + buttons.length) % buttons.length].focus({
    preventScroll: true,
  });
}

function setOptionsOpen(
  entry,
  open,
  {
    returnFocus = false,
    focusOption = null,
    owner = null,
    preservePreview = false,
  } = {},
) {
  const previousKey = expandedOptionsKey;
  const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
  const nextKey = open ? (entry?.key ?? null) : null;
  const nextOwner = open ? owner : null;
  if (previousKey === nextKey && expandedOptionsOwner === nextOwner) return;
  if (previewEntry && !preservePreview) closePreview();
  expandedOptionsKey = nextKey;
  expandedOptionsOwner = nextOwner;
  settlingOptionsFocus = true;
  try {
    renderMargin();
    if (returnFocus && previousKey) {
      const more = moreMarginElements.get(previousKey);
      if (more?.isConnected && !more.hidden) more.focus({ preventScroll: true });
    } else if (focusOption && nextKey) {
      const choices = clusterMarginElements(optionGroups.get(nextKey));
      const fallback = clusterMarginElements(hosts.get(nextKey));
      const next =
        (focusOption === "last" ? choices.at(-1) : choices[0]) ??
        (focusOption === "last" ? fallback.at(-1) : fallback[0]);
      next?.focus({ preventScroll: true });
    }
  } finally {
    settlingOptionsFocus = false;
  }
  if (previousGroup?.querySelector(".lf-margin-reactions"))
    document.dispatchEvent(new CustomEvent("lf-margin-element-options-closed"));
}

export function focusForNavigation(control) {
  const wasSuppressingOptionsArrival = suppressingOptionsArrival;
  suppressingOptionsArrival = true;
  try {
    control.focus({ preventScroll: true });
  } finally {
    suppressingOptionsArrival = wasSuppressingOptionsArrival;
  }
}

// A contributed control remains the action's canonical target even when the margin
// presents its secondary through a proxy in the unfolded cluster. Geometry belongs to
// what the reader can see; dispatch still belongs to the original control.
export function presentedControl(control) {
  if (control.checkVisibility()) return control;
  const proxy = controlProxies.get(control);
  return proxy?.checkVisibility() ? proxy : control;
}

export function openMarginElementOptions(target, { owner = null } = {}) {
  renderMargin();
  const entry = pageMapEntries.find((candidate) => candidate.target === target);
  const more = entry && moreMarginElements.get(entry.key);
  const focusedOffer = owner && entry?.offers.find((offered) => offered.key === owner);
  if (!entry || !more || (owner && !focusedOffer)) return false;
  if (expandedOptionsKey === entry.key && expandedOptionsOwner === owner) {
    const options = optionGroups.get(entry.key);
    if (options?.isConnected && !options.hidden) return true;
    expandedOptionsKey = null;
    expandedOptionsOwner = null;
    renderMargin();
  }
  if (expandedOptionsKey === entry.key && expandedOptionsOwner !== owner) {
    setOptionsOpen(entry, true, { owner });
    return true;
  }
  if (!owner && more.hidden) return false;
  setOptionsOpen(entry, true, { owner });
  return true;
}

export function pageMapMarginElements() {
  return pageMapEntries.flatMap((entry) => clusterMarginElements(hosts.get(entry.key)));
}

// A generated reading control has one exact meaning even when its target holds other
// readings behind More. Contributed action controls have no core reading kind.
export function pageMapMarginElementKind(control) {
  const host = closestAcross(control, "[data-lf-margin-for]");
  const entry = host?.lfEntry;
  if (!entry) return null;
  if (control.lfChoice) return control.lfChoice.kind;
  return control === rows.get(entry.key) ? (primaryReading(entry)?.kind ?? null) : null;
}

export function openPageMapMarginElement(control) {
  const item = closestAcross(control, "[data-lf-margin-for]");
  const entry = item?.lfEntry;
  if (!entry?.target || !control) return false;
  scrollToElement(entry.target, undefined, "nearest");
  // Arrive before activation, then use the exact visible margin element's own press. A generated
  // route never chooses among the cluster's actions on the reader's behalf.
  focusForNavigation(control);
  control.click();
  return true;
}

// The direct destination opens the complete map. Its visible margin elements also join the page's
// transient generated-hint namespace without claiming the sheet ends there.
export function enterPageMap() {
  openSheet();
}

function pageMapInvoker() {
  const shelf = mapButton.closest(".lf-banner-menu");
  if (shelf?.lfInvoker?.checkVisibility()) return shelf.lfInvoker;
  return mapButton;
}

export const pageMapIsActive = () => sheet.open || availableRows().includes(focused());
// The dispatcher's own way out of the `g M` frame, and the one close that owes the
// reader nothing: it captured where they stood before the press and restores it in the
// same press. That restore is synchronous while `close` arrives in a task of its own,
// so the door's return route below would run a frame later and put the reader on the
// Map control instead of the ask row or the reading place they asked to come back to.
export function leavePageMap() {
  if (!sheet.open) return;
  sheetCloseOwnsFocus = true;
  sheet.close();
}

function focusMapControl(entry = null) {
  const marker = entry ? rows.get(entry.key) : null;
  if (marker?.isConnected && marker.checkVisibility()) {
    marker.focus({ preventScroll: true });
    return;
  }
  if (mapButton.isConnected && mapButton.checkVisibility()) {
    mapButton.focus({ preventScroll: true });
    return;
  }
  const visible = visibleRows();
  (visible.find((row) => row.tabIndex === 0) ?? visible[0] ?? versionBtn).focus({
    preventScroll: true,
  });
}

// The rail holds one tab stop: the way in from the page, not the reading position,
// which the walk, generated go-to hints, and the pointer all reach without it. A
// status reports a move already made, so the stop passes to the nearest marker that
// still offers a press.
function holdTabStop(next) {
  const available = availableRows();
  const acts = (row) => row.dataset.lfBehavior !== "status";
  let stop = next;
  if (stop && !acts(stop)) {
    const at = available.indexOf(stop);
    stop = available.reduce((nearest, row, index) => {
      if (!acts(row)) return nearest;
      if (!nearest) return { row, distance: Math.abs(index - at) };
      const distance = Math.abs(index - at);
      return distance < nearest.distance ? { row, distance } : nearest;
    }, null)?.row;
  }
  for (const row of rows.values()) keeps(row, "tabindex", row === stop ? 0 : -1);
}

function syncRoving() {
  const available = availableRows();
  const visible = visibleRows();
  if (!available.length) {
    holdTabStop(null);
    return;
  }
  const focused = available.find((row) => row === document.activeElement);
  const candidates = visible.length ? visible : available;
  const held = candidates.find(
    (row) => row === document.activeElement || row.tabIndex === 0,
  );
  const next =
    focused ??
    held ??
    candidates.reduce((best, row) => {
      const distance = (candidate) => {
        const box = candidate.getBoundingClientRect();
        if (box.bottom < 0) return -box.bottom;
        if (box.top > innerHeight) return box.top - innerHeight;
        return 0;
      };
      return distance(row) < distance(best) ? row : best;
    });
  holdTabStop(next);
}

function scheduleRoving() {
  cancelAnimationFrame(rovingFrame);
  rovingFrame = requestAnimationFrame(() => {
    rovingFrame = 0;
    syncRoving();
  });
}

function walkMarkers(direction, edge = null) {
  const visible = visibleRows();
  if (!visible.length) return;
  const next =
    edge === "first"
      ? visible[0]
      : edge === "last"
        ? visible.at(-1)
        : clampedRow(visible, document.activeElement, direction);
  holdTabStop(next);
  next.focus({ preventScroll: true });
}

let marginKeysAvailable = false;
const marginKeys = [
  // The seat a reading holds is a span, so the platform's own activation is not under
  // it. Declared here rather than answered by a listener on the control: this is the
  // register's whole bargain — the line and the reference draw the key off the same row
  // the press is matched against, so neither can promise what the other does not do.
  // Only the span-shaped readings, because a native margin element in this cluster answers its
  // own press and a second answer here would be two meanings for one key.
  {
    id: "margin.press",
    keys: PRESS,
    // Said for the margin element under the reader, not for margin elements in general: "work this
    // margin element" over a Change reading promised something, and Enter there scrolls to a
    // paragraph already on screen. A reading's press goes to what it points at; a
    // disclosure's opens or closes it; an action's does the verb on its face.
    // Read off the standing margin element, and only where there is one: the reference
    // lists this row's sentence from anywhere on the page.
    does: () => {
      const behavior = focusedMarginElementBehavior();
      if (behavior === "disclosure")
        return "Open or close what the focused margin element holds";
      if (behavior === "action") return "Press the focused margin element";
      if (behavior) return "Go to what the focused margin element points at";
      return "Work the focused margin element";
    },
    line: () => {
      const behavior = focusedMarginElementBehavior();
      if (behavior === "disclosure") return "open / close";
      if (behavior === "action") return "press";
      if (behavior) return "go to it";
      return "work this margin element";
    },
    when: () => focused()?.matches?.('.lf-margin-element[role="button"]'),
    run: () => focused().click(),
  },
  {
    id: "margin.controls",
    keys: ["ArrowLeft", "ArrowRight"],
    does: "Move through the margin elements on this target",
    line: "move through margin elements",
    repeat: true,
    when: () => {
      const active = focused();
      const host = closestAcross(active, "[data-lf-margin-for]");
      return (
        active?.matches?.(".lf-margin-element") &&
        clusterMarginElements(host).length > 1
      );
    },
    run: stepClusterMarginElements,
  },
  {
    id: "margin.walk",
    keys: ["ArrowUp", "ArrowDown"],
    does: "Walk the visible page-map markers",
    line: "walk the page map",
    repeat: true,
    when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
    run: (binding) => walkMarkers(binding === "ArrowDown" ? 1 : -1),
  },
  {
    id: "margin.first",
    keys: ["Home"],
    does: "First visible page-map marker",
    line: "first marker",
    when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
    run: () => walkMarkers(0, "first"),
  },
  {
    id: "margin.last",
    keys: ["End"],
    does: "Last visible page-map marker",
    line: "last marker",
    when: () => focused()?.matches?.(".lf-margin-marker") && visibleRows().length > 0,
    run: () => walkMarkers(0, "last"),
  },
];

function pressMarker(event) {
  const marker = event.currentTarget;
  const choice = primaryReading(marker.lfEntry);
  if (!choice) return;
  if (choice.kind !== "comment") {
    activate(choice.items[0], marker.lfEntry);
    return;
  }
  openThreadChoice(marker.lfEntry, marker);
}

function paintMarker(row, entry, primary, { suppressed = false } = {}) {
  const { kinds: markerKinds, face, label, count: markerCount } = markerFace(entry);
  const choice = primaryReading(entry);
  const behavior = readingBehavior(face);
  row.lfEntry = entry;
  keepsHidden(row, suppressed || markerKinds.length === 0 || Boolean(primary));
  keeps(row, "data-lf-kinds", markerKinds.map(({ kind }) => kind).join(" "));
  marginElement(row, {
    key: `reading:${choice?.key ?? "none"}`,
    icon: face.icon,
    label,
    context: readingContext(choice),
    behavior,
    role: "reading",
    state: readingState(choice),
    writesRelation: false,
    writesSeat: false,
  });
  row.onclick = behavior === "status" ? null : pressMarker;
  syncReadingRelation(row, choice);
  row.removeAttribute("aria-pressed");
  syncMarginElementCount(row, markerCount);
  if (row.lfTakeFocus) {
    delete row.lfTakeFocus;
    (row.hidden ? document.body : row).focus({ preventScroll: true });
  }
}

function externalPerch(target, main, flow = commentsEdge.over.matches) {
  if (!main) return target;
  // A hanging item must be a child of main's own positioning context. In flow it
  // belongs immediately after the rendered block that owns its target. A declared
  // shadow tree still contributes through its host, where document CSS can reach the
  // controls.
  let perch = flow ? (blockAt(target) ?? target) : target;
  while (!main.contains(perch)) {
    const root = perch.getRootNode();
    if (!(root instanceof ShadowRoot)) return target;
    perch = root.host;
  }
  if (flow) return perch;
  while (perch.parentElement !== main && main.contains(perch.parentElement))
    perch = perch.parentElement;
  return perch;
}

function moveExternalHost(host, flow) {
  const main = document.querySelector("main");
  const target = host.lfEntry?.target;
  if (!main || !target || commentsEdge.over.matches) return;
  const perch = externalPerch(target, main, flow);
  let after = perch;
  for (const entry of pageMapEntries) {
    const candidate = hosts.get(entry.key);
    if (candidate === host) break;
    if (
      candidate?.isConnected &&
      externalPerch(entry.target, main, flow) === perch &&
      candidate.parentNode === perch.parentNode
    )
      after = candidate;
  }
  if (after.nextSibling !== host) moveHost(host, () => after.after(host));
}

function optionControlNode(control, entry) {
  let node = controlProxies.get(control);
  if (!node) {
    node = offer("button", "lf-margin-option-proxy");
    node.type = "button";
    controlProxies.set(control, node);
  }
  const record = marginElementRecord(control);
  marginElement(node, {
    key: `${record.key}:proxy`,
    ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
    label: record.label,
    context: record.context,
    behavior: record.behavior,
    tone: record.tone,
    role: record.role,
    state: record.state,
    writesRelation: record.writesRelation,
  });
  syncForwardedMarginElementState(node, control);
  node.lfForwardedControl = control;
  // The proxy carries the control's press, so it carries where that control stands.
  standsWith(node, control);
  keeps(node, "data-lf-margin-element-owner", record.owner);
  node.onclick = () => {
    control.click();
  };
  return node;
}

function readingOptionNode(entry, choice) {
  const key = readingKey(entry, choice);
  let node = readingMarginElements.get(key);
  if (!node) {
    node = readingControl("lf-margin-reading-option");
    readingMarginElements.set(key, node);
  }
  const face = readingFace(choice);
  const behavior = readingBehavior(face);
  const count = choice.items.length;
  const label = count > 1 ? `${face.label}s` : face.label;
  marginElement(node, {
    key: `reading:${choice.key}`,
    icon: face.icon,
    label,
    context: readingContext(choice),
    behavior,
    role: "reading",
    state: readingState(choice),
    writesRelation: false,
  });
  node.lfEntry = entry;
  node.lfChoice = choice;
  syncReadingRelation(node, choice);
  keeps(node, "data-lf-kinds", choice.kind);
  keeps(
    node,
    "aria-label",
    `${label} for ${entry.title}${count > 1 ? `, ${count} items` : ""}`,
  );
  syncMarginElementCount(node, count);
  node.onclick =
    behavior === "status"
      ? null
      : () => {
          if (node.lfChoice.kind !== "comment") {
            setOptionsOpen(node.lfEntry, false, { returnFocus: true });
            activate(node.lfChoice.items[0], node.lfEntry, { focusMap: false });
            return;
          }
          openThreadChoice(node.lfEntry, node);
        };
  return node;
}

function focusedOwnerOffer(entry) {
  if (expandedOptionsKey !== entry.key || !expandedOptionsOwner) return null;
  return entry.offers.find((offered) => offered.key === expandedOptionsOwner) ?? null;
}

function optionNodes(entry, primary, focusedOffer = null) {
  if (focusedOffer) {
    const controls = controlsOf(focusedOffer).filter((control) =>
      entry.shownControls.has(control),
    );
    return focusedOffer.side === "after"
      ? controls
      : controls.map((control) => optionControlNode(control, entry));
  }
  return [
    ...secondaryControls(entry, primary).map((control) =>
      optionControlNode(control, entry),
    ),
    ...secondaryReadings(entry, primary).map((choice) =>
      readingOptionNode(entry, choice),
    ),
    ...afterOffers(entry).flatMap((offered) =>
      controlsOf(offered)
        .filter((control) => entry.shownControls.has(control))
        .map((control) => ({ control, offered }))
        .sort(compareControlRecords)
        .map(({ control }) => control),
    ),
  ];
}

function syncOptionGroup(group, entry, primary, optionsOpen, focusedOffer = null) {
  const allNodes = optionNodes(entry, primary, focusedOffer);
  const unique = [...new Set(allNodes)];
  // Peers may use the whole cluster budget only when no margin element stands outside this
  // group. Reaction mode is the common case: it has neither a primary nor a reading
  // marker, so its six declared choices fit exactly. A reading-only target keeps its
  // marker visible, and that margin element counts just as a contributed primary would.
  const peerCapacity = Math.max(
    0,
    EXPANDED_MARGIN_ELEMENT_BUDGET -
      (!focusedOffer && (primary || markerFace(entry).kinds.length) ? 1 : 0),
  );
  const needsSpill = unique.length > peerCapacity;
  // The spill route consumes the last visible margin element; it does not increase the
  // cluster beyond its budget. A fully expanded cluster is therefore either one
  // primary plus five peers, or one primary plus four peers plus the Page map route.
  const visibleCapacity = needsSpill ? peerCapacity - 1 : peerCapacity;
  const hidden = Math.max(0, unique.length - visibleCapacity);
  const direct = unique.slice(0, visibleCapacity);
  const forcedThread =
    forcedInlineKey === entry.key
      ? unique.find((node) => node.lfChoice?.kind === "comment")
      : null;
  // An open thread card keeps its owning Thread control on the page edge. When the
  // ordinary order would put it beyond the six-control budget, spill the last unrelated
  // peer in its place; the Page map still retains every action in canonical order.
  if (forcedThread && direct.length && !direct.includes(forcedThread))
    direct[direct.length - 1] = forcedThread;
  const visible = new Set(direct);
  const after = focusedOffer
    ? focusedOffer.side === "after"
      ? [focusedOffer]
      : []
    : afterOffers(entry);
  const afterControls = new Set(after.flatMap(controlsOf));
  const wanted = unique.filter((node) => visible.has(node) && !afterControls.has(node));
  // Keep contributor-owned groups intact: their keyboard scopes and event handlers
  // belong to the real controls. Overflow hides individual margin elements, not the owner.
  for (const offered of after) {
    const controls = controlsOf(offered);
    for (const control of controls)
      control.toggleAttribute("data-lf-margin-element-overflow", !visible.has(control));
    offered.controls.toggleAttribute(
      "data-lf-margin-element-overflow",
      !controls.some((control) => visible.has(control)),
    );
    wanted.push(offered.controls);
  }
  let spill = spillMarginElements.get(entry.key);
  if (needsSpill) {
    if (!spill) {
      spill = offer("button", "lf-margin-spill");
      spill.type = "button";
      spillMarginElements.set(entry.key, spill);
    }
    marginElement(spill, {
      key: "all-options",
      icon: "all",
      label: `Show ${hidden} more in Page map`,
      behavior: "disclosure",
      role: "overflow",
      state: "idle",
    });
    keeps(spill, "data-lf-spill-count", hidden);
    spill.lfFirstSpilledOption = unique.find((node) => !visible.has(node));
    keeps(spill, "aria-label", `Show ${hidden} more in Page map`);
    spill.onclick = () => openSheet(entry, { invoker: spill, focusSpill: true });
    wanted.push(spill);
  } else if (spill) {
    spill.remove();
    spillMarginElements.delete(entry.key);
  }
  for (const child of [...group.children]) if (!wanted.includes(child)) child.remove();
  wanted.forEach((child, position) => {
    if (group.children[position] !== child)
      group.insertBefore(child, group.children[position] ?? null);
  });
  group.lfEntry = entry;
  keeps(
    group,
    "aria-label",
    `${entryEngaged(entry) ? "Actions" : "More options"} for ${entry.title}`,
  );
  keepsHidden(group, !optionsOpen || wanted.length === 0);
}

function syncControls(host, marker, more, options, entry) {
  const active = document.activeElement;
  const focusedOption = options.contains(active);
  const forwardedControl = active?.lfForwardedControl;
  const focusedOffer = focusedOwnerOffer(entry);
  const primary = focusedOffer ? null : syncControlRoles(entry);
  if (focusedOffer)
    for (const control of directControls(entry))
      control.removeAttribute("data-lf-margin-element-primary");
  const controls = focusedOffer
    ? []
    : directOffers(entry)
        .filter((offered) => offered.controls)
        .map((offered) => offered.controls);
  const wanted = [...controls, marker, more, options];
  for (const child of [...host.children]) if (!wanted.includes(child)) child.remove();
  wanted.forEach((child, position) => {
    if (host.children[position] !== child)
      host.insertBefore(child, host.children[position] ?? null);
  });
  const secondaries = focusedOffer
    ? controlsOf(focusedOffer).filter((control) => entry.shownControls.has(control))
        .length
    : secondaryCount(entry, primary);
  const hasOptions = focusedOffer ? secondaries > 0 : optionsOffered(entry, primary);
  if (!hasOptions && expandedOptionsKey === entry.key) {
    expandedOptionsKey = null;
    expandedOptionsOwner = null;
  }
  const optionsOpen =
    secondaries > 0 &&
    (!hasOptions || expandedOptionsKey === entry.key || entryEngaged(entry));
  keepsHidden(more, !hasOptions || optionsOpen);
  more.lfEntry = entry;
  keeps(more, "aria-label", `More options for ${entry.title}`);
  keeps(more, "aria-expanded", optionsOpen);
  host.toggleAttribute("data-lf-options-open", optionsOpen);
  keeps(host, "data-lf-state", entryState(entry));
  // Replacing a focused proxy fires focusout synchronously. The render already owns
  // the resulting cluster state and transfers focus below, so do not let that event
  // start a nested render against the same child list.
  const wasSettlingOptionsFocus = settlingOptionsFocus;
  settlingOptionsFocus = true;
  try {
    syncOptionGroup(options, entry, primary, optionsOpen, focusedOffer);
  } finally {
    settlingOptionsFocus = wasSettlingOptionsFocus;
  }
  const lostOptionFocus = focusedOption && !options.contains(document.activeElement);
  if (!hasOptions && (document.activeElement === more || lostOptionFocus)) {
    const destination = primary ?? (primaryReading(entry) ? marker : null);
    if (destination === marker && marker.hidden) marker.lfTakeFocus = true;
    else (destination ?? document.body).focus({ preventScroll: true });
  } else if (lostOptionFocus) {
    // A secondary proxy can become the real primary when its press settles. Keep
    // focus on that same semantic control instead of jumping to the first status
    // reading merely because the cluster stayed engaged and replaced its peers.
    const next =
      (forwardedControl?.checkVisibility() ? forwardedControl : null) ??
      primary ??
      clusterMarginElements(options)[0] ??
      clusterMarginElements(host)[0];
    (next ?? document.body).focus({ preventScroll: true });
  }
  return primary;
}

// A widget frozen into a conversation belongs to that conversation's document,
// not to the page margin behind it. Keep its contributed controls in the local
// flow, grouped by the same exact target identity, without registering a page rail
// claim or a second placement model in the widget module.
function syncInlineOffers() {
  const grouped = new Map();
  for (const offered of marginContributions) {
    const target =
      typeof offered.target === "function" ? offered.target() : offered.target;
    if (!target?.isConnected || !inChrome(target) || !offered.controls) continue;
    const offers = grouped.get(target) ?? [];
    offers.push(offered);
    grouped.set(target, offers);
  }

  for (const [target, offers] of grouped) {
    let host = inlineHosts.get(target);
    if (!host) {
      host = el("div", "lf-ui");
      host.dataset.lfGen = "1";
      host.setAttribute("role", "group");
      inlineHosts.set(target, host);
    }
    keeps(host, "data-lf-margin-for", target.id || targetPath(target));
    host.lfTarget = target;
    keeps(host, "aria-label", `Actions for ${itemWord(target)}`);
    const controls = (side) =>
      offers
        .filter((offered) => offered.side === side)
        .sort(compareOffers)
        .map((offered) => offered.controls);
    const wanted = [...controls("before"), ...controls("after")];
    for (const child of [...host.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((child, position) => {
      if (host.children[position] !== child)
        host.insertBefore(child, host.children[position] ?? null);
    });
    if (target.nextSibling !== host) moveHost(host, () => target.after(host));
  }

  for (const [target, host] of inlineHosts)
    if (!grouped.has(target)) {
      host.remove();
      inlineHosts.delete(target);
    }
}

function moveHost(host, move) {
  const held = host.contains(document.activeElement) ? document.activeElement : null;
  // Moving a focused expanded cluster between the hanging rail and document flow
  // synchronously emits focusout. That is a placement transition, not the reader
  // leaving the cluster, so keep the options state machine from treating it as an
  // instruction to fold the controls it just exposed — and say the same thing to every
  // other reader of where the reader stands, which is what `placingChrome` is for.
  const wasSettlingOptionsFocus = settlingOptionsFocus;
  const wasPlacingChrome = runtime.placingChrome;
  settlingOptionsFocus = true;
  runtime.placingChrome = true;
  try {
    move();
    if (held?.isConnected) held.focus({ preventScroll: true });
  } finally {
    settlingOptionsFocus = wasSettlingOptionsFocus;
    runtime.placingChrome = wasPlacingChrome;
  }
  // The one case where the placement did move the reader: the control they were
  // standing on did not survive it, so focus is wherever the removal left it and the
  // standing paint is owed the news the guard above withheld.
  if (held && document.activeElement !== held) paintHere();
}

const labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height,
  },
});

const rectsOverlap = (left, right) =>
  left.left < right.right &&
  left.right > right.left &&
  left.top < right.bottom &&
  left.bottom > right.top;

function placeMarginElementLabel(control) {
  const label = control.querySelector(":scope > .lf-margin-element-label");
  if (!label || !control.checkVisibility()) return;
  const marginElementBox = control.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  const edgeAligned = Math.max(
    4,
    Math.min(marginElementBox.right - labelBox.width, innerWidth - 4 - labelBox.width),
  );
  const cluster = control.closest(".lf-margin-cluster") ?? control.parentElement;
  const clusterMarginElements = [
    ...(cluster?.querySelectorAll(".lf-margin-element") ?? []),
  ]
    .filter((candidate) => candidate.checkVisibility())
    .map((candidate) => candidate.getBoundingClientRect());
  const clusterLeft = Math.min(...clusterMarginElements.map((box) => box.left));
  const clusterRight = Math.max(...clusterMarginElements.map((box) => box.right));
  const centered =
    (marginElementBox.top + marginElementBox.bottom - labelBox.height) / 2;
  const candidates = [
    labelRect("below", edgeAligned, marginElementBox.bottom + 6, labelBox),
    labelRect(
      "above",
      edgeAligned,
      marginElementBox.top - 6 - labelBox.height,
      labelBox,
    ),
    labelRect("after", clusterRight + 6, centered, labelBox),
    labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox),
  ];
  const blockers = [
    ...[...document.querySelectorAll(".lf-margin-element")].filter(
      (candidate) => candidate !== control && candidate.checkVisibility(),
    ),
    ...document.querySelectorAll(".lf-banner, .lf-shortcut-bar"),
  ].map((candidate) => candidate.getBoundingClientRect());
  const fits = ({ rect }) =>
    rect.left >= 4 &&
    rect.right <= innerWidth - 4 &&
    rect.top >= 4 &&
    rect.bottom <= innerHeight - 4;
  const choice =
    candidates.find(
      (candidate) =>
        fits(candidate) &&
        !blockers.some((blocker) => rectsOverlap(candidate.rect, blocker)),
    ) ??
    candidates.find(fits) ??
    candidates[0];
  control.dataset.lfLabelSide = choice.name;
  label.style.setProperty(
    "--lf-label-x",
    `${choice.rect.left - marginElementBox.left}px`,
  );
  label.style.setProperty(
    "--lf-label-y",
    `${choice.rect.top - marginElementBox.top}px`,
  );
}

let labelPlacementFrame = 0;
function scheduleMarginElementLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = requestAnimationFrame(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      '.lf-margin-element:is(:hover, :focus-visible, .lf-focus-visible):not([aria-expanded="true"])',
    ))
      placeMarginElementLabel(control);
  });
}

function unfoldOpenThreadOwner(entry) {
  const previousKey = expandedOptionsKey;
  const previousGroup = previousKey ? optionGroups.get(previousKey) : null;
  expandedOptionsKey = entry.key;
  expandedOptionsOwner = null;
  renderMargin();
  if (previousGroup?.querySelector(".lf-margin-reactions"))
    document.dispatchEvent(new CustomEvent("lf-margin-element-options-closed"));
}

function transferThreadCard(
  button,
  { returnFocus = document.activeElement === previewMarginElement } = {},
) {
  if (previewMarginElement === button) return;
  previewMarginElement = button;
  previewReferenceSeen = false;
  if (returnFocus) button.focus({ preventScroll: true });
}

// Paper is not a posture this can be read in. Print hides every injected control
// (`[data-lf-offer]` in the chrome stylesheet's print block) and the living margin
// with it, so the one contributor-visibility reading a render is built on comes back
// empty: every cluster folds to nothing, and what has been written down is the medium
// rather than the page. Nobody sees it on the sheet, where the margin does not print
// at all, but the fold outlives the print preview and stands on screen until the next
// render repairs it. It is the panel's head-room rule on the other surface that
// measures: a reading taken where the box is `display: none` is not a measurement. So
// a render asked for on paper is refused whole and taken once the screen is back.
const onPaper = matchMedia("print");
onPaper.addEventListener("change", () => {
  if (!onPaper.matches) renderMargin();
});

function renderNow() {
  if (onPaper.matches) return;
  const threadOwnerHeld =
    transferThreadFocus || document.activeElement === previewMarginElement;
  transferThreadFocus = false;
  const main = document.querySelector("main");
  if (!nav.isConnected) chromeRoot.append(nav);
  const mainRect = main?.getBoundingClientRect();
  measureMargin(mainRect)?.();
  syncInlineOffers();
  pageMapEntries = collectEntries().filter((entry) => entry.target);
  // Read contributor visibility once for the whole render, before folding any
  // controls. Placement and option counts share this reading; probing again
  // temporarily unfolds controls and forces style/layout work for every row.
  const shownControls = new Set(
    controlsShownByOwner([
      ...new Set(pageMapEntries.flatMap((entry) => entry.offers.flatMap(controlsOf))),
    ]),
  );
  for (const entry of pageMapEntries) entry.shownControls = shownControls;
  const liveHosts = new Set(
    pageMapEntries.filter(entryHasMarginHost).map((entry) => entry.key),
  );
  const liveReadingKeys = new Set(
    pageMapEntries.flatMap((entry) =>
      readingChoices(entry).map((choice) => readingKey(entry, choice)),
    ),
  );
  for (const key of readingMarginElements.keys())
    if (!liveReadingKeys.has(key)) readingMarginElements.delete(key);
  if (expandedOptionsKey && !liveHosts.has(expandedOptionsKey)) {
    expandedOptionsKey = null;
    expandedOptionsOwner = null;
  }
  for (const [key, marker] of rows)
    if (!liveHosts.has(key)) {
      const host = hosts.get(key);
      unregisterMarginRow(host);
      host?.remove();
      rows.delete(key);
      moreMarginElements.delete(key);
      spillMarginElements.delete(key);
      optionGroups.delete(key);
      hosts.delete(key);
    }
  const externalDocks = new Map();
  let corePosition = 0;
  pageMapEntries.forEach((entry) => {
    if (!entryHasMarginHost(entry)) return;
    let marker = rows.get(entry.key);
    let more = moreMarginElements.get(entry.key);
    let options = optionGroups.get(entry.key);
    let host = hosts.get(entry.key);
    if (host) host.lfEntry = entry;
    if (!marker) {
      host = el("div", "lf-ui lf-margin-cluster");
      host.dataset.lfGen = "1";
      host.setAttribute("role", "group");
      marker = marginElement(readingControl("lf-margin-marker"), {
        key: "reading",
        icon: "dot",
        label: "Open page details",
        behavior: "disclosure",
        role: "reading",
        writesRelation: false,
        writesSeat: false,
      });
      keys(host, "In the page map", marginKeys, () => marginKeysAvailable);
      host.lfEntry = entry;
      rows.set(entry.key, marker);
      more = marginElement(offer("button", "lf-margin-more"), {
        key: "options",
        icon: "more",
        label: "More options",
        behavior: "disclosure",
        role: "overflow",
      });
      options = el("div", "lf-margin-options");
      options.id = `lf-margin-options-${++optionsOrdinal}`;
      options.hidden = true;
      options.setAttribute("role", "group");
      more.setAttribute("aria-controls", options.id);
      more.onclick = () => {
        const open = expandedOptionsKey !== more.lfEntry.key;
        setOptionsOpen(more.lfEntry, open, {
          focusOption: open ? "first" : null,
        });
      };
      host.addEventListener("focusin", (event) => {
        const control = event.target.closest?.(".lf-margin-element");
        if (
          settlingOptionsFocus ||
          suppressingOptionsArrival ||
          !control ||
          !host.contains(control) ||
          !control.matches(":focus-visible")
        )
          return;
        const current = host.lfEntry;
        const primary = current && choosePrimary(current);
        if (!current || !optionsOffered(current, primary)) return;
        if (expandedOptionsKey === current.key && expandedOptionsOwner) return;
        if (entryEngaged(current)) return;
        setOptionsOpen(current, true, {
          focusOption: control === more ? "last" : null,
        });
      });
      host.addEventListener("focusin", () => {
        // A new keyboard destination outranks a pointer parked on the previous
        // target. Real pointer movement can take ownership back without a press.
        hoveredHost = null;
        refreshHighlight();
      });
      host.addEventListener("focusout", () => requestAnimationFrame(refreshHighlight));
      const takePointerOwnership = (event) => {
        const control = document
          .elementFromPoint(event.clientX, event.clientY)
          ?.closest?.(".lf-margin-element");
        hoveredHost = control && host.contains(control) ? host : null;
        refreshHighlight();
      };
      host.addEventListener("pointermove", takePointerOwnership);
      host.addEventListener("pointerleave", () => {
        if (hoveredHost === host) {
          hoveredHost = null;
        }
        refreshHighlight();
      });
      host.addEventListener("focusout", (event) => {
        const current = host.lfEntry;
        if (
          settlingOptionsFocus ||
          !current ||
          expandedOptionsKey !== current.key ||
          inRetainedContext(event.relatedTarget) ||
          host.contains(event.relatedTarget)
        )
          return;
        setOptionsOpen(current, false);
      });
      // A direct primary belongs to its owner rather than the generated proxy path.
      // Fold only a temporary expansion before that action; an engaged owner keeps
      // its completion actions exposed until its own state actually ends.
      host.addEventListener(
        "click",
        (event) => {
          if (!expandedOptionsKey || entryEngaged(host.lfEntry)) return;
          const primary = event.target.closest?.("[data-lf-margin-element-primary]");
          if (primary && host.contains(primary)) setOptionsOpen(host.lfEntry, false);
        },
        { capture: true },
      );
      moreMarginElements.set(entry.key, more);
      optionGroups.set(entry.key, options);
      hosts.set(entry.key, host);
      registerMarginRow(host, markerOptions(host));
    } else updateMarginRow(host, markerOptions(host));
    host.lfEntry = entry;
    host.lfTarget = entry.target;
    keeps(host, "data-lf-margin-for", entry.target.id || entry.key);
    keeps(host, "aria-label", `Page actions for ${entry.title}`);
    marker.lfEntry = entry;
    const primary = syncControls(host, marker, more, options, entry);
    if (entry.offers.length || readingRegionFor(entry.target)) {
      keeps(host, "data-lf-external", "1");
      const perch = externalPerch(entry.target, main);
      const dock = externalDocks.get(perch) ?? perch;
      if (dock.nextSibling !== host) moveHost(host, () => dock.after(host));
      externalDocks.set(perch, host);
    } else {
      delete host.dataset.lfExternal;
      if (toolbar.children[corePosition] !== host)
        moveHost(host, () =>
          toolbar.insertBefore(host, toolbar.children[corePosition] ?? null),
        );
      corePosition += 1;
    }
    paintMarker(marker, entry, primary, {
      suppressed: Boolean(focusedOwnerOffer(entry)),
    });
  });
  // Geometry is one read-only batch after every row has reconciled. Reading a target
  // between two marker writes forced one full document layout per Page-map entry —
  // including on the two-second heartbeat. The spoken positions use the main rect
  // already read above and one final scroll height, then write every name together.
  const mainHeight = main?.scrollHeight ?? 0;
  const positions = pageMapEntries.map((entry) =>
    entry.target && !readingRegionFor(entry.target) && mainRect && mainHeight
      ? Math.round(
          ((entry.target.getBoundingClientRect().top - mainRect.top) / mainHeight) *
            100,
        )
      : null,
  );
  const walked = pageMapEntries
    .map((entry, index) => ({ entry, position: positions[index] }))
    .filter(({ entry }) => entryHasMarginHost(entry));
  walked.forEach(({ entry, position }, index) => {
    const marker = rows.get(entry.key);
    const name = markerName(entry, index, walked.length, position);
    keeps(marker, "aria-label", name);
  });
  const mapSays = `Map (${pageMapEntries.length})`;
  keepsHidden(mapButton, pageMapEntries.length === 0);
  if (mapButton.textContent !== mapSays) mapButton.textContent = mapSays;
  keepsHidden(nav, pageMapEntries.length === 0);
  keeps(nav, "aria-label", `Page map, ${pageMapEntries.length} locations`);
  if (sheet.open) renderSheet();
  if (previewEntry) {
    const fresh = pageMapEntries.find((entry) => entry.key === previewEntry.key);
    if (!fresh || !fresh.items.some((item) => item.kind === "comment"))
      closePreview(preview.contains(document.activeElement));
    else {
      previewEntry = fresh;
      const owner = threadMarginElement(fresh);
      if (
        owner &&
        !owner.checkVisibility() &&
        forcedInlineKey !== fresh.key &&
        expandedOptionsKey !== fresh.key &&
        !moreMarginElements.get(fresh.key)?.hidden
      ) {
        transferThreadFocus = threadOwnerHeld;
        unfoldOpenThreadOwner(fresh);
        return;
      }
      if (!owner || (!owner.checkVisibility() && forcedInlineKey !== fresh.key))
        closePreview();
      else {
        transferThreadCard(owner, { returnFocus: threadOwnerHeld });
        buildThreadCard(fresh);
        for (const row of rows.values())
          syncReadingRelation(row, primaryReading(row.lfEntry));
        for (const reading of readingMarginElements.values())
          syncReadingRelation(reading, reading.lfChoice);
      }
    }
  }
  refreshHighlight();
  scheduleMarginLayout();
  scheduleRoving();
  scheduleMarginElementLabels();
  // Every Page-map host contributes the same keyboard section. Its capability is the
  // map's existence; each row already asks the narrower question of whether its press
  // works from the current focus. Repeating live geometry in every scope's `when`
  // forced a layout per location when paintKeys reflected them.
  marginKeysAvailable = pageMapEntries.length > 0;
  paintKeys();
}

function buildThreadCard(entry) {
  const focusedNode = preview.contains(document.activeElement)
    ? document.activeElement.closest?.("[data-lf-margin-element]")
    : null;
  const focusedItem = focusedNode?.dataset.lfMarginElement ?? null;
  const threadItems = entry.items.filter((item) => item.kind === "comment");
  const targetHeading = entry.target?.querySelector(":scope > strong")?.textContent;
  // A target with a heading is named by it. One without — an aside, a paragraph —
  // and holding one thread is headed by the passage that thread quotes, as the panel
  // heads it: a card headed "aside · The fallback cookie is read-only…" over a comment
  // on the aside's last sentence was a third name for one thread, and the least exact.
  const quoted =
    threadItems.length === 1 && threadItems[0].thread?.anchor
      ? anchorLabel(threadItems[0].thread.anchor, threadItems[0].thread.root.about)
      : null;
  const title = trimmed(targetHeading || quoted || entry.title, 72);
  keeps(preview, "data-lf-thread", "");
  keeps(preview, "aria-label", `Thread for ${title}`);
  previewTitle.textContent = title;
  const nodes = threadItems.map(previewItemNode);
  const keep = new Set(nodes);
  for (const child of [...previewList.children]) if (!keep.has(child)) child.remove();
  let cursor = previewList.firstChild;
  for (const node of nodes) {
    if (node === cursor) cursor = cursor.nextSibling;
    else previewList.insertBefore(node, cursor);
  }
  if (focusedItem && !focusedNode?.isConnected) {
    const replacement = [
      ...previewList.querySelectorAll("[data-lf-margin-element]"),
    ].find((candidate) => candidate.dataset.lfMarginElement === focusedItem);
    const destination = replacement?.matches("button, textarea:not([disabled])")
      ? replacement
      : (replacement?.querySelector("textarea:not([disabled])") ??
        replacement?.querySelector("button") ??
        previewClose);
    destination.focus({ preventScroll: true });
  }
  placeThreadPreview();
}

function previewItemNode(item) {
  let node = [...previewList.children].find(
    (candidate) => candidate.dataset.lfMarginElement === item.id,
  );
  if (!node?.classList.contains("lf-margin-thread")) {
    node?.remove();
    node = el("section", "lf-margin-thread");
    const body = el("div", "lf-margin-thread-body");
    node.append(body);
  }
  renderMarginThread(
    node.querySelector(":scope > .lf-margin-thread-body"),
    item.thread,
  );
  node.dataset.lfMarginElement = item.id;
  return node;
}

function highlight(target) {
  if (highlighted === target) return;
  highlighted = target;
  traceTarget(target);
}

function refreshHighlight() {
  const active = focused();
  const focusedHost = closestAcross(active, "[data-lf-margin-for]");
  const pointerHost = hoveredHost?.isConnected ? hoveredHost : null;
  const source =
    pointerHost ??
    focusedHost ??
    (preview.contains(active) || preview.matches(":popover-open")
      ? hosts.get(previewEntry?.key)
      : null);
  const entry = pageMapEntries.find(
    (candidate) => candidate.key === source?.lfEntry?.key,
  );
  // A drawing already marks this target on the page. When every item at the location
  // is a drawing comment, focusing its marker or thread needs no second target box.
  const drawingOnly =
    entry?.items.length &&
    entry.items.every(
      (item) => item.kind === "comment" && Boolean(item.thread?.root.drawing),
    );
  highlight(drawingOnly ? null : (entry?.target ?? null));
}

function showPreview(entry, button, retry = true) {
  if (!entry || designOn) return;
  if (forcedInlineKey && forcedInlineKey !== entry.key) forcedInlineKey = null;
  if (previewEntry && previewEntry.key !== entry.key) clearThreadTransition();
  previewEntry = entry;
  transferThreadCard(button);
  buildThreadCard(entry);
  // The open pseudo-class is not observable until the browser's show operation
  // completes, and another auto popover may still be closing in this rendering turn.
  if (!preview.matches(":popover-open") && !previewShowing) {
    previewShowing = true;
    try {
      // The card remains an ordinary popover rather than an implicit invoker target so
      // its close control and conversation keep their established order in the shared
      // chrome layer.
      preview.showPopover();
    } catch (error) {
      // Chromium also refuses a second popover operation in the same rendering turn,
      // even when it belongs to another surface. Keep the requested marker current and
      // try the show once that turn has settled; a focus move meanwhile cancels it, and
      // focus remains a usable Page-map arrival if the browser still refuses the preview.
      if (!(error instanceof DOMException) || error.name !== "InvalidStateError")
        throw error;
      if (retry)
        requestAnimationFrame(() => {
          if (previewMarginElement === button && button.isConnected)
            showPreview(entry, button, false);
        });
    } finally {
      previewShowing = false;
    }
  }
  placeThreadPreview();
  refreshHighlight();
  for (const row of rows.values())
    syncReadingRelation(row, primaryReading(row.lfEntry));
  for (const button of readingMarginElements.values())
    syncReadingRelation(button, button.lfChoice);
  paintKeys();
}

function togglePinned(entry, button) {
  if (pinnedKey === entry.key && previewMarginElement === button) {
    pinnedKey = null;
    closePreview();
    return;
  }
  pinnedKey = entry.key;
  showPreview(entry, button);
  const reply = previewList.querySelector("textarea");
  if (reply) landInConversation(reply);
}

export function closePreview(returnFocus = false) {
  clearThreadTransition();
  const button = previewMarginElement;
  pinnedKey = null;
  forcedInlineKey = null;
  forcedInlineOptionsKey = null;
  previewEntry = null;
  previewMarginElement = null;
  previewReferenceSeen = false;
  if (preview.matches(":popover-open")) preview.hidePopover();
  refreshHighlight();
  for (const row of rows.values())
    syncReadingRelation(row, primaryReading(row.lfEntry));
  for (const reading of readingMarginElements.values())
    syncReadingRelation(reading, reading.lfChoice);
  if (returnFocus) {
    if (button?.isConnected && button.checkVisibility())
      button.focus({ preventScroll: true });
    else if (button?.lfEntry) focusMapControl(button.lfEntry);
  }
  paintKeys();
}

// The card and its owning margin element cluster are one page-map stack even though the card
// is hoisted into the chrome. Expose the current rung to the one keyboard register so
// it can stand ahead of reaction and navigation modes, preserving the local surface's
// old order without another keydown listener. One press closes only the deepest rung.
export function keyboardRung({ atFocus = true } = {}) {
  const active = focused();
  const host = closestAcross(active, "[data-lf-margin-for]");
  if (
    preview.matches(":popover-open") &&
    (!atFocus ||
      preview.contains(active) ||
      (previewMarginElement && host?.contains(previewMarginElement)))
  )
    return {
      does: "Close the thread card",
      says: "close thread",
      out: () => closePreview(true),
    };
  const optionsHost = atFocus ? host : hosts.get(expandedOptionsKey);
  if (optionsHost?.lfEntry?.key === expandedOptionsKey)
    return {
      does: "Fold the secondary page actions",
      says: "close options",
      out: () => setOptionsOpen(optionsHost.lfEntry, false, { returnFocus: true }),
    };
  return null;
}

function activate(item, entry, { focusMap = true } = {}) {
  if (expandedOptionsKey && expandedOptionsKey !== entry.key)
    setOptionsOpen(entry, false);
  closePreview();
  if (sheet.open) {
    sheetCloseOwnsFocus = true;
    sheet.close();
  }
  const landsOnTarget = focusMap && !entryHasMarginHost(entry);
  if (focusMap && !landsOnTarget) focusMapControl(entry);
  item.activate();
  // A Page-map-only location has no margin control to receive the handoff. Reveal its
  // target first, then lend that authored element a programmatic tab stop so keyboard
  // focus and the visible arrival name the same place.
  if (landsOnTarget && entry.target?.isConnected) focusDestination(entry.target);
}

function openThreadChoice(entry, button) {
  const choice = threadReading(entry);
  if (!choice) return;
  if (panelIsOpen()) {
    activate(choice.items[0], entry, { focusMap: false });
    return;
  }
  if (expandedOptionsKey && expandedOptionsKey !== entry.key)
    setOptionsOpen(entry, false);
  togglePinned(entry, button);
}

export function openInlineThread(id, transition = null) {
  const itemId = marginThreadItem(threadList().find((t) => t.root.id === id));
  const entry = pageMapEntries.find((candidate) =>
    candidate.items.some((item) => item.id === itemId),
  );
  if (!entry || designOn || panelIsOpen()) return null;
  const choice = threadReading(entry);
  if (!choice) return null;
  const previousForcedOptionsKey = forcedInlineOptionsKey;
  const transfersPreview = preview.matches(":popover-open");
  forcedInlineKey = entry.key;
  forcedInlineOptionsKey = null;
  // Reuse an open card as the thread walk changes targets. Hiding and showing the same
  // popover in one keyboard turn leaves its delayed close event free to clear the new
  // owner's return route.
  if (transfersPreview) {
    previewEntry = entry;
    pinnedKey = entry.key;
  }
  if (previousForcedOptionsKey && expandedOptionsKey === previousForcedOptionsKey)
    setOptionsOpen(null, false, { preservePreview: transfersPreview });
  let button = threadMarginElement(entry);
  if (!button?.checkVisibility()) {
    forcedInlineOptionsKey = expandedOptionsKey === entry.key ? null : entry.key;
    if (forcedInlineOptionsKey)
      setOptionsOpen(entry, true, { preservePreview: transfersPreview });
    else renderMargin();
    button = threadMarginElement(entry);
  }
  if (!button?.isConnected) {
    const optionsKey = forcedInlineOptionsKey;
    forcedInlineKey = null;
    forcedInlineOptionsKey = null;
    if (previewEntry) closePreview();
    if (optionsKey && expandedOptionsKey === optionsKey) setOptionsOpen(null, false);
    return null;
  }
  pinnedKey = entry.key;
  showPreview(entry, button);
  const item = [...previewList.children].find(
    (candidate) => candidate.dataset.lfMarginElement === itemId,
  );
  item?.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
  if (transition) scheduleThreadTransition(transition, entry);
  return item?.querySelector(".lf-conversation-thread") ?? null;
}

// A route that starts on the page stays on the page while that thread has an inline
// address. Widget-local surfaces are already rendered, while a living-margin thread is
// opened on demand. Threads remains the complete fallback for a detached or otherwise
// unaddressable conversation. Callers choose only the landing within the conversation;
// this function owns the surface choice so a mark, its accessibility note, and t/T
// cannot drift into different policies.
export function openPageThread(id, { focus = "reply" } = {}) {
  if (!panelIsOpen()) {
    const local = focusSurface(id, { focus });
    if (local) {
      const optionsKey = forcedInlineOptionsKey;
      closePreview();
      if (optionsKey && expandedOptionsKey === optionsKey) setOptionsOpen(null, false);
      scrollToThread(id);
      return local;
    }
    const thread = openInlineThread(id);
    if (thread) {
      const destination =
        focus === "thread"
          ? thread
          : (thread.querySelector("textarea:not([disabled])") ?? thread);
      if (destination === thread) {
        thread.focus({ preventScroll: true });
        thread.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
        scrollToThread(id);
      } else {
        landInConversation(destination);
      }
      return destination;
    }
  }
  showThread(id, { focus });
  return null;
}

function sheetControls(entry) {
  const records = entry.offers
    .flatMap((offered) =>
      controlsOf(offered)
        .filter((control) => entry.shownControls.has(control))
        .map((control) => ({ control, offered })),
    )
    .sort(compareControlRecords);
  return [...new Set(records.map(({ control }) => control))];
}

function sheetItemKey(entry, item) {
  return `${entry.key}:item:${item.id}`;
}

function sheetControlKey(entry, control) {
  const record = marginElementRecord(control);
  return `${entry.key}:${record.owner}:${record.key}`;
}

function syncSheetFace(button, { icon, glyph, label, visibleLabel = label }) {
  let face = button.querySelector(":scope > .lf-margin-kind");
  if (icon) {
    if (!(face instanceof SVGSVGElement) || face.dataset.lfIcon !== icon)
      face = iconElement(icon, "lf-margin-kind");
  } else {
    if (!(face instanceof HTMLSpanElement)) face = document.createElement("span");
    if (face.className !== "lf-margin-kind") face.className = "lf-margin-kind";
    if (face.hasAttribute("data-lf-icon")) face.removeAttribute("data-lf-icon");
    if (face.textContent !== glyph) face.textContent = glyph;
  }
  let text = button.querySelector(":scope > .lf-page-map-action-label");
  if (!text) text = el("span", "lf-page-map-action-label");
  if (text.textContent !== visibleLabel) text.textContent = visibleLabel;
  if (
    button.childNodes.length !== 2 ||
    button.childNodes[0] !== face ||
    button.childNodes[1] !== text
  )
    button.replaceChildren(face, text);
  if (button.getAttribute("aria-label") !== label)
    button.setAttribute("aria-label", label);
}

function syncSheetItem(button, entry, item) {
  button.lfMapEntry = entry;
  button.lfMapItem = item;
  delete button.lfMapControl;
  button.dataset.lfMapItem = item.id;
  delete button.dataset.lfMapMarginElement;
  const label = item.text || entry.title;
  syncSheetFace(button, {
    icon: KINDS[item.kind].icon,
    label: `Open ${KINDS[item.kind].label.toLowerCase()}: ${label}`,
    visibleLabel: label,
  });
  button.disabled = false;
}

function syncSheetControl(button, entry, control) {
  button.lfMapEntry = entry;
  button.lfMapControl = control;
  delete button.lfMapItem;
  delete button.dataset.lfMapItem;
  button.dataset.lfMapMarginElement = sheetControlKey(entry, control);
  const record = marginElementRecord(control);
  button.dataset.lfBehavior = record.behavior;
  button.dataset.lfTone = record.tone;
  button.dataset.lfRole = record.role;
  button.dataset.lfState = record.state;
  syncSheetFace(button, {
    ...(record.icon ? { icon: record.icon } : { glyph: record.glyph }),
    label: record.label,
    visibleLabel: visibleMarginElementLabel(record),
  });
  syncForwardedMarginElementState(button, control);
}

function makeSheetAction(key) {
  const button = el("button", "lf-page-map-action");
  button.type = "button";
  button.dataset.lfMapKey = key;
  button.onclick = () => {
    if (button.lfMapItem) {
      activate(button.lfMapItem, button.lfMapEntry);
      return;
    }
    const control = button.lfMapControl;
    if (!control) return;
    const from = sheetFrom;
    sheetCloseOwnsFocus = true;
    sheet.close();
    // Closing the native modal is synchronous; preserve the source interaction and
    // forward the press before a later state render can retire its real control.
    if (from?.isConnected && from.checkVisibility())
      from.focus({ preventScroll: true });
    control.click();
  };
  return button;
}

function renderSheet() {
  const active = sheet.contains(document.activeElement) ? document.activeElement : null;
  const heldScroll = sheetList.scrollTop;
  const groups = new Map(
    [...sheetList.children].map((group) => [group.dataset.lfMapGroup, group]),
  );
  const wantedGroups = [];
  for (const entry of pageMapEntries) {
    let group = groups.get(entry.key);
    if (!group) {
      group = el("section", "lf-page-map-group");
      group.dataset.lfMapGroup = entry.key;
      group.append(el("h3"), el("div", "lf-page-map-actions"));
    }
    const heading = group.querySelector(":scope > h3");
    if (heading.textContent !== entry.title) heading.textContent = entry.title;
    const actions = group.querySelector(":scope > .lf-page-map-actions");
    const existing = new Map(
      [...actions.children].map((button) => [button.dataset.lfMapKey, button]),
    );
    const controls = sheetControls(entry);
    const controlOwners = new Set(
      controls.map((control) => marginElementRecord(control).owner),
    );
    const items = entry.items.filter(
      (item) => !item.owner || !controlOwners.has(item.owner),
    );
    const wantedActions = [];
    for (const item of items) {
      const key = sheetItemKey(entry, item);
      const button = existing.get(key) ?? makeSheetAction(key);
      syncSheetItem(button, entry, item);
      wantedActions.push(button);
    }
    for (const control of controls) {
      const key = `control:${sheetControlKey(entry, control)}`;
      const button = existing.get(key) ?? makeSheetAction(key);
      syncSheetControl(button, entry, control);
      wantedActions.push(button);
    }
    for (const child of [...actions.children])
      if (!wantedActions.includes(child)) child.remove();
    wantedActions.forEach((button, index) => {
      if (actions.children[index] !== button)
        actions.insertBefore(button, actions.children[index] ?? null);
    });
    // A rewrite's own label says `old → new`, but the location a reader remembers
    // is usually the sentence around it. Index the same text block the passage runtime
    // uses for anchoring, alongside the visible Page-map labels, so a search for either
    // the margin element or its surrounding document words reaches this one group.
    const passage = blockAt(entry.target);
    group.lfMapSearch = [group.textContent, passage ? says(passage) : ""]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
    wantedGroups.push(group);
  }
  for (const child of [...sheetList.children])
    if (!wantedGroups.includes(child)) child.remove();
  wantedGroups.forEach((group, index) => {
    if (sheetList.children[index] !== group)
      sheetList.insertBefore(group, sheetList.children[index] ?? null);
  });
  filterSheet();
  sheetList.scrollTop = heldScroll;
  if (active && (!active.isConnected || !active.checkVisibility()))
    sheetSearch.focus({ preventScroll: true });
}

function filterSheet() {
  const query = sheetSearch.value.trim().toLocaleLowerCase();
  let shown = 0;
  for (const group of sheetList.children) {
    const matches = !query || group.lfMapSearch.includes(query);
    group.hidden = !matches;
    if (matches) shown += 1;
  }
  sheetEmpty.textContent = query
    ? "No matching actions, statuses, or locations"
    : "No margin controls, status indicators, or locations yet";
  sheetEmpty.hidden = shown !== 0;
}

function openSheet(entry = null, { invoker = null, focusSpill = false } = {}) {
  const from = invoker ?? pageMapInvoker();
  sheetTarget = entry?.target ?? null;
  // The command's door owns the return route, not incidental keyboard focus. Page
  // addresses and the map sequence use the Map toggle; overflow names its exact margin element.
  if (!sheet.open) {
    sheetFrom = from;
    sheetSearch.value = "";
  }
  renderSheet();
  if (!sheet.open) sheet.showModal();
  const index = entry
    ? pageMapEntries.findIndex((candidate) => candidate.key === entry.key)
    : -1;
  const group = index < 0 ? null : sheetList.children[index];
  if (group) {
    const listBox = sheetList.getBoundingClientRect();
    const groupBox = group.getBoundingClientRect();
    if (groupBox.top < listBox.top) sheetList.scrollTop -= listBox.top - groupBox.top;
    else if (groupBox.bottom > listBox.bottom)
      sheetList.scrollTop += groupBox.bottom - listBox.bottom;
  }
  const spilled = focusSpill ? from.lfFirstSpilledOption : null;
  const forwarded = spilled?.lfForwardedControl ?? spilled;
  const destination = focusSpill
    ? [...(group?.querySelectorAll(".lf-page-map-action") ?? [])].find(
        (button) =>
          button.lfMapControl === forwarded ||
          spilled?.lfChoice?.items.some((item) => button.lfMapItem?.id === item.id),
      )
    : group?.querySelector(".lf-page-map-action");
  (destination ?? sheetSearch).focus({ preventScroll: true });
  paintKeys();
}
mapButton.onclick = () => openSheet(null, { invoker: pageMapInvoker() });
sheetSearch.addEventListener("input", filterSheet);
sheet.addEventListener("close", () => {
  const from = sheetFrom;
  const focusOwned = sheetCloseOwnsFocus;
  sheetCloseOwnsFocus = false;
  // A dialog delivers `close` in a task of its own, so a reader who reopens the sheet
  // in the same breath — Esc off the overflow route and straight back onto the margin element
  // that named it — is standing in the next opening by the time this arrives. That
  // opening owns the return route and the target the retained context is read from
  // (marginElementContextContains), so a late close must not take either with it: cleared,
  // the reopened sheet stops counting as its target's own surface and the next press
  // inside it stands the reaction down instead of sending it.
  if (sheet.open) return;
  sheetFrom = null;
  sheetTarget = null;
  paintKeys();
  if (focusOwned) return;
  if (from?.isConnected && from.checkVisibility()) from.focus({ preventScroll: true });
  else focusMapControl();
});
previewClose.onclick = () => closePreview(true);
preview.addEventListener("focusin", keepThreadPreviewFocusVisible);
preview.addEventListener("toggle", (event) => {
  if (event.newState !== "closed") return;
  clearThreadTransition();
  if (!previewEntry) return;
  const button = previewMarginElement;
  pinnedKey = null;
  forcedInlineKey = null;
  forcedInlineOptionsKey = null;
  previewEntry = null;
  previewMarginElement = null;
  previewReferenceSeen = false;
  refreshHighlight();
  for (const row of rows.values())
    syncReadingRelation(row, primaryReading(row.lfEntry));
  for (const reading of readingMarginElements.values())
    syncReadingRelation(reading, reading.lfChoice);
  paintKeys();
});
// The row's acknowledgment face is read out of the state projection, so it follows the
// applied log on `lf-actions` rather than the receipt paint: every path that reconciles
// a complete state dispatches that once it has reconciled, and both of the paths that
// paint receipts sit inside one. A repaint driven from the paint instead ran inside the
// panel render the application performs *before* reconciliation, which is early enough
// to read a candidate the same read is about to reject — and it ran inside a dispatch,
// where the fault that candidate throws is reported as an uncaught page error rather
// than rejecting the read.
document.addEventListener("lf-actions", renderMargin);
document.addEventListener("lf-answered", renderMargin);
document.addEventListener("lf-comparison", renderMargin);
// The margin packs its rows a frame after anything moves them — a row registering,
// the column resizing under a diagram that finished or a disclosure that opened — and
// the card was placed from its cluster when it opened. margin-layout.js says when it has
// moved the rows, and the card follows in that same frame, so a reader never sees it
// standing above or below where its controls used to be.
document.addEventListener("lf-margin-layout", () => {
  placeThreadPreview({ remeasure: true });
  scheduleMarginElementLabels();
});
for (const event of ["pointerover", "focusin"])
  document.addEventListener(event, scheduleMarginElementLabels, { capture: true });
document.addEventListener(
  "pointerdown",
  (event) => {
    if (!expandedOptionsKey) return;
    const host = hosts.get(expandedOptionsKey);
    if (
      !host ||
      event.composedPath().includes(host) ||
      event.composedPath().some(inRetainedContext)
    )
      return;
    setOptionsOpen(host.lfEntry, false);
  },
  { capture: true },
);
contributionListeners.add(renderMargin);
document.addEventListener(
  "scroll",
  () => {
    scheduleRoving();
    scheduleThreadPreviewPosition(false, true);
  },
  { capture: true, passive: true },
);
window.addEventListener("resize", () => {
  scheduleThreadPreviewPosition(true);
  schedulePostureRender();
});

export const marginElementChoices = (target) =>
  clusterMarginElements(marginElementHost(target));
export const unfoldedMarginElements = () =>
  expandedOptionsKey ? (hosts.get(expandedOptionsKey) ?? null) : null;
export const foldMarginElementOptions = () => setOptionsOpen(null, false);
export const activeInlineThread = () => {
  const active = focused();
  const direct = active?.closest?.(".lf-conversation-thread[data-thread]");
  if (direct && !panelIsOpen()) return direct;
  if (
    !pinnedKey ||
    previewEntry?.key !== pinnedKey ||
    !preview.matches(":popover-open") ||
    !preview.hasAttribute("data-lf-thread")
  )
    return null;
  const held = preview.contains(active)
    ? active.closest?.(".lf-conversation-thread")
    : null;
  if (held) return held;
  if (active !== previewMarginElement) return null;
  const conversations = previewList.querySelectorAll(
    ".lf-margin-thread .lf-conversation-thread",
  );
  return conversations.length === 1 ? conversations[0] : null;
};

// The margin's parts into the chrome, once it is mounted (chrome.js): the map button beside
// the version chooser, then its own parts in the root.
export function mountMargin() {
  // The first render, once every owner it reads (the version chooser's comparison, the
  // reconciled threads) has evaluated.
  renderMargin();
  commentsEdge.over.addEventListener("change", changePosture);
  versionBtn.before(mapButton);
  foldShelf();
  chromeRoot.append(nav);
  chromeRoot.append(preview);
  chromeRoot.append(sheet);
}
