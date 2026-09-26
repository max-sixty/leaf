/* Stable DOM relations shared by thread views and focus recovery. */
import { TEXT_FIELD } from "../focus.js";
export const SAYS_IN = ".lf-thread, .lf-page-thread, .lf-thread-seat";
export const SAY_BOX = `:scope > .lf-compose ${TEXT_FIELD}, :scope > .lf-say ${TEXT_FIELD}`;
