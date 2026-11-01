/* One current reading and activation capability for every contributed page action.
   The registration owns data and commands; shared control views retain browser
   capabilities, and each subscribed renderer owns its own paint and geometry.
   Changes in one script publish once. Immediate updates settle subscribed renderers
   synchronously before focus or control lookup, without selecting a layout here. */
import { commandRun } from "./keyboard/bindings.js";
import { afterScript } from "./rendering.js";
import { watchCommandAvailability } from "./keyboard/scopes.js";
import {
  normalizeReading,
  contributionCommand,
  contributionOwnsCommand,
  contributionCommandDisabled,
  contributionControl,
  contributionContains,
  contributionHasCurrentLocation,
  forgetContributionControls,
} from "./contribution-controls.js";
import { focusDestination, focused } from "./focus.js";
/** @typedef {import("./contribution-model.js").ReadingOptions} ReadingOptions
 * @typedef {import("./contribution-model.js").ContributionReading} ContributionReading
 * @typedef {import("./contribution-model.js").OwnedEntry} OwnedEntry
 * @typedef {import("./contribution-model.js").ContributionModel} ContributionModel
 * @typedef {"margin" | "page" | "map" | "inline"} ContributionSurface
 * @typedef {{origin?: Element | null, surface?: ContributionSurface | null,
 * input?: "keyboard" | "pointer", focus?: (key: string) => boolean}} ActivationRequest
 * @typedef {ActivationRequest & {entry: OwnedEntry, focus: (key: string) => boolean}} ActivationContext
 * @typedef {(activation: string, context: ActivationContext) => unknown} Activate
 * @typedef {{entry: Exclude<OwnedEntry, {behavior: "status"}>, activate: Activate}} UnscopedAction
 * @typedef {ContributionModel & {source: () => ContributionSource}} ContributionOffer
 * @typedef {{key: string, target: () => Element | null, source: () => Element | null,
 * read: () => ReadingOptions, activate: Activate | undefined,
 * reading: ContributionReading, model: ContributionOffer, unscoped: UnscopedAction[],
 * readingActions: Map<string, (() => unknown) | undefined>,
 * registration: ContributionRegistration,
 * focusRequest: {key: string, surface: ContributionSurface | null} | null}} ContributionSource
 * @typedef {{entry: (key: string) => OwnedEntry | null,
 * control: (key: string, surface?: ContributionSurface | null, visible?: boolean) => Element | null,
 * contains: (node: Node | null) => boolean,
 * hasCurrentLocation: () => boolean,
 * activate: (key: string, context?: ActivationRequest) => boolean,
 * activateReading: (id: string) => boolean,
 * focus: (key: string, cause: Parameters<typeof focusDestination>[1], surface?: ContributionSurface | null) => boolean,
 * update: (options?: {immediate?: boolean, focus?: string | null}) => void,
 * unregister: () => void}} ContributionRegistration
 */
/** @param {unknown} value */
const text = (value) => String(value ?? "").trim();
let publishing = 0;
/** @param {{key: string, read: () => ReadingOptions, activate: Activate | undefined}} offered
 * @param {ContributionReading | null} previous @param {() => ContributionSource} source */
function readPublication(offered, previous, source) {
  // A command's control lookup cannot settle an older update during normalization.
  publishing++;
  try {
    const declared = offered.read();
    const reading = normalizeReading(declared, offered.key, previous);
    /** @type {UnscopedAction[]} */
    const unscoped = [];
    for (const entry of reading.entries) {
      if (entry.behavior === "status" || contributionOwnsCommand(entry)) continue;
      const activate = offered.activate;
      if (!activate)
        throw new TypeError(
          "An unscoped contribution action needs an activate function",
        );
      unscoped.push({ entry, activate });
    }
    const readingActions = new Map(
      (declared.readings ?? []).map(({ id, activate }) => [id, activate]),
    );
    const { readings, ...fields } = reading;
    const model = Object.freeze({
      key: offered.key,
      reading: Object.freeze({ ...fields, hasReadings: readings.length > 0 }),
      source,
    });
    return { reading, readingActions, unscoped, model };
  } finally {
    publishing--;
  }
}
/** @param {ContributionSource} offered */
function publishReading(offered) {
  Object.assign(
    offered,
    readPublication(offered, offered.reading, offered.model.source),
  );
}

/** @type {Set<ContributionSource>} */
const contributions = new Set();
/** @type {Set<(options: {immediate: boolean}) => void>} */
const listeners = new Set();
let owed = false;
const changed = () => {
  owed = true;
  afterScript(settle);
};
function settle({ immediate = false } = {}) {
  if (!owed || publishing) return;
  owed = false;
  for (const listener of listeners) listener({ immediate });
}

export const contributionEntries = () => contributions.values();
// Private command closures are invalidated by paintKeys. Refresh only a changed
// projection, before native controls and shortcut attributes consume that reading.
watchCommandAvailability(() => {
  for (const offered of contributions)
    if (
      offered.reading.entries.some(
        (entry) =>
          contributionOwnsCommand(entry) &&
          entry.disabled !== contributionCommandDisabled(entry),
      )
    )
      offered.registration.update({ immediate: true });
});
// A render that reads every contribution presents whatever change was owed.
export function presentingContributions() {
  owed = false;
}
/** @param {(options: {immediate: boolean}) => void} listener */
export function watchContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** @typedef {Element | null | (() => Element | null)} ContributionTarget */
/** @param {{key: string, target: ContributionTarget, source?: ContributionTarget,
 * read: () => ReadingOptions, activate?: Activate}} options @returns {ContributionRegistration} */
export function registerContribution({ key, target, source = target, read, activate }) {
  const owner = text(key);
  if (!owner) throw new TypeError("A contribution needs a key");
  // A target is an element or a function returning the one that anchors the action
  // now; consumers call it each time, so a function target follows its live anchor.
  const targetOf = typeof target === "function" ? target : () => target;
  const sourceOf =
    source === target ? targetOf : typeof source === "function" ? source : () => source;
  const sourceCapability = () => offered;
  const publication = readPublication(
    { key: owner, read, activate },
    null,
    sourceCapability,
  );

  /** @param {string} entryKey */
  const entry = (entryKey) =>
    offered.reading.entries.find((candidate) => candidate.key === entryKey) ?? null;
  /** @param {string} entryKey @param {ContributionSurface | null} surface @param {boolean} visible */
  const control = (entryKey, surface = null, visible = false) => {
    settle();
    return contributionControl(offered, entryKey, surface, visible);
  };
  /** @type {string | null} */
  let owedFocus = null;
  const landFocus = () => {
    const key = owedFocus;
    owedFocus = null;
    offered.focusRequest = null;
    if (key != null) registration.focus(key, "move");
  };
  // An explicit arrival materializes the current surface before its retained control
  // is read. The request is mechanical and never enters the immutable contribution.
  /** @param {string} entryKey @param {ContributionSurface | null} surface
   * @param {(destination: Element) => boolean} move */
  const arrive = (entryKey, surface, move) => {
    const request = { key: text(entryKey), surface };
    const previous = offered.focusRequest;
    offered.focusRequest = request;
    try {
      changed();
      settle({ immediate: true });
      const destination = control(request.key, surface, true);
      if (!destination) return false;
      return move(destination);
    } finally {
      if (offered.focusRequest === request) offered.focusRequest = previous;
    }
  };
  /** @type {ContributionRegistration} */
  const registration = Object.freeze({
    entry(entryKey) {
      return entry(text(entryKey));
    },
    control,
    contains(node) {
      return contributionContains(offered, node);
    },
    hasCurrentLocation() {
      return contributionHasCurrentLocation(offered);
    },
    activate(entryKey, context = {}) {
      if (!contributions.has(offered)) return false;
      const current = entry(text(entryKey));
      if (
        !current ||
        !current.visible ||
        (contributionOwnsCommand(current)
          ? contributionCommandDisabled(current)
          : current.disabled) ||
        current.behavior === "status"
      )
        return false;
      const originOwnsFocus = context.origin == null || context.origin === focused();
      /** @param {string} key */
      const focusCurrentSurface = (key) =>
        arrive(key, context.surface ?? null, (destination) => {
          if (context.focus) return context.focus(key);
          focusDestination(destination, "return");
          return true;
        });
      const activationContext = {
        ...context,
        entry: current,
        focus: originOwnsFocus ? focusCurrentSurface : () => false,
      };
      const command = contributionCommand(current);
      if (command) commandRun(command.row, command.binding)?.();
      else {
        const action = offered.unscoped.find(({ entry }) => entry === current);
        if (!action) return false;
        action.activate(action.entry.activation, activationContext);
      }
      return true;
    },
    activateReading(id) {
      const activate = offered.readingActions.get(id);
      if (!activate) return false;
      activate();
      return true;
    },
    // Puts the user on the entry's control, saying what moved them (focus.js,
    // `focusDestination`).
    focus(entryKey, cause, surface = null) {
      return arrive(entryKey, surface, (destination) => {
        focusDestination(destination, cause);
        return true;
      });
    },
    // A focus asked for with an update lands when the script's render does, on the
    // control that render leaves: two updates in one script (an undo shown pending, then
    // its publication) render once rather than painting the step between them.
    update({ immediate = false, focus = null } = {}) {
      publishReading(offered);
      if (focus != null) {
        owedFocus = text(focus);
        offered.focusRequest = { key: owedFocus, surface: null };
        afterScript(landFocus);
      }
      changed();
      if (immediate) {
        settle({ immediate: true });
      }
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      forgetContributionControls(offered);
      changed();
    },
  });
  /** @type {ContributionSource} */
  const offered = {
    key: owner,
    target: targetOf,
    source: sourceOf,
    read,
    activate,
    ...publication,
    registration,
    focusRequest: null,
  };
  contributions.add(offered);
  changed();
  return registration;
}
