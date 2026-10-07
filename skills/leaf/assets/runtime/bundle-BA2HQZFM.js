import{ka as f}from"./bundle-AK64EAQI.js";import{Ra as m}from"./bundle-74S6MXBM.js";import{M as s,O as c,S as d}from"./bundle-QYO5KORU.js";import{html as u,render as w}from"/vendor/browser-runtime.js";var p="/media/",a=String.raw`!\[Pasted image\]\((${p}[^\s)]+)\)`,v=new RegExp(a,"g"),A=new RegExp(`(?:^|\\n\\n)${a}(?:\\n\\n${a})*(?![\\s\\S])`),P=e=>e.startsWith(p),$=e=>c?d(e):new URL(s(e.slice(1))).pathname;function C(e){let t=A.exec(e);return t?{text:e.slice(0,t.index),paths:Array.from(t[0].matchAll(v),r=>r[1])}:{text:e,paths:[]}}function S(e,t){if(!t.length)return e;let r=t.map(g=>`![Pasted image](${g})`).join(`

`);return e?e+`

`+r:r}var l=f({name:"Close image preview",title:"Close image preview (Esc)"});l.onclick=()=>i.close();function o(e){w(u`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        ${l}
      </div>
      <div class="lf-media-viewer-stage">
        ${e?u`<img src=${e.url} alt=${e.alt} />`:null}
      </div>
    `,i)}var i=document.createElement("dialog");i.id="lf-media-viewer";i.className="lf-ui lf-media-viewer";i.setAttribute("closedby","any");i.setAttribute("aria-modal","true");i.setAttribute("aria-labelledby","lf-media-viewer-title");o(null);var n=null,E=(e,t,r)=>{n=r,o({url:e,alt:t}),i.open||i.showModal(),l.focus({preventScroll:!0})};i.addEventListener("close",()=>{i.open||(o(null),n&&m(n),n=null)});document.addEventListener("click",e=>{let t=e.composedPath().find(r=>r instanceof Element&&r.matches(".lf-media-open[data-lf-media-url]"));t&&E(t.dataset.lfMediaUrl,t.querySelector("img")?.alt||"Pasted image",t)});export{P as a,$ as b,C as c,S as d,i as e};
