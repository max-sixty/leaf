(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/diff/initial/lf-worktree.js
  document.documentElement.lfInitial.register("lf-worktree", (host, tools) => {
    const body = tools.authoredBody(document.createElement("div"));
    body.className = "lf-worktree-body";
    const key = `worktree:${host.id}`;
    const kept = tools.tabStore.get(key);
    const open = kept === null ? host.hasAttribute("open") : kept === "open";
    const remember = (event) => {
      const shown = event.currentTarget.open;
      tools.tabStore.set(
        key,
        shown === host.hasAttribute("open") ? null : shown ? "open" : "closed"
      );
    };
    const said = (node) => node && tools.generatedElement(node, { says: true });
    return {
      render() {
        const branch = host.getAttribute("branch");
        const head = host.getAttribute("head");
        const identity = [branch || (head ? "Detached HEAD" : null), head?.slice(0, 8)].filter(Boolean).join(" \xB7 ");
        const status = host.getAttribute("status");
        const word = { clean: "Clean", unavailable: "Unavailable" }[status];
        const files = Number(host.getAttribute("files"));
        const binary = Number(host.getAttribute("binary-files"));
        return html`<details
        class="lf-worktree-disclosure"
        ?open=${open}
        @toggle=${remember}
      >
        <summary class="lf-worktree-summary lf-disclosure-marker" ${ref(said)}>
          <span class="lf-worktree-identity"
            ><strong class="lf-worktree-label">${host.getAttribute("label")}</strong
            ><span class="lf-worktree-ref">${identity}</span></span
          >
          ${word ? html`<span class="lf-worktree-status">${word}</span>` : nothing}
          <span class="lf-worktree-stats"
            >${status === "unavailable" ? nothing : html`
                    <span>${files} ${files === 1 ? "file" : "files"}</span>
                    <span class="lf-worktree-additions"
                      >+${host.getAttribute("additions")}</span
                    >
                    <span class="lf-worktree-deletions"
                      >−${host.getAttribute("deletions")}</span
                    >
                    ${binary ? html`<span class="lf-worktree-binary">${binary} binary</span>` : nothing}
                  `}</span
          >
        </summary>
        <div class="lf-worktree-path" ${ref(said)}>
          <span>Worktree</span><code>${host.getAttribute("path")}</code>
        </div>
        ${body}
      </details>`;
      }
    };
  });
})();
