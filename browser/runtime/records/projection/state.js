// Compiled from state.ts by build/typescript.mjs; edit that file.
/* Semantic projection is a selector over the application root. */
import { readPart } from "../../state/semantic-state.js";

export const currentProjection = readPart((root) => root.effective.projection);
