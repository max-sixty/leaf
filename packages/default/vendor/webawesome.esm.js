/*! Web Awesome 3.14.0 — MIT — licenses: webawesome.LICENSES.txt */
import{a as h,b as p,c as m,d as l,e as u,f as a,g as f,h as g,i as v,j as w,k as y,l as D,m as E,n as b}from"./webawesome/chunk-TYUQ4MD6.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var L=h`
  :host {
    --divider-width: 0.125rem;
    --handle-size: 2.5rem;

    display: block;
    position: relative;
    max-width: 100%;
    max-height: 100%;
    overflow: hidden;
  }

  .before,
  .after {
    display: block;

    &::slotted(img),
    &::slotted(svg) {
      display: block;
      max-width: 100% !important;
      height: auto;
    }

    &::slotted(:not(img, svg)) {
      isolation: isolate;
    }
  }

  .after {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 100%;
  }

  /* Disable pointer-events while dragging. This is especially important for iframes. */
  :host(:state(dragging)) {
    .before,
    .after {
      pointer-events: none;
    }
  }

  .divider {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 0;
    width: var(--divider-width);
    height: 100%;
    background-color: var(--wa-color-surface-default);
    translate: calc(var(--divider-width) / -2);
    cursor: ew-resize;
  }

  .handle {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: calc(50% - (var(--handle-size) / 2));
    width: var(--handle-size);
    height: var(--handle-size);
    background-color: var(--wa-color-surface-default);
    border-radius: var(--wa-border-radius-circle);
    font-size: calc(var(--handle-size) * 0.4);
    color: var(--wa-color-neutral-on-quiet);
    cursor: inherit;
    z-index: 10;
  }

  .handle:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function S(t,i){function o(s){let r=t.getBoundingClientRect(),d=t.ownerDocument.defaultView,k=r.left+d.pageXOffset,A=r.top+d.pageYOffset,z=s.pageX-k,M=s.pageY-A;i?.onMove&&i.onMove(z,M)}function e(){document.removeEventListener("pointermove",o),document.removeEventListener("pointerup",e),i?.onStop&&i.onStop()}document.addEventListener("pointermove",o,{passive:!0}),document.addEventListener("pointerup",e),i?.initialEvent instanceof PointerEvent&&o(i.initialEvent)}var Y=typeof window<"u"&&"ontouchstart"in window;/**
 * @license
 * Copyright 2018 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var x="important",T=" !"+x,c=E(class extends b{constructor(t){if(super(t),t.type!==D.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce(((i,o)=>{let e=t[o];return e==null?i:i+`${o=o.includes("-")?o:o.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${e};`}),"")}update(t,[i]){let{style:o}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(i)),this.render(i);for(let e of this.ft)i[e]==null&&(this.ft.delete(e),e.includes("-")?o.removeProperty(e):o[e]=null);for(let e in i){let s=i[e];if(s!=null){this.ft.add(e);let r=typeof s=="string"&&s.endsWith(T);e.includes("-")||r?o.setProperty(e,r?s.slice(0,-11):s,r?x:""):o[e]=s}}return m}});/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var n=class extends w{constructor(){super(...arguments),this.localize=new y(this),this.position=50}handleDrag(t){let{width:i}=this.getBoundingClientRect(),o=this.localize.dir()==="rtl";t.preventDefault(),S(this,{onMove:e=>{this.customStates.set("dragging",!0),this.position=parseFloat(l(e/i*100,0,100).toFixed(2)),o&&(this.position=100-this.position)},onStop:()=>{this.customStates.set("dragging",!1)},initialEvent:t})}handleKeyDown(t){let i=this.matches(":dir(ltr)"),o=this.localize.dir()==="rtl";if(["ArrowLeft","ArrowRight","Home","End"].includes(t.key)){let e=t.shiftKey?10:1,s=this.position;t.preventDefault(),(i&&t.key==="ArrowLeft"||o&&t.key==="ArrowRight")&&(s-=e),(i&&t.key==="ArrowRight"||o&&t.key==="ArrowLeft")&&(s+=e),t.key==="Home"&&(s=0),t.key==="End"&&(s=100),s=l(s,0,100),this.position=s}}handlePositionChange(){this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}render(){let t=this.hasUpdated?this.localize.dir()==="rtl":this.dir==="rtl";return p`
      <div id="comparison" class="image" part="base comparison">
        <div part="before" class="before">
          <slot name="before"></slot>
        </div>

        <div
          part="after"
          class="after"
          style=${c({clipPath:t?`inset(0 0 0 ${100-this.position}%)`:`inset(0 ${100-this.position}% 0 0)`})}
        >
          <slot name="after"></slot>
        </div>
      </div>

      <div
        part="divider"
        class="divider"
        style=${c({left:t?`${100-this.position}%`:`${this.position}%`})}
        @keydown=${this.handleKeyDown}
        @mousedown=${this.handleDrag}
        @touchstart=${this.handleDrag}
      >
        <div
          part="handle"
          class="handle"
          role="scrollbar"
          aria-valuenow=${this.position}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-controls="comparison"
          tabindex="0"
        >
          <slot name="handle">
            <wa-icon library="system" name="grip-vertical" variant="solid"></wa-icon>
          </slot>
        </div>
      </div>
    `}};n.css=L;a([v(".handle")],n.prototype,"handle",2);a([g({type:Number,reflect:!0})],n.prototype,"position",2);a([u("position",{waitUntilFirstUpdate:!0})],n.prototype,"handlePositionChange",1);n=a([f("wa-comparison")],n);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
