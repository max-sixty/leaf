/* The immutable identity delivered with this document.
 *
 * The server's runtime markers say which revision and public stamp the document is,
 * whether its executable graph can take a revision in place, and which authored widget
 * bodies may be retained. The composition root initializes the single semantic publisher
 * from this reading before it constructs browser owners; version travel and contained
 * gallery documents consume the same executable and widget readings.
 */
import { applicationState } from "./semantic-state.js";
import { LIVE_ROOT, PAGE_PATH, VERSION_PATH } from "./storage.js";

const versionMatch = PAGE_PATH.match(VERSION_PATH);
const servedRevision = document.querySelector(
  'meta[name="lf-revision"][data-lf-runtime]',
)?.content;
const servedStampMarker = document.querySelector(
  'meta[name="lf-version"][data-lf-runtime]',
);

export const servedExecutable = document.querySelector(
  'meta[name="lf-executable"][data-lf-runtime]',
)?.content;

export const documentWidgetDigests = (doc) => {
  const stated = doc.querySelector('meta[name="lf-widgets"][data-lf-runtime]')?.content;
  return stated ? JSON.parse(stated) : {};
};

export const servedWidgets = documentWidgetDigests(document);

export function initializeServedDocument() {
  applicationState.identify(
    servedRevision ? parseInt(servedRevision, 10) : null,
    servedStampMarker
      ? parseInt(servedStampMarker.content, 10)
      : versionMatch
        ? parseInt(versionMatch[1], 10)
        : null,
    LIVE_ROOT,
  );
  servedStampMarker?.remove();
}
