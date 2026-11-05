/*! Web Awesome 3.14.0 — MIT — licenses: webawesome.LICENSES.txt */
import{a as w,b as x,d as u,e as r,g as A,h as S,i as f,k as m,l as v,m as z,n as b}from"./chunk-HU5QTSKI.js";import{css as I}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var L=I`
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
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function R(e,t){function o(a){let s=e.getBoundingClientRect(),p=e.ownerDocument.defaultView,d=s.left+p.pageXOffset,D=s.top+p.pageYOffset,B=a.pageX-d,M=a.pageY-D;t?.onMove&&t.onMove(B,M)}function i(){document.removeEventListener("pointermove",o),document.removeEventListener("pointerup",i),t?.onStop&&t.onStop()}document.addEventListener("pointermove",o,{passive:!0}),document.addEventListener("pointerup",i),t?.initialEvent instanceof PointerEvent&&o(t.initialEvent)}var y=typeof window<"u"&&"ontouchstart"in window,Z=class{constructor(e,t){this.isActive=!1,this.isDragging=!1,this.handleDragStart=o=>{let i="touches"in o?o.touches[0].clientX:o.clientX,a="touches"in o?o.touches[0].clientY:o.clientY;this.isDragging||!y&&o.buttons>1||(this.isDragging=!0,document.addEventListener("pointerup",this.handleDragStop),document.addEventListener("pointermove",this.handleDragMove),document.addEventListener("pointercancel",this.handleDragStop),document.addEventListener("touchend",this.handleDragStop),document.addEventListener("touchmove",this.handleDragMove),document.addEventListener("touchcancel",this.handleDragStop),this.options.start(i,a))},this.handleDragStop=o=>{let i="changedTouches"in o?o.changedTouches[0].clientX:o.clientX,a="changedTouches"in o?o.changedTouches[0].clientY:o.clientY;this.isDragging=!1,document.removeEventListener("pointerup",this.handleDragStop),document.removeEventListener("pointermove",this.handleDragMove),document.removeEventListener("pointercancel",this.handleDragStop),document.removeEventListener("touchend",this.handleDragStop),document.removeEventListener("touchmove",this.handleDragMove),document.removeEventListener("touchcancel",this.handleDragStop),this.options.stop(i,a)},this.handleDragMove=o=>{let i="touches"in o?o.touches[0].clientX:o.clientX,a="touches"in o?o.touches[0].clientY:o.clientY;window.getSelection()?.removeAllRanges(),this.options.move(i,a)},this.element=e,this.options={start:()=>{},stop:()=>{},move:()=>{},...t},this.start()}start(){this.isActive||(this.element.addEventListener("pointerdown",this.handleDragStart),y&&this.element.addEventListener("touchstart",this.handleDragStart),this.isActive=!0)}stop(){document.removeEventListener("pointerup",this.handleDragStop),document.removeEventListener("pointermove",this.handleDragMove),document.removeEventListener("pointercancel",this.handleDragStop),document.removeEventListener("touchend",this.handleDragStop),document.removeEventListener("touchmove",this.handleDragMove),document.removeEventListener("touchcancel",this.handleDragStop),this.element.removeEventListener("pointerdown",this.handleDragStart),y&&this.element.removeEventListener("touchstart",this.handleDragStart),this.isActive=!1,this.isDragging=!1}toggle(e){(e!==void 0?e:!this.isActive)?this.start():this.stop()}};import{html as W}from"/vendor/lit.js";import{customElement as X,property as Y,query as T}from"/vendor/lit.js";import{styleMap as C}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var h=class extends A{constructor(){super(...arguments),this.localize=new S(this),this.position=50}handleDrag(e){let{width:t}=this.getBoundingClientRect(),o=this.localize.dir()==="rtl";e.preventDefault(),R(this,{onMove:i=>{this.customStates.set("dragging",!0),this.position=parseFloat(w(i/t*100,0,100).toFixed(2)),o&&(this.position=100-this.position)},onStop:()=>{this.customStates.set("dragging",!1)},initialEvent:e})}handleKeyDown(e){let t=this.matches(":dir(ltr)"),o=this.localize.dir()==="rtl";if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){let i=e.shiftKey?10:1,a=this.position;e.preventDefault(),(t&&e.key==="ArrowLeft"||o&&e.key==="ArrowRight")&&(a-=i),(t&&e.key==="ArrowRight"||o&&e.key==="ArrowLeft")&&(a+=i),e.key==="Home"&&(a=0),e.key==="End"&&(a=100),a=w(a,0,100),this.position=a}}handlePositionChange(){this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}render(){let e=this.hasUpdated?this.localize.dir()==="rtl":this.dir==="rtl";return W`
      <div id="comparison" class="image" part="base comparison">
        <div part="before" class="before">
          <slot name="before"></slot>
        </div>

        <div
          part="after"
          class="after"
          style=${C({clipPath:e?`inset(0 0 0 ${100-this.position}%)`:`inset(0 ${100-this.position}% 0 0)`})}
        >
          <slot name="after"></slot>
        </div>
      </div>

      <div
        part="divider"
        class="divider"
        style=${C({left:e?`${100-this.position}%`:`${this.position}%`})}
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
    `}};h.css=L;r([T(".handle")],h.prototype,"handle",2);r([Y({type:Number,reflect:!0})],h.prototype,"position",2);r([u("position",{waitUntilFirstUpdate:!0})],h.prototype,"handlePositionChange",1);h=r([X("wa-comparison")],h);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */import{css as F}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var _=F`
  .form-control {
    position: relative;
    border: none;
    padding: 0;
    margin: 0;
  }

  .label {
    padding: 0;
  }

  .radio-group-required .label::after {
    content: var(--wa-form-control-required-content);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  [part~='form-control-input'] {
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    gap: 0; /* Radios handle their own spacing */
  }

  /* Horizontal */
  :host([orientation='horizontal']) [part~='form-control-input'] {
    flex-direction: row;
  }

  /* Help text */
  [part~='hint'] {
    margin-block-start: 0.5em;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var q=(e={})=>{let{validationElement:t,validationProperty:o}=e;t||typeof document<"u"&&"createElement"in document&&(t=Object.assign(document.createElement("input"),{required:!0})),o||(o="value");let i={observedAttributes:["required"],message:t?.validationMessage,checkValidity(a){let s={message:"",isValid:!0,invalidKeys:[]};return(a.required??a.hasAttribute("required"))&&!a[o]&&(s.message=typeof i.message=="function"?i.message(a):i.message||"",s.isValid=!1,s.invalidKeys.push("valueMissing")),s}};return i};import{html as j,isServer as k}from"/vendor/lit.js";import{customElement as K,property as c,query as O,state as U}from"/vendor/lit.js";import{classMap as E}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var n=class extends m{constructor(){super(),this.hasSlotController=new z(this,"hint","label"),this.label="",this.hint="",this.name=null,this.disabled=!1,this.orientation="vertical",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.required=!1,this.withLabel=!1,this.withHint=!1,this.handleRadioClick=e=>{let t=e.target.closest("wa-radio");if(!t||t.disabled||t.forceDisabled||this.disabled)return;let o=this.value;this.value=t.value,t.checked=!0;let i=this.getAllRadios();for(let a of i)t!==a&&(a.checked=!1,a.setAttribute("tabindex","-1"));this.value!==o&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})},k||(this.addEventListener("keydown",this.handleKeyDown),this.addEventListener("click",this.handleRadioClick))}static get validators(){let e=k?[]:[q({validationElement:Object.assign(document.createElement("input"),{required:!0,type:"radio",name:x("__wa-radio")})})];return[...super.validators,...e]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(e){typeof e=="number"&&(e=String(e)),this.valueHasChanged=!0,this._value=e}handleSizeChange(){v(this.localName,this.size)}get validationTarget(){if(k)return;let e=this.querySelector(":is(wa-radio):not([disabled])");if(e)return e}updated(e){(e.has("disabled")||e.has("size")||e.has("value")||e.has("defaultValue"))&&this.syncRadioElements()}formResetCallback(...e){this._value=null,super.formResetCallback(...e),this.syncRadioElements()}getAllRadios(){return[...this.querySelectorAll("wa-radio")]}handleLabelClick(){this.focus()}async syncRadioElements(){let e=this.getAllRadios();if(e.forEach((t,o)=>{this.size&&t.setAttribute("size",this.size),t.toggleAttribute("data-wa-radio-horizontal",this.orientation!=="vertical"),t.toggleAttribute("data-wa-radio-vertical",this.orientation==="vertical"),t.toggleAttribute("data-wa-radio-first",o===0),t.toggleAttribute("data-wa-radio-inner",o!==0&&o!==e.length-1),t.toggleAttribute("data-wa-radio-last",o===e.length-1),t.forceDisabled=this.disabled}),await Promise.all(e.map(async t=>{await t.updateComplete,!t.disabled&&t.value===this.value?t.checked=!0:t.checked=!1})),this.disabled)e.forEach(t=>{t.tabIndex=-1});else{let t=e.filter(i=>!i.disabled),o=t.find(i=>i.checked);t.length>0&&(o?t.forEach(i=>{i.tabIndex=i.checked?0:-1}):t.forEach((i,a)=>{i.tabIndex=a===0?0:-1})),e.filter(i=>i.disabled).forEach(i=>{i.tabIndex=-1})}}handleKeyDown(e){if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(e.key)||this.disabled)return;let t=this.getAllRadios().filter(d=>!d.disabled);if(t.length<=0)return;e.preventDefault();let o=this.value,i=t.find(d=>d.checked)??t[0],a=e.key===" "?0:["ArrowUp","ArrowLeft"].includes(e.key)?-1:1,s=t.indexOf(i)+a;s||(s=0),s<0&&(s=t.length-1),s>t.length-1&&(s=0);let p=t.some(d=>d.tagName.toLowerCase()==="wa-radio-button");this.getAllRadios().forEach(d=>{d.checked=!1,p||d.setAttribute("tabindex","-1")}),this.value=t[s].value,t[s].checked=!0,p?t[s].shadowRoot.querySelector("button").focus({preventScroll:!0}):(t[s].setAttribute("tabindex","0"),t[s].focus({preventScroll:!0})),this.value!==o&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),e.preventDefault()}focus(e){if(this.disabled)return;let t=this.getAllRadios(),o=t.find(s=>s.checked),i=t.find(s=>!s.disabled),a=o||i;a&&a.focus(e)}render(){let e=this.hasSlotController.test("label","withLabel"),t=this.hasSlotController.test("hint","withHint"),o=this.label?!0:!!e,i=this.hint?!0:!!t;return j`
      <fieldset
        part="form-control"
        class=${E({"form-control":!0,"form-control-radio-group":!0,"form-control-has-label":o})}
        role="radiogroup"
        aria-labelledby="label"
        aria-describedby="hint"
        aria-errormessage="error-message"
        aria-orientation=${this.orientation}
      >
        <label
          part="form-control-label"
          id="label"
          class=${E({label:!0,"has-label":o})}
          aria-hidden=${o?"false":"true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <slot part="form-control-input" @slotchange=${this.syncRadioElements}></slot>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${E({"has-slotted":i})}
          aria-hidden=${i?"false":"true"}
          >${this.hint}</slot
        >
      </fieldset>
    `}};n.css=[b,f,_];n.shadowRootOptions={...m.shadowRootOptions,delegatesFocus:!0};r([O("slot:not([name])")],n.prototype,"defaultSlot",2);r([c()],n.prototype,"label",2);r([c({attribute:"hint"})],n.prototype,"hint",2);r([c({reflect:!0})],n.prototype,"name",2);r([c({type:Boolean,reflect:!0})],n.prototype,"disabled",2);r([c({reflect:!0})],n.prototype,"orientation",2);r([U()],n.prototype,"value",1);r([c({attribute:"value",reflect:!0})],n.prototype,"defaultValue",2);r([c({reflect:!0})],n.prototype,"size",2);r([u("size")],n.prototype,"handleSizeChange",1);r([c({type:Boolean,reflect:!0})],n.prototype,"required",2);r([c({type:Boolean,attribute:"with-label"})],n.prototype,"withLabel",2);r([c({type:Boolean,attribute:"with-hint"})],n.prototype,"withHint",2);n=r([K("wa-radio-group")],n);n.disableWarning?.("change-in-update");import{css as G}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var $=G`
  :host {
    --checked-icon-color: var(--wa-form-control-activated-color);
    --checked-icon-scale: 0.7;

    color: var(--wa-form-control-value-color);
    display: inline-flex;
    flex-direction: row;
    align-items: top;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  :host(:focus) {
    outline: none;
  }

  /* When the control isn't checked, hide the circle for Windows High Contrast mode a11y */
  :host(:not(:state(checked))) svg circle {
    opacity: 0;
  }

  [part~='label'] {
    display: inline;
  }

  [part~='hint'] {
    margin-block-start: 0.5em;
  }

  /* Default spacing for default appearance radios */
  :host([appearance='default']) {
    margin-block: 0.375em; /* Half of the original 0.75em gap on each side */
  }

  :host([appearance='default'][data-wa-radio-horizontal]) {
    margin-block: 0;
    margin-inline: 0.5em; /* Half of the original 1em gap on each side */
  }

  /* Remove margin from first/last items to prevent extra space */
  :host([appearance='default'][data-wa-radio-first]) {
    margin-block-start: 0;
    margin-inline-start: 0;
  }

  :host([appearance='default'][data-wa-radio-last]) {
    margin-block-end: 0;
    margin-inline-end: 0;
  }

  /* Button appearance have no spacing, they get handled by the overlap margins below */
  :host([appearance='button']) {
    margin: 0;
    align-items: center;
    min-height: var(--wa-form-control-height);
    background-color: var(--wa-color-surface-default);
    border: var(--wa-form-control-border-width) var(--wa-form-control-border-style) var(--wa-form-control-border-color);
    border-radius: var(--wa-border-radius-m);
    padding: 0 var(--wa-form-control-padding-inline);
    transition:
      background-color var(--wa-transition-fast),
      border-color var(--wa-transition-fast);
  }

  /* Default appearance */
  :host([appearance='default']) {
    .control {
      flex: 0 0 auto;
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      border-color: var(--wa-form-control-border-color);
      border-radius: 50%;
      border-style: var(--wa-form-control-border-style);
      border-width: var(--wa-form-control-border-width);
      background-color: var(--wa-form-control-background-color);
      color: transparent;
      transition:
        background var(--wa-transition-normal),
        border-color var(--wa-transition-fast),
        box-shadow var(--wa-transition-fast),
        color var(--wa-transition-fast);
      transition-timing-function: var(--wa-transition-easing);

      margin-inline-end: 0.5em;
    }

    .checked-icon {
      display: flex;
      fill: currentColor;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      scale: var(--checked-icon-scale);
    }
  }

  /* Button appearance */
  :host([appearance='button']) {
    .control {
      display: none;
    }
  }

  /* Checked */
  :host(:state(checked)) .control {
    color: var(--checked-icon-color);
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-form-control-background-color);
  }

  /* Focus */
  :host(:focus-visible) .control {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled */
  :host(:state(disabled)) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Horizontal grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-first]) {
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-end-start-radius: 0;
  }

  /* Vertical grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-first]) {
    border-end-start-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-start-end-radius: 0;
  }

  @media (hover: hover) {
    :host([appearance='button']:hover:not(:state(disabled), :state(checked))) {
      background-color: color-mix(in srgb, var(--wa-color-surface-default) 95%, var(--wa-color-mix-hover));
    }
  }

  :host([appearance='button']:focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  :host([appearance='button']:state(checked)) {
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-color-brand-fill-quiet);
  }

  :host([appearance='button']:state(checked):focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Button overlap margins */
  :host([appearance='button'][data-wa-radio-horizontal]:not([data-wa-radio-first])) {
    margin-inline-start: calc(-1 * var(--wa-form-control-border-width));
  }

  :host([appearance='button'][data-wa-radio-vertical]:not([data-wa-radio-first])) {
    margin-block-start: calc(-1 * var(--wa-form-control-border-width));
  }

  /* Ensure interactive states are visible above adjacent buttons */
  :host([appearance='button']:hover),
  :host([appearance='button']:state(checked)) {
    position: relative;
    z-index: 1;
  }

  :host([appearance='button']:focus-visible) {
    z-index: 2;
  }
`;import{html as H,isServer as N}from"/vendor/lit.js";import{customElement as P,property as g,state as V}from"/vendor/lit.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var l=class extends m{constructor(){super(),this.checked=!1,this.forceDisabled=!1,this.appearance="default",this.disabled=!1,this.handleClick=()=>{!this.disabled&&!this.forceDisabled&&(this.checked=!0)},N||this.addEventListener("click",this.handleClick)}handleSizeChange(){v(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.setInitialAttributes()}setInitialAttributes(){this.setAttribute("role","radio"),this.tabIndex=0,this.setAttribute("aria-disabled",this.disabled||this.forceDisabled?"true":"false")}updated(e){if(super.updated(e),e.has("checked")&&(this.customStates.set("checked",this.checked),this.setAttribute("aria-checked",this.checked?"true":"false"),!this.disabled&&!this.forceDisabled&&(this.tabIndex=this.checked?0:-1)),e.has("disabled")||e.has("forceDisabled")){let t=this.disabled||this.forceDisabled;this.customStates.set("disabled",t),this.setAttribute("aria-disabled",t?"true":"false"),t?this.tabIndex=-1:this.tabIndex=this.checked?0:-1}}setValue(){}render(){return H`
      <span part="control" class="control">
        ${this.checked?H`
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" part="checked-icon" class="checked-icon">
                <circle cx="8" cy="8" r="8" />
              </svg>
            `:""}
      </span>

      <slot part="label" class="label"></slot>
    `}};l.css=[f,b,$];r([V()],l.prototype,"checked",2);r([V()],l.prototype,"forceDisabled",2);r([g({reflect:!0})],l.prototype,"value",2);r([g({reflect:!0})],l.prototype,"appearance",2);r([g({reflect:!0})],l.prototype,"size",2);r([u("size")],l.prototype,"handleSizeChange",1);r([g({type:Boolean})],l.prototype,"disabled",2);l=r([P("wa-radio")],l);l.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */export{Z as a,q as b};
