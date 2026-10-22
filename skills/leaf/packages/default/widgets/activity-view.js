/* One Solid drawing from the retained tab-local reading through live history. The
 * returned paint closure keeps its template identities when the behavior module
 * adopts it. Retained rows are presentation snapshots, never semantic state; the
 * behavior module holds/reveals authoritative history through HeldReading and supplies
 * the live clock, thread action and current-document target reading. */
import {
  html,
  render,
  createSignal,
  createEffect,
  flush,
  For,
  Show,
  runWithOwner,
} from "/vendor/solid.js";

export const ACTIVITY_VIEW = "activity-reading:";

// Before modules load only the light document's ids can be read. The behavior module
// supplies fragmentTarget, which also finds shadow ids and refuses settled content.
const lightTarget = (fragment, doc) =>
  doc.readyState !== "loading" &&
  doc.getElementById(decodeURIComponent(fragment.slice(1)));

export function initialActivity(host, { offerElement, tabStore, keeps }) {
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
  const [state, setState] = createSignal(
    { shown: reading, live: {}, rows: JSON.parse(reading.shown) },
    { ownedWrite: true },
  );
  const hidden = () => !state().shown.open && !state().live.printing;
  const target = (row) => {
    if (row().thread)
      return html`<button
        type="button"
        ref=${(node) => offerElement(node, "lf-activity-target")}
        data-lf-carry=${() => `row-${row().id}`}
        data-lf-echo
        onClick=${() => state().live.openThread?.(row().thread)}
      >
        ${() => row().label}
      </button>`;
    if (!row().widget && !row().label) return null;
    if (!row().widget)
      return html`<span class="lf-activity-target">${() => row().label}</span>`;
    const link = html`<a
      class="lf-activity-target"
      data-lf-carry=${() => `row-${row().id}`}
      >${() => row().label}</a
    >`;
    createEffect(
      () => ({ row: row(), names: state().live.names ?? lightTarget }),
      ({ row, names }) => {
        const fragment = `#${encodeURIComponent(row.widget)}`;
        const href = names(fragment, host.ownerDocument) ? fragment : null;
        // A focused link first receives a programmatic stop before it loses href;
        // returning links receive href before that temporary stop leaves.
        if (!href) keeps(link, "tabindex", "-1");
        keeps(link, "href", href);
        if (href) keeps(link, "tabindex", null);
      },
    );
    return link;
  };
  const rowTemplate = (row) =>
    html`<li class="lf-activity-row" data-lf-undone=${() => (row().undone ? "" : null)}>
      <p class="lf-activity-line">
        <strong class="lf-activity-actor">${() => row().actor}</strong>
        <span class="lf-activity-what">${() => row().what}</span> ${target(row)}
        <time
          class="lf-activity-time"
          datetime=${() => row().ts}
          title=${() => new Date(row().ts).toLocaleString()}
          >${() => state().live.age?.(row().ts) ?? ""}</time
        >
        ${Show({
        get when() {
          return row().undone;
        },
        children: (_visible) => html` <span class="lf-activity-undone">undone</span>`,
      })}
      </p>
      ${Show({
      get when() {
        return row().excerpt;
      },
      children: (_visible) =>
        html`<p class="lf-activity-excerpt">${() => row().excerpt}</p>`,
    })}
    </li>`;
  const paint = (next = state().shown, live = state().live) => {
    flush(() => setState({ shown: next, live, rows: JSON.parse(next.shown) }));
  };
  host.replaceChildren();
  runWithOwner(null, () =>
    render(
      () =>
        html` <button
            ref=${(node) => {
      drawing.notice = node;
      offerElement(node, "lf-activity-news lf-thread-notice");
    }}
            type="button"
            data-lf-carry="notice"
            aria-expanded=${() => String(state().shown.open)}
            data-lf-news=${() => (state().shown.news ? "" : null)}
          >
            ${() => state().shown.label}
          </button>
          <ol
            class="lf-activity-list"
            data-lf-gen="1"
            hidden=${hidden}
            ref=${(node) => (drawing.list = node)}
          >
            ${For({
        get each() {
          return state().rows;
        },
        keyed: (row) => row.id,
        children: rowTemplate,
      })}
          </ol>
          <p
            class="lf-activity-empty"
            data-lf-gen="1"
            hidden=${() => hidden() || state().rows.length > 0}
            ref=${(node) => (drawing.empty = node)}
          >
            Nothing shown yet.
          </p>`,
      host,
    ),
  );
  // A missing destination may still be below this host while parsing. Refresh at
  // interactive, before module requests can delay DOMContentLoaded.
  if (host.ownerDocument.readyState === "loading")
    host.ownerDocument.addEventListener("readystatechange", () => paint(), {
      once: true,
    });
  return Object.assign(drawing, { paint });
}
