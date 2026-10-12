/* This module owns registry loading, pre-upgrade passage fences, dynamic widget
 * imports, and initial presentation. */
import { registryFor, adoptRegistry, registry, tagsDeclaring } from "./registry.js";
import { publicationVocabulary } from "./widget-vocabularies.js";
import { vocabularyFor, bindVocabulary } from "./widget-contexts.js";
import { paintDeclaredWords, watchExternalLinks } from "./declared-words.js";
import { watchCodeBlocks } from "./code-copy.js";
import { reachScrollers } from "./reach.js";

import { loadShadowRules } from "./shadow.js";
import { revealLayer, admitResponse, sameLayer } from "./layer-client.js";
import {
  applicationState,
  attachApplicationPresentation,
  readApplication,
  whenApplicationPresented,
  whenWidgetsPresented,
} from "./semantic-state.js";
import { rememberAuthoredParents, stageAuthoredStates } from "./projection/authored.js";
import {
  commitWidgetDescriptors,
  stageWidgetDescriptors,
} from "./widget-descriptors.js";
import {
  fencePassageParts,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
} from "./passages.js";
import { offlineInteractive, runtimeResource } from "./context.js";
import { loadDeclaredMarkdown, formatDeclaredMarkdown } from "./markdown.js";
import { initialOrigin, initialSource } from "./initial-render.js";
import { registeredTags, widgetImports } from "./widget-imports.js";

/* Registry loading and the one initial widget-upgrade lifecycle.

   A page loads what it uses. `importWidgetModules` is the one import-on-demand door: it takes
   the markup about to be upgraded, imports each declared tag standing in it once per
   publication. Shared dependency preparation loads shadow rules only where an `x-shadow`
   widget is among them, alongside any declared Markdown parser. Three
   boundaries introduce markup and all three use it — startup with the document, a
   version activation with the incoming `main`, and the state application with the frozen
   markup an agent's reply carries, ahead of the panel building a body. Each of them
   names the tags it needs, so nothing imports on a mutation after the element is already
   connected. A module whose own payload is large (`lf-diff`'s renderer) imports it on
   first render for the same reason. `missingUpgrades` therefore reports the page's own
   widgets; that a declared module exists at all stays `package check`'s. An offline
   export embeds only the widget modules these boundaries can ask for
   (`_module_urls` in `exporting.py`), so a new boundary is one it has to read too.

   Preloading a revision leaves its authored document intact; only copied arrival nodes
   are formatted, after typed initial values and descriptors are captured and before
   connection. Startup and frozen messages format after their own source capture.

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
  scope = initialSource(scope);
  for (const tag of tagsDeclaring(
    (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
  ))
    for (const root of within(scope, tag)) {
      const live = initialOrigin(root);
      if (rememberedPassageRoots.has(live)) continue;
      rememberedPassageRoots.add(live);
      fencePassageParts(live, [...root.children].map(initialOrigin));
    }
  for (const [ownerIndex, root] of preservingOwners(scope).entries()) {
    const live = initialOrigin(root);
    if (rememberedPassageRoots.has(live)) continue;
    rememberedPassageRoots.add(live);
    identifyPreserving(root, [...source, ownerIndex]);
  }
}

const preservingOwners = (scope) =>
  within(scope, "*").filter(
    (root) => registryFor(root)[root.localName]?.["x-verbatim"],
  );

function identifyPreserving(root, owner) {
  verbatimOwnerIdentity.set(initialOrigin(root), owner);
  let boundaryIndex = 0;
  const visit = (parent) => {
    for (const child of parent.children) {
      if (registryFor(child)[child.localName]?.["x-upgrade"])
        verbatimBoundaryIdentity.set(initialOrigin(child), {
          owner,
          index: boundaryIndex++,
        });
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
  for (const [ownerIndex, root] of preservingOwners(initialSource(scope)).entries())
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
// A tag is asked for once per publication and the same promise answers later callers,
// so a second diff in the same publication's replies and a poll that sees the same
// thread again cost nothing. A failed import stays rejected:
// startup and activation must not present markup whose required module is absent.
const registryUrl = () => runtimeResource("/registry.json");

async function loadWidgetDependencies(scope) {
  // Before the modules import, because a widget's first render asks for these rules and
  // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
  // Asked of the same scope for the same reason, and that is what makes the narrowing
  // safe: `shadowStage` is reachable only from a module, a module loads only where its
  // tag stands in some scope, and a tag declaring x-shadow brings the rules in on that
  // same call. The shadow rules are read once per publication however many scopes ask.
  const declarations = registryFor(scope);
  await Promise.all([
    loadDeclaredMarkdown(scope),
    ...(registeredTags(scope, declarations).some((tag) => declarations[tag]["x-shadow"])
      ? [loadShadowRules(scope)]
      : []),
  ]);
}

async function importWidgetModules(scope) {
  const context = vocabularyFor(scope);
  const required = widgetImports(scope, registryFor(scope));
  await Promise.all(
    required.initializers.map(({ tag, path }) =>
      document.documentElement.lfInitial.has(tag, context.revision)
        ? undefined
        : context.loadInitializer(path),
    ),
  );
  await context.load(scope);
}

// Source-only preparation loads constructors without upgrading the inert authored
// document: its connected nodes belong to another Document, and a callback there
// would mutate the source before typed capture or adopt live-document resources.
// Live revisions instantiate only their copied arrivals inside the live vocabulary.
export async function preloadWidgets(scope) {
  await loadWidgetDependencies(scope);
  await importWidgetModules(scope);
}

// Startup and frozen-message presentation may consume their captured markup. Format
// before module imports can synchronously connect an already-standing custom element.
export async function importWidgets(scope) {
  await loadWidgetDependencies(scope);
  formatDeclaredMarkdown(scope);
  await importWidgetModules(scope);
  const context = vocabularyFor(scope);
  if (context.registry !== customElements) context.upgrade(scope);
}

// The upgrade lifecycle for the whole authored body, at startup: read it while it is
// still what its author wrote, import what its tags declare, and paint its declared words.
async function installDocument(scope) {
  const presentation = attachApplicationPresentation("document:installation", scope);
  try {
    rememberPassageParts(scope);
    rememberAuthoredParents(scope);
    const descriptors = stageWidgetDescriptors(scope);
    const authored = stageAuthoredStates(scope, new Map());
    const prior = readApplication().document;
    applicationState.captureDocument({
      ...prior,
      registry: registryFor(scope),
      authored: new Map([...prior.authored, ...authored]),
      descriptors: new Map([...prior.descriptors, ...descriptors.descriptors]),
    });
    commitWidgetDescriptors(descriptors);
    watchExternalLinks();
    watchCodeBlocks();
    await importWidgets(scope);
    await settle(presentation, scope, [scope], whenApplicationPresented);
  } finally {
    presentation.disconnect();
  }
}

// The same lifecycle for a revision patched into the document a user is standing in.
// What arrives is scattered through the page rather than being one subtree, so each step
// takes the nodes it applies to. The pre-upgrade readings belong to each arrival, before
// insertion hands a widget's children to its controller, so `patch` makes them as it goes
// and answers with the roots it brought. Dressing the page instead of those would
// re-tokenize a code block no revision touched and hand its spans back as new nodes,
// which is the user's own page rebuilt under them. Modules are asked for earlier still,
// off the arriving document, so the install spends nothing on a fetch.
//
// A patch runs inside the state turn that brought the revision, and that answer may
// carry more than the revision: a data replacement for a widget the revision left
// standing reaches that widget only after the turn adopts the answer. So the patch
// waits for the widgets it brought and for its own dressing, never for the whole
// application — that wait would be on a renderer whose turn cannot come until this one
// returns, and a page that stops there has stopped answering with nothing said.
export async function patchDocument(scope, patch) {
  const presentation = attachApplicationPresentation("document:patch", scope);
  try {
    const { roots, widgets, ...result } = patch();
    await settle(presentation, scope, roots, () => whenWidgetsPresented(widgets));
    return result;
  } finally {
    presentation.disconnect();
  }
}

// What arriving markup owes the document once it stands in it: the dressing passes over
// each root, then the reading that is of the document rather than of the markup: where
// the keyboard can reach. Authored state was already captured from source markup
// before any module could turn that input into presentation. `presented` is the wait
// each caller owes: the whole application at startup, the widgets it brought for a patch.
async function settle(presentation, scope, arrived, presented) {
  const painted = Promise.all(arrived.map(paintDeclaredWords));
  const presenting = presentation.present(scope);
  presenting.resolve(painted);
  await presenting.ready;
  await presented();
  reachScrollers(scope);
}

export async function upgradeWidgets({ buildReactionBar }) {
  const response = await fetch(registryUrl());
  if (!admitResponse(response)) return false;
  if (!response.ok)
    throw new Error(`leaf: registry failed to load (${response.status})`);
  const declarations = await response.json();
  adoptRegistry(declarations);
  const registryGeneration = registry.$layer?.generation;
  if (typeof registryGeneration !== "string" || !registryGeneration)
    throw new Error("leaf: registry lacks $layer.generation");
  if (!sameLayer(registryGeneration)) return false;
  if (
    !registry.$events?.kinds ||
    !registry.$languages?.names ||
    !registry.$languages?.paths ||
    !registry.$tones?.names ||
    !registry.$reactions?.tokens ||
    !registry.$decisions ||
    !registry.$states ||
    !registry.$marks
  )
    throw new Error(
      "leaf: registry lacks $events, $languages, $tones, $reactions, $decisions, $states or $marks",
    );
  const probe = document.querySelector("script[data-lf-vocabulary-root]").dataset
    .lfVocabularyRoot;
  const pageUrl = offlineInteractive
    ? runtimeResource(probe)
    : new URL(probe, document.baseURI).href;
  let pageDeclarations = declarations;
  if (pageUrl !== registryUrl()) {
    const responsePage = await fetch(pageUrl);
    if (!responsePage.ok)
      throw new Error(`Leaf page vocabulary failed (${responsePage.status})`);
    pageDeclarations = await responsePage.json();
  }
  const revision = Number(document.body.dataset.lfVocabulary);
  const root = probe.slice(0, probe.lastIndexOf("/"));
  const context = publicationVocabulary(revision, pageDeclarations, root, true);
  bindVocabulary(document, context);
  revealLayer();
  buildReactionBar();
  await installDocument(document.body);
  return true;
}
