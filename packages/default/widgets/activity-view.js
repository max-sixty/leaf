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

function refreshTarget(link, row, write, names) {
  const fragment = `#${encodeURIComponent(row.widget)}`;
  const href = names(fragment, link.ownerDocument) ? fragment : null;
  // Preserve the focused node as a link becomes historical text, and back again.
  // Give it a programmatic stop before removing href; restore href before removing
  // that stop. The unavailable target is never a Tab offer.
  if (!href) write(link, "tabindex", "-1");
  write(link, "href", href);
  if (href) write(link, "tabindex", null);
}

export function createActivity(host) {
  const storageKey = ACTIVITY_VIEW + host.id;
  const saved = tabStore.get(storageKey);
  const reading = saved
    ? JSON.parse(saved)
    : { open: false, shown: "[]", label: "Show activity", news: false };
  const drawing = {
    storageKey,
    reading,
    restored: saved !== null,
    notice: null,
    list: null,
    empty: null,
  };
  let shown = reading;
  let capabilities = {};
  const notice = (node) => {
    if (!node) return;
    drawing.notice = node;
    offerActionElement(node, "inline", "lf-activity-news");
  };
  const target = (row) => {
    if (row.thread)
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
        @click=${
          capabilities.openThread ? () => capabilities.openThread(row.thread) : null
        }
      >
        ${row.label}
      </button>`;
    if (!row.widget && !row.label) return nothing;
    if (!row.widget) return html`<span class="lf-activity-target">${row.label}</span>`;
    return html`<a
      class="lf-activity-target"
      data-lf-carry=${`row-${row.id}`}
      ${ref(
        (node) =>
          node && refreshTarget(node, row, keeps, capabilities.names ?? fragmentTarget),
      )}
      >${row.label}</a
    >`;
  };
  const rowTemplate = (row) =>
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
