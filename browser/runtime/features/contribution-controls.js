/* Shared contribution controls. Records carry no browser capabilities; this owner
   retains their command scopes and presented controls, independently of the renderer
   that seats them. Every projection uses this directory for control, focus and
   containment, so a producer updates one registration whichever surface shows it. */
import { closestAcross, renderedUnder } from "../lib/shadow-tree.js";
import { html, render } from "/vendor/lit.js";
import { untracked } from "/vendor/signals-core.js";
import { iconTemplate } from "../lib/icons.js";
import { progressFace, workflowWord } from "../records/thread/workflow.js";
import { ownedObligationControl } from "../records/obligations/answer.js";
import { agentSays, linesOf, saidBy, voiced } from "../base/voice.js";
import { agentName, readPart } from "../state/semantic-state.js";
import { elementDirective, offerActionElement } from "../lib/controls.js";
import { keeps, inlineStyle } from "../lib/keeps.js";
import { pressIsKeyboardActivation } from "../base/pointer.js";
import { currentLocationIn, nativeFocusTarget } from "../dom/focus.js";
import { reducedMotion } from "../dom/motion.js";
import { motionTime } from "../lib/motion-timing.js";
import {
  commandDeclarationsWithin,
  projectCommandScope,
  statedScope,
} from "../dom/keyboard/scopes.js";
import {
  commandAvailable,
  commandBinding,
  commandRoutes,
  controlAvailabilityOutput,
} from "../dom/keyboard/bindings.js";
import {
  isContributionEntry,
  contributionEntry as normalizeContributionEntry,
  normalizeContributionReading,
  visibleContributionEntryLabel,
} from "../base/contribution-model.js";
/** An entry as a contributor offers it, its command scope by the keyboard's own contract
 * (dom/keyboard/scopes.js), whose rows carry the routes and scopes base can't name.
 * @typedef {Omit<import("../base/contribution-model.js").EntryInput, "scope"> & {
 * scope?: NonNullable<Element["lfCommands"]> | import("../dom/keyboard/scopes.js").CommandCapability | null | undefined}} EntryInput
 * @typedef {import("../base/contribution-model.js").ContributionEntry} Entry
 * @typedef {import("../base/contribution-model.js").OwnedEntry} OwnedEntry
 * @typedef {Entry & {owner?: string}} PresentedEntry
 * @typedef {Omit<import("../base/contribution-model.js").ReadingOptions, "entries"> & {entries?: readonly EntryInput[]}} ReadingOptions
 * @typedef {import("../base/contribution-model.js").ContributionReading} ContributionReading
 * @typedef {import("./contributions.js").ContributionSource} ContributionSource
 * @typedef {import("./contributions.js").ContributionSurface} Surface
 * @typedef {import("../dom/keyboard/scopes.js").CommandCapability} CommandScope
 * @typedef {{accessibleLabel?: string | null, relatedControlIds?: readonly string[],
 * writesRelation?: boolean, writesSeat?: boolean, selected?: boolean}} HostOptions
 * @typedef {{description: string | null, title: string | null,
 * stage: ReturnType<typeof progressFace>, word: ReturnType<typeof workflowWord>, detail: string | null}} AgentDescription
 * @typedef {{offered: ContributionSource, entry: OwnedEntry, control: Element, surface: Surface, event: UIEvent}} ControlActivation
 */
// Scopes belong to the browser declaration, not the immutable model record.
/** @type {WeakMap<object, CommandScope>} */
const commandScopes = new WeakMap();
/** @type {WeakSet<object>} */
const commandEntries = new WeakSet();
/** @param {object | undefined} record */
export const contributionOwnsCommand = (record) =>
  record !== undefined && commandEntries.has(record);
// The key this module projects an entry's scope onto its control under.
const CONTRIBUTION_ENTRY = Symbol("contribution entry");
// An entry's scope: the one kept for its record, or the one its `scope` states, which
// a package gives as the object its element holds as `lfCommands` (`statedScope`).
/** @param {EntryInput} declared */
const scopeOf = (declared) =>
  commandScopes.get(declared) ??
  (declared.scope == null ? undefined : statedScope(declared.scope));
/** @template {object} R @param {R} record @param {EntryInput} declared */
function bindScope(record, declared) {
  const scope = scopeOf(declared);
  if (scope) commandScopes.set(record, scope);
  if (contributionOwnsCommand(declared)) commandEntries.add(record);
  return record;
}

/** @param {EntryInput} offered */
export function contributionEntry(offered) {
  const command = entryCommand(scopeOf(offered), offered.activation);
  if (command) commandEntries.add(offered);
  return bindScope(
    normalizeContributionEntry(
      contributionOwnsCommand(offered)
        ? {
            ...offered,
            disabled: commandDisabled(command),
          }
        : offered,
    ),
    offered,
  );
}

// An entry may project a declared command as its native action. The stable command
// id in activation keeps every projection on that callback, including its disabled
// reading, while the native adapter retains surface and gesture intent.
/** @param {EntryInput | Entry | undefined} record */
export function contributionCommand(record) {
  if (!record || !contributionOwnsCommand(record)) return null;
  const scope = commandScopes.get(record);
  return entryCommand(scope, record.activation);
}
// Which entries answer `widget`'s question: those that run one of the decision commands
// the widget and its contents declare for it, which an On Me card offers for it
// (records/obligations/view.js). The declaration decides, not the command's availability
// now, which waits on the very control the entry draws.
/** @param {Element} widget @returns {(record: EntryInput | Entry) => boolean} */
export function answersTo(widget) {
  /** @type {Set<object> | undefined} */
  let rows;
  return (record) => {
    const command = contributionCommand(record);
    if (!command || !(command.route ?? command.row).decision) return false;
    rows ??= new Set(
      commandDeclarationsWithin(widget)
        .filter(({ source }) => ownedObligationControl(widget, source))
        .flatMap(({ scope }) => scope.rows),
    );
    return rows.has(command.row);
  };
}
/** @param {EntryInput | Entry | undefined} record */
export function contributionCommandDisabled(record) {
  const command = contributionCommand(record);
  return contributionOwnsCommand(record) && commandDisabled(command);
}
/** @param {ReturnType<typeof entryCommand>} command */
const commandDisabled = (command) =>
  Boolean(
    !command ||
    (command.scope.scope.when && !command.scope.scope.when()) ||
    !commandAvailable(command.row, command.route),
  );
/** @param {CommandScope | null | undefined} scope @param {string | null | undefined} id */
function entryCommand(scope, id) {
  if (!scope) return null;
  for (const row of scope.scope.rows) {
    if (!row.run && !row.runKey) continue;
    const routes = commandRoutes(row);
    if (!routes.length && row.id === id)
      return { scope, row, route: null, binding: commandBinding(row) };
    const route = routes.find((route) => route.id === id);
    if (route) return { scope, row, route, binding: commandBinding(row, route) };
  }
  return null;
}

/** @param {ReadingOptions} reading @param {string} owner @param {ContributionReading | null} previous */
export function normalizeReading(reading, owner, previous = null) {
  const priorEntries = new Map(
    (previous?.entries ?? []).map((entry) => [entry.key, entry]),
  );
  const entries = (reading.entries ?? []).map((entry) => {
    const prior = priorEntries.get(entry.key);
    if (
      prior &&
      contributionOwnsCommand(prior) &&
      entry.activation === prior.activation &&
      scopeOf(entry) === commandScopes.get(prior)
    )
      commandEntries.add(entry);
    if (!isContributionEntry(entry)) return contributionEntry(entry);
    if (!contributionOwnsCommand(entry)) return entry;
    const { owner: _owner, ...fields } = entry;
    const declaration = { ...fields, scope: commandScopes.get(entry) };
    commandEntries.add(declaration);
    return contributionEntry(declaration);
  });
  const normalized = normalizeContributionReading({ ...reading, entries }, owner);
  const declarations = entries[Symbol.iterator]();
  for (const entry of normalized.entries) {
    const declared = declarations.next();
    if (declared.done) break;
    bindScope(entry, declared.value);
  }
  return normalized;
}

// Primary annotation and inline Thread seats share each native entry. Page Map
// keeps its own modal projection in the presented directory below.
/** @type {WeakMap<ContributionSource, Map<string, HTMLElement>>} */
const contributionControls = new WeakMap();
let relationOrdinal = 0;
/** @type {WeakMap<ContributionSource, Map<Surface, Map<string, Element>>>} */
const presented = new WeakMap();
/** @type {WeakMap<Element, PresentedEntry>} */
const records = new WeakMap();
/** @type {WeakMap<Element, ContributionSource>} */
const controlContributions = new WeakMap();

/** Create the native host for one generated margin entry reading. */
/** @param {Entry} record */
function createContributionControl(record) {
  return offerActionElement(
    document.createElement(record.behavior === "status" ? "span" : "button"),
    "entry",
  );
}

/** @param {Element} control @param {Entry} record */
const contributionControlMatches = (control, record) =>
  record.behavior === "status"
    ? control instanceof HTMLSpanElement
    : control instanceof HTMLButtonElement;

/** @param {Element} control */
export function contributionEntryRecord(control) {
  const record = records.get(control);
  if (!record)
    throw new TypeError("A presented margin control needs a margin entry record");
  return record;
}

/** @param {Element} control */
export function contributionEntrySource(control) {
  const offered = controlContributions.get(control);
  if (!offered) return null;
  return offered.source();
}

// Agent workflow is projection state. One claim gets one shared arrival window so the
// independently rendered Margin and Page Map carriers join rather than replay its pulse.
// The window lasts while a published workflow holds the claim: the first paint after
// the workflows change drops each claim none of them holds, so the page keeps arrivals
// only for unsettled updates, and a claim that comes back arrives anew.
/** @type {WeakMap<Element, AgentDescription>} */
const agentWorkflowDescriptions = new WeakMap();
/** @type {Map<string, number>} */
const claimArrivals = new Map();
/** @type {WeakMap<Element, string>} */
const controlArrivals = new WeakMap();
const publishedWorkflows = readPart((root) => root.effective.workflows);
// The published workflows the kept claims were last checked against.
/** @type {ReturnType<typeof publishedWorkflows> | null} */
let claimsChecked = null;
/** @param {import("../../types/domain.js").Workflow} receipt */
const claimOf = (receipt) =>
  JSON.stringify([receipt.subject.kind, receipt.subject.id, receipt.id]);
function dropSettledClaims() {
  // A control's paint follows its own receipt, not every workflow's.
  const workflows = untracked(publishedWorkflows);
  if (workflows === claimsChecked) return;
  claimsChecked = workflows;
  const held = new Set(workflows.map(claimOf));
  for (const claim of claimArrivals.keys())
    if (!held.has(claim)) claimArrivals.delete(claim);
}
/** @param {Element} control */
function agentWorkflowDescription(control) {
  let reading = agentWorkflowDescriptions.get(control);
  if (!reading) {
    reading = {
      description: control.getAttribute("aria-description"),
      title: control.getAttribute("title"),
      stage: null,
      word: null,
      detail: null,
    };
    agentWorkflowDescriptions.set(control, reading);
  }
  return reading;
}

/** @param {Element} control @param {import("../../types/domain.js").Workflow | null | undefined} receipt */
function syncAgentArrival(control, receipt) {
  dropSettledClaims();
  if (!receipt || progressFace(receipt) !== "working") {
    control.removeAttribute("data-lf-agent-arrival");
    controlArrivals.delete(control);
    return;
  }
  const claim = claimOf(receipt);
  let began = claimArrivals.get(claim);
  if (began === undefined) {
    began = performance.now();
    claimArrivals.set(claim, began);
  }
  const elapsed = performance.now() - began;
  if (controlArrivals.get(control) === claim) return;
  controlArrivals.set(control, claim);
  if (elapsed >= motionTime("--lf-motion-agent-arrival") || reducedMotion()) return;
  inlineStyle(control).setProperty("--lf-agent-arrival-delay", `${-elapsed}ms`);
  keeps(control, "data-lf-agent-arrival", "1");
  control.addEventListener(
    "animationend",
    () => control.removeAttribute("data-lf-agent-arrival"),
    { once: true },
  );
}

/** @param {Element} control */
function paintAgentDescription(control) {
  const reading = agentWorkflowDescriptions.get(control);
  if (!reading) {
    control.removeAttribute("aria-description");
    return;
  }
  const work = reading.stage
    ? [reading.word?.text, reading.detail].filter(Boolean).join(" · ")
    : "";
  keeps(
    control,
    "aria-description",
    [reading.description, work].filter(Boolean).join(" · ") || null,
  );
}

// What an entry says when pointed at (annotations/preview.js): its label, the context its
// projection gives it, and what its title says beyond the label, such as an agent's work
// on it, each word said by whoever says it. A finger holding the entry reads the same.
// It is about the passage it stands beside, which it leaves in view.
/** @this {Element} */
function entryPreview() {
  const record = records.get(this);
  if (!record) return null;
  const label = visibleContributionEntryLabel(record);
  const reading = agentWorkflowDescriptions.get(this);
  // A part the label already says, as a Delivered receipt's stage word does, is
  // said once.
  const more = [
    reading?.title !== record.label && reading?.title,
    reading?.stage && reading.word,
    reading?.stage && reading.detail && agentSays(reading.detail),
  ]
    .flatMap((part) =>
      part && (typeof part === "string" ? part : part.text) !== label ? [part] : [],
    )
    .flatMap((part, index) => (index ? [" · ", part] : [part]));
  return {
    name: record.voice ? voiced(saidBy(record.voice, label)) : label,
    about: closestAcross(this, "[data-lf-margin-for]")?.lfTarget ?? null,
    detail: [
      // A context of several lines says each on its own (base/voice.js, `linesOf`).
      ...(record.context ? linesOf(record.context).map(voiced) : []),
      more.length ? voiced(more) : null,
    ],
  };
}

/** @param {Element} control @param {string | null} description @param {string | null} title */
function syncAgentDescriptionBase(control, description, title) {
  Object.assign(agentWorkflowDescription(control), { description, title });
  paintAgentDescription(control);
}

/** @param {Element} control @param {import("../../types/domain.js").Workflow | null | undefined} receipt */
function syncContributionAgentWorkflow(control, receipt) {
  const paintedStage = progressFace(receipt);
  syncAgentArrival(control, receipt);
  const reading = agentWorkflowDescription(control);
  keeps(control, "data-lf-agent-workflow", paintedStage || null);
  Object.assign(
    reading,
    receipt && paintedStage
      ? {
          stage: paintedStage,
          word: workflowWord(receipt, agentName()),
          detail: receipt.detail,
        }
      : { stage: null, word: null, detail: null },
  );
  paintAgentDescription(control);
}

/** @param {Element} control @param {boolean | undefined} selected */
export function syncContributionSelection(control, selected) {
  control.toggleAttribute("data-lf-target-selected", Boolean(selected));
}

// Whose word a reading is waiting on. Projection state like agent workflow, and written
// the same way: the projection decides it, both surfaces paint the same attribute, and a
// carrier that stops waiting loses it rather than keeping a stale colour. Only the
// user's turn is named, because that is the one a page has to point at; a thread with
// the agent already says so through pickup and work.
/** @param {Element} control @param {boolean} awaitsUser */
function syncContributionTurn(control, awaitsUser) {
  keeps(control, "data-lf-turn", awaitsUser ? "user" : null);
}

/** @param {Element} control @param {EntryInput | PresentedEntry} offered @param {HostOptions} [options] */
export function presentContributionHost(
  control,
  offered,
  {
    accessibleLabel = null,
    relatedControlIds = [],
    writesRelation = true,
    writesSeat = true,
  } = {},
) {
  /** @type {PresentedEntry} */
  const record = isContributionEntry(offered) ? offered : contributionEntry(offered);
  if (control instanceof HTMLButtonElement && record.behavior === "status")
    throw new TypeError("A status margin entry needs a stable span host");
  controlAvailabilityOutput(
    control,
    CONTRIBUTION_ENTRY,
    contributionOwnsCommand(record)
      ? { disabled: control instanceof HTMLButtonElement, ariaDisabled: true }
      : null,
  );
  records.set(control, record);
  keeps(control, "data-lf-margin-entry-key", record.key);
  keeps(control, "data-lf-margin-entry-owner", record.owner || null);
  // The entry's whole identity, which a hold across a projection keys on.
  keeps(
    control,
    "data-lf-margin-entry-identity",
    JSON.stringify([record.owner, record.key]),
  );
  keeps(control, "data-lf-behavior", record.behavior);
  keeps(control, "data-lf-tone", record.tone);
  keeps(control, "data-lf-rank", record.rank);
  keeps(control, "data-lf-state", record.state);
  keeps(control, "data-lf-offer", record.behavior === "status" ? "" : "button");
  keeps(control, "aria-pressed", record.pressed);
  keeps(control, "aria-busy", record.state === "busy" ? "true" : null);
  const relation = record.relation;
  if (writesRelation) {
    keeps(
      control,
      "aria-expanded",
      record.behavior === "disclosure" ? (relation?.expanded ?? false) : null,
    );
    keeps(
      control,
      "aria-controls",
      relation?.kind === "element"
        ? relation.id
        : relation?.kind === "entries" && relatedControlIds.length
          ? relatedControlIds.join(" ")
          : null,
    );
    keeps(control, "aria-haspopup", relation?.popup || null);
  }
  if (control instanceof HTMLButtonElement) {
    const wasStatus = control.getAttribute("role") === "status";
    control.removeAttribute("role");
    if (writesSeat && wasStatus) control.removeAttribute("tabindex");
    if (control.type !== "button") control.type = "button";
    // A pending action can be the user's retained place even while it refuses a
    // second activation. Native disabled buttons cannot hold that place; the immutable
    // record and registration enforce refusal while aria exposes it to the user.
    if (control.disabled) control.disabled = false;
    keeps(control, "aria-disabled", record.disabled);
  } else if (record.behavior === "status") {
    keeps(control, "role", "status");
    control.removeAttribute("aria-disabled");
    if (writesSeat) keeps(control, "tabindex", -1);
  } else {
    keeps(control, "role", "button");
    keeps(control, "aria-disabled", record.disabled);
    if (writesSeat) {
      const target = nativeFocusTarget(control);
      if (target.tabIndex < 0) target.tabIndex = 0;
    }
  }
  keeps(control, "aria-label", accessibleLabel ?? record.accessibleLabel);
  syncAgentDescriptionBase(control, record.description || null, record.title || null);
  projectCommandScope(control, CONTRIBUTION_ENTRY, commandScopes.get(record));
  return record;
}

// Template hosts use the same writer as retained margin controls, and are tracked on
// their surface as every presented control is: `${contributionHost(source, "map",
// record, options)}`. Templates own the body and event bindings; this directive owns
// the record's host attributes and scope.
export const contributionHost = elementDirective(
  "contributionHost",
  (
    control,
    /** @type {ContributionSource} */ source,
    /** @type {Surface} */ surface,
    /** @type {EntryInput | PresentedEntry} */ record,
    /** @type {HostOptions | undefined} */ options = undefined,
  ) => {
    presentContributionHost(control, record, options);
    trackContributionControl(source, surface, record.key, control);
  },
);

// A control's receipts are seat state, not entry semantics: the seat that shows a
// control paints what its projection chose, on every pass, so a control keeps no
// receipt from the seat or the projection it last stood in. Retained controls call
// it directly, or pass `receipt` and `awaitsUser` to `presentContributionEntry` where
// they draw the entry in the same pass; templates bind
// `${contributionReceipts(receipt, awaitsUser)}`.
/** @param {Element} control @param {import("../../types/domain.js").Workflow | null | undefined} receipt @param {boolean} awaitsUser */
export function presentContributionReceipts(control, receipt, awaitsUser) {
  syncContributionAgentWorkflow(control, receipt);
  syncContributionTurn(control, awaitsUser);
}
export const contributionReceipts = elementDirective(
  "contributionReceipts",
  presentContributionReceipts,
);

// An entry's badges stand in one row on its top edge (`.lf-badges`, controls.css): the
// unread dot, for agent content the user has not taken in (the same Thread `unread`
// the panel paints), and its count where it stands for more than one. Like `selected`,
// each receipt (`presentContributionReceipts`), `receipt` and `awaitsUser`, is painted
// where the options carry it, and otherwise left as the seat last painted it.
/** @param {HTMLElement} control @param {EntryInput | PresentedEntry} offered
 * @param {HostOptions & {preview?: import("../base/preview-declaration.js").Read | null, unread?: boolean,
 * receipt?: import("../../types/domain.js").Workflow | null, awaitsUser?: boolean}} [options] */
export function presentContributionEntry(control, offered, options = {}) {
  const record = presentContributionHost(control, offered, options);
  if (Object.hasOwn(options, "selected"))
    syncContributionSelection(control, options.selected);
  if (Object.hasOwn(options, "receipt"))
    syncContributionAgentWorkflow(control, options.receipt);
  if (Object.hasOwn(options, "awaitsUser"))
    syncContributionTurn(control, Boolean(options.awaitsUser));
  // Its label is its preview, which a resting pointer, the keyboard and a finger
  // holding it read (`entryPreview`), unless its projection says what it opens more
  // fully, as a thread's entry previews its threads.
  control.classList.toggle("lf-margin-entry", true);
  control.lfPreview = options.preview ?? entryPreview;
  const glyph = record.icon
    ? iconTemplate(record.icon)
    : html`<span class="lf-margin-entry-glyph" aria-hidden="true"
        >${record.glyph}</span
      >`;
  const counted = record.count > 1;
  render(
    html`${glyph}${
      counted || options.unread
        ? html`<span class="lf-badges" aria-hidden="true"
            >${options.unread ? html`<span class="lf-unread-dot"></span>` : null}${
              counted ? html`<span class="lf-badge-count">${record.count}</span>` : null
            }</span
          >`
        : null
    }`,
    control,
  );
  paintAgentDescription(control);
  return control;
}

/** @param {ContributionSource} offered @param {Surface} surface @param {string} key @param {Element} control */
export function trackContributionControl(offered, surface, key, control) {
  controlContributions.set(control, offered);
  let surfaces = presented.get(offered);
  if (!surfaces) {
    surfaces = new Map();
    presented.set(offered, surfaces);
  }
  let controls = surfaces.get(surface);
  if (!controls) {
    controls = new Map();
    surfaces.set(surface, controls);
  }
  controls.set(key, control);
}

/** @param {ContributionSource} offered @param {Surface} surface @param {ReadonlySet<string>} liveKeys */
export function clearContributionControls(offered, surface, liveKeys) {
  const surfaces = presented.get(offered);
  const controls = surfaces?.get(surface);
  if (!surfaces || !controls) return;
  for (const [key, control] of controls) {
    if (liveKeys.has(key)) continue;
    controls.delete(key);
    const retained = [...surfaces.values()].some((seats) =>
      [...seats.values()].includes(control),
    );
    if (!retained) releaseContributionControl(control);
  }
}

/** @param {ContributionSource} offered @param {string} entryKey @param {Surface | null} surface @param {boolean} visible */
export function contributionControl(
  offered,
  entryKey,
  surface = null,
  visible = false,
) {
  const surfaces = presented.get(offered);
  /** @type {readonly Surface[]} */
  const names = surface ? [surface] : ["margin", "map", "inline"];
  for (const name of names) {
    const control = surfaces?.get(name)?.get(entryKey);
    if (control?.isConnected && (!visible || control.checkVisibility())) return control;
  }
  return null;
}

/** @param {ContributionSource} offered */
const presentedControls = (offered) =>
  [...(presented.get(offered)?.values() ?? [])].flatMap((controls) => [
    ...controls.values(),
  ]);

/** @param {ContributionSource} offered @param {Node | null} node */
export function contributionContains(offered, node) {
  return presentedControls(offered).some((control) => renderedUnder(node, control));
}

/** The registration spans each of its controls, whichever surface presents them.
 * @param {ContributionSource} offered */
export const contributionHasCurrentLocation = (offered) =>
  presentedControls(offered).some(currentLocationIn);

/** @param {Element} control */
function releaseContributionControl(control) {
  controlAvailabilityOutput(control, CONTRIBUTION_ENTRY);
  projectCommandScope(control, CONTRIBUTION_ENTRY, null);
  controlContributions.delete(control);
}
/** @param {ContributionSource} offered */
export function forgetContributionControls(offered) {
  for (const controls of presented.get(offered)?.values() ?? [])
    for (const control of controls.values()) releaseContributionControl(control);
  presented.delete(offered);
}

/** Activate the current record from the control pressed on `surface`.
 *  @param {ControlActivation} activation */
export function activateContributionControl({
  offered,
  entry,
  control,
  surface,
  event,
}) {
  return offered.registration.activate(entry.key, {
    origin: control,
    surface,
    input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
  });
}

/** Materialize the chosen immutable reading while retaining its source's native controls.
 * The returned capability draws an exact owned record, so a selected snapshot never
 * has to recover its control from the source's later reading by a string key.
 * @param {import("./contributions.js").ContributionOffer} offer @param {Surface} surface
 * @param {(activation: ControlActivation) => unknown} activate */
export function materializeContributionControls(offer, surface, activate) {
  const source = offer.source();
  let controls = contributionControls.get(source);
  if (!controls) {
    controls = new Map();
    contributionControls.set(source, controls);
  }
  const directory = controls;
  const entries = offer.reading.entries.filter((entry) => entry.visible);
  const liveKeys = new Set(entries.map((entry) => entry.key));
  for (const key of directory.keys()) if (!liveKeys.has(key)) directory.delete(key);
  /** @param {OwnedEntry} entry */
  const retain = (entry) => {
    let control = directory.get(entry.key);
    let changed;
    if (!control || !contributionControlMatches(control, entry)) {
      control = createContributionControl(entry);
      directory.set(entry.key, control);
      changed = true;
    } else changed = contributionEntryRecord(control) !== entry;
    const native = control;
    native.onclick = (event) =>
      activate({ offered: source, entry, control: native, surface, event });
    trackContributionControl(source, surface, entry.key, native);
    return { entry, control: native, changed };
  };
  const drawn = entries.map(retain);
  clearContributionControls(source, surface, liveKeys);
  /** @param {ReturnType<typeof retain>} view */
  const paint = ({ entry, control, changed }) => {
    const related =
      entry.relation?.kind === "entries"
        ? entry.relation.keys.flatMap((key) => directory.get(key) ?? [])
        : [];
    related.forEach((node, index) => {
      if (!node.id) node.id = `lf-margin-related-${++relationOrdinal}-${index + 1}`;
    });
    if (changed)
      presentContributionEntry(control, entry, {
        relatedControlIds: related.map((node) => node.id),
      });
  };
  drawn.forEach(paint);
  return (/** @type {OwnedEntry} */ entry) => {
    const view = retain(entry);
    paint(view);
    return view.control;
  };
}
