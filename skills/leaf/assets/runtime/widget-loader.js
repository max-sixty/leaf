/* This module owns registry loading, pre-upgrade passage fences, dynamic widget
 * imports, and initial presentation. */
import {
  MARKED_IN_PAGE,
  dress,
  markDeclared,
  watchExternalLinks,
} from "./presentation.js";
import { reachScrollers } from "./reach.js";
import { registry, tagsDeclaring } from "./registry.js";
import { loadShadowRules } from "./shadow.js";
import { revealLayer, sameDelivery, sameLayer } from "./layer-client.js";
import {
  attachApplicationPresentation,
  whenApplicationPresented,
} from "./semantic-state.js";
import {
  captureAuthoredFacets,
  rememberAuthoredParents,
} from "./projection/authored.js";
import { captureWidgetDescriptors } from "./widget-descriptors.js";
import {
  opaquePassageParts,
  opaquePassageRoots,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
} from "./passages.js";
import { offlineInteractive, runtimeModule, runtimeResource } from "./context.js";

/* Registry loading and the one initial widget-upgrade lifecycle.

   A page loads what it uses. `importWidgets` is the one import-on-demand door: it takes
   the markup about to be upgraded, imports each declared tag standing in it once per
   tab, and loads the shadow rules only where an `x-shadow` widget is among them. Three
   boundaries introduce markup and all three call it — startup with the document, a
   version activation with the incoming `main`, and the state application with the frozen
   markup an agent's reply carries, ahead of the panel building a body. Each of them
   names the tags it needs, so nothing imports on a mutation after the element is already
   connected. A module whose own payload is large (`lf-diff`'s renderer) imports it on
   first render for the same reason. `missingUpgrades` therefore reports the page's own
   widgets; that a declared module exists at all stays `package check`'s.

   Required widget imports reject through the startup or activation boundary; a missing
   module cannot count as a completed upgrade. */
// An opaque widget and its original direct children fence passage capture. A
// preserving widget owns prose around ordered upgraded-child boundaries instead. Its
// pre-upgrade source and occurrence pair the rendered owner with the file even when it
// has no authored id. Record these readings before upgrades move or replace nodes.
const rememberedPassageRoots = new WeakSet();

// Root-inclusive, like every reading of arriving markup: when a live revision brings a
// single widget, the scope is that widget.
const within = (scope, selector) => [
  ...(scope.matches?.(selector) ? [scope] : []),
  ...scope.querySelectorAll(selector),
];

export function rememberPassageParts(scope = document, source = ["page", null]) {
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
  ))
    for (const root of within(scope, tag)) {
      if (rememberedPassageRoots.has(root)) continue;
      rememberedPassageRoots.add(root);
      opaquePassageRoots.add(root);
      for (const child of root.children) opaquePassageParts.add(child);
    }
  for (const [ownerIndex, root] of preservingOwners(scope).entries()) {
    if (rememberedPassageRoots.has(root)) continue;
    rememberedPassageRoots.add(root);
    identifyPreserving(root, [...source, ownerIndex]);
  }
}

const preservingOwners = (scope) =>
  within(scope, "*").filter((root) => registry[root.localName]?.["x-verbatim"]);

function identifyPreserving(root, owner) {
  verbatimOwnerIdentity.set(root, owner);
  let boundaryIndex = 0;
  const visit = (parent) => {
    for (const child of parent.children) {
      if (registry[child.localName]?.["x-upgrade"])
        verbatimBoundaryIdentity.set(child, { owner, index: boundaryIndex++ });
      else visit(child);
    }
  };
  visit(root);
}

// A preserving owner with no id is identified by where it stands among the document's
// other preserving owners, which is a fact about all of them rather than about any one.
// A live revision that inserts or drops one therefore renumbers the rest, and leaving
// the standing owners on the numbers they arrived with would have two of them answering
// to the same name. Read from the document rather than from what the patch brought in,
// for the same reason: the order is the whole document's.
export function reindexPassageOwners(scope = document, source = ["page", null]) {
  for (const [ownerIndex, root] of preservingOwners(scope).entries())
    identifyPreserving(root, [...source, ownerIndex]);
}

// The one import-on-demand door: a page loads the modules its own markup uses and no
// others. The vocabulary is the layer's and the page is one document in it, so
// importing every declared tag made every page pay for the whole layer — a triage
// board with no diff anywhere on it fetched Pierre's 1.7MB renderer on every load,
// which was more than half the bytes that page moved.
//
// Three boundaries can bring a tag into the document and all three ask here: startup,
// a version activation, and the panel's instantiation of the frozen markup an agent
// message carries. Each of them holds the markup it is about to upgrade, so each can
// name what it needs; a MutationObserver could only import after the element was
// already connected, which is the one order the startup contract forbids.
//
// A tag is asked for once per tab and the same promise answers every later caller, so
// a version that keeps a tag, a second diff in a second reply, and a poll that sees
// the same conversation again all cost nothing. A failed import stays rejected:
// startup and activation must not present markup whose required module is absent.
const modules = new Map();
const registryUrl = () =>
  offlineInteractive
    ? runtimeResource("/registry.json")
    : (document.querySelector("script[data-lf-runtime][data-lf-probe]")?.dataset
        .lfProbe ?? "/registry.json");
const widgetUrl = (tag) =>
  offlineInteractive
    ? runtimeModule(`/widgets/${tag}.js`)
    : new URL(
        `widgets/${tag}.js`,
        new URL("./", new URL(registryUrl(), document.baseURI)),
      ).href;
const presentTags = (scope, holds) =>
  tagsDeclaring(holds).filter((tag) => scope.querySelector(tag));

export async function importWidgets(scope) {
  // Before the modules import, because a widget's first render asks for these rules and
  // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
  // Asked of the same scope for the same reason, and that is what makes the narrowing
  // safe: `shadowStage` is reachable only from a module, a module loads only where its
  // tag stands in some scope, and a tag declaring x-shadow brings the rules in on that
  // same call. The theme is read once for the tab however many scopes ask.
  if (presentTags(scope, (entry) => entry["x-shadow"]).length) await loadShadowRules();
  await Promise.all(
    presentTags(scope, (entry) => entry["x-upgrade"]).map((tag) => {
      if (!modules.has(tag)) modules.set(tag, import(widgetUrl(tag)));
      return modules.get(tag);
    }),
  );
}

// The upgrade lifecycle for the whole authored body, at startup: read it while it is
// still what its author wrote, import what its tags declare, and dress it.
export async function installDocument(scope) {
  const presentation = attachApplicationPresentation("document:installation", scope);
  try {
    rememberPassageParts(scope);
    rememberAuthoredParents(scope);
    captureWidgetDescriptors(scope);
    markDeclared(scope, MARKED_IN_PAGE);
    watchExternalLinks(scope);
    await importWidgets(scope);
    await settle(presentation, scope, [scope]);
  } finally {
    presentation.disconnect();
  }
}

// The same lifecycle for a revision patched into the document a reader is standing in.
// What arrives is scattered through the page rather than being one subtree, so each step
// takes the nodes it applies to. The pre-upgrade readings belong to each arrival, before
// insertion hands a widget's children to its controller, so `patch` makes them as it goes
// and answers with the roots it brought. Dressing the page instead of those would
// re-tokenize a code block no revision touched and hand its spans back as new nodes,
// which is the reader's own page rebuilt under them. Modules are asked for earlier still,
// off the arriving document, so the install spends nothing on a fetch.
export async function patchDocument(scope, patch) {
  const presentation = attachApplicationPresentation("document:patch", scope);
  try {
    await settle(presentation, scope, patch());
  } finally {
    presentation.disconnect();
  }
}

// What arriving markup owes the document once it stands in it: the dressing passes over
// each root, then the two readings that are of the document rather than of the markup —
// where the keyboard can reach, and the authored initial condition of every widget not
// already holding one.
async function settle(presentation, scope, arrived) {
  await presentation.present(scope, Promise.all(arrived.map(dress)));
  await whenApplicationPresented();
  reachScrollers(scope);
  captureAuthoredFacets(scope);
  // Capturing the authored initial condition is a semantic publication. Wait for
  // subscribers to paint that newest reading before declaring upgrade complete.
  await whenApplicationPresented();
}

export async function upgradeWidgets({ buildReactionBar }) {
  const response = await fetch(registryUrl());
  if (!response.ok)
    throw new Error(`leaf: registry failed to load (${response.status})`);
  if (!sameDelivery(response)) return false;
  Object.assign(registry, await response.json());
  const registryGeneration = registry.$layer?.generation;
  if (typeof registryGeneration !== "string" || !registryGeneration)
    throw new Error("leaf: registry lacks $layer.generation");
  if (!sameLayer(registryGeneration)) return false;
  if (
    !registry.$events?.kinds ||
    !registry.$languages?.names ||
    !registry.$languages?.paths ||
    !registry.$tones?.names ||
    !registry.$reactions?.tokens
  )
    throw new Error("leaf: registry lacks $events, $languages, $tones or $reactions");
  revealLayer();
  buildReactionBar();
  await installDocument(document.body);
  return true;
}
