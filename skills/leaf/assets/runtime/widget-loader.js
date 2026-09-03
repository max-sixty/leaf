import {
  MARKED_IN_PAGE,
  dress,
  markDeclared,
  watchExternalLinks,
} from "./presentation.js";
import { reachScrollers } from "./reach.js";
import { registry, tagsDeclaring } from "./registry.js";
import { loadShadowRules } from "./shadow.js";
import { settle, settling } from "./widget-upgrade.js";

/* Registry loading and the one initial widget-upgrade lifecycle. */
export function createWidgetLoader({
  buildReactBar,
  rememberAuthoredMarkup,
  reportPageError,
  revealLayer,
  sameLayer,
}) {
  // The file-side passage reader fences an upgraded element and each of its original
  // direct children when the registry cannot promise its body is verbatim. Remember
  // those parts before custom-element definitions can add or move anything, so the
  // browser can stop captured context at the same seams after every upgrade has run.
  const opaquePassageRoots = new WeakSet();
  const opaquePassageParts = new WeakSet();

  function rememberPassageParts(scope = document) {
    for (const tag of tagsDeclaring(
      (entry) => entry["x-upgrade"] && !entry["x-verbatim"],
    ))
      for (const root of scope.querySelectorAll(tag)) {
        opaquePassageRoots.add(root);
        for (const child of root.children) opaquePassageParts.add(child);
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
  // the same conversation again all cost nothing.
  const modules = new Map();
  const presentTags = (scope, holds) =>
    tagsDeclaring(holds).filter((tag) => scope.querySelector(tag));

  async function importWidgets(scope) {
    // Before the modules import, because a widget's first render asks for these rules and
    // an async stage would put every x-shadow widget's look a fetch behind its own nodes.
    // Asked of the same scope for the same reason, and that is what makes the narrowing
    // safe: `shadowStage` is reachable only from a module, a module loads only where its
    // tag stands in some scope, and a tag declaring x-shadow brings the rules in on that
    // same call. The theme is read once for the tab however many scopes ask.
    if (presentTags(scope, (entry) => entry["x-shadow"]).length)
      await loadShadowRules();
    await Promise.all(
      presentTags(scope, (entry) => entry["x-upgrade"]).map((tag) => {
        if (!modules.has(tag))
          modules.set(
            tag,
            import(`/widgets/${tag}.js`).catch((err) =>
              reportPageError(`widget ${tag} failed to load: ${err?.message ?? err}`),
            ),
          );
        return modules.get(tag);
      }),
    );
  }

  async function upgradeWidgets() {
    const response = await fetch("/registry.json");
    if (!response.ok)
      throw new Error(`leaf: registry failed to load (${response.status})`);
    const responseGeneration = response.headers.get("Leaf-Layer");
    if (responseGeneration && !sameLayer(responseGeneration)) return false;
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
    buildReactBar();
    rememberPassageParts();
    rememberAuthoredMarkup();
    markDeclared(document.body, MARKED_IN_PAGE);
    watchExternalLinks(document.body);
    await importWidgets(document);
    settle(dress(document.body));
    // Importing defined the elements and ran their connectedCallbacks; async ones
    // registered their work via settle(). Wait it out so geometry is final.
    await Promise.allSettled(settling);
    // After the wait, because the box a widget scrolls is a box its module built: run this
    // with the rest of the upgrade and a diff's pre and a code block's are half there.
    reachScrollers(document.body);
    return true;
  }

  return {
    importWidgets,
    opaquePassageParts,
    opaquePassageRoots,
    rememberPassageParts,
    upgradeWidgets,
  };
}
