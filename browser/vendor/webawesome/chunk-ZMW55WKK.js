/*! Web Awesome 3.14.0 — MIT — licenses: webawesome.LICENSES.txt */
import{b as kt,c as At,d as B,e as a,f as Qt,g as ht,h as ut,i as Zt,k as Ft,l as te,m as ee,n as oe}from"./chunk-HU5QTSKI.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ie=class extends Event{constructor(t){super("wa-copy",{bubbles:!0,cancelable:!1,composed:!0}),this.detail=t}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var Mt=null,Nt=null,lo=7e3;function re(t){let e=document.createElement("div");return e.setAttribute("role","log"),e.setAttribute("aria-live",t),e.setAttribute("aria-relevant","additions"),Object.assign(e.style,{position:"absolute",width:"1px",height:"1px",margin:"-1px",padding:"0",border:"0",overflow:"hidden",clip:"rect(0 0 0 0)",clipPath:"inset(50%)",whiteSpace:"nowrap"}),e}function co(t){return t==="assertive"?(Nt??(Nt=document.body.appendChild(re("assertive"))),Nt):(Mt??(Mt=document.body.appendChild(re("polite"))),Mt)}function ne(t,e="polite"){if(!t)return;let i=co(e),o=document.createElement("div");o.textContent=t,i.appendChild(o),setTimeout(()=>o.remove(),lo)}import{css as po}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var se=po`
  :host {
    display: inline-block;
    color: var(--wa-color-neutral-on-quiet);
  }

  .copy-button__trigger {
    position: relative;
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background-color: transparent;
    border: none;
    border-radius: var(--wa-form-control-border-radius);
    color: inherit;
    font-size: inherit;
    height: calc(var(--wa-form-control-height) * 0.8);
    aspect-ratio: 1;
    cursor: pointer;
    transition-property: background-color, color;
    transition-duration: var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
  }

  @media (hover: hover) {
    .button:hover:not([disabled]) {
      background-color: var(--wa-color-neutral-fill-quiet);
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
    }
  }

  .button:focus-visible:not([disabled]) {
    background-color: var(--wa-color-neutral-fill-quiet);
    color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
  }

  .button:active:not([disabled]) {
    color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
  }

  .button:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  .button[disabled] {
    opacity: 0.5;
    cursor: not-allowed !important;
  }

  slot {
    display: inline-flex;
  }

  /* Icon swap animation */
  .show {
    animation: copy-button-icon-show var(--wa-transition-fast) var(--wa-transition-easing);
  }

  .hide {
    animation: copy-button-icon-show var(--wa-transition-fast) var(--wa-transition-easing) reverse;
  }

  @keyframes copy-button-icon-show {
    from {
      scale: 0.25;
      opacity: 0.25;
    }
    to {
      scale: 1;
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .show,
    .hide {
      animation-duration: 1ms;
    }
  }
`;import{css as ho}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ae=ho`
  .wa-visually-hidden:not(:focus-within),
  .wa-visually-hidden-force,
  .wa-visually-hidden-hint::part(hint),
  .wa-visually-hidden-label::part(label),
  .wa-visually-hidden-label::part(form-control-label) {
    top: 0px !important;
    left: 0px !important;
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    clip: rect(0 0 0 0) !important;
    clip-path: inset(50%) !important;
    border: none !important;
    overflow: hidden !important;
    white-space: nowrap !important;
    padding: 0 !important;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function Z(t,e){return new Promise(i=>{let o=new AbortController,{signal:r}=o;if(t.classList.contains(e))return;t.classList.add(e);let n=!1,s=()=>{n||(n=!0,t.classList.remove(e),i(),o.abort())};t.addEventListener("animationend",s,{once:!0,signal:r}),t.addEventListener("animationcancel",s,{once:!0,signal:r}),requestAnimationFrame(()=>{!n&&t.getAnimations().length===0&&s()})})}import{html as le}from"/vendor/lit.js";import{customElement as uo,property as Y,query as wt,state as Vt}from"/vendor/lit.js";import{classMap as fo}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ce="wa-internal-tooltip",Wt="__waCopyButtonAssignedId",T=class extends ht{constructor(){super(...arguments),this.localize=new ut(this),this.isCopying=!1,this.status="rest",this.hasCustomTrigger=!1,this.customTriggerEl=null,this.lightTooltip=null,this.feedbackTimeout=null,this.value="",this.from="",this.disabled=!1,this.copyLabel="",this.successLabel="",this.errorLabel="",this.feedbackDuration=1e3,this.tooltipPlacement="top",this.tooltip="full",this.handleDefaultSlotChange=()=>{let e=(this.defaultSlot?.assignedElements({flatten:!0})??[]).find(i=>i instanceof HTMLElement)??null;e!==this.customTriggerEl&&(this.releaseAssignedId(this.customTriggerEl),this.customTriggerEl=e),this.hasCustomTrigger=e!==null,e&&this.tooltip!=="none"?(e.id||(e.id=kt("wa-copy-button-trigger-"),e[Wt]=!0),this.ensureLightTooltip()):this.removeLightTooltip()}}get activeTooltip(){return this.lightTooltip??this.shadowTooltip??null}get currentLabel(){return this.status==="success"?this.successLabel||this.localize.term("copied"):this.status==="error"?this.errorLabel||this.localize.term("error"):this.copyLabel||this.localize.term("copy")}firstUpdated(t){super.firstUpdated(t),this.didSSR?this.updateComplete.then(()=>{this.handleDefaultSlotChange()}):this.handleDefaultSlotChange()}disconnectedCallback(){super.disconnectedCallback(),this.removeLightTooltip()}handleStatusChange(){this.customStates.set("success",this.status==="success"),this.customStates.set("error",this.status==="error"),this.syncTooltipText(),(this.status==="success"||this.status==="error")&&ne(this.currentLabel,"polite")}handleLabelChange(){this.syncTooltipText()}handleTooltipOptionsChange(){this.lightTooltip&&(this.lightTooltip.placement=this.tooltipPlacement,this.lightTooltip.disabled=this.disabled)}handleTooltipModeChange(t){this.tooltip==="none"?this.removeLightTooltip():t==="none"?this.handleDefaultSlotChange():this.lightTooltip&&this.lightTooltip.setAttribute("trigger",this.tooltip==="copy"?"manual":"hover focus")}releaseAssignedId(t){t&&t[Wt]&&(t.removeAttribute("id"),delete t[Wt])}ensureLightTooltip(){if(!this.customTriggerEl)return;let t=this.tooltip==="copy"?"manual":"hover focus";if(this.lightTooltip)this.lightTooltip.setAttribute("for",this.customTriggerEl.id),this.lightTooltip.setAttribute("trigger",t),this.lightTooltip.placement=this.tooltipPlacement,this.lightTooltip.disabled=this.disabled,this.lightTooltip.textContent=this.currentLabel;else{let e=document.createElement("wa-tooltip");e.setAttribute("slot",ce),e.setAttribute("part","feedback"),e.setAttribute("trigger",t),e.dataset.copyButtonTooltip="",e.setAttribute("for",this.customTriggerEl.id),e.placement=this.tooltipPlacement,e.disabled=this.disabled,e.textContent=this.currentLabel,this.appendChild(e),this.lightTooltip=e}}removeLightTooltip(){this.lightTooltip&&(this.releaseAssignedId(this.customTriggerEl),this.lightTooltip.remove(),this.lightTooltip=null)}syncTooltipText(){this.lightTooltip&&(this.lightTooltip.textContent=this.currentLabel)}async handleCopy(){if(this.disabled||this.isCopying)return;this.isCopying=!0;let t=this.value;if(this.from){let e=this.getRootNode(),i=this.from.includes("."),o=this.from.includes("[")&&this.from.includes("]"),r=this.from,n="";i?[r,n]=this.from.trim().split("."):o&&([r,n]=this.from.trim().replace(/\]$/,"").split("["));let s="getElementById"in e?e.getElementById(r):null;s?o?t=s.getAttribute(n)||"":i?t=s[n]||"":t=s.textContent||"":(this.showStatus("error"),this.dispatchEvent(new At))}if(!t)this.showStatus("error"),this.dispatchEvent(new At);else try{await navigator.clipboard.writeText(t),this.showStatus("success"),this.dispatchEvent(new ie({value:t}))}catch{this.showStatus("error"),this.dispatchEvent(new At)}}async showStatus(t){if(this.status=t,this.copyIcon){let o=t==="success"?this.successIcon:this.errorIcon;await Z(this.copyIcon,"hide"),this.copyIcon.hidden=!0,o.hidden=!1,await Z(o,"show")}await this.updateComplete;let e=this.tooltip==="none"?null:this.activeTooltip,i=null;e&&(e.show(),i=new Promise(o=>{e.addEventListener("wa-after-hide",()=>{this.feedbackTimeout!==null&&(clearTimeout(this.feedbackTimeout),this.feedbackTimeout=null),o()},{once:!0})}),this.feedbackTimeout=window.setTimeout(async()=>{this.feedbackTimeout=null,await e.hide()},this.feedbackDuration)),setTimeout(async()=>{if(i&&await i,this.copyIcon){let o=t==="success"?this.successIcon:this.errorIcon;await Z(o,"hide"),o.hidden=!0,this.copyIcon.hidden=!1,await Z(this.copyIcon,"show")}this.status="rest",this.isCopying=!1},this.feedbackDuration)}render(){let e=!this.hasCustomTrigger&&this.tooltip!=="none",i=this.tooltip==="copy"?"manual":"hover focus";return this.didSSR&&!this.hasUpdated&&(e=!1),le`
      <div class="copy-button__trigger" @click=${this.handleCopy}>
        <slot @slotchange=${this.handleDefaultSlotChange}></slot>
        <button
          class="button"
          part="button"
          type="button"
          id="copy-button"
          aria-label=${this.currentLabel}
          ?disabled=${this.disabled}
          ?hidden=${this.hasCustomTrigger}
        >
          <slot part="copy-icon" name="copy-icon">
            <wa-icon library="system" name="copy" variant="regular"></wa-icon>
          </slot>
          <slot part="success-icon" name="success-icon" variant="solid" hidden>
            <wa-icon library="system" name="check"></wa-icon>
          </slot>
          <slot part="error-icon" name="error-icon" variant="solid" hidden>
            <wa-icon library="system" name="xmark"></wa-icon>
          </slot>
        </button>

        ${e?le`
              <wa-tooltip
                part="feedback"
                for="copy-button"
                placement=${this.tooltipPlacement}
                trigger=${i}
                class=${fo({"copy-button-tooltip":!0,"copy-button-tooltip-success":this.status==="success","copy-button-tooltip-error":this.status==="error"})}
                ?disabled=${this.disabled}
                >${this.currentLabel}</wa-tooltip
              >
            `:""}
        <slot name="${ce}"></slot>
      </div>
    `}};T.css=[Qt,ae,se];a([wt('slot[name="copy-icon"]')],T.prototype,"copyIcon",2);a([wt('slot[name="success-icon"]')],T.prototype,"successIcon",2);a([wt('slot[name="error-icon"]')],T.prototype,"errorIcon",2);a([wt("slot:not([name])")],T.prototype,"defaultSlot",2);a([wt('wa-tooltip[part="feedback"]')],T.prototype,"shadowTooltip",2);a([Vt()],T.prototype,"isCopying",2);a([Vt()],T.prototype,"status",2);a([Vt()],T.prototype,"hasCustomTrigger",2);a([Y()],T.prototype,"value",2);a([Y()],T.prototype,"from",2);a([Y({type:Boolean,reflect:!0})],T.prototype,"disabled",2);a([Y({attribute:"copy-label"})],T.prototype,"copyLabel",2);a([Y({attribute:"success-label"})],T.prototype,"successLabel",2);a([Y({attribute:"error-label"})],T.prototype,"errorLabel",2);a([Y({attribute:"feedback-duration",type:Number})],T.prototype,"feedbackDuration",2);a([Y({attribute:"tooltip-placement",reflect:!0})],T.prototype,"tooltipPlacement",2);a([Y({reflect:!0})],T.prototype,"tooltip",2);a([B("status")],T.prototype,"handleStatusChange",1);a([B(["copyLabel","successLabel","errorLabel"])],T.prototype,"handleLabelChange",1);a([B(["tooltipPlacement","disabled"],{waitUntilFirstUpdate:!0})],T.prototype,"handleTooltipOptionsChange",1);a([B("tooltip",{waitUntilFirstUpdate:!0})],T.prototype,"handleTooltipModeChange",1);T=a([uo("wa-copy-button")],T);import{css as mo}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var pe=mo`
  :host {
    --max-width: 30ch;

    /** These styles are added so we don't interfere in the DOM. */
    display: inline-block;
    position: absolute;

    /** Defaults for inherited CSS properties */
    color: var(--wa-tooltip-content-color);
    font-size: var(--wa-tooltip-font-size);
    line-height: var(--wa-tooltip-line-height);
    text-align: start;
    white-space: normal;
  }

  .tooltip {
    --arrow-size: var(--wa-tooltip-arrow-size);
    --arrow-color: var(--wa-tooltip-background-color);
  }

  .tooltip::part(popup) {
    z-index: 1000;
  }

  .tooltip[placement^='top']::part(popup) {
    transform-origin: bottom;
  }

  .tooltip[placement^='bottom']::part(popup) {
    transform-origin: top;
  }

  .tooltip[placement^='left']::part(popup) {
    transform-origin: right;
  }

  .tooltip[placement^='right']::part(popup) {
    transform-origin: left;
  }

  .body {
    display: block;
    width: max-content;
    max-width: var(--max-width);
    border-radius: var(--wa-tooltip-border-radius);
    background-color: var(--wa-tooltip-background-color);
    border: var(--wa-tooltip-border-width) var(--wa-tooltip-border-style) var(--wa-tooltip-border-color);
    padding: 0.25em 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  .tooltip {
    --popup-border-width: var(--wa-tooltip-border-width);

    /* Inset box-shadow, not a border: Safari seams a clip-path edge that runs along a border. */
    &::part(arrow) {
      box-shadow: inset calc(-1 * var(--wa-tooltip-border-width)) calc(-1 * var(--wa-tooltip-border-width)) 0 0
        var(--wa-tooltip-border-color);
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var he=class extends Event{constructor(){super("wa-show",{bubbles:!0,cancelable:!0,composed:!0})}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ue=class extends Event{constructor(t){super("wa-hide",{bubbles:!0,cancelable:!0,composed:!0}),this.detail=t}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var de=class extends Event{constructor(){super("wa-after-hide",{bubbles:!0,cancelable:!1,composed:!0})}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var fe=class extends Event{constructor(){super("wa-after-show",{bubbles:!0,cancelable:!1,composed:!0})}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var me=class extends Event{constructor(){super("wa-reposition",{bubbles:!0,cancelable:!1,composed:!0})}};import{css as go}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ge=go`
  :host {
    --arrow-color: black;
    --arrow-size: var(--wa-tooltip-arrow-size);
    --popup-border-width: 0px;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);

    /*
     * These properties are computed to account for the arrow's dimensions after being rotated 45º. The constant
     * 0.7071 is derived from sin(45) to calculate the length of the arrow after rotation.
     *
     * The diamond will be translated inward by --arrow-base-offset, the border thickness, to centralise it on
     * the inner edge of the popup border. This also means we need to increase the size of the arrow by the
     * same amount to compensate.
     *
     * A diamond shaped clipping mask is used to avoid overlap of popup content. This extends slightly inward so
     * the popup border is covered with no sub-pixel rounding artifacts. The diamond corners are mitred at 22.5º
     * to properly merge any arrow border with the popup border. The constant 1.4142 is derived from 1 + tan(22.5).
     *
     */
    --arrow-base-offset: var(--popup-border-width);
    --arrow-size-diagonal: calc((var(--arrow-size) + var(--arrow-base-offset)) * 0.7071);
    --arrow-padding-offset: calc(var(--arrow-size-diagonal) - var(--arrow-size));
    --arrow-size-div: calc(var(--arrow-size-diagonal) * 2);
    --arrow-clipping-corner: calc(var(--arrow-base-offset) * 1.4142);

    display: contents;
  }

  .popup {
    position: absolute;
    isolation: isolate;
    max-width: var(--auto-size-available-width, none);
    max-height: var(--auto-size-available-height, none);

    /* Clear UA styles for [popover] */
    :where(&) {
      inset: unset;
      padding: unset;
      margin: unset;
      width: unset;
      height: unset;
      color: unset;
      background: unset;
      border: unset;
      overflow: unset;
    }
  }

  .popup-fixed {
    position: fixed;
  }

  .popup:not(.popup-active) {
    display: none;
  }

  .arrow {
    position: absolute;
    width: var(--arrow-size-div);
    height: var(--arrow-size-div);
    background: var(--arrow-color);
    z-index: 3;
    clip-path: polygon(
      var(--arrow-clipping-corner) 100%,
      var(--arrow-base-offset) calc(100% - var(--arrow-base-offset)),
      calc(var(--arrow-base-offset) - 2px) calc(100% - var(--arrow-base-offset)),
      calc(100% - var(--arrow-base-offset)) calc(var(--arrow-base-offset) - 2px),
      calc(100% - var(--arrow-base-offset)) var(--arrow-base-offset),
      100% var(--arrow-clipping-corner),
      100% 100%
    );
    rotate: 45deg;
  }

  :host([data-current-placement|='left']) .arrow {
    rotate: -45deg;
  }

  :host([data-current-placement|='right']) .arrow {
    rotate: 135deg;
  }

  :host([data-current-placement|='bottom']) .arrow {
    rotate: 225deg;
  }

  /* Hover bridge */
  .popup-hover-bridge:not(.popup-hover-bridge-visible) {
    display: none;
  }

  .popup-hover-bridge {
    position: fixed;
    z-index: 899;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    clip-path: polygon(
      var(--hover-bridge-top-left-x, 0) var(--hover-bridge-top-left-y, 0),
      var(--hover-bridge-top-right-x, 0) var(--hover-bridge-top-right-y, 0),
      var(--hover-bridge-bottom-right-x, 0) var(--hover-bridge-bottom-right-y, 0),
      var(--hover-bridge-bottom-left-x, 0) var(--hover-bridge-bottom-left-y, 0)
    );
  }

  /* Built-in animations */
  .show {
    animation: show var(--show-duration) ease;
  }

  .hide {
    animation: show var(--hide-duration) ease reverse;
  }

  @keyframes show {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .show-with-scale {
    animation: show-with-scale var(--show-duration) ease;
  }

  .hide-with-scale {
    animation: show-with-scale var(--hide-duration) ease reverse;
  }

  @keyframes show-with-scale {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }
`;var H=Math.min,M=Math.max,vt=Math.round,xt=Math.floor,q=t=>({x:t,y:t}),bo={left:"right",right:"left",bottom:"top",top:"bottom"};function It(t,e,i){return M(t,H(e,i))}function rt(t,e){return typeof t=="function"?t(e):t}function tt(t){return t.split("-")[0]}function nt(t){return t.split("-")[1]}function Ht(t){return t==="x"?"y":"x"}function Lt(t){return t==="y"?"height":"width"}function U(t){let e=t[0];return e==="t"||e==="b"?"y":"x"}function Rt(t){return Ht(U(t))}function ye(t,e,i){i===void 0&&(i=!1);let o=nt(t),r=Rt(t),n=Lt(r),s=r==="x"?o===(i?"end":"start")?"right":"left":o==="start"?"bottom":"top";return e.reference[n]>e.floating[n]&&(s=yt(s)),[s,yt(s)]}function ve(t){let e=yt(t);return[Ot(t),e,Ot(e)]}function Ot(t){return t.includes("start")?t.replace("start","end"):t.replace("end","start")}var be=["left","right"],we=["right","left"],wo=["top","bottom"],yo=["bottom","top"];function vo(t,e,i){switch(t){case"top":case"bottom":return i?e?we:be:e?be:we;case"left":case"right":return e?wo:yo;default:return[]}}function xe(t,e,i,o){let r=nt(t),n=vo(tt(t),i==="start",o);return r&&(n=n.map(s=>s+"-"+r),e&&(n=n.concat(n.map(Ot)))),n}function yt(t){let e=tt(t);return bo[e]+t.slice(e.length)}function xo(t){var e,i,o,r;return{top:(e=t.top)!=null?e:0,right:(i=t.right)!=null?i:0,bottom:(o=t.bottom)!=null?o:0,left:(r=t.left)!=null?r:0}}function qt(t){return typeof t!="number"?xo(t):{top:t,right:t,bottom:t,left:t}}function st(t){let{x:e,y:i,width:o,height:r}=t;return{width:o,height:r,top:i,left:e,right:e+o,bottom:i+r,x:e,y:i}}function Ce(t,e,i){let{reference:o,floating:r}=t,n=U(e),s=Rt(e),l=Lt(s),c=tt(e),p=n==="y",u=o.x+o.width/2-r.width/2,d=o.y+o.height/2-r.height/2,f=o[l]/2-r[l]/2,h;switch(c){case"top":h={x:u,y:o.y-r.height};break;case"bottom":h={x:u,y:o.y+o.height};break;case"right":h={x:o.x+o.width,y:d};break;case"left":h={x:o.x-r.width,y:d};break;default:h={x:o.x,y:o.y}}let m=nt(e);return m&&(h[s]+=f*(m==="end"?1:-1)*(i&&p?-1:1)),h}async function Ee(t,e){var i;e===void 0&&(e={});let{x:o,y:r,platform:n,rects:s,elements:l,strategy:c}=t,{boundary:p="clippingAncestors",rootBoundary:u="viewport",elementContext:d="floating",altBoundary:f=!1,padding:h=0}=rt(e,t),m=qt(h),y=l[f?d==="floating"?"reference":"floating":d],w=st(await n.getClippingRect({element:(i=await(n.isElement==null?void 0:n.isElement(y)))==null||i?y:y.contextElement||await(n.getDocumentElement==null?void 0:n.getDocumentElement(l.floating)),boundary:p,rootBoundary:u,strategy:c})),C=d==="floating"?{x:o,y:r,width:s.floating.width,height:s.floating.height}:s.reference,E=await(n.getOffsetParent==null?void 0:n.getOffsetParent(l.floating)),P=await(n.isElement==null?void 0:n.isElement(E))&&await(n.getScale==null?void 0:n.getScale(E))||{x:1,y:1},R=st(n.convertOffsetParentRelativeRectToViewportRelativeRect?await n.convertOffsetParentRelativeRectToViewportRelativeRect({elements:l,rect:C,offsetParent:E,strategy:c}):C);return{top:(w.top-R.top+m.top)/P.y,bottom:(R.bottom-w.bottom+m.bottom)/P.y,left:(w.left-R.left+m.left)/P.x,right:(R.right-w.right+m.right)/P.x}}var Co=50,Te=async(t,e,i)=>{let{placement:o="bottom",strategy:r="absolute",middleware:n=[],platform:s}=i,l=s.detectOverflow?s:{...s,detectOverflow:Ee},c=await(s.isRTL==null?void 0:s.isRTL(e)),p=await s.getElementRects({reference:t,floating:e,strategy:r}),{x:u,y:d}=Ce(p,o,c),f=o,h=0,m={};for(let g=0;g<n.length;g++){let y=n[g];if(!y)continue;let{name:w,fn:C}=y,{x:E,y:P,data:R,reset:A}=await C({x:u,y:d,initialPlacement:o,placement:f,strategy:r,middlewareData:m,rects:p,platform:l,elements:{reference:t,floating:e}});u=E??u,d=P??d,m[w]={...m[w],...R},A&&h<Co&&(h++,typeof A=="object"&&(A.placement&&(f=A.placement),A.rects&&(p=A.rects===!0?await s.getElementRects({reference:t,floating:e,strategy:r}):A.rects),{x:u,y:d}=Ce(p,f,c)),g=-1)}return{x:u,y:d,placement:f,strategy:r,middlewareData:m}},Pe=t=>({name:"arrow",options:t,async fn(e){let{x:i,y:o,placement:r,rects:n,platform:s,elements:l,middlewareData:c}=e,{element:p,padding:u=0}=rt(t,e)||{};if(p==null)return{};let d=qt(u),f={x:i,y:o},h=Rt(r),m=Lt(h),g=await s.getDimensions(p),y=h==="y",w=y?"top":"left",C=y?"bottom":"right",E=y?"clientHeight":"clientWidth",P=n.reference[m]+n.reference[h]-f[h]-n.floating[m],R=f[h]-n.reference[h],A=await(s.getOffsetParent==null?void 0:s.getOffsetParent(p)),$=A?A[E]:0;(!$||!await(s.isElement==null?void 0:s.isElement(A)))&&($=l.floating[E]||n.floating[m]);let z=P/2-R/2,V=$/2-g[m]/2-1,O=H(d[w],V),gt=H(d[C],V),bt=$-g[m]-gt,I=$/2-g[m]/2+z,_=It(O,I,bt),ot=!c.arrow&&nt(r)!=null&&I!==_&&n.reference[m]/2-(I<O?O:gt)-g[m]/2<0,X=ot?I<O?I-O:I-bt:0;return{[h]:f[h]+X,data:{[h]:_,centerOffset:I-_-X,...ot&&{alignmentOffset:X}},reset:ot}}});var Se=function(t){return t===void 0&&(t={}),{name:"flip",options:t,async fn(e){var i,o;let{placement:r,middlewareData:n,rects:s,initialPlacement:l,platform:c,elements:p}=e,{mainAxis:u=!0,crossAxis:d=!0,fallbackPlacements:f,fallbackStrategy:h="bestFit",fallbackAxisSideDirection:m="none",flipAlignment:g=!0,...y}=rt(t,e);if((i=n.arrow)!=null&&i.alignmentOffset)return{};let w=tt(r),C=U(l),E=tt(l)===l,P=await(c.isRTL==null?void 0:c.isRTL(p.floating)),R=f||(E||!g?[yt(l)]:ve(l)),A=m!=="none";!f&&A&&R.push(...xe(l,g,m,P));let $=[l,...R],z=await c.detectOverflow(e,y),V=[],O=((o=n.flip)==null?void 0:o.overflows)||[];if(u&&V.push(z[w]),d){let _=ye(r,s,P);V.push(z[_[0]],z[_[1]])}if(O=[...O,{placement:r,overflows:V}],!V.every(_=>_<=0)){var gt,bt;let _=(((gt=n.flip)==null?void 0:gt.index)||0)+1,ot=$[_];if(ot&&(!(d==="alignment"?C!==U(ot):!1)||O.every(F=>U(F.placement)===C?F.overflows[0]>0:!0)))return{data:{index:_,overflows:O},reset:{placement:ot}};let X=(bt=O.filter(it=>it.overflows[0]<=0).sort((it,F)=>it.overflows[1]-F.overflows[1])[0])==null?void 0:bt.placement;if(!X)switch(h){case"bestFit":{var I;let it=(I=O.filter(F=>{if(A){let Q=U(F.placement);return Q===C||Q==="y"}return!0}).map(F=>[F.placement,F.overflows.filter(Q=>Q>0).reduce((Q,ao)=>Q+ao,0)]).sort((F,Q)=>F[1]-Q[1])[0])==null?void 0:I[0];it&&(X=it);break}case"initialPlacement":X=l;break}if(r!==X)return{reset:{placement:X}}}return{}}}};var Eo=new Set(["left","top"]);async function To(t,e){let{placement:i,platform:o,elements:r}=t,n=await(o.isRTL==null?void 0:o.isRTL(r.floating)),s=tt(i),l=nt(i),c=U(i)==="y",p=Eo.has(s)?-1:1,u=n&&c?-1:1,d=rt(e,t),{mainAxis:f,crossAxis:h,alignmentAxis:m}=typeof d=="number"?{mainAxis:d,crossAxis:0,alignmentAxis:null}:{mainAxis:d.mainAxis||0,crossAxis:d.crossAxis||0,alignmentAxis:d.alignmentAxis};return l&&typeof m=="number"&&(h=l==="end"?m*-1:m),c?{x:h*u,y:f*p}:{x:f*p,y:h*u}}var ke=function(t){return t===void 0&&(t=0),{name:"offset",options:t,async fn(e){var i,o;let{x:r,y:n,placement:s,middlewareData:l}=e,c=await To(e,t);return s===((i=l.offset)==null?void 0:i.placement)&&(o=l.arrow)!=null&&o.alignmentOffset?{}:{x:r+c.x,y:n+c.y,data:{...c,placement:s}}}}},Ae=function(t){return t===void 0&&(t={}),{name:"shift",options:t,async fn(e){let{x:i,y:o,placement:r,platform:n}=e,{mainAxis:s=!0,crossAxis:l=!1,limiter:c={fn:C=>{let{x:E,y:P}=C;return{x:E,y:P}}},...p}=rt(t,e),u={x:i,y:o},d=await n.detectOverflow(e,p),f=U(r),h=Ht(f),m=u[h],g=u[f],y=(C,E)=>It(E+d[C==="y"?"top":"left"],E,E-d[C==="y"?"bottom":"right"]);s&&(m=y(h,m)),l&&(g=y(f,g));let w=c.fn({...e,[h]:m,[f]:g});return{...w,data:{x:w.x-i,y:w.y-o,enabled:{[h]:s,[f]:l}}}}}};var Oe=function(t){return t===void 0&&(t={}),{name:"size",options:t,async fn(e){let{placement:i,rects:o,platform:r,elements:n}=e,{apply:s=()=>{},...l}=rt(t,e),c=await r.detectOverflow(e,l),p=tt(i),u=nt(i),d=U(i)==="y",{width:f,height:h}=o.floating,m,g;p==="top"||p==="bottom"?(m=p,g=u===(await(r.isRTL==null?void 0:r.isRTL(n.floating))?"start":"end")?"left":"right"):(g=p,m=u==="end"?"top":"bottom");let y=h-c.top-c.bottom,w=f-c.left-c.right,C=H(h-c[m],y),E=H(f-c[g],w),P=e.middlewareData.shift,R=!P,A=C,$=E;P!=null&&P.enabled.x&&($=w),P!=null&&P.enabled.y&&(A=y),R&&!u&&(d?$=f-2*M(c.left,c.right):A=h-2*M(c.top,c.bottom)),await s({...e,availableWidth:$,availableHeight:A});let z=await r.getDimensions(n.floating);return f!==z.width||h!==z.height?{reset:{rects:!0}}:{}}}};function $t(){return typeof window<"u"}function lt(t){return Re(t)?(t.nodeName||"").toLowerCase():"#document"}function L(t){var e;return(t==null||(e=t.ownerDocument)==null?void 0:e.defaultView)||window}function j(t){var e;return(e=(Re(t)?t.ownerDocument:t.document)||window.document)==null?void 0:e.documentElement}function Re(t){return $t()?t instanceof Node||t instanceof L(t).Node:!1}function N(t){return $t()?t instanceof Element||t instanceof L(t).Element:!1}function J(t){return $t()?t instanceof HTMLElement||t instanceof L(t).HTMLElement:!1}function Le(t){return!$t()||typeof ShadowRoot>"u"?!1:t instanceof ShadowRoot||t instanceof L(t).ShadowRoot}function Ct(t){let{overflow:e,overflowX:i,overflowY:o,display:r}=W(t);return/auto|scroll|overlay|hidden|clip/.test(e+o+i)&&r!=="inline"&&r!=="contents"}function $e(t){return/^(table|td|th)$/.test(lt(t))}function Et(t){try{if(t.matches(":popover-open"))return!0}catch{}try{return t.matches(":modal")}catch{return!1}}var Po=/transform|translate|scale|rotate|perspective|filter/,So=/paint|layout|strict|content/,at=t=>!!t&&t!=="none",Ut;function dt(t){let e=N(t)?W(t):t;return at(e.transform)||at(e.translate)||at(e.scale)||at(e.rotate)||at(e.perspective)||!Bt()&&(at(e.backdropFilter)||at(e.filter))||Po.test(e.willChange||"")||So.test(e.contain||"")}function Be(t){let e=et(t);for(;J(e)&&!ft(e);){if(dt(e))return e;if(Et(e))return null;e=et(e)}return null}function Bt(){return Ut==null&&(Ut=typeof CSS<"u"&&CSS.supports&&CSS.supports("-webkit-backdrop-filter","none")),Ut}function ft(t){return/^(html|body|#document)$/.test(lt(t))}function W(t){return L(t).getComputedStyle(t)}function Tt(t){return N(t)?{scrollLeft:t.scrollLeft,scrollTop:t.scrollTop}:{scrollLeft:t.scrollX,scrollTop:t.scrollY}}function et(t){if(lt(t)==="html")return t;let e=t.assignedSlot||t.parentNode||Le(t)&&t.host||j(t);return Le(e)?e.host:e}function De(t){let e=et(t);return ft(e)?(t.ownerDocument||t).body:J(e)&&Ct(e)?e:De(e)}function G(t,e,i){var o;e===void 0&&(e=[]),i===void 0&&(i=!0);let r=De(t),n=r===((o=t.ownerDocument)==null?void 0:o.body),s=L(r);if(n){let l=Dt(s);return e.concat(s,s.visualViewport||[],Ct(r)?r:[],l&&i?G(l):[])}else return e.concat(r,G(r,[],i))}function Dt(t){return t.parent&&Object.getPrototypeOf(t.parent)?t.frameElement:null}function Fe(t){let e=W(t),i=parseFloat(e.width)||0,o=parseFloat(e.height)||0,r=J(t),n=r?t.offsetWidth:i,s=r?t.offsetHeight:o,l=vt(i)!==n||vt(o)!==s;return l&&(i=n,o=s),{width:i,height:o,$:l}}function Kt(t){return N(t)?t:t.contextElement}function mt(t){let e=Kt(t);if(!J(e))return q(1);let i=e.getBoundingClientRect(),{width:o,height:r,$:n}=Fe(e),s=(n?vt(i.width):i.width)/o,l=(n?vt(i.height):i.height)/r;return(!s||!Number.isFinite(s))&&(s=1),(!l||!Number.isFinite(l))&&(l=1),{x:s,y:l}}var ko=q(0);function Me(t){let e=L(t);return!Bt()||!e.visualViewport?ko:{x:e.visualViewport.offsetLeft,y:e.visualViewport.offsetTop}}function Ao(t,e,i){return e===void 0&&(e=!1),!!i&&e&&i===L(t)}function ct(t,e,i,o){e===void 0&&(e=!1),i===void 0&&(i=!1);let r=t.getBoundingClientRect(),n=Kt(t),s=q(1);e&&(o?N(o)&&(s=mt(o)):s=mt(t));let l=Ao(n,i,o)?Me(n):q(0),c=(r.left+l.x)/s.x,p=(r.top+l.y)/s.y,u=r.width/s.x,d=r.height/s.y;if(n&&o){let f=L(n),h=N(o)?L(o):o,m=f,g=Dt(m);for(;g&&h!==m;){let y=mt(g),w=g.getBoundingClientRect(),C=W(g),E=w.left+(g.clientLeft+parseFloat(C.paddingLeft))*y.x,P=w.top+(g.clientTop+parseFloat(C.paddingTop))*y.y;c*=y.x,p*=y.y,u*=y.x,d*=y.y,c+=E,p+=P,m=L(g),g=Dt(m)}}return st({width:u,height:d,x:c,y:p})}function zt(t,e){let i=Tt(t).scrollLeft;return e?e.left+i:ct(j(t)).left+i}function Ne(t,e){let i=t.getBoundingClientRect(),o=i.left+e.scrollLeft-zt(t,i),r=i.top+e.scrollTop;return{x:o,y:r}}function Oo(t){let{elements:e,rect:i,offsetParent:o,strategy:r}=t,n=r==="fixed",s=j(o),l=e?Et(e.floating):!1;if(o===s||l&&n)return i;let c={scrollLeft:0,scrollTop:0},p=q(1),u=q(0),d=J(o);if((d||!n)&&((lt(o)!=="body"||Ct(s))&&(c=Tt(o)),d)){let h=ct(o);p=mt(o),u.x=h.x+o.clientLeft,u.y=h.y+o.clientTop}let f=s&&!d&&!n?Ne(s,c):q(0);return{width:i.width*p.x,height:i.height*p.y,x:i.x*p.x-c.scrollLeft*p.x+u.x+f.x,y:i.y*p.y-c.scrollTop*p.y+u.y+f.y}}function Lo(t){return t.getClientRects?Array.from(t.getClientRects()):[]}function Ro(t){let e=Tt(t),i=t.ownerDocument.body,o=M(t.scrollWidth,t.clientWidth,i.scrollWidth,i.clientWidth),r=M(t.scrollHeight,t.clientHeight,i.scrollHeight,i.clientHeight),n=-e.scrollLeft+zt(t),s=-e.scrollTop;return W(i).direction==="rtl"&&(n+=M(t.clientWidth,i.clientWidth)-o),{width:o,height:r,x:n,y:s}}var $o=25;function Bo(t,e,i){i===void 0&&(i="viewport");let o=i==="layoutViewport",r=L(t),n=j(t),s=r.visualViewport,l=n.clientWidth,c=n.clientHeight,p=0,u=0;if(s){let f=!Bt()||e==="fixed";o?f||(p=-s.offsetLeft,u=-s.offsetTop):(l=s.width,c=s.height,f&&(p=s.offsetLeft,u=s.offsetTop))}if(zt(n)<=0){let f=n.ownerDocument,h=f.body,m=getComputedStyle(h),g=f.compatMode==="CSS1Compat"&&parseFloat(m.marginLeft)+parseFloat(m.marginRight)||0,y=Math.abs(n.clientWidth-h.clientWidth-g),w=getComputedStyle(n).scrollbarGutter==="stable both-edges"?y/2:y;w<=$o&&(l-=w)}return{width:l,height:c,x:p,y:u}}function Do(t,e){let i=ct(t,!0,e==="fixed"),o=i.top+t.clientTop,r=i.left+t.clientLeft,n=mt(t),s=t.clientWidth*n.x,l=t.clientHeight*n.y,c=r*n.x,p=o*n.y;return{width:s,height:l,x:c,y:p}}function ze(t,e,i){let o;if(e==="viewport"||e==="layoutViewport")o=Bo(t,i,e);else if(e==="document")o=Ro(j(t));else if(N(e))o=Do(e,i);else{let r=Me(t);o={x:e.x-r.x,y:e.y-r.y,width:e.width,height:e.height}}return st(o)}function zo(t,e){let i=e.get(t);if(i)return i;let o=G(t,[],!1).filter(l=>N(l)&&lt(l)!=="body"),r=null,n=W(t).position==="fixed",s=n?et(t):t;for(;N(s)&&!ft(s);){let l=W(s),c=dt(s),p=r?r.position:n?"fixed":"";!c&&(p==="fixed"||p==="absolute"&&l.position==="static")?o=o.filter(d=>d!==s):r=l,s=et(s)}return e.set(t,o),o}function _o(t){let{element:e,boundary:i,rootBoundary:o,strategy:r}=t,s=[...i==="clippingAncestors"?Et(e)?[]:zo(e,this._c):[].concat(i),o],l=ze(e,s[0],r),c=l.top,p=l.right,u=l.bottom,d=l.left;for(let f=1;f<s.length;f++){let h=ze(e,s[f],r);c=M(h.top,c),p=H(h.right,p),u=H(h.bottom,u),d=M(h.left,d)}return{width:p-d,height:u-c,x:d,y:c}}function Fo(t){let{width:e,height:i}=Fe(t);return{width:e,height:i}}function Mo(t,e,i){let o=J(e),r=j(e),n=i==="fixed",s=ct(t,!0,n,e),l={scrollLeft:0,scrollTop:0},c=q(0);if((o||!n)&&((lt(e)!=="body"||Ct(r))&&(l=Tt(e)),o)){let f=ct(e,!0,n,e);c.x=f.x+e.clientLeft,c.y=f.y+e.clientTop}!o&&r&&(c.x=zt(r));let p=r&&!o&&!n?Ne(r,l):q(0),u=s.left+l.scrollLeft-c.x-p.x,d=s.top+l.scrollTop-c.y-p.y;return{x:u,y:d,width:s.width,height:s.height}}function jt(t){return W(t).position==="static"}function _e(t,e){if(!J(t)||W(t).position==="fixed")return null;if(e)return e(t);let i=t.offsetParent;return j(t)===i&&(i=i.ownerDocument.body),i}function We(t,e){let i=L(t);if(Et(t))return i;if(!J(t)){let r=et(t);for(;r&&!ft(r);){if(N(r)&&!jt(r))return r;r=et(r)}return i}let o=_e(t,e);for(;o&&$e(o)&&jt(o);)o=_e(o,e);return o&&ft(o)&&jt(o)&&!dt(o)?i:o||Be(t)||i}var No=async function(t){let e=this.getOffsetParent||We,i=this.getDimensions,o=await i(t.floating);return{reference:Mo(t.reference,await e(t.floating),t.strategy),floating:{x:0,y:0,width:o.width,height:o.height}}};function Wo(t){return W(t).direction==="rtl"}var Pt={convertOffsetParentRelativeRectToViewportRelativeRect:Oo,getDocumentElement:j,getClippingRect:_o,getOffsetParent:We,getElementRects:No,getClientRects:Lo,getDimensions:Fo,getScale:mt,isElement:N,isRTL:Wo};function Ve(t,e){return t.x===e.x&&t.y===e.y&&t.width===e.width&&t.height===e.height}function Vo(t,e,i){let o=null,r,n=j(t);function s(){var u;clearTimeout(r),(u=o)==null||u.disconnect(),o=null}function l(u,d){u===void 0&&(u=!1),d===void 0&&(d=1),s();let f=t.getBoundingClientRect(),{left:h,top:m,width:g,height:y}=f;if(u||e(),!g||!y)return;let w=xt(m),C=xt(n.clientWidth-(h+g)),E=xt(n.clientHeight-(m+y)),P=xt(h),A={rootMargin:-w+"px "+-C+"px "+-E+"px "+-P+"px",threshold:M(0,H(1,d))||1},$=!0;function z(V){let O=V[0].intersectionRatio;if(!Ve(f,t.getBoundingClientRect()))return l();if(O!==d){if(!$)return l();O?l(!1,O):r=setTimeout(()=>{l(!1,1e-7)},1e3)}$=!1}try{o=new IntersectionObserver(z,{...A,root:n.ownerDocument})}catch{o=new IntersectionObserver(z,A)}o.observe(t)}let c=L(t),p=()=>l(i);return c.addEventListener("resize",p),l(!0),()=>{c.removeEventListener("resize",p),s()}}function Ie(t,e,i,o){o===void 0&&(o={});let{ancestorScroll:r=!0,ancestorResize:n=!0,elementResize:s=typeof ResizeObserver=="function",layoutShift:l=typeof IntersectionObserver=="function",animationFrame:c=!1}=o,p=Kt(t),u=r||n?[...p?G(p):[],...e?G(e):[]]:[];u.forEach(w=>{r&&w.addEventListener("scroll",i),n&&w.addEventListener("resize",i)});let d=p&&l?Vo(p,i,n):null,f=-1,h=null;s&&(h=new ResizeObserver(w=>{let[C]=w;C&&C.target===p&&h&&e&&(h.unobserve(e),cancelAnimationFrame(f),f=requestAnimationFrame(()=>{var E;(E=h)==null||E.observe(e)})),i()}),p&&!c&&h.observe(p),e&&h.observe(e));let m,g=c?ct(t):null;c&&y();function y(){let w=ct(t);g&&!Ve(g,w)&&i(),g=w,m=requestAnimationFrame(y)}return i(),()=>{var w;u.forEach(C=>{r&&C.removeEventListener("scroll",i),n&&C.removeEventListener("resize",i)}),d?.(),(w=h)==null||w.disconnect(),h=null,c&&cancelAnimationFrame(m)}}var He=ke;var qe=Ae,Ue=Se,Xt=Oe;var je=Pe;var Ke=(t,e,i)=>{let o=new Map,r=i??{},n={...Pt,...r.platform,_c:o};return Te(t,e,{...r,platform:n})};function Xe(t){return Io(t)}function Yt(t){return t.assignedSlot?t.assignedSlot:t.parentNode instanceof ShadowRoot?t.parentNode.host:t.parentNode}function Io(t){for(let e=t;e;e=Yt(e))if(e instanceof Element&&getComputedStyle(e).display==="none")return null;for(let e=Yt(t);e;e=Yt(e)){if(!(e instanceof Element))continue;let i=getComputedStyle(e);if(i.display!=="contents"&&(i.position!=="static"||dt(i)||e.tagName==="BODY"))return e}return null}import{html as Ye}from"/vendor/lit.js";import{customElement as Ho,property as S,query as Qe}from"/vendor/lit.js";import{classMap as Ge}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function Je(t){return t!==null&&typeof t=="object"&&"getBoundingClientRect"in t&&("contextElement"in t?t instanceof Element:!0)}var qo=!!globalThis?.HTMLElement?.prototype.hasOwnProperty("popover"),v=class extends ht{constructor(){super(...arguments),this.localize=new ut(this),this.SUPPORTS_POPOVER=!1,this.active=!1,this.placement="top",this.boundary="viewport",this.distance=0,this.skidding=0,this.arrow=!1,this.arrowPlacement="anchor",this.arrowPadding=10,this.flip=!1,this.flipFallbackPlacements="",this.flipFallbackStrategy="best-fit",this.flipPadding=0,this.shift=!1,this.shiftPadding=0,this.autoSizePadding=0,this.hoverBridge=!1,this.updateHoverBridge=()=>{if(this.hoverBridge&&this.anchorEl&&this.popup){let t=this.anchorEl.getBoundingClientRect(),e=this.popup.getBoundingClientRect(),i=this.placement.includes("top")||this.placement.includes("bottom"),o=0,r=0,n=0,s=0,l=0,c=0,p=0,u=0;i?t.top<e.top?(o=t.left,r=t.bottom,n=t.right,s=t.bottom,l=e.left,c=e.top,p=e.right,u=e.top):(o=e.left,r=e.bottom,n=e.right,s=e.bottom,l=t.left,c=t.top,p=t.right,u=t.top):t.left<e.left?(o=t.right,r=t.top,n=e.left,s=e.top,l=t.right,c=t.bottom,p=e.left,u=e.bottom):(o=e.right,r=e.top,n=t.left,s=t.top,l=e.right,c=e.bottom,p=t.left,u=t.bottom),this.style.setProperty("--hover-bridge-top-left-x",`${o}px`),this.style.setProperty("--hover-bridge-top-left-y",`${r}px`),this.style.setProperty("--hover-bridge-top-right-x",`${n}px`),this.style.setProperty("--hover-bridge-top-right-y",`${s}px`),this.style.setProperty("--hover-bridge-bottom-left-x",`${l}px`),this.style.setProperty("--hover-bridge-bottom-left-y",`${c}px`),this.style.setProperty("--hover-bridge-bottom-right-x",`${p}px`),this.style.setProperty("--hover-bridge-bottom-right-y",`${u}px`)}}}async connectedCallback(){super.connectedCallback(),await this.updateComplete,this.SUPPORTS_POPOVER=qo,this.start()}disconnectedCallback(){super.disconnectedCallback(),this.stop()}async updated(t){super.updated(t),t.has("active")&&(this.active?this.start():this.stop()),t.has("anchor")&&this.handleAnchorChange(),this.active&&(await this.updateComplete,this.reposition())}async handleAnchorChange(){if(await this.stop(),this.anchor&&typeof this.anchor=="string"){let t=this.getRootNode();this.anchorEl=t.getElementById(this.anchor)}else this.anchor instanceof Element||Je(this.anchor)?this.anchorEl=this.anchor:this.anchorEl=this.querySelector('[slot="anchor"]');this.anchorEl instanceof HTMLSlotElement&&(this.anchorEl=this.anchorEl.assignedElements({flatten:!0})[0]),this.anchorEl&&this.start()}start(){!this.anchorEl||!this.active||!this.isConnected||(this.popup?.showPopover?.(),this.cleanup=Ie(this.anchorEl,this.popup,()=>{this.reposition()}))}async stop(){return new Promise(t=>{this.popup?.hidePopover?.(),this.cleanup?(this.cleanup(),this.cleanup=void 0,this.removeAttribute("data-current-placement"),this.style.removeProperty("--auto-size-available-width"),this.style.removeProperty("--auto-size-available-height"),requestAnimationFrame(()=>t())):t()})}reposition(){if(!this.active||!this.anchorEl||!this.popup)return;let t=[He({mainAxis:this.distance,crossAxis:this.skidding})];this.sync?t.push(Xt({apply:({rects:o})=>{let r=this.sync==="width"||this.sync==="both",n=this.sync==="height"||this.sync==="both";this.popup.style.width=r?`${o.reference.width}px`:"",this.popup.style.height=n?`${o.reference.height}px`:""}})):(this.popup.style.width="",this.popup.style.height="");let e;this.SUPPORTS_POPOVER&&!Je(this.anchor)&&this.boundary==="scroll"&&(e=G(this.anchorEl).filter(o=>o instanceof Element)),this.flip&&t.push(Ue({boundary:this.flipBoundary||e,fallbackPlacements:this.flipFallbackPlacements,fallbackStrategy:this.flipFallbackStrategy==="best-fit"?"bestFit":"initialPlacement",padding:this.flipPadding})),this.shift&&t.push(qe({boundary:this.shiftBoundary||e,padding:this.shiftPadding})),this.autoSize?t.push(Xt({boundary:this.autoSizeBoundary||e,padding:this.autoSizePadding,apply:({availableWidth:o,availableHeight:r})=>{this.autoSize==="vertical"||this.autoSize==="both"?this.style.setProperty("--auto-size-available-height",`${r}px`):this.style.removeProperty("--auto-size-available-height"),this.autoSize==="horizontal"||this.autoSize==="both"?this.style.setProperty("--auto-size-available-width",`${o}px`):this.style.removeProperty("--auto-size-available-width")}})):(this.style.removeProperty("--auto-size-available-width"),this.style.removeProperty("--auto-size-available-height")),this.arrow&&t.push(je({element:this.arrowEl,padding:this.arrowPadding}));let i=this.SUPPORTS_POPOVER?o=>Pt.getOffsetParent(o,Xe):Pt.getOffsetParent;Ke(this.anchorEl,this.popup,{placement:this.placement,middleware:t,strategy:this.SUPPORTS_POPOVER?"absolute":"fixed",platform:{...Pt,getOffsetParent:i}}).then(({x:o,y:r,middlewareData:n,placement:s})=>{let l=this.localize.dir()==="rtl",c={top:"bottom",right:"left",bottom:"top",left:"right"}[s.split("-")[0]];if(this.setAttribute("data-current-placement",s),Object.assign(this.popup.style,{left:`${o}px`,top:`${r}px`}),this.arrow){let p=n.arrow.x,u=n.arrow.y,d="",f="",h="",m="";if(this.arrowPlacement==="start"){let g=typeof p=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"";d=typeof u=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"",f=l?g:"",m=l?"":g}else if(this.arrowPlacement==="end"){let g=typeof p=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"";f=l?"":g,m=l?g:"",h=typeof u=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:""}else this.arrowPlacement==="center"?(m=typeof p=="number"?"calc(50% - var(--arrow-size-diagonal))":"",d=typeof u=="number"?"calc(50% - var(--arrow-size-diagonal))":""):(m=typeof p=="number"?`${p}px`:"",d=typeof u=="number"?`${u}px`:"");Object.assign(this.arrowEl.style,{top:d,right:f,bottom:h,left:m,[c]:"calc(var(--arrow-base-offset) - var(--arrow-size-diagonal))"})}}),requestAnimationFrame(()=>this.updateHoverBridge()),this.dispatchEvent(new me)}render(){return Ye`
      <slot name="anchor" @slotchange=${this.handleAnchorChange}></slot>

      <span
        part="hover-bridge"
        class=${Ge({"popup-hover-bridge":!0,"popup-hover-bridge-visible":this.hoverBridge&&this.active})}
      ></span>

      <div
        popover="manual"
        part="popup"
        class=${Ge({popup:!0,"popup-active":this.active,"popup-fixed":!this.SUPPORTS_POPOVER,"popup-has-arrow":this.arrow})}
      >
        <slot></slot>
        ${this.arrow?Ye`<div part="arrow" class="arrow" role="presentation"></div>`:""}
      </div>
    `}};v.css=ge;a([Qe(".popup")],v.prototype,"popup",2);a([Qe(".arrow")],v.prototype,"arrowEl",2);a([S({attribute:!1,type:Boolean})],v.prototype,"SUPPORTS_POPOVER",2);a([S()],v.prototype,"anchor",2);a([S({type:Boolean,reflect:!0})],v.prototype,"active",2);a([S({reflect:!0})],v.prototype,"placement",2);a([S()],v.prototype,"boundary",2);a([S({type:Number})],v.prototype,"distance",2);a([S({type:Number})],v.prototype,"skidding",2);a([S({type:Boolean})],v.prototype,"arrow",2);a([S({attribute:"arrow-placement"})],v.prototype,"arrowPlacement",2);a([S({attribute:"arrow-padding",type:Number})],v.prototype,"arrowPadding",2);a([S({type:Boolean})],v.prototype,"flip",2);a([S({attribute:"flip-fallback-placements",converter:{fromAttribute:t=>t.split(" ").map(e=>e.trim()).filter(e=>e!==""),toAttribute:t=>t.join(" ")}})],v.prototype,"flipFallbackPlacements",2);a([S({attribute:"flip-fallback-strategy"})],v.prototype,"flipFallbackStrategy",2);a([S({type:Object})],v.prototype,"flipBoundary",2);a([S({attribute:"flip-padding",type:Number})],v.prototype,"flipPadding",2);a([S({type:Boolean})],v.prototype,"shift",2);a([S({type:Object})],v.prototype,"shiftBoundary",2);a([S({attribute:"shift-padding",type:Number})],v.prototype,"shiftPadding",2);a([S({attribute:"auto-size"})],v.prototype,"autoSize",2);a([S()],v.prototype,"sync",2);a([S({type:Object})],v.prototype,"autoSizeBoundary",2);a([S({attribute:"auto-size-padding",type:Number})],v.prototype,"autoSizePadding",2);a([S({attribute:"hover-bridge",type:Boolean})],v.prototype,"hoverBridge",2);v=a([Ho("wa-popup")],v);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var pt=[];function Ze(t){_t(t),pt.push(t)}function _t(t){for(let e=pt.length-1;e>=0;e--)if(pt[e]===t){pt.splice(e,1);break}}function to(t){return pt.length>0&&pt[pt.length-1]===t}/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function Gt(t,e){return new Promise(i=>{function o(r){r.target===t&&(t.removeEventListener(e,o),i())}t.addEventListener(e,o)})}import{html as Uo}from"/vendor/lit.js";import{customElement as jo,property as K,query as Jt,state as Ko}from"/vendor/lit.js";import{classMap as Xo}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function eo(t,e){for(;e;){if(e===t)return!0;e instanceof Element&&e.assignedSlot?e=e.assignedSlot:e.parentNode?e=e.parentNode:e instanceof ShadowRoot?e=e.host:e=null}return!1}var k=class extends ht{constructor(){super(...arguments),this.dismissedByPress=!1,this.placement="top",this.disabled=!1,this.distance=8,this.open=!1,this.skidding=0,this.showDelay=150,this.hideDelay=0,this.trigger="hover focus",this.withoutArrow=!1,this.for=null,this.anchor=null,this.eventController=new AbortController,this.handleBlur=()=>{this.dismissedByPress=!1,this.hasTrigger("focus")&&this.hide()},this.handleClick=()=>{if(this.hasTrigger("click")){this.open?this.hide():this.show();return}this.hasTrigger("manual")||this.lightDismiss()},this.handleFocus=()=>{this.dismissedByPress||this.hasTrigger("focus")&&this.show()},this.handleMouseDown=()=>{this.hasTrigger("click")||this.hasTrigger("manual")||this.lightDismiss()},this.handleDocumentKeyDown=t=>{this.hasTrigger("manual")||t.key==="Escape"&&this.open&&to(this)&&(t.preventDefault(),t.stopPropagation(),this.hide())},this.handleDocumentClick=t=>{this.hasTrigger("manual")||this.anchor&&t.composedPath().includes(this.anchor)||this.hide()},this.handleMouseOver=()=>{this.dismissedByPress||this.hasTrigger("hover")&&(clearTimeout(this.hoverTimeout),this.hoverTimeout=window.setTimeout(()=>this.show(),this.showDelay))},this.handleMouseOut=t=>{let e=t.relatedTarget,i=!!(e&&this.anchor&&eo(this.anchor,e)),o=!!(e&&eo(this,e));i||o||(this.dismissedByPress=!1,this.hasTrigger("hover")&&(clearTimeout(this.hoverTimeout),this.hoverTimeout=window.setTimeout(()=>{this.hide()},this.hideDelay)))}}connectedCallback(){super.connectedCallback(),typeof document<"u"&&(this.eventController.signal.aborted&&(this.eventController=new AbortController),this.addEventListener("mouseout",this.handleMouseOut),this.dismissedByPress=!1,this.open&&(this.open=!1,this.updateComplete.then(()=>{this.open=!0})),this.id||(this.id=kt("wa-tooltip-")),this.for&&this.anchor?(this.anchor=null,this.handleForChange()):this.for&&this.handleForChange())}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("click",this.handleDocumentClick),_t(this),this.eventController.abort(),this.anchor&&this.removeFromAriaLabelledBy(this.anchor,this.id)}firstUpdated(t){this.body.hidden=!this.open,this.open&&(this.popup.active=!0,this.popup.reposition()),super.firstUpdated(t)}lightDismiss(){clearTimeout(this.hoverTimeout),this.dismissedByPress=!0,this.hide()}hasTrigger(t){return this.trigger.split(" ").includes(t)}addToAriaLabelledBy(t,e){let o=(t.getAttribute("aria-labelledby")||"").split(/\s+/).filter(Boolean);o.includes(e)||(o.push(e),t.setAttribute("aria-labelledby",o.join(" ")))}removeFromAriaLabelledBy(t,e){let r=(t.getAttribute("aria-labelledby")||"").split(/\s+/).filter(Boolean).filter(n=>n!==e);r.length>0?t.setAttribute("aria-labelledby",r.join(" ")):t.removeAttribute("aria-labelledby")}async handleOpenChange(){if(this.open){if(this.disabled)return;let t=new he;if(this.dispatchEvent(t),t.defaultPrevented){this.open=!1;return}this.hasTrigger("manual")||(document.addEventListener("keydown",this.handleDocumentKeyDown,{signal:this.eventController.signal}),document.addEventListener("click",this.handleDocumentClick,{signal:this.eventController.signal}),Ze(this)),this.body.hidden=!1,this.popup.active=!0,await Z(this.popup.popup,"show-with-scale"),this.popup.reposition(),this.dispatchEvent(new fe)}else{let t=new ue;if(this.dispatchEvent(t),t.defaultPrevented){this.open=!0;return}document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("click",this.handleDocumentClick),_t(this),await Z(this.popup.popup,"hide-with-scale"),this.popup.active=!1,this.body.hidden=!0,this.dispatchEvent(new de)}}handleForChange(){let t=this.getRootNode?.();if(!t)return;let e=this.for?t.getElementById?.(this.for):null,i=this.anchor;if(e===i)return;this.dismissedByPress=!1;let{signal:o}=this.eventController;e&&(this.addToAriaLabelledBy(e,this.id),e.addEventListener("blur",this.handleBlur,{capture:!0,signal:o}),e.addEventListener("focus",this.handleFocus,{capture:!0,signal:o}),e.addEventListener("click",this.handleClick,{signal:o}),e.addEventListener("mousedown",this.handleMouseDown,{signal:o}),e.addEventListener("mouseover",this.handleMouseOver,{signal:o}),e.addEventListener("mouseout",this.handleMouseOut,{signal:o})),i&&(this.removeFromAriaLabelledBy(i,this.id),i.removeEventListener("blur",this.handleBlur,{capture:!0}),i.removeEventListener("focus",this.handleFocus,{capture:!0}),i.removeEventListener("click",this.handleClick),i.removeEventListener("mousedown",this.handleMouseDown),i.removeEventListener("mouseover",this.handleMouseOver),i.removeEventListener("mouseout",this.handleMouseOut)),this.anchor=e}async handleOptionsChange(){this.hasUpdated&&(await this.updateComplete,this.popup.reposition())}handleDisabledChange(){this.disabled&&this.open&&this.hide()}async show(){if(!this.open)return this.open=!0,Gt(this,"wa-after-show")}async hide(){if(this.open)return this.open=!1,Gt(this,"wa-after-hide")}render(){return Uo`
      <wa-popup
        part="base tooltip"
        exportparts="
          popup:base__popup,
          arrow:base__arrow
        "
        class=${Xo({tooltip:!0,"tooltip-open":this.open})}
        placement=${this.placement}
        distance=${this.distance}
        skidding=${this.skidding}
        flip
        shift
        ?arrow=${!this.withoutArrow}
        hover-bridge
        .anchor=${this.anchor}
      >
        <div part="body" class="body">
          <slot></slot>
        </div>
      </wa-popup>
    `}};k.css=pe;k.dependencies={"wa-popup":v};a([Jt("slot:not([name])")],k.prototype,"defaultSlot",2);a([Jt(".body")],k.prototype,"body",2);a([Jt("wa-popup")],k.prototype,"popup",2);a([K()],k.prototype,"placement",2);a([K({type:Boolean,reflect:!0})],k.prototype,"disabled",2);a([K({type:Number})],k.prototype,"distance",2);a([K({type:Boolean,reflect:!0})],k.prototype,"open",2);a([K({type:Number})],k.prototype,"skidding",2);a([K({attribute:"show-delay",type:Number})],k.prototype,"showDelay",2);a([K({attribute:"hide-delay",type:Number})],k.prototype,"hideDelay",2);a([K()],k.prototype,"trigger",2);a([K({attribute:"without-arrow",type:Boolean,reflect:!0})],k.prototype,"withoutArrow",2);a([K()],k.prototype,"for",2);a([Ko()],k.prototype,"anchor",2);a([B("open",{waitUntilFirstUpdate:!0})],k.prototype,"handleOpenChange",1);a([B("for")],k.prototype,"handleForChange",1);a([B(["distance","placement","skidding"])],k.prototype,"handleOptionsChange",1);a([B("disabled")],k.prototype,"handleDisabledChange",1);k=a([jo("wa-tooltip")],k);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var oo=class extends Event{constructor(){super("wa-clear",{bubbles:!0,cancelable:!1,composed:!0})}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function io(t,e){let i=t.metaKey||t.ctrlKey||t.shiftKey||t.altKey;t.key==="Enter"&&!i&&setTimeout(()=>{!t.defaultPrevented&&!t.isComposing&&Qo(e)})}var Yo=new Map([["input",!0],["wa-input",!0],["wa-tag-input",!0],["wa-number-input",!0],["wa-otp-input",!0],["wa-slider",!0]]),Go=new Map([["button",!1],["checkbox",!1],["color",!1],["date",!1],["datetime-local",!1],["email",!0],["file",!1],["hidden",!1],["image",!1],["month",!1],["number",!0],["password",!0],["radio",!1],["range",!1],["reset",!0],["search",!0],["submit",!1],["tel",!0],["text",!0],["time",!1],["url",!0],["week",!1]]),Jo=t=>{let e=t?.localName;if(!e||!!!Yo.get(e))return!1;if(e!=="input"&&e!=="wa-input")return!0;let o=t.type;return!!Go.get(o)};function Qo(t){let e=null;if("form"in t&&(e=t.form),!e&&"getForm"in t&&(e=t.getForm()),!e)return;let i=Array.from(e.elements),o=0;for(let n of i)Jo(n)&&(o+=1);if(o===1){e.requestSubmit(null);return}let r=i.find(n=>n.type==="submit"&&!n.matches(":disabled"));r&&(["input","button"].includes(r.localName)?e.requestSubmit(r):r.click())}import{css as Zo}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ro=Zo`
  :host {
    border-width: 0;
  }

  :host(:focus) {
    outline: none;
  }

  .text-field {
    display: flex;
    align-items: stretch;
    justify-content: start;
    position: relative;
    transition: inherit;
    height: var(--wa-form-control-height);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    cursor: text;
    color: var(--wa-form-control-value-color);
    font-size: var(--wa-form-control-value-font-size);
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    vertical-align: middle;
    width: 100%;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    background-color: var(--wa-form-control-background-color);
    box-shadow: var(--box-shadow);
    padding: 0 var(--wa-form-control-padding-inline);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Only ring the field when the text input has focus, not inner buttons */
    &:has(input:focus, textarea:focus) {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled inputs */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .text-field {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  :host([pill]) .text-field {
    border-radius: var(--wa-border-radius-pill) !important;
  }

  .text-field {
    /* Show autofill styles over the entire text field, not just the native <input> */
    &:has(:autofill),
    &:has(:-webkit-autofill) {
      background-color: var(--wa-color-brand-fill-quiet) !important;
    }

    input,
    textarea {
      /*
      Fixes an alignment issue with placeholders.
      https://github.com/shoelace-style/webawesome/issues/342
    */
      height: 100%;

      padding: 0;
      border: none;
      outline: none;
      box-shadow: none;
      margin: 0;
      cursor: inherit;
      -webkit-appearance: none;
      font: inherit;

      /* Turn off Safari's autofill styles */
      &:-webkit-autofill,
      &:-webkit-autofill:hover,
      &:-webkit-autofill:focus,
      &:-webkit-autofill:active {
        -webkit-background-clip: text;
        background-color: transparent;
        -webkit-text-fill-color: inherit;
      }
    }
  }

  input {
    flex: 1 1 auto;
    min-width: 0;
    height: 100%;
    transition: inherit;

    /* prettier-ignore */
    background-color: rgb(118 118 118 / 0); /* ensures proper placeholder styles in webkit's date input */
    height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    padding-block: 0;
    color: inherit;

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &::-webkit-search-decoration,
    &::-webkit-search-cancel-button,
    &::-webkit-search-results-button,
    &::-webkit-search-results-decoration {
      -webkit-appearance: none;
    }

    &:focus {
      outline: none;
    }
  }

  textarea {
    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }
  }

  .start,
  .end {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    cursor: default;

    &::slotted(wa-icon) {
      color: var(--wa-color-neutral-on-quiet);
    }
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  /*
   * Clearable + Password Toggle
   */

  .clear,
  .password-toggle {
    position: relative;
    display: inline-flex;
    align-self: center;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    height: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    border-radius: var(--wa-border-radius-s);
    background: none;
    padding: 0;
    transition: var(--wa-transition-normal) color;
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half of that growth on each side. Keeps the
       glyph flush with the field's trailing padding edge, like every other form control. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &::after {
      content: '';
      position: absolute;
      inset-inline: 0;
      height: var(--wa-form-control-height);
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  /* Don't show the browser's password toggle in Edge */
  ::-ms-reveal {
    display: none;
  }

  /* Hide the built-in number spinner */
  :host([without-spin-buttons]) input[type='number'] {
    -moz-appearance: textfield;

    &::-webkit-outer-spin-button,
    &::-webkit-inner-spin-button {
      -webkit-appearance: none;
      display: none;
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var no=()=>({checkValidity(t){let e=t.input,i={message:"",isValid:!0,invalidKeys:[]};if(!e)return i;let o=!0;if("checkValidity"in e&&(o=e.checkValidity()),o)return i;if(i.isValid=!1,"validationMessage"in e&&(i.message=e.validationMessage),!("validity"in e))return i.invalidKeys.push("customError"),i;for(let r in e.validity){if(r==="valid")continue;let n=r;e.validity[n]&&i.invalidKeys.push(n)}return i}});import{html as St,isServer as ti}from"/vendor/lit.js";import{customElement as ei,property as x,query as oi,state as ii}from"/vendor/lit.js";import{classMap as so}from"/vendor/lit.js";import{ifDefined as D}from"/vendor/lit.js";import{live as ri}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var b=class extends Ft{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.hasSlotController=new ee(this,"hint","label"),this.localize=new ut(this),this.title="",this.type="text",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.size="m",this.appearance="outlined",this.pill=!1,this.label="",this.hint="",this.withClear=!1,this.placeholder="",this.readonly=!1,this.passwordToggle=!1,this.passwordVisible=!1,this.withoutSpinButtons=!1,this.required=!1,this.spellcheck=!0,this.withLabel=!1,this.withHint=!1}static get validators(){return ti?[]:[...super.validators,no()]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(t){this._value!==t&&(this.valueHasChanged=!0,this._value=t)}updateFormValue(t){if(t==null){this.setValue("",null);return}super.updateFormValue(t)}handleSizeChange(){te(this.localName,this.size)}handleChange(t){this.value=this.input.value,this.relayNativeEvent(t,{bubbles:!0,composed:!0})}handleClearClick(t){t.preventDefault(),this.value!==""&&(this.value="",this.updateComplete.then(()=>{this.dispatchEvent(new oo),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})),this.input.focus()}handleInput(){this.value=this.input.value}handleKeyDown(t){io(t,this)}handlePasswordToggle(){this.passwordVisible=!this.passwordVisible}updated(t){if(super.updated(t),t.has("value")||t.has("defaultValue")||t.has("type")){let e=["number","date","time","datetime-local"];this.input&&e.includes(this.type)&&this.value&&this.input.value!==this.value&&(this._value=this.input.value),this.customStates.set("blank",!this.value),this.updateValidity()}}handleStepChange(){this.input.step=String(this.step),this.updateValidity()}focus(t){this.input.focus(t)}blur(){this.input.blur()}select(){this.input.select()}setSelectionRange(t,e,i="none"){this.input.setSelectionRange(t,e,i)}setRangeText(t,e,i,o="preserve"){let r=e??this.input.selectionStart,n=i??this.input.selectionEnd;this.input.setRangeText(t,r,n,o),this.value!==this.input.value&&(this.value=this.input.value)}showPicker(){"showPicker"in HTMLInputElement.prototype&&this.input.showPicker()}stepUp(){this.input.stepUp(),this.value!==this.input.value&&(this.value=this.input.value)}stepDown(){this.input.stepDown(),this.value!==this.input.value&&(this.value=this.input.value)}formResetCallback(){this.value=null,this.input&&(this.input.value=this.value),super.formResetCallback()}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,o=this.hint?!0:!!e,r=this.withClear&&!this.disabled&&!this.readonly,n=(!this.didSSR||this.hasUpdated)&&r&&(typeof this.value=="number"||this.value&&this.value.length>0);return St`
      <label
        part="form-control-label label"
        class=${so({label:!0,"has-label":i})}
        for="input"
        aria-hidden=${i?"false":"true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base input-wrapper" class="text-field">
        <slot name="start" part="start" class="start"></slot>

        <input
          part="input"
          id="input"
          class="control"
          type=${this.type==="password"&&this.passwordVisible?"text":this.type}
          title=${this.title}
          name=${D(this.name)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${D(this.placeholder)}
          minlength=${D(this.minlength)}
          maxlength=${D(this.maxlength)}
          min=${D(this.min)}
          max=${D(this.max)}
          step=${D(this.step)}
          .value=${ri(this.value??"")}
          autocapitalize=${D(this.autocapitalize)}
          autocomplete=${D(this.autocomplete)}
          autocorrect=${this.autocorrect?"on":"off"}
          ?autofocus=${this.autofocus}
          spellcheck=${this.spellcheck}
          pattern=${D(this.pattern)}
          enterkeyhint=${D(this.enterkeyhint)}
          inputmode=${D(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
        />

        ${n?St`
              <button
                part="clear-button"
                class="clear"
                type="button"
                aria-label=${this.localize.term("clearEntry")}
                @click=${this.handleClearClick}
                tabindex="-1"
              >
                <slot name="clear-icon">
                  <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                </slot>
              </button>
            `:""}
        ${this.passwordToggle&&!this.disabled?St`
              <button
                part="password-toggle-button"
                class="password-toggle"
                type="button"
                aria-label=${this.localize.term(this.passwordVisible?"hidePassword":"showPassword")}
                @click=${this.handlePasswordToggle}
              >
                ${this.passwordVisible?St`
                      <slot name="hide-password-icon">
                        <wa-icon name="eye-slash" library="system" variant="regular"></wa-icon>
                      </slot>
                    `:St`
                      <slot name="show-password-icon">
                        <wa-icon name="eye" library="system" variant="regular"></wa-icon>
                      </slot>
                    `}
              </button>
            `:""}

        <slot name="end" part="end" class="end"></slot>
      </div>

      <slot
        id="hint"
        part="hint"
        name="hint"
        class=${so({"has-slotted":o})}
        aria-hidden=${o?"false":"true"}
        >${this.hint}</slot
      >
    `}};b.css=[oe,Zt,ro];b.shadowRootOptions={...Ft.shadowRootOptions,delegatesFocus:!0};a([oi("input")],b.prototype,"input",2);a([x()],b.prototype,"title",2);a([x({reflect:!0})],b.prototype,"type",2);a([ii()],b.prototype,"value",1);a([x({attribute:"value",reflect:!0})],b.prototype,"defaultValue",2);a([x({reflect:!0})],b.prototype,"size",2);a([B("size")],b.prototype,"handleSizeChange",1);a([x({reflect:!0})],b.prototype,"appearance",2);a([x({type:Boolean,reflect:!0})],b.prototype,"pill",2);a([x()],b.prototype,"label",2);a([x({attribute:"hint"})],b.prototype,"hint",2);a([x({attribute:"with-clear",type:Boolean})],b.prototype,"withClear",2);a([x()],b.prototype,"placeholder",2);a([x({type:Boolean,reflect:!0})],b.prototype,"readonly",2);a([x({attribute:"password-toggle",type:Boolean})],b.prototype,"passwordToggle",2);a([x({attribute:"password-visible",type:Boolean})],b.prototype,"passwordVisible",2);a([x({attribute:"without-spin-buttons",type:Boolean,reflect:!0})],b.prototype,"withoutSpinButtons",2);a([x({type:Boolean,reflect:!0})],b.prototype,"required",2);a([x()],b.prototype,"pattern",2);a([x({type:Number})],b.prototype,"minlength",2);a([x({type:Number})],b.prototype,"maxlength",2);a([x()],b.prototype,"min",2);a([x()],b.prototype,"max",2);a([x()],b.prototype,"step",2);a([x()],b.prototype,"autocapitalize",2);a([x({type:Boolean,converter:{fromAttribute:t=>!(!t||t==="off"),toAttribute:t=>t?"on":"off"}})],b.prototype,"autocorrect",2);a([x()],b.prototype,"autocomplete",2);a([x({type:Boolean})],b.prototype,"autofocus",2);a([x()],b.prototype,"enterkeyhint",2);a([x({type:Boolean,converter:{fromAttribute:t=>!(!t||t==="false"),toAttribute:t=>t?"true":"false"}})],b.prototype,"spellcheck",2);a([x()],b.prototype,"inputmode",2);a([x({attribute:"with-label",type:Boolean})],b.prototype,"withLabel",2);a([x({attribute:"with-hint",type:Boolean})],b.prototype,"withHint",2);a([B("step",{waitUntilFirstUpdate:!0})],b.prototype,"handleStepChange",1);b=a([ei("wa-input")],b);b.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */export{Z as a,he as b,ue as c,de as d,fe as e,Ze as f,_t as g,to as h,Gt as i,io as j,oo as k,no as l};
