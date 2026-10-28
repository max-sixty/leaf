(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/default/widgets/tally-view.js
  function initialTally(host, { generatedElement, offerActionElement, keeps }) {
    const next = host.hasAttribute("next");
    let advance = null;
    const mark = (node) => node && generatedElement(node, { says: false });
    const control = (node) => node && offerActionElement(node, "word", "lf-tally-next");
    const template = ({
      ready = false,
      done = false,
      generic = "00 left to answer \xB7 00 on the agent",
      named = generic,
      words = "",
      onUser = false
    } = {}, onNext = null) => {
      advance = onNext;
      keeps(host, "data-lf-ready", ready ? "" : null);
      return html`<span class="lf-tally-face" ${ref(mark)}>
      <span class=${done ? "lf-tally-count lf-tally-done" : "lf-tally-count"}>
        <span class="lf-tally-room" aria-hidden="true">${generic}</span>
        <span class="lf-tally-room" aria-hidden="true">${named}</span>
        <span class="lf-tally-words">${words}</span>
      </span>
      ${next ? html`<button
              ${ref(control)}
              type="button"
              title="Next on me here"
              aria-controls=${host.getAttribute("for")}
              ?disabled=${!ready || !onUser}
              @mousedown=${(event) => event.preventDefault()}
              @click=${() => advance?.()}
            >
              Next on me
            </button>` : nothing}
    </span>`;
    };
    host.replaceChildren();
    return { render: template };
  }

  // packages/default/initial/lf-tally.js
  document.documentElement.lfInitial.register("lf-tally", initialTally);
})();
