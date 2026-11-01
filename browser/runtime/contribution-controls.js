/* Shared contribution controls. Records carry no browser capabilities; this owner
   retains their command scopes and presented controls, independently of the renderer
   that seats them. Every projection uses this directory for control, focus and
   containment, so a producer updates one registration whichever surface shows it. */
import { renderedUnder } from "./shadow-tree.js";
import { html, render } from "/runtime/framework.js";
import { iconTemplate } from "./icons.js";
import { HOLDS_WORD } from "./held-word.js";
import { progressFace, workflowWord } from "./thread/workflow.js";
import { agentSays, saidBy, voiced } from "./voice.js";
import { agentName } from "./semantic-state.js";
import { elementDirective, offer } from "./widget-elements.js";
import { keeps, inlineStyle } from "./keeps.js";
import { pressIsKeyboardActivation } from "./pointer.js";
import { currentLocationIn, focusDestination, nativeFocusTarget } from "./focus.js";
import { agentArrivalDuration, reducedMotion } from "./motion.js";
import { isCommandScope, projectCommandScope } from "./keyboard/scopes.js";
import {
  commandAvailable,
  commandBinding,
  commandRoutes,
  controlAvailabilityOutput,
} from "./keyboard/bindings.js";
import {
  isContributionEntry,
  contributionEntry as normalizeContributionEntry,
  normalizeContributionReading,
  visibleContributionEntryLabel,
} from "./contribution-model.js";
/** @typedef {import("./contribution-model.js").EntryInput} EntryInput
 * @typedef {import("./contribution-model.js").ContributionEntry} Entry
 * @typedef {import("./contribution-model.js").OwnedEntry} OwnedEntry
 * @typedef {Entry & {owner?: string}} PresentedEntry
 * @typedef {import("./contribution-model.js").ReadingOptions} ReadingOptions
 * @typedef {import("./contribution-model.js").ContributionReading} ContributionReading
 * @typedef {import("./contributions.js").ContributionSource} ContributionSource
 * @typedef {import("./contributions.js").ContributionSurface} Surface
 * @typedef {import("./keyboard/scopes.js").CommandCapability} CommandScope
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
/** @template {object} R @param {R} record @param {EntryInput} declared */
function bindScope(record, declared) {
  const scope = commandScopes.get(declared) ?? declared.scope;
  if (scope != null) commandScopes.set(record, scope);
  if (contributionOwnsCommand(declared)) commandEntries.add(record);
  return record;
}

/** @param {EntryInput} offered */
export function contributionEntry(offered) {
  const scope = commandScopes.get(offered) ?? offered.scope;
  if (scope != null && !isCommandScope(scope))
    throw new TypeError("A margin entry scope needs a commandScope capability");
  const command = entryCommand(scope, offered.activation);
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
      (commandScopes.get(entry) ?? entry.scope) === commandScopes.get(prior)
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
/** @type {WeakMap<Element, string[]>} */
const contributorClasses = new WeakMap();

/** Create the native host for one generated margin entry reading. */
/** @param {Entry} record @param {string} [className] */
function createContributionControl(record, className = "") {
  return offer(record.behavior === "status" ? "span" : "button", className);
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
export function contributionControlKey(control) {
  const { owner, key } = contributionEntryRecord(control);
  return JSON.stringify([owner, key]);
}

/** @param {Element} control */
export function contributionEntrySource(control) {
  const offered = controlContributions.get(control);
  if (!offered) return null;
  return offered.source();
}

// Agent workflow is projection state. One claim gets one shared arrival window so the
// independently rendered Margin and Page Map carriers join rather than replay its pulse.
/** @type {WeakMap<Element, AgentDescription>} */
const agentWorkflowDescriptions = new WeakMap();
/** @type {Map<string, number>} */
const claimArrivals = new Map();
/** @type {WeakMap<Element, string>} */
const controlArrivals = new WeakMap();
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

/** @param {Element} control @param {import("./framework/application.js").Workflow | null | undefined} receipt */
function syncAgentArrival(control, receipt) {
  if (!receipt || progressFace(receipt) !== "working") {
    control.removeAttribute("data-lf-agent-arrival");
    return;
  }
  const claim = JSON.stringify([receipt.subject.kind, receipt.subject.id, receipt.id]);
  let began = claimArrivals.get(claim);
  if (began === undefined) {
    began = performance.now();
    claimArrivals.set(claim, began);
  }
  const elapsed = performance.now() - began;
  if (controlArrivals.get(control) === claim) return;
  controlArrivals.set(control, claim);
  if (elapsed >= agentArrivalDuration() || reducedMotion()) return;
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
    control.removeAttribute("title");
    paintLabelMore(control, null);
    return;
  }
  const record = records.get(control);
  // What the title says beyond the label, which a margin entry's label says too, so a
  // finger holding the entry reads all of it, each word said by whoever says it.
  const more = [
    reading.title !== record?.label && reading.title,
    reading.stage && reading.word,
    reading.stage && reading.detail && agentSays(reading.detail),
  ]
    .flatMap((part) => (part ? [part] : []))
    .flatMap((part, index) => (index ? [" · ", part] : [part]));
  paintLabelMore(control, more);
  if (!reading.stage) {
    for (const [attribute, value] of Object.entries({
      "aria-description": reading.description,
      title: reading.title,
    })) {
      keeps(control, attribute, value);
    }
    return;
  }
  const work = [reading.word?.text, reading.detail].filter(Boolean).join(" · ");
  keeps(
    control,
    "aria-description",
    [reading.description, work].filter(Boolean).join(" · "),
  );
  keeps(
    control,
    "title",
    [
      record?.title ?? record?.label,
      reading.title !== (record?.title ?? record?.label) && reading.title,
      work,
    ]
      .filter(Boolean)
      .join(" · "),
  );
}

/** @param {Element} control @param {import("./voice.js").Words | null} more */
function paintLabelMore(control, more) {
  /** @type {HTMLElement | null} */
  const line = control.querySelector(
    ":scope > .lf-margin-entry-label > .lf-margin-entry-more",
  );
  if (line) render(voiced(more ?? []), line);
}

/** @param {Element} control @param {string | null} description @param {string | null} title */
function syncAgentDescriptionBase(control, description, title) {
  Object.assign(agentWorkflowDescription(control), { description, title });
  paintAgentDescription(control);
}

/** @param {Element} control @param {import("./framework/application.js").Workflow | null | undefined} receipt */
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

// Whether a reading carries agent content the user has not taken in: the same
// Thread `unread` the panel and the margin paint, as one attribute both surfaces share.
/** @param {Element} control @param {number} count */
export function syncContributionUnread(control, count) {
  control.toggleAttribute("data-lf-unread", Boolean(count));
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
// it directly; templates bind `${contributionReceipts(receipt, awaitsUser)}`.
/** @param {Element} control @param {import("./framework/application.js").Workflow | null | undefined} receipt @param {boolean} awaitsUser */
export function presentContributionReceipts(control, receipt, awaitsUser) {
  syncContributionAgentWorkflow(control, receipt);
  syncContributionTurn(control, awaitsUser);
}
export const contributionReceipts = elementDirective(
  "contributionReceipts",
  presentContributionReceipts,
);

/** @param {HTMLElement} control @param {EntryInput | PresentedEntry} offered @param {HostOptions} [options] */
export function presentContributionEntry(control, offered, options = {}) {
  const record = presentContributionHost(control, offered, options);
  if (Object.hasOwn(options, "selected"))
    syncContributionSelection(control, options.selected);
  // Its label shows to a resting pointer and the keyboard, and to a finger holding it.
  control.classList.toggle("lf-margin-entry", true);
  control.classList.toggle(HOLDS_WORD, true);
  const priorClasses = contributorClasses.get(control) ?? [];
  const nextClasses = record.className?.split(/\s+/).filter(Boolean) ?? [];
  for (const name of priorClasses)
    if (!nextClasses.includes(name)) control.classList.toggle(name, false);
  for (const name of nextClasses) control.classList.toggle(name, true);
  contributorClasses.set(control, nextClasses);
  const visibleLabel = visibleContributionEntryLabel(record);
  const glyph = record.icon
    ? iconTemplate(record.icon)
    : html`<span class="lf-margin-entry-glyph" aria-hidden="true"
        >${record.glyph}</span
      >`;
  render(
    html`${glyph}<span class="lf-margin-entry-space" aria-hidden="true"> </span
      ><span class="lf-margin-entry-label" aria-hidden="true"
        ><span class="lf-margin-entry-label-word"
          >${
            record.voice ? voiced(saidBy(record.voice, visibleLabel)) : visibleLabel
          }</span
        >${
          record.context
            ? html`<span class="lf-margin-entry-context"
                >${voiced(record.context)}</span
              >`
            : null
        }<span class="lf-margin-entry-more"></span></span
      >${
        record.count > 1
          ? html`<span class="lf-margin-count" aria-hidden="true"
              >${record.count}</span
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
  const names = surface ? [surface] : ["margin", "page", "map", "inline"];
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

/** Activate the current record and retain focus through its current surface: the
 *  activation's `focus(key)` hands the user on from the control they pressed to the
 *  entry `key` names, which is a return (focus.js, `focusDestination`). `reveal` shows a
 *  destination its surface hides first, as the margin does a row annotations hide. */
/** @param {ControlActivation} activation @param {((control: Element) => unknown) | null} reveal */
export function activateContributionControl(
  { offered, entry, control, surface, event },
  reveal = null,
) {
  return offered.registration.activate(entry.key, {
    origin: control,
    surface,
    input: pressIsKeyboardActivation(event) ? "keyboard" : "pointer",
    focus: (key) => {
      const destination = offered.registration.control(key, surface, true);
      if (!destination) return false;
      reveal?.(destination);
      focusDestination(destination, "return");
      return true;
    },
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
