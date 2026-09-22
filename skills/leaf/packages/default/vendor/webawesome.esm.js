/*! Web Awesome 3.13.0 — MIT — licenses: webawesome.LICENSES.txt */
import{A as et,B as v,C as _,D as wt,E as yt,F as xt,G as k,H as f,I as Kt,J as kt,K as X,L as it,M as jt,N as Gt,O as Xt,P as Yt,a as o,b as C,c as d,d as Nt,e as Wt,f as mt,g as at,h as ft,i as bt,j as vt,k as st,l as H,m as S,n as Ut,o as gt,p as E,q as s,r as y,s as Pt,t as m,u as j,v as z,w as F,x as D,y as A,z as tt}from"./webawesome/chunk-JLLYHHSI.js";/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var rt=(t={})=>{let{validationElement:e,validationProperty:i}=t;e||typeof document<"u"&&"createElement"in document&&(e=Object.assign(document.createElement("input"),{required:!0})),i||(i="value");let r={observedAttributes:["required"],message:e?.validationMessage,checkValidity(a){let n={message:"",isValid:!0,invalidKeys:[]};return(a.required??a.hasAttribute("required"))&&!a[i]&&(n.message=typeof r.message=="function"?r.message(a):r.message||"",n.isValid=!1,n.invalidKeys.push("valueMissing")),n}};return r};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var Zt=C`
  :host {
    --grid-width: 17em;
    --grid-height: 12em;
    --grid-handle-size: 1.25em;
    --slider-height: 1em;
    --slider-handle-size: calc(var(--slider-height) + 0.25em);
  }

  .color-picker {
    background-color: var(--wa-color-surface-raised);
    border-radius: var(--wa-border-radius-m);
    border-style: var(--wa-border-style);
    border-width: var(--wa-border-width-s);
    border-color: var(--wa-color-surface-border);
    box-shadow: var(--wa-shadow-m);
    color: var(--color);
    font: inherit;
    font-size: inherit;
    user-select: none;
    width: var(--grid-width);
    -webkit-user-select: none;
  }

  .grid {
    position: relative;
    height: var(--grid-height);
    background-image:
      linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 1) 100%),
      linear-gradient(to right, #fff 0%, rgba(255, 255, 255, 0) 100%);
    border-top-left-radius: calc(var(--wa-border-radius-m) - var(--wa-border-width-s));
    border-top-right-radius: calc(var(--wa-border-radius-m) - var(--wa-border-width-s));
    cursor: crosshair;
    forced-color-adjust: none;
  }

  .grid-handle {
    position: absolute;
    width: var(--grid-handle-size);
    height: var(--grid-handle-size);
    border-radius: var(--wa-border-radius-circle);
    box-shadow: 0 0 0 0.0625rem rgba(0, 0, 0, 0.2);
    border: solid 0.125rem white;
    margin-top: calc(var(--grid-handle-size) / -2);
    margin-left: calc(var(--grid-handle-size) / -2);
    transition: scale var(--wa-transition-normal) var(--wa-transition-easing);
  }

  .grid-handle-dragging {
    cursor: none;
    scale: 1.5;
  }

  .grid-handle:focus-visible {
    outline: var(--wa-focus-ring);
  }

  .controls {
    padding: 0.75em;
    display: flex;
    align-items: center;
  }

  .sliders {
    flex: 1 1 auto;
  }

  .slider {
    position: relative;
    height: var(--slider-height);
    border-radius: var(--wa-border-radius-s);
    box-shadow: inset 0 0 0 0.0625rem rgba(0, 0, 0, 0.2);
    forced-color-adjust: none;
  }

  .slider:not(:last-of-type) {
    margin-bottom: 0.75em;
  }

  .slider-handle {
    position: absolute;
    top: calc(50% - var(--slider-handle-size) / 2);
    width: var(--slider-handle-size);
    height: var(--slider-handle-size);
    border-radius: var(--wa-border-radius-circle);
    border: solid 0.125rem white;
    box-shadow: 0 0 0 0.0625rem rgba(0, 0, 0, 0.2);
    margin-left: calc(var(--slider-handle-size) / -2);
  }

  .slider-handle:focus-visible {
    outline: var(--wa-focus-ring);
  }

  .hue {
    background-image: linear-gradient(
      to right,
      rgb(255, 0, 0) 0%,
      rgb(255, 255, 0) 17%,
      rgb(0, 255, 0) 33%,
      rgb(0, 255, 255) 50%,
      rgb(0, 0, 255) 67%,
      rgb(255, 0, 255) 83%,
      rgb(255, 0, 0) 100%
    );
  }

  .alpha .alpha-gradient {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border-radius: inherit;
  }

  .preview {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    position: relative;
    width: 3em;
    height: 3em;
    border: none;
    border-radius: var(--wa-border-radius-circle);
    background: none;
    font-size: inherit;
    margin-inline-start: 0.75em;
    cursor: copy;
    forced-color-adjust: none;
  }

  .preview:before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    box-shadow: inset 0 0 0 0.0625rem rgba(0, 0, 0, 0.2);

    /* We use a custom property in lieu of currentColor because of https://bugs.webkit.org/show_bug.cgi?id=216780 */
    background-color: var(--preview-color);
  }

  .preview:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  .preview-color {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: solid 0.0625rem rgba(0, 0, 0, 0.125);
  }

  .preview-color-copied {
    animation: pulse 850ms;
  }

  @keyframes pulse {
    0% {
      box-shadow: 0 0 0 0 var(--wa-color-brand-fill-loud);
    }
    70% {
      box-shadow: 0 0 0 0.5rem transparent;
    }
    100% {
      box-shadow: 0 0 0 0 transparent;
    }
  }

  .user-input {
    display: flex;
    align-items: center;
    padding: 0 0.75em 0.75em 0.75em;
  }

  .user-input wa-input {
    min-width: 0; /* fix input width in Safari */
    flex: 1 1 auto;

    &::part(form-control-label) {
      /* Visually hidden */
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
  }

  .user-input wa-button-group {
    margin-inline-start: 0.75em;

    &::part(base) {
      flex-wrap: nowrap;
    }
  }

  .user-input wa-button:first-of-type {
    min-width: 3em;
    max-width: 3em;
  }

  .swatches {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(1.5em, 100%), 1fr));
    grid-gap: 0.5em;
    justify-items: center;
    border-block-start: var(--wa-form-control-border-style) var(--wa-form-control-border-width)
      var(--wa-color-surface-border);
    padding: 0.5em;
    forced-color-adjust: none;
  }

  .swatch {
    position: relative;
    aspect-ratio: 1 / 1;
    width: 100%;
    border-radius: var(--wa-border-radius-s);
  }

  .swatch .swatch-color {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: solid 0.0625rem rgba(0, 0, 0, 0.125);
    border-radius: inherit;
    cursor: pointer;
  }

  .swatch:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  .transparent-bg {
    background-image:
      linear-gradient(45deg, var(--wa-color-neutral-fill-normal) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, var(--wa-color-neutral-fill-normal) 75%),
      linear-gradient(45deg, transparent 75%, var(--wa-color-neutral-fill-normal) 75%),
      linear-gradient(45deg, var(--wa-color-neutral-fill-normal) 25%, transparent 25%);
    background-size: 0.5rem 0.5rem;
    background-position:
      0 0,
      0 0,
      -0.25rem -0.25rem,
      0.25rem 0.25rem;
  }

  :host([disabled]) {
    opacity: 0.5;
    cursor: not-allowed;

    .grid,
    .grid-handle,
    .slider,
    .slider-handle,
    .preview,
    .swatch,
    .swatch-color {
      pointer-events: none;
    }
  }

  /*
   * Color dropdown
   */

  .color-dropdown {
    display: contents;
  }

  .color-dropdown::part(panel) {
    max-height: none;
    background-color: var(--wa-color-surface-raised);
    border: var(--wa-border-style) var(--wa-border-width-s) var(--wa-color-surface-border);
    border-radius: var(--wa-border-radius-m);
    overflow: visible;
  }

  .trigger {
    display: block;
    position: relative;
    background-color: transparent;
    border: none;
    cursor: pointer;
    font-size: inherit;
    forced-color-adjust: none;
    width: var(--wa-form-control-height);
    height: var(--wa-form-control-height);
    border-radius: var(--wa-form-control-border-radius);
  }

  .trigger:before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    background-color: currentColor;
    box-shadow:
      inset 0 0 0 var(--wa-form-control-border-width) var(--wa-form-control-border-color),
      inset 0 0 0 calc(var(--wa-form-control-border-width) * 3) var(--wa-color-surface-default);
  }

  .trigger-empty:before {
    background-color: transparent;
  }

  .trigger:focus-visible {
    outline: none;
  }

  .trigger:focus-visible:not(.trigger:disabled) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  :host([disabled]) :is(.label, .trigger) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .form-control.form-control-has-label .label {
    cursor: pointer;
    display: inline-block;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function ot(t,e){function i(a){let n=t.getBoundingClientRect(),l=t.ownerDocument.defaultView,h=n.left+l.pageXOffset,u=n.top+l.pageYOffset,p=a.pageX-h,V=a.pageY-u;e?.onMove&&e.onMove(p,V)}function r(){document.removeEventListener("pointermove",i),document.removeEventListener("pointerup",r),e?.onStop&&e.onStop()}document.addEventListener("pointermove",i,{passive:!0}),document.addEventListener("pointerup",r),e?.initialEvent instanceof PointerEvent&&i(e.initialEvent)}var Vt=typeof window<"u"&&"ontouchstart"in window,nt=class{constructor(t,e){this.isActive=!1,this.isDragging=!1,this.handleDragStart=i=>{let r="touches"in i?i.touches[0].clientX:i.clientX,a="touches"in i?i.touches[0].clientY:i.clientY;this.isDragging||!Vt&&i.buttons>1||(this.isDragging=!0,document.addEventListener("pointerup",this.handleDragStop),document.addEventListener("pointermove",this.handleDragMove),document.addEventListener("pointercancel",this.handleDragStop),document.addEventListener("touchend",this.handleDragStop),document.addEventListener("touchmove",this.handleDragMove),document.addEventListener("touchcancel",this.handleDragStop),this.options.start(r,a))},this.handleDragStop=i=>{let r="changedTouches"in i?i.changedTouches[0].clientX:i.clientX,a="changedTouches"in i?i.changedTouches[0].clientY:i.clientY;this.isDragging=!1,document.removeEventListener("pointerup",this.handleDragStop),document.removeEventListener("pointermove",this.handleDragMove),document.removeEventListener("pointercancel",this.handleDragStop),document.removeEventListener("touchend",this.handleDragStop),document.removeEventListener("touchmove",this.handleDragMove),document.removeEventListener("touchcancel",this.handleDragStop),this.options.stop(r,a)},this.handleDragMove=i=>{let r="touches"in i?i.touches[0].clientX:i.clientX,a="touches"in i?i.touches[0].clientY:i.clientY;window.getSelection()?.removeAllRanges(),this.options.move(r,a)},this.element=t,this.options={start:()=>{},stop:()=>{},move:()=>{},...e},this.start()}start(){this.isActive||(this.element.addEventListener("pointerdown",this.handleDragStart),Vt&&this.element.addEventListener("touchstart",this.handleDragStart),this.isActive=!0)}stop(){document.removeEventListener("pointerup",this.handleDragStop),document.removeEventListener("pointermove",this.handleDragMove),document.removeEventListener("pointercancel",this.handleDragStop),document.removeEventListener("touchend",this.handleDragStop),document.removeEventListener("touchmove",this.handleDragMove),document.removeEventListener("touchcancel",this.handleDragStop),this.element.removeEventListener("pointerdown",this.handleDragStart),Vt&&this.element.removeEventListener("touchstart",this.handleDragStart),this.isActive=!1,this.isDragging=!1}toggle(t){(t!==void 0?t:!this.isActive)?this.start():this.stop()}};function R(t,e){Ce(t)&&(t="100%");let i=$e(t);return t=e===360?t:Math.min(e,Math.max(0,parseFloat(t))),i&&(t=parseInt(String(t*e),10)/100),Math.abs(t-e)<1e-6?1:(e===360?t=(t<0?t%e+e:t%e)/parseFloat(String(e)):t=t%e/parseFloat(String(e)),t)}function lt(t){return Math.min(1,Math.max(0,t))}function Ce(t){return typeof t=="string"&&t.indexOf(".")!==-1&&parseFloat(t)===1}function $e(t){return typeof t=="string"&&t.indexOf("%")!==-1}function Ct(t){return t=parseFloat(t),(isNaN(t)||t<0||t>1)&&(t=1),t}function ht(t){return Number(t)<=1?`${Number(t)*100}%`:t}function Y(t){return t.length===1?"0"+t:String(t)}function Jt(t,e,i){return{r:R(t,255)*255,g:R(e,255)*255,b:R(i,255)*255}}function Dt(t,e,i){t=R(t,255),e=R(e,255),i=R(i,255);let r=Math.max(t,e,i),a=Math.min(t,e,i),n=0,l=0,h=(r+a)/2;if(r===a)l=0,n=0;else{let u=r-a;switch(l=h>.5?u/(2-r-a):u/(r+a),r){case t:n=(e-i)/u+(e<i?6:0);break;case e:n=(i-t)/u+2;break;case i:n=(t-e)/u+4;break;default:break}n/=6}return{h:n,s:l,l:h}}function _t(t,e,i){return i<0&&(i+=1),i>1&&(i-=1),i<1/6?t+(e-t)*(6*i):i<1/2?e:i<2/3?t+(e-t)*(2/3-i)*6:t}function Qt(t,e,i){let r,a,n;if(t=R(t,360),e=R(e,100),i=R(i,100),e===0)a=i,n=i,r=i;else{let l=i<.5?i*(1+e):i+e-i*e,h=2*i-l;r=_t(h,l,t+1/3),a=_t(h,l,t),n=_t(h,l,t-1/3)}return{r:r*255,g:a*255,b:n*255}}function At(t,e,i){t=R(t,255),e=R(e,255),i=R(i,255);let r=Math.max(t,e,i),a=Math.min(t,e,i),n=0,l=r,h=r-a,u=r===0?0:h/r;if(r===a)n=0;else{switch(r){case t:n=(e-i)/h+(e<i?6:0);break;case e:n=(i-t)/h+2;break;case i:n=(t-e)/h+4;break;default:break}n/=6}return{h:n,s:u,v:l}}function te(t,e,i){t=R(t,360)*6,e=R(e,100),i=R(i,100);let r=Math.floor(t),a=t-r,n=i*(1-e),l=i*(1-a*e),h=i*(1-(1-a)*e),u=r%6,p=[i,l,n,n,h,i][u],V=[h,i,i,l,n,n][u],O=[n,n,h,i,i,l][u];return{r:p*255,g:V*255,b:O*255}}function Tt(t,e,i,r){let a=[Y(Math.round(t).toString(16)),Y(Math.round(e).toString(16)),Y(Math.round(i).toString(16))];return r&&a[0].startsWith(a[0].charAt(1))&&a[1].startsWith(a[1].charAt(1))&&a[2].startsWith(a[2].charAt(1))?a[0].charAt(0)+a[1].charAt(0)+a[2].charAt(0):a.join("")}function ee(t,e,i,r,a){let n=[Y(Math.round(t).toString(16)),Y(Math.round(e).toString(16)),Y(Math.round(i).toString(16)),Y(Se(r))];return a&&n[0].startsWith(n[0].charAt(1))&&n[1].startsWith(n[1].charAt(1))&&n[2].startsWith(n[2].charAt(1))&&n[3].startsWith(n[3].charAt(1))?n[0].charAt(0)+n[1].charAt(0)+n[2].charAt(0)+n[3].charAt(0):n.join("")}function ie(t,e,i,r){let a=t/100,n=e/100,l=i/100,h=r/100,u=255*(1-a)*(1-h),p=255*(1-n)*(1-h),V=255*(1-l)*(1-h);return{r:u,g:p,b:V}}function Rt(t,e,i){let r=1-t/255,a=1-e/255,n=1-i/255,l=Math.min(r,a,n);return l===1?(r=0,a=0,n=0):(r=(r-l)/(1-l)*100,a=(a-l)/(1-l)*100,n=(n-l)/(1-l)*100),l*=100,{c:Math.round(r),m:Math.round(a),y:Math.round(n),k:Math.round(l)}}function Se(t){return Math.round(parseFloat(t)*255).toString(16)}function Mt(t){return B(t)/255}function B(t){return parseInt(t,16)}function re(t){return{r:t>>16,g:(t&65280)>>8,b:t&255}}var ut={aliceblue:"#f0f8ff",antiquewhite:"#faebd7",aqua:"#00ffff",aquamarine:"#7fffd4",azure:"#f0ffff",beige:"#f5f5dc",bisque:"#ffe4c4",black:"#000000",blanchedalmond:"#ffebcd",blue:"#0000ff",blueviolet:"#8a2be2",brown:"#a52a2a",burlywood:"#deb887",cadetblue:"#5f9ea0",chartreuse:"#7fff00",chocolate:"#d2691e",coral:"#ff7f50",cornflowerblue:"#6495ed",cornsilk:"#fff8dc",crimson:"#dc143c",cyan:"#00ffff",darkblue:"#00008b",darkcyan:"#008b8b",darkgoldenrod:"#b8860b",darkgray:"#a9a9a9",darkgreen:"#006400",darkgrey:"#a9a9a9",darkkhaki:"#bdb76b",darkmagenta:"#8b008b",darkolivegreen:"#556b2f",darkorange:"#ff8c00",darkorchid:"#9932cc",darkred:"#8b0000",darksalmon:"#e9967a",darkseagreen:"#8fbc8f",darkslateblue:"#483d8b",darkslategray:"#2f4f4f",darkslategrey:"#2f4f4f",darkturquoise:"#00ced1",darkviolet:"#9400d3",deeppink:"#ff1493",deepskyblue:"#00bfff",dimgray:"#696969",dimgrey:"#696969",dodgerblue:"#1e90ff",firebrick:"#b22222",floralwhite:"#fffaf0",forestgreen:"#228b22",fuchsia:"#ff00ff",gainsboro:"#dcdcdc",ghostwhite:"#f8f8ff",goldenrod:"#daa520",gold:"#ffd700",gray:"#808080",green:"#008000",greenyellow:"#adff2f",grey:"#808080",honeydew:"#f0fff0",hotpink:"#ff69b4",indianred:"#cd5c5c",indigo:"#4b0082",ivory:"#fffff0",khaki:"#f0e68c",lavenderblush:"#fff0f5",lavender:"#e6e6fa",lawngreen:"#7cfc00",lemonchiffon:"#fffacd",lightblue:"#add8e6",lightcoral:"#f08080",lightcyan:"#e0ffff",lightgoldenrodyellow:"#fafad2",lightgray:"#d3d3d3",lightgreen:"#90ee90",lightgrey:"#d3d3d3",lightpink:"#ffb6c1",lightsalmon:"#ffa07a",lightseagreen:"#20b2aa",lightskyblue:"#87cefa",lightslategray:"#778899",lightslategrey:"#778899",lightsteelblue:"#b0c4de",lightyellow:"#ffffe0",lime:"#00ff00",limegreen:"#32cd32",linen:"#faf0e6",magenta:"#ff00ff",maroon:"#800000",mediumaquamarine:"#66cdaa",mediumblue:"#0000cd",mediumorchid:"#ba55d3",mediumpurple:"#9370db",mediumseagreen:"#3cb371",mediumslateblue:"#7b68ee",mediumspringgreen:"#00fa9a",mediumturquoise:"#48d1cc",mediumvioletred:"#c71585",midnightblue:"#191970",mintcream:"#f5fffa",mistyrose:"#ffe4e1",moccasin:"#ffe4b5",navajowhite:"#ffdead",navy:"#000080",oldlace:"#fdf5e6",olive:"#808000",olivedrab:"#6b8e23",orange:"#ffa500",orangered:"#ff4500",orchid:"#da70d6",palegoldenrod:"#eee8aa",palegreen:"#98fb98",paleturquoise:"#afeeee",palevioletred:"#db7093",papayawhip:"#ffefd5",peachpuff:"#ffdab9",peru:"#cd853f",pink:"#ffc0cb",plum:"#dda0dd",powderblue:"#b0e0e6",purple:"#800080",rebeccapurple:"#663399",red:"#ff0000",rosybrown:"#bc8f8f",royalblue:"#4169e1",saddlebrown:"#8b4513",salmon:"#fa8072",sandybrown:"#f4a460",seagreen:"#2e8b57",seashell:"#fff5ee",sienna:"#a0522d",silver:"#c0c0c0",skyblue:"#87ceeb",slateblue:"#6a5acd",slategray:"#708090",slategrey:"#708090",snow:"#fffafa",springgreen:"#00ff7f",steelblue:"#4682b4",tan:"#d2b48c",teal:"#008080",thistle:"#d8bfd8",tomato:"#ff6347",turquoise:"#40e0d0",violet:"#ee82ee",wheat:"#f5deb3",white:"#ffffff",whitesmoke:"#f5f5f5",yellow:"#ffff00",yellowgreen:"#9acd32"};function oe(t){let e={r:0,g:0,b:0},i=1,r=null,a=null,n=null,l=!1,h=!1;return typeof t=="string"&&(t=Ve(t)),typeof t=="object"&&(N(t.r)&&N(t.g)&&N(t.b)?(e=Jt(t.r,t.g,t.b),l=!0,h=String(t.r).substr(-1)==="%"?"prgb":"rgb"):N(t.h)&&N(t.s)&&N(t.v)?(r=ht(t.s),a=ht(t.v),e=te(t.h,r,a),l=!0,h="hsv"):N(t.h)&&N(t.s)&&N(t.l)?(r=ht(t.s),n=ht(t.l),e=Qt(t.h,r,n),l=!0,h="hsl"):N(t.c)&&N(t.m)&&N(t.y)&&N(t.k)&&(e=ie(t.c,t.m,t.y,t.k),l=!0,h="cmyk"),Object.prototype.hasOwnProperty.call(t,"a")&&(i=t.a)),i=Ct(i),{ok:l,format:t.format||h,r:Math.min(255,Math.max(e.r,0)),g:Math.min(255,Math.max(e.g,0)),b:Math.min(255,Math.max(e.b,0)),a:i}}var Ee="[-\\+]?\\d+%?",ze="[-\\+]?\\d*\\.\\d+%?",Z="(?:"+ze+")|(?:"+Ee+")",Lt="[\\s|\\(]+("+Z+")[,|\\s]+("+Z+")[,|\\s]+("+Z+")\\s*\\)?",$t="[\\s|\\(]+("+Z+")[,|\\s]+("+Z+")[,|\\s]+("+Z+")[,|\\s]+("+Z+")\\s*\\)?",W={CSS_UNIT:new RegExp(Z),rgb:new RegExp("rgb"+Lt),rgba:new RegExp("rgba"+$t),hsl:new RegExp("hsl"+Lt),hsla:new RegExp("hsla"+$t),hsv:new RegExp("hsv"+Lt),hsva:new RegExp("hsva"+$t),cmyk:new RegExp("cmyk"+$t),hex3:/^#?([0-9a-fA-F]{1})([0-9a-fA-F]{1})([0-9a-fA-F]{1})$/,hex6:/^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/,hex4:/^#?([0-9a-fA-F]{1})([0-9a-fA-F]{1})([0-9a-fA-F]{1})([0-9a-fA-F]{1})$/,hex8:/^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/};function Ve(t){if(t=t.trim().toLowerCase(),t.length===0)return!1;let e=!1;if(ut[t])t=ut[t],e=!0;else if(t==="transparent")return{r:0,g:0,b:0,a:0,format:"name"};let i=W.rgb.exec(t);return i?{r:i[1],g:i[2],b:i[3]}:(i=W.rgba.exec(t),i?{r:i[1],g:i[2],b:i[3],a:i[4]}:(i=W.hsl.exec(t),i?{h:i[1],s:i[2],l:i[3]}:(i=W.hsla.exec(t),i?{h:i[1],s:i[2],l:i[3],a:i[4]}:(i=W.hsv.exec(t),i?{h:i[1],s:i[2],v:i[3]}:(i=W.hsva.exec(t),i?{h:i[1],s:i[2],v:i[3],a:i[4]}:(i=W.cmyk.exec(t),i?{c:i[1],m:i[2],y:i[3],k:i[4]}:(i=W.hex8.exec(t),i?{r:B(i[1]),g:B(i[2]),b:B(i[3]),a:Mt(i[4]),format:e?"name":"hex8"}:(i=W.hex6.exec(t),i?{r:B(i[1]),g:B(i[2]),b:B(i[3]),format:e?"name":"hex"}:(i=W.hex4.exec(t),i?{r:B(i[1]+i[1]),g:B(i[2]+i[2]),b:B(i[3]+i[3]),a:Mt(i[4]+i[4]),format:e?"name":"hex8"}:(i=W.hex3.exec(t),i?{r:B(i[1]+i[1]),g:B(i[2]+i[2]),b:B(i[3]+i[3]),format:e?"name":"hex"}:!1))))))))))}function N(t){return typeof t=="number"?!Number.isNaN(t):W.CSS_UNIT.test(t)}var dt=class t{constructor(e="",i={}){if(e instanceof t)return e;typeof e=="number"&&(e=re(e)),this.originalInput=e;let r=oe(e);this.originalInput=e,this.r=r.r,this.g=r.g,this.b=r.b,this.a=r.a,this.roundA=Math.round(100*this.a)/100,this.format=i.format??r.format,this.gradientType=i.gradientType,this.r<1&&(this.r=Math.round(this.r)),this.g<1&&(this.g=Math.round(this.g)),this.b<1&&(this.b=Math.round(this.b)),this.isValid=r.ok}isDark(){return this.getBrightness()<128}isLight(){return!this.isDark()}getBrightness(){let e=this.toRgb();return(e.r*299+e.g*587+e.b*114)/1e3}getLuminance(){let e=this.toRgb(),i,r,a,n=e.r/255,l=e.g/255,h=e.b/255;return n<=.03928?i=n/12.92:i=Math.pow((n+.055)/1.055,2.4),l<=.03928?r=l/12.92:r=Math.pow((l+.055)/1.055,2.4),h<=.03928?a=h/12.92:a=Math.pow((h+.055)/1.055,2.4),.2126*i+.7152*r+.0722*a}getAlpha(){return this.a}setAlpha(e){return this.a=Ct(e),this.roundA=Math.round(100*this.a)/100,this}isMonochrome(){let{s:e}=this.toHsl();return e===0}toHsv(){let e=At(this.r,this.g,this.b);return{h:e.h*360,s:e.s,v:e.v,a:this.a}}toHsvString(){let e=At(this.r,this.g,this.b),i=Math.round(e.h*360),r=Math.round(e.s*100),a=Math.round(e.v*100);return this.a===1?`hsv(${i}, ${r}%, ${a}%)`:`hsva(${i}, ${r}%, ${a}%, ${this.roundA})`}toHsl(){let e=Dt(this.r,this.g,this.b);return{h:e.h*360,s:e.s,l:e.l,a:this.a}}toHslString(){let e=Dt(this.r,this.g,this.b),i=Math.round(e.h*360),r=Math.round(e.s*100),a=Math.round(e.l*100);return this.a===1?`hsl(${i}, ${r}%, ${a}%)`:`hsla(${i}, ${r}%, ${a}%, ${this.roundA})`}toHex(e=!1){return Tt(this.r,this.g,this.b,e)}toHexString(e=!1){return"#"+this.toHex(e)}toHex8(e=!1){return ee(this.r,this.g,this.b,this.a,e)}toHex8String(e=!1){return"#"+this.toHex8(e)}toHexShortString(e=!1){return this.a===1?this.toHexString(e):this.toHex8String(e)}toRgb(){return{r:Math.round(this.r),g:Math.round(this.g),b:Math.round(this.b),a:this.a}}toRgbString(){let e=Math.round(this.r),i=Math.round(this.g),r=Math.round(this.b);return this.a===1?`rgb(${e}, ${i}, ${r})`:`rgba(${e}, ${i}, ${r}, ${this.roundA})`}toPercentageRgb(){let e=i=>`${Math.round(R(i,255)*100)}%`;return{r:e(this.r),g:e(this.g),b:e(this.b),a:this.a}}toPercentageRgbString(){let e=i=>Math.round(R(i,255)*100);return this.a===1?`rgb(${e(this.r)}%, ${e(this.g)}%, ${e(this.b)}%)`:`rgba(${e(this.r)}%, ${e(this.g)}%, ${e(this.b)}%, ${this.roundA})`}toCmyk(){return{...Rt(this.r,this.g,this.b)}}toCmykString(){let{c:e,m:i,y:r,k:a}=Rt(this.r,this.g,this.b);return`cmyk(${e}, ${i}, ${r}, ${a})`}toName(){if(this.a===0)return"transparent";if(this.a<1)return!1;let e="#"+Tt(this.r,this.g,this.b,!1);for(let[i,r]of Object.entries(ut))if(e===r)return i;return!1}toString(e){let i=!!e;e=e??this.format;let r=!1,a=this.a<1&&this.a>=0;return!i&&a&&(e.startsWith("hex")||e==="name")?e==="name"&&this.a===0?this.toName():this.toRgbString():(e==="rgb"&&(r=this.toRgbString()),e==="prgb"&&(r=this.toPercentageRgbString()),(e==="hex"||e==="hex6")&&(r=this.toHexString()),e==="hex3"&&(r=this.toHexString(!0)),e==="hex4"&&(r=this.toHex8String(!0)),e==="hex8"&&(r=this.toHex8String()),e==="name"&&(r=this.toName()),e==="hsl"&&(r=this.toHslString()),e==="hsv"&&(r=this.toHsvString()),e==="cmyk"&&(r=this.toCmykString()),r||this.toHexString())}toNumber(){return(Math.round(this.r)<<16)+(Math.round(this.g)<<8)+Math.round(this.b)}clone(){return new t(this.toString())}lighten(e=10){let i=this.toHsl();return i.l+=e/100,i.l=lt(i.l),new t(i)}brighten(e=10){let i=this.toRgb();return i.r=Math.max(0,Math.min(255,i.r-Math.round(255*-(e/100)))),i.g=Math.max(0,Math.min(255,i.g-Math.round(255*-(e/100)))),i.b=Math.max(0,Math.min(255,i.b-Math.round(255*-(e/100)))),new t(i)}darken(e=10){let i=this.toHsl();return i.l-=e/100,i.l=lt(i.l),new t(i)}tint(e=10){return this.mix("white",e)}shade(e=10){return this.mix("black",e)}desaturate(e=10){let i=this.toHsl();return i.s-=e/100,i.s=lt(i.s),new t(i)}saturate(e=10){let i=this.toHsl();return i.s+=e/100,i.s=lt(i.s),new t(i)}greyscale(){return this.desaturate(100)}spin(e){let i=this.toHsl(),r=(i.h+e)%360;return i.h=r<0?360+r:r,new t(i)}mix(e,i=50){let r=this.toRgb(),a=new t(e).toRgb(),n=i/100,l={r:(a.r-r.r)*n+r.r,g:(a.g-r.g)*n+r.g,b:(a.b-r.b)*n+r.b,a:(a.a-r.a)*n+r.a};return new t(l)}analogous(e=6,i=30){let r=this.toHsl(),a=360/i,n=[this];for(r.h=(r.h-(a*e>>1)+720)%360;--e;)r.h=(r.h+a)%360,n.push(new t(r));return n}complement(){let e=this.toHsl();return e.h=(e.h+180)%360,new t(e)}monochromatic(e=6){let i=this.toHsv(),{h:r}=i,{s:a}=i,{v:n}=i,l=[],h=1/e;for(;e--;)l.push(new t({h:r,s:a,v:n})),n=(n+h)%1;return l}splitcomplement(){let e=this.toHsl(),{h:i}=e;return[this,new t({h:(i+72)%360,s:e.s,l:e.l}),new t({h:(i+216)%360,s:e.s,l:e.l})]}onBackground(e){let i=this.toRgb(),r=new t(e).toRgb(),a=i.a+r.a*(1-i.a);return new t({r:(i.r*i.a+r.r*r.a*(1-i.a))/a,g:(i.g*i.a+r.g*r.a*(1-i.a))/a,b:(i.b*i.a+r.b*r.a*(1-i.a))/a,a})}triad(){return this.polyad(3)}tetrad(){return this.polyad(4)}polyad(e){let i=this.toHsl(),{h:r}=i,a=[this],n=360/e;for(let l=1;l<e;l++)a.push(new t({h:(r+l*n)%360,s:i.s,l:i.l}));return a}equals(e){let i=new t(e);return this.format==="cmyk"||i.format==="cmyk"?this.toCmykString()===i.toCmykString():this.toRgbString()===i.toRgbString()}};/**
 * @license
 * Copyright 2018 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var ae="important",_e=" !"+ae,M=yt(class extends xt{constructor(t){if(super(t),t.type!==wt.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,i)=>{let r=t[i];return r==null?e:e+`${i=i.includes("-")?i:i.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${r};`},"")}update(t,[e]){let{style:i}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let r of this.ft)e[r]==null&&(this.ft.delete(r),r.includes("-")?i.removeProperty(r):i[r]=null);for(let r in e){let a=e[r];if(a!=null){this.ft.add(r);let n=typeof a=="string"&&a.endsWith(_e);r.includes("-")||n?i.setProperty(r,n?a.slice(0,-11):a,n?ae:""):i[r]=a}}return mt}});/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var c=class extends z{constructor(){super(),this.hasSlotController=new F(this,"hint","label"),this.isSafeValue=!1,this.localize=new _(this),this.hasFocus=!1,this.isDraggingGridHandle=!1,this.inputValue="",this.hue=0,this.isEmpty=!0,this.saturation=100,this.brightness=100,this.alpha=100,this._value=null,this.defaultValue=this.getAttribute("value")||null,this.withLabel=!1,this.withHint=!1,this.hasEyeDropper=!1,this.label="",this.hint="",this.format="hex",this.size="m",this.placement="bottom-start",this.withoutFormatToggle=!1,this.name=null,this.disabled=!1,this.open=!1,this.opacity=!1,this.uppercase=!1,this.swatches="",this.required=!1,this.handleFocusIn=()=>{this.hasFocus=!0},this.handleFocusOut=()=>{this.hasFocus=!1},this.reportValidityAfterShow=()=>{this.removeEventListener("invalid",this.emitInvalid),this.reportValidity(),this.addEventListener("invalid",this.emitInvalid)},this.handleKeyDown=e=>{this.open&&e.key==="Escape"&&st(this)&&(e.stopPropagation(),this.hide(),this.focus())},this.handleDocumentKeyDown=e=>{if(e.key==="Escape"&&this.open&&st(this)){e.stopPropagation(),this.focus(),this.hide();return}e.key==="Tab"&&setTimeout(()=>{let i=this.getRootNode()instanceof ShadowRoot?document.activeElement?.shadowRoot?.activeElement:document.activeElement;(!this||i?.closest(this.tagName.toLowerCase())!==this)&&this.hide()})},this.handleDocumentMouseDown=e=>{let r=e.composedPath().some(a=>a instanceof Element&&(a.closest(".color-picker")||a===this.trigger));this&&!r&&this.hide()},this.addEventListener("focusin",this.handleFocusIn),this.addEventListener("focusout",this.handleFocusOut),this.opacity=this.hasAttribute("opacity"),this.uppercase=this.hasAttribute("uppercase");let t=this.getAttribute("format");(t==="rgb"||t==="hsl"||t==="hsv")&&(this.format=t),this.handleValueChange("",this.value||"")}static get validators(){let t=[rt()];return[...super.validators,...t]}get validationTarget(){return this.popup?.active?this.input:this.trigger}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(t){this._value!==t&&(this.valueHasChanged=!0,this._value=t)}handleSizeChange(){D(this.localName,this.size)}updateFormValue(t){if(t==null){this.setValue("",null);return}super.updateFormValue(t)}handleCopy(){this.input.select(),document.execCommand("copy"),this.previewButton.focus(),this.previewButton.classList.add("preview-color-copied"),this.previewButton.addEventListener("animationend",()=>{this.previewButton.classList.remove("preview-color-copied")})}handleFormatToggle(){let t=["hex","rgb","hsl","hsv"],e=(t.indexOf(this.format)+1)%t.length;this.format=t[e],this.setColor(this.value||""),this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))})}handleAlphaDrag(t){let e=this.shadowRoot.querySelector(".slider.alpha"),i=e.querySelector(".slider-handle"),{width:r}=e.getBoundingClientRect(),a=this.value,n=this.value;i.focus(),t.preventDefault(),ot(e,{onMove:l=>{this.alpha=S(l/r*100,0,100),this.syncValues(),this.value!==n&&(n=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))}))},onStop:()=>{this.value!==a&&(a=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))},initialEvent:t})}handleHueDrag(t){let e=this.shadowRoot.querySelector(".slider.hue"),i=e.querySelector(".slider-handle"),{width:r}=e.getBoundingClientRect(),a=this.value,n=this.value;i.focus(),t.preventDefault(),ot(e,{onMove:l=>{this.hue=S(l/r*360,0,360),this.syncValues(),this.value!==n&&(n=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input"))}))},onStop:()=>{this.value!==a&&(a=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))},initialEvent:t})}handleGridDrag(t){let e=this.shadowRoot.querySelector(".grid"),i=e.querySelector(".grid-handle"),{width:r,height:a}=e.getBoundingClientRect(),n=this.value,l=this.value;i.focus(),t.preventDefault(),this.isDraggingGridHandle=!0,ot(e,{onMove:(h,u)=>{this.saturation=S(h/r*100,0,100),this.brightness=S(100-u/a*100,0,100),this.syncValues(),this.value!==l&&(l=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))}))},onStop:()=>{this.isDraggingGridHandle=!1,this.value!==n&&(n=this.value,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))},initialEvent:t})}handleAlphaKeyDown(t){let e=t.shiftKey?10:1,i=this.value;t.key==="ArrowLeft"&&(t.preventDefault(),this.alpha=S(this.alpha-e,0,100),this.syncValues()),t.key==="ArrowRight"&&(t.preventDefault(),this.alpha=S(this.alpha+e,0,100),this.syncValues()),t.key==="Home"&&(t.preventDefault(),this.alpha=0,this.syncValues()),t.key==="End"&&(t.preventDefault(),this.alpha=100,this.syncValues()),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleHueKeyDown(t){let e=t.shiftKey?10:1,i=this.value;t.key==="ArrowLeft"&&(t.preventDefault(),this.hue=S(this.hue-e,0,360),this.syncValues()),t.key==="ArrowRight"&&(t.preventDefault(),this.hue=S(this.hue+e,0,360),this.syncValues()),t.key==="Home"&&(t.preventDefault(),this.hue=0,this.syncValues()),t.key==="End"&&(t.preventDefault(),this.hue=360,this.syncValues()),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleGridKeyDown(t){let e=t.shiftKey?10:1,i=this.value;t.key==="ArrowLeft"&&(t.preventDefault(),this.saturation=S(this.saturation-e,0,100),this.syncValues()),t.key==="ArrowRight"&&(t.preventDefault(),this.saturation=S(this.saturation+e,0,100),this.syncValues()),t.key==="ArrowUp"&&(t.preventDefault(),this.brightness=S(this.brightness+e,0,100),this.syncValues()),t.key==="ArrowDown"&&(t.preventDefault(),this.brightness=S(this.brightness-e,0,100),this.syncValues()),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleInputChange(t){let e=t.target,i=this.value;t.stopPropagation(),this.input.value?(this.setColor(e.value),e.value=this.value||""):this.value="",this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleInputInput(t){this.updateValidity(),t.stopPropagation()}handleInputKeyDown(t){if(t.key==="Enter"){let e=this.value;this.input.value?(this.setColor(this.input.value),this.input.value=this.value,this.value!==e&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),setTimeout(()=>this.input.select())):this.hue=0}}handleTouchMove(t){t.preventDefault()}parseColor(t){if(!t||t.trim()==="")return null;let e=new dt(t);if(!e.isValid)return null;let i=e.toHsl(),r=e.toRgb(),a=e.toHsv();if(!r||r.r==null||r.g==null||r.b==null)return null;let n={h:i.h||0,s:(i.s||0)*100,l:(i.l||0)*100,a:i.a||0},l=e.toHexString(),h=e.toHex8String(),u={h:a.h||0,s:(a.s||0)*100,v:(a.v||0)*100,a:a.a||0};return{hsl:{h:n.h,s:n.s,l:n.l,string:this.setLetterCase(`hsl(${Math.round(n.h)}, ${Math.round(n.s)}%, ${Math.round(n.l)}%)`)},hsla:{h:n.h,s:n.s,l:n.l,a:n.a,string:this.setLetterCase(`hsla(${Math.round(n.h)}, ${Math.round(n.s)}%, ${Math.round(n.l)}%, ${n.a.toFixed(2).toString()})`)},hsv:{h:u.h,s:u.s,v:u.v,string:this.setLetterCase(`hsv(${Math.round(u.h)}, ${Math.round(u.s)}%, ${Math.round(u.v)}%)`)},hsva:{h:u.h,s:u.s,v:u.v,a:u.a,string:this.setLetterCase(`hsva(${Math.round(u.h)}, ${Math.round(u.s)}%, ${Math.round(u.v)}%, ${u.a.toFixed(2).toString()})`)},rgb:{r:r.r,g:r.g,b:r.b,string:this.setLetterCase(`rgb(${Math.round(r.r)}, ${Math.round(r.g)}, ${Math.round(r.b)})`)},rgba:{r:r.r,g:r.g,b:r.b,a:r.a||0,string:this.setLetterCase(`rgba(${Math.round(r.r)}, ${Math.round(r.g)}, ${Math.round(r.b)}, ${(r.a||0).toFixed(2).toString()})`)},hex:this.setLetterCase(l),hexa:this.setLetterCase(h)}}setColor(t){let e=this.parseColor(t);return e===null?!1:(this.hue=e.hsva.h,this.saturation=e.hsva.s,this.brightness=e.hsva.v,this.alpha=this.opacity?e.hsva.a*100:100,this.syncValues(),!0)}setLetterCase(t){return typeof t!="string"?"":this.uppercase?t.toUpperCase():t.toLowerCase()}async syncValues(){let t=this.parseColor(`hsva(${this.hue}, ${this.saturation}%, ${this.brightness}%, ${this.alpha/100})`);t!==null&&(this.format==="hsl"?this.inputValue=this.opacity?t.hsla.string:t.hsl.string:this.format==="rgb"?this.inputValue=this.opacity?t.rgba.string:t.rgb.string:this.format==="hsv"?this.inputValue=this.opacity?t.hsva.string:t.hsv.string:this.inputValue=this.opacity?t.hexa:t.hex,this.isSafeValue=!0,this.value=this.inputValue,await this.updateComplete,this.isSafeValue=!1)}handleAfterHide(){this.previewButton.classList.remove("preview-color-copied"),this.updateValidity()}handleAfterShow(){this.updateValidity()}handleEyeDropper(){if(!this.hasEyeDropper)return;new EyeDropper().open().then(e=>{let i=this.value;this.setColor(e.sRGBHex),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}).catch(()=>{})}selectSwatch(t){let e=this.value;this.disabled||(this.setColor(t),this.value!==e&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))}getHexString(t,e,i,r=100){let a=new dt(`hsva(${t}, ${e}%, ${i}%, ${r/100})`);return a.isValid?a.toHex8String():""}stopNestedEventPropagation(t){t.stopImmediatePropagation()}handleFormatChange(){this.syncValues()}handleOpacityChange(){this.alpha=100}willUpdate(t){(t.has("value")||t.has("defaultValue"))&&this.handleValueChange(t.get("value")||"",this.value||""),super.willUpdate(t)}handleValueChange(t,e){if(this.isEmpty=!e,e||(this.hue=0,this.saturation=0,this.brightness=100,this.alpha=100),!this.isSafeValue){let i=this.parseColor(e);i!==null?(this.inputValue=this.value||"",this.hue=i.hsva.h,this.saturation=i.hsva.s,this.brightness=i.hsva.v,this.alpha=this.opacity?i.hsva.a*100:100,this.syncValues()):this.inputValue=t??""}this.requestUpdate()}focus(t){this.trigger.focus(t)}blur(){let t=this.trigger;this.hasFocus&&(t.focus({preventScroll:!0}),t.blur()),this.popup?.active&&this.hide()}getFormattedValue(t="hex"){let e=this.parseColor(`hsva(${this.hue}, ${this.saturation}%, ${this.brightness}%, ${this.alpha/100})`);if(e===null)return"";switch(t){case"hex":return e.hex;case"hexa":return e.hexa;case"rgb":return e.rgb.string;case"rgba":return e.rgba.string;case"hsl":return e.hsl.string;case"hsla":return e.hsla.string;case"hsv":return e.hsv.string;case"hsva":return e.hsva.string;default:return""}}reportValidity(){return!this.validity.valid&&!this.open?(this.addEventListener("wa-after-show",this.reportValidityAfterShow,{once:!0}),this.show(),this.disabled||this.dispatchEvent(new gt),!1):super.reportValidity()}formResetCallback(){this.value=this.defaultValue,super.formResetCallback()}firstUpdated(t){super.firstUpdated(t),this.hasEyeDropper="EyeDropper"in window}handleTriggerClick(){this.open?this.hide():(this.show(),this.focus())}async handleTriggerKeyDown(t){if([" ","Enter"].includes(t.key)){t.preventDefault(),this.handleTriggerClick();return}}handleTriggerKeyUp(t){t.key===" "&&t.preventDefault()}updateAccessibleTrigger(){let t=this.trigger;t&&(t.setAttribute("aria-haspopup","true"),t.setAttribute("aria-expanded",this.open?"true":"false"))}async show(){if(!this.open)return this.open=!0,tt(this,"wa-after-show")}async hide(){if(this.open)return this.open=!1,tt(this,"wa-after-hide")}addOpenListeners(){this.base.addEventListener("keydown",this.handleKeyDown),document.addEventListener("keydown",this.handleDocumentKeyDown),document.addEventListener("mousedown",this.handleDocumentMouseDown),bt(this)}removeOpenListeners(){this.base&&this.base.removeEventListener("keydown",this.handleKeyDown),document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("mousedown",this.handleDocumentMouseDown),vt(this)}async handleOpenChange(){if(this.disabled){this.open=!1;return}this.updateAccessibleTrigger(),this.open?(this.dispatchEvent(new CustomEvent("wa-show")),this.addOpenListeners(),await this.updateComplete,this.base.hidden=!1,this.popup.active=!0,await et(this.popup.popup,"show-with-scale"),this.dispatchEvent(new CustomEvent("wa-after-show"))):(this.dispatchEvent(new CustomEvent("wa-hide")),this.removeOpenListeners(),await et(this.popup.popup,"hide-with-scale"),this.base.hidden=!0,this.popup.active=!1,this.dispatchEvent(new CustomEvent("wa-after-hide")))}render(){let t=this.isEmpty,e=this.hasSlotController.test("label","withLabel"),i=this.hasSlotController.test("hint","withHint"),r=this.label?!0:!!e,a=this.hint?!0:!!i,n=this.saturation,l=100-this.brightness,h=Array.isArray(this.swatches)?this.swatches.map(p=>typeof p=="string"?{color:p,label:p}:p):this.swatches.split(";").filter(p=>p.trim()!=="").map(p=>({color:p.trim(),label:p.trim()})),u=d`
      <div
        part="base color-picker"
        class=${k({"color-picker":!0})}
        aria-disabled=${this.disabled?"true":"false"}
        tabindex="-1"
      >
        <div
          part="grid"
          class="grid"
          style=${M({backgroundColor:this.getHexString(this.hue,100,100)})}
          @pointerdown=${this.handleGridDrag}
          @touchmove=${this.handleTouchMove}
        >
          <span
            part="grid-handle"
            class=${k({"grid-handle":!0,"grid-handle-dragging":this.isDraggingGridHandle})}
            style=${M({top:`${l}%`,left:`${n}%`,backgroundColor:this.getHexString(this.hue,this.saturation,this.brightness,this.alpha)})}
            role="application"
            aria-label="HSV"
            tabindex=${f(this.disabled?void 0:"0")}
            @keydown=${this.handleGridKeyDown}
          ></span>
        </div>

        <div class="controls">
          <div class="sliders">
            <div
              part="slider hue-slider"
              class="hue slider"
              @pointerdown=${this.handleHueDrag}
              @touchmove=${this.handleTouchMove}
            >
              <span
                part="slider-handle hue-slider-handle"
                class="slider-handle"
                style=${M({left:`${this.hue===0?0:100/(360/this.hue)}%`,backgroundColor:this.getHexString(this.hue,100,100)})}
                role="slider"
                aria-label="hue"
                aria-orientation="horizontal"
                aria-valuemin="0"
                aria-valuemax="360"
                aria-valuenow=${`${Math.round(this.hue)}`}
                tabindex=${f(this.disabled?void 0:"0")}
                @keydown=${this.handleHueKeyDown}
              ></span>
            </div>

            ${this.opacity?d`
                  <div
                    part="slider opacity-slider"
                    class="alpha slider transparent-bg"
                    @pointerdown="${this.handleAlphaDrag}"
                    @touchmove=${this.handleTouchMove}
                  >
                    <div
                      class="alpha-gradient"
                      style=${M({backgroundImage:`linear-gradient(
                          to right,
                          ${this.getHexString(this.hue,this.saturation,this.brightness,0)} 0%,
                          ${this.getHexString(this.hue,this.saturation,this.brightness,100)} 100%
                        )`})}
                    ></div>
                    <span
                      part="slider-handle opacity-slider-handle"
                      class="slider-handle"
                      style=${M({left:`${this.alpha}%`,backgroundColor:this.getHexString(this.hue,this.saturation,this.brightness,this.alpha)})}
                      role="slider"
                      aria-label="alpha"
                      aria-orientation="horizontal"
                      aria-valuemin="0"
                      aria-valuemax="100"
                      aria-valuenow=${Math.round(this.alpha)}
                      tabindex=${f(this.disabled?void 0:"0")}
                      @keydown=${this.handleAlphaKeyDown}
                    ></span>
                  </div>
                `:""}
          </div>

          <button
            type="button"
            part="preview"
            class="preview transparent-bg"
            aria-label=${this.localize.term("copy")}
            style=${M({"--preview-color":this.getHexString(this.hue,this.saturation,this.brightness,this.alpha)})}
            @click=${this.handleCopy}
          ></button>
        </div>

        <div class="user-input" aria-live="polite">
          <wa-input
            part="input"
            type="text"
            name=${this.name}
            size="s"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            spellcheck="false"
            .value=${t?"":this.inputValue}
            value=${t?"":this.inputValue}
            ?required=${this.required}
            ?disabled=${this.disabled}
            aria-label=${this.localize.term("currentValue")}
            @keydown=${this.handleInputKeyDown}
            @change=${this.handleInputChange}
            @input=${this.handleInputInput}
            @blur=${this.stopNestedEventPropagation}
            @focus=${this.stopNestedEventPropagation}
          ></wa-input>

          <wa-button-group>
            ${this.withoutFormatToggle?"":d`
                  <wa-button
                    part="format-button"
                    size="s"
                    appearance="outlined"
                    aria-label=${this.localize.term("toggleColorFormat")}
                    exportparts="
                      base:format-button__base,
                      start:format-button__start,
                      label:format-button__label,
                      end:format-button__end,
                      caret:format-button__caret
                    "
                    @click=${this.handleFormatToggle}
                    @blur=${this.stopNestedEventPropagation}
                    @focus=${this.stopNestedEventPropagation}
                  >
                    ${this.setLetterCase(this.format)}
                  </wa-button>
                `}
            ${this.hasEyeDropper?d`
                  <wa-button
                    part="eyedropper-button"
                    size="s"
                    appearance="outlined"
                    exportparts="
                      base:eyedropper-button__base,
                      start:eyedropper-button__start,
                      label:eyedropper-button__label,
                      end:eyedropper-button__end,
                      caret:eyedropper-button__caret
                    "
                    @click=${this.handleEyeDropper}
                    @blur=${this.stopNestedEventPropagation}
                    @focus=${this.stopNestedEventPropagation}
                  >
                    <wa-icon
                      library="system"
                      name="eyedropper"
                      variant="solid"
                      label=${this.localize.term("selectAColorFromTheScreen")}
                    ></wa-icon>
                  </wa-button>
                `:""}
          </wa-button-group>
        </div>

        ${h.length>0?d`
              <div part="swatches" class="swatches">
                ${h.map(p=>{let V=this.parseColor(p.color);return V?d`
                    <div
                      part="swatch"
                      class="swatch transparent-bg"
                      tabindex=${f(this.disabled?void 0:"0")}
                      role="button"
                      aria-label=${p.label}
                      @click=${()=>this.selectSwatch(p.color)}
                      @keydown=${O=>{(O.key==="Enter"||O.key===" ")&&(O.preventDefault(),this.selectSwatch(p.color))}}
                    >
                      <div class="swatch-color" style=${M({backgroundColor:V.hexa})}></div>
                    </div>
                  `:""})}
              </div>
            `:""}
      </div>
    `;return d`
      <div
        class=${k({container:!0,"form-control":!0,"form-control-has-label":r})}
        part="trigger-container form-control"
      >
        <div
          part="form-control-label"
          class=${k({label:!0,"has-label":r})}
          id="form-control-label"
        >
          <slot name="label">${this.label}</slot>
        </div>

        <button
          id="trigger"
          part="trigger form-control-input"
          class=${k({trigger:!0,"trigger-empty":t,"transparent-bg":!0,"form-control-input":!0})}
          style=${M({color:this.getHexString(this.hue,this.saturation,this.brightness,this.alpha)})}
          type="button"
          aria-labelledby="form-control-label"
          aria-describedby="hint"
          .disabled=${this.disabled}
          @click=${this.handleTriggerClick}
          @keydown=${this.handleTriggerKeyDown}
          @keyup=${this.handleTriggerKeyUp}
        ></button>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${k({"has-slotted":a})}
          >${this.hint}</slot
        >
      </div>

      <wa-popup
        class="color-popup"
        anchor="trigger"
        placement=${this.placement}
        distance="0"
        skidding="0"
        flip
        flip-fallback-strategy="best-fit"
        shift
        shift-padding="10"
        aria-disabled=${this.disabled?"true":"false"}
        @wa-after-show=${this.handleAfterShow}
        @wa-after-hide=${this.handleAfterHide}
      >
        ${u}
      </wa-popup>
    `}};c.css=[ft,A,H,Zt];c.shadowRootOptions={...z.shadowRootOptions,delegatesFocus:!0};o([m('[part~="base"]')],c.prototype,"base",2);o([m('[part~="input"]')],c.prototype,"input",2);o([m('[part~="form-control-label"]')],c.prototype,"triggerLabel",2);o([m('[part~="form-control-input"]')],c.prototype,"triggerButton",2);o([m(".color-popup")],c.prototype,"popup",2);o([m('[part~="preview"]')],c.prototype,"previewButton",2);o([m('[part~="trigger"]')],c.prototype,"trigger",2);o([y()],c.prototype,"hasFocus",2);o([y()],c.prototype,"isDraggingGridHandle",2);o([y()],c.prototype,"inputValue",2);o([y()],c.prototype,"hue",2);o([y()],c.prototype,"isEmpty",2);o([y()],c.prototype,"saturation",2);o([y()],c.prototype,"brightness",2);o([y()],c.prototype,"alpha",2);o([y()],c.prototype,"value",1);o([s({attribute:"value",reflect:!0})],c.prototype,"defaultValue",2);o([s({attribute:"with-label",reflect:!0,type:Boolean})],c.prototype,"withLabel",2);o([s({attribute:"with-hint",reflect:!0,type:Boolean})],c.prototype,"withHint",2);o([y()],c.prototype,"hasEyeDropper",2);o([s()],c.prototype,"label",2);o([s({attribute:"hint"})],c.prototype,"hint",2);o([s()],c.prototype,"format",2);o([s({reflect:!0})],c.prototype,"size",2);o([v("size")],c.prototype,"handleSizeChange",1);o([s({reflect:!0})],c.prototype,"placement",2);o([s({attribute:"without-format-toggle",type:Boolean})],c.prototype,"withoutFormatToggle",2);o([s({reflect:!0})],c.prototype,"name",2);o([s({type:Boolean})],c.prototype,"disabled",2);o([s({type:Boolean,reflect:!0})],c.prototype,"open",2);o([s({type:Boolean})],c.prototype,"opacity",2);o([s({type:Boolean})],c.prototype,"uppercase",2);o([s()],c.prototype,"swatches",2);o([s({type:Boolean,reflect:!0})],c.prototype,"required",2);o([Pt({passive:!1})],c.prototype,"handleTouchMove",1);o([v("format",{waitUntilFirstUpdate:!0})],c.prototype,"handleFormatChange",1);o([v("opacity",{waitUntilFirstUpdate:!0})],c.prototype,"handleOpacityChange",1);o([v("value")],c.prototype,"handleValueChange",1);o([v("open",{waitUntilFirstUpdate:!0})],c.prototype,"handleOpenChange",1);c=o([E("wa-color-picker")],c);c.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var se=C`
  :host {
    display: inline-flex;
  }

  .button-group {
    display: flex;
    position: relative;
    isolation: isolate;
    flex-wrap: wrap;

    @media (hover: hover) {
      > :hover,
      &::slotted(:hover) {
        z-index: 1;
      }
    }

    /* Focus and checked are always on top */
    > :focus,
    &::slotted(:focus),
    > [aria-checked='true'],
    &::slotted([aria-checked='true']),
    > [checked],
    &::slotted([checked]) {
      z-index: 2 !important;
    }

    :host([orientation='horizontal']) & {
      flex-direction: row;
    }

    :host([orientation='vertical']) & {
      flex-direction: column;
    }
  }

  /* Set custom properties to be inherited by slotted buttons */
  :host([orientation='horizontal']) {
    --_button-horizontal-indent: var(--wa-form-control-border-width);
    --_button-horizontal-indent-outlined: calc(var(--wa-form-control-border-width) * -1);

    ::slotted(:first-child) {
      --_button-horizontal-indent: 0;
      --_button-horizontal-indent-outlined: 0;
    }
  }

  :host([orientation='vertical']) {
    --_button-vertical-indent: var(--wa-form-control-border-width);
    --_button-vertical-indent-outlined: calc(var(--wa-form-control-border-width) * -1);

    ::slotted(:first-child) {
      --_button-vertical-indent: 0;
      --_button-vertical-indent-outlined: 0;
    }
  }

  /* All buttons that are not in front or at the end get their border radius removed */
  ::slotted(:not(:first-child):not(:last-child)) {
    --_button-start-start-radius: 0;
    --_button-start-end-radius: 0;
    --_button-end-start-radius: 0;
    --_button-end-end-radius: 0;
  }

  /* Remove leading and trailing buttons border radius individually */
  :host([orientation='horizontal']) {
    ::slotted(:first-child:not(:last-child)) {
      --_button-start-end-radius: 0;
      --_button-end-end-radius: 0;
    }

    ::slotted(:last-child:not(:first-child)) {
      --_button-start-start-radius: 0;
      --_button-end-start-radius: 0;
    }
  }

  :host([orientation='vertical']) {
    ::slotted(:first-child:not(:last-child)) {
      --_button-end-start-radius: 0;
      --_button-end-end-radius: 0;
    }

    ::slotted(:last-child:not(:first-child)) {
      --_button-start-start-radius: 0;
      --_button-start-end-radius: 0;
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var J=class extends j{constructor(){super(...arguments),this.disableRole=!1,this.hasOutlined=!1,this.label="",this.orientation="horizontal"}updated(t){super.updated(t),t.has("orientation")&&this.setAttribute("aria-orientation",this.orientation)}handleFocus(t){St(t.target)?.classList.add("button-focus")}handleBlur(t){St(t.target)?.classList.remove("button-focus")}handleMouseOver(t){St(t.target)?.classList.add("button-hover")}handleMouseOut(t){St(t.target)?.classList.remove("button-hover")}render(){return d`
      <slot
        part="base"
        class="button-group"
        role="${this.disableRole?"presentation":"group"}"
        aria-label=${this.label}
        aria-orientation=${this.orientation}
        @focusout=${this.handleBlur}
        @focusin=${this.handleFocus}
        @mouseover=${this.handleMouseOver}
        @mouseout=${this.handleMouseOut}
      ></slot>
    `}};J.css=[se];o([m("slot")],J.prototype,"defaultSlot",2);o([y()],J.prototype,"disableRole",2);o([y()],J.prototype,"hasOutlined",2);o([s()],J.prototype,"label",2);o([s({reflect:!0})],J.prototype,"orientation",2);J=o([E("wa-button-group")],J);function St(t){let e="wa-button, wa-radio-button";return t.closest(e)??t.querySelector(e)}/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ne=C`
  @layer wa-component {
    :host {
      display: inline-block;

      /* Workaround because Chrome doesn't like :host(:has()) below
       * https://issues.chromium.org/issues/40062355
       * Firefox doesn't like this nested rule, so both are needed */
      &:has(wa-badge) {
        position: relative;
      }
    }

    /* Apply relative positioning only when needed to position wa-badge
     * This avoids creating a new stacking context for every button */
    :host(:has(wa-badge)) {
      position: relative;
    }
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    user-select: none;
    -webkit-user-select: none;
    white-space: nowrap;
    vertical-align: middle;
    transition-property: background, border, box-shadow, color, opacity, transform;
    transition-duration: var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    transform-origin: center;
    cursor: pointer;
    padding: 0 var(--wa-form-control-padding-inline);
    font-family: inherit;
    font-size: inherit;
    font-weight: var(--wa-font-weight-action);
    height: var(--wa-form-control-height);
    width: 100%;

    background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));

    border-color: transparent;
    color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-form-control-border-radius));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-form-control-border-radius));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-form-control-border-radius));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-form-control-border-radius));
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
  }

  /* Hover and active transforms */
  .button:not(.disabled):not(.loading) {
    @media (hover: hover) {
      &:hover {
        transform: var(--wa-button-transform-hover);
      }
    }
    &:active {
      transform: var(--wa-button-transform-active);
    }

    @media (prefers-reduced-motion: reduce) {
      &:hover,
      &:active {
        transform: none;
      }
    }
  }

  /* Appearance modifiers */
  :host([appearance='plain']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled-outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='accent']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
        var(--wa-color-mix-active)
      );
    }
  }

  /* Focus states */
  .button:focus {
    outline: none;
  }

  .button:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled state */
  :host([disabled]) {
    opacity: 0.5;
    cursor: not-allowed;

    /* When disabled, prevent mouse events from bubbling up from children */
    .button {
      pointer-events: none;
    }
  }

  /* Keep it last so Safari doesn't stop parsing this block */
  .button::-moz-focus-inner {
    border: 0;
  }

  /* Icon buttons */
  .button.is-icon-button {
    outline-offset: 2px;
    width: var(--wa-form-control-height);
    aspect-ratio: 1;
  }

  /* Icon buttons with a caret need to grow to fit both the icon and the caret */
  .button.is-icon-button.caret {
    width: auto;
    aspect-ratio: auto;
    min-width: var(--wa-form-control-height);
  }

  /* Pill modifier */
  :host([pill]) .button {
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-border-radius-pill));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-border-radius-pill));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-border-radius-pill));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-border-radius-pill));
  }

  /*
   * Label
   */

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    pointer-events: none;
  }

  .label {
    display: inline-block;
  }

  .is-icon-button .label {
    display: flex;
    justify-content: center;
  }

  .label::slotted(wa-icon) {
    align-self: center;
  }

  /*
   * Caret modifier
   */

  wa-icon[part='caret'] {
    display: flex;
    align-self: center;
    align-items: center;

    &::part(svg) {
      width: 0.875em;
      height: 0.875em;
    }

    .button:has(&) .end {
      display: none;
    }
  }

  /*
   * Loading modifier
   */

  .loading {
    position: relative;
    cursor: wait;

    .start,
    .label,
    .end,
    .caret {
      /* Hidden with opacity, not visibility, so the label stays in the accessibility tree */
      opacity: 0;

      /* Unlike visibility: hidden, opacity leaves the content clickable */
      pointer-events: none;
    }

    wa-spinner {
      --indicator-color: currentColor;
      --track-color: color-mix(in oklab, currentColor, transparent 90%);

      position: absolute;
      font-size: 1em;
      height: 1em;
      width: 1em;
      top: calc(50% - 0.5em);
      left: calc(50% - 0.5em);
    }
  }

  /*
   * Badges
   */

  .button ::slotted(wa-badge) {
    border-color: var(--wa-color-surface-default);
    position: absolute;
    inset-block-start: 0;
    inset-inline-end: 0;
    translate: 50% -50%;
    pointer-events: none;
  }

  :host(:dir(rtl)) ::slotted(wa-badge) {
    translate: -50% -50%;
  }

  /*
  * Button spacing
  */

  slot[name='start']::slotted(*) {
    margin-inline-end: 0.75em;
  }

  slot[name='end']::slotted(*),
  .button:not(.visually-hidden-label) [part='caret'] {
    margin-inline-start: 0.75em;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var Et=C`
  :where(:root),
  .wa-neutral,
  :host([variant='neutral']) {
    --wa-color-fill-loud: var(--wa-color-neutral-fill-loud);
    --wa-color-fill-normal: var(--wa-color-neutral-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-neutral-fill-quiet);
    --wa-color-border-loud: var(--wa-color-neutral-border-loud);
    --wa-color-border-normal: var(--wa-color-neutral-border-normal);
    --wa-color-border-quiet: var(--wa-color-neutral-border-quiet);
    --wa-color-on-loud: var(--wa-color-neutral-on-loud);
    --wa-color-on-normal: var(--wa-color-neutral-on-normal);
    --wa-color-on-quiet: var(--wa-color-neutral-on-quiet);
  }

  .wa-brand,
  :host([variant='brand']) {
    --wa-color-fill-loud: var(--wa-color-brand-fill-loud);
    --wa-color-fill-normal: var(--wa-color-brand-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-brand-fill-quiet);
    --wa-color-border-loud: var(--wa-color-brand-border-loud);
    --wa-color-border-normal: var(--wa-color-brand-border-normal);
    --wa-color-border-quiet: var(--wa-color-brand-border-quiet);
    --wa-color-on-loud: var(--wa-color-brand-on-loud);
    --wa-color-on-normal: var(--wa-color-brand-on-normal);
    --wa-color-on-quiet: var(--wa-color-brand-on-quiet);
  }

  .wa-success,
  :host([variant='success']) {
    --wa-color-fill-loud: var(--wa-color-success-fill-loud);
    --wa-color-fill-normal: var(--wa-color-success-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-success-fill-quiet);
    --wa-color-border-loud: var(--wa-color-success-border-loud);
    --wa-color-border-normal: var(--wa-color-success-border-normal);
    --wa-color-border-quiet: var(--wa-color-success-border-quiet);
    --wa-color-on-loud: var(--wa-color-success-on-loud);
    --wa-color-on-normal: var(--wa-color-success-on-normal);
    --wa-color-on-quiet: var(--wa-color-success-on-quiet);
  }

  .wa-warning,
  :host([variant='warning']) {
    --wa-color-fill-loud: var(--wa-color-warning-fill-loud);
    --wa-color-fill-normal: var(--wa-color-warning-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-warning-fill-quiet);
    --wa-color-border-loud: var(--wa-color-warning-border-loud);
    --wa-color-border-normal: var(--wa-color-warning-border-normal);
    --wa-color-border-quiet: var(--wa-color-warning-border-quiet);
    --wa-color-on-loud: var(--wa-color-warning-on-loud);
    --wa-color-on-normal: var(--wa-color-warning-on-normal);
    --wa-color-on-quiet: var(--wa-color-warning-on-quiet);
  }

  .wa-danger,
  :host([variant='danger']) {
    --wa-color-fill-loud: var(--wa-color-danger-fill-loud);
    --wa-color-fill-normal: var(--wa-color-danger-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-danger-fill-quiet);
    --wa-color-border-loud: var(--wa-color-danger-border-loud);
    --wa-color-border-normal: var(--wa-color-danger-border-normal);
    --wa-color-border-quiet: var(--wa-color-danger-border-quiet);
    --wa-color-on-loud: var(--wa-color-danger-on-loud);
    --wa-color-on-normal: var(--wa-color-danger-on-normal);
    --wa-color-on-quiet: var(--wa-color-danger-on-quiet);
  }
`;/**
 * @license
 * Copyright 2020 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var he=Symbol.for(""),De=t=>{if(t?.r===he)return t?._$litStatic$};var Ot=(t,...e)=>({_$litStatic$:e.reduce((i,r,a)=>i+(n=>{if(n._$litStatic$!==void 0)return n._$litStatic$;throw Error(`Value passed to 'literal' function must be a 'literal' result: ${n}. Use 'unsafeStatic' to pass non-literal values, but
            take care to ensure page security.`)})(r)+t[a+1],t[0]),r:he}),le=new Map,qt=t=>(e,...i)=>{let r=i.length,a,n,l=[],h=[],u,p=0,V=!1;for(;p<r;){for(u=e[p];p<r&&(n=i[p],(a=De(n))!==void 0);)u+=a+e[++p],V=!0;p!==r&&h.push(n),l.push(u),p++}if(p===r&&l.push(e[r]),V){let O=l.join("$$lit$$");(e=le.get(O))===void 0&&(l.raw=l,le.set(O,e=l)),i=h}return t(e,...i)},zt=qt(d),Ni=qt(Nt),Wi=qt(Wt);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var x=class extends z{constructor(){super(...arguments),this.assumeInteractionOn=["click"],this.hasSlotController=new F(this,"[default]","start","end"),this.localize=new _(this),this.invalid=!1,this.isIconButton=!1,this.title="",this.variant="neutral",this.appearance="accent",this.size="m",this.withCaret=!1,this.withStart=!1,this.withEnd=!1,this.disabled=!1,this.loading=!1,this.pill=!1,this.type="button"}static get validators(){return[...super.validators,X()]}handleSizeChange(){D(this.localName,this.size)}constructLightDOMButton(){let t=document.createElement("button");for(let e of this.attributes)e.name!=="style"&&t.setAttribute(e.name,e.value);return t.type=this.type,t.style.position="absolute !important",t.style.width="0 !important",t.style.height="0 !important",t.style.clipPath="inset(50%) !important",t.style.overflow="hidden !important",t.style.whiteSpace="nowrap !important",this.name&&(t.name=this.name),t.value=this.value||"",t}handleClick(t){if(this.disabled||this.loading){t.preventDefault(),t.stopImmediatePropagation();return}if(this.type!=="submit"&&this.type!=="reset"||!this.getForm())return;let i=this.constructLightDOMButton();this.parentElement?.append(i),i.click(),i.remove()}handleInvalid(){this.dispatchEvent(new gt)}handleLabelSlotChange(){let t=this.labelSlot.assignedNodes({flatten:!0}),e=!1,i=!1,r=!1,a=!1;[...t].forEach(n=>{if(n.nodeType===Node.ELEMENT_NODE){let l=n;l.localName==="wa-icon"?(i=!0,e||(e=l.label!==void 0)):a=!0}else n.nodeType===Node.TEXT_NODE&&(n.textContent?.trim()||"").length>0&&(r=!0)}),this.isIconButton=i&&!r&&!a,this.customStates.set("icon-button",this.isIconButton),this.isIconButton&&!e&&console.warn('Icon buttons must have a label for screen readers. Add <wa-icon label="..."> to remove this warning.',this)}isButton(){return!this.href}isLink(){return!!this.href}handleDisabledChange(){this.customStates.set("disabled",this.disabled),this.updateValidity()}handleHrefChange(){this.customStates.set("link",this.isLink())}handleLoadingChange(){this.customStates.set("loading",this.loading)}setValue(...t){}click(){this.button.click()}focus(t){this.button.focus(t)}blur(){this.button.blur()}render(){let t=this.isLink(),e=t?Ot`a`:Ot`button`;return zt`
      <${e}
        part="base button"
        class=${k({button:!0,caret:this.withCaret,disabled:this.disabled,loading:this.loading,rtl:this.localize.dir()==="rtl","has-label":this.hasSlotController.test("[default]"),"has-start":this.hasSlotController.test("start","withStart"),"has-end":this.hasSlotController.test("end","withEnd"),"is-icon-button":this.isIconButton})}
        ?disabled=${f(t?void 0:this.disabled)}
        type=${f(t?void 0:this.type)}
        title=${this.title}
        name=${f(t?void 0:this.name)}
        value=${f(t?void 0:this.value)}
        href=${f(t?this.href:void 0)}
        target=${f(t?this.target:void 0)}
        download=${f(t?this.download:void 0)}
        rel=${f(t&&this.rel?this.rel:void 0)}
        role=${f(t?void 0:"button")}
        aria-disabled=${f(t&&this.disabled?"true":void 0)}
        aria-busy=${this.loading?"true":"false"}
        tabindex=${this.disabled?"-1":"0"}
        @invalid=${this.isButton()?this.handleInvalid:null}
        @click=${this.handleClick}
      >
        <slot name="start" part="start" class="start"></slot>
        <slot part="label" class="label" @slotchange=${this.handleLabelSlotChange}></slot>
        <slot name="end" part="end" class="end"></slot>
        ${this.withCaret?zt`
                <wa-icon part="caret" class="caret" library="system" name="chevron-down" variant="solid"></wa-icon>
              `:""}
        ${this.loading?zt`<wa-spinner part="spinner"></wa-spinner>`:""}
      </${e}>
    `}};x.shadowRootOptions={...z.shadowRootOptions,delegatesFocus:!0};x.css=[ne,Et,A];o([m(".button")],x.prototype,"button",2);o([m("slot:not([name])")],x.prototype,"labelSlot",2);o([y()],x.prototype,"invalid",2);o([y()],x.prototype,"isIconButton",2);o([s()],x.prototype,"title",2);o([s({reflect:!0})],x.prototype,"variant",2);o([s({reflect:!0})],x.prototype,"appearance",2);o([s({reflect:!0})],x.prototype,"size",2);o([v("size")],x.prototype,"handleSizeChange",1);o([s({attribute:"with-caret",type:Boolean,reflect:!0})],x.prototype,"withCaret",2);o([s({attribute:"with-start",type:Boolean})],x.prototype,"withStart",2);o([s({attribute:"with-end",type:Boolean})],x.prototype,"withEnd",2);o([s({type:Boolean})],x.prototype,"disabled",2);o([s({type:Boolean,reflect:!0})],x.prototype,"loading",2);o([s({type:Boolean,reflect:!0})],x.prototype,"pill",2);o([s()],x.prototype,"type",2);o([s({reflect:!0})],x.prototype,"name",2);o([s({reflect:!0})],x.prototype,"value",2);o([s({reflect:!0})],x.prototype,"href",2);o([s()],x.prototype,"target",2);o([s()],x.prototype,"rel",2);o([s()],x.prototype,"download",2);o([s({attribute:"formaction"})],x.prototype,"formAction",2);o([s({attribute:"formenctype"})],x.prototype,"formEnctype",2);o([s({attribute:"formmethod"})],x.prototype,"formMethod",2);o([s({attribute:"formnovalidate",type:Boolean})],x.prototype,"formNoValidate",2);o([s({attribute:"formtarget"})],x.prototype,"formTarget",2);o([v("disabled",{waitUntilFirstUpdate:!0})],x.prototype,"handleDisabledChange",1);o([v("href")],x.prototype,"handleHrefChange",1);o([v("loading",{waitUntilFirstUpdate:!0})],x.prototype,"handleLoadingChange",1);x=o([E("wa-button")],x);x.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ue=C`
  :host {
    --track-width: 2px;
    --track-color: var(--wa-color-neutral-fill-normal);
    --indicator-color: var(--wa-color-brand-fill-loud);
    --speed: 2s;
    --size: 1em;

    /*
      Resizing a spinner element using anything but font-size will break the animation because the animation uses em
      units. Therefore, if a spinner is used in a flex container without \`flex: none\` applied, the spinner can
      grow/shrink and break the animation. The use of \`flex: none\` on the host element prevents this by always having
      the spinner sized according to its actual dimensions.
    */
    flex: none;
    display: inline-flex;
    width: var(--size);
    height: var(--size);
  }

  svg {
    width: 100%;
    height: 100%;
    aspect-ratio: 1;
    animation: spin var(--speed) linear infinite;
  }

  .track,
  .indicator {
    --radius: calc(var(--size) / 2 - var(--track-width) / 2);
    --circumference: calc(var(--radius) * 2 * 3.141592654);

    cx: calc(var(--size) / 2);
    cy: calc(var(--size) / 2);
    r: var(--radius);
    fill: none;
    stroke-width: var(--track-width);
  }

  .track {
    stroke: var(--track-color);
  }

  .indicator {
    stroke: var(--indicator-color);
    stroke-linecap: round;
    stroke-dasharray: calc(0.597 * var(--circumference)), calc(0.796 * var(--circumference));
    stroke-dashoffset: calc(-0.04 * var(--circumference));
    animation: dash 1.5s ease-in-out infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes dash {
    0% {
      stroke-dasharray: calc(0.008 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: 0;
    }
    50% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.278 * var(--circumference));
    }
    100% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.987 * var(--circumference));
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var Ht=class extends j{constructor(){super(...arguments),this.localize=new _(this)}render(){return d`
      <svg
        part="base spinner"
        role="progressbar"
        aria-label=${this.localize.term("loading")}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle class="track" />
        <circle class="indicator" />
      </svg>
    `}};Ht.css=ue;Ht=o([E("wa-spinner")],Ht);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var de=C`
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
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var Q=class extends j{constructor(){super(...arguments),this.localize=new _(this),this.position=50}handleDrag(t){let{width:e}=this.getBoundingClientRect(),i=this.localize.dir()==="rtl";t.preventDefault(),ot(this,{onMove:r=>{this.customStates.set("dragging",!0),this.position=parseFloat(S(r/e*100,0,100).toFixed(2)),i&&(this.position=100-this.position)},onStop:()=>{this.customStates.set("dragging",!1)},initialEvent:t})}handleKeyDown(t){let e=this.matches(":dir(ltr)"),i=this.localize.dir()==="rtl";if(["ArrowLeft","ArrowRight","Home","End"].includes(t.key)){let r=t.shiftKey?10:1,a=this.position;t.preventDefault(),(e&&t.key==="ArrowLeft"||i&&t.key==="ArrowRight")&&(a-=r),(e&&t.key==="ArrowRight"||i&&t.key==="ArrowLeft")&&(a+=r),t.key==="Home"&&(a=0),t.key==="End"&&(a=100),a=S(a,0,100),this.position=a}}handlePositionChange(){this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}render(){let t=this.hasUpdated?this.localize.dir()==="rtl":this.dir==="rtl";return d`
      <div id="comparison" class="image" part="base comparison">
        <div part="before" class="before">
          <slot name="before"></slot>
        </div>

        <div
          part="after"
          class="after"
          style=${M({clipPath:t?`inset(0 0 0 ${100-this.position}%)`:`inset(0 ${100-this.position}% 0 0)`})}
        >
          <slot name="after"></slot>
        </div>
      </div>

      <div
        part="divider"
        class="divider"
        style=${M({left:t?`${100-this.position}%`:`${this.position}%`})}
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
    `}};Q.css=de;o([m(".handle")],Q.prototype,"handle",2);o([s({type:Number,reflect:!0})],Q.prototype,"position",2);o([v("position",{waitUntilFirstUpdate:!0})],Q.prototype,"handlePositionChange",1);Q=o([E("wa-comparison")],Q);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ce=C`
  :host {
    --height: var(--wa-form-control-toggle-size);
    --width: calc(var(--height) * 1.75);
    --thumb-size: 0.75em;

    display: inline-flex;
    line-height: var(--wa-form-control-value-line-height);
  }

  label {
    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    color: var(--wa-form-control-value-color);
    vertical-align: middle;
    cursor: pointer;
  }

  .switch {
    flex: 0 0 auto;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--width);
    height: var(--height);
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--height);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    transition-property: translate, background, border-color, box-shadow;
    transition-duration: var(--wa-transition-normal);
    transition-timing-function: var(--wa-transition-easing);
  }

  :host([did-ssr]:not(:defined)) .switch {
    transition-property: unset;
    transition-duration: unset;
    transition-timing-function: unset;
  }

  .switch .thumb {
    aspect-ratio: 1 / 1;
    width: var(--thumb-size);
    height: var(--thumb-size);
    background-color: var(--wa-form-control-border-color);
    border-radius: 50%;
    translate: calc((var(--width) - var(--height)) / -2);
    transition: inherit;
  }
  .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / 2);
  }

  .input {
    position: absolute;
    opacity: 0;
    padding: 0;
    margin: 0;
    pointer-events: none;
  }

  /* Focus */
  label:not(.disabled) .input:focus-visible ~ [part~='control'] {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Checked */
  .checked .switch {
    background-color: var(--wa-form-control-activated-color);
    border-color: var(--wa-form-control-activated-color);
  }

  .checked .switch .thumb {
    background-color: var(--wa-color-surface-default);
    translate: calc((var(--width) - var(--height)) / 2);
  }
  .checked .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / -2);
  }

  /* Disabled */
  label:has(> :disabled) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  [part~='label'] {
    display: inline-block;
    line-height: var(--height);
    margin-inline-start: 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  :host([required]) [part~='label']::after {
    content: var(--wa-form-control-required-content);
    color: var(--wa-form-control-required-content-color);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  @media (forced-colors: active) {
    :checked:enabled + .switch:hover .thumb,
    :checked + .switch .thumb {
      background-color: ButtonText;
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var T=class extends z{constructor(){super(...arguments),this.hasSlotController=new F(this,"hint"),this.localize=new _(this),this.title="",this.name=null,this._value=this.getAttribute("value")??null,this.size="m",this.disabled=!1,this._checked=null,this.defaultChecked=this.hasAttribute("checked"),this.required=!1,this.hint="",this.withHint=!1}static get validators(){return[...super.validators,X()]}get value(){return this._value??"on"}set value(t){this._value=t}handleSizeChange(){D(this.localName,this.size)}get checked(){return this.valueHasChanged?!!this._checked:this._checked??this.defaultChecked}set checked(t){this._checked=!!t,this.valueHasChanged=!0}handleClick(){this.hasInteracted=!0,this.checked=!this.checked,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleKeyDown(t){let e=this.localize.dir()==="rtl";t.key==="ArrowLeft"&&(t.preventDefault(),this.checked=e,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))})),t.key==="ArrowRight"&&(t.preventDefault(),this.checked=!e,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))}))}willUpdate(t){super.willUpdate(t),(t.has("value")||t.has("checked")||t.has("defaultChecked")||t.has("disabled"))&&this.handleValueOrCheckedChange()}handleValueOrCheckedChange(){if(this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleValueOrCheckedChange()});return}this.setValue(this.checked?this.value:null,this._value),this.updateValidity()}handleStateChange(){this.hasUpdated&&(this.input.checked=this.checked),this.customStates.set("checked",this.checked),this.updateValidity()}handleDisabledChange(){this.updateValidity()}click(){this.input.click()}focus(t){this.input.focus(t)}blur(){this.input.blur()}setValue(t,e){if(!this.checked){this.internals.setFormValue(null,null);return}this.internals.setFormValue(t??"on",e)}formResetCallback(){this._checked=null,super.formResetCallback(),this.handleValueOrCheckedChange()}render(){let t=this.hasSlotController.test("hint","withHint"),e=this.hint?!0:!!t,i=this.didSSR&&!this.hasUpdated?this.checked:this.defaultChecked,r=this.didSSR&&!this.hasUpdated?null:it(this.checked);return d`
      <label
        part="base switch"
        class=${k({checked:this.checked,disabled:this.disabled})}
      >
        <input
          class="input"
          type="checkbox"
          title=${this.title}
          name=${f(this.name)}
          value=${f(this.value)}
          .checked=${f(r)}
          ?checked=${i}
          ?disabled=${this.disabled}
          ?required=${this.required}
          role="switch"
          aria-checked=${this.checked?"true":"false"}
          aria-describedby="hint"
          @click=${this.handleClick}
          @keydown=${this.handleKeyDown}
        />

        <span part="control" class="switch">
          <span part="thumb" class="thumb"></span>
        </span>

        <slot part="label" class="label"></slot>
      </label>

      <slot
        id="hint"
        name="hint"
        part="hint"
        class=${k({"has-slotted":e})}
        aria-hidden=${e?"false":"true"}
        >${this.hint}</slot
      >
    `}};T.shadowRootOptions={...z.shadowRootOptions,delegatesFocus:!0};T.css=[H,A,ce];o([m('input[type="checkbox"]')],T.prototype,"input",2);o([s()],T.prototype,"title",2);o([s({reflect:!0})],T.prototype,"name",2);o([s({reflect:!0})],T.prototype,"value",1);o([s({reflect:!0})],T.prototype,"size",2);o([v("size")],T.prototype,"handleSizeChange",1);o([s({type:Boolean})],T.prototype,"disabled",2);o([s({type:Boolean,attribute:!1})],T.prototype,"checked",1);o([s({type:Boolean,attribute:"checked",reflect:!0})],T.prototype,"defaultChecked",2);o([s({type:Boolean,reflect:!0})],T.prototype,"required",2);o([s({attribute:"hint"})],T.prototype,"hint",2);o([s({attribute:"with-hint",type:Boolean})],T.prototype,"withHint",2);o([v(["checked","defaultChecked"])],T.prototype,"handleStateChange",1);o([v("disabled",{waitUntilFirstUpdate:!0})],T.prototype,"handleDisabledChange",1);T=o([E("wa-switch")],T);T.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var pe=C`
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
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var L=class extends z{constructor(){super(),this.hasSlotController=new F(this,"hint","label"),this.label="",this.hint="",this.name=null,this.disabled=!1,this.orientation="vertical",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.required=!1,this.withLabel=!1,this.withHint=!1,this.handleRadioClick=t=>{let e=t.target.closest("wa-radio");if(!e||e.disabled||e.forceDisabled||this.disabled)return;let i=this.value;this.value=e.value,e.checked=!0;let r=this.getAllRadios();for(let a of r)e!==a&&(a.checked=!1,a.setAttribute("tabindex","-1"));this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})},this.addEventListener("keydown",this.handleKeyDown),this.addEventListener("click",this.handleRadioClick)}static get validators(){let t=[rt({validationElement:Object.assign(document.createElement("input"),{required:!0,type:"radio",name:Ut("__wa-radio")})})];return[...super.validators,...t]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(t){typeof t=="number"&&(t=String(t)),this.valueHasChanged=!0,this._value=t}handleSizeChange(){D(this.localName,this.size)}get validationTarget(){if(!1)return;let t=this.querySelector(":is(wa-radio):not([disabled])");if(t)return t}updated(t){(t.has("disabled")||t.has("size")||t.has("value")||t.has("defaultValue"))&&this.syncRadioElements()}formResetCallback(...t){this._value=null,super.formResetCallback(...t),this.syncRadioElements()}getAllRadios(){return[...this.querySelectorAll("wa-radio")]}handleLabelClick(){this.focus()}async syncRadioElements(){let t=this.getAllRadios();if(t.forEach((e,i)=>{this.size&&e.setAttribute("size",this.size),e.toggleAttribute("data-wa-radio-horizontal",this.orientation!=="vertical"),e.toggleAttribute("data-wa-radio-vertical",this.orientation==="vertical"),e.toggleAttribute("data-wa-radio-first",i===0),e.toggleAttribute("data-wa-radio-inner",i!==0&&i!==t.length-1),e.toggleAttribute("data-wa-radio-last",i===t.length-1),e.forceDisabled=this.disabled}),await Promise.all(t.map(async e=>{await e.updateComplete,!e.disabled&&e.value===this.value?e.checked=!0:e.checked=!1})),this.disabled)t.forEach(e=>{e.tabIndex=-1});else{let e=t.filter(r=>!r.disabled),i=e.find(r=>r.checked);e.length>0&&(i?e.forEach(r=>{r.tabIndex=r.checked?0:-1}):e.forEach((r,a)=>{r.tabIndex=a===0?0:-1})),t.filter(r=>r.disabled).forEach(r=>{r.tabIndex=-1})}}handleKeyDown(t){if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(t.key)||this.disabled)return;let e=this.getAllRadios().filter(h=>!h.disabled);if(e.length<=0)return;t.preventDefault();let i=this.value,r=e.find(h=>h.checked)??e[0],a=t.key===" "?0:["ArrowUp","ArrowLeft"].includes(t.key)?-1:1,n=e.indexOf(r)+a;n||(n=0),n<0&&(n=e.length-1),n>e.length-1&&(n=0);let l=e.some(h=>h.tagName.toLowerCase()==="wa-radio-button");this.getAllRadios().forEach(h=>{h.checked=!1,l||h.setAttribute("tabindex","-1")}),this.value=e[n].value,e[n].checked=!0,l?e[n].shadowRoot.querySelector("button").focus():(e[n].setAttribute("tabindex","0"),e[n].focus()),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),t.preventDefault()}focus(t){if(this.disabled)return;let e=this.getAllRadios(),i=e.find(n=>n.checked),r=e.find(n=>!n.disabled),a=i||r;a&&a.focus(t)}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,r=this.hint?!0:!!e;return d`
      <fieldset
        part="form-control"
        class=${k({"form-control":!0,"form-control-radio-group":!0,"form-control-has-label":i})}
        role="radiogroup"
        aria-labelledby="label"
        aria-describedby="hint"
        aria-errormessage="error-message"
        aria-orientation=${this.orientation}
      >
        <label
          part="form-control-label"
          id="label"
          class=${k({label:!0,"has-label":i})}
          aria-hidden=${i?"false":"true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <slot part="form-control-input" @slotchange=${this.syncRadioElements}></slot>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${k({"has-slotted":r})}
          aria-hidden=${r?"false":"true"}
          >${this.hint}</slot
        >
      </fieldset>
    `}};L.css=[A,H,pe];L.shadowRootOptions={...z.shadowRootOptions,delegatesFocus:!0};o([m("slot:not([name])")],L.prototype,"defaultSlot",2);o([s()],L.prototype,"label",2);o([s({attribute:"hint"})],L.prototype,"hint",2);o([s({reflect:!0})],L.prototype,"name",2);o([s({type:Boolean,reflect:!0})],L.prototype,"disabled",2);o([s({reflect:!0})],L.prototype,"orientation",2);o([y()],L.prototype,"value",1);o([s({attribute:"value",reflect:!0})],L.prototype,"defaultValue",2);o([s({reflect:!0})],L.prototype,"size",2);o([v("size")],L.prototype,"handleSizeChange",1);o([s({type:Boolean,reflect:!0})],L.prototype,"required",2);o([s({type:Boolean,attribute:"with-label"})],L.prototype,"withLabel",2);o([s({type:Boolean,attribute:"with-hint"})],L.prototype,"withHint",2);L=o([E("wa-radio-group")],L);L.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var me=C`
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
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var U=class extends z{constructor(){super(),this.checked=!1,this.forceDisabled=!1,this.appearance="default",this.disabled=!1,this.handleClick=()=>{!this.disabled&&!this.forceDisabled&&(this.checked=!0)},this.addEventListener("click",this.handleClick)}handleSizeChange(){D(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.setInitialAttributes()}setInitialAttributes(){this.setAttribute("role","radio"),this.tabIndex=0,this.setAttribute("aria-disabled",this.disabled||this.forceDisabled?"true":"false")}updated(t){if(super.updated(t),t.has("checked")&&(this.customStates.set("checked",this.checked),this.setAttribute("aria-checked",this.checked?"true":"false"),!this.disabled&&!this.forceDisabled&&(this.tabIndex=this.checked?0:-1)),t.has("disabled")||t.has("forceDisabled")){let e=this.disabled||this.forceDisabled;this.customStates.set("disabled",e),this.setAttribute("aria-disabled",e?"true":"false"),e?this.tabIndex=-1:this.tabIndex=this.checked?0:-1}}setValue(){}render(){return d`
      <span part="control" class="control">
        ${this.checked?d`
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" part="checked-icon" class="checked-icon">
                <circle cx="8" cy="8" r="8" />
              </svg>
            `:""}
      </span>

      <slot part="label" class="label"></slot>
    `}};U.css=[H,A,me];o([y()],U.prototype,"checked",2);o([y()],U.prototype,"forceDisabled",2);o([s({reflect:!0})],U.prototype,"value",2);o([s({reflect:!0})],U.prototype,"appearance",2);o([s({reflect:!0})],U.prototype,"size",2);o([v("size")],U.prototype,"handleSizeChange",1);o([s({type:Boolean})],U.prototype,"disabled",2);U=o([E("wa-radio")],U);U.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var fe=C`
  :host {
    --track-size: 0.5em;
    --thumb-width: 1.4em;
    --thumb-height: 1.4em;
    --marker-width: 0.1875em;
    --marker-height: 0.1875em;
  }

  :host([orientation='vertical']) {
    width: auto;
  }

  #label:has(~ .vertical) {
    display: block;
    order: 2;
    max-width: none;
    text-align: center;
  }

  #description:has(~ .vertical) {
    order: 3;
    text-align: center;
  }

  /* Add extra space between slider and label, when present */
  #label.has-label ~ #slider {
    &.horizontal {
      margin-block-start: 0.5em;
    }
    &.vertical {
      margin-block-end: 0.5em;
    }
  }

  #slider {
    touch-action: none;

    &:focus {
      outline: none;
    }

    &:focus-visible:not(.disabled) #thumb,
    &:focus-visible:not(.disabled) #thumb-min,
    &:focus-visible:not(.disabled) #thumb-max {
      outline: var(--wa-focus-ring);
      /* intentionally no offset due to border */
    }
  }

  #track {
    position: relative;
    border-radius: 9999px;
    background: var(--wa-color-neutral-fill-normal);
    isolation: isolate;
  }

  /* Orientation */
  .horizontal #track {
    height: var(--track-size);
  }

  .vertical #track {
    order: 1;
    width: var(--track-size);
    height: 200px;
  }

  /* Disabled */
  .disabled #track {
    cursor: not-allowed;
    opacity: 0.5;
  }

  /* Indicator */
  #indicator {
    position: absolute;
    border-radius: inherit;
    background-color: var(--wa-form-control-activated-color);

    &:dir(ltr) {
      right: calc(100% - max(var(--start), var(--end)));
      left: min(var(--start), var(--end));
    }

    &:dir(rtl) {
      right: min(var(--start), var(--end));
      left: calc(100% - max(var(--start), var(--end)));
    }
  }

  .horizontal #indicator {
    top: 0;
    height: 100%;
  }

  .vertical #indicator {
    top: calc(100% - var(--end));
    bottom: var(--start);
    left: 0;
    width: 100%;
  }

  /* Thumbs */
  #thumb,
  #thumb-min,
  #thumb-max {
    z-index: 3;
    position: absolute;
    width: var(--thumb-width);
    height: var(--thumb-height);
    border: solid 0.125em var(--wa-color-surface-default);
    border-radius: 50%;
    background-color: var(--wa-form-control-activated-color);
    cursor: pointer;
  }

  .disabled #thumb,
  .disabled #thumb-min,
  .disabled #thumb-max {
    cursor: inherit;
  }

  .horizontal #thumb,
  .horizontal #thumb-min,
  .horizontal #thumb-max {
    top: calc(50% - var(--thumb-height) / 2);

    &:dir(ltr) {
      right: auto;
      left: calc(var(--position) - var(--thumb-width) / 2);
    }

    &:dir(rtl) {
      right: calc(var(--position) - var(--thumb-width) / 2);
      left: auto;
    }
  }

  .vertical #thumb,
  .vertical #thumb-min,
  .vertical #thumb-max {
    bottom: calc(var(--position) - var(--thumb-height) / 2);
    left: calc(50% - var(--thumb-width) / 2);
  }

  /* Range-specific thumb styles */
  :host([range]) {
    #thumb-min:focus-visible,
    #thumb-max:focus-visible {
      z-index: 4; /* Ensure focused thumb appears on top */
      outline: var(--wa-focus-ring);
      /* intentionally no offset due to border */
    }
  }

  /* Markers */
  #markers {
    pointer-events: none;
  }

  .marker {
    z-index: 2;
    position: absolute;
    width: var(--marker-width);
    height: var(--marker-height);
    border-radius: 50%;
    background-color: var(--wa-color-surface-default);
  }

  .marker:first-of-type,
  .marker:last-of-type {
    display: none;
  }

  .horizontal .marker {
    top: calc(50% - var(--marker-height) / 2);
    left: calc(var(--position) - var(--marker-width) / 2);
  }

  .vertical .marker {
    top: calc(var(--position) - var(--marker-height) / 2);
    left: calc(50% - var(--marker-width) / 2);
  }

  /* Marker labels */
  #references {
    position: relative;

    slot {
      display: flex;
      justify-content: space-between;
      height: 100%;
    }

    ::slotted(*) {
      color: var(--wa-color-text-quiet);
      font-size: 0.875em;
      line-height: 1;
    }
  }

  .horizontal {
    #references {
      margin-block-start: 0.5em;
    }
  }

  .vertical {
    display: flex;
    margin-inline: auto;

    #track {
      order: 1;
    }

    #references {
      order: 2;
      width: min-content;
      margin-inline-start: 0.75em;

      slot {
        flex-direction: column;
      }
    }
  }

  .vertical #references slot {
    flex-direction: column;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function*Ft(t=document.activeElement){t!=null&&(yield t,"shadowRoot"in t&&t.shadowRoot&&t.shadowRoot.mode!=="closed"&&(yield*Ft(t.shadowRoot.activeElement)))}/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function It(t,e,i){let r=(t-e)/i;return Math.abs(r-Math.round(r))>1e-9}var Ae=()=>({observedAttributes:["min","max","step"],checkValidity(t){let e={message:"",isValid:!0,invalidKeys:[]},i=(r,a,n,l)=>{if(typeof document>"u")return"";let h=document.createElement("input");return h.type="range",h.min=String(a),h.max=String(n),h.step=String(l),h.value=String(r),h.checkValidity(),h.validationMessage};if(t.isRange){let r=t.minValue,a=t.maxValue;if(r<t.min)return e.isValid=!1,e.invalidKeys.push("rangeUnderflow"),e.message=i(r,t.min,t.max,t.step)||`Value must be greater than or equal to ${t.min}.`,e;if(a>t.max)return e.isValid=!1,e.invalidKeys.push("rangeOverflow"),e.message=i(a,t.min,t.max,t.step)||`Value must be less than or equal to ${t.max}.`,e;if(t.step&&t.step!==1){let n=It(r,t.min,t.step),l=It(a,t.min,t.step);if(n||l){e.isValid=!1,e.invalidKeys.push("stepMismatch");let h=n?r:a;return e.message=i(h,t.min,t.max,t.step)||`Value must be a multiple of ${t.step}.`,e}}}else{let r=t.value;if(r<t.min)return e.isValid=!1,e.invalidKeys.push("rangeUnderflow"),e.message=i(r,t.min,t.max,t.step)||`Value must be greater than or equal to ${t.min}.`,e;if(r>t.max)return e.isValid=!1,e.invalidKeys.push("rangeOverflow"),e.message=i(r,t.min,t.max,t.step)||`Value must be less than or equal to ${t.max}.`,e;if(t.step&&t.step!==1&&It(r,t.min,t.step))return e.isValid=!1,e.invalidKeys.push("stepMismatch"),e.message=i(r,t.min,t.max,t.step)||`Value must be a multiple of ${t.step}.`,e}return e}}),g=class extends z{constructor(){super(...arguments),this.draggableThumbMin=null,this.draggableThumbMax=null,this.hasSlotController=new F(this,"hint","label"),this.localize=new _(this),this.activeThumb=null,this.lastTrackPosition=null,this.label="",this.hint="",this.minValue=0,this.maxValue=50,this.defaultValue=this.getAttribute("value")==null?this.minValue:Number(this.getAttribute("value")),this._value=null,this.range=!1,this.disabled=!1,this.readonly=!1,this.orientation="horizontal",this.size="m",this.min=0,this.max=100,this.step=1,this.tooltipDistance=8,this.tooltipPlacement="top",this.withMarkers=!1,this.withTooltip=!1,this.withLabel=!1,this.withHint=!1}static get validators(){return[...super.validators,Ae()]}get focusableAnchor(){return this.isRange?this.thumbMin||this.slider:this.slider}get validationTarget(){return this.focusableAnchor}get value(){if(this.valueHasChanged){let e=this._value??this.minValue??0;return S(e,this.min,this.max)}let t=this._value??this.defaultValue;return S(t,this.min,this.max)}set value(t){t=Number(t)??this.minValue,this._value!==t&&(this.valueHasChanged=!0,this._value=t)}get isRange(){return this.range}handleSizeChange(){D(this.localName,this.size)}firstUpdated(t){super.firstUpdated(t),this.isRange?(this.draggableThumbMin=new nt(this.thumbMin,{start:()=>{this.activeThumb="min",this.trackBoundingClientRect=this.track.getBoundingClientRect(),this.valueWhenDraggingStarted=this.minValue,this.customStates.set("dragging",!0),this.showRangeTooltips()},move:(e,i)=>{this.setThumbValueFromCoordinates(e,i,"min")},stop:()=>{this.minValue!==this.valueWhenDraggingStarted&&(this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.hasInteracted=!0),this.hideRangeTooltips(),this.customStates.set("dragging",!1),this.valueWhenDraggingStarted=void 0,this.activeThumb=null}}),this.draggableThumbMax=new nt(this.thumbMax,{start:()=>{this.activeThumb="max",this.trackBoundingClientRect=this.track.getBoundingClientRect(),this.valueWhenDraggingStarted=this.maxValue,this.customStates.set("dragging",!0),this.showRangeTooltips()},move:(e,i)=>{this.setThumbValueFromCoordinates(e,i,"max")},stop:()=>{this.maxValue!==this.valueWhenDraggingStarted&&(this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.hasInteracted=!0),this.hideRangeTooltips(),this.customStates.set("dragging",!1),this.valueWhenDraggingStarted=void 0,this.activeThumb=null}}),this.draggableTrack=new nt(this.track,{start:(e,i)=>{if(this.trackBoundingClientRect=this.track.getBoundingClientRect(),this.activeThumb)this.valueWhenDraggingStarted=this.activeThumb==="min"?this.minValue:this.maxValue;else{let r=this.getValueFromCoordinates(e,i),a=Math.abs(r-this.minValue),n=Math.abs(r-this.maxValue);if(a===n)if(r>this.maxValue)this.activeThumb="max";else if(r<this.minValue)this.activeThumb="min";else{let l=this.localize.dir()==="rtl",h=this.orientation==="vertical",u=h?i:e,p=this.lastTrackPosition||u;this.lastTrackPosition=u;let V=u>p!==l&&!h||u<p&&h;this.activeThumb=V?"max":"min"}else this.activeThumb=a<=n?"min":"max";this.valueWhenDraggingStarted=this.activeThumb==="min"?this.minValue:this.maxValue}this.customStates.set("dragging",!0),this.setThumbValueFromCoordinates(e,i,this.activeThumb),this.showRangeTooltips()},move:(e,i)=>{this.activeThumb&&this.setThumbValueFromCoordinates(e,i,this.activeThumb)},stop:()=>{this.activeThumb&&(this.activeThumb==="min"?this.minValue:this.maxValue)!==this.valueWhenDraggingStarted&&(this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.hasInteracted=!0),this.hideRangeTooltips(),this.customStates.set("dragging",!1),this.valueWhenDraggingStarted=void 0,this.activeThumb=null}})):this.draggableTrack=new nt(this.slider,{start:(e,i)=>{this.trackBoundingClientRect=this.track.getBoundingClientRect(),this.valueWhenDraggingStarted=this.value,this.customStates.set("dragging",!0),this.setValueFromCoordinates(e,i),this.showTooltip()},move:(e,i)=>{this.setValueFromCoordinates(e,i)},stop:()=>{this.value!==this.valueWhenDraggingStarted&&(this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.hasInteracted=!0),this.hideTooltip(),this.customStates.set("dragging",!1),this.valueWhenDraggingStarted=void 0}})}willUpdate(t){this.isRange&&(t.has("minValue")||t.has("maxValue")||t.has("min")||t.has("max"))&&(this.minValue=S(this.minValue,this.min,this.maxValue),this.maxValue=S(this.maxValue,this.minValue,this.max)),super.willUpdate(t)}updated(t){if(this.isRange&&(t.has("minValue")||t.has("maxValue"))&&this.updateFormValue(),t.has("disabled")||t.has("readonly")){let e=!(this.disabled||this.readonly);this.isRange&&(this.draggableThumbMin&&this.draggableThumbMin.toggle(e),this.draggableThumbMax&&this.draggableThumbMax.toggle(e)),this.draggableTrack&&this.draggableTrack.toggle(e)}super.updated(t)}formDisabledCallback(t){this.disabled=t}formResetCallback(){this.isRange?(this.minValue=parseFloat(this.getAttribute("min-value")??String(this.min)),this.maxValue=parseFloat(this.getAttribute("max-value")??String(this.max))):(this._value=null,this.defaultValue=this.defaultValue??parseFloat(this.getAttribute("value")??String(this.min))),this.valueHasChanged=!1,this.hasInteracted=!1,super.formResetCallback()}clampAndRoundToStep(t){let e=(String(this.step).split(".")[1]||"").replace(/0+$/g,"").length,i=Number(this.step),r=Number(this.min),a=Number(this.max);return t=Math.round(t/i)*i,t=S(t,r,a),parseFloat(t.toFixed(e))}getPercentageFromValue(t){return(t-this.min)/(this.max-this.min)*100}getValueFromCoordinates(t,e){let i=this.localize.dir()==="rtl",r=this.orientation==="vertical",{top:a,right:n,bottom:l,left:h,height:u,width:p}=this.trackBoundingClientRect,V=r?e:t,O=r?{start:a,end:l,size:u}:{start:h,end:n,size:p},K=(r||i?O.end-V:V-O.start)/O.size;return this.clampAndRoundToStep(this.min+(this.max-this.min)*K)}handleBlur(){this.isRange?requestAnimationFrame(()=>{let t=this.shadowRoot?.activeElement;t===this.thumbMin||t===this.thumbMax||this.hideRangeTooltips()}):this.hideTooltip(),this.customStates.set("focused",!1),this.dispatchEvent(new FocusEvent("blur",{bubbles:!0,composed:!0}))}handleFocus(t){let e=t.target;this.isRange?(e===this.thumbMin?this.activeThumb="min":e===this.thumbMax&&(this.activeThumb="max"),this.showRangeTooltips()):this.showTooltip(),this.customStates.set("focused",!0),this.dispatchEvent(new FocusEvent("focus",{bubbles:!0,composed:!0}))}handleKeyDown(t){let e=this.localize.dir()==="rtl",i=t.target;if(this.disabled||this.readonly||this.isRange&&(i===this.thumbMin?this.activeThumb="min":i===this.thumbMax&&(this.activeThumb="max"),!this.activeThumb))return;let r=this.isRange?this.activeThumb==="min"?this.minValue:this.maxValue:this.value,a=r;switch(t.key){case"ArrowUp":case(e?"ArrowLeft":"ArrowRight"):t.preventDefault(),a=this.clampAndRoundToStep(r+this.step);break;case"ArrowDown":case(e?"ArrowRight":"ArrowLeft"):t.preventDefault(),a=this.clampAndRoundToStep(r-this.step);break;case"Home":t.preventDefault(),a=this.isRange&&this.activeThumb==="min"?this.min:this.isRange?this.minValue:this.min;break;case"End":t.preventDefault(),a=this.isRange&&this.activeThumb==="max"?this.max:this.isRange?this.maxValue:this.max;break;case"PageUp":t.preventDefault();let n=Math.max(r+(this.max-this.min)/10,r+this.step);a=this.clampAndRoundToStep(n);break;case"PageDown":t.preventDefault();let l=Math.min(r-(this.max-this.min)/10,r-this.step);a=this.clampAndRoundToStep(l);break;case"Enter":kt(t,this);return}a!==r&&(this.isRange?(this.activeThumb==="min"?a>this.maxValue?(this.maxValue=a,this.minValue=a):this.minValue=Math.max(this.min,a):a<this.minValue?(this.minValue=a,this.maxValue=a):this.maxValue=Math.min(this.max,a),this.updateFormValue()):this.value=S(a,this.min,this.max),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.hasInteracted=!0)}handleLabelPointerDown(t){t.preventDefault(),this.disabled||(this.isRange?this.thumbMin?.focus():this.slider.focus())}setValueFromCoordinates(t,e){let i=this.value;this.value=this.getValueFromCoordinates(t,e),this.value!==i&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))})}setThumbValueFromCoordinates(t,e,i){let r=this.getValueFromCoordinates(t,e),a=i==="min"?this.minValue:this.maxValue;i==="min"?r>this.maxValue?(this.maxValue=r,this.minValue=r):this.minValue=Math.max(this.min,r):r<this.minValue?(this.minValue=r,this.maxValue=r):this.maxValue=Math.min(this.max,r),a!==(i==="min"?this.minValue:this.maxValue)&&(this.updateFormValue(),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))}))}showTooltip(){this.withTooltip&&this.tooltip&&(this.tooltip.open=!0)}hideTooltip(){this.withTooltip&&this.tooltip&&(this.tooltip.open=!1)}showRangeTooltips(){if(!this.withTooltip)return;let t=this.shadowRoot?.getElementById("tooltip-thumb-min"),e=this.shadowRoot?.getElementById("tooltip-thumb-max");this.activeThumb==="min"?(t&&(t.open=!0),e&&(e.open=!1)):this.activeThumb==="max"&&(e&&(e.open=!0),t&&(t.open=!1))}hideRangeTooltips(){if(!this.withTooltip)return;let t=this.shadowRoot?.getElementById("tooltip-thumb-min"),e=this.shadowRoot?.getElementById("tooltip-thumb-max");t&&(t.open=!1),e&&(e.open=!1)}updateFormValue(t){if(this.isRange){let e=new FormData;e.append(this.name||"",String(this.minValue)),e.append(this.name||"",String(this.maxValue)),this.setValue(e,e);return}super.updateFormValue(t)}focus(){this.isRange?this.thumbMin?.focus():this.slider.focus()}blur(){if(this.isRange){for(let t of Ft())if(t===this.thumbMin){this.thumbMin.blur();break}else if(t===this.thumbMax){this.thumbMax.blur();break}}else this.slider.blur()}stepDown(){if(this.isRange){let t=this.clampAndRoundToStep(this.minValue-this.step);this.minValue=S(t,this.min,this.maxValue),this.updateFormValue()}else{let t=this.clampAndRoundToStep(this.value-this.step);this.value=t}}stepUp(){if(this.isRange){let t=this.clampAndRoundToStep(this.maxValue+this.step);this.maxValue=S(t,this.minValue,this.max),this.updateFormValue()}else{let t=this.clampAndRoundToStep(this.value+this.step);this.value=t}}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,r=this.hint?!0:!!e,a=this.hasSlotController.test("reference"),n=k({xs:this.size==="xs",s:this.size==="s"||this.size==="small",m:this.size==="m"||this.size==="medium",l:this.size==="l"||this.size==="large",xl:this.size==="xl",small:this.size==="small"||this.size==="s",medium:this.size==="medium"||this.size==="m",large:this.size==="large"||this.size==="l",horizontal:this.orientation==="horizontal",vertical:this.orientation==="vertical",disabled:this.disabled}),l=[];if(this.withMarkers)for(let q=this.min;q<=this.max;q+=this.step)l.push(this.getPercentageFromValue(q));let h=d`
      <label
        id="label"
        part="label"
        for=${this.isRange?"thumb-min":"text-box"}
        class=${k({vh:!i,"has-label":i})}
        @pointerdown=${this.handleLabelPointerDown}
      >
        <slot name="label">${this.label}</slot>
      </label>
    `,u=d`
      <div
        id="hint"
        part="hint"
        class=${k({"has-slotted":r})}
      >
        <slot name="hint">${this.hint}</slot>
      </div>
    `,p=this.withMarkers?d`
          <div id="markers" part="markers">
            ${l.map(q=>d`<span part="marker" class="marker" style=${M({"--position":`${q}%`})}></span>`)}
          </div>
        `:"",V=a?d`
          <div id="references" part="references" aria-hidden="true">
            <slot name="reference"></slot>
          </div>
        `:"",O=(q,K)=>this.withTooltip?d`
            <wa-tooltip
              id=${`tooltip${q!=="thumb"?"-"+q:""}`}
              part="tooltip"
              exportparts="
                base:tooltip__base,
                tooltip:tooltip__tooltip,
                body:tooltip__body,
                arrow:tooltip__arrow
              "
              trigger="manual"
              distance=${this.tooltipDistance}
              placement=${this.tooltipPlacement}
              for=${q}
              activation="manual"
              dir=${this.localize.dir()}
            >
              <span aria-hidden="true">
                ${typeof this.valueFormatter=="function"?this.valueFormatter(K):this.localize.number(K)}
              </span>
            </wa-tooltip>
          `:"";if(this.isRange){let q=S(this.getPercentageFromValue(this.minValue),0,100),K=S(this.getPercentageFromValue(this.maxValue),0,100);return d`
        ${h}

        <div id="slider" part="slider" class=${n}>
          <div id="track" part="track">
            <div
              id="indicator"
              part="indicator"
              style=${M({"--start":`${Math.min(q,K)}%`,"--end":`${Math.max(q,K)}%`})}
            ></div>

            ${p}

            <span
              id="thumb-min"
              part="thumb thumb-min"
              style=${M({"--position":`${q}%`})}
              role="slider"
              aria-valuemin=${this.min}
              aria-valuenow=${this.minValue}
              aria-valuetext=${typeof this.valueFormatter=="function"?this.valueFormatter(this.minValue):this.localize.number(this.minValue)}
              aria-valuemax=${this.max}
              aria-label="${this.label?`${this.label} (minimum value)`:"Minimum value"}"
              aria-orientation=${this.orientation}
              aria-disabled=${this.disabled?"true":"false"}
              aria-readonly=${this.readonly?"true":"false"}
              tabindex=${this.disabled?-1:0}
              @blur=${this.handleBlur}
              @focus=${this.handleFocus}
              @keydown=${this.handleKeyDown}
            ></span>

            <span
              id="thumb-max"
              part="thumb thumb-max"
              style=${M({"--position":`${K}%`})}
              role="slider"
              aria-valuemin=${this.min}
              aria-valuenow=${this.maxValue}
              aria-valuetext=${typeof this.valueFormatter=="function"?this.valueFormatter(this.maxValue):this.localize.number(this.maxValue)}
              aria-valuemax=${this.max}
              aria-label="${this.label?`${this.label} (maximum value)`:"Maximum value"}"
              aria-orientation=${this.orientation}
              aria-disabled=${this.disabled?"true":"false"}
              aria-readonly=${this.readonly?"true":"false"}
              tabindex=${this.disabled?-1:0}
              @blur=${this.handleBlur}
              @focus=${this.handleFocus}
              @keydown=${this.handleKeyDown}
            ></span>
          </div>

          ${V} ${u}
        </div>

        ${O("thumb-min",this.minValue)} ${O("thumb-max",this.maxValue)}
      `}else{let q=S(this.getPercentageFromValue(this.value),0,100),K=S(this.getPercentageFromValue(typeof this.indicatorOffset=="number"?this.indicatorOffset:this.min),0,100);return d`
        ${h}

        <div
          id="slider"
          part="slider"
          class=${n}
          role="slider"
          aria-disabled=${this.disabled?"true":"false"}
          aria-readonly=${this.disabled?"true":"false"}
          aria-orientation=${this.orientation}
          aria-valuemin=${this.min}
          aria-valuenow=${this.value}
          aria-valuetext=${typeof this.valueFormatter=="function"?this.valueFormatter(this.value):this.localize.number(this.value)}
          aria-valuemax=${this.max}
          aria-labelledby="label"
          aria-describedby="hint"
          tabindex=${this.disabled?-1:0}
          @blur=${this.handleBlur}
          @focus=${this.handleFocus}
          @keydown=${this.handleKeyDown}
        >
          <div id="track" part="track">
            <div
              id="indicator"
              part="indicator"
              style=${M({"--start":`${K}%`,"--end":`${q}%`})}
            ></div>

            ${p}
            <span id="thumb" part="thumb" style=${M({"--position":`${q}%`})}></span>
          </div>

          ${V} ${u}
        </div>

        ${O("thumb",this.value)}
      `}}};g.formAssociated=!0;g.observeSlots=!0;g.css=[A,H,fe];o([m("#slider")],g.prototype,"slider",2);o([m("#thumb")],g.prototype,"thumb",2);o([m("#thumb-min")],g.prototype,"thumbMin",2);o([m("#thumb-max")],g.prototype,"thumbMax",2);o([m("#track")],g.prototype,"track",2);o([m("#tooltip")],g.prototype,"tooltip",2);o([s()],g.prototype,"label",2);o([s({attribute:"hint"})],g.prototype,"hint",2);o([s({reflect:!0})],g.prototype,"name",2);o([s({type:Number,attribute:"min-value"})],g.prototype,"minValue",2);o([s({type:Number,attribute:"max-value"})],g.prototype,"maxValue",2);o([s({attribute:"value",reflect:!0,type:Number})],g.prototype,"defaultValue",2);o([y()],g.prototype,"value",1);o([s({type:Boolean,reflect:!0})],g.prototype,"range",2);o([s({type:Boolean})],g.prototype,"disabled",2);o([s({type:Boolean,reflect:!0})],g.prototype,"readonly",2);o([s({reflect:!0})],g.prototype,"orientation",2);o([s({reflect:!0})],g.prototype,"size",2);o([v("size")],g.prototype,"handleSizeChange",1);o([s({attribute:"indicator-offset",type:Number})],g.prototype,"indicatorOffset",2);o([s({type:Number})],g.prototype,"min",2);o([s({type:Number})],g.prototype,"max",2);o([s({type:Number})],g.prototype,"step",2);o([s({type:Boolean})],g.prototype,"autofocus",2);o([s({attribute:"tooltip-distance",type:Number})],g.prototype,"tooltipDistance",2);o([s({attribute:"tooltip-placement",reflect:!0})],g.prototype,"tooltipPlacement",2);o([s({attribute:"with-markers",type:Boolean})],g.prototype,"withMarkers",2);o([s({attribute:"with-tooltip",type:Boolean})],g.prototype,"withTooltip",2);o([s({attribute:"with-label",type:Boolean})],g.prototype,"withLabel",2);o([s({attribute:"with-hint",type:Boolean})],g.prototype,"withHint",2);o([s({attribute:!1})],g.prototype,"valueFormatter",2);g=o([E("wa-slider")],g);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var be=C`
  :host {
    --tag-max-size: 10ch;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);
  }

  /* Add ellipses to multi select options */
  :host wa-tag::part(content) {
    display: initial;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    max-width: var(--tag-max-size);
  }

  :host .disabled [part~='combobox'] {
    opacity: 0.5;
    cursor: not-allowed;
    outline: none;
  }

  :host .enabled:is(.open, :focus-within) [part~='combobox'] {
    outline-color: var(--wa-color-focus);
  }

  /** The popup */
  .select {
    flex: 1 1 auto;
    display: inline-flex;
    width: 100%;
    position: relative;
    vertical-align: middle;

    /* Pass through from select to the popup */
    --show-duration: inherit;
    --hide-duration: inherit;

    &::part(popup) {
      z-index: 900;
    }

    &[data-current-placement^='top']::part(popup) {
      transform-origin: bottom;
    }

    &[data-current-placement^='bottom']::part(popup) {
      transform-origin: top;
    }
  }

  /* Combobox */
  .combobox {
    flex: 1;
    display: flex;
    width: 100%;
    min-width: 0;
    align-items: center;
    justify-content: start;

    min-height: var(--wa-form-control-height);

    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    color: var(--wa-form-control-value-color);
    cursor: pointer;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    overflow: hidden;
    padding: 0 var(--wa-form-control-padding-inline);
    position: relative;
    vertical-align: middle;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Pills */
    :host([pill]) & {
      border-radius: var(--wa-border-radius-pill);
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .combobox {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  .display-input {
    position: relative;
    width: 100%;
    font: inherit;
    border: none;
    background: none;
    line-height: var(--wa-form-control-value-line-height);
    color: var(--wa-form-control-value-color);
    cursor: inherit;
    overflow: hidden;
    padding: 0;
    margin: 0;
    -webkit-appearance: none;

    &:focus {
      outline: none;
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
    }
  }

  /* Manage spacing when tags are present */
  :host([multiple]) {
    --_padding-with-tags: calc(var(--wa-form-control-height) * 0.1 - var(--wa-form-control-border-width));

    & .combobox:has(.tags wa-tag) {
      padding-block: var(--_padding-with-tags);
      padding-inline-start: var(--_padding-with-tags);
    }
  }

  /* Visually hide the display input when multiple is enabled */
  :host([multiple]) .combobox:has(.tags wa-tag) .display-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
  }

  .value-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    padding: 0;
    margin: 0;
  }

  .tags {
    display: flex;
    flex: 1;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.25em;

    /* Nested inside the box, so a step down from the box's radius */
    & wa-tag:not([pill]) {
      border-radius: var(--wa-border-radius-s);
    }

    .disabled & {
      cursor: not-allowed !important;
    }
  }

  /* Start and End */

  .start,
  .end {
    flex: 0;
    display: inline-flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  :host([multiple]) .combobox:has(.tags wa-tag) .start::slotted(*) {
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - var(--_padding-with-tags));
  }

  /* Clear button */
  [part~='clear-button'] {
    flex: 0 0 auto;
    display: inline-flex;
    align-self: stretch;
    align-items: center;
    justify-content: center;
    inline-size: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    background: none;
    padding: 0;
    transition: color var(--wa-transition-normal);
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half that growth on each side. Keeps the glyph
       on the same trailing axis as the segmented-field pickers' clear buttons. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &:focus {
      outline: none;
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }
  }

  /* Expand icon */
  .expand-icon {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
    transition: rotate var(--wa-transition-slow) var(--wa-transition-easing);
    rotate: 0deg;
    margin-inline-start: var(--wa-form-control-padding-inline);

    .open & {
      rotate: -180deg;
    }
  }

  /* Listbox */
  .listbox {
    display: block;
    position: relative;
    font: inherit;
    box-shadow: var(--wa-shadow-m);
    background: var(--wa-color-surface-raised);
    border-color: var(--wa-color-surface-border);
    border-radius: var(--wa-border-radius-m);
    border-style: var(--wa-border-style);
    border-width: var(--wa-border-width-s);
    padding: 0.25em;
    overflow: auto;
    overscroll-behavior: none;

    /* Make sure it adheres to the popup's auto size */
    max-width: var(--auto-size-available-width);
    max-height: var(--auto-size-available-height);

    &::slotted(wa-divider) {
      --spacing: 0.5em;
    }
  }

  /* Space options with half the listbox's padding */
  .listbox slot:not([name]) {
    display: flex;
    flex-direction: column;
    gap: 0.125em;
  }

  slot:not([name])::slotted(small) {
    display: block;
    font-size: var(--wa-font-size-smaller);
    font-weight: var(--wa-font-weight-semibold);
    color: var(--wa-color-text-quiet);
    padding-block: 0.5em;
    padding-inline: 2.25em;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function Te(t,e){return{top:Math.round(t.getBoundingClientRect().top-e.getBoundingClientRect().top),left:Math.round(t.getBoundingClientRect().left-e.getBoundingClientRect().left)}}function Bt(t,e,i="vertical",r="smooth"){let a=Te(t,e),n=a.top+e.scrollTop,l=a.left+e.scrollLeft,h=e.scrollLeft,u=e.scrollLeft+e.offsetWidth,p=e.scrollTop,V=e.scrollTop+e.offsetHeight;(i==="horizontal"||i==="both")&&(l<h?e.scrollTo({left:l,behavior:r}):l+t.clientWidth>u&&e.scrollTo({left:l-e.offsetWidth+t.clientWidth,behavior:r})),(i==="vertical"||i==="both")&&(n<p?e.scrollTo({top:n,behavior:r}):n+t.clientHeight>V&&e.scrollTo({top:n-e.offsetHeight+t.clientHeight,behavior:r}))}/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */var ct=class extends xt{constructor(e){if(super(e),this.it=at,e.type!==wt.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(e){if(e===at||e==null)return this._t=void 0,this.it=e;if(e===mt)return e;if(typeof e!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(e===this.it)return this._t;this.it=e;let i=[e];return i.raw=i,this._t={_$litType$:this.constructor.resultType,strings:i,values:[]}}};ct.directiveName="unsafeHTML",ct.resultType=1;var ve=yt(ct);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var w=class extends z{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.cachedOptions=null,this.hasSlotController=new F(this,"hint","label"),this.localize=new _(this),this.selectionOrder=new Map,this.typeToSelectString="",this.slotChangePending=!1,this.displayLabel="",this.selectedOptions=[],this.name="",this._defaultValue=null,this.size="m",this.placeholder="",this.multiple=!1,this.maxOptionsVisible=3,this.disabled=!1,this.withClear=!1,this.open=!1,this.appearance="outlined",this.pill=!1,this.label="",this.placement="bottom",this.hint="",this.withLabel=!1,this.withHint=!1,this.required=!1,this.getTag=t=>d`
        <wa-tag
          part="tag"
          exportparts="
            base:tag__base,
            content:tag__content,
            remove-button:tag__remove-button,
            remove-button__base:tag__remove-button__base
          "
          ?pill=${this.pill}
          size=${this.size}
          with-remove
          data-value=${t.value}
          @wa-remove=${e=>this.handleTagRemove(e,t)}
        >
          ${t.label}
        </wa-tag>
      `,this.handleDocumentFocusIn=t=>{let e=t.composedPath();this&&!e.includes(this)&&this.hide()},this.handleDocumentKeyDown=t=>{let e=t.target,i=e.closest('[part~="clear-button"]')!==null,r=e.closest("wa-button")!==null;if(!(i||r)){if(t.key==="Escape"&&this.open&&st(this)&&(t.preventDefault(),t.stopPropagation(),this.hide(),this.displayInput.focus({preventScroll:!0})),t.key==="Enter"||t.key===" "&&this.typeToSelectString===""){if(t.preventDefault(),t.stopImmediatePropagation(),!this.open){this.show();return}this.currentOption&&!this.currentOption.disabled&&(this.valueHasChanged=!0,this.hasInteracted=!0,this.multiple?this.toggleOptionSelection(this.currentOption):this.setSelectedOptions(this.currentOption),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.multiple||(this.hide(),this.displayInput.focus({preventScroll:!0})));return}if(["ArrowUp","ArrowDown","Home","End"].includes(t.key)){let a=this.getAllOptions(),n=a.indexOf(this.currentOption),l=Math.max(0,n);if(t.preventDefault(),!this.open&&(this.show(),this.currentOption))return;t.key==="ArrowDown"?(l=n+1,l>a.length-1&&(l=0)):t.key==="ArrowUp"?(l=n-1,l<0&&(l=a.length-1)):t.key==="Home"?l=0:t.key==="End"&&(l=a.length-1),this.setCurrentOption(a[l])}if(t.key?.length===1||t.key==="Backspace"){let a=this.getAllOptions();if(t.metaKey||t.ctrlKey||t.altKey)return;if(!this.open){if(t.key==="Backspace")return;this.show()}t.stopPropagation(),t.preventDefault(),clearTimeout(this.typeToSelectTimeout),this.typeToSelectTimeout=window.setTimeout(()=>this.typeToSelectString="",1e3),t.key==="Backspace"?this.typeToSelectString=this.typeToSelectString.slice(0,-1):this.typeToSelectString+=t.key.toLowerCase();for(let n of a)if(n.label.toLowerCase().startsWith(this.typeToSelectString)){this.setCurrentOption(n);break}}}},this.handleDocumentMouseDown=t=>{let e=t.composedPath();this&&!e.includes(this)&&this.hide()}}static get validators(){let t=[rt({validationElement:Object.assign(document.createElement("select"),{required:!0})})];return[...super.validators,...t]}get validationTarget(){return this.valueInput}set defaultValue(t){this._defaultValue=this.convertDefaultValue(t)}get defaultValue(){return this.convertDefaultValue(this._defaultValue)}rawValuesEqual(t,e){return t==null&&e==null?!0:t==null||e==null||t.length!==e.length?!1:t.every((i,r)=>i===e[r])}convertDefaultValue(t){return!(this.multiple||this.hasAttribute("multiple"))&&Array.isArray(t)&&(t=t[0]),t}set value(t){let e=this.value;t instanceof FormData&&(t=t.getAll(this.name)),t!=null&&!Array.isArray(t)&&(t=[t]);let i=this._value;this._value=t??null,this.rawValuesEqual(i,this._value)||(this.valueHasChanged=!0,this.requestUpdate("value",e))}get value(){let t=this._value??this.defaultValue??null;t!=null&&(t=Array.isArray(t)?t:[t]),this.optionValues=new Set(this.getAllOptions().filter(i=>!i.disabled).map(i=>i.value));let e=t;return t!=null&&(e=t.filter(i=>this.optionValues.has(i)),e=this.multiple?e:e[0],e=e??null),e}handleSizeChange(){D(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.processSlotChange(),this.open=!1}disconnectedCallback(){super.disconnectedCallback(),this.removeOpenListeners(),this.cachedOptions=null}updateDefaultValue(){let e=this.getAllOptions().filter(i=>i.hasAttribute("selected")||i.defaultSelected);if(e.length>0){let i=e.map(r=>r.value);this._defaultValue=this.multiple?i:i[0]}this.hasAttribute("value")&&(this._defaultValue=this.getAttribute("value")||null)}addOpenListeners(){document.addEventListener("focusin",this.handleDocumentFocusIn),document.addEventListener("keydown",this.handleDocumentKeyDown),document.addEventListener("mousedown",this.handleDocumentMouseDown),bt(this),this.getRootNode()!==document&&this.getRootNode().addEventListener("focusin",this.handleDocumentFocusIn)}removeOpenListeners(){document.removeEventListener("focusin",this.handleDocumentFocusIn),document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("mousedown",this.handleDocumentMouseDown),vt(this),this.getRootNode()!==document&&this.getRootNode().removeEventListener("focusin",this.handleDocumentFocusIn)}handleFocus(){this.displayInput.setSelectionRange(0,0)}handleLabelClick(){this.displayInput.focus()}handleComboboxClick(t){t.preventDefault()}handleComboboxMouseDown(t){let i=t.composedPath().some(r=>r instanceof Element&&r.tagName.toLowerCase()==="wa-button");this.disabled||i||(t.preventDefault(),this.displayInput.focus({preventScroll:!0}),this.open=!this.open)}handleComboboxKeyDown(t){t.stopPropagation(),this.handleDocumentKeyDown(t)}handleClearClick(t){t.stopPropagation(),this.hasInteracted=!0,this.valueHasChanged=!0,this.value!==null&&(this.displayLabel="",this.selectionOrder.clear(),this.setSelectedOptions([]),this.displayInput.focus({preventScroll:!0}),this.updateComplete.then(()=>{this.dispatchEvent(new Kt),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))}handleClearMouseDown(t){t.stopPropagation(),t.preventDefault()}handleOptionClick(t){let i=t.target.closest("wa-option");i&&!i.disabled&&(this.hasInteracted=!0,this.valueHasChanged=!0,this.multiple?this.toggleOptionSelection(i):this.setSelectedOptions(i),this.updateComplete.then(()=>this.displayInput.focus({preventScroll:!0})),this.requestUpdate("value"),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.multiple||(this.hide(),this.displayInput.focus({preventScroll:!0})))}handleDefaultSlotChange(){this.slotChangePending||(this.slotChangePending=!0,queueMicrotask(()=>{this.slotChangePending=!1,this.processSlotChange()}))}processSlotChange(){if(customElements.get("wa-option")||customElements.whenDefined("wa-option").then(()=>this.handleDefaultSlotChange()),this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleDefaultSlotChange()});return}this.cachedOptions=null;let t=this.getAllOptions();this.updateDefaultValue();let e=this.value;if(e==null||!this.valueHasChanged&&!this.hasInteracted){this.selectionChanged();return}Array.isArray(e)||(e=[e]);let i=t.filter(r=>e.includes(r.value));this.setSelectedOptions(i)}handleTagRemove(t,e){if(t.stopPropagation(),this.disabled)return;this.hasInteracted=!0,this.valueHasChanged=!0;let i=e;if(!i){let r=t.target.closest("wa-tag[data-value]");if(r){let a=r.dataset.value;i=this.selectedOptions.find(n=>n.value===a)}}i&&(this.toggleOptionSelection(i,!1),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))}getAllOptions(){return this.cachedOptions?this.cachedOptions:this?.querySelectorAll?(this.cachedOptions=[...this.querySelectorAll("wa-option")],this.cachedOptions):[]}getFirstOption(){return this.querySelector("wa-option")}setCurrentOption(t){this.getAllOptions().forEach(i=>{i.current=!1,i.tabIndex=-1}),t&&(this.currentOption=t,t.current=!0,t.tabIndex=0,t.focus({preventScroll:!0}),this.open&&!this.listbox.hidden&&Bt(t,this.listbox,"vertical","auto"))}setSelectedOptions(t){let e=this.getAllOptions(),i=Array.isArray(t)?t:[t];e.forEach(r=>{i.includes(r)||(r.selected=!1)}),i.length&&i.forEach(r=>r.selected=!0),this.selectionChanged()}toggleOptionSelection(t,e){e===!0||e===!1?t.selected=e:t.selected=!t.selected,this.selectionChanged()}selectionChanged(){let e=this.getAllOptions().filter(l=>{if(!this.hasInteracted&&!this.valueHasChanged){let h=this.defaultValue,u=Array.isArray(h)?h:[h];return l.hasAttribute("selected")||l.defaultSelected||l.selected||u?.includes(l.value)}return l.selected}),i=new Set(e.map(l=>l.value));for(let l of this.selectionOrder.keys())i.has(l)||this.selectionOrder.delete(l);let a=(this.selectionOrder.size>0?Math.max(...this.selectionOrder.values()):-1)+1;for(let l of e)this.selectionOrder.has(l.value)||this.selectionOrder.set(l.value,a++);this.selectedOptions=e.sort((l,h)=>{let u=this.selectionOrder.get(l.value)??0,p=this.selectionOrder.get(h.value)??0;return u-p});let n=new Set(this.selectedOptions.map(l=>l.value));if(n.size>0||this._value){let l=this._value;if(this._value==null){let h=this.defaultValue??[];this._value=Array.isArray(h)?h:[h]}this._value=this._value?.filter(h=>!this.optionValues?.has(h))??null,this._value?.unshift(...n),this.requestUpdate("value",l)}if(this.multiple)this.placeholder&&!this.value?.length?this.displayLabel="":this.displayLabel=this.localize.term("numOptionsSelected",this.selectedOptions.length);else{let l=this.selectedOptions[0];this.displayLabel=l?.label??""}this.updateComplete.then(()=>{this.updateValidity()})}get tags(){return this.selectedOptions.map((t,e)=>{if(e<this.maxOptionsVisible||this.maxOptionsVisible<=0){let i=this.getTag(t,e);return i?typeof i=="string"?ve(i):i:null}else if(e===this.maxOptionsVisible)return d`
          <wa-tag
            part="tag"
            exportparts="
              base:tag__base,
              content:tag__content,
              remove-button:tag__remove-button,
              remove-button__base:tag__remove-button__base
            "
            ?pill=${this.pill}
            size=${this.size}
            >+${this.selectedOptions.length-e}</wa-tag
          >
        `;return null})}updated(t){super.updated(t),(t.has("value")||t.has("displayLabel"))&&this.customStates.set("blank",!this.value&&!this.displayLabel)}handleDisabledChange(){this.disabled&&this.open&&(this.open=!1)}handleValueChange(){let t=this.getAllOptions(),e=Array.isArray(this.value)?this.value:[this.value],i=t.filter(r=>e.includes(r.value));this.setSelectedOptions(i),this.updateValidity()}async handleOpenChange(){if(this.open&&!this.disabled){this.setCurrentOption(this.selectedOptions[0]||this.getFirstOption());let t=new jt;if(this.dispatchEvent(t),t.defaultPrevented){this.open=!1;return}this.addOpenListeners(),this.listbox.hidden=!1,this.popup.active=!0,requestAnimationFrame(()=>{this.setCurrentOption(this.currentOption)}),await et(this.popup.popup,"show"),this.currentOption&&Bt(this.currentOption,this.listbox,"vertical","auto"),this.dispatchEvent(new Yt)}else{let t=new Gt;if(this.dispatchEvent(t),t.defaultPrevented){this.open=!1;return}this.removeOpenListeners(),await et(this.popup.popup,"hide"),this.listbox.hidden=!0,this.popup.active=!1,this.dispatchEvent(new Xt)}}async show(){if(this.open||this.disabled){this.open=!1;return}return this.open=!0,tt(this,"wa-after-show")}async hide(){if(!this.open||this.disabled){this.open=!1;return}return this.open=!1,tt(this,"wa-after-hide")}focus(t){this.displayInput.focus(t)}blur(){this.displayInput.blur()}formResetCallback(){this.selectionOrder.clear(),this.value=this.defaultValue,super.formResetCallback(),this.handleValueChange(),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,r=this.hint?!0:!!e,a=(this.hasUpdated||!1)&&this.withClear&&!this.disabled&&(this.displayLabel||this.value&&this.value.length>0);return d`
      <div
        part="form-control"
        class=${k({"form-control":!0,"form-control-has-label":i})}
      >
        <label
          id="label"
          part="form-control-label label"
          class=${k({label:!0,"has-label":i})}
          aria-hidden=${i?"false":"true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <div part="form-control-input" class="form-control-input">
          <wa-popup
            class=${k({select:!0,open:this.open,disabled:this.disabled,enabled:!this.disabled,multiple:this.multiple})}
            placement=${this.placement}
            flip
            shift
            sync="width"
            auto-size="vertical"
            auto-size-padding="10"
          >
            <div
              part="combobox"
              class="combobox"
              slot="anchor"
              @keydown=${this.handleComboboxKeyDown}
              @mousedown=${this.handleComboboxMouseDown}
              @click=${this.handleComboboxClick}
            >
              <slot part="start" name="start" class="start"></slot>

              <input
                part="display-input"
                class="display-input"
                type="text"
                placeholder=${this.placeholder}
                .disabled=${this.disabled}
                .value=${this.displayLabel}
                ?required=${this.required}
                autocomplete="off"
                spellcheck="false"
                autocapitalize="off"
                readonly
                aria-invalid=${!this.validity.valid}
                aria-controls="listbox"
                aria-expanded=${this.open?"true":"false"}
                aria-haspopup="listbox"
                aria-labelledby="label"
                aria-disabled=${this.disabled?"true":"false"}
                aria-describedby="hint"
                role="combobox"
                tabindex="0"
                @focus=${this.handleFocus}
              />

              <!-- Tags need to wait for first hydration before populating otherwise it will create a hydration mismatch. -->
              ${this.multiple&&this.hasUpdated?d`<div part="tags" class="tags" @wa-remove=${this.handleTagRemove}>${this.tags}</div>`:""}

              <input
                class="value-input"
                type="text"
                ?disabled=${this.disabled}
                ?required=${this.required}
                .value=${Array.isArray(this.value)?this.value.join(", "):this.value}
                tabindex="-1"
                aria-hidden="true"
                @focus=${()=>this.focus()}
              />

              ${a?d`
                    <button
                      part="clear-button"
                      type="button"
                      aria-label=${this.localize.term("clearEntry")}
                      @mousedown=${this.handleClearMouseDown}
                      @click=${this.handleClearClick}
                      tabindex="-1"
                    >
                      <slot name="clear-icon">
                        <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                      </slot>
                    </button>
                  `:""}

              <slot name="end" part="end" class="end"></slot>

              <slot name="expand-icon" part="expand-icon" class="expand-icon">
                <wa-icon library="system" name="chevron-down" variant="solid"></wa-icon>
              </slot>
            </div>

            <div
              id="listbox"
              role="listbox"
              aria-expanded=${this.open?"true":"false"}
              aria-multiselectable=${this.multiple?"true":"false"}
              aria-labelledby="label"
              part="listbox"
              class="listbox"
              tabindex="-1"
              @mouseup=${this.handleOptionClick}
            >
              <slot @slotchange=${this.handleDefaultSlotChange}></slot>
            </div>
          </wa-popup>
        </div>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${k({"has-slotted":r})}
          aria-hidden=${r?"false":"true"}
          >${this.hint}</slot
        >
      </div>
    `}};w.css=[be,H,A];o([m(".select")],w.prototype,"popup",2);o([m(".combobox")],w.prototype,"combobox",2);o([m(".display-input")],w.prototype,"displayInput",2);o([m(".value-input")],w.prototype,"valueInput",2);o([m(".listbox")],w.prototype,"listbox",2);o([y()],w.prototype,"displayLabel",2);o([y()],w.prototype,"currentOption",2);o([y()],w.prototype,"selectedOptions",2);o([s({reflect:!0})],w.prototype,"name",2);o([s({attribute:!1})],w.prototype,"defaultValue",1);o([s({attribute:"value",reflect:!1})],w.prototype,"value",1);o([s({reflect:!0})],w.prototype,"size",2);o([v("size")],w.prototype,"handleSizeChange",1);o([s()],w.prototype,"placeholder",2);o([s({type:Boolean,reflect:!0})],w.prototype,"multiple",2);o([s({attribute:"max-options-visible",type:Number})],w.prototype,"maxOptionsVisible",2);o([s({type:Boolean})],w.prototype,"disabled",2);o([s({attribute:"with-clear",type:Boolean})],w.prototype,"withClear",2);o([s({type:Boolean,reflect:!0})],w.prototype,"open",2);o([s({reflect:!0})],w.prototype,"appearance",2);o([s({type:Boolean,reflect:!0})],w.prototype,"pill",2);o([s()],w.prototype,"label",2);o([s({reflect:!0})],w.prototype,"placement",2);o([s({attribute:"hint"})],w.prototype,"hint",2);o([s({attribute:"with-label",type:Boolean})],w.prototype,"withLabel",2);o([s({attribute:"with-hint",type:Boolean})],w.prototype,"withHint",2);o([s({type:Boolean,reflect:!0})],w.prototype,"required",2);o([s({attribute:!1})],w.prototype,"getTag",2);o([v("disabled",{waitUntilFirstUpdate:!0})],w.prototype,"handleDisabledChange",1);o([v("value",{waitUntilFirstUpdate:!0})],w.prototype,"handleValueChange",1);o([v("open",{waitUntilFirstUpdate:!0})],w.prototype,"handleOpenChange",1);w=o([E("wa-select")],w);w.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ge=class extends Event{constructor(){super("wa-remove",{bubbles:!0,cancelable:!1,composed:!0})}};/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var we=C`
  @layer wa-component {
    :host {
      display: inline-flex;
      gap: 0.5em;
      border-radius: var(--wa-border-radius-m);
      align-items: center;
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
      border-style: var(--wa-border-style);
      border-width: var(--wa-border-width-s);
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      font-size: inherit;
      line-height: 1;
      white-space: nowrap;
      user-select: none;
      -webkit-user-select: none;
      height: calc(var(--wa-form-control-height) * 0.8);
      line-height: calc(var(--wa-form-control-height) - var(--wa-form-control-border-width) * 2);
      padding: 0 0.75em;
    }

    /* Appearance modifiers */
    :host([appearance='outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }

    :host([appearance='filled']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: transparent;
    }

    :host([appearance='filled-outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }

    :host([appearance='accent']) {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
  }

  .content {
    font-size: var(--wa-font-size-smaller);
  }

  [part='remove-button'] {
    line-height: 1;
  }

  [part='remove-button']::part(base) {
    padding: 0;
    height: 1em;
    width: 1em;
    color: currentColor;
  }

  @media (hover: hover) {
    :host(:hover) > [part='remove-button']::part(base) {
      background-color: transparent;
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
    }
  }

  :host(:active) > [part='remove-button']::part(base) {
    background-color: transparent;
    color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
  }

  /*
   * Pill modifier
   */
  :host([pill]) {
    border-radius: var(--wa-border-radius-pill);
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var G=class extends j{constructor(){super(...arguments),this.localize=new _(this),this.variant="neutral",this.appearance="filled-outlined",this.size="m",this.pill=!1,this.withRemove=!1}handleSizeChange(){D(this.localName,this.size)}handleRemoveClick(){this.dispatchEvent(new ge)}render(){return d`
      <slot part="content" class="content"></slot>

      ${this.withRemove?d`
            <wa-button
              part="remove-button"
              exportparts="base:remove-button__base"
              class="remove"
              appearance="plain"
              size=${this.size}
              @click=${this.handleRemoveClick}
              tabindex="-1"
            >
              <wa-icon name="xmark" library="system" variant="solid" label=${this.localize.term("remove")}></wa-icon>
            </wa-button>
          `:""}
    `}};G.css=[we,Et,A];o([s({reflect:!0})],G.prototype,"variant",2);o([s({reflect:!0})],G.prototype,"appearance",2);o([s({reflect:!0})],G.prototype,"size",2);o([v("size")],G.prototype,"handleSizeChange",1);o([s({type:Boolean,reflect:!0})],G.prototype,"pill",2);o([s({attribute:"with-remove",type:Boolean})],G.prototype,"withRemove",2);G=o([E("wa-tag")],G);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ye=C`
  :host {
    --current-text-color: var(--wa-color-brand-on-loud);

    display: block;
    color: var(--wa-color-text-normal);
    -webkit-user-select: none;
    user-select: none;

    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    padding: 0.5em 1em 0.5em 0.25em;
    border-radius: var(--wa-border-radius-s);
    line-height: var(--wa-line-height-condensed);
    transition: var(--wa-transition-fast) background-color var(--wa-transition-easing);
    cursor: pointer;
  }

  :host(:focus) {
    outline: none;
  }

  @media (hover: hover) {
    :host(:not(:state(disabled), :state(current)):is(:state(hover), :hover)) {
      background-color: var(--wa-color-neutral-fill-normal);
      color: var(--wa-color-neutral-on-normal);
    }
  }

  :host(:state(current)),
  :host(:state(disabled):state(current)) {
    background-color: var(--wa-form-control-activated-color);
    color: var(--current-text-color);
    opacity: 1;
  }

  :host(:state(disabled)) {
    outline: none;
    opacity: 0.5;
    cursor: not-allowed;
  }

  .label {
    flex: 1 1 auto;
    display: inline-block;
  }

  .check {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--wa-font-size-smaller);
    visibility: hidden;
    width: 2em;
  }

  :host(:state(selected)) .check {
    visibility: visible;
  }

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .start::slotted(*) {
    margin-inline-end: 0.5em;
  }

  .end::slotted(*) {
    margin-inline-start: 0.5em;
  }

  @media (forced-colors: active) {
    :host(:hover:not([aria-disabled='true'])) {
      outline: dashed 1px SelectedItem;
      outline-offset: -1px;
    }
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */function pt(t,e=0){if(!t||!globalThis.Node)return"";if(typeof t[Symbol.iterator]=="function")return(Array.isArray(t)?t:[...t]).map(a=>pt(a,--e)).join("");let i=t;if(i.nodeType===Node.TEXT_NODE)return i.textContent??"";if(i.nodeType===Node.ELEMENT_NODE){let r=i;if(r.hasAttribute("slot")||r.matches("style, script"))return"";if(r instanceof HTMLSlotElement){let a=r.assignedNodes({flatten:!0});if(a.length>0)return pt(a,--e)}return e>-1?pt(r,--e):r.textContent??""}return i.hasChildNodes()?pt(i.childNodes,--e):""}var P=class extends j{constructor(){super(...arguments),this.localize=new _(this),this.cachedDefaultLabel="",this.isInitialized=!1,this.isDefaultLabelDirty=!0,this.current=!1,this.value="",this.disabled=!1,this.selected=!1,this.defaultSelected=!1,this._label="",this.handleHover=t=>{t.type==="mouseenter"?this.customStates.set("hover",!0):t.type==="mouseleave"&&this.customStates.set("hover",!1)}}set label(t){let e=this._label;this._label=t||"",this._label!==e&&this.requestUpdate("label",e)}get label(){return this._label?this._label:this.defaultLabel}get defaultLabel(){return(this.isDefaultLabelDirty||!this.cachedDefaultLabel)&&this.updateDefaultLabel(),this.cachedDefaultLabel}connectedCallback(){super.connectedCallback(),this.setAttribute("role","option"),this.setAttribute("aria-selected","false"),this.addEventListener("mouseenter",this.handleHover),this.addEventListener("mouseleave",this.handleHover)}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener("mouseenter",this.handleHover),this.removeEventListener("mouseleave",this.handleHover)}handleDefaultSlotChange(){this.isDefaultLabelDirty=!0,this.isInitialized?(customElements.whenDefined("wa-select").then(()=>{let t=this.closest("wa-select");t&&t.handleDefaultSlotChange?.()}),customElements.whenDefined("wa-combobox").then(()=>{let t=this.closest("wa-combobox");t&&t.handleDefaultSlotChange?.()})):this.isInitialized=!0}willUpdate(t){t.has("defaultSelected")&&(this.didSSR&&this.hasUpdated||!this.didSSR)&&this.syncDefaultSelected(),super.willUpdate(t)}syncDefaultSelected(){if("closest"in this&&!this.closest("wa-combobox, wa-select")?.hasInteracted&&this.defaultSelected){let t=this.selected;this.selected=this.defaultSelected,this.requestUpdate("selected",t)}}updated(t){t.has("disabled")&&(this.setAttribute("aria-disabled",this.disabled?"true":"false"),this.customStates.set("disabled",this.disabled)),t.has("selected")&&(this.setAttribute("aria-selected",this.selected?"true":"false"),this.customStates.set("selected",this.selected)),t.has("value")&&(typeof this.value!="string"&&(this.value=String(this.value)),this.handleDefaultSlotChange()),t.has("current")&&this.customStates.set("current",this.current),super.updated(t)}async firstUpdated(t){if(super.firstUpdated(t),this.didSSR&&!this.hasUpdated?(await this.updateComplete,this.syncDefaultSelected()):this.syncDefaultSelected(),this.selected&&!this.defaultSelected){let e=this.closest("wa-select, wa-combobox");e&&!e.hasInteracted&&(await customElements.whenDefined(e?.localName),await e.updateComplete,e.selectionChanged?.())}}updateDefaultLabel(){let t=this.cachedDefaultLabel;this.cachedDefaultLabel=pt(this).trim(),this.isDefaultLabelDirty=!1;let e=this.cachedDefaultLabel!==t;return!this._label&&e&&this.requestUpdate("label",t),e}render(){let t=this.selected;return this.didSSR&&!this.hasUpdated?(this.updateComplete.then(()=>{this.requestUpdate()}),at):d`
      ${t?d`<wa-icon
            part="checked-icon"
            class="check"
            name="check"
            library="system"
            variant="solid"
            aria-hidden="true"
          ></wa-icon>`:d`<span part="checked-icon" class="check" aria-hidden="true"></span>`}
      <slot part="start" name="start" class="start"></slot>
      <slot part="label" class="label" @slotchange=${this.handleDefaultSlotChange}></slot>
      <slot part="end" name="end" class="end"></slot>
    `}};P.css=ye;o([m(".label")],P.prototype,"defaultSlot",2);o([y()],P.prototype,"current",2);o([s({reflect:!0})],P.prototype,"value",2);o([s({type:Boolean})],P.prototype,"disabled",2);o([s({type:Boolean,attribute:!1})],P.prototype,"selected",2);o([s({type:Boolean,attribute:"selected"})],P.prototype,"defaultSelected",2);o([s()],P.prototype,"label",1);P=o([E("wa-option")],P);/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var xe=C`
  :host {
    border-width: 0;
  }

  .textarea {
    display: grid;
    align-items: center;
    margin: 0;
    border: none;
    outline: none;
    cursor: inherit;
    font: inherit;
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    -webkit-appearance: none;
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    &:focus-within {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled textareas */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .textarea {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  textarea {
    display: block;
    width: 100%;
    border: none;
    background: transparent;
    font: inherit;
    color: inherit;
    cursor: inherit;
    scroll-padding-block: var(--wa-form-control-padding-block);
    padding: calc(var(--wa-form-control-padding-block) - ((1lh - 1em) / 2)) var(--wa-form-control-padding-inline); /* accounts for the larger line height of textarea content */
    min-height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    box-shadow: none;
    margin: 0;

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &:focus {
      outline: none;
    }
  }

  /* Shared textarea and size-adjuster positioning */
  .control,
  .size-adjuster {
    grid-area: 1 / 1 / 2 / 2;
  }

  .size-adjuster {
    visibility: hidden;
    pointer-events: none;
    opacity: 0;
    padding: 0;
  }

  textarea::-webkit-search-decoration,
  textarea::-webkit-search-cancel-button,
  textarea::-webkit-search-results-button,
  textarea::-webkit-search-results-decoration {
    -webkit-appearance: none;
  }

  /*
   * Resize types
   */

  :host([resize='none']) textarea {
    resize: none;
  }

  textarea,
  :host([resize='vertical']) textarea {
    resize: vertical;
  }

  :host([resize='horizontal']) textarea {
    resize: horizontal;
  }

  :host([resize='both']) textarea {
    resize: both;
  }

  :host([resize='auto']) textarea {
    height: auto;
    resize: none;
    overflow-y: hidden;
  }

  /*
   * Footer (hint + character count)
   */

  /*
   * This element carries the hint part, so the shared form control styles apply to it. Those styles set display:block
   * and hide the element when it has no hint, both of which have to be undone when a character count is present.
   */
  .footer.has-slotted,
  .footer.has-count {
    display: flex;
    align-items: baseline;
    gap: 1em;
  }

  /* Slots default to display:contents, which would leave the hint unable to shrink below its content */
  .footer.has-count .hint {
    display: block;
    flex: 1 1 auto;
    min-width: 0;
  }

  .count {
    flex: 0 0 auto;
    color: var(--wa-form-control-hint-color);
    font-weight: var(--wa-form-control-hint-font-weight);
    line-height: var(--wa-form-control-hint-line-height);
    margin-block-start: 0.5em;
    font-size: var(--wa-font-size-smaller);
    margin-inline-start: auto;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var b=class extends z{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.hasSlotController=new F(this,"hint","label"),this.localize=new _(this),this.announcedCountText="",this.title="",this.name=null,this._value=null,this.defaultValue=this.getAttribute("value")??"",this.size="m",this.appearance="outlined",this.label="",this.hint="",this.placeholder="",this.rows=4,this.resize="vertical",this.disabled=!1,this.readonly=!1,this.required=!1,this.spellcheck=!0,this.withLabel=!1,this.withHint=!1,this.withCount=!1,this.lastObservedWidth=0}static get validators(){return[...super.validators,X()]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(t){this._value!==t&&(this.valueHasChanged=!0,this._value=t)}handleSizeChange(){D(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.updateComplete.then(()=>{if(this.setTextareaDimensions(),this.updateResizeObserver(),this.didSSR&&this.input&&this.value!==this.input.value){let t=this.input.value;this.value=t}})}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this.countAnnounceTimeout),this.resizeObserver?.disconnect(),this.resizeObserver=void 0}updateFormValue(t){if(t==null){this.setValue("",null);return}super.updateFormValue(t)}updateResizeObserver(){let t=this.resize!=="none";this.resizeObserver&&(this.resizeObserver.disconnect(),this.resizeObserver=void 0),t&&this.input&&(this.resize==="auto"?(this.resizeObserver=new ResizeObserver(e=>{let i=e[0]?.contentRect.width??0;i!==this.lastObservedWidth&&(this.lastObservedWidth=i,requestAnimationFrame(()=>this.setTextareaDimensions()))}),this.resizeObserver.observe(this)):(this.resizeObserver=new ResizeObserver(()=>this.setTextareaDimensions()),this.resizeObserver.observe(this.input)))}handleBlur(){this.checkValidity()}handleChange(t){this.valueHasChanged=!0,this.value=this.input.value,this.setTextareaDimensions(),this.checkValidity(),this.relayNativeEvent(t,{bubbles:!0,composed:!0})}handleInput(t){this.valueHasChanged=!0,this.value=this.input.value,this.relayNativeEvent(t,{bubbles:!0,composed:!0}),this.scheduleCountAnnouncement()}scheduleCountAnnouncement(){clearTimeout(this.countAnnounceTimeout),this.countAnnounceTimeout=setTimeout(()=>{let t=(this.value??"").length;this.announcedCountText=this.maxlength!=null?this.localize.term("numCharactersRemaining",this.maxlength-t):this.localize.term("numCharacters",t)},1e3)}setTextareaDimensions(){if(this.resize==="none"){this.base.style.width="",this.base.style.height="";return}if(this.resize==="auto"){this.sizeAdjuster.style.height=`${this.input.clientHeight}px`,this.input.style.height="auto";let t=this.input.scrollHeight;this.input.style.height=`${t}px`,this.sizeAdjuster.style.height=`${t}px`,this.base.style.width="",this.base.style.height="";return}if(this.input.style.width){let t=Number(this.input.style.width.split(/px/)[0])+2;this.base.style.width=`${t}px`}if(this.input.style.height){let t=Number(this.input.style.height.split(/px/)[0])+2;this.base.style.height=`${t}px`}}handleRowsChange(){this.setTextareaDimensions()}async handleValueChange(){await this.updateComplete,this.checkValidity(),this.setTextareaDimensions()}updated(t){t.has("resize")&&(this.setTextareaDimensions(),this.updateResizeObserver()),super.updated(t),t.has("value")&&this.customStates.set("blank",!this.value)}focus(t){this.input.focus(t)}blur(){this.input.blur()}select(){this.input.select()}scrollPosition(t){if(t){typeof t.top=="number"&&(this.input.scrollTop=t.top),typeof t.left=="number"&&(this.input.scrollLeft=t.left);return}return{top:this.input.scrollTop,left:this.input.scrollTop}}setSelectionRange(t,e,i="none"){this.input.setSelectionRange(t,e,i)}setRangeText(t,e,i,r="preserve"){let a=e??this.input.selectionStart,n=i??this.input.selectionEnd;this.input.setRangeText(t,a,n,r),this.value!==this.input.value&&(this.value=this.input.value,this.setTextareaDimensions())}formResetCallback(){this._value=null,this.input&&(this.input.value=this.value||""),super.formResetCallback()}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,r=this.hint?!0:!!e,a=(this.value??"").length,n=this.maxlength!=null?this.localize.term("numCharactersRemaining",this.maxlength-a):this.localize.term("numCharacters",a);return d`
      <label
        part="form-control-label label"
        class=${k({label:!0,"has-label":i})}
        for="input"
        aria-hidden=${i?"false":"true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base textarea-wrapper" class="textarea">
        <textarea
          part="textarea"
          id="input"
          class="control"
          title=${this.title}
          name=${f(this.name)}
          .value=${it(this.value)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${f(this.placeholder)}
          rows=${f(this.rows)}
          minlength=${f(this.minlength)}
          maxlength=${f(this.maxlength)}
          autocapitalize=${f(this.autocapitalize)}
          autocorrect=${f(this.autocorrect)}
          ?autofocus=${this.autofocus}
          spellcheck=${f(this.spellcheck)}
          enterkeyhint=${f(this.enterkeyhint)}
          inputmode=${f(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @blur=${this.handleBlur}
        ></textarea>

        <!-- This "adjuster" exists to prevent layout shifting. https://github.com/shoelace-style/shoelace/issues/2180 -->
        <div part="textarea-adjuster" class="size-adjuster" ?hidden=${this.resize!=="auto"}></div>
      </div>

      <div
        part="hint"
        class=${k({footer:!0,"has-count":this.withCount,"has-slotted":r})}
      >
        <slot id="hint" name="hint" class="hint" aria-hidden=${r?"false":"true"}>${this.hint}</slot>

        ${this.withCount?d`
              <div part="count" class="count" aria-hidden="true">${n}</div>
              <div class="wa-visually-hidden-force" aria-live="polite">${this.announcedCountText}</div>
            `:""}
      </div>
    `}};b.css=[xe,H,A,ft];o([y()],b.prototype,"announcedCountText",2);o([m(".control")],b.prototype,"input",2);o([m('[part~="base"]')],b.prototype,"base",2);o([m(".size-adjuster")],b.prototype,"sizeAdjuster",2);o([s()],b.prototype,"title",2);o([s({reflect:!0})],b.prototype,"name",2);o([y()],b.prototype,"value",1);o([s({attribute:"value",reflect:!0})],b.prototype,"defaultValue",2);o([s({reflect:!0})],b.prototype,"size",2);o([v("size")],b.prototype,"handleSizeChange",1);o([s({reflect:!0})],b.prototype,"appearance",2);o([s()],b.prototype,"label",2);o([s({attribute:"hint"})],b.prototype,"hint",2);o([s()],b.prototype,"placeholder",2);o([s({type:Number})],b.prototype,"rows",2);o([s({reflect:!0})],b.prototype,"resize",2);o([s({type:Boolean})],b.prototype,"disabled",2);o([s({type:Boolean,reflect:!0})],b.prototype,"readonly",2);o([s({type:Boolean,reflect:!0})],b.prototype,"required",2);o([s({type:Number})],b.prototype,"minlength",2);o([s({type:Number})],b.prototype,"maxlength",2);o([s()],b.prototype,"autocapitalize",2);o([s({type:Boolean,converter:{fromAttribute:t=>!(!t||t==="off"),toAttribute:t=>t?"on":"off"}})],b.prototype,"autocorrect",2);o([s()],b.prototype,"autocomplete",2);o([s({type:Boolean})],b.prototype,"autofocus",2);o([s()],b.prototype,"enterkeyhint",2);o([s({type:Boolean,converter:{fromAttribute:t=>!(!t||t==="false"),toAttribute:t=>t?"true":"false"}})],b.prototype,"spellcheck",2);o([s()],b.prototype,"inputmode",2);o([s({attribute:"with-label",type:Boolean})],b.prototype,"withLabel",2);o([s({attribute:"with-hint",type:Boolean})],b.prototype,"withHint",2);o([s({attribute:"with-count",type:Boolean,reflect:!0})],b.prototype,"withCount",2);o([v("rows",{waitUntilFirstUpdate:!0})],b.prototype,"handleRowsChange",1);o([v("value",{waitUntilFirstUpdate:!0})],b.prototype,"handleValueChange",1);b=o([E("wa-textarea")],b);b.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license *//*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var ke=C`
  :host(:focus) {
    outline: none;
  }

  .number-field {
    display: flex;
    align-items: stretch;
    justify-content: start;
    position: relative;
    height: var(--wa-form-control-height);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    cursor: text;
    color: var(--wa-form-control-value-color);
    font-size: inherit;
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
    padding: 0;
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    &:focus-within {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled inputs */
    &:has(input:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) {
    .number-field {
      background-color: var(--wa-form-control-background-color);
      border-color: var(--wa-form-control-border-color);
    }

    .stepper {
      color: var(--wa-color-neutral-on-quiet);

      @media (hover: hover) {
        &:hover:not(:disabled) {
          color: var(--wa-color-neutral-on-quiet);
          background-color: var(--wa-color-neutral-fill-quiet);
        }
      }

      &:active:not(:disabled) {
        color: color-mix(in oklab, var(--wa-color-neutral-on-quiet), var(--wa-color-mix-active));
        background-color: color-mix(in oklab, var(--wa-color-neutral-fill-quiet), var(--wa-color-mix-active));
      }
    }
  }

  :host([appearance='filled']) {
    .number-field {
      background-color: var(--wa-color-neutral-fill-quiet);
      border-color: var(--wa-color-neutral-fill-quiet);
    }

    .stepper {
      color: var(--wa-color-neutral-on-quiet);

      @media (hover: hover) {
        &:hover:not(:disabled) {
          color: var(--wa-color-neutral-on-normal);
          background-color: var(--wa-color-neutral-fill-normal);
        }
      }

      &:active:not(:disabled) {
        color: color-mix(in oklab, var(--wa-color-neutral-on-normal), var(--wa-color-mix-active));
        background-color: color-mix(in oklab, var(--wa-color-neutral-fill-normal), var(--wa-color-mix-active));
      }
    }
  }

  :host([appearance='filled-outlined']) {
    .number-field {
      background-color: var(--wa-color-neutral-fill-quiet);
      border-color: var(--wa-form-control-border-color);
    }

    .stepper {
      color: var(--wa-color-neutral-on-quiet);

      @media (hover: hover) {
        &:hover:not(:disabled) {
          color: var(--wa-color-neutral-on-normal);
          background-color: var(--wa-color-neutral-fill-normal);
        }
      }

      &:active:not(:disabled) {
        color: color-mix(in oklab, var(--wa-color-neutral-on-normal), var(--wa-color-mix-active));
        background-color: color-mix(in oklab, var(--wa-color-neutral-fill-normal), var(--wa-color-mix-active));
      }
    }
  }

  :host([pill]) {
    .number-field,
    .stepper {
      border-radius: var(--wa-border-radius-pill);
    }
  }

  .number-field {
    /* Show autofill styles over the entire number field, not just the native <input> */
    &:has(:autofill),
    &:has(:-webkit-autofill) {
      background-color: var(--wa-color-brand-fill-quiet) !important;
    }

    input {
      flex: auto;
      height: 100%;
      width: auto;
      min-width: 0;
      margin: 0;
      padding: 0 var(--wa-form-control-padding-inline);
      outline: none;
      box-shadow: none;
      border: none;
      background-color: transparent;
      font: inherit;
      transition: inherit;
      cursor: inherit;
      -webkit-appearance: none;

      /* Center-align and use tabular numbers for better alignment */
      text-align: center;
      font-variant-numeric: tabular-nums;

      /* Hide the number spinners in Firefox */
      -moz-appearance: textfield;

      /* Hide the number spinners in Chrome/Safari */
      &::-webkit-outer-spin-button,
      &::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
        display: none;
      }

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

    &:focus {
      outline: none;
    }
  }

  .start,
  .end {
    display: inline-flex;
    flex: 1;
    align-items: center;
    cursor: default;

    &::slotted(wa-icon) {
      color: var(--wa-color-neutral-on-quiet);
    }
  }

  .start {
    justify-content: start;
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  .end {
    justify-content: end;
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  /*
   * Steppers - horizontal layout with minus on start, plus on end
   */

  .stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1 / 1;
    height: calc(100% - var(--wa-form-control-border-width) * 2);
    flex: 0 0 auto;
    border: none;
    border-radius: calc(var(--wa-form-control-border-radius) - var(--wa-form-control-border-width) * 2);
    background: transparent;
    cursor: pointer;
    margin: var(--wa-form-control-border-width);
    padding: 0;
    font-size: inherit;
    transition-property: background-color, color;
    transition-duration: var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    &:focus {
      outline: none;
    }
  }

  :host([without-steppers]) .stepper {
    display: none;
  }
`;/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */var $=class extends z{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.hasSlotController=new F(this,"hint","label"),this.localize=new _(this),this.title="",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.size="m",this.appearance="outlined",this.pill=!1,this.label="",this.hint="",this.placeholder="",this.readonly=!1,this.required=!1,this.step=1,this.withoutSteppers=!1,this.inputmode="numeric",this.withLabel=!1,this.withHint=!1}static get validators(){return[...super.validators,X()]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(t){this._value!==t&&(this.valueHasChanged=!0,this._value=t)}handleSizeChange(){D(this.localName,this.size)}updateFormValue(t){if(t==null){this.setValue("",null);return}super.updateFormValue(t)}get isAtMin(){if(this.min===void 0)return!1;let t=parseFloat(this.value||"");return!isNaN(t)&&t<=this.min}get isAtMax(){if(this.max===void 0)return!1;let t=parseFloat(this.value||"");return!isNaN(t)&&t>=this.max}handleChange(t){this.value=this.input.value,this.relayNativeEvent(t,{bubbles:!0,composed:!0})}handleInput(){this.value=this.input.value}handleKeyDown(t){kt(t,this),(t.key==="ArrowUp"||t.key==="ArrowDown")&&requestAnimationFrame(()=>{this.value!==this.input.value&&(this.value=this.input.value)})}handleStepperPointerUp(t,e){if(this.disabled||this.readonly)return;let i=new InputEvent("beforeinput",{bubbles:!0,cancelable:!0,composed:!0});this.dispatchEvent(i),!i.defaultPrevented&&(t==="up"?this.input.stepUp():this.input.stepDown(),this.value!==this.input.value&&(this.value=this.input.value),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),e.pointerType!=="touch"&&this.input.focus())}handleStepperPointerDown(t){t.pointerType!=="touch"&&(t.preventDefault(),this.input.focus())}updated(t){super.updated(t),(t.has("value")||t.has("defaultValue"))&&(this.input&&this.value&&this.input.value!==this.value&&(this._value=this.input.value),this.customStates.set("blank",!this.value))}handleStepChange(){this.input.step=String(this.step),this.updateValidity()}focus(t){this.input.focus(t)}blur(){this.input.blur()}select(){this.input.select()}stepUp(){this.input.stepUp(),this.value!==this.input.value&&(this.value=this.input.value)}stepDown(){this.input.stepDown(),this.value!==this.input.value&&(this.value=this.input.value)}formResetCallback(){this.value=this.defaultValue,super.formResetCallback()}render(){let t=this.hasSlotController.test("label","withLabel"),e=this.hasSlotController.test("hint","withHint"),i=this.label?!0:!!t,r=this.hint?!0:!!e;return d`
      <label
        part="form-control-label label"
        class=${k({label:!0,"has-label":i})}
        for="input"
        aria-hidden=${i?"false":"true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base number-input" class="number-field">
        ${this.withoutSteppers?"":d`
              <button
                part="stepper stepper-decrement"
                class="stepper stepper-decrement"
                type="button"
                tabindex="-1"
                aria-label=${this.localize.term("decrement")}
                ?disabled=${this.disabled||this.readonly||this.isAtMin}
                @pointerdown=${this.handleStepperPointerDown}
                @pointerup=${a=>this.handleStepperPointerUp("down",a)}
              >
                <slot name="decrement-icon">
                  <wa-icon name="minus" library="system"></wa-icon>
                </slot>
              </button>
            `}

        <slot name="start" part="start" class="start"></slot>

        <input
          part="input"
          id="input"
          class="control"
          type="number"
          inputmode=${f(this.inputmode)}
          title=${this.title}
          name=${f(this.name)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${f(this.placeholder)}
          min=${f(this.min)}
          max=${f(this.max)}
          step=${f(this.step)}
          .value=${it(this.value??"")}
          autocomplete=${f(this.autocomplete)}
          ?autofocus=${this.autofocus}
          enterkeyhint=${f(this.enterkeyhint)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
        />

        <slot name="end" part="end" class="end"></slot>

        ${this.withoutSteppers?"":d`
              <button
                part="stepper stepper-increment"
                class="stepper stepper-increment"
                type="button"
                tabindex="-1"
                aria-label=${this.localize.term("increment")}
                ?disabled=${this.disabled||this.readonly||this.isAtMax}
                @pointerdown=${this.handleStepperPointerDown}
                @pointerup=${a=>this.handleStepperPointerUp("up",a)}
              >
                <slot name="increment-icon">
                  <wa-icon name="plus" library="system"></wa-icon>
                </slot>
              </button>
            `}
      </div>

      <slot
        id="hint"
        part="hint"
        name="hint"
        class=${k({"has-slotted":r})}
        aria-hidden=${r?"false":"true"}
        >${this.hint}</slot
      >
    `}};$.css=[A,H,ke];$.shadowRootOptions={...z.shadowRootOptions,delegatesFocus:!0};o([m("input")],$.prototype,"input",2);o([s()],$.prototype,"title",2);o([y()],$.prototype,"value",1);o([s({attribute:"value",reflect:!0})],$.prototype,"defaultValue",2);o([s({reflect:!0})],$.prototype,"size",2);o([v("size")],$.prototype,"handleSizeChange",1);o([s({reflect:!0})],$.prototype,"appearance",2);o([s({type:Boolean,reflect:!0})],$.prototype,"pill",2);o([s()],$.prototype,"label",2);o([s({attribute:"hint"})],$.prototype,"hint",2);o([s()],$.prototype,"placeholder",2);o([s({type:Boolean,reflect:!0})],$.prototype,"readonly",2);o([s({type:Boolean,reflect:!0})],$.prototype,"required",2);o([s({type:Number})],$.prototype,"min",2);o([s({type:Number})],$.prototype,"max",2);o([s()],$.prototype,"step",2);o([s({attribute:"without-steppers",type:Boolean})],$.prototype,"withoutSteppers",2);o([s()],$.prototype,"autocomplete",2);o([s({type:Boolean})],$.prototype,"autofocus",2);o([s()],$.prototype,"enterkeyhint",2);o([s()],$.prototype,"inputmode",2);o([s({attribute:"with-label",type:Boolean})],$.prototype,"withLabel",2);o([s({attribute:"with-hint",type:Boolean})],$.prototype,"withHint",2);o([v("step",{waitUntilFirstUpdate:!0})],$.prototype,"handleStepChange",1);$=o([E("wa-number-input")],$);$.disableWarning?.("change-in-update");/*! Copyright 2026 Fonticons, Inc. - https://webawesome.com/license */
