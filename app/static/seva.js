/* Seva Setu India - homepage logic: i18n, config, search, voice, modal, a11y. */
(function(){
"use strict";
var $=function(s,r){return (r||document).querySelector(s)}, $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var store={get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},set:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
var LANGS=window.SEVA_LANGS||[], I18N=window.SEVA_I18N||{}, CATS=window.SEVA_CATS||[], POP=window.SEVA_POPULAR||[];
var lang=store.get("seva-lang")||"hi"; if(!I18N[lang])lang="hi";
var CFG={name:"Seva Setu India",wa:"917033167496"};
function t(k){return (I18N[lang]&&I18N[lang][k])||(I18N.en&&I18N.en[k])||k}
function applyI18n(){
 document.documentElement.lang=lang;
 $$("[data-i18n]").forEach(function(el){var v=t(el.getAttribute("data-i18n")); if(v)el.textContent=v});
 $$("[data-i18n-ph]").forEach(function(el){el.setAttribute("placeholder",t(el.getAttribute("data-i18n-ph")))});
 var ln=$("#langNote"); if(ln){ln.hidden=(lang==="en"||lang==="hi"?false:false); ln.hidden=false;}
 document.title=CFG.name;
 buildCards(); closeSuggest();
}
function setLang(l){lang=l;store.set("seva-lang",l);var s=$("#langSel");if(s)s.value=l;applyI18n()}
/* language selector */
(function(){var s=$("#langSel");if(!s)return;LANGS.forEach(function(L){var o=document.createElement("option");o.value=L.c;o.textContent=L.n;s.appendChild(o)});s.value=lang;s.addEventListener("change",function(){setLang(s.value)})})();
/* config */
fetch("/api/config").then(function(r){return r.json()}).then(function(c){
 if(c){if(c.brand_name)CFG.name=c.brand_name; if(c.wa_number)CFG.wa=(""+c.wa_number).replace(/\D/g,"");}
 var bn=$("#brandName"); if(bn)bn.textContent=CFG.name;
 document.title=CFG.name; wireWa();
}).catch(function(){wireWa()});
function waUrl(msg){return "https://wa.me/"+CFG.wa+"?text="+encodeURIComponent(msg||t("waPrefill"))}
function wireWa(){var a=$("#waHero"); if(a)a.href=waUrl();}
/* cards */
function catCard(c,cls){
 var b=document.createElement("button");b.className=cls;b.type="button";
 b.setAttribute("aria-label",c.n[lang]||c.n.en);
 b.innerHTML='<span class="'+(cls==="popc"?"pi":"ci")+'" aria-hidden="true">'+c.ic+'</span><div class="'+(cls==="popc"?"pn":"cn")+'"></div>'+(cls==="catc"?'<div class="cb"></div>':"");
 b.querySelector(".pn,.cn").textContent=c.n[lang]||c.n.en;
 var cb=b.querySelector(".cb"); if(cb)cb.textContent=c.b[lang]||c.b.en;
 b.addEventListener("click",function(){openModal(c)});
 return b;
}
function buildCards(){
 var p=$("#pop"); if(p){p.innerHTML="";POP.forEach(function(id){var c=CATS.filter(function(x){return x.id===id})[0];if(c)p.appendChild(catCard(c,"popc"))})}
 var g=$("#catGrid"); if(g){g.innerHTML="";CATS.forEach(function(c){g.appendChild(catCard(c,"catc"))})}
}
/* modal */
var modal=$("#modal"),lastFocus=null;
function openModal(c){
 lastFocus=document.activeElement;
 $("#mIc").textContent=c.ic; $("#mTitle").textContent=c.n[lang]||c.n.en;
 $("#mBlurb").textContent=c.b[lang]||c.b.en;
 var on=c.on==="yes"?t("online.yes"):c.on==="no"?t("online.no"):t("online.varies");
 $("#mOn").textContent="● "+on;
 $("#mDocsH").textContent="📋 "+t("sec.docs");
 var ul=$("#mDocs");ul.innerHTML="";(c.docs[lang]||c.docs.en).forEach(function(d){var li=document.createElement("li");li.textContent=d;ul.appendChild(li)});
 var ml=$("#mLinks");ml.innerHTML="";
 c.links.forEach(function(L){var a=document.createElement("a");a.className="btn btn-navy";a.href=L.u;a.target="_blank";a.rel="noopener";a.textContent=(L.l[lang]||L.l.en);ml.appendChild(a)});
 var wa=document.createElement("a");wa.className="btn btn-green";wa.href=waUrl(t("waPrefill")+(c.n[lang]||c.n.en));wa.target="_blank";wa.rel="noopener";wa.textContent=t("cat.assist");ml.appendChild(wa);
 if(c.complaint){var cp=document.createElement("a");cp.className="btn btn-saffron";cp.href="/app";cp.textContent=t("complaintsCta");ml.appendChild(cp)}
 $("#mVer").textContent=t("verifiedOn")+": "+c.verified;
 modal.hidden=false; $(".mx",modal).focus();
 document.body.style.overflow="hidden";
}
function closeModal(){modal.hidden=true;document.body.style.overflow="";if(lastFocus)lastFocus.focus()}
$$("[data-close]",modal).forEach(function(el){el.addEventListener("click",closeModal)});
document.addEventListener("keydown",function(e){if(e.key==="Escape"){if(!modal.hidden)closeModal();closeSuggest()}});
/* search */
var q=$("#q"),sres=$("#sres"),sel=-1;
function findCats(s){
 s=s.trim().toLowerCase(); if(s.length<2)return [];
 return CATS.filter(function(c){
  var hay=[c.id]; for(var k in c.n)hay.push(c.n[k]); hay.push(c.b.en,c.b.hi);
  return hay.join(" ").toLowerCase().indexOf(s)>-1;
 }).slice(0,7);
}
function closeSuggest(){if(sres){sres.hidden=true;sres.innerHTML="";sel=-1}}
function showSuggest(list){
 sres.innerHTML="";
 if(!list.length){var d=document.createElement("div");d.className="none";d.textContent=t("search.noResults");sres.appendChild(d);sres.hidden=false;return}
 list.forEach(function(c,i){
  var b=document.createElement("button");b.type="button";b.setAttribute("role","option");
  b.innerHTML='<span class="sic2" aria-hidden="true">'+c.ic+'</span><span></span>';
  b.querySelector("span:last-child").textContent=c.n[lang]||c.n.en;
  b.addEventListener("click",function(){openModal(c);closeSuggest()});
  sres.appendChild(b);
 });
 sres.hidden=false;
}
if(q){
 q.addEventListener("input",function(){var l=findCats(q.value); if(q.value.trim().length<2){closeSuggest()}else showSuggest(l)});
 $("#searchForm").addEventListener("submit",function(e){
  e.preventDefault();var l=findCats(q.value);
  if(l.length){openModal(l[0])}else{showSuggest([])}
 });
 document.addEventListener("click",function(e){if(!$("#searchForm").contains(e.target)&&!sres.contains(e.target))closeSuggest()});
}
/* voice search */
var mic=$("#micBtn");
if(mic){
 var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SR){mic.style.display="none"}
 else{
  mic.addEventListener("click",function(){
   var code=(LANGS.filter(function(L){return L.c===lang})[0]||{}).s||"hi-IN";
   var r=new SR();r.lang=code;r.interimResults=false;r.maxAlternatives=1;
   mic.classList.add("listening");
   r.onresult=function(ev){var txt=ev.results[0][0].transcript;q.value=txt;var l=findCats(txt);showSuggest(l);if(l.length===1)openModal(l[0])};
   r.onend=function(){mic.classList.remove("listening")};
   r.onerror=function(){mic.classList.remove("listening")};
   try{r.start()}catch(e){mic.classList.remove("listening")}
  });
 }
}
/* a11y toggles */
function bindToggle(id,key,cls,def){
 var b=$(id);if(!b)return;
 var on=store.get(key); if(on===null)on=def?"1":"0";
 function ap(){document.documentElement.classList.toggle(cls,on==="1");b.setAttribute("aria-pressed",on==="1"?"true":"false")}
 b.addEventListener("click",function(){on=on==="1"?"0":"1";store.set(key,on);ap()});ap();
}
bindToggle("#tFont","seva-bigtext","bigtext",false);
bindToggle("#tContrast","seva-contrast","hc",false);
(function(){var def=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;bindToggle("#tMotion","seva-motion","lomotion",def)})();
/* header shadow */
var sh=$("#sh");
window.addEventListener("scroll",function(){if(sh)sh.classList.toggle("scrolled",window.scrollY>8)},{passive:true});
/* reveal on scroll */
if("IntersectionObserver" in window && !document.documentElement.classList.contains("lomotion")){
 var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}})},{threshold:.12});
 $$(".reveal").forEach(function(el){io.observe(el)});
}else{$$(".reveal").forEach(function(el){el.classList.add("in")})}
/* service worker */
if("serviceWorker" in navigator){navigator.serviceWorker.register("/sw.js").catch(function(){})}
applyI18n();
})();
