/* Core scope declarations join the element register at boot. Readers inspect the same
   objects; this module never imports a feature to discover its commands. */
import { bindings } from "./bindings.js";
export const ELEMENTS = Symbol("the scopes of the focused element");
let scopes;
let reference;
let typing;
let auxiliaryModality;
export function registerPageScopes(
  declarations,
  universalReference,
  textEntry,
  auxiliaryLayer,
) {
  scopes = declarations;
  reference = universalReference;
  typing = textEntry;
  auxiliaryModality = auxiliaryLayer;
}
export const pageScopes = () => scopes;
export const universalReference = () => reference;
export const allButTheReference = (binding) => !bindings(reference).includes(binding);
export const textEntryScope = () => typing;
export const coveringAuxiliarySurface = () => auxiliaryModality.coveringSurface();
export const coveringAuxiliaryFocus = () => auxiliaryModality.coveringFocus();
export const auxiliaryAllowsNativeLayer = (node, establishedOver) =>
  auxiliaryModality.allowsNativeLayer(node, establishedOver);
export const openAuxiliarySurfaceFor = (node) => auxiliaryModality.openSurfaceFor(node);
