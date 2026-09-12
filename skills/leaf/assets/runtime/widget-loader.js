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

export function rememberPassageParts(scope = document, source = ["page", null]) {
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
  ))
    for (const root of scope.querySelectorAll(tag)) {
      if (rememberedPassageRoots.has(root)) continue;
      rememberedPassageRoots.add(root);
      opaquePassageRoots.add(root);
      for (const child of root.children) opaquePassageParts.add(child);
    }
  const preserving = [...scope.querySelectorAll("*")].filter(
    (root) => registry[root.localName]?.["x-verbatim"],
  );
  for (const [ownerIndex, root] of preserving.entries()) {
    if (rememberedPassageRoots.has(root)) continue;
    rememberedPassageRoots.add(root);
    const owner = [...source, ownerIndex];
    verbatimOwnerIdentity.set(root, owner);
    let boundaryIndex = 0;
    const visit = (parent) => {
      for (const child of parent.children) {
        if (registry[child.localName]?.["x-upgrade"]) {
          verbatimBoundaryIdentity.set(child, {
            owner,
            index: boundaryIndex++,
          });
        } else visit(child);
      }
    };
    visit(root);
  }
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

export async function installDocument(
  scope,
  { source = ["page", null], mount = () => {}, watchLinks = false } = {},
) {
  const presentation = attachApplicationPresentation("document:installation", scope);
  try {
    rememberPassageParts(scope, source);
    rememberAuthoredParents(scope);
    captureWidgetDescriptors(scope);
    markDeclared(scope, MARKED_IN_PAGE);
    if (watchLinks) watchExternalLinks(scope);
    await importWidgets(scope);
    mount();
    await presentation.present(scope, dress(scope));
    await whenApplicationPresented();
    reachScrollers(scope);
    captureAuthoredFacets(scope);
    // Capturing the authored initial condition is a semantic publication. Wait for
    // subscribers to paint that newest reading before declaring upgrade complete.
    await whenApplicationPresented();
  } finally {
    presentation.disconnect();
  }
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
  await installDocument(document.body, { watchLinks: true });
  return true;
}
