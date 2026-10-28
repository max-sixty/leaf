(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/diff/initial/lf-worktree-diffs.js
  document.documentElement.lfInitial.register("lf-worktree-diffs", (host, tools) => {
    const root = document.createElement("div");
    root.className = "lf-worktree-overview";
    tools.generatedElement(root, { says: true });
    host.prepend(root);
    return {
      root,
      render() {
        const members = [...host.querySelectorAll(":scope > lf-worktree")];
        const known = members.filter(
          (member) => member.getAttribute("status") !== "unavailable"
        );
        const sum = (attribute) => known.reduce(
          (total, member) => total + Number(member.getAttribute(attribute)),
          0
        );
        const binary = sum("binary-files");
        const files = sum("files");
        return html`<strong class="lf-worktree-total"
          >${members.length ? `${members.length} ${members.length === 1 ? "worktree" : "worktrees"}` : "No worktrees supplied"}</strong
        >
        <span class="lf-worktree-stats" ?hidden=${!known.length}>
          <span>${files} ${files === 1 ? "file" : "files"}</span>
          <span class="lf-worktree-additions">+${sum("additions")}</span>
          <span class="lf-worktree-deletions">−${sum("deletions")}</span>
          <span class="lf-worktree-binary" ?hidden=${!binary}>${binary} binary</span>
        </span>
        <span class="lf-worktree-unavailable" ?hidden=${known.length === members.length}
          >${members.length - known.length} unavailable</span
        >`;
      }
    };
  });
})();
