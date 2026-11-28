/* Seva Setu India - super-admin console (Phase 6). Auth: admin token with seva.admin permission. */
(function(){
"use strict";
var $=function(s){return document.querySelector((s.charAt(0)==="#"||s.charAt(0)==="."||s.charAt(0)==="["||s.indexOf(" ")>=0)?s:"#"+s)}, $$=function(s){return Array.prototype.slice.call(document.querySelectorAll(s))};
var LS=window.localStorage, T=LS.getItem("at")||"";
function esc(s){return (s==null?"":""+s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
async function api(m,p,b){
 var r=await fetch(p,{method:m,headers:Object.assign({"Content-Type":"application/json"},T?{Authorization:"Bearer "+T}:{}) ,body:b?JSON.stringify(b):undefined});
 var j=await r.json().catch(function(){return {}});
 if(!r.ok){var e=new Error(j.error||("HTTP "+r.status));e.status=r.status;throw e}
 return j;
}
function showLogin(){$("loginView").classList.remove("hide");$("adminView").classList.add("hide");$("logoutB").classList.add("hide")}
function showAdmin(){$("loginView").classList.add("hide");$("adminView").classList.remove("hide");$("logoutB").classList.remove("hide")}
async function boot(){
 if(!T)return showLogin();
 try{await api("GET","/api/admin/overview");showAdmin();loadTab("overview")}
 catch(e){T="";LS.removeItem("at");showLogin();$("lmsg").textContent="Token rejected - super admin only.";$("lmsg").classList.add("err")}
}
$("loginB").onclick=function(){T=$("atok").value.trim();LS.setItem("at",T);boot()};
$("logoutB").onclick=function(){T="";LS.removeItem("at");location.reload()};

/* tabs */
$$("#tabs .tab").forEach(function(b){b.onclick=function(){loadTab(b.getAttribute("data-tab"))}});
function loadTab(name){
 $$("#tabs .tab").forEach(function(b){var on=b.getAttribute("data-tab")===name;b.className="tab btn "+(on?"btn-navy":"btn-ghost")});
 $$(".tabpane").forEach(function(p){p.classList.add("hide")});
 $("tab-"+name).classList.remove("hide");
 ({overview:loadOverview,citizens:loadCitizens,staff:loadStaff,catalog:loadCatalog,translations:loadTranslations,settings:loadSettings,audit:loadAudit})[name]();
}

/* overview */
async function loadOverview(){
 var o=await api("GET","/api/admin/overview");
 var stats=[["citizens","Citizens"],["applications","Applications"],["pending_applications","Pending"],["documents","Documents"],["complaints","Complaints"],["staff","Staff tokens"],["verified_submissions","Verified submissions"],["schemes","Active schemes"]];
 $("statGrid").innerHTML=stats.map(function(s){return '<div class="stat"><b>'+esc(o[s[0]])+'</b><span>'+s[1]+"</span></div>"}).join("");
 var rows=Object.keys(o.applications_by_status||{}).map(function(k){return "<tr><td>"+esc(k)+"</td><td>"+o.applications_by_status[k]+"</td></tr>"}).join("");
 $("statusTbl").innerHTML="<tr><th>Status</th><th>Count</th></tr>"+(rows||'<tr><td colspan="2">No applications yet</td></tr>');
}

/* citizens */
async function loadCitizens(q){
 var r=await api("GET","/api/admin/citizens"+(q?("?q="+encodeURIComponent(q)):""));
 $("citTbl").innerHTML="<tr><th>Citizen</th><th>Location</th><th>Joined</th><th>Status</th><th></th></tr>"+r.items.map(function(u){
  var sus=u.flag==="suspended";
  return "<tr><td><b>"+esc(u.name||"-")+"</b><br><span class='mut'>"+esc(u.phone||"")+"</span></td><td>"+esc([u.district,u.state].filter(Boolean).join(", "))+"</td><td>"+esc((u.created_at||"").slice(0,10))+"</td>"+
   "<td>"+(sus?'<span class="pill warn">suspended</span><br><span class="mut">'+esc(u.reason||"")+"</span>":'<span class="pill ok">active</span>')+"</td>"+
   '<td><button class="btn '+(sus?"btn-ghost":"btn-navy")+' sm" data-cit="'+u.id+'" data-sus="'+(sus?0:1)+'">'+(sus?"Lift suspension":"Suspend")+"</button></td></tr>";
 }).join("")||"<tr><td>No citizens found</td></tr>";
 $$("#citTbl [data-cit]").forEach(function(b){b.onclick=async function(){
  var sus=b.getAttribute("data-sus")==="1", reason="";
  if(sus){reason=window.prompt("Reason for suspension (goes to audit log):")||"";if(!reason.trim())return}
  await api("POST","/api/admin/citizens/"+b.getAttribute("data-cit")+"/flag",{flag:sus?"suspended":"clear",reason:reason});
  loadCitizens($("citQ").value.trim());
 }});
}
$("citGo").onclick=function(){loadCitizens($("citQ").value.trim())};

/* staff */
async function loadStaff(){
 var r=await api("GET","/api/admin/staff");
 var sel=$("stfRole");sel.innerHTML=r.roles.map(function(x){return "<option>"+esc(x)+"</option>"}).join("");sel.value="seva_operator";
 $("stfTbl").innerHTML="<tr><th>Name</th><th>Role</th><th>Scope</th><th>Created</th><th>Token</th><th></th></tr>"+r.items.map(function(s){
  return "<tr><td><b>"+esc(s.name)+"</b></td><td>"+esc(s.role)+"</td><td>"+esc([s.scope_state,s.scope_city].filter(Boolean).join("/")||"all")+"</td><td>"+esc((s.created_at||"").slice(0,10))+"</td>"+
   "<td>"+(s.active?'<span class="pill ok">active</span>':'<span class="pill warn">disabled</span>')+"</td>"+
   "<td>"+(s.active?'<button class="btn btn-ghost sm" data-stf="'+s.id+'">Disable</button>':"")+"</td></tr>";
 }).join("");
 $$("#stfTbl [data-stf]").forEach(function(b){b.onclick=async function(){
  if(!window.confirm("Disable this token? The person loses access immediately."))return;
  var r2=await api("POST","/api/admin/staff/"+b.getAttribute("data-stf")+"/disable",{});
  if(r2.error)$("stfMsg").textContent=r2.error,$("stfMsg").className="msg err";
  loadStaff();
 }});
}
$("stfGo").onclick=async function(){
 try{
  var r=await api("POST","/api/admin/staff",{name:$("stfName").value,role:$("stfRole").value});
  $("stfMsg").className="msg ok";
  $("stfMsg").innerHTML="Token for <b>"+esc(r.name)+"</b> ("+esc(r.role)+") - copy it now, it is shown once:<br><code style='word-break:break-all'>"+esc(r.token)+"</code>";
  $("stfName").value="";loadStaffList();
 }catch(e){$("stfMsg").textContent=e.message;$("stfMsg").className="msg err"}
};
async function loadStaffList(){var r=await api("GET","/api/admin/staff");$("stfTbl").innerHTML="<tr><th>Name</th><th>Role</th><th>Scope</th><th>Created</th><th>Token</th><th></th></tr>"+r.items.map(function(s){
  return "<tr><td><b>"+esc(s.name)+"</b></td><td>"+esc(s.role)+"</td><td>"+esc([s.scope_state,s.scope_city].filter(Boolean).join("/")||"all")+"</td><td>"+esc((s.created_at||"").slice(0,10))+"</td>"+
   "<td>"+(s.active?'<span class="pill ok">active</span>':'<span class="pill warn">disabled</span>')+"</td>"+
   "<td>"+(s.active?'<button class="btn btn-ghost sm" data-stf="'+s.id+'">Disable</button>':"")+"</td></tr>";
 }).join("");
 $$("#stfTbl [data-stf]").forEach(function(b){b.onclick=async function(){if(!window.confirm("Disable this token?"))return;await api("POST","/api/admin/staff/"+b.getAttribute("data-stf")+"/disable",{});loadStaffList()}});
}

/* catalog */
async function loadCatalog(){
 var c=await api("GET","/api/admin/catalog");
 var sel=$("svcCat");sel.innerHTML=c.categories.map(function(x){return '<option value="'+esc(x.id)+'">'+esc(x.id)+"</option>"}).join("");
 $("catList").innerHTML=c.categories.map(function(cat){
  var nm;try{nm=JSON.parse(cat.names||"{}").en||cat.id}catch(e){nm=cat.id}
  var svcs=c.services.filter(function(s){return s.category_id===cat.id});
  return '<div class="note" style="background:#fff;border-color:#e4e9f2;color:inherit"><b>'+esc(nm)+'</b> <span class="mut">('+esc(cat.id)+", "+svcs.length+" services)</span>"+
   (svcs.length?"<ul style='margin:6px 0 0'>"+svcs.map(function(s){return "<li>"+esc(s.name)+(s.dept?" <span class='mut'>- "+esc(s.dept)+"</span>":"")+"</li>"}).join("")+"</ul>":"")+"</div>";
 }).join("")+"<p class='mut'>"+c.schemes.length+" schemes in the schemes table.</p>";
}
$("catGo").onclick=async function(){
 try{var r=await api("POST","/api/admin/catalog/category",{id:$("catId").value,name:$("catName").value,blurb:$("catBlurb").value,sort:$("catSort").value});
 $("catMsg").className="msg ok";$("catMsg").textContent=(r.created?"Category created: ":"Category updated: ")+r.id;loadCatalog()}
 catch(e){$("catMsg").textContent=e.message;$("catMsg").className="msg err"}
};
$("svcGo").onclick=async function(){
 try{var r=await api("POST","/api/admin/catalog/service",{category_id:$("svcCat").value,name:$("svcName").value,dept:$("svcDept").value,state:$("svcState").value,link:$("svcLink").value});
 $("svcMsg").className="msg ok";$("svcMsg").textContent="Service added (#"+r.id+")";$("svcName").value="";loadCatalog()}
 catch(e){$("svcMsg").textContent=e.message;$("svcMsg").className="msg err"}
};
$("schGo").onclick=async function(){
 try{var r=await api("POST","/api/admin/catalog/scheme",{slug:$("schSlug").value,name:$("schName").value,benefit:$("schBenefit").value,link:$("schLink").value,source:$("schSource").value});
 $("schMsg").className="msg ok";$("schMsg").textContent=(r.created?"Scheme created":"Scheme updated")+" (#"+r.id+")";loadCatalog()}
 catch(e){$("schMsg").textContent=e.message;$("schMsg").className="msg err"}
};

/* translations */
async function loadTranslations(){
 var r=await api("GET","/api/admin/translations");
 $("trTbl").innerHTML="<tr><th>Key</th><th>Lang</th><th>Text</th><th>Status</th></tr>"+(r.items.map(function(x){
  return "<tr><td>"+esc(x.key)+"</td><td>"+esc(x.lang)+"</td><td>"+esc(x.text)+"</td><td>"+esc(x.status)+"</td></tr>"}).join("")||'<tr><td colspan="4">No translations stored yet</td></tr>');
}
$("trGo").onclick=async function(){
 try{await api("POST","/api/admin/translations",{key:$("trKey").value,lang:$("trLang").value,text:$("trText").value});
 $("trMsg").className="msg ok";$("trMsg").textContent="Saved.";loadTranslations()}
 catch(e){$("trMsg").textContent=e.message;$("trMsg").className="msg err"}
};

/* settings */
async function loadSettings(){
 var s=await api("GET","/api/admin/settings");
 $("setBrand").value=s.brand_name||"";$("setShort").value=s.brand_short||"";
 $("setWa").value=s.wa_number||"";$("setWaStatus").value=s.whatsapp_status||"manual";
 $("setSupport").value=s.support_text||"";$("setRetention").value=s.data_retention_days||"";
 $("waState").innerHTML=s.whatsapp_cloud_configured
  ?"WhatsApp Cloud API: <b>configured</b> (env tokens present)."
  :"WhatsApp: <b>manual chat mode</b> - the homepage button opens a wa.me chat with the number below. Cloud API (Phase 7) is not connected; it needs Kamal's own business number, a Meta app and vault-collected tokens.";
}
$("setGo").onclick=async function(){
 try{
  await api("POST","/api/admin/settings",{brand_name:$("setBrand").value,brand_short:$("setShort").value,wa_number:$("setWa").value,whatsapp_status:$("setWaStatus").value,support_text:$("setSupport").value,data_retention_days:$("setRetention").value});
  $("setMsg").className="msg ok";$("setMsg").textContent="Saved. Homepage brand and WhatsApp button update from these values on next page load.";
 }catch(e){$("setMsg").textContent=e.message;$("setMsg").className="msg err"}
};

/* audit */
async function loadAudit(){
 var r=await api("GET","/api/admin/audit?limit=150");
 $("auditTbl").innerHTML="<tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr>"+(r.items.map(function(x){
  return "<tr><td>"+esc((x.ts||"").slice(0,19))+"</td><td>"+esc(x.actor)+"</td><td>"+esc(x.action)+"</td><td>"+esc(x.detail)+"</td></tr>"}).join("")||'<tr><td colspan="4">No audit entries yet</td></tr>');
}

boot();
})();
