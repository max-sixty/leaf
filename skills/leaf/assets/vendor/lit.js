// node_modules/@lit/reactive-element/css-tag.js
var t = globalThis;
var e = t.ShadowRoot && (void 0 === t.ShadyCSS || t.ShadyCSS.nativeShadow) && "adoptedStyleSheets" in Document.prototype && "replace" in CSSStyleSheet.prototype;
var s = /* @__PURE__ */ Symbol();
var o = /* @__PURE__ */ new WeakMap();
var n = class {
  constructor(t9, e14, o21) {
    if (this._$cssResult$ = true, o21 !== s) throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");
    this.cssText = t9, this.t = e14;
  }
  get styleSheet() {
    let t9 = this.o;
    const s8 = this.t;
    if (e && void 0 === t9) {
      const e14 = void 0 !== s8 && 1 === s8.length;
      e14 && (t9 = o.get(s8)), void 0 === t9 && ((this.o = t9 = new CSSStyleSheet()).replaceSync(this.cssText), e14 && o.set(s8, t9));
    }
    return t9;
  }
  toString() {
    return this.cssText;
  }
};
var r = (t9) => new n("string" == typeof t9 ? t9 : t9 + "", void 0, s);
var i = (t9, ...e14) => {
  const o21 = 1 === t9.length ? t9[0] : e14.reduce((e15, s8, o22) => e15 + ((t10) => {
    if (true === t10._$cssResult$) return t10.cssText;
    if ("number" == typeof t10) return t10;
    throw Error("Value passed to 'css' function must be a 'css' function result: " + t10 + ". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.");
  })(s8) + t9[o22 + 1], t9[0]);
  return new n(o21, t9, s);
};
var S = (s8, o21) => {
  if (e) s8.adoptedStyleSheets = o21.map((t9) => t9 instanceof CSSStyleSheet ? t9 : t9.styleSheet);
  else for (const e14 of o21) {
    const o22 = document.createElement("style"), n14 = t.litNonce;
    void 0 !== n14 && o22.setAttribute("nonce", n14), o22.textContent = e14.cssText, s8.appendChild(o22);
  }
};
var c = e ? (t9) => t9 : (t9) => t9 instanceof CSSStyleSheet ? ((t10) => {
  let e14 = "";
  for (const s8 of t10.cssRules) e14 += s8.cssText;
  return r(e14);
})(t9) : t9;

// node_modules/@lit/reactive-element/reactive-element.js
var { is: i2, defineProperty: e2, getOwnPropertyDescriptor: h, getOwnPropertyNames: r2, getOwnPropertySymbols: o2, getPrototypeOf: n2 } = Object;
var a = globalThis;
var c2 = a.trustedTypes;
var l = c2 ? c2.emptyScript : "";
var p = a.reactiveElementPolyfillSupport;
var d = (t9, s8) => t9;
var u = { toAttribute(t9, s8) {
  switch (s8) {
    case Boolean:
      t9 = t9 ? l : null;
      break;
    case Object:
    case Array:
      t9 = null == t9 ? t9 : JSON.stringify(t9);
  }
  return t9;
}, fromAttribute(t9, s8) {
  let i12 = t9;
  switch (s8) {
    case Boolean:
      i12 = null !== t9;
      break;
    case Number:
      i12 = null === t9 ? null : Number(t9);
      break;
    case Object:
    case Array:
      try {
        i12 = JSON.parse(t9);
      } catch (t10) {
        i12 = null;
      }
  }
  return i12;
} };
var f = (t9, s8) => !i2(t9, s8);
var b = { attribute: true, type: String, converter: u, reflect: false, useDefault: false, hasChanged: f };
Symbol.metadata ??= /* @__PURE__ */ Symbol("metadata"), a.litPropertyMetadata ??= /* @__PURE__ */ new WeakMap();
var y = class extends HTMLElement {
  static addInitializer(t9) {
    this._$Ei(), (this.l ??= []).push(t9);
  }
  static get observedAttributes() {
    return this.finalize(), this._$Eh && [...this._$Eh.keys()];
  }
  static createProperty(t9, s8 = b) {
    if (s8.state && (s8.attribute = false), this._$Ei(), this.prototype.hasOwnProperty(t9) && ((s8 = Object.create(s8)).wrapped = true), this.elementProperties.set(t9, s8), !s8.noAccessor) {
      const i12 = /* @__PURE__ */ Symbol(), h9 = this.getPropertyDescriptor(t9, i12, s8);
      void 0 !== h9 && e2(this.prototype, t9, h9);
    }
  }
  static getPropertyDescriptor(t9, s8, i12) {
    const { get: e14, set: r11 } = h(this.prototype, t9) ?? { get() {
      return this[s8];
    }, set(t10) {
      this[s8] = t10;
    } };
    return { get: e14, set(s9) {
      const h9 = e14?.call(this);
      r11?.call(this, s9), this.requestUpdate(t9, h9, i12);
    }, configurable: true, enumerable: true };
  }
  static getPropertyOptions(t9) {
    return this.elementProperties.get(t9) ?? b;
  }
  static _$Ei() {
    if (this.hasOwnProperty(d("elementProperties"))) return;
    const t9 = n2(this);
    t9.finalize(), void 0 !== t9.l && (this.l = [...t9.l]), this.elementProperties = new Map(t9.elementProperties);
  }
  static finalize() {
    if (this.hasOwnProperty(d("finalized"))) return;
    if (this.finalized = true, this._$Ei(), this.hasOwnProperty(d("properties"))) {
      const t10 = this.properties, s8 = [...r2(t10), ...o2(t10)];
      for (const i12 of s8) this.createProperty(i12, t10[i12]);
    }
    const t9 = this[Symbol.metadata];
    if (null !== t9) {
      const s8 = litPropertyMetadata.get(t9);
      if (void 0 !== s8) for (const [t10, i12] of s8) this.elementProperties.set(t10, i12);
    }
    this._$Eh = /* @__PURE__ */ new Map();
    for (const [t10, s8] of this.elementProperties) {
      const i12 = this._$Eu(t10, s8);
      void 0 !== i12 && this._$Eh.set(i12, t10);
    }
    this.elementStyles = this.finalizeStyles(this.styles);
  }
  static finalizeStyles(s8) {
    const i12 = [];
    if (Array.isArray(s8)) {
      const e14 = new Set(s8.flat(1 / 0).reverse());
      for (const s9 of e14) i12.unshift(c(s9));
    } else void 0 !== s8 && i12.push(c(s8));
    return i12;
  }
  static _$Eu(t9, s8) {
    const i12 = s8.attribute;
    return false === i12 ? void 0 : "string" == typeof i12 ? i12 : "string" == typeof t9 ? t9.toLowerCase() : void 0;
  }
  constructor() {
    super(), this._$Ep = void 0, this.isUpdatePending = false, this.hasUpdated = false, this._$Em = null, this._$Ev();
  }
  _$Ev() {
    this._$ES = new Promise((t9) => this.enableUpdating = t9), this._$AL = /* @__PURE__ */ new Map(), this._$E_(), this.requestUpdate(), this.constructor.l?.forEach((t9) => t9(this));
  }
  addController(t9) {
    (this._$EO ??= /* @__PURE__ */ new Set()).add(t9), void 0 !== this.renderRoot && this.isConnected && t9.hostConnected?.();
  }
  removeController(t9) {
    this._$EO?.delete(t9);
  }
  _$E_() {
    const t9 = /* @__PURE__ */ new Map(), s8 = this.constructor.elementProperties;
    for (const i12 of s8.keys()) this.hasOwnProperty(i12) && (t9.set(i12, this[i12]), delete this[i12]);
    t9.size > 0 && (this._$Ep = t9);
  }
  createRenderRoot() {
    const t9 = this.shadowRoot ?? this.attachShadow(this.constructor.shadowRootOptions);
    return S(t9, this.constructor.elementStyles), t9;
  }
  connectedCallback() {
    this.renderRoot ??= this.createRenderRoot(), this.enableUpdating(true), this._$EO?.forEach((t9) => t9.hostConnected?.());
  }
  enableUpdating(t9) {
  }
  disconnectedCallback() {
    this._$EO?.forEach((t9) => t9.hostDisconnected?.());
  }
  attributeChangedCallback(t9, s8, i12) {
    this._$AK(t9, i12);
  }
  _$ET(t9, s8) {
    const i12 = this.constructor.elementProperties.get(t9), e14 = this.constructor._$Eu(t9, i12);
    if (void 0 !== e14 && true === i12.reflect) {
      const h9 = (void 0 !== i12.converter?.toAttribute ? i12.converter : u).toAttribute(s8, i12.type);
      this._$Em = t9, null == h9 ? this.removeAttribute(e14) : this.setAttribute(e14, h9), this._$Em = null;
    }
  }
  _$AK(t9, s8) {
    const i12 = this.constructor, e14 = i12._$Eh.get(t9);
    if (void 0 !== e14 && this._$Em !== e14) {
      const t10 = i12.getPropertyOptions(e14), h9 = "function" == typeof t10.converter ? { fromAttribute: t10.converter } : void 0 !== t10.converter?.fromAttribute ? t10.converter : u;
      this._$Em = e14;
      const r11 = h9.fromAttribute(s8, t10.type);
      this[e14] = r11 ?? this._$Ej?.get(e14) ?? r11, this._$Em = null;
    }
  }
  requestUpdate(t9, s8, i12, e14 = false, h9) {
    if (void 0 !== t9) {
      const r11 = this.constructor;
      if (false === e14 && (h9 = this[t9]), i12 ??= r11.getPropertyOptions(t9), !((i12.hasChanged ?? f)(h9, s8) || i12.useDefault && i12.reflect && h9 === this._$Ej?.get(t9) && !this.hasAttribute(r11._$Eu(t9, i12)))) return;
      this.C(t9, s8, i12);
    }
    false === this.isUpdatePending && (this._$ES = this._$EP());
  }
  C(t9, s8, { useDefault: i12, reflect: e14, wrapped: h9 }, r11) {
    i12 && !(this._$Ej ??= /* @__PURE__ */ new Map()).has(t9) && (this._$Ej.set(t9, r11 ?? s8 ?? this[t9]), true !== h9 || void 0 !== r11) || (this._$AL.has(t9) || (this.hasUpdated || i12 || (s8 = void 0), this._$AL.set(t9, s8)), true === e14 && this._$Em !== t9 && (this._$Eq ??= /* @__PURE__ */ new Set()).add(t9));
  }
  async _$EP() {
    this.isUpdatePending = true;
    try {
      await this._$ES;
    } catch (t10) {
      Promise.reject(t10);
    }
    const t9 = this.scheduleUpdate();
    return null != t9 && await t9, !this.isUpdatePending;
  }
  scheduleUpdate() {
    return this.performUpdate();
  }
  performUpdate() {
    if (!this.isUpdatePending) return;
    if (!this.hasUpdated) {
      if (this.renderRoot ??= this.createRenderRoot(), this._$Ep) {
        for (const [t11, s9] of this._$Ep) this[t11] = s9;
        this._$Ep = void 0;
      }
      const t10 = this.constructor.elementProperties;
      if (t10.size > 0) for (const [s9, i12] of t10) {
        const { wrapped: t11 } = i12, e14 = this[s9];
        true !== t11 || this._$AL.has(s9) || void 0 === e14 || this.C(s9, void 0, i12, e14);
      }
    }
    let t9 = false;
    const s8 = this._$AL;
    try {
      t9 = this.shouldUpdate(s8), t9 ? (this.willUpdate(s8), this._$EO?.forEach((t10) => t10.hostUpdate?.()), this.update(s8)) : this._$EM();
    } catch (s9) {
      throw t9 = false, this._$EM(), s9;
    }
    t9 && this._$AE(s8);
  }
  willUpdate(t9) {
  }
  _$AE(t9) {
    this._$EO?.forEach((t10) => t10.hostUpdated?.()), this.hasUpdated || (this.hasUpdated = true, this.firstUpdated(t9)), this.updated(t9);
  }
  _$EM() {
    this._$AL = /* @__PURE__ */ new Map(), this.isUpdatePending = false;
  }
  get updateComplete() {
    return this.getUpdateComplete();
  }
  getUpdateComplete() {
    return this._$ES;
  }
  shouldUpdate(t9) {
    return true;
  }
  update(t9) {
    this._$Eq &&= this._$Eq.forEach((t10) => this._$ET(t10, this[t10])), this._$EM();
  }
  updated(t9) {
  }
  firstUpdated(t9) {
  }
};
y.elementStyles = [], y.shadowRootOptions = { mode: "open" }, y[d("elementProperties")] = /* @__PURE__ */ new Map(), y[d("finalized")] = /* @__PURE__ */ new Map(), p?.({ ReactiveElement: y }), (a.reactiveElementVersions ??= []).push("2.1.2");

// node_modules/lit-html/lit-html.js
var t2 = globalThis;
var i3 = t2.trustedTypes;
var s2 = i3 ? i3.createPolicy("lit-html", { createHTML: (t9) => t9 }) : void 0;
var e3 = "$lit$";
var h2 = `lit$${Math.random().toFixed(9).slice(2)}$`;
var o3 = "?" + h2;
var n3 = `<${o3}>`;
var r3 = document;
var l2 = () => r3.createComment("");
var c3 = (t9) => null === t9 || "object" != typeof t9 && "function" != typeof t9;
var a2 = Array.isArray;
var u2 = (t9) => a2(t9) || "function" == typeof t9?.[Symbol.iterator];
var d2 = "[ 	\n\f\r]";
var f2 = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;
var v = /-->/g;
var _ = />/g;
var m = RegExp(`>|${d2}(?:([^\\s"'>=/]+)(${d2}*=${d2}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g");
var p2 = /'/g;
var g = /"/g;
var $ = /^(?:script|style|textarea|title)$/i;
var y2 = (t9) => (i12, ...s8) => ({ _$litType$: t9, strings: i12, values: s8 });
var x = y2(1);
var b2 = y2(2);
var w = y2(3);
var T = /* @__PURE__ */ Symbol.for("lit-noChange");
var E = /* @__PURE__ */ Symbol.for("lit-nothing");
var A = /* @__PURE__ */ new WeakMap();
var C = r3.createTreeWalker(r3, 129);
function P(t9, i12) {
  if (!a2(t9) || !t9.hasOwnProperty("raw")) throw Error("invalid template strings array");
  return void 0 !== s2 ? s2.createHTML(i12) : i12;
}
var V = (t9, i12) => {
  const s8 = t9.length - 1, o21 = [];
  let r11, l6 = 2 === i12 ? "<svg>" : 3 === i12 ? "<math>" : "", c10 = f2;
  for (let i13 = 0; i13 < s8; i13++) {
    const s9 = t9[i13];
    let a4, u6, d5 = -1, y3 = 0;
    for (; y3 < s9.length && (c10.lastIndex = y3, u6 = c10.exec(s9), null !== u6); ) y3 = c10.lastIndex, c10 === f2 ? "!--" === u6[1] ? c10 = v : void 0 !== u6[1] ? c10 = _ : void 0 !== u6[2] ? ($.test(u6[2]) && (r11 = RegExp("</" + u6[2], "g")), c10 = m) : void 0 !== u6[3] && (c10 = m) : c10 === m ? ">" === u6[0] ? (c10 = r11 ?? f2, d5 = -1) : void 0 === u6[1] ? d5 = -2 : (d5 = c10.lastIndex - u6[2].length, a4 = u6[1], c10 = void 0 === u6[3] ? m : '"' === u6[3] ? g : p2) : c10 === g || c10 === p2 ? c10 = m : c10 === v || c10 === _ ? c10 = f2 : (c10 = m, r11 = void 0);
    const x2 = c10 === m && t9[i13 + 1].startsWith("/>") ? " " : "";
    l6 += c10 === f2 ? s9 + n3 : d5 >= 0 ? (o21.push(a4), s9.slice(0, d5) + e3 + s9.slice(d5) + h2 + x2) : s9 + h2 + (-2 === d5 ? i13 : x2);
  }
  return [P(t9, l6 + (t9[s8] || "<?>") + (2 === i12 ? "</svg>" : 3 === i12 ? "</math>" : "")), o21];
};
var N = class _N {
  constructor({ strings: t9, _$litType$: s8 }, n14) {
    let r11;
    this.parts = [];
    let c10 = 0, a4 = 0;
    const u6 = t9.length - 1, d5 = this.parts, [f5, v3] = V(t9, s8);
    if (this.el = _N.createElement(f5, n14), C.currentNode = this.el.content, 2 === s8 || 3 === s8) {
      const t10 = this.el.content.firstChild;
      t10.replaceWith(...t10.childNodes);
    }
    for (; null !== (r11 = C.nextNode()) && d5.length < u6; ) {
      if (1 === r11.nodeType) {
        if (r11.hasAttributes()) for (const t10 of r11.getAttributeNames()) if (t10.endsWith(e3)) {
          const i12 = v3[a4++], s9 = r11.getAttribute(t10).split(h2), e14 = /([.?@])?(.*)/.exec(i12);
          d5.push({ type: 1, index: c10, name: e14[2], strings: s9, ctor: "." === e14[1] ? H : "?" === e14[1] ? I : "@" === e14[1] ? L : k }), r11.removeAttribute(t10);
        } else t10.startsWith(h2) && (d5.push({ type: 6, index: c10 }), r11.removeAttribute(t10));
        if ($.test(r11.tagName)) {
          const t10 = r11.textContent.split(h2), s9 = t10.length - 1;
          if (s9 > 0) {
            r11.textContent = i3 ? i3.emptyScript : "";
            for (let i12 = 0; i12 < s9; i12++) r11.append(t10[i12], l2()), C.nextNode(), d5.push({ type: 2, index: ++c10 });
            r11.append(t10[s9], l2());
          }
        }
      } else if (8 === r11.nodeType) if (r11.data === o3) d5.push({ type: 2, index: c10 });
      else {
        let t10 = -1;
        for (; -1 !== (t10 = r11.data.indexOf(h2, t10 + 1)); ) d5.push({ type: 7, index: c10 }), t10 += h2.length - 1;
      }
      c10++;
    }
  }
  static createElement(t9, i12) {
    const s8 = r3.createElement("template");
    return s8.innerHTML = t9, s8;
  }
};
function S2(t9, i12, s8 = t9, e14) {
  if (i12 === T) return i12;
  let h9 = void 0 !== e14 ? s8._$Co?.[e14] : s8._$Cl;
  const o21 = c3(i12) ? void 0 : i12._$litDirective$;
  return h9?.constructor !== o21 && (h9?._$AO?.(false), void 0 === o21 ? h9 = void 0 : (h9 = new o21(t9), h9._$AT(t9, s8, e14)), void 0 !== e14 ? (s8._$Co ??= [])[e14] = h9 : s8._$Cl = h9), void 0 !== h9 && (i12 = S2(t9, h9._$AS(t9, i12.values), h9, e14)), i12;
}
var M = class {
  constructor(t9, i12) {
    this._$AV = [], this._$AN = void 0, this._$AD = t9, this._$AM = i12;
  }
  get parentNode() {
    return this._$AM.parentNode;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  u(t9) {
    const { el: { content: i12 }, parts: s8 } = this._$AD, e14 = (t9?.creationScope ?? r3).importNode(i12, true);
    C.currentNode = e14;
    let h9 = C.nextNode(), o21 = 0, n14 = 0, l6 = s8[0];
    for (; void 0 !== l6; ) {
      if (o21 === l6.index) {
        let i13;
        2 === l6.type ? i13 = new R(h9, h9.nextSibling, this, t9) : 1 === l6.type ? i13 = new l6.ctor(h9, l6.name, l6.strings, this, t9) : 6 === l6.type && (i13 = new z(h9, this, t9)), this._$AV.push(i13), l6 = s8[++n14];
      }
      o21 !== l6?.index && (h9 = C.nextNode(), o21++);
    }
    return C.currentNode = r3, e14;
  }
  p(t9) {
    let i12 = 0;
    for (const s8 of this._$AV) void 0 !== s8 && (void 0 !== s8.strings ? (s8._$AI(t9, s8, i12), i12 += s8.strings.length - 2) : s8._$AI(t9[i12])), i12++;
  }
};
var R = class _R {
  get _$AU() {
    return this._$AM?._$AU ?? this._$Cv;
  }
  constructor(t9, i12, s8, e14) {
    this.type = 2, this._$AH = E, this._$AN = void 0, this._$AA = t9, this._$AB = i12, this._$AM = s8, this.options = e14, this._$Cv = e14?.isConnected ?? true;
  }
  get parentNode() {
    let t9 = this._$AA.parentNode;
    const i12 = this._$AM;
    return void 0 !== i12 && 11 === t9?.nodeType && (t9 = i12.parentNode), t9;
  }
  get startNode() {
    return this._$AA;
  }
  get endNode() {
    return this._$AB;
  }
  _$AI(t9, i12 = this) {
    t9 = S2(this, t9, i12), c3(t9) ? t9 === E || null == t9 || "" === t9 ? (this._$AH !== E && this._$AR(), this._$AH = E) : t9 !== this._$AH && t9 !== T && this._(t9) : void 0 !== t9._$litType$ ? this.$(t9) : void 0 !== t9.nodeType ? this.T(t9) : u2(t9) ? this.k(t9) : this._(t9);
  }
  O(t9) {
    return this._$AA.parentNode.insertBefore(t9, this._$AB);
  }
  T(t9) {
    this._$AH !== t9 && (this._$AR(), this._$AH = this.O(t9));
  }
  _(t9) {
    this._$AH !== E && c3(this._$AH) ? this._$AA.nextSibling.data = t9 : this.T(r3.createTextNode(t9)), this._$AH = t9;
  }
  $(t9) {
    const { values: i12, _$litType$: s8 } = t9, e14 = "number" == typeof s8 ? this._$AC(t9) : (void 0 === s8.el && (s8.el = N.createElement(P(s8.h, s8.h[0]), this.options)), s8);
    if (this._$AH?._$AD === e14) this._$AH.p(i12);
    else {
      const t10 = new M(e14, this), s9 = t10.u(this.options);
      t10.p(i12), this.T(s9), this._$AH = t10;
    }
  }
  _$AC(t9) {
    let i12 = A.get(t9.strings);
    return void 0 === i12 && A.set(t9.strings, i12 = new N(t9)), i12;
  }
  k(t9) {
    a2(this._$AH) || (this._$AH = [], this._$AR());
    const i12 = this._$AH;
    let s8, e14 = 0;
    for (const h9 of t9) e14 === i12.length ? i12.push(s8 = new _R(this.O(l2()), this.O(l2()), this, this.options)) : s8 = i12[e14], s8._$AI(h9), e14++;
    e14 < i12.length && (this._$AR(s8 && s8._$AB.nextSibling, e14), i12.length = e14);
  }
  _$AR(t9 = this._$AA.nextSibling, i12) {
    for (this._$AP?.(false, true, i12); t9 && t9 !== this._$AB; ) {
      const i13 = t9.nextSibling;
      t9.remove(), t9 = i13;
    }
  }
  setConnected(t9) {
    void 0 === this._$AM && (this._$Cv = t9, this._$AP?.(t9));
  }
};
var k = class {
  get tagName() {
    return this.element.tagName;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  constructor(t9, i12, s8, e14, h9) {
    this.type = 1, this._$AH = E, this._$AN = void 0, this.element = t9, this.name = i12, this._$AM = e14, this.options = h9, s8.length > 2 || "" !== s8[0] || "" !== s8[1] ? (this._$AH = Array(s8.length - 1).fill(new String()), this.strings = s8) : this._$AH = E;
  }
  _$AI(t9, i12 = this, s8, e14) {
    const h9 = this.strings;
    let o21 = false;
    if (void 0 === h9) t9 = S2(this, t9, i12, 0), o21 = !c3(t9) || t9 !== this._$AH && t9 !== T, o21 && (this._$AH = t9);
    else {
      const e15 = t9;
      let n14, r11;
      for (t9 = h9[0], n14 = 0; n14 < h9.length - 1; n14++) r11 = S2(this, e15[s8 + n14], i12, n14), r11 === T && (r11 = this._$AH[n14]), o21 ||= !c3(r11) || r11 !== this._$AH[n14], r11 === E ? t9 = E : t9 !== E && (t9 += (r11 ?? "") + h9[n14 + 1]), this._$AH[n14] = r11;
    }
    o21 && !e14 && this.j(t9);
  }
  j(t9) {
    t9 === E ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t9 ?? "");
  }
};
var H = class extends k {
  constructor() {
    super(...arguments), this.type = 3;
  }
  j(t9) {
    this.element[this.name] = t9 === E ? void 0 : t9;
  }
};
var I = class extends k {
  constructor() {
    super(...arguments), this.type = 4;
  }
  j(t9) {
    this.element.toggleAttribute(this.name, !!t9 && t9 !== E);
  }
};
var L = class extends k {
  constructor(t9, i12, s8, e14, h9) {
    super(t9, i12, s8, e14, h9), this.type = 5;
  }
  _$AI(t9, i12 = this) {
    if ((t9 = S2(this, t9, i12, 0) ?? E) === T) return;
    const s8 = this._$AH, e14 = t9 === E && s8 !== E || t9.capture !== s8.capture || t9.once !== s8.once || t9.passive !== s8.passive, h9 = t9 !== E && (s8 === E || e14);
    e14 && this.element.removeEventListener(this.name, this, s8), h9 && this.element.addEventListener(this.name, this, t9), this._$AH = t9;
  }
  handleEvent(t9) {
    "function" == typeof this._$AH ? this._$AH.call(this.options?.host ?? this.element, t9) : this._$AH.handleEvent(t9);
  }
};
var z = class {
  constructor(t9, i12, s8) {
    this.element = t9, this.type = 6, this._$AN = void 0, this._$AM = i12, this.options = s8;
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AI(t9) {
    S2(this, t9);
  }
};
var Z = { M: e3, P: h2, A: o3, C: 1, L: V, R: M, D: u2, V: S2, I: R, H: k, N: I, U: L, B: H, F: z };
var j = t2.litHtmlPolyfillSupport;
j?.(N, R), (t2.litHtmlVersions ??= []).push("3.3.0");
var B = (t9, i12, s8) => {
  const e14 = s8?.renderBefore ?? i12;
  let h9 = e14._$litPart$;
  if (void 0 === h9) {
    const t10 = s8?.renderBefore ?? null;
    e14._$litPart$ = h9 = new R(i12.insertBefore(l2(), t10), t10, void 0, s8 ?? {});
  }
  return h9._$AI(t9), h9;
};

// node_modules/lit-element/lit-element.js
var s3 = globalThis;
var i4 = class extends y {
  constructor() {
    super(...arguments), this.renderOptions = { host: this }, this._$Do = void 0;
  }
  createRenderRoot() {
    const t9 = super.createRenderRoot();
    return this.renderOptions.renderBefore ??= t9.firstChild, t9;
  }
  update(t9) {
    const r11 = this.render();
    this.hasUpdated || (this.renderOptions.isConnected = this.isConnected), super.update(t9), this._$Do = B(r11, this.renderRoot, this.renderOptions);
  }
  connectedCallback() {
    super.connectedCallback(), this._$Do?.setConnected(true);
  }
  disconnectedCallback() {
    super.disconnectedCallback(), this._$Do?.setConnected(false);
  }
  render() {
    return T;
  }
};
i4._$litElement$ = true, i4["finalized"] = true, s3.litElementHydrateSupport?.({ LitElement: i4 });
var o4 = s3.litElementPolyfillSupport;
o4?.({ LitElement: i4 });
var n4 = { _$AK: (t9, e14, r11) => {
  t9._$AK(e14, r11);
}, _$AL: (t9) => t9._$AL };
(s3.litElementVersions ??= []).push("4.2.2");

// node_modules/lit-html/is-server.js
var o5 = false;

// node_modules/lit-html/directive-helpers.js
var { I: t3 } = Z;
var i5 = (o21) => null === o21 || "object" != typeof o21 && "function" != typeof o21;
var n5 = { HTML: 1, SVG: 2, MATHML: 3 };
var e4 = (o21, t9) => void 0 === t9 ? void 0 !== o21?._$litType$ : o21?._$litType$ === t9;
var l3 = (o21) => null != o21?._$litType$?.h;
var c4 = (o21) => void 0 !== o21?._$litDirective$;
var d3 = (o21) => o21?._$litDirective$;
var f3 = (o21) => void 0 === o21.strings;
var s4 = () => document.createComment("");
var r4 = (o21, i12, n14) => {
  const e14 = o21._$AA.parentNode, l6 = void 0 === i12 ? o21._$AB : i12._$AA;
  if (void 0 === n14) {
    const i13 = e14.insertBefore(s4(), l6), c10 = e14.insertBefore(s4(), l6);
    n14 = new t3(i13, c10, o21, o21.options);
  } else {
    const t9 = n14._$AB.nextSibling, i13 = n14._$AM, c10 = i13 !== o21;
    if (c10) {
      let t10;
      n14._$AQ?.(o21), n14._$AM = o21, void 0 !== n14._$AP && (t10 = o21._$AU) !== i13._$AU && n14._$AP(t10);
    }
    if (t9 !== l6 || c10) {
      let o22 = n14._$AA;
      for (; o22 !== t9; ) {
        const t10 = o22.nextSibling;
        e14.insertBefore(o22, l6), o22 = t10;
      }
    }
  }
  return n14;
};
var v2 = (o21, t9, i12 = o21) => (o21._$AI(t9, i12), o21);
var u3 = {};
var m2 = (o21, t9 = u3) => o21._$AH = t9;
var p3 = (o21) => o21._$AH;
var M2 = (o21) => {
  o21._$AP?.(false, true);
  let t9 = o21._$AA;
  const i12 = o21._$AB.nextSibling;
  for (; t9 !== i12; ) {
    const o22 = t9.nextSibling;
    t9.remove(), t9 = o22;
  }
};
var h3 = (o21) => {
  o21._$AR();
};

// node_modules/lit-html/directive.js
var t4 = { ATTRIBUTE: 1, CHILD: 2, PROPERTY: 3, BOOLEAN_ATTRIBUTE: 4, EVENT: 5, ELEMENT: 6 };
var e5 = (t9) => (...e14) => ({ _$litDirective$: t9, values: e14 });
var i6 = class {
  constructor(t9) {
  }
  get _$AU() {
    return this._$AM._$AU;
  }
  _$AT(t9, e14, i12) {
    this._$Ct = t9, this._$AM = e14, this._$Ci = i12;
  }
  _$AS(t9, e14) {
    return this.update(t9, e14);
  }
  update(t9, e14) {
    return this.render(...e14);
  }
};

// node_modules/lit-html/async-directive.js
var s5 = (i12, t9) => {
  const e14 = i12._$AN;
  if (void 0 === e14) return false;
  for (const i13 of e14) i13._$AO?.(t9, false), s5(i13, t9);
  return true;
};
var o6 = (i12) => {
  let t9, e14;
  do {
    if (void 0 === (t9 = i12._$AM)) break;
    e14 = t9._$AN, e14.delete(i12), i12 = t9;
  } while (0 === e14?.size);
};
var r5 = (i12) => {
  for (let t9; t9 = i12._$AM; i12 = t9) {
    let e14 = t9._$AN;
    if (void 0 === e14) t9._$AN = e14 = /* @__PURE__ */ new Set();
    else if (e14.has(i12)) break;
    e14.add(i12), c5(t9);
  }
};
function h4(i12) {
  void 0 !== this._$AN ? (o6(this), this._$AM = i12, r5(this)) : this._$AM = i12;
}
function n6(i12, t9 = false, e14 = 0) {
  const r11 = this._$AH, h9 = this._$AN;
  if (void 0 !== h9 && 0 !== h9.size) if (t9) if (Array.isArray(r11)) for (let i13 = e14; i13 < r11.length; i13++) s5(r11[i13], false), o6(r11[i13]);
  else null != r11 && (s5(r11, false), o6(r11));
  else s5(this, i12);
}
var c5 = (i12) => {
  i12.type == t4.CHILD && (i12._$AP ??= n6, i12._$AQ ??= h4);
};
var f4 = class extends i6 {
  constructor() {
    super(...arguments), this._$AN = void 0;
  }
  _$AT(i12, t9, e14) {
    super._$AT(i12, t9, e14), r5(this), this.isConnected = i12._$AU;
  }
  _$AO(i12, t9 = true) {
    i12 !== this.isConnected && (this.isConnected = i12, i12 ? this.reconnected?.() : this.disconnected?.()), t9 && (s5(this, i12), o6(this));
  }
  setValue(t9) {
    if (f3(this._$Ct)) this._$Ct._$AI(t9, this);
    else {
      const i12 = [...this._$Ct._$AH];
      i12[this._$Ci] = t9, this._$Ct._$AI(i12, this, 0);
    }
  }
  disconnected() {
  }
  reconnected() {
  }
};

// node_modules/@lit/reactive-element/decorators/custom-element.js
var t5 = (t9) => (e14, o21) => {
  void 0 !== o21 ? o21.addInitializer(() => {
    customElements.define(t9, e14);
  }) : customElements.define(t9, e14);
};

// node_modules/@lit/reactive-element/decorators/property.js
var o7 = { attribute: true, type: String, converter: u, reflect: false, hasChanged: f };
var r6 = (t9 = o7, e14, r11) => {
  const { kind: n14, metadata: i12 } = r11;
  let s8 = globalThis.litPropertyMetadata.get(i12);
  if (void 0 === s8 && globalThis.litPropertyMetadata.set(i12, s8 = /* @__PURE__ */ new Map()), "setter" === n14 && ((t9 = Object.create(t9)).wrapped = true), s8.set(r11.name, t9), "accessor" === n14) {
    const { name: o21 } = r11;
    return { set(r12) {
      const n15 = e14.get.call(this);
      e14.set.call(this, r12), this.requestUpdate(o21, n15, t9, true, r12);
    }, init(e15) {
      return void 0 !== e15 && this.C(o21, void 0, t9, e15), e15;
    } };
  }
  if ("setter" === n14) {
    const { name: o21 } = r11;
    return function(r12) {
      const n15 = this[o21];
      e14.call(this, r12), this.requestUpdate(o21, n15, t9, true, r12);
    };
  }
  throw Error("Unsupported decorator location: " + n14);
};
function n7(t9) {
  return (e14, o21) => "object" == typeof o21 ? r6(t9, e14, o21) : ((t10, e15, o22) => {
    const r11 = e15.hasOwnProperty(o22);
    return e15.constructor.createProperty(o22, t10), r11 ? Object.getOwnPropertyDescriptor(e15, o22) : void 0;
  })(t9, e14, o21);
}

// node_modules/@lit/reactive-element/decorators/state.js
function r7(r11) {
  return n7({ ...r11, state: true, attribute: false });
}

// node_modules/@lit/reactive-element/decorators/event-options.js
function t6(t9) {
  return (n14, o21) => {
    const c10 = "function" == typeof n14 ? n14 : n14[o21];
    Object.assign(c10, t9);
  };
}

// node_modules/@lit/reactive-element/decorators/base.js
var e6 = (e14, t9, c10) => (c10.configurable = true, c10.enumerable = true, Reflect.decorate && "object" != typeof t9 && Object.defineProperty(e14, t9, c10), c10);

// node_modules/@lit/reactive-element/decorators/query.js
function e7(e14, r11) {
  return (n14, s8, i12) => {
    const o21 = (t9) => t9.renderRoot?.querySelector(e14) ?? null;
    if (r11) {
      const { get: e15, set: r12 } = "object" == typeof s8 ? n14 : i12 ?? /* @__PURE__ */ (() => {
        const t9 = /* @__PURE__ */ Symbol();
        return { get() {
          return this[t9];
        }, set(e16) {
          this[t9] = e16;
        } };
      })();
      return e6(n14, s8, { get() {
        let t9 = e15.call(this);
        return void 0 === t9 && (t9 = o21(this), (null !== t9 || this.hasUpdated) && r12.call(this, t9)), t9;
      } });
    }
    return e6(n14, s8, { get() {
      return o21(this);
    } });
  };
}

// node_modules/@lit/reactive-element/decorators/query-all.js
var e8;
function r8(r11) {
  return (n14, o21) => e6(n14, o21, { get() {
    return (this.renderRoot ?? (e8 ??= document.createDocumentFragment())).querySelectorAll(r11);
  } });
}

// node_modules/@lit/reactive-element/decorators/query-async.js
function r9(r11) {
  return (n14, e14) => e6(n14, e14, { async get() {
    return await this.updateComplete, this.renderRoot?.querySelector(r11) ?? null;
  } });
}

// node_modules/@lit/reactive-element/decorators/query-assigned-elements.js
function o8(o21) {
  return (e14, n14) => {
    const { slot: r11, selector: s8 } = o21 ?? {}, c10 = "slot" + (r11 ? `[name=${r11}]` : ":not([name])");
    return e6(e14, n14, { get() {
      const t9 = this.renderRoot?.querySelector(c10), e15 = t9?.assignedElements(o21) ?? [];
      return void 0 === s8 ? e15 : e15.filter((t10) => t10.matches(s8));
    } });
  };
}

// node_modules/@lit/reactive-element/decorators/query-assigned-nodes.js
function n8(n14) {
  return (o21, r11) => {
    const { slot: e14 } = n14 ?? {}, s8 = "slot" + (e14 ? `[name=${e14}]` : ":not([name])");
    return e6(o21, r11, { get() {
      const t9 = this.renderRoot?.querySelector(s8);
      return t9?.assignedNodes(n14) ?? [];
    } });
  };
}

// node_modules/lit-html/directives/private-async-helpers.js
var t7 = async (t9, s8) => {
  for await (const i12 of t9) if (false === await s8(i12)) return;
};
var s6 = class {
  constructor(t9) {
    this.G = t9;
  }
  disconnect() {
    this.G = void 0;
  }
  reconnect(t9) {
    this.G = t9;
  }
  deref() {
    return this.G;
  }
};
var i7 = class {
  constructor() {
    this.Y = void 0, this.Z = void 0;
  }
  get() {
    return this.Y;
  }
  pause() {
    this.Y ??= new Promise(((t9) => this.Z = t9));
  }
  resume() {
    this.Z?.(), this.Y = this.Z = void 0;
  }
};

// node_modules/lit-html/directives/async-replace.js
var o9 = class extends f4 {
  constructor() {
    super(...arguments), this._$CK = new s6(this), this._$CX = new i7();
  }
  render(i12, s8) {
    return T;
  }
  update(i12, [s8, r11]) {
    if (this.isConnected || this.disconnected(), s8 === this._$CJ) return T;
    this._$CJ = s8;
    let n14 = 0;
    const { _$CK: o21, _$CX: h9 } = this;
    return t7(s8, (async (t9) => {
      for (; h9.get(); ) await h9.get();
      const i13 = o21.deref();
      if (void 0 !== i13) {
        if (i13._$CJ !== s8) return false;
        void 0 !== r11 && (t9 = r11(t9, n14)), i13.commitValue(t9, n14), n14++;
      }
      return true;
    })), T;
  }
  commitValue(t9, i12) {
    this.setValue(t9);
  }
  disconnected() {
    this._$CK.disconnect(), this._$CX.pause();
  }
  reconnected() {
    this._$CK.reconnect(this), this._$CX.resume();
  }
};
var h5 = e5(o9);

// node_modules/lit-html/directives/async-append.js
var c6 = e5(class extends o9 {
  constructor(r11) {
    if (super(r11), r11.type !== t4.CHILD) throw Error("asyncAppend can only be used in child expressions");
  }
  update(r11, e14) {
    return this._$Ctt = r11, super.update(r11, e14);
  }
  commitValue(r11, e14) {
    0 === e14 && h3(this._$Ctt);
    const s8 = r4(this._$Ctt);
    v2(s8, r11);
  }
});

// node_modules/lit-html/directives/cache.js
var d4 = (t9) => l3(t9) ? t9._$litType$.h : t9.strings;
var h6 = e5(class extends i6 {
  constructor(t9) {
    super(t9), this.et = /* @__PURE__ */ new WeakMap();
  }
  render(t9) {
    return [t9];
  }
  update(s8, [e14]) {
    const u6 = e4(this.it) ? d4(this.it) : null, h9 = e4(e14) ? d4(e14) : null;
    if (null !== u6 && (null === h9 || u6 !== h9)) {
      const e15 = p3(s8).pop();
      let o21 = this.et.get(u6);
      if (void 0 === o21) {
        const s9 = document.createDocumentFragment();
        o21 = B(E, s9), o21.setConnected(false), this.et.set(u6, o21);
      }
      m2(o21, [e15]), r4(o21, void 0, e15);
    }
    if (null !== h9) {
      if (null === u6 || u6 !== h9) {
        const t9 = this.et.get(h9);
        if (void 0 !== t9) {
          const i12 = p3(t9).pop();
          h3(s8), r4(s8, void 0, i12), m2(s8, [i12]);
        }
      }
      this.it = e14;
    } else this.it = void 0;
    return this.render(e14);
  }
});

// node_modules/lit-html/directives/choose.js
var r10 = (r11, o21, t9) => {
  for (const t10 of o21) if (t10[0] === r11) return (0, t10[1])();
  return t9?.();
};

// node_modules/lit-html/directives/class-map.js
var e9 = e5(class extends i6 {
  constructor(t9) {
    if (super(t9), t9.type !== t4.ATTRIBUTE || "class" !== t9.name || t9.strings?.length > 2) throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.");
  }
  render(t9) {
    return " " + Object.keys(t9).filter(((s8) => t9[s8])).join(" ") + " ";
  }
  update(s8, [i12]) {
    if (void 0 === this.st) {
      this.st = /* @__PURE__ */ new Set(), void 0 !== s8.strings && (this.nt = new Set(s8.strings.join(" ").split(/\s/).filter(((t9) => "" !== t9))));
      for (const t9 in i12) i12[t9] && !this.nt?.has(t9) && this.st.add(t9);
      return this.render(i12);
    }
    const r11 = s8.element.classList;
    for (const t9 of this.st) t9 in i12 || (r11.remove(t9), this.st.delete(t9));
    for (const t9 in i12) {
      const s9 = !!i12[t9];
      s9 === this.st.has(t9) || this.nt?.has(t9) || (s9 ? (r11.add(t9), this.st.add(t9)) : (r11.remove(t9), this.st.delete(t9)));
    }
    return T;
  }
});

// node_modules/lit-html/directives/guard.js
var e10 = {};
var i8 = e5(class extends i6 {
  constructor() {
    super(...arguments), this.ot = e10;
  }
  render(r11, t9) {
    return t9();
  }
  update(t9, [s8, e14]) {
    if (Array.isArray(s8)) {
      if (Array.isArray(this.ot) && this.ot.length === s8.length && s8.every(((r11, t10) => r11 === this.ot[t10]))) return T;
    } else if (this.ot === s8) return T;
    return this.ot = Array.isArray(s8) ? Array.from(s8) : s8, this.render(s8, e14);
  }
});

// node_modules/lit-html/directives/if-defined.js
var o10 = (o21) => o21 ?? E;

// node_modules/lit-html/directives/join.js
function* o11(o21, t9) {
  const f5 = "function" == typeof t9;
  if (void 0 !== o21) {
    let i12 = -1;
    for (const n14 of o21) i12 > -1 && (yield f5 ? t9(i12) : t9), i12++, yield n14;
  }
}

// node_modules/lit-html/directives/keyed.js
var i9 = e5(class extends i6 {
  constructor() {
    super(...arguments), this.key = E;
  }
  render(r11, t9) {
    return this.key = r11, t9;
  }
  update(r11, [t9, e14]) {
    return t9 !== this.key && (m2(r11), this.key = t9), e14;
  }
});

// node_modules/lit-html/directives/live.js
var l4 = e5(class extends i6 {
  constructor(r11) {
    if (super(r11), r11.type !== t4.PROPERTY && r11.type !== t4.ATTRIBUTE && r11.type !== t4.BOOLEAN_ATTRIBUTE) throw Error("The `live` directive is not allowed on child or event bindings");
    if (!f3(r11)) throw Error("`live` bindings can only contain a single expression");
  }
  render(r11) {
    return r11;
  }
  update(i12, [t9]) {
    if (t9 === T || t9 === E) return t9;
    const o21 = i12.element, l6 = i12.name;
    if (i12.type === t4.PROPERTY) {
      if (t9 === o21[l6]) return T;
    } else if (i12.type === t4.BOOLEAN_ATTRIBUTE) {
      if (!!t9 === o21.hasAttribute(l6)) return T;
    } else if (i12.type === t4.ATTRIBUTE && o21.getAttribute(l6) === t9 + "") return T;
    return m2(i12), t9;
  }
});

// node_modules/lit-html/directives/map.js
function* o12(o21, f5) {
  if (void 0 !== o21) {
    let i12 = 0;
    for (const t9 of o21) yield f5(t9, i12++);
  }
}

// node_modules/lit-html/directives/range.js
function* o13(o21, t9, e14 = 1) {
  const i12 = void 0 === t9 ? 0 : o21;
  t9 ??= o21;
  for (let o22 = i12; e14 > 0 ? o22 < t9 : t9 < o22; o22 += e14) yield o22;
}

// node_modules/lit-html/directives/ref.js
var e11 = () => new h7();
var h7 = class {
};
var o14 = /* @__PURE__ */ new WeakMap();
var n9 = e5(class extends f4 {
  render(i12) {
    return E;
  }
  update(i12, [s8]) {
    const e14 = s8 !== this.G;
    return e14 && void 0 !== this.G && this.rt(void 0), (e14 || this.lt !== this.ct) && (this.G = s8, this.ht = i12.options?.host, this.rt(this.ct = i12.element)), E;
  }
  rt(t9) {
    if (this.isConnected || (t9 = void 0), "function" == typeof this.G) {
      const i12 = this.ht ?? globalThis;
      let s8 = o14.get(i12);
      void 0 === s8 && (s8 = /* @__PURE__ */ new WeakMap(), o14.set(i12, s8)), void 0 !== s8.get(this.G) && this.G.call(this.ht, void 0), s8.set(this.G, t9), void 0 !== t9 && this.G.call(this.ht, t9);
    } else this.G.value = t9;
  }
  get lt() {
    return "function" == typeof this.G ? o14.get(this.ht ?? globalThis)?.get(this.G) : this.G?.value;
  }
  disconnected() {
    this.lt === this.ct && this.rt(void 0);
  }
  reconnected() {
    this.rt(this.ct);
  }
});

// node_modules/lit-html/directives/repeat.js
var u4 = (e14, s8, t9) => {
  const r11 = /* @__PURE__ */ new Map();
  for (let l6 = s8; l6 <= t9; l6++) r11.set(e14[l6], l6);
  return r11;
};
var c7 = e5(class extends i6 {
  constructor(e14) {
    if (super(e14), e14.type !== t4.CHILD) throw Error("repeat() can only be used in text expressions");
  }
  dt(e14, s8, t9) {
    let r11;
    void 0 === t9 ? t9 = s8 : void 0 !== s8 && (r11 = s8);
    const l6 = [], o21 = [];
    let i12 = 0;
    for (const s9 of e14) l6[i12] = r11 ? r11(s9, i12) : i12, o21[i12] = t9(s9, i12), i12++;
    return { values: o21, keys: l6 };
  }
  render(e14, s8, t9) {
    return this.dt(e14, s8, t9).values;
  }
  update(s8, [t9, r11, c10]) {
    const d5 = p3(s8), { values: p4, keys: a4 } = this.dt(t9, r11, c10);
    if (!Array.isArray(d5)) return this.ut = a4, p4;
    const h9 = this.ut ??= [], v3 = [];
    let m4, y3, x2 = 0, j2 = d5.length - 1, k2 = 0, w2 = p4.length - 1;
    for (; x2 <= j2 && k2 <= w2; ) if (null === d5[x2]) x2++;
    else if (null === d5[j2]) j2--;
    else if (h9[x2] === a4[k2]) v3[k2] = v2(d5[x2], p4[k2]), x2++, k2++;
    else if (h9[j2] === a4[w2]) v3[w2] = v2(d5[j2], p4[w2]), j2--, w2--;
    else if (h9[x2] === a4[w2]) v3[w2] = v2(d5[x2], p4[w2]), r4(s8, v3[w2 + 1], d5[x2]), x2++, w2--;
    else if (h9[j2] === a4[k2]) v3[k2] = v2(d5[j2], p4[k2]), r4(s8, d5[x2], d5[j2]), j2--, k2++;
    else if (void 0 === m4 && (m4 = u4(a4, k2, w2), y3 = u4(h9, x2, j2)), m4.has(h9[x2])) if (m4.has(h9[j2])) {
      const e14 = y3.get(a4[k2]), t10 = void 0 !== e14 ? d5[e14] : null;
      if (null === t10) {
        const e15 = r4(s8, d5[x2]);
        v2(e15, p4[k2]), v3[k2] = e15;
      } else v3[k2] = v2(t10, p4[k2]), r4(s8, d5[x2], t10), d5[e14] = null;
      k2++;
    } else M2(d5[j2]), j2--;
    else M2(d5[x2]), x2++;
    for (; k2 <= w2; ) {
      const e14 = r4(s8, v3[w2 + 1]);
      v2(e14, p4[k2]), v3[k2++] = e14;
    }
    for (; x2 <= j2; ) {
      const e14 = d5[x2++];
      null !== e14 && M2(e14);
    }
    return this.ut = a4, m2(s8, v3), T;
  }
});

// node_modules/lit-html/directives/style-map.js
var n10 = "important";
var i10 = " !" + n10;
var o15 = e5(class extends i6 {
  constructor(t9) {
    if (super(t9), t9.type !== t4.ATTRIBUTE || "style" !== t9.name || t9.strings?.length > 2) throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.");
  }
  render(t9) {
    return Object.keys(t9).reduce(((e14, r11) => {
      const s8 = t9[r11];
      return null == s8 ? e14 : e14 + `${r11 = r11.includes("-") ? r11 : r11.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g, "-$&").toLowerCase()}:${s8};`;
    }), "");
  }
  update(e14, [r11]) {
    const { style: s8 } = e14.element;
    if (void 0 === this.ft) return this.ft = new Set(Object.keys(r11)), this.render(r11);
    for (const t9 of this.ft) null == r11[t9] && (this.ft.delete(t9), t9.includes("-") ? s8.removeProperty(t9) : s8[t9] = null);
    for (const t9 in r11) {
      const e15 = r11[t9];
      if (null != e15) {
        this.ft.add(t9);
        const r12 = "string" == typeof e15 && e15.endsWith(i10);
        t9.includes("-") || r12 ? s8.setProperty(t9, r12 ? e15.slice(0, -11) : e15, r12 ? n10 : "") : s8[t9] = e15;
      }
    }
    return T;
  }
});

// node_modules/lit-html/directives/template-content.js
var o16 = e5(class extends i6 {
  constructor(t9) {
    if (super(t9), t9.type !== t4.CHILD) throw Error("templateContent can only be used in child bindings");
  }
  render(r11) {
    return this.vt === r11 ? T : (this.vt = r11, document.importNode(r11.content, true));
  }
});

// node_modules/lit-html/directives/unsafe-html.js
var e12 = class extends i6 {
  constructor(i12) {
    if (super(i12), this.it = E, i12.type !== t4.CHILD) throw Error(this.constructor.directiveName + "() can only be used in child bindings");
  }
  render(r11) {
    if (r11 === E || null == r11) return this._t = void 0, this.it = r11;
    if (r11 === T) return r11;
    if ("string" != typeof r11) throw Error(this.constructor.directiveName + "() called with a non-string value");
    if (r11 === this.it) return this._t;
    this.it = r11;
    const s8 = [r11];
    return s8.raw = s8, this._t = { _$litType$: this.constructor.resultType, strings: s8, values: [] };
  }
};
e12.directiveName = "unsafeHTML", e12.resultType = 1;
var o17 = e5(e12);

// node_modules/lit-html/directives/unsafe-mathml.js
var e13 = class extends e12 {
};
e13.directiveName = "unsafeMath", e13.resultType = 3;
var o18 = e5(e13);

// node_modules/lit-html/directives/unsafe-svg.js
var t8 = class extends e12 {
};
t8.directiveName = "unsafeSVG", t8.resultType = 2;
var o19 = e5(t8);

// node_modules/lit-html/directives/until.js
var n11 = (t9) => !i5(t9) && "function" == typeof t9.then;
var h8 = 1073741823;
var c8 = class extends f4 {
  constructor() {
    super(...arguments), this._$Cwt = h8, this._$Cbt = [], this._$CK = new s6(this), this._$CX = new i7();
  }
  render(...s8) {
    return s8.find(((t9) => !n11(t9))) ?? T;
  }
  update(s8, i12) {
    const e14 = this._$Cbt;
    let r11 = e14.length;
    this._$Cbt = i12;
    const o21 = this._$CK, c10 = this._$CX;
    this.isConnected || this.disconnected();
    for (let t9 = 0; t9 < i12.length && !(t9 > this._$Cwt); t9++) {
      const s9 = i12[t9];
      if (!n11(s9)) return this._$Cwt = t9, s9;
      t9 < r11 && s9 === e14[t9] || (this._$Cwt = h8, r11 = 0, Promise.resolve(s9).then((async (t10) => {
        for (; c10.get(); ) await c10.get();
        const i13 = o21.deref();
        if (void 0 !== i13) {
          const e15 = i13._$Cbt.indexOf(s9);
          e15 > -1 && e15 < i13._$Cwt && (i13._$Cwt = e15, i13.setValue(t10));
        }
      })));
    }
    return T;
  }
  disconnected() {
    this._$CK.disconnect(), this._$CX.pause();
  }
  reconnected() {
    this._$CK.reconnect(this), this._$CX.resume();
  }
};
var m3 = e5(c8);

// node_modules/lit-html/directives/when.js
function n12(n14, r11, t9) {
  return n14 ? r11(n14) : t9?.(n14);
}

// node_modules/lit-html/static.js
var a3 = /* @__PURE__ */ Symbol.for("");
var o20 = (t9) => {
  if (t9?.r === a3) return t9?._$litStatic$;
};
var s7 = (t9) => ({ _$litStatic$: t9, r: a3 });
var i11 = (t9, ...r11) => ({ _$litStatic$: r11.reduce(((r12, e14, a4) => r12 + ((t10) => {
  if (void 0 !== t10._$litStatic$) return t10._$litStatic$;
  throw Error(`Value passed to 'literal' function must be a 'literal' result: ${t10}. Use 'unsafeStatic' to pass non-literal values, but
            take care to ensure page security.`);
})(e14) + t9[a4 + 1]), t9[0]), r: a3 });
var l5 = /* @__PURE__ */ new Map();
var n13 = (t9) => (r11, ...e14) => {
  const a4 = e14.length;
  let s8, i12;
  const n14 = [], u6 = [];
  let c10, $3 = 0, f5 = false;
  for (; $3 < a4; ) {
    for (c10 = r11[$3]; $3 < a4 && void 0 !== (i12 = e14[$3], s8 = o20(i12)); ) c10 += s8 + r11[++$3], f5 = true;
    $3 !== a4 && u6.push(i12), n14.push(c10), $3++;
  }
  if ($3 === a4 && n14.push(r11[a4]), f5) {
    const t10 = n14.join("$$lit$$");
    void 0 === (r11 = l5.get(t10)) && (n14.raw = n14, l5.set(t10, r11 = n14)), e14 = u6;
  }
  return t9(r11, ...e14);
};
var u5 = n13(x);
var c9 = n13(b2);
var $2 = n13(w);
export {
  f4 as AsyncDirective,
  o9 as AsyncReplaceDirective,
  n as CSSResult,
  i6 as Directive,
  i4 as LitElement,
  t4 as PartType,
  y as ReactiveElement,
  n5 as TemplateResultType,
  e12 as UnsafeHTMLDirective,
  c8 as UntilDirective,
  n4 as _$LE,
  Z as _$LH,
  S as adoptStyles,
  c6 as asyncAppend,
  h5 as asyncReplace,
  h6 as cache,
  r10 as choose,
  e9 as classMap,
  h3 as clearPart,
  e11 as createRef,
  i as css,
  t5 as customElement,
  u as defaultConverter,
  e5 as directive,
  t6 as eventOptions,
  p3 as getCommittedValue,
  c as getCompatibleStyle,
  d3 as getDirectiveClass,
  i8 as guard,
  x as html,
  o10 as ifDefined,
  r4 as insertPart,
  l3 as isCompiledTemplateResult,
  c4 as isDirectiveResult,
  i5 as isPrimitive,
  o5 as isServer,
  f3 as isSingleExpression,
  e4 as isTemplateResult,
  o11 as join,
  i9 as keyed,
  i11 as literal,
  l4 as live,
  o12 as map,
  w as mathml,
  T as noChange,
  f as notEqual,
  E as nothing,
  n7 as property,
  e7 as query,
  r8 as queryAll,
  o8 as queryAssignedElements,
  n8 as queryAssignedNodes,
  r9 as queryAsync,
  o13 as range,
  n9 as ref,
  M2 as removePart,
  B as render,
  c7 as repeat,
  v2 as setChildPartValue,
  m2 as setCommittedValue,
  r6 as standardProperty,
  r7 as state,
  u5 as staticHtml,
  $2 as staticMathml,
  c9 as staticSvg,
  o15 as styleMap,
  e as supportsAdoptingStyleSheets,
  b2 as svg,
  o16 as templateContent,
  r as unsafeCSS,
  o17 as unsafeHTML,
  o18 as unsafeMathML,
  o19 as unsafeSVG,
  s7 as unsafeStatic,
  m3 as until,
  n12 as when,
  n13 as withStatic
};
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
lit-html/directive.js:
lit-html/async-directive.js:
@lit/reactive-element/decorators/custom-element.js:
@lit/reactive-element/decorators/property.js:
@lit/reactive-element/decorators/state.js:
@lit/reactive-element/decorators/event-options.js:
@lit/reactive-element/decorators/base.js:
@lit/reactive-element/decorators/query.js:
@lit/reactive-element/decorators/query-all.js:
@lit/reactive-element/decorators/query-async.js:
@lit/reactive-element/decorators/query-assigned-nodes.js:
lit-html/directives/async-replace.js:
lit-html/directives/async-append.js:
lit-html/directives/cache.js:
lit-html/directives/repeat.js:
lit-html/directives/unsafe-html.js:
lit-html/directives/unsafe-svg.js:
lit-html/directives/until.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directive-helpers.js:
lit-html/directives/live.js:
lit-html/directives/ref.js:
lit-html/directives/template-content.js:
lit-html/static.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-assigned-elements.js:
lit-html/directives/private-async-helpers.js:
lit-html/directives/choose.js:
lit-html/directives/join.js:
lit-html/directives/keyed.js:
lit-html/directives/map.js:
lit-html/directives/range.js:
lit-html/directives/when.js:
  (**
   * @license
   * Copyright 2021 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/class-map.js:
lit-html/directives/guard.js:
lit-html/directives/if-defined.js:
lit-html/directives/style-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/unsafe-mathml.js:
  (**
   * @license
   * Copyright 2024 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
