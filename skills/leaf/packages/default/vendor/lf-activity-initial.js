(() => {
  // leaf-initial-solid:solid
  var { createSignal, createMemo, createRoot, createReaction, getObserver, runWithOwner, createEffect, createTrackedEffect, createProjection, flush, untrack, For, Show, onCleanup, render, insert, spread, html } = document.documentElement.lfInitial.solid;

  // skills/leaf/packages/default/widgets/activity-view.js
  var ACTIVITY_VIEW = "activity-reading:";
  var lightTarget = (fragment, doc) => doc.readyState !== "loading" && doc.getElementById(decodeURIComponent(fragment.slice(1)));
  function initialActivity(host, { offerElement, tabStore, keeps }) {
    const storageKey = ACTIVITY_VIEW + host.id;
    const saved = tabStore.get(storageKey);
    const reading = saved ? JSON.parse(saved) : { open: false, shown: "[]", label: "Show activity", news: false };
    const drawing = {
      storageKey,
      reading,
      restored: saved !== null,
      notice: null,
      list: null,
      empty: null
    };
    const [state, setState] = createSignal(
      { shown: reading, live: {}, rows: JSON.parse(reading.shown) },
      { ownedWrite: true }
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
        ({ row: row2, names }) => {
          const fragment = `#${encodeURIComponent(row2.widget)}`;
          const href = names(fragment, host.ownerDocument) ? fragment : null;
          if (!href) keeps(link, "tabindex", "-1");
          keeps(link, "href", href);
          if (href) keeps(link, "tabindex", null);
        }
      );
      return link;
    };
    const rowTemplate = (row) => html`<li class="lf-activity-row" data-lf-undone=${() => row().undone ? "" : null}>
      <p class="lf-activity-line">
        <strong class="lf-activity-actor">${() => row().actor}</strong>${" "}
        <span class="lf-activity-what">${() => row().what}</span
        >${" "}${target(row)}${" "}
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
      children: (_visible) => html`${" "}<span class="lf-activity-undone">undone</span>`
    })}
      </p>
      ${Show({
      get when() {
        return row().excerpt;
      },
      children: (_visible) => html`<p class="lf-activity-excerpt">${() => row().excerpt}</p>`
    })}
    </li>`;
    const paint = (next = state().shown, live = state().live) => {
      flush(() => setState({ shown: next, live, rows: JSON.parse(next.shown) }));
    };
    host.replaceChildren();
    runWithOwner(
      null,
      () => render(
        () => html` <button
            ref=${(node) => {
          drawing.notice = node;
          offerElement(node, "lf-activity-news lf-thread-notice");
        }}
            type="button"
            data-lf-carry="notice"
            aria-expanded=${() => String(state().shown.open)}
            data-lf-news=${() => state().shown.news ? "" : null}
          >
            ${() => state().shown.label}
          </button>
          <ol
            class="lf-activity-list"
            data-lf-gen="1"
            hidden=${hidden}
            ref=${(node) => drawing.list = node}
          >
            ${For({
          get each() {
            return state().rows;
          },
          keyed: (row) => row.id,
          children: rowTemplate
        })}
          </ol>
          <p
            class="lf-activity-empty"
            data-lf-gen="1"
            hidden=${() => hidden() || state().rows.length > 0}
            ref=${(node) => drawing.empty = node}
          >
            Nothing shown yet.
          </p>`,
        host
      )
    );
    if (host.ownerDocument.readyState === "loading")
      host.ownerDocument.addEventListener("readystatechange", () => paint(), {
        once: true
      });
    return Object.assign(drawing, { paint });
  }

  // skills/leaf/packages/default/initial/lf-activity.js
  document.documentElement.lfInitial.register("lf-activity", initialActivity);
})();
