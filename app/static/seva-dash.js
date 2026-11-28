/* Seva Setu India - citizen dashboard (Phase 3). Shares the session token (LS key "jt") with the complaint app. */
(function(){
"use strict";
const LS=(()=>{try{const s=window['local'+'Storage'];s.setItem('_t','1');s.removeItem('_t');return s}catch(e){const m={};return{getItem:k=>m[k]??null,setItem:(k,v)=>{m[k]=v},removeItem:k=>{delete m[k]}}}})();
const $=id=>document.getElementById(id);
let T=LS.getItem('jt')||'', LANG=LS.getItem('sdlang')||'hi', CATALOG=null, APPS=[], PROFILE={};

const I18N={
hi:{"notGov":"Seva Setu India ek private sahayata seva hai, sarkari website nahi.","nav.home":"होम","nav.complaints":"शिकायतें","nav.help":"मदद","logout":"लॉग आउट",
"login.title":"लॉगिन / साइन अप","login.help":"मोबाइल नंबर या ईमेल डालें। हम एक बार का कोड (OTP) भेजते हैं।","login.id":"मोबाइल नंबर या ईमेल","login.code":"OTP कोड","login.name":"आपका नाम (पहली बार)","login.send":"OTP भेजें","login.verify":"OTP से लॉगिन",
"tab.over":"सारांश","tab.apps":"आवेदन","tab.schemes":"योजना खोजें","tab.prof":"प्रोफ़ाइल",
"over.next":"आप क्या करना चाहेंगे?","over.newApp":"नया आवेदन शुरू करें","over.findScheme":"मेरे लिए योजनाएं खोजें","over.complaint":"शिकायत दर्ज करें","over.recent":"हाल के आवेदन",
"apps.title":"आपके आवेदन","apps.new":"+ नया","sch.title":"योजना खोजें","sch.help":"3 सवालों के जवाब दें - हम verified list से केंद्रीय योजनाएं मिलाते हैं। आवेदन से पहले official portal पर जरूर confirm करें।","sch.age":"आपकी उम्र","sch.occ":"काम","sch.any":"कोई भी","sch.farmer":"किसान","sch.student":"छात्र/छात्रा","sch.selfemp":"स्वरोज़गार","sch.unemp":"काम की तलाश","sch.senior":"वरिष्ठ नागरिक","sch.state":"राज्य / केंद्र शासित प्रदेश","sch.find":"योजनाएं खोजें",
"prof.title":"आपकी प्रोफ़ाइल","prof.lang":"पसंदीदा भाषा","prof.state":"राज्य / केंद्र शासित प्रदेश","prof.district":"ज़िला","prof.block":"ब्लॉक / तहसील","prof.pin":"पिन कोड","prof.age":"उम्र समूह","prof.occ":"काम","prof.salaried":"नौकरीपेशा","prof.other":"अन्य","prof.save":"प्रोफ़ाइल सेव करें",
"new.title":"नया आवेदन","new.help":"सेवा चुनें। आपका अनुरोध पहले Seva Setu में सेव होता है - आपकी मंज़ूरी के बिना कुछ भी किसी सरकारी portal पर नहीं जाता।","new.desc":"छोटा विवरण (optional)","new.create":"अनुरोध सेव करें",
"foot.privacy":"Privacy","foot.contact":"Contact","foot.disclaimer":"Disclaimer"},
en:{"notGov":"Seva Setu India is a private assistance service, not a government website.","nav.home":"Home","nav.complaints":"Complaints","nav.help":"Help","logout":"Logout",
"login.title":"Login / Sign up","login.help":"Enter your mobile number or email. We send a one-time code (OTP) to verify it is you.","login.id":"Mobile number or email","login.code":"OTP code","login.name":"Your name (first time)","login.send":"Send OTP","login.verify":"Verify & login",
"tab.over":"Overview","tab.apps":"Applications","tab.schemes":"Scheme finder","tab.prof":"Profile",
"over.next":"What would you like to do?","over.newApp":"Start a new application","over.findScheme":"Find schemes for me","over.complaint":"File a complaint","over.recent":"Recent applications",
"apps.title":"Your applications","apps.new":"+ New","sch.title":"Scheme finder","sch.help":"Answer 3 questions - we match you with central schemes from our verified list. Always confirm on the official portal before applying.","sch.age":"Your age","sch.occ":"Occupation","sch.any":"Any","sch.farmer":"Farmer","sch.student":"Student","sch.selfemp":"Self-employed","sch.unemp":"Looking for work","sch.senior":"Senior citizen","sch.state":"State / UT","sch.find":"Find schemes",
"prof.title":"Your profile","prof.lang":"Preferred language","prof.state":"State / UT","prof.district":"District","prof.block":"Block / Tehsil","prof.pin":"PIN code","prof.age":"Age group","prof.occ":"Occupation","prof.salaried":"Salaried","prof.other":"Other","prof.save":"Save profile",
"new.title":"New application","new.help":"Pick a service. We save your request in Seva Setu first - nothing goes to any government portal until you approve it.","new.desc":"Short description (optional)","new.create":"Save request",
"foot.privacy":"Privacy","foot.contact":"Contact","foot.disclaimer":"Disclaimer"}};
const t=k=>(I18N[LANG]&&I18N[LANG][k])||I18N.en[k]||k;
function applyI18n(){document.querySelectorAll('[data-t]').forEach(e=>{e.textContent=t(e.getAttribute('data-t'))});document.documentElement.lang=LANG;$('langT').textContent=LANG=='hi'?'EN':'हिं';}

/* Status labels: honest vocabulary. Pre-official = Seva Setu record only. Official only with verified ack (server enforces). */
const STATUSES=["request_received","documents_pending","documents_received","under_verification","form_preparation","awaiting_citizen_approval","ready_for_submission","submitted_to_portal","government_processing","additional_info_required","approved","rejected","completed"];
const OFFICIAL=new Set(["submitted_to_portal","government_processing","approved","rejected","completed"]);
const SLBL={
request_received:{en:"Request received",hi:"अनुरोध मिल गया"},
documents_pending:{en:"Documents pending",hi:"दस्तावेज़ बाकी"},
documents_received:{en:"Documents received",hi:"दस्तावेज़ मिल गए"},
under_verification:{en:"Under verification",hi:"जांच जारी"},
form_preparation:{en:"Form being prepared",hi:"फ़ॉर्म तैयार हो रहा"},
awaiting_citizen_approval:{en:"Waiting for your approval",hi:"आपकी मंज़ूरी बाकी"},
ready_for_submission:{en:"Ready for submission",hi:"जमा करने के लिए तैयार"},
submitted_to_portal:{en:"Submitted to official portal",hi:"Official portal पर जमा"},
government_processing:{en:"Government processing",hi:"सरकारी प्रक्रिया जारी"},
additional_info_required:{en:"More info needed",hi:"और जानकारी चाहिए"},
approved:{en:"Approved",hi:"स्वीकृत"},
rejected:{en:"Rejected",hi:"अस्वीकृत"},
completed:{en:"Completed",hi:"पूर्ण"}};
function slbl(s){const l=SLBL[s];return l?(LANG=='hi'?l.hi:l.en):s;}
function sbadge(s){
 if(s=='approved'||s=='completed')return'<span class="badge b-ok">'+slbl(s)+'</span>';
 if(s=='rejected')return'<span class="badge b-rej">'+slbl(s)+'</span>';
 if(OFFICIAL.has(s))return'<span class="badge b-off">'+slbl(s)+'</span>';
 if(s=='awaiting_citizen_approval'||s=='documents_pending'||s=='additional_info_required')return'<span class="badge b-warn">'+slbl(s)+'</span>';
 return'<span class="badge b-ssi">'+slbl(s)+'</span>';}
function honestNote(a){
 if(OFFICIAL.has(a.status))return LANG=='hi'?'Official: portal "'+a.status.replace(/_/g,'')+'" verified acknowledgement के साथ दर्ज।':'Official status, backed by a verified acknowledgement record.';
 return LANG=='hi'?'Seva Setu रिकॉर्ड - अभी किसी सरकारी portal पर भेजा नहीं गया।':'Saved in Seva Setu - not yet sent to any government portal.';}

async function api(m,p,b){const h={'Content-Type':'application/json'};if(T)h.Authorization='Bearer '+T;
 const r=await fetch(p,{method:m,headers:h,body:b?JSON.stringify(b):undefined});
 let d=null;try{d=await r.json()}catch(e){}
 if(r.status==401){throw{auth:true}}
 if(!r.ok)throw Object.assign(new Error('api'),d||{});
 return d;}

/* ---------- login ---------- */
function showLogin(){$('loginView').classList.remove('hide');$('dashView').classList.add('hide');$('logoutB').classList.add('hide');}
async function boot(){
 applyI18n();fillStates();
 if(!T){showLogin();return}
 try{
  PROFILE=await api('GET','/api/seva/profile');
  await loadCatalog();await loadApps();showDash();
 }catch(e){if(e&&e.auth){T='';LS.removeItem('jt');showLogin()}else{showLogin()}}
}
function showDash(){$('loginView').classList.add('hide');$('dashView').classList.remove('hide');$('logoutB').classList.remove('hide');renderAll();}

$('sendOtp').onclick=async()=>{
 const id=$('lid').value.trim();const m=$('lmsg');m.classList.remove('err');
 if(!id){m.textContent=LANG=='hi'?'नंबर या ईमेल डालें':'Enter your number or email';m.classList.add('err');return}
 try{const r=await api('POST','/api/otp/request',{phone:id});
  $('otpRow').classList.remove('hide');$('nameRow').classList.remove('hide');$('verifyOtp').classList.remove('hide');
  m.textContent=r.sent?(LANG=='hi'?'OTP भेज दिया गया':'OTP sent'):(r.note||'');
  if(r.dev_code)m.textContent+=' [dev code: '+r.dev_code+']';
 }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};
$('verifyOtp').onclick=async()=>{
 const m=$('lmsg');m.classList.remove('err');
 try{const r=await api('POST','/api/otp/verify',{phone:$('lid').value.trim(),code:$('lcode').value.trim(),name:$('lname').value.trim()});
  if(r&&r.token){T=r.token;LS.setItem('jt',T);boot()}
  else{m.textContent=LANG=='hi'?'गलत या expire हुआ कोड':'Wrong or expired code';m.classList.add('err')}
 }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};
$('logoutB').onclick=()=>{T='';LS.removeItem('jt');location.href='/'};
$('langT').onclick=()=>{LANG=LANG=='hi'?'en':'hi';LS.setItem('sdlang',LANG);applyI18n();renderAll()};

/* ---------- tabs ---------- */
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x==b));
 document.querySelectorAll('.tpane').forEach(p=>p.classList.add('hide'));
 $('tab-'+b.getAttribute('data-tab')).classList.remove('hide');
});

/* ---------- data ---------- */
async function loadCatalog(){if(!CATALOG)CATALOG=await api('GET','/api/seva/catalog');}
async function loadApps(){APPS=(await api('GET','/api/seva/applications')).items||[];}
function fillStates(){
 const states=["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal","Andaman and Nicobar Islands","Chandigarh","Dadra and Nagar Haveli and Daman and Diu","Delhi","Jammu and Kashmir","Ladakh","Lakshadweep","Puducherry"];
 ['qState','pState'].forEach(id=>{const s=$(id);if(!s.options.length||s.options.length<2)s.innerHTML='<option value="">--</option>'+states.map(x=>'<option>'+x+'</option>').join('')});
}

/* ---------- render ---------- */
function catName(id){const c=(CATALOG.categories||[]).find(c=>c.slug==id||c.id==id);if(!c)return id;const n=c.names||{};return n[LANG]||n.en||n.hi||id;}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderAll(){renderOver();renderApps();renderSchemes();renderProf();}

function renderOver(){
 $('hello').textContent=(LANG=='hi'?'नमस्ते':'Namaste')+(PROFILE&&PROFILE.district?', '+PROFILE.district:'')+'!';
 const off=APPS.filter(a=>OFFICIAL.has(a.status)).length,prog=APPS.length-off;
 $('stats').innerHTML=
  '<div class="stat"><b>'+APPS.length+'</b><span>'+(LANG=='hi'?'कुल आवेदन':'Total applications')+'</span></div>'+
  '<div class="stat"><b>'+prog+'</b><span>'+(LANG=='hi'?'Seva Setu में':'In Seva Setu')+'</span></div>'+
  '<div class="stat"><b>'+off+'</b><span>'+(LANG=='hi'?'Official (verified)':'Official (verified)')+'</span></div>';
 $('recentList').innerHTML=APPS.length?APPS.slice(0,3).map(appRow).join(''):'<div class="empty">'+(LANG=='hi'?'अभी कोई आवेदन नहीं। "नया आवेदन" से शुरू करें।':'No applications yet. Start with "New application".')+'</div>';
 bindRows($('recentList'));
}
function appRow(a){
 return '<div class="appitem" data-ref="'+esc(a.ref_no)+'"><div class="top"><div><div class="ttl">'+esc(a.title||catName(a.category_id))+'</div>'+
 '<div class="ref">'+esc(a.ref_no)+' · '+esc(catName(a.category_id))+'</div></div>'+sbadge(a.status)+'</div>'+
 '<div class="honest">'+honestNote(a)+'</div></div>';
}
function renderApps(){
 $('appDetail').classList.add('hide');$('appList').classList.remove('hide');
 $('appList').innerHTML=APPS.length?APPS.map(appRow).join(''):'<div class="empty">'+(LANG=='hi'?'अभी कोई आवेदन नहीं।':'No applications yet.')+'</div>';
 bindRows($('appList'));
}
function bindRows(root){root.querySelectorAll('.appitem').forEach(el=>el.onclick=()=>openApp(el.getAttribute('data-ref')));}
async function openApp(ref){
 let a;try{a=await api('GET','/api/seva/applications/'+encodeURIComponent(ref))}catch(e){return}
 $('appList').classList.add('hide');const d=$('appDetail');d.classList.remove('hide');
 const hist=(a.history||[]).map(h=>'<div class="ev"><div class="st">'+slbl(h.status)+'</div><div class="ts">'+esc(h.ts||'')+(h.note?' · '+esc(h.note):'')+'</div></div>').join('');
 const subs=(a.submissions||[]).map(s=>'<div class="subnote'+(s.verified?'':' unv')+'">'+
  (s.verified?(LANG=='hi'?'✓ Verified submission':'✓ Verified submission'):(LANG=='hi'?'Unverified (manual note)':'Unverified (manual note)'))+
  ' · '+esc(s.portal||'')+(s.ack_no?' · Ack: '+esc(s.ack_no):'')+(s.ts?' · '+esc(s.ts):'')+'</div>').join('');
 d.innerHTML='<button class="btn btn-ghost" id="backL">&larr; '+(LANG=='hi'?'सूची':'Back')+'</button>'+
  '<div class="card"><h3>'+esc(a.title||catName(a.category_id))+'</h3>'+
  '<div class="ref" style="font-family:ui-monospace,monospace;color:var(--mut);font-size:13px">'+esc(a.ref_no)+' · '+esc(catName(a.category_id))+'</div>'+
  '<div style="margin:10px 0">'+sbadge(a.status)+'</div><div class="honest">'+honestNote(a)+'</div>'+subs+
  '<h3 style="margin-top:16px">'+(LANG=='hi'?'इतिहास':'Timeline')+'</h3><div class="tl">'+hist+'</div></div>';
 $('backL').onclick=renderApps;
}

/* ---------- new application ---------- */
let newCat='';
function openNew(){
 const g=$('catGrid');newCat='';
 g.innerHTML=(CATALOG.categories||[]).map(c=>'<button class="cat" data-c="'+esc(c.slug||c.id)+'">'+esc(catName(c.slug||c.id))+'</button>').join('');
 g.querySelectorAll('.cat').forEach(b=>b.onclick=()=>{g.querySelectorAll('.cat').forEach(x=>x.classList.toggle('on',x==b));newCat=b.getAttribute('data-c')});
 $('newTitle').value='';$('newMsg').textContent='';$('newSheet').hidden=false;
}
$('newAppB').onclick=openNew;$('qNewApp').onclick=()=>{document.querySelector('[data-tab="apps"]').click();openNew()};
$('newClose').onclick=()=>{$('newSheet').hidden=true};
$('newCreate').onclick=async()=>{
 const m=$('newMsg');m.classList.remove('err');
 if(!newCat){m.textContent=LANG=='hi'?'पहले सेवा चुनें':'Pick a service first';m.classList.add('err');return}
 try{
  const r=await api('POST','/api/seva/applications',{category_id:newCat,title:$('newTitle').value.trim()||catName(newCat)});
  if(r.ok){$('newSheet').hidden=true;await loadApps();renderOver();renderApps();
   document.querySelector('[data-tab="apps"]').click();openApp(r.ref_no)}
  else{m.textContent=r.error||'Failed';m.classList.add('err')}
 }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};

/* ---------- scheme finder ---------- */
function schemeMatch(s){
 const age=parseInt($('qAge').value)||0,occ=$('qOcc').value,st=$('qState').value;
 const el=s.eligibility||{};let score=0,ok=true;
 if(s.state&&s.state!='all'&&st&&s.state!=st)ok=false;
 if(el.age_min&&age&&age<el.age_min)ok=false;
 if(el.age_max&&age&&age>el.age_max)ok=false;
 if(el.occupation&&occ){ok=el.occupation.indexOf(occ)>=0;if(!ok)return{ok:false,score:0};score+=2}
 if(el.occupation&&!occ)score+=0;
 if(!el.occupation)score+=1;
 return{ok:ok,score:score};
}
function renderSchemes(list){
 const arr=list||((CATALOG&&CATALOG.schemes)||[]);
 $('schemeList').innerHTML=arr.length?arr.map(s=>{
  const n=(s.names||{});const docs=(s.docs||[]).map(esc).join(', ');
  const note=s.eligibility&&s.eligibility.note?'<div class="docs">'+esc(s.eligibility.note)+'</div>':'';
  return '<div class="schcard"><h4>'+esc(n[LANG]||n.en||s.name)+'</h4><div class="ben">'+esc(s.benefit||'')+'</div>'+note+
   (docs?'<div class="docs">'+(LANG=='hi'?'दस्तावेज़':'Documents')+': '+docs+'</div>':'')+
   '<a class="btn btn-navy" style="margin-top:10px" href="'+esc(s.link)+'" target="_blank" rel="noopener">'+(LANG=='hi'?'Official portal खोलें':'Open official portal')+'</a>'+
   '<div class="src">'+(LANG=='hi'?'स्रोत':'Source')+': '+esc(s.source||s.link)+' · '+(LANG=='hi'?'जाँचा गया':'verified')+' '+esc(s.last_verified||'')+'</div></div>';
 }).join(''):'<div class="empty">'+(LANG=='hi'?'कोई योजना नहीं मिली - फ़िल्टर बदलकर देखें':'No schemes matched - try changing your answers')+'</div>';
}
$('findB').onclick=()=>{
 const ms=(CATALOG.schemes||[]).map(s=>({s:s,m:schemeMatch(s)})).filter(x=>x.m.ok);
 ms.sort((a,b)=>b.m.score-a.m.score);renderSchemes(ms.map(x=>x.s));
};
$('qScheme').onclick=()=>{document.querySelector('[data-tab="schemes"]').click()};

/* ---------- profile ---------- */
function renderProf(){
 $('pLang').value=PROFILE.preferred_lang||LANG;$('pState').value=PROFILE.state||'';
 $('pDist').value=PROFILE.district||'';$('pBlock').value=PROFILE.block||'';
 $('pPin').value=PROFILE.pincode||'';$('pAge').value=PROFILE.age_group||'';$('pOcc').value=PROFILE.occupation||'';
}
$('saveProf').onclick=async()=>{
 const m=$('pmsg');m.classList.remove('err');
 try{
  PROFILE=await api('POST','/api/seva/profile',{preferred_lang:$('pLang').value,state:$('pState').value,district:$('pDist').value.trim(),block:$('pBlock').value.trim(),pincode:$('pPin').value.trim(),age_group:$('pAge').value,occupation:$('pOcc').value});
  m.textContent=LANG=='hi'?'प्रोफ़ाइल सेव हो गई':'Profile saved';renderOver();
 }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};

boot();
})();
