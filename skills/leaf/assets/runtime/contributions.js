/* One current reading and activation capability for every contributed page action.
   The registration owns data and commands; shared control views retain browser
   capabilities, and each subscribed renderer owns its own paint and geometry.
   Changes in one script publish once. Immediate updates settle subscribed renderers
   synchronously before focus or control lookup, without selecting a layout here. */
import { afterScript } from "./rendering.js";
import { focused } from "./keyboard/scopes.js";
import {
  normalizeReading,
  contributionControl,
  contributionContains,
  forgetContributionControls,
} from "./contribution-controls.js";
const text = (value) => String(value ?? "").trim();
// A registration publishes its data once per update. Both projections use those
// same records; only this registry resolves their live activation capability.
const contributionSources = new WeakMap();
export const contributionSource = (model) => contributionSources.get(model);
function publishReading(offered) {
  const declared = offered.read();
  offered.readingActions = new Map(
    (declared.readings ?? []).map(({ id, activate }) => [id, activate]),
  );
  offered.reading = normalizeReading(declared, offered.key);
  const { readings, ...reading } = offered.reading;
  offered.model = Object.freeze({
    key: offered.key,
    reading: Object.freeze({ ...reading, hasReadings: readings.length > 0 }),
  });
  contributionSources.set(offered.model, offered);
}

const contributions = new Set();
const listeners = new Set();
let owed = false;
const changed = () => {
  owed = true;
  afterScript(settle);
};
function settle({ immediate = false } = {}) {
  if (!owed) return;
  owed = false;
  for (const listener of listeners) listener({ immediate });
}

export const contributionEntries = () => contributions.values();
// A render that reads every contribution presents whatever change was owed.
export function presentingContributions() {
  owed = false;
}
export function watchContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function registerContribution({ key, target, source = target, read, activate }) {
  const owner = text(key);
  if (!owner) throw new TypeError("A contribution needs a key");
  if (typeof read !== "function")
    throw new TypeError("A contribution needs a read function");
  if (typeof activate !== "function")
    throw new TypeError("A contribution needs an activate function");
  const offered = { key: owner, target, source, read, activate, reading: null };
  publishReading(offered);
  contributions.add(offered);
  changed();

  const entry = (entryKey) =>
    offered.reading.entries.find((candidate) => candidate.key === entryKey) ?? null;
  const control = (entryKey, surface = null, visible = false) => {
    settle();
    return contributionControl(offered, entryKey, surface, visible);
  };
  let owedFocus = null;
  const landFocus = () => {
    const key = owedFocus;
    owedFocus = null;
    if (key != null) registration.focus(key);
  };
  const registration = Object.freeze({
    entry(entryKey) {
      return entry(text(entryKey));
    },
    control,
    contains(node) {
      return contributionContains(offered, node);
    },
    activate(entryKey, context = {}) {
      const current = entry(text(entryKey));
      if (
        !current ||
        !current.visible ||
        current.disabled ||
        current.behavior === "status"
      )
        return false;
      const originOwnsFocus = context.origin == null || context.origin === focused();
      const focusCurrentSurface =
        context.focus ??
        ((key) => {
          const destination = control(key, context.surface ?? null, true);
          if (!destination) return false;
          destination.focus({ preventScroll: true });
          return true;
        });
      offered.activate(current.activation, {
        ...context,
        entry: current,
        focus: originOwnsFocus ? focusCurrentSurface : () => false,
      });
      return true;
    },
    activateReading(id) {
      const activate = offered.readingActions.get(id);
      if (!activate) return false;
      activate();
      return true;
    },
    focus(entryKey, surface = null) {
      const destination = control(text(entryKey), surface, true);
      if (!destination) return false;
      destination.focus({ preventScroll: true });
      return true;
    },
    // A focus asked for with an update lands when the script's render does, on the
    // control that render leaves: two updates in one script (an undo shown pending, then
    // its publication) render once rather than painting the step between them.
    update({ immediate = false, focus = null } = {}) {
      publishReading(offered);
      changed();
      if (immediate) {
        settle({ immediate: true });
      }
      if (focus != null) {
        owedFocus = focus;
        afterScript(landFocus);
      }
    },
    unregister() {
      if (!contributions.delete(offered)) return;
      forgetContributionControls(offered);
      changed();
    },
  });
  offered.registration = registration;
  return registration;
}
