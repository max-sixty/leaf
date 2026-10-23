(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/default/initial/lf-approval.js
  document.documentElement.lfInitial.register("lf-approval", (host, tools) => {
    const root = host.ownerDocument.createElement("div");
    root.className = "lf-approval-actions";
    tools.generatedElement(root, { says: false });
    host.append(root);
    const drawing = { button: null, paint };
    function paint(approved = false) {
      render(
        html` <span
          class="lf-approval-status"
          role="status"
          ${ref((node) => node && tools.generatedElement(node, { says: true }))}
          data-room=${"Awaiting approval\nApproved"}
        >
          <span>${approved ? "Approved" : "Awaiting approval"}</span>
        </span>
        <button
          type="button"
          data-lf-carry="approve"
          data-room=${"Approve\nUndo approval"}
          ${ref((button) => {
          if (!button) return;
          drawing.button = button;
          tools.offerElement(button, "lf-btn");
        })}
        >
          <span>${approved ? "Undo approval" : "Approve"}</span>
        </button>`,
        root
      );
    }
    paint();
    return drawing;
  });
})();
