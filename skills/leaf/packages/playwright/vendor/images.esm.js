/*!
 * Viewer.js v1.15.2
 * https://fengyuanchen.github.io/viewerjs
 *
 * Copyright 2015-present Chen Fengyuan
 * Released under the MIT license
 *
 * Date: 2026-10-01T05:04:39.019Z
 */function zt(a,e){if(!(a instanceof e))throw new TypeError("Cannot call a class as a function")}function Ye(a,e){for(var t=0;t<e.length;t++){var i=e[t];i.enumerable=i.enumerable||!1,i.configurable=!0,"value"in i&&(i.writable=!0),Object.defineProperty(a,wt(i.key),i)}}function Dt(a,e,t){return e&&Ye(a.prototype,e),t&&Ye(a,t),Object.defineProperty(a,"prototype",{writable:!1}),a}function fe(a,e,t){return(e=wt(e))in a?Object.defineProperty(a,e,{value:t,enumerable:!0,configurable:!0,writable:!0}):a[e]=t,a}function Xe(a,e){var t=Object.keys(a);if(Object.getOwnPropertySymbols){var i=Object.getOwnPropertySymbols(a);e&&(i=i.filter(function(r){return Object.getOwnPropertyDescriptor(a,r).enumerable})),t.push.apply(t,i)}return t}function Ae(a){for(var e=1;e<arguments.length;e++){var t=arguments[e]!=null?arguments[e]:{};e%2?Xe(Object(t),!0).forEach(function(i){fe(a,i,t[i])}):Object.getOwnPropertyDescriptors?Object.defineProperties(a,Object.getOwnPropertyDescriptors(t)):Xe(Object(t)).forEach(function(i){Object.defineProperty(a,i,Object.getOwnPropertyDescriptor(t,i))})}return a}function It(a,e){if(typeof a!="object"||!a)return a;var t=a[Symbol.toPrimitive];if(t!==void 0){var i=t.call(a,e||"default");if(typeof i!="object")return i;throw new TypeError("@@toPrimitive must return a primitive value.")}return(e==="string"?String:Number)(a)}function wt(a){var e=It(a,"string");return typeof e=="symbol"?e:e+""}function Le(a){"@babel/helpers - typeof";return Le=typeof Symbol=="function"&&typeof Symbol.iterator=="symbol"?function(e){return typeof e}:function(e){return e&&typeof Symbol=="function"&&e.constructor===Symbol&&e!==Symbol.prototype?"symbol":typeof e},Le(a)}var We={backdrop:!0,button:!0,navbar:!0,navigation:!1,title:!0,toolbar:!0,className:"",container:"body",filter:null,fullscreen:!0,inheritedAttributes:["crossOrigin","decoding","isMap","loading","referrerPolicy","sizes","srcset","useMap"],initialCoverage:.9,initialViewIndex:0,inline:!1,autoplay:!0,interval:5e3,keyboard:!0,focus:!0,loading:!0,loop:!0,preload:!0,minWidth:200,minHeight:100,movable:!0,magnifier:!1,rotatable:!0,rotateOnGesture:!0,rotateOnTouch:!0,scalable:!0,zoomable:!0,zoomOnTouch:!0,zoomOnGesture:!0,zoomOnWheel:!0,slideOnTouch:!0,slideOnWheel:!0,toggleOnDblclick:!0,tooltip:!0,transition:!0,zIndex:2015,zIndexInline:0,zoomRatio:.1,minZoomRatio:.01,maxZoomRatio:100,url:"src",ready:null,show:null,shown:null,hide:null,hidden:null,view:null,viewed:null,move:null,moved:null,rotate:null,rotated:null,scale:null,scaled:null,zoom:null,zoomed:null,play:null,playing:null,stop:null},St='<div class="viewer-container" tabindex="-1" touch-action="none"><div class="viewer-canvas"></div><div class="viewer-magnifier" aria-hidden="true"><img class="viewer-magnifier-image" alt=""></div><div class="viewer-navigation" aria-hidden="true"><div class="viewer-prev" data-viewer-action="prev" role="button" aria-label="Previous"></div><div class="viewer-next" data-viewer-action="next" role="button" aria-label="Next"></div></div><div class="viewer-title" aria-hidden="true"></div><div class="viewer-toolbar" aria-hidden="true"></div><div class="viewer-navbar" aria-hidden="true"><ul class="viewer-list" role="navigation"></ul></div><div class="viewer-tooltip" role="alert" aria-hidden="true"></div><div class="viewer-button" data-viewer-action="mix" role="button" aria-hidden="true"></div><div class="viewer-player" aria-hidden="true"></div></div>',Ce=typeof window<"u"&&typeof window.document<"u",K=Ce?window:{},se=Ce&&K.document.documentElement?"ontouchstart"in K.document.documentElement:!1,pe=Ce?"PointerEvent"in K:!1,g="viewer",xt="move",yt="rotate",Oe="switch",ze="transform",Re="zoom",De="".concat(g,"-active"),kt="".concat(g,"-close"),Ie="".concat(g,"-fade"),Ve="".concat(g,"-fixed"),Nt="".concat(g,"-fullscreen"),He="".concat(g,"-fullscreen-exit"),G="".concat(g,"-hide"),At="".concat(g,"-hide-md-down"),Ct="".concat(g,"-hide-sm-down"),Mt="".concat(g,"-hide-xs-down"),W="".concat(g,"-in"),ge="".concat(g,"-invisible"),le="".concat(g,"-loading"),Lt="".concat(g,"-move"),qe="".concat(g,"-open"),ae="".concat(g,"-show"),A="".concat(g,"-transition"),te="click",_e="dblclick",je="dragstart",Ue="focusin",ke="keydown",U="load",re="error",Rt=se?"touchend touchcancel":"mouseup",Vt=se?"touchmove":"mousemove",_t=se?"touchstart":"mousedown",Be=pe?"pointerdown":_t,Ze=pe?"pointerenter":"mouseenter",Ge=pe?"pointerleave":"mouseleave",xe=pe?"pointermove":Vt,Ke=pe?"pointerup pointercancel":Rt,$e="resize",q="transitionend",Je="wheel",Qe="gesturestart gesturechange gestureend",et="ready",tt="show",it="shown",rt="hide",at="hidden",nt="view",me="viewed",ot="move",st="moved",lt="rotate",ht="rotated",vt="scale",ct="scaled",ut="zoom",ft="zoomed",gt="play",ye="playing",dt="stop",de="".concat(g,"Action"),be=/\s+/,Ee=["zoom-in","zoom-out","one-to-one","reset","prev","play","next","rotate-left","rotate-right","flip-horizontal","flip-vertical"];function he(a){return typeof a=="string"}var Ft={ctrl:"ctrlKey",shift:"shiftKey",alt:"altKey",meta:"metaKey"};function mt(a,e){return a?a===!0?!0:he(a)&&a.split("+").every(function(t){return e[Ft[t.trim().toLowerCase()]]}):!1}var Pt=Number.isNaN||K.isNaN;function I(a){return typeof a=="number"&&!Pt(a)}function j(a){return typeof a>"u"}function ve(a){return Le(a)==="object"&&a!==null}var Yt=Object.prototype.hasOwnProperty;function P(a){if(!ve(a))return!1;try{var e=a.constructor,t=e.prototype;return e&&t&&Yt.call(t,"isPrototypeOf")}catch{return!1}}function E(a){return typeof a=="function"}function D(a,e){if(a&&E(e))if(Array.isArray(a)||I(a.length)){var t=a.length,i;for(i=0;i<t&&e.call(a,a[i],i,a)!==!1;i+=1);}else ve(a)&&Object.keys(a).forEach(function(r){e.call(a,a[r],r,a)});return a}function Ne(a,e,t){D(t,function(i){var r=e.getAttribute(i);r!==null&&a.setAttribute(i,r)})}function V(a,e){var t=a.transition;return t&&t[e]!==!1}var _=Object.assign||function(e){for(var t=arguments.length,i=new Array(t>1?t-1:0),r=1;r<t;r++)i[r-1]=arguments[r];return ve(e)&&i.length>0&&i.forEach(function(n){ve(n)&&Object.keys(n).forEach(function(o){e[o]=n[o]})}),e},Xt=/^(?:width|height|left|top|marginLeft|marginTop)$/;function B(a,e){var t=a.style;D(e,function(i,r){Xt.test(r)&&I(i)&&(i+="px"),t[r]=i})}function Wt(a){return he(a)?a.replace(/&(?!amp;|quot;|#39;|lt;|gt;)/g,"&amp;").replace(/"/g,"&quot;").replace(/'/g,"&#39;").replace(/</g,"&lt;").replace(/>/g,"&gt;"):a}function oe(a,e){return!a||!e?!1:a.classList?a.classList.contains(e):a.className.split(be).indexOf(e)>-1}function f(a,e){if(!(!a||!e)){if(I(a.length)){D(a,function(i){f(i,e)});return}if(a.classList){a.classList.add(e);return}var t=a.className.trim();t?t.indexOf(e)<0&&(a.className="".concat(t," ").concat(e)):a.className=e}}function y(a,e){if(!(!a||!e)){if(I(a.length)){D(a,function(i){y(i,e)});return}if(a.classList){a.classList.remove(e);return}var t=a.className;t&&t.indexOf(e)>=0&&(a.className=t.split(be).filter(function(i){return i&&i!==e}).join(" "))}}function H(a,e,t){if(e){if(I(a.length)){D(a,function(i){H(i,e,t)});return}t?f(a,e):y(a,e)}}var Ht=/([a-z\d])([A-Z])/g;function Pe(a){return a.replace(Ht,"$1-$2").toLowerCase()}function ee(a,e){return ve(a[e])?a[e]:a.dataset?a.dataset[e]:a.getAttribute("data-".concat(Pe(e)))}function Fe(a,e,t){ve(t)?a[e]=t:a.dataset?a.dataset[e]=t:a.setAttribute("data-".concat(Pe(e)),t)}var Et=(function(){var a=!1;if(Ce){var e=!1,t=function(){},i=Object.defineProperty({},"once",{get:function(){return a=!0,e},set:function(n){e=n}});K.addEventListener("test",t,i),K.removeEventListener("test",t,i)}return a})();function z(a,e,t){var i=arguments.length>3&&arguments[3]!==void 0?arguments[3]:{},r=t;e.trim().split(be).forEach(function(n){if(!Et){var o=a.listeners;o&&o[n]&&o[n][t]&&(r=o[n][t],delete o[n][t],Object.keys(o[n]).length===0&&delete o[n],Object.keys(o).length===0&&delete a.listeners)}a.removeEventListener(n,r,i)})}function m(a,e,t){var i=arguments.length>3&&arguments[3]!==void 0?arguments[3]:{},r=t;e.trim().split(be).forEach(function(n){if(i.once&&!Et){var o=a.listeners,s=o===void 0?{}:o;r=function(){delete s[n][t],a.removeEventListener(n,r,i);for(var h=arguments.length,v=new Array(h),u=0;u<h;u++)v[u]=arguments[u];t.apply(a,v)},s[n]||(s[n]={}),s[n][t]&&a.removeEventListener(n,s[n][t],i),s[n][t]=r,a.listeners=s}a.addEventListener(n,r,i)})}function L(a,e,t,i){var r;return E(Event)&&E(CustomEvent)?r=new CustomEvent(e,Ae({bubbles:!0,cancelable:!0,detail:t},i)):(r=document.createEvent("CustomEvent"),r.initCustomEvent(e,!0,!0,t)),a.dispatchEvent(r)}function qt(a){var e=a.getBoundingClientRect();return{left:e.left+(window.pageXOffset-document.documentElement.clientLeft),top:e.top+(window.pageYOffset-document.documentElement.clientTop)}}function Se(a){var e=a.rotate,t=a.scaleX,i=a.scaleY,r=a.translateX,n=a.translateY,o=[];I(r)&&r!==0&&o.push("translateX(".concat(r,"px)")),I(n)&&n!==0&&o.push("translateY(".concat(n,"px)")),I(e)&&e!==0&&o.push("rotate(".concat(e,"deg)")),I(t)&&I(i)&&(t!==1||i!==1)&&(o.push("scaleX(".concat(t,")")),o.push("scaleY(".concat(i,")")));var s=o.length?o.join(" "):"none";return{WebkitTransform:s,msTransform:s,transform:s}}function jt(a){return he(a)?decodeURIComponent(a.replace(/^.*\//,"").replace(/[?&#].*$/,"")):""}var Me=K.navigator&&/Version\/\d+(\.\d+)+?\s+Safari/i.test(K.navigator.userAgent);function Tt(a,e,t){var i=document.createElement("img");if(a.naturalWidth&&!Me)return t(a.naturalWidth,a.naturalHeight),i;var r=document.body||document.documentElement;return i.onload=function(){t(i.width,i.height),Me||r.removeChild(i)},Ne(i,a,e.inheritedAttributes),i.src=a.src,Me||(i.style.cssText="left:0;max-height:none!important;max-width:none!important;min-height:0!important;min-width:0!important;opacity:0;position:absolute;top:0;z-index:-1;",r.appendChild(i)),i}function ne(a){switch(a){case 2:return Mt;case 3:return Ct;case 4:return At;default:return""}}function pt(a){var e=Ae({},a),t=[];return D(a,function(i,r){delete e[r],D(e,function(n){var o=Math.abs(i.startX-n.startX),s=Math.abs(i.startY-n.startY),l=Math.abs(i.endX-n.endX),h=Math.abs(i.endY-n.endY),v=Math.sqrt(o*o+s*s),u=Math.sqrt(l*l+h*h),p=(u-v)/v;t.push(p)})}),t.sort(function(i,r){return Math.abs(i)<Math.abs(r)}),t[0]}function bt(a){var e=Ae({},a),t=[];return D(a,function(i,r){delete e[r],D(e,function(n){var o=Math.atan2(n.startY-i.startY,n.startX-i.startX),s=Math.atan2(n.endY-i.endY,n.endX-i.endX),l=s-o;l>Math.PI?l-=Math.PI*2:l<-Math.PI&&(l+=Math.PI*2),t.push(l*180/Math.PI)})}),t.sort(function(i,r){return Math.abs(r)-Math.abs(i)}),t[0]||0}function Te(a,e){var t=a.pageX,i=a.pageY,r={endX:t,endY:i};return e?r:Ae({timeStamp:Date.now(),startX:t,startY:i},r)}function Ut(a){var e=0,t=0,i=0;return D(a,function(r){var n=r.startX,o=r.startY;e+=n,t+=o,i+=1}),e/=i,t/=i,{pageX:e,pageY:t}}var Bt={render:function(){this.initContainer(),this.initViewer(),this.initList(),this.renderViewer()},initBody:function(){var e=this.ownerDocument,t=e.body||e.documentElement;this.body=t,this.scrollbarWidth=window.innerWidth-e.documentElement.clientWidth,this.initialBodyPaddingRight=t.style.paddingRight,this.initialBodyComputedPaddingRight=window.getComputedStyle(t).paddingRight},initContainer:function(){this.containerData={width:window.innerWidth,height:window.innerHeight}},initViewer:function(){var e=this.options,t=this.parent,i;e.inline&&(i={width:Math.max(t.offsetWidth,e.minWidth),height:Math.max(t.offsetHeight,e.minHeight)},this.parentData=i),(this.fulled||!i)&&(i=this.containerData),this.viewerData=_({},i)},renderViewer:function(){this.options.inline&&!this.fulled&&B(this.viewer,this.viewerData)},initList:function(){var e=this,t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:this.index,i=this.element,r=this.options,n=this.list,o=[],s=P(r.navbar)?r.navbar:{},l=document.createElement("li");this.containerData||this.initContainer(),n.appendChild(l);var h=this.isNavbarVertical?l.offsetHeight+parseInt(window.getComputedStyle(l).marginTop,10):l.offsetWidth+parseInt(window.getComputedStyle(l).marginLeft,10);n.removeChild(l);var v=I(s.visibleItemCount)?Math.floor(s.visibleItemCount):Math.floor((this.isNavbarVertical?this.containerData.height:this.containerData.width)/h);v=Math.min(v,this.length);var u=v>0?Math.min(Math.max(0,t-Math.floor(v/2)),Math.max(0,this.length-v)):0,p=v>0?Math.min(this.length,u+v):this.length;if(n.innerHTML="",D(this.images,function(w,c){if(!(v>0&&(c<u||c>=p))){var T=w.src,O=w.alt||jt(T),b=e.getImageURL(w);if(T||b){var x=document.createElement("li"),S=document.createElement("img");Ne(S,w,r.inheritedAttributes),r.navbar&&(S.src=T||b),S.alt=O,S.setAttribute("data-original-url",b||T),x.setAttribute("data-index",c),x.setAttribute("data-viewer-action","view"),x.setAttribute("role","button"),r.keyboard&&x.setAttribute("tabindex",0),x.appendChild(S),n.appendChild(x),o.push(x)}}}),this.items=o,this.viewed){var d=this.getItem(this.index);d&&(f(d,De),d.setAttribute("aria-selected",!0))}D(o,function(w){var c=w.firstElementChild,T,O;Fe(c,"filled",!0),r.loading&&f(w,le),m(c,U,T=function(x){z(c,re,O),r.loading&&y(w,le),e.loadImage(x)},{once:!0}),m(c,re,O=function(){z(c,U,T),r.loading&&y(w,le)},{once:!0})}),V(r,"view")&&m(i,me,function(){f(n,A)},{once:!0})},getItem:function(e){var t;return D(this.items,function(i){return Number(ee(i,"index"))===e?(t=i,!1):!0}),t},renderList:function(){var e=this.index,t=this.getItem(e);if(t){var i=t.nextElementSibling,r=parseInt(window.getComputedStyle(i||t)[this.isNavbarVertical?"marginTop":"marginLeft"],10),n=this.isNavbarVertical?t.offsetHeight:t.offsetWidth,o=n+r;B(this.list,_(fe({},this.isNavbarVertical?"height":"width",o*this.items.length-r),Se(fe({},this.isNavbarVertical?"translateY":"translateX",((this.isNavbarVertical?this.viewerData.height:this.viewerData.width)-n)/2-(this.isNavbarVertical?t.offsetTop:t.offsetLeft)))))}},resetList:function(){var e=this.list;e.innerHTML="",y(e,A),B(e,_(fe({},this.isNavbarVertical?"height":"width",0),Se(fe({},this.isNavbarVertical?"translateY":"translateX",0))))},initImage:function(e){var t=this,i=this.options,r=this.image,n=this.viewerData,o=this.title,s=this.toolbar,l=this.navbar,h={top:0,right:0,bottom:0,left:0},v=this.imageData||{},u=o.offsetHeight,p;u&&(h.bottom=n.height-o.offsetTop),D([s,l],function(c){var T=c.offsetWidth,O=c.offsetHeight;!T&&!O||["top","right","bottom","left"].some(function(b){if(oe(c,"".concat(g,"-").concat(c===s?"toolbar":"navbar","-").concat(b))){var x=c.offsetLeft+T;return b==="top"?x=c.offsetTop+O:b==="right"?x=n.width-c.offsetLeft:b==="bottom"&&(x=n.height-c.offsetTop),h[b]=Math.max(h[b],x),!0}return!1})});var d=Math.max(n.width-h.left-h.right,h.left,h.right),w=Math.max(n.height-h.top-h.bottom,h.top,h.bottom);this.imageInitializing={abort:function(){p.onload=null}},p=Tt(r,i,function(c,T){var O=c/T,b=Math.max(0,Math.min(1,i.initialCoverage)),x=d,S=w;t.imageInitializing=!1,w*O>d?S=d/O:x=w*O,b=I(b)?b:.9,x=Math.min(x*b,c),S=Math.min(S*b,T);var C=h.left+(d-x)/2,M=h.top+(w-S)/2,k={left:C,top:M,x:C,y:M,width:x,height:S,oldRatio:1,ratio:x/c,aspectRatio:O,naturalWidth:c,naturalHeight:T},Y=_({},k);i.rotatable&&(k.rotate=v.rotate||0,Y.rotate=0),i.scalable&&(k.scaleX=v.scaleX||1,k.scaleY=v.scaleY||1,Y.scaleX=1,Y.scaleY=1),t.imageData=k,t.initialImageData=Y,e&&e()})},renderImage:function(e){var t=this,i=this.image,r=this.imageData;if(B(i,_({width:r.width,height:r.height,marginLeft:r.x,marginTop:r.y},Se(r))),this.magnifierPoint&&this.renderMagnifier(),e){var n=!1;if(this.viewing?n="view":this.moving?n="move":this.rotating?n="rotate":this.scaling?n="scale":this.zooming&&(n="zoom"),n&&V(this.options,n)&&oe(i,A)){var o=function(){t.imageRendering=!1,e()};this.imageRendering={abort:function(){z(i,q,o)}},m(i,q,o,{once:!0})}else e()}},resetImage:function(){var e=this.image;e&&(this.viewing&&this.viewing.abort(),e.parentNode.removeChild(e),this.image=null,this.title.innerHTML="")}},Zt={bind:function(){var e=this.options,t=this.viewer,i=this.canvas,r=this.ownerDocument;m(t,te,this.onClick=this.click.bind(this)),m(t,je,this.onDragStart=this.dragstart.bind(this)),m(t,Ze,this.onMagnifyEnter=this.magnify.bind(this)),m(t,xe,this.onMagnify=this.magnify.bind(this)),m(t,Ge,this.onMagnifierLeave=this.hideMagnifier.bind(this)),m(i,Be,this.onPointerDown=this.pointerdown.bind(this)),m(r,xe,this.onPointerMove=this.pointermove.bind(this)),m(r,Ke,this.onPointerUp=this.pointerup.bind(this)),m(r,ke,this.onKeyDown=this.keydown.bind(this)),m(window,$e,this.onResize=this.resize.bind(this)),(e.zoomable&&e.zoomOnWheel||e.slideOnWheel)&&m(t,Je,this.onWheel=this.wheel.bind(this),{passive:!1,capture:!0}),(e.zoomable&&e.zoomOnGesture||e.rotatable&&e.rotateOnGesture)&&m(t,Qe,this.onGesture=this.gesture.bind(this),{passive:!1}),e.toggleOnDblclick&&m(i,_e,this.onDblclick=this.dblclick.bind(this))},unbind:function(){var e=this.options,t=this.viewer,i=this.canvas,r=this.ownerDocument;z(t,te,this.onClick),z(t,je,this.onDragStart),z(t,Ze,this.onMagnifyEnter),z(t,xe,this.onMagnify),z(t,Ge,this.onMagnifierLeave),z(i,Be,this.onPointerDown),z(r,xe,this.onPointerMove),z(r,Ke,this.onPointerUp),z(r,ke,this.onKeyDown),z(window,$e,this.onResize),(e.zoomable&&e.zoomOnWheel||e.slideOnWheel)&&z(t,Je,this.onWheel,{passive:!1,capture:!0}),(e.zoomable&&e.zoomOnGesture||e.rotatable&&e.rotateOnGesture)&&z(t,Qe,this.onGesture,{passive:!1}),e.toggleOnDblclick&&z(i,_e,this.onDblclick)}},Gt={click:function(e){var t=this.options,i=this.imageData,r=e.target,n=ee(r,de);switch(!n&&r.localName==="img"&&r.parentElement.localName==="li"&&(r=r.parentElement,n=ee(r,de)),se&&e.isTrusted&&r===this.canvas&&clearTimeout(this.clickCanvasTimeout),this.actionEvent=e,n){case"mix":this.played?this.stop():t.inline?this.fulled?this.exit():this.full():this.hide();break;case"hide":this.pointerMoved||this.hide();break;case"view":this.view(ee(r,"index"));break;case"zoom-in":this.zoom(.1,!0);break;case"zoom-out":this.zoom(-.1,!0);break;case"one-to-one":this.toggle();break;case"reset":this.reset();break;case"prev":this.prev(t.loop);break;case"play":this.play(t.fullscreen);break;case"next":this.next(t.loop);break;case"rotate-left":this.rotate(-90);break;case"rotate-right":this.rotate(90);break;case"flip-horizontal":this.scaleX(-i.scaleX||-1);break;case"flip-vertical":this.scaleY(-i.scaleY||-1);break;default:this.played&&this.stop()}},dblclick:function(e){e.preventDefault(),this.viewed&&e.target===this.image&&(se&&e.isTrusted&&clearTimeout(this.doubleClickImageTimeout),this.actionEvent=e.isTrusted?e:e.detail&&e.detail.originalEvent,this.toggle())},load:function(){var e=this;this.timeout&&(clearTimeout(this.timeout),this.timeout=!1);var t=this.element,i=this.options,r=this.image,n=this.index,o=this.viewerData;y(r,ge),i.loading&&y(this.canvas,le),r.style.cssText="height:0;"+"margin-left:".concat(o.width/2,"px;")+"margin-top:".concat(o.height/2,"px;")+"max-width:none!important;position:relative;width:0;",this.initImage(function(){H(r,Lt,i.movable),H(r,A,V(i,"view")),e.renderImage(function(){e.viewed=!0,e.viewing=!1,setTimeout(function(){H(r,A,i.transition)},300),E(i.viewed)&&m(t,me,i.viewed,{once:!0}),L(t,me,{originalImage:e.images[n],index:n,image:r,originalEvent:e.viewOriginalEvent||null},{cancelable:!1}),e.viewOriginalEvent=null})})},loadImage:function(e){var t=e.target,i=t.parentNode,r=i.offsetWidth||30,n=i.offsetHeight||50,o=!!ee(t,"filled");Tt(t,this.options,function(s,l){var h=s/l,v=r,u=n;n*h>r?o?v=n*h:u=r/h:o?u=r/h:v=n*h,B(t,_({width:v,height:u},Se({translateX:(r-v)/2,translateY:(n-u)/2})))})},keydown:function(e){var t=this.options;if(t.keyboard){var i=e.keyCode||e.which||e.charCode;if(this.actionEvent=e,i===13&&this.viewer.contains(e.target)&&this.click(e),!!this.fulled)switch(i){case 27:this.played?this.stop():t.inline?this.fulled&&this.exit():this.hide();break;case 32:this.played&&this.stop();break;case 37:this.played&&this.playing?this.playing.prev():this.prev(t.loop);break;case 38:e.preventDefault(),this.zoom(t.zoomRatio,!0);break;case 39:this.played&&this.playing?this.playing.next():this.next(t.loop);break;case 40:e.preventDefault(),this.zoom(-t.zoomRatio,!0);break;case 48:case 49:e.ctrlKey&&(e.preventDefault(),this.toggle());break}}},dragstart:function(e){e.target.localName==="img"&&e.preventDefault()},magnify:function(e){if(e.changedTouches||e.pointerType&&e.pointerType!=="mouse"){this.hideMagnifier();return}this.magnifierPoint={clientX:e.clientX,clientY:e.clientY},this.renderMagnifier()},renderMagnifier:function(){var e=this.options,t=this.imageData,i=this.magnifier,r=this.magnifierImage,n=this.viewer,o=P(e.magnifier)?e.magnifier:{},s=this.magnifierPoint;if(!e.magnifier||!this.fulled||!this.viewed||!i||!r||!s){this.hideMagnifier();return}var l=Math.max(1,Number(o.size)||100),h=Math.max(1,Number(o.zoomRatio)||2),v=Number(o.opacity),u=n.getBoundingClientRect(),p=s.clientX-u.left,d=s.clientY-u.top,w=this.image.currentSrc||this.image.src,c=this.image.getBoundingClientRect();if(s.clientX<c.left||s.clientX>c.right||s.clientY<c.top||s.clientY>c.bottom){this.hideMagnifier();return}var T=I(t.scaleX)?t.scaleX:1,O=I(t.scaleY)?t.scaleY:1,b=(t.rotate||0)*Math.PI/180,x=Math.cos(b),S=Math.sin(b),C=x*T,M=S*T,k=-S*O,Y=x*O,$=T*O;if($===0){this.hideMagnifier();return}var we=t.x+t.width/2,ce=t.y+t.height/2,J=(Y*(p-we)-k*(d-ce))/$,N=(-M*(p-we)+C*(d-ce))/$,Q=J+t.width/2,R=N+t.height/2,F=t.width*h,X=t.height*h,ie=C*(Q*h-F/2)+k*(R*h-X/2),ue=M*(Q*h-F/2)+Y*(R*h-X/2);this.magnifierSourcePoint={x:Q,y:R},i.style.width="".concat(l,"px"),i.style.height="".concat(l,"px"),i.style.opacity="".concat(Math.max(0,Math.min(1,I(v)?v:1))),r.src=w,r.style.width="".concat(F,"px"),r.style.height="".concat(X,"px"),r.style.left="".concat(l/2-F/2-ie,"px"),r.style.top="".concat(l/2-X/2-ue,"px"),r.style.transform="rotate(".concat(t.rotate||0,"deg) scaleX(").concat(T,") scaleY(").concat(O,")"),i.removeAttribute("aria-hidden"),f(i,"viewer-show")},hideMagnifier:function(){this.magnifier&&(y(this.magnifier,"viewer-show"),this.magnifier.setAttribute("aria-hidden",!0),this.magnifierPoint=null)},pointerdown:function(e){var t=this.options,i=this.pointers,r=this.imageData,n=e.buttons,o=e.button,s=Object.keys(i).length===0;if(this.pointerMoved=!1,!(!this.viewed||this.showing||this.viewing||this.hiding||(e.type==="mousedown"||e.type==="pointerdown"&&e.pointerType==="mouse")&&(I(n)&&n!==1||I(o)&&o!==0||e.ctrlKey))){e.preventDefault(),e.changedTouches?D(e.changedTouches,function(h){i[h.identifier]=Te(h)}):i[e.pointerId||0]=Te(e);var l=t.movable?xt:!1;(t.zoomable&&t.zoomOnTouch||t.rotatable&&t.rotateOnTouch)&&Object.keys(i).length>1?l=ze:t.slideOnTouch&&(e.pointerType==="touch"||e.type==="touchstart")&&this.isSwitchable()&&(l=Oe),l&&y(this.image,A),s&&(this.rotateThreshold=r.rotate===0),this.switching=l===Oe?{x:r.x,y:r.y}:!1,this.action=l}},pointermove:function(e){var t=this.pointers,i=this.action;!this.viewed||!i||(e.preventDefault(),e.changedTouches?D(e.changedTouches,function(r){_(t[r.identifier]||{},Te(r,!0))}):_(t[e.pointerId||0]||{},Te(e,!0)),this.change(e),y(this.image,A))},pointerup:function(e){var t=this,i=this.options,r=this.action,n=this.pointers,o=this.viewerData,s;if(e.changedTouches?D(e.changedTouches,function(d){s=n[d.identifier],delete n[d.identifier]}):(s=n[e.pointerId||0],delete n[e.pointerId||0]),Object.keys(n).length===0){if(this.rotateThreshold){var l=Math.round(this.imageData.rotate/90)*90;l!==this.imageData.rotate&&(this.actionEvent=e,this.rotateTo(l))}this.rotateThreshold=!1}if(r){e.preventDefault();var h=r===ze?V(i,Re)||V(i,yt):V(i,r);if(H(this.image,A,h),r===Oe&&this.switching){var v=this.imageData,u=this.switching,p=v.x-u.x;this.switching=!1,this.actionEvent=e,Math.abs(p)>o.width/2?p>0?this.prev(i.loop):this.next(i.loop):(v.x!==u.x||v.y!==u.y)&&this.moveTo(u.x,u.y)}this.action=!1,se&&r!==Re&&r!==ze&&s&&Date.now()-s.timeStamp<500&&(clearTimeout(this.clickCanvasTimeout),clearTimeout(this.doubleClickImageTimeout),i.toggleOnDblclick&&this.viewed&&e.target===this.image?this.pointerMoved?this.imageClicked=!1:this.imageClicked?(this.imageClicked=!1,this.doubleClickImageTimeout=setTimeout(function(){L(t.image,_e,{originalEvent:e})},50)):(this.imageClicked=!0,this.doubleClickImageTimeout=setTimeout(function(){t.imageClicked=!1},500)):(this.imageClicked=!1,i.backdrop&&i.backdrop!=="static"&&e.target===this.canvas&&(this.clickCanvasTimeout=setTimeout(function(){L(t.canvas,te,{originalEvent:e})},50))))}},resize:function(){var e=this;if(!(!this.isShown||this.hiding)){this.fulled&&(this.close(),this.initBody(),this.open()),this.initContainer(),this.initViewer(),this.renderViewer();var t=P(this.options.navbar)?this.options.navbar:{};if(j(t.visibleItemCount)&&this.initList(this.index),this.renderList(),this.viewed&&this.initImage(function(){e.renderImage()}),this.played){if(this.options.fullscreen&&this.fulled&&!(document.fullscreenElement||document.webkitFullscreenElement||document.mozFullScreenElement||document.msFullscreenElement)){this.stop();return}D(this.player.getElementsByTagName("img"),function(i){m(i,U,e.loadImage.bind(e),{once:!0}),L(i,U)})}}},wheel:function(e){var t=this,i=this.options,r=this.navbar;if(this.viewed&&(e.preventDefault(),!this.gesturing&&!this.wheeling)){this.wheeling=!0,setTimeout(function(){t.wheeling=!1},50);var n=1;e.deltaY?n=e.deltaY>0?1:-1:e.wheelDelta?n=-e.wheelDelta/120:e.detail&&(n=e.detail>0?1:-1);var o=r&&r.contains(e.target),s=!o&&i.zoomable&&mt(i.zoomOnWheel,e);if(s){var l=Number(i.zoomRatio)||.1;this.actionEvent=e,this.zoom(-n*l,!0);return}mt(i.slideOnWheel,e)&&(this.actionEvent=e,n>0?this.next(i.loop):n<0&&this.prev(i.loop))}},gesture:function(e){var t=this.options;if(!(!this.viewed||!t.zoomOnGesture&&!t.rotateOnGesture))switch(e.preventDefault(),e.type){case"gesturestart":this.gesturing=!0,this.gestureScale=e.scale||1,this.gestureRotation=e.rotation||0;break;case"gesturechange":{var i=e.scale||1,r=i/(this.gestureScale||1),n=Number(e.rotation),o=n-(this.gestureRotation||0);this.gestureScale=i,t.zoomable&&t.zoomOnGesture&&r!==1&&(this.actionEvent=e,this.zoom(r>=1?r-1:1-1/r)),t.rotatable&&t.rotateOnGesture&&I(n)&&(this.gestureRotation=n,o!==0&&(this.actionEvent=e,this.rotate(o)));break}case"gestureend":if(t.rotatable&&t.rotateOnGesture){var s=Math.round(this.imageData.rotate/90)*90;s!==this.imageData.rotate&&(this.actionEvent=e,this.rotateTo(s))}this.gesturing=!1,this.gestureScale=1,this.gestureRotation=0;break}}},Kt={show:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1,t=this.element,i=this.options;if(i.inline||this.showing||this.isShown||this.showing)return this;if(!this.ready)return this.build(),this.ready&&this.show(e),this;var r=this.actionEvent||this.showOriginalEvent||this.viewOriginalEvent||null;if(this.actionEvent=null,this.showOriginalEvent=r,E(i.show)&&m(t,tt,i.show,{once:!0}),L(t,tt,{originalEvent:r})===!1||!this.ready)return this;this.hiding&&this.transitioning.abort(),this.showing=!0,this.open();var n=this.viewer;if(y(n,G),n.setAttribute("role","dialog"),n.setAttribute("aria-labelledby",this.title.id),n.setAttribute("aria-modal",!0),n.removeAttribute("aria-hidden"),V(i,"show")&&!e){var o=this.shown.bind(this);this.transitioning={abort:function(){z(n,q,o),y(n,W)}},f(n,A),n.initialOffsetWidth=n.offsetWidth,m(n,q,o,{once:!0}),f(n,W)}else f(n,W),this.shown();return this},hide:function(){var e=this,t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1,i=this.element,r=this.options;if(r.inline||this.hiding||!(this.isShown||this.showing))return this;var n=this.actionEvent||this.hideOriginalEvent||null;if(this.actionEvent=null,this.hideOriginalEvent=n,E(r.hide)&&m(i,rt,r.hide,{once:!0}),L(i,rt,{originalEvent:n})===!1||this.destroyed)return this;this.showing&&this.transitioning.abort(),this.hiding=!0,this.played?this.stop():this.viewing&&this.viewing.abort();var o=this.viewer,s=this.image,l=function(){y(o,W),e.hidden()};if(V(r,"hide")&&!t){var h=function(p){p&&p.target===o&&(z(o,q,h),e.hidden())},v=function(){oe(o,A)?(m(o,q,h),y(o,W)):l()};this.transitioning={abort:function(){e.viewed&&oe(s,A)?z(s,q,v):oe(o,A)&&z(o,q,h)}},this.viewed&&oe(s,A)?(m(s,q,v,{once:!0}),this.zoomable=!0,this.zoomTo(0,!1)):v()}else l();return this},view:function(){var e=this,t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:this.options.initialViewIndex,i=this.index;if(t=Number(t)||0,this.hiding||this.played||t<0||t>=this.length||this.viewed&&t===i)return this;var r=this.actionEvent||this.viewOriginalEvent||null;if(this.actionEvent=null,this.viewOriginalEvent=r,!this.isShown)return this.index=t,this.show();this.viewing&&this.viewing.abort();var n=this.element,o=this.options,s=this.title,l=this.canvas,h=this.getItem(t);h||(this.initList(t),h=this.getItem(t));var v=h.querySelector("img"),u=ee(v,"originalUrl"),p=v.getAttribute("alt"),d=document.createElement("img");if(Ne(d,v,o.inheritedAttributes),d.src=u,d.alt=p,E(o.view)&&m(n,nt,o.view,{once:!0}),L(n,nt,{originalImage:this.images[t],index:t,image:d,originalEvent:r})===!1||!this.isShown||this.hiding||this.played)return this;this.hideMagnifier();var w=this.getItem(i);w&&(y(w,De),w.removeAttribute("aria-selected")),f(h,De),h.setAttribute("aria-selected",!0),o.focus&&h.focus(),this.image=d,this.viewed=!1,this.index=t,this.imageData={},f(d,ge),o.loading&&f(l,le),l.innerHTML="",l.appendChild(d),this.renderList(),s.innerHTML="";var c=function(){var b=e.imageData,x=Array.isArray(o.title)?o.title[1]:o.title;if(s.innerHTML=Wt(E(x)?x.call(e,d,b):"".concat(p," (").concat(b.naturalWidth," \xD7 ").concat(b.naturalHeight,")")),o.preload){var S=t<i?-1:1,C=t+S;if((C<0||C>=e.length)&&(o.loop?C=S>0?0:e.length-1:C=-1),C!==t){var M=e.images[C],k=document.createElement("img");Ne(k,M,o.inheritedAttributes),k.src=e.getImageURL(M)||M.src}}};m(n,me,c,{once:!0});var T=function(){var b=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1,x,S,C=function(){z(d,U,x),z(d,re,S),e.timeout&&(clearTimeout(e.timeout),e.timeout=!1)};e.viewing={abort:function(){z(n,me,c),d.complete?e.imageRendering?e.imageRendering.abort():e.imageInitializing&&e.imageInitializing.abort():(d.src="",C())}},d.complete?e.load():(m(d,U,x=function(){C(),e.load()},{once:!0}),m(d,re,S=function(){if(C(),!b){var k=v.src;if(k&&k!==d.src){d.src=k,T(!0);return}}y(d,ge),o.loading&&y(e.canvas,le)},{once:!0}),e.timeout&&clearTimeout(e.timeout),e.timeout=setTimeout(function(){y(d,ge),e.timeout=!1},1e3))};return T(),this},prev:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1,t=this.index-1;return t<0&&(t=e?this.length-1:0),this.view(t),this},next:function(){var e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1,t=this.length-1,i=this.index+1;return i>t&&(i=e?0:t),this.view(i),this},move:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:e,i=this.imageData;return this.moveTo(j(e)?e:i.x+Number(e),j(t)?t:i.y+Number(t)),this},moveTo:function(e){var t=this,i=arguments.length>1&&arguments[1]!==void 0?arguments[1]:e,r=this.element,n=this.options,o=this.imageData;if(e=Number(e),i=Number(i),this.viewed&&!this.played&&n.movable){var s=o.x,l=o.y,h=!1;if(I(e)?h=!0:e=s,I(i)?h=!0:i=l,h){var v=this.actionEvent||null;if(this.actionEvent=null,E(n.move)&&m(r,ot,n.move,{once:!0}),L(r,ot,{x:e,y:i,oldX:s,oldY:l,originalEvent:v})===!1)return this;o.x=e,o.y=i,o.left=e,o.top=i,H(this.image,A,V(n,"move")),this.moving=!0,this.renderImage(function(){t.moving=!1,E(n.moved)&&m(r,st,n.moved,{once:!0}),L(r,st,{x:e,y:i,oldX:s,oldY:l,originalEvent:v},{cancelable:!1})})}}return this},rotate:function(e){return this.rotateTo((this.imageData.rotate||0)+Number(e)),this},rotateTo:function(e){var t=this,i=this.element,r=this.options,n=this.imageData;if(e=Number(e),I(e)&&this.viewed&&!this.played&&r.rotatable){var o=n.rotate,s=this.actionEvent||null;if(this.actionEvent=null,E(r.rotate)&&m(i,lt,r.rotate,{once:!0}),L(i,lt,{degree:e,oldDegree:o,originalEvent:s})===!1)return this;n.rotate=e,H(this.image,A,V(r,"rotate")),this.rotating=!0,this.renderImage(function(){t.rotating=!1,E(r.rotated)&&m(i,ht,r.rotated,{once:!0}),L(i,ht,{degree:e,oldDegree:o,originalEvent:s},{cancelable:!1})})}return this},scaleX:function(e){return this.scale(e,this.imageData.scaleY),this},scaleY:function(e){return this.scale(this.imageData.scaleX,e),this},scale:function(e){var t=this,i=arguments.length>1&&arguments[1]!==void 0?arguments[1]:e,r=this.element,n=this.options,o=this.imageData;if(e=Number(e),i=Number(i),this.viewed&&!this.played&&n.scalable){var s=o.scaleX,l=o.scaleY,h=!1;if(I(e)?h=!0:e=s,I(i)?h=!0:i=l,h){var v=this.actionEvent||null;if(this.actionEvent=null,E(n.scale)&&m(r,vt,n.scale,{once:!0}),L(r,vt,{scaleX:e,scaleY:i,oldScaleX:s,oldScaleY:l,originalEvent:v})===!1)return this;o.scaleX=e,o.scaleY=i,H(this.image,A,V(n,"scale")),this.scaling=!0,this.renderImage(function(){t.scaling=!1,E(n.scaled)&&m(r,ct,n.scaled,{once:!0}),L(r,ct,{scaleX:e,scaleY:i,oldScaleX:s,oldScaleY:l,originalEvent:v},{cancelable:!1})})}}return this},zoom:function(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!1,i=arguments.length>2&&arguments[2]!==void 0?arguments[2]:null,r=this.imageData;return e=Number(e),e<0?e=1/(1-e):e=1+e,this.zoomTo(r.width*e/r.naturalWidth,t,i),this},zoomTo:function(e){var t=this,i=arguments.length>1&&arguments[1]!==void 0?arguments[1]:!1,r=arguments.length>2&&arguments[2]!==void 0?arguments[2]:null,n=this.element,o=this.options,s=this.pointers,l=this.imageData,h=this.zoomable,v=l.x,u=l.y,p=l.width,d=l.height,w=l.naturalWidth,c=l.naturalHeight;if(this.zoomable=!1,e=Math.max(0,e),I(e)&&this.viewed&&!this.played&&(h||o.zoomable)){if(!h){var T=Math.max(.01,E(o.minZoomRatio)?o.minZoomRatio.call(this,this.image,l):o.minZoomRatio),O=Math.min(100,E(o.maxZoomRatio)?o.maxZoomRatio.call(this,this.image,l):o.maxZoomRatio);e=Math.min(Math.max(e,T),O)}var b=this.actionEvent||null;if(this.actionEvent=null,b&&b.type!==te)switch(b.type){case"wheel":o.zoomRatio>=.055&&e>.95&&e<1.05&&(e=1);break;case"pointermove":case"touchmove":case"mousemove":e>.99&&e<1.01&&(e=1);break}var x=w*e,S=c*e,C=x-p,M=S-d,k=l.ratio;if(E(o.zoom)&&m(n,ut,o.zoom,{once:!0}),L(n,ut,{ratio:e,oldRatio:k,originalEvent:b})===!1)return this;if(this.zooming=!0,b&&b.type!==te){var Y=qt(this.viewer),$=s&&Object.keys(s).length>0?Ut(s):{pageX:b.pageX,pageY:b.pageY};l.x-=C*(($.pageX-Y.left-v)/p),l.y-=M*(($.pageY-Y.top-u)/d)}else P(r)&&I(r.x)&&I(r.y)?(l.x-=C*((r.x-v)/p),l.y-=M*((r.y-u)/d)):(l.x-=C/2,l.y-=M/2);l.left=l.x,l.top=l.y,l.width=x,l.height=S,l.oldRatio=k,l.ratio=e,H(this.image,A,V(o,"zoom")),this.renderImage(function(){t.zooming=!1,E(o.zoomed)&&m(n,ft,o.zoomed,{once:!0}),L(n,ft,{ratio:e,oldRatio:k,originalEvent:b},{cancelable:!1})}),i&&this.tooltip()}return this},play:function(){var e=this,t=arguments.length>0&&arguments[0]!==void 0?arguments[0]:!1;if(!this.isShown||this.played)return this;var i=this.element,r=this.options,n=this.actionEvent||null;if(this.actionEvent=null,E(r.play)&&m(i,gt,r.play,{once:!0}),L(i,gt,{originalEvent:n})===!1)return this;var o=this.player,s=this.loadImage.bind(this),l=[],h=0,v=0;if(this.played=!0,this.onLoadWhenPlay=s,t&&this.requestFullscreen(t),f(o,ae),o.removeAttribute("aria-hidden"),D(this.images,function(d,w){var c=document.createElement("img");c.src=e.getImageURL(d)||d.src,c.alt=d.alt||"",c.referrerPolicy=d.referrerPolicy,h+=1,f(c,Ie),H(c,A,V(r,"play")),w===e.index&&(f(c,W),v=w),l.push(c),m(c,U,s,{once:!0}),o.appendChild(c)}),I(r.interval)&&r.interval>0){var u=function(){clearTimeout(e.playing.timeout);var w=e.actionEvent||null;e.actionEvent=null;var c=v-1;if(c=c>=0?c:h-1,E(r.playing)&&m(i,ye,r.playing,{once:!0}),L(i,ye,{originalImage:e.images[c],index:c,image:l[c],originalEvent:w})===!1){e.playing.timeout=r.autoplay?setTimeout(u,r.interval):null;return}y(l[v],W),v=c,f(l[v],W),e.playing.timeout=r.autoplay?setTimeout(u,r.interval):null},p=function(){clearTimeout(e.playing.timeout);var w=e.actionEvent||null;e.actionEvent=null;var c=v+1;if(c=c<h?c:0,E(r.playing)&&m(i,ye,r.playing,{once:!0}),L(i,ye,{originalImage:e.images[c],index:c,image:l[c],originalEvent:w})===!1){e.playing.timeout=r.autoplay?setTimeout(p,r.interval):null;return}y(l[v],W),v=c,f(l[v],W),e.playing.timeout=r.autoplay?setTimeout(p,r.interval):null};h>1&&(this.playing={prev:u,next:p,timeout:r.autoplay?setTimeout(p,r.interval):null})}return this},stop:function(){var e=this;if(!this.played)return this;var t=this.element,i=this.options,r=this.actionEvent||null;if(this.actionEvent=null,E(i.stop)&&m(t,dt,i.stop,{once:!0}),L(t,dt,{originalEvent:r})===!1)return this;var n=this.player;return clearTimeout(this.playing.timeout),this.playing=!1,this.played=!1,D(n.getElementsByTagName("img"),function(o){z(o,U,e.onLoadWhenPlay)}),y(n,ae),n.setAttribute("aria-hidden",!0),n.innerHTML="",this.exitFullscreen(),this},full:function(){var e=this,t=this.options,i=this.viewer,r=this.image,n=this.list;return!this.isShown||this.played||this.fulled||!t.inline?this:(this.fulled=!0,this.open(),f(this.button,He),y(n,A),this.viewed&&y(r,A),f(i,Ve),i.setAttribute("role","dialog"),i.setAttribute("aria-labelledby",this.title.id),i.setAttribute("aria-modal",!0),i.removeAttribute("style"),B(i,{zIndex:t.zIndex}),t.focus&&this.enforceFocus(),this.initContainer(),this.viewerData=_({},this.containerData),this.renderList(),this.viewed&&this.initImage(function(){e.renderImage()}),this)},exit:function(){var e=this,t=this.options,i=this.viewer,r=this.image,n=this.list;return!this.isShown||this.played||!this.fulled||!t.inline?this:(this.fulled=!1,this.close(),y(this.button,He),y(n,A),this.viewed&&y(r,A),t.focus&&this.clearEnforceFocus(),i.removeAttribute("role"),i.removeAttribute("aria-labelledby"),i.removeAttribute("aria-modal"),y(i,Ve),B(i,{zIndex:t.zIndexInline}),this.viewerData=_({},this.parentData),this.renderViewer(),this.renderList(),this.viewed&&this.initImage(function(){e.renderImage()}),this)},tooltip:function(){var e=this,t=this.options,i=this.tooltipBox,r=this.imageData;return!this.viewed||this.played||!t.tooltip?this:(i.textContent="".concat(Math.round(r.ratio*100),"%"),this.tooltipping?clearTimeout(this.tooltipping):V(t,"tooltip")?(this.fading&&L(i,q),f(i,ae),f(i,Ie),f(i,A),i.removeAttribute("aria-hidden"),i.initialOffsetWidth=i.offsetWidth,f(i,W)):(f(i,ae),i.removeAttribute("aria-hidden")),this.tooltipping=setTimeout(function(){V(t,"tooltip")?(m(i,q,function(){y(i,ae),y(i,Ie),y(i,A),i.setAttribute("aria-hidden",!0),e.fading=!1},{once:!0}),y(i,W),e.fading=!0):(y(i,ae),i.setAttribute("aria-hidden",!0)),e.tooltipping=!1},1e3),this)},toggle:function(){return this.imageData.ratio===1?this.zoomTo(this.imageData.oldRatio,!0):this.zoomTo(1,!0),this},reset:function(){return this.viewed&&!this.played&&(this.imageData=_({},this.initialImageData),this.renderImage()),this},update:function(e){var t=this,i=this.element,r=this.options,n=this.isImg;if(P(e)&&_(r,e),n&&!i.parentNode)return this.destroy();var o=[];if(D(n?[i]:i.querySelectorAll("img"),function(v){E(r.filter)?r.filter.call(t,v)&&o.push(v):t.getImageURL(v)&&o.push(v)}),!o.length)return this;if(this.images=o,this.length=o.length,this.ready){var s=[];if(D(this.items,function(v){var u=v.querySelector("img"),p=Number(ee(v,"index")),d=o[p];d&&u?(d.src!==u.src||d.alt!==u.alt)&&s.push(p):s.push(p)}),B(this.list,{width:"auto"}),this.initList(),this.isShown)if(this.length){if(this.viewed){var l=s.indexOf(this.index);if(l>=0)this.viewed=!1,this.view(Math.max(Math.min(this.index-l,this.length-1),0));else{var h=this.getItem(this.index);f(h,De),h.setAttribute("aria-selected",!0)}}}else this.image=null,this.viewed=!1,this.index=0,this.imageData={},this.canvas.innerHTML="",this.title.innerHTML=""}else this.build();return this},destroy:function(){var e=this.element,t=this.options;return e[g]?(this.destroyed=!0,this.ready?(this.played&&this.stop(),t.inline?(this.fulled&&this.exit(),this.unbind()):this.isShown?(this.viewing&&(this.imageRendering?this.imageRendering.abort():this.imageInitializing&&this.imageInitializing.abort()),this.hiding&&this.transitioning.abort(),this.hidden()):this.showing&&(this.transitioning.abort(),this.hidden()),this.ready=!1,this.viewer.parentNode.removeChild(this.viewer)):t.inline&&(this.delaying?this.delaying.abort():this.initializing&&this.initializing.abort()),t.inline||(z(e,te,this.onElementClick),z(e,ke,this.onElementKeyDown)),e[g]=void 0,this):this}},$t={getImageURL:function(e){var t=this.options.url;return he(t)?t=e.getAttribute(t):E(t)?t=t.call(this,e):t="",t},enforceFocus:function(){var e=this;this.clearEnforceFocus(),m(document,Ue,this.onFocusin=function(t){var i=e.viewer,r=t.target;if(!(r===document||r===i||i.contains(r))){for(;r;){if(r.getAttribute("tabindex")!==null||r.getAttribute("aria-modal")==="true")return;r=r.parentElement}i.focus()}})},clearEnforceFocus:function(){this.onFocusin&&(z(document,Ue,this.onFocusin),this.onFocusin=null)},open:function(){var e=this.body;f(e,qe),this.scrollbarWidth>0&&(e.style.paddingRight="".concat(this.scrollbarWidth+(parseFloat(this.initialBodyComputedPaddingRight)||0),"px"))},close:function(){var e=this.body;y(e,qe),this.scrollbarWidth>0&&(e.style.paddingRight=this.initialBodyPaddingRight)},shown:function(){var e=this.element,t=this.options,i=this.viewer;this.fulled=!0,this.isShown=!0,this.render(),this.bind(),this.showing=!1,t.focus&&(i.focus(),this.enforceFocus()),E(t.shown)&&m(e,it,t.shown,{once:!0}),L(e,it,{originalEvent:this.showOriginalEvent||null})!==!1&&(this.showOriginalEvent=null,this.ready&&this.isShown&&!this.hiding&&this.view(this.index))},hidden:function(){var e=this.element,t=this.options,i=this.viewer,r=i.ownerDocument.activeElement;r&&i.contains(r)&&E(r.blur)&&r.blur(),t.focus&&this.clearEnforceFocus(),this.close(),this.unbind(),f(i,G),i.removeAttribute("role"),i.removeAttribute("aria-labelledby"),i.removeAttribute("aria-modal"),i.setAttribute("aria-hidden",!0),this.resetList(),this.resetImage(),this.fulled=!1,this.viewed=!1,this.isShown=!1,this.hiding=!1,this.destroyed||(E(t.hidden)&&m(e,at,t.hidden,{once:!0}),L(e,at,{originalEvent:this.hideOriginalEvent||null},{cancelable:!1}),this.hideOriginalEvent=null)},requestFullscreen:function(e){var t=this.ownerDocument;if(this.fulled&&!(t.fullscreenElement||t.webkitFullscreenElement||t.mozFullScreenElement||t.msFullscreenElement)){var i=t.documentElement;i.requestFullscreen?P(e)?i.requestFullscreen(e):i.requestFullscreen():i.webkitRequestFullscreen?i.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT):i.mozRequestFullScreen?i.mozRequestFullScreen():i.msRequestFullscreen&&i.msRequestFullscreen()}},exitFullscreen:function(){var e=this.ownerDocument;this.fulled&&(e.fullscreenElement||e.webkitFullscreenElement||e.mozFullScreenElement||e.msFullscreenElement)&&(e.exitFullscreen?e.exitFullscreen():e.webkitExitFullscreen?e.webkitExitFullscreen():e.mozCancelFullScreen?e.mozCancelFullScreen():e.msExitFullscreen&&e.msExitFullscreen())},change:function(e){var t=this.options,i=this.pointers,r=i[Object.keys(i)[0]];if(r){var n=r.endX-r.startX,o=r.endY-r.startY;switch(this.action){case xt:(n!==0||o!==0)&&(this.pointerMoved=!0,this.actionEvent=e,this.move(n,o));break;case Re:if(t.zoomable&&t.zoomOnTouch){var s=pt(i);s!==0&&(this.actionEvent=e,this.zoom(s))}break;case yt:if(t.rotatable&&t.rotateOnTouch){var l=bt(i);l!==0&&(this.actionEvent=e,this.rotate(l))}break;case ze:if(t.zoomable&&t.zoomOnTouch){var h=pt(i);h!==0&&(this.actionEvent=e,this.zoom(h))}if(t.rotatable&&t.rotateOnTouch){var v=bt(i);v!==0&&(this.actionEvent=e,this.rotate(v))}break;case Oe:{var u=Math.abs(n);u>1&&u>Math.abs(o)&&(this.pointerMoved=!0,this.actionEvent=e,this.move(n,0));break}}D(i,function(p){p.startX=p.endX,p.startY=p.endY})}},isSwitchable:function(){var e=this.imageData,t=this.viewerData;return this.length>1&&e.x>=0&&e.y>=0&&e.width<=t.width&&e.height<=t.height}},Jt=K.Viewer,Qt=(function(a){return function(){return a+=1,a}})(-1),Ot=(function(){function a(e){var t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{};if(zt(this,a),!e||e.nodeType!==1&&e.nodeType!==11)throw new Error("The first argument is required and must be an element.");this.element=e,this.ownerDocument=e.ownerDocument||e.host.ownerDocument,this.options=_({},We,P(t)&&t),this.action=!1,this.actionEvent=null,this.fading=!1,this.fulled=!1,this.hiding=!1,this.imageClicked=!1,this.imageData={},this.index=this.options.initialViewIndex,this.isImg=!1,this.isShown=!1,this.length=0,this.moving=!1,this.played=!1,this.playing=!1,this.pointers={},this.ready=!1,this.rotating=!1,this.scaling=!1,this.showing=!1,this.timeout=!1,this.tooltipping=!1,this.viewed=!1,this.viewing=!1,this.wheeling=!1,this.zoomable=!1,this.zooming=!1,this.pointerMoved=!1,this.id=Qt(),this.init()}return Dt(a,[{key:"init",value:function(){var t=this,i=this.element,r=this.options;if(!i[g]){i[g]=this,r.focus&&!r.keyboard&&(r.focus=!1);var n=i.localName==="img",o=[];if(D(n?[i]:i.querySelectorAll("img"),function(h){E(r.filter)?r.filter.call(t,h)&&o.push(h):t.getImageURL(h)&&o.push(h)}),this.isImg=n,this.length=o.length,this.images=o,this.initBody(),j(this.ownerDocument.createElement(g).style.transition)&&(r.transition=!1),r.inline){var s=0,l=function(){if(s+=1,s===t.length){var v;t.initializing=!1,t.delaying={abort:function(){clearTimeout(v)}},v=setTimeout(function(){t.delaying=!1,t.build()},0)}};this.initializing={abort:function(){D(o,function(v){v.complete||(z(v,U,l),z(v,re,l))})}},D(o,function(h){if(h.complete)l();else{var v,u;m(h,U,v=function(){z(h,re,u),l()},{once:!0}),m(h,re,u=function(){z(h,U,v),l()},{once:!0})}})}else m(i,te,this.onElementClick=function(h){var v=h.target;v.localName==="img"&&(!E(r.filter)||r.filter.call(t,v))&&(t.actionEvent=h,t.view(t.images.indexOf(v)))}),m(i,ke,this.onElementKeyDown=function(h){var v=h.target,u=h.key;v.localName==="img"&&(u==="Enter"||u===" ")&&(h.preventDefault(),(!E(r.filter)||r.filter.call(t,v))&&(t.actionEvent=h,t.view(t.images.indexOf(v))))})}}},{key:"build",value:function(){var t=this;if(!this.ready){var i=this.element,r=this.options,n=i.parentNode,o=document.createElement("div");o.innerHTML=St;var s=o.querySelector(".".concat(g,"-container")),l=s.querySelector(".".concat(g,"-title")),h=s.querySelector(".".concat(g,"-toolbar")),v=s.querySelector(".".concat(g,"-navbar")),u=s.querySelector(".".concat(g,"-navigation")),p=s.querySelector(".".concat(g,"-button")),d=s.querySelector(".".concat(g,"-canvas"));this.parent=n,this.viewer=s,this.title=l,this.toolbar=h,this.navbar=v,this.navigation=u,this.button=p,this.canvas=d,this.magnifier=s.querySelector(".".concat(g,"-magnifier")),this.magnifierImage=s.querySelector(".".concat(g,"-magnifier-image")),this.tooltipBox=s.querySelector(".".concat(g,"-tooltip")),this.player=s.querySelector(".".concat(g,"-player")),this.list=s.querySelector(".".concat(g,"-list")),s.id="".concat(g).concat(this.id),l.id="".concat(g,"Title").concat(this.id),f(l,r.title?ne(Array.isArray(r.title)?r.title[0]:r.title):G),r.title&&l.removeAttribute("aria-hidden");var w=P(r.navbar)?r.navbar:{},c=r.navbar,T=j(w.size)?r.navbar:w.size,O=["top","right","bottom","left"].indexOf(w.position)!==-1?w.position:"bottom";P(r.navbar)&&(c=j(w.show)?!0:w.show),f(v,c?ne(c):G),c&&v.removeAttribute("aria-hidden"),["small","medium","large"].indexOf(T)!==-1&&f(v,"".concat(g,"-").concat(T));var b=O==="left"||O==="right";if(this.isNavbarVertical=b,f(v,"".concat(g,"-navbar-").concat(O)),c){var x=b?u:l,S=b?"navigation":"title";f(x,"".concat(g,"-").concat(S,"-navbar-").concat(O)),b&&f(l,"".concat(g,"-title-navbar-").concat(O)),["small","large"].indexOf(T)!==-1&&(f(x,"".concat(g,"-").concat(S,"-navbar-").concat(b?"".concat(O,"-"):"").concat(T)),b&&f(l,"".concat(g,"-title-navbar-").concat(O,"-").concat(T)))}if(P(r.navigation)?D(u.querySelectorAll('[role="button"]'),function(N){var Q=ee(N,de),R=r.navigation[Q],F=P(R),X=F&&!j(R.show)?R.show:R,ie=F&&!j(R.size)?R.size:R;H(N,G,!X),I(X)&&f(N,ne(X)),["small","large"].indexOf(ie)!==-1&&f(N,"".concat(g,"-").concat(ie))}):f(u,r.navigation?ne(r.navigation):G),r.navigation&&u.removeAttribute("aria-hidden"),H(p,G,!r.button),r.button&&p.removeAttribute("aria-hidden"),r.keyboard&&(p.setAttribute("tabindex",0),D(u.querySelectorAll('[role="button"]'),function(N){N.setAttribute("tabindex",0)})),r.backdrop&&(f(s,"".concat(g,"-backdrop")),!r.inline&&r.backdrop!=="static"&&Fe(d,de,"hide")),he(r.className)&&r.className&&r.className.split(be).forEach(function(N){f(s,N)}),r.toolbar){var C=document.createElement("ul"),M=P(r.toolbar),k=M&&["top","right","bottom","left"].indexOf(r.toolbar.position)!==-1?r.toolbar.position:"bottom",Y=Ee.slice(0,3),$=Ee.slice(7,9),we=Ee.slice(9);M||f(h,ne(r.toolbar)),h.removeAttribute("aria-hidden"),f(h,"".concat(g,"-toolbar-").concat(k)),f(l,"".concat(g,"-title-toolbar-").concat(k)),c&&k===O&&(f(h,"".concat(g,"-toolbar-navbar-").concat(O)),["small","large"].indexOf(T)!==-1&&f(h,"".concat(g,"-toolbar-navbar-").concat(T))),D(M?r.toolbar:Ee,function(N,Q){if(Q!=="position"){var R=M&&P(N),F=M?Pe(Q):N,X=R&&!j(N.show)?N.show:N;if(!(!X||!r.zoomable&&Y.indexOf(F)!==-1||!r.rotatable&&$.indexOf(F)!==-1||!r.scalable&&we.indexOf(F)!==-1)){var ie=R&&!j(N.size)?N.size:N,ue=R&&!j(N.click)?N.click:N,Z=document.createElement("li");r.keyboard&&Z.setAttribute("tabindex",0),Z.setAttribute("role","button"),f(Z,"".concat(g,"-").concat(F)),E(ue)||Fe(Z,de,F),I(X)&&f(Z,ne(X)),["small","large"].indexOf(ie)!==-1?f(Z,"".concat(g,"-").concat(ie)):F==="play"&&f(Z,"".concat(g,"-large")),E(ue)&&m(Z,te,ue.bind(t)),C.appendChild(Z)}}}),h.appendChild(C),(k==="left"||k==="right")&&f(u,"".concat(g,"-navigation-toolbar-").concat(k))}else f(h,G);if(!r.rotatable){var ce=h.querySelectorAll('li[class*="rotate"]');f(ce,ge),D(ce,function(N){h.appendChild(N)})}if(r.inline)f(p,Nt),B(s,{zIndex:r.zIndexInline}),window.getComputedStyle(n).position==="static"&&B(n,{position:"relative"}),n.insertBefore(s,i.nextSibling);else{f(p,kt),f(s,Ve),f(s,Ie),f(s,G),B(s,{zIndex:r.zIndex});var J=r.container;he(J)&&(J=this.ownerDocument.querySelector(J)),J||(J=this.body),J.appendChild(s)}if(r.inline&&(this.render(),this.bind(),this.isShown=!0),this.ready=!0,E(r.ready)&&m(i,et,r.ready,{once:!0}),L(i,et)===!1){this.ready=!1;return}this.ready&&r.inline&&this.view(this.index)}}}],[{key:"create",value:function(t,i){return new a(t,i)}},{key:"setDefaults",value:function(t){_(We,P(t)&&t)}},{key:"noConflict",value:function(){return window.Viewer=Jt,a}}])})();_(Ot.prototype,Bt,Zt,Gt,Kt,$t);var ti=`/*!
 * Viewer.js v1.15.2
 * https://fengyuanchen.github.io/viewerjs
 *
 * Copyright 2015-present Chen Fengyuan
 * Released under the MIT license
 *
 * Date: 2026-10-01T05:04:36.958Z
 */

.viewer-zoom-in::before, .viewer-zoom-out::before, .viewer-one-to-one::before, .viewer-reset::before, .viewer-prev::before, .viewer-play::before, .viewer-next::before, .viewer-rotate-left::before, .viewer-rotate-right::before, .viewer-flip-horizontal::before, .viewer-flip-vertical::before, .viewer-fullscreen::before, .viewer-fullscreen-exit::before, .viewer-close::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22 viewBox%3D%220 0 560 40%22%3E%3Cpath fill%3D%22%23fff%22 d%3D%22M49.6 17.9h20.2v3.9H49.6zm123.1 2 10.9-11 2.7 2.8-8.2 8.2 8.2 8.2-2.7 2.7-10.9-10.9zm94 0-10.8-11-2.7 2.8 8.1 8.2-8.1 8.2 2.7 2.7 10.8-10.9zM212 9.3l20.1 10.6L212 30.5V9.3zm161.5 4.6-7.2 6 7.2 5.9v-4h12.4v4l7.3-5.9-7.3-6v4h-12.4v-4zm40.2 12.3 5.9 7.2 5.9-7.2h-4V13.6h4l-5.9-7.3-5.9 7.3h4v12.6h-4zm35.9-16.5h6.3v2h-4.3V16h-2V9.7Zm14 0h6.2V16h-2v-4.3h-4.2v-2Zm6.2 14V30h-6.2v-2h4.2v-4.3h2Zm-14 6.3h-6.2v-6.3h2v4.4h4.3v2Zm-438 .1v-8.3H9.6v-3.9h8.2V9.7h3.9v8.2h8.1v3.9h-8.1v8.3h-3.9zM93.6 9.7h-5.8v3.9h2V30h3.8V9.7zm16.1 0h-5.8v3.9h1.9V30h3.9V9.7zm-11.9 4.1h3.9v3.9h-3.9zm0 8.2h3.9v3.9h-3.9zm244.6-11.7 7.2 5.9-7.2 6v-3.6c-5.4-.4-7.8.8-8.7 2.8-.8 1.7-1.8 4.9 2.8 8.2-6.3-2-7.5-6.9-6-11.3 1.6-4.4 8-5 11.9-4.9v-3.1Zm147.2 13.4h6.3V30h-2v-4.3h-4.3v-2zm14 6.3v-6.3h6.2v2h-4.3V30h-1.9zm6.2-14h-6.2V9.7h1.9V14h4.3v2zm-13.9 0h-6.3v-2h4.3V9.7h2V16zm33.3 12.5 8.6-8.6-8.6-8.7 1.9-1.9 8.6 8.7 8.6-8.7 1.9 1.9-8.6 8.7 8.6 8.6-1.9 2-8.6-8.7-8.6 8.7-1.9-2zM297 10.3l-7.1 5.9 7.2 6v-3.6c5.3-.4 7.7.8 8.7 2.8.8 1.7 1.7 4.9-2.9 8.2 6.3-2 7.5-6.9 6-11.3-1.6-4.4-7.9-5-11.8-4.9v-3.1Zm-157.3-.6c2.3 0 4.4.7 6 2l2.5-3 1.9 9.2h-9.3l2.6-3.1a6.2 6.2 0 0 0-9.9 5.1c0 3.4 2.8 6.3 6.2 6.3 2.8 0 5.1-1.9 6-4.4h4c-1 4.7-5 8.3-10 8.3a10 10 0 0 1-10-10.2 10 10 0 0 1 10-10.2Z%22%2F%3E%3C%2Fsvg%3E");
    background-repeat: no-repeat;
    background-size: 280px;
    color: transparent;
    display: block;
    font-size: 0;
    height: 20px;
    line-height: 0;
    width: 20px;
  }

.viewer-zoom-in::before {
  background-position: 0 0;
  content: 'Zoom In';
}

.viewer-zoom-out::before {
  background-position: -20px 0;
  content: 'Zoom Out';
}

.viewer-one-to-one::before {
  background-position: -40px 0;
  content: 'One to One';
}

.viewer-reset::before {
  background-position: -60px 0;
  content: 'Reset';
}

.viewer-prev::before {
  background-position: -80px 0;
  content: 'Previous';
}

.viewer-play::before {
  background-position: -100px 0;
  content: 'Play';
}

.viewer-next::before {
  background-position: -120px 0;
  content: 'Next';
}

.viewer-rotate-left::before {
  background-position: -140px 0;
  content: 'Rotate Left';
}

.viewer-rotate-right::before {
  background-position: -160px 0;
  content: 'Rotate Right';
}

.viewer-flip-horizontal::before {
  background-position: -180px 0;
  content: 'Flip Horizontal';
}

.viewer-flip-vertical::before {
  background-position: -200px 0;
  content: 'Flip Vertical';
}

.viewer-fullscreen::before {
  background-position: -220px 0;
  content: 'Enter Full Screen';
}

.viewer-fullscreen-exit::before {
  background-position: -240px 0;
  content: 'Exit Full Screen';
}

.viewer-close::before {
  background-position: -260px 0;
  content: 'Close';
}

.viewer-container {
  bottom: 0;
  direction: ltr;
  font-size: 0;
  left: 0;
  line-height: 0;
  overflow: hidden;
  position: absolute;
  right: 0;
  -webkit-tap-highlight-color: transparent;
  top: 0;
  -ms-touch-action: none;
      touch-action: none;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
     -moz-user-select: none;
      -ms-user-select: none;
          user-select: none;
}

.viewer-container::-moz-selection, .viewer-container *::-moz-selection {
    background-color: transparent;
  }

.viewer-container::selection,
  .viewer-container *::selection {
    background-color: transparent;
  }

.viewer-container:focus {
    outline: 0;
  }

.viewer-container img {
    display: block;
    height: auto;
    max-height: none !important;
    max-width: none !important;
    min-height: 0 !important;
    min-width: 0 !important;
    width: 100%;
  }

.viewer-canvas {
  bottom: 0;
  left: 0;
  overflow: hidden;
  position: absolute;
  right: 0;
  top: 0;
}

.viewer-canvas > img {
    height: auto;
    margin: 15px auto;
    max-width: 90% !important;
    width: auto;
  }

.viewer-magnifier {
  background-color: #fff;
  background-repeat: no-repeat;
  border: 2px solid #fff;
  border-radius: 50%;
  box-shadow: 0 1px 5px rgba(0, 0, 0, 0.5);
  box-sizing: border-box;
  display: none;
  left: 16px;
  overflow: hidden;
  pointer-events: none;
  position: absolute;
  top: 16px;
  z-index: 2;
}

.viewer-magnifier.viewer-show {
    display: block;
  }

.viewer-magnifier-image {
  left: 0;
  max-width: none !important;
  position: absolute;
  top: 0;
  -ms-transform-origin: center;
      transform-origin: center;
}

.viewer-navigation {
  left: 0;
  position: absolute;
  right: 0;
  top: 50%;
}

.viewer-navigation > .viewer-prev,
  .viewer-navigation > .viewer-next {
    background-color: rgba(0, 0, 0, 0.5);
    border-radius: 50%;
    cursor: pointer;
    height: 40px;
    margin-top: -20px;
    position: absolute;
    width: 40px;
  }

.viewer-navigation > .viewer-prev:focus,
    .viewer-navigation > .viewer-next:focus,
    .viewer-navigation > .viewer-prev:hover,
    .viewer-navigation > .viewer-next:hover {
      background-color: rgba(0, 0, 0, 0.8);
    }

.viewer-navigation > .viewer-prev:focus, .viewer-navigation > .viewer-next:focus {
      box-shadow: 0 0 3px #fff;
      outline: 0;
    }

.viewer-navigation > .viewer-prev::before, .viewer-navigation > .viewer-next::before {
      margin: 10px;
    }

.viewer-navigation > .viewer-prev {
    left: 15px;
  }

.viewer-navigation > .viewer-next {
    right: 15px;
  }

.viewer-navigation > .viewer-large {
    height: 48px;
    margin-top: -24px;
    width: 48px;
  }

.viewer-navigation > .viewer-large::before {
      margin: 14px;
    }

.viewer-navigation > .viewer-small {
    height: 32px;
    margin-top: -16px;
    width: 32px;
  }

.viewer-navigation > .viewer-small::before {
      margin: 6px;
    }

.viewer-navigation-toolbar-left > .viewer-prev {
  left: 51px;
}

.viewer-navigation-toolbar-right > .viewer-next {
  right: 51px;
}

.viewer-navigation-navbar-left > .viewer-prev {
  left: 67px;
}

.viewer-navigation-navbar-right > .viewer-next {
  right: 67px;
}

.viewer-navigation-navbar-left-small > .viewer-prev {
  left: 57px;
}

.viewer-navigation-navbar-right-small > .viewer-next {
  right: 57px;
}

.viewer-navigation-navbar-left-large > .viewer-prev {
  left: 77px;
}

.viewer-navigation-navbar-right-large > .viewer-next {
  right: 77px;
}

.viewer-navigation.viewer-navigation-toolbar-left.viewer-navigation-navbar-left > .viewer-prev {
  left: 103px;
}

.viewer-navigation.viewer-navigation-toolbar-left.viewer-navigation-navbar-left.viewer-navigation-navbar-left-small > .viewer-prev {
  left: 93px;
}

.viewer-navigation.viewer-navigation-toolbar-left.viewer-navigation-navbar-left.viewer-navigation-navbar-left-large > .viewer-prev {
  left: 113px;
}

.viewer-navigation.viewer-navigation-toolbar-right.viewer-navigation-navbar-right > .viewer-next {
  right: 103px;
}

.viewer-navigation.viewer-navigation-toolbar-right.viewer-navigation-navbar-right.viewer-navigation-navbar-right-small > .viewer-next {
  right: 93px;
}

.viewer-navigation.viewer-navigation-toolbar-right.viewer-navigation-navbar-right.viewer-navigation-navbar-right-large > .viewer-next {
  right: 113px;
}

.viewer-navbar {
  background-color: rgba(0, 0, 0, 0.5);
  bottom: 0;
  left: 0;
  overflow: hidden;
  position: absolute;
  right: 0;
}

.viewer-navbar.viewer-small > .viewer-list {
    height: 40px;

    > li {
      height: 40px;
      width: 24px;
    }
  }

.viewer-navbar.viewer-large > .viewer-list {
    height: 60px;

    > li {
      height: 60px;
      width: 36px;
    }
  }

.viewer-navbar-top {
  bottom: auto;
  top: 0;
}

.viewer-navbar-left,
.viewer-navbar-right {
  bottom: 0;
  top: 0;
  width: 52px;

  > .viewer-list {
    height: auto;
    padding: 0 1px;
    width: 50px;

    > li {
      float: none;
      height: 30px;
      width: 50px;
    }

      > li + li {
        margin-left: 0;
        margin-top: 1px;
      }
  }
}

.viewer-navbar-left.viewer-small, .viewer-navbar-right.viewer-small {
    width: 42px;

    > .viewer-list {
      width: 40px;

      > li {
        height: 24px;
        width: 40px;
      }
    }
  }

.viewer-navbar-left.viewer-large, .viewer-navbar-right.viewer-large {
    width: 62px;

    > .viewer-list {
      width: 60px;

      > li {
        height: 36px;
        width: 60px;
      }
    }
  }

.viewer-navbar-left {
  right: auto;
}

.viewer-navbar-right {
  left: auto;
}

.viewer-list {
  box-sizing: content-box;
  height: 50px;
  margin: 0;
  overflow: hidden;
  padding: 1px 0;
}

.viewer-list > li {
    color: transparent;
    cursor: pointer;
    float: left;
    font-size: 0;
    height: 50px;
    line-height: 0;
    opacity: 0.5;
    overflow: hidden;
    transition: opacity 0.15s;
    width: 30px;
  }

.viewer-list > li:focus,
    .viewer-list > li:hover {
      opacity: 0.75;
    }

.viewer-list > li:focus {
      outline: 0;
    }

.viewer-list > li + li {
      margin-left: 1px;
    }

.viewer-list > .viewer-loading {
    position: relative;
  }

.viewer-list > .viewer-loading::after {
      border-width: 2px;
      height: 20px;
      margin-left: -10px;
      margin-top: -10px;
      width: 20px;
    }

.viewer-list > .viewer-active,
  .viewer-list > .viewer-active:focus,
  .viewer-list > .viewer-active:hover {
    opacity: 1;
  }

.viewer-player {
  background-color: #000;
  bottom: 0;
  cursor: none;
  display: none;
  left: 0;
  position: absolute;
  right: 0;
  top: 0;
  z-index: 1;
}

.viewer-player > img {
    left: 0;
    position: absolute;
    top: 0;
  }

.viewer-toolbar {
  bottom: 0;
  left: 0;
  position: absolute;
  right: 0;
  text-align: center;
}

.viewer-toolbar.viewer-toolbar-top {
    bottom: auto;
    top: 0;
  }

.viewer-toolbar.viewer-toolbar-navbar-top {
    top: 52px;
  }

.viewer-toolbar.viewer-toolbar-navbar-top.viewer-toolbar-navbar-small {
      top: 42px;
    }

.viewer-toolbar.viewer-toolbar-navbar-top.viewer-toolbar-navbar-large {
      top: 62px;
    }

.viewer-toolbar.viewer-toolbar-navbar-right {
    right: 52px;
  }

.viewer-toolbar.viewer-toolbar-navbar-right.viewer-toolbar-navbar-small {
      right: 42px;
    }

.viewer-toolbar.viewer-toolbar-navbar-right.viewer-toolbar-navbar-large {
      right: 62px;
    }

.viewer-toolbar.viewer-toolbar-navbar-bottom {
    bottom: 52px;
  }

.viewer-toolbar.viewer-toolbar-navbar-bottom.viewer-toolbar-navbar-small {
      bottom: 42px;
    }

.viewer-toolbar.viewer-toolbar-navbar-bottom.viewer-toolbar-navbar-large {
      bottom: 62px;
    }

.viewer-toolbar.viewer-toolbar-navbar-left {
    left: 52px;
  }

.viewer-toolbar.viewer-toolbar-navbar-left.viewer-toolbar-navbar-small {
      left: 42px;
    }

.viewer-toolbar.viewer-toolbar-navbar-left.viewer-toolbar-navbar-large {
      left: 62px;
    }

.viewer-toolbar.viewer-toolbar-left,
  .viewer-toolbar.viewer-toolbar-right {
    bottom: auto;
    left: auto;
    right: 0;
    top: 50%;
    -ms-transform: translateY(-50%);
        transform: translateY(-50%);
    width: 36px;
  }

.viewer-toolbar.viewer-toolbar-left > ul, .viewer-toolbar.viewer-toolbar-right > ul {
      margin: 0;
      padding: 3px 6px;
    }

.viewer-toolbar.viewer-toolbar-left > ul > li, .viewer-toolbar.viewer-toolbar-right > ul > li {
        float: none;
      }

.viewer-toolbar.viewer-toolbar-left > ul > li + li, .viewer-toolbar.viewer-toolbar-right > ul > li + li {
          margin-left: 0;
          margin-top: 1px !important;
        }

.viewer-toolbar.viewer-toolbar-left > ul > .viewer-small, .viewer-toolbar.viewer-toolbar-right > ul > .viewer-small {
        margin: 0 3px;
      }

.viewer-toolbar.viewer-toolbar-left > ul > .viewer-large, .viewer-toolbar.viewer-toolbar-right > ul > .viewer-large {
        margin: 0 -3px;
      }

.viewer-toolbar.viewer-toolbar-left {
    left: 0;
    right: auto;
  }

.viewer-toolbar > ul {
    display: inline-block;
    margin: 0 auto 5px;
    overflow: hidden;
    padding: 6px 3px;
  }

.viewer-toolbar > ul > li {
      background-color: rgba(0, 0, 0, 0.5);
      border-radius: 50%;
      cursor: pointer;
      float: left;
      height: 24px;
      overflow: hidden;
      transition: background-color 0.15s;
      width: 24px;
    }

.viewer-toolbar > ul > li:focus,
      .viewer-toolbar > ul > li:hover {
        background-color: rgba(0, 0, 0, 0.8);
      }

.viewer-toolbar > ul > li:focus {
        box-shadow: 0 0 3px #fff;
        outline: 0;
        position: relative;
        z-index: 1;
      }

.viewer-toolbar > ul > li::before {
        margin: 2px;
      }

.viewer-toolbar > ul > li + li {
        margin-left: 1px;
      }

.viewer-toolbar > ul > .viewer-small {
      height: 18px;
      margin-bottom: 3px;
      margin-top: 3px;
      width: 18px;
    }

.viewer-toolbar > ul > .viewer-small::before {
        margin: -1px;
      }

.viewer-toolbar > ul > .viewer-large {
      height: 30px;
      margin-bottom: -3px;
      margin-top: -3px;
      width: 30px;
    }

.viewer-toolbar > ul > .viewer-large::before {
        margin: 5px;
      }

.viewer-tooltip {
  background-color: rgba(0, 0, 0, 0.8);
  border-radius: 10px;
  color: #fff;
  display: none;
  font-size: 12px;
  height: 20px;
  left: 50%;
  line-height: 20px;
  margin-left: -25px;
  margin-top: -10px;
  position: absolute;
  text-align: center;
  top: 50%;
  width: 50px;
}

.viewer-title {
  bottom: 0;
  color: #ccc;
  display: inline-block;
  font-size: 12px;
  left: 50%;
  line-height: 1.2;
  max-width: 90%;
  min-height: 14px;
  opacity: 0.8;
  overflow: hidden;
  padding: 5px;
  position: absolute;
  text-overflow: ellipsis;
  -ms-transform: translateX(-50%);
      transform: translateX(-50%);
  transition: opacity 0.15s;
  white-space: nowrap;
}

.viewer-title.viewer-title-navbar-bottom {
    bottom: 52px;
  }

.viewer-title.viewer-title-navbar-bottom.viewer-title-navbar-small {
      bottom: 42px;
    }

.viewer-title.viewer-title-navbar-bottom.viewer-title-navbar-large {
      bottom: 62px;
    }

.viewer-title.viewer-title-toolbar-bottom {
    bottom: 42px;
  }

.viewer-title.viewer-title-toolbar-bottom.viewer-title-navbar-bottom {
      bottom: 94px;
    }

.viewer-title.viewer-title-toolbar-bottom.viewer-title-navbar-bottom.viewer-title-navbar-small {
        bottom: 84px;
      }

.viewer-title.viewer-title-toolbar-bottom.viewer-title-navbar-bottom.viewer-title-navbar-large {
        bottom: 104px;
      }

.viewer-title.viewer-title-toolbar-left,
  .viewer-title.viewer-title-toolbar-right,
  .viewer-title.viewer-title-navbar-left,
  .viewer-title.viewer-title-navbar-right {
    max-width: none;
    text-align: center;
    -ms-transform: none;
        transform: none;
  }

.viewer-title.viewer-title-toolbar-left {
    left: 36px;
    right: 0;
  }

.viewer-title.viewer-title-toolbar-right {
    left: 0;
    right: 36px;
  }

.viewer-title.viewer-title-navbar-left {
    left: 52px;
    right: 0;
  }

.viewer-title.viewer-title-navbar-left.viewer-title-navbar-left-small {
      left: 42px;
    }

.viewer-title.viewer-title-navbar-left.viewer-title-navbar-left-large {
      left: 62px;
    }

.viewer-title.viewer-title-navbar-right {
    left: 0;
    right: 52px;
  }

.viewer-title.viewer-title-navbar-right.viewer-title-navbar-right-small {
      right: 42px;
    }

.viewer-title.viewer-title-navbar-right.viewer-title-navbar-right-large {
      right: 62px;
    }

.viewer-title.viewer-title-toolbar-left.viewer-title-navbar-right {
    left: 36px;
  }

.viewer-title.viewer-title-toolbar-right.viewer-title-navbar-left {
    right: 36px;
  }

.viewer-title.viewer-title-toolbar-left.viewer-title-navbar-left {
    left: 88px;
  }

.viewer-title.viewer-title-toolbar-left.viewer-title-navbar-left.viewer-title-navbar-left-small {
      left: 78px;
    }

.viewer-title.viewer-title-toolbar-left.viewer-title-navbar-left.viewer-title-navbar-left-large {
      left: 98px;
    }

.viewer-title.viewer-title-toolbar-right.viewer-title-navbar-right {
    right: 88px;
  }

.viewer-title.viewer-title-toolbar-right.viewer-title-navbar-right.viewer-title-navbar-right-small {
      right: 78px;
    }

.viewer-title.viewer-title-toolbar-right.viewer-title-navbar-right.viewer-title-navbar-right-large {
      right: 98px;
    }

.viewer-title:hover {
    opacity: 1;
  }

.viewer-button {
  -webkit-app-region: no-drag;
  background-color: rgba(0, 0, 0, 0.5);
  border-radius: 50%;
  cursor: pointer;
  height: 80px;
  overflow: hidden;
  position: absolute;
  right: -40px;
  top: -40px;
  transition: background-color 0.15s;
  width: 80px;
}

.viewer-button:focus,
  .viewer-button:hover {
    background-color: rgba(0, 0, 0, 0.8);
  }

.viewer-button:focus {
    box-shadow: 0 0 3px #fff;
    outline: 0;
  }

.viewer-button::before {
    bottom: 15px;
    left: 15px;
    position: absolute;
  }

.viewer-fixed {
  position: fixed;
}

.viewer-open {
  overflow: hidden;
}

.viewer-show {
  display: block;
}

.viewer-hide {
  display: none;
}

.viewer-backdrop {
  background-color: rgba(0, 0, 0, 0.5);
}

.viewer-invisible {
  visibility: hidden;
}

.viewer-move {
  cursor: move;
  cursor: grab;
}

.viewer-fade {
  opacity: 0;
}

.viewer-in {
  opacity: 1;
}

.viewer-transition {
  transition: all 0.3s;
}

@keyframes viewer-spinner {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.viewer-loading::after {
    animation: viewer-spinner 1s linear infinite;
    border: 4px solid rgba(255, 255, 255, 0.1);
    border-left-color: rgba(255, 255, 255, 0.5);
    border-radius: 50%;
    content: '';
    display: inline-block;
    height: 40px;
    left: 50%;
    margin-left: -20px;
    margin-top: -20px;
    position: absolute;
    top: 50%;
    width: 40px;
    z-index: 1;
  }

@media (max-width: 767px) {
  .viewer-hide-xs-down {
    display: none;
  }
}

@media (max-width: 991px) {
  .viewer-hide-sm-down {
    display: none;
  }
}

@media (max-width: 1199px) {
  .viewer-hide-md-down {
    display: none;
  }
}
`;export{Ot as Viewer,ti as css};
