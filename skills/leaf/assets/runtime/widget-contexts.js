/* Physical publication identity shared by vocabulary loading and widget readers.
   These maps retain original node/context associations outside semantic snapshots;
   reading a declaration never imports content modules or starts their registration.
   Every imported node can bind a publication, including text and comment arrivals. */
import { isElementName } from "./registry-contract.js";

const contexts = new Map();
const owners = new WeakMap();
export const knownVocabulary = (revision) => contexts.get(revision);
export const rememberVocabulary = (context) => contexts.set(context.revision, context);
export function normalizeDeclarations(declarations) {
  for (const [tag, entry] of Object.entries(declarations))
    if (isElementName(tag))
      for (const spec of Object.values(entry["x-state"] ?? {})) spec.writer ??= "user";
  return declarations;
}

export function bindVocabulary(root, context) {
  owners.set(root, context);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  for (let element = walker.nextNode(); element; element = walker.nextNode())
    owners.set(element, context);
}
export function vocabularyFor(node) {
  for (let held = node; held; held = held.parentNode ?? held.host) {
    const context = owners.get(held);
    if (context) return context;
  }
  return null;
}

export const vocabularies = () => [...contexts.values()];
