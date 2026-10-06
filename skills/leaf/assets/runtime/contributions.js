/* One current reading and activation capability for every contributed page action.
   The registration owns data and commands; shared control views retain browser
   capabilities, and each subscribed renderer owns its own paint and geometry.
   Changes in one script publish once. Immediate updates settle subscribed renderers
   synchronously before focus or control lookup, without selecting a layout here. */
import { afterScript } from "./rendering.js";
import { focused, watchCommandAvailability } from "./keyboard/scopes.js";
import {
  normalizeReading,
  contributionCommand,
  contributionOwnsCommand,
  contributionCommandDisabled,
  contributionControl,
  contributionContains,
  forgetContributionControls,
} from "./contribution-controls.js";
const text = (value) => String(value ?? "").trim();
// A registration publishes its data once per update. Both projections use those
// same records; only this registry resolves their live activation capability.
const contributionSources = new WeakMap();
let publishing = 0;
export const contributionSource = (model) => contributionSources.get(model);
function publishReading(offered) {
  // A command's availability may look up its retained control while its
  // contribution is being normalized. That lookup must not settle an older
  // update and reenter the annotation renderer with this reading half-built.
  publishing++;
  try {
    const declared = offered.read();
    const normalized = normalizeReading(declared, offered.key, offered.reading);
    if (
      !offered.activate &&
      normalized.entries.some(
        (entry) => entry.behavior !== "status" && !contributionOwnsCommand(entry),
      )
    )
      throw new TypeError("An unscoped contribution action needs an activate function");
    offered.readingActions = new Map(
      (declared.readings ?? []).map(({ id, activate }) => [id, activate]),
    );
    offered.reading = normalized;
    const { readings, ...reading } = offered.reading;
    offered.model = Object.freeze({
      key: offered.key,
      reading: Object.freeze({ ...reading, hasReadings: readings.length > 0 }),
    });
    contributionSources.set(offered.model, offered);
  } finally {
    publishing--;
  }
}

const contributions = new Set();
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
export function watchContributions(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function registerContribution({ key, target, source = target, read, activate }) {
  const owner = text(key);
  if (!owner) throw new TypeError("A contribution needs a key");
  if (typeof read !== "function")
    throw new TypeError("A contribution needs a read function");
  if (activate !== undefined && typeof activate !== "function")
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
    offered.focusRequest = null;
    if (key != null) registration.focus(key);
  };
  // An explicit arrival materializes the current surface before its retained control
  // is read. The request is mechanical and never enters the immutable contribution.
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
  const registration = Object.freeze({
    entry(entryKey) {
      return entry(text(entryKey));
    },
    control,
    contains(node) {
      return contributionContains(offered, node);
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
      const focusCurrentSurface = (key) =>
        arrive(key, context.surface ?? null, (destination) => {
          if (context.focus) return context.focus(key);
          destination.focus({ preventScroll: true });
          return true;
        });
      const activationContext = {
        ...context,
        entry: current,
        focus: originOwnsFocus ? focusCurrentSurface : () => false,
      };
      const command = contributionCommand(current);
      if (command) command.row.run(command.binding, activationContext);
      else offered.activate(current.activation, activationContext);
      return true;
    },
    activateReading(id) {
      const activate = offered.readingActions.get(id);
      if (!activate) return false;
      activate();
      return true;
    },
    focus(entryKey, surface = null) {
      return arrive(entryKey, surface, (destination) => {
        destination.focus({ preventScroll: true });
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
  offered.registration = registration;
  return registration;
}
