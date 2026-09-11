/* Registry-declared widget-local placements for canonical Thread views.

   Registrations are the domain's durable extension points. Each public registration is
   supplied the application invalidation that owns its next semantic render; the module
   stores no application service or generic event channel. */
import { setChildren } from "../dom-children.js";
import { reportPageError } from "../layer-client.js";
import { datumAimTarget, resolveAnchor } from "../anchor-resolution.js";
import { containsAcross, pageText } from "../passages.js";
import { registry } from "../registry.js";
import { renderThreadSurface } from "./inline.js";
import { removeConversationNode } from "./reaction-strips.js";

const registrations = new Map();
let claimedIds = new Set();

function update(registration) {
  if (registration.reconcileQueued) return;
  registration.reconcileQueued = true;
  queueMicrotask(() => {
    registration.reconcileQueued = false;
    void registration.invalidate();
  });
}

export function registerThreadSurface(
  owner,
  adapter,
  { invalidate, closeReactionMode, composition },
) {
  if (!(owner instanceof Element))
    throw new TypeError("registerThreadSurface owner must be a widget element");
  if (registry[owner.localName]?.["x-thread-surface"] !== true)
    throw new Error(
      `registerThreadSurface(${owner.localName}) requires x-thread-surface: true`,
    );
  if (
    !adapter ||
    typeof adapter !== "object" ||
    typeof adapter.begin !== "function" ||
    typeof adapter.outletFor !== "function" ||
    typeof adapter.end !== "function"
  )
    throw new TypeError(
      "registerThreadSurface adapter needs begin, outletFor, and end functions",
    );
  if (typeof invalidate !== "function")
    throw new TypeError("registerThreadSurface needs an invalidation function");
  if (typeof closeReactionMode !== "function")
    throw new TypeError("registerThreadSurface needs reaction teardown");
  if (
    !composition ||
    typeof composition.open !== "function" ||
    typeof composition.active !== "function" ||
    typeof composition.node !== "function" ||
    typeof composition.seat !== "function" ||
    typeof composition.restore !== "function" ||
    typeof composition.outlet !== "function"
  )
    throw new TypeError("registerThreadSurface needs composition presentation");
  if (registrations.has(owner))
    throw new Error(`registerThreadSurface(${owner.localName}) registered twice`);
  const registration = {
    adapter,
    owner,
    invalidate,
    closeReactionMode,
    composition,
    outlets: new Set(),
    reconcileQueued: false,
  };
  registrations.set(owner, registration);
  update(registration);
  let active = true;
  return {
    open(datum, { origin = null } = {}) {
      if (!active) return false;
      const target = datumAimTarget(datum);
      if (
        !target ||
        target.anchor.section !== owner.id ||
        !containsAcross(owner, target.element)
      )
        throw new TypeError(
          `registerThreadSurface(${owner.localName}) can open only its own projected datum`,
        );
      composition.open(target, { origin });
      return true;
    },
    update: () => update(registration),
    unregister() {
      if (!active) return;
      active = false;
      registrations.delete(owner);
      clearRegistration(registration);
      update(registration);
    },
  };
}

function removeNode(node, commands) {
  removeConversationNode(node, commands.reaction.closeReactionMode);
}

function clearOutlets(outlets, commands) {
  for (const outlet of outlets) {
    setChildren(outlet, [], (node) => removeNode(node, commands));
    delete outlet.dataset.lfThreadSurface;
  }
}

function reportFailure({ owner }, error) {
  reportPageError(
    `thread surface ${owner.localName}#${owner.id} failed: ${error?.message ?? error}`,
  );
}

function clearRegistration(registration, commands) {
  if (registration.outlets.has(registration.composition.outlet()))
    registration.composition.restore();
  try {
    registration.adapter.begin();
    registration.adapter.end();
  } catch (error) {
    reportFailure(registration, error);
  }
  if (commands) clearOutlets(registration.outlets, commands);
  else
    for (const outlet of registration.outlets)
      setChildren(outlet, [], (node) =>
        removeConversationNode(node, registration.closeReactionMode),
      );
  registration.outlets.clear();
}

export function renderSurfaces(threads, placedAt, commands) {
  const nextClaimed = new Set();
  const activeComposition = commands.composition.active();
  let compositionSeated = false;
  for (const registration of [...registrations.values()]) {
    const { adapter, owner } = registration;
    if (registrations.get(owner) !== registration) continue;
    if (!owner.isConnected) {
      registrations.delete(owner);
      clearRegistration(registration, commands);
      continue;
    }
    const byOutlet = new Map();
    let compositionOutlet = null;
    let compositionPrepared = false;
    try {
      adapter.begin();
      for (const thread of threads) {
        const anchor = thread.anchor;
        const placement = placedAt(thread.root.id);
        if (
          !anchor?.datum ||
          anchor.section !== owner.id ||
          placement?.status !== "exact" ||
          !(placement.datumElement instanceof Element) ||
          !containsAcross(owner, placement.datumElement)
        )
          continue;
        const outlet = adapter.outletFor({ anchor, placement, thread });
        if (!(outlet instanceof Element)) continue;
        const held = byOutlet.get(outlet) ?? [];
        held.push(thread);
        byOutlet.set(outlet, held);
      }
      const anchor = activeComposition?.anchor;
      if (anchor?.datum && anchor.section === owner.id) {
        const placement = resolveAnchor(anchor, pageText());
        if (
          placement?.status === "exact" &&
          placement.datumElement instanceof Element &&
          containsAcross(owner, placement.datumElement)
        ) {
          compositionOutlet = adapter.outletFor({
            anchor,
            placement,
            composition: activeComposition,
          });
          if (compositionOutlet instanceof Element && !byOutlet.has(compositionOutlet))
            byOutlet.set(compositionOutlet, []);
        }
      }
      const currentCompositionOutlet = commands.composition.outlet();
      if (compositionOutlet instanceof Element)
        compositionPrepared = commands.composition.seat(compositionOutlet);
      else if (registration.outlets.has(currentCompositionOutlet))
        commands.composition.restore();
      adapter.end();
      if (registrations.get(owner) !== registration) continue;
      for (const outlet of byOutlet.keys()) {
        if (!outlet.isConnected) byOutlet.delete(outlet);
        else if (!containsAcross(owner, outlet))
          throw new Error(
            `registerThreadSurface(${owner.localName}) returned an outlet outside its widget`,
          );
      }
      if (compositionPrepared) compositionSeated = true;
    } catch (error) {
      if (
        registration.outlets.has(commands.composition.outlet()) ||
        compositionOutlet === commands.composition.outlet()
      )
        commands.composition.restore();
      clearOutlets(registration.outlets, commands);
      registration.outlets.clear();
      reportFailure(registration, error);
      continue;
    }
    clearOutlets(
      [...registration.outlets].filter((outlet) => !byOutlet.has(outlet)),
      commands,
    );
    registration.outlets = new Set(byOutlet.keys());
    for (const [outlet, localThreads] of byOutlet) {
      outlet.dataset.lfThreadSurface = "";
      const response =
        compositionPrepared && outlet === compositionOutlet
          ? commands.composition.node()
          : null;
      renderThreadSurface(outlet, localThreads, commands, response);
      for (const thread of localThreads) nextClaimed.add(thread.root.id);
    }
  }
  if (!compositionSeated) commands.composition.restore();
  claimedIds = nextClaimed;
  return claimedIds;
}

export const claimed = (id) => claimedIds.has(id);

export function focusSurface(id, { focus = "reply" } = {}) {
  for (const registration of registrations.values()) {
    const root = registration.owner.shadowRoot ?? registration.owner;
    const thread = root.querySelector(
      `.lf-conversation-thread[data-thread="${CSS.escape(id)}"]`,
    );
    if (!thread) continue;
    const summary = thread.querySelector(":scope > summary");
    const target =
      (focus === "thread" ? thread : null) ??
      (summary && !thread.hasAttribute("open") ? summary : null) ??
      thread.querySelector("textarea:not([disabled])") ??
      summary ??
      thread;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest" });
    return target;
  }
  return null;
}
