/*! Web Awesome 3.13.0 — MIT — licenses: webawesome.LICENSES.txt */
import{B as a,G as g,H as o,L as s,a as t,b as h,c as d,l as p,m as u,p as m,q as r,t as f,v as n,w as k,x as b,y as v}from"./webawesome/chunk-CGEUEGJS.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var y=h`
  :host {
    --checked-icon-color: var(--wa-color-brand-on-loud);
    --checked-icon-scale: 0.8;

    display: inline-flex;
    color: var(--wa-form-control-value-color);
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    user-select: none;
    -webkit-user-select: none;
  }

  [part~='control'] {
    display: inline-flex;
    flex: 0 0 auto;
    position: relative;
    align-items: center;
    justify-content: center;
    width: var(--wa-form-control-toggle-size);
    height: var(--wa-form-control-toggle-size);
    border-color: var(--wa-form-control-border-color);
    border-radius: min(
      calc(var(--wa-form-control-toggle-size) * 0.375),
      var(--wa-border-radius-s)
    ); /* min prevents entirely circular checkbox */
    border-style: var(--wa-border-style);
    border-width: var(--wa-form-control-border-width);
    background-color: var(--wa-form-control-background-color);
    transition:
      background var(--wa-transition-normal),
      border-color var(--wa-transition-fast),
      box-shadow var(--wa-transition-fast),
      color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);

    margin-inline-end: 0.5em;
  }

  [part~='base'] {
    display: flex;
    align-items: flex-start;
    position: relative;
    color: currentColor;
    vertical-align: middle;
    cursor: pointer;
  }

  [part~='label'] {
    display: inline;
  }

  /* Checked */
  [part~='control']:has(:checked, :indeterminate) {
    color: var(--checked-icon-color);
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-form-control-activated-color);
  }

  /* Focus */
  [part~='control']:has(> input:focus-visible:not(:disabled)) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled */
  :host [part~='base']:has(input:disabled) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  input {
    position: absolute;
    padding: 0;
    margin: 0;
    height: 100%;
    width: 100%;
    opacity: 0;
    pointer-events: none;
  }

  [part~='icon'] {
    display: flex;
    scale: var(--checked-icon-scale);

    /* Without this, Safari renders the icon slightly to the left */
    &::part(svg) {
      translate: 0.0009765625em;
    }

    input:not(:checked, :indeterminate) + & {
      visibility: hidden;
    }
  }

  :host([required]) [part~='label']::after {
    content: var(--wa-form-control-required-content);
    color: var(--wa-form-control-required-content-color);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var e=class extends n{constructor(){super(...arguments),this.hasSlotController=new k(this,"hint"),this.title="",this._value=this.getAttribute("value")??null,this.size="m",this.disabled=!1,this.indeterminate=!1,this._checked=null,this.defaultChecked=this.hasAttribute("checked"),this.required=!1,this.hint=""}static get validators(){let i=[p({validationProperty:"checked",validationElement:Object.assign(document.createElement("input"),{type:"checkbox",required:!0})})];return[...super.validators,...i]}get value(){return this._value??"on"}set value(i){this._value=i}handleSizeChange(){b(this.localName,this.size)}get checked(){return this.valueHasChanged?!!this._checked:this._checked??this.defaultChecked}set checked(i){this._checked=!!i,this.valueHasChanged=!0}handleClick(){this.hasInteracted=!0,this.checked=!this.checked,this.indeterminate=!1,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}connectedCallback(){if(super.connectedCallback(),this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleDefaultCheckedChange()});return}this.handleDefaultCheckedChange()}handleDefaultCheckedChange(){this.handleValueOrCheckedChange()}handleValueOrCheckedChange(){if(this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleValueOrCheckedChange()});return}this.setValue(this.checked?this.value:null,this._value),this.updateValidity()}handleStateChange(){this.hasUpdated&&(this.input.checked=this.checked,this.input.indeterminate=this.indeterminate),this.customStates.set("checked",this.checked),this.customStates.set("indeterminate",this.indeterminate),this.updateValidity()}handleDisabledChange(){this.customStates.set("disabled",this.disabled)}willUpdate(i){super.willUpdate(i),(i.has("value")||i.has("checked")||i.has("defaultChecked")||i.has("disabled"))&&this.handleValueOrCheckedChange()}formResetCallback(){this._checked=null,super.formResetCallback(),this.handleValueOrCheckedChange()}click(){this.input.click()}focus(i){this.input.focus(i)}blur(){this.input.blur()}render(){let i=this.hasSlotController.test("hint"),l=this.hint?!0:!!i,c=!this.checked&&this.indeterminate,w=c?"indeterminate":"check",S=c?"indeterminate":"checked",x=this.didSSR&&!this.hasUpdated?this.checked:this.defaultChecked,_=this.didSSR&&!this.hasUpdated?null:s(this.checked);return d`
      <label part="base checkbox">
        <span part="control">
          <input
            class="input"
            type="checkbox"
            title=${this.title}
            name=${o(this.name)}
            value=${o(this.value)}
            .indeterminate=${s(this.indeterminate)}
            .checked=${o(_)}
            ?checked=${x}
            ?disabled=${this.disabled}
            ?required=${this.required}
            aria-checked=${this.indeterminate?"mixed":this.checked?"true":"false"}
            aria-describedby="hint"
            @click=${this.handleClick}
          />

          <wa-icon part="${S}-icon icon" library="system" name=${w}></wa-icon>
        </span>

        <slot part="label"></slot>
      </label>

      <slot
        id="hint"
        part="hint"
        name="hint"
        aria-hidden=${l?"false":"true"}
        class="${g({"has-slotted":l})}"
      >
        ${this.hint}
      </slot>
    `}};e.css=[u,v,y];e.shadowRootOptions={...n.shadowRootOptions,delegatesFocus:!0};t([f('input[type="checkbox"]')],e.prototype,"input",2);t([r()],e.prototype,"title",2);t([r({reflect:!0})],e.prototype,"value",1);t([r({reflect:!0})],e.prototype,"size",2);t([a("size")],e.prototype,"handleSizeChange",1);t([r({type:Boolean})],e.prototype,"disabled",2);t([r({type:Boolean,reflect:!0})],e.prototype,"indeterminate",2);t([r({type:Boolean,attribute:!1})],e.prototype,"checked",1);t([r({type:Boolean,reflect:!0,attribute:"checked"})],e.prototype,"defaultChecked",2);t([r({type:Boolean,reflect:!0})],e.prototype,"required",2);t([r()],e.prototype,"hint",2);t([a(["checked","defaultChecked"])],e.prototype,"handleDefaultCheckedChange",1);t([a(["checked","indeterminate"])],e.prototype,"handleStateChange",1);t([a("disabled")],e.prototype,"handleDisabledChange",1);e=t([m("wa-checkbox")],e);e.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
