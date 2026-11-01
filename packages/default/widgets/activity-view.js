import {
  offerElement,
  offerActionElement,
  fragmentTarget,
  generatedElement,
  keeps,
  tabStore,
} from "/runtime/widget-api.js";
/* One Lit drawing from the retained tab-local reading through live history. The
 * retained template keeps its identity through live updates.
 * Retained rows are presentation snapshots, never semantic state; the
 * behavior module holds/reveals authoritative history through HeldReading and supplies
 * the live clock, thread action and current-document target reading. */
import { html, nothing, ref, repeat } from "/vendor/lit.js";

export const ACTIVITY_VIEW = "activity-reading:";

/** @typedef {{id: string, ts: string, actor: string, what: string, label?: string | null | undefined, widget?: string | null | undefined, thread?: string | undefined, excerpt?: string | null, undone: boolean}} ActivityRow */
/** @typedef {{open: boolean, shown: string, label: string, news: boolean}} ActivityReading */
/** @typedef {(fragment: string, document: Document) => Element | null} ActivityTarget */
/** @typedef {{printing?: boolean, names?: ActivityTarget, age?: (ts: string) => string, openThread?: (id: string) => void}} ActivityCapabilities */
/** @param {Element} link @param {string} widget @param {typeof keeps} write @param {ActivityTarget} names */
function refreshTarget(link, widget, write, names) {
  const fragment = `#${encodeURIComponent(widget)}`;
  const href = names(fragment, link.ownerDocument) ? fragment : null;
  // Preserve the focused node as a link becomes historical text, and back again.
  // Give it a programmatic stop before removing href; restore href before removing
  // that stop. The unavailable target is never a Tab offer.
  if (!href) write(link, "tabindex", "-1");
  write(link, "href", href);
  if (href) write(link, "tabindex", null);
}

/** @param {HTMLElement} host */
export function createActivity(host) {
  const storageKey = ACTIVITY_VIEW + host.id;
  const saved = tabStore.get(storageKey);
  /** @type {ActivityReading} */
  const reading = saved
    ? JSON.parse(saved)
    : { open: false, shown: "[]", label: "Show activity", news: false };
  /** @type {{storageKey: string, reading: ActivityReading, restored: boolean, notice: Element | null, list: Element | null, empty: Element | null}} */
  const drawing = {
    storageKey,
    reading,
    restored: saved !== null,
    notice: null,
    list: null,
    empty: null,
  };
  let shown = reading;
  /** @type {ActivityCapabilities} */
  let capabilities = {};
  const notice = (/** @type {Element | undefined} */ node) => {
    if (!node) return;
    drawing.notice = node;
    offerActionElement(node, "inline", "lf-activity-news");
  };
  const target = (/** @type {ActivityRow} */ row) => {
    const thread = row.thread;
    const openThread = capabilities.openThread;
    if (thread)
      return html`<button
        ${ref(
          (node) =>
            node &&
            generatedElement(offerElement(node, "lf-activity-target"), {
              says: "echo",
            }),
        )}
        type="button"
        data-lf-carry=${`row-${row.id}`}
        @click=${openThread ? () => openThread(thread) : null}
      >
        ${row.label}
      </button>`;
    if (!row.widget && !row.label) return nothing;
    if (!row.widget) return html`<span class="lf-activity-target">${row.label}</span>`;
    const widget = row.widget;
    return html`<a
      class="lf-activity-target"
      data-lf-carry=${`row-${row.id}`}
      ${ref(
        (node) =>
          node &&
          refreshTarget(node, widget, keeps, capabilities.names ?? fragmentTarget),
      )}
      >${row.label}</a
    >`;
  };
  const rowTemplate = (/** @type {ActivityRow} */ row) =>
    html`<li class="lf-activity-row" ?data-lf-undone=${row.undone}>
      <p class="lf-activity-line">
        <strong class="lf-activity-actor">${row.actor}</strong>
        <span class="lf-activity-what">${row.what}</span> ${target(row)}
        <time
          class="lf-activity-time"
          datetime=${row.ts}
          title=${new Date(row.ts).toLocaleString()}
          >${capabilities.age?.(row.ts) ?? ""}</time
        >${row.undone ? html` <span class="lf-activity-undone">undone</span>` : nothing}
      </p>
      ${row.excerpt ? html`<p class="lf-activity-excerpt">${row.excerpt}</p>` : nothing}
    </li>`;
  const template = (next = shown, live = capabilities) => {
    shown = next;
    capabilities = live;
    /** @type {ActivityRow[]} */
    const rows = JSON.parse(shown.shown);
    const hidden = !shown.open && !capabilities.printing;
    return html`
      <button
        ${ref(notice)}
        type="button"
        data-lf-carry="notice"
        aria-expanded=${String(shown.open)}
        ?data-lf-news=${shown.news}
      >
        ${shown.label}
      </button>
      <ol
        class="lf-activity-list scroll"
        ?hidden=${hidden}
        ${ref((node) => {
          if (node) drawing.list = generatedElement(node, { says: false });
        })}
      >
        ${repeat(rows, (row) => row.id, rowTemplate)}
      </ol>
      <p
        class="lf-activity-empty"
        ?hidden=${hidden || rows.length > 0}
        ${ref((node) => {
          if (node) drawing.empty = generatedElement(node, { says: false });
        })}
      >
        Nothing shown yet.
      </p>
    `;
  };
  host.replaceChildren();
  return Object.assign(drawing, { render: template });
}
