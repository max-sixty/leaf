// Compiled from document-identity.ts by build/typescript.mjs; edit that file.
/* The immutable identity delivered with this document.
 *
 * The server's runtime markers say which revision and public stamp the document is
 * (every delivery of a stamped revision writes `lf-version`, whatever its address,
 * so the address is never read for it),
 * and whether its executable graph can take a revision in place. The composition root initializes the single semantic publisher
 * from this reading before it constructs browser owners. Each sample receives its
 * own served identity through the same document delivery as an ordinary page.
 */
import { applicationState } from "./semantic-state.js";
import { LIVE_ROOT } from "./context.js";

const servedRevisionText = document.querySelector(
  'meta[name="lf-revision"][data-lf-runtime]',
)?.content;
export const servedRevision = servedRevisionText
  ? parseInt(servedRevisionText, 10)
  : null;
const servedStampMarker = document.querySelector(
  'meta[name="lf-version"][data-lf-runtime]',
);

export const servedExecutable = document.querySelector(
  'meta[name="lf-executable"][data-lf-runtime]',
)?.content;

export function initializeServedDocument() {
  applicationState.identify(
    servedRevision,
    servedStampMarker ? parseInt(servedStampMarker.content, 10) : null,
    LIVE_ROOT,
  );
  servedStampMarker?.remove();
}
