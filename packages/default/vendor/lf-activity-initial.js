(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/default/widgets/activity-view.js
  var ACTIVITY_VIEW = "activity-reading:";
  var lightTarget = (fragment, doc) => doc.readyState !== "loading" && doc.getElementById(decodeURIComponent(fragment.slice(1)));
  function refreshTarget(link, row, write, names) {
    const fragment = `#${encodeURIComponent(row.widget)}`;
    const href = names(fragment, link.ownerDocument) ? fragment : null;
    if (!href) write(link, "tabindex", "-1");
    write(link, "href", href);
    if (href) write(link, "tabindex", null);
  }
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
    let shown = reading;
    let capabilities = {};
    const notice = (node) => {
      if (!node) return;
      drawing.notice = node;
      offerElement(node, "lf-activity-news lf-thread-notice");
    };
    const target = (row) => {
      if (row.thread)
        return html`<button
        ${ref((node) => node && offerElement(node, "lf-activity-target"))}
        type="button"
        data-lf-carry=${`row-${row.id}`}
        data-lf-echo
        @click=${capabilities.openThread ? () => capabilities.openThread(row.thread) : null}
      >
        ${row.label}
      </button>`;
      if (!row.widget && !row.label) return nothing;
      if (!row.widget) return html`<span class="lf-activity-target">${row.label}</span>`;
      return html`<a
      class="lf-activity-target"
      data-lf-carry=${`row-${row.id}`}
      ${ref(
        (node) => node && refreshTarget(node, row, keeps, capabilities.names ?? lightTarget)
      )}
      >${row.label}</a
    >`;
    };
    const rowTemplate = (row) => html`<li class="lf-activity-row" ?data-lf-undone=${row.undone}>
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
    const paint = (next = shown, live2 = capabilities) => {
      shown = next;
      capabilities = live2;
      const rows = JSON.parse(shown.shown);
      const hidden = !shown.open && !capabilities.printing;
      render(
        html`
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
          class="lf-activity-list"
          data-lf-gen="1"
          ?hidden=${hidden}
          ${ref((node) => {
          if (node) drawing.list = node;
        })}
        >
          ${repeat(rows, (row) => row.id, rowTemplate)}
        </ol>
        <p
          class="lf-activity-empty"
          data-lf-gen="1"
          ?hidden=${hidden || rows.length > 0}
          ${ref((node) => {
          if (node) drawing.empty = node;
        })}
        >
          Nothing shown yet.
        </p>
      `,
        host
      );
    };
    host.replaceChildren();
    paint();
    if (host.ownerDocument.readyState === "loading")
      host.ownerDocument.addEventListener("readystatechange", () => paint(), {
        once: true
      });
    return Object.assign(drawing, { paint });
  }

  // packages/default/initial/lf-activity.js
  document.documentElement.lfInitial.register("lf-activity", initialActivity);
})();
